from __future__ import annotations

import unittest
from dataclasses import replace

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import historical_extreme_release_candidates, physical_entry_candidates
from strategy_core.detectors.heist_geometry import HeistGeometryConfig, detect_heist_geometry
from strategy_core.paper_execution import PaperPosition
from strategy_core.paper_runtime import ToolRackPaperEngine
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from tests.tool_rack.test_mountain_only_reset import synthetic_terminal_snapshot
from tests.tool_rack.test_opportunity_first_commander import parent_snapshot


def snap(*, t=1000.0, yes=.08, no=.92, metadata=None):
    md={"physical_current":True,"geometry_last_epoch_ms":t*1000.0,
        "geometry_continuity_generation":1,"current_geometry":{},"mountain":{},
        "tp_geometry":{"target_between_ema9_ema30":False},
        "commander_strategy":{}}
    if metadata: md.update(metadata)
    return MarketSnapshot(now_ts=t,ticker="KX-PID252",contract_age_s=300.0,
        yes_ask=yes,no_ask=no,yes_bid=max(.001,yes-.01),no_bid=max(.001,no-.01),yes_sell_allowed=True,no_sell_allowed=True,metadata=md)


class PID252TacticalPromotionTests(unittest.TestCase):
    def test_recent_level_match_sub20_return_bypasses_tool_wait_stack(self):
        md={
            "historical_extreme_release":{
                "qualified":False,
                "recent_level_match":{"side":"YES","anchor":76400.0,"anchor_time":280.0,
                                      "age_s":720.0,"distance_btc":3.0},
            },
            "current_geometry":{"epoch_ms":1000000.0,"btc_change6":4.0,"btc_change9":6.0,
                                "ema9_change6":1.0},
            "mountain":{"owner_side":"NO","failed_reextension":False,"stall":False,
                        "hesitation":False,"meaningful_retreat":False,"strong_active_release":False},
            "commander_strategy":{"active_overlays":["MARKET_HEIST"]},
        }
        # Numeric synthetic terminal proof is independent of the advisory
        # overlay and old level label; the label alone cannot authorize entry.
        base=synthetic_terminal_snapshot(side=Side.YES,ask=.20,ticker="KX-PID252")
        md["historical_extreme_release"]["recent_level_match"]["anchor"]=base.metadata["current_geometry"]["btc_price"]-3.
        s=replace(base,metadata={**base.metadata,
            "historical_extreme_release":md["historical_extreme_release"],
            "commander_strategy":{"active_overlays":["MARKET_HEIST"]}})
        intents=physical_entry_candidates(s)
        self.assertEqual(len(intents),1)
        self.assertEqual(intents[0].reason,"COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN")
        self.assertIs(intents[0].side,Side.YES)
        d=OneCommander().decide_entry(list(intents),s,{})
        self.assertIs(d.action,Action.ENTER)

    def test_recent_level_match_above_20_does_not_force_entry(self):
        md={
            "historical_extreme_release":{
                "qualified":False,
                "recent_level_match":{"side":"YES","anchor":76400.0,"anchor_time":280.0,
                                      "age_s":720.0,"distance_btc":3.0},
            },
            "current_geometry":{"epoch_ms":1000000.0,"btc_change6":4.0,"btc_change9":6.0,
                                "ema9_change6":1.0},
            "mountain":{"owner_side":"NO","strong_active_release":False},
            "commander_strategy":{"active_overlays":["MARKET_HEIST"]},
        }
        self.assertEqual(physical_entry_candidates(snap(yes=.21,no=.79,metadata=md)),())

    def test_historical_extreme_release_prep_requires_reversal_and_cheap_value(self):
        md={
            "historical_extreme_release":{"qualified":True,"side":"YES","prior_low_anchor":100.0,
                                          "prior_high_anchor":180.0,"prior_low_hits":3},
            "current_geometry":{"epoch_ms":1000000.0,"btc_change6":4.0,"btc_change9":6.0,
                                "ema9_change6":1.0},
            "mountain":{"owner_side":"NO","failed_reextension":True,"strong_active_release":False},
        }
        intents=historical_extreme_release_candidates(snap(yes=.07,no=.93,metadata=md))
        self.assertEqual(len(intents),1)
        self.assertIs(intents[0].side,Side.YES)
        self.assertEqual(intents[0].size_tier,15.0)
        self.assertEqual(intents[0].max_price,.15)
        base=synthetic_terminal_snapshot(side=Side.YES,ask=.07,ticker="KX-PID252")
        supported=replace(base,metadata={**base.metadata,
            "historical_extreme_release":{**md["historical_extreme_release"],
                "prior_low_anchor":75994.,"prior_high_anchor":76080.}})
        self.assertIs(OneCommander().decide(intents,supported).action,Action.ENTER)
        md["current_geometry"]["btc_change9"]=-2.0
        self.assertEqual(historical_extreme_release_candidates(snap(yes=.07,no=.93,metadata=md)),[])

    def test_heist_seed_promotes_to_same_side_release_custody(self):
        position={"position_id":"P1","ticker":"KX-PID252","side":Side.YES,"entry_price":.10,
                  "entry_time":900.0,"close_ts":1900.0,"tool":"MARKET_HEIST","territory_id":"H",
                  "opportunity_id":"H:1","lane":Lane.TACTICAL,"custody_state":"NORMAL",
                  "entry_metadata":{}}
        s=snap(t=1000,yes=.40,no=.60,metadata={"release_in_progress":True,
            "release_candidate_side":"YES","commander_strategy":{"owned_side":"YES"},
            "mountain":{"owner_side":"YES"}})
        d=OneCommander().decide_position((),s,position)
        self.assertIs(d.action,Action.HOLD)
        self.assertEqual(d.reason,"COMMANDER_HEIST_SEED_PROMOTED_TO_RELEASE_CUSTODY")
        self.assertEqual(d.intent.lane,Lane.MAIN)

    def test_leg_aligned_winner_delays_first_floor_to_200pct_until_stall(self):
        p=PaperPosition("P","KX-PID252",Side.NO,10,.29,2.9,0.0,900.0,1900.0,
            "ONE_COMMANDER_PRIMARY","MOUNTAIN_CONTRACT_LEG","O",Lane.MAIN,"Q","R",
            {"floor_policy":{"arm_roi":1.0,"trail_fraction":.05,"min_age_s":0.0,
                             "immediate_arm_roi":1.0,"first_arm_from_current_bid":True,
                             "roi_trail_tiers":[[1.5,.03]]}},None,None,None,False,None,
            position_role="PRIMARY")
        live=snap(t=1000,yes=.40,no=.60,metadata={"commander_strategy":{"owned_side":"NO"},
            "mountain":{"owner_side":"NO","terminal_evidence_qualified":False,"stall":False,"hesitation":False}})
        pol=ToolRackPaperEngine._floor_policy((),p,live)
        self.assertEqual(pol.arm_roi,2.0)
        self.assertEqual(pol.immediate_arm_roi,2.0)
        stalled=snap(t=1001,yes=.40,no=.60,metadata={"commander_strategy":{"owned_side":"NO"},
            "mountain":{"owner_side":"NO","terminal_evidence_qualified":False,"stall":True,"hesitation":False}})
        pol2=ToolRackPaperEngine._floor_policy((),p,stalled)
        self.assertEqual(pol2.arm_roi,1.0)

    def test_primary_position_opposite_living_ema9_parent_exits(self):
        position={"position_id":"P-WRONG","ticker":"KX-PID252","side":Side.YES,"entry_price":.20,
                  "entry_time":900.0,"close_ts":1900.0,"tool":"ONE_COMMANDER_PRIMARY",
                  "territory_id":"MOUNTAIN_CONTRACT_LEG","opportunity_id":"WRONG","lane":Lane.MAIN,
                  "custody_state":"NORMAL","position_role":"PRIMARY","entry_metadata":{"position_role":"PRIMARY"}}
        s=snap(t=1000,yes=.15,no=.85,metadata={
            "mission_context":{"parent":{"id":"P-DOWN","side":"NO","status":"ACTIVE","supported":True}},
            "commander_strategy":{"owned_side":"YES"},
            "mountain":{"owner_side":"YES","parent_structure":{"parent_side":"NO","parent_terminal_ready":False}}})
        d=OneCommander().decide_position((),s,position)
        self.assertIs(d.action,Action.EXIT)
        self.assertEqual(d.intent.reason,"COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT")


    def test_terminal_return_seed_is_not_immediately_killed_by_old_parent(self):
        position={"position_id":"P-RETURN","ticker":"KX-PID252","side":Side.YES,"entry_price":.19,
                  "entry_time":999.0,"close_ts":1900.0,"tool":"ONE_COMMANDER_PRIMARY",
                  "territory_id":"MOUNTAIN_EDGE","opportunity_id":"RETURN","lane":Lane.MAIN,
                  "custody_state":"NORMAL","position_role":"PRIMARY",
                  "entry_metadata":{"position_role":"PRIMARY","commander_candidate_family":"MOUNTAIN_EDGE",
                                    "commander_physical_evidence":{"entry_location":"FRESH_EXTENDED_MOUNTAIN_EXTREME"}}}
        s=snap(t=1000,yes=.18,no=.82,metadata={
            "mission_context":{"parent":{"id":"P-DOWN","side":"NO","status":"ACTIVE","supported":True}},
            "commander_strategy":{"owned_side":"NO"},
            "mountain":{"owner_side":"NO","parent_structure":{"parent_side":"NO","parent_terminal_ready":True},
                        "terminal_evidence_qualified":True,"stall":True,"hesitation":True}})
        d=OneCommander().decide_position((),s,position)
        self.assertIsNot(d.action,Action.EXIT)
        if d.intent is not None:
            self.assertNotEqual(d.intent.reason,"COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT")

    def test_floor_alignment_uses_physical_parent_before_stale_tool_owner(self):
        p=PaperPosition("P2","KX-PID252",Side.NO,10,.29,2.9,0.0,900.0,1900.0,
            "ONE_COMMANDER_PRIMARY","MOUNTAIN_CONTRACT_LEG","O2",Lane.MAIN,"Q","R",
            {"floor_policy":{"arm_roi":1.0,"trail_fraction":.05,"min_age_s":0.0,
                             "immediate_arm_roi":1.0,"first_arm_from_current_bid":True,
                             "roi_trail_tiers":[[1.5,.03]]}},None,None,None,False,None,
            position_role="PRIMARY")
        live=snap(t=1000,yes=.40,no=.60,metadata={
            "mission_context":{"parent":{"id":"P-DOWN","side":"NO","status":"ACTIVE","supported":True}},
            "commander_strategy":{"owned_side":"YES"},
            "mountain":{"owner_side":"YES","parent_structure":{"parent_side":"NO","parent_terminal_ready":False},
                        "terminal_evidence_qualified":False,"stall":False,"hesitation":False}})
        pol=ToolRackPaperEngine._floor_policy((),p,live)
        self.assertEqual(pol.arm_roi,2.0)
        self.assertEqual(pol.immediate_arm_roi,2.0)

    def test_opposite_inventory_is_exit_pending_not_strategy_owner(self):
        # A real synthetic measured rejoin is required before testing the
        # independent opposite-inventory rule. A family label is insufficient.
        commander=OneCommander()
        for t,price in ((1000.,120.),(1010.,115.)):
            commander.decide_entry((),parent_snapshot(t=t,price=price,ask=.30),{})
        s=parent_snapshot(t=1020.,price=118.,ask=.30)
        intents=commander.physical_entry_candidates(s)
        intent=next(i for i in intents if i.reason=="COMMANDER_OPPORTUNITY_MAIN_EMA9_VALUE_REJOIN")
        self.assertEqual(intent.metadata["commander_opportunity"]["qualified"],True)
        held={"P":{"position_id":"P","ticker":s.ticker,"side":"NO","custody_state":"NORMAL"}}
        d=commander.decide_entry((intent,),s,held)
        self.assertIs(d.action,Action.WAIT)
        self.assertEqual(d.reason,"CURRENT_CONTRACT_OPPOSITE_INVENTORY_EXIT_PENDING_CORRECTIVE_HANDOFF")

    def test_inherited_rollover_continuation_has_transition_custody_against_old_parent(self):
        position={"position_id":"P-ROLL","ticker":"KX-PID252","side":Side.YES,"entry_price":.51,
                  "entry_time":990.0,"close_ts":1900.0,"tool":"ONE_COMMANDER_PRIMARY",
                  "territory_id":"MOUNTAIN_CONTRACT_LEG","opportunity_id":"ROLL","lane":Lane.MAIN,
                  "custody_state":"NORMAL","position_role":"PRIMARY",
                  "entry_reason":"COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION",
                  "entry_metadata":{"position_role":"PRIMARY","commander_candidate_family":"MOUNTAIN_CONTRACT_LEG"}}
        s=snap(t=1000,yes=.45,no=.55,metadata={
            "mission_context":{"parent":{"id":"P-DOWN","side":"NO","status":"ACTIVE","supported":True}},
            "mountain":{"owner_side":"NO","parent_structure":{"parent_side":"NO","parent_terminal_ready":False}}})
        d=OneCommander().decide_position((),s,position)
        self.assertFalse(d.action is Action.EXIT and d.intent and
                         d.intent.reason=="COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT")

    def test_heist_return_has_transition_custody_even_if_primary_slot(self):
        position={"position_id":"P-H","ticker":"KX-PID252","side":Side.YES,"entry_price":.24,
                  "entry_time":990.0,"close_ts":1900.0,"tool":"MARKET_HEIST",
                  "territory_id":"H","opportunity_id":"H","lane":Lane.TACTICAL,
                  "custody_state":"NORMAL","position_role":"PRIMARY",
                  "entry_reason":"HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED",
                  "entry_metadata":{"position_role":"PRIMARY"}}
        s=snap(t=1000,yes=.27,no=.73,metadata={
            "mission_context":{"parent":{"id":"P-DOWN","side":"NO","status":"ACTIVE","supported":True}},
            "mountain":{"owner_side":"NO","parent_structure":{"parent_side":"NO","parent_terminal_ready":False}}})
        d=OneCommander().decide_position((),s,position)
        self.assertFalse(d.action is Action.EXIT and d.intent and
                         d.intent.reason=="COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT")

    def test_unpromoted_heist_renter_cannot_drift_to_settlement(self):
        position={"position_id":"P-T","ticker":"KX-PID252","side":Side.NO,"entry_price":.26,
                  "entry_time":700.0,"close_ts":1100.0,"tool":"MARKET_HEIST",
                  "territory_id":"H","opportunity_id":"T","lane":Lane.TACTICAL,
                  "custody_state":"NORMAL","position_role":"TACTICAL",
                  "entry_reason":"HEIST_OUTER_EDGE_TACTICAL_RENTER",
                  "entry_metadata":{"position_role":"TACTICAL"}}
        s=snap(t=1000,yes=.70,no=.30,metadata={"mountain":{"owner_side":"YES"}})
        d=OneCommander().decide_position((),s,position)
        self.assertIs(d.action,Action.EXIT)
        self.assertEqual(d.intent.reason,"TACTICAL_MAX_HOLD_EXIT")

    def test_historical_extreme_scout_arms_protection_at_60pct(self):
        md={
            "historical_extreme_release":{"qualified":True,"side":"YES","prior_low_anchor":100.0,
                                          "prior_high_anchor":180.0,"prior_low_hits":3},
            "current_geometry":{"epoch_ms":1000000.0,"btc_change6":4.0,"btc_change9":6.0,
                                "ema9_change6":1.0},
            "mountain":{"owner_side":"NO","failed_reextension":True,"strong_active_release":False},
        }
        intent=historical_extreme_release_candidates(snap(yes=.07,no=.93,metadata=md))[0]
        fp=intent.metadata["floor_policy"]
        self.assertEqual(fp["arm_roi"],.60)
        self.assertEqual(fp["immediate_arm_roi"],.60)


    def test_wide_heist_qualifies_after_long_bilateral_revisitation(self):
        cfg=HeistGeometryConfig(minimum_lower_visits=2,minimum_upper_visits=2,
            minimum_center_traversals=2,min_observed_span_s=150.0,min_box_range_dollars=20.0,
            max_ema9_drift_fraction=.65,max_ema30_drift_fraction=.45,
            compression_drift_fraction=.30,parallel_drift_difference_fraction=.18)
        # One full lower/upper visit, repeated center traversals over >9 minutes.
        pattern=[100,140,180,145,135,150,142,138,152,145,100]
        rows=[]
        for i in range(61):
            price=pattern[min(len(pattern)-1,int(i/6))]
            rows.append({"epoch_ms":i*10000.0,"btc_price":price,
                         "ema9":140.0 + .02*i,"ema30":139.0 + .015*i,
                         "arc_prominence_threshold":10.0,"connection_epoch":1})
        d=detect_heist_geometry(rows,cfg)
        self.assertTrue(d.qualified_box)
        self.assertTrue(d.diagnostics["wide_heist_qualified"] or d.diagnostics["classic_qualified"])


if __name__ == '__main__':
    unittest.main()
