from __future__ import annotations

from dataclasses import replace
import unittest

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import _return_settlement_feasible
from strategy_core.tool_rack import ToolRackController
from strategy_core.tools.rail import RailTool
from strategy_core.tools.release import ReleaseEvidence
from strategy_core.types import Action, Lane, MarketSnapshot, Side, Territory, ToolIntent
from tests.tool_rack.test_mountain_only_reset import synthetic_terminal_snapshot
from tests.tool_rack.test_opportunity_first_commander import real_heist_snapshot


def snap(*, t=1000.0, age=300.0, yes=.15, no=.15, metadata=None, ticker="KX-A"):
    md={
        "physical_current":True,
        "geometry_last_epoch_ms":t*1000.0,
        "geometry_continuity_generation":1,
        "current_geometry":{},
        "mountain":{},
        "tp_geometry":{"target_between_ema9_ema30":False},
    }
    if metadata: md.update(metadata)
    return MarketSnapshot(now_ts=t,ticker=ticker,contract_age_s=age,
        yes_ask=yes,no_ask=no,yes_bid=max(.001,yes-.01),no_bid=max(.001,no-.01),metadata=md)


def primary(side:Side, *, family="MOUNTAIN_EDGE", max_price=.20, reason="COMMANDER_MOUNTAIN_TRUE_EDGE_RETURN"):
    return ToolIntent(tool="ONE_COMMANDER_PRIMARY",territory_id=family,lane=Lane.MAIN,
        side=side,action=Action.ENTER,opportunity_id="P",max_price=max_price,size_tier=10,
        reason=reason,source_time=1000.0,metadata={
            "commander_primary_candidate":True,"commander_candidate_family":family})


class PID1172AuthorizedRepairsTests(unittest.TestCase):
    def test_house_protected_still_allows_sub20_true_terminal_but_not_contract_leg(self):
        s=synthetic_terminal_snapshot(side=Side.YES,ask=.15)
        s=replace(s,metadata={**s.metadata,"contract_house_state":{"mode":"PROTECTED"}})
        d=OneCommander().decide([primary(Side.YES)],s)
        self.assertIs(d.action,Action.ENTER)
        leg=primary(Side.YES,family="MOUNTAIN_CONTRACT_LEG",max_price=.40,
            reason="COMMANDER_MOUNTAIN_BOUNCE_OWNS_CONTRACT")
        blocked=OneCommander().decide([leg],s)
        self.assertIs(blocked.action,Action.WAIT)
        self.assertEqual(blocked.reason,"COMMANDER_HOUSE_PROTECTED_WAIT_NEXT_CONTRACT")

    def test_mountain_late_defer_is_advisory_not_commander_veto(self):
        s=synthetic_terminal_snapshot(side=Side.YES,ask=.14,age=735)
        edge=primary(Side.YES)
        defer=ToolIntent(tool="ALTERNATING_MOUNTAIN",territory_id="M",lane=Lane.MAIN,
            side=Side.YES,action=Action.WAIT,opportunity_id=None,max_price=.20,size_tier=None,
            reason="MOUNTAIN_LATE_EDGE_DEFER_TO_NEXT_CONTRACT_CHEAP_VALUE",source_time=s.now_ts)
        d=OneCommander().decide_entry([edge,defer],s,{})
        self.assertIs(d.action,Action.ENTER)
        self.assertEqual(d.reason,"COMMANDER_ACCEPTED_TOOL_INTENT")

    def test_release_local_bounce_cannot_break_intact_mature_opposite_gap(self):
        rack=ToolRackController()
        rack._owned_territory=Territory.ALTERNATING_MOUNTAIN
        rack._owned_side=Side.NO
        md={"ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"ROLLING","current_side":"NO"}},
            "heist_cycle_context":{"pop_prep":False}}
        e=ReleaseEvidence(candidate_side=Side.YES,boundary_break=True,directional_expansion=True,
            old_owner_failed_reextension=True,new_side_residence=False)
        guarded,diag=rack._release_entry_evidence_guard(e,snap(metadata=md),latched=False)
        self.assertFalse(guarded.confirmed)
        self.assertEqual(diag["basis"],"MATURE_OLD_SIDE_GAP_REQUIRES_NEW_SIDE_RESIDENCE")
        residence=replace(e,new_side_residence=True)
        guarded2,_=rack._release_entry_evidence_guard(residence,snap(metadata=md),latched=False)
        self.assertTrue(guarded2.confirmed)

    def test_heist_pop_prep_real_break_plus_expansion_can_confirm_release(self):
        rack=ToolRackController()
        rack._owned_territory=Territory.MARKET_HEIST
        rack._owned_side=None
        md={"heist_cycle_context":{"pop_prep":True},
            "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"DEVELOPING","current_side":"YES"}}}
        e=ReleaseEvidence(candidate_side=Side.YES,boundary_break=True,directional_expansion=True,
            old_owner_failed_reextension=False,new_side_residence=False)
        guarded,diag=rack._release_entry_evidence_guard(e,snap(metadata=md),latched=False)
        self.assertTrue(guarded.confirmed)
        self.assertEqual(diag["basis"],"HEIST_POP_PREP_BOX_BREAK_DIRECTIONAL_EXPANSION_CONFIRMS_TRANSFER")

    def test_heist_blocked_inside_living_mature_directional_parent(self):
        md={
            "mountain":{"owner_side":"NO","terminal_evidence_qualified":False,
                "current_motion":{"30":{"covered":True,"owner_price_rate_btc_s":.4,
                                            "owner_ema9_rate_btc_s":.2}},
                "parent_structure":{"parent_terminal_ready":False,"extended_parent":False,
                                      "slow_rolling_parent":False}},
            "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"ROLLING","current_side":"NO"}},
            "commander_strategy":{"owned_territory":"MARKET_HEIST","active_tool":"MARKET_HEIST"},
        }
        base=real_heist_snapshot()
        s=replace(base,yes_ask=.19,no_ask=.81,metadata={**base.metadata,**md,
            "mountain":{**base.metadata["mountain"],**md["mountain"]}})
        heist=ToolIntent(tool="MARKET_HEIST",territory_id="H",lane=Lane.TACTICAL,
            side=Side.YES,action=Action.ENTER,opportunity_id="H1",max_price=.20,size_tier=10,
            reason="HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED",source_time=s.now_ts,
            metadata={"parallel_return_entry":True})
        d=OneCommander().decide([heist],s)
        self.assertIs(d.action,Action.WAIT)
        self.assertEqual(d.reason,"COMMANDER_HEIST_BLOCKED_LIVING_DIRECTIONAL_PARENT")

    def test_far_tp_single_outlier_does_not_prove_return_runway(self):
        s=snap(age=300)
        tp={"observed_target_side":"NO","required_move_to_target_btc":195.0,"remaining_seconds":600.0}
        mountain={"return_leg_reference":{"count":3,"median_amplitude_btc":62.0,
            "median_speed_btc_s":.35,"max_amplitude_btc":533.0,"max_speed_btc_s":1.5,
            "legs":[
                {"arc_id":"A","btc_amplitude_btc":60.0,"duration_s":180.0,"average_btc_speed_btc_s":.333},
                {"arc_id":"B","btc_amplitude_btc":62.0,"duration_s":180.0,"average_btc_speed_btc_s":.344},
                {"arc_id":"C","btc_amplitude_btc":533.0,"duration_s":400.0,"average_btc_speed_btc_s":1.3325},
            ]}}
        ok,evidence=_return_settlement_feasible(s,tp,mountain,Side.YES)
        self.assertFalse(ok)
        self.assertEqual(evidence["basis"],"TP_DISTANCE_SUPPORTED_ONLY_BY_SINGLE_OUTLIER_LEG")
        high={"return_leg_reference":{"count":3,"median_amplitude_btc":350.0,
            "median_speed_btc_s":1.2,"max_amplitude_btc":420.0,"max_speed_btc_s":1.4,
            "legs":[
                {"arc_id":"H1","btc_amplitude_btc":300.0,"duration_s":220.0,"average_btc_speed_btc_s":1.36},
                {"arc_id":"H2","btc_amplitude_btc":350.0,"duration_s":260.0,"average_btc_speed_btc_s":1.35},
                {"arc_id":"H3","btc_amplitude_btc":420.0,"duration_s":300.0,"average_btc_speed_btc_s":1.4},
            ]}}
        ok2,_=_return_settlement_feasible(s,tp,high,Side.YES)
        self.assertTrue(ok2)

    @staticmethod
    def rail_meta(*, dip:bool):
        geom={"btc_price":105.0,"ema9":110.0,"ema30":100.0,"arc_direction":"DOWN" if dip else "UP",
              "parent_direction":"UP"}
        mountain={"parent_structure":{"parent_side":"YES","parent_terminal_ready":False}}
        life={"gap_lifecycle":{"stage":"MATURE","current_side":"YES"}}
        return {"current_geometry":geom,"mountain":mountain,"ema9_ema30_cross_context":life}

    def test_rail_preferred_35_and_established_dip_hard_below_40(self):
        normal=RailTool(territory_id="R",side=Side.YES,activated_at=1000.0)
        wait=list(normal.on_market_event(snap(t=1400,age=400,yes=.36,no=.64,metadata=self.rail_meta(dip=False))))[0]
        self.assertIs(wait.action,Action.WAIT)
        self.assertIn("ABOVE_MAX_0.350",wait.reason)
        dip=RailTool(territory_id="R2",side=Side.YES,activated_at=1000.0)
        entered=list(dip.on_market_event(snap(t=1400,age=400,yes=.399,no=.601,metadata=self.rail_meta(dip=True))))[0]
        self.assertIs(entered.action,Action.ENTER)
        self.assertEqual(entered.reason,"RAIL_EMA9_DIP_VALUE")
        self.assertAlmostEqual(entered.max_price,.399)
        self.assertTrue(entered.metadata["rail_price_policy"]["uses_hard_tier"])
        too_high=RailTool(territory_id="R3",side=Side.YES,activated_at=1000.0)
        blocked=list(too_high.on_market_event(snap(t=1400,age=400,yes=.40,no=.60,metadata=self.rail_meta(dip=True))))[0]
        self.assertIs(blocked.action,Action.WAIT)
        self.assertIn("ABOVE_MAX_0.399",blocked.reason)


if __name__ == "__main__":
    unittest.main()
