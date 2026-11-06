"""Approved PID17224 B: ordinary MAIN returns retain established-parent proof.

The negative control is the exact entry-time snapshot/intent at decision 6087.
Derived mirror and old-predicate proof-completion controls are labelled
synthetic. The original snapshot includes physical rows later than its captured
decision clock; neither an old predicate nor a role label can bypass the new
current-source requirement. No future outcomes or settlement information enter.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import (
    _physical_entry_candidates,
    ema9_continuation_precedent,
    main_return_matches_established_parent,
    physical_entry_candidates,
    positive_candidate_matches_continuation,
)
from strategy_core.directional_parent import directional_parent_evidence
from strategy_core.types import Action, Lane, Side
from tests.tool_rack.pid17224_recorded_fixtures import entry_intent, intents, record, snapshot


DENIAL = "OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED"


def level_match_snapshot():
    """Restore the exact current rack cache copied into the recorded intent.

    The raw physical_metadata is captured before ToolRack.prepare_snapshot
    adds historical_extreme_release.  The accepted intent records the exact
    recent_level_match that this route consumed on that same decision. Only
    this object is restored here; no historical candles or outcomes are added.
    Boundary tests also exercise the unaugmented raw snapshot separately.
    """
    s = snapshot(6087)
    match = entry_intent(6087).metadata["commander_physical_evidence"]["recent_level_match"]
    return replace(s, metadata={**s.metadata, "historical_extreme_release": {
        "recent_level_match": deepcopy(match),
    }})


def mirror_main_scene(s, intent):
    """Reflect the entry evidence about a fixed price axis; retain all clocks.

    This is a labelled symmetry control, not another recorded market scene.
    The full original snapshot remains available unchanged in the corpus.
    """
    signed = {
        "ema_gap", "current_signed_gap_btc", "current_signed_target_gap",
        "distance_btc", "btc_change6", "btc_change9", "btc_change30",
        "btc_change60", "ema9_change6", "ema9_change30", "ema9_change60",
        "micro_slope3s", "micro_slope6s", "micro_slope9s",
        "struct_slope3m", "struct_slope6m", "struct_slope9m", "ema30_slope3m",
    }
    absolute = {
        "btc_price", "ema9", "ema30", "target", "anchor", "entry_btc",
        "entry_ema9", "arc_start_ema9", "arc_extreme_ema9", "origin_ema9",
        "origin_btc", "extreme_btc", "ema9_extreme",
    }
    swap = {"YES": "NO", "NO": "YES", "UP": "DOWN", "DOWN": "UP"}

    def reflected(value, key=""):
        if isinstance(value, dict):
            result = {k: reflected(v, k) for k, v in value.items()}
            for low, high in (("observed_min_btc", "observed_max_btc"),):
                if low in value and high in value:
                    result[low], result[high] = 160000.0-value[high], 160000.0-value[low]
            return result
        if isinstance(value, (list, tuple)):
            return type(value)(reflected(v, key) for v in value)
        if isinstance(value, str):
            return swap.get(value, value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if key in signed:
                return -value
            if key in absolute:
                return 160000.0-value
        return value

    mirrored = replace(s, yes_ask=s.no_ask, no_ask=s.yes_ask,
                       yes_bid=s.no_bid, no_bid=s.yes_bid,
                       yes_sell_allowed=s.no_sell_allowed,
                       no_sell_allowed=s.yes_sell_allowed,
                       metadata=reflected(deepcopy(s.metadata)))
    new_side = Side.NO if intent.side is Side.YES else Side.YES
    mirrored_intent = replace(intent, side=new_side,
                              metadata=reflected(deepcopy(intent.metadata)))
    return mirrored, mirrored_intent


def completed_transfer_scene():
    """Derived positive: the established NO parent has actual terminal transfer.

    No EMA cross is imposed.  The old gap and current arc may still point NO;
    the existing terminal, 30-second reversal and TP transfer proof are present.
    """
    s = level_match_snapshot()
    md = deepcopy(s.metadata)
    md["mountain"].update(
        terminal_evidence_qualified=True, mature_edge=True, edge_window_active=True,
        failed_reextension=True, meaningful_retreat=True,
    )
    md["mountain"]["parent_structure"].update(
        parent_terminal_ready=True, parent_turning_or_flat=True,
    )
    md["current_geometry"]["ema9_change30"] = abs(md["current_geometry"]["ema9_change30"])
    md["tp_geometry"].update(contract_ownership="BOUNCE_FAVORED", contract_ownership_side="YES")
    return replace(s, metadata=md), entry_intent(6087)


class PID17224MainReturnTests(unittest.TestCase):
    def test_recorded_bounce_does_not_erase_the_established_no_parent(self):
        s, intent = level_match_snapshot(), entry_intent(6087)
        parent = directional_parent_evidence(s)
        self.assertTrue(parent["qualified"])
        self.assertEqual(parent["side"], "NO")
        self.assertIsNone(parent["gap_age_s"])
        self.assertGreater(parent["observed_residence_age_s"], 1600.0)
        self.assertFalse(ema9_continuation_precedent(s)["qualified"])
        self.assertGreater(s.metadata["current_geometry"]["btc_change6"], 0)
        self.assertLess(s.metadata["current_geometry"]["ema9_change30"], 0)
        self.assertFalse(main_return_matches_established_parent(intent, s))
        self.assertFalse(positive_candidate_matches_continuation(intent, s))
        # Confirm this is the route that generated the original bad proposal,
        # then prove every published positive candidate receives the check.
        unchecked = _physical_entry_candidates(s)
        self.assertEqual([(i.reason, i.side) for i in unchecked], [(intent.reason, intent.side)])
        self.assertFalse(any(i.side is Side.YES for i in physical_entry_candidates(s)))
        self.assertFalse(any(i.side is Side.YES for i in OneCommander().physical_entry_candidates(s)))

    def test_original_recorded_main_intent_cannot_bypass_the_commander_boundary(self):
        source = next(row["decision"] for row in record(6087)["decisions"] if row["scope"] == "ENTRY")
        self.assertEqual(source["action"], "ENTER")
        s, intent = snapshot(6087), entry_intent(6087)
        decision = OneCommander().decide_entry((intent,), s, {})
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, DENIAL)
        self.assertIsNone(decision.intent)

    def test_mirrored_up_parent_rejects_the_same_short_no_bounce(self):
        s, intent = mirror_main_scene(level_match_snapshot(), entry_intent(6087))
        self.assertEqual(directional_parent_evidence(s)["side"], "YES")
        self.assertFalse(ema9_continuation_precedent(s)["qualified"])
        self.assertIs(intent.side, Side.NO)
        self.assertFalse(main_return_matches_established_parent(intent, s))
        self.assertFalse(positive_candidate_matches_continuation(intent, s))
        self.assertEqual([i.side for i in _physical_entry_candidates(s)], [Side.NO])
        self.assertFalse(any(i.side is Side.NO for i in physical_entry_candidates(s)))
        decision = OneCommander().decide_entry((intent,), s, {})
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, DENIAL)

    def test_old_terminal_transfer_predicate_does_not_override_current_source_requirement(self):
        original = completed_transfer_scene()
        for s, intent in (original, mirror_main_scene(*original)):
            with self.subTest(side=intent.side):
                parent = directional_parent_evidence(s)
                self.assertTrue(parent["qualified"])
                self.assertNotEqual(parent["side"], intent.side.value)
                self.assertTrue(main_return_matches_established_parent(intent, s))
                candidates = physical_entry_candidates(s)
                matching = [i for i in candidates if i.side is intent.side
                            and i.reason == "COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN"]
                self.assertEqual(len(matching), 1)
                decision = OneCommander().decide_entry(matching, s, {})
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, DENIAL)
                self.assertEqual(matching[0].max_price, .20)

    def test_partial_terminal_or_tp_claims_do_not_inherit_the_transfer_exception(self):
        complete, intent = completed_transfer_scene()
        variants = {
            "tp_still_old_side": ("tp_geometry", "contract_ownership_side", "NO"),
            "ema9_still_old_side": ("current_geometry", "ema9_change30", -8.049760507623432),
            "no_current_terminal": ("mountain", "terminal_evidence_qualified", False),
            "no_current_edge_window": ("mountain", "edge_window_active", False),
        }
        for name, (group, key, value) in variants.items():
            with self.subTest(proof=name):
                md = deepcopy(complete.metadata)
                md[group][key] = value
                s = replace(complete, metadata=md)
                self.assertFalse(main_return_matches_established_parent(intent, s))
                self.assertFalse(any(i.side is Side.YES for i in physical_entry_candidates(s)))

    def test_mountain_family_cannot_escape_by_changing_role_lane_or_family_variant(self):
        s, original = snapshot(6087), entry_intent(6087)
        for family in ("MOUNTAIN_EDGE", "MOUNTAIN_CONTRACT_LEG"):
            for lane in (Lane.MAIN, Lane.TACTICAL):
                with self.subTest(family=family, lane=lane):
                    intent = replace(original, lane=lane, metadata={
                        **original.metadata, "commander_candidate_family": family,
                        "position_role": "TACTICAL" if lane is Lane.TACTICAL else "PRIMARY",
                    })
                    self.assertFalse(main_return_matches_established_parent(intent, s))
                    decision = OneCommander().decide_entry((intent,), s, {})
                    self.assertIs(decision.action, Action.WAIT)
                    self.assertEqual(decision.reason, DENIAL)

    def test_separate_tactical_and_release_species_keep_their_own_checks(self):
        s, ordinary = snapshot(6087), entry_intent(6087)
        for family in ("EDGE_HEIST", "QUOTE_WAVE_SCALP", "HISTORICAL_EXTREME_RELEASE_PREP"):
            with self.subTest(family=family):
                tactical = replace(ordinary, lane=Lane.TACTICAL, metadata={
                    **ordinary.metadata, "commander_candidate_family": family,
                    "position_role": "TACTICAL",
                })
                self.assertTrue(main_return_matches_established_parent(tactical, s))
        heist = next(i for i in intents(5600) if i.tool == "MARKET_HEIST")
        self.assertTrue(main_return_matches_established_parent(heist, snapshot(5600)))
        for seq in (4561, 4601):
            self.assertTrue(main_return_matches_established_parent(entry_intent(seq), snapshot(seq)))

    def test_current_confirmed_release_transfer_retires_old_parent_claim(self):
        s, intent = snapshot(6087), entry_intent(6087)
        md = deepcopy(s.metadata)
        md.update(release_confirmed_current=True, release_candidate_side="YES")
        released = replace(s, metadata=md)
        self.assertFalse(directional_parent_evidence(released)["qualified"])
        self.assertTrue(main_return_matches_established_parent(intent, released))

    def test_quality_check_does_not_rewrite_original_inputs_or_return_floor(self):
        s, intent = snapshot(6087), entry_intent(6087)
        before_s, before_i = deepcopy(s), deepcopy(intent)
        main_return_matches_established_parent(intent, s)
        positive_candidate_matches_continuation(intent, s)
        physical_entry_candidates(s)
        self.assertEqual(s, before_s)
        self.assertEqual(intent, before_i)
        positive, _ = completed_transfer_scene()
        candidate = next(i for i in physical_entry_candidates(positive) if i.side is Side.YES)
        self.assertEqual(candidate.metadata["floor_policy"], intent.metadata["floor_policy"])
        self.assertEqual(candidate.max_price, intent.max_price)
        self.assertEqual(candidate.size_tier, intent.size_tier)


if __name__ == "__main__":
    unittest.main()
