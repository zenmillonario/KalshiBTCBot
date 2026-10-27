from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Mapping

from strategy_core.config_loader import (
    ToolConfigBundle,
    load_default_tool_configs,
)
from strategy_core.detectors.release_geometry import (
    ReleaseProbe,
    detect_release_for_owner,
)
from strategy_core.lane_resolver import LaneResolver
from strategy_core.router import (
    PhysicalEvidence,
    TerritoryDecision,
    TerritoryRouter,
)
from strategy_core.tools.base import StrategyTool
from strategy_core.tools.heist import MarketHeistTool
from strategy_core.tools.mountain import AlternatingMountainTool
from strategy_core.tools.rail import RailTool
from strategy_core.tools.release import (
    ReleaseEvidence,
    ReleaseWatcher,
)
from strategy_core.tools.management import as_side, number
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
    handoff_confirmed: bool
    release_transition_pending: bool


class ToolRackController:
    """Stateful territory ownership + compatible tool overlays.

    Territory Router classifies. One primary tool owns its lane. ReleaseWatcher
    observes beside it. A confirmed release suppresses the old tool immediately
    and moves the rack through RELEASE_TRANSITION before the next tool acquires.

    This controller produces intents only. It has no account, PAPER execution,
    or venue-order authority.
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

        self._pending_release_transition: Side | None = None
        self._release_from_side: Side | None = None
        self._release_from_territory: Territory | None = None
        # References to retired tools exist only while their exact PAPER
        # position remains open; closing custody removes both maps' entries.
        self._filled_tools: dict[tuple[str, str, str], StrategyTool] = {}
        self._custody_tools: dict[tuple[str, str, str], StrategyTool] = {}
        self._last_result: ToolRackShadowResult | None = None
        self._last_snapshot_ts: float | None = None
        self._heist_owner_bounds: tuple[float, float, float] | None = None

    def _pin_heist_owner_bounds(self, snapshot: MarketSnapshot) -> None:
        """Capture one qualified physical box for this ownership chapter.

        Rolling candidate windows may refine their own measurement, but cannot
        move the outgoing owner's release boundary with an escaping price.
        """
        if self._heist_owner_bounds is not None:
            return
        details = snapshot.metadata.get("heist")
        if not isinstance(details, Mapping) or details.get("qualified_box") is not True:
            return
        bounds = tuple(number(details.get(key)) for key in ("lower", "upper", "edge_tolerance"))
        if any(value is None or not math.isfinite(value) for value in bounds):
            return
        lower, upper, tolerance = bounds
        assert lower is not None and upper is not None and tolerance is not None
        if lower < upper and tolerance >= 0:
            self._heist_owner_bounds = (lower, upper, tolerance)

    def _new_territory_id(self, territory: Territory) -> str:
        self._serial += 1
        return f"{territory.value}_{self._serial:04d}"

    @staticmethod
    def _is_rail(territory: Territory) -> bool:
        return territory in (Territory.UP_RAIL, Territory.DOWN_RAIL)

    @staticmethod
    def _supports_release_overlay(territory: Territory) -> bool:
        return territory in (
            Territory.UP_RAIL,
            Territory.DOWN_RAIL,
            Territory.ALTERNATING_MOUNTAIN,
            Territory.MARKET_HEIST,
        )

    @staticmethod
    def _supported_primary_territory(territory: Territory) -> bool:
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
        self._territory_id = self._new_territory_id(decision.territory)
        self._active_tool = None
        self._release_watcher = None
        self._heist_owner_bounds = None

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
        elif decision.territory is Territory.ALTERNATING_MOUNTAIN:
            self._active_tool = AlternatingMountainTool(
                territory_id=self._territory_id,
                owner_side=decision.side,
                config=self.configs.mountain,
            )
        elif decision.territory is Territory.MARKET_HEIST:
            self._pin_heist_owner_bounds(snapshot)
            self._active_tool = MarketHeistTool(
                territory_id=self._territory_id,
                config=self.configs.heist,
            )

        if (
            self._active_tool is not None
            and self._supports_release_overlay(decision.territory)
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
            list(self._active_tool.on_deactivate(snapshot, reason))
        if self._release_watcher is not None:
            list(self._release_watcher.on_deactivate(snapshot, reason))

        self._owned_territory = Territory.UNKNOWN
        self._owned_side = None
        self._territory_id = None
        self._active_tool = None
        self._release_watcher = None
        self._heist_owner_bounds = None

    def _begin_release_transition(
        self,
        snapshot: MarketSnapshot,
    ) -> None:
        side = self._pending_release_transition
        if side is None:
            return

        if self._active_tool is not None:
            list(
                self._active_tool.on_deactivate(
                    snapshot,
                    "PHYSICAL_RELEASE_CONFIRMED",
                )
            )
        self._active_tool = None

        if (
            self._owned_territory is Territory.RELEASE_TRANSITION
            and self._release_watcher is not None
        ):
            # A failed release can itself hand off. Preserve the immediately
            # outgoing direction as ancestry for the newly confirmed transfer.
            self._release_watcher.update_owner_side(self._owned_side)

        # Keep the existing ReleaseWatcher alive through transitional custody.
        # Its owner_side remains the outgoing side for audit/ancestry.
        self._owned_territory = Territory.RELEASE_TRANSITION
        self._owned_side = side
        self._territory_id = self._new_territory_id(
            Territory.RELEASE_TRANSITION
        )
        self._pending_release_transition = None
        self._heist_owner_bounds = None

    def _resolve_release_evidence(
        self,
        evidence: PhysicalEvidence,
        snapshot: MarketSnapshot,
    ) -> tuple[ReleaseEvidence, str | None, Mapping[str, Any]]:
        if (
            self._owned_territory is Territory.RELEASE_TRANSITION
            and self._release_watcher is not None
        ):
            probe = snapshot.metadata.get("release_probe")
            if isinstance(probe, ReleaseProbe):
                reversal = detect_release_for_owner(
                    probe, owner_territory=Territory.RELEASE_TRANSITION,
                    owner_side=self._owned_side,
                    config=self.configs.release_detector,
                )
                if reversal.evidence.confirmed:
                    return reversal.evidence, reversal.boundary_name, reversal.diagnostics
            return (
                self._release_watcher.evidence,
                "RELEASE_TRANSITION_LATCHED",
                {
                    "source": "LATCHED_CONFIRMED_RELEASE",
                    "from_territory": (
                        self._release_from_territory.value
                        if self._release_from_territory
                        else None
                    ),
                    "from_side": (
                        self._release_from_side.value
                        if self._release_from_side
                        else None
                    ),
                },
            )

        probe = snapshot.metadata.get("release_probe")
        if (
            isinstance(probe, ReleaseProbe)
            and self._owned_territory is not Territory.UNKNOWN
        ):
            if self._owned_territory is Territory.MARKET_HEIST:
                # Incomplete startup fixtures can acquire the owner before
                # bounds arrive. Pin once on the first qualified observation.
                self._pin_heist_owner_bounds(snapshot)
                if self._heist_owner_bounds is not None:
                    lower, upper, tolerance = self._heist_owner_bounds
                    probe = replace(probe, heist_lower=lower, heist_upper=upper,
                                    heist_edge_tolerance=tolerance)
            detection = detect_release_for_owner(
                probe,
                owner_territory=self._owned_territory,
                owner_side=self._owned_side,
                config=self.configs.release_detector,
            )
            return (
                detection.evidence,
                detection.boundary_name,
                {
                    **detection.diagnostics,
                    **({"owner_box_lower": self._heist_owner_bounds[0],
                        "owner_box_upper": self._heist_owner_bounds[1],
                        "owner_box_edge_tolerance": self._heist_owner_bounds[2],
                        "owner_box_boundary_pinned": True}
                       if self._owned_territory is Territory.MARKET_HEIST
                       and self._heist_owner_bounds is not None else {}),
                },
            )

        # Explicit fields are retained for deterministic unit fixtures only.
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
        any_fallback = any(
            (
                fallback.candidate_side is not None,
                fallback.boundary_break,
                fallback.directional_expansion,
                fallback.old_owner_failed_reextension,
                fallback.new_side_residence,
                fallback.first_slowdown_only,
            )
        )
        return (
            fallback,
            "EXPLICIT_TEST_EVIDENCE" if any_fallback else None,
            {"source": "PHYSICAL_EVIDENCE_FIELDS"},
        )

    @staticmethod
    def _release_in_progress(release: ReleaseEvidence) -> bool:
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

        # During RELEASE_TRANSITION keep the outgoing owner recorded in the
        # watcher instead of rewriting ancestry to the incoming side.
        if self._owned_territory is not Territory.RELEASE_TRANSITION:
            self._release_watcher.update_owner_side(self._owned_side)
        self._release_watcher.update_evidence(release)

    def _transition_can_accept(
        self,
        raw: TerritoryDecision,
    ) -> bool:
        if not self._supported_primary_territory(raw.territory):
            return False
        # A directionless classifier does not complete a directional handoff.
        # Keep its confirmed incoming side until an actual same-side territory
        # is established; neutral flicker cannot erase release custody.
        return raw.side is not None and raw.side is self._owned_side

    def observe(
        self,
        evidence: PhysicalEvidence,
        snapshot: MarketSnapshot,
    ) -> ToolRackShadowResult:
        # A physical handoff confirmed on the prior beat retires the old primary
        # before any new raw territory is considered.
        if self._pending_release_transition is not None:
            self._begin_release_transition(snapshot)

        territory_id_before = self._territory_id
        raw = self.router.classify(evidence)
        ownership_reason = raw.reason

        (
            release_evidence,
            release_boundary_name,
            release_diagnostics,
        ) = self._resolve_release_evidence(evidence, snapshot)
        release_in_progress = self._release_in_progress(release_evidence)
        mountain_metadata = snapshot.metadata.get("mountain")
        physical_mountain_side = (
            as_side(mountain_metadata.get("owner_side"))
            if isinstance(mountain_metadata, Mapping) else None
        )

        if self._owned_territory is Territory.RELEASE_TRANSITION:
            if self._transition_can_accept(raw):
                self._deactivate_current(
                    snapshot,
                    "RELEASE_TRANSITION_COMPLETE",
                )
                self._activate(raw, snapshot)
                ownership_reason = "RELEASE_TRANSITION_TO_NEW_TERRITORY"
            else:
                ownership_reason = (
                    "RELEASE_TRANSITION_AWAITING_NEXT_TOOL_TERRITORY"
                )

        elif (
            self._owned_territory in (
                Territory.ALTERNATING_MOUNTAIN, Territory.MARKET_HEIST,
            )
            and self._is_rail(raw.territory)
            and raw.side is not None
            and (
                self._owned_side is None or raw.side is self._owned_side
                or (
                    self._owned_territory is Territory.ALTERNATING_MOUNTAIN
                    and raw.side is physical_mountain_side
                )
            )
            and not release_evidence.confirmed
        ):
            # A WATCH is advisory preparation, not a veto over same-direction
            # qualified Rail. Genuine opposite transfer still outranks this.
            reason = (
                "MOUNTAIN_GRADUATED_TO_SAME_DIRECTION_RAIL"
                if self._owned_territory is Territory.ALTERNATING_MOUNTAIN
                else "QUALIFIED_RAIL_REPLACES_SAME_DIRECTION_HEIST"
            )
            self._deactivate_current(snapshot, reason)
            self._activate(raw, snapshot)
            ownership_reason = reason

        elif self._is_rail(self._owned_territory):
            if (
                evidence.heist_takeover_confirmed
                and raw.territory is Territory.MARKET_HEIST
                and not release_in_progress
            ):
                self._deactivate_current(snapshot, "QUALIFIED_HEIST_TAKEOVER")
                self._activate(raw, snapshot)
                ownership_reason = "QUALIFIED_HEIST_TAKEOVER"
            else:
                ownership_reason = (
                    "LATCHED_RAIL_OWNER_UNTIL_RELEASE_OR_CONFIRMED_TERRITORY_TRANSFER"
                )

        elif self._owned_territory is Territory.MARKET_HEIST:
            if release_in_progress:
                ownership_reason = (
                    "HEIST_BOX_RETAINS_OWNER_DURING_RELEASE_WATCH"
                )
            elif raw.territory is Territory.MARKET_HEIST:
                if raw.side is not None:
                    self._owned_side = raw.side
                ownership_reason = "HEIST_BOX_REMAINS_OWNER_WHILE_BOUNDED"
            else:
                # A raw Mountain/UNKNOWN/rolling label cannot silently steal a
                # qualified Heist box. The box remains owner until the universal
                # release protocol proves physical escape/transfer.
                ownership_reason = (
                    "HEIST_OWNER_PERSISTS_UNTIL_RELEASE_TRANSFER"
                )

        elif self._owned_territory is Territory.ALTERNATING_MOUNTAIN:
            if release_in_progress:
                ownership_reason = (
                    "MOUNTAIN_RETAINS_OWNER_DURING_RELEASE_WATCH"
                )
            elif raw.territory is Territory.ALTERNATING_MOUNTAIN:
                if raw.side is not None:
                    self._owned_side = raw.side
                if isinstance(self._active_tool, AlternatingMountainTool):
                    self._active_tool.update_owner_side(raw.side)
                ownership_reason = (
                    "MOUNTAIN_TERRITORY_PERSISTS_ACROSS_EDGE_RELAYS"
                )
            else:
                # Heist/rolling/unknown classifier flicker cannot steal the
                # living EMA9 Mountain. Only a real release/transfer or a
                # same-direction Rail graduation changes ownership.
                ownership_reason = (
                    "MOUNTAIN_OWNER_PERSISTS_UNTIL_EDGE_RELAY_OR_RELEASE"
                )

        elif raw.territory is not self._owned_territory:
            self._deactivate_current(snapshot, "TERRITORY_CHANGED")
            if self._supported_primary_territory(raw.territory):
                self._activate(raw, snapshot)

        elif raw.side is not self._owned_side:
            self._owned_side = raw.side

        # If a new territory was activated this beat, resolve release once
        # against that new owner. Side changes within the same territory do not
        # rewrite the old owner mid-beat.
        if (
            self._release_watcher is not None
            and self._owned_territory is not Territory.RELEASE_TRANSITION
            and self._territory_id != territory_id_before
        ):
            (
                release_evidence,
                release_boundary_name,
                release_diagnostics,
            ) = self._resolve_release_evidence(evidence, snapshot)

        self._update_release_watcher(release_evidence)

        primary_intents: tuple[ToolIntent, ...] = ()
        if self._active_tool is not None:
            primary_intents = tuple(
                self._active_tool.on_market_event(snapshot)
            )

        overlay_intents: tuple[ToolIntent, ...] = ()
        handoff_confirmed = False
        if self._release_watcher is not None:
            overlay_intents = tuple(
                self._release_watcher.on_market_event(snapshot)
            )
            handoff_confirmed = self._release_watcher.confirmed

        resolution = self.lane_resolver.resolve(
            primary=primary_intents,
            overlays=overlay_intents,
            handoff_confirmed=handoff_confirmed,
        )

        if (
            handoff_confirmed
            and (
                self._owned_territory is not Territory.RELEASE_TRANSITION
                or release_evidence.candidate_side is not self._owned_side
            )
            and release_evidence.candidate_side is not None
        ):
            self._pending_release_transition = release_evidence.candidate_side
            self._release_from_side = self._owned_side
            self._release_from_territory = self._owned_territory

        result = ToolRackShadowResult(
            raw_decision=raw,
            owned_territory=self._owned_territory,
            owned_side=self._owned_side,
            territory_id=self._territory_id,
            active_tool=(
                self._active_tool.name
                if self._active_tool is not None
                else None
            ),
            active_overlays=(
                (self._release_watcher.name,)
                if self._release_watcher is not None
                else ()
            ),
            primary_intents=primary_intents,
            overlay_intents=overlay_intents,
            intents=resolution.intents,
            ownership_reason=ownership_reason,
            lane_resolution_reason=resolution.reason,
            release_boundary_name=release_boundary_name,
            release_diagnostics=release_diagnostics,
            handoff_confirmed=handoff_confirmed,
            release_transition_pending=(
                self._pending_release_transition is not None
            ),
        )
        self._last_result = result
        self._last_snapshot_ts = snapshot.now_ts
        return result

    def commit_accepted_intent(
        self,
        intent: ToolIntent,
        snapshot: MarketSnapshot,
    ) -> None:
        """Record a committed PAPER fill; observing an intent never consumes it."""
        if intent.action not in (Action.ENTER, Action.RELAY) or not intent.opportunity_id:
            return
        tool = next((candidate for candidate in (self._active_tool, self._release_watcher)
                     if candidate is not None and candidate.name == intent.tool
                     and candidate.territory_id == intent.territory_id), None)
        if tool is None:
            raise ValueError("Committed intent has no exact tool/territory owner")
        tool.mark_entry_filled(intent.opportunity_id, ticker=snapshot.ticker)
        key = (snapshot.ticker, intent.territory_id, intent.opportunity_id)
        self._filled_tools[key] = tool

    def mark_position_closed(
        self, *, ticker: str, territory_id: str,
        opportunity_id: str | None = None, release_handoff: bool = False,
    ) -> None:
        """Close exact custody; old-contract finality cannot rearm a new slice."""
        keys = [key for key in self._filled_tools
                if key[0] == ticker and key[1] == territory_id
                and (opportunity_id is None or key[2] == opportunity_id)]
        for key in keys:
            origin = self._filled_tools.pop(key)
            custody = self._custody_tools.pop(key, None)
            for tool in {id(tool): tool for tool in (origin, custody) if tool is not None}.values():
                tool.mark_position_closed(ticker=ticker, release_handoff=release_handoff)

    def manage_position(
        self, position: Mapping[str, Any], snapshot: MarketSnapshot,
    ) -> tuple[ToolIntent, ...]:
        """Route held custody to its tool; Commander remains the one decider."""
        key = (str(position.get("ticker") or ""),
               str(position.get("territory_id") or ""),
               str(position.get("opportunity_id") or ""))
        origin = self._filled_tools.get(key)
        if origin is None:
            return ()
        manager = self._custody_tools.get(key, origin)
        context: dict[str, Any] = {}
        result = self._last_result if self._last_snapshot_ts == snapshot.now_ts else None
        side = as_side(position.get("side"))
        if result is not None:
            release_side = next((intent.side for intent in result.overlay_intents
                                 if result.handoff_confirmed and intent.side is not None), None)
            context = {
                "owned_territory": result.owned_territory.value,
                "owned_side": result.owned_side.value if result.owned_side else None,
                "raw_territory": result.raw_decision.territory.value,
                "confirmed_release_side": release_side.value if release_side else None,
            }
            next_manager = manager
            if release_side is side and side is not None and self._release_watcher is not None:
                next_manager = self._release_watcher
            elif self.active_rail_tool is not None and self.active_rail_tool.side is side:
                next_manager = self.active_rail_tool
            if next_manager is not manager:
                # Adopt existing inventory without emitting another entry or
                # changing its original economic/physical entry evidence.
                next_manager.mark_entry_filled(key[2], ticker=key[0])
                self._custody_tools[key] = next_manager
                manager = next_manager
        managed_snapshot = replace(snapshot, metadata={**snapshot.metadata, "tool_rack": context})
        return tuple(manager.manage_position(position, managed_snapshot))

    @property
    def active_rail_tool(self) -> RailTool | None:
        return (
            self._active_tool
            if isinstance(self._active_tool, RailTool)
            else None
        )

    @property
    def active_mountain_tool(self) -> AlternatingMountainTool | None:
        return (
            self._active_tool
            if isinstance(self._active_tool, AlternatingMountainTool)
            else None
        )

    @property
    def active_heist_tool(self) -> MarketHeistTool | None:
        return (
            self._active_tool
            if isinstance(self._active_tool, MarketHeistTool)
            else None
        )
