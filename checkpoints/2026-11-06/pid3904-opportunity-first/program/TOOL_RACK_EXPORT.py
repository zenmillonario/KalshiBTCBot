"""Export a stopped Tool Rack PAPER run with a verified economic journal."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile
from typing import Any, Mapping

from TOOL_RACK_PAPER import default_output_root
from strategy_core.paper_execution import PaperExecutioner


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()



def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _select(source: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    row = _mapping(source)
    return {key: row.get(key) for key in keys if key in row}


def _top_book(book: Any) -> dict[str, Any]:
    row = _mapping(book)
    return {
        **_select(row, ("ticker", "quote_id", "observed_ts", "exchange_ts", "close_ts",
                        "current", "entry_allowed", "yes_sell_allowed", "no_sell_allowed")),
        "yes_bids_top": list(row.get("yes_bids") or ())[:5],
        "no_bids_top": list(row.get("no_bids") or ())[:5],
    }


def _compact_intent(intent: Any) -> dict[str, Any] | None:
    row = _mapping(intent)
    if not row:
        return None
    md = _mapping(row.get("metadata"))
    evidence = _mapping(md.get("commander_physical_evidence"))
    return {
        **_select(row, ("tool", "territory_id", "lane", "side", "action", "opportunity_id",
                        "max_price", "size_tier", "reason", "source_time", "expires_when")),
        "metadata": {
            **_select(md, ("commander_primary_candidate", "commander_candidate_family",
                           "physical_mission_id", "position_role", "floor_policy")),
            "commander_physical_evidence": dict(evidence),
            "entry_geometry": _select(md.get("entry_geometry"), (
                "epoch_ms", "btc_price", "ema9", "ema30", "ema_gap", "range60", "range180",
                "arc_id", "arc_direction", "arc_phase", "arc_start_ms", "arc_extreme_ms",
                "arc_age_sec", "arc_amplitude", "btc_change30", "btc_change60",
                "ema9_change30", "ema9_change60", "comparison_arc", "parent_direction")),
        },
    }


def _compact_decision(decision: Any) -> dict[str, Any]:
    row = _mapping(decision)
    custody = _mapping(row.get("custody_review"))
    qualification = _mapping(custody.get("qualification"))
    return {
        **_select(row, ("action", "reason")),
        "intent": _compact_intent(row.get("intent")),
        "custody_update": _select(row.get("custody_update"),
                                  ("position_id", "previous_state", "state", "reason", "reviewed_at")),
        "custody_review": {
            **_select(custody, ("action", "reason", "hard_exit", "next_state")),
            "qualification": _select(qualification, (
                "position_id", "action", "reason", "age_seconds", "seconds_left",
                "current_executable_bid", "opening_executable_bid", "developed_loss",
                "lazarus_qualified", "maturity_qualified", "confirmed_opposing_handoff_exit")),
        } if custody else None,
    }


def _compact_decisions(rows: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in rows or ():
        row = _mapping(raw)
        item = {"scope": row.get("scope"), "position_id": row.get("position_id"),
                "decision": _compact_decision(row.get("decision"))}
        floors = []
        for floor in row.get("floors") or ():
            floors.append(_select(floor, ("position_id", "ticker", "side", "quote_id", "bid", "peak_bid",
                                          "floor_bid", "armed", "breached", "reason", "full_quantity_visible")))
        if floors:
            item["floors"] = floors
        receipt = _mapping(row.get("receipt"))
        if receipt:
            item["receipt"] = _select(receipt, ("status", "reason", "position_id", "price", "bid", "qty",
                                                      "fees", "gross_pnl", "net_pnl", "event"))
        result.append(item)
    return result


def _compact_mountain(value: Any) -> dict[str, Any]:
    row = _mapping(value)
    diagnostics = _mapping(row.get("diagnostics"))
    parent = _mapping(row.get("parent_structure"))
    result = _select(row, (
        "qualified_alternating_mountain", "owner_side", "current_arc_id", "edge_id",
        "terminal_evidence_qualified", "primary_collection_terminal_qualified",
        "mature_edge", "edge_window_active", "stall", "hesitation", "failed_reextension",
        "meaningful_retreat", "strong_active_release", "spent_edge", "owner_extreme_btc",
        "owner_price_gap", "retreat_dollars", "contact_width", "source_ms", "quality"))
    result["current_motion"] = row.get("current_motion")
    result["slowdown"] = row.get("slowdown")
    result["return_leg_reference"] = row.get("return_leg_reference") or diagnostics.get("return_leg_reference")
    result["parent_structure"] = _select(parent, (
        "parent_id", "parent_side", "parent_age_s", "parent_amplitude", "parent_terminal_ready",
        "parent_turning_or_flat", "slow_rolling_parent", "extended_parent", "child_arc_count"))
    result["diagnostics"] = _select(diagnostics, ("current_age_s", "phase", "reason"))
    return result


def _compact_cross(value: Any) -> dict[str, Any]:
    row = _mapping(value)
    lifecycle = _mapping(row.get("gap_lifecycle"))
    return {
        **_select(row, ("source_ms", "current_signed_gap_btc", "current_side", "current_arc_id",
                        "touching_spine", "observed_cross_count", "current_leg_cross_count",
                        "continued_on_latest_cross_side")),
        "gap_lifecycle": dict(lifecycle),
        "latest_observed_cross": _select(row.get("latest_observed_cross"),
                                         ("direction", "known_source_ms", "observed_continuously")),
    }


def _compact_decision_record(row: Mapping[str, Any], *, kind: str) -> dict[str, Any]:
    md = _mapping(row.get("physical_metadata"))
    source = _mapping(row.get("source_status"))
    current = _mapping(md.get("current_geometry"))
    tp = md.get("tp_geometry") or md.get("contract_value_context")
    rack = _mapping(row.get("rack"))
    adviser = rack.get("commander_intents") or rack.get("intents") or ()
    return {
        "sequence": row.get("sequence"), "now_ts": row.get("now_ts"), "compact_kind": kind,
        "market": _select(row.get("market"), ("ticker", "open_ts", "close_ts", "status", "title",
                                                    "target", "target_source")),
        "native_book": _top_book(row.get("native_book")),
        "source_health": _select(source, ("btc_current", "btc_geometry_age_seconds", "book_current",
                                                    "entry_quote_available", "source_error", "discovery_error")),
        "physical": _select(row.get("physical"), (
            "ema9_direction", "ema30_direction", "ema_pair_parallel", "directional_residence",
            "rolling_mountain_repetitions", "contracts_persistent", "alternating_mountain",
            "rolling_mountain", "mountain_direction", "qualified_heist", "compression_unresolved",
            "rail_launch_qualified", "rail_launch_side", "parent_extended", "parent_slow_rolling",
            "parent_terminal_ready", "release_candidate_side", "release_handoff_confirmed", "release_side")),
        "current_geometry": _select(current, (
            "epoch_ms", "btc_price", "ema9", "ema30", "ema_gap", "range60", "range180",
            "btc_change6", "btc_change9", "btc_change30", "btc_change60",
            "ema9_change6", "ema9_change30", "ema9_change60", "arc_id", "arc_direction",
            "arc_phase", "arc_start_ms", "arc_extreme_ms", "arc_age_sec", "arc_amplitude",
            "comparison_arc", "parent_direction", "measurement_source", "observed_history_seconds")),
        "mountain": _compact_mountain(md.get("mountain")),
        "ema9_ema30_cross_context": _compact_cross(md.get("ema9_ema30_cross_context")),
        "tp_geometry": dict(_mapping(tp)),
        "commander_strategy": dict(_mapping(md.get("commander_strategy"))),
        "position_inventory": md.get("position_inventory"),
        "available_paper_cash": md.get("available_paper_cash"),
        "adviser_intents": [_compact_intent(x) for x in adviser if _compact_intent(x) is not None],
        "decisions": _compact_decisions(row.get("decisions")),
        "ledger_seq": row.get("ledger_seq"),
    }


def _hot_decision_row(row: Mapping[str, Any]) -> bool:
    for raw in row.get("decisions") or ():
        decision = _mapping(_mapping(raw).get("decision"))
        if str(decision.get("action") or "").upper() in {"ENTER", "EXIT", "RELAY"}:
            return True
        if _mapping(raw).get("receipt"):
            return True
    return False


def _decision_state_signature(row: Mapping[str, Any]) -> tuple[Any, ...]:
    md = _mapping(row.get("physical_metadata")); mountain = _mapping(md.get("mountain"))
    gap = _mapping(_mapping(md.get("ema9_ema30_cross_context")).get("gap_lifecycle"))
    market = _mapping(row.get("market"))
    return (market.get("ticker"), mountain.get("owner_side"), mountain.get("current_arc_id"),
            bool(mountain.get("terminal_evidence_qualified")), bool(mountain.get("mature_edge")),
            bool(mountain.get("edge_window_active")), bool(mountain.get("primary_collection_terminal_qualified")),
            gap.get("stage"), gap.get("current_side"), len(md.get("position_inventory") or ()))


def _write_compact_decisions(archive: zipfile.ZipFile, source: Path, arcname: str) -> dict[str, Any]:
    seen = kept = event_rows = bad = state_rows = 0
    last_sample_ts = -1e30
    last_signature: tuple[Any, ...] | None = None
    with source.open("r", encoding="utf-8", errors="replace") as src, archive.open(arcname, "w", force_zip64=True) as dst:
        for raw in src:
            seen += 1
            try:
                row = json.loads(raw)
            except Exception:
                bad += 1
                continue
            ts = row.get("now_ts")
            hot = _hot_decision_row(row)
            sample = isinstance(ts, (int, float)) and float(ts) - last_sample_ts >= 1.0
            signature = _decision_state_signature(row)
            state_change = signature != last_signature
            if not (hot or sample or state_change):
                continue
            kind = "EVENT" if hot else "STATE_CHANGE" if state_change and not sample else "1S_SAMPLE"
            compact = _compact_decision_record(row, kind=kind)
            dst.write((json.dumps(compact, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8"))
            kept += 1
            if hot:
                event_rows += 1
            if state_change:
                state_rows += 1
            if sample and isinstance(ts, (int, float)):
                last_sample_ts = float(ts)
            last_signature = signature
    return {"decision_rows_scanned": seen, "decision_rows_kept": kept, "event_rows_kept": event_rows,
            "state_change_rows_kept": state_rows, "bad_json_rows": bad, "sample_seconds": 1.0,
            "full_decisions_included": False, "projection_revision": "COMPACT_DECISIONS_V2_SELECTED_FIELDS"}

def export_run(run: Path, output: Path | None = None, *, compact: bool = False) -> Path:
    run = run.expanduser().resolve()
    status = json.loads((run / "STATUS.json").read_text(encoding="utf-8"))
    if status.get("state") != "STOPPED":
        raise ValueError("Stop the PAPER run before making its final diagnostic archive.")
    checked = PaperExecutioner.inspect_journal(run)
    if not checked["records"] or checked["state"] is None:
        raise ValueError("A committed PAPER journal is required for a verified export.")
    allowed = {"RUN_MANIFEST.json", "RUN_SUMMARY.json", "STATUS.json", "PAPER_LEDGER.json",
               "ERROR.json", "physical_geometry.jsonl", "market_data_source.jsonl", "mission_history.jsonl",
               "console.log", "quote_echo_shadow.jsonl"}
    if not compact:
        allowed.add("decisions.jsonl")
    paths = sorted([p for p in run.iterdir() if p.is_file() and p.name in allowed] +
                   list((run / "paper_journal").glob("*.json")) +
                   [p for p in (run / "reconciliation").glob("*/*")
                    if p.is_file() and p.name in ("report.json", "official_receipts.json", "before.zip")])
    if output is None:
        output = run.parent / (run.name + ("_COMPACT_FORENSICS.zip" if compact else "_DIAGNOSTICS.zip"))
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError("Choose another archive path; an existing diagnostic archive is never replaced.")
    manifest = {"mode": "PAPER", "run_id": run.name,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "journal_verified": True, "journal_seq": checked["seq"],
                "journal_sha256": checked["sha256"], "compact": bool(compact),
                "files": {p.relative_to(run).as_posix(): _sha256_file(p) for p in paths}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in paths:
            archive.write(path, f"{run.name}/{path.relative_to(run).as_posix()}")
        if compact:
            decisions = run / "decisions.jsonl"
            if not decisions.is_file():
                raise FileNotFoundError(f"decisions.jsonl missing: {decisions}")
            compact_name = f"{run.name}/decisions_compact_1s.jsonl"
            manifest["compact_decisions"] = _write_compact_decisions(archive, decisions, compact_name)
        archive.writestr(f"{run.name}/EXPORT_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-root", type=Path, default=default_output_root())
    parser.add_argument("--compact", action="store_true",
                        help="Exclude multi-gigabyte raw decisions and include a 1-second selected-field forensic stream.")
    args = parser.parse_args(argv)
    if args.run is None:
        latest = json.loads((args.output_root / "LAST_RUN.json").read_text(encoding="utf-8"))
        args.run = Path(latest["run_dir"])
    print(export_run(args.run, args.output, compact=args.compact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
