"""PID3860 read-only regression controls for the existing Mountain/Heist doctrine.

No hypothetical fills or historical P&L are calculated.  These tests verify
Commander admission/collection given explicit causal predecision evidence.
"""
import copy
import gzip
import json
from pathlib import Path
import unittest

from strategy_core.types import MarketSnapshot, Side, Action
from strategy_core.custody_evidence import build_custody_evidence
from strategy_core.commander_candidates import _inherited_leg_still_live
from strategy_core.commander import OneCommander


def snapshot(md=None, *, when=1050., bid=.38):
    return MarketSnapshot(
        now_ts=when, ticker="KX-TEST-15M", contract_age_s=when-1000,
        yes_ask=.39, no_ask=.62, yes_bid=bid, no_bid=.60,
        yes_sell_allowed=True, no_sell_allowed=True,
        metadata=md or {},
    )


def position():
    return {
        "position_id": "P-STALLED", "ticker": "KX-TEST-15M", "territory_id": "MOUNTAIN_EDGE",
        "opportunity_id": "O-STALLED", "tool": "ONE_COMMANDER_PRIMARY", "lane": "MAIN",
        "side": Side.YES, "entry_price": .29, "entry_time": 1000.,
        "close_ts": 1900., "peak_bid": .38, "floor_bid": None, "custody_state": "NORMAL",
        "entry_metadata": {"commander_candidate_family": "MOUNTAIN_EDGE"},
    }


def mark(*, bid=.38, net=1.8):
    return {"version": "PAPER_REMAINING_EXIT_MARK_V1",
            "ticker": "KX-TEST-15M", "position_id": "P-STALLED",
            "current": True, "full_quantity_visible": True,
            "full_lot_bid": bid, "net_after_fees": net}


def mature_md():
    return {"physical_current": True,
            "commander_strategy": {"owned_territory": "ALTERNATING_MOUNTAIN", "owned_side": "YES"},
            "mountain": {"owner_side": "YES", "mature_edge": True,
                         "edge_window_active": True, "failed_reextension": True,
                         "stall": True, "hesitation": True,
                         "strong_active_release": False},
            "paper_exit_mark": mark(), "release_in_progress": False}


class PID3860StalledExcursionCollection(unittest.TestCase):
    def test_repeated_failed_mature_mountain_collects_at_current_fee_positive_peak(self):
        md=mature_md()
        evidence=build_custody_evidence(position(),snapshot(md))
        self.assertTrue(evidence["fee_positive_mature_hover_collect"])
        self.assertEqual(evidence["reason"], "COMMANDER_FEE_POSITIVE_MATURE_EXCURSION_HOVER")
        decision=OneCommander().decide_position([],snapshot(md),position())
        self.assertIs(decision.action,Action.EXIT)
        self.assertEqual(decision.intent.reason,"COMMANDER_FEE_POSITIVE_MATURE_EXCURSION_HOVER")

    def test_not_first_stall_without_failed_reextension(self):
        md=mature_md()
        md["mountain"].update(failed_reextension=False, stall=True, hesitation=True)
        evidence=build_custody_evidence(position(),snapshot(md))
        self.assertFalse(evidence["fee_positive_mature_hover_collect"])

    def test_no_sale_on_prior_peak_below_current_full_lot_mark(self):
        md=mature_md()
        md["paper_exit_mark"]=mark(bid=.36,net=1.0)
        self.assertFalse(build_custody_evidence(position(),snapshot(md,bid=.36))["fee_positive_mature_hover_collect"])

    def test_no_fee_negative_sale_even_with_technical_profit(self):
        md=mature_md()
        md["paper_exit_mark"]=mark(net=-.20)
        self.assertFalse(build_custody_evidence(position(),snapshot(md))["fee_positive_mature_hover_collect"])

    def test_no_sale_on_stale_unauthenticated_or_wrong_position_mark(self):
        md=mature_md()
        for change in ({"current": False}, {"full_quantity_visible": False},
                       {"position_id": "P-OTHER"}, {"ticker": "OLD-CONTRACT"}):
            case=copy.deepcopy(md)
            case["paper_exit_mark"].update(change)
            self.assertFalse(build_custody_evidence(position(),snapshot(case))["fee_positive_mature_hover_collect"],change)

    def test_no_first_candle_sale(self):
        md=mature_md()
        self.assertFalse(build_custody_evidence(position(),snapshot(md,when=1012))["fee_positive_mature_hover_collect"])

    def test_no_sale_during_breakout_or_running_rail(self):
        for change in ({"strong_active_release": True},):
            md=mature_md();md["mountain"].update(change)
            self.assertFalse(build_custody_evidence(position(),snapshot(md))["fee_positive_mature_hover_collect"])
        md=mature_md();md["release_in_progress"]=True
        self.assertFalse(build_custody_evidence(position(),snapshot(md))["fee_positive_mature_hover_collect"])
        md=mature_md();md["commander_strategy"]["owned_territory"]="DOWN_RAIL"
        self.assertFalse(build_custody_evidence(position(),snapshot(md))["fee_positive_mature_hover_collect"])

    def test_genuine_repeated_heist_at_far_edge_collects(self):
        md=mature_md()
        md["commander_strategy"]["owned_territory"]="MARKET_HEIST"
        md["mountain"].update(mature_edge=False,edge_window_active=False,failed_reextension=False)
        md["heist"]={"qualified_box":True, "at_upper_edge":True,
                     "diagnostics":{"classic_qualified":True,"lower_visits":2,"upper_visits":2}}
        self.assertTrue(build_custody_evidence(position(),snapshot(md))["fee_positive_mature_hover_collect"])
        md["heist"]["diagnostics"]["upper_visits"]=1
        self.assertFalse(build_custody_evidence(position(),snapshot(md))["fee_positive_mature_hover_collect"])


class PID3860RecordedSequenceIntegrity(unittest.TestCase):
    def test_original_complete_decision_sequence_and_mature_rollover_case(self):
        source=Path(__file__).resolve().parent / "fixtures/pid3860_compact_decisions.json.gz"
        frames=json.loads(gzip.decompress(source.read_bytes()))
        self.assertEqual(len(frames), 7776)
        self.assertEqual([row["seq"] for row in frames], list(range(1,7777)))
        entries=[row for row in frames if row.get("dec_action") == "ENTER"]
        self.assertEqual(len(entries), 6)
        rollover=next(row for row in frames if row["seq"] == 5734)
        self.assertEqual(rollover["dec_side"], "YES")
        self.assertEqual(rollover["pdir"], "YES")
        self.assertGreater(rollover["gap"], 100.)
        self.assertLess(rollover["btc30"], -40.)
        self.assertLess(rollover["btc60"], -80.)
        self.assertGreater(rollover["askNO"], 0.50)
        # The old recorded ENTRY is evidence of the regression, not a filled
        # alternative.  The new helper must recognize current mature retreat.
        live,_=PID3860MatureRolloverDoNotChase._evidence(
            rollover["btc30"]/30.,rollover["btc60"]/60.,
            rollover["e30"]/30.,rollover["e60"]/60.)
        self.assertFalse(live)
        # The original full-run ledger remains immutable: six real PAPER
        # entries.  Do not infer a new NO purchase from the historical ask.


class PID3860MatureRolloverDoNotChase(unittest.TestCase):
    @staticmethod
    def _evidence(p30,p60,e30,e60,mature=True):
        mountain={"current_motion":{
            "30":{"covered":True,"owner_price_rate_btc_s":p30,"owner_ema9_rate_btc_s":e30},
            "60":{"covered":True,"owner_price_rate_btc_s":p60,"owner_ema9_rate_btc_s":e60}},
            "slowdown":{"owner_price_retreat_observed": p30 < 0},
            "diagnostics":{"phase":"MATURE" if mature else "BUILDING"}}
        parent={"parent_terminal_ready":False}
        md={"current_geometry":{"ema_gap":113.21,"range60":150.,"arc_phase":"MATURE" if mature else "BUILDING"},
            "ema9_ema30_cross_context":{"gap_lifecycle":{"current_side":"YES","stage":"MATURE"}}}
        return _inherited_leg_still_live(snapshot(md),mountain,parent,Side.YES)

    def test_pid3860_original_mature_top_price_retreat_not_live_rollover_yes(self):
        # Source-bound PID3860 BTC30=-$51.09 and BTC60=-$90.77 (per-second rates).
        live,proof=self._evidence(-51.09/30.,-90.77/60.,6.069/30.,-1.867/60.)
        self.assertFalse(live)
        self.assertTrue(proof["pronounced_mature_price_retreat"])
        self.assertTrue(proof["spent"])

    def test_ordinary_pullback_with_advancing_hour_parent_remains_valid(self):
        live,proof=self._evidence(-.5, .2, .2, .18)
        self.assertTrue(live)
        self.assertFalse(proof["pronounced_mature_price_retreat"])

    def test_newborn_child_not_an_established_old_arc(self):
        live,proof=self._evidence(-1.9,-1.7,-.4,-.25,mature=False)
        self.assertTrue(live)
        self.assertFalse(proof["pronounced_mature_price_retreat"])

    def test_still_advancing_mature_rail_can_continue(self):
        live,proof=self._evidence(.5,.7,.15,.20)
        self.assertTrue(live)
        self.assertFalse(proof["spent"])

if __name__ == "__main__":
    unittest.main()
