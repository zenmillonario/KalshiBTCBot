from __future__ import annotations

from dataclasses import dataclass

from strategy_core.types import Action, Lane, ToolIntent


@dataclass(frozen=True)
class LaneResolution:
    intents: tuple[ToolIntent, ...]
    reason: str


class LaneResolver:
    """Deterministic lane arbitration before OneCommander.

    This is not a vote. A confirmed HANDOFF relay has explicit priority over
    stale MAIN/TACTICAL entry intents from the outgoing territory. Otherwise
    the primary tool continues normally.
    """

    def resolve(
        self,
        *,
        primary: tuple[ToolIntent, ...],
        overlays: tuple[ToolIntent, ...],
    ) -> LaneResolution:
        handoffs = tuple(
            intent
            for intent in overlays
            if (
                intent.lane is Lane.HANDOFF
                and intent.action is not Action.WAIT
            )
        )

        if len(handoffs) == 1:
            return LaneResolution(
                handoffs,
                "CONFIRMED_HANDOFF_SUPPRESSES_OUTGOING_TERRITORY_INTENTS",
            )

        if len(handoffs) > 1:
            return LaneResolution(
                handoffs,
                "MULTIPLE_HANDOFF_INTENTS_REQUIRE_COMMANDER_CONFLICT_WAIT",
            )

        primary_actionable = tuple(
            intent
            for intent in primary
            if intent.action is not Action.WAIT
        )
        if primary_actionable:
            return LaneResolution(
                primary_actionable,
                "PRIMARY_TERRITORY_TOOL_CONTINUES",
            )

        if primary:
            return LaneResolution(
                primary,
                "PRIMARY_TOOL_WAIT",
            )

        if overlays:
            return LaneResolution(
                overlays,
                "OVERLAY_WATCH_ONLY",
            )

        return LaneResolution(
            (),
            "NO_TOOL_INTENTS",
        )
