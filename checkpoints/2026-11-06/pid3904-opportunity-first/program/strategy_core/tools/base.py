from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from strategy_core.types import MarketSnapshot, ToolIntent


class StrategyTool(ABC):
    """Small common contract for all territory tools."""

    def sync_tactical_inventory(self, *, ticker: str, present: bool) -> None:
        """Project exact controller custody into a tool's local entry slot.

        Recovery detachment is not an economic close and never consumes or
        renews an opportunity. The controller counts all remaining active lots
        before projecting this flag, so one lot cannot clear another's slot.
        """
        open_tickers = getattr(self, "_open_tickers", None)
        if open_tickers is not None:
            if present:
                open_tickers.add(ticker)
            else:
                open_tickers.discard(ticker)

    def detach_position_custody(self, *, ticker: str, opportunity_id: str) -> None:
        self.sync_tactical_inventory(ticker=ticker, present=False)

    def recover_position_custody(self, *, ticker: str, opportunity_id: str) -> None:
        self.sync_tactical_inventory(ticker=ticker, present=True)
        # Only a Commander-approved supported recovery invokes this hook.
        # Immutable objective floor state remains in the execution ledger.
        latches = getattr(self, "_exit_latches", None)
        if latches is not None:
            latches.pop(opportunity_id, None)

    @abstractmethod
    def on_activate(self, snapshot: MarketSnapshot) -> Iterable[ToolIntent]:
        raise NotImplementedError

    @abstractmethod
    def on_market_event(self, snapshot: MarketSnapshot) -> Iterable[ToolIntent]:
        raise NotImplementedError

    @abstractmethod
    def on_deactivate(self, snapshot: MarketSnapshot, reason: str) -> Iterable[ToolIntent]:
        raise NotImplementedError
