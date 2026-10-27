from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from strategy_core.tools.base import StrategyTool
from strategy_core.tools.management import (
    floor_policy, opposing_transfer, position_intent,
)


@dataclass(frozen=True)
class RailConfig:
    """Rail-only knobs.

    These values deliberately live here so Rail can be tuned without editing
    Mountain, Heist, Commander, or execution code.
    """

    size_tier: float = 25.0
    first_60s_max: float = 0.40
    sec_60_120_max: float = 0.42
    sec_120_240_max: float = 0.44
    later_soft_max: float = 0.50
    activation_window_s: float = 240.0
    reentry_after_exit: bool = True
    floor_arm_roi: float = 1.0
    floor_trail_fraction: float = 0.10
    floor_min_age_s: float = 30.0
    floor_immediate_arm_roi: float | None = 1.0


class RailTool(StrategyTool):
    """Open-ended same-direction Rail participation.

    The Rail tool intentionally has no opposite-fade path. A release/handoff
    overlay is responsible for terminating Rail ownership.
    """

    name = "RAIL"

    def __init__(
        self,
        *,
        territory_id: str,
        side: Side,
        activated_at: float,
        config: RailConfig | None = None,
    ) -> None:
        self.territory_id = territory_id
        self.side = side
        self.activated_at = activated_at
        self.config = config or RailConfig()
        self._active = True
        self._current_ticker: str | None = None
        self._filled_opportunity_ids: set[str] = set()
        self._open_tickers: set[str] = set()
        self._rearm_generations: dict[str, int] = {}
        self._exit_latches: dict[str, str] = {}

    @property
    def active(self) -> bool:
        return self._active

    def _max_price(self, snapshot: MarketSnapshot) -> float:
        # A newly activated Rail gets its own value-discovery window even when
        # activation happens mid-contract. Rollover gets the normal contract
        # opening ladder automatically because contract_age_s resets.
        activation_age = max(0.0, snapshot.now_ts - self.activated_at)
        age = min(snapshot.contract_age_s, activation_age)
        if age < 60:
            return self.config.first_60s_max
        if age < 120:
            return self.config.sec_60_120_max
        if age < 240:
            return self.config.sec_120_240_max
        return self.config.later_soft_max

    def _opportunity_id(self, snapshot: MarketSnapshot) -> str:
        return (
            f"{self.territory_id}:RAIL_VALUE:{snapshot.ticker}:"
            f"REARM{self._rearm_generations.get(snapshot.ticker, 0)}"
        )

    def _wait(
        self,
        snapshot: MarketSnapshot,
        reason: str,
        *,
        max_price: float | None = None,
    ) -> ToolIntent:
        return ToolIntent(
            tool=self.name,
            territory_id=self.territory_id,
            lane=Lane.MAIN,
            side=self.side,
            action=Action.WAIT,
            opportunity_id=self._opportunity_id(snapshot),
            max_price=max_price,
            size_tier=self.config.size_tier,
            reason=reason,
            source_time=snapshot.now_ts,
        )

    def on_activate(self, snapshot: MarketSnapshot) -> Iterable[ToolIntent]:
        self._current_ticker = snapshot.ticker
        return self.on_market_event(snapshot)

    def on_market_event(self, snapshot: MarketSnapshot) -> Iterable[ToolIntent]:
        if not self._active:
            return []

        if self._current_ticker != snapshot.ticker:
            # New Kalshi contract = fresh economic slice of the same physical
            # Rail. It is NOT a new Rail territory.
            self._current_ticker = snapshot.ticker
            self._rearm_generations.setdefault(snapshot.ticker, 0)

        max_price = self._max_price(snapshot)
        opportunity_id = self._opportunity_id(snapshot)

        if snapshot.ticker in self._open_tickers:
            return [
                self._wait(
                    snapshot,
                    "RAIL_POSITION_ALREADY_OPEN",
                    max_price=max_price,
                )
            ]

        if opportunity_id in self._filled_opportunity_ids:
            return [
                self._wait(
                    snapshot,
                    "RAIL_VALUE_OPPORTUNITY_ALREADY_FILLED",
                    max_price=max_price,
                )
            ]

        ask = snapshot.ask_for(self.side)
        if ask is None:
            return [
                self._wait(
                    snapshot,
                    "MAIN_SIDE_ASK_UNAVAILABLE",
                    max_price=max_price,
                )
            ]

        if ask > max_price:
            # Critical doctrine: WAIT does not consume the opportunity.
            return [
                self._wait(
                    snapshot,
                    f"ASK_{ask:.3f}_ABOVE_MAX_{max_price:.3f}",
                    max_price=max_price,
                )
            ]

        return [
            ToolIntent(
                tool=self.name,
                territory_id=self.territory_id,
                lane=Lane.MAIN,
                side=self.side,
                action=Action.ENTER,
                opportunity_id=opportunity_id,
                max_price=max_price,
                size_tier=self.config.size_tier,
                reason="RAIL_MAIN_VALUE",
                source_time=snapshot.now_ts,
                expires_when="RAIL_HANDOFF_OR_VALUE_WINDOW_CHANGE",
                metadata={"observed_ask": ask, "floor_policy": floor_policy(self.config)},
            )
        ]

    def mark_entry_filled(
        self, opportunity_id: str, *, ticker: str | None = None,
    ) -> None:
        self._filled_opportunity_ids.add(opportunity_id)
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._open_tickers.add(ticker)
            self._exit_latches.pop(ticker, None)

    def mark_position_closed(
        self, *, ticker: str | None = None, release_handoff: bool = False,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is None:
            return
        self._open_tickers.discard(ticker)
        self._exit_latches.pop(ticker, None)
        if release_handoff:
            self._active = False
            return
        if self.config.reentry_after_exit:
            # A profit/protection exit does not end the Rail. Rearm a fresh
            # value opportunity immediately. A genuine release is what stops
            # the cycle.
            self._rearm_generations[ticker] = self._rearm_generations.get(ticker, 0) + 1

    def manage_position(
        self, position: Mapping[str, Any], snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        ticker = str(position.get("ticker") or "")
        if opposing_transfer(position, snapshot):
            self._exit_latches[ticker] = "RAIL_CONFIRMED_OPPOSING_RELEASE"
        action = Action.EXIT if ticker in self._exit_latches else Action.HOLD
        reason = self._exit_latches.get(ticker, "RAIL_STRUCTURAL_CUSTODY_INTACT")
        # Quote validity and ticker matching remain independent execution
        # constraints. A structural EXIT stays latched while its quote recovers.
        return [position_intent(
            tool=self.name, territory_id=self.territory_id, lane=Lane.MAIN,
            position=position, snapshot=snapshot, action=action, reason=reason,
            config=self.config,
        )]

    def on_deactivate(
        self,
        snapshot: MarketSnapshot,
        reason: str,
    ) -> Iterable[ToolIntent]:
        self._active = False
        return [
            ToolIntent(
                tool=self.name,
                territory_id=self.territory_id,
                lane=Lane.HANDOFF,
                side=self.side,
                action=Action.WAIT,
                opportunity_id=None,
                max_price=None,
                size_tier=None,
                reason=f"RAIL_DEACTIVATED:{reason}",
                source_time=snapshot.now_ts,
            )
        ]
