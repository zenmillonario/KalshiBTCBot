from __future__ import annotations

import unittest

from strategy_core.commander import OneCommander
from strategy_core.mission_policy import MissionPolicy
from strategy_core.tools.heist import MarketHeistTool
from strategy_core.tools.rail import RailTool
from strategy_core.tools.release import ReleaseConfig, ReleaseEvidence, ReleaseWatcher
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


def snap(*, age=300.0, yes=.15, no=.15, t=1000.0, metadata=None):
    # Explicit synthetic numeric source/target context. These tool/mechanics
    # controls are not original recorded entry frames.
    md={"physical_current":True,"geometry_last_epoch_ms":t*1000.0,
        "geometry_continuity_generation":1,"current_geometry":{
            "epoch_ms":t*1000.0,"btc_price":120.,"ema9":119.,"ema30":118.,
            "btc_change30":10.,"btc_change60":20.,"ema9_change30":5.,"ema9_change60":10.},
        "mountain":{},"tp_geometry":{"target":110.,"remaining_seconds":900.-age,
            "observed_target_side":"YES","required_move_to_target_btc":0.,
            "contract_ownership_side":"YES","target_between_ema9_ema30":False}}
    if metadata: md.update(metadata)
    return MarketSnapshot(now_ts=t,ticker="KX-T",contract_age_s=age,yes_ask=yes,no_ask=no,
                          yes_bid=max(.001,yes-.01),no_bid=max(.001,no-.01),metadata=md)


def heist_meta(*, zone="UPPER", btc6=2.0, ema6=1.0, qualified=False, release=False,
               required=30.0, remaining=600.0, return_amp=80.0, return_duration=120.0):
    return {
        "release_in_progress": release,
        "current_geometry":{"btc_change6":btc6,"ema9_change6":ema6,"ema_gap":1.0,
                            "range180":80.0,"ema30_slope3m":1.0},
        "heist":{"qualified_box":qualified,"at_upper_edge":zone=="UPPER","at_lower_edge":zone=="LOWER",
                 "current_zone":zone,"box_id":"B1","visit_id":"U1" if zone=="UPPER" else "L1",
                 "lower":100.0,"upper":140.0,"edge_tolerance":5.0,
                 "repeatability_proof":{"observed_span_s":360.0},
                 "diagnostics":{"heist_environment":True,"parallel_emas":True,"minimum_box_range":20.0}},
        "mountain":{"owner_side":"YES" if zone in ("UPPER","INNER") else "NO",
                    "return_leg_reference":{"count":2,"basis":"TEST_RETURN",
                        "legs":[
                            {"arc_id":"R1","btc_amplitude_btc":return_amp,"duration_s":return_duration,
                             "average_btc_speed_btc_s":return_amp/return_duration},
                            {"arc_id":"R2","btc_amplitude_btc":return_amp,"duration_s":return_duration,
                             "average_btc_speed_btc_s":return_amp/return_duration},
                        ]}},
        "tp_geometry":{"observed_target_side":"YES","required_move_to_target_btc":required,
                       "remaining_seconds":remaining,"target_between_ema9_ema30":False},
        "commander_strategy":{"owned_territory":"MARKET_HEIST","owned_side":None,"active_tool":"MARKET_HEIST"},
    }


class AuthorizedReactivationTests(unittest.TestCase):
    def test_parallel_heist_arms_excursion_but_does_not_fade_extension(self):
        tool=MarketHeistTool(territory_id="H")
        first=list(tool.on_market_event(snap(metadata=heist_meta(zone="UPPER",btc6=3,ema6=1))))[0]
        self.assertIs(first.action,Action.WAIT)
        self.assertEqual(first.reason,"HEIST_PARALLEL_EXCURSION_ARMED_AWAIT_RETURN")

    def test_parallel_heist_enters_no_only_after_upper_excursion_returns(self):
        tool=MarketHeistTool(territory_id="H")
        list(tool.on_market_event(snap(t=1000,metadata=heist_meta(zone="UPPER",btc6=3,ema6=1))))
        md=heist_meta(zone="INNER",btc6=-3,ema6=-1)
        # Preserve the same parallel excursion identity while price leaves the edge.
        md["heist"]["visit_id"]=None
        intent=list(tool.on_market_event(snap(t=1001,metadata=md)))[0]
        self.assertIs(intent.action,Action.ENTER)
        self.assertIs(intent.side,Side.NO)
        self.assertEqual(intent.reason,"HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED")
        self.assertTrue(intent.metadata["parallel_return_entry"])


    def test_qualified_parallel_box_also_waits_for_return_not_first_push(self):
        tool=MarketHeistTool(territory_id="H")
        first=list(tool.on_market_event(snap(metadata=heist_meta(zone="UPPER",btc6=3,ema6=1,qualified=True))))[0]
        self.assertIs(first.action,Action.WAIT)
        self.assertEqual(first.reason,"HEIST_PARALLEL_EXCURSION_ARMED_AWAIT_RETURN")
        md=heist_meta(zone="INNER",btc6=-2,ema6=-.5,qualified=True)
        md["heist"]["visit_id"]=None
        second=list(tool.on_market_event(snap(t=1001,metadata=md)))[0]
        self.assertIs(second.action,Action.ENTER)
        self.assertEqual(second.reason,"HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED")


    def test_unproven_parallel_return_remains_advice_until_repeated_walls_exist(self):
        tool=MarketHeistTool(territory_id="H")
        first_md=heist_meta(zone="UPPER",btc6=3,ema6=1)
        first_md["current_geometry"]["epoch_ms"]=1000.0*1000.0
        list(tool.on_market_event(snap(t=1000,metadata=first_md)))

        md=heist_meta(zone="INNER",btc6=-3,ema6=-1)
        md["heist"]["visit_id"]=None
        md["current_geometry"]["epoch_ms"]=1001.0*1000.0
        md["tp_geometry"]["target"]=120.0
        md["mission_context"]={
            "current":True,"source_ms":1001.0*1000.0,"continuity_generation":1,
            "parent":{"id":"P1","side":"YES","status":"ACTIVE","supported":True,
                      "invalidated":False,"source_ms":1001.0*1000.0,
                      "known_ms":999000.0,"continuity_generation":1},
            "local":{"arc_id":"A1"},
            "candidates":{},
            "contract":{"ticker":"KX-T","target":120.0,"history_status":"READY",
                        "reference_window":{"completed_prior_contracts":2},
                        "thesis_side":"UNKNOWN","reason":"fixture"},
        }
        s2=snap(t=1001,metadata=md)
        raw=list(tool.on_market_event(s2))[0]
        self.assertIs(raw.action,Action.ENTER)
        reviewed=MissionPolicy().review(raw,s2)
        mission=reviewed.metadata["mission"]
        self.assertTrue(mission["parallel_heist_return"])
        self.assertTrue(mission["neutral_heist_repeatable"])
        self.assertEqual(mission["classification"],"PARALLEL_HEIST_RETURN")
        decision=OneCommander().decide([reviewed],s2)
        self.assertIs(decision.action,Action.WAIT)
        self.assertEqual(decision.reason,"OPPORTUNITY_HEIST_REPEATED_BILATERAL_WALLS_REQUIRED")

    def test_parallel_heist_release_cancels_return(self):
        tool=MarketHeistTool(territory_id="H")
        list(tool.on_market_event(snap(metadata=heist_meta(zone="UPPER",btc6=3,ema6=1))))
        md=heist_meta(zone="INNER",btc6=-3,ema6=-1,release=True)
        intent=list(tool.on_market_event(snap(t=1001,metadata=md)))[0]
        self.assertIs(intent.action,Action.WAIT)
        self.assertEqual(intent.reason,"HEIST_RELEASE_RUNWAY_ACTIVE_STOP_FADING_BOX")

    def test_late_heist_fast_regime_can_enter(self):
        tool=MarketHeistTool(territory_id="H")
        list(tool.on_market_event(snap(age=720,t=1000,metadata=heist_meta(zone="UPPER",btc6=3,ema6=1,
                                                                          required=50,remaining=180,
                                                                          return_amp=100,return_duration=60))))
        md=heist_meta(zone="INNER",btc6=-3,ema6=-1,required=50,remaining=180,
                      return_amp=100,return_duration=60)
        md["heist"]["visit_id"]=None
        intent=list(tool.on_market_event(snap(age=720,t=1001,metadata=md)))[0]
        self.assertIs(intent.action,Action.ENTER)
        self.assertIs(intent.side,Side.NO)
        self.assertEqual(intent.metadata["late_dynamic_runway"]["basis"],"PROVEN_RETURN_LEG_CAN_REACH_TP")

    def test_late_heist_quiet_regime_is_blocked_by_dynamic_runway(self):
        tool=MarketHeistTool(territory_id="H")
        list(tool.on_market_event(snap(age=720,t=1000,metadata=heist_meta(zone="UPPER",btc6=3,ema6=1,
                                                                          required=50,remaining=180,
                                                                          return_amp=20,return_duration=120))))
        md=heist_meta(zone="INNER",btc6=-3,ema6=-1,required=50,remaining=180,
                      return_amp=20,return_duration=120)
        md["heist"]["visit_id"]=None
        intent=list(tool.on_market_event(snap(age=720,t=1001,metadata=md)))[0]
        self.assertIs(intent.action,Action.WAIT)
        self.assertEqual(intent.reason,"HEIST_LATE_DYNAMIC_TP_RUNWAY_BLOCK")

    def _rail_snapshot(self, *, amp, duration, required=200.0, remaining=180.0):
        rows=[{"leg_id":"Y1","side":"YES","btc_amplitude":amp,"duration_s":duration},
              {"leg_id":"Y2","side":"YES","btc_amplitude":amp,"duration_s":duration}]
        return snap(age=720,yes=.09,no=.91,metadata={
            "current_geometry":{"parent_direction":"UP","range60":100.0,"btc_change6":2.0,"ema9_change6":1.0},
            "mountain":{"owner_side":"YES"},
            "leg_echo":{"side":"YES","completed_comparable_legs":rows},
            "tp_geometry":{"observed_target_side":"NO","required_move_to_target_btc":required,
                           "remaining_seconds":remaining,"target_between_ema9_ema30":False},
            "commander_strategy":{"owned_territory":"UP_RAIL","owned_side":"YES","active_tool":"RAIL"},
        })

    def test_late_rail_fast_regime_can_enter(self):
        tool=RailTool(territory_id="R",side=Side.YES,activated_at=1000.0)
        intent=list(tool.on_market_event(self._rail_snapshot(amp=300,duration=120)))[0]
        self.assertIs(intent.action,Action.ENTER)
        self.assertEqual(intent.reason,"RAIL_MAIN_VALUE")
        self.assertEqual(intent.metadata["late_dynamic_runway"]["basis"],"PROVEN_RETURN_LEG_CAN_REACH_TP")
        # Reactivation must not silently alter Rail custody policy.
        self.assertEqual(intent.metadata["floor_policy"]["arm_roi"],.5)
        self.assertEqual(intent.metadata["floor_policy"]["trail_fraction"],.10)

    def test_late_rail_quiet_regime_is_blocked(self):
        tool=RailTool(territory_id="R",side=Side.YES,activated_at=1000.0)
        intent=list(tool.on_market_event(self._rail_snapshot(amp=100,duration=180)))[0]
        self.assertIs(intent.action,Action.WAIT)
        self.assertEqual(intent.reason,"RAIL_LATE_DYNAMIC_TP_RUNWAY_BLOCK")

    def test_confirmed_release_is_reactivated_but_first_slowdown_is_not(self):
        watcher=ReleaseWatcher(territory_id="REL",owner_side=Side.NO,
                               config=ReleaseConfig(soft_max_price=.20))
        watcher.update_evidence(ReleaseEvidence(candidate_side=Side.YES,boundary_break=True,
            directional_expansion=True,new_side_residence=True),
            entry_evidence=ReleaseEvidence(candidate_side=Side.YES,boundary_break=True,
                directional_expansion=True,new_side_residence=True),
            entry_diagnostics={"fresh_transfer":True,"observed_at":1000.0,
                "qualified":True,"candidate_side":"YES","boundary_break":True,
                "directional_expansion":True,"new_side_residence":True})
        s=snap(yes=.15,no=.85,metadata={"commander_strategy":{"owned_territory":"RELEASE_TRANSITION",
            "owned_side":"YES","active_tool":"RELEASE_WATCHER","handoff_confirmed":True},
            "release_in_progress":True,"release_candidate_side":"YES","mountain":{"owner_side":"YES"}})
        intent=list(watcher.on_market_event(s))[0]
        d=OneCommander().decide([intent],s)
        self.assertIs(d.action,Action.RELAY)
        self.assertEqual(intent.reason,"RELEASE_CONFIRMED_LEVIATHAN_HANDOFF")
        self.assertEqual(intent.metadata["floor_policy"]["trail_fraction"],.10)

        waiting=ReleaseWatcher(territory_id="REL2",owner_side=Side.NO)
        waiting.update_evidence(ReleaseEvidence(candidate_side=Side.YES,first_slowdown_only=True))
        w=list(waiting.on_market_event(s))[0]
        self.assertIs(w.action,Action.WAIT)
        self.assertEqual(w.reason,"RELEASE_FIRST_SLOWDOWN_IS_WATCH_NOT_HANDOFF")

    def test_commander_blocks_unapproved_specialist_and_legacy_mountain_intent(self):
        s=snap(metadata={"commander_strategy":{"owned_territory":"UNKNOWN","owned_side":None,"active_tool":None}})
        fade=ToolIntent(tool="TACTICAL_FADE",territory_id="F",lane=Lane.TACTICAL,side=Side.YES,
            action=Action.ENTER,opportunity_id="F",max_price=.2,size_tier=10,reason="F",source_time=1000)
        d=OneCommander().decide([fade],s)
        self.assertIs(d.action,Action.WAIT)
        self.assertEqual(d.reason,"COMMANDER_UNAUTHORIZED_SPECIALIST_ENTRY_PAUSED")
        old_mountain=ToolIntent(tool="ALTERNATING_MOUNTAIN",territory_id="M",lane=Lane.MAIN,side=Side.YES,
            action=Action.ENTER,opportunity_id="M",max_price=.2,size_tier=10,
            reason="MOUNTAIN_ARMED_EDGE_SUB20_VALUE_ENTRY",source_time=1000,
            metadata={"armed_edge_value":{"edge_id":"E"}})
        d2=OneCommander().decide([old_mountain],s)
        self.assertIs(d2.action,Action.WAIT)
        self.assertEqual(d2.reason,"COMMANDER_LEGACY_MOUNTAIN_SPECIALIST_ENTRY_PAUSED_USE_PRIMARY")


if __name__ == "__main__":
    unittest.main()
