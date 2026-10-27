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


def _side(
    value: Any,
) -> Side | None:
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


def _opposite(
    side: Side | None,
) -> Side | None:
    if side is Side.YES:
        return Side.NO
    if side is Side.NO:
        return Side.YES
    return None


@dataclass(frozen=True)
class MountainConfig:
    regular_size: float = 10.0
    a_plus_size: float = 15.0
    exceptional_size: float = 25.0
    soft_max_price: float = 0.50


class AlternatingMountainTool(
    StrategyTool
):
    """PID19420-style clean Mountain hard relay.

    The tool does not buy the middle. It waits for a mature physical extreme,
    then uses stall/hesitation/failed re-extension/retreat to relay into the
    next EMA9 leg before a perfect visible curl is required.
    """

    name = "ALTERNATING_MOUNTAIN"

    def __init__(
        self,
        *,
        territory_id: str,
        owner_side: Side | None,
        config: MountainConfig | None = None,
    ) -> None:
        self.territory_id = territory_id
        self.owner_side = owner_side
        self.config = (
            config
            or MountainConfig()
        )
        self._active = True

    @property
    def active(self) -> bool:
        return self._active

    def update_owner_side(
        self,
        side: Side | None,
    ) -> None:
        if side is not None:
            self.owner_side = side

    def _details(
        self,
        snapshot: MarketSnapshot,
    ) -> Mapping[str, Any]:
        raw = snapshot.metadata.get(
            "mountain",
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
    ) -> ToolIntent:
        return ToolIntent(
            tool=self.name,
            territory_id=self.territory_id,
            lane=Lane.MAIN,
            side=_opposite(
                self.owner_side
            ),
            action=Action.WAIT,
            opportunity_id=None,
            max_price=(
                self.config.soft_max_price
            ),
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
        owner = (
            _side(
                details.get(
                    "owner_side"
                )
            )
            or self.owner_side
        )
        self.update_owner_side(
            owner
        )
        entry_side = _opposite(
            owner
        )

        if (
            owner is None
            or entry_side is None
        ):
            return [
                self._wait(
                    snapshot,
                    "MOUNTAIN_OWNER_SIDE_UNAVAILABLE",
                )
            ]

        if not details:
            return [
                self._wait(
                    snapshot,
                    "MOUNTAIN_EDGE_EVIDENCE_UNAVAILABLE",
                )
            ]

        if (
            details.get(
                "strong_active_release"
            )
            is True
        ):
            return [
                self._wait(
                    snapshot,
                    "MOUNTAIN_EDGE_DEFER_ACTIVE_RELEASE",
                )
            ]

        if (
            details.get(
                "mature_edge"
            )
            is not True
        ):
            return [
                self._wait(
                    snapshot,
                    "MOUNTAIN_WAIT_FOR_MATURE_EDGE_NEVER_MIDDLE",
                )
            ]

        if (
            details.get(
                "edge_window_active",
                True,
            )
            is not True
        ):
            return [
                self._wait(
                    snapshot,
                    "MOUNTAIN_EDGE_WINDOW_NOT_ACTIVE",
                )
            ]

        terminal = bool(
            details.get("stall") is True
            or details.get(
                "hesitation"
            )
            is True
            or details.get(
                "failed_reextension"
            )
            is True
            or details.get(
                "meaningful_retreat"
            )
            is True
        )
        if not terminal:
            return [
                self._wait(
                    snapshot,
                    "MOUNTAIN_EDGE_WAIT_FOR_STALL_OR_FAILED_EXTENSION",
                )
            ]

        ask = snapshot.ask_for(
            entry_side
        )
        if ask is None:
            return [
                self._wait(
                    snapshot,
                    "MOUNTAIN_ENTRY_ASK_UNAVAILABLE",
                )
            ]

        premium_ok = bool(
            details.get(
                "premium_value_qualified"
            )
            is True
        )
        if (
            ask
            > self.config.soft_max_price
            and not premium_ok
        ):
            return [
                self._wait(
                    snapshot,
                    "MOUNTAIN_EDGE_PRICE_ABOVE_SOFT_VALUE",
                )
            ]

        quality = str(
            details.get("quality")
            or "REGULAR"
        ).upper()

        if (
            ask < 0.20
            or quality == "EXCEPTIONAL"
        ):
            size = (
                self.config.exceptional_size
            )
        elif quality in (
            "A_PLUS",
            "A+",
        ):
            size = (
                self.config.a_plus_size
            )
        else:
            size = (
                self.config.regular_size
            )

        edge_id = str(
            details.get("edge_id")
            or (
                f"{snapshot.ticker}:"
                f"{snapshot.now_ts:.3f}"
            )
        )

        return [
            ToolIntent(
                tool=self.name,
                territory_id=self.territory_id,
                lane=Lane.MAIN,
                side=entry_side,
                action=Action.RELAY,
                opportunity_id=(
                    f"{self.territory_id}:"
                    f"MOUNTAIN_EDGE:{edge_id}"
                ),
                max_price=(
                    None
                    if premium_ok
                    else self.config.soft_max_price
                ),
                size_tier=size,
                reason=(
                    "MOUNTAIN_MATURE_EDGE_HARD_RELAY"
                ),
                source_time=snapshot.now_ts,
                expires_when=(
                    "EDGE_WINDOW_ENDS_OR_ACTIVE_RELEASE_RESUMES"
                ),
                metadata={
                    "owner_side": owner.value,
                    "observed_ask": ask,
                    "terminal_evidence": {
                        "stall": bool(
                            details.get(
                                "stall"
                            )
                        ),
                        "hesitation": bool(
                            details.get(
                                "hesitation"
                            )
                        ),
                        "failed_reextension": bool(
                            details.get(
                                "failed_reextension"
                            )
                        ),
                        "meaningful_retreat": bool(
                            details.get(
                                "meaningful_retreat"
                            )
                        ),
                    },
                },
            )
        ]

    def on_deactivate(
        self,
        snapshot: MarketSnapshot,
        reason: str,
    ) -> Iterable[ToolIntent]:
        self._active = False
        return [
            self._wait(
                snapshot,
                f"MOUNTAIN_DEACTIVATED:{reason}",
            )
        ]
