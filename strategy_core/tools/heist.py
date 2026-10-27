from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from strategy_core.tools.base import StrategyTool
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
        self._position_open = False
        self._filled_opportunities: set[str] = set()

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

        details = self._details(
            snapshot
        )
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

        if self._position_open:
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
        # The consumed identity is the physical edge visit, not the estimated
        # box bounds. Small boundary re-estimation cannot mint a duplicate
        # trade at the same visit; center traversal / a genuinely new visit can.
        opportunity_id = (
            f"{self.territory_id}:"
            f"HEIST_VISIT:{visit_id}:{side.value}"
        )

        if (
            opportunity_id
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
                },
            )
        ]

    def mark_entry_filled(
        self,
        opportunity_id: str,
    ) -> None:
        self._filled_opportunities.add(
            opportunity_id
        )
        self._position_open = True

    def mark_position_closed(
        self,
    ) -> None:
        self._position_open = False

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
