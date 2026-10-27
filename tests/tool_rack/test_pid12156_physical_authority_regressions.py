"""Recorded PID12156 failure classes and custody controls for PAPER promotion."""

import unittest
from dataclasses import replace

from strategy_core.detectors.heist_geometry import detect_heist_geometry
from strategy_core.detectors.mountain_geometry import detect_mountain_geometry
from strategy_core.detectors.release_geometry import ReleaseProbe
from strategy_core.router import PhysicalEvidence
from strategy_core.tool_rack import ToolRackController
from strategy_core.tools.heist import MarketHeistTool
from strategy_core.tools.mountain import AlternatingMountainTool
from strategy_core.tools.rail import RailTool
from strategy_core.tools.release import ReleaseEvidence, ReleaseWatcher
from strategy_core.types import Action, MarketSnapshot, Side, Territory


def snap(ts=1000, ticker="KX1", age=500, yes=.35, no=.35, **metadata):
    return MarketSnapshot(ts, ticker, age, yes, no, metadata=metadata)


def mountain(side=Side.YES, *, extreme=1100, edge="A1:1000000", mature=True):
    return {
        "owner_side": side.value, "current_arc_id": "A1",
        "mature_edge": mature, "edge_window_active": True,
        "stall": mature, "hesitation": mature, "failed_reextension": False,
        "meaningful_retreat": False, "strong_active_release": False,
        "edge_id": edge, "owner_extreme_btc": extreme,
        "edge_tolerance_dollars": 3.0,
    }


def rail_evidence(side=Side.YES, **overrides):
    values = dict(ema9_direction=side, ema30_direction=side,
                  ema_pair_parallel=True, directional_residence=True,
                  contracts_persistent=1.0, rolling_mountain=True)
    values.update(overrides)
    return PhysicalEvidence(**values)


def position(intent, snapshot):
    return {"ticker": snapshot.ticker, "side": intent.side.value,
            "territory_id": intent.territory_id,
            "opportunity_id": intent.opportunity_id,
            "entry_metadata": dict(intent.metadata), "entry_time": snapshot.now_ts}


class RecordedAuthorityRegressions(unittest.TestCase):
    @staticmethod
    def box_probe(btc=1050, side=Side.YES, lower=1000, upper=1100, tolerance=10):
        return ReleaseProbe(
            btc=btc, ema9=btc - (5 if side is Side.YES else -5),
            ema30=btc - (10 if side is Side.YES else -10), range60=100,
            arc_side=side, arc_phase="EXPANDING", short_struct_side=side,
            medium_struct_side=side, micro_side=side,
            yes_residence_fraction=1 if side is Side.YES else 0,
            no_residence_fraction=1 if side is Side.NO else 0,
            yes_stack_fraction=1 if side is Side.YES else 0,
            no_stack_fraction=1 if side is Side.NO else 0,
            heist_lower=lower, heist_upper=upper, heist_edge_tolerance=tolerance,
            mountain_extreme_btc=btc, mountain_edge_age_s=0, diagnostics={},
        )

    def test_heist_release_uses_owner_box_when_rolling_bounds_chase_breakout(self):
        for side, btc, lower, upper in (
            (Side.YES, 1120, 1010, 1140), (Side.NO, 980, 950, 1080),
        ):
            with self.subTest(side=side):
                rack = ToolRackController()
                evidence = PhysicalEvidence(qualified_heist=True, ema9_direction=side)
                rack.observe(evidence, snap(
                    heist={"qualified_box": True, "lower": 1000, "upper": 1100,
                           "edge_tolerance": 10}, release_probe=self.box_probe(side=side)))
                out = rack.observe(evidence, snap(ts=1010,
                    heist={"qualified_box": True, "lower": lower, "upper": upper,
                           "edge_tolerance": 12},
                    release_probe=self.box_probe(btc, side, lower, upper, 12)))
                self.assertTrue(out.handoff_confirmed)
                self.assertEqual(out.intents[0].side, side)
                self.assertEqual(out.release_diagnostics["owner_box_lower"], 1000)
                self.assertEqual(out.release_diagnostics["owner_box_upper"], 1100)
                self.assertTrue(out.release_diagnostics["owner_box_boundary_pinned"])

    def test_new_box_after_confirmed_handoff_gets_its_own_boundaries(self):
        rack = ToolRackController()
        evidence = PhysicalEvidence(qualified_heist=True, ema9_direction=Side.YES)
        first = rack.observe(evidence, snap(
            heist={"qualified_box": True, "lower": 1000, "upper": 1100,
                   "edge_tolerance": 10}, release_probe=self.box_probe()))
        rack.observe(evidence, snap(ts=1010,
            heist={"qualified_box": True, "lower": 1010, "upper": 1140,
                   "edge_tolerance": 12}, release_probe=self.box_probe(1120, upper=1140)))
        new = rack.observe(evidence, snap(ts=1020,
            heist={"qualified_box": True, "lower": 1110, "upper": 1150,
                   "edge_tolerance": 5},
            release_probe=self.box_probe(1120, lower=1110, upper=1150, tolerance=5)))
        self.assertEqual(new.owned_territory, Territory.MARKET_HEIST)
        self.assertNotEqual(new.territory_id, first.territory_id)
        self.assertFalse(new.handoff_confirmed)
        self.assertEqual(new.release_diagnostics["owner_box_lower"], 1110)
        self.assertEqual(new.release_diagnostics["owner_box_upper"], 1150)

    def test_rail_matches_current_physical_mountain_despite_retained_old_owner(self):
        rack = ToolRackController()
        rack.observe(PhysicalEvidence(ema9_direction=Side.YES, alternating_mountain=True),
                     snap(mountain=mountain()))
        out = rack.observe(rail_evidence(Side.NO, release_candidate_side=Side.NO),
                           snap(ts=1100, mountain=mountain(Side.NO, mature=False)))
        self.assertEqual(out.owned_territory, Territory.DOWN_RAIL)
        self.assertEqual(out.owned_side, Side.NO)
        self.assertEqual(out.intents[0].tool, "RAIL")
        self.assertEqual(out.intents[0].side, Side.NO)

    def test_pid12156_up_rail_is_not_suppressed_by_mountain_release_watch(self):
        rack = ToolRackController()
        rack.observe(PhysicalEvidence(ema9_direction=Side.YES, alternating_mountain=True),
                     snap(mountain=mountain()))
        out = rack.observe(rail_evidence(
            release_candidate_side=Side.NO, release_first_slowdown_only=True),
            snap(ts=1010, yes=.35, no=.65, mountain=mountain()))
        self.assertEqual(out.owned_territory, Territory.UP_RAIL)
        self.assertEqual(out.intents[0].tool, "RAIL")
        self.assertEqual(out.intents[0].side, Side.YES)
        self.assertEqual(out.intents[0].action, Action.ENTER)
        self.assertFalse(any(i.tool == "ALTERNATING_MOUNTAIN" for i in out.intents))

    def test_confirmed_opposing_release_still_outranks_old_side_raw_rail(self):
        rack = ToolRackController()
        rack.observe(PhysicalEvidence(ema9_direction=Side.YES, alternating_mountain=True),
                     snap(mountain=mountain()))
        out = rack.observe(rail_evidence(
            release_candidate_side=Side.NO, release_boundary_break=True,
            release_directional_expansion=True, release_new_side_residence=True),
            snap(ts=1010, mountain=mountain()))
        self.assertTrue(out.handoff_confirmed)
        self.assertEqual(out.intents[0].tool, "RELEASE_WATCHER")
        self.assertEqual(out.intents[0].side, Side.NO)

    def test_directionless_classifier_cannot_erase_confirmed_release_side(self):
        rack = ToolRackController()
        rack.observe(rail_evidence(Side.NO), snap())
        rack.observe(rail_evidence(Side.NO, release_candidate_side=Side.YES,
                                  release_boundary_break=True,
                                  release_directional_expansion=True,
                                  release_new_side_residence=True), snap(ts=1010))
        for index, evidence in enumerate((
            PhysicalEvidence(alternating_mountain=True),
            PhysicalEvidence(qualified_heist=True),
        )):
            out = rack.observe(evidence, snap(ts=1020 + index))
            self.assertEqual(out.owned_territory, Territory.RELEASE_TRANSITION)
            self.assertEqual(out.owned_side, Side.YES)
            self.assertIsNone(out.active_tool)
        out = rack.observe(rail_evidence(Side.YES), snap(ts=1030))
        self.assertEqual(out.owned_territory, Territory.UP_RAIL)

    def test_mountain_none_flicker_preserves_owner_then_rail_graduates(self):
        rack = ToolRackController()
        rack.observe(PhysicalEvidence(ema9_direction=Side.YES, alternating_mountain=True),
                     snap(mountain=mountain()))
        out = rack.observe(PhysicalEvidence(alternating_mountain=True),
                           snap(ts=1001, mountain=mountain()))
        self.assertEqual(out.owned_side, Side.YES)
        out = rack.observe(rail_evidence(), snap(ts=1010))
        self.assertEqual(out.owned_territory, Territory.UP_RAIL)

    def test_same_direction_heist_watch_does_not_hide_qualified_rail(self):
        rack = ToolRackController()
        rack.observe(PhysicalEvidence(qualified_heist=True, ema9_direction=Side.YES), snap())
        out = rack.observe(rail_evidence(release_candidate_side=Side.NO,
                                         release_first_slowdown_only=True), snap(ts=1010))
        self.assertEqual(out.owned_territory, Territory.UP_RAIL)


class PhysicalOpportunityRegressions(unittest.TestCase):
    def test_equal_extreme_retest_keeps_detector_identity_strict_new_high_renews(self):
        def row(ts, price):
            return {"arc_id": "A1", "arc_direction": "UP", "epoch_ms": ts * 1000,
                    "arc_age_sec": ts, "btc_price": price, "ema9": price - 3,
                    "arc_phase": "CREST_FORMING", "arc_amplitude": 40,
                    "arc_prominence_threshold": 5, "range60": 100}
        rows = [row(0, 1050), row(110, 1100), row(125, 1090)]
        first = detect_mountain_geometry(rows)
        same = detect_mountain_geometry(rows + [row(140, 1100), row(155, 1095)])
        new = detect_mountain_geometry(rows + [row(140, 1101), row(155, 1095)])
        self.assertEqual(first.edge_id, same.edge_id)
        self.assertNotEqual(first.edge_id, new.edge_id)

    def test_filled_mountain_equal_retest_cannot_rearm_but_strict_extreme_can(self):
        tool = AlternatingMountainTool(territory_id="M1", owner_side=Side.YES)
        first = list(tool.on_market_event(snap(mountain=mountain())))[0]
        tool.mark_entry_filled(first.opportunity_id, ticker="KX1")
        tool.mark_position_closed(ticker="KX1")
        same = list(tool.on_market_event(snap(ts=1010, mountain=mountain(edge="A1:1010000"))))[0]
        self.assertEqual(same.action, Action.WAIT)
        self.assertEqual(same.reason, "MOUNTAIN_EDGE_ALREADY_FILLED")
        new = list(tool.on_market_event(snap(ts=1020, mountain=mountain(extreme=1105, edge="A1:1020000"))))[0]
        self.assertEqual(new.action, Action.RELAY)
        self.assertNotEqual(first.opportunity_id, new.opportunity_id)

    def test_heist_inner_wiggle_preserves_visit_center_traversal_renews(self):
        prices = [1000, 1050, 1100, 1050, 1000, 1050, 1100, 1050, 1000, 1050, 1100]
        def rows(values):
            return [{"epoch_ms": i * 15000, "btc_price": p, "ema9": 1050,
                     "ema30": 1050, "arc_prominence_threshold": 5}
                    for i, p in enumerate(values)]
        first = detect_heist_geometry(rows(prices))
        same = detect_heist_geometry(rows(prices + [1080, 1099]))
        new = detect_heist_geometry(rows(prices + [1080, 1099, 1050, 1099]))
        self.assertTrue(first.qualified_box)
        self.assertEqual(first.visit_id, same.visit_id)
        self.assertNotEqual(first.visit_id, new.visit_id)

    def test_reestimated_heist_visit_timestamp_without_center_is_not_new_fill(self):
        tool = MarketHeistTool(territory_id="H1")
        details = {"qualified_box": True, "at_upper_edge": True,
                   "current_zone": "UPPER", "visit_id": "UPPER:1000"}
        first = list(tool.on_market_event(snap(heist=details)))[0]
        tool.mark_entry_filled(first.opportunity_id, ticker="KX1")
        tool.mark_position_closed(ticker="KX1")
        details = {**details, "visit_id": "UPPER:1005", "box_id": "new-bound-estimate"}
        same = list(tool.on_market_event(snap(ts=1010, heist=details)))[0]
        self.assertEqual(same.reason, "HEIST_EDGE_VISIT_ALREADY_FILLED")

    def test_late_penny_counterfade_waits_without_blocking_valid_17c_edge(self):
        for side in (Side.YES, Side.NO):
            tool = AlternatingMountainTool(territory_id="M1", owner_side=side)
            negative = list(tool.on_market_event(snap(age=856, yes=.002, no=.002,
                                                       mountain=mountain(side))))[0]
            self.assertEqual(negative.action, Action.WAIT)
            self.assertEqual(negative.reason, "LATE_COUNTER_PENNY_REQUIRES_CONFIRMED_TRANSFER")
            positive = list(tool.on_market_event(snap(age=856, yes=.17, no=.17,
                                                       mountain=mountain(side))))[0]
            self.assertEqual(positive.action, Action.RELAY)
            self.assertEqual(positive.size_tier, 10.0)

    def test_late_heist_penny_requires_release_but_confirmed_release_survives(self):
        heist = MarketHeistTool(territory_id="H1")
        negative = list(heist.on_market_event(snap(age=856, no=.002,
            heist={"qualified_box": True, "at_upper_edge": True, "visit_id": "UPPER:1"})))[0]
        self.assertEqual(negative.action, Action.WAIT)
        release = ReleaseWatcher(territory_id="H1", owner_side=Side.YES)
        release.update_evidence(ReleaseEvidence(candidate_side=Side.NO, boundary_break=True,
                                                directional_expansion=True, new_side_residence=True))
        positive = list(release.on_market_event(snap(age=856, no=.002)))[0]
        self.assertEqual(positive.action, Action.RELAY)
        self.assertEqual(positive.side, Side.NO)


class ToolCustodyRegressions(unittest.TestCase):
    def test_release_custody_detects_affirmative_reversal_while_raw_owner_is_neutral(self):
        rack = ToolRackController()
        rack.observe(rail_evidence(Side.NO), snap())
        release_snap = snap(ts=1010)
        release = rack.observe(rail_evidence(Side.NO, release_candidate_side=Side.YES,
            release_boundary_break=True, release_directional_expansion=True,
            release_new_side_residence=True), release_snap).intents[0]
        rack.commit_accepted_intent(release, release_snap)
        pos = position(release, release_snap)
        rack.observe(PhysicalEvidence(), snap(ts=1020))
        reversal_probe = ReleaseProbe(
            btc=90, ema9=100, ema30=105, range60=10,
            arc_side=Side.NO, arc_phase="EXPANDING", short_struct_side=Side.NO,
            medium_struct_side=Side.NO, micro_side=Side.NO,
            yes_residence_fraction=0, no_residence_fraction=1,
            yes_stack_fraction=0, no_stack_fraction=1,
            heist_lower=None, heist_upper=None, heist_edge_tolerance=None,
            mountain_extreme_btc=90, mountain_edge_age_s=0, diagnostics={},
        )
        reversal_snap = snap(ts=1030, release_probe=reversal_probe)
        reversal = rack.observe(PhysicalEvidence(), reversal_snap)
        self.assertTrue(reversal.handoff_confirmed)
        self.assertTrue(reversal.release_transition_pending)
        managed = rack.manage_position(pos, reversal_snap)[0]
        self.assertEqual(managed.action, Action.EXIT)
        next_owner = rack.observe(rail_evidence(Side.NO), snap(ts=1040))
        self.assertEqual(next_owner.owned_territory, Territory.DOWN_RAIL)

    def test_aligned_heist_release_upgrades_to_release_custody_through_neutral_flicker(self):
        rack = ToolRackController()
        first_snap = snap(heist={"qualified_box": True, "at_lower_edge": True,
                                "visit_id": "LOWER:1"})
        entry = rack.observe(PhysicalEvidence(qualified_heist=True, ema9_direction=Side.YES), first_snap).intents[0]
        rack.commit_accepted_intent(entry, first_snap)
        pos = position(entry, first_snap)
        release_snap = snap(ts=1010)
        rack.observe(PhysicalEvidence(qualified_heist=True, ema9_direction=Side.YES,
            release_candidate_side=Side.YES, release_boundary_break=True,
            release_directional_expansion=True, release_new_side_residence=True), release_snap)
        held = rack.manage_position(pos, release_snap)[0]
        self.assertEqual(held.tool, "RELEASE_WATCHER")
        self.assertEqual(held.action, Action.HOLD)
        self.assertEqual(held.metadata["floor_policy"]["arm_roi"], 1.0)
        neutral = snap(ts=1020, heist={"qualified_box": True, "at_upper_edge": True})
        rack.observe(PhysicalEvidence(qualified_heist=True), neutral)
        self.assertEqual(rack.manage_position(pos, neutral)[0].action, Action.HOLD)

    def test_old_contract_close_does_not_rearm_or_clear_new_rail_position(self):
        rack = ToolRackController()
        first_snap = snap(ticker="KX1", age=10)
        first = rack.observe(rail_evidence(Side.NO), first_snap).intents[0]
        rack.commit_accepted_intent(first, first_snap)
        new_snap = snap(ts=1900, ticker="KX2", age=10)
        second = rack.observe(rail_evidence(Side.NO), new_snap).intents[0]
        rack.commit_accepted_intent(second, new_snap)
        rack.mark_position_closed(ticker="KX1", territory_id=first.territory_id,
                                  opportunity_id=first.opportunity_id)
        held = rack.observe(rail_evidence(Side.NO), replace(new_snap, now_ts=1901))
        self.assertEqual(held.intents[0].reason, "RAIL_POSITION_ALREADY_OPEN")
        rack.mark_position_closed(ticker="KX2", territory_id=second.territory_id,
                                  opportunity_id=second.opportunity_id)
        rearm = rack.observe(rail_evidence(Side.NO), replace(new_snap, now_ts=1902))
        self.assertEqual(rearm.intents[0].action, Action.ENTER)
        self.assertNotEqual(rearm.intents[0].opportunity_id, second.opportunity_id)
        self.assertFalse(rack._filled_tools)
        self.assertFalse(rack._custody_tools)

    def test_rail_hold_survives_slowdown_rollover_then_opposing_transfer_exits(self):
        tool = RailTool(territory_id="R1", side=Side.NO, activated_at=1000)
        pos = {"ticker": "KX1", "side": "NO", "opportunity_id": "OP1"}
        for state in (snap(mountain=mountain()), snap(ticker="KX2")):
            held = list(tool.manage_position(pos, state))[0]
            self.assertEqual(held.action, Action.HOLD)
            self.assertEqual(held.metadata["floor_policy"]["arm_roi"], 1.0)
        exiting = list(tool.manage_position(pos, snap(tool_rack={"confirmed_release_side": "YES"})))[0]
        self.assertEqual(exiting.action, Action.EXIT)
        self.assertEqual(list(tool.manage_position(pos, snap()))[0].action, Action.EXIT)

    def test_mountain_holds_new_leg_until_next_mature_edge_without_perfect_curl(self):
        tool = AlternatingMountainTool(territory_id="M1", owner_side=Side.YES)
        first_snap = snap(mountain=mountain())
        entry = list(tool.on_market_event(first_snap))[0]
        pos = position(entry, first_snap)
        next_leg = {**mountain(Side.NO, mature=False), "current_arc_id": "A2"}
        self.assertEqual(list(tool.manage_position(pos, snap(mountain=next_leg)))[0].action, Action.HOLD)
        next_edge = {**next_leg, "mature_edge": True, "meaningful_retreat": True,
                     "visible_ema9_curl": False}
        out = list(tool.manage_position(pos, snap(mountain=next_edge)))[0]
        self.assertEqual(out.action, Action.EXIT)
        self.assertEqual(out.reason, "MOUNTAIN_NEXT_MATURE_PHYSICAL_EDGE")

    def test_mountain_entry_anchor_ignores_equal_and_noise_then_invalidates(self):
        tool = AlternatingMountainTool(territory_id="M1", owner_side=Side.YES)
        first_snap = snap(mountain=mountain())
        pos = position(list(tool.on_market_event(first_snap))[0], first_snap)
        for extreme in (1100, 1102):
            out = list(tool.manage_position(pos, snap(mountain=mountain(extreme=extreme))))[0]
            self.assertEqual(out.action, Action.HOLD)
        out = list(tool.manage_position(pos, snap(mountain=mountain(extreme=1104))))[0]
        self.assertEqual(out.action, Action.EXIT)
        self.assertEqual(out.reason, "MOUNTAIN_ENTRY_EDGE_PHYSICALLY_INVALIDATED")

    def test_heist_exits_at_other_edge_and_release_holds_through_slowdown(self):
        heist = MarketHeistTool(territory_id="H1")
        pos = {"ticker": "KX1", "side": "YES", "opportunity_id": "OP1"}
        held = list(heist.manage_position(pos, snap(heist={"qualified_box": True})))[0]
        self.assertEqual(held.action, Action.HOLD)
        out = list(heist.manage_position(pos, snap(heist={"qualified_box": True, "at_upper_edge": True})))[0]
        self.assertEqual(out.action, Action.EXIT)
        release = ReleaseWatcher(territory_id="H1", owner_side=Side.NO)
        held = list(release.manage_position(pos, snap(mountain=mountain())))[0]
        self.assertEqual(held.action, Action.HOLD)
        self.assertEqual(held.metadata["floor_policy"]["arm_roi"], 1.0)

    def test_mountain_position_adopts_same_side_rail_custody_then_close_rearms(self):
        rack = ToolRackController()
        first_snap = snap(mountain=mountain())
        entry = rack.observe(PhysicalEvidence(ema9_direction=Side.YES, alternating_mountain=True), first_snap).intents[0]
        rack.commit_accepted_intent(entry, first_snap)
        pos = position(entry, first_snap)
        rack.observe(PhysicalEvidence(ema9_direction=Side.NO, alternating_mountain=True),
                     snap(ts=1010, mountain=mountain(Side.NO, mature=False)))
        rail_snap = snap(ts=1020, mountain=mountain(Side.NO, mature=False))
        rack.observe(rail_evidence(Side.NO), rail_snap)
        held = rack.manage_position(pos, rail_snap)[0]
        self.assertEqual(held.tool, "RAIL")
        self.assertEqual(held.action, Action.HOLD)
        self.assertEqual(held.metadata["floor_policy"]["arm_roi"], 1.0)
        rack.mark_position_closed(ticker="KX1", territory_id=entry.territory_id,
                                  opportunity_id=entry.opportunity_id)
        out = rack.observe(rail_evidence(Side.NO), snap(ts=1021))
        self.assertEqual(out.intents[0].action, Action.ENTER)
        self.assertFalse(rack._filled_tools)
        self.assertFalse(rack._custody_tools)


if __name__ == "__main__":
    unittest.main()
