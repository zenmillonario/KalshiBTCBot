from __future__ import annotations

from dataclasses import dataclass

from strategy_core.types import Action, Lane, ToolIntent


@dataclass(frozen=True)
class LaneResolution:
    intents: tuple[ToolIntent, ...]
    reason: str


class LaneResolver:
    """Deterministic lane arbitration before OneCommander.

    This is not a vote. Once ReleaseWatcher physically confirms handoff, the
    outgoing primary tool loses entry authority immediately—even when the
    release entry itself must WAIT on value. Before confirmation, primary
    territory behavior continues normally.
    """

    def resolve(
        self,
        *,
        primary: tuple[ToolIntent, ...],
        overlays: tuple[ToolIntent, ...],
        handoff_confirmed: bool = False,
    ) -> LaneResolution:
        handoffs = tuple(
            intent
            for intent in overlays
            if (
                intent.lane is Lane.HANDOFF
                and intent.action is not Action.WAIT
            )
        )

        if handoff_confirmed:
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
            if overlays:
                # Physical handoff is confirmed but the release tool may be
                # waiting on price/depth. The old territory still may not act.
                return LaneResolution(
                    overlays,
                    "CONFIRMED_HANDOFF_VALUE_WAIT_SUPPRESSES_OLD_TERRITORY",
                )
            return LaneResolution(
                (),
                "CONFIRMED_HANDOFF_NO_RELEASE_INTENT",
            )

        if len(handoffs) == 1:
            return LaneResolution(
                handoffs,
                "HANDOFF_INTENT_PRIORITY",
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
