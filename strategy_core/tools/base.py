from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from strategy_core.types import MarketSnapshot, ToolIntent


class StrategyTool(ABC):
    """Small common contract for all territory tools."""

    @abstractmethod
    def on_activate(self, snapshot: MarketSnapshot) -> Iterable[ToolIntent]:
        raise NotImplementedError

    @abstractmethod
    def on_market_event(self, snapshot: MarketSnapshot) -> Iterable[ToolIntent]:
        raise NotImplementedError

    @abstractmethod
    def on_deactivate(self, snapshot: MarketSnapshot, reason: str) -> Iterable[ToolIntent]:
        raise NotImplementedError
