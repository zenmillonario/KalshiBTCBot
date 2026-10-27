from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from strategy_core.detectors.release_geometry import (
    ReleaseProbe,
    detect_release_for_owner,
)

from strategy_core.config_loader import (
    ToolConfigBundle,
    load_default_tool_configs,
)
from strategy_core.lane_resolver import LaneResolver
from strategy_core.router import (
    PhysicalEvidence,
    TerritoryDecision,
    TerritoryRouter,
)
from strategy_core.tools.base import StrategyTool
from strategy_core.tools.heist import MarketHeistTool
from strategy_core.tools.mountain import (
    AlternatingMountainTool,
)
from strategy_core.tools.rail import RailTool
from strategy_core.tools.release import (
    ReleaseEvidence,
    ReleaseWatcher,
)
from strategy_core.types import (
    Action,
    MarketSnapshot,
    Side,
    Territory,
    ToolIntent,
)


@dataclass(frozen=True)
class ToolRackShadowResult:
    raw_decision: TerritoryDecision
    owned_territory: Territory
    owned_side: Side | None
    territory_id: str | None
    active_tool: str | None
    active_overlays: tuple[str, ...]
    primary_intents: tuple[ToolIntent, ...]
    overlay_intents: tuple[ToolIntent, ...]
    intents: tuple[ToolIntent, ...]
    ownership_reason: str
    lane_resolution_reason: str
    release_boundary_name: str | None
    release_diagnostics: Mapping[str, Any]


class ToolRackController:
    """Stateful territory ownership + compatible tool overlays.

    This object produces intents only. It has no execution, account, or venue
    order authority. ReleaseWatcher runs beside the primary tool and a
    deterministic LaneResolver handles handoff priority before OneCommander.
    """

    def __init__(
        self,
        router: TerritoryRouter | None = None,
        configs: ToolConfigBundle | None = None,
    ) -> None:
        self.router = router or TerritoryRouter()
        self.configs = configs or load_default_tool_configs()
        self.lane_resolver = LaneResolver()
        self._owned_territory = Territory.UNKNOWN
        self._owned_side: Side | None = None
        self._territory_id: str | None = None
        self._serial = 0
        self._active_tool: StrategyTool | None = None
        self._release_watcher: ReleaseWatcher | None = None

    def _new_territory_id(
        self,
        territory: Territory,
    ) -> str:
        self._serial += 1
        return f"{territory.value}_{self._serial:04d}"

    def _is_rail(
        self,
        territory: Territory,
    ) -> bool:
        return territory in (
            Territory.UP_RAIL,
            Territory.DOWN_RAIL,
        )

    def _supports_release_overlay(
        self,
        territory: Territory,
    ) -> bool:
        return territory in (
            Territory.UP_RAIL,
            Territory.DOWN_RAIL,
            Territory.ALTERNATING_MOUNTAIN,
            Territory.MARKET_HEIST,
        )

    def _activate(
        self,
        decision: TerritoryDecision,
        snapshot: MarketSnapshot,
    ) -> None:
        self._owned_territory = decision.territory
        self._owned_side = decision.side
        self._territory_id = self._new_territory_id(
            decision.territory
        )
        self._active_tool = None
        self._release_watcher = None

        if (
            self._is_rail(decision.territory)
            and decision.side is not None
        ):
            self._active_tool = RailTool(
                territory_id=self._territory_id,
                side=decision.side,
                activated_at=snapshot.now_ts,
                config=self.configs.rail,
            )
        elif (
            decision.territory
            is Territory.ALTERNATING_MOUNTAIN
        ):
            self._active_tool = AlternatingMountainTool(
                territory_id=self._territory_id,
                owner_side=decision.side,
                config=self.configs.mountain,
            )
        elif (
            decision.territory
            is Territory.MARKET_HEIST
        ):
            self._active_tool = MarketHeistTool(
                territory_id=self._territory_id,
                config=self.configs.heist,
            )

        if (
            self._active_tool is not None
            and self._supports_release_overlay(
                decision.territory
            )
        ):
            self._release_watcher = ReleaseWatcher(
                territory_id=self._territory_id,
                owner_side=self._owned_side,
                config=self.configs.release,
            )

    def _deactivate_current(
        self,
        snapshot: MarketSnapshot,
        reason: str,
    ) -> None:
        if self._active_tool is not None:
            list(
                self._active_tool.on_deactivate(
                    snapshot,
                    reason,
                )
            )
        if self._release_watcher is not None:
            list(
                self._release_watcher.on_deactivate(
                    snapshot,
                    reason,
                )
            )
        self._owned_territory = Territory.UNKNOWN
        self._owned_side = None
        self._territory_id = None
        self._active_tool = None
        self._release_watcher = None

    def _resolve_release_evidence(
        self,
        evidence: PhysicalEvidence,
        snapshot: MarketSnapshot,
    ) -> tuple[ReleaseEvidence, str | None, Mapping[str, Any]]:
        probe = snapshot.metadata.get("release_probe")
        if (
            isinstance(probe, ReleaseProbe)
            and self._owned_territory is not Territory.UNKNOWN
        ):
            detection = detect_release_for_owner(
                probe,
                owner_territory=self._owned_territory,
                owner_side=self._owned_side,
            )
            return (
                detection.evidence,
                detection.boundary_name,
                detection.diagnostics,
            )

        fallback = ReleaseEvidence(
            candidate_side=evidence.release_candidate_side,
            boundary_break=evidence.release_boundary_break,
            directional_expansion=evidence.release_directional_expansion,
            old_owner_failed_reextension=(
                evidence.release_old_owner_failed_reextension
            ),
            new_side_residence=evidence.release_new_side_residence,
            first_slowdown_only=evidence.release_first_slowdown_only,
        )
        return (
            fallback,
            "EXPLICIT_TEST_EVIDENCE"
            if any(
                (
                    fallback.candidate_side is not None,
                    fallback.boundary_break,
                    fallback.directional_expansion,
                    fallback.old_owner_failed_reextension,
                    fallback.new_side_residence,
                    fallback.first_slowdown_only,
                )
            )
            else None,
            {"source": "PHYSICAL_EVIDENCE_FIELDS"},
        )

    @staticmethod
    def _release_in_progress(
        release: ReleaseEvidence,
    ) -> bool:
        return bool(
            release.candidate_side is not None
            or release.boundary_break
            or release.directional_expansion
            or release.old_owner_failed_reextension
            or release.new_side_residence
            or release.first_slowdown_only
        )

    def _update_release_watcher(
        self,
        release: ReleaseEvidence,
    ) -> None:
        if self._release_watcher is None:
            return
        self._release_watcher.update_owner_side(
            self._owned_side
        )
        self._release_watcher.update_evidence(release)

    def observe(
        self,
        evidence: PhysicalEvidence,
        snapshot: MarketSnapshot,
    ) -> ToolRackShadowResult:
        raw = self.router.classify(evidence)
        ownership_reason = raw.reason
        (
            release_evidence,
            release_boundary_name,
            release_diagnostics,
        ) = self._resolve_release_evidence(
            evidence,
            snapshot,
        )
        release_in_progress = self._release_in_progress(
            release_evidence
        )

        if self._is_rail(self._owned_territory):
            if (
                evidence.heist_takeover_confirmed
                and raw.territory
                is Territory.MARKET_HEIST
                and not release_in_progress
            ):
                self._deactivate_current(
                    snapshot,
                    "QUALIFIED_HEIST_TAKEOVER",
                )
                self._activate(raw, snapshot)
                ownership_reason = "QUALIFIED_HEIST_TAKEOVER"
            else:
                ownership_reason = (
                    "LATCHED_RAIL_OWNER_UNTIL_RELEASE_OR_CONFIRMED_TERRITORY_TRANSFER"
                )

        elif (
            self._owned_territory
            is Territory.MARKET_HEIST
        ):
            if release_in_progress:
                ownership_reason = (
                    "HEIST_BOX_RETAINS_OWNER_DURING_RELEASE_WATCH"
                )
            elif (
                raw.territory
                is Territory.MARKET_HEIST
            ):
                self._owned_side = raw.side
                ownership_reason = (
                    "HEIST_BOX_REMAINS_OWNER_WHILE_BOUNDED"
                )
            else:
                self._deactivate_current(
                    snapshot,
                    "HEIST_BOX_NO_LONGER_OWNS",
                )
                if (
                    raw.territory
                    is not Territory.UNKNOWN
                ):
                    self._activate(raw, snapshot)

        elif (
            self._owned_territory
            is Territory.ALTERNATING_MOUNTAIN
            and raw.territory
            is Territory.ALTERNATING_MOUNTAIN
        ):
            self._owned_side = raw.side
            if isinstance(
                self._active_tool,
                AlternatingMountainTool,
            ):
                self._active_tool.update_owner_side(
                    raw.side
                )
            ownership_reason = (
                "MOUNTAIN_TERRITORY_PERSISTS_ACROSS_EDGE_RELAYS"
            )

        elif (
            self._owned_territory
            is Territory.ALTERNATING_MOUNTAIN
            and release_in_progress
        ):
            ownership_reason = (
                "MOUNTAIN_RETAINS_OWNER_DURING_RELEASE_WATCH"
            )

        elif (
            raw.territory
            is not self._owned_territory
        ):
            self._deactivate_current(
                snapshot,
                "TERRITORY_CHANGED",
            )
            if (
                raw.territory
                is not Territory.UNKNOWN
            ):
                self._activate(raw, snapshot)

        elif (
            raw.side
            is not self._owned_side
        ):
            self._owned_side = raw.side

        # If a territory was activated on this beat, resolve release again
        # against the newly owned territory before updating its overlay.
        if (
            self._release_watcher is not None
            and snapshot.metadata.get("release_probe") is not None
            and self._owned_territory is not Territory.UNKNOWN
        ):
            (
                release_evidence,
                release_boundary_name,
                release_diagnostics,
            ) = self._resolve_release_evidence(
                evidence,
                snapshot,
            )
        self._update_release_watcher(release_evidence)

        primary_intents: tuple[ToolIntent, ...] = ()
        if self._active_tool is not None:
            primary_intents = tuple(
                self._active_tool.on_market_event(
                    snapshot
                )
            )

        overlay_intents: tuple[ToolIntent, ...] = ()
        if self._release_watcher is not None:
            overlay_intents = tuple(
                self._release_watcher.on_market_event(
                    snapshot
                )
            )

        resolution = self.lane_resolver.resolve(
            primary=primary_intents,
            overlays=overlay_intents,
        )

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
            active_overlays=(
                (self._release_watcher.name,)
                if self._release_watcher
                else ()
            ),
            primary_intents=primary_intents,
            overlay_intents=overlay_intents,
            intents=resolution.intents,
            ownership_reason=ownership_reason,
            lane_resolution_reason=resolution.reason,
            release_boundary_name=release_boundary_name,
            release_diagnostics=release_diagnostics,
        )

    def commit_accepted_intent(
        self,
        intent: ToolIntent,
        snapshot: MarketSnapshot,
    ) -> None:
        """Advance territory state after an actually accepted/committed intent.

        Production integration must call this only after the corresponding
        guarded PAPER transaction commits. Shadow/replay may call it to model
        the same lifecycle.
        """

        if (
            intent.tool == "RELEASE_WATCHER"
            and intent.action is Action.RELAY
            and intent.lane.value == "HANDOFF"
        ):
            self._deactivate_current(
                snapshot,
                "COMMITTED_RELEASE_HANDOFF",
            )

    @property
    def active_rail_tool(
        self,
    ) -> RailTool | None:
        return (
            self._active_tool
            if isinstance(
                self._active_tool,
                RailTool,
            )
            else None
        )

    @property
    def active_mountain_tool(
        self,
    ) -> AlternatingMountainTool | None:
        return (
            self._active_tool
            if isinstance(
                self._active_tool,
                AlternatingMountainTool,
            )
            else None
        )

    @property
    def active_heist_tool(
        self,
    ) -> MarketHeistTool | None:
        return (
            self._active_tool
            if isinstance(
                self._active_tool,
                MarketHeistTool,
            )
            else None
        )
