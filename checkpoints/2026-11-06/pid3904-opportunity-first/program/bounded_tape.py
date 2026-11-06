"""Bounded, ordered engine-input evidence; never an execution authority.

The producer queues references to already pinned input envelopes. Only the
worker encodes, hashes, and writes them. A failed capture is rejected by the
reader; it cannot block or change an engine decision. A complete manifest
requires an orderly shutdown, not merely an existing tape. This is not a
power-loss durability or real-time latency guarantee.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import tempfile
import threading

from input_codec import decode, encode
from snapshot_delta import SnapshotDeltaDecoder, SnapshotDeltaEncoder, SnapshotDeltaError

SCHEMA = "tachyos.engine_input_tape.v2"
MANIFEST_SCHEMA = "tachyos.engine_input_tape_manifest.v2"
LEGACY_SCHEMA = "tachyos.engine_input_tape.v1"
LEGACY_MANIFEST_SCHEMA = "tachyos.engine_input_tape_manifest.v1"
ZERO = "0" * 64
MAX_RECORD_BYTES = 64_000_000


class TapeError(RuntimeError):
    """The evidence is incomplete, incompatible, or internally inconsistent."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


class TapeWriter:
    """One bounded FIFO and one background writer.

    submit() accepts only objects already pinned by input_codec.pin(). It does
    not inspect or copy their contents. Header data is detached once at setup.
    close() is a shutdown operation and may wait up to timeout_s for the worker.
    Repeated close calls return the same result; submit after close returns False.
    """

    def __init__(self, path: Path, *, header: dict, queue_capacity=64,
                 max_bytes=512_000_000, writer_delay_s=0, snapshot_delta=True):
        self.path = Path(path)
        self.manifest_path = self.path.with_suffix(".manifest.json")
        self.queue_capacity = queue_capacity
        self.max_bytes = max_bytes
        self.writer_delay_s = writer_delay_s
        self.schema = SCHEMA if snapshot_delta else LEGACY_SCHEMA
        self._manifest_schema = MANIFEST_SCHEMA if snapshot_delta else LEGACY_MANIFEST_SCHEMA
        self._lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._abort = threading.Event()
        self._ready_event = threading.Event()
        self._ready = False
        self._queue = None
        self._thread = None
        self._closed = False
        self._failure = None
        self._final_manifest = None
        self._owns_tape = False
        self._end_written = False
        self._attempted = self._accepted = self._written = self._dropped = 0
        self._bytes = 0
        self._queue_high_water = 0
        self._backlog_high_water = 0
        self._last = ZERO
        self._header_hash = None
        self._delta = SnapshotDeltaEncoder() if snapshot_delta else None
        self._delta_health = self._delta.stats() if self._delta is not None else {"enabled": False}
        try:
            if (type(queue_capacity) is not int or queue_capacity < 1
                    or type(max_bytes) is not int or max_bytes < 1
                    or type(writer_delay_s) not in (int, float)
                    or not math.isfinite(writer_delay_s) or writer_delay_s < 0
                    or type(snapshot_delta) is not bool
                    or not isinstance(header, dict)):
                raise ValueError("INVALID_CONFIGURATION")
            self._header = deepcopy(header)
            self._queue = queue.Queue(maxsize=queue_capacity)
            self._thread = threading.Thread(target=self._write_loop,
                                           name="TachyosInputEvidenceWriter", daemon=True)
            self._thread.start()
        except Exception as exc:
            self.fail("INITIALIZATION:" + type(exc).__name__ + ":" + str(exc))
            if self._thread is not None and self._thread.ident is None:
                self._thread = None

    def fail(self, reason):
        """Invalidate an open capture without raising into the engine."""
        try:
            with self._lock:
                if self._final_manifest is not None:
                    return
                self._failure = self._failure or str(reason)[:240]
            self._abort.set()
            self._ready_event.set()
        except Exception:
            # No disk access, logging, or engine action on this path.
            self._abort.set()
            self._ready_event.set()

    def submit(self, immutable_call) -> bool:
        try:
            with self._lock:
                if self._closed:
                    return False
                self._attempted += 1
                if self._failure is not None or self._queue is None:
                    self._dropped += 1
                    return False
                sequence = self._accepted + 1
                try:
                    self._queue.put_nowait((sequence, immutable_call))
                except queue.Full:
                    self._dropped += 1
                    self._failure = "QUEUE_OVERFLOW"
                    self._abort.set()
                    return False
                self._accepted += 1
                self._queue_high_water = max(self._queue_high_water, 1, self._queue.qsize())
                self._backlog_high_water = max(self._backlog_high_water, self._accepted - self._written)
                return True
        except Exception as exc:
            self.fail("SUBMIT:" + type(exc).__name__)
            return False

    def _write_record(self, handle, kind, sequence, payload):
        record = {"schema": self.schema, "kind": kind, "sequence": sequence,
                  "previous_sha256": self._last, "payload": payload}
        record["sha256"] = _digest(record)
        raw = _canonical(record) + b"\n"
        if len(raw) > MAX_RECORD_BYTES:
            raise TapeError("RECORD_BYTE_LIMIT")
        if self._bytes + len(raw) > self.max_bytes:
            raise TapeError("CAPTURE_BYTE_LIMIT")
        handle.write(raw)
        with self._lock:
            self._bytes += len(raw)
            self._last = record["sha256"]

    def _write_loop(self):
        try:
            if self._abort.is_set():
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.manifest_path.exists():
                raise TapeError("MANIFEST_ALREADY_EXISTS")
            with self.path.open("xb") as handle:
                self._owns_tape = True
                self._write_record(handle, "HEADER", 0, self._header)
                # Startup readiness confirms an actual write/flush, not only a
                # Python-buffered header. Per-call dispatch still performs no I/O.
                handle.flush()
                with self._lock:
                    self._header_hash = self._last
                    self._ready = True
                self._ready_event.set()
                while not self._abort.is_set():
                    try:
                        sequence, payload = self._queue.get(timeout=0.05)
                    except queue.Empty:
                        with self._lock:
                            if self._closed:
                                break
                        continue
                    if self.writer_delay_s and self._abort.wait(self.writer_delay_s):
                        break
                    encoded = (self._delta.encode(payload, sequence)
                               if self._delta is not None else encode(payload))
                    self._write_record(handle, "CALL", sequence, encoded)
                    delta_health = self._delta.stats() if self._delta is not None else {"enabled": False}
                    with self._lock:
                        self._written += 1
                        self._delta_health = delta_health
                if not self._abort.is_set():
                    with self._lock:
                        if not self._closed or self._accepted != self._written:
                            raise TapeError("INCOMPLETE_DRAIN")
                    self._write_record(handle, "END", self._written + 1,
                                       {"calls": self._written})
                    self._end_written = True
                handle.flush()
                os.fsync(handle.fileno())
        except Exception as exc:
            self.fail("WRITER:" + type(exc).__name__ + ":" + str(exc))
        finally:
            self._ready_event.set()
            # Release queued payload references after a failure, without waiting
            # for a shutdown sentinel to fit into a full or abandoned queue.
            if self._queue is not None:
                while True:
                    try:
                        self._queue.get_nowait()
                    except queue.Empty:
                        break

    def _manifest(self):
        alive = self._thread is not None and self._thread.is_alive()
        with self._lock:
            return {"schema": self._manifest_schema, "tape_schema": self.schema,
                    "complete": bool(self._closed and self._end_written and not alive
                                     and self._failure is None and self._dropped == 0
                                     and self._attempted == self._accepted == self._written),
                    "attempted": self._attempted, "accepted": self._accepted,
                    "written": self._written, "dropped": self._dropped,
                    "bytes": self._bytes, "last_sha256": self._last,
                    "header_sha256": self._header_hash, "reason": self._failure,
                    "queue_capacity": self.queue_capacity, "max_bytes": self.max_bytes,
                    "writer_alive": alive, "queue_high_water": self._queue_high_water,
                    "backlog_high_water": self._backlog_high_water,
                    "delta": deepcopy(self._delta_health)}

    def wait_ready(self, timeout_s=3.0) -> bool:
        """Wait only at startup for HEADER creation; never an engine decision."""
        if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s)
                or timeout_s < 0):
            return False
        self._ready_event.wait(timeout_s)
        with self._lock:
            return self._ready and self._failure is None and not self._closed

    def health(self) -> dict:
        """Current evidence health without I/O, serialization, or engine actions.

        backlog includes the in-flight writer call. Failure is visible before
        close; queued accepted calls discarded after failure remain in backlog
        because they were never written. A live healthy capture is not complete.
        """
        with self._lock:
            alive = self._thread is not None and self._thread.is_alive()
            complete = bool(self._closed and self._end_written and not alive
                            and self._failure is None and self._dropped == 0
                            and self._attempted == self._accepted == self._written)
            status = ("failed" if self._failure is not None else "complete" if complete
                      else "draining" if self._closed else "running" if self._ready else "starting")
            return {"status": status, "ready": self._ready, "complete": complete,
                    "closed": self._closed, "writer_alive": alive,
                    "failure": self._failure, "reason": self._failure,
                    "attempted": self._attempted, "accepted": self._accepted,
                    "written": self._written, "dropped": self._dropped,
                    "backlog": self._accepted - self._written,
                    "backlog_high_water": self._backlog_high_water,
                    "queue_depth": self._queue.qsize() if self._queue is not None else 0,
                    "queue_high_water": self._queue_high_water,
                    "queue_highwater": self._queue_high_water,
                    "queue_capacity": self.queue_capacity,
                    "bytes": self._bytes, "max_bytes": self.max_bytes,
                    "tape_schema": self.schema, "delta": deepcopy(self._delta_health)}

    def close(self, timeout_s=10) -> dict:
        with self._close_lock:
            if self._final_manifest is not None:
                return dict(self._final_manifest)
            if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s)
                    or timeout_s < 0):
                self.fail("INVALID_CLOSE_TIMEOUT")
                timeout_s = 0
            with self._lock:
                self._closed = True
            if self._thread is not None:
                self._thread.join(timeout=timeout_s)
                if self._thread.is_alive():
                    self.fail("WRITER_SHUTDOWN_TIMEOUT")
            manifest = self._manifest()
            # A timed-out writer can still finish an OS write. Do not publish any
            # manifest in that case; a missing manifest is always rejected.
            if self._owns_tape and not manifest["writer_alive"]:
                temporary = None
                try:
                    if self.manifest_path.exists():
                        raise TapeError("MANIFEST_ALREADY_EXISTS")
                    fd, name = tempfile.mkstemp(prefix=self.manifest_path.name + ".",
                                                suffix=".tmp", dir=self.path.parent)
                    temporary = Path(name)
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(_canonical(manifest) + b"\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, self.manifest_path)
                    temporary = None
                except Exception as exc:
                    self.fail("MANIFEST:" + type(exc).__name__ + ":" + str(exc))
                    manifest = self._manifest()
                finally:
                    if temporary is not None:
                        try:
                            temporary.unlink()
                        except OSError:
                            pass
            self._final_manifest = manifest
            return dict(manifest)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TapeError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _invalid_constant(value):
    raise TapeError("NONFINITE_JSON_NUMBER:" + value)


def _parse(raw):
    try:
        return json.loads(raw, object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise TapeError("INVALID_JSON:" + type(exc).__name__) from exc


def _is_hash(value):
    return (isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


def _validate_call(payload, number, closed):
    try:
        envelope = decode(payload)
    except Exception as exc:
        raise TapeError("INPUT_DECODE:" + type(exc).__name__ + ":" + str(exc)) from exc
    if (not isinstance(envelope, dict) or set(envelope) != {"call", "clocks", "expected"}
            or not isinstance(envelope["call"], dict)
            or set(envelope["call"]) != {"method", "arguments"}
            or not isinstance(envelope["call"]["arguments"], dict)):
        raise TapeError("CALL_ENVELOPE_INVALID")
    method = envelope["call"]["method"]
    if (closed or method not in ("init", "process", "settle", "close")
            or (number == 1) != (method == "init")
            or method == "init" and envelope["call"]["arguments"]):
        raise TapeError("CALL_LIFECYCLE_INVALID")
    clocks, expected = envelope["clocks"], envelope["expected"]
    if (not isinstance(clocks, (tuple, list))
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in clocks)
            or not isinstance(expected, dict)
            or set(expected) != {"decision_seq", "decision_sha256", "journal_seq", "journal_sha256"}
            or any(type(expected[key]) is not int or expected[key] < 0
                   for key in ("decision_seq", "journal_seq"))
            or any(not _is_hash(expected[key])
                   for key in ("decision_sha256", "journal_sha256"))):
        raise TapeError("CALL_CLOCKS_OR_EXPECTED_POINTERS_INVALID")
    return method == "close"


class _VerifiedCalls:
    """A private verified disk spool: later source-file edits cannot affect replay."""

    def __init__(self, spool, tape_schema):
        self._spool = spool
        self._delta = SnapshotDeltaDecoder() if tape_schema == SCHEMA else None

    def __iter__(self):
        return self

    def __next__(self):
        if self._spool is None:
            raise StopIteration
        raw = self._spool.readline()
        if not raw:
            self.close()
            raise StopIteration
        try:
            record = _parse(raw)
            payload = (self._delta.expand(record["payload"], record["sequence"])
                       if self._delta is not None else record["payload"])
            return decode(payload)
        except Exception:
            self.close()
            raise

    def close(self):
        if self._spool is not None:
            self._spool.close()
            self._spool = None

    def __del__(self):
        self.close()


def iter_tape(path: Path, *, expected_source_hashes=None):
    """Verify the entire tape before returning (header, decoded-call iterator).

    Verification retains at most one record plus two bounded snapshot windows.
    Verified compact call bytes (not expanded snapshots)
    are spooled to a private temporary file, avoiding an unverified second read
    of a tape that another process could change. Exhaust or close the iterator
    to release the spool. Both source tape and manifest must already be closed.
    """
    path = Path(path)
    spool = None
    try:
        with path.with_suffix(".manifest.json").open("rb") as handle:
            raw_manifest = handle.read(65_537)
        if len(raw_manifest) > 65_536:
            raise TapeError("MANIFEST_TOO_LARGE")
        manifest = _parse(raw_manifest)
        if (not isinstance(manifest, dict)
                or manifest.get("schema") not in (MANIFEST_SCHEMA, LEGACY_MANIFEST_SCHEMA)
                or manifest.get("complete") is not True or manifest.get("reason") is not None
                or manifest.get("writer_alive") is not False):
            raise TapeError("CAPTURE_NOT_COMPLETE")
        tape_schema = SCHEMA if manifest["schema"] == MANIFEST_SCHEMA else LEGACY_SCHEMA
        if tape_schema == SCHEMA and manifest.get("tape_schema") != SCHEMA:
            raise TapeError("MANIFEST_TAPE_SCHEMA_INVALID")
        delta = SnapshotDeltaDecoder() if tape_schema == SCHEMA else None
        for name in ("attempted", "accepted", "written", "dropped", "bytes"):
            if type(manifest.get(name)) is not int or manifest[name] < 0:
                raise TapeError("MANIFEST_COUNTS_INVALID")
        if (manifest["dropped"] != 0
                or not manifest["attempted"] == manifest["accepted"] == manifest["written"]):
            raise TapeError("CAPTURE_COUNTS_INCOMPLETE")
        spool = tempfile.TemporaryFile(mode="w+b")
        previous = ZERO
        header = None
        calls = total_bytes = sequence = 0
        closed = ended = False
        with path.open("rb") as handle:
            while True:
                raw = handle.readline(MAX_RECORD_BYTES + 1)
                if not raw:
                    break
                if len(raw) > MAX_RECORD_BYTES or not raw.endswith(b"\n"):
                    raise TapeError("RECORD_TRUNCATED_OR_TOO_LARGE")
                total_bytes += len(raw)
                if total_bytes > manifest["bytes"]:
                    raise TapeError("TAPE_EXCEEDS_MANIFEST_SIZE")
                record = _parse(raw)
                if (not isinstance(record, dict)
                        or set(record) != {"schema", "kind", "sequence", "previous_sha256", "payload", "sha256"}
                        or record["schema"] != tape_schema or type(record["sequence"]) is not int
                        or record["sequence"] != sequence or record["previous_sha256"] != previous
                        or not _is_hash(record["sha256"]) or ended):
                    raise TapeError("RECORD_SEQUENCE_OR_SHAPE_INVALID")
                digest = record.pop("sha256")
                if _digest(record) != digest:
                    raise TapeError("RECORD_HASH_MISMATCH")
                previous = digest
                if sequence == 0:
                    header = record["payload"]
                    if (record["kind"] != "HEADER" or not isinstance(header, dict)
                            or not isinstance(header.get("source_hashes"), dict)
                            or not header["source_hashes"]):
                        raise TapeError("HEADER_OR_SOURCE_PROVENANCE_INVALID")
                    if digest != manifest.get("header_sha256"):
                        raise TapeError("HEADER_HASH_MISMATCH")
                    if expected_source_hashes is not None and header["source_hashes"] != expected_source_hashes:
                        raise TapeError("SOURCE_HASH_MISMATCH")
                elif record["kind"] == "CALL":
                    calls += 1
                    try:
                        payload = (delta.expand(record["payload"], sequence)
                                   if delta is not None else record["payload"])
                    except SnapshotDeltaError as exc:
                        raise TapeError("SNAPSHOT_DELTA:" + str(exc)) from exc
                    closed = _validate_call(payload, calls, closed)
                    spool.write(raw)
                elif record["kind"] == "END":
                    if record["payload"] != {"calls": calls} or calls < 2 or not closed:
                        raise TapeError("END_OR_CLOSE_LIFECYCLE_MISSING")
                    ended = True
                else:
                    raise TapeError("UNEXPECTED_RECORD_KIND")
                sequence += 1
        if (not ended or header is None or total_bytes != manifest["bytes"]
                or calls != manifest["written"] or previous != manifest.get("last_sha256")):
            raise TapeError("TAPE_TRUNCATED_OR_MANIFEST_MISMATCH")
        spool.seek(0)
        result = _VerifiedCalls(spool, tape_schema)
        spool = None
        return header, result
    except TapeError:
        raise
    except Exception as exc:
        raise TapeError("TAPE_READ:" + type(exc).__name__ + ":" + str(exc)) from exc
    finally:
        if spool is not None:
            spool.close()


def load_tape(path: Path, *, expected_source_hashes=None):
    """Convenience loader for small tapes; iter_tape avoids retaining all calls."""
    header, calls = iter_tape(path, expected_source_hashes=expected_source_hashes)
    try:
        return header, list(calls)
    finally:
        calls.close()
