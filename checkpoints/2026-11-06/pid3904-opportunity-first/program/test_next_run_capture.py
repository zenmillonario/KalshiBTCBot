"""Small readiness-gate checks; no engine, feed, network, or timed load run."""
from __future__ import annotations

from copy import deepcopy
import unittest

from prepare_next_run import (
    CAPTURE_MAX_BYTES, DISPATCH_BUDGET_US, GEOMETRY_ROWS, HZ,
    LOAD_SECONDS, SHORT_TOTAL_SECONDS, LoadInputs, acceptance_failures,
    storage_projection,
)


def good_evidence():
    proof = {"pass": True, "original_vs_recorded": {"pass": True},
             "recorded_vs_replay": {"pass": True},
             "replay": {"pass": True, "validation_scope": "ALL_PERSISTENT_ENGINE_OUTPUT_FILES"},
             "altered_input_control": {"pass": True},
             "integrity_tests": {"pass": True, "run": 18},
             "capture_timing": {"measured_capture_work": {"max_us": 100.0}}}
    load = {
        "process_calls": LOAD_SECONDS * HZ,
        "manifest": {"complete": True, "dropped": 0}, "tape_integrity_verified": True,
        "backlog_before_close": 0, "queue_highwater": 3,
        "producer_capture": {"max_us": 100.0}, "steady_scheduling_lag": {"max_us": 100.0},
        "initial_observed_bytes_at_warmup_end": 8_000_000,
        "steady_write_bytes_per_second": 1000.0,
        "final_health": {"reason": None, "delta": {
            "enabled": True, "max_snapshot_rows": 10_000, "max_snapshot_bytes": 32_000_000}},
        "cache_observed": {
            "geometry_rows": {"max_rows": 3600, "max_canonical_bytes": 8_000_000},
            "historical_candles": {"max_rows": 361, "max_canonical_bytes": 250_000},
        },
    }
    return proof, load


class NextRunReadinessTests(unittest.TestCase):
    def test_complete_measured_short_candidate_is_accepted(self):
        proof, load = good_evidence()
        projection = storage_projection(load, 1024, SHORT_TOTAL_SECONDS)
        self.assertEqual(acceptance_failures(proof, load, projection, 1 << 50), [])

    def test_material_capture_failures_block_readiness(self):
        cases = (
            ("dropped", "RECORDER_DROPS_OR_FAILURE"),
            ("incomplete", "RECORDER_EVIDENCE_INCOMPLETE"),
            ("backlog", "RECORDER_BACKLOG_AT_END_OF_PACED_LOAD"),
            ("latency", "LOAD_CAPTURE_EXCEEDS_250MS_OBSERVED_BUDGET"),
            ("missing_cache", "BOUNDED_DELTA_ACCOUNTING_REQUIRED"),
            ("oversized_capture", "62MIN_INPUT_PROJECTION_EXCEEDS_CAPTURE_CAP_WITH_HEADROOM"),
            ("insufficient_disk", "INSUFFICIENT_PROJECTED_FREE_DISK_FOR_INPUT_ENGINE_REPLAY_AND_ZIP"),
        )
        for damage, reason in cases:
            with self.subTest(damage=damage):
                proof, load = deepcopy(good_evidence())
                free_bytes = 1 << 50
                if damage == "dropped":
                    load["manifest"]["dropped"] = 1
                elif damage == "incomplete":
                    load["manifest"]["complete"] = False
                elif damage == "backlog":
                    load["backlog_before_close"] = 1
                elif damage == "latency":
                    load["producer_capture"]["max_us"] = DISPATCH_BUDGET_US
                elif damage == "missing_cache":
                    load["cache_observed"] = {}
                elif damage == "oversized_capture":
                    load["steady_write_bytes_per_second"] = CAPTURE_MAX_BYTES / SHORT_TOTAL_SECONDS
                elif damage == "insufficient_disk":
                    free_bytes = 0
                projection = storage_projection(load, 1024, SHORT_TOTAL_SECONDS)
                self.assertIn(reason, acceptance_failures(proof, load, projection, free_bytes))

    def test_storage_counts_initial_snapshot_once_and_engine_logs_separately(self):
        _, load = good_evidence()
        projection = storage_projection(load, 2048, SHORT_TOTAL_SECONDS)
        self.assertEqual(projection["input_tape_bytes_estimate"],
                         8_000_000 + int(1000 * SHORT_TOTAL_SECONDS))
        self.assertEqual(projection["engine_output_bytes_estimate_per_copy"],
                         2048 * HZ * SHORT_TOTAL_SECONDS)
        self.assertGreater(projection["required_free_bytes_estimate"],
                           projection["original_and_replay_output_bytes"]
                           + projection["input_tape_bytes_with_headroom"])

    def test_load_keeps_full_immutable_window_and_exercises_revisions(self):
        inputs = LoadInputs()
        first, _ = inputs.frame(0)
        second, _ = inputs.frame(1)
        advanced, _ = inputs.frame(HZ)
        self.assertEqual(len(first["feed"].geometry_rows), GEOMETRY_ROWS)
        self.assertEqual(len(advanced["feed"].geometry_rows), GEOMETRY_ROWS)
        self.assertIs(first["feed"].geometry_rows[0], second["feed"].geometry_rows[0])
        self.assertIs(first["feed"].geometry_rows[1], advanced["feed"].geometry_rows[0])
        with self.assertRaises(TypeError):
            first["feed"].geometry_rows[0]["btc_price"] = 1.0
        inputs.frame(15 * HZ)
        inputs.frame(30 * HZ)
        inputs.frame(45 * HZ)
        self.assertEqual(inputs.candle_revisions, 2)
        self.assertEqual(inputs.candle_appends, 1)
        self.assertEqual(inputs.candle_evictions, 1)
        self.assertEqual(inputs.geometry_appends, inputs.geometry_evictions)
        self.assertEqual(len(inputs.candles), 361)


if __name__ == "__main__":
    unittest.main()
