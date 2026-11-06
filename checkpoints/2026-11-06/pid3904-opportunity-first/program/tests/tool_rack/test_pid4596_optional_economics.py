"""PID4596 optional-estimate crash, exact retained controls, missing-data paths."""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import fields, replace
import math
import unittest
from unittest.mock import patch

from strategy_core.mission_policy import _heist_return_destination
from strategy_core.paper_execution import PriceLevel
from strategy_core.paper_runtime import plain
from strategy_core.source_freshness import RECEIPT_KEY
from strategy_core.types import Action
from tests.tool_rack.pid4596_runtime_fixtures import (
    boundary_case, corpus, manifest, observed_policy, original_crash_control,
    physical_component_conformance, retained_last_intent, retained_last_snapshot,
    synthetic_response_case,
)


UNAVAILABLE = "TACTICAL_RETURN_SCENARIO_UNAVAILABLE"
RESPONSE_UNAVAILABLE = "TACTICAL_RESPONSE_OR_REMAINING_TIME_INSUFFICIENT"
SUGGESTION = "mission_policy_suggested_max_price"


class PID4596OptionalEconomicsTests(unittest.TestCase):
    def assert_proposal_preserved(self, proposed, reviewed):
        for field in fields(proposed):
            if field.name != "metadata":
                self.assertEqual(getattr(reviewed, field.name), getattr(proposed, field.name), field.name)
        self.assertEqual(reviewed.metadata["mission_policy_advice"]["authority"], "ADVISORY_ONLY")

    def assert_unassessed_wait(self, policy, intent, snapshot, reason):
        reviewed = policy.review(intent, snapshot)
        self.assert_proposal_preserved(intent, reviewed)
        advice = reviewed.metadata["mission_policy_advice"]
        self.assertEqual((advice["decision"], advice["reason"]), ("WAIT", reason))
        self.assertEqual(advice["economics"]["status"], "UNASSESSED")
        self.assertIsNone(advice["economics"]["estimated_exit_bid"])
        self.assertNotIn(SUGGESTION, reviewed.metadata)
        self.assertIs(advice["economics"]["automatic_take_profit"], False)
        return reviewed

    def test_fixture_preserves_provenance_and_does_not_claim_missing_atomic_input(self):
        data, sealed = corpus(), manifest()
        self.assertEqual(data["run_id"], "TOOL_RACK_PAPER_20261105T011602Z_PID4596")
        self.assertEqual(len(data["quote_observations"]), 570)
        self.assertEqual(sealed["original_complete_decisions"], 1)
        self.assertEqual(sealed["original_raw_geometry_observations"], 957)
        self.assertFalse(data["atomic_failed_feed_snapshot_available"])
        self.assertFalse(data["failed_engine_clock_tape_available"])
        self.assertFalse(data["normal_replay_acceptance"])
        self.assertEqual(data["normal_loader_rejection"], "CAPTURE_NOT_COMPLETE")
        self.assertTrue(data["reconstruction"]["receipt_control"]["not_an_original_atomic_capture"])
        self.assertTrue(data["reconstruction"]["source_times_and_quote_prices_unchanged"])
        self.assertFalse(data["reconstruction"]["future_market_inputs_used"])

    def test_raw_source_reproduces_previous_metadata_and_final_retained_geometry(self):
        result = physical_component_conformance()
        self.assertEqual(result["raw_observations"], 957)
        self.assertEqual(result["preceding_metadata_mismatches"], [])
        self.assertTrue(result["final_geometry_matches_retained_record"])
        self.assertEqual((result["before_lean"], result["after_lean"]), ("MIXED", "NEUTRAL"))
        self.assertEqual(result["current_source_ms"], 1793842544391.147)

    def test_last_complete_original_review_and_quote_wave_are_unchanged(self):
        snapshot, intent = retained_last_snapshot(), retained_last_intent()
        for original in (True, False):
            with self.subTest(captured_original=original):
                policy = observed_policy(original=original)
                self.assertEqual(len(policy._quotes), 562)
                self.assertEqual(policy.quote_wave_briefing(snapshot), snapshot.metadata["quote_wave"])
                self.assertEqual(policy.review(intent, snapshot), intent)
                self.assertEqual(policy.reviews[-1]["reason"], "TACTICAL_CURRENT_EMA9_DIRECTION_MIXED")

    def test_recorded_component_economics_deliberately_has_no_exit_estimate(self):
        policy, intent, snapshot = boundary_case()
        destination, evidence, reason = _heist_return_destination(snapshot, "NO",
            snapshot.metadata["mission_context"], snapshot.metadata["heist"])
        self.assertIsNone(reason)
        self.assertEqual(evidence["basis"], "OBSERVED_NEUTRAL_BOX_OPPOSITE_WALL")
        economics = policy.tactical_economics(intent, snapshot, destination)
        self.assertEqual(economics, corpus()["boundary"]["original_advice_before_error"]["economics"])
        self.assertEqual(economics["response_pair_count"], 34)
        self.assertEqual(economics["bid_response_per_btc"], 0.)
        self.assertEqual(economics["quantity"], 62)
        self.assertEqual((economics["entry_ask"], economics["required_exit_bid"]), (.15, .21))
        self.assertEqual(economics["reason"], RESPONSE_UNAVAILABLE)
        self.assertIsNone(economics["estimated_exit_bid"])
        self.assertIsNone(economics["gross_roi"])
        self.assertIsNone(economics["net_after_fees"])

    def test_hash_verified_captured_source_reproduces_exact_error_and_line(self):
        crash = original_crash_control()
        self.assertEqual(crash["error_type"], "TypeError")
        self.assertEqual(crash["message"], "unsupported operand type(s) for /: 'NoneType' and 'float'")
        self.assertEqual(crash["source_file"], "captured_original/strategy_core/mission_policy.py")
        self.assertEqual(crash["source_line"], 743)
        self.assertEqual(crash["advice_before_error"], corpus()["boundary"]["original_advice_before_error"])

    def test_repair_returns_original_wait_advice_without_creating_price_or_authority(self):
        policy, intent, snapshot = boundary_case()
        before = deepcopy(intent)
        reviewed = self.assert_unassessed_wait(policy, intent, snapshot, RESPONSE_UNAVAILABLE)
        self.assertEqual(plain(reviewed), corpus()["boundary"]["corrected_intent"])
        self.assertEqual(intent, before)
        self.assertEqual(reviewed.metadata["mission_policy_advice"], corpus()["boundary"]["original_advice_before_error"])
        self.assertEqual((reviewed.action, reviewed.max_price), (Action.ENTER, .35))

    def test_unavailable_estimate_clears_prior_suggestion_on_rereview(self):
        for stale in (.99, 0., "previous numeric advice"):
            with self.subTest(stale=stale):
                policy, intent, snapshot = boundary_case()
                intent = replace(intent, metadata={**intent.metadata, SUGGESTION: stale})
                self.assert_unassessed_wait(policy, intent, snapshot, RESPONSE_UNAVAILABLE)
                self.assertEqual(intent.metadata[SUGGESTION], stale)

    def test_unavailable_quote_and_proposal_prerequisites_remain_explicit_waits(self):
        for case in ("no_quotes", "stale_quote", "entry_unavailable", "quote_identity_mismatch", "zero_budget", "missing_ask_book"):
            with self.subTest(case=case):
                policy, intent, snapshot = boundary_case()
                if case == "no_quotes":
                    policy._quotes.clear()
                elif case == "stale_quote":
                    snapshot = replace(snapshot, quote_current=False)
                elif case == "entry_unavailable":
                    snapshot = replace(snapshot, entry_allowed=False)
                elif case == "quote_identity_mismatch":
                    policy._quotes[-1]["quote_id"] = "SYNTHETIC_DIFFERENT_CURRENT_QUOTE"
                elif case == "zero_budget":
                    intent = replace(intent, size_tier=0.)
                else:
                    policy._quotes[-1]["YES"] = ()
                self.assert_unassessed_wait(policy, intent, snapshot, UNAVAILABLE)

    def test_affordability_and_full_lot_depth_shortfalls_do_not_become_prices(self):
        for case in ("price_above_limit", "less_than_one_affordable_contract", "current_bid_depth_short"):
            with self.subTest(case=case):
                policy, intent, snapshot = boundary_case()
                if case == "price_above_limit":
                    intent = replace(intent, max_price=.10)
                elif case == "less_than_one_affordable_contract":
                    intent = replace(intent, size_tier=.001)
                else:
                    policy._quotes[-1]["NO"] = (PriceLevel(.14, 1.),)
                reason = ("TACTICAL_CURRENT_FULL_LOT_BID_UNAVAILABLE" if case == "current_bid_depth_short"
                          else "TACTICAL_ENTRY_DEPTH_OR_AFFORDABLE_LOT_UNAVAILABLE")
                self.assert_unassessed_wait(policy, intent, snapshot, reason)

    def test_unverified_or_already_reached_destinations_remain_unassessed(self):
        for tolerance, reason in ((None, "TACTICAL_PHYSICAL_DESTINATION_NOT_VERIFIED"),
                                   (1000., "TACTICAL_PHYSICAL_COLLECTION_BAND_ALREADY_REACHED")):
            with self.subTest(synthetic_tolerance=tolerance):
                policy, intent, snapshot = boundary_case()
                metadata = deepcopy(snapshot.metadata)
                metadata["heist"]["edge_tolerance"] = tolerance
                self.assert_unassessed_wait(policy, intent, replace(snapshot, metadata=metadata), reason)

    def test_insufficient_history_adverse_response_and_time_are_not_synthetic_estimates(self):
        for case in ("one_observation", "adverse_response", "insufficient_time"):
            with self.subTest(case=case):
                if case == "adverse_response":
                    policy, intent, snapshot = synthetic_response_case((.17, .16, .15, .14))
                else:
                    policy, intent, snapshot = synthetic_response_case()
                    if case == "one_observation":
                        policy._quotes = deque((policy._quotes[-1],), maxlen=2048)
                    else:
                        metadata = deepcopy(snapshot.metadata)
                        metadata["contract_value_context"]["close_ts"] = snapshot.now_ts + 1.
                        snapshot = replace(snapshot, metadata=metadata)
                reason = ("TACTICAL_INSUFFICIENT_EXACT_CONTRACT_PRICE_RESPONSE"
                          if case == "one_observation" else RESPONSE_UNAVAILABLE)
                self.assert_unassessed_wait(policy, intent, snapshot, reason)

    def test_absent_nonfinite_boolean_or_malformed_optional_estimates_clear_stale_hint(self):
        # Deliberately synthetic calculator-return controls exercise the
        # optional field contract. No fictional market prices are recorded.
        missing = object()
        values = (missing, None, float("nan"), float("inf"), -float("inf"), True, False, "bad-number", "1e9999")
        for value in values:
            with self.subTest(estimate=repr(value)):
                policy, intent, snapshot = boundary_case()
                economics = deepcopy(corpus()["boundary"]["original_advice_before_error"]["economics"])
                if value is missing:
                    economics.pop("estimated_exit_bid")
                else:
                    economics["estimated_exit_bid"] = value
                proposed = replace(intent, metadata={**intent.metadata, SUGGESTION: .99})
                with patch.object(policy, "tactical_economics", return_value=economics):
                    reviewed = policy.review(proposed, snapshot)
                self.assert_proposal_preserved(proposed, reviewed)
                self.assertEqual(reviewed.metadata["mission_policy_advice"]["decision"], "WAIT")
                self.assertEqual(reviewed.metadata["mission_policy_advice"]["reason"], RESPONSE_UNAVAILABLE)
                self.assertNotIn(SUGGESTION, reviewed.metadata)

    def test_finite_passing_and_below_hurdle_scenarios_match_captured_behavior(self):
        for bids, expected_status, expected_decision in (
                ((.05, .08, .11, .14), "SCENARIO_PASSES", "ELIGIBLE"),
                ((.11, .12, .13, .14), "BELOW_THRESHOLD", "WAIT")):
            with self.subTest(synthetic_bids=bids):
                outputs = []
                for original in (True, False):
                    policy, intent, snapshot = synthetic_response_case(bids, original=original)
                    reviewed = policy.review(intent, snapshot)
                    outputs.append(reviewed)
                    self.assert_proposal_preserved(intent, reviewed)
                    economics = reviewed.metadata["tactical_economics"]
                    self.assertEqual(economics["status"], expected_status)
                    self.assertEqual(reviewed.metadata["mission_policy_advice"]["decision"], expected_decision)
                    self.assertTrue(math.isfinite(economics["estimated_exit_bid"]))
                    self.assertEqual(reviewed.metadata[SUGGESTION], economics["estimated_exit_bid"] / 1.4)
                    self.assertEqual(policy.config.minimum_gross_roi, .4)
                self.assertEqual(outputs[0], outputs[1])

    def test_finite_zero_remains_a_zero_advisory_value_without_becoming_executable_price(self):
        policy, intent, snapshot = boundary_case()
        economics = deepcopy(corpus()["boundary"]["original_advice_before_error"]["economics"])
        economics["estimated_exit_bid"] = 0.
        with patch.object(policy, "tactical_economics", return_value=economics):
            reviewed = policy.review(intent, snapshot)
        self.assert_proposal_preserved(intent, reviewed)
        self.assertEqual(reviewed.metadata[SUGGESTION], 0.)
        self.assertEqual(reviewed.max_price, .35)
        self.assertEqual(reviewed.metadata["mission_policy_advice"]["decision"], "WAIT")

    def test_a_later_calibrated_observation_can_be_reviewed_after_missing_estimate(self):
        policy, intent, snapshot = synthetic_response_case()
        valid_quotes = deepcopy(policy._quotes)
        policy._quotes.clear()
        first = self.assert_unassessed_wait(policy, intent, snapshot, UNAVAILABLE)
        policy._quotes = valid_quotes
        second = policy.review(first, snapshot)
        self.assert_proposal_preserved(first, second)
        self.assertEqual(second.metadata["mission_policy_advice"]["decision"], "ELIGIBLE")
        self.assertEqual(second.metadata["tactical_economics"]["status"], "SCENARIO_PASSES")
        self.assertGreater(second.metadata[SUGGESTION], 0.)

    def test_missing_current_source_receipt_still_prevents_current_physical_advice(self):
        policy, intent, snapshot = boundary_case()
        metadata = deepcopy(snapshot.metadata)
        metadata.pop(RECEIPT_KEY)
        reviewed = policy.review(replace(intent, metadata={**intent.metadata, SUGGESTION: .99}),
                                 replace(snapshot, metadata=metadata))
        self.assert_proposal_preserved(intent, reviewed)
        advice = reviewed.metadata["mission_policy_advice"]
        self.assertEqual((advice["decision"], advice["reason"]),
            ("WAIT", "MISSION_CURRENT_PHYSICAL_CONTEXT_REQUIRED"))
        self.assertIsNone(advice["economics"])
        self.assertNotIn(SUGGESTION, reviewed.metadata)

    def test_non_entry_instructions_are_returned_without_new_economics(self):
        policy, intent, snapshot = boundary_case()
        for action in (Action.WAIT, Action.HOLD, Action.EXIT):
            with self.subTest(action=action):
                proposed = replace(intent, action=action)
                self.assertIs(policy.review(proposed, snapshot), proposed)


if __name__ == "__main__":
    unittest.main()
