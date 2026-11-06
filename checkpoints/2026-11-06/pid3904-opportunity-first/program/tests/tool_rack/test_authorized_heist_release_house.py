from __future__ import annotations

from types import SimpleNamespace
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from strategy_core.commander import OneCommander
from strategy_core.commander import CommanderDecision
from strategy_core.paper_execution import PaperBook, PaperExecutioner, PriceLevel
from strategy_core.paper_runtime import ToolRackPaperEngine
from strategy_core.router import PhysicalEvidence
from strategy_core.tool_rack import ToolRackController
from strategy_core.tools.heist import MarketHeistTool
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent, Territory
from strategy_core.commander_candidates import physical_entry_candidates
from tests.tool_rack.test_opportunity_first_commander import real_heist_snapshot


def snap(*, ticker="KX-A", t=1000.0, age=300.0, yes=.19, no=.19, metadata=None):
    md={
        "physical_current": True,
        "geometry_last_epoch_ms": t*1000.0,
        "geometry_continuity_generation": 1,
        "current_geometry": {},
        "mountain": {},
        "tp_geometry": {"target_between_ema9_ema30": False},
    }
    if metadata:
        md.update(metadata)
    return MarketSnapshot(now_ts=t,ticker=ticker,contract_age_s=age,
        yes_ask=yes,no_ask=no,yes_bid=max(.001,yes-.01),no_bid=max(.001,no-.01),metadata=md)


def parallel_meta(*, zone, btc6, ema6, qualified=False, visit="V1", release=False,
                  lower_visits=1, upper_visits=1, centers=1):
    return {
        "release_in_progress": release,
        "current_geometry": {"epoch_ms": 1000_000.0, "btc_change6": btc6,
            "ema9_change6": ema6, "ema_gap": 1.0, "range180": 80.0,
            "ema30_slope3m": 1.0},
        "heist": {
            "qualified_box": qualified,
            "at_upper_edge": zone == "UPPER",
            "at_lower_edge": zone == "LOWER",
            "current_zone": zone,
            "box_id": "B1",
            "visit_id": visit if zone != "INNER" else None,
            "lower": 100.0, "upper": 140.0, "edge_tolerance": 5.0,
            "lower_visits": lower_visits, "upper_visits": upper_visits,
            "center_traversals": centers,
            "repeatability_proof": {"observed_span_s": 360.0},
            "diagnostics": {"heist_environment": True, "parallel_emas": True,
                "minimum_box_range": 20.0},
        },
        "mountain": {"owner_side": "YES", "parent_structure": {
            "parent_terminal_ready": True, "extended_parent": False,
            "slow_rolling_parent": False}},
        "tp_geometry": {"target_between_ema9_ema30": False,
            "observed_target_side": "YES", "remaining_seconds": 600.0,
            "required_move_to_target_btc": 10.0},
    }


class AuthorizedHeistReleaseHouseTests(unittest.TestCase):
    def test_parallel_heist_overlay_coexists_with_mountain_and_survives_to_return(self):
        rack=ToolRackController()
        ev=PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES)
        first=snap(t=1000,yes=.19,no=.19,metadata=parallel_meta(
            zone="LOWER",btc6=-3,ema6=-1,qualified=False,visit="L1"))
        r1=rack.observe(ev,first)
        self.assertEqual(r1.owned_territory,Territory.ALTERNATING_MOUNTAIN)
        self.assertIn("MARKET_HEIST",r1.active_overlays)
        self.assertTrue(any(i.reason=="HEIST_PARALLEL_EXCURSION_ARMED_AWAIT_RETURN"
                            for i in r1.overlay_intents))

        second_meta=parallel_meta(zone="INNER",btc6=3,ema6=1,qualified=False,visit="L1")
        second_meta["current_geometry"]["epoch_ms"]=1001_000.0
        second=snap(t=1001,yes=.19,no=.81,metadata=second_meta)
        r2=rack.observe(PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES),second)
        entries=[i for i in r2.commander_intents if i.action is Action.ENTER and i.tool=="MARKET_HEIST"]
        self.assertEqual(len(entries),1)
        self.assertIs(entries[0].side,Side.YES)
        self.assertEqual(entries[0].reason,"HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED")

    def test_primary_heist_arm_survives_classifier_flicker_to_mountain(self):
        rack=ToolRackController()
        first=snap(t=1000,yes=.19,no=.19,metadata=parallel_meta(
            zone="LOWER",btc6=-3,ema6=-1,qualified=True,visit="L1"))
        r1=rack.observe(PhysicalEvidence(qualified_heist=True,ema9_direction=Side.YES),first)
        self.assertEqual(r1.owned_territory,Territory.MARKET_HEIST)
        self.assertFalse(any(i.action is Action.WAIT for i in r1.commander_intents))
        self.assertTrue(any(b.get("reason")=="HEIST_PARALLEL_EXCURSION_ARMED_AWAIT_RETURN"
                            and b.get("state")=="PREPARE" for b in r1.briefings))

        md=parallel_meta(zone="INNER",btc6=3,ema6=1,qualified=False,visit="L1")
        md["current_geometry"]["epoch_ms"]=1001_000.0
        second=snap(t=1001,yes=.19,no=.81,metadata=md)
        r2=rack.observe(PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES),second)
        self.assertEqual(r2.owned_territory,Territory.MARKET_HEIST)
        self.assertEqual(r2.ownership_reason,"HEIST_ARMED_RETURN_PERSISTS_THROUGH_CLASSIFIER_FLICKER")
        self.assertTrue(any(i.action is Action.ENTER and i.tool=="MARKET_HEIST" and i.side is Side.YES
                            for i in r2.commander_intents))

    def test_armed_heist_overlay_owns_quick_return_and_suppresses_competing_mountain_edge(self):
        mountain={
            "qualified_alternating_mountain":True,"owner_side":"YES","current_arc_id":"Q1",
            "edge_id":"Q1:E","terminal_evidence_qualified":True,"mature_edge":True,
            "edge_window_active":True,"strong_active_release":False,
            "diagnostics":{"current_age_s":90.0},
            "parent_structure":{"parent_id":"P","parent_side":"YES","parent_age_s":500.0,
                "parent_amplitude":80.0,"parent_terminal_ready":True,
                "slow_rolling_parent":False,"extended_parent":False},
        }
        s=snap(yes=.81,no=.19,metadata={"mountain":mountain,
            "tp_geometry":{"target_between_ema9_ema30":False,"remaining_seconds":600.0},
            "commander_strategy":{"owned_territory":"ALTERNATING_MOUNTAIN",
                "owned_side":"YES","active_tool":"ALTERNATING_MOUNTAIN",
                "active_overlays":["MARKET_HEIST"]}})
        self.assertEqual(OneCommander().physical_entry_candidates(s),())

    def test_living_release_suppresses_parallel_heist_overlay(self):
        rack=ToolRackController()
        md=parallel_meta(zone="LOWER",btc6=-3,ema6=-1,release=True)
        s=snap(metadata=md)
        intents=rack._parallel_heist_overlay_intents(s,
            raw=rack.router.classify(PhysicalEvidence(compression_unresolved=True)),
            release_in_progress=True)
        self.assertEqual(intents,())

    def test_confirmed_release_is_attached_to_mountain_owner_and_produces_relay(self):
        rack=ToolRackController()
        base=snap(t=1000,yes=.85,no=.15,metadata={"mountain":{"owner_side":"YES"}})
        r1=rack.observe(PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES),base)
        self.assertIn("RELEASE_WATCHER",r1.active_overlays)
        md={"mountain":{"owner_side":"YES"},"current_geometry":{"epoch_ms":1001_000.0}}
        second=snap(t=1001,yes=.85,no=.15,metadata=md)
        ev=PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES,
            release_candidate_side=Side.NO,release_boundary_break=True,
            release_directional_expansion=True,release_old_owner_failed_reextension=True)
        r2=rack.observe(ev,second)
        releases=[i for i in r2.commander_intents if i.tool=="RELEASE_WATCHER"]
        self.assertTrue(any(i.action is Action.RELAY and i.side is Side.NO and
                            i.reason=="RELEASE_CONFIRMED_LEVIATHAN_HANDOFF" for i in releases))
        self.assertTrue(r2.handoff_confirmed)

    def test_three_completed_quick_heist_contracts_prepare_fourth_without_entry_authority(self):
        rack=ToolRackController()
        def pattern(ticker,t):
            return snap(ticker=ticker,t=t,metadata=parallel_meta(
                zone="INNER",btc6=0,ema6=0,qualified=True,
                lower_visits=2,upper_visits=2,centers=2))
        contexts=[]
        for idx,ticker in enumerate(("KX-A","KX-B","KX-C","KX-D")):
            contexts.append(rack._update_heist_cycle_context(pattern(ticker,1000+idx)))
        self.assertEqual(contexts[-1]["consecutive_completed_pattern_contracts"],3)
        self.assertTrue(contexts[-1]["pop_prep"])
        self.assertFalse(contexts[-1]["entry_authority"])

    def test_quick_heist_entry_carries_immediate_40pct_3pct_peak_lock(self):
        tool=MarketHeistTool(territory_id="H")
        first=snap(t=1000,yes=.19,no=.81,metadata=parallel_meta(
            zone="LOWER",btc6=-3,ema6=-1,qualified=False,visit="L1"))
        list(tool.on_market_event(first))
        md=parallel_meta(zone="INNER",btc6=3,ema6=1,qualified=False,visit="L1")
        md["current_geometry"]["epoch_ms"]=1001_000.0
        intent=list(tool.on_market_event(snap(t=1001,yes=.19,no=.81,metadata=md)))[0]
        self.assertIs(intent.action,Action.ENTER)
        floor=intent.metadata["floor_policy"]
        self.assertEqual(floor["immediate_arm_roi"],.40)
        self.assertEqual(floor["trail_fraction"],.03)
        self.assertTrue(floor["first_arm_from_current_bid"])
        self.assertEqual(floor["profit_policy_revision"],"OPERATOR_AUTHORIZED_QUICK_HEIST_40_ARM_3_TRAIL_V1")


    def test_quick_heist_40pct_floor_actually_arms_in_executor(self):
        tool=MarketHeistTool(territory_id="H")
        list(tool.on_market_event(snap(t=1000,yes=.19,no=.81,metadata=parallel_meta(
            zone="LOWER",btc6=-3,ema6=-1,qualified=False,visit="L1"))))
        md=parallel_meta(zone="INNER",btc6=3,ema6=1,qualified=False,visit="L1")
        md["current_geometry"]["epoch_ms"]=1001_000.0
        intent=list(tool.on_market_event(snap(t=1001,yes=.19,no=.81,metadata=md)))[0]
        with tempfile.TemporaryDirectory() as td:
            ex=PaperExecutioner(Path(td)/"run")
            try:
                entry_book=PaperBook("KX-A","Q1",1001,1001,
                    (PriceLevel(.18,1000),),(PriceLevel(.81,1000),),1900)
                receipt=ex.execute(CommanderDecision(Action.ENTER,intent,"TEST"),entry_book,
                    now_ts=1001,command_id="E1")
                self.assertEqual(receipt.status,"BOOKED")
                position=ex.positions[receipt.position_id]
                policy=ToolRackPaperEngine._floor_policy([intent],position)
                self.assertIsNotNone(policy)
                self.assertEqual(policy.immediate_arm_roi,.40)
                self.assertEqual(policy.trail_fraction,.03)
                floor_book=PaperBook("KX-A","Q2",1002,1002,
                    (PriceLevel(.27,1000),),(PriceLevel(.72,1000),),1900)
                obs=ex.observe_floors(floor_book,now_ts=1002,policies={receipt.position_id:policy})[0]
                self.assertTrue(obs.armed)
                self.assertAlmostEqual(obs.floor_bid,.27*.97,places=8)
            finally:
                ex.close()

    def test_pid12220_trade1_120pct_exact_peak_stall_collects_before_floor(self):
        mountain={
            "owner_side":"NO","stall":True,"hesitation":False,
            "strong_active_release":False,"mature_edge":False,"edge_window_active":False,
            "terminal_evidence_qualified":False,
        }
        md={
            "mountain":mountain,
            "release_in_progress":False,
            "commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"},
            "paper_exit_mark":{"current":True,"full_quantity_visible":True,"full_lot_bid":.86},
        }
        s=replace(snap(t=1200,yes=.15,no=.87,metadata=md), no_sell_allowed=True)
        pos={"position_id":"P1","ticker":s.ticker,"territory_id":"MOUNTAIN_CONTRACT_LEG",
             "opportunity_id":"O1","tool":"ONE_COMMANDER_PRIMARY","lane":"MAIN","side":Side.NO,
             "entry_price":.39,"entry_time":1000.0,"close_ts":1900.0,"custody_state":"NORMAL",
             "entry_metadata":{"commander_candidate_family":"MOUNTAIN_CONTRACT_LEG"},
             "peak_bid":.86,"protected_peak_bid":.86,"floor_bid":.817,"trail_fraction":.05}
        d=OneCommander().decide_position([],s,pos)
        self.assertIs(d.action,Action.EXIT)
        self.assertEqual(d.intent.reason,"COMMANDER_HIGH_PROFIT_PEAK_HOVER_COLLECT")

    def test_peak_hover_skim_does_not_fire_off_peak_or_during_release(self):
        base={
            "position_id":"P1","ticker":"KX-A","territory_id":"MOUNTAIN_CONTRACT_LEG",
            "opportunity_id":"O1","tool":"ONE_COMMANDER_PRIMARY","lane":"MAIN","side":Side.NO,
            "entry_price":.39,"entry_time":1000.0,"close_ts":1900.0,"custody_state":"NORMAL",
            "entry_metadata":{"commander_candidate_family":"MOUNTAIN_CONTRACT_LEG"},
            "peak_bid":.86,"protected_peak_bid":.86,"floor_bid":.817,"trail_fraction":.05}
        off=replace(snap(t=1200,ticker="KX-A",yes=.16,no=.86,metadata={
            "mountain":{"owner_side":"NO","stall":True,"strong_active_release":False},
            "paper_exit_mark":{"current":True,"full_quantity_visible":True,"full_lot_bid":.85},
            "commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}}), no_sell_allowed=True)
        self.assertIs(OneCommander().decide_position([],off,base).action,Action.HOLD)
        rel=replace(snap(t=1200,ticker="KX-A",yes=.15,no=.87,metadata={
            "mountain":{"owner_side":"NO","stall":True,"strong_active_release":True},
            "release_in_progress":True,"release_candidate_side":"YES",
            "paper_exit_mark":{"current":True,"full_quantity_visible":True,"full_lot_bid":.86},
            "commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}}), no_sell_allowed=True)
        self.assertIs(OneCommander().decide_position([],rel,base).action,Action.HOLD)

    def test_rollover_terminal_return_below_50_has_quick_floor_and_50_is_strict(self):
        mountain={
            "qualified_alternating_mountain":True,"owner_side":"YES","current_arc_id":"A1",
            "terminal_evidence_qualified":True,"mature_edge":True,"edge_window_active":True,
            "strong_active_release":False,"edge_id":"E1",
            "diagnostics":{"current_age_s":120.0,"phase":"MATURE"},
            "parent_structure":{"parent_id":"P1","parent_side":"YES","parent_age_s":120.0,
                "parent_amplitude":40.0,"parent_terminal_ready":True,
                "slow_rolling_parent":False,"extended_parent":False,"child_arc_count":2},
        }
        tp={"contract_ownership":"BOUNCE_FAVORED","contract_ownership_side":"NO",
            "target_between_ema9_ema30":False,"observed_target_side":"YES",
            "required_move_to_target_btc":10.0,"remaining_seconds":880.0}
        s=snap(t=2000,age=20,yes=.51,no=.49,metadata={"mountain":mountain,"tp_geometry":tp,
            "commander_strategy":{"owned_territory":"ALTERNATING_MOUNTAIN",
                                  "owned_side":"YES","active_tool":"ALTERNATING_MOUNTAIN"}})
        # This partial synthetic wrapper tests the pre-existing opening cap
        # and floor policy; it does not assert complete source admission.
        candidates=physical_entry_candidates(s)
        self.assertEqual(len(candidates),1)
        intent=candidates[0]
        self.assertEqual(intent.reason,"COMMANDER_ROLLOVER_TERMINAL_RETURN_START")
        self.assertEqual(intent.max_price,.50)
        self.assertIs(intent.side,Side.NO)
        self.assertEqual(intent.metadata["floor_policy"]["immediate_arm_roi"],.40)
        self.assertEqual(intent.metadata["floor_policy"]["trail_fraction"],.03)
        s50=snap(t=2000,age=20,yes=.50,no=.50,metadata={"mountain":mountain,"tp_geometry":tp,
            "commander_strategy":{"owned_territory":"ALTERNATING_MOUNTAIN",
                                  "owned_side":"YES","active_tool":"ALTERNATING_MOUNTAIN"}})
        self.assertEqual(physical_entry_candidates(s50),())
        self.assertEqual(OneCommander().physical_entry_candidates(s),())

    def test_pop_prep_context_reaches_confirmed_release_without_granting_early_entry(self):
        rack=ToolRackController()
        def pattern(ticker,t):
            return snap(ticker=ticker,t=t,metadata=parallel_meta(zone="INNER",btc6=0,ema6=0,
                qualified=True,lower_visits=2,upper_visits=2,centers=2))
        for idx,ticker in enumerate(("KX-A","KX-B","KX-C")):
            rack._update_heist_cycle_context(pattern(ticker,1000+idx))
        # Move to fourth contract and establish a Mountain owner. The 3x state
        # is briefing only until a confirmed transfer actually appears.
        fourth=snap(ticker="KX-D",t=1010,yes=.85,no=.15,metadata={"mountain":{"owner_side":"YES"}})
        r0=rack.observe(PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES),fourth)
        self.assertFalse(any(i.action in (Action.ENTER,Action.RELAY) and i.tool=="RELEASE_WATCHER"
                             for i in r0.commander_intents))
        fifth=snap(ticker="KX-D",t=1011,yes=.85,no=.15,metadata={"mountain":{"owner_side":"YES"},
            "current_geometry":{"epoch_ms":1011_000.0}})
        ev=PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES,
            release_candidate_side=Side.NO,release_boundary_break=True,
            release_directional_expansion=True,release_new_side_residence=True)
        r1=rack.observe(ev,fifth)
        release=next(i for i in r1.commander_intents if i.tool=="RELEASE_WATCHER"
                     and i.action is Action.RELAY)
        self.assertTrue(release.metadata["heist_cycle_context"]["pop_prep"])
        self.assertEqual(release.metadata["heist_cycle_context"]["consecutive_completed_pattern_contracts"],3)

    def test_house_state_one_win_caution_two_wins_or_100pct_protected(self):
        engine=ToolRackPaperEngine.__new__(ToolRackPaperEngine)
        engine.executor=SimpleNamespace(events=[])
        self.assertEqual(engine._contract_house_state("KX-A")["mode"],"OPEN")
        engine.executor.events=[{"ticker":"KX-A","event":"EXIT","position_id":"1","gross_pnl":5,"cost":10}]
        self.assertEqual(engine._contract_house_state("KX-A")["mode"],"CAUTION")
        engine.executor.events.append({"ticker":"KX-A","event":"EXIT","position_id":"2","gross_pnl":1,"cost":10})
        self.assertEqual(engine._contract_house_state("KX-A")["mode"],"PROTECTED")
        engine.executor.events=[{"ticker":"KX-A","event":"EXIT","position_id":"3","gross_pnl":10,"cost":10}]
        self.assertEqual(engine._contract_house_state("KX-A")["mode"],"PROTECTED")
        self.assertEqual(engine._contract_house_state("KX-B")["mode"],"OPEN")

    def test_house_protected_blocks_non_heist_but_good_heist_remains_exception(self):
        commander=OneCommander()
        s=snap(metadata={"contract_house_state":{"mode":"PROTECTED"},
            "commander_strategy":{"owned_territory":"MARKET_HEIST","active_tool":"MARKET_HEIST"}})
        mountain=ToolIntent(tool="ONE_COMMANDER_PRIMARY",territory_id="MOUNTAIN_EDGE",lane=Lane.MAIN,
            side=Side.YES,action=Action.ENTER,opportunity_id="M",max_price=.19,size_tier=10,
            reason="COMMANDER_MOUNTAIN_TRUE_EDGE_RETURN",source_time=s.now_ts,
            metadata={"commander_primary_candidate":True,"commander_candidate_family":"MOUNTAIN_EDGE"})
        d=commander.decide([mountain],s)
        self.assertIs(d.action,Action.WAIT)
        self.assertEqual(d.reason,"COMMANDER_HOUSE_PROTECTED_WAIT_NEXT_CONTRACT")

        heist=ToolIntent(tool="MARKET_HEIST",territory_id="H",lane=Lane.TACTICAL,side=Side.YES,
            action=Action.ENTER,opportunity_id="H",max_price=.20,size_tier=10,
            reason="HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED",source_time=s.now_ts,
            metadata={"parallel_return_entry":True})
        valid=real_heist_snapshot(t=s.now_ts,age=s.contract_age_s)
        valid=replace(valid,yes_ask=.19,no_ask=.81,yes_bid=.18,no_bid=.80,
            metadata={**valid.metadata,"contract_house_state":{"mode":"PROTECTED"},
                "commander_strategy":{"owned_territory":"MARKET_HEIST","active_tool":"MARKET_HEIST"}})
        dh=commander.decide([heist],valid)
        self.assertIs(dh.action,Action.ENTER)
        self.assertIs(dh.intent.side,Side.YES)

    def test_house_caution_uses_live_ask_and_does_not_replace_source_proof(self):
        commander=OneCommander()
        cheap_snap=snap(yes=.15,no=.85,metadata={"contract_house_state":{"mode":"CAUTION"}})
        route=ToolIntent(tool="ONE_COMMANDER_PRIMARY",territory_id="MOUNTAIN_CONTRACT_LEG",lane=Lane.MAIN,
            side=Side.YES,action=Action.ENTER,opportunity_id="P",max_price=.40,size_tier=10,
            reason="COMMANDER_MOUNTAIN_BOUNCE_OWNS_CONTRACT",source_time=cheap_snap.now_ts,
            metadata={"commander_primary_candidate":True,"commander_candidate_family":"MOUNTAIN_CONTRACT_LEG"})
        # House economics is a separate necessary condition. A bare route
        # label does not satisfy the new physical opportunity contract.
        self.assertEqual(commander._entry_strategy_denial(route,cheap_snap),
                         "OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED")
        premium_snap=snap(yes=.25,no=.75,metadata={"contract_house_state":{"mode":"CAUTION"}})
        dp=commander.decide([route],premium_snap)
        self.assertIs(dp.action,Action.WAIT)
        self.assertEqual(dp.reason,"COMMANDER_HOUSE_CAUTION_BLOCK_PREMIUM_ENTRY")

if __name__ == "__main__":
    unittest.main()
