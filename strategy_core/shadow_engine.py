from __future__ import annotations

from dataclasses import asdict
from typing import Any

from strategy_core.commander import OneCommander
from strategy_core.shadow_frame import ShadowFrame
from strategy_core.tool_rack import ToolRackController


class ToolRackShadowEngine:
    """Read-only Tool Rack evaluator.

    Produces auditable territory/tool/Commander output. It has no executor and
    cannot place or book an order.
    """

    def __init__(self) -> None:
        self.rack = ToolRackController()
        self.commander = OneCommander()

    def evaluate(
        self,
        frame: ShadowFrame,
    ) -> dict[str, Any]:
        rack_result = self.rack.observe(
            frame.evidence,
            frame.snapshot,
        )
        decision = self.commander.decide(
            rack_result.intents,
            frame.snapshot,
        )

        intent = decision.intent
        return {
            "now_ts": frame.snapshot.now_ts,
            "ticker": frame.snapshot.ticker,
            "raw_territory": (
                rack_result.raw_decision.territory.value
            ),
            "raw_side": (
                rack_result.raw_decision.side.value
                if rack_result.raw_decision.side
                else None
            ),
            "owned_territory": (
                rack_result.owned_territory.value
            ),
            "owned_side": (
                rack_result.owned_side.value
                if rack_result.owned_side
                else None
            ),
            "territory_id": rack_result.territory_id,
            "active_tool": rack_result.active_tool,
            "active_overlays": list(
                rack_result.active_overlays
            ),
            "ownership_reason": (
                rack_result.ownership_reason
            ),
            "lane_resolution_reason": (
                rack_result.lane_resolution_reason
            ),
            "release_boundary_name": (
                rack_result.release_boundary_name
            ),
            "release_diagnostics": dict(
                rack_result.release_diagnostics
            ),
            "handoff_confirmed": rack_result.handoff_confirmed,
            "release_transition_pending": (
                rack_result.release_transition_pending
            ),
            "primary_intents": [
                asdict(intent_)
                for intent_
                in rack_result.primary_intents
            ],
            "overlay_intents": [
                asdict(intent_)
                for intent_
                in rack_result.overlay_intents
            ],
            "resolved_intents": [
                asdict(intent_)
                for intent_
                in rack_result.intents
            ],
            "commander_action": (
                decision.action.value
            ),
            "commander_reason": decision.reason,
            "accepted_tool": (
                intent.tool
                if intent
                else None
            ),
            "accepted_side": (
                intent.side.value
                if intent and intent.side
                else None
            ),
            "accepted_opportunity_id": (
                intent.opportunity_id
                if intent
                else None
            ),
            "accepted_max_price": (
                intent.max_price
                if intent
                else None
            ),
            "accepted_observed_ask": (
                frame.snapshot.ask_for(intent.side)
                if intent and intent.side
                else None
            ),
        }
