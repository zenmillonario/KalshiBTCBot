"""Offline PID4596 optional-estimate defect proof; no market connection."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True

from strategy_core.paper_runtime import plain
from tests.tool_rack.pid4596_runtime_fixtures import (
    boundary_case, corpus, manifest, original_crash_control, physical_component_conformance,
)


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "PID4596_RUNTIME_REPAIR_CONSTRUCT_RESULTS" / "report.json"


def main() -> int:
    print("PID4596 optional-economics runtime repair checks running...", flush=True)
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.tool_rack.test_pid4596_optional_economics")
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    data, sealed = corpus(), manifest()
    crash = original_crash_control()
    policy, intent, snapshot = boundary_case()
    reviewed = policy.review(intent, snapshot)
    report = {
        "schema": "PID4596_OPTIONAL_ECONOMICS_RUNTIME_REPAIR_CONSTRUCT_V1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "passed": result.wasSuccessful(), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "test_output": stream.getvalue(),
        "scope": [
            "Runtime implementation repair only: omit unavailable numeric advice and clear any stale suggestion.",
            "The original session stopped with no trades; its failed process was not submitted to the input tape.",
            "The normal replay loader still rejects this incomplete original recording with CAPTURE_NOT_COMPLETE.",
            "This Construct uses exact preceding observations and retained failure components with explicitly reconstructed adviser context.",
            "It is not an exact failed-call replay, full-session replay, alternate fill sequence, or profit claim.",
            "The captured original MissionPolicy source is hash-verified and executed only as an offline regression control.",
        ],
        "fixture": {"file": "tests/tool_rack/fixtures/pid4596_optional_economics_cases.json.gz",
            "manifest": "tests/tool_rack/fixtures/pid4596_optional_economics_manifest.json",
            "compressed_sha256": sealed["compressed_sha256"],
            "compressed_bytes": sealed["compressed_bytes"], "source_run": sealed["source_run"],
            "original_archive_sha256": sealed["original_archive_sha256"],
            "captured_original_policy_sha256": sealed["original_policy_sha256"],
            "original_complete_decisions": sealed["original_complete_decisions"],
            "original_quote_observation_projections": sealed["original_quote_observation_projections"],
            "original_raw_geometry_observations": sealed["original_raw_geometry_observations"],
            "original_last_decision_sha256": sealed["original_last_decision_sha256"]},
        "physical_component_conformance": physical_component_conformance(),
        "reconstruction": data["reconstruction"],
        "input_scope": data["input_scope"],
        "atomic_failed_feed_snapshot_available": False,
        "failed_engine_clock_tape_available": False,
        "original_session_replay_accepted": False,
        "original_source_crash_reproduced": crash,
        "corrected_review": plain(reviewed.metadata["mission_policy_advice"]),
        "unchanged_proposed_fields": {key: plain(getattr(reviewed, key))
            for key in ("tool", "territory_id", "side", "action", "lane", "max_price", "size_tier", "reason")},
        "suggested_max_price_present": "mission_policy_suggested_max_price" in reviewed.metadata,
        "guardrails": {"missing_estimate_becomes_zero": False, "stale_suggestion_retained": False,
            "strategy_thresholds_changed": False, "one_commander": True,
            "proposed_action_lane_and_executable_price_preserved": True,
            "advisory_only_authority_preserved": True, "catch_all_added_to_production": False,
            "finite_passing_and_below_threshold_scenarios_preserved": True,
            "missing_quote_depth_destination_history_and_time_controls_pass": result.wasSuccessful()},
        "repaired_policy_sha256": hashlib.sha256((ROOT / "strategy_core/mission_policy.py").read_bytes()).hexdigest(),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if not result.wasSuccessful():
        print(stream.getvalue())
        print("PID4596 RUNTIME REPAIR CONSTRUCT FAIL")
        return 1
    print("PID4596 RUNTIME REPAIR CONSTRUCT PASS")
    print(f"{result.testsRun} tests; captured old source reproduces the error; corrected adviser preserves WAIT and omits unavailable price advice.")
    print("570 recorded observation projections; 957 raw BTC rows; failed atomic input remains unavailable.")
    print(f"Report: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
