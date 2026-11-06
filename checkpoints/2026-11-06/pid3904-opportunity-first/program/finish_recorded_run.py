"""Replay one closed PAPER recording and make one unsampled results ZIP.

The selected interpreter is also the replay interpreter. Incomplete recordings
still receive a clearly failed diagnostic archive; they never become accepted
replay input. No credentials are copied and no network operation is needed.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import tempfile
import zipfile

from bounded_tape import TapeError, iter_tape
from capture_session import (CAPTURE_DIRECTORY, ENGINE_OUTPUT_FILES, INVENTORY_NAME,
                             STATUS_NAME, TAPE_NAME, verify_engine_inventory, write_json)
from engine_replay import (ROOT, SOURCE_ROOT, ReplayMismatch, file_sha256, replay,
                           verify_bundled_source)
from run_validation import network_forbidden
from strategy_core.paper_execution import PaperExecutioner
from strategy_core.paper_runtime import GlobalPaperLease, source_manifest
from TOOL_RACK_PAPER import default_output_root, global_lease_path


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _recording_header(run_dir):
    header, calls = iter_tape(run_dir / CAPTURE_DIRECTORY / TAPE_NAME,
                              expected_source_hashes=verify_bundled_source())
    calls.close()
    for name, expected in header.get("recorder_source_hashes", {}).items():
        relative = Path(name)
        if (relative.is_absolute() or ".." in relative.parts or "\\" in name
                or not (ROOT / relative).is_file() or file_sha256(ROOT / relative) != expected):
            raise TapeError("RECORDER_PACKAGE_DIFFERS_FROM_CAPTURE:" + str(name))
    if not header.get("recorder_source_hashes"):
        raise TapeError("LIVE_CAPTURE_RECORDER_PROVENANCE_MISSING")
    return header


def _export_capsule(run_dir, replay_parent, report_path, destination, *, accepted):
    """Write and verify a complete allowlisted capsule, then publish atomically."""
    from CHECK_TOOL_RACK_PAPER import PACKAGE_FILES, MANIFEST_NAME

    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("Existing results archives are never overwritten: " + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = {}

    def add(path, archive_name):
        if path.is_file():
            if path.is_symlink():
                raise TapeError("CAPSULE_SYMLINK_UNSUPPORTED:" + str(path))
            files[archive_name] = path

    supporting = ("console.log", "market_data_source.jsonl", "ERROR.json", INVENTORY_NAME, STATUS_NAME)
    for name in ENGINE_OUTPUT_FILES + supporting:
        add(run_dir / name, "original/" + run_dir.name + "/" + name)
    for path in sorted((run_dir / "paper_journal").glob("*.json")):
        add(path, "original/" + run_dir.name + "/paper_journal/" + path.name)
    for name in (TAPE_NAME, Path(TAPE_NAME).with_suffix(".manifest.json").name):
        add(run_dir / CAPTURE_DIRECTORY / name,
            "original/" + run_dir.name + "/" + CAPTURE_DIRECTORY + "/" + name)
    for path in sorted(replay_parent.rglob("*")):
        if path.is_file() and path.name != "paper_writer.lock":
            add(path, "replay/" + path.relative_to(replay_parent).as_posix())
    for name in tuple(PACKAGE_FILES) + (MANIFEST_NAME,):
        path = ROOT / name
        if not path.is_file():
            raise TapeError("CAPSULE_PROGRAM_FILE_MISSING:" + name)
        add(path, "program/" + name)
    add(report_path, "RESULT.json")
    inventory = {name: {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
                 for name, path in sorted(files.items())}
    manifest = {
        "schema": "tachyos.full_engine_replay_capsule.v1", "run_id": run_dir.name,
        "created_utc": datetime.now(timezone.utc).isoformat(), "mode": "PAPER",
        "complete_replay_accepted": bool(accepted), "sampled": False, "trimmed": False,
        "native_transport_replay": False, "credentials_included": False,
        "files": inventory,
    }
    descriptor, name = tempfile.mkstemp(prefix=destination.stem + ".", suffix=".tmp", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as archive:
            for archive_name, path in sorted(files.items()):
                archive.write(path, archive_name)
            archive.writestr("CAPSULE_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        with zipfile.ZipFile(temporary, "r") as archive:
            if set(archive.namelist()) != set(inventory) | {"CAPSULE_MANIFEST.json"}:
                raise TapeError("CAPSULE_FILE_SET_CHANGED")
            # Streaming hashes verify the actual archived bytes against the
            # inventory; CRC alone would not catch a changing source file.
            import hashlib
            for archive_name, expected in inventory.items():
                digest = hashlib.sha256()
                length = 0
                with archive.open(archive_name) as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        length += len(chunk)
                        digest.update(chunk)
                if length != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
                    raise TapeError("CAPSULE_SOURCE_CHANGED_DURING_EXPORT:" + archive_name)
        if destination.exists():
            raise FileExistsError("Results destination appeared during export")
        if os.name == "nt":
            # Windows rename refuses an existing destination, including on
            # ordinary removable filesystems without hard-link support.
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
            temporary.unlink()
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def finish_run(run_dir, *, output=None):
    run_dir = Path(run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        raise TapeError("RECORDED_RUN_DIRECTORY_MISSING")
    work = Path(tempfile.mkdtemp(prefix=run_dir.name + "_REPLAY_CHECK_", dir=run_dir.parent))
    report_path = work / "RESULT.json"
    report = {
        "schema": "tachyos.closed_run_replay_result.v1", "run_id": run_dir.name,
        "pass": False, "strategy_modified": False, "mode": "PAPER",
        "native_transport_replay": False, "profitability_proven": False,
        "python": platform.python_version(), "implementation": platform.python_implementation(),
        "platform": platform.platform(), "unresolved_inventory_count": None,
        "ready_for_longer_run": False,
    }
    try:
        from CHECK_TOOL_RACK_PAPER import verify_manifest
        verify_manifest(ROOT, required=True)
        summary = _read_json(run_dir / "RUN_SUMMARY.json")
        if summary.get("state") != "STOPPED":
            raise TapeError("ORIGINAL_ENGINE_NOT_CLOSED")
        report["stop_reason"] = summary.get("stop_reason")
        status = _read_json(run_dir / STATUS_NAME)
        if not status.get("replay_ready") or not status.get("engine_closed") or status.get("writer_alive"):
            raise TapeError("CAPTURE_NOT_COMPLETE_AND_CLOSED")
        inventory = verify_engine_inventory(run_dir)
        report["engine_output_files"] = len(inventory["files"])
        journal = PaperExecutioner.inspect_journal(run_dir)
        if journal["state"] is None:
            raise TapeError("COMMITTED_JOURNAL_UNAVAILABLE")
        report["unresolved_inventory_count"] = len(journal["state"]["positions"])
        report["journal_records"] = journal["records"]
        captured_manifest = _read_json(run_dir / "RUN_MANIFEST.json")
        current_manifest = source_manifest(SOURCE_ROOT)
        if any(captured_manifest.get(key) != value for key, value in current_manifest.items()):
            raise TapeError("ENGINE_PACKAGE_CHANGED_AFTER_CAPTURE")
        header = _recording_header(run_dir)
        report["input_kind"] = header["input_kind"]
        report["capture_platform"] = header["platform"]
        report["capture_python"] = header["python"]
        print("The paper session is closed. Checking its complete recording offline...", flush=True)
        with (work / "replay_console.txt").open("w", encoding="utf-8", newline="\n") as log:
            with redirect_stdout(log), redirect_stderr(log), network_forbidden():
                report["replay"] = replay(run_dir / CAPTURE_DIRECTORY / TAPE_NAME,
                    work / "engine", reference_dir=run_dir, reference_files=tuple(inventory["files"]))
        verify_engine_inventory(run_dir)
        report["pass"] = True
        report["next_action"] = ("Review this real PAPER run for strategy contradictions before choosing corrections or a longer run."
                                  if header["input_kind"] == "REAL_MARKET_PAPER_ENGINE_BOUNDARY" else
                                  "Synthetic integration evidence only; obtain a complete real PAPER recording next.")
    except Exception as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        if isinstance(exc, ReplayMismatch):
            report["failure"]["first_divergence"] = exc.report
        report["next_action"] = "Review the diagnostic ZIP; this run is not accepted as complete replay evidence."
    write_json(report_path, report)
    if output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = run_dir.parent / (run_dir.name + "_REPLAY_RESULTS_" + stamp + f"_{os.getpid()}.zip")
    destination = _export_capsule(run_dir, work, report_path, output, accepted=report["pass"])
    print("Results ZIP: " + str(destination), flush=True)
    print("Recording and replay matched exactly." if report["pass"] else
          "The recording did not pass. The ZIP retains the failure and available evidence.", flush=True)
    if report["unresolved_inventory_count"]:
        print("Unresolved PAPER positions remain explicit. Review them before starting another ledger.", flush=True)
    print("Trading performance has not been improved or certified by this recording check.", flush=True)
    return report, destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--run", type=Path)
    selection.add_argument("--run-receipt", type=Path)
    selection.add_argument("--last-run", action="store_true")
    parser.add_argument("--output-root", type=Path, default=default_output_root())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.run_receipt:
            receipt = _read_json(args.run_receipt)
            if receipt.get("mode") != "PAPER":
                raise TapeError("PAPER_RUN_RECEIPT_REQUIRED")
            run_dir = Path(receipt["run_dir"])
        elif args.last_run:
            run_dir = Path(_read_json(args.output_root / "LAST_RUN.json")["run_dir"])
        else:
            run_dir = args.run
        # This existing lease proves the native launcher is no longer running
        # and prevents a new native PAPER run during replay/export.
        with GlobalPaperLease(global_lease_path()), network_forbidden():
            report, _ = finish_run(run_dir, output=args.output)
        return 0 if report["pass"] and report["unresolved_inventory_count"] == 0 else 2
    except Exception as exc:
        print("Results could not be completed: " + type(exc).__name__ + ": " + str(exc), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
