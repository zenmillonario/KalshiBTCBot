"""Current source-bound Commander diagnostics never replay an old opportunity."""
from types import SimpleNamespace
import unittest

from strategy_core.commander import CommanderDecision
from strategy_core.paper_execution import ExecutionReceipt
from strategy_core.paper_runtime import opportunity_audit
from strategy_core.types import Action, MarketSnapshot


class OpportunityDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = MarketSnapshot(1000.0, "KX-TEST", 500.0, .20, .82,
            metadata={"current_geometry": {"epoch_ms": 1_000_000.0},
                      "geometry_continuity_generation": 3})
        self.review = {"ticker": "KX-TEST", "source_ms": 1_000_000.0,
            "continuity_generation": 3, "watch_state": "PREPARE",
            "main_alignment": {"qualified_count": 1}}
        self.commander = SimpleNamespace(opportunity_review=self.review)
        self.wait = CommanderDecision(Action.WAIT, None, "CURRENT_CONTRACT_SAME_SIDE_INVENTORY_NO_DUPLICATE")

    def test_current_qualified_but_unbooked_opportunity_keeps_exact_final_reason(self):
        result = opportunity_audit(self.commander, self.snapshot, self.wait, evaluated=True)
        self.assertTrue(result["evaluated_current_frame"])
        self.assertEqual(result["main_alignment"]["qualified_count"], 1)
        self.assertEqual(result["final_reason"], self.wait.reason)
        self.assertEqual(result["final_action"], "WAIT")
        self.assertFalse(result["execution_authority"])
        self.assertNotIn("final_action", self.review)

    def test_same_source_but_skipped_evaluation_never_reuses_old_quote_review(self):
        result = opportunity_audit(self.commander, self.snapshot,
            CommanderDecision(Action.WAIT, None, "PAPER_ENTRY_WINDOW_CLOSED_DRAINING"))
        self.assertFalse(result["evaluated_current_frame"])
        self.assertEqual(result["watch_state"], "NOT_EVALUATED_THIS_FRAME")
        self.assertNotIn("main_alignment", result)

    def test_ticker_source_or_continuity_change_cannot_relabel_previous_review(self):
        for field, value in (("ticker", "OLD"), ("source_ms", 999_999.0),
                             ("continuity_generation", 2)):
            with self.subTest(field=field):
                self.commander.opportunity_review = {**self.review, field: value}
                result = opportunity_audit(self.commander, self.snapshot, self.wait, evaluated=True)
                self.assertFalse(result["evaluated_current_frame"])
                self.assertNotIn("main_alignment", result)

    def test_admission_is_distinct_from_actual_execution_receipt(self):
        decision = CommanderDecision(Action.ENTER, None, "COMMANDER_ACCEPTED")
        receipt = ExecutionReceipt("REJECTED", "FULL_LOT_DEPTH_UNAVAILABLE")
        result = opportunity_audit(self.commander, self.snapshot, decision, receipt, evaluated=True)
        self.assertEqual(result["final_action"], "ENTER")
        self.assertEqual(result["receipt_status"], "REJECTED")
        self.assertEqual(result["receipt_reason"], "FULL_LOT_DEPTH_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
