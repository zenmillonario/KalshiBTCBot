"""Lossless upload packaging for one explicitly selected, already exported PAPER run.

This program only reads a completed results ZIP. It neither imports the trading
program nor starts a replay. The small review ZIP is explicitly a subset; all
bytes of the complete results ZIP are preserved in the numbered upload ZIPs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import threading
import time
import uuid
import zipfile


DEFAULT_RESULTS = Path(r"E:\TachyosToolRackPaper\PAPER_RESULTS")
SCHEMA = "tachyos.lossless_upload_parts.v1"
CHUNK_BYTES = 95_000_000
MAX_ZIP_BYTES = 100_000_000
BUFFER_BYTES = 1_048_576
REVIEW_LIMIT = 25_000_000
OPTIONAL_MEMBER_LIMIT = 5_000_000
REVIEW_NAME = "00_SEND_FIRST_REVIEW.zip"
PAYLOAD_NAME = "archive_chunk.bin"
REPORT_NAME = "COMPLETION_REPORT.json"
REQUIRED_RUN_FILES = (
    "RUN_MANIFEST.json", "RUN_SUMMARY.json", "PAPER_LEDGER.json",
    "STATUS.json", "CAPTURE_STATUS.json", "ENGINE_OUTPUTS.json",
    "replay_capture/engine_inputs.manifest.json",
)
OPTIONAL_RUN_FILES = ("leg_performance.jsonl", "mission_history.jsonl", "console.log", "ERROR.json")
OPTIONAL_PROGRAM_FILES = (
    "program/SOURCE_SHA256.json", "program/APPROVED_STRATEGY_CHANGES.json",
    "program/NEXT_RUN_STATUS.json", "program/TOOL_RACK_PAPER_BUNDLE_MANIFEST.json",
)


class UploadError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + "\n").encode("utf-8")


def _atomic_json(path, value):
    path = Path(path)
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp",
                                          dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(json_bytes(value))
            handle.flush()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _snapshot(path):
    info = Path(path).stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_json_member(archive, name, limit=REVIEW_LIMIT):
    if archive.getinfo(name).file_size > limit:
        raise UploadError("Metadata is too large to inspect safely: " + name)
    value = json.loads(archive.read(name))
    if not isinstance(value, dict):
        raise UploadError("Expected a JSON object in " + name)
    return value


class Progress:
    """A heartbeat whose lock never covers console or disk output."""
    def __init__(self, stream):
        self.stream = stream
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.phase = "Starting"
        self.done = 0
        self.total = None
        self.started = time.monotonic()
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=0.2)

    def set(self, phase, total=None):
        with self.lock:
            self.phase, self.done, self.total = phase, 0, total
        self.show()

    def add(self, amount):
        with self.lock:
            self.done += amount

    def show(self):
        with self.lock:
            phase, done, total = self.phase, self.done, self.total
        detail = "working" if total is None else "{:.1f} / {:.1f} MB".format(done / 1e6, total / 1e6)
        print("{} | {} | elapsed {:.0f}s".format(phase, detail, time.monotonic() - self.started),
              file=self.stream, flush=True)

    def _heartbeat(self):
        while not self.stop.wait(5.0):
            self.show()


def select_source(results_dir, explicit=None):
    results_dir = Path(results_dir).resolve()
    if not results_dir.is_dir():
        raise UploadError("Results folder is missing: " + str(results_dir))
    if explicit is None:
        raise UploadError("An exact completed source ZIP is required; no previous or newest run is selected")
    path = Path(explicit).resolve()
    if path.parent != results_dir:
        raise UploadError("The source ZIP must be directly inside the selected PAPER_RESULTS folder")
    if not path.is_file() or path.suffix.lower() != ".zip" or ".partial" in path.name.lower():
        raise UploadError("The exact completed source ZIP is missing or incomplete: " + str(path))
    return path


def inspect_source(source, expected_run_id=None):
    with zipfile.ZipFile(source, "r") as archive:
        report = _read_json_member(archive, REPORT_NAME)
        run_id = report.get("run_id")
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", run_id):
            raise UploadError("The completed archive has no safe exact run identity")
        if expected_run_id is not None and run_id != expected_run_id:
            raise UploadError("The completed archive identifies another run")
        prefix = "original/" + run_id + "/"
        items = archive.infolist()
        names = [item.filename for item in items]
        if len(names) != len(set(names)):
            raise UploadError("The results ZIP has duplicate member names")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise UploadError("Unexpected archive path: " + name)
            if name.startswith("original/") and not name.startswith(prefix):
                raise UploadError("The archive contains an original folder for another run")
        # Validate the COMPLETE source independently of the bounded preview.
        # The review is a subset, never a requirement that the entire recorded
        # journal fit into one 25 MB attachment. The numbered parts carry every
        # original byte and are subsequently checksum-verified.
        required = {prefix + name for name in REQUIRED_RUN_FILES} | {REPORT_NAME}
        missing = sorted(required - set(names))
        if missing:
            raise UploadError("The complete exported results ZIP is missing: " + ", ".join(missing))
        summary = _read_json_member(archive, prefix + "RUN_SUMMARY.json")
        run_manifest = _read_json_member(archive, prefix + "RUN_MANIFEST.json")
        report = _read_json_member(archive, REPORT_NAME)
        for label, value in (("RUN_MANIFEST", run_manifest), ("COMPLETION_REPORT", report)):
            if value.get("run_id") != run_id or value.get("mode") != "PAPER":
                raise UploadError(label + " identifies another run or a non-PAPER mode")
        # A constructor-only capture closes before latest_status receives the
        # repeated identity fields. Require the exact manifest/report binding
        # above, an empty decisions stream, and no nonzero recorded sequence.
        if summary.get("run_id", run_id) != run_id or summary.get("mode", "PAPER") != "PAPER":
            raise UploadError("RUN_SUMMARY identifies another run or a non-PAPER mode")
        if "run_id" not in summary or "mode" not in summary:
            if (summary.get("sequence", 0) != 0 or prefix + "decisions.jsonl" not in names
                    or archive.getinfo(prefix + "decisions.jsonl").file_size != 0):
                raise UploadError("Missing summary identity is allowed only for a closed run with zero decisions")
        if summary.get("state") != "STOPPED":
            raise UploadError("This helper only packages the already stopped PAPER run")
        journals = sorted(name for name in names if name.startswith(prefix + "paper_journal/")
                          and not name.endswith("/"))
        if not journals:
            raise UploadError("The original paper journal is missing from the results ZIP")
        inventory = [{"name": item.filename, "bytes": item.file_size,
                      "compressed_bytes": item.compress_size, "crc32": "%08x" % item.CRC,
                      "compression": item.compress_type, "directory": item.is_dir()}
                     for item in items]
        sizes = {item.filename: item.file_size for item in items}
        # Reserve space for REVIEW_SCOPE, inventory and embedded manifest. The
        # original ZIP is never touched, even if one journal file is huge.
        budget = REVIEW_LIMIT - 2_000_000
        essentials = [REPORT_NAME, prefix + "RUN_MANIFEST.json", prefix + "RUN_SUMMARY.json"]
        selected = list(essentials)
        total = sum(sizes[name] for name in selected)
        if total > budget:
            raise UploadError("Essential completion/summary metadata alone exceed the bounded review budget; original archive remains intact")
        omissions = {}
        optional_run_meta = [prefix + name for name in REQUIRED_RUN_FILES if name not in
                             ("RUN_MANIFEST.json", "RUN_SUMMARY.json")]
        for name in optional_run_meta:
            if total + sizes[name] <= budget:
                selected.append(name)
                total += sizes[name]
            else:
                omissions[name] = "Large review metadata omitted from first-review subset; complete bytes remain in numbered parts"

        # Prioritize the start/end and evenly dispersed *complete* journal
        # entries, so a large run is represented throughout its timeline.
        # No partial journal files, sampling of their bytes, or fabricated
        # journal entries are permitted. Every omitted entry is enumerated.
        for name in _journal_review_priority(journals):
            if total + sizes[name] <= budget:
                selected.append(name)
                total += sizes[name]
            else:
                omissions[name] = "Full paper-journal entry exceeds remaining first-review budget; exact entry remains in numbered parts"

        missing_optional = []
        for name in tuple(prefix + relative for relative in OPTIONAL_RUN_FILES) + OPTIONAL_PROGRAM_FILES:
            if name not in sizes:
                missing_optional.append(name)
            elif sizes[name] > OPTIONAL_MEMBER_LIMIT:
                omissions[name] = "Optional review member exceeds 5 MB; complete bytes remain in numbered parts"
            elif total + sizes[name] > budget:
                omissions[name] = "Optional review budget; complete bytes remain in numbered parts"
            else:
                selected.append(name)
                total += sizes[name]
        included = set(selected)
        omitted = [{"name": item["name"], "bytes": item["bytes"],
                    "reason": omissions.get(item["name"],
                        "Outside preliminary review subset; complete bytes remain in numbered parts")}
                   for item in inventory if item["name"] not in included and not item["directory"]]
        reviewed_journals = len(set(journals) & included)
        return {"run_id": run_id, "inventory": inventory, "selected": sorted(selected), "omitted": omitted,
                "missing_optional": missing_optional, "review_input_bytes": total,
                "reviewed_journals": reviewed_journals, "total_journals": len(journals),
                "report": report}



def _journal_review_priority(journals):
    """Yield journal names in deterministic across-run coverage order.

    Endpoints first, then recursively interleaved midpoints. When all entries
    fit, the exact same complete journal set is selected as before.
    """
    count = len(journals)
    if not count:
        return
    yield journals[0]
    if count > 1:
        yield journals[-1]
    intervals = [(0, count - 1)]
    while intervals:
        following = []
        for low, high in intervals:
            mid = (low + high) // 2
            if mid > low and mid < high:
                yield journals[mid]
                following.extend(((low, mid), (mid, high)))
        intervals = following


def _part_name(number, total):
    return "01_RUN_PART_{:03d}_OF_{:03d}.zip".format(number, total)


def write_parts(source, working, transfer_id, source_size, chunk_bytes, progress, source_details):
    part_count = math.ceil(source_size / chunk_bytes)
    if not 1 <= part_count <= 1000:
        raise UploadError("Expected between 1 and 1000 upload pieces")
    records = []
    complete_digest = hashlib.sha256()
    progress.set("Making numbered upload pieces", source_size)
    with source.open("rb") as original:
        for index in range(1, part_count + 1):
            offset = original.tell()
            wanted = min(chunk_bytes, source_size - offset)
            name = _part_name(index, part_count)
            digest = hashlib.sha256()
            written = 0
            with zipfile.ZipFile(working / name, "x", compression=zipfile.ZIP_STORED,
                                 allowZip64=True) as part:
                with part.open(PAYLOAD_NAME, "w", force_zip64=True) as target:
                    while written < wanted:
                        block = original.read(min(BUFFER_BYTES, wanted - written))
                        if not block:
                            raise UploadError("The original ZIP changed or ended during copying")
                        target.write(block)
                        digest.update(block)
                        complete_digest.update(block)
                        written += len(block)
                        progress.add(len(block))
                record = {"part_number": index, "file_name": name, "payload_name": PAYLOAD_NAME,
                          "offset": offset, "bytes": written, "sha256": digest.hexdigest()}
                records.append(record)
                part_info = {"schema": SCHEMA, "run_id": source_details["run_id"], "transfer_id": transfer_id,
                             "scope": "EXACT_RAW_BYTE_SLICE_OF_THE_COMPLETE_ORIGINAL_RESULTS_ZIP",
                             "source_archive_name": source.name, "source_size": source_size,
                             "part_count": part_count, **record,
                             "complete_manifest_in": _part_name(part_count, part_count)}
                part.writestr("PART_INFO.json", json_bytes(part_info))
                if index == part_count:
                    if original.read(1):
                        raise UploadError("The original ZIP grew while copying")
                    manifest = {"schema": SCHEMA, "run_id": source_details["run_id"], "transfer_id": transfer_id,
                                "created_utc": utc_now(), "state": "VERIFIED_ON_PUBLICATION",
                                "source_archive_name": source.name, "source_size": source_size,
                                "source_sha256": complete_digest.hexdigest(),
                                "part_count": part_count, "parts": records,
                                "review_zip": REVIEW_NAME,
                                "reconstruction": "Read archive_chunk.bin from each numbered ZIP in part_number order, concatenate the raw payloads, then verify source_size and source_sha256. Do not concatenate the outer ZIP containers.",
                                "scope": "Lossless transport of the existing complete results ZIP; no new replay, source-match, profitability, or strategy claim",
                                "original_report_program_state": source_details["report"].get("program", {}).get("state"),
                                "original_report_capture_state": source_details["report"].get("capture", {}).get("state"),
                                "original_report_replay": source_details["report"].get("replay"),
                                "original_files_modified": False}
                    part.writestr("TRANSFER_MANIFEST.json", json_bytes(manifest))
            if (working / name).stat().st_size >= MAX_ZIP_BYTES:
                raise UploadError("An upload piece unexpectedly exceeds the 100 MB limit")
    return manifest


def verify_parts(directory, manifest, progress=None):
    """Verify each payload and the exact concatenated original, without unpacking it."""
    if progress is not None:
        progress.set("Checking every upload piece", manifest["source_size"])
    aggregate = hashlib.sha256()
    total = 0
    records = manifest["parts"]
    if len(records) != manifest["part_count"]:
        raise UploadError("Part count does not match the transfer manifest")
    for number, record in enumerate(records, 1):
        if record["part_number"] != number or record["offset"] != total:
            raise UploadError("Part sequence or offsets do not match")
        path = Path(directory) / record["file_name"]
        if path.stat().st_size >= MAX_ZIP_BYTES:
            raise UploadError("An upload piece exceeds the size limit")
        with zipfile.ZipFile(path, "r") as archive:
            expected_names = [PAYLOAD_NAME, "PART_INFO.json"]
            if number == len(records):
                expected_names.append("TRANSFER_MANIFEST.json")
            if sorted(archive.namelist()) != sorted(expected_names):
                raise UploadError("Unexpected contents in upload piece " + path.name)
            info = _read_json_member(archive, "PART_INFO.json", limit=100_000)
            if (info.get("run_id") != manifest["run_id"] or info.get("transfer_id") != manifest["transfer_id"]
                    or info.get("source_archive_name") != manifest["source_archive_name"]
                    or info.get("source_size") != manifest["source_size"]
                    or info.get("part_count") != len(records)
                    or any(info.get(key) != value for key, value in record.items())):
                raise UploadError("Upload piece metadata does not match: " + path.name)
            digest = hashlib.sha256()
            length = 0
            with archive.open(PAYLOAD_NAME, "r") as payload:
                for block in iter(lambda: payload.read(BUFFER_BYTES), b""):
                    digest.update(block)
                    aggregate.update(block)
                    length += len(block)
                    if progress is not None:
                        progress.add(len(block))
            if length != record["bytes"] or digest.hexdigest() != record["sha256"]:
                raise UploadError("Upload piece checksum failed: " + path.name)
            total += length
            if number == len(records) and _read_json_member(archive, "TRANSFER_MANIFEST.json") != manifest:
                raise UploadError("The embedded complete transfer manifest does not match")
    if total != manifest["source_size"] or aggregate.hexdigest() != manifest["source_sha256"]:
        raise UploadError("The upload pieces do not reconstruct the exact original ZIP")
    return True


def make_review(source, working, details, manifest, progress):
    records = []
    progress.set("Making the small first-review ZIP", details["review_input_bytes"])
    target_path = working / REVIEW_NAME
    with zipfile.ZipFile(source, "r") as original, zipfile.ZipFile(
            target_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6,
            allowZip64=True) as target:
        for name in details["selected"]:
            digest = hashlib.sha256()
            copied = 0
            with original.open(name, "r") as reader, target.open(name, "w", force_zip64=True) as writer:
                for block in iter(lambda: reader.read(BUFFER_BYTES), b""):
                    writer.write(block)
                    digest.update(block)
                    copied += len(block)
                    progress.add(len(block))
            records.append({"name": name, "bytes": copied, "sha256": digest.hexdigest()})
        report = details["report"]
        scope = {"schema": "tachyos.preliminary_review_subset.v1", "run_id": manifest["run_id"],
                 "created_utc": utc_now(), "complete_recording": False,
                 "purpose": "Small preliminary trade review. Use the numbered ZIP pieces for the complete recording and full trajectory/replay analysis.",
                 "source_archive_name": source.name, "source_size": manifest["source_size"],
                 "source_sha256": manifest["source_sha256"],
                 "transfer_id": manifest["transfer_id"], "part_count": manifest["part_count"],
                 "full_original_archive_preserved_in_numbered_parts": True,
                 "members_are_exact_original_bytes": True, "truncated_members": [],
                 "paper_journal_members_in_preview": details["reviewed_journals"],
                 "paper_journal_members_in_original": details["total_journals"],
                 "paper_journal_preview_complete": details["reviewed_journals"] == details["total_journals"],
                 "included_members": records, "omitted_members": details["omitted"],
                 "missing_optional_members": details["missing_optional"],
                 "original_report_program_state": report.get("program", {}).get("state"),
                 "original_report_capture_state": report.get("capture", {}).get("state"),
                 "original_report_replay": report.get("replay"),
                 "replay_performed_by_this_helper": False, "strategy_modified": False,
                 "original_files_modified": False}
        extras = {"REVIEW_SCOPE.json": json_bytes(scope),
                  "SOURCE_ARCHIVE_INVENTORY.json": json_bytes({
                      "schema": SCHEMA, "run_id": manifest["run_id"],
                      "source_archive_name": source.name,
                      "source_sha256": manifest["source_sha256"],
                      "members": details["inventory"]}),
                  "TRANSFER_MANIFEST.json": json_bytes(manifest)}
        total = sum(record["bytes"] for record in records) + sum(len(data) for data in extras.values())
        if total > REVIEW_LIMIT:
            raise UploadError("The preliminary review including its metadata exceeds 25 MB")
        for name, data in extras.items():
            target.writestr(name, data)
    progress.set("Checking the small review ZIP", total)
    with zipfile.ZipFile(target_path, "r") as archive:
        if set(archive.namelist()) != set(details["selected"]) | set(extras):
            raise UploadError("The review archive file list does not match")
        for record in records:
            digest = hashlib.sha256()
            copied = 0
            with archive.open(record["name"], "r") as handle:
                for block in iter(lambda: handle.read(BUFFER_BYTES), b""):
                    digest.update(block)
                    copied += len(block)
                    progress.add(len(block))
            if copied != record["bytes"] or digest.hexdigest() != record["sha256"]:
                raise UploadError("A review member changed during copying: " + record["name"])
        for name, expected in extras.items():
            data = archive.read(name)
            if data != expected:
                raise UploadError("Review metadata verification failed: " + name)
            progress.add(len(data))
    return scope


def _publish_directory(working, final):
    if final.exists():
        raise UploadError("Refusing to overwrite an existing upload folder: " + str(final))
    os.rename(working, final)


def make_uploads(*, results_dir=DEFAULT_RESULTS, source=None, status_file=None,
                 chunk_bytes=CHUNK_BYTES, stream=None, expected_run_id=None, expected_sha256=None):
    stream = sys.stdout if stream is None else stream
    status = {"schema": SCHEMA, "run_id": expected_run_id, "created_utc": utc_now(),
              "state": "RUNNING", "all_verified": False, "phase": "Starting",
              "original_files_modified": False, "strategy_modified": False,
              "replay_requested": False}
    status_path = Path(status_file).resolve() if status_file is not None else None
    owned_status = False
    working = None
    try:
        if status_path is not None:
            # The launcher supplies a new attempt path. Never overwrite an
            # existing user file, even when a CLI argument is mistaken.
            with status_path.open("xb") as handle:
                handle.write(json_bytes(status))
            owned_status = True

        def update(**fields):
            status.update(fields, updated_utc=utc_now())
            if owned_status:
                _atomic_json(status_path, status)

        if not isinstance(chunk_bytes, int) or isinstance(chunk_bytes, bool) or not 1 <= chunk_bytes <= CHUNK_BYTES:
            raise UploadError("Chunk size must be between 1 and 95,000,000 bytes")
        results = Path(results_dir).resolve()
        selected = select_source(results, source)
        before = _snapshot(selected)
        source_size = before[2]
        if source_size <= 0:
            raise UploadError("The selected results ZIP is empty")
        update(source=str(selected), source_size=source_size)
        print("Selected completed run ZIP: " + str(selected), file=stream, flush=True)
        print("The saved recording is read only. No trading or replay will start.", file=stream, flush=True)
        with Progress(stream) as progress:
            progress.set("Checking the exported run")
            details = inspect_source(selected, expected_run_id=expected_run_id)
            run_id = details["run_id"]
            update(run_id=run_id)
            if _snapshot(selected) != before:
                raise UploadError("The source ZIP changed while its contents were inspected")
            count = math.ceil(source_size / chunk_bytes)
            if not 1 <= count <= 1000:
                raise UploadError("Expected between 1 and 1000 upload pieces")
            needed = source_size + REVIEW_LIMIT + 64_000_000 + count * 4096
            free = shutil.disk_usage(results).free
            if free < needed:
                raise UploadError("Not enough free disk space for separate upload copies: need about {:.0f} MB; free {:.0f} MB".format(needed / 1e6, free / 1e6))
            transfer_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:12]
            final = results / (run_id + "_SMALL_UPLOADS_" + transfer_id)
            working = results / (final.name + ".working")
            if final.exists():
                raise UploadError("Refusing to overwrite an existing upload folder")
            working.mkdir(exist_ok=False)
            update(working_dir=str(working), phase="Making numbered upload pieces", part_count=count)
            manifest = write_parts(selected, working, transfer_id, source_size, chunk_bytes, progress, details)
            update(phase="Checking every upload piece", source_sha256=manifest["source_sha256"])
            if expected_sha256 is not None and manifest["source_sha256"] != expected_sha256:
                raise UploadError("The source ZIP does not match the verified export SHA256")
            verify_parts(working, manifest, progress)
            update(phase="Making and checking the small review ZIP")
            make_review(selected, working, details, manifest, progress)
            with (working / "TRANSFER_MANIFEST.json").open("xb") as handle:
                handle.write(json_bytes(manifest))
            if details["reviewed_journals"] == details["total_journals"]:
                journal_explanation = "It includes every complete paper-journal member.\r\n"
            else:
                journal_explanation = ("It includes {}/{} complete journal members. The omitted entries are\r\n"
                    "named in REVIEW_SCOPE.json, and their exact bytes remain in numbered parts.\r\n".format(
                    details["reviewed_journals"], details["total_journals"]))
            instructions = (
                "SEND 00_SEND_FIRST_REVIEW.zip to ChatGPT first.\r\n\r\n"
                "It contains available summary/ledger and other bounded review files.\r\n"
                + journal_explanation +
                "It is a clearly labelled subset, not the complete recording.\r\n\r\n"
                "For the complete recording, send ALL 01_RUN_PART_...zip files in numbered order.\r\n"
                "Each numbered ZIP is under 100 MB. Do not unzip the pieces before sending them.\r\n"
                "The first-review ZIP includes the transfer manifest. The last numbered part does too.\r\n\r\n"
                "Keep the original large ZIP. Nothing in it or the original run was changed.\r\n"
                "This helper did not run a new PAPER session or replay.\r\n"
            )
            with (working / "READ_ME_FIRST.txt").open("x", encoding="utf-8", newline="") as handle:
                handle.write(instructions)
            if _snapshot(selected) != before:
                raise UploadError("The original results ZIP changed during upload packaging")
            progress.set("Publishing verified upload files")
            _publish_directory(working, final)
            parts = [str(final / record["file_name"]) for record in manifest["parts"]]
            update(state="COMPLETE", phase="Complete", all_verified=True,
                   output_dir=str(final), working_dir=None, review_zip=str(final / REVIEW_NAME),
                   parts=parts, source_sha256=manifest["source_sha256"],
                   original_report_program_state=details["report"].get("program", {}).get("state"),
                   original_report_capture_state=details["report"].get("capture", {}).get("state"),
                   original_report_replay=details["report"].get("replay"), completed_utc=utc_now())
        print("\nREADY. Every upload piece has been checked against the original ZIP.", file=stream, flush=True)
        print("SEND FIRST: " + status["review_zip"], file=stream, flush=True)
        print("Then send the {} numbered 01_RUN_PART ZIP file(s) for the complete recording.".format(status["part_count"]),
              file=stream, flush=True)
        print("Upload folder: " + status["output_dir"], file=stream, flush=True)
        return status
    except (Exception, KeyboardInterrupt) as exc:
        status.update(state="ERROR", phase="Upload packaging failed", all_verified=False,
                      error={"type": type(exc).__name__, "message": str(exc)}, updated_utc=utc_now())
        if working is not None and working.is_dir():
            status["unfinished_working_dir"] = str(working)
        if owned_status:
            try:
                _atomic_json(status_path, status)
            except Exception as status_error:
                status["status_write_error"] = type(status_error).__name__ + ": " + str(status_error)
        print("\nUpload packaging failed: " + type(exc).__name__ + ": " + str(exc), file=stream, flush=True)
        if status_path is not None:
            print("Status path: " + str(status_path), file=stream, flush=True)
        print("The original results ZIP and run were not changed.", file=stream, flush=True)
        return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--source", type=Path, required=True, help="Exact completed results ZIP; no newest-run fallback")
    parser.add_argument("--status-file", type=Path, help="New status JSON path supplied by the display launcher")
    args = parser.parse_args(argv)
    result = make_uploads(results_dir=args.results_dir, source=args.source, status_file=args.status_file)
    return 0 if result.get("state") == "COMPLETE" and result.get("all_verified") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
