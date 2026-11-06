from __future__ import annotations

import unittest

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import (
    ema9_continuation_precedent,
    physical_entry_candidates,
    positive_candidate_matches_continuation,
)
from strategy_core.paper_execution import PaperPosition
from strategy_core.paper_runtime import ToolRackPaperEngine
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


def snap(*, t=1000.0, yes=.40, no=.60, owner="YES", gap_side="NO",
         stage="SPROUT", stall=False, terminal=False, metadata=None):
    md = {
        "physical_current": True,
        "geometry_last_epoch_ms": t * 1000.0,
        "geometry_continuity_generation": 1,
        "current_geometry": {},
        "mountain": {
            "owner_side": owner,
            "stall": stall,
            "hesitation": False,
            "failed_reextension": False,
            "meaningful_retreat": False,
            "terminal_evidence_qualified": terminal,
            "mature_edge": terminal,
            "edge_window_active": terminal,
            "strong_active_release": False,
            "current_motion": {
                "30": {"covered": True, "owner_price_rate_btc_s": 1.1,
                       "owner_ema9_rate_btc_s": .22},
                "60": {"covered": True, "owner_price_rate_btc_s": .9,
                       "owner_ema9_rate_btc_s": .28},
            },
        },
        "ema9_ema30_cross_context": {
            "current_side": gap_side,
            "current_signed_gap_btc": -11.0 if gap_side == "NO" else 11.0,
            "previous_observed_cross_present": True,
            "observed_cross_count": 4,
            "recent_crossings": [
                {"direction": owner, "observed_continuously": True},
                {"direction": gap_side, "observed_continuously": True},
            ],
            "gap_lifecycle": {
                "stage": stage,
                "current_side": gap_side,
                "current_abs_gap_btc": 11.0,
                "gap_expanding_6s": True,
            },
        },
        "tp_geometry": {"target_between_ema9_ema30": False},
        "commander_strategy": {"owned_side": owner, "owned_territory": "MARKET_HEIST"},
    }
    if metadata:
        for key, value in metadata.items():
            if key in md and isinstance(md[key], dict) and isinstance(value, dict):
                md[key].update(value)
            else:
                md[key] = value
    return MarketSnapshot(
        now_ts=t, ticker="KX-PID7812", contract_age_s=300.0,
        yes_ask=yes, no_ask=no, yes_bid=max(.001, yes-.01), no_bid=max(.001, no-.01),
        yes_sell_allowed=True, no_sell_allowed=True, metadata=md,
    )


def heist_seed_position(*, custody="NORMAL", t=900.0):
    return {
        "position_id": "18", "ticker": "KX-PID7812", "side": Side.YES,
        "entry_price": .40, "entry_time": t, "close_ts": 1900.0,
        "tool": "MARKET_HEIST", "territory_id": "MARKET_HEIST_0052",
        "opportunity_id": "H18", "lane": Lane.TACTICAL,
        "custody_state": custody, "position_role": "PRIMARY",
        "entry_reason": "HEIST_PARALLEL_STALLED_EDGE_RETURN",
        "entry_metadata": {"position_role": "PRIMARY"},
    }


class PID7812SproutPromotionTests(unittest.TestCase):
    def test_trade18_comparable_cross_precedent_is_positive_yes(self):
        evidence = ema9_continuation_precedent(snap())
        self.assertTrue(evidence["qualified"])
        self.assertEqual(evidence["side"], "YES")
        self.assertEqual(evidence["basis"], "COMPARABLE_PRIOR_EMA9_CROSS_CONTINUATION")

    def test_trade18_heist_seed_promotes_to_living_ema9_custody(self):
        decision = OneCommander().decide_position((), snap(), heist_seed_position())
        self.assertIs(decision.action, Action.HOLD)
        self.assertEqual(decision.reason, "COMMANDER_HEIST_SEED_PROMOTED_TO_LIVING_EMA9_CUSTODY")
        self.assertEqual((decision.custody_update or {}).get("state"), "PROMOTED_MAIN")
        self.assertIs(decision.intent.lane, Lane.MAIN)

    def test_trade18_quick_heist_floor_waits_for_200pct_while_leg_alive(self):
        position = PaperPosition(
            position_id="18", ticker="KX-PID7812", side=Side.YES, qty=25,
            entry_price=.40, cost=10.0, entry_fee_remaining=0.0,
            entry_time=900.0, close_ts=1900.0, tool="MARKET_HEIST",
            territory_id="MARKET_HEIST_0052", opportunity_id="H18",
            lane=Lane.TACTICAL, entry_quote_id="Q", entry_reason="HEIST_PARALLEL_STALLED_EDGE_RETURN",
            entry_metadata={"floor_policy": {"arm_roi": .40, "trail_fraction": .03,
                "min_age_s": 0.0, "immediate_arm_roi": .40,
                "first_arm_from_current_bid": True}},
            peak_bid=.80, floor_bid=None, trail_fraction=None,
            exit_required=False, exit_reason=None, position_role="PRIMARY",
        )
        policy = ToolRackPaperEngine._floor_policy((), position, snap(yes=.81, no=.19))
        self.assertEqual(policy.arm_roi, 2.0)
        self.assertEqual(policy.immediate_arm_roi, 2.0)
        self.assertGreaterEqual(policy.trail_fraction, .05)

    def test_promoted_seed_does_not_hit_old_180_second_tactical_timeout(self):
        position = heist_seed_position(custody="PROMOTED_MAIN", t=600.0)
        decision = OneCommander().decide_position((), snap(t=1000.0), position)
        self.assertIs(decision.action, Action.HOLD)
        self.assertNotIn("MAX_HOLD", decision.reason)

    def test_trade19_opposite_heist_briefing_is_not_sent_during_yes_precedent(self):
        intent = ToolIntent(
            tool="MARKET_HEIST", territory_id="H", lane=Lane.TACTICAL,
            side=Side.NO, action=Action.ENTER, opportunity_id="19",
            max_price=.35, size_tier=10.0,
            reason="HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED", source_time=1000.0,
            metadata={"position_role": "TACTICAL"},
        )
        self.assertFalse(positive_candidate_matches_continuation(intent, snap()))

    def test_trade20_fast_no_fade_is_not_generated_during_fresh_yes_sprout(self):
        s = snap(yes=.90, no=.10, owner="YES", gap_side="YES", stage="SPROUT", metadata={
            "mountain": {
                "qualified": True, "qualified_alternating_mountain": True,
                "current_arc_id": "YES-SPROUT", "source_ms": 1000000.0,
                "edge_extreme_ms": 990000.0, "spent_edge": False,
                "full_leg_scale_evidence": {"qualified": True},
                "diagnostics": {"current_age_s": 500.0},
            },
            "mission_context": {"parent": {"side": "YES", "measurements": {"age_seconds": 500.0}}},
        })
        # PID8552 now suppresses the premature cheap counterfade at the
        # positive-candidate construction stage, not merely downstream.
        raw = physical_entry_candidates(s)
        self.assertEqual(raw, ())
        self.assertEqual(OneCommander().physical_entry_candidates(s), ())

    def test_mirror_fresh_no_sprout_does_not_brief_yes_fade(self):
        intent = ToolIntent(
            tool="MARKET_HEIST", territory_id="H", lane=Lane.TACTICAL,
            side=Side.YES, action=Action.ENTER, opportunity_id="MIRROR",
            max_price=.35, size_tier=10.0,
            reason="HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED", source_time=1000.0,
            metadata={"position_role": "TACTICAL"},
        )
        s = snap(owner="NO", gap_side="NO", stage="SPROUT", yes=.15, no=.85)
        self.assertFalse(positive_candidate_matches_continuation(intent, s))

    def test_confirmed_opposite_release_may_replace_sprout(self):
        intent = ToolIntent(
            tool="RELEASE_WATCHER", territory_id="R", lane=Lane.MAIN,
            side=Side.NO, action=Action.ENTER, opportunity_id="HANDOFF",
            max_price=.30, size_tier=25.0, reason="CONFIRMED_RELEASE_HANDOFF", source_time=1000.0,
            metadata={"position_role": "PRIMARY"},
        )
        self.assertTrue(positive_candidate_matches_continuation(
            intent, snap(), confirmed_release_side=Side.NO))

    def test_current_weakness_retires_continuation_precedent(self):
        s = snap(stall=True)
        evidence = ema9_continuation_precedent(s)
        self.assertFalse(evidence["qualified"])
        intent = ToolIntent(
            tool="MARKET_HEIST", territory_id="H", lane=Lane.TACTICAL,
            side=Side.NO, action=Action.ENTER, opportunity_id="TURN",
            max_price=.20, size_tier=10.0, reason="HEIST_OUTER_EDGE_TACTICAL_RENTER",
            source_time=1000.0, metadata={"position_role": "TACTICAL"},
        )
        self.assertTrue(positive_candidate_matches_continuation(intent, s))


if __name__ == "__main__":
    unittest.main()
