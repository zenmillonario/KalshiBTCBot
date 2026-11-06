"""PID17224 source negatives and explicitly derived mechanics controls.

Raw decisions contain physical rows later than the captured decision clock;
the old Heists also lack repeated bilateral walls. They must remain WAIT.
Mechanics scenes below retain original intents and book depth but explicitly
align source time and supply a synthetic qualifying species/contract runway.
Those scenes test custody, floors and inventory, never historical admission
or a counterfactual session profit. The recorded corpus stays unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import tempfile
import unittest

from strategy_core.commander import OneCommander
from strategy_core.paper_execution import PaperExecutioner
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, Lane
from tests.tool_rack.pid17224_recorded_fixtures import (
    book as recorded_book, entry_intent, intents, journal_state, snapshot as recorded_snapshot,
)


def snapshot(sequence):
    """Derived mechanics premise; not the historical entry-time snapshot.

    Clock alignment waits until the recorded geometry could be known. Heist
    mechanics receive an authored repeated box; Release mechanics receive a
    target below current price/EMAs and 400 seconds of contract runway. Quotes,
    depth, strategy intent, mission and floor instructions remain the original.
    Raw source qualification is tested separately without these changes.
    """
    original = recorded_snapshot(sequence)
    md = deepcopy(original.metadata)
    source_ms = md["current_geometry"]["epoch_ms"]
    now = max(original.now_ts, source_ms / 1000 + .01)
    age = original.contract_age_s
    if sequence in (4561, 4562, 4601):
        age = 500.
        g = md["current_geometry"]
        target = min(g["btc_price"], g["ema9"], g["ema30"]) - 10.
        md["tp_geometry"].update(target=target, required_move_to_target_btc=0.,
            observed_target_side="YES", target_between_ema9_ema30=False,
            remaining_seconds=900-age)
    else:
        h = md["heist"]
        proof = h["repeatability_proof"]
        proof.update(lower_visits=2, upper_visits=2, center_traversals=2,
            window_start_ms=source_ms-300000., window_end_ms=source_ms,
            repeatability_visits=[{"zone": zone, "epoch_ms": source_ms-300000.+index*40000.}
                for index, zone in enumerate(("LOWER", "CENTER", "UPPER", "CENTER", "LOWER", "UPPER"))])
    md["test_scene_provenance"] = "EXPLICIT_DERIVED_PID17224_MECHANICS_NOT_RECORDED"
    return replace(original, now_ts=now, contract_age_s=age, metadata=md)


def book(sequence):
    """Original book depth with the derived mechanics scene's contract clock."""
    current = snapshot(sequence)
    return replace(recorded_book(sequence), close_ts=current.now_ts+900-current.contract_age_s)


class PID17224RawSourceProofTests(unittest.TestCase):
    def test_original_future_source_and_partial_boxes_do_not_admit(self):
        for sequence in (4561, 4601, 5377, 5600):
            with self.subTest(sequence=sequence):
                current = recorded_snapshot(sequence)
                intent = entry_intent(sequence) if sequence in (4561, 4601) else heist_intent(sequence)
                self.assertGreater(current.metadata["current_geometry"]["epoch_ms"], current.now_ts*1000)
                decision = OneCommander().decide_entry((intent,), current, {})
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, "OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED")

    def test_clock_alignment_alone_does_not_invent_repeated_walls(self):
        for sequence in (5377, 5600):
            with self.subTest(sequence=sequence):
                original = recorded_snapshot(sequence)
                current = replace(original, now_ts=original.metadata["current_geometry"]["epoch_ms"]/1000+.01)
                decision = OneCommander().decide_entry((heist_intent(sequence),), current, {})
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, "OPPORTUNITY_HEIST_REPEATED_BILATERAL_WALLS_REQUIRED")


def heist_intent(sequence=5600):
    return next(intent for intent in intents(sequence) if intent.tool == "MARKET_HEIST")


class PID17224ReleaseCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.executor = PaperExecutioner(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.executor.close)
        self.commander = OneCommander()

    def enter_derived(self, sequence, intent=None):
        current = snapshot(sequence)
        decision = self.commander.decide_entry(
            (intent or entry_intent(sequence),), current, self.executor.positions)
        receipt = self.executor.execute(decision, book(sequence),
            now_ts=current.now_ts, command_id=f"PID17224:{sequence}:ENTRY")
        self.assertEqual(receipt.status, "BOOKED", receipt.reason)
        return decision, self.executor.snapshot()["positions"][receipt.position_id]

    def test_4561_release_resolves_role_and_mission_before_committed_fill(self):
        original = entry_intent(4561)
        preserved = deepcopy(original)
        self.assertEqual(original.metadata["position_role"], "TACTICAL")
        self.assertEqual(original.metadata["mission"]["purpose"], "TACTICAL_RETURN")
        self.assertGreater(recorded_snapshot(4561).contract_age_s, 840.0)
        self.assertEqual(snapshot(4561).contract_age_s, 500.0)

        decision, position = self.enter_derived(4561, intent=original)
        accepted = decision.intent
        self.assertEqual(accepted.metadata["position_role"], "PRIMARY")
        self.assertEqual(accepted.metadata["custody"], "LEVIATHAN_RELEASE")
        self.assertEqual(accepted.metadata["mission"]["purpose"], "MAIN_CONTRACT")
        self.assertEqual(accepted.metadata["mission"]["target_kind"], "PARENT_TERMINAL")
        self.assertEqual(accepted.metadata["mission"]["collection_policy"], "THIRD_DISTINCT_WEAKNESS_V1")
        self.assertEqual(accepted.metadata["mission"]["contract_thesis_at_entry"], "MIXED")
        self.assertEqual(position["position_role"], "PRIMARY")
        self.assertEqual(position["entry_metadata"]["mission"], accepted.metadata["mission"])
        self.assertEqual(position["qty"], 57)
        self.assertEqual(float(position["entry_price"]), .30)
        audit = accepted.metadata["commander_release_custody_admission"]
        self.assertEqual(audit["advisory_position_role"], "TACTICAL")
        self.assertEqual(audit["advisory_mission"], original.metadata["mission"])
        for key in ("floor_policy", "entry_geometry", "physical_mission_id", "mission_policy_advice"):
            self.assertEqual(accepted.metadata[key], original.metadata[key], key)
        for key in ("parent_leg_id", "swing_id", "source_ms", "continuity_generation"):
            self.assertEqual(accepted.metadata["mission"][key], original.metadata["mission"][key], key)
        self.assertEqual(original, preserved)

    def test_4562_next_callback_holds_the_corrected_release(self):
        _, position = self.enter_derived(4561)
        following = snapshot(4562)
        # The historical lot really was liquidated by the generic renter timer.
        historical_position = next(iter(journal_state(2)["positions"].values()))
        historical = OneCommander().decide_position((), recorded_snapshot(4562), historical_position)
        self.assertIs(historical.action, Action.EXIT)
        self.assertEqual(historical.intent.reason, "TACTICAL_EXIT_BEFORE_SETTLEMENT_WINDOW")

        decision = self.commander.decide_position((), following, position)
        self.assertIs(decision.action, Action.HOLD)
        receipt = self.executor.execute(decision, book(4562), now_ts=following.now_ts,
            command_id="PID17224:4562:CUSTODY", position_id=position["position_id"])
        self.assertEqual(receipt.status, "NO_ACTION")
        self.assertEqual(self.executor.positions[position["position_id"]].qty, 57)
        self.assertEqual(len(self.executor.events), 1)

    def test_4601_derived_release_mechanics_when_inventory_is_clear(self):
        original = entry_intent(4601)
        decision, position = self.enter_derived(4601)
        self.assertEqual(replace(decision.intent, metadata=original.metadata), original)
        self.assertEqual(decision.intent.metadata["commander_opportunity"]["species"], "RELEASE_HANDOFF")
        self.assertEqual(position["position_role"], "PRIMARY")
        self.assertEqual(position["qty"], 26)
        self.assertEqual(position["entry_metadata"]["floor_policy"], original.metadata["floor_policy"])

    def test_corrected_4561_custody_prevents_duplicate_4601_entry(self):
        self.enter_derived(4561)
        decision = self.commander.decide_entry((entry_intent(4601),), snapshot(4601),
            self.executor.positions)
        self.assertIs(decision.action, Action.WAIT)
        self.assertIn("INVENTORY", decision.reason)
        self.assertEqual(len(self.executor.events), 1)
        decision = self.commander.decide_entry((entry_intent(4601),), snapshot(4601),
            self.executor.snapshot()["positions"])
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, "CURRENT_CONTRACT_SAME_SIDE_INVENTORY_NO_DUPLICATE")

    def test_objective_floor_and_manual_stop_authority_remain_prior_to_release_custody(self):
        _, position = self.enter_derived(4561)
        current = snapshot(4562)
        for flag, reason in (("floor_breached", "ALREADY_ARMED_EXECUTABLE_BID_FLOOR"),
                             ("stop_requested", "OPERATOR_PAPER_STOP")):
            with self.subTest(flag=flag):
                decision = self.commander.decide_position((), current, position, **{flag: True})
                self.assertIs(decision.action, Action.EXIT)
                self.assertEqual(decision.intent.reason, reason)
        receipt = self.executor.execute(decision, book(4562), now_ts=current.now_ts,
            command_id="PID17224:4562:STOP", position_id=position["position_id"])
        self.assertEqual(receipt.status, "EXITED")
        self.assertEqual(receipt.event["qty"], 57)
        self.assertFalse(self.executor.positions)

    def test_confirmed_release_resolution_is_idempotent_in_candidate_selection(self):
        current = snapshot(4561)
        original = entry_intent(4561)
        selected, denial = self.commander._select_entry_intent([original], current)
        self.assertIsNone(denial)
        decision = self.commander.decide((selected,), current)
        self.assertEqual(replace(decision.intent, metadata=selected.metadata), selected)
        self.assertEqual(decision.intent.metadata["mission"], selected.metadata["mission"])
        self.assertEqual(decision.intent.metadata["commander_opportunity"]["species"], "RELEASE_HANDOFF")
        self.assertEqual(decision.intent.metadata["commander_release_custody_admission"]
            ["advisory_position_role"], "TACTICAL")

    def test_unconfirmed_release_cannot_obtain_primary_admission(self):
        current = snapshot(4561)
        metadata = deepcopy(current.metadata)
        metadata["commander_strategy"]["handoff_confirmed"] = False
        current = replace(current, contract_age_s=500.0, metadata=metadata)
        decision = self.commander.decide((entry_intent(4561),), current)
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, "OPPORTUNITY_NO_POSITIVE_SPECIES")

    def test_only_tactical_entry_waits_when_its_existing_final_minute_exit_applies(self):
        intent = heist_intent()
        current = snapshot(5600)
        before = self.commander.decide((intent,), replace(current, contract_age_s=839.999))
        self.assertIs(before.action, Action.ENTER)
        for age in (840.0, 845.409, 899.0):
            with self.subTest(age=age):
                decision = self.commander.decide((intent,), replace(current, contract_age_s=age))
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, "COMMANDER_TACTICAL_ENTRY_MANDATORY_EXIT_WINDOW")

    def test_primary_label_alone_cannot_hide_an_existing_tactical_exit_family(self):
        intent = heist_intent()
        intent = replace(intent, metadata={**intent.metadata, "position_role": "PRIMARY"})
        decision = self.commander.decide((intent,), replace(snapshot(5600), contract_age_s=840.0))
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, "COMMANDER_TACTICAL_ENTRY_MANDATORY_EXIT_WINDOW")

    def test_existing_same_side_seed_promotion_precedes_the_tactical_clock(self):
        # Controlled variants of entry-time inputs preserve the pre-existing
        # same-side seed-promotion path; these are not historical run claims.
        original = heist_intent()
        intent = replace(original, metadata={**original.metadata,
            "mission": {**original.metadata["mission"], "counter_parent_fade": False}})
        for mode in ("RELEASE", "CONTINUATION"):
            with self.subTest(mode=mode):
                current = snapshot(5600)
                metadata = deepcopy(current.metadata)
                metadata["mountain"]["owner_side"] = "YES"
                metadata["current_geometry"].update(arc_direction="UP", parent_direction="UP")
                metadata["ema9_ema30_cross_context"]["gap_lifecycle"].update(
                    current_side="YES", stage="DEVELOPING")
                metadata["release_in_progress"] = mode == "RELEASE"
                metadata["release_candidate_side"] = "YES"
                current = replace(current, contract_age_s=840.0, metadata=metadata)
                decision = self.commander.decide((intent,), current)
                # An in-progress Release blocks a new Heist; the existing
                # seed can still be promoted by held-position custody below.
                self.assertIs(decision.action, Action.WAIT if mode == "RELEASE" else Action.ENTER)
                if mode == "RELEASE":
                    self.assertEqual(decision.reason, "OPPORTUNITY_DIRECTIONAL_RELEASE_CANCELS_HEIST_RETURN")
                position = {"ticker": current.ticker, "side": "YES", "tool": "MARKET_HEIST",
                    "territory_id": intent.territory_id, "lane": "TACTICAL", "position_id": "seed",
                    "opportunity_id": intent.opportunity_id, "entry_time": current.now_ts,
                    "close_ts": current.now_ts + 60.0, "entry_reason": intent.reason,
                    "position_role": "TACTICAL", "entry_metadata": intent.metadata}
                custody = self.commander.decide_position((), current, position)
                self.assertIs(custody.action, Action.HOLD)
                self.assertEqual(custody.intent.metadata["position_role"], "PRIMARY")
                self.assertEqual(custody.custody_update["state"], "PROMOTED_MAIN")


class PID17224LaterHeistTests(unittest.TestCase):
    def test_derived_repeated_box_5377_and_5600_preserve_execution_and_tactical_role(self):
        # Additional bilateral visits are authored in snapshot(); raw records
        # above remain WAIT. The recorded book depth tests quantity and role.
        for sequence, quantity in ((5377, 28), (5600, 43)):
            with self.subTest(sequence=sequence), tempfile.TemporaryDirectory() as temp:
                current = snapshot(sequence)
                intent = heist_intent(sequence)
                self.assertTrue(intent.metadata["mission"]["counter_parent_fade"])
                self.assertFalse(intent.metadata["mission"]["neutral_heist_repeatable"])
                decision = OneCommander().decide_entry((intent,), current, {})
                self.assertIs(decision.action, Action.ENTER)
                self.assertEqual(replace(decision.intent, metadata=intent.metadata), intent)
                self.assertEqual(decision.intent.metadata["commander_opportunity"]["species"], "REAL_HEIST_RETURN")
                with PaperExecutioner(temp) as executor:
                    receipt = executor.execute(decision, book(sequence), now_ts=current.now_ts,
                        command_id=f"PID17224:{sequence}:HEIST")
                    self.assertEqual(receipt.status, "BOOKED", receipt.reason)
                    position = executor.snapshot()["positions"][receipt.position_id]
                    self.assertEqual(position["qty"], quantity)
                    self.assertEqual(position["position_role"], "TACTICAL")
                    self.assertEqual(position["entry_metadata"]["mission"]["purpose"], "TACTICAL_RETURN")

    def test_first_and_repeat_callbacks_stay_observation_later_swing_can_qualify(self):
        rack = ToolRackController()
        # Starting a new observer here makes 5377 its first observed swing;
        # this is an explicit memory control, not the original session history.
        first = heist_intent(5377)
        first_metadata = dict(first.metadata)
        first_metadata.pop("dual_lane_counterfade_calibrated")
        first = replace(first, metadata=first_metadata)
        for _ in range(4):
            self.assertEqual(rack.filter_independent_lane_candidates((first,), snapshot(5377)), ())
        self.assertEqual(rack._dual_counterfade.last_observation["ticks"], 4)

        later = heist_intent(5600)
        later_metadata = dict(later.metadata)
        later_metadata.pop("dual_lane_counterfade_calibrated")
        later = replace(later, metadata=later_metadata)
        for _ in range(2):
            allowed = rack.filter_independent_lane_candidates((later,), snapshot(5600))
            self.assertEqual(len(allowed), 1)
            self.assertTrue(allowed[0].metadata["dual_lane_counterfade_calibrated"])
            self.assertIs(OneCommander().decide(allowed, snapshot(5600)).action, Action.ENTER)

    def test_current_visit_survives_rolling_box_window_id_change(self):
        current, intent = snapshot(5600), heist_intent()
        self.assertNotEqual(intent.metadata["box_id"], current.metadata["heist"]["box_id"])
        self.assertEqual(intent.metadata["visit_id"], current.metadata["heist"]["visit_id"])
        self.assertIs(OneCommander().decide((intent,), current).action, Action.ENTER)

    def test_calibration_marker_without_current_qualified_box_does_not_exempt_pause(self):
        current = snapshot(5600)
        metadata = deepcopy(current.metadata)
        metadata["heist"]["qualified_box"] = False
        decision = OneCommander().decide((heist_intent(),), replace(current, metadata=metadata))
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, "OPPORTUNITY_HEIST_REPEATED_BILATERAL_WALLS_REQUIRED")

    def test_missing_or_wrong_current_visit_cannot_reuse_calibration(self):
        intent = heist_intent()
        for visit in (None, "EARLIER_VISIT"):
            with self.subTest(visit=visit):
                changed = replace(intent, metadata={**intent.metadata, "visit_id": visit})
                decision = OneCommander().decide((changed,), snapshot(5600))
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, "COMMANDER_TACTICAL_FADES_PAUSED" if visit is None
                    else "OPPORTUNITY_CURRENT_PHYSICAL_HEIST_VISIT_REQUIRED")

    def test_main_lane_primary_role_or_missing_calibration_keeps_old_pause(self):
        intent = heist_intent()
        changes = {
            "MAIN lane": replace(intent, lane=Lane.MAIN),
            "PRIMARY role": replace(intent, metadata={**intent.metadata, "position_role": "PRIMARY"}),
            "uncalibrated": replace(intent, metadata={**intent.metadata,
                "dual_lane_counterfade_calibrated": False}),
        }
        for name, changed in changes.items():
            with self.subTest(case=name):
                decision = OneCommander().decide((changed,), snapshot(5600))
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, "COMMANDER_TACTICAL_FADES_PAUSED")

    def test_other_tools_and_unauthorized_heist_reasons_receive_no_exception(self):
        original = heist_intent()
        for intent, reason in (
            (replace(original, tool="RAIL", reason="RAIL_MAIN_VALUE"), "OPPORTUNITY_MAIN_CURRENT_EMA9_PARENT_REQUIRED"),
            (replace(original, reason="HEIST_UNAUTHORIZED_ENTRY"), "COMMANDER_UNAUTHORIZED_HEIST_ENTRY_REASON"),
        ):
            with self.subTest(tool=intent.tool, reason=intent.reason):
                decision = OneCommander().decide((intent,), snapshot(5600))
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, reason)

    def test_current_or_in_progress_release_removes_only_the_pause_exception(self):
        for key in ("release_in_progress", "release_confirmed_current"):
            with self.subTest(key=key):
                current = snapshot(5600)
                current = replace(current, metadata={**current.metadata, key: True})
                decision = OneCommander().decide((heist_intent(),), current)
                self.assertIs(decision.action, Action.WAIT)

    def test_strong_opposing_release_check_still_runs_after_pause_exception(self):
        current = snapshot(5600)
        metadata = deepcopy(current.metadata)
        metadata["mountain"]["strong_active_release"] = True
        decision = OneCommander().decide((heist_intent(),), replace(current, metadata=metadata))
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, "OPPORTUNITY_DIRECTIONAL_RELEASE_CANCELS_HEIST_RETURN")

    def test_objective_source_quote_depth_permission_and_price_checks_still_run(self):
        current = snapshot(5600)
        cases = (
            (replace(current, quote_current=False), "OBJECTIVE_QUOTE_STALE"),
            (replace(current, depth_available=False), "OBJECTIVE_DEPTH_UNAVAILABLE"),
            (replace(current, entry_allowed=False), "OBJECTIVE_ENTRY_NOT_ALLOWED"),
            (replace(current, metadata={**current.metadata, "physical_current": False}),
                "OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED"),
            (replace(current, yes_ask=.41), "OBJECTIVE_PRICE_MOVED_ABOVE_TOOL_LIMIT"),
        )
        for changed, reason in cases:
            with self.subTest(reason=reason):
                decision = OneCommander().decide((heist_intent(),), changed)
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, reason)

    def test_tp_economics_still_runs_after_the_old_pause_is_exempted(self):
        current = snapshot(5600)
        metadata = deepcopy(current.metadata)
        metadata["tp_geometry"].update(observed_target_side="NO",
            required_move_to_target_btc=10000.0,
            contract_ownership="STARTING_LEG_FAVORED", contract_ownership_side="NO")
        intent = heist_intent()
        intent = replace(intent, metadata={**intent.metadata, "qualified_fade": True})
        decision = OneCommander().decide((intent,), replace(current, metadata=metadata))
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, "COMMANDER_TP_REQUIRED_MOVE_EXCEEDS_DEMONSTRATED_RETURN")

    def test_both_inventory_directions_remain_blocked(self):
        current = snapshot(5600)
        for side, reason in (
            ("YES", "CURRENT_CONTRACT_SAME_SIDE_INVENTORY_NO_DUPLICATE"),
            ("NO", "CURRENT_CONTRACT_OPPOSITE_INVENTORY_EXIT_PENDING_CORRECTIVE_HANDOFF"),
        ):
            with self.subTest(side=side):
                held = {"existing": {"ticker": current.ticker, "side": side,
                    "custody_state": "NORMAL", "position_role": "PRIMARY"}}
                decision = OneCommander().decide_entry((heist_intent(),), current, held)
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, reason)

    def test_executor_still_rejects_a_stale_command_even_with_qualified_heist_metadata(self):
        current = snapshot(5600)
        stale = replace(heist_intent(), source_time=current.now_ts - 4.0)
        rejected = OneCommander().decide((stale,), current)
        self.assertIs(rejected.action, Action.WAIT)
        self.assertEqual(rejected.reason, "OPPORTUNITY_CURRENT_CANDIDATE_SOURCE_REQUIRED")
        fresh = OneCommander().decide((heist_intent(),), current)
        self.assertIs(fresh.action, Action.ENTER)
        # Executor independently rejects a command that became stale after
        # admission; this is a direct defensive API test, not a new admission.
        decision = replace(fresh, intent=stale)
        with tempfile.TemporaryDirectory() as temp, PaperExecutioner(temp) as executor:
            receipt = executor.execute(decision, book(5600), now_ts=current.now_ts,
                command_id="PID17224:5600:STALE_COMMAND")
            self.assertEqual(receipt.status, "REJECTED")
            self.assertEqual(receipt.reason, "COMMAND_PHYSICAL_SOURCE_STALE_OR_FUTURE")
            self.assertFalse(executor.positions)


if __name__ == "__main__":
    unittest.main()
