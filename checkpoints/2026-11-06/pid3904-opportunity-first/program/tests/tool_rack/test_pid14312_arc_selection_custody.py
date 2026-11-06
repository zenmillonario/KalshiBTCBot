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
from strategy_core.tools.release import ReleaseConfig, ReleaseEvidence, ReleaseWatcher
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


def snap(*, t=1000.0, age=300.0, yes=.50, no=.50, owner="YES", gap_side="YES",
         stage="SPROUT", arc="UP", phase="BUILDING", tp_side="YES",
         tp_status="STARTING_LEG_FAVORED", parent_age=250.0, parent_amp=35.0,
         extended=False, mature=False, stall=False, hesitation=False,
         failed=False, retreat=False, parent_turning=False, metadata=None):
    md = {
        "physical_current": True,
        "geometry_last_epoch_ms": t * 1000.0,
        "geometry_continuity_generation": 1,
        "current_geometry": {
            "arc_direction": arc,
            "arc_phase": phase,
            "btc_change6": 3.0 if arc == "UP" else -3.0,
            "btc_change9": 5.0 if arc == "UP" else -5.0,
            "ema9_change6": 1.0 if arc == "UP" else -1.0,
        },
        "mountain": {
            "owner_side": owner,
            "terminal_evidence_qualified": False,
            "mature_edge": mature,
            "edge_window_active": mature,
            "stall": stall,
            "hesitation": hesitation,
            "failed_reextension": failed,
            "meaningful_retreat": retreat,
            "strong_active_release": False,
            "current_motion": {
                # Deliberately uncovered: PID14312 proved the live arc/TP path
                # must still create positive continuation briefing quality.
                "30": {"covered": False},
                "60": {"covered": False},
            },
            "parent_structure": {
                "parent_side": owner,
                "parent_age_s": parent_age,
                "parent_amplitude": parent_amp,
                "extended_parent": extended,
                "parent_terminal_ready": False,
                "parent_turning_or_flat": parent_turning,
            },
        },
        "ema9_ema30_cross_context": {
            "current_side": gap_side,
            "current_signed_gap_btc": 10.0 if gap_side == "YES" else -10.0,
            "previous_observed_cross_present": True,
            "observed_cross_count": 3,
            "recent_crossings": [
                {"direction": owner, "observed_continuously": True},
                {"direction": gap_side, "observed_continuously": True},
            ],
            "gap_lifecycle": {
                "stage": stage,
                "current_side": gap_side,
                "current_abs_gap_btc": 10.0,
                "gap_expanding_6s": True,
            },
        },
        "tp_geometry": {
            "target_between_ema9_ema30": False,
            "contract_ownership": tp_status,
            "contract_ownership_side": tp_side,
        },
        "commander_strategy": {"owned_side": owner, "owned_territory": "MARKET_HEIST"},
    }
    if metadata:
        for key, value in metadata.items():
            if key in md and isinstance(md[key], dict) and isinstance(value, dict):
                md[key].update(value)
            else:
                md[key] = value
    return MarketSnapshot(
        now_ts=t, ticker="KX-PID14312", contract_age_s=age,
        yes_ask=yes, no_ask=no, yes_bid=max(.001, yes-.01), no_bid=max(.001, no-.01),
        yes_sell_allowed=True, no_sell_allowed=True, metadata=md,
    )


def heist_intent(side: Side, reason="HEIST_PARALLEL_STALLED_EDGE_RETURN") -> ToolIntent:
    return ToolIntent(
        tool="MARKET_HEIST", territory_id="H", lane=Lane.TACTICAL,
        side=side, action=Action.ENTER, opportunity_id=f"H:{side.value}",
        max_price=.40, size_tier=10.0, reason=reason, source_time=1000.0,
        metadata={"position_role": "PRIMARY"},
    )


def return_position(*, side=Side.NO, reason="COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN",
                    entry_time=700.0, custody="NORMAL", evidence=None):
    return {
        "position_id": "P", "ticker": "KX-PID14312", "side": side,
        "entry_price": .057, "entry_time": entry_time, "close_ts": 1900.0,
        "tool": "ONE_COMMANDER_PRIMARY", "territory_id": "MOUNTAIN_EDGE",
        "opportunity_id": "RET", "lane": Lane.MAIN, "custody_state": custody,
        "position_role": "PRIMARY", "entry_reason": reason,
        "entry_metadata": {
            "position_role": "PRIMARY", "commander_candidate_family": "MOUNTAIN_EDGE",
            "commander_physical_evidence": evidence or {
                "entry_location": "RECENT_LEVEL_MATCH_RETURN", "outgoing_owner_side": "YES"
            },
        },
    }


class PID14312ArcSelectionCustodyTests(unittest.TestCase):
    def test_trade2_young_yes_sprout_does_not_brief_no_fade(self):
        s = snap(yes=.82, no=.19, owner="YES", gap_side="YES", arc="UP",
                 phase="BUILDING", tp_side="YES", parent_age=252, extended=False)
        self.assertTrue(ema9_continuation_precedent(s)["qualified"])
        self.assertFalse(positive_candidate_matches_continuation(heist_intent(Side.NO), s))

    def test_trade3_ultracheap_extended_top_seed_remains_eligible(self):
        s = snap(yes=.973, no=.028, owner="YES", gap_side="YES", arc="UP",
                 phase="EXPANDING", tp_side="YES", parent_age=433,
                 parent_amp=78, extended=True)
        self.assertTrue(ema9_continuation_precedent(s)["qualified"])
        self.assertTrue(positive_candidate_matches_continuation(heist_intent(Side.NO), s))

    def test_trade5_expensive_counter_return_is_not_briefed(self):
        s = snap(yes=.40, no=.61, owner="NO", gap_side="NO", arc="DOWN",
                 phase="MATURE", tp_side="NO", parent_age=452,
                 parent_amp=71, extended=True)
        self.assertTrue(ema9_continuation_precedent(s)["qualified"])
        self.assertFalse(positive_candidate_matches_continuation(heist_intent(Side.YES), s))

    def test_trade7_up_arc_tp_continuation_suppresses_no_renter_before_cross(self):
        s = snap(yes=.68, no=.33, owner="YES", gap_side="NO", stage="DEVELOPING",
                 arc="UP", phase="BUILDING", tp_side="YES", parent_age=88,
                 parent_amp=13, extended=False)
        evidence = ema9_continuation_precedent(s)
        self.assertTrue(evidence["qualified"])
        self.assertEqual(evidence["basis"], "CURRENT_ARC_TP_CONTINUATION")
        self.assertFalse(positive_candidate_matches_continuation(
            heist_intent(Side.NO, "HEIST_OUTER_EDGE_TACTICAL_RENTER"), s))

    def test_trade8_mature_stalled_sub20_return_is_allowed(self):
        s = snap(yes=.944, no=.057, owner="YES", gap_side="YES", arc="UP",
                 phase="EXPANDING", tp_side="YES", parent_age=287,
                 parent_amp=86, mature=True, stall=True)
        self.assertFalse(ema9_continuation_precedent(s)["qualified"])
        self.assertTrue(positive_candidate_matches_continuation(
            heist_intent(Side.NO, "HEIST_OUTER_EDGE_TACTICAL_RENTER"), s))

    def test_level_match_return_floor_breathes_30_seconds(self):
        s = snap(yes=.84, no=.16, owner="YES", gap_side="YES", arc="UP",
                 phase="MATURE", tp_side="YES", mature=True, stall=True, metadata={
            "historical_extreme_release": {
                "recent_level_match": {"side": "NO", "anchor": 77700.0,
                                       "anchor_time": 200.0, "age_s": 720.0,
                                       "distance_btc": 2.0},
            },
            "current_geometry": {"arc_direction": "UP", "arc_phase": "MATURE",
                                 "btc_change6": -3.0, "btc_change9": -4.0,
                                 "ema9_change6": -1.0},
        })
        candidate = physical_entry_candidates(s)[0]
        policy = candidate.metadata["floor_policy"]
        self.assertEqual(candidate.reason, "COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN")
        self.assertEqual(policy["min_age_s"], 30.0)
        self.assertEqual(policy["arm_roi"], 1.0)
        self.assertEqual(policy["immediate_arm_roi"], 1.5)

    def test_promoted_trade3_survives_180s_when_current_arc_is_held_side(self):
        p = return_position(side=Side.NO, reason="HEIST_PARALLEL_STALLED_EDGE_RETURN",
                            entry_time=700.0, custody="PROMOTED_MAIN")
        p["tool"] = "MARKET_HEIST"
        p["lane"] = Lane.TACTICAL
        s = snap(t=1000.0, yes=.96, no=.04, owner="YES", gap_side="YES",
                 arc="DOWN", phase="ROLLING", tp_side=None, tp_status="UNRESOLVED",
                 parent_turning=True)
        d = OneCommander().decide_position((), s, p)
        self.assertIs(d.action, Action.HOLD)
        self.assertNotEqual(d.intent.reason if d.intent else "", "COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT")

    def test_trade8_level_match_survives_180s_while_tp_bounce_favors_held_side(self):
        p = return_position(side=Side.NO, entry_time=700.0, custody="NORMAL")
        s = snap(t=1000.0, yes=.94, no=.06, owner="YES", gap_side="YES",
                 arc="UP", phase="MATURE", tp_side="NO", tp_status="BOUNCE_FAVORED",
                 parent_turning=True)
        d = OneCommander().decide_position((), s, p)
        self.assertFalse(d.action is Action.EXIT and d.intent and
                         d.intent.reason == "COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT")

    def test_trade6_unsupported_return_exits_after_transition_window(self):
        p = return_position(side=Side.YES,
                            reason="COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN",
                            entry_time=700.0, custody="NORMAL",
                            evidence={"entry_location": "FRESH_EXTENDED_MOUNTAIN_EXTREME",
                                      "outgoing_owner_side": "NO"})
        s = snap(t=1000.0, yes=.12, no=.88, owner="NO", gap_side="NO",
                 arc="DOWN", phase="TROUGH_FORMING", tp_side="NO",
                 tp_status="STARTING_LEG_FAVORED", parent_turning=False)
        d = OneCommander().decide_position((), s, p)
        self.assertIs(d.action, Action.EXIT)
        self.assertEqual(d.intent.reason, "COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT")

    def test_late_release_carries_60pct_floor_and_150pct_immediate_lock(self):
        watcher = ReleaseWatcher(territory_id="REL", owner_side=Side.YES,
                                 config=ReleaseConfig(soft_max_price=.30))
        evidence = ReleaseEvidence(candidate_side=Side.NO, boundary_break=True,
                                   directional_expansion=True, new_side_residence=True)
        watcher.update_evidence(evidence, entry_evidence=evidence,
                                entry_diagnostics={"fresh_transfer": True, "observed_at": 1000.0})
        s = snap(t=1000.0, age=720.0, yes=.89, no=.11, owner="NO", gap_side="YES",
                 arc="DOWN", phase="BUILDING", tp_side="NO", metadata={
            "release_in_progress": True, "release_candidate_side": "NO",
            "commander_strategy": {"owned_side": "NO", "owned_territory": "RELEASE_TRANSITION"},
        })
        intent = list(watcher.on_market_event(s))[0]
        self.assertEqual(intent.reason, "RELEASE_CONFIRMED_LEVIATHAN_HANDOFF")
        policy = intent.metadata["floor_policy"]
        self.assertEqual(policy["arm_roi"], .60)
        self.assertEqual(policy["min_age_s"], 30.0)
        self.assertEqual(policy["immediate_arm_roi"], 1.50)

    def test_late_release_floor_is_not_promoted_to_200pct_runner(self):
        p = PaperPosition(
            position_id="R9", ticker="KX-PID14312", side=Side.NO, qty=100,
            entry_price=.11, cost=11.0, entry_fee_remaining=0.0,
            entry_time=900.0, close_ts=1200.0, tool="RELEASE_WATCHER",
            territory_id="REL", opportunity_id="R9", lane=Lane.HANDOFF,
            entry_quote_id="Q", entry_reason="RELEASE_CONFIRMED_LEVIATHAN_HANDOFF",
            entry_metadata={"floor_policy": {"arm_roi": .60, "trail_fraction": .05,
                "min_age_s": 30.0, "immediate_arm_roi": 1.50,
                "first_arm_allowed": True, "first_arm_from_current_bid": True,
                "roi_trail_tiers": [[1.0, .05], [1.5, .03]]}},
            peak_bid=None, floor_bid=None, trail_fraction=None,
            exit_required=False, exit_reason=None, position_role="PRIMARY",
        )
        s = snap(t=1000.0, age=700.0, yes=.80, no=.20, owner="NO", gap_side="NO",
                 arc="DOWN", phase="BUILDING", tp_side="NO", metadata={
            "release_in_progress": True, "release_candidate_side": "NO",
            "mission_context": {"parent": {"side": "NO", "status": "ACTIVE"}},
        })
        policy = ToolRackPaperEngine._floor_policy((), p, s)
        self.assertEqual(policy.arm_roi, .60)
        self.assertEqual(policy.immediate_arm_roi, 1.50)


if __name__ == "__main__":
    unittest.main()
