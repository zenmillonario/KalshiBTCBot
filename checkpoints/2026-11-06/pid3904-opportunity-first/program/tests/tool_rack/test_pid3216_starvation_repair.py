import gzip
import json
from pathlib import Path
import unittest

from strategy_core.commander import OneCommander
from strategy_core.detectors.mountain_geometry import detect_mountain_geometry
from strategy_core.physical_source import DirectPhysicalSource, PhysicalConfig
from strategy_core.types import Action, MarketSnapshot


def _completed_arc(arc_id, direction, start_ms, duration_s, base):
    sign = 1 if direction == "UP" else -1
    rows = []
    for age in range(0, duration_s + 1, 5):
        e9 = base + sign * 40 * age / duration_s
        rows.append({
            "arc_id": arc_id,
            "arc_direction": direction,
            "epoch_ms": start_ms + age * 1000,
            "arc_age_sec": age,
            "btc_price": e9,
            "ema9": e9,
            "ema30": e9 - sign * 10,
            "arc_phase": "ROLLING" if age == duration_s else "BUILDING",
            "arc_amplitude": abs(e9 - base),
            "arc_prominence_threshold": 5.0,
            "range60": 40.0,
            "struct_slope3m": sign * 1.0,
            "struct_slope6m": sign * 1.2,
        })
    return rows


def _history_with_current(*, plateau: bool):
    rows = []
    t = 0
    specs = [
        ("A1", "UP", 180, 1000),
        ("A2", "DOWN", 190, 1040),
        ("A3", "UP", 170, 1005),
        ("A4", "DOWN", 180, 1045),
        ("A5", "UP", 200, 1010),
        ("A6", "DOWN", 170, 1050),
    ]
    for arc_id, direction, duration, base in specs:
        rows.extend(_completed_arc(arc_id, direction, t, duration, base))
        t += (duration + 5) * 1000

    # Current UP arc is deliberately younger than the comparable-duration
    # maturity window.  It either flattens for 40 seconds (PID3216-style hover)
    # or keeps advancing (negative control).
    for age in range(0, 101, 5):
        if plateau:
            advance_age = min(age, 60)
        else:
            advance_age = age
        e9 = 1010.0 + 8.0 * advance_age / 60.0
        btc = 1030.0 + 10.0 * advance_age / 60.0
        rows.append({
            "arc_id": "A7",
            "arc_direction": "UP",
            "epoch_ms": t + age * 1000,
            "arc_age_sec": age,
            "btc_price": btc,
            "ema9": e9,
            "ema30": e9 - 28.0,
            "arc_phase": "MATURE" if age >= 70 else "BUILDING",
            "arc_amplitude": e9 - 1010.0,
            "arc_prominence_threshold": 5.0,
            "range60": 20.0,
            "struct_slope3m": 1.0,
            "struct_slope6m": 1.2,
        })
    return rows


class PID3216StarvationRepairTests(unittest.TestCase):
    def _raw(self, ts_s):
        return {
            "epoch_ms": ts_s * 1000.0,
            "btc_price": 1000.0,
            "ema9": 999.0,
            "ema30": 998.0,
            "connection_epoch": 1,
            "sequence_num": 1,
        }

    def test_small_negative_geometry_age_is_clock_skew_not_stale(self):
        src = DirectPhysicalSource(physical_config=PhysicalConfig(max_future_skew_seconds=2.0))
        frame = src.observe([self._raw(101.30)], now_ts=100.0)
        self.assertTrue(frame.current)
        self.assertAlmostEqual(frame.metadata["geometry_age_seconds"], -1.30, places=6)
        self.assertEqual(frame.metadata["geometry_max_future_skew_seconds"], 2.0)

    def test_materially_future_geometry_remains_invalid(self):
        src = DirectPhysicalSource(physical_config=PhysicalConfig(max_future_skew_seconds=2.0))
        frame = src.observe([self._raw(102.01)], now_ts=100.0)
        self.assertFalse(frame.current)
        self.assertLess(frame.metadata["geometry_age_seconds"], -2.0)

    def test_pid3216_style_hover_can_prove_terminal_before_duration_maturity(self):
        out = detect_mountain_geometry(_history_with_current(plateau=True))
        self.assertFalse(out.diagnostics["mature_by_comparison"])
        self.assertTrue(out.diagnostics["mature_by_causal_hover"])
        self.assertTrue(out.diagnostics["effective_physically_mature"])
        self.assertTrue(out.edge_window_active)
        self.assertTrue(out.stall)
        self.assertTrue(out.mature_edge)
        self.assertTrue(out.diagnostics["terminal_evidence_qualified"])
        self.assertFalse(out.strong_active_release)

    def test_still_advancing_parent_does_not_gain_hover_maturity(self):
        out = detect_mountain_geometry(_history_with_current(plateau=False))
        self.assertFalse(out.diagnostics["mature_by_causal_hover"])
        self.assertFalse(out.diagnostics["terminal_evidence_qualified"])


    def test_pid3216_actual_ultra_160950_hover_now_qualifies_terminal(self):
        fixture = Path(__file__).with_name("fixtures") / "pid3216_160950_ultra_geometry.jsonl.gz"
        with gzip.open(fixture, "rt", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        out = detect_mountain_geometry(rows)
        self.assertEqual(out.current_arc_id, "G000A000008")
        self.assertFalse(out.diagnostics["mature_by_comparison"])
        self.assertTrue(out.diagnostics["mature_by_causal_hover"])
        self.assertTrue(out.mature_edge)
        self.assertTrue(out.edge_window_active)
        self.assertTrue(out.stall)
        self.assertTrue(out.diagnostics["terminal_evidence_qualified"])
        motion30 = out.diagnostics["current_motion"]["30"]
        self.assertEqual(motion30["owner_price_rate_btc_s"], 0.0)
        self.assertEqual(motion30["owner_ema9_rate_btc_s"], 0.0)

    def test_pid3216_hover_does_not_change_tp_between_emas_wait_rule(self):
        # Actual PID3216 top geometry: even after the physical hover is allowed
        # to qualify as a terminal, the separately authorized TP-junction rule
        # remains untouched and therefore no paid reverse candidate is created.
        mountain = {
            "qualified_alternating_mountain": True,
            "owner_side": "YES",
            "current_arc_id": "PID3216-1609",
            "edge_id": "PID3216-1609-TOP",
            "mature_edge": True,
            "edge_window_active": True,
            "stall": True,
            "terminal_evidence_qualified": True,
            "strong_active_release": False,
            "parent_structure": {"parent_side": "YES", "parent_age_s": 113.8,
                                 "parent_terminal_ready": False, "slow_rolling_parent": False,
                                 "extended_parent": False, "child_arc_count": 2},
            "diagnostics": {"current_age_s": 113.8},
        }
        snap = MarketSnapshot(
            now_ts=1_793_565_399.0,
            ticker="KXBTC15M-PID3216",
            contract_age_s=599.0,
            yes_ask=.958,
            no_ask=.043,
            yes_bid=.957,
            no_bid=.042,
            metadata={
                "physical_current": True,
                "geometry_last_epoch_ms": 1_793_565_399_000.0,
                "geometry_continuity_generation": 1,
                "current_geometry": {"btc_price": 77830.84, "ema9": 77817.43, "ema30": 77788.64},
                "commander_strategy": {"owned_territory": "ALTERNATING_MOUNTAIN",
                                       "owned_side": "YES", "active_tool": "ALTERNATING_MOUNTAIN"},
                "mountain": mountain,
                "tp_geometry": {"target": 77794.24, "btc": 77830.84,
                                "target_between_ema9_ema30": True,
                                "required_move_to_target_btc": 36.60,
                                "remaining_seconds": 301.0,
                                "observed_target_side": "YES"},
            },
        )
        commander = OneCommander()
        self.assertEqual(commander.physical_entry_candidates(snap), ())
        decision = commander.decide_entry([], snap, {})
        self.assertIs(decision.action, Action.WAIT)


if __name__ == "__main__":
    unittest.main()
