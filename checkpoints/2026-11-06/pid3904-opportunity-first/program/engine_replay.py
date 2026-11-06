"""Synchronous-engine input capture and offline replay of the frozen engine.

The source in source_original is imported unchanged. The only interposition is
the paper_runtime module's clock object, scoped to one synchronous call. No
global time monkeypatch, decision substitution, state restoration, or network.
"""
from __future__ import annotations

from contextlib import contextmanager
from collections import deque
import hashlib
import json
import platform
from pathlib import Path
import sys
import threading
import time
from typing import Callable

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT / "source_original" if (ROOT / "source_original").is_dir() else ROOT
sys.path.insert(0, str(SOURCE_ROOT))

from strategy_core import paper_runtime as runtime
from strategy_core.paper_execution import PaperExecutioner
from bounded_tape import TapeError, TapeWriter, iter_tape
from input_codec import pin, pin_call

_CLOCK_OWNER = threading.Lock()


class ReplayMismatch(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__(json.dumps(report, sort_keys=True))


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_hashes():
    """All 66 original core/config/UI files, not only the Commander."""
    return {p.relative_to(SOURCE_ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((SOURCE_ROOT / "strategy_core").rglob("*"))
            if p.is_file() and p.suffix in (".py", ".json", ".html", ".css", ".js")}


def verify_bundled_source():
    expected = json.loads((ROOT / "SOURCE_SHA256.json").read_text(encoding="utf-8"))
    actual = source_hashes()
    if actual != expected:
        raise TapeError("BUNDLED_SOURCE_OR_CONFIG_CHANGED")
    if Path(runtime.__file__).resolve() != (SOURCE_ROOT / "strategy_core/paper_runtime.py").resolve():
        raise TapeError("UNEXPECTED_IMPORTED_ENGINE")
    return actual


class ScriptClock:
    """Authored fixture clock. Each actual engine clock read advances 10 us."""
    def __init__(self, base, increment=0.00001):
        self.base = float(base)
        self.increment = increment
        self.reads = 0

    def __call__(self):
        value = self.base + self.reads * self.increment
        self.reads += 1
        return value


class ClockProxy:
    def __init__(self, supplier: Callable[[], float]):
        self.supplier = supplier
        self.values = []
        self.read_elapsed_ns = 0

    def time(self):
        before = time.perf_counter_ns()
        value = self.supplier()
        self.values.append(value)
        self.read_elapsed_ns += time.perf_counter_ns() - before
        return value

    @staticmethod
    def sleep(seconds):
        # Only the original filesystem retry path uses this operation.
        time.sleep(seconds)


class ReplayClock:
    def __init__(self, values, call_index):
        self.values = tuple(values)
        self.index = 0
        self.call_index = call_index

    def __call__(self):
        if self.index == len(self.values):
            raise ReplayMismatch({"call_index": self.call_index, "path": "clock_reads",
                                  "reason": "CLOCK_TAPE_EXHAUSTED", "actual_reads": self.index + 1})
        value = self.values[self.index]
        self.index += 1
        return value

    def verify_consumed(self):
        if self.index != len(self.values):
            raise ReplayMismatch({"call_index": self.call_index, "path": "clock_reads",
                                  "reason": "UNCONSUMED_CLOCK_READS",
                                  "expected_reads": len(self.values), "actual_reads": self.index})


@contextmanager
def runtime_clock(clock):
    """This standalone runner owns one engine thread; restore even on failure."""
    if not _CLOCK_OWNER.acquire(blocking=False):
        raise TapeError("CONCURRENT_OR_NESTED_ENGINE_CLOCK_UNSUPPORTED")
    previous = runtime.time
    runtime.time = clock
    try:
        yield
    finally:
        runtime.time = previous
        _CLOCK_OWNER.release()


def pointers(engine):
    # Existing scalar heads; never walk or project mutable strategy state.
    return {"decision_seq": engine._seq, "decision_sha256": engine._previous_hash,
            "journal_seq": engine.executor._seq, "journal_sha256": engine.executor._last_hash}


def require_fresh(run_dir, *, allowed_launcher_files=()):
    """Permit only explicitly named launcher files, never prior engine state."""
    allowed = frozenset(allowed_launcher_files)
    if not allowed.issubset({"console.log"}):
        raise TapeError("UNSUPPORTED_FRESH_DIRECTORY_EXCEPTION")
    if run_dir.is_symlink():
        raise TapeError("FRESH_RUN_DIRECTORY_MUST_NOT_BE_SYMLINK")
    if run_dir.exists():
        for path in run_dir.iterdir():
            if path.name not in allowed or not path.is_file() or path.is_symlink():
                raise TapeError("FRESH_EMPTY_RUN_DIRECTORY_REQUIRED")
    run_dir.mkdir(parents=True, exist_ok=True)


class RecordedEngine:
    """Optional evidence capture around the unchanged original engine.

    Capture failure marks evidence unusable and still returns the original
    engine outcome. It does not become a Commander decision or safety veto.
    Engine exceptions retain their original behavior and invalidate the tape.

    Inputs must remain privately owned throughout the synchronous call, as in
    the original feed/launcher. Caller mutations after the call returns cannot
    change pinned history. Concurrent mutation during the call is unsupported.
    """
    def __init__(self, run_dir, tape_path, *, input_kind, clock_supplier=time.time,
                 queue_capacity=64, max_bytes=512_000_000, writer_delay_s=0,
                 allowed_launcher_files=()):
        self.run_dir = Path(run_dir)
        require_fresh(self.run_dir, allowed_launcher_files=allowed_launcher_files)
        hashes = verify_bundled_source()
        self.metrics = {"pin_us": deque(maxlen=4096), "finish_enqueue_us": deque(maxlen=4096),
                        "clock_read_us": deque(maxlen=4096), "clock_read_count": 0,
                        "calls_measured": 0, "sample_limit": 4096,
                        "capture_work_max_us": 0.0, "capture_work_total_us": 0.0}
        self._close_started = False
        self._close_manifest = None
        recorder_files = ("engine_replay.py", "input_codec.py", "bounded_tape.py", "snapshot_delta.py",
                          "capture_session.py", "finish_recorded_run.py", "TOOL_RACK_PAPER.py")
        recorder_hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                           for name in recorder_files if (ROOT / name).is_file()}
        self.writer = TapeWriter(Path(tape_path), header={
            "boundary": "ToolRackPaperEngine.process/settle", "input_kind": input_kind,
            "initial_state": "FRESH_CONSTRUCTOR_NO_RESTORED_INVENTORY",
            "run_id": self.run_dir.name, "source_hashes": hashes,
            "python": platform.python_version(), "implementation": platform.python_implementation(),
            "platform": platform.platform(), "transport_replay": False,
            "runtime_revision": runtime.RUNTIME_REVISION,
            "recorder_source_hashes": recorder_hashes,
            "clock_scope": "paper_runtime.time.time at init/process/close; each actual read",
            "excluded_nondeterminism": "executor lock UUID/PID/time, absent from committed outputs",
        }, queue_capacity=queue_capacity, max_bytes=max_bytes, writer_delay_s=writer_delay_s)
        self.engine = None
        try:
            self._call("init", {}, clock_supplier)
        except BaseException:
            self.writer.close()
            raise

    def _call(self, method, arguments, supplier):
        before = time.perf_counter_ns()
        pinned = None
        try:
            pinned = pin_call(method, arguments)
        except Exception as exc:
            self.writer.fail("PIN_FAILED:" + type(exc).__name__)
        pin_us = (time.perf_counter_ns() - before) / 1000
        self.metrics["pin_us"].append(pin_us)
        clock = ClockProxy(supplier)
        try:
            with runtime_clock(clock):
                if method == "init":
                    self.engine = runtime.ToolRackPaperEngine(self.run_dir, source_root=SOURCE_ROOT)
                    result = None
                else:
                    result = getattr(self.engine, method)(**arguments)
        except BaseException as exc:
            self.writer.fail("ENGINE_EXCEPTION:" + type(exc).__name__)
            raise
        before = time.perf_counter_ns()
        if pinned is not None:
            try:
                self.writer.submit(pin({"call": pinned, "clocks": tuple(clock.values),
                                        "expected": pointers(self.engine)}))
            except Exception as exc:
                self.writer.fail("ENQUEUE_FAILED:" + type(exc).__name__)
        finish_us = (time.perf_counter_ns() - before) / 1000
        self.metrics["finish_enqueue_us"].append(finish_us)
        self.metrics["clock_read_count"] += len(clock.values)
        clock_us = clock.read_elapsed_ns / 1000
        self.metrics["clock_read_us"].append(clock_us)
        capture_us = pin_us + finish_us + clock_us
        self.metrics["calls_measured"] += 1
        self.metrics["capture_work_total_us"] += capture_us
        self.metrics["capture_work_max_us"] = max(self.metrics["capture_work_max_us"], capture_us)
        return result

    def invoke(self, method, arguments, *, clock_supplier=time.time):
        if self._close_started:
            raise TapeError("ENGINE_ALREADY_CLOSED")
        if method not in ("process", "settle"):
            raise ValueError("PROCESS_OR_SETTLE_REQUIRED")
        return self._call(method, arguments, clock_supplier)

    def close(self, *, reason, clock_supplier=time.time):
        if self._close_started:
            return dict(self._close_manifest or self.writer.close())
        self._close_started = True
        try:
            self._call("close", {"reason": reason}, clock_supplier)
        finally:
            self._close_manifest = self.writer.close()
        return dict(self._close_manifest)


def first_difference(expected, actual, path="$"):
    if type(expected) is not type(actual):
        return {"path": path, "expected": expected, "actual": actual, "reason": "TYPE_OR_VALUE"}
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            return {"path": path, "expected_keys": list(expected), "actual_keys": list(actual),
                    "reason": "KEYS"}
        for key in expected:
            difference = first_difference(expected[key], actual[key], path + "." + str(key))
            if difference:
                return difference
    elif isinstance(expected, (tuple, list)):
        if len(expected) != len(actual):
            return {"path": path, "expected_length": len(expected), "actual_length": len(actual),
                    "reason": "LENGTH"}
        for index, (left, right) in enumerate(zip(expected, actual)):
            difference = first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
    elif expected != actual:
        return {"path": path, "expected": expected, "actual": actual, "reason": "VALUE"}
    return None


def _journal_difference(reference_dir, replay_dir, sequence):
    name = f"paper_journal/{sequence:08d}.json"
    left, right = Path(reference_dir) / name, Path(replay_dir) / name
    if left.exists() and right.exists():
        return {"file": name, **(first_difference(json.loads(left.read_text(encoding="utf-8")),
                                                  json.loads(right.read_text(encoding="utf-8"))) or {})}
    return {"file": name, "expected_exists": left.exists(), "actual_exists": right.exists()}


def _decision_record(directory, sequence):
    with (Path(directory) / "decisions.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record["sequence"] == sequence:
                return record
    return None


def replay(tape_path, parent_dir, *, reference_dir=None, allow_python_mismatch=False,
           reference_files=None):
    """Verify complete input evidence before instantiating a fresh engine."""
    hashes = verify_bundled_source()
    header, calls = iter_tape(Path(tape_path), expected_source_hashes=hashes)
    try:
        if header.get("initial_state") != "FRESH_CONSTRUCTOR_NO_RESTORED_INVENTORY":
            raise TapeError("UNSUPPORTED_INITIAL_STATE")
        if not allow_python_mismatch and (header.get("python") != platform.python_version()
                or header.get("implementation") != platform.python_implementation()):
            raise TapeError("PYTHON_ENVIRONMENT_DIFFERS_EXPLICIT_EXPERIMENT_REQUIRED")
        run_id = header["run_id"]
        if not isinstance(run_id, str) or Path(run_id).name != run_id or run_id in (".", "..") or "\\" in run_id:
            raise TapeError("INVALID_RECORDED_RUN_ID")
        run_dir = Path(parent_dir) / run_id
        require_fresh(run_dir)
    except BaseException:
        calls.close()
        raise
    engine = None
    count = 0
    try:
        for count, envelope in enumerate(calls, 1):
            call = envelope["call"]
            method, arguments = call["method"], call["arguments"]
            clock = ReplayClock(envelope["clocks"], count)
            with runtime_clock(ClockProxy(clock)):
                if method == "init":
                    if engine is not None or arguments:
                        raise TapeError("INVALID_INIT_CALL")
                    engine = runtime.ToolRackPaperEngine(run_dir, source_root=SOURCE_ROOT)
                elif method in ("process", "settle", "close") and engine is not None:
                    getattr(engine, method)(**arguments)
                else:
                    raise TapeError("INVALID_ENGINE_CALL")
            clock.verify_consumed()
            actual = pointers(engine)
            expected = envelope["expected"]
            if expected != actual:
                report = {"call_index": count, "method": method,
                          "reason": "FIRST_ENGINE_OUTPUT_DIVERGENCE",
                          "expected": expected, "actual": actual}
                if reference_dir:
                    if expected["decision_seq"] == actual["decision_seq"] and expected["decision_sha256"] != actual["decision_sha256"]:
                        report["difference"] = {"file": "decisions.jsonl", **(first_difference(
                            _decision_record(reference_dir, expected["decision_seq"]),
                            _decision_record(run_dir, actual["decision_seq"])) or {})}
                    elif expected["journal_seq"] == actual["journal_seq"]:
                        report["difference"] = _journal_difference(reference_dir, run_dir, actual["journal_seq"])
                raise ReplayMismatch(report)
        inspected = PaperExecutioner.inspect_journal(run_dir)
        files = compare_directories(reference_dir, run_dir, reference_files=reference_files) if reference_dir else None
        if files is not None and not files["pass"]:
            raise ReplayMismatch({"call_index": count, "method": "close",
                                  "reason": "FINAL_OUTPUT_FILES_DIVERGED",
                                  "difference": files["differences"][0]})
        return {"pass": True, "calls": count, "run_dir": str(run_dir),
                "journal_records": inspected["records"], "journal_sha256": inspected["sha256"],
                "input_kind": header["input_kind"], "transport_replay": False,
                "validation_scope": "ALL_PERSISTENT_ENGINE_OUTPUT_FILES" if files else "DECISION_AND_LEDGER_HEADS_ONLY",
                "files_compared": files["files_compared"] if files else None,
                "python_version_match": header["python"] == platform.python_version()}
    finally:
        calls.close()
        # On a divergence, release the original writer without adding fictional
        # process calls/settlements. Close outputs are marked failed explicitly.
        if engine is not None and not engine.executor._closed:
            with runtime_clock(ClockProxy(lambda: 0.0)):
                engine.close(reason="REPLAY_FAILED_NOT_ACCEPTED")


def compare_directories(expected_dir, actual_dir, *, reference_files=None):
    """Exact bytes across all persistent original-engine outputs; no normalization."""
    left, right = Path(expected_dir), Path(actual_dir)
    def inventory(root):
        return {p.relative_to(root).as_posix(): file_sha256(p)
                for p in sorted(root.rglob("*")) if p.is_file() and p.name != "paper_writer.lock"}
    if reference_files is None:
        a = inventory(left)
    else:
        names = tuple(reference_files)
        if len(set(names)) != len(names):
            raise TapeError("DUPLICATE_REFERENCE_OUTPUT")
        a = {}
        for name in names:
            path = Path(name)
            if (not isinstance(name, str) or path.is_absolute() or ".." in path.parts
                    or "\\" in name or not (left / path).is_file()):
                raise TapeError("INVALID_REFERENCE_OUTPUT")
            a[name] = file_sha256(left / path)
    b = inventory(right)
    differences = []
    for name in sorted(a.keys() | b.keys()):
        if a.get(name) != b.get(name):
            item = {"file": name, "expected_sha256": a.get(name), "actual_sha256": b.get(name)}
            if name in a and name in b and name.endswith(".json"):
                item["difference"] = first_difference(json.loads((left / name).read_text(encoding="utf-8")),
                                                       json.loads((right / name).read_text(encoding="utf-8")))
            elif name in a and name in b and name.endswith(".jsonl"):
                from itertools import zip_longest
                with (left / name).open(encoding="utf-8") as aa, (right / name).open(encoding="utf-8") as bb:
                    for line, (av, bv) in enumerate(zip_longest(aa, bb), 1):
                        if av != bv:
                            item["line"] = line
                            item["difference"] = first_difference(json.loads(av) if av else None,
                                                                   json.loads(bv) if bv else None)
                            break
            differences.append(item)
    return {"pass": not differences, "files_compared": len(a.keys() | b.keys()),
            "differences": differences,
            "scope": "DECLARED_ENGINE_OUTPUTS_VS_ALL_REPLAY_OUTPUTS" if reference_files is not None else "ALL_PERSISTENT_ENGINE_OUTPUTS",
            "excluded": ["ephemeral paper_writer.lock", "live supporting files outside declared engine inventory"] if reference_files is not None else ["ephemeral paper_writer.lock only"],
            "output_sha256": a}
