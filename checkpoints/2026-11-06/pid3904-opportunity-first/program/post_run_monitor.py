"""Display file-backed completion progress for the exact newly closed PAPER run.

The worker saves the original archive and creates its small upload files. Its
output goes directly to a regular log file, independently of console display.
This launcher never starts an engine, selects a latest run, or requests replay.
"""
from __future__ import annotations

import argparse
import codecs
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid


ROOT = Path(__file__).resolve().parent
HELPER_NAME = "complete_paper_run.py"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def _read_json(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(16_000_001)
    if len(raw) > 16_000_000:
        raise ValueError("Completion metadata is unexpectedly large")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Completion metadata must be an object")
    return value


def _atomic_json(path, value):
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _process_options():
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def execute_logged(command, log_path, *, stream=None, on_started=None, poll_seconds=0.2):
    """Start the worker before console writes; no console pipe can block it."""
    stream = sys.stdout if stream is None else stream
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    log_path = Path(log_path)
    with log_path.open("xb") as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
            stderr=subprocess.STDOUT, env=environment, shell=False, **_process_options())
    if on_started is not None:
        on_started(process)
    print("Saving the recording and preparing smaller upload files.", file=stream, flush=True)
    print("Progress log: " + str(log_path), file=stream, flush=True)
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    with log_path.open("rb") as observed:
        while True:
            chunk = observed.read(65_536)
            if chunk:
                stream.write(decoder.decode(chunk))
                stream.flush()
                continue
            code = process.poll()
            if code is not None:
                while True:
                    chunk = observed.read(65_536)
                    if not chunk:
                        break
                    stream.write(decoder.decode(chunk))
                stream.write(decoder.decode(b"", final=True))
                stream.flush()
                return code
            time.sleep(poll_seconds)


def _command(root, run, output, pointer):
    return [sys.executable, "-X", "utf8", "-u", str(root / HELPER_NAME),
            "--run", str(run), "--output-dir", str(output),
            "--status-pointer", str(pointer), "--small-uploads"]


def validate_completion(pointer, run, output):
    selected = _read_json(pointer)
    if selected.get("run_id") != run.name:
        raise ValueError("Completion pointer identifies another run")
    path = Path(selected.get("status_path", ""))
    if not path.is_absolute() or not path.resolve().is_relative_to(output):
        raise ValueError("Completion status is outside the exact results folder")
    status = _read_json(path)
    if (status.get("run_id") != run.name or status.get("mode") != "PAPER"
            or Path(status.get("source", "")).resolve() != run):
        raise ValueError("Completion status identifies another run or mode")
    if status.get("replay", {}).get("state") != "NOT_REQUESTED":
        raise ValueError("This launcher did not request replay")
    export = status.get("export", {})
    archive = Path(export.get("archive", ""))
    if (export.get("state") != "VERIFIED" or not archive.is_absolute()
            or archive.resolve().parent != output or not archive.is_file()
            or archive.stat().st_size != export.get("bytes")):
        raise ValueError("No verified complete original archive is available")
    uploads = status.get("uploads", {})
    folder = Path(uploads.get("output_dir", ""))
    if (uploads.get("state") != "COMPLETE" or uploads.get("all_verified") is not True
            or uploads.get("run_id") != run.name
            or uploads.get("source") != str(archive)
            or uploads.get("source_sha256") != export.get("sha256")
            or not folder.is_absolute() or folder.resolve().parent != output or not folder.is_dir()):
        raise ValueError("Small upload files do not match the verified original archive")
    manifest = _read_json(folder / "TRANSFER_MANIFEST.json")
    if (manifest.get("run_id") != run.name or manifest.get("source_sha256") != export.get("sha256")
            or manifest.get("source_size") != export.get("bytes")
            or manifest.get("source_archive_name") != archive.name):
        raise ValueError("Upload transfer manifest does not match the exact export")
    expected_parts = [str(folder / item["file_name"]) for item in manifest.get("parts", [])]
    if (not expected_parts or uploads.get("parts") != expected_parts
            or uploads.get("part_count") != len(expected_parts)):
        raise ValueError("Upload part inventory is incomplete")
    review = Path(uploads.get("review_zip", ""))
    if review != folder / "00_SEND_FIRST_REVIEW.zip" or not review.is_file():
        raise ValueError("The small first-review ZIP is missing")
    for name in expected_parts:
        part = Path(name)
        if part.resolve().parent != folder or not part.is_file() or part.stat().st_size >= 100_000_000:
            raise ValueError("An upload part is missing or outside the size limit")
    complete = (status.get("capture", {}).get("state") == "REPORTED_COMPLETE"
        and status.get("capture", {}).get("unresolved_inventory_count") == 0
        and status.get("program", {}).get("state") == "MATCHED_CAPTURE"
        and export.get("inventory_matches") is True and not status.get("completion_error"))
    return status, folder, complete


def run_completion(run, *, root=ROOT, output_dir=None, stream=None, open_folder=True):
    stream = sys.stdout if stream is None else stream
    root, run = Path(root).resolve(), Path(run).expanduser().resolve()
    if not run.is_dir():
        raise ValueError("The exact recorded run folder is missing")
    output = Path(output_dir).expanduser().resolve() if output_dir else run.parent / "PAPER_RESULTS"
    if any(output == protected or protected in output.parents for protected in (run, root)):
        raise ValueError("Completion output must be outside the original run and program")
    output.mkdir(parents=True, exist_ok=True)
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:12]
    attempt = output / (run.name + "_COMPLETION_LAUNCH_" + tag)
    attempt.mkdir(exist_ok=False)
    pointer, log = attempt / "STATUS_POINTER.json", attempt / "COMPLETION_LOG.txt"
    receipt_path = attempt / "LAUNCH_STATUS.json"
    receipt = {"run_id": run.name, "mode": "PAPER", "run_dir": str(run), "state": "LAUNCHING",
               "created_utc": utc_now(), "log_path": str(log), "status_pointer": str(pointer),
               "engine_started": False, "replay_requested": False}
    _atomic_json(receipt_path, receipt)

    def started(process):
        receipt.update(state="WORKER_STARTED", worker_pid=process.pid)
        _atomic_json(receipt_path, receipt)

    try:
        code = execute_logged(_command(root, run, output, pointer), log, stream=stream, on_started=started)
    except (Exception, KeyboardInterrupt) as exc:
        receipt.update(state="DISPLAY_OR_LAUNCH_ERROR", error=type(exc).__name__ + ": " + str(exc))
        _atomic_json(receipt_path, receipt)
        # Do not terminate a running worker merely because its viewer failed.
        raise
    receipt.update(worker_returncode=code, completed_utc=utc_now(), state="FINISHED")
    try:
        status, folder, complete = validate_completion(pointer, run, output)
        receipt.update(completion_status=status["status_path"], upload_folder=str(folder))
        if code == 0 and not complete:
            code = 2
            receipt["validation_error"] = "Worker exited zero without a complete matched export"
        if open_folder and os.name == "nt":
            try:
                os.startfile(str(folder))
            except OSError as exc:
                receipt["folder_open_error"] = str(exc)
        print("\nSEND FIRST: " + str(folder / "00_SEND_FIRST_REVIEW.zip"), file=stream, flush=True)
        print("Then send all numbered 01_RUN_PART ZIP files from that folder.", file=stream, flush=True)
    except Exception as exc:
        receipt["validation_error"] = type(exc).__name__ + ": " + str(exc)
        if code == 0:
            code = 1
        print("Completion needs review: " + str(exc), file=stream, flush=True)
    receipt["launcher_returncode"] = code
    _atomic_json(receipt_path, receipt)
    print("Completion log and status: " + str(attempt), file=stream, flush=True)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--run", type=Path)
    selection.add_argument("--run-receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        run = args.run
        if args.run_receipt:
            receipt = _read_json(args.run_receipt)
            if receipt.get("mode") != "PAPER" or not isinstance(receipt.get("run_dir"), str):
                raise ValueError("An exact PAPER run receipt is required")
            run = Path(receipt["run_dir"])
        return run_completion(run)
    except KeyboardInterrupt:
        print("The display was interrupted. Check the printed completion log before restarting.", flush=True)
        return 130
    except Exception as exc:
        print("Completion launch failed: " + type(exc).__name__ + ": " + str(exc), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
