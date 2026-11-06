import unittest
from dataclasses import replace
from unittest.mock import patch

from strategy_core.commander import OneCommander
from strategy_core.detectors.mountain_geometry import detect_mountain_geometry
from strategy_core.looking_glass import build_looking_glass
from strategy_core.mission_context import MissionContext
from strategy_core.mission_policy import MissionPolicy
from strategy_core.tools.rail import RailTool
from strategy_core.types import Action, MarketSnapshot, Side


class PID2672AuthorizedRepairsTests(unittest.TestCase):
    def test_looking_glass_tolerates_same_two_second_future_skew(self):
        market = {
            "ticker": "KXBTC15M-T",
            "time": 101.3,
            "close_ts": 1000.0,
            "target": 100.0,
            "btc": 101.0,
            "e9": 100.5,
            "e30": 99.5,
            "fresh": True,
        }
        self.assertNotEqual(build_looking_glass(market, now_ts=100.0)["status"], "STALE")
        self.assertEqual(build_looking_glass({**market, "time": 102.1}, now_ts=100.0)["status"], "STALE")

    def test_mission_context_tolerates_same_two_second_future_skew(self):
        row = {
            "epoch_ms": 101300.0,
            "btc_price": 101.0,
            "ema9": 100.5,
            "ema30": 99.5,
            "arc_id": "A",
            "arc_direction": "UP",
            "arc_phase": "BUILDING",
            "arc_age_sec": 10.0,
            "arc_amplitude": 1.0,
            "arc_prominence_threshold": 1.0,
        }
        ctx = MissionContext()
        out = ctx.observe(
            {"current_geometry": row, "physical_current": True, "geometry_continuity_generation": 0},
            ticker="KXBTC15M-T", open_ts=0.0, close_ts=900.0, target=100.0,
            now_ts=100.0, rows=[row], historical_candles=[])
        self.assertTrue(out["current"])
        self.assertEqual(out["source_ms"], 101300.0)

        late = {**row, "epoch_ms": 102100.0}
        ctx2 = MissionContext()
        out2 = ctx2.observe(
            {"current_geometry": late, "physical_current": True, "geometry_continuity_generation": 0},
            ticker="KXBTC15M-T", open_ts=0.0, close_ts=900.0, target=100.0,
            now_ts=100.0, rows=[late], historical_candles=[])
        self.assertFalse(out2["current"])

    def test_paired_gap_is_prepare_alert_not_paid_terminal_by_itself(self):
        rows = []
        for age in range(0, 31, 5):
            ema9 = 100.0 + age * 0.2
            rows.append({
                "arc_id": "CURRENT-UP", "arc_direction": "UP",
                "epoch_ms": 100000.0 + age * 1000.0,
                "arc_age_sec": age, "btc_price": ema9 + 10.0,
                "ema9": ema9, "ema30": ema9 - 20.0,
                "arc_phase": "MATURE", "arc_amplitude": age * 0.2,
                "arc_prominence_threshold": 2.0, "range60": 20.0,
                "struct_slope3m": 1.0, "struct_slope6m": 1.2,
            })
        paired = {
            "eligible": True, "reference_count": 2, "references": [], "matches": [{}],
            "selected_match": {}, "current_pair": {}, "current_slowdown": {"observed": True},
            "steep_observed": False, "gap_relative_tolerance": 0.18,
            "steepness_formula": "TEST", "shape_age_height_prerequisites": False,
            "measurement_calibration": "TEST",
        }
        with patch("strategy_core.detectors.mountain_geometry._paired_gap_evidence", return_value=paired):
            out = detect_mountain_geometry(rows)
        self.assertTrue(out.diagnostics["mature_by_paired_gap"])
        self.assertTrue(out.diagnostics["paired_gap_prepare_alert"])
        self.assertFalse(out.diagnostics["paired_gap_trade_authority"])
        self.assertTrue(out.mature_edge)
        self.assertTrue(out.edge_window_active)
        self.assertFalse(out.stall)
        self.assertFalse(out.diagnostics["terminal_evidence_qualified"])

    @staticmethod
    def _pid2672_190502_snapshot(*, seconds_left=597.73):
        contract_age = 900.0 - seconds_left
        mountain = {
            "qualified_alternating_mountain": True,
            "owner_side": "YES",
            "current_arc_id": "G000A000059",
            "edge_id": "G000A000059:1793577901336",
            "terminal_evidence_qualified": True,
            "mature_edge": True,
            "edge_window_active": True,
            "stall": True,
            "meaningful_retreat": True,
            "failed_reextension": False,
            "strong_active_release": False,
            "parent_structure": {
                "parent_id": "E000A000015", "parent_side": "YES",
                "parent_age_s": 1057.0, "parent_amplitude": 134.1,
                "parent_terminal_ready": True, "parent_turning_or_flat": True,
                "slow_rolling_parent": False, "extended_parent": True, "child_arc_count": 12,
            },
            "diagnostics": {"current_age_s": 10.3},
            "current_motion": {
                "30": {"covered": True, "owner_price_rate_btc_s": -1.87, "owner_ema9_rate_btc_s": -0.095},
                "60": {"covered": True, "owner_price_rate_btc_s": -0.66, "owner_ema9_rate_btc_s": 0.007},
            },
            "return_leg_reference": {
                "count": 4,
                "basis": "LAST_COMPLETED_OPPOSITE_DIRECTION_PARENT_MOUNTAINS",
                "median_amplitude_btc": 26.06,
                "median_speed_btc_s": 0.316,
                "max_amplitude_btc": 37.66,
                "max_speed_btc_s": 0.369,
                "legs": [
                    {"arc_id": "a", "btc_amplitude_btc": 26.5, "duration_s": 393.0, "average_btc_speed_btc_s": 0.067},
                    {"arc_id": "b", "btc_amplitude_btc": 25.6, "duration_s": 75.3, "average_btc_speed_btc_s": 0.34},
                    {"arc_id": "c", "btc_amplitude_btc": 37.66, "duration_s": 128.3, "average_btc_speed_btc_s": 0.293},
                    {"arc_id": "d", "btc_amplitude_btc": 19.71, "duration_s": 53.3, "average_btc_speed_btc_s": 0.369},
                ],
            },
        }
        return MarketSnapshot(
            now_ts=1793577902.27, ticker="KXBTC15M-PID2672", contract_age_s=contract_age,
            yes_ask=.85, no_ask=.16, yes_bid=.84, no_bid=.15,
            metadata={
                "physical_current": True,
                "geometry_last_epoch_ms": 1793577902401.1,
                "current_geometry": {"btc_price": 78323.15, "ema9": 78296.06, "ema30": 78211.13},
                "commander_strategy": {"owned_territory": "ALTERNATING_MOUNTAIN", "owned_side": "YES", "active_tool": "ALTERNATING_MOUNTAIN"},
                "mountain": mountain,
                "tp_geometry": {
                    "target": 78240.38, "btc": 78323.15,
                    "observed_target_side": "YES",
                    "required_move_to_target_btc": 82.77,
                    "remaining_seconds": seconds_left,
                    "contract_ownership": "BOUNCE_FAVORED",
                    "contract_ownership_side": "NO",
                    "comparable_parent_amplitude_btc": 237.138,
                    "target_between_ema9_ema30": True,
                },
            },
        )

    def test_old_partial_tp_junction_proposal_cannot_publish_current_executable_candidate(self):
        snap = self._pid2672_190502_snapshot(seconds_left=597.73)
        from strategy_core.commander_candidates import physical_entry_candidates
        intents = physical_entry_candidates(snap)
        self.assertEqual(len(intents), 1)
        self.assertIs(intents[0].action, Action.ENTER)
        self.assertIs(intents[0].side, Side.NO)
        self.assertEqual(intents[0].reason, "COMMANDER_MOUNTAIN_BOUNCE_OWNS_CONTRACT")
        j = intents[0].metadata["commander_physical_evidence"]["tp_junction_policy"]
        self.assertEqual(j["basis"], "TP_JUNCTION_ADVISORY_EARLY_BOUNCE_FAVORED_PARENT_SCALE")
        self.assertTrue(j["runway_override"])
        # Retain the historical adviser predicate. The November6 contract
        # requires current source/parent evidence and treats TP junctions as
        # WAIT; this partial wrapper cannot prove an executable exception.
        self.assertEqual(OneCommander().physical_entry_candidates(snap),())

    def test_same_tp_junction_relaxation_is_not_available_inside_final_five_minutes(self):
        snap = self._pid2672_190502_snapshot(seconds_left=299.0)
        self.assertEqual(OneCommander().physical_entry_candidates(snap), ())

    def test_pid2672_2016_mature_up_rail_ema9_dip_can_use_20c_value_ceiling(self):
        now = 1793582215.81
        snap = MarketSnapshot(
            now_ts=now, ticker="KXBTC15M-PID2672-RAIL", contract_age_s=95.0,
            yes_ask=.20, no_ask=.81, yes_bid=.19, no_bid=.80,
            metadata={
                "source": "DIRECT_BTC_AND_NATIVE_KALSHI",
                "current_geometry": {
                    "btc_price": 78212.50, "ema9": 78257.24, "ema30": 78158.25,
                    "arc_direction": "DOWN", "parent_direction": "UP",
                    "btc_change30": -27.19, "ema9_change30": -5.44,
                },
                "mountain": {"parent_structure": {
                    "parent_side": "YES", "parent_age_s": 937.4,
                    "parent_terminal_ready": False, "slow_rolling_parent": True,
                }},
                "ema9_ema30_cross_context": {"gap_lifecycle": {
                    "stage": "MATURE", "current_side": "YES",
                    "continued_on_latest_cross_side": True,
                    "age_seconds_since_observed_cross": 900.08,
                }},
                "mission_context": {"contract": {
                    "target": 78300.0, "history_status": "READY",
                    "reference_window": {"completed_prior_contracts": 2},
                }},
            },
        )
        rail = RailTool(territory_id="UP_RAIL_1", side=Side.YES, activated_at=now - 30.0)
        intent = list(rail.on_activate(snap))[0]
        self.assertIs(intent.action, Action.ENTER)
        self.assertEqual(intent.reason, "RAIL_EMA9_DIP_VALUE")
        self.assertAlmostEqual(intent.max_price, .399)
        self.assertTrue(intent.metadata["ema9_dip_value"]["corridor_pullback"])

        # Retain the adviser/MissionPolicy price species. A label in this
        # partial95-second wrapper cannot authorize normal MAIN before300s
        # or replace a current measured value rejoin.
        reviewed_raw = replace(intent, metadata={**intent.metadata,
            "parent_scale_rail_authority": True,
            "physical_mission_id": "UP_RAIL_1:RAIL_CHAPTER",
            "physical_renewal": {"independent": True, "renewal_kind": "NEW_RAIL_TERRITORY",
                                 "observed_at": now},
        })
        md = dict(snap.metadata)
        md["mission_context"] = {
            "current": True, "source_ms": now * 1000.0, "continuity_generation": 1,
            "parent": {"id": "P-R", "side": "YES", "status": "ACTIVE", "supported": True,
                       "invalidated": False, "source_ms": now * 1000.0,
                       "known_ms": (now - 1) * 1000.0, "continuity_generation": 1},
            "local": {"arc_id": "G-R-DIP"}, "candidates": {},
            "contract": {"ticker": snap.ticker, "target": 78300.0, "history_status": "READY",
                         "reference_window": {"completed_prior_contracts": 2},
                         "thesis_side": "YES", "reason": "fixture"},
        }
        policy_snap = MarketSnapshot(**{**snap.__dict__, "metadata": md})
        reviewed = MissionPolicy().review(reviewed_raw, policy_snap)
        decision = OneCommander().decide([reviewed], policy_snap)
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason,"OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED")
        self.assertEqual(reviewed.metadata["mission_policy_advice"]["classification"], "RAIL_EMA9_DIP_VALUE")

        still_value = MarketSnapshot(**{**snap.__dict__, "yes_ask": .21})
        rail2 = RailTool(territory_id="UP_RAIL_2", side=Side.YES, activated_at=now - 30.0)
        intent2 = list(rail2.on_activate(still_value))[0]
        self.assertIs(intent2.action, Action.ENTER)
        self.assertEqual(intent2.reason, "RAIL_EMA9_DIP_VALUE")
        too_expensive = MarketSnapshot(**{**snap.__dict__, "yes_ask": .40})
        rail3 = RailTool(territory_id="UP_RAIL_3", side=Side.YES, activated_at=now - 30.0)
        intent3 = list(rail3.on_activate(too_expensive))[0]
        self.assertIs(intent3.action, Action.WAIT)
        self.assertIn("ABOVE_MAX_0.399", intent3.reason)


if __name__ == "__main__":
    unittest.main()
