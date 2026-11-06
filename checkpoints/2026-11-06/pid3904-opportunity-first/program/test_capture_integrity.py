"""Focused evidence-integrity checks; no trading or strategy assertions.

These cases protect the capture/replay acceptance claims: detached mutable
inputs, bounded failure detection, verified complete tapes, original-source
identity, clock consumption, and a complete engine-call lifecycle.  The small
tapes below are explicitly synthetic and do not execute the trading engine.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
from types import MappingProxyType
import unittest
from unittest.mock import patch

from engine_replay import ReplayClock, ReplayMismatch
from bounded_tape import TapeError, TapeWriter, iter_tape
from input_codec import CodecError, encode, pin, pin_call
from strategy_core.paper_feed import FeedSnapshot, freeze_data


_HASHES = {"strategy_core/paper_runtime.py": "a" * 64}


class CaptureIntegrityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tachyos_integrity_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    @staticmethod
    def feed():
        return FeedSnapshot(
            1, 1001.0, None, None, (),
            freeze_data({"btc_current": False, "synthetic": True}),
        )

    @staticmethod
    def envelope(method, arguments=None, clocks=()):
        return pin({
            "call": pin_call(method, {} if arguments is None else arguments),
            "clocks": tuple(clocks),
            "expected": {
                "decision_seq": 0,
                "decision_sha256": "0" * 64,
                "journal_seq": 1,
                "journal_sha256": "1" * 64,
            },
        })

    def writer(self, name, **options):
        path = self.root / (name + ".jsonl")
        writer = TapeWriter(path, header={
            "input_kind": "SYNTHETIC_INTEGRITY_FIXTURE",
            "source_hashes": dict(_HASHES),
        }, **options)
        return path, writer

    def complete_tape(self, name):
        path, writer = self.writer(name)
        writer.submit(self.envelope("init", clocks=(1000.0,)))
        writer.submit(self.envelope(
            "close", {"reason": "SYNTHETIC_INTEGRITY_COMPLETE"}, (1002.0,)))
        manifest = writer.close(timeout_s=3.0)
        self.assertTrue(manifest["complete"], manifest)
        header, calls = iter_tape(path, expected_source_hashes=_HASHES)
        self.assertEqual(header["source_hashes"], _HASHES)
        self.assertEqual([item["call"]["method"] for item in calls], ["init", "close"])
        return path

    def assert_rejected_before_iteration(self, path, hashes=None):
        # Validation must fail at the entry point, before a caller could create
        # an engine or consume even the first call from unaccepted evidence.
        with self.assertRaises(TapeError):
            iter_tape(path, expected_source_hashes=_HASHES if hashes is None else hashes)

    def test_mutable_history_is_pinned_before_async_serialization(self):
        history = [{"time": 940.0, "close": 100.0,
                    "detail": {"samples": [1, 2]}}]
        arguments = {"feed": self.feed(), "historical_candles": history,
                     "entry_window_closed": False}
        pinned = self.envelope("process", arguments, (1001.0,))

        # Mutate once before enqueueing so this check cannot pass merely
        # because the worker won a scheduling race and serialized too early.
        history[0]["close"] = 999.0
        history[0]["detail"]["samples"].append(3)
        history.append({"time": 1000.0, "close": 999.0})
        arguments["entry_window_closed"] = True
        arguments["feed"] = replace(arguments["feed"], generation=999)

        path, writer = self.writer("pin_detachment", writer_delay_s=.01)
        writer.submit(self.envelope("init", clocks=(1000.0,)))
        writer.submit(pinned)
        history.clear()  # Caller remains free to mutate while the worker runs.
        writer.submit(self.envelope("close", {"reason": "DONE"}, (1002.0,)))
        manifest = writer.close(timeout_s=3.0)
        self.assertTrue(manifest["complete"], manifest)
        _, stream = iter_tape(path, expected_source_hashes=_HASHES)
        recorded = list(stream)[1]["call"]["arguments"]
        self.assertEqual(recorded["historical_candles"], [
            {"time": 940.0, "close": 100.0, "detail": {"samples": [1, 2]}}])
        self.assertIs(recorded["entry_window_closed"], False)
        self.assertIsInstance(recorded["feed"], FeedSnapshot)
        self.assertEqual(recorded["feed"].generation, 1)

    def test_retained_shallow_frozen_source_rejects_mutable_descendants(self):
        # A frozen dataclass plus a mapping proxy is insufficient if any child
        # remains mutable. Deferred writer validation must discover that fact.
        for child in ([], {}):
            with self.subTest(child_type=type(child).__name__):
                unsafe = replace(self.feed(), source_status=MappingProxyType({
                    "synthetic": True, "nested": child}))
                pinned = self.envelope("process", {"feed": unsafe}, (1001.0,))
                with self.assertRaisesRegex(CodecError, "RETAINED_SOURCE_MUTABLE"):
                    encode(pinned)
                path, writer = self.writer("mutable_" + type(child).__name__)
                writer.submit(self.envelope("init", clocks=(1000.0,)))
                writer.submit(pinned)
                writer.submit(self.envelope("close", {"reason": "DONE"}, (1002.0,)))
                manifest = writer.close(timeout_s=3.0)
                self.assertFalse(manifest["complete"], manifest)
                self.assert_rejected_before_iteration(path)

    def test_slow_writer_queue_overflow_invalidates_evidence(self):
        path, writer = self.writer("overflow", queue_capacity=1, writer_delay_s=.02)
        writer.submit(self.envelope("init", clocks=(1000.0,)))
        event = self.envelope("process", {"feed": self.feed()}, (1001.0,))
        for _ in range(128):
            writer.submit(event)
        writer.submit(self.envelope("close", {"reason": "DONE"}, (1002.0,)))
        manifest = writer.close(timeout_s=3.0)
        self.assertFalse(manifest["complete"], manifest)
        self.assertGreater(manifest["dropped"], 0, manifest)
        self.assert_rejected_before_iteration(path)

    def test_byte_limit_and_writer_io_failure_reject_evidence(self):
        with self.subTest(failure="byte_limit"):
            path, writer = self.writer("byte_limit", max_bytes=1)
            writer.submit(self.envelope("init", clocks=(1000.0,)))
            writer.submit(self.envelope("close", {"reason": "DONE"}, (1002.0,)))
            manifest = writer.close(timeout_s=3.0)
            self.assertFalse(manifest["complete"], manifest)
            self.assert_rejected_before_iteration(path)

        with self.subTest(failure="writer_open_error"):
            path = self.root / "writer_io_failure.jsonl"
            original_open = Path.open

            def fail_capture_open(candidate, *args, **kwargs):
                mode = args[0] if args else kwargs.get("mode", "r")
                if candidate == path and mode == "xb":
                    raise OSError("SYNTHETIC_CAPTURE_OPEN_FAILURE")
                return original_open(candidate, *args, **kwargs)

            # Inject failure only on this tape's worker open; allow its failure
            # manifest and all other files to use their original operations.
            with patch.object(Path, "open", fail_capture_open):
                _, writer = self.writer("writer_io_failure")
                writer.submit(self.envelope("init", clocks=(1000.0,)))
                writer.submit(self.envelope("close", {"reason": "DONE"}, (1002.0,)))
                manifest = writer.close(timeout_s=3.0)
            self.assertFalse(manifest["complete"], manifest)
            self.assert_rejected_before_iteration(path)

    def test_truncation_and_missing_manifest_reject_before_iteration(self):
        for damage in ("truncate", "missing_manifest"):
            with self.subTest(damage=damage):
                path = self.complete_tape(damage)
                if damage == "truncate":
                    original = path.read_bytes()
                    path.write_bytes(original[:-17])
                else:
                    path.with_suffix(".manifest.json").unlink()
                self.assert_rejected_before_iteration(path)

    def test_different_source_hashes_reject_before_iteration(self):
        path = self.complete_tape("source_mismatch")
        self.assert_rejected_before_iteration(path, {
            "strategy_core/paper_runtime.py": "b" * 64})

    def test_clock_extra_or_missing_reads_reject(self):
        extra = ReplayClock((1000.0,), call_index=7)
        self.assertEqual(extra(), 1000.0)
        with self.assertRaises(ReplayMismatch) as failure:
            extra()
        self.assertEqual(failure.exception.report["reason"], "CLOCK_TAPE_EXHAUSTED")
        self.assertEqual(failure.exception.report["call_index"], 7)

        missing = ReplayClock((1000.0, 1000.001), call_index=8)
        self.assertEqual(missing(), 1000.0)
        with self.assertRaises(ReplayMismatch) as failure:
            missing.verify_consumed()
        self.assertEqual(failure.exception.report["reason"], "UNCONSUMED_CLOCK_READS")
        self.assertEqual(failure.exception.report["call_index"], 8)

        # A fully consumed clock is accepted; rejection is tied to mismatch.
        exact = ReplayClock((1000.0,), call_index=9)
        self.assertEqual(exact(), 1000.0)
        exact.verify_consumed()

    def test_missing_engine_close_rejects_completed_writer_tape(self):
        path, writer = self.writer("missing_engine_close")
        writer.submit(self.envelope("init", clocks=(1000.0,)))
        writer.close(timeout_s=3.0)
        self.assert_rejected_before_iteration(path)


if __name__ == "__main__":
    unittest.main()
