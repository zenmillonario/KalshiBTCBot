from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class Side(str, Enum):
    YES = "YES"
    NO = "NO"


class Action(str, Enum):
    ENTER = "ENTER"
    HOLD = "HOLD"
    EXIT = "EXIT"
    RELAY = "RELAY"
    WAIT = "WAIT"


class Lane(str, Enum):
    MAIN = "MAIN"
    TACTICAL = "TACTICAL"
    HANDOFF = "HANDOFF"


class Territory(str, Enum):
    UNKNOWN = "UNKNOWN"
    COMPRESSION_UNRESOLVED = "COMPRESSION_UNRESOLVED"
    ALTERNATING_MOUNTAIN = "ALTERNATING_MOUNTAIN"
    ROLLING_MOUNTAIN = "ROLLING_MOUNTAIN"
    UP_RAIL = "UP_RAIL"
    DOWN_RAIL = "DOWN_RAIL"
    MARKET_HEIST = "MARKET_HEIST"
    RELEASE_TRANSITION = "RELEASE_TRANSITION"


@dataclass(frozen=True)
class MarketSnapshot:
    """Minimal strategy-facing market state.

    Feed transport, account, settlement, journaling, and venue safety remain
    outside the Tool Rack.
    """

    now_ts: float
    ticker: str
    contract_age_s: float
    yes_ask: float | None
    no_ask: float | None
    quote_current: bool = True
    depth_available: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # Exact held-contract bid permissions are independent of entry permission.
    # Missing bid evidence can never authorize an EXIT at an invented price.
    yes_bid: float | None = None
    no_bid: float | None = None
    entry_allowed: bool = True
    yes_sell_allowed: bool = False
    no_sell_allowed: bool = False

    def ask_for(self, side: Side) -> float | None:
        return self.yes_ask if side is Side.YES else self.no_ask

    def bid_for(self, side: Side) -> float | None:
        return self.yes_bid if side is Side.YES else self.no_bid

    def can_sell(self, side: Side) -> bool:
        return self.yes_sell_allowed if side is Side.YES else self.no_sell_allowed


@dataclass(frozen=True)
class ToolIntent:
    tool: str
    territory_id: str
    lane: Lane
    side: Side | None
    action: Action
    opportunity_id: str | None
    max_price: float | None
    size_tier: float | None
    reason: str
    source_time: float
    expires_when: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
