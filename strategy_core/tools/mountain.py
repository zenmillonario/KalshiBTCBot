from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from strategy_core.tools.base import StrategyTool
from strategy_core.tools.management import (
    as_side, entry_metadata, floor_policy, number, opposing_transfer,
    position_intent,
)
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
    late_counter_window_s: float = 60.0
    late_counter_max_ask: float = 0.01
    floor_arm_roi: float = 0.50
    floor_trail_fraction: float = 0.05
    floor_min_age_s: float = 30.0
    floor_immediate_arm_roi: float | None = 1.0


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
        self._current_ticker: str | None = None
        self._open_tickers: set[str] = set()
        self._filled_opportunities: set[tuple[str, str]] = set()
        self._edge_anchor: tuple[str, Side, float, str] | None = None
        self._exit_latches: dict[str, str] = {}

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
        self._current_ticker = snapshot.ticker
        self._filled_opportunities = {
            key for key in self._filled_opportunities
            if key[0] == snapshot.ticker or key[0] in self._open_tickers
        }

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

        if snapshot.ticker in self._open_tickers:
            return [self._wait(snapshot, "MOUNTAIN_POSITION_ALREADY_OPEN")]

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

        # Exact historical negative class: an almost-expired penny counterfade
        # is not a physical handoff. Confirmed transfers use ReleaseWatcher.
        if (
            900.0 - snapshot.contract_age_s <= self.config.late_counter_window_s
            and ask <= self.config.late_counter_max_ask
        ):
            return [self._wait(snapshot, "LATE_COUNTER_PENNY_REQUIRES_CONFIRMED_TRANSFER")]

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

        if quality == "EXCEPTIONAL":
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
        arc_id = str(details.get("current_arc_id") or "")
        extreme = number(details.get("owner_extreme_btc"))
        if arc_id and extreme is not None:
            anchor = self._edge_anchor
            if anchor is None or anchor[:2] != (arc_id, owner):
                self._edge_anchor = (arc_id, owner, extreme, edge_id)
            elif (owner is Side.YES and extreme > anchor[2]) or (
                owner is Side.NO and extreme < anchor[2]
            ):
                self._edge_anchor = (arc_id, owner, extreme, edge_id)
            else:
                # A rolling input tail or equal-price retest may move the
                # detector's timestamp; it cannot renew this physical attempt.
                edge_id = anchor[3]
        opportunity_id = f"{self.territory_id}:MOUNTAIN_EDGE:{edge_id}"
        if (snapshot.ticker, opportunity_id) in self._filled_opportunities:
            return [self._wait(snapshot, "MOUNTAIN_EDGE_ALREADY_FILLED")]

        return [
            ToolIntent(
                tool=self.name,
                territory_id=self.territory_id,
                lane=Lane.MAIN,
                side=entry_side,
                action=Action.RELAY,
                opportunity_id=opportunity_id,
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
                    "entry_arc_id": arc_id or None,
                    "edge_id": edge_id,
                    "owner_extreme_btc": extreme,
                    "edge_tolerance_dollars": number(details.get("edge_tolerance_dollars")),
                    "floor_policy": floor_policy(self.config),
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

    def mark_entry_filled(self, opportunity_id: str, *, ticker: str | None = None) -> None:
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._open_tickers.add(ticker)
            self._filled_opportunities.add((ticker, opportunity_id))
            self._exit_latches.pop(ticker, None)

    def mark_position_closed(
        self, *, ticker: str | None = None, release_handoff: bool = False,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._open_tickers.discard(ticker)
            self._exit_latches.pop(ticker, None)

    def manage_position(
        self, position: Mapping[str, Any], snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        side = as_side(position.get("side"))
        ticker = str(position.get("ticker") or "")
        details = self._details(snapshot)
        entry = entry_metadata(position)
        owner = _side(details.get("owner_side"))
        action, reason = Action.HOLD, "MOUNTAIN_CARRY_LIVING_LEG"
        if position.get("ticker") != snapshot.ticker:
            reason = "MOUNTAIN_AWAIT_EXACT_CONTRACT_CUSTODY"
        elif opposing_transfer(position, snapshot):
            action, reason = Action.EXIT, "MOUNTAIN_CONFIRMED_OPPOSING_RELEASE"
        else:
            entry_owner = as_side(entry.get("owner_side"))
            original_extreme = number(entry.get("owner_extreme_btc"))
            current_extreme = number(details.get("owner_extreme_btc"))
            tolerance = number(entry.get("edge_tolerance_dollars"))
            tolerance = max(0.0, tolerance if tolerance is not None else 0.0)
            same_entry_arc = bool(
                entry.get("entry_arc_id")
                and entry.get("entry_arc_id") == details.get("current_arc_id")
            )
            failed_attempt = bool(
                same_entry_arc and owner is entry_owner and owner is not side
                and original_extreme is not None and current_extreme is not None
                and (
                    (owner is Side.YES and current_extreme > original_extreme + tolerance)
                    or (owner is Side.NO and current_extreme < original_extreme - tolerance)
                )
            )
            if failed_attempt:
                action, reason = Action.EXIT, "MOUNTAIN_ENTRY_EDGE_PHYSICALLY_INVALIDATED"
            elif (
                side is not None and owner is side
                and details.get("mature_edge") is True
                and details.get("edge_window_active", True) is True
                and details.get("strong_active_release") is not True
                and any(details.get(key) is True for key in (
                    "stall", "hesitation", "failed_reextension", "meaningful_retreat"
                ))
            ):
                action, reason = Action.EXIT, "MOUNTAIN_NEXT_MATURE_PHYSICAL_EDGE"
            elif owner is not side:
                reason = "MOUNTAIN_EDGE_AWAITING_NEW_LEG_WITH_ANCHOR_INTACT"
        if action is Action.EXIT:
            self._exit_latches[ticker] = reason
        if ticker in self._exit_latches:
            action, reason = Action.EXIT, self._exit_latches[ticker]
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
            self._wait(
                snapshot,
                f"MOUNTAIN_DEACTIVATED:{reason}",
            )
        ]
