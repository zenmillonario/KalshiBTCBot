from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


@dataclass(frozen=True)
class CommanderDecision:
    action: Action
    intent: ToolIntent | None
    reason: str


class OneCommander:
    """Single strategy decision boundary.

    Tools own strategy inside their territory. Commander does not reinterpret
    terrain; it resolves standardized intents and enforces objective safety.
    """

    def decide(
        self,
        intents: tuple[ToolIntent, ...] | list[ToolIntent],
        snapshot: MarketSnapshot,
    ) -> CommanderDecision:
        actionable = [
            intent
            for intent in intents
            if intent.action is not Action.WAIT
        ]

        if not actionable:
            wait_reason = (
                intents[0].reason
                if intents
                else "NO_TOOL_INTENT"
            )
            return CommanderDecision(
                Action.WAIT,
                None,
                wait_reason,
            )

        if len(actionable) > 1:
            return CommanderDecision(
                Action.WAIT,
                None,
                "CONFLICTING_ACTIONABLE_INTENTS_REQUIRE_LANE_RESOLUTION",
            )

        intent = actionable[0]

        if intent.action is Action.HOLD:
            return CommanderDecision(Action.HOLD, intent, "COMMANDER_ACCEPTED_TOOL_CUSTODY")

        if intent.action is Action.EXIT:
            return self._exit_decision(intent, snapshot)

        if not snapshot.quote_current:
            return CommanderDecision(
                Action.WAIT,
                None,
                "OBJECTIVE_QUOTE_STALE",
            )

        if not snapshot.depth_available:
            return CommanderDecision(
                Action.WAIT,
                None,
                "OBJECTIVE_DEPTH_UNAVAILABLE",
            )

        if not snapshot.entry_allowed:
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_ENTRY_NOT_ALLOWED")
        if snapshot.metadata.get("physical_current") is False:
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_PHYSICAL_SOURCE_STALE")

        if (
            intent.action in (
                Action.ENTER,
                Action.RELAY,
            )
            and intent.side is not None
        ):
            ask = snapshot.ask_for(
                intent.side
            )
            if ask is None or not math.isfinite(ask) or not 0 < ask < 1:
                return CommanderDecision(
                    Action.WAIT,
                    None,
                    "OBJECTIVE_EXECUTABLE_ASK_UNAVAILABLE",
                )
            if (
                intent.max_price is not None
                and ask > intent.max_price
            ):
                return CommanderDecision(
                    Action.WAIT,
                    None,
                    "OBJECTIVE_PRICE_MOVED_ABOVE_TOOL_LIMIT",
                )

        return CommanderDecision(
            intent.action,
            intent,
            "COMMANDER_ACCEPTED_TOOL_INTENT",
        )

    @staticmethod
    def _exit_decision(intent: ToolIntent, snapshot: MarketSnapshot) -> CommanderDecision:
        if intent.side is None:
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_HELD_SIDE_MISSING")
        if not snapshot.quote_current:
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_QUOTE_STALE_EXIT_PENDING")
        bid = snapshot.bid_for(intent.side)
        if (not snapshot.can_sell(intent.side) or bid is None or not math.isfinite(bid)
                or not 0 < bid < 1):
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_HELD_SIDE_BID_UNAVAILABLE_EXIT_PENDING")
        return CommanderDecision(Action.EXIT, intent, "COMMANDER_ACCEPTED_EXACT_HELD_SIDE_EXIT")

    def decide_position(
        self, intents: tuple[ToolIntent, ...] | list[ToolIntent], snapshot: MarketSnapshot,
        position: Mapping[str, Any], *, floor_breached: bool = False,
        stop_requested: bool = False,
    ) -> CommanderDecision:
        """The same Commander resolves custody and mandatory objective exits.

        Tools select structural HOLD/EXIT. Already armed floors and an explicit
        operator stop take precedence. Loss alone never suppresses a tool's
        EXIT, and a stale quote never turns that EXIT into a simulated fill.
        """
        side = position.get("side")
        if not isinstance(side, Side):
            side = Side(str(side).upper())
        if position.get("ticker") != snapshot.ticker:
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_HELD_TICKER_MISMATCH")
        if snapshot.now_ts >= float(position["close_ts"]):
            return CommanderDecision(Action.WAIT, None, "EXACT_CONTRACT_AWAITING_OFFICIAL_FINALITY")
        required = floor_breached or bool(position.get("exit_required"))
        if required or stop_requested:
            reason = (str(position.get("exit_reason") or "ALREADY_ARMED_EXECUTABLE_BID_FLOOR")
                      if required else "OPERATOR_PAPER_STOP")
            intent = ToolIntent(tool=str(position["tool"]), territory_id=str(position["territory_id"]),
                lane=Lane(position.get("lane", Lane.MAIN)), side=side, action=Action.EXIT,
                opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                reason=reason, source_time=snapshot.now_ts,
                metadata={"ticker": snapshot.ticker, "objective_exit": True})
            return self._exit_decision(intent, snapshot)
        if (snapshot.metadata.get("physical_current") is False
                and not snapshot.metadata.get("pending_exit_was_previously_observed")):
            return CommanderDecision(Action.HOLD, None, "PHYSICAL_SOURCE_STALE_CUSTODY_UNCHANGED")
        if not intents:
            return CommanderDecision(Action.HOLD, None, "ORIGINAL_TOOL_CUSTODY_UNAVAILABLE")
        if len(intents) != 1 or intents[0].action not in (Action.HOLD, Action.EXIT):
            return CommanderDecision(Action.WAIT, None, "CONFLICTING_POSITION_MANAGEMENT_INTENTS")
        intent = intents[0]
        if intent.side is not side:
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_EXIT_SIDE_DOES_NOT_MATCH_POSITION")
        return self.decide(intents, snapshot)

    def decide_entry(
        self, intents: tuple[ToolIntent, ...] | list[ToolIntent], snapshot: MarketSnapshot,
        positions: Mapping[str, Any],
    ) -> CommanderDecision:
        for position in positions.values():
            ticker = position.get("ticker") if isinstance(position, Mapping) else position.ticker
            if ticker == snapshot.ticker:
                return CommanderDecision(Action.WAIT, None, "CURRENT_CONTRACT_INVENTORY_OWNS_CUSTODY")
        return self.decide(intents, snapshot)
