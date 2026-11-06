from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.tool_rack.test_pid14312_arc_selection_custody import PID14312ArcSelectionCustodyTests

CORPUS = Path(__file__).with_name("docs") / "PID14312_ARC_SELECTION_CUSTODY_CONTROLS.json"


def main() -> int:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    controls = data.get("controls") or []
    corpus_rows = [
        ("nine_trade_forensic_corpus", len(controls) == 9, f"count={len(controls)}"),
        ("positive_and_negative_entry_controls", {
            "GOOD_LEVEL_MATCH_ENTRY_EXIT_TOO_EARLY",
            "BAD_PREMATURE_COUNTER_BRIEFING",
            "VALID_ULTRACHEAP_EXTENDED_TOP_SEED_CUSTODY_TOO_SHORT",
            "EXCELLENT_CONFIRMED_RELEASE",
            "BAD_EXPENSIVE_FADE_OF_LIVING_DOWN_PARENT",
            "GOOD_EXTREME_RETURN_PROFIT_SURRENDERED",
            "BAD_FADE_INTO_NEW_UP_RELEASE",
            "EXCELLENT_CHEAP_TOP_SEED_CUSTODY_TOO_SHORT",
            "GOOD_LATE_RELEASE_PEAK_NOT_PROTECTED",
        } == {str(row.get("classification")) for row in controls}, "all classifications frozen"),
        ("run_economics_frozen", abs(float(data.get("realized_net_usd")) - 24.578) < 1e-9
             and int(data.get("closed_trades")) == 9, "PID14312 ledger summary"),
    ]

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PID14312ArcSelectionCustodyTests)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    test_total = result.testsRun
    test_passed = test_total - len(result.failures) - len(result.errors)
    rows = corpus_rows + [
        ("pid14312_live_path_controls", result.wasSuccessful() and test_total == 11,
         f"{test_passed}/{test_total} tests"),
    ]
    passed = sum(ok for _, ok, _ in rows)
    print(f"PID14312 ARC SELECTION / CUSTODY CONSTRUCT: {passed}/{len(rows)} PASS · live controls {test_passed}/{test_total}")
    for name, ok, detail in rows:
        print(("PASS" if ok else "FAIL"), name, detail)
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
