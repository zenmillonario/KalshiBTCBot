"""Predeclared raw-price/clock/quote inputs for the profitable ARC exception.

The first pullback is reused from the existing holding tape. The short-clock
contract still lasts exactly 900 seconds; its opening precedes the current
leg. No source labels, held positions, weakness or timing references are
provided to production. Quote-only giveback is an authored control input.
"""
from dataclasses import dataclass
import math

from strategy_core.marketdata.kalshi_public import MarketInfo
from tests.tool_rack.construct_arc_fixtures import BASE
from tests.tool_rack.construct_holding_fixtures import HoldingScenario


@dataclass(frozen=True)
class ContractInterruptionScenario(HoldingScenario):
    name: str = "contract_interruption_up"
    close_relative_seconds: int = 240
    current_weakness_path: bool = True
    quote_only_giveback: bool = False

    def __post_init__(self):
        super().__post_init__()
        if self.close_relative_seconds not in (240, 900):
            raise ValueError("UNDECLARED_CONTRACT_INTERRUPTION_CLOCK")
        if self.quote_only_giveback == self.current_weakness_path:
            raise ValueError("CONTROL_REQUIRES_MONOTONIC_PRICE_AND_QUOTE_ONLY_GIVEBACK")

    @property
    def end_offset(self):
        return self.current_start + 216

    def price(self, offset):
        if offset < self.current_start or self.current_weakness_path:
            return super().price(offset)
        # Same opening and initial advance as the positive path, with no
        # physical pause/pullback. This is not a detector-provided label.
        elapsed = offset - self.current_start
        return 80_000. + self.direction * (-120. + .5 * elapsed)

    def contract(self, offset):
        first_open = self.current_start + self.close_relative_seconds - 900
        number = math.floor((offset - first_open) / 900)
        opened = first_open + 900 * number
        # Fixed and known at each synthetic contract opening. Keeping this
        # strike identical across clock controls isolates runway from price.
        strike = 80_000. + self.direction * 60.
        return MarketInfo(f"KXBTC15M-CONSTRUCT-{self.name}-{number}",
            BASE + opened, BASE + opened + 900, "active", target=strike,
            target_source="CONSTRUCT_FIXED_OPENING_STRIKE")

    def quote_values(self, offset):
        values = super().quote_values(offset)
        if not self.quote_only_giveback:
            return values
        elapsed = offset - self.current_start
        # The held side gives back five probability cents over the exact
        # same150–174s interval while BTC keeps advancing. This asks whether
        # price weakness is actually required, independently of a bid dip.
        adjustment = min(.05, max(0., (elapsed - 150.) / 24.) * .05)
        signed = self.direction * adjustment
        yes_bid = round(values["yes_bid"] - signed, 6)
        no_bid = round(values["no_bid"] + signed, 6)
        return {"yes_bid": yes_bid, "yes_ask": round(1. - no_bid, 6),
                "no_bid": no_bid, "no_ask": round(1. - yes_bid, 6)}

    def expectations(self):
        positive = self.close_relative_seconds == 240 and self.current_weakness_path
        return {"source": "AUTHORED_RAW_PRICE_CLOCK_AND_QUOTES_BEFORE_ENGINE_OUTPUT",
            "synthetic": True, "current_leg_start_offset": self.current_start,
            "opening_entry_window_relative": [0, 60],
            "opening_side": "YES" if self.direction == 1 else "NO",
            "required_entry_purpose": "ARC_RETURN",
            "required_entry_scale_family_is_earned": True,
            "normal_contract_seconds": 900, "contract_close_relative_seconds": self.close_relative_seconds,
            "fixed_strike": 80_000. + self.direction * 60.,
            "end_relative_seconds": 216,
            "observed_weakness_window_relative": [150, 210],
            "expected_profitable_interruption": positive,
            "expected_hold_through_end": not positive,
            "allowed_exception_weakness_counts": [1, 2],
            "required_parent_status_at_sale": "ACTIVE",
            "required_exit_reason": "ARC_PROFITABLE_CONTRACT_INTERRUPTION",
            "required_full_remaining_lot_net_positive": True,
            "control": None if positive else "SUFFICIENT_RUNWAY" if self.current_weakness_path
                else "NO_CURRENT_PHYSICAL_WEAKNESS",
            "current_weakness_path": self.current_weakness_path,
            "quote_only_giveback": self.quote_only_giveback,
            "quote_giveback_interval_relative": [150, 174],
            "quote_only_giveback_probability_cents": 5 if self.quote_only_giveback else 0,
            "prior_completed_cycles": self.prior_cycles,
            "reference_leg_seconds": self.leg_seconds,
            "reference_plateau_seconds": self.plateau_seconds,
            "authored_price_knots": list(super().expectations()["authored_signed_price_knots"])
                if self.current_weakness_path else [[0, -120.], [216, -12.]],
            "quote_formula": "Inherited complementary book from current BTC/fixed strike; optional predeclared quote-only giveback",
            "quote_scale": self.quote_scale, "quote_half_spread": self.quote_half_spread,
            "no_official_settlement_needed_before_test_end": True,
            "no_injected_holdings_missions_weakness_or_timing_references": True}
