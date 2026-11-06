"""Causal opening-value controls from PID19996, with no outcome-based entry input."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import physical_entry_candidates
from strategy_core.source_freshness import RECEIPT_KEY
from strategy_core.types import Action, Lane, Side, ToolIntent
from tests.tool_rack.pid19996_rail_fixtures import (
    manifest, opening_trajectory_probe, original_entry_intent, original_intents,
    record, snapshot,
)


REJOIN = "COMMANDER_OPENING_RAIL_DIP_VALUE_REJOIN"


def armed_commander():
    commander = OneCommander()
    commander.physical_entry_candidates(snapshot(8723))
    if commander._opening_rail_value_watch.state is None:
        raise AssertionError("Exact earned 54c opening did not retain a value watch")
    return commander


def rejoin_candidates(commander, snap):
    return tuple(intent for intent in commander.physical_entry_candidates(snap) if intent.reason == REJOIN)


def rail_adviser(snap, side=Side.YES):
    return ToolIntent(tool="RAIL", territory_id="PID19996_CURRENT_RAIL", lane=Lane.MAIN,
        side=side, action=Action.ENTER, opportunity_id="CURRENT_RAIL_VALUE",
        max_price=.399, size_tier=25., reason="RAIL_MAIN_VALUE", source_time=snap.now_ts)


def mirror(snap):
    """Explicit synthetic NO mirror; original fixture bytes are never changed."""
    md = deepcopy(snap.metadata)
    for key in ("btc_price", "ema9", "ema30"):
        md["current_geometry"][key] = 200000. - md["current_geometry"][key]
    for key in ("btc_change6", "btc_change9", "btc_change30", "btc_change60",
                "ema9_change6", "ema9_change30", "ema9_change60", "ema_gap"):
        if md["current_geometry"].get(key) is not None:
            md["current_geometry"][key] *= -1.
    def flip(mapping, keys):
        for key in keys:
            if mapping.get(key) in {"YES", "NO", "UP", "DOWN"}:
                mapping[key] = {"YES": "NO", "NO": "YES", "UP": "DOWN", "DOWN": "UP"}[mapping[key]]
    flip(md["current_geometry"], ("arc_direction", "parent_direction", "current_native_direction"))
    flip(md["mission_context"]["parent"], ("side", "direction"))
    flip(md["ema9_ema30_cross_context"]["gap_lifecycle"], ("current_side", "cross_side"))
    flip(md["mountain"], ("owner_side",))
    flip(md["mountain"]["parent_structure"], ("parent_side", "parent_direction"))
    flip(md["commander_strategy"], ("owned_side",))
    flip(md["tp_geometry"], ("contract_ownership_side", "observed_target_side", "parent_side"))
    for key in ("target", "btc", "ema9", "ema30"):
        if md["tp_geometry"].get(key) is not None:
            md["tp_geometry"][key] = 200000. - md["tp_geometry"][key]
    md["tp_geometry"]["signed_gap_btc"] *= -1.
    return replace(snap, yes_ask=snap.no_ask, no_ask=snap.yes_ask,
                   yes_bid=snap.no_bid, no_bid=snap.yes_bid, metadata=md)


class PID19996RailFishingTests(unittest.TestCase):
    def test_complete_recorded_opening_windows_are_hash_verified(self):
        proof = manifest()
        self.assertEqual(len(proof["records"]), 681)
        self.assertEqual(len(proof["groups"]["third_first_300s"]), 609)
        self.assertEqual(len(proof["groups"]["third_whole_recorded_first_minute"]), 115)
        self.assertEqual(proof["source_bytes"], 2002182688)
        trajectories = opening_trajectory_probe()  # verifies every full original line and decision SHA
        self.assertEqual(sum(len(item["callbacks"]) for item in trajectories.values()), 674)

    def test_entire_third_first_minute_waits_without_substitute_entry(self):
        first_minute = [row for row in opening_trajectory_probe()["third_first_300s"]["callbacks"]
                        if row["contract_age_s"] <= 60.]
        self.assertEqual(len(first_minute), 115)
        self.assertTrue(all(row["action"] == "WAIT" for row in first_minute))

    def test_all_nine_original_premium_dip_callbacks_are_deferred(self):
        for sequence in range(8723, 8732):
            with self.subTest(sequence=sequence):
                snap = snapshot(sequence)
                self.assertIn(snap.yes_ask, (.53, .54))
                self.assertEqual(snap.metadata["current_geometry"]["current_native_direction"], "DOWN")
                self.assertFalse(any(intent.side is Side.YES for intent in physical_entry_candidates(snap)))
                original = original_entry_intent(8723)
                decision = OneCommander().decide_entry((original,), snap, {})
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, "COMMANDER_OPENING_RAIL_DIP_KEEP_FISHING")

    def test_first_causal_value_rejoin_is_8860_at_35c_before_session_deadline(self):
        rows = opening_trajectory_probe()["third_first_300s"]["callbacks"]
        entries = [row for row in rows if row["action"] == "ENTER"]
        first = entries[0]
        self.assertEqual(first["sequence"], 8860)
        self.assertEqual(first["candidate_reason"], REJOIN)
        self.assertEqual(first["yes_ask"], .35)
        self.assertEqual(first["max_price"], .35)
        self.assertAlmostEqual(first["contract_age_s"], 83.44110107421875)
        self.assertTrue(first["recorded_engine_entry_window_open"])
        self.assertTrue(all(row["action"] == "WAIT" for row in rows if row["sequence"] < 8860))
        self.assertTrue(all(value > 0 for value in first["motion"].values()))
        evidence = first["physical_evidence"]
        self.assertEqual(evidence["deferred_ask"], .54)
        self.assertEqual(evidence["parent_id"], "P000L000001")
        self.assertEqual(evidence["lowest_observed_ask"], .29)
        self.assertFalse(evidence["clock_alone_has_trade_authority"])

    def test_first_two_winners_keep_original_first_eligible_entries(self):
        for group, sequence, price, native in (
            ("winner_one_opening", 3126, .36, "NONE"),
            ("winner_two_opening", 6320, .47, "UP"),
        ):
            with self.subTest(group=group):
                probe = opening_trajectory_probe()[group]
                entries = [row for row in probe["callbacks"] if row["action"] == "ENTER"]
                self.assertEqual([row["sequence"] for row in entries], [sequence])
                self.assertEqual(entries[0]["yes_ask"], price)
                self.assertEqual(entries[0]["native_direction"], native)
                self.assertEqual(probe["watch_changes"], [])

    def test_watch_is_one_parent_opportunity_across_whole_first_300s(self):
        probe = opening_trajectory_probe()["third_first_300s"]
        self.assertEqual(probe["watch_changes"], [
            {"sequence": 8723, "deferred_source_ms": 1793832321487.436}])
        self.assertTrue(all(row["watch_retained"] for row in probe["callbacks"] if row["sequence"] >= 8723))
        self.assertEqual({row["parent_id"] for row in probe["callbacks"]}, {"P000L000001"})

    def test_existing_mountain_floor_and_25_dollar_allowance_are_preserved(self):
        commander = armed_commander()
        intent = rejoin_candidates(commander, snapshot(8860))[0]
        original = original_entry_intent(8723)
        self.assertEqual(intent.metadata["floor_policy"], original.metadata["floor_policy"])
        self.assertEqual(intent.size_tier, 25.)
        self.assertEqual(intent.metadata["position_role"], "PRIMARY")
        self.assertIs(intent.lane, Lane.MAIN)

    def test_cheaper_but_still_falling_and_one_window_bounce_are_not_rejoins(self):
        for sequence in (8839, 8850, 8853, 8880):
            with self.subTest(sequence=sequence):
                commander = armed_commander()
                snap = snapshot(sequence)
                self.assertLessEqual(snap.yes_ask, .35)
                self.assertEqual(rejoin_candidates(commander, snap), ())
                decision = commander.decide_entry((rail_adviser(snap),), snap, {})
                self.assertIs(decision.action, Action.WAIT)
                self.assertIn("OPENING_RAIL", decision.reason)
                self.assertIsNotNone(commander._opening_rail_value_watch.state)

    def test_adviser_and_relabelled_primary_cannot_bypass_early_dip_check(self):
        snap = snapshot(8723)
        original = original_entry_intent(8723)
        renamed = replace(original, lane=Lane.TACTICAL,
            metadata={**original.metadata, "position_role": "TACTICAL"})
        for intent in (original, renamed, rail_adviser(snap)):
            with self.subTest(tool=intent.tool, lane=intent.lane):
                self.assertEqual(OneCommander().decide_entry((intent,), snap, {}).reason,
                                 "COMMANDER_OPENING_RAIL_DIP_KEEP_FISHING")

    def test_value_cap_stays_35c_even_on_confirmed_current_rejoin(self):
        commander = armed_commander()
        snap = replace(snapshot(8860), yes_ask=.350001)
        self.assertFalse(rejoin_candidates(commander, snap))
        decision = commander.decide_entry((rail_adviser(snap),), snap, {})
        self.assertEqual(decision.reason, "COMMANDER_OPENING_RAIL_WAIT_FOR_VALUE_REJOIN")
        self.assertIsNotNone(commander._opening_rail_value_watch.state)

    def test_local_arc_and_display_label_do_not_retire_parent(self):
        for territory in ("UP_RAIL", "ROLLING_MOUNTAIN", "ALTERNATING_MOUNTAIN"):
            with self.subTest(territory=territory):
                snap = snapshot(8860)
                md = deepcopy(snap.metadata)
                md["commander_strategy"]["owned_territory"] = territory
                self.assertEqual(md["current_geometry"]["arc_direction"], "DOWN")
                self.assertTrue(rejoin_candidates(armed_commander(), replace(snap, metadata=md)))

    def test_advisory_terminal_watch_does_not_invalidate_still_active_parent(self):
        snap = snapshot(8860)
        md = deepcopy(snap.metadata)
        md["mission_context"]["parent"]["terminal"]["qualified"] = True
        md["mission_context"]["parent"]["supported"] = False
        self.assertTrue(rejoin_candidates(armed_commander(), replace(snap, metadata=md)))

    def test_changed_invalidated_or_transferred_parent_cancels_watch(self):
        for change in ({"id": "A_DIFFERENT_PARENT"}, {"status": "INVALIDATED"},
                       {"invalidated": True}, {"side": "NO"}, {"continuity_generation": 1}):
            with self.subTest(change=change):
                commander = armed_commander()
                snap = snapshot(8860)
                md = deepcopy(snap.metadata)
                md["mission_context"]["parent"].update(change)
                self.assertFalse(rejoin_candidates(commander, replace(snap, metadata=md)))
                self.assertIsNone(commander._opening_rail_value_watch.state)
                self.assertFalse(rejoin_candidates(commander, snapshot(8860)))

    def test_ticker_and_source_generation_do_not_inherit_old_watch(self):
        commander = armed_commander()
        self.assertFalse(rejoin_candidates(commander, replace(snapshot(8860), ticker="NEXT_CONTRACT")))
        self.assertIsNone(commander._opening_rail_value_watch.state)
        for field in ("geometry_continuity_generation", "source_generation"):
            commander = armed_commander()
            snap = snapshot(8860)
            md = deepcopy(snap.metadata)
            md[field] += 1
            self.assertFalse(rejoin_candidates(commander, replace(snap, metadata=md)))
            self.assertIsNone(commander._opening_rail_value_watch.state)

    def test_stale_unknown_or_mismatched_receipt_cancels_watch(self):
        for kind in ("missing", "stale", "source_mismatch", "not_physical_current"):
            with self.subTest(kind=kind):
                commander = armed_commander()
                snap = snapshot(8860)
                md = deepcopy(snap.metadata)
                if kind == "missing":
                    md.pop(RECEIPT_KEY)
                elif kind == "stale":
                    md[RECEIPT_KEY]["receive_age_seconds_at_capture"] = 6.
                elif kind == "source_mismatch":
                    md[RECEIPT_KEY]["source_ms"] += 1.
                else:
                    md["physical_current"] = False
                self.assertFalse(rejoin_candidates(commander, replace(snap, metadata=md)))
                self.assertIsNone(commander._opening_rail_value_watch.state)

    def test_source_backstep_cannot_rearm_by_repeating_old_callback(self):
        commander = armed_commander()
        commander.physical_entry_candidates(snapshot(8731))
        for _ in range(2):
            commander.physical_entry_candidates(snapshot(8723))
            self.assertIsNone(commander._opening_rail_value_watch.state)
        self.assertFalse(rejoin_candidates(commander, snapshot(8860)))

    def test_repeated_wait_and_price_refresh_do_not_consume_or_reset_opportunity(self):
        commander = armed_commander()
        original = deepcopy(commander._opening_rail_value_watch.state)
        for sequence in (8723, 8723, 8731, 8731, 8853):
            commander.physical_entry_candidates(snapshot(sequence))
            state = commander._opening_rail_value_watch.state
            self.assertEqual(state["mission_id"], original["mission_id"])
            self.assertEqual(state["deferred_ask"], .54)
            self.assertFalse(commander._consumed_physical_missions)
        self.assertTrue(rejoin_candidates(commander, snapshot(8860)))

    def test_existing_first_300s_window_expires_without_forcing_entry(self):
        commander = armed_commander()
        snap = snapshot(8860)
        self.assertTrue(rejoin_candidates(commander, replace(snap, contract_age_s=300.)))
        self.assertFalse(rejoin_candidates(commander, replace(snap, contract_age_s=300.001)))
        self.assertIsNone(commander._opening_rail_value_watch.state)
        commander = armed_commander()
        self.assertFalse(rejoin_candidates(commander, snapshot(9308)))

    def test_elapsed_time_alone_cannot_enter_without_current_rejoin(self):
        commander = armed_commander()
        snap = replace(snapshot(8853), contract_age_s=299.)
        self.assertFalse(rejoin_candidates(commander, snap))
        self.assertIs(commander.decide_entry((rail_adviser(snap),), snap, {}).action, Action.WAIT)

    def test_current_watch_required_to_admit_saved_rejoin_candidate(self):
        snap = snapshot(8860)
        candidate = rejoin_candidates(armed_commander(), snap)[0]
        decision = OneCommander().decide_entry((candidate,), snap, {})
        self.assertEqual(decision.reason, "COMMANDER_OPENING_RAIL_CURRENT_WATCH_REQUIRED")

    def test_saved_candidate_cannot_borrow_a_different_current_parent_watch(self):
        snap = snapshot(8860)
        saved = rejoin_candidates(armed_commander(), snap)[0]
        commander = OneCommander()
        def other_parent(sequence):
            original = snapshot(sequence)
            md = deepcopy(original.metadata)
            md["mission_context"]["parent"]["id"] = "DISTINCT_PARENT"
            return replace(original, metadata=md)
        commander.physical_entry_candidates(other_parent(8723))
        current = other_parent(8860)
        self.assertTrue(rejoin_candidates(commander, current))
        decision = commander.decide_entry((saved,), current, {})
        self.assertEqual(decision.reason, "COMMANDER_OPENING_RAIL_CURRENT_WATCH_IDENTITY_REQUIRED")

    def test_rejoin_candidate_provenance_and_exact_current_frame_are_rechecked(self):
        for field in ("parent_id", "continuity_generation", "observed_residence_start_source_ms",
                      "source_connection_epoch", "deferred_source_ms", "deferred_mission_id"):
            with self.subTest(field=field):
                commander = armed_commander()
                snap = snapshot(8860)
                candidate = rejoin_candidates(commander, snap)[0]
                metadata = deepcopy(candidate.metadata)
                metadata["commander_physical_evidence"][field] = "MISMATCH"
                decision = commander.decide_entry((replace(candidate, metadata=metadata),), snap, {})
                self.assertEqual(decision.reason, "COMMANDER_OPENING_RAIL_CURRENT_WATCH_IDENTITY_REQUIRED")
        commander = armed_commander()
        candidate = rejoin_candidates(commander, snapshot(8860))[0]
        decision = commander.decide_entry((candidate,), snapshot(8861), {})
        self.assertEqual(decision.reason, "COMMANDER_OPENING_RAIL_CURRENT_WATCH_IDENTITY_REQUIRED")

    def test_real_fill_consumes_original_and_value_missions_once(self):
        commander = armed_commander()
        snap = snapshot(8860)
        state = deepcopy(commander._opening_rail_value_watch.state)
        candidate = rejoin_candidates(commander, snap)[0]
        commander.mark_entry_filled(candidate, ticker=snap.ticker)
        self.assertIn((snap.ticker, state["deferred_mission_id"]), commander._consumed_physical_missions)
        self.assertIn((snap.ticker, candidate.metadata["physical_mission_id"]), commander._consumed_physical_missions)
        self.assertFalse(rejoin_candidates(commander, snapshot(8861)))
        self.assertIs(commander.decide_entry((candidate,), snapshot(8861), {}).action, Action.WAIT)

    def test_adviser_fill_also_consumes_shared_value_watch(self):
        commander = armed_commander()
        snap = snapshot(8860)
        candidate = rejoin_candidates(commander, snap)[0]
        adviser = rail_adviser(snap)
        self.assertIs(commander.decide_entry((adviser,), snap, {}).action, Action.ENTER)
        commander.mark_entry_filled(adviser, ticker=snap.ticker)
        self.assertIn((snap.ticker, candidate.metadata["physical_mission_id"]), commander._consumed_physical_missions)
        self.assertFalse(rejoin_candidates(commander, snapshot(8861)))

    def test_consumed_original_opening_cannot_reenter_through_direct_admission(self):
        commander = armed_commander()
        snap = snapshot(8860)
        candidate = rejoin_candidates(commander, snap)[0]
        commander.mark_entry_filled(candidate, ticker=snap.ticker)
        old_opening = replace(original_entry_intent(8723),
            source_time=snap.metadata["current_geometry"]["epoch_ms"] / 1000.)
        decision = commander.decide_entry((old_opening,), snap, {})
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, "COMMANDER_PHYSICAL_MISSION_ALREADY_FILLED")

    def test_filled_first_minute_watch_cannot_rearm_on_later_premium_dip(self):
        # Explicit synthetic lifecycle control: advance source and parent
        # together on a nonfuture legacy clock, then provide a value rejoin
        # before the original 60-second window ends.  No recorded trade claim.
        start = snapshot(8723)
        def advance(seconds, *, rejoin):
            md = deepcopy(start.metadata)
            now = start.now_ts + seconds
            source = (now - .1) * 1000.
            md.pop(RECEIPT_KEY)
            md["current_geometry"]["epoch_ms"] = source
            md["geometry_last_epoch_ms"] = source
            md["mission_context"]["parent"]["source_ms"] = source
            gap = md["ema9_ema30_cross_context"]["gap_lifecycle"]
            gap["observed_side_residence_seconds"] = (source - gap["observed_side_residence_start_source_ms"]) / 1000.
            if rejoin:
                md["current_geometry"]["current_native_direction"] = "UP"
                for key in ("btc_change6", "btc_change9", "ema9_change6"):
                    md["current_geometry"][key] = abs(md["current_geometry"][key])
            return replace(start, now_ts=now, contract_age_s=start.contract_age_s + seconds,
                           yes_ask=.35 if rejoin else .54, metadata=md)
        for source_break in ("none", "connection", "connection_and_generation"):
            with self.subTest(source_break=source_break):
                commander = armed_commander()
                ready = advance(10., rejoin=True)
                candidate = rejoin_candidates(commander, ready)[0]
                self.assertIs(commander.decide_entry((candidate,), ready, {}).action, Action.ENTER)
                commander.mark_entry_filled(candidate, ticker=ready.ticker)
                for seconds, rejoin in ((20., False), (30., True)):
                    later = advance(seconds, rejoin=rejoin)
                    if source_break != "none":
                        later.metadata["current_geometry"]["connection_epoch"] += 1
                    if source_break == "connection_and_generation":
                        later.metadata["geometry_continuity_generation"] += 1
                        later.metadata["mission_context"]["parent"]["continuity_generation"] += 1
                    self.assertFalse(rejoin_candidates(commander, later))
                    self.assertIsNone(commander._opening_rail_value_watch.state)

    def test_genuinely_new_original_mission_remains_eligible_after_consumption(self):
        commander = OneCommander()
        old = original_entry_intent(3126)
        commander.mark_entry_filled(old, ticker=snapshot(3126).ticker)
        snap = snapshot(6320)
        candidates = commander.physical_entry_candidates(snap)
        self.assertTrue(candidates)
        self.assertIs(commander.decide_entry(candidates, snap, {}).action, Action.ENTER)

    def test_opening_filled_without_watch_cannot_later_seed_value_watch(self):
        # Synthetic current-UP version isolates an ordinary premium fill with
        # no deferred watch.  Later dip/rejoin frames are the exact originals.
        early = snapshot(8723)
        md = deepcopy(early.metadata)
        md["current_geometry"]["current_native_direction"] = "UP"
        for key in ("btc_change6", "btc_change9", "ema9_change6"):
            md["current_geometry"][key] = abs(md["current_geometry"][key])
        early = replace(early, metadata=md)
        commander = OneCommander()
        candidates = commander.physical_entry_candidates(early)
        accepted = commander.decide_entry(candidates, early, {})
        self.assertIs(accepted.action, Action.ENTER)
        self.assertIsNone(commander._opening_rail_value_watch.state)
        commander.mark_entry_filled(accepted.intent, ticker=early.ticker)
        self.assertFalse(commander.physical_entry_candidates(snapshot(8731)))
        self.assertIsNone(commander._opening_rail_value_watch.state)
        self.assertFalse(rejoin_candidates(commander, snapshot(8860)))

    def test_objective_wait_keeps_watch_and_closed_session_does_not_enter(self):
        for changes, expected in (({"quote_current": False}, "OBJECTIVE_QUOTE_STALE"),
                                  ({"depth_available": False}, "OBJECTIVE_DEPTH_UNAVAILABLE"),
                                  ({"entry_allowed": False}, "OBJECTIVE_ENTRY_NOT_ALLOWED")):
            with self.subTest(changes=changes):
                commander = armed_commander()
                snap = replace(snapshot(8860), **changes)
                candidates = rejoin_candidates(commander, snap)
                self.assertEqual(commander.decide_entry(candidates, snap, {}).reason, expected)
                self.assertFalse(commander._consumed_physical_missions)
                self.assertIsNotNone(commander._opening_rail_value_watch.state)
        rows = opening_trajectory_probe()["third_first_300s"]["callbacks"]
        closed = [row for row in rows if not row["recorded_engine_entry_window_open"]]
        self.assertEqual(closed[0]["sequence"], 8964)

    def test_affirmative_opposite_release_cancels_watch(self):
        commander = armed_commander()
        snap = snapshot(8860)
        md = deepcopy(snap.metadata)
        md.update(release_confirmed_current=True, release_candidate_side="NO")
        self.assertFalse(rejoin_candidates(commander, replace(snap, metadata=md)))
        self.assertIsNone(commander._opening_rail_value_watch.state)

    def test_opposing_tp_or_junction_defers_without_rewriting_parent(self):
        for changes in ({"contract_ownership": "STARTING_LEG_FAVORED", "contract_ownership_side": "NO"},
                        {"target_between_ema9_ema30": True}):
            with self.subTest(changes=changes):
                commander = armed_commander()
                snap = snapshot(8860)
                md = deepcopy(snap.metadata)
                md["tp_geometry"].update(changes)
                self.assertFalse(rejoin_candidates(commander, replace(snap, metadata=md)))
                self.assertIsNotNone(commander._opening_rail_value_watch.state)
                self.assertTrue(rejoin_candidates(commander, snap))

    def test_synthetic_no_parent_mirror_uses_same_value_and_rejoin_rules(self):
        commander = OneCommander()
        early = mirror(snapshot(8723))
        self.assertFalse(commander.physical_entry_candidates(early))
        self.assertIsNotNone(commander._opening_rail_value_watch.state)
        later = mirror(snapshot(8860))
        candidates = rejoin_candidates(commander, later)
        self.assertEqual(len(candidates), 1)
        self.assertIs(candidates[0].side, Side.NO)
        self.assertEqual(candidates[0].max_price, .35)
        self.assertIs(commander.decide_entry(candidates, later, {}).action, Action.ENTER)

    def test_exact_same_side_enum_and_text_inventory_both_wait_without_duplicate(self):
        data = record(8823)
        snap = snapshot(8823)
        intents = tuple(intent for intent in original_intents(data) if intent.action in (Action.ENTER, Action.RELAY))
        self.assertTrue(intents)
        # A fresh Commander cannot manufacture the earlier opening watch
        # from this generic early Rail. Test inventory governance against the
        # independently earned current8860 value rejoin below.
        self.assertEqual(OneCommander().decide_entry(intents,snap,{}).reason,
                         "OPPORTUNITY_MAIN_OBSERVE_UNTIL_300S")
        for held_side in (Side.YES, "YES"):
            with self.subTest(held_side=held_side):
                commander=armed_commander();snap=snapshot(8860)
                intents=rejoin_candidates(commander,snap)
                decision = commander.decide_entry(intents, snap,
                    {"3": {"ticker": snap.ticker, "side": held_side, "custody_state": "NORMAL"}})
                self.assertIs(decision.action, Action.WAIT)
                self.assertIsNone(decision.intent)
                self.assertEqual(decision.reason, "CURRENT_CONTRACT_SAME_SIDE_INVENTORY_NO_DUPLICATE")

    def test_opposite_inventory_diagnostic_keeps_wait_semantics(self):
        snap = snapshot(8860)
        for held_side in (Side.NO, "NO"):
            commander=armed_commander()
            decision = commander.decide_entry((rail_adviser(snap),), snap,
                {"3": {"ticker": snap.ticker, "side": held_side, "custody_state": "NORMAL"}})
            self.assertIs(decision.action, Action.WAIT)
            self.assertEqual(decision.reason, "CURRENT_CONTRACT_OPPOSITE_INVENTORY_EXIT_PENDING_CORRECTIVE_HANDOFF")


if __name__ == "__main__":
    unittest.main()
