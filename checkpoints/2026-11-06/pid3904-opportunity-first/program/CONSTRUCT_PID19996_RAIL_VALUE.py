"""Offline exact-frame opening-value Construct; no market connection or orders."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True

from tests.tool_rack.pid19996_rail_fixtures import manifest, opening_trajectory_probe


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "PID19996_RAIL_VALUE_CONSTRUCT_RESULTS" / "report.json"


def main() -> int:
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.tool_rack.test_pid19996_rail_fishing")
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    corpus = manifest()
    probes = opening_trajectory_probe()
    third = probes["third_first_300s"]
    entries = [row for row in third["callbacks"] if row["action"] == "ENTER"]
    first_minute = [row for row in third["callbacks"] if row["contract_age_s"] <= 60.]
    original_premium = [row for row in third["callbacks"] if 8723 <= row["sequence"] <= 8731]
    first_closed = next(row for row in third["callbacks"] if not row["recorded_engine_entry_window_open"])
    report = {
        "schema": "PID19996_OPENING_RAIL_VALUE_CONSTRUCT_V1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "passed": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "test_output": stream.getvalue(),
        "scope": [
            "Offline exact original snapshots, offered in recorded order to one Commander per contract.",
            "Each opening frame passes the runtime recovery qualification, role qualification, dual-lane filter, and Commander entry admission chain with explicitly empty inventory.",
            "No recorded position is sold or rewritten; these are candidate/admission controls, not replayed fills or counterfactual P/L.",
            "Local capture time for the new source receipt is derived from the exact recorded source time plus recorded source age. No source, quote, or decision timestamp is shifted.",
            "Candidate probes after the recorded session entry deadline are research observations only. The first qualifying value rejoin precedes that deadline.",
        ],
        "fixture": {
            "file": "tests/tool_rack/fixtures/pid19996_rail_fishing_cases.jsonl.xz",
            "manifest": "tests/tool_rack/fixtures/pid19996_rail_fishing_manifest.json",
            "compressed_sha256": corpus["compressed_sha256"],
            "source_run": corpus["source_run"], "source_bytes": corpus["source_bytes"],
            "unmodified_complete_original_records": len(corpus["records"]),
            "each_original_line_and_canonical_decision_hash_verified": True,
            "groups": {name: len(values) for name, values in corpus["groups"].items()},
        },
        "preserved_original_first_entries": {
            name: [row for row in probes[name]["callbacks"] if row["action"] == "ENTER"]
            for name in ("winner_one_opening", "winner_two_opening")
        },
        "third_whole_first_minute": {
            "callbacks": len(first_minute),
            "all_wait": all(row["action"] == "WAIT" for row in first_minute),
            "nine_original_53_54c_current_down_callbacks": original_premium,
        },
        "first_value_rejoin": entries[0] if entries else None,
        "first_value_rejoin_time_est": (datetime.fromtimestamp(entries[0]["now_ts"], timezone.utc)
            .astimezone(timezone(timedelta(hours=-5)))
            .isoformat() if entries else None),
        "recorded_session_entry_deadline": {
            "first_closed_sequence": first_closed["sequence"], "now_ts": first_closed["now_ts"],
            "contract_age_s": first_closed["contract_age_s"],
            "first_value_rejoin_precedes_deadline": bool(entries and entries[0]["sequence"] < first_closed["sequence"]),
        },
        "watch_changes": third["watch_changes"],
        "complete_first_300s_probe": third["callbacks"],
        "policy": {
            "normal_value_ceiling": .35, "existing_exceptional_opening_ceiling": .55,
            "existing_opening_search_window_seconds": 300.,
            "no_fixed_sleep_or_forced_entry": True, "no_new_profit_floor_or_partial_exit": True,
            "one_commander": True, "wait_does_not_consume": True,
            "booked_fill_consumes_original_and_rejoin_mission": True,
            "consumed_mission_rechecked_at_authoritative_admission": True,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if not result.wasSuccessful():
        print(stream.getvalue())
        print("PID19996 RAIL VALUE CONSTRUCT FAIL")
        return 1
    print("PID19996 RAIL VALUE CONSTRUCT PASS")
    print(f"{result.testsRun} tests; 681 original hash-checked records; first rejoin seq 8860 at 35c after 83.441s.")
    print(f"Report: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
