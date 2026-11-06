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
from strategy_core.position_roles import field, position_role, POSITION_ROLES
from strategy_core.source_freshness import current_source_is_fresh, current_source_receipt
from strategy_core.router import (
    PhysicalEvidence,
    TerritoryDecision,
    TerritoryRouter,
)
from strategy_core.tools.base import StrategyTool
from strategy_core.tools.heist import MarketHeistTool
from strategy_core.tools.mountain import AlternatingMountainTool, RollingMountainTool
from strategy_core.tools.rail import RailTool
from strategy_core.tools.release import (
    ReleaseEvidence,
    ReleaseWatcher,
)
from strategy_core.tools.management import as_side, number
from strategy_core.mission_context import MissionContext
from strategy_core.directional_parent import directional_parent_evidence
from strategy_core.dual_lane import (
    DualLaneCounterfadeMemory, early_main_policy, _current_mission_parent,
)
from strategy_core.navigator_briefing import navigator_terrain_briefing
from strategy_core.commander_candidates import (
    ema9_continuation_precedent, positive_candidate_matches_continuation, heist_sprout_fade_ready,
)
from strategy_core.mission_policy import MissionPolicy
from strategy_core.mission_scopes import qualified_full_arc_candidate
from strategy_core.types import (
    Action,
    Lane,
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
    release_in_progress: bool = False
    release_candidate_side: Side | None = None
    # Complete reviewed adviser set presented to the one Commander.  The
    # legacy lane-resolved `intents` remains diagnostic/backward-compatible,
    # but it is no longer the PAPER strategy authority.
    commander_intents: tuple[ToolIntent, ...] = ()
    # Positive, display-only adviser briefings. These never reach execution.
    briefings: tuple[Mapping[str, Any], ...] = ()


def _positive_briefing(intent: ToolIntent) -> Mapping[str, Any] | None:
    """Translate tool state into a positive, non-executable briefing.

    The one Commander receives only actionable ENTER/RELAY candidates.  WAIT
    reasons remain diagnostics.  This helper exposes only useful preparation
    states for Nautilus/operator awareness: PREPARE, FISH, or ENTRY_WINDOW.
    """
    reason = str(intent.reason or "").upper()
    state = None
    if intent.action in (Action.ENTER, Action.RELAY):
        state = "ENTRY_WINDOW"
    elif intent.action is Action.WAIT:
        fish_tokens = (
            "ARMED_AWAIT_SUB20_PULLBACK", "AWAIT_CHEAP_VALUE",
            "PRICE_ABOVE", "ABOVE_SOFT_VALUE", "ABOVE_EXCEPTIONAL_VALUE",
        )
        prep_tokens = (
            "ARMED_AWAIT_RETURN", "WATCHING_FOR_AFFIRMATIVE_TRANSFER",
            "POP_PREP", "DEFER_TO_NEXT_CONTRACT", "PREPARE",
        )
        if any(token in reason for token in fish_tokens):
            state = "FISH"
        elif any(token in reason for token in prep_tokens):
            state = "PREPARE"
    if state is None or intent.side is None:
        return None
    return {
        "tool": intent.tool, "territory_id": intent.territory_id,
        "state": state, "side": intent.side.value,
        "max_price": intent.max_price, "size_tier": intent.size_tier,
        "reason": intent.reason, "opportunity_id": intent.opportunity_id,
        "source_time": intent.source_time,
        "execution_authority": False, "can_veto": False,
    }


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
        # Operator-authorized 2026-11-01: parallel/unresolved Market Heist may
        # observe and trade as a tactical overlay beside Mountain instead of
        # requiring primary-territory takeover first.  Keep one persistent
        # overlay instance so an armed excursion survives ordinary classifier
        # flicker until the return, invalidation, or ticker rollover.
        self._heist_overlay: MarketHeistTool | None = None
        self._heist_overlay_territory_id = "MARKET_HEIST_PARALLEL_OVERLAY"
        # Independent *advisory* lanes. Territory is evidence, not exclusive
        # permission to speak. One Commander remains the execution authority.
        self._dual_main_rail: RailTool | None = None
        self._dual_tactical_heist: MarketHeistTool | None = None
        self._dual_counterfade = DualLaneCounterfadeMemory()

        # Three quick Heist-pattern contracts prepare the fourth for a pop.
        # This is briefing/priority context only; confirmed Release evidence is
        # still mandatory before ReleaseWatcher may book.
        self._heist_cycle_ticker: str | None = None
        self._heist_pattern_seen_current_contract = False
        self._heist_consecutive_pattern_contracts = 0

        self._pending_release_transition: Side | None = None
        self._release_from_side: Side | None = None
        self._release_from_territory: Territory | None = None
        self._release_transfer_source_ms: float | None = None
        self._territory_started_source_ms: float | None = None
        # References to retired tools exist only while their exact PAPER
        # position remains open; closing custody removes both maps' entries.
        self._filled_tools: dict[tuple[str, str, str], StrategyTool | None] = {}
        self._custody_tools: dict[tuple[str, str, str], StrategyTool] = {}
        self._custody_mission_ids: dict[tuple[str, str, str], str] = {}
        self._custody_physical_missions: dict[tuple[str, str, str], str] = {}
        self._position_keys: dict[str, tuple[str, str, str]] = {}
        self._recovery_detached: set[tuple[str, str, str]] = set()
        self._compatible_tools: dict[tuple[str, str], StrategyTool] = {}
        self._last_result: ToolRackShadowResult | None = None
        self._last_snapshot_ts: float | None = None
        self._heist_owner_bounds: tuple[float, float, float] | None = None
        self._heist_owner_box_id: str | None = None
        self._release_origin_box: tuple[float, float, float] | None = None
        self._release_origin_box_id: str | None = None
        # This is Mountain's own physical attempt memory, shared only across
        # replacements of that tool. Rail/Heist opportunities never consult it.
        self._mountain_mission_registry: dict[tuple[str, Side], dict[str, Any]] = {}
        self._mission_context = MissionContext(self.configs.mountain_detector)
        self.mission_policy = MissionPolicy()
        self.last_mission_context: Mapping[str, Any] = {}
        self._mission_history: tuple[Mapping[str, Any], ...] = ()

    def _historical_extreme_release_context(self, snapshot: MarketSnapshot) -> Mapping[str, Any]:
        """Causal prior-high/low context for an early Release-Prep scout.

        Completed historical candles only.  This is descriptive evidence; it
        cannot create a trade without current failed-extension + 6/9s reversal
        and cheap executable opposite value at Commander.
        """
        geometry = snapshot.metadata.get("current_geometry")
        geometry = geometry if isinstance(geometry, Mapping) else {}
        btc = number(geometry.get("btc_price"))
        r180 = max(1.0, number(geometry.get("range180")) or 1.0)
        if btc is None:
            return {"version": "HISTORICAL_EXTREME_RELEASE_V1", "qualified": False, "reason": "BTC_UNAVAILABLE"}
        now = snapshot.now_ts
        prior=[]
        for raw in self._mission_history:
            if not isinstance(raw, Mapping) or raw.get("complete") is not True:
                continue
            ts=number(raw.get("time")); known=number(raw.get("known_at"))
            if ts is None or ts + 60 > now - 90:
                continue
            if known is not None and known > now:
                continue
            lo=number(raw.get("low")); hi=number(raw.get("high")); close=number(raw.get("close"))
            if lo is None: lo=close
            if hi is None: hi=close
            if lo is not None and hi is not None and now - (ts+60) <= 4*3600:
                prior.append((ts+60,lo,hi))
        if len(prior) < 6:
            return {"version": "HISTORICAL_EXTREME_RELEASE_V1", "qualified": False, "reason": "INSUFFICIENT_COMPLETED_HISTORY"}
        lows=sorted(x[1] for x in prior); highs=sorted((x[2] for x in prior), reverse=True)
        tol=max(12.0,0.25*r180)
        low_anchor=lows[0]; high_anchor=highs[0]
        low_hits=sum(abs(v-low_anchor)<=tol for v in lows)
        high_hits=sum(abs(v-high_anchor)<=tol for v in highs)
        low_test=bool(low_hits>=2 and low_anchor-1.25*r180 <= btc <= low_anchor+tol)
        high_test=bool(high_hits>=2 and high_anchor-tol <= btc <= high_anchor+1.25*r180)
        side="YES" if low_test and not high_test else "NO" if high_test and not low_test else None

        # Recent level-match context: preserve a simple, causal support/resistance
        # retest independent of the broader extreme-cluster classifier.  This is
        # intentionally descriptive only; Commander still requires cheap return
        # value plus a current short-horizon rejection before it can enter.
        recent = [row for row in prior if 240.0 <= now-row[0] <= 1800.0]
        recent_low = min(recent, key=lambda row: abs(row[1]-btc)) if recent else None
        recent_high = min(recent, key=lambda row: abs(row[2]-btc)) if recent else None
        recent_low_match = bool(recent_low is not None and abs(recent_low[1]-btc) <= tol)
        recent_high_match = bool(recent_high is not None and abs(recent_high[2]-btc) <= tol)
        recent_side = ("YES" if recent_low_match and not recent_high_match else
                       "NO" if recent_high_match and not recent_low_match else None)
        recent_match = None
        if recent_side == "YES" and recent_low is not None:
            recent_match = {"side":"YES", "anchor":recent_low[1],
                            "anchor_time":recent_low[0], "age_s":now-recent_low[0],
                            "distance_btc":btc-recent_low[1]}
        elif recent_side == "NO" and recent_high is not None:
            recent_match = {"side":"NO", "anchor":recent_high[2],
                            "anchor_time":recent_high[0], "age_s":now-recent_high[0],
                            "distance_btc":btc-recent_high[2]}

        return {"version":"HISTORICAL_EXTREME_RELEASE_V2", "qualified": side is not None,
                "side":side, "btc":btc, "range180":r180, "tolerance":tol,
                "prior_low_anchor":low_anchor, "prior_low_hits":low_hits,
                "prior_high_anchor":high_anchor, "prior_high_hits":high_hits,
                "recent_level_match":recent_match,
                "basis":"COMPLETED_PRIOR_CANDLE_EXTREME_CLUSTER_NO_FUTURE_ROWS"}

    def prepare_snapshot(self, snapshot: MarketSnapshot, *, rows=(), historical_candles=None,
                         confirmed_release_side: Side | None = None) -> MarketSnapshot:
        """Attach one causal physical purpose shared by entry and custody."""
        if historical_candles is not None:
            self._mission_history = tuple(historical_candles)
        metadata = dict(snapshot.metadata)
        if confirmed_release_side is not None:
            metadata.update(confirmed_release_side=confirmed_release_side.value,
                confirmed_release_source_ms=metadata.get("geometry_last_epoch_ms"))
        contract = metadata.get("contract_value_context") or {}
        close_ts = number(contract.get("close_ts"))
        close_ts = close_ts if close_ts is not None else snapshot.now_ts + 900 - snapshot.contract_age_s
        context = self._mission_context.observe(metadata, ticker=snapshot.ticker,
            open_ts=close_ts - 900, close_ts=close_ts, target=number(contract.get("target")),
            now_ts=snapshot.now_ts, rows=rows, historical_candles=self._mission_history)
        self.mission_policy.carry_paid_holding_links(context, snapshot.ticker)
        self.last_mission_context = context
        interim = replace(snapshot, metadata={**metadata, "mission_context": context})
        extreme = self._historical_extreme_release_context(interim)
        return replace(interim, metadata={**interim.metadata, "historical_extreme_release": extreme})

    def record_scope_reacquisition(self, snapshot: MarketSnapshot, *, side: Side | None,
                                   basis: str) -> MarketSnapshot:
        """Link interrupted held scopes only after actual current reacquisition.

        The original lot and entry mission are immutable. The model records a
        causal bridge to a newly observed same-side parent; the bridge itself
        is neither a terminal nor a permission to buy another slice.
        """
        generation = snapshot.metadata.get("geometry_continuity_generation")
        held_missions = []
        for position in snapshot.metadata.get("position_inventory", ()):
            if not isinstance(position, Mapping) or position.get("ticker") != snapshot.ticker:
                continue
            mission = (position.get("entry_metadata") or {}).get("mission") or {}
            if (mission.get("purpose") in ("MAIN_CONTRACT", "ARC_RETURN")
                    and type(mission.get("continuity_generation")) is int
                    and mission.get("continuity_generation") != generation):
                held_missions.append(mission)
        if side is None or not held_missions:
            return snapshot
        context = self._mission_context.record_reacquisition(side=side.value,
            source_ms=snapshot.metadata.get("geometry_last_epoch_ms"),
            continuity_generation=generation, basis=basis, held_missions=held_missions)
        self.mission_policy.carry_paid_holding_links(context, snapshot.ticker)
        self.last_mission_context = context
        return replace(snapshot, metadata={**snapshot.metadata, "mission_context": context})

    def _update_heist_cycle_context(self, snapshot: MarketSnapshot) -> Mapping[str, Any]:
        """Track consecutive quick-Heist contracts for the operator's 3x-pop briefing.

        A contract counts only after the live detector has actually observed at
        least one lower visit, one upper visit, and one center traversal in a
        parallel Heist environment.  The fourth contract is POP_PREP after
        three consecutive observed pattern contracts.  This state never grants
        an entry by itself.
        """
        ticker = snapshot.ticker
        if self._heist_cycle_ticker is None:
            self._heist_cycle_ticker = ticker
        elif ticker != self._heist_cycle_ticker:
            if self._heist_pattern_seen_current_contract:
                self._heist_consecutive_pattern_contracts += 1
            else:
                self._heist_consecutive_pattern_contracts = 0
            self._heist_cycle_ticker = ticker
            self._heist_pattern_seen_current_contract = False

        details = snapshot.metadata.get("heist")
        details = details if isinstance(details, Mapping) else {}
        diag = details.get("diagnostics")
        diag = diag if isinstance(diag, Mapping) else {}
        parallel = bool(diag.get("heist_environment") is True
                        and diag.get("parallel_emas") is True)
        lower = int(details.get("lower_visits") or 0)
        upper = int(details.get("upper_visits") or 0)
        centers = int(details.get("center_traversals") or 0)
        observed_pattern_now = bool(parallel and lower >= 1 and upper >= 1 and centers >= 1)
        if observed_pattern_now:
            self._heist_pattern_seen_current_contract = True
        pop_prep = self._heist_consecutive_pattern_contracts >= 3
        return {
            "revision": "OPERATOR_AUTHORIZED_HEIST_THREE_TIMES_POP_V1",
            "ticker": ticker,
            "consecutive_completed_pattern_contracts": self._heist_consecutive_pattern_contracts,
            "current_contract_pattern_seen": self._heist_pattern_seen_current_contract,
            "observed_pattern_now": observed_pattern_now,
            "pop_prep": pop_prep,
            "entry_authority": False,
        }

    @staticmethod
    def _long_parent_suppresses_heist(snapshot: MarketSnapshot) -> bool:
        """Local churn inside a living directional parent is not Heist.

        PID1172 #8 showed that a small local box could still fire YES while the
        living DOWN parent, EMA9 gap and 30/60-second motion were all continuing
        downward.  Heist remains available for true neutral/parallel churn, but
        a MATURE/ROLLING same-side gap with current owner-direction expansion is
        still one directional chapter and suppresses the local renter.
        """
        if directional_parent_evidence(snapshot).get("qualified") is True:
            return True
        if snapshot.metadata.get("release_in_progress") is True:
            return True
        mountain = snapshot.metadata.get("mountain")
        mountain = mountain if isinstance(mountain, Mapping) else {}
        if mountain.get("strong_active_release") is True:
            return True
        parent = mountain.get("parent_structure")
        parent = parent if isinstance(parent, Mapping) else {}
        if bool(
            parent.get("parent_terminal_ready") is not True
            and (parent.get("extended_parent") is True
                 or parent.get("slow_rolling_parent") is True)
        ):
            return True
        cross = snapshot.metadata.get("ema9_ema30_cross_context")
        cross = cross if isinstance(cross, Mapping) else {}
        lifecycle = cross.get("gap_lifecycle")
        lifecycle = lifecycle if isinstance(lifecycle, Mapping) else {}
        stage = str(lifecycle.get("stage") or "").upper()
        gap_side = str(lifecycle.get("current_side") or "").upper()
        owner_side = str(mountain.get("owner_side") or "").upper()
        motion = mountain.get("current_motion")
        motion = motion if isinstance(motion, Mapping) else {}
        m30 = motion.get("30")
        m30 = m30 if isinstance(m30, Mapping) else {}
        try:
            owner_price_rate = float(m30.get("owner_price_rate_btc_s"))
            owner_ema9_rate = float(m30.get("owner_ema9_rate_btc_s"))
        except (TypeError, ValueError):
            owner_price_rate = owner_ema9_rate = 0.0
        return bool(
            stage in {"MATURE", "ROLLING"}
            and owner_side in {"YES", "NO"}
            and gap_side == owner_side
            and mountain.get("terminal_evidence_qualified") is not True
            and m30.get("covered") is True
            and owner_price_rate > 0 and owner_ema9_rate > 0
        )

    def _parallel_heist_overlay_intents(
        self, snapshot: MarketSnapshot, *, raw: TerritoryDecision, release_in_progress: bool,
    ) -> tuple[ToolIntent, ...]:
        """Run unresolved/parallel Heist beside Mountain without stealing parent ownership."""
        if isinstance(self._active_tool, MarketHeistTool):
            return ()
        if self._is_rail(self._owned_territory) or release_in_progress:
            return ()
        details = snapshot.metadata.get("heist")
        details = details if isinstance(details, Mapping) else {}
        if details.get("qualified_box") is True:
            # Qualified box is evaluated by the independent TACTICAL lane,
            # avoiding duplicate entries from two overlay instances.
            return ()
        diag = details.get("diagnostics")
        diag = diag if isinstance(diag, Mapping) else {}
        parallel_environment = bool(
            diag.get("heist_environment") is True and diag.get("parallel_emas") is True
        )
        if self._long_parent_suppresses_heist(snapshot):
            if self._heist_overlay is not None:
                # Let the tool observe current release metadata so any arm is
                # explicitly cleared by its own invalidation path.
                tuple(self._heist_overlay.on_market_event(snapshot))
            return ()
        armed = bool(self._heist_overlay is not None
                     and self._heist_overlay.parallel_return_armed)
        # COMPRESSION_UNRESOLVED is intentionally eligible here: the Heist
        # tool's own rule can arm the first parallel excursion and still waits
        # for BTC+EMA9 return confirmation before producing ENTER.
        if not parallel_environment and not armed:
            return ()
        if self._heist_overlay is None:
            self._heist_overlay = MarketHeistTool(
                territory_id=self._heist_overlay_territory_id, config=self.configs.heist)
        return tuple(self._heist_overlay.on_market_event(snapshot))

    def _independent_lane_intents(self, snapshot: MarketSnapshot) -> tuple[ToolIntent, ...]:
        """Observe MAIN + TACTICAL concurrently, regardless of owner label.

        Each tool still qualifies its own physical setup. This method only
        removes exclusive tool activation and adds the operator's normal
        first-five-minute MAIN observation preference. All exceptions on the
        existing dedicated rollover/Release paths remain untouched.
        """
        offers: list[ToolIntent] = []
        history = directional_parent_evidence(snapshot)
        parent = as_side(history.get("side")) if history.get("qualified") is True else None
        if parent is None:
            self._dual_main_rail = None
        elif not (isinstance(self._active_tool, RailTool) and self._active_tool.side is parent):
            if self._dual_main_rail is None or self._dual_main_rail.side is not parent:
                self._dual_main_rail = RailTool(territory_id=f"PARALLEL_MAIN_{parent.value}",
                    side=parent, activated_at=snapshot.now_ts, config=self.configs.rail)
            for offer in self._dual_main_rail.on_market_event(snapshot):
                if offer.action in (Action.ENTER, Action.RELAY):
                    offer = replace(offer, metadata={**offer.metadata,
                        "position_role":"PRIMARY", "dual_lane":"MAIN",
                        # Stable cross-chapter identity, not a new mission on
                        # every quote/observation timestamp.
                        "physical_mission_id":f"RAIL_PARENT:{parent.value}:" + str(
                            round(float(history.get('observed_residence_start_source_ms')) / 1000.0, -1)
                            if history.get('observed_residence_start_source_ms') is not None
                            and history.get('gap_age_s') is None
                            else round(snapshot.now_ts - float(history.get('gap_age_s') or 0), -1)),
                        "dual_lane_parent_evidence":dict(history)})
                    if early_main_policy(offer, snapshot):
                        offers.append(offer)
        # The Heist observer stays online alongside Mountain/Rail. It cannot
        # manufacture an unqualified box or escape a confirmed Release.
        heist = snapshot.metadata.get("heist")
        heist = heist if isinstance(heist, Mapping) else {}
        if not isinstance(self._active_tool, MarketHeistTool) and heist.get("qualified_box") is True:
            if self._dual_tactical_heist is None:
                # Reuse already-observed parallel arms when present.
                self._dual_tactical_heist = (self._heist_overlay or MarketHeistTool(
                    territory_id="PARALLEL_TACTICAL_HEIST", config=self.configs.heist))
            for offer in self._dual_tactical_heist.on_market_event(snapshot):
                if offer.action in (Action.ENTER, Action.RELAY):
                    offers.append(replace(offer, metadata={**offer.metadata,
                        "position_role":"TACTICAL", "dual_lane":"TACTICAL"}))
        elif heist.get("qualified_box") is not True and self._dual_tactical_heist is not None:
            # Current environment can invalidate a pending wall; do not carry
            # its arm across an unqualified or fully released box.
            tuple(self._dual_tactical_heist.on_market_event(snapshot))
        return tuple(offers)

    def filter_independent_lane_candidates(
        self, candidates: tuple[ToolIntent, ...], snapshot: MarketSnapshot,
    ) -> tuple[ToolIntent, ...]:
        """Calibrate the first opposing tactical swing, not a global veto.

        The observer is keyed by the *physical* EMA9 parent chapter and swing,
        never by the Kalshi contract boundary or repeated quote callbacks.
        """
        allowed=[]
        for offer in candidates:
            # This is a result of the current calibration check, not incoming
            # authority that may survive a Release/terminal or same-side bypass.
            if "dual_lane_counterfade_calibrated" in offer.metadata:
                offer = replace(offer, metadata={k:v for k,v in offer.metadata.items()
                    if k != "dual_lane_counterfade_calibrated"})
            if self._dual_counterfade.consider(offer, snapshot):
                # Only annotate a genuine independent tactical opportunity;
                # metadata cannot fabricate the required observed Heist box.
                calibrated = self._dual_counterfade.calibration_for(offer, snapshot)
                if (calibrated and offer.metadata.get("position_role") == "TACTICAL"
                        and offer.lane is Lane.TACTICAL):
                    offer=replace(offer, metadata={**offer.metadata,
                        "dual_lane_counterfade_calibrated": True})
                allowed.append(offer)
        return tuple(allowed)

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
            self._heist_owner_box_id = str(details.get("box_id") or "") or None

    def _new_territory_id(self, territory: Territory) -> str:
        self._serial += 1
        return f"{territory.value}_{self._serial:04d}"

    @staticmethod
    def _is_rail(territory: Territory) -> bool:
        return territory in (Territory.UP_RAIL, Territory.DOWN_RAIL)

    @staticmethod
    def _is_mountain(territory: Territory) -> bool:
        return territory in (Territory.ALTERNATING_MOUNTAIN, Territory.ROLLING_MOUNTAIN)

    @staticmethod
    def _supports_release_overlay(territory: Territory) -> bool:
        # Explicit operator authorization 2026-11-01: confirmed Release /
        # Leviathan is active beside the current Mountain, Rail, or Heist owner.
        # ReleaseWatcher itself still requires boundary break + directional
        # expansion + failed re-extension/residence; first slowdown is watch-only.
        return territory in (
            Territory.UP_RAIL, Territory.DOWN_RAIL,
            Territory.ALTERNATING_MOUNTAIN, Territory.ROLLING_MOUNTAIN,
            Territory.MARKET_HEIST,
        )

    @staticmethod
    def _supported_primary_territory(territory: Territory) -> bool:
        return territory in (
            Territory.UP_RAIL,
            Territory.DOWN_RAIL,
            Territory.ALTERNATING_MOUNTAIN,
            Territory.ROLLING_MOUNTAIN,
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
        self._territory_started_source_ms = (
            number(snapshot.metadata.get("geometry_last_epoch_ms")) or snapshot.now_ts * 1000.0
        )
        self._active_tool = None
        self._release_watcher = None
        self._heist_owner_bounds = None
        self._heist_owner_box_id = None
        self._release_origin_box = None
        self._release_origin_box_id = None

        if self._is_rail(decision.territory):
            # Rail is active again, but only after the physical source has
            # proved parent-scale EMA9 agreement. EMA30 alignment alone can no
            # longer instantiate this tool.
            if decision.side is not None:
                self._active_tool = RailTool(
                    territory_id=self._territory_id,
                    side=decision.side,
                    activated_at=snapshot.now_ts,
                    config=self.configs.rail,
                )
        elif self._is_mountain(decision.territory):
            mountain_tool = (RollingMountainTool
                             if decision.territory is Territory.ROLLING_MOUNTAIN
                             else AlternatingMountainTool)
            self._active_tool = mountain_tool(
                territory_id=self._territory_id,
                owner_side=decision.side,
                config=self.configs.mountain,
                mission_registry=self._mountain_mission_registry,
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
        self._heist_owner_box_id = None
        self._territory_started_source_ms = None

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
        self._heist_owner_box_id = None

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
            # A latched owner keeps its holdings, but historical expansion is
            # not authority to buy later. Revalidate the original transfer
            # against today's frozen probe and the original physical boundary.
            entry_evidence = ReleaseEvidence()
            entry_details: dict[str, Any] = {"reason": "CURRENT_RELEASE_PROBE_UNAVAILABLE"}
            if isinstance(probe, ReleaseProbe):
                origin_territory = self._release_from_territory or Territory.RELEASE_TRANSITION
                if origin_territory is Territory.MARKET_HEIST and self._release_origin_box is not None:
                    lo, hi, tolerance = self._release_origin_box
                    probe = replace(probe, heist_lower=lo, heist_upper=hi,
                                    heist_edge_tolerance=tolerance)
                revalidated = detect_release_for_owner(
                    probe, owner_territory=origin_territory,
                    owner_side=self._release_from_side,
                    config=self.configs.release_detector,
                )
                entry_evidence = revalidated.evidence
                entry_details = {"boundary": revalidated.boundary_name, **revalidated.diagnostics}
            return (
                self._release_watcher.evidence,
                "RELEASE_TRANSITION_LATCHED",
                {
                    "source": "LATCHED_CONFIRMED_RELEASE",
                    "entry_evidence": entry_evidence,
                    "entry_revalidation": entry_details,
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
                    "from_box_id": self._release_origin_box_id,
                    "transfer_source_ms": self._release_transfer_source_ms,
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
        # A hypothetical opposite candidate or first slowdown is descriptive
        # only.  A Release exists only after current transfer evidence is
        # observed.  This prevents every directional owner from automatically
        # manufacturing an opposite "release in progress".
        return bool(
            release.boundary_break
            or release.directional_expansion
            or release.old_owner_failed_reextension
            or release.new_side_residence
        )

    def _release_entry_evidence_guard(
        self, evidence: ReleaseEvidence, snapshot: MarketSnapshot, *, latched: bool
    ) -> tuple[ReleaseEvidence, Mapping[str, Any]]:
        """Keep Release causal across mature gaps while honoring 3x-pop prep.

        PID1172 #2 was a local opposite bounce that satisfied the old Release
        tuple even though a MATURE/ROLLING old-side EMA9 gap still physically
        owned the chapter.  Until meaningful new-side residence appears, that
        intact mature gap blocks a paid Release.  Conversely, the already
        authorized three-Heist-contract POP_PREP may promote a *real* Heist box
        break that has both boundary break and measured directional expansion;
        POP_PREP alone still has zero entry authority.
        """
        if evidence.candidate_side is None:
            return evidence, {"basis": "NO_RELEASE_CANDIDATE"}
        owner_side = self._release_from_side if latched else self._owned_side
        owner_territory = self._release_from_territory if latched else self._owned_territory
        cross = snapshot.metadata.get("ema9_ema30_cross_context")
        cross = cross if isinstance(cross, Mapping) else {}
        lifecycle = cross.get("gap_lifecycle")
        lifecycle = lifecycle if isinstance(lifecycle, Mapping) else {}
        stage = str(lifecycle.get("stage") or "").upper()
        gap_side = str(lifecycle.get("current_side") or "").upper()
        cycle = snapshot.metadata.get("heist_cycle_context")
        cycle = cycle if isinstance(cycle, Mapping) else {}
        guarded = evidence
        basis = "RELEASE_EVIDENCE_UNCHANGED"

        if (owner_territory is not Territory.MARKET_HEIST
                and owner_side is not None and evidence.candidate_side is not owner_side
                and stage in {"MATURE", "ROLLING"}
                and gap_side == owner_side.value
                and not evidence.new_side_residence):
            # A failed local re-extension is insufficient while the old mature
            # gap remains intact. Require actual new-side residence (or later
            # gap transfer) before paying for the handoff.
            guarded = replace(guarded, old_owner_failed_reextension=False)
            basis = "MATURE_OLD_SIDE_GAP_REQUIRES_NEW_SIDE_RESIDENCE"

        if (owner_territory is Territory.MARKET_HEIST
                and cycle.get("pop_prep") is True
                and guarded.boundary_break and guarded.directional_expansion
                and not guarded.confirmed):
            # Three completed quick-Heist pattern contracts prepare the fourth
            # for the pop. A real box break + measured expansion is sufficient
            # to declare the old box failed; POP_PREP without those signals is
            # still only a briefing state.
            guarded = replace(guarded, old_owner_failed_reextension=True)
            basis = "HEIST_POP_PREP_BOX_BREAK_DIRECTIONAL_EXPANSION_CONFIRMS_TRANSFER"

        return guarded, {
            "basis": basis,
            "owner_territory": owner_territory.value if isinstance(owner_territory, Territory) else None,
            "owner_side": owner_side.value if isinstance(owner_side, Side) else None,
            "gap_stage": stage or None,
            "gap_side": gap_side or None,
            "pop_prep": cycle.get("pop_prep") is True,
            "candidate_side": guarded.candidate_side.value if guarded.candidate_side else None,
            "confirmed_after_guard": guarded.confirmed,
        }

    def _update_release_watcher(
        self,
        release: ReleaseEvidence,
        snapshot: MarketSnapshot,
        boundary_name: str | None,
        diagnostics: Mapping[str, Any],
    ) -> None:
        if self._release_watcher is None:
            return

        # During RELEASE_TRANSITION keep the outgoing owner recorded in the
        # watcher instead of rewriting ancestry to the incoming side.
        if self._owned_territory is not Territory.RELEASE_TRANSITION:
            self._release_watcher.update_owner_side(self._owned_side)
        latched = boundary_name == "RELEASE_TRANSITION_LATCHED"
        entry_evidence = diagnostics.get("entry_evidence") if latched else release
        if not isinstance(entry_evidence, ReleaseEvidence):
            entry_evidence = ReleaseEvidence()
        entry_evidence, parent_gap_guard = self._release_entry_evidence_guard(
            entry_evidence, snapshot, latched=latched)
        geometry_ms = number(snapshot.metadata.get("geometry_last_epoch_ms"))
        observed_at = geometry_ms / 1000.0 if geometry_ms is not None else snapshot.now_ts
        self._release_watcher.update_evidence(
            release, entry_evidence=entry_evidence,
            entry_diagnostics={
                "source": "CURRENT_REVALIDATED_TRANSFER" if latched else "CURRENT_TRANSFER",
                "qualified": entry_evidence.confirmed,
                "fresh_transfer": bool(not latched and release.confirmed),
                "observed_at": observed_at,
                "candidate_side": entry_evidence.candidate_side.value if entry_evidence.candidate_side else None,
                "boundary_break": entry_evidence.boundary_break,
                "directional_expansion": entry_evidence.directional_expansion,
                "old_owner_failed_reextension": entry_evidence.old_owner_failed_reextension,
                "new_side_residence": entry_evidence.new_side_residence,
                "revalidation": diagnostics.get("entry_revalidation", {}),
                "parent_gap_guard": dict(parent_gap_guard),
            },
        )

    def _transition_can_accept(
        self,
        raw: TerritoryDecision,
        snapshot: MarketSnapshot | None = None,
    ) -> bool:
        if not self._supported_primary_territory(raw.territory):
            return False
        if raw.territory is Territory.MARKET_HEIST:
            # Heist is a two-sided territory. It earns new ownership through
            # a genuinely repeated current box, not Rail's directional vote.
            # Matching an old direction or renaming old bounds is insufficient.
            return snapshot is not None and self._new_heist_box_observed(
                snapshot, after_source_ms=self._release_transfer_source_ms)
        # A directionless classifier does not complete a directional handoff.
        # Keep its confirmed incoming side until an actual same-side territory
        # is established; neutral flicker cannot erase release custody.
        return raw.side is not None and raw.side is self._owned_side

    def _new_heist_box_observed(
        self, snapshot: MarketSnapshot, *, after_source_ms: float | None,
    ) -> bool:
        """Require new native repeatability after this ownership boundary.

        The detector already defines a box's range, drift and visit counts.
        This check adds provenance for the transfer, without a timer, a Rail
        compass prerequisite, or permission from a merely qualified old label.
        """
        metadata = snapshot.metadata
        details = metadata.get("heist")
        geometry = metadata.get("current_geometry")
        summary = metadata.get("territory_detector_summary")
        if (after_source_ms is None or metadata.get("physical_current") is not True
                or not isinstance(details, Mapping) or details.get("qualified_box") is not True
                or not isinstance(geometry, Mapping) or not isinstance(summary, Mapping)
                or summary.get("rail_established") is not False):
            return False
        proof = details.get("repeatability_proof")
        if (not isinstance(proof, Mapping)
                or proof.get("source") != "OBSERVED_HEIST_REPEATABILITY_V1"
                or proof.get("single_connection_epoch") is not True
                or proof.get("strict_source_times") is not True
                or proof.get("connection_epoch") != geometry.get("connection_epoch")):
            return False
        source_ms = number(metadata.get("geometry_last_epoch_ms"))
        geometry_ms = number(geometry.get("epoch_ms"))
        start_ms, end_ms = number(proof.get("window_start_ms")), number(proof.get("window_end_ms"))
        lower, upper = number(details.get("lower")), number(details.get("upper"))
        current_btc = number(geometry.get("btc_price"))
        drift9, drift30 = number(proof.get("ema9_drift")), number(proof.get("ema30_drift"))
        if any(value is None for value in
               (source_ms, geometry_ms, start_ms, end_ms, lower, upper, current_btc, drift9, drift30)):
            return False
        assert source_ms is not None and geometry_ms is not None
        assert start_ms is not None and end_ms is not None and lower is not None and upper is not None
        assert current_btc is not None and drift9 is not None and drift30 is not None
        cfg = self.configs.heist_detector
        max_age = number(metadata.get("geometry_max_source_age_seconds")) or 3.0
        if (not current_source_is_fresh(snapshot, source_ms, max_age_seconds=max_age)
                or abs(source_ms - geometry_ms) > 1e-3 or abs(end_ms - source_ms) > 1e-3
                or (end_ms - start_ms) / 1000.0 < cfg.min_observed_span_s
                or not lower <= current_btc <= upper
                or upper - lower < cfg.min_box_range_dollars
                or number(proof.get("lower")) != lower or number(proof.get("upper")) != upper
                or abs(drift9) > cfg.max_ema9_drift_fraction * (upper - lower)
                or abs(drift30) > cfg.max_ema30_drift_fraction * (upper - lower)):
            return False
        visits = proof.get("repeatability_visits")
        if not isinstance(visits, (list, tuple)):
            return False
        counts = {"LOWER": 0, "UPPER": 0, "CENTER": 0}
        previous = None
        for visit in visits:
            if not isinstance(visit, Mapping):
                return False
            observed = number(visit.get("epoch_ms"))
            zone = visit.get("zone")
            if (observed is None or zone not in counts or not start_ms <= observed <= end_ms
                    or observed <= after_source_ms or previous is not None and observed <= previous):
                return False
            counts[zone] += 1
            previous = observed
        return (counts["LOWER"] >= cfg.minimum_lower_visits
                and counts["UPPER"] >= cfg.minimum_upper_visits
                and counts["CENTER"] >= cfg.minimum_center_traversals)

    def observe(
        self,
        evidence: PhysicalEvidence,
        snapshot: MarketSnapshot,
    ) -> ToolRackShadowResult:
        if ("mission_context" not in snapshot.metadata
                and snapshot.metadata.get("source") == "DIRECT_BTC_AND_NATIVE_KALSHI"):
            snapshot = self.prepare_snapshot(snapshot)
        heist_cycle_context = self._update_heist_cycle_context(snapshot)
        snapshot = replace(snapshot, metadata={**snapshot.metadata,
            "heist_cycle_context": dict(heist_cycle_context)})
        self.mission_policy.observe(snapshot)
        quote_wave = self.mission_policy.quote_wave_briefing(snapshot)
        snapshot = replace(snapshot, metadata={**snapshot.metadata, "quote_wave": quote_wave})
        self._dual_counterfade.observe_first_physical_swing(snapshot)
        # Propagate advisory briefing through the shared metadata mapping used
        # by the PAPER coordinator/Commander without granting tool authority.
        if isinstance(snapshot.metadata, dict):
            pass
        # A physical handoff confirmed on the prior beat retires the old primary
        # before any new raw territory is considered.
        if self._pending_release_transition is not None:
            self._begin_release_transition(snapshot)

        territory_id_before = self._territory_id
        owned_side_before = self._owned_side
        raw = self.router.classify(evidence)
        historical_parent = directional_parent_evidence(snapshot)
        # A repeatedly qualified local Heist may still run brief tactical
        # observations, but cannot retain *primary* ownership of a persistent
        # multi-contract directional EMA9 gap.  Rolling Mountain and Rail
        # share the with-wind playbook without being called identical terrain.
        if (historical_parent.get("qualified") is True
                and raw.territory is Territory.MARKET_HEIST
                and self._owned_territory is not Territory.RELEASE_TRANSITION):
            direction = as_side(historical_parent.get("side"))
            if direction is not None:
                raw = TerritoryDecision(
                    Territory.ROLLING_MOUNTAIN, direction,
                    "HISTORICAL_PARENT_RETIRES_LOCAL_HEIST_OWNERSHIP")
        ownership_reason = raw.reason

        (
            release_evidence,
            release_boundary_name,
            release_diagnostics,
        ) = self._resolve_release_evidence(evidence, snapshot)
        release_in_progress = self._release_in_progress(release_evidence)
        # A latched historical Release is ancestry only unless its paid-entry
        # transfer evidence revalidates on the current beat.  Do not let stale
        # Release custody advertise a global release_in_progress veto.
        if release_boundary_name == "RELEASE_TRANSITION_LATCHED":
            current_entry_evidence = release_diagnostics.get("entry_evidence")
            if not isinstance(current_entry_evidence, ReleaseEvidence) or not current_entry_evidence.confirmed:
                release_in_progress = False
        snapshot = replace(snapshot, metadata={**snapshot.metadata,
            "release_in_progress": release_in_progress,
            "release_candidate_side": (release_evidence.candidate_side.value
                if release_evidence.candidate_side is not None else None),
            "release_confirmed_current": release_evidence.confirmed is True,
        })
        mountain_metadata = snapshot.metadata.get("mountain")
        physical_mountain_side = (
            as_side(mountain_metadata.get("owner_side"))
            if isinstance(mountain_metadata, Mapping) else None
        )
        parent_structure = (mountain_metadata.get("parent_structure")
            if isinstance(mountain_metadata, Mapping)
            and isinstance(mountain_metadata.get("parent_structure"), Mapping) else {})
        parent_side = as_side(parent_structure.get("parent_side"))

        if self._owned_territory is Territory.RELEASE_TRANSITION:
            current_entry_evidence = release_diagnostics.get("entry_evidence")
            current_release_revalidated = bool(
                isinstance(current_entry_evidence, ReleaseEvidence)
                and current_entry_evidence.confirmed
            )
            opposing_release = (current_release_revalidated
                and current_entry_evidence.candidate_side is not self._owned_side)
            # If the latched Release cannot revalidate a paid entry now, it has
            # no ownership veto over a currently qualified primary territory.
            # This is the implementation of the existing anti-starvation rule:
            # stale Release ancestry remains briefing only.
            stale_release_yields = bool(
                not current_release_revalidated
                and self._supported_primary_territory(raw.territory)
            )
            if not opposing_release and (stale_release_yields or self._transition_can_accept(raw, snapshot)):
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

        elif self._is_rail(self._owned_territory):
            if (raw.territory is Territory.MARKET_HEIST
                    and (evidence.heist_takeover_confirmed or self._new_heist_box_observed(
                        snapshot, after_source_ms=self._territory_started_source_ms))):
                self._deactivate_current(snapshot, "QUALIFIED_HEIST_TAKEOVER")
                self._activate(raw, snapshot)
                ownership_reason = "QUALIFIED_HEIST_TAKEOVER"
            elif self._is_mountain(raw.territory):
                parent_still_owns = bool(parent_side is self._owned_side
                    and parent_structure.get("parent_terminal_ready") is not True
                    and (parent_structure.get("extended_parent") is True
                         or parent_structure.get("slow_rolling_parent") is True))
                if parent_still_owns:
                    # Child arcs are breathing inside the same long parent.
                    ownership_reason = "RAIL_LONG_PARENT_IGNORES_CHILD_MOUNTAIN_FLICKER"
                else:
                    self._deactivate_current(snapshot, "PARENT_RAIL_ENDED_RETURN_TO_MOUNTAIN")
                    self._activate(raw, snapshot)
                    ownership_reason = "PARENT_RAIL_ENDED_RETURN_TO_MOUNTAIN"
            elif self._is_rail(raw.territory):
                if raw.side is not None:
                    self._owned_side = raw.side
                    if isinstance(self._active_tool, RailTool):
                        self._active_tool.side = raw.side
                ownership_reason = "RAIL_PARENT_PERSISTS"
            else:
                parent_still_owns = bool(parent_side is self._owned_side
                    and parent_structure.get("parent_terminal_ready") is not True
                    and parent_structure.get("slow_rolling_parent") is True)
                if parent_still_owns:
                    ownership_reason = "SLOW_ROLLING_PARENT_PRESERVES_RAIL_CUSTODY"
                else:
                    self._deactivate_current(snapshot, "RAIL_PARENT_NO_LONGER_QUALIFIED")
                    ownership_reason = "RAIL_PARENT_NO_LONGER_QUALIFIED"

        elif self._owned_territory is Territory.MARKET_HEIST:
            current_heist = snapshot.metadata.get("heist")
            current_heist = current_heist if isinstance(current_heist, Mapping) else {}
            current_heist_qualified = current_heist.get("qualified_box") is True
            current_diag = current_heist.get("diagnostics")
            current_diag = current_diag if isinstance(current_diag, Mapping) else {}
            current_parallel = bool(current_diag.get("heist_environment") is True
                                    and current_diag.get("parallel_emas") is True)
            armed_return = bool(isinstance(self._active_tool, MarketHeistTool)
                                and self._active_tool.parallel_return_armed)
            if (not self._long_parent_suppresses_heist(snapshot)
                    and (raw.territory is Territory.MARKET_HEIST or current_heist_qualified
                         or (current_parallel and armed_return))):
                if raw.side is not None:
                    self._owned_side = raw.side
                ownership_reason = (
                    "HEIST_ARMED_RETURN_PERSISTS_THROUGH_CLASSIFIER_FLICKER"
                    if current_parallel and armed_return and raw.territory is not Territory.MARKET_HEIST
                    else "HEIST_STRICT_BOX_REMAINS_OWNER_WHILE_QUALIFIED"
                )
            elif self._is_mountain(raw.territory):
                self._deactivate_current(snapshot, "HEIST_ENDED_RETURN_TO_EMA9_MOUNTAIN")
                self._activate(raw, snapshot)
                ownership_reason = "HEIST_ENDED_RETURN_TO_EMA9_MOUNTAIN"
            elif self._is_rail(raw.territory):
                self._deactivate_current(snapshot, "HEIST_ENDED_RAIL_CONTEXT_ONLY")
                self._activate(raw, snapshot)
                ownership_reason = "HEIST_ENDED_RAIL_CONTEXT_ONLY"
            else:
                self._deactivate_current(snapshot, "HEIST_NO_LONGER_STRICTLY_QUALIFIED")
                ownership_reason = "HEIST_NO_LONGER_STRICTLY_QUALIFIED"

        elif self._is_mountain(self._owned_territory):
            if (raw.territory is Territory.MARKET_HEIST
                    and self._new_heist_box_observed(
                        snapshot, after_source_ms=self._territory_started_source_ms)
                    ):
                # Heist may replace Mountain only after its own detector has
                # earned a NEW tight repeated box.  The detector itself now
                # requires compression or parallel-EMA churn, so a single
                # classifier flicker cannot steal the living EMA9 arc.
                self._deactivate_current(snapshot, "QUALIFIED_HEIST_TAKEOVER")
                self._activate(raw, snapshot)
                ownership_reason = "QUALIFIED_HEIST_TAKEOVER"
            elif self._is_rail(raw.territory):
                # Controlled promotion: only the physical parent-scale router
                # can produce this raw Rail. A local child arc / EMA30 cross
                # cannot. Existing same-side custody transfers without a new fill.
                self._deactivate_current(snapshot, "LONG_PARENT_PROMOTES_TO_RAIL")
                self._activate(raw, snapshot)
                ownership_reason = "LONG_PARENT_PROMOTES_TO_RAIL"
            elif self._is_mountain(raw.territory):
                if raw.side is not None:
                    self._owned_side = raw.side
                if isinstance(self._active_tool, AlternatingMountainTool):
                    self._active_tool.update_owner_side(raw.side)
                ownership_reason = (
                    "MOUNTAIN_TERRITORY_PERSISTS_ACROSS_EDGE_RELAYS"
                )
            else:
                # Unknown classifier flicker cannot steal the living EMA9
                # Mountain. Rail is already suppressed at the live physical
                # source while a meaningful EMA9 arc exists.
                ownership_reason = (
                    "MOUNTAIN_OWNER_PERSISTS_UNTIL_EDGE_RELAY_OR_RELEASE"
                )

        elif raw.territory is not self._owned_territory:
            self._deactivate_current(snapshot, "TERRITORY_CHANGED")
            if self._supported_primary_territory(raw.territory):
                self._activate(raw, snapshot)

        elif raw.side is not self._owned_side:
            self._owned_side = raw.side

        # Resolve a new physical owner coherently. A confirmed transfer above
        # preserves outgoing ancestry. An unconfirmed WATCH cannot freeze the
        # Mountain compass after a real new arc, nor leave a candidate measured
        # against the old side attached to the newly observed owner.
        if (
            self._release_watcher is not None
            and self._owned_territory is not Territory.RELEASE_TRANSITION
            and (self._territory_id != territory_id_before
                 or self._owned_side is not owned_side_before)
        ):
            (
                release_evidence,
                release_boundary_name,
                release_diagnostics,
            ) = self._resolve_release_evidence(evidence, snapshot)

        self._update_release_watcher(release_evidence, snapshot, release_boundary_name, release_diagnostics)

        current_transfer = (self._release_watcher is not None and release_evidence.confirmed and (
            release_boundary_name != "RELEASE_TRANSITION_LATCHED"
            or isinstance(release_diagnostics.get("entry_evidence"), ReleaseEvidence)
            and release_diagnostics["entry_evidence"].confirmed))
        if (current_transfer and release_evidence.candidate_side is not None
                and "mission_context" in snapshot.metadata):
            snapshot = self.prepare_snapshot(snapshot, confirmed_release_side=release_evidence.candidate_side)

        primary_intents: tuple[ToolIntent, ...] = ()
        if self._active_tool is not None:
            offered = tuple(self._active_tool.on_market_event(snapshot))
            if isinstance(self._active_tool, AlternatingMountainTool):
                if "mission_context" not in snapshot.metadata:
                    # Compatibility for isolated historical tool fixtures.
                    # Every standalone runtime capture supplies mission_context.
                    inventory = [p for p in snapshot.metadata.get("position_inventory", ())
                                 if isinstance(p, Mapping) and p.get("ticker") == snapshot.ticker]
                    has_primary = any(position_role(p) == "PRIMARY" for p in inventory)
                    offered = tuple(replace(intent, metadata={**intent.metadata,
                        "position_role": "TACTICAL" if has_primary else "PRIMARY"})
                        if intent.action in (Action.ENTER, Action.RELAY) else intent for intent in offered)
                aligned = self._active_tool.aligned_entry_intent(snapshot)
                if self._active_tool.main_proposal_review is not None:
                    self.mission_policy.reviews.append(dict(self._active_tool.main_proposal_review))
                if aligned is not None and not any(
                        intent.opportunity_id == aligned.opportunity_id
                        and intent.side is aligned.side and intent.action is aligned.action
                        for intent in offered):
                    offered += (aligned,)
            # No hidden compatible strategy under the owner. Mountain trades
            # only its terminal edges; strict Heist trades only its box edges.
            reviewed_primary_intents = tuple(
                self.mission_policy.review(self._physical_intent(intent, snapshot), snapshot)
                for intent in offered)
            primary_intents = self._select_role_candidates(reviewed_primary_intents, snapshot)
        else:
            reviewed_primary_intents = ()

        overlay_candidates: list[ToolIntent] = []
        handoff_confirmed = False
        if self._release_watcher is not None:
            overlay_candidates.extend(self._release_watcher.on_market_event(snapshot))
            handoff_confirmed = self._release_watcher.confirmed
        overlay_candidates.extend(self._parallel_heist_overlay_intents(
            snapshot, raw=raw, release_in_progress=release_in_progress))
        rail_child = self._rail_child_arc_value_intent(snapshot)
        if rail_child is not None:
            overlay_candidates.append(rail_child)
        # Each lane observes even when the Router's primary label is different.
        # Separate stable tool identities allow independent custody after fills.
        overlay_candidates.extend(self._independent_lane_intents(snapshot))
        overlay_intents = tuple(
            self.mission_policy.review(self._physical_intent(intent, snapshot), snapshot)
            for intent in overlay_candidates)

        # One Commander sees only positive actionable adviser candidates.
        # Specialist WAIT/HOLD/EXIT output remains diagnostic/briefing evidence
        # and cannot enter the Commander's decision channel.
        reviewed_adviser_intents = reviewed_primary_intents + overlay_intents
        confirmed_side = (release_evidence.candidate_side
                          if current_transfer and release_evidence.confirmed else None)
        # Observe the first counterfade *before* applying continuation briefs.
        # A later, distinct qualified Heist swing can coexist with a directional
        # parent without granting authority to the first tentative countermove.
        calibrated = self.filter_independent_lane_candidates(tuple(
            intent for intent in reviewed_adviser_intents
            if intent.action in (Action.ENTER, Action.RELAY)), snapshot)
        def briefing_coherent(intent: ToolIntent) -> bool:
            if not heist_sprout_fade_ready(intent, snapshot):
                return False
            if positive_candidate_matches_continuation(
                    intent, snapshot, confirmed_release_side=confirmed_side):
                return True
            return bool(intent.tool == "MARKET_HEIST"
                and intent.metadata.get("dual_lane_counterfade_calibrated") is True
                and isinstance(snapshot.metadata.get("heist"), Mapping)
                and snapshot.metadata["heist"].get("qualified_box") is True
                and snapshot.metadata.get("release_in_progress") is not True
                and snapshot.metadata.get("release_confirmed_current") is not True)
        commander_intents = tuple(intent for intent in calibrated if briefing_coherent(intent))
        briefing_rows: list[Mapping[str, Any]] = []
        seen_briefings: set[tuple[Any, ...]] = set()
        for adviser_intent in reviewed_adviser_intents:
            if (adviser_intent.action in (Action.ENTER, Action.RELAY)
                    and not any(i.opportunity_id == adviser_intent.opportunity_id
                                and i.side is adviser_intent.side
                                for i in commander_intents)):
                continue
            briefing = _positive_briefing(adviser_intent)
            if briefing is None:
                continue
            key = (briefing.get("tool"), briefing.get("state"), briefing.get("side"),
                   briefing.get("opportunity_id"), briefing.get("max_price"), briefing.get("reason"))
            if key in seen_briefings:
                continue
            seen_briefings.add(key)
            briefing_rows.append(briefing)
        # Causal last-3/4-contract parent briefs the Commander on the side
        # worth JOINING; a local child Heist cannot submit competing full
        # strength fade entries against it. No negative WAIT is introduced.
        # Read-only Navigator restores the original terrain counsellor's
        # positive cross-contract briefing without granting tool authority.
        # TP/junction ambiguity means PREPARE, not a speculative ENTRY_WINDOW.
        navigator = navigator_terrain_briefing(snapshot)
        if navigator is not None:
            briefing_rows.append(navigator)
        continuation = ema9_continuation_precedent(snapshot)
        if continuation.get("qualified") is True and continuation.get("side") in {"YES", "NO"}:
            briefing_rows.append({
                "tool": "EMA9_CONTINUATION_PRECEDENT",
                "territory_id": "EMA9_LIVING_LEG",
                "state": "PREPARE",
                "side": continuation["side"],
                "max_price": None,
                "size_tier": None,
                "reason": continuation.get("basis"),
                "opportunity_id": f"EMA9_CONTINUATION:{snapshot.ticker}:{continuation['side']}",
                "source_time": snapshot.now_ts,
                "evidence": dict(continuation),
                "execution_authority": False,
                "can_veto": False,
            })
        observed_first_fade = self._dual_counterfade.last_observation
        if observed_first_fade is not None:
            briefing_rows.append(observed_first_fade)
        briefings = tuple(briefing_rows)
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
            self._release_origin_box = self._heist_owner_bounds
            self._release_origin_box_id = self._heist_owner_box_id
            self._release_transfer_source_ms = (
                number(snapshot.metadata.get("geometry_last_epoch_ms")) or snapshot.now_ts * 1000.0
            )

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
            active_overlays=tuple(
                name for name in (
                    self._release_watcher.name if self._release_watcher is not None else None,
                    self._heist_overlay.name if self._heist_overlay is not None
                        and self._heist_overlay.parallel_return_armed else None,
                ) if name is not None
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
            release_in_progress=release_in_progress,
            release_candidate_side=release_evidence.candidate_side,
            commander_intents=commander_intents,
            briefings=briefings,
        )
        self._last_result = result
        self._last_snapshot_ts = snapshot.now_ts
        return result

    @staticmethod
    def _position_key(position: Mapping[str, Any]) -> tuple[str, str, str]:
        return (str(position.get("ticker") or ""), str(position.get("territory_id") or ""),
                str(position.get("opportunity_id") or ""))

    @staticmethod
    def _physical_intent(intent: ToolIntent, snapshot: MarketSnapshot) -> ToolIntent:
        """Describe the tool's physical mission without adding entry authority.

        These identities are deliberately not ticker, quote or route aliases.
        Mountain supplies its own measured attempt generation. Rail profit
        re-entry remains a value opportunity inside the same physical chapter.
        """
        if intent.action not in (Action.ENTER, Action.RELAY):
            return intent
        role = intent.metadata.get("position_role") or (
            "TACTICAL" if intent.tool == "MARKET_HEIST" else "PRIMARY")
        intent = replace(intent, metadata={**intent.metadata, "position_role": role})
        if intent.metadata.get("physical_mission_id"):
            return intent
        metadata = dict(intent.metadata)
        epoch_ms = number(snapshot.metadata.get("geometry_last_epoch_ms"))
        observed_at = epoch_ms / 1000.0 if epoch_ms is not None else snapshot.now_ts
        mission = None
        kind = None
        if intent.tool == "RAIL":
            mission, kind = f"{intent.territory_id}:RAIL_CHAPTER", "NEW_RAIL_TERRITORY"
            summary = snapshot.metadata.get("territory_detector_summary")
            mountain = snapshot.metadata.get("mountain")
            parent = mountain.get("parent_structure") if isinstance(mountain, Mapping) else None
            parent_side = parent.get("parent_side") if isinstance(parent, Mapping) else None
            if (isinstance(summary, Mapping)
                    and summary.get("rail_launch_qualified") is True
                    and parent_side == intent.side.value):
                metadata["parent_scale_rail_authority"] = True
        elif intent.tool == "MARKET_HEIST":
            box, visit = metadata.get("box_id"), metadata.get("visit_id")
            if box and visit:
                mission, kind = f"HEIST:{box}:VISIT:{visit}", "HEIST_NEW_EDGE_VISIT"
        if mission is None:
            return intent
        metadata.update(physical_mission_id=mission, physical_renewal={
            "independent": True, "renewal_kind": kind, "observed_at": observed_at,
        })
        return replace(intent, metadata=metadata)

    def _tool_has_active_ticker(self, tool: StrategyTool, ticker: str) -> bool:
        return any(key[0] == ticker and key not in self._recovery_detached
                   and (origin is tool or self._custody_tools.get(key) is tool)
                   for key, origin in self._filled_tools.items())

    def _sync_tool_slots(self, key: tuple[str, str, str]) -> None:
        tools = (self._filled_tools.get(key), self._custody_tools.get(key))
        for tool in {id(t): t for t in tools if t is not None}.values():
            tool.sync_tactical_inventory(ticker=key[0], present=self._tool_has_active_ticker(tool, key[0]))

    def mark_position_recovery_detached(self, position: Mapping[str, Any]) -> None:
        """Release the tactical slot, never the consumed physical mission."""
        key = self._position_key(position)
        if key not in self._filled_tools:
            return
        self._recovery_detached.add(key)
        origin, manager = self._filled_tools[key], self._custody_tools.get(key)
        for tool in {id(t): t for t in (origin, manager) if t is not None}.values():
            local_mission = self._custody_mission_ids.get(key, key[2]) if tool is manager else key[2]
            tool.detach_position_custody(ticker=key[0], opportunity_id=local_mission)
        self._sync_tool_slots(key)

    def mark_position_recovery_restored(self, position: Mapping[str, Any]) -> None:
        key = self._position_key(position)
        if key not in self._filled_tools:
            return
        self._recovery_detached.discard(key)
        origin, manager = self._filled_tools[key], self._custody_tools.get(key)
        for tool in {id(t): t for t in (origin, manager) if t is not None}.values():
            local_mission = self._custody_mission_ids.get(key, key[2]) if tool is manager else key[2]
            tool.recover_position_custody(ticker=key[0], opportunity_id=local_mission)
        self._sync_tool_slots(key)

    @staticmethod
    def _select_role_candidates(intents: tuple[ToolIntent, ...], snapshot: MarketSnapshot) -> tuple[ToolIntent, ...]:
        held = [p for p in snapshot.metadata.get("position_inventory", ())
                if isinstance(p, Mapping) and p.get("ticker") == snapshot.ticker]
        actionable = [intent for intent in intents if intent.action in (Action.ENTER, Action.RELAY)]
        if len(held) == 1 and position_role(held[0]) in POSITION_ROLES and held[0].get("custody_state") != "LAZARUS":
            allowed = [intent for intent in actionable
                       if intent.metadata.get("position_role") != position_role(held[0])
                       and intent.side is not None and intent.side.value != held[0].get("side")]
            if allowed:
                actionable = allowed
        if actionable:
            # A full physical turn owns the next leg even while the outgoing
            # contract thesis still points the old way. Smaller tactical
            # excursions remain lower priority than either parent-leg purpose.
            priorities = {"ARC_RETURN": 0, "MAIN_CONTRACT": 1, "TACTICAL_RETURN": 2}
            actionable.sort(key=lambda intent: priorities.get(
                (intent.metadata.get("mission") or {}).get("purpose"), 3))
            return (actionable[0],)
        return intents[:1]

    def _rail_fade_value(self, intent: ToolIntent, snapshot: MarketSnapshot) -> ToolIntent | None:
        if intent.side is self._owned_side:
            return intent
        mission = intent.metadata.get("mission") or {}
        full_arc = bool(intent.metadata.get("full_arc_return") is True
                        or intent.metadata.get("position_role") == "PRIMARY"
                        and mission.get("purpose") == "ARC_RETURN")
        genuine_heist = bool(intent.tool == "MARKET_HEIST"
            and (snapshot.metadata.get("heist") or {}).get("qualified_box") is True
            and (snapshot.metadata.get("heist") or {}).get("release_confirmed") is not True)
        # Smooth Rail ownership is deliberately low-frequency. Ordinary local
        # Mountain pauses do not earn a paid counter-fade. A source-qualified
        # whole-parent/full-arc turn can still relay before EMA9 visibly curls;
        # a genuine repeatable Heist box keeps its own tactical fade toolkit.
        if not (full_arc or genuine_heist):
            return None
        if "mission_context" in snapshot.metadata:
            return replace(intent, metadata={**intent.metadata,
                "rail_tactical_value": {"parent_side": self._owned_side.value if self._owned_side else None,
                    "basis": "FULL_PARENT_ARC_OR_GENUINE_HEIST_ONLY",
                    "full_arc_return": full_arc, "genuine_heist": genuine_heist,
                    "opening_time_used_as_permission": False}})
        context = snapshot.metadata.get("contract_value_context") or {}
        geometry = snapshot.metadata.get("current_geometry") or {}
        target, btc = number(context.get("target")), number(geometry.get("btc_price"))
        target_favors_side = bool(context.get("ticker") == snapshot.ticker
            and context.get("target_source") == "KALSHI_MARKET_FLOOR_STRIKE"
            and target is not None and btc is not None and intent.side is not None
            and (btc-target) * (1 if intent.side is Side.YES else -1) >= 0)
        spine = number(geometry.get("ema30"))
        sign = 1 if intent.side is Side.YES else -1
        target_in_return_corridor = bool(context.get("ticker") == snapshot.ticker
            and context.get("target_source") == "KALSHI_MARKET_FLOOR_STRIKE"
            and target is not None and btc is not None and spine is not None
            and sign * (spine-btc) > 0 and sign * (target-btc) >= 0
            and sign * (spine-target) >= 0)
        age = snapshot.contract_age_s
        ceiling = .40 if age < 60 else .42 if age < 120 else .44
        ask = snapshot.ask_for(intent.side) if intent.side else None
        opening_value = bool(0 <= age < 240 and ask is not None and ask <= ceiling)
        if not target_favors_side and not target_in_return_corridor and not opening_value:
            return None
        return replace(intent, metadata={**intent.metadata,
            "rail_tactical_value": {"parent_side": self._owned_side.value if self._owned_side else None,
                "target_context_favors_side": target_favors_side,
                "target_in_observed_spine_return_corridor": target_in_return_corridor,
                "opening_value": opening_value, "opening_ceiling": ceiling if opening_value else None,
                "target_is_not_settlement_prediction": True}})

    def _compatible_main_intent(self, snapshot: MarketSnapshot) -> ToolIntent | None:
        """Expose the one source-qualified MAIN mission under a local Heist owner.

        Heist keeps ownership of its box and tactical edges.  It may not suppress
        an independently qualified parent-leg MAIN entry merely because the box
        itself is waiting for an outer edge.  The Mountain helper supplies only
        the already-source-qualified MAIN/full-arc proposal; it does not acquire
        territory or emit local Mountain fades here.
        """
        if not self._territory_id or not isinstance(self._active_tool, MarketHeistTool):
            return None
        details = snapshot.metadata.get("mountain") or {}
        key = (self._territory_id, "MAIN_MOUNTAIN")
        tool = self._compatible_tools.get(key)
        if tool is None:
            tool = self._compatible_tools[key] = RollingMountainTool(
                territory_id=self._territory_id + ":MAIN_MOUNTAIN",
                owner_side=as_side(details.get("owner_side")),
                config=self.configs.mountain, mission_registry=self._mountain_mission_registry)
        assert isinstance(tool, RollingMountainTool)
        intent = tool.aligned_entry_intent(snapshot)
        if tool.main_proposal_review is not None:
            review = dict(tool.main_proposal_review)
            review["compatible_owner"] = "MARKET_HEIST"
            self.mission_policy.reviews.append(review)
        return intent

    def _rail_child_arc_value_intent(self, snapshot: MarketSnapshot) -> ToolIntent | None:
        """Expose one cheap local Mountain leg under an established Rail.

        Parent ownership does not transfer. Generic Rail fades remain disabled;
        this is a bounded child-arc value rider proven by current EMA9 geometry.
        """
        if (not self._territory_id or not self._is_rail(self._owned_territory)
                or self._owned_side is None or not isinstance(self._active_tool, RailTool)):
            return None
        # This is a long-Mountain/Rail breathing tactic, not an activation-time
        # guess. Require the parent Rail itself to have lived for two minutes.
        if snapshot.now_ts - self._active_tool.activated_at < 120.0:
            return None
        key = (self._territory_id, "RAIL_CHILD_ARC")
        tool = self._compatible_tools.get(key)
        if tool is None:
            tool = self._compatible_tools[key] = RollingMountainTool(
                territory_id=self._territory_id + ":RAIL_CHILD_ARC",
                owner_side=self._owned_side, config=self.configs.mountain,
                mission_registry=self._mountain_mission_registry)
        assert isinstance(tool, RollingMountainTool)
        tool.update_owner_side(self._owned_side)
        return tool.rail_child_arc_value_intent(snapshot, rail_side=self._owned_side)

    def _compatible_tactical_intents(self, snapshot: MarketSnapshot) -> tuple[ToolIntent, ...]:
        """Attach measured tactical tools without transferring the parent owner."""
        if not self._territory_id or not (self._is_rail(self._owned_territory)
                or self._is_mountain(self._owned_territory)):
            return ()
        details = snapshot.metadata.get("mountain") or {}
        context = snapshot.metadata.get("mission_context") or {}
        full_zone = any(qualified_full_arc_candidate(context, side.value)
                        for side in (Side.YES, Side.NO))
        if details.get("strong_active_release") is True:
            # Active expansion owns the parent.  A full-zone label cannot
            # manufacture an opposite companion while that expansion lives.
            # ReleaseWatcher is the only transfer path.
            return ()
        candidates: list[ToolIntent] = []
        if self._is_rail(self._owned_territory) and not self.configs.rail.opposite_fades:
            # Rail is a first-class parent territory.  Do not manufacture an
            # opposite Mountain/Heist trade while it owns the physical flow.
            # A true transfer is the ReleaseWatcher HANDOFF lane, not a fade.
            return ()
        if self._is_rail(self._owned_territory) and self.configs.mountain.tactical_fades_enabled:
            key = (self._territory_id, "MOUNTAIN")
            tool = self._compatible_tools.get(key)
            if tool is None:
                tool = self._compatible_tools[key] = RollingMountainTool(
                    territory_id=self._territory_id + ":TACTICAL_MOUNTAIN",
                    owner_side=as_side(details.get("owner_side")), config=self.configs.mountain,
                    mission_registry=self._mountain_mission_registry)
            offered = tuple(tool.on_market_event(snapshot))
            aligned = tool.aligned_entry_intent(snapshot)
            if (aligned is not None and aligned.side is not self._owned_side
                    and not any(intent.opportunity_id == aligned.opportunity_id
                                and intent.side is aligned.side and intent.action is aligned.action
                                for intent in offered)):
                offered += (replace(aligned, lane=Lane.TACTICAL,
                    metadata={**aligned.metadata, "position_role": "TACTICAL"}),)
            for intent in offered:
                if intent.action in (Action.ENTER, Action.RELAY):
                    qualified = self._rail_fade_value(intent, snapshot)
                    if qualified is not None:
                        candidates.append(qualified)
        # Strong active expansion returned above; no compatible opposite
        # strategy is allowed to coexist with it.
        heist = snapshot.metadata.get("heist") or {}
        if heist.get("qualified_box") is True and heist.get("release_confirmed") is not True:
            key = (self._territory_id, "HEIST")
            tool = self._compatible_tools.get(key)
            if tool is None:
                tool = self._compatible_tools[key] = MarketHeistTool(
                    territory_id=self._territory_id + ":TACTICAL_HEIST", config=self.configs.heist)
            for intent in tool.on_market_event(snapshot):
                if intent.action in (Action.ENTER, Action.RELAY):
                    qualified = self._rail_fade_value(intent, snapshot) if self._is_rail(self._owned_territory) else intent
                    if qualified is not None:
                        candidates.append(qualified)
        return tuple(candidates)

    def qualify_independent_role_mission(
        self, intent: ToolIntent, snapshot: MarketSnapshot, positions: Mapping[str, Any],
    ) -> ToolIntent:
        if intent.action not in (Action.ENTER, Action.RELAY):
            return intent
        held = [p for p in positions.values() if field(p, "ticker") == snapshot.ticker]
        if len(held) != 1 or field(held[0], "custody_state", "NORMAL") not in ("NORMAL", "RECOVERED_NORMAL"):
            return intent
        old = held[0]
        old_role, role = position_role(old), intent.metadata.get("position_role")
        old_entry = field(old, "entry_metadata", {}) or {}
        mission, old_mission = intent.metadata.get("physical_mission_id"), old_entry.get("physical_mission_id")
        source = number(snapshot.metadata.get("geometry_last_epoch_ms"))
        generation = snapshot.metadata.get("geometry_continuity_generation")
        if (old_role not in POSITION_ROLES or role not in POSITION_ROLES or role == old_role
                or not mission or not old_mission or mission == old_mission
                or snapshot.metadata.get("physical_current") is not True or source is None
                or type(generation) is not int or generation < 0
                or not current_source_is_fresh(snapshot, source, max_age_seconds=3.)):
            return intent
        proof = {"protocol": "NORMAL_PRIMARY_TACTICAL_V1", "ticker": snapshot.ticker,
            "held_position_id": str(field(old, "position_id")), "held_role": old_role,
            "held_mission_id": old_mission, "new_role": role, "mission_id": mission,
            "observed_ts": source / 1000, "source_ms": source,
            "continuity_generation": generation}
        source_receipt = current_source_receipt(snapshot, source, max_age_seconds=3.)
        if source_receipt is not None:
            proof.update(observed_ts=snapshot.now_ts, source_receipt=source_receipt)
        return replace(intent, metadata={**intent.metadata, "independent_role_mission": proof})

    @staticmethod
    def _recovery_entry_identity(intent: ToolIntent, snapshot: MarketSnapshot) -> Mapping[str, Any]:
        """Pin observed ownership, not a route name or extreme timestamp.

        This is retained evidence for a possible later recovery coexistence
        review. It neither earns an entry nor changes the ordinary entry gate.
        An unobserved parent origin remains explicitly unobserved.
        """
        parent = _current_mission_parent(snapshot)
        context = snapshot.metadata.get("mission_context") or {}
        mission = intent.metadata.get("mission") or {}
        scope = mission.get("parent_leg_id") if isinstance(mission, Mapping) else None
        if scope:
            proposed = (context.get("parents_by_id") or {}).get(scope) or {}
            source = number(snapshot.metadata.get("geometry_last_epoch_ms"))
            generation = snapshot.metadata.get("geometry_continuity_generation")
            known = number(proposed.get("known_ms"))
            if (context.get("current") is True and source is not None
                    and type(generation) is int and generation >= 0
                    and type(context.get("continuity_generation")) is int
                    and type(proposed.get("continuity_generation")) is int
                    and context.get("continuity_generation") == generation
                    and proposed.get("continuity_generation") == generation
                    and number(context.get("source_ms")) == source
                    and number(proposed.get("source_ms")) == source
                    and proposed.get("id") == scope
                    and proposed.get("status") in ("ACTIVE", "ANTICIPATED")
                    and proposed.get("invalidated") is not True
                    and intent.side is not None and proposed.get("side") == intent.side.value
                    and known is not None and 0 <= known <= source
                    and snapshot.metadata.get("physical_current") is True
                    and current_source_is_fresh(snapshot, source, max_age_seconds=3.)):
                parent = proposed
        if not parent:
            return {}
        geometry = snapshot.metadata.get("current_geometry") or {}
        return {"version": "PID4824_RECOVERY_PHYSICAL_IDENTITY_V1",
            "parent_leg_id": parent["id"], "parent_side": parent["side"],
            "parent_known_ms": parent.get("known_ms"),
            "parent_origin_ms": parent.get("origin_ms"),
            "parent_origin_observed": parent.get("origin_observed"),
            "arc_id": geometry.get("arc_id"),
            "continuity_generation": snapshot.metadata.get("geometry_continuity_generation"),
            "connection_epoch": geometry.get("connection_epoch"),
            "source_ms": geometry.get("epoch_ms")}

    @staticmethod
    def _measured_recovery_rejection(renewal: Mapping[str, Any], entry: Mapping[str, Any],
                                     entry_time: Any, observed: float) -> bool:
        """Only the existing post-fill retreat/retest/rejection can renew.

        The producer already measures this chapter. A supplied renewal label,
        a new high/low timestamp, or an unrelated older attempt is insufficient.
        """
        if renewal.get("renewal_kind") != "RETREAT_RETEST_REJECTION":
            return False
        prior = entry.get("physical_mission_id")
        times = [number(renewal.get(key)) for key in
                 ("retreat_source", "retest_source", "rejection_source")]
        paid = number(entry_time)
        # Source and local clocks can differ within the retained receipt's
        # allowed skew. A source event preceding the paid observation cannot
        # become post-fill merely because that source clock led local time.
        entry_source = number((entry.get("entry_geometry") or {}).get("epoch_ms"))
        if entry_source is None:
            entry_source = number((entry.get("recovery_physical_identity") or {}).get("source_ms"))
        if paid is not None and entry_source is not None:
            paid = max(paid, entry_source / 1000.)
        threshold = number(renewal.get("measured_retreat_threshold"))
        prices = [number(renewal.get(key)) for key in
                  ("retreat_extreme", "retreat_price", "retest_extreme", "rejection_price")]
        if (not prior or renewal.get("prior_attempt_id") != prior or paid is None
                or any(value is None or not math.isfinite(value) for value in times + prices)
                or threshold is None or not math.isfinite(threshold) or threshold <= 0
                or not paid < times[0] < times[1] < times[2] <= observed):
            return False
        retreat = prices[0] - prices[1]
        rejection = prices[2] - prices[3]
        return bool(abs(retreat) >= threshold and abs(rejection) >= threshold
                    and retreat * rejection > 0)

    def qualify_independent_recovery_mission(
        self, intent: ToolIntent, snapshot: MarketSnapshot, positions: Mapping[str, Any],
    ) -> ToolIntent:
        """Attach tool evidence for Commander's bounded recovery coexistence.

        No generic global opportunity gate is applied to normal entries. This
        proof is required only when the requested new lot would coexist with
        a Commander-approved recovery lot in the same exact contract.
        """
        if intent.action not in (Action.ENTER, Action.RELAY):
            return intent
        # Never accept a previously attached recovery proof as a substitute
        # for this exact current review. Pin fresh ownership on ordinary fills
        # too, so a later child/route cannot erase the original parent's wound.
        metadata = {k: v for k, v in intent.metadata.items()
                    if k not in ("independent_recovery_mission", "recovery_physical_identity")}
        identity = self._recovery_entry_identity(intent, snapshot)
        if identity:
            metadata["recovery_physical_identity"] = identity
        intent = replace(intent, metadata=metadata)
        def field(position: Any, name: str, default: Any = None) -> Any:
            return position.get(name, default) if isinstance(position, Mapping) else getattr(position, name, default)
        held = [p for p in positions.values() if field(p, "ticker") == snapshot.ticker]
        if not held or len(held) != 1 or any(field(p, "custody_state") != "LAZARUS" for p in held):
            return intent
        renewal = intent.metadata.get("physical_renewal")
        mission = intent.metadata.get("physical_mission_id")
        if not isinstance(renewal, Mapping) or renewal.get("independent") is not True or not mission:
            return intent
        if renewal.get("renewal_kind") not in {
            "NEW_ARC", "RETREAT_RETEST_REJECTION", "HEIST_NEW_EDGE_VISIT",
            "NEW_RAIL_TERRITORY", "CONFIRMED_RELEASE_TRANSFER",
            "PARENT_SCOPE_ACQUISITION",
        }:
            return intent
        observed = number(renewal.get("observed_at"))
        if (observed is None or not math.isfinite(observed)
                or not (0 <= snapshot.now_ts - observed <= 3.0
                    or current_source_is_fresh(snapshot, observed * 1000., max_age_seconds=3.))):
            return intent
        parent_scope = None
        if renewal.get("renewal_kind") == "PARENT_SCOPE_ACQUISITION":
            # Adapt the new persistent identity to the existing bounded
            # recovery protocol without relaxing loss/recovery qualification.
            # A renamed route or merely supplied parent ID is not proof.
            context = snapshot.metadata.get("mission_context") or {}
            held_mission = intent.metadata.get("mission") or {}
            parent_scope = held_mission.get("parent_leg_id")
            parent = (context.get("parents_by_id") or {}).get(parent_scope) or {}
            candidate = (context.get("candidates") or {}).get(intent.side.value if intent.side else "") or {}
            if (context.get("current") is not True
                    or number(context.get("source_ms")) != observed * 1000
                    or context.get("continuity_generation") != snapshot.metadata.get("geometry_continuity_generation")
                    or not parent_scope or parent.get("id") != parent_scope
                    or parent.get("status") not in ("ACTIVE", "ANTICIPATED")
                    or parent.get("supported") is not True or parent.get("invalidated") is True
                    or intent.side is None or parent.get("side") != intent.side.value
                    or candidate.get("parent_leg_id") != parent_scope
                    or not (candidate.get("entry_location_qualified") is True
                            or candidate.get("qualified_edge") is True)):
                return intent
        detached_ids = []
        for position in held:
            entry = field(position, "entry_metadata", {}) or {}
            key = (str(field(position, "ticker")), str(field(position, "territory_id")),
                   str(field(position, "opportunity_id")))
            if key not in self._recovery_detached:
                return intent
            previous_missions = {entry.get("physical_mission_id"), entry.get("entry_arc_id"),
                                 self._custody_physical_missions.get(key)}
            if mission in previous_missions or intent.opportunity_id == key[2]:
                return intent
            if parent_scope and parent_scope == ((entry.get("mission") or {}).get("parent_leg_id")
                    or (entry.get("recovery_physical_identity") or {}).get("parent_leg_id")):
                return intent
            if intent.side is as_side(field(position, "side")) and not parent_scope:
                old_identity = entry.get("recovery_physical_identity") or {}
                old_geometry = entry.get("entry_geometry") or {}
                geometry = snapshot.metadata.get("current_geometry") or {}
                old_parent = ((entry.get("mission") or {}).get("parent_leg_id")
                              or old_identity.get("parent_leg_id"))
                new_parent = identity.get("parent_leg_id")
                old_arc = entry.get("entry_arc_id") or old_identity.get("arc_id") or old_geometry.get("arc_id")
                new_arc = intent.metadata.get("entry_arc_id") or geometry.get("arc_id")
                same_parent = bool(old_parent and old_parent == new_parent)
                same_arc = bool(old_arc and old_arc == new_arc)
                # A currently witnessed new owner may supersede the local
                # swing before its display label changes. A reset/unknown
                # origin alone never proves that ownership changed.
                same_continuity = bool(old_identity and identity
                    and old_identity.get("continuity_generation") == identity.get("continuity_generation")
                    and old_identity.get("connection_epoch") == identity.get("connection_epoch"))
                origin = number(identity.get("parent_origin_ms"))
                known = number(identity.get("parent_known_ms"))
                current_source = number(identity.get("source_ms"))
                paid_source = number(old_identity.get("source_ms"))
                witnessed_after_reset = bool(identity.get("parent_origin_observed") is True
                    and None not in (origin, known, current_source, paid_source)
                    and paid_source < origin <= known <= current_source)
                new_owner = bool(old_parent and new_parent and old_parent != new_parent
                    and (same_continuity or witnessed_after_reset))
                reset_without_new_owner = bool(old_identity and not same_continuity and not new_owner)
                measured_rejection = self._measured_recovery_rejection(
                    renewal, entry, field(position, "entry_time"), observed)
                if ((same_parent or (same_arc and not new_owner) or reset_without_new_owner)
                        and not measured_rejection):
                    return intent
            detached_ids.append(str(field(position, "position_id")))
        proof = {"detached_position_ids": detached_ids, "mission_id": str(mission),
                 "independently_renewed": True, "observed_ts": observed,
                 "continuity_generation": int(snapshot.metadata.get("geometry_continuity_generation", 0))}
        source_receipt = current_source_receipt(snapshot, observed * 1000., max_age_seconds=3.)
        if source_receipt is not None:
            proof.update(observed_ts=snapshot.now_ts, source_ms=observed * 1000.,
                         source_receipt=source_receipt)
        return replace(intent, metadata={**intent.metadata, "independent_recovery_mission": proof})

    def commit_accepted_intent(
        self,
        intent: ToolIntent,
        snapshot: MarketSnapshot,
        *, position_id: str | None = None,
    ) -> None:
        """Record a committed PAPER fill; observing an intent never consumes it."""
        if intent.action not in (Action.ENTER, Action.RELAY) or not intent.opportunity_id:
            return
        tool = next((candidate for candidate in (
                        self._active_tool, self._release_watcher, self._heist_overlay,
                        self._dual_main_rail, self._dual_tactical_heist,
                        *self._compatible_tools.values())
                     if candidate is not None and candidate.name == intent.tool
                     and candidate.territory_id == intent.territory_id), None)
        key = (snapshot.ticker, intent.territory_id, intent.opportunity_id)
        if tool is None:
            if intent.metadata.get("commander_primary_candidate") is not True:
                raise ValueError("Committed intent has no exact tool/territory owner")
            # OneCommander-owned missions have no specialist custody owner by
            # design.  Preserve exact mission consumption/position identity in
            # the rack ledger without fabricating a tool authority. Commander
            # will manage the position directly from current evidence.
            self.mission_policy.committed(intent, snapshot.ticker)
            self._filled_tools[key] = None
            if position_id is not None:
                self._position_keys[str(position_id)] = key
            return
        tool.mark_entry_filled(intent.opportunity_id, ticker=snapshot.ticker)
        self.mission_policy.committed(intent, snapshot.ticker)
        self._filled_tools[key] = tool
        if position_id is not None:
            self._position_keys[str(position_id)] = key

    def mark_position_closed(
        self, *, ticker: str, territory_id: str,
        opportunity_id: str | None = None, release_handoff: bool = False,
        position_id: str | None = None,
    ) -> None:
        """Close exact custody; old-contract finality cannot rearm a new slice."""
        keys = [key for key in self._filled_tools
                if key[0] == ticker and key[1] == territory_id
                and (opportunity_id is None or key[2] == opportunity_id)]
        for key in keys:
            origin = self._filled_tools.pop(key)
            custody = self._custody_tools.pop(key, None)
            self._recovery_detached.discard(key)
            manager_mission = self._custody_mission_ids.pop(key, key[2])
            self._custody_physical_missions.pop(key, None)
            for tool in {id(tool): tool for tool in (origin, custody) if tool is not None}.values():
                other_active = self._tool_has_active_ticker(tool, ticker)
                local_mission = manager_mission if tool is custody else key[2]
                tool.mark_position_closed(ticker=ticker, opportunity_id=local_mission,
                                          release_handoff=release_handoff)
                latches = getattr(tool, "_exit_latches", {})
                latches.pop(key[2], None)
                latches.pop(manager_mission, None)
                tool.sync_tactical_inventory(ticker=ticker, present=other_active)
        if position_id is not None:
            self._position_keys.pop(str(position_id), None)

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
        context: dict[str, Any] = {"custody_tool": manager.name,
            "position_role": position_role(position)}
        result = self._last_result if self._last_snapshot_ts == snapshot.now_ts else None
        side = as_side(position.get("side"))
        if result is not None:
            release_side = next((intent.side for intent in result.overlay_intents
                                 if result.handoff_confirmed and intent.side is not None), None)
            context = {**context,
                "owned_territory": result.owned_territory.value,
                "owned_side": result.owned_side.value if result.owned_side else None,
                "raw_territory": result.raw_decision.territory.value,
                "confirmed_release_side": release_side.value if release_side else None,
            }
            next_manager = manager
            if release_side is side and side is not None and self._release_watcher is not None:
                next_manager = self._release_watcher
            elif (position_role(position) != "TACTICAL" and self.active_rail_tool is not None
                  and self.active_rail_tool.side is side):
                next_manager = self.active_rail_tool
            if next_manager is not manager:
                previous_manager = manager
                # Adopt existing inventory without emitting another entry or
                # changing its original economic/physical entry evidence.
                if isinstance(next_manager, ReleaseWatcher):
                    self._custody_mission_ids[key] = next_manager.adopt_position(ticker=key[0])
                    self._custody_physical_missions[key] = next_manager.physical_mission_id()
                else:
                    next_manager.mark_entry_filled(key[2], ticker=key[0])
                    self._custody_mission_ids[key] = key[2]
                    self._custody_physical_missions[key] = f"{next_manager.territory_id}:RAIL_CHAPTER"
                self._custody_tools[key] = next_manager
                manager = next_manager
                if key in self._recovery_detached:
                    next_manager.detach_position_custody(ticker=key[0], opportunity_id=self._custody_mission_ids[key])
                self._sync_tool_slots(key)
                # Management transfer is not an economic close or mission
                # rearm. Retire only this prior manager's local occupancy,
                # retaining any other lot it still manages for this ticker.
                previous_manager.sync_tactical_inventory(ticker=key[0],
                    present=self._tool_has_active_ticker(previous_manager, key[0]))
            context["custody_tool"] = manager.name
            context["custody_physical_mission_id"] = self._custody_physical_missions.get(key)
        managed_snapshot = replace(snapshot, metadata={**snapshot.metadata, "tool_rack": context})
        return tuple(manager.manage_position(position, managed_snapshot))

    def handoff_intent(
        self, position: Mapping[str, Any], snapshot: MarketSnapshot,
    ) -> ToolIntent | None:
        """Review the next Mountain leg while exact outgoing custody remains.

        This is a proposal for one coordinated sell-then-buy decision, never
        permission to overlap inventory or skip current native execution checks.
        A retired tool cannot use this path to compete with the present owner.
        """
        result = self._last_result if self._last_snapshot_ts == snapshot.now_ts else None
        tool = self.active_mountain_tool
        key = self._position_key(position)
        origin = self._filled_tools.get(key)
        manager = self._custody_tools.get(key, origin)
        if (result is None or result.handoff_confirmed or tool is None
                or manager is not tool or key in self._recovery_detached
                or str(position.get("ticker") or "") != snapshot.ticker):
            return None
        intent = tool.handoff_intent(position, snapshot)
        if intent is None:
            return None
        reviewed = self.mission_policy.review(self._physical_intent(intent, snapshot), snapshot)
        return reviewed if reviewed.action in (Action.ENTER, Action.RELAY) else None

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
