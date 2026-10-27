from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from strategy_core.tools.base import StrategyTool
from strategy_core.tools.management import (
    floor_policy, opposing_transfer, position_intent,
)
from strategy_core.types import (
    Action,
    Lane,
    MarketSnapshot,
    Side,
    ToolIntent,
)


@dataclass(frozen=True)
class ReleaseConfig:
    structural_size: float = 25.0
    soft_max_price: float = 0.50
    floor_arm_roi: float = 1.0
    floor_trail_fraction: float = 0.10
    floor_min_age_s: float = 30.0
    floor_immediate_arm_roi: float | None = 1.0


@dataclass(frozen=True)
class ReleaseEvidence:
    candidate_side: Side | None = None
    boundary_break: bool = False
    directional_expansion: bool = False
    old_owner_failed_reextension: bool = False
    new_side_residence: bool = False
    first_slowdown_only: bool = False

    @property
    def confirmed(self) -> bool:
        return bool(
            not self.first_slowdown_only
            and self.candidate_side is not None
            and self.boundary_break
            and self.directional_expansion
            and (self.old_owner_failed_reextension or self.new_side_residence)
        )


class ReleaseWatcher(StrategyTool):
    """Universal territory-ending overlay.

    ReleaseWatcher never performs ordinary fades. It observes beside the
    primary tool and emits a HANDOFF relay only when physical transfer evidence
    is affirmative. A legacy release label is not sufficient.
    """

    name = "RELEASE_WATCHER"

    def __init__(
        self,
        *,
        territory_id: str,
        owner_side: Side | None,
        config: ReleaseConfig | None = None,
    ) -> None:
        self.territory_id = territory_id
        self.owner_side = owner_side
        self.config = config or ReleaseConfig()
        self._active = True
        self._evidence = ReleaseEvidence()
        self._current_ticker: str | None = None
        self._open_tickers: set[str] = set()
        self._filled_opportunities: set[tuple[str, str]] = set()
        self._exit_latches: dict[str, str] = {}

    @property
    def active(self) -> bool:
        return self._active

    @property
    def confirmed(self) -> bool:
        return self._confirmed()

    @property
    def evidence(self) -> ReleaseEvidence:
        return self._evidence

    def update_owner_side(
        self,
        side: Side | None,
    ) -> None:
        if side is not None:
            self.owner_side = side

    def update_evidence(
        self,
        evidence: ReleaseEvidence,
    ) -> None:
        self._evidence = evidence

    def _confirmed(self) -> bool:
        return self._evidence.confirmed

    def _wait(
        self,
        snapshot: MarketSnapshot,
        reason: str,
    ) -> ToolIntent:
        return ToolIntent(
            tool=self.name,
            territory_id=self.territory_id,
            lane=Lane.HANDOFF,
            side=self._evidence.candidate_side,
            action=Action.WAIT,
            opportunity_id=None,
            max_price=self.config.soft_max_price,
            size_tier=None,
            reason=reason,
            source_time=snapshot.now_ts,
        )

    def on_activate(
        self,
        snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        return self.on_market_event(snapshot)

    def on_market_event(
        self,
        snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        if not self._active:
            return []
        self._current_ticker = snapshot.ticker

        e = self._evidence
        if e.first_slowdown_only:
            return [
                self._wait(
                    snapshot,
                    "RELEASE_FIRST_SLOWDOWN_IS_WATCH_NOT_HANDOFF",
                )
            ]

        if not self._confirmed():
            return [
                self._wait(
                    snapshot,
                    "RELEASE_WATCHING_FOR_AFFIRMATIVE_TRANSFER",
                )
            ]

        side = e.candidate_side
        assert side is not None
        opportunity_id = f"{self.territory_id}:RELEASE:{side.value}:{snapshot.ticker}"
        if snapshot.ticker in self._open_tickers:
            return [self._wait(snapshot, "RELEASE_POSITION_ALREADY_OPEN")]
        if (snapshot.ticker, opportunity_id) in self._filled_opportunities:
            return [self._wait(snapshot, "RELEASE_OPPORTUNITY_ALREADY_FILLED")]
        ask = snapshot.ask_for(side)
        if ask is None:
            return [
                self._wait(
                    snapshot,
                    "RELEASE_SIDE_ASK_UNAVAILABLE",
                )
            ]

        if ask > self.config.soft_max_price:
            return [
                self._wait(
                    snapshot,
                    "RELEASE_CONFIRMED_BUT_PRICE_ABOVE_SOFT_VALUE",
                )
            ]

        return [
            ToolIntent(
                tool=self.name,
                territory_id=self.territory_id,
                lane=Lane.HANDOFF,
                side=side,
                action=Action.RELAY,
                opportunity_id=opportunity_id,
                max_price=self.config.soft_max_price,
                size_tier=self.config.structural_size,
                reason="RELEASE_CONFIRMED_LEVIATHAN_HANDOFF",
                source_time=snapshot.now_ts,
                expires_when="RELEASE_INVALIDATES_OR_NEXT_TERRITORY_OWNS",
                metadata={
                    "custody": "LEVIATHAN_RELEASE",
                    "old_owner_side": (
                        self.owner_side.value
                        if self.owner_side
                        else None
                    ),
                    "boundary_break": e.boundary_break,
                    "directional_expansion": e.directional_expansion,
                    "old_owner_failed_reextension": (
                        e.old_owner_failed_reextension
                    ),
                    "new_side_residence": e.new_side_residence,
                    "floor_policy": floor_policy(self.config),
                },
            )
        ]

    def mark_entry_filled(
        self, opportunity_id: str, *, ticker: str | None = None,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._filled_opportunities.add((ticker, opportunity_id))
            self._open_tickers.add(ticker)
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
        ticker = str(position.get("ticker") or "")
        if opposing_transfer(position, snapshot):
            self._exit_latches[ticker] = "RELEASE_CONFIRMED_OPPOSING_TRANSFER"
        action = Action.EXIT if ticker in self._exit_latches else Action.HOLD
        reason = self._exit_latches.get(ticker, "RELEASE_STRUCTURAL_CUSTODY_INTACT")
        return [position_intent(
            tool=self.name, territory_id=self.territory_id, lane=Lane.HANDOFF,
            position=position, snapshot=snapshot, action=action, reason=reason,
            config=self.config, metadata={"custody": "LEVIATHAN_RELEASE"},
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
                f"RELEASE_WATCHER_DEACTIVATED:{reason}",
            )
        ]
