from __future__ import annotations

from dataclasses import dataclass

from strategy_core.router import PhysicalEvidence, TerritoryDecision, TerritoryRouter
from strategy_core.tools.rail import RailTool
from strategy_core.types import MarketSnapshot, Side, Territory, ToolIntent


@dataclass(frozen=True)
class ToolRackShadowResult:
    raw_decision: TerritoryDecision
    owned_territory: Territory
    owned_side: Side | None
    territory_id: str | None
    active_tool: str | None
    intents: tuple[ToolIntent, ...]
    ownership_reason: str


class ToolRackController:
    """Stateful territory ownership + tool activation in SHADOW mode.

    This object produces intents only. It has no execution, account, or order
    authority. Rail ownership is latched until an affirmative handoff.
    """

    def __init__(self, router: TerritoryRouter | None = None) -> None:
        self.router = router or TerritoryRouter()
        self._owned_territory = Territory.UNKNOWN
        self._owned_side: Side | None = None
        self._territory_id: str | None = None
        self._serial = 0
        self._active_tool: RailTool | None = None

    def _new_territory_id(self, territory: Territory) -> str:
        self._serial += 1
        return f"{territory.value}_{self._serial:04d}"

    def _is_rail(self, territory: Territory) -> bool:
        return territory in (Territory.UP_RAIL, Territory.DOWN_RAIL)

    def _activate(
        self,
        decision: TerritoryDecision,
        snapshot: MarketSnapshot,
    ) -> None:
        self._owned_territory = decision.territory
        self._owned_side = decision.side
        self._territory_id = self._new_territory_id(decision.territory)
        self._active_tool = None
        if self._is_rail(decision.territory) and decision.side is not None:
            self._active_tool = RailTool(
                territory_id=self._territory_id,
                side=decision.side,
                activated_at=snapshot.now_ts,
            )

    def _deactivate_current(
        self,
        snapshot: MarketSnapshot,
        reason: str,
    ) -> None:
        if self._active_tool is not None:
            list(self._active_tool.on_deactivate(snapshot, reason))
        self._owned_territory = Territory.UNKNOWN
        self._owned_side = None
        self._territory_id = None
        self._active_tool = None

    def observe(
        self,
        evidence: PhysicalEvidence,
        snapshot: MarketSnapshot,
    ) -> ToolRackShadowResult:
        raw = self.router.classify(evidence)
        ownership_reason = raw.reason

        # Rail is sticky. Raw classifier flicker cannot put the tool down.
        if self._is_rail(self._owned_territory):
            if evidence.release_handoff_confirmed:
                self._deactivate_current(
                    snapshot,
                    "AFFIRMATIVE_RELEASE_HANDOFF",
                )
                # After a proven handoff, the same beat may already provide a
                # qualified new territory (including the opposite Rail).
                if raw.territory is not Territory.UNKNOWN:
                    self._activate(raw, snapshot)
                    ownership_reason = "RELEASE_HANDOFF_TO_NEW_TERRITORY"
                else:
                    ownership_reason = (
                        "RELEASE_HANDOFF_AWAITING_NEXT_TERRITORY"
                    )
            elif (
                evidence.heist_takeover_confirmed
                and raw.territory is Territory.MARKET_HEIST
            ):
                self._deactivate_current(
                    snapshot,
                    "QUALIFIED_HEIST_TAKEOVER",
                )
                self._activate(raw, snapshot)
                ownership_reason = "QUALIFIED_HEIST_TAKEOVER"
            else:
                ownership_reason = (
                    "LATCHED_RAIL_OWNER_UNTIL_AFFIRMATIVE_HANDOFF"
                )
        elif (
            raw.territory is not self._owned_territory
            or raw.side is not self._owned_side
        ):
            self._activate(raw, snapshot)

        intents: tuple[ToolIntent, ...] = ()
        if self._active_tool is not None:
            intents = tuple(self._active_tool.on_market_event(snapshot))

        return ToolRackShadowResult(
            raw_decision=raw,
            owned_territory=self._owned_territory,
            owned_side=self._owned_side,
            territory_id=self._territory_id,
            active_tool=(
                self._active_tool.name
                if self._active_tool
                else None
            ),
            intents=intents,
            ownership_reason=ownership_reason,
        )

    @property
    def active_rail_tool(self) -> RailTool | None:
        return self._active_tool
