"""Optional recording around the existing PAPER launcher; no trading authority.

All engine-owned outputs are inventoried after their original handles close.
Feed, console and capture files are supporting evidence, not replay outputs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from bounded_tape import TapeError
from engine_replay import RecordedEngine, file_sha256, require_fresh


CAPTURE_REVISION = "TACHYOS_SHORT_PAPER_CAPTURE_CANDIDATE_20261104"
CAPTURE_DIRECTORY = "replay_capture"
TAPE_NAME = "engine_inputs.jsonl"
INVENTORY_NAME = "ENGINE_OUTPUTS.json"
STATUS_NAME = "CAPTURE_STATUS.json"
CAPTURE_MAX_BYTES = 512_000_000
ENGINE_OUTPUT_FILES = (
    "decisions.jsonl", "physical_geometry.jsonl", "mission_history.jsonl",
    "quote_echo_shadow.jsonl", "leg_performance.jsonl", "RUN_MANIFEST.json",
    "STATUS.json", "PAPER_LEDGER.json", "RUN_SUMMARY.json",
)
OPTIONAL_ENGINE_OUTPUT_FILES = frozenset(("leg_performance.jsonl",))


def write_json(path, value):
    """Atomic sidecar publication, outside the original engine's output files."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def engine_output_inventory(run_dir):
    """A complete declared output scope, including every committed journal file."""
    run_dir = Path(run_dir)
    # The leg ledger is lazy: a session ending before any physical leg event
    # may never create that file. Record its actual presence; later mutation
    # or disappearance still fails inventory and replay comparison.
    missing = [name for name in ENGINE_OUTPUT_FILES if name not in OPTIONAL_ENGINE_OUTPUT_FILES
               and not (run_dir / name).is_file()]
    if missing:
        raise TapeError("MISSING_ENGINE_OUTPUTS:" + ",".join(missing))
    journals = sorted((run_dir / "paper_journal").glob("*.json"))
    if not journals:
        raise TapeError("COMMITTED_BASELINE_JOURNAL_REQUIRED")
    for number, path in enumerate(journals, 1):
        if path.name != f"{number:08d}.json":
            raise TapeError("JOURNAL_INVENTORY_SEQUENCE_GAP")
    paths = [run_dir / name for name in ENGINE_OUTPUT_FILES if (run_dir / name).is_file()] + journals
    if any(path.is_symlink() for path in paths):
        raise TapeError("ENGINE_OUTPUT_SYMLINK_UNSUPPORTED")
    return {
        "schema": "tachyos.closed_engine_outputs.v1", "run_id": run_dir.name,
        "scope": "ALL_PERSISTENT_OUTPUTS_OWNED_BY_THE_FROZEN_ENGINE",
        "files": {path.relative_to(run_dir).as_posix(): {
            "bytes": path.stat().st_size, "sha256": file_sha256(path)} for path in paths},
        "excluded": ["ephemeral paper_writer.lock", "feed/console/dashboard/capture supporting files"],
    }


def verify_engine_inventory(run_dir):
    run_dir = Path(run_dir)
    path = run_dir / INVENTORY_NAME
    if not path.is_file():
        raise TapeError("CLOSED_ENGINE_INVENTORY_MISSING")
    expected = json.loads(path.read_text(encoding="utf-8"))
    actual = engine_output_inventory(run_dir)
    if expected != actual:
        raise TapeError("CLOSED_ENGINE_OUTPUTS_CHANGED_OR_MISSING")
    return actual


def open_capture(run_dir, args):
    """Preflight the requested recording before starting source workers."""
    run_dir = Path(run_dir)
    require_fresh(run_dir, allowed_launcher_files=("console.log",))
    maximum = getattr(args, "capture_max_bytes", CAPTURE_MAX_BYTES)
    if type(maximum) is not int or maximum < 1:
        raise TapeError("INVALID_CAPTURE_BYTE_LIMIT")
    # The longer same-interpreter preparation also estimates engine logs,
    # replay and export space. This catches an immediately unavailable drive.
    if shutil.disk_usage(run_dir).free < maximum + 1_000_000_000:
        raise TapeError("INSUFFICIENT_FREE_SPACE_FOR_SHORT_CAPTURE")
    descriptor, probe_name = tempfile.mkstemp(prefix="capture_write_probe_", dir=run_dir)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(b"TACHYOS_CAPTURE_PREFLIGHT\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        Path(probe_name).unlink(missing_ok=True)
    recorder = RecordedEngine(run_dir, run_dir / CAPTURE_DIRECTORY / TAPE_NAME,
        input_kind="REAL_MARKET_PAPER_ENGINE_BOUNDARY", allowed_launcher_files=("console.log",),
        queue_capacity=64, max_bytes=maximum)
    recorder._capture_started_perf = time.perf_counter()
    if not recorder.writer.wait_ready(timeout_s=3.0):
        recorder.writer.fail("CAPTURE_STARTUP_NOT_READY")
        finish_capture(recorder, reason="CAPTURE_STARTUP_FAILED_BEFORE_FEED")
        raise TapeError("CAPTURE_STARTUP_FAILED_BEFORE_FEED")
    print("Recording enabled: every engine input and clock read; trading rules unchanged.", flush=True)
    return recorder


def capture_health(recorder):
    """Read only bounded counters; never inspect trading collections or write I/O."""
    health = dict(recorder.writer.health())
    metrics = recorder.metrics
    measured = metrics["calls_measured"]
    health.update({
        "enabled": True, "capture_revision": CAPTURE_REVISION,
        "path": str(recorder.writer.path), "strategy_modified": False,
        "calls_measured": measured, "clock_reads": metrics["clock_read_count"],
        "capture_work_max_us": round(metrics["capture_work_max_us"], 4),
        "capture_work_mean_us": round(metrics["capture_work_total_us"] / measured, 4) if measured else 0,
        "timing_sample_limit": metrics["sample_limit"],
    })
    started = getattr(recorder, "_capture_started_perf", None)
    if started is not None:
        elapsed = max(0.0, time.perf_counter() - started)
        health["elapsed_seconds"] = round(elapsed, 3)
        health["mean_written_bytes_per_second"] = round(health.get("bytes", 0) / elapsed, 2) if elapsed else 0
    return health


def finish_capture(recorder, *, reason):
    """Close the original engine once, drain recording, then publish sidecars.

    Original close exceptions remain exceptions. A sidecar publication error
    marks acceptance failed without inventing or changing a trading operation.
    """
    if hasattr(recorder, "_finished_capture_health"):
        return dict(recorder._finished_capture_health)
    original_error = None
    try:
        recorder.close(reason=reason)
    except BaseException as exc:
        original_error = exc
    health = capture_health(recorder)
    health["engine_closed"] = bool(recorder.engine is not None and recorder.engine.executor._closed)
    health["stop_reason"] = reason
    health["engine_output_inventory_complete"] = False
    if original_error is not None:
        health["engine_close_error"] = type(original_error).__name__ + ": " + str(original_error)
    try:
        if not health["engine_closed"]:
            raise TapeError("ORIGINAL_ENGINE_DID_NOT_CLOSE")
        inventory = engine_output_inventory(recorder.run_dir)
        write_json(recorder.run_dir / INVENTORY_NAME, inventory)
        health["engine_output_inventory_complete"] = True
        health["engine_output_files"] = len(inventory["files"])
        health["engine_output_bytes"] = sum(item["bytes"] for item in inventory["files"].values())
    except Exception as exc:
        health["inventory_error"] = type(exc).__name__ + ": " + str(exc)
    health["replay_ready"] = bool(health.get("complete") and health["engine_closed"]
                                   and health["engine_output_inventory_complete"] and original_error is None)
    try:
        write_json(recorder.run_dir / STATUS_NAME, health)
    except Exception as exc:
        health["replay_ready"] = False
        health["status_write_error"] = type(exc).__name__ + ": " + str(exc)
        print("Recording report could not be saved: " + health["status_write_error"], flush=True)
    recorder._finished_capture_health = dict(health)
    if original_error is not None:
        raise original_error
    return health
