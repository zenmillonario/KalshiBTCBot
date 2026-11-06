"""Save one closed PAPER recording first; replay only when explicitly requested.

The default path uses only the standard library. It copies complete original
files and the matching whitelisted program, verifies the archived bytes, then
publishes a unique ZIP. It never constructs an engine. Optional replay uses a
private verified copy of that published archive and the unchanged replay API.
Capture, export and replay results are separate; exporting never implies PASS.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import sys
import tempfile
import threading
import time
import uuid
import zipfile


ROOT = Path(__file__).resolve().parent
REVISION = "TACHYOS_COMPLETE_EXPORT_AND_SMALL_UPLOADS_20261104"
SCHEMA = "tachyos.complete_paper_original_export.v1"
STATUS_SCHEMA = "tachyos.paper_completion_status.v1"
REPORT_NAME = "COMPLETION_REPORT.json"
STATUS_NAME = "POST_RUN_STATUS.json"
BUNDLE_NAME = "TOOL_RACK_PAPER_BUNDLE_MANIFEST.json"
TAPE_NAME = "replay_capture/engine_inputs.jsonl"
TAPE_MANIFEST = "replay_capture/engine_inputs.manifest.json"
HEARTBEAT_SECONDS = 4.0
CHUNK_BYTES = 1024 * 1024
ENGINE_NAMES = (
    "RUN_MANIFEST.json", "RUN_SUMMARY.json", "STATUS.json", "PAPER_LEDGER.json",
    "decisions.jsonl", "physical_geometry.jsonl", "mission_history.jsonl",
    "quote_echo_shadow.jsonl", "leg_performance.jsonl",
)
SUPPORT_NAMES = ("CAPTURE_STATUS.json", "ENGINE_OUTPUTS.json", "ERROR.json",
                 "console.log", "market_data_source.jsonl", "btc_public_source.jsonl.gz",
                 TAPE_NAME, TAPE_MANIFEST)
RECORDER_NAMES = {"engine_replay.py", "input_codec.py", "bounded_tape.py", "snapshot_delta.py",
                  "capture_session.py", "finish_recorded_run.py", "TOOL_RACK_PAPER.py"}


class CompletionError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CompletionError("DUPLICATE_JSON_KEY:" + str(key))
        result[key] = value
    return result


def _parse(data):
    def invalid(value):
        raise CompletionError("NONFINITE_JSON:" + str(value))
    return json.loads(data, object_pairs_hook=_unique_object, parse_constant=invalid)


def read_json(path, *, limit=16_000_000):
    with Path(path).open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise CompletionError("METADATA_READ_LIMIT:" + Path(path).name)
    return _parse(data)


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _atomic_json(path, value):
    path = Path(path)
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_relative(name):
    if (not isinstance(name, str) or not name or "\\" in name or "\x00" in name
            or ":" in name or PureWindowsPath(name).drive):
        raise CompletionError("UNSAFE_FILE_NAME")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in name.split("/")):
        raise CompletionError("UNSAFE_FILE_NAME:" + name)
    return Path(*path.parts)


def _run_id(value):
    path = _safe_relative(value)
    if len(path.parts) != 1:
        raise CompletionError("INVALID_RUN_ID")
    return value


def _checked_file(root, relative):
    path = Path(root)
    for part in _safe_relative(relative).parts:
        path = path / part
        if path.is_symlink():
            raise CompletionError("LINKED_EVIDENCE_UNSUPPORTED:" + relative)
    if not path.is_file():
        raise CompletionError("EVIDENCE_FILE_MISSING:" + relative)
    return path


def file_sha256(path, progress=None):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
            if progress is not None:
                progress.advance(len(chunk))
    return digest.hexdigest()


def global_lease_path():
    # Same path and OS lock primitive as paper_runtime.GlobalPaperLease, without
    # importing the feed or engine on the default export-only path.
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "TachyosToolRack" / "paper_engine.lock"


@contextmanager
def exclusive_completion_lease(path=None):
    path = Path(path) if path is not None else global_lease_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b" ")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise CompletionError("ANOTHER_TOOL_RACK_PAPER_ENGINE_IS_RUNNING") from None
        yield
    finally:
        handle.close()


class Progress:
    """One console/persistent heartbeat independent of lengthy file work."""
    def __init__(self, status_path, status, *, interval=HEARTBEAT_SECONDS, stream=None):
        self.path, self.status = Path(status_path), status
        self.interval = interval
        self.stream = stream if stream is not None else sys.stdout
        self.started = self.phase_started = time.monotonic()
        self.lock = threading.RLock()
        self.write_lock = threading.RLock()
        self.stop = threading.Event()
        self.failure = None
        self.probe = None
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)
        status["progress"] = {"phase": "Opening completion status", "done": 0, "total": None, "unit": "bytes"}

    def _publish(self):
        # Persist a coherent snapshot independently of console printing. The
        # supplied launcher redirects this helper's console to a real log file,
        # so selecting text in the monitor cannot hold up export work.
        with self.write_lock:
            with self.lock:
                now = time.monotonic()
                self.status["updated_utc"] = utc_now()
                self.status["elapsed_seconds"] = round(now - self.started, 3)
                self.status["progress"]["phase_elapsed_seconds"] = round(now - self.phase_started, 3)
                snapshot = copy.deepcopy(self.status)
            _atomic_json(self.path, snapshot)
        progress = snapshot["progress"]
        if progress.get("total") is not None:
            unit = progress.get("unit", "bytes")
            done, total = progress["done"], progress["total"]
            quantity = (f"{done / 1_000_000:.1f}/{total / 1_000_000:.1f} MB"
                        if unit == "bytes" else f"{done}/{total} {unit}")
        else:
            quantity = "working"
        print(f"{progress['phase']} | {quantity} | elapsed {snapshot['elapsed_seconds']:.0f}s",
              file=self.stream, flush=True)

    def phase(self, name, *, total=None, unit="bytes", done=0):
        self.check()
        with self.lock:
            self.phase_started = time.monotonic()
            self.status["progress"] = {"phase": name, "done": done, "total": total, "unit": unit}
        self._publish()

    def state(self, section, state, **fields):
        with self.lock:
            self.status[section].update(state=state, **fields)
        self.check()
        self._publish()

    def terminal_state(self, section, state, **fields):
        # A failed heartbeat must not prevent recording ERROR/INTERRUPTED or
        # leave a separate replay report falsely stuck at RUNNING.
        with self.lock:
            self.status[section].update(state=state, **fields)
        try:
            self._publish()
        except Exception as exc:
            self.failure = exc

    def advance(self, count):
        self.check()
        with self.lock:
            self.status["progress"]["done"] += count

    def check(self):
        if self.failure is not None:
            raise CompletionError("PROGRESS_STATUS_WRITE_FAILED:" + str(self.failure))

    def _heartbeat(self):
        while not self.stop.wait(self.interval):
            try:
                if self.probe is not None:
                    observed = self.probe()
                    if observed:
                        with self.lock:
                            self.status["progress"].update(observed)
                self._publish()
            except Exception as exc:
                self.failure = exc
                print("Progress status could not be written: " + str(exc), file=self.stream, flush=True)
                return

    def __enter__(self):
        self._publish()
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=5)


def _new_status(run_id, source, output_dir, *, replay_requested=False):
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    work = output_dir / (run_id + "_POST_RUN_" + tag)
    work.mkdir(exist_ok=False)
    status = {
        "schema": STATUS_SCHEMA, "run_id": run_id, "created_utc": utc_now(),
        "mode": "PAPER", "source": str(source), "status_path": str(work / STATUS_NAME),
        "completion_tool": {"revision": REVISION, "sha256": file_sha256(Path(__file__))},
        "capture": {"state": "NOT_CHECKED"}, "export": {"state": "NOT_STARTED"},
        "uploads": {"state": "NOT_REQUESTED"},
        "replay": {"state": "REQUESTED" if replay_requested else "NOT_REQUESTED"},
        "strategy_modified_by_completion": False, "original_files_modified": False,
        "profitability_proven": False, "ready_for_longer_run": False,
        "environment": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                        "platform": platform.platform()},
    }
    return work, tag, status


def selected_original_files(run):
    selected = {}
    for relative in ENGINE_NAMES + SUPPORT_NAMES:
        if (run / relative).is_file():
            selected[relative] = _checked_file(run, relative)
    if (run / "paper_journal").is_symlink():
        raise CompletionError("LINKED_JOURNAL_UNSUPPORTED")
    for path in sorted((run / "paper_journal").glob("*.json")):
        if len(path.stem) != 8 or not path.stem.isdigit():
            raise CompletionError("UNEXPECTED_JOURNAL_FILENAME:" + path.name)
        relative = "paper_journal/" + path.name
        selected[relative] = _checked_file(run, relative)
    # No persistent output may silently disappear from the capsule. Ephemeral
    # writer locks and operating-system transfer placeholders are not outputs.
    for path in run.rglob("*"):
        relative = path.relative_to(run)
        if any(part.startswith(".") for part in relative.parts) or path.name == "paper_writer.lock":
            continue
        if path.is_symlink():
            raise CompletionError("LINKED_EVIDENCE_UNSUPPORTED:" + relative.as_posix())
        if path.is_file() and relative.as_posix() not in selected:
            raise CompletionError("UNDECLARED_RUN_FILE_REQUIRES_REVIEW:" + relative.as_posix())
    return selected


def bounded_header(run):
    with _checked_file(run, TAPE_NAME).open("rb") as handle:
        raw = handle.readline(1_000_001)
    if len(raw) > 1_000_000 or not raw.endswith(b"\n"):
        raise CompletionError("CAPTURE_HEADER_TRUNCATED_OR_OVERSIZED")
    record = _parse(raw)
    if (not isinstance(record, dict)
            or set(record) != {"schema", "kind", "sequence", "previous_sha256", "payload", "sha256"}
            or record["kind"] != "HEADER" or record["sequence"] != 0
            or record["previous_sha256"] != "0" * 64
            or record["schema"] not in {"tachyos.engine_input_tape.v1", "tachyos.engine_input_tape.v2"}
            or not isinstance(record["payload"], dict)):
        raise CompletionError("CAPTURE_HEADER_INVALID")
    signed = {key: value for key, value in record.items() if key != "sha256"}
    digest = hashlib.sha256(json.dumps(signed, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()
    if digest != record["sha256"]:
        raise CompletionError("CAPTURE_HEADER_HASH_MISMATCH")
    manifest = read_json(_checked_file(run, TAPE_MANIFEST), limit=65_536)
    if manifest.get("header_sha256") != digest or record["payload"].get("run_id") != run.name:
        raise CompletionError("CAPTURE_HEADER_IDENTITY_MISMATCH")
    return record["payload"], manifest


def _closed_run(run, progress=None):
    if progress is not None:
        progress.phase("Checking closed run metadata")
    summary = read_json(_checked_file(run, "RUN_SUMMARY.json"))
    run_manifest = read_json(_checked_file(run, "RUN_MANIFEST.json"))
    capture = read_json(_checked_file(run, "CAPTURE_STATUS.json"))
    declared = read_json(_checked_file(run, "ENGINE_OUTPUTS.json"))
    # A fresh engine can close before its first process() event. In that case
    # its summary has no repeated identity fields; RUN_MANIFEST always does.
    if (run_manifest.get("mode") != "PAPER" or run_manifest.get("run_id") != run.name
            or summary.get("mode", "PAPER") != "PAPER"
            or summary.get("run_id", run.name) != run.name):
        raise CompletionError("EXACT_PAPER_RUN_IDENTITY_REQUIRED")
    if summary.get("state") != "STOPPED":
        raise CompletionError("ORIGINAL_PAPER_ENGINE_NOT_CLOSED")
    if capture.get("engine_closed") is not True or capture.get("writer_alive") is not False:
        raise CompletionError("ORIGINAL_RECORDING_NOT_CLOSED")
    if declared.get("run_id") != run.name or not isinstance(declared.get("files"), dict):
        raise CompletionError("EXACT_CLOSED_ENGINE_INVENTORY_REQUIRED")
    if progress is not None:
        progress.phase("Listing complete original files")
    files = selected_original_files(run)
    required = set(ENGINE_NAMES) - {"leg_performance.jsonl"}
    required |= {"CAPTURE_STATUS.json", "ENGINE_OUTPUTS.json", TAPE_NAME, TAPE_MANIFEST}
    missing = sorted((required | set(declared["files"])) - set(files))
    if missing:
        raise CompletionError("ORIGINAL_RECORDING_FILES_MISSING:" + ",".join(missing))
    actual_engine = {name for name in files if name in ENGINE_NAMES or name.startswith("paper_journal/")}
    if set(declared["files"]) != actual_engine:
        raise CompletionError("CLOSED_ENGINE_INVENTORY_SCOPE_MISMATCH")
    journals = sorted(name for name in files if name.startswith("paper_journal/"))
    if not journals or journals != [f"paper_journal/{number:08d}.json" for number in range(1, len(journals) + 1)]:
        raise CompletionError("COMMITTED_JOURNAL_SEQUENCE_GAP")
    for name, record in declared["files"].items():
        _safe_relative(name)
        if (not isinstance(record, dict) or type(record.get("bytes")) is not int
                or record["bytes"] < 0 or not isinstance(record.get("sha256"), str)
                or len(record["sha256"]) != 64):
            raise CompletionError("CLOSED_ENGINE_INVENTORY_INVALID")
    return summary, capture, declared, files


def program_snapshot(run, *, program_root=ROOT, progress=None):
    """Verify and select the complete captured bundle without importing it."""
    program_root = Path(program_root).resolve()
    if progress is not None:
        progress.phase("Selecting unchanged captured program")
    manifest_path = _checked_file(program_root, BUNDLE_NAME)
    manifest = read_json(manifest_path)
    if (manifest.get("schema") != "TACHYOS_TOOL_RACK_PAPER_BUNDLE_V1"
            or manifest.get("mode") != "PAPER" or manifest.get("venue_order_authority") != "NONE"
            or not isinstance(manifest.get("files"), dict) or not manifest["files"]):
        raise CompletionError("PAPER_PROGRAM_MANIFEST_INVALID")
    paths = {name: _checked_file(program_root, name) for name in manifest["files"]}
    if BUNDLE_NAME in paths:
        raise CompletionError("SELF_REFERENCING_PROGRAM_MANIFEST")
    paths[BUNDLE_NAME] = manifest_path
    if progress is not None:
        progress.phase("Checking captured program", total=sum(p.stat().st_size for p in paths.values()))
    hashes = {name: file_sha256(path, progress) for name, path in paths.items()}
    for name, expected in manifest["files"].items():
        if expected.get("size") != paths[name].stat().st_size or expected.get("sha256") != hashes[name]:
            raise CompletionError("PROGRAM_BUNDLE_CHANGED:" + name)
    captured = read_json(_checked_file(run, "RUN_MANIFEST.json"))
    captured_files = captured.get("files")
    if not isinstance(captured_files, dict) or captured_files.get(BUNDLE_NAME) != hashes[BUNDLE_NAME]:
        raise CompletionError("PROGRAM_MANIFEST_DIFFERS_FROM_CAPTURE")
    if any(hashes.get(name) != digest for name, digest in captured_files.items()):
        raise CompletionError("PROGRAM_SOURCE_DIFFERS_FROM_CAPTURE")
    canonical = json.dumps(captured_files, sort_keys=True, separators=(",", ":")).encode()
    if captured.get("source_and_config_sha256") != hashlib.sha256(canonical).hexdigest():
        raise CompletionError("CAPTURED_SOURCE_MANIFEST_INVALID")
    header, tape_manifest = bounded_header(run)
    source_hashes = read_json(_checked_file(program_root, "SOURCE_SHA256.json"))
    if not source_hashes or source_hashes != header.get("source_hashes"):
        raise CompletionError("CORE_SOURCE_HASHES_DIFFER_FROM_CAPTURE")
    actual_core = {p.relative_to(program_root).as_posix()
                   for p in (program_root / "strategy_core").rglob("*")
                   if p.is_file() and p.suffix in (".py", ".json", ".html", ".css", ".js")}
    if actual_core != set(source_hashes):
        raise CompletionError("CORE_SOURCE_FILE_SET_CHANGED")
    if any(hashes.get(name) != digest for name, digest in source_hashes.items()):
        raise CompletionError("CORE_SOURCE_FILES_CHANGED")
    recorder = header.get("recorder_source_hashes")
    if (not isinstance(recorder, dict) or set(recorder) != RECORDER_NAMES
            or any(hashes.get(name) != digest for name, digest in recorder.items())):
        raise CompletionError("RECORDER_SOURCE_DIFFERS_FROM_CAPTURE")
    return paths, {"state": "MATCHED_CAPTURE", "release_id": manifest.get("release_id"),
        "bundle_manifest_sha256": hashes[BUNDLE_NAME], "source_and_config_sha256": captured["source_and_config_sha256"],
        "files": {name: {"bytes": path.stat().st_size, "sha256": hashes[name]} for name, path in paths.items()},
        "header": header, "tape_manifest": tape_manifest}


def _publish_unique(temporary, destination):
    if os.name == "nt":
        # Windows rename fails if the destination exists, including on ordinary
        # removable filesystems without hard-link support.
        os.rename(temporary, destination)
    else:
        os.link(temporary, destination)
        temporary.unlink()


def _verify_archive(path, records, report_bytes, progress, *, extract_original_to=None, run_id=None):
    progress.phase("Verifying archived bytes", total=sum(r["bytes"] for r in records.values()) + len(report_bytes))
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        expected_names = set(records) | {REPORT_NAME}
        if len(names) != len(set(names)) or set(names) != expected_names:
            raise CompletionError("ARCHIVE_FILE_SET_CHANGED")
        for name in names:
            _safe_relative(name)
        for name, expected in records.items():
            digest = hashlib.sha256()
            size = 0
            target = None
            if extract_original_to is not None and name.startswith("original/" + run_id + "/"):
                relative = name[len("original/" + run_id + "/"):]
                output = Path(extract_original_to) / _safe_relative(relative)
                output.parent.mkdir(parents=True, exist_ok=True)
                target = output.open("xb")
            try:
                with archive.open(name) as source:
                    for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
                        digest.update(chunk)
                        size += len(chunk)
                        if target is not None:
                            target.write(chunk)
                        progress.advance(len(chunk))
            finally:
                if target is not None:
                    target.close()
            if size != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
                raise CompletionError("ARCHIVED_BYTES_DIFFER:" + name)
        actual_report = archive.read(REPORT_NAME)
        progress.advance(len(actual_report))
        if actual_report != report_bytes:
            raise CompletionError("ARCHIVE_REPORT_CHANGED")


def _capture_report(run, summary, capture):
    # These are bounded sidecar checks, not a replacement for the typed, fully
    # decoded tape validation inside the optional replay. Keep that scope clear.
    failure = None
    try:
        manifest = read_json(_checked_file(run, TAPE_MANIFEST), limit=65_536)
        count_names = ("attempted", "accepted", "written", "dropped", "bytes")
        counts_valid = all(type(item.get(name)) is int and item[name] >= 0
                           for item in (capture, manifest) for name in count_names)
        complete = (counts_valid and capture.get("complete") is True
                    and capture.get("replay_ready") is True
                    and capture.get("engine_output_inventory_complete") is True
                    and capture.get("reason") is None and capture.get("dropped") == 0
                    and manifest.get("complete") is True and manifest.get("reason") is None
                    and manifest.get("writer_alive") is False
                    and manifest.get("schema") in {"tachyos.engine_input_tape_manifest.v1",
                                                    "tachyos.engine_input_tape_manifest.v2"}
                    and all(capture[name] == manifest[name] for name in count_names)
                    and manifest["attempted"] == manifest["accepted"] == manifest["written"]
                    and manifest["written"] >= 2
                    and manifest["bytes"] == (run / TAPE_NAME).stat().st_size)
    except Exception as exc:
        complete = False
        failure = type(exc).__name__ + ": " + str(exc)
    result = {"state": "REPORTED_COMPLETE" if complete else "REPORTED_INCOMPLETE",
        "reported_complete": capture.get("complete"), "reported_replay_ready": capture.get("replay_ready"),
        "written_calls": capture.get("written"), "unresolved_inventory_count": summary.get("unresolved_inventory_count"),
        "stop_reason": summary.get("stop_reason"), "cash": summary.get("cash"),
        "verification_scope": "Closed-run identity and copy hashes; full typed tape verification is part of optional replay."}
    if failure:
        result["failure"] = failure
    return result


def export_original(run, work, tag, status, progress, *, program_root=ROOT):
    summary, capture, declared, originals = _closed_run(run, progress)
    progress.phase("Checking capture completion metadata")
    with progress.lock:
        status["capture"] = _capture_report(run, summary, capture)
    progress.state("export", "RUNNING")
    try:
        programs, program = program_snapshot(run, program_root=program_root, progress=progress)
    except Exception as exc:
        programs = {}
        program = {"state": "NOT_MATCHED", "failure": type(exc).__name__ + ": " + str(exc)}
        print("Program provenance needs review; saving complete original evidence for diagnosis.",
              file=progress.stream, flush=True)
    with progress.lock:
        status["program"] = {key: value for key, value in program.items() if key not in {"files", "header", "tape_manifest"}}
    files = {"original/" + run.name + "/" + name: path for name, path in originals.items()}
    files.update({"program/" + name: path for name, path in programs.items()})
    stats = {name: (path.stat().st_size, path.stat().st_mtime_ns) for name, path in files.items()}
    total = sum(value[0] for value in stats.values())
    destination = work.parent / (run.name + "_FULL_ORIGINAL_" + tag + ".zip")
    descriptor, name = tempfile.mkstemp(prefix=destination.stem + ".", suffix=".partial", dir=work.parent)
    os.close(descriptor)
    temporary = Path(name)
    report = {"schema": SCHEMA, "run_id": run.name, "created_utc": utc_now(), "mode": "PAPER",
        "source_run": str(run), "completion_tool": status["completion_tool"],
        "capture": status["capture"], "program": program,
        "export": {"state": "VERIFIED_ON_ATOMIC_PUBLICATION", "source_files": len(originals),
                   "program_files": len(programs), "sampled": False, "trimmed": False},
        "replay": {"state": "NOT_REQUESTED", "performed": False},
        "original_files_modified": False, "strategy_modified_by_completion": False,
        "profitability_proven": False, "venue_fill_claim": False,
        "inventory_mismatches": [], "files": {},
        "verification_scope": "Every archived original/program byte is stream-hashed and verified before atomic publication. No engine replay occurs during export.",
        "engine_inventory": declared}
    try:
        progress.phase("Saving complete original recording and program", total=total)
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
            for arcname, path in files.items():
                digest = hashlib.sha256()
                size = 0
                with path.open("rb") as source, archive.open(arcname, "w", force_zip64=True) as target:
                    for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
                        target.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                        progress.advance(len(chunk))
                after = path.stat()
                if stats[arcname] != (after.st_size, after.st_mtime_ns) or size != after.st_size:
                    raise CompletionError("SOURCE_CHANGED_DURING_EXPORT:" + arcname)
                record = {"bytes": size, "sha256": digest.hexdigest()}
                report["files"][arcname] = record
                if arcname.startswith("original/"):
                    relative = path.relative_to(run).as_posix()
                    expected = declared["files"].get(relative)
                    if expected is not None and expected != record:
                        report["inventory_mismatches"].append(relative)
                else:
                    relative = path.relative_to(Path(program_root).resolve()).as_posix()
                    if record != program["files"][relative]:
                        raise CompletionError("PROGRAM_CHANGED_DURING_EXPORT:" + relative)
            if report["inventory_mismatches"]:
                with progress.lock:
                    status["capture"]["state"] = "ORIGINAL_OUTPUTS_CHANGED"
            report["inventory_matches"] = not report["inventory_mismatches"]
            report_bytes = _json_bytes(report)
            archive.writestr(REPORT_NAME, report_bytes)
        # Source stats are rechecked across the complete copying interval.
        if any((path.stat().st_size, path.stat().st_mtime_ns) != stats[name] for name, path in files.items()):
            raise CompletionError("SOURCE_CHANGED_DURING_EXPORT")
        _verify_archive(temporary, report["files"], report_bytes, progress)
        progress.phase("Fingerprinting completed archive", total=temporary.stat().st_size)
        archive_sha256 = file_sha256(temporary, progress)
        progress.check()
        # Verification may take time on a large recorded run. Keep the source
        # snapshot fixed through publication, including its complete file set.
        if any((path.stat().st_size, path.stat().st_mtime_ns) != stats[name]
               for name, path in files.items()):
            raise CompletionError("SOURCE_CHANGED_DURING_EXPORT")
        if set(selected_original_files(run)) != set(originals):
            raise CompletionError("SOURCE_FILE_SET_CHANGED_DURING_EXPORT")
        _publish_unique(temporary, destination)
        status["binding"] = {
            "input_tape_sha256": report["files"]["original/" + run.name + "/" + TAPE_NAME]["sha256"],
            "engine_inventory_sha256": report["files"]["original/" + run.name + "/ENGINE_OUTPUTS.json"]["sha256"],
            "archive_sha256": archive_sha256, "program_manifest_sha256": program.get("bundle_manifest_sha256")}
        # Publication is already real. Retain its location even if a status
        # write or the heartbeat fails immediately after this point.
        with progress.lock:
            status["export"].update(state="VERIFIED", archive=str(destination), bytes=destination.stat().st_size,
                                    sha256=archive_sha256, inventory_matches=report["inventory_matches"])
        print("\nCOMPLETE ORIGINAL ZIP: " + str(destination), file=progress.stream, flush=True)
        print("Original recording saved and verified. Replay: NOT REQUESTED.", file=progress.stream, flush=True)
        progress.state("export", "VERIFIED", archive=str(destination), bytes=destination.stat().st_size,
                       sha256=archive_sha256, inventory_matches=report["inventory_matches"])
        _atomic_json(work / "EXPORT_REPORT.json", report)
        return destination, report
    finally:
        temporary.unlink(missing_ok=True)


def _read_archive_report(archive):
    with zipfile.ZipFile(archive, "r") as handle:
        info = handle.getinfo(REPORT_NAME)
        if info.file_size > 16_000_000:
            raise CompletionError("ARCHIVE_REPORT_TOO_LARGE")
        raw = handle.read(REPORT_NAME)
    report = _parse(raw)
    if report.get("schema") != SCHEMA or report.get("mode") != "PAPER":
        raise CompletionError("COMPLETE_ORIGINAL_ARCHIVE_REQUIRED")
    run_id = _run_id(report.get("run_id"))
    records = report.get("files")
    if not isinstance(records, dict) or not records:
        raise CompletionError("ARCHIVE_RECORDS_MISSING")
    for name, record in records.items():
        _safe_relative(name)
        if not (name.startswith("original/" + run_id + "/") or name.startswith("program/")):
            raise CompletionError("UNEXPECTED_ARCHIVE_FILE_SCOPE")
        if (not isinstance(record, dict) or type(record.get("bytes")) is not int or record["bytes"] < 0
                or not isinstance(record.get("sha256"), str) or len(record["sha256"]) != 64):
            raise CompletionError("INVALID_ARCHIVE_FILE_RECORD")
    return report, raw


def _replay_progress(reference, replay_parent):
    status_path = replay_parent / reference.name / "STATUS.json"
    original_sequence = read_json(reference / "RUN_SUMMARY.json").get("sequence")
    def probe():
        if not status_path.is_file():
            return {"phase": "Verifying complete recorded inputs", "done": 0, "total": None}
        try:
            status = read_json(status_path)
        except Exception:
            return None
        if status.get("state") == "STOPPED":
            return {"phase": "Replay closed; comparing complete output files", "total": None}
        return {"phase": "Replaying recorded decisions", "done": status.get("sequence", 0),
                "total": original_sequence, "unit": "decisions"}
    return probe


def _perform_replay(reference, replay_parent, progress, *, program_root=ROOT):
    # These imports occur only after an explicit replay request. No untrusted
    # archive program is executed; the current sealed package must match it.
    from CHECK_TOOL_RACK_PAPER import verify_manifest
    from engine_replay import ROOT as replay_root, SOURCE_ROOT, replay
    from strategy_core.paper_execution import PaperExecutioner
    from strategy_core.paper_runtime import source_manifest
    from run_validation import network_forbidden

    if Path(program_root).resolve() != ROOT or Path(replay_root).resolve() != ROOT or SOURCE_ROOT.resolve() != ROOT:
        raise CompletionError("UNEXPECTED_REPLAY_PROGRAM_ROOT")
    verify_manifest(ROOT, required=True)
    _, program = program_snapshot(reference, program_root=ROOT, progress=progress)
    header = program["header"]
    if (header.get("python") != platform.python_version()
            or header.get("implementation") != platform.python_implementation()):
        raise CompletionError("REPLAY_REQUIRES_CAPTURE_PYTHON_VERSION")
    if header.get("initial_state") != "FRESH_CONSTRUCTOR_NO_RESTORED_INVENTORY":
        raise CompletionError("REPLAY_REQUIRES_FRESH_ORIGINAL_CONSTRUCTOR")
    captured = read_json(reference / "RUN_MANIFEST.json")
    if any(captured.get(key) != value for key, value in source_manifest(ROOT).items()):
        raise CompletionError("REPLAY_ENGINE_PACKAGE_DIFFERS_FROM_CAPTURE")
    inspected = PaperExecutioner.inspect_journal(reference)
    if inspected.get("state") is None:
        raise CompletionError("ORIGINAL_COMMITTED_JOURNAL_UNAVAILABLE")
    inventory = read_json(reference / "ENGINE_OUTPUTS.json")
    progress.probe = _replay_progress(reference, replay_parent)
    progress.phase("Verifying complete recorded inputs")
    with (replay_parent.parent / "replay_console.txt").open("w", encoding="utf-8", newline="\n") as log:
        with redirect_stdout(log), redirect_stderr(log), network_forbidden():
            # Exactly one fully verified spool is created by this call. The
            # old _recording_header() full/decode/discard pass is not used.
            result = replay(reference / TAPE_NAME, replay_parent,
                            reference_dir=reference, reference_files=tuple(inventory["files"]))
    progress.probe = None
    progress.check()
    if (result.get("pass") is not True
            or result.get("validation_scope") != "ALL_PERSISTENT_ENGINE_OUTPUT_FILES"
            or result.get("files_compared") != len(inventory["files"])
            or result.get("calls") != program["tape_manifest"].get("written")):
        raise CompletionError("COMPLETE_REPLAY_PASS_NOT_ESTABLISHED")
    # Ensure source/provenance stayed fixed throughout the offline worker.
    program_snapshot(reference, program_root=ROOT, progress=progress)
    return result


def replay_published_archive(archive, work, status, progress, *, program_root=ROOT):
    run_id = status["run_id"]
    result = None
    try:
        progress.state("replay", "RUNNING", archive=str(archive), started_utc=utc_now())
        report, raw_report = _read_archive_report(archive)
        if run_id != report["run_id"]:
            raise CompletionError("REPLAY_ARCHIVE_RUN_ID_CHANGED")
        status["capture"] = dict(report["capture"])
        before = (archive.stat().st_size, archive.stat().st_mtime_ns)
        progress.phase("Fingerprinting selected original archive", total=archive.stat().st_size)
        archive_hash = file_sha256(archive, progress)
        reference = work / "reference" / run_id
        reference.mkdir(parents=True, exist_ok=False)
        _verify_archive(archive, report["files"], raw_report, progress,
                        extract_original_to=reference, run_id=run_id)
        if before != (archive.stat().st_size, archive.stat().st_mtime_ns):
            raise CompletionError("SELECTED_ARCHIVE_CHANGED")
        status["export"] = {"state": "VERIFIED", "archive": str(archive), "sha256": archive_hash,
                            "bytes": before[0], "origin": "EXISTING_PUBLISHED_ARCHIVE"}
        status["binding"] = {
            "input_tape_sha256": report["files"]["original/" + run_id + "/" + TAPE_NAME]["sha256"],
            "engine_inventory_sha256": report["files"]["original/" + run_id + "/ENGINE_OUTPUTS.json"]["sha256"],
            "archive_sha256": archive_hash,
            "program_manifest_sha256": report.get("program", {}).get("bundle_manifest_sha256")}
        if report.get("inventory_matches") is not True or report.get("program", {}).get("state") != "MATCHED_CAPTURE":
            raise CompletionError("ARCHIVED_ORIGINAL_OR_PROGRAM_REQUIRES_REVIEW")
        if report["capture"].get("state") != "REPORTED_COMPLETE":
            raise CompletionError("CAPTURE_NOT_COMPLETE_FOR_REPLAY")
        _, _, inventory, _ = _closed_run(reference)
        for name, record in inventory["files"].items():
            if report["files"].get("original/" + run_id + "/" + name) != record:
                raise CompletionError("ARCHIVED_ENGINE_INVENTORY_MISMATCH")
        _, program = program_snapshot(reference, program_root=program_root, progress=progress)
        # The saved program copy and currently selected validator must match.
        for name, record in program["files"].items():
            if report["files"].get("program/" + name) != record:
                raise CompletionError("ARCHIVED_PROGRAM_DIFFERS_FROM_VALIDATOR:" + name)
        result = _perform_replay(reference, work / "replay", progress, program_root=program_root)
        progress.state("replay", "PASS", result=result, completed_utc=utc_now(),
                       result_path=str(work / "REPLAY_RESULT.json"))
    except KeyboardInterrupt:
        progress.probe = None
        progress.terminal_state("replay", "INTERRUPTED", completed_utc=utc_now(),
                       failure={"type": "KeyboardInterrupt", "message": "Optional replay interrupted; published original archive retained."})
    except Exception as exc:
        progress.probe = None
        failure = {"type": type(exc).__name__, "message": str(exc)}
        if hasattr(exc, "report"):
            failure["first_divergence"] = exc.report
        state = "FAIL" if type(exc).__name__ in {"ReplayMismatch", "TapeError"} else "ERROR"
        progress.terminal_state("replay", state, failure=failure, completed_utc=utc_now())
    finally:
        progress.probe = None
        status["replay"]["result_path"] = str(work / "REPLAY_RESULT.json")
        _atomic_json(work / "REPLAY_RESULT.json", {"schema": "tachyos.explicit_optional_replay.v1",
            "run_id": run_id, "binding": status.get("binding"), "completion_tool": status["completion_tool"],
            "replay": status["replay"], "pass": status["replay"]["state"] == "PASS",
            "export": status["export"], "profitability_proven": False})
    return result


def _failed_status(status, progress, exc):
    with progress.lock:
        progress.phase_started = time.monotonic()
        status["progress"] = {"phase": "Completion interrupted" if isinstance(exc, KeyboardInterrupt) else "Completion failed",
                              "done": 0, "total": None, "unit": "bytes"}
    failed = {"state": "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "ERROR",
              "failure": {"type": type(exc).__name__, "message": str(exc)}}
    changed = False
    if status["export"]["state"] != "VERIFIED":
        status["export"].update(failed)
        changed = True
    if status["replay"]["state"] in {"REQUESTED", "RUNNING"}:
        status["replay"].update(failed)
        changed = True
    if not changed:
        status["completion_error"] = failed
    try:
        progress._publish()
    except Exception:
        pass


def complete_run(run_dir, *, output_dir=None, replay_requested=False, program_root=ROOT,
                 lease_path=None, heartbeat_seconds=HEARTBEAT_SECONDS, stream=None,
                 status_pointer=None, small_uploads=False):
    run = Path(run_dir).expanduser().resolve()
    if not run.is_dir():
        raise CompletionError("RECORDED_RUN_DIRECTORY_MISSING")
    _run_id(run.name)
    output = Path(output_dir).expanduser().resolve() if output_dir else run.parent / "PAPER_RESULTS"
    program_root = Path(program_root).expanduser().resolve()
    if any(output == protected or protected in output.parents for protected in (run, program_root)):
        raise CompletionError("COMPLETION_OUTPUT_MUST_BE_OUTSIDE_ORIGINAL_RUN_AND_PROGRAM")
    pointer = Path(status_pointer).expanduser().resolve() if status_pointer is not None else None
    if pointer is not None and any(pointer == protected or protected in pointer.parents for protected in (run, program_root)):
        raise CompletionError("STATUS_POINTER_MUST_BE_OUTSIDE_ORIGINAL_RUN_AND_PROGRAM")
    with exclusive_completion_lease(lease_path):
        work, tag, status = _new_status(run.name, run, output, replay_requested=replay_requested)
        if pointer is not None:
            pointer.parent.mkdir(parents=True, exist_ok=True)
            if pointer.exists():
                raise CompletionError("STATUS_POINTER_ALREADY_EXISTS")
            _atomic_json(pointer, {"run_id": run.name, "status_path": status["status_path"]})
        print("Completion status: " + status["status_path"], file=stream or sys.stdout, flush=True)
        with Progress(work / STATUS_NAME, status, interval=heartbeat_seconds, stream=stream) as progress:
            try:
                archive, _ = export_original(run, work, tag, status, progress, program_root=program_root)
                if small_uploads:
                    from make_upload_parts import make_uploads
                    progress.state("uploads", "RUNNING")
                    progress.phase("Creating smaller upload files from the verified original ZIP")
                    uploads = make_uploads(results_dir=output, source=archive,
                        expected_run_id=run.name, expected_sha256=status["export"]["sha256"],
                        status_file=work / "UPLOAD_STATUS.json", stream=progress.stream)
                    with progress.lock:
                        status["uploads"] = uploads
                    progress._publish()
                    if uploads.get("state") != "COMPLETE" or uploads.get("all_verified") is not True:
                        raise CompletionError("SMALL_UPLOADS_FAILED: " + str(uploads.get("error")))
                if replay_requested:
                    replay_published_archive(archive, work, status, progress, program_root=program_root)
                progress.phase("Completion finished")
            except BaseException as exc:
                _failed_status(status, progress, exc)
                raise
        return status


def replay_archive(archive_path, *, output_dir=None, program_root=ROOT, lease_path=None,
                   heartbeat_seconds=HEARTBEAT_SECONDS, stream=None):
    archive = Path(archive_path).expanduser().resolve()
    if not archive.is_file():
        raise CompletionError("PUBLISHED_ORIGINAL_ARCHIVE_MISSING")
    report, _ = _read_archive_report(archive)
    output = Path(output_dir).expanduser().resolve() if output_dir else archive.parent
    with exclusive_completion_lease(lease_path):
        work, _, status = _new_status(report["run_id"], archive, output, replay_requested=True)
        with Progress(work / STATUS_NAME, status, interval=heartbeat_seconds, stream=stream) as progress:
            try:
                replay_published_archive(archive, work, status, progress, program_root=program_root)
                progress.phase("Optional replay finished")
            except BaseException as exc:
                _failed_status(status, progress, exc)
                raise
        return status


def result_code(status):
    if status.get("completion_error"):
        return 130 if status["completion_error"].get("state") == "INTERRUPTED" else 1
    if status.get("uploads", {}).get("state", "NOT_REQUESTED") not in {"NOT_REQUESTED", "COMPLETE"}:
        return 1
    replay_state = status["replay"]["state"]
    if replay_state == "INTERRUPTED":
        return 130
    if replay_state not in {"NOT_REQUESTED", "PASS"}:
        return 2
    if (status["export"]["state"] != "VERIFIED"
            or status["capture"].get("state") != "REPORTED_COMPLETE"
            or status["capture"].get("unresolved_inventory_count") != 0
            or status.get("program", {}).get("state", "MATCHED_CAPTURE") != "MATCHED_CAPTURE"
            or status["export"].get("inventory_matches", True) is not True):
        return 2
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--run", type=Path)
    selection.add_argument("--run-receipt", type=Path)
    selection.add_argument("--archive", type=Path, help="An already published original ZIP; requires --replay.")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--status-pointer", type=Path)
    parser.add_argument("--small-uploads", action="store_true", help="Create checked small upload ZIPs after saving the complete original.")
    parser.add_argument("--replay", action="store_true", help="Explicit optional replay after the verified original ZIP is available.")
    args = parser.parse_args(argv)
    if args.archive and not args.replay:
        parser.error("--archive requires --replay; an existing archive is never silently rerun")
    try:
        if args.archive:
            status = replay_archive(args.archive, output_dir=args.output_dir)
        else:
            run = args.run
            if args.run_receipt:
                receipt = read_json(args.run_receipt)
                if receipt.get("mode") != "PAPER" or not isinstance(receipt.get("run_dir"), str):
                    raise CompletionError("EXACT_PAPER_RUN_RECEIPT_REQUIRED")
                run = Path(receipt["run_dir"])
            status = complete_run(run, output_dir=args.output_dir, replay_requested=args.replay,
                                  status_pointer=args.status_pointer, small_uploads=args.small_uploads)
        print("\nCapture: " + status["capture"]["state"] + " | Export: " + status["export"]["state"]
              + " | Replay: " + status["replay"]["state"], flush=True)
        print("Completion status: " + status["status_path"], flush=True)
        if status["replay"].get("result_path"):
            print("Exact replay result: " + status["replay"]["result_path"], flush=True)
        if status["capture"].get("unresolved_inventory_count"):
            print("Unresolved PAPER positions remain explicit; reconcile them before another run.", flush=True)
        if status["replay"]["state"] == "NOT_REQUESTED":
            print("Optional exact replay: 07_REPLAY_CLOSED_PAPER_RUN.cmd using the saved ZIP.", flush=True)
        print("This completion report does not certify trading profitability.", flush=True)
        return result_code(status)
    except KeyboardInterrupt:
        print("\nCompletion interrupted. Original run files and any already published ZIP remain available.", flush=True)
        return 130
    except Exception as exc:
        print("\nCompletion failed: " + type(exc).__name__ + ": " + str(exc), flush=True)
        print("Keep the original run folder and the completion status for review.", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
