"""Authored raw paths for parent-leg holding acceptance.

The strategy receives prices through the existing production EMA/candle
fixture. These annotations describe test expectations only; no weakness,
terminal, parent identity, or desired order is supplied to the engine.
"""
from dataclasses import dataclass

from tests.tool_rack.construct_arc_fixtures import ArcScenario


PATHS = {
    "TWO_PULLBACKS_THEN_TERMINAL": (
        (0, -120.), (150, -45.), (174, -60.), (210, -45.),
        (330, 30.), (354, 12.), (396, 30.),
        (570, 108.), (630, 120.), (654, 120.),
        (672, 114.), (690, 118.), (708, 108.), (780, 84.), (840, 60.),
    ),
    "ONE_REPEATED_PATCH": (
        (0, -120.), (150, -45.), (174, -60.), (300, -60.),
        (336, -45.), (480, 30.), (660, 140.), (840, 270.),
    ),
    "THREE_PAUSES_CONTINUATION": (
        (0, -120.), (120, -70.), (138, -78.), (180, -55.),
        (240, -20.), (258, -28.), (300, -5.),
        (360, 25.), (378, 17.), (420, 40.),
        (540, 110.), (660, 190.), (840, 330.),
    ),
    "DRIFTING_SINGLE_PAUSE": (
        (0, -120.), (150, -45.), (210, -33.), (300, -33.), (840, 270.),
    ),
}


@dataclass(frozen=True)
class HoldingScenario(ArcScenario):
    name: str = "holding_up"
    path_kind: str = "TWO_PULLBACKS_THEN_TERMINAL"

    def __post_init__(self):
        super().__post_init__()
        if self.path_kind not in PATHS:
            raise ValueError("UNKNOWN_HOLDING_CONSTRUCT_PATH")
        if (self.leg_seconds != 660 or self.plateau_seconds != 120
                or self.amplitude != 120. or self.drift_per_second != 0.):
            raise ValueError("HOLDING_EXPECTATIONS_REQUIRE_DECLARED_REFERENCE_GEOMETRY")

    @property
    def end_offset(self):
        # All scored management happens before the current contract closes.
        return self.current_start + 840

    def price(self, offset):
        if offset < self.current_start:
            return super().price(offset)
        elapsed = offset - self.current_start
        points = PATHS[self.path_kind]
        for (start, a), (end, b) in zip(points, points[1:]):
            if start <= elapsed <= end:
                signed = a + (b - a) * (elapsed - start) / (end - start)
                return 80_000. + self.direction * signed
        raise ValueError("HOLDING_PRICE_OUTSIDE_AUTHORED_PATH")

    def expectations(self):
        terminal = self.path_kind == "TWO_PULLBACKS_THEN_TERMINAL"
        single_pause = self.path_kind in ("ONE_REPEATED_PATCH", "DRIFTING_SINGLE_PAUSE")
        return {
            "source": "AUTHORED_RAW_PRICE_PATH_BEFORE_ENGINE_OUTPUT",
            "synthetic": True,
            "current_leg_start_offset": self.current_start,
            "end_relative_seconds": 840,
            "opening_entry_window_relative": [0, 60],
            "opening_side": "YES" if self.direction == 1 else "NO",
            "incoming_return_side": "NO" if self.direction == 1 else "YES",
            "terminal_exit_window_relative": [570, 732] if terminal else None,
            "early_pullback_hold_windows_relative": [[150, 210], [330, 396]] if terminal else [],
            "counter_checkpoint_relative": 300 if single_pause else 420,
            "expected_counter_at_checkpoint": 2 if terminal else 1 if single_pause else 3,
            "required_distinct_weaknesses": 3,
            "same_source_repeat_relative": 192,
            "same_source_repeat_count": 3,
            "expected_terminal_collection": terminal,
            "expected_hold_through_end": not terminal,
            "incoming_arc_same_position_full_quantity_through_end": terminal,
            "incoming_arc_same_parent_scope_through_end": terminal,
            "incoming_arc_no_reentry_through_end": terminal,
            "incoming_arc_hold_beyond_observed_ema9_contact": terminal,
            "incoming_arc_scope_active_at_end": terminal,
            "incoming_lifecycle_acceptance_revision": "SAME_INCOMING_ARC_THROUGH_NATURAL_RETURN_V1",
            "prior_completed_cycles": self.prior_cycles,
            "prior_cycle_candle_count_each_travel_leg": self.leg_seconds / 60,
            "prior_plateau_candles": self.plateau_seconds / 60,
            "authored_signed_price_knots": list(PATHS[self.path_kind]),
            "early_pullbacks_create_new_parent": False,
            "marks_are_only_scorer_annotations": True,
            "quote_formula": "current BTC and fixed contract strike only; inherited synthetic complementary book",
            "quote_scale": self.quote_scale,
            "midpoint_floor": self.midpoint_floor,
            "quote_half_spread": self.quote_half_spread,
            "normal_contract_seconds": 900,
            "no_official_settlement_needed_before_test_end": True,
        }
