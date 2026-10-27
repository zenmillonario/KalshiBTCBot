from __future__ import annotations

from dataclasses import dataclass

from strategy_core.types import Action, MarketSnapshot, ToolIntent


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
            if ask is None:
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
