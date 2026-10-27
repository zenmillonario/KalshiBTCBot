from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from strategy_core.tools.base import StrategyTool
from strategy_core.tools.management import (
    as_side, floor_policy, opposing_transfer, position_intent, rack_context,
)
from strategy_core.types import (
    Action,
    Lane,
    MarketSnapshot,
    Side,
    ToolIntent,
)


def _side(value: Any) -> Side | None:
    if isinstance(value, Side):
        return value
    if value is None:
        return None
    text = str(value).upper()
    if text == "YES":
        return Side.YES
    if text == "NO":
        return Side.NO
    return None


@dataclass(frozen=True)
class HeistConfig:
    regular_size: float = 10.0
    lean_favored_size: float = 15.0
    soft_max_price: float = 0.50
    late_counter_window_s: float = 60.0
    late_counter_max_ask: float = 0.01
    floor_arm_roi: float = 0.50
    floor_trail_fraction: float = 0.03
    floor_min_age_s: float = 30.0
    floor_immediate_arm_roi: float | None = 1.0


class MarketHeistTool(StrategyTool):
    """Repeated edge-to-edge business inside a genuine compression box."""

    name = "MARKET_HEIST"

    def __init__(
        self,
        *,
        territory_id: str,
        config: HeistConfig | None = None,
    ) -> None:
        self.territory_id = territory_id
        self.config = config or HeistConfig()
        self._active = True
        self._current_ticker: str | None = None
        self._open_tickers: set[str] = set()
        self._filled_opportunities: set[tuple[str, str]] = set()
        self._visit_side: Side | None = None
        self._visit_id: str | None = None
        self._center_since_visit = True
        self._exit_latches: dict[str, str] = {}

    @property
    def active(self) -> bool:
        return self._active

    def _details(
        self,
        snapshot: MarketSnapshot,
    ) -> Mapping[str, Any]:
        raw = snapshot.metadata.get(
            "heist",
            {},
        )
        return (
            raw
            if isinstance(raw, Mapping)
            else {}
        )

    def _wait(
        self,
        snapshot: MarketSnapshot,
        reason: str,
        *,
        side: Side | None = None,
        opportunity_id: str | None = None,
    ) -> ToolIntent:
        return ToolIntent(
            tool=self.name,
            territory_id=self.territory_id,
            lane=Lane.TACTICAL,
            side=side,
            action=Action.WAIT,
            opportunity_id=opportunity_id,
            max_price=self.config.soft_max_price,
            size_tier=None,
            reason=reason,
            source_time=snapshot.now_ts,
        )

    def on_activate(
        self,
        snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        return self.on_market_event(
            snapshot
        )

    def on_market_event(
        self,
        snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        if not self._active:
            return []
        self._current_ticker = snapshot.ticker
        self._filled_opportunities = {
            key for key in self._filled_opportunities
            if key[0] == snapshot.ticker or key[0] in self._open_tickers
        }

        details = self._details(
            snapshot
        )
        if details.get("current_zone") == "CENTER":
            self._center_since_visit = True
        if not details:
            return [
                self._wait(
                    snapshot,
                    "HEIST_EVIDENCE_UNAVAILABLE",
                )
            ]

        if (
            details.get(
                "release_confirmed"
            )
            is True
        ):
            return [
                self._wait(
                    snapshot,
                    "HEIST_RELEASE_CONFIRMED_STOP_FADING_BOX",
                    side=_side(
                        details.get(
                            "release_side"
                        )
                    ),
                )
            ]

        if (
            details.get(
                "qualified_box"
            )
            is not True
        ):
            return [
                self._wait(
                    snapshot,
                    "HEIST_COMPRESSION_UNRESOLVED_WAIT",
                )
            ]

        if snapshot.ticker in self._open_tickers:
            return [
                self._wait(
                    snapshot,
                    "HEIST_POSITION_ALREADY_OPEN",
                )
            ]

        at_lower = (
            details.get(
                "at_lower_edge"
            )
            is True
        )
        at_upper = (
            details.get(
                "at_upper_edge"
            )
            is True
        )

        if at_lower == at_upper:
            return [
                self._wait(
                    snapshot,
                    "HEIST_WAIT_FOR_REAL_OUTER_EDGE",
                )
            ]

        side = (
            Side.YES
            if at_lower
            else Side.NO
        )
        box_id = str(
            details.get("box_id")
            or "BOX"
        )
        visit_id = str(
            details.get("visit_id")
            or f"{snapshot.now_ts:.3f}"
        )
        if details.get("current_zone") in ("UPPER", "LOWER"):
            if (
                self._visit_id is None or side is not self._visit_side
                or self._center_since_visit
            ):
                self._visit_id = visit_id
                self._visit_side = side
                self._center_since_visit = False
            else:
                visit_id = self._visit_id
        # The consumed identity is the physical edge visit, not the estimated
        # box bounds. Small boundary re-estimation cannot mint a duplicate
        # trade at the same visit; center traversal / a genuinely new visit can.
        opportunity_id = (
            f"{self.territory_id}:"
            f"HEIST_VISIT:{visit_id}:{side.value}"
        )

        if (
            (snapshot.ticker, opportunity_id)
            in self._filled_opportunities
        ):
            return [
                self._wait(
                    snapshot,
                    "HEIST_EDGE_VISIT_ALREADY_FILLED",
                    side=side,
                    opportunity_id=opportunity_id,
                )
            ]

        ask = snapshot.ask_for(side)
        if ask is None:
            return [
                self._wait(
                    snapshot,
                    "HEIST_EDGE_ASK_UNAVAILABLE",
                    side=side,
                    opportunity_id=opportunity_id,
                )
            ]

        if (
            900.0 - snapshot.contract_age_s <= self.config.late_counter_window_s
            and ask <= self.config.late_counter_max_ask
        ):
            return [self._wait(
                snapshot, "LATE_COUNTER_PENNY_REQUIRES_CONFIRMED_TRANSFER",
                side=side, opportunity_id=opportunity_id,
            )]

        premium_ok = bool(
            details.get(
                "premium_value_qualified"
            )
            is True
        )
        if (
            ask > self.config.soft_max_price
            and not premium_ok
        ):
            return [
                self._wait(
                    snapshot,
                    "HEIST_EDGE_PRICE_ABOVE_SOFT_VALUE",
                    side=side,
                    opportunity_id=opportunity_id,
                )
            ]

        lean = _side(
            details.get(
                "lean_side"
            )
        )
        aligned = (
            lean is not None
            and lean is side
        )
        size = (
            self.config.lean_favored_size
            if aligned
            else self.config.regular_size
        )
        reason = (
            "HEIST_OUTER_EDGE_ALIGNED_WITH_EMA_LEAN"
            if aligned
            else "HEIST_OUTER_EDGE_TACTICAL_RENTER"
        )

        return [
            ToolIntent(
                tool=self.name,
                territory_id=self.territory_id,
                lane=Lane.TACTICAL,
                side=side,
                action=Action.ENTER,
                opportunity_id=opportunity_id,
                max_price=(
                    None
                    if premium_ok
                    else self.config.soft_max_price
                ),
                size_tier=size,
                reason=reason,
                source_time=snapshot.now_ts,
                expires_when=(
                    "BOX_EDGE_LEAVES_OR_RELEASE_CONFIRMS"
                ),
                metadata={
                    "box_id": box_id,
                    "visit_id": visit_id,
                    "lean_side": (
                        lean.value
                        if lean
                        else None
                    ),
                    "lean_aligned": aligned,
                    "observed_ask": ask,
                    "entry_box_lower": details.get("lower"),
                    "entry_box_upper": details.get("upper"),
                    "entry_edge_tolerance": details.get("edge_tolerance"),
                    "floor_policy": floor_policy(self.config),
                },
            )
        ]

    def mark_entry_filled(
        self,
        opportunity_id: str,
        *, ticker: str | None = None,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._filled_opportunities.add((ticker, opportunity_id))
            self._open_tickers.add(ticker)
            self._exit_latches.pop(ticker, None)

    def mark_position_closed(
        self,
        *, ticker: str | None = None, release_handoff: bool = False,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._open_tickers.discard(ticker)
            self._exit_latches.pop(ticker, None)

    def manage_position(
        self, position: Mapping[str, Any], snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        details = self._details(snapshot)
        ticker = str(position.get("ticker") or "")
        side = as_side(position.get("side"))
        release_side = as_side(rack_context(snapshot).get("confirmed_release_side"))
        action, reason = Action.HOLD, "HEIST_CARRY_TO_OPPOSITE_BOX_EDGE"
        if position.get("ticker") != snapshot.ticker:
            reason = "HEIST_AWAIT_EXACT_CONTRACT_CUSTODY"
        elif opposing_transfer(position, snapshot):
            action, reason = Action.EXIT, "HEIST_CONFIRMED_OPPOSING_RELEASE"
        elif release_side is side and side is not None:
            reason = "HEIST_ALIGNED_RELEASE_TRANSFERS_HIGHER_CUSTODY"
        elif details.get("qualified_box") is True and (
            (side is Side.YES and details.get("at_upper_edge") is True)
            or (side is Side.NO and details.get("at_lower_edge") is True)
        ):
            action, reason = Action.EXIT, "HEIST_OPPOSITE_PHYSICAL_BOX_EDGE"
        if action is Action.EXIT:
            self._exit_latches[ticker] = reason
        if ticker in self._exit_latches:
            action, reason = Action.EXIT, self._exit_latches[ticker]
        return [position_intent(
            tool=self.name, territory_id=self.territory_id, lane=Lane.TACTICAL,
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
            self._wait(
                snapshot,
                f"HEIST_DEACTIVATED:{reason}",
            )
        ]
