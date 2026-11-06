"""Finite lossless-storage checks; these tests never execute a trading engine."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
from types import MappingProxyType
import unittest
from unittest.mock import patch

from bounded_tape import TapeError, TapeWriter, iter_tape
from input_codec import CodecError, canonical_bytes, decode, encode, pin
from snapshot_delta import (MAX_SNAPSHOT_ROWS, SnapshotDeltaDecoder,
                            SnapshotDeltaEncoder, SnapshotDeltaError)
from strategy_core.paper_feed import FeedSnapshot, freeze_data


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def envelope(method, arguments=None, *, beat=0):
    return pin({"call": {"method": method, "arguments": arguments or {}},
                "clocks": (1000.0 + beat, 1000.00001 + beat),
                "expected": {"decision_seq": beat, "decision_sha256": "a" * 64,
                             "journal_seq": 1, "journal_sha256": "b" * 64}})


def process(rows, candles, *, beat=0, epoch=1, gaps=0):
    return envelope("process", {
        "feed": FeedSnapshot(beat, 1000.0 + beat, None, None, tuple(rows),
                             freeze_data({"connection_epoch": epoch, "source_gap_count": gaps})),
        "historical_candles": candles, "stop_requested": False,
        "entry_window_closed": bool(beat % 2),
    }, beat=beat)


def component(wire, name):
    def member(node, key, field="items"):
        return next(pair[1] for pair in node[field] if pair[0] == key)
    arguments = member(member(wire["envelope"], "call"), "arguments")
    if name == "historical_candles":
        return member(arguments, name)
    return member(member(arguments, "feed"), name, "fields")


class SnapshotDeltaTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tachyos_delta_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_full_typed_equality_for_window_changes_and_source_resets(self):
        a = freeze_data({"source_row_id": "A", "timestamp": 1000, "price": 1.0})
        b = freeze_data({"source_row_id": "B", "timestamp": 1001, "price": 2.0})
        c = freeze_data({"source_row_id": "C", "timestamp": 1002, "price": 3.0})
        changed = freeze_data({"source_row_id": "B", "timestamp": 1001, "price": -0.0})
        reordered_keys = freeze_data({"price": -0.0, "timestamp": 1001, "source_row_id": "B"})
        candles = [{"time": 960, "close": Decimal("12.30"), "complete": False,
                    "detail": {"samples": [1, 2]}}]
        revised = deepcopy(candles)
        revised[0]["close"] = Decimal("12.31")
        revised[0]["complete"] = True
        revised[0]["detail"]["samples"].append(3)
        values = [
            envelope("init"),
            process((a, b), candles, beat=1),
            process((a, b), deepcopy(candles), beat=2),  # Every repeated WAIT stays a call.
            process((a, b, c), candles, beat=3),
            process((b, c), candles, beat=4),
            process((c, b, c), revised, beat=5),
            process((c, changed), revised, beat=6),  # Same timestamp/id, different value.
            process((reordered_keys, c), tuple(revised), beat=7),
            process((freeze_data(dict(reordered_keys)), c), tuple(revised), beat=8),
            process((), (), beat=9, epoch=2, gaps=1),
            process((a,), revised, beat=10, epoch=2, gaps=1),
            envelope("settle", {"receipt": None}, beat=11),
            process((a,), revised, beat=12, epoch=2, gaps=1),
            envelope("close", {"reason": "TEST_COMPLETE"}, beat=13),
        ]
        encoder, decoder = SnapshotDeltaEncoder(), SnapshotDeltaDecoder()
        for sequence, value in enumerate(values, 1):
            with self.subTest(sequence=sequence):
                wire = encoder.encode(value, sequence)
                restored_tree = decoder.expand(deepcopy(wire), sequence)
                self.assertEqual(canonical(restored_tree), canonical_bytes(value))
                self.assertEqual(canonical_bytes(decode(restored_tree)), canonical_bytes(value))
                if sequence == 13:  # Intervening settle cleared both windows.
                    self.assertTrue(all(piece[0] == "literal"
                                        for piece in component(wire, "geometry_rows")["pieces"]))

    def test_validated_immutable_identity_reuse_and_exact_numeric_equality(self):
        a = freeze_data({"id": "unchanged", "price": 1})
        encoder = SnapshotDeltaEncoder()
        encoder.encode(process((a,), []), 1)
        encoder.encode(process((a,), [], beat=1), 2)
        stats = encoder.stats()
        self.assertEqual(stats["geometry_encodes"], 1)
        self.assertEqual(stats["immutable_geometry_reuses"], 1)
        for sequence, price in enumerate((True, 1.0, -0.0, 0.0), 3):
            wire = encoder.encode(process((freeze_data({"id": "unchanged", "price": price}),), []), sequence)
            self.assertEqual(component(wire, "geometry_rows")["pieces"][0][0], "literal")
        self.assertEqual(encoder.stats()["geometry_rows"]["rows"], 1)
        unsafe = MappingProxyType({"nested": []})
        with self.assertRaisesRegex(CodecError, "RETAINED_SOURCE_MUTABLE"):
            encoder.encode(process((unsafe,), []), 7)

    def test_malformed_references_and_expansion_bounds_are_rejected(self):
        row = freeze_data({"id": "A", "value": 1})
        encoder = SnapshotDeltaEncoder()
        first = encoder.encode(process((row,), []), 1)
        second = encoder.encode(process((row,), []), 2)
        mutations = {
            "negative": lambda node: node.update(pieces=[["copy", -1, 1]]),
            "outside": lambda node: node.update(pieces=[["copy", 1, 1]]),
            "zero_count": lambda node: node.update(pieces=[["copy", 0, 0]]),
            "boolean_index": lambda node: node.update(pieces=[["copy", False, 1]]),
            "oversized_count": lambda node: node.update(pieces=[["copy", 0, 2]]),
            "wrong_length": lambda node: node.update(length=2),
            "unknown_piece": lambda node: node.update(pieces=[["future", 0, 1]]),
            "unknown_field": lambda node: node.update(extra=True),
            "row_bound": lambda node: node.update(length=MAX_SNAPSHOT_ROWS + 1),
            "empty_literal": lambda node: node.update(pieces=[["literal", []]]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                decoder = SnapshotDeltaDecoder()
                decoder.expand(deepcopy(first), 1)
                broken = deepcopy(second)
                mutate(component(broken, "geometry_rows"))
                with self.assertRaises(SnapshotDeltaError):
                    decoder.expand(broken, 2)
        decoder = SnapshotDeltaDecoder()
        decoder.expand(deepcopy(first), 1)
        wrong_base = deepcopy(second)
        wrong_base["base_sequence"] = 0
        with self.assertRaisesRegex(SnapshotDeltaError, "BASE"):
            decoder.expand(wrong_base, 2)
        with patch("snapshot_delta.MAX_SNAPSHOT_ROWS", 1):
            with self.assertRaisesRegex(SnapshotDeltaError, "ROW_LIMIT"):
                SnapshotDeltaEncoder().encode(process((row, row), []), 1)
        with patch("snapshot_delta.MAX_SNAPSHOT_BYTES", 1):
            with self.assertRaisesRegex(SnapshotDeltaError, "BYTE_LIMIT"):
                SnapshotDeltaEncoder().encode(process((row,), []), 1)
            with self.assertRaisesRegex(SnapshotDeltaError, "BYTE_LIMIT"):
                SnapshotDeltaDecoder().expand(deepcopy(first), 1)

    def write_tape(self, name, *, snapshot_delta=True):
        path = self.root / (name + ".jsonl")
        writer = TapeWriter(path, header={"source_hashes": {"test.py": "a" * 64}},
                            snapshot_delta=snapshot_delta)
        self.assertTrue(writer.wait_ready(2), writer.health())
        a = freeze_data({"id": "A", "payload": "x" * 2000})
        values = [envelope("init"), process((a,), [{"time": 1, "close": 2}], beat=1),
                  process((a,), [{"time": 1, "close": 2}], beat=2),
                  envelope("close", {"reason": "TEST_COMPLETE"}, beat=3)]
        for value in values:
            self.assertTrue(writer.submit(value), writer.health())
        manifest = writer.close(3)
        self.assertTrue(manifest["complete"], manifest)
        return path, values, writer

    def test_v1_v2_reading_private_compact_spool_and_mutable_decode_isolation(self):
        for version in (1, 2):
            with self.subTest(version=version):
                path, values, writer = self.write_tape("v" + str(version), snapshot_delta=version == 2)
                _, calls = iter_tape(path)
                self.addCleanup(calls.close)
                call_bytes = sum(len(line) for line in path.read_bytes().splitlines(keepends=True)
                                 if json.loads(line)["kind"] == "CALL")
                self.assertEqual(calls._spool.seek(0, 2), call_bytes)
                calls._spool.seek(0)
                path.write_bytes(b"changed after complete verification\n")
                actual = []
                for index, value in enumerate(calls):
                    actual.append(canonical_bytes(value))
                    if index == 1:
                        value["call"]["arguments"]["historical_candles"][0]["close"] = 999
                self.assertEqual(actual, [canonical_bytes(value) for value in values])
                health = writer.health()
                self.assertEqual(health["status"], "complete")
                self.assertEqual(health["backlog"], 0)
                self.assertEqual(health["attempted"], 4)
                self.assertEqual(health["written"], 4)
                self.assertIsNone(health["failure"])

    def test_invalid_reference_rejected_before_iterator_despite_valid_hash_chain(self):
        path, _, _ = self.write_tape("invalid_ref")
        records = [json.loads(line) for line in path.read_bytes().splitlines()]
        component(records[3]["payload"], "geometry_rows")["pieces"] = [["copy", 999, 1]]
        previous = "0" * 64
        raw = []
        for record in records:
            record.pop("sha256")
            record["previous_sha256"] = previous
            previous = hashlib.sha256(canonical(record)).hexdigest()
            record["sha256"] = previous
            raw.append(canonical(record) + b"\n")
        path.write_bytes(b"".join(raw))
        manifest_path = path.with_suffix(".manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update(bytes=path.stat().st_size, header_sha256=records[0]["sha256"],
                        last_sha256=previous)
        manifest_path.write_bytes(canonical(manifest) + b"\n")
        with self.assertRaisesRegex(TapeError, "SNAPSHOT_DELTA:DELTA_REFERENCE_OUT_OF_RANGE"):
            iter_tape(path)

    def test_health_reports_startup_and_live_failure_without_close(self):
        existing = self.root / "already_exists.jsonl"
        existing.write_bytes(b"untouched")
        writer = TapeWriter(existing, header={"source_hashes": {"test.py": "a" * 64}})
        self.assertFalse(writer.wait_ready(2))
        self.assertEqual(writer.health()["status"], "failed")
        self.assertIsNotNone(writer.health()["failure"])
        writer.close(2)
        self.assertEqual(existing.read_bytes(), b"untouched")

        path = self.root / "live_failure.jsonl"
        writer = TapeWriter(path, header={"source_hashes": {"test.py": "a" * 64}})
        self.assertTrue(writer.wait_ready(2))
        self.assertEqual(writer.health()["status"], "running")
        writer.fail("SYNTHETIC_LIVE_FAILURE")
        health = writer.health()
        self.assertFalse(health["closed"])
        self.assertEqual(health["failure"], "SYNTHETIC_LIVE_FAILURE")
        self.assertEqual(health["status"], "failed")
        self.assertFalse(writer.submit(envelope("init")))
        self.assertEqual(writer.health()["dropped"], 1)
        self.assertFalse(writer.close(2)["complete"])


if __name__ == "__main__":
    unittest.main()
