"""Finish expired positions in stopped PAPER ledgers using exact official results.

This command does not start a feed, strategy, new treasury or venue order. It
backs up the original economic record, appends official settlements and leaves
the normal restart inventory check in force.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid
import zipfile

from TOOL_RACK_PAPER import default_output_root, global_lease_path
from strategy_core.marketdata.kalshi_public import PublicMarketClient
from strategy_core.paper_execution import PaperExecutioner
from strategy_core.paper_feed import official_result_from_receipt
from strategy_core.paper_runtime import GlobalPaperLease, atomic_json, plain


RECONCILIATION_REVISION = "TOOL_RACK_STOPPED_PAPER_FINALITY_V1_20261028"
_BACKUP_FILES = ("RUN_MANIFEST.json", "RUN_SUMMARY.json", "STATUS.json",
                 "PAPER_LEDGER.json", "ERROR.json")


def _write_json(path: Path, value: object) -> None:
    if not atomic_json(path, value, required=True):
        raise OSError("RECONCILIATION_EVIDENCE_OR_PROJECTION_UNAVAILABLE:" + str(path))


def _read_stopped_status(run: Path) -> dict:
    status = json.loads((run / "STATUS.json").read_text(encoding="utf-8"))
    if status.get("state") != "STOPPED" or status.get("mode") != "PAPER":
        raise ValueError("RECONCILIATION_REQUIRES_STOPPED_PAPER_RUN")
    return status


def resolve_runs(runs: list[Path], pointers: tuple[Path, ...]) -> list[Path]:
    """Resolve both normal restart pointers without changing either one."""
    targets = list(runs)
    for pointer in pointers:
        if not pointer.exists():
            continue
        value = json.loads(pointer.read_text(encoding="utf-8"))
        if not isinstance(value.get("run_dir"), str) or not value["run_dir"].strip():
            raise ValueError("PREVIOUS_RUN_POINTER_INVALID:" + str(pointer))
        if value.get("mode", "PAPER") != "PAPER":
            raise ValueError("PREVIOUS_RUN_POINTER_NOT_PAPER:" + str(pointer))
        targets.append(Path(value["run_dir"]))
    resolved = list(dict.fromkeys(path.expanduser().resolve() for path in targets))
    if not resolved:
        raise ValueError("NO_PREVIOUS_PAPER_RUN_FOUND: use --run with the stopped run folder")
    for path in resolved:
        if not path.is_dir():
            raise ValueError("PREVIOUS_RUN_FOLDER_UNAVAILABLE:" + str(path))
    return resolved


def _backup(run: Path, attempt: Path, reviewed: dict) -> Path:
    """Back up verified journal bytes and projections before any settlement."""
    paths = sorted((run / "paper_journal").glob("*.json"))
    paths += [run / name for name in _BACKUP_FILES if (run / name).is_file()]
    manifest = {"revision": RECONCILIATION_REVISION, "mode": "PAPER",
                "journal_seq": reviewed["seq"], "journal_sha256": reviewed["sha256"],
                "files": {}}
    destination = attempt / "before.zip"
    with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths:
            content = path.read_bytes()
            name = path.relative_to(run).as_posix()
            manifest["files"][name] = hashlib.sha256(content).hexdigest()
            archive.writestr(name, content)
        archive.writestr("BACKUP_MANIFEST.json", json.dumps(manifest, sort_keys=True, indent=2))
    with destination.open("r+b") as handle:
        os.fsync(handle.fileno())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("RECONCILIATION_BACKUP_VERIFICATION_FAILED")
    return destination


def _economics(state: dict) -> dict:
    return {**{key: state[key] for key in
               ("starting_cash", "cash", "realized_gross", "realized_net", "fees_paid")},
            "open_positions": len(state["positions"]), "events": len(state["events"])}


def _publish_stopped_projections(run: Path, status: dict, state: dict,
                                 report: dict, now_ts: float) -> None:
    final = {**status, "mode": "PAPER", "state": "STOPPED", "updated_at": now_ts,
             "original_stop_reason": status.get("original_stop_reason", status.get("stop_reason")),
             "stop_reason": ("POST_RUN_OFFICIAL_FINALITY_RECONCILED_FLAT" if not state["positions"]
                             else "POST_RUN_OFFICIAL_FINALITY_STILL_UNRESOLVED"),
             "positions": state["positions"], "events": state["events"][-100:],
             "unresolved_inventory_count": len(state["positions"]),
             "ledger_seq": state["journal_seq"], "ledger_sha256": state["journal_sha256"],
             "final_ledger_seq": state["journal_seq"],
             "final_ledger_sha256": state["journal_sha256"],
             "post_run_reconciliation": {key: report[key] for key in
                 ("revision", "status", "report_path", "backup_path", "started_at", "completed_at", "settled_position_ids")}}
    for key in ("cash", "realized_gross", "realized_net", "fees_paid"):
        final[key] = state[key]
    _write_json(run / "PAPER_LEDGER.json", state)
    _write_json(run / "STATUS.json", final)
    _write_json(run / "RUN_SUMMARY.json", final)


def _reconcile_one(run: Path, client: PublicMarketClient, now_ts: float) -> dict:
    print("Verifying stopped PAPER journal: " + str(run), flush=True)
    status = _read_stopped_status(run)
    reviewed = PaperExecutioner.inspect_journal(run)
    if reviewed["state"] is None or reviewed["records"] == 0:
        raise ValueError("RECONCILIATION_REQUIRES_EXISTING_COMMITTED_JOURNAL")
    if reviewed["uncommitted_temporary_files"]:
        raise ValueError("UNCOMMITTED_JOURNAL_FILES_REQUIRE_REVIEW")
    contracts: dict[str, float] = {}
    for position in reviewed["state"]["positions"].values():
        close = float(position["close_ts"])
        if not math.isfinite(close) or close <= 0 or close > now_ts:
            raise ValueError("UNEXPIRED_POSITION_REMAINS_UNRESOLVED:" + position["ticker"])
        if position["ticker"] in contracts and contracts[position["ticker"]] != close:
            raise ValueError("HELD_CONTRACT_CLOSE_CONFLICT")
        contracts[position["ticker"]] = close

    # The per-run writer lock is acquired before backup and retained until all
    # commits/projections are complete. Expected head checks close the race
    # between initial inspection and opening this settlement-only writer.
    with PaperExecutioner(run, settlement_only=True,
                          expected_journal_sha256=reviewed["sha256"],
                          expected_journal_seq=reviewed["seq"]) as writer:
        _read_stopped_status(run)
        print(f"Verified {reviewed['seq']} journal records; backing up the original economic record.", flush=True)
        attempt_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
        attempt = run / "reconciliation" / attempt_id
        attempt.mkdir(parents=True, exist_ok=False)
        report = {"revision": RECONCILIATION_REVISION, "mode": "PAPER",
                  "run_dir": str(run), "started_at": now_ts,
                  "status": "PREPARING", "venue_order_authority": "NONE",
                  "report_path": str(attempt / "report.json"),
                  "backup_path": str(attempt / "before.zip"),
                  "before_journal_seq": reviewed["seq"],
                  "before_journal_sha256": reviewed["sha256"],
                  "before": _economics(reviewed["state"]),
                  "settled_position_ids": [], "official_results": [],
                  "repair_source_sha256": {
                      "TOOL_RACK_RECONCILE.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "strategy_core/paper_execution.py": hashlib.sha256(
                          (Path(__file__).resolve().parent / "strategy_core/paper_execution.py").read_bytes()).hexdigest()}}
        backup = _backup(run, attempt, reviewed)
        report["backup_sha256"] = hashlib.sha256(backup.read_bytes()).hexdigest()
        _write_json(attempt / "report.json", report)
        print("Original economic backup verified.", flush=True)
        responses = []
        results = []
        try:
            # Validate every response before committing the first settlement.
            # Unavailable/provisional results never become assumed zeroes.
            for ticker, close_ts in contracts.items():
                print("Checking exact official result: " + ticker, flush=True)
                receipt = client.market(ticker)
                responses.append(plain(receipt))
                _write_json(attempt / "official_receipts.json", responses)
                result = official_result_from_receipt(ticker, close_ts, receipt)
                if result is None:
                    raise ValueError("OFFICIAL_FINAL_RESULT_NOT_AVAILABLE:" + ticker)
                results.append(result)
            for result in results:
                committed = writer.settle(result)
                report["official_results"].append(plain(result))
                report["settled_position_ids"].extend(
                    row.position_id for row in committed if row.status == "SETTLED")
            state = writer.snapshot()
            verified = PaperExecutioner.inspect_journal(run)
            if (verified["sha256"] != state["journal_sha256"]
                    or verified["seq"] != state["journal_seq"]):
                raise ValueError("RECONCILIATION_FINAL_JOURNAL_BOUNDARY_MISMATCH")
            report.update({"status": "COMPLETE_FLAT" if not state["positions"] else "UNRESOLVED",
                           "after_journal_seq": verified["seq"],
                           "after_journal_sha256": verified["sha256"], "after": _economics(state),
                           "completed_at": time.time()})
            _publish_stopped_projections(run, status, state, report, report["completed_at"])
            _write_json(attempt / "report.json", report)
            return report
        except Exception as exc:
            # A successful settlement cannot be rolled back because a later
            # projection is locked. Keep the committed boundary explicit; a
            # rerun reopens that boundary and cannot charge or settle twice.
            report.update({"status": "BLOCKED", "error_type": type(exc).__name__,
                           "error": str(exc)[:500], "completed_at": time.time()})
            try:
                verified = PaperExecutioner.inspect_journal(run)
                report.update({"after_journal_seq": verified["seq"],
                               "after_journal_sha256": verified["sha256"],
                               "after": _economics(verified["state"])})
                _write_json(attempt / "report.json", report)
            except Exception:
                pass
            raise RuntimeError(str(exc) + "; reconciliation evidence: " + str(attempt)) from exc


def reconcile_runs(runs: list[Path], *, pointers: tuple[Path, ...] = (),
                   lease_path: Path | None = None, client: PublicMarketClient | None = None,
                   now_ts: float | None = None) -> list[dict]:
    """Global lease applies to direct calls as well as the Windows launcher."""
    now = time.time() if now_ts is None else now_ts
    if not math.isfinite(now) or now <= 0:
        raise ValueError("FINITE_RECONCILIATION_TIME_REQUIRED")
    with GlobalPaperLease(lease_path or global_lease_path()):
        targets = resolve_runs(runs, pointers)
        public = client if client is not None else PublicMarketClient(timeout=5.0)
        return [_reconcile_one(run, public, now) for run in targets]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, help="An explicit stopped PAPER run folder; otherwise check both last-run pointers.")
    parser.add_argument("--output-root", type=Path, default=default_output_root())
    args = parser.parse_args(argv)
    lease = global_lease_path()
    pointers = (() if args.run is not None else
                (lease.with_name("paper_last_run.json"), args.output_root.expanduser() / "LAST_RUN.json"))
    try:
        reports = reconcile_runs([args.run] if args.run is not None else [],
                                 pointers=pointers, lease_path=lease)
        for report in reports:
            print("\n" + report["status"] + ": " + report["run_dir"])
            print(f"Positions settled: {len(report['settled_position_ids'])}; unresolved: {report['after']['open_positions']}")
            print(f"Original run cash ${float(report['after']['cash']):.4f}; net ${float(report['after']['realized_net']):.4f}")
            print("Verified backup: " + report["backup_path"])
            print("Report: " + report["report_path"])
        if any(report["status"] != "COMPLETE_FLAT" for report in reports):
            return 2
        print("\nReconciliation complete. You can now run 01_START_TOOL_RACK_PAPER_90M.cmd.")
        print("The normal restart check will still verify the previous committed inventory.")
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(f"PAPER reconciliation stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("No inventory bypass was applied. Keep the original run and review this message.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
