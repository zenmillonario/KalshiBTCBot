from __future__ import annotations

import unittest

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import quote_wave_scalp_candidates, edge_heist_candidates
from strategy_core.detectors.rail_geometry import RailGeometryConfig, detect_rail_geometry
from strategy_core.tools.heist import HeistConfig, MarketHeistTool
from strategy_core.types import Action, MarketSnapshot, Side


def snap(*, t=1000.0, yes=.10, no=.90, metadata=None):
    # Synthetic source clock/target; quote-cycle metadata is still only an
    # adviser proposal and supplies no repeated physical-wall proof.
    md={"physical_current":True,"geometry_last_epoch_ms":t*1000.0,
        "geometry_continuity_generation":1,"current_geometry":{"epoch_ms":t*1000.0},"mountain":{},
        "tp_geometry":{"target":120.,"remaining_seconds":600.,"target_between_ema9_ema30":False}}
    if metadata: md.update(metadata)
    return MarketSnapshot(now_ts=t,ticker="KX-Q",contract_age_s=300.0,
        yes_ask=yes,no_ask=no,yes_bid=max(.001,yes-.01),no_bid=max(.001,no-.01),metadata=md)


def heist_meta(*, upper=True, btc6=-2.0, ema6=-1.0):
    return {
        "current_geometry":{"btc_change6":btc6,"ema9_change6":ema6,"ema_gap":1.0,
                            "range180":100.0,"ema30_slope3m":1.0,"epoch_ms":1000000.0},
        "heist":{"qualified_box":True,"at_upper_edge":upper,"at_lower_edge":not upper,
                 "current_zone":"UPPER" if upper else "LOWER","box_id":"B","visit_id":"V",
                 "lower":100.0,"upper":180.0,"edge_tolerance":8.0,"lean_side":None,
                 "repeatability_proof":{"observed_span_s":900.0},
                 "diagnostics":{"heist_environment":True,"parallel_emas":False,
                                "minimum_box_range":20.0}},
        "mountain":{"owner_side":"YES" if upper else "NO"},
        "commander_strategy":{"owned_territory":"MARKET_HEIST","active_tool":"MARKET_HEIST"},
    }


class WideHeistRailQuoteWaveTests(unittest.TestCase):
    def test_wide_heist_32c_requires_confirmed_return_and_then_enters(self):
        tool=MarketHeistTool(territory_id="H", config=HeistConfig(wide_normal_max_price=.30,
            wide_exceptional_max_price=.35))
        blocked=list(tool.on_market_event(snap(no=.32,yes=.68,metadata=heist_meta(upper=True,btc6=2,ema6=1))))[0]
        self.assertIs(blocked.action, Action.WAIT)
        self.assertEqual(blocked.reason, "HEIST_31_35_REQUIRES_CONFIRMED_OUTER_RETURN")
        entered=list(tool.on_market_event(snap(t=1001,no=.32,yes=.68,metadata=heist_meta(upper=True,btc6=-2,ema6=-1))))[0]
        self.assertIs(entered.action, Action.ENTER)
        self.assertIs(entered.side, Side.NO)

    def test_wide_heist_above_35_waits(self):
        tool=MarketHeistTool(territory_id="H", config=HeistConfig(wide_normal_max_price=.30,
            wide_exceptional_max_price=.35))
        intent=list(tool.on_market_event(snap(no=.36,yes=.64,metadata=heist_meta(upper=True,btc6=-2,ema6=-1))))[0]
        self.assertIs(intent.action, Action.WAIT)
        self.assertEqual(intent.reason, "HEIST_EDGE_PRICE_ABOVE_EXCEPTIONAL_VALUE")

    def test_quote_wave_revisits_do_not_replace_physical_terminal_or_repeated_walls(self):
        series=[
            {"time":950.0,"ask":.06,"bid":.05},
            {"time":960.0,"ask":.16,"bid":.14},
            {"time":975.0,"ask":.07,"bid":.06},
            {"time":985.0,"ask":.18,"bid":.16},
            {"time":999.0,"ask":.07,"bid":.06},
        ]
        md=heist_meta(upper=True)
        md["quote_wave"]={"sides":{"NO":{"available":True,"low_ask":.06,"high_ask":.18,
                                               "series":series},
                                  "YES":{"available":False}}}
        s=snap(t=1000,no=.07,yes=.93,metadata=md)
        intents=quote_wave_scalp_candidates(s)
        self.assertEqual(len(intents),1)
        q=intents[0]
        self.assertIs(q.side, Side.NO)
        self.assertEqual(q.max_price, .08)
        self.assertEqual(q.size_tier, 10.0)
        self.assertEqual(q.metadata["floor_policy"]["arm_roi"], .60)
        d=OneCommander().decide([q],s)
        self.assertIs(d.action, Action.WAIT)
        self.assertEqual(d.reason,"OPPORTUNITY_MOUNTAIN_PARENT_TERMINAL_PROOF_REQUIRED")

    def test_quote_wave_scalp_does_not_create_trade_without_edge(self):
        md={"quote_wave":{"sides":{"NO":{"available":True,"low_ask":.05,"high_ask":.20,
            "series":[{"time":950,"ask":.05},{"time":960,"ask":.15},{"time":999,"ask":.05}]}}}}
        self.assertEqual(quote_wave_scalp_candidates(snap(t=1000,no=.05,yes=.95,metadata=md)), [])


    def test_35pct_quote_cycle_cannot_make_inactive_mountain_edge_executable(self):
        md={
            "mountain":{"owner_side":"NO","mature_edge":True,"edge_window_active":False,
                        "strong_active_release":False,"current_arc_id":"EDGE1",
                        "primary_collection_evidence":{}},
            "quote_wave":{"sides":{"YES":{"available":True,"low_ask":.10,"high_ask":.20,
                "series":[{"time":950,"ask":.10},{"time":960,"ask":.20},
                          {"time":999,"ask":.11},{"time":999.5,"ask":.10}]}}},
            "commander_strategy":{"owned_territory":"ALTERNATING_MOUNTAIN","owned_side":"NO"},
        }
        s=snap(t=1000,yes=.10,no=.90,metadata=md)
        intents=edge_heist_candidates(s)
        self.assertEqual(len(intents),1)
        e=intents[0]
        self.assertIs(e.side, Side.YES)
        self.assertEqual(e.metadata["commander_candidate_family"], "EDGE_HEIST")
        self.assertEqual(e.size_tier,10.0)
        decision=OneCommander().decide([e],s)
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason,"OPPORTUNITY_MOUNTAIN_PARENT_TERMINAL_PROOF_REQUIRED")

    def test_edge_heist_requires_real_quote_cycle_not_first_cheap_print(self):
        md={
            "mountain":{"owner_side":"YES","mature_edge":True,"strong_active_release":False,
                        "current_arc_id":"EDGE2","primary_collection_evidence":{}},
            "quote_wave":{"sides":{"NO":{"available":True,"low_ask":.10,"high_ask":.18,
                "series":[{"time":980,"ask":.10},{"time":990,"ask":.11},
                          {"time":995,"ask":.12},{"time":999,"ask":.10}]}}},
        }
        self.assertEqual(edge_heist_candidates(snap(t=1000,no=.10,yes=.90,metadata=md)),[])

    def test_edge_heist_caps_after_two_cycles(self):
        series=[{"time":940,"ask":.10},{"time":950,"ask":.20},{"time":960,"ask":.10},
                {"time":970,"ask":.20},{"time":980,"ask":.10},{"time":990,"ask":.20},
                {"time":999,"ask":.10}]
        md={"mountain":{"owner_side":"YES","mature_edge":True,"strong_active_release":False,
                           "current_arc_id":"EDGE3","primary_collection_evidence":{}},
            "quote_wave":{"sides":{"NO":{"available":True,"low_ask":.10,"high_ask":.20,"series":series}}}}
        self.assertEqual(edge_heist_candidates(snap(t=1000,no=.10,yes=.90,metadata=md)),[])

    def test_rail_requires_two_same_direction_arcs_and_long_persistence(self):
        rows=[]
        for i in range(31):
            rows.append({"epoch_ms":i*60*1000,"btc_price":100+i,"ema9":99+i,"ema30":98+i,
                         "struct_slope3m":1.0,"struct_slope6m":1.0,"struct_slope9m":1.0,
                         "ema30_slope3m":.5,"arc_id":"A1","arc_direction":"UP","arc_amplitude":100+i})
        cfg=RailGeometryConfig(current_residence_window_s=900,persistence_windows_s=(1800,1500,1200,900),
            qualification_min_persistence_s=900,min_same_direction_arcs=2,chapter_history_window_s=3600,
            opposite_arc_break_fraction=.45)
        one=detect_rail_geometry(rows,cfg)
        self.assertFalse(one.qualified_rail)
        for row in rows[16:]:
            row["arc_id"]="A2"
        two=detect_rail_geometry(rows,cfg)
        self.assertTrue(two.qualified_rail)
        self.assertGreaterEqual(two.diagnostics["same_direction_arc_count"],2)


if __name__ == "__main__":
    unittest.main()

class TestFastExtendedMountainReturn(unittest.TestCase):
    def _fast_snap(self, owner="NO", yes=.12, no=.88, overlay=True, extreme_age_s=10, extended=True):
        now=1000.0
        side_owner=owner
        md={
            "physical_current":True,
            "mountain":{
                "qualified":True,"qualified_alternating_mountain":True,"owner_side":side_owner,"current_arc_id":"FAST-EXTREME",
                "source_ms":now*1000,"edge_extreme_ms":now*1000-extreme_age_s*1000,
                "spent_edge":False,"strong_active_release":False,
                "full_leg_scale_evidence":{"qualified":extended},
                "diagnostics":{"current_age_s":500.0},
            },
            # Entry-time opposite-color / short EMA9 curl evidence. Cheapness
            # plus a fresh extreme alone is not sufficient after PID8552.
            "current_geometry":{
                "btc_change6": 3.0 if owner == "NO" else -3.0,
                "btc_change9": 4.0 if owner == "NO" else -4.0,
                "ema9_change6": 0.5 if owner == "NO" else -0.5,
            },
            "mission_context":{"parent":{"side":side_owner,"measurements":{"age_seconds":500.0}}},
            "commander_strategy":{"active_overlays":["MARKET_HEIST"] if overlay else []},
        }
        return snap(t=now,no=no,yes=yes,metadata=md)

    def test_extended_down_new_low_sub20_yes_bypasses_heist_overlay(self):
        from strategy_core.commander_candidates import physical_entry_candidates
        intents=physical_entry_candidates(self._fast_snap(owner="NO",yes=.12,no=.88,overlay=True))
        self.assertEqual(len(intents),1)
        self.assertEqual(intents[0].side.value,"YES")
        self.assertEqual(intents[0].reason,"COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN")

    def test_extended_up_new_high_sub20_no_mirrors(self):
        from strategy_core.commander_candidates import physical_entry_candidates
        intents=physical_entry_candidates(self._fast_snap(owner="YES",yes=.90,no=.10,overlay=True))
        self.assertEqual(len(intents),1)
        self.assertEqual(intents[0].side.value,"NO")

    def test_fast_return_does_not_fire_when_opposite_price_above_20c(self):
        from strategy_core.commander_candidates import physical_entry_candidates
        intents=physical_entry_candidates(self._fast_snap(owner="NO",yes=.21,no=.79,overlay=True))
        self.assertEqual(intents,())
