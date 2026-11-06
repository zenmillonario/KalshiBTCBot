from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from strategy_core.mission_scopes import qualified_full_arc_candidate as _full_arc_candidate
from strategy_core.tools.base import StrategyTool
from strategy_core.position_roles import position_role
from strategy_core.source_freshness import current_source_is_fresh
from strategy_core.tools.management import (
    ARC_CONTRACT_PROFIT_REASON, as_side, entry_metadata, floor_policy, mapping, number, opposing_transfer,
    ordinary_profit_hold_reason, position_intent, mission_collection_evidence,
    runner_harvest_update, opposing_transfer,
)
from strategy_core.types import (
    Action,
    Lane,
    MarketSnapshot,
    Side,
    ToolIntent,
)


def _side(
    value: Any,
) -> Side | None:
    if isinstance(value, Side):
        return value
    if value is None:
        return None
    text = str(value).upper()
    if text == "YES":
        return Side.YES
    if text == "NO":
        return Side.NO
    return None


def _opposite(
    side: Side | None,
) -> Side | None:
    if side is Side.YES:
        return Side.NO
    if side is Side.NO:
        return Side.YES
    return None


@dataclass(frozen=True)
class MountainConfig:
    regular_size: float = 10.0
    a_plus_size: float = 15.0
    exceptional_size: float = 25.0
    soft_max_price: float = 0.20
    # Explicit hard restraints loaded from mountain.json.  They used to be
    # present in configuration but were never part of the runtime config.
    mid_leg_entries: bool = False
    strong_active_release_defers_fade: bool = True
    tactical_fades_enabled: bool = False
    aligned_leg_entries_enabled: bool = False
    # Current PAPER doctrine: once an EMA9 edge entry is paid, custody remains
    # with that leg until the next terminal EMA9 edge.  Numeric profit floors,
    # release overlays and generic failure heuristics do not cut the leg early.
    edge_only_custody: bool = True
    late_counter_window_s: float = 60.0
    late_counter_max_ask: float = 0.01
    floor_arm_roi: float = 1.00
    floor_trail_fraction: float = 0.10
    floor_min_age_s: float = 30.0
    floor_immediate_arm_roi: float | None = None
    ordinary_min_age_s: float = 30.0
    first_exhaustion_review_s: float = 120.0
    failure_persistence_s: float = 6.0
    rollover_skip_last_s: float = 240.0
    rollover_reentry_window_s: float = 240.0
    rollover_reentry_max_ask: float = 0.20
    edge_value_max_ask: float = 0.20
    cheap_hover_min_ask: float = 0.11
    cheap_hover_max_ask: float = 0.16
    cheap_hover_min_seconds_left: float = 300.0
    small_arc_immediate_max_age_s: float = 180.0
    small_arc_immediate_max_ask: float = 0.20
    fast_handoff_max_arc_age_s: float = 360.0
    fast_handoff_max_terminal_window_age_s: float = 90.0
    value_ladder_stage1_ask: float = 0.10
    value_ladder_stage2_ask: float = 0.15
    value_ladder_stage1_seconds: float = 90.0
    value_ladder_stage2_seconds: float = 150.0
    wide_top_patient_target_ask: float = 0.15
    wide_top_patient_seconds: float = 240.0
    # PID10168 low/wide sideways Mountain execution class.  This is deliberately
    # separate from regular/tall Mountain timing and from 15m Slow-Rolling/Rail.
    low_wide_min_parent_age_s: float = 90.0
    low_wide_max_parent_age_s: float = 600.0
    low_wide_max_average_ema9_rate_btc_s: float = 0.20
    low_wide_max_abs_ema_gap_btc: float = 65.0
    low_wide_max_parent_amplitude_btc: float = 150.0
    low_wide_min_child_arcs: int = 2
    low_wide_stage1_ask: float = 0.30
    low_wide_stage2_ask: float = 0.35
    low_wide_hard_max_ask: float = 0.40
    low_wide_stage1_seconds: float = 45.0
    low_wide_stage2_seconds: float = 90.0
    low_wide_profit_arm_roi: float = 0.65
    low_wide_profit_trail_fraction: float = 0.03
    # PID20964 parallel-fakeout governance. Low/wide terrain waits through
    # the contract open, establishes a parent lean, and only rents the
    # opposite return after a real outer rejection. A late exception exists
    # only for extremely cheap confirmed fakeouts with enough time to return.
    low_wide_contract_open_wait_s: float = 60.0
    low_wide_late_min_seconds_left: float = 120.0
    low_wide_late_exception_max_ask: float = 0.10


class AlternatingMountainTool(
    StrategyTool
):
    """PID19420-style clean Mountain hard relay.

    The tool does not buy the middle. It waits for a mature physical extreme,
    then uses stall/hesitation/failed re-extension/retreat to relay into the
    next EMA9 leg before a perfect visible curl is required.
    """

    name = "ALTERNATING_MOUNTAIN"

    def __init__(
        self,
        *,
        territory_id: str,
        owner_side: Side | None,
        config: MountainConfig | None = None,
        mission_registry: dict[tuple[str, Side], dict[str, Any]] | None = None,
    ) -> None:
        self.territory_id = territory_id
        self.owner_side = owner_side
        self.config = (
            config
            or MountainConfig()
        )
        self._active = True
        self._current_ticker: str | None = None
        self._open_tickers: set[str] = set()
        self._open_positions: dict[str, set[str]] = {}
        self._detached_positions: set[tuple[str, str]] = set()
        self._filled_opportunities: set[tuple[str, str]] = set()
        self._edge_anchor: tuple[str, Side, float, str] | None = None
        self._exit_latches: dict[tuple[str, str], str] = {}
        self._failure_watches: dict[tuple[str, str], dict[str, Any]] = {}
        self._missions = mission_registry if mission_registry is not None else {}
        self._offered_missions: dict[str, tuple[str, Side]] = {}
        # Diagnostic only: why the current contract thesis did or did not
        # produce a physical proposal. Eligibility remains the rack's review.
        self.main_proposal_review: dict[str, Any] | None = None
        # A terminal edge discovered in the final rollover window is not bought
        # in the expiring contract. Preserve only that exact earned side/edge
        # for the next ticker's cheap opening window.
        self._rollover_pending: dict[str, Any] | None = None
        # A physically earned ordinary Mountain edge may arm the next leg and
        # then wait for price value. The edge itself is not consumed by an
        # expensive first quote. This is deliberately separate from Rail and
        # from the rollover carry.
        self._armed_value_entry: dict[str, Any] | None = None
        self._runner_harvest: dict[str, dict[str, Any]] = {}

    def _observe_mission(self, details: Mapping[str, Any], owner: Side,
                         snapshot: MarketSnapshot) -> dict[str, Any] | None:
        """A paid attempt survives quote/ticker changes and strict new extremes.

        A distinct arc, or an actually observed retreat -> retest -> rejection
        chapter inside the same arc, can create a new attempt. Elapsed time and
        trade count never do. Every leg of renewal occurs after the prior fill.
        """
        arc_id = str(details.get("current_arc_id") or "")
        if not arc_id:
            return None
        key = (arc_id, owner)
        source_ms = number(details.get("source_ms"))
        source = source_ms / 1000 if source_ms is not None else None
        extreme = number(details.get("owner_extreme_btc"))
        price = number(details.get("current_btc"))
        state = self._missions.get(key)
        cold_origin = details.get("arc_origin_observed") is False
        paid = [(old_key, old_state) for old_key, old_state in self._missions.items()
                if old_state.get("consumed") and old_state is not state]
        earned_chapter = bool(state and (state.get("renewal") or {}).get("renewal_kind")
                             == "RETREAT_RETEST_REJECTION")
        if cold_origin and not earned_chapter and (state is None or not state.get("consumed")):
            same_side_paid = [(old_key, old_state) for old_key, old_state in paid if old_key[1] is owner]
            if same_side_paid:
                _, previous = max(same_side_paid, key=lambda item:
                    item[1].get("consumed_source") or item[1].get("last_source") or 0)
                # A reconnect can rename an unfinished physical arc. Preserve
                # its paid identity; no unseen retreat/reclaim is credited.
                self._missions[key] = previous
                previous.update(last_source=source, latest_price=price,
                    stage="SEEK_RETREAT", post_fill_extreme=price)
                for field in ("retreat_source", "retreat_extreme", "retreat_price", "retest_source", "retest_extreme"):
                    previous.pop(field, None)
                return previous
        if state is None:
            mission_id = f"MOUNTAIN:{arc_id}:{owner.value}:ATTEMPT:0"
            state = self._missions[key] = {
                "generation": 0, "mission_id": mission_id, "consumed": False,
                "last_source": source, "stage": "SEEK_RETREAT",
                "latest_price": price,
                "continuity_unproven": cold_origin and bool(paid),
                "renewal": {"observed_at": source, "renewal_kind": "NEW_ARC",
                    "independent": source is not None and details.get("arc_origin_ms") is not None
                        and details.get("arc_origin_observed") is not False,
                    "prior_attempt_id": None},
            }
        if source is None or (state.get("last_source") is not None and source <= state["last_source"]):
            return state
        previous_source = state.get("last_source")
        state["last_source"] = source
        state["latest_price"] = price
        if previous_source is not None and source - previous_source > 15.0:
            # Missing source can hide a whole reclaim. Never infer its outcome.
            state.update(stage="SEEK_RETREAT", post_fill_extreme=price)
            for field in ("retreat_source", "retreat_extreme", "retreat_price", "retest_source", "retest_extreme"):
                state.pop(field, None)
        if not state["consumed"] or state.get("active_paid") or price is None or extreme is None:
            return state
        tolerance = max(0.0, number(details.get("edge_tolerance_dollars")) or 0.0)
        threshold = max(2.0, number(details.get("retreat_threshold")) or tolerance)
        sign = 1.0 if owner is Side.YES else -1.0
        post_fill_extreme = state.get("post_fill_extreme")
        if post_fill_extreme is None or sign * (price - post_fill_extreme) > 0:
            post_fill_extreme = state["post_fill_extreme"] = price
        retreat = sign * (post_fill_extreme - price)
        stage = state["stage"]
        if stage == "SEEK_RETREAT" and retreat >= threshold:
            state.update(stage="SEEK_RETEST", retreat_source=source,
                         retreat_extreme=post_fill_extreme, retreat_price=price)
        elif stage == "SEEK_RETEST":
            if sign * (price - state["retreat_price"]) < 0:
                state["retreat_price"] = price
            if (source > state["retreat_source"]
                    and sign * (state["retreat_extreme"] - price) <= tolerance):
                state.update(stage="SEEK_REJECTION", retest_source=source, retest_extreme=price)
        elif stage == "SEEK_REJECTION":
            if sign * (price - state["retest_extreme"]) > 0:
                state.update(retest_extreme=price, retest_source=source)
            elif (source > state["retest_source"]
                    and sign * (state["retest_extreme"] - price) >= threshold
                    and details.get("strong_active_release") is not True
                    and details.get("spent_edge") is not True):
                previous_id = state["mission_id"]
                state["generation"] += 1
                state.update(mission_id=f"MOUNTAIN:{arc_id}:{owner.value}:ATTEMPT:{state['generation']}",
                    consumed=False, continuity_unproven=False, stage="SEEK_RETREAT",
                    renewal={"observed_at": source, "renewal_kind": "RETREAT_RETEST_REJECTION",
                        "independent": True, "prior_attempt_id": previous_id,
                        "retreat_source": state["retreat_source"], "retest_source": state["retest_source"],
                        "rejection_source": source, "retreat_extreme": state["retreat_extreme"],
                        "retreat_price": state["retreat_price"], "retest_extreme": state["retest_extreme"],
                        "rejection_price": price, "measured_retreat_threshold": threshold})
        return state

    @property
    def active(self) -> bool:
        return self._active

    def update_owner_side(
        self,
        side: Side | None,
    ) -> None:
        if side is not None:
            self.owner_side = side

    def _details(
        self,
        snapshot: MarketSnapshot,
    ) -> Mapping[str, Any]:
        raw = snapshot.metadata.get(
            "mountain",
            {},
        )
        return (
            raw
            if isinstance(raw, Mapping)
            else {}
        )

    @staticmethod
    def _parent_geometry(snapshot: MarketSnapshot) -> Mapping[str, Any]:
        """Use the same current whole-parent measurement as its entry proof.

        A small native child can be young or already at EMA9 while the larger
        parent is at its own edge.  Its labels cannot replace that parent's
        observed geometry.  Archived/foreign packets are not current evidence.
        """
        context = mapping(snapshot.metadata.get("mission_context"))
        parent = mapping(context.get("parent"))
        geometry = mapping(parent.get("geometry"))
        current = mapping(snapshot.metadata.get("current_geometry"))
        source = number(context.get("source_ms"))
        generation = context.get("continuity_generation")
        limit = number(snapshot.metadata.get("geometry_max_source_age_seconds")) or 5.
        if (not geometry or context.get("current") is not True
                or snapshot.metadata.get("physical_current") is not True
                or parent.get("status") != "ACTIVE" or parent.get("invalidated") is True
                or source is None or not current_source_is_fresh(snapshot, source, max_age_seconds=limit)
                or number(geometry.get("source_ms")) != source
                or number(current.get("epoch_ms")) != source
                or number(parent.get("source_ms")) != source
                or type(generation) is not int
                or parent.get("continuity_generation") != generation
                or snapshot.metadata.get("geometry_continuity_generation") != generation
                or geometry.get("current_arc_id") != parent.get("id")
                or not parent.get("id")
                or _side(geometry.get("owner_side")) is not _side(parent.get("side"))
                or _side(parent.get("side")) is None):
            return {}
        for measured, raw in (("current_btc", "btc_price"), ("current_ema9", "ema9"),
                              ("current_ema30", "ema30")):
            value = number(current.get(raw))
            if value is None or value <= 0 or number(geometry.get(measured)) != value:
                return {}
        return geometry

    def _entry_details(self, snapshot: MarketSnapshot) -> Mapping[str, Any]:
        context = mapping(snapshot.metadata.get("mission_context"))
        parent = mapping(context.get("parent"))
        parent_geometry = self._parent_geometry(snapshot)
        owner = _side(parent_geometry.get("owner_side"))
        opposite = _opposite(owner)
        if (opposite is not None and _full_arc_candidate(
                context, opposite.value,
                number(parent_geometry.get("source_ms")))):
            return parent_geometry
        if "geometry" in parent and any(_full_arc_candidate(
                context, side.value, number(context.get("source_ms")))
                for side in (Side.YES, Side.NO)):
            return {}
        return self._details(snapshot)

    def _arc_entry_scale(self, snapshot: MarketSnapshot, side: Side) -> dict[str, Any]:
        """Copy the earned full-leg comparison family at the actual entry.

        A bare retest can independently authorize its entry, but cannot
        invent a duration family for a later contract-fit exception. All
        fields are new scalars; later parent geometry cannot enrich this
        position's entry evidence.
        """
        context = mapping(snapshot.metadata.get("mission_context"))
        parent = mapping(context.get("parent"))
        details = self._parent_geometry(snapshot)
        proof = mapping(details.get("full_leg_scale_evidence"))
        candidate = mapping(mapping(context.get("candidates")).get(side.value))
        source = number(details.get("source_ms"))
        received = proof.get("comparable_current_leg_mature") is True
        minutes = proof.get("completed_minute_parent_mature") is True
        family = "received_parent" if received else "completed_minute_parent" if minutes else None
        valid = bool(details and source is not None
            and _full_arc_candidate(context, side.value, source)
            and proof.get("qualified") is True
            and proof.get("basis") == "INDEPENDENT_CURRENT_PARENT_SCALE_V1"
            and proof.get("parent_id") == parent.get("id")
            and proof.get("side") == parent.get("side")
            and number(proof.get("source_ms")) == source
            and proof.get("comparison_family") == family and family is not None)
        return {"version": "ARC_ENTRY_SCALE_V1", "qualified": valid,
            "parent_id": parent.get("id"), "side": parent.get("side"),
            "incoming_parent_id": candidate.get("parent_leg_id"), "incoming_side": side.value,
            "source_ms": source, "continuity_generation": context.get("continuity_generation"),
            "comparison_family": family if valid else None,
            "qualification_basis": "INDEPENDENT_RECEIVED_PARENT_MATURITY" if valid and received
                else "INDEPENDENT_COMPLETED_MINUTE_PARENT_MATURITY" if valid else "NO_EARNED_TIMING_FAMILY",
            "comparable_current_leg_mature": received, "completed_minute_parent_mature": minutes,
            "qualification_evidence": {"qualified": valid,
                "basis": proof.get("basis"), "parent_id": proof.get("parent_id"),
                "side": proof.get("side"), "source_ms": number(proof.get("source_ms")),
                "continuity_generation": context.get("continuity_generation"),
                "comparable_current_leg_mature": received,
                "completed_minute_parent_mature": minutes,
                "comparison_family": family if valid else None},
            "frozen_at_entry": True, "later_family_switch_allowed": False}

    def _mountain_size(self, ask: float, *, cheap_hover: bool = False) -> float:
        if cheap_hover:
            return self.config.exceptional_size
        if ask <= self.config.edge_value_max_ask:
            return self.config.a_plus_size
        return self.config.regular_size

    def _entry_floor_policy(self, low_wide: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Persist mechanical protection on the entry itself.

        PID20964 trade #2 reached +110% executable gross but had no floor because
        the armed-value entry path did not store any floor policy.  Every
        Mountain entry now carries its mechanical protection into the ledger,
        even if territory ownership changes before the next management beat.
        """
        policy = dict(floor_policy(self.config))
        if low_wide is not None and low_wide.get("qualified") is True:
            arm = number(low_wide.get("profit_arm_roi")) or self.config.low_wide_profit_arm_roi
            trail = number(low_wide.get("profit_trail_fraction")) or self.config.low_wide_profit_trail_fraction
            policy.update(
                arm_roi=arm,
                trail_fraction=trail,
                min_age_s=0.0,
                immediate_arm_roi=arm,
                first_arm_allowed=True,
                first_arm_from_current_bid=True,
                roi_trail_tiers=[[arm, trail], [1.0, trail], [1.5, min(trail, .025)], [6.0, .02]],
                tighten_armed_to=None,
                profit_protection_state="PID20964_LOW_WIDE_TIGHT_PEAK_LOCK",
                profit_policy_revision="PID20964_LOW_WIDE_65_3_V1",
            )
        return policy

    def _small_fast_arc_edge(self, snapshot: MarketSnapshot, details: Mapping[str, Any],
                             ask: float | None) -> bool:
        if ask is None or not 0 < ask <= self.config.small_arc_immediate_max_ask:
            return False
        age = number(mapping(details.get("diagnostics")).get("current_age_s"))
        parent = mapping(details.get("parent_structure"))
        heist = mapping(snapshot.metadata.get("heist"))
        entry_side = _opposite(_side(details.get("owner_side")))
        geometry = mapping(snapshot.metadata.get("current_geometry"))
        trend180 = str(geometry.get("trend_direction_180s") or "").upper()
        trend_side = Side.YES if trend180 == "UP" else Side.NO if trend180 == "DOWN" else None
        return bool(age is not None and age <= self.config.small_arc_immediate_max_age_s
            and details.get("terminal_evidence_qualified") is True
            and details.get("strong_active_release") is not True
            and entry_side is not None and trend_side is entry_side
            and parent.get("extended_parent") is not True
            and parent.get("slow_rolling_parent") is not True
            and parent.get("blocks_child_reversal") is not True
            and heist.get("qualified_box") is not True)

    def _cheap_hover_edge(self, details: Mapping[str, Any], ask: float | None,
                          *, seconds_left: float) -> bool:
        if ask is None or not (self.config.cheap_hover_min_ask <= ask <= self.config.cheap_hover_max_ask):
            return False
        if seconds_left < self.config.cheap_hover_min_seconds_left:
            return False
        parent = mapping(details.get("parent_structure"))
        gap = mapping(details.get("ema9_ema30_gap_edge_guard"))
        return bool(details.get("mature_edge") is True
            and (details.get("stall") is True or details.get("hesitation") is True
                 or details.get("comparable_slow_edge") is True)
            and details.get("strong_active_release") is not True
            and details.get("spent_edge") is not True
            and parent.get("extended_parent") is not True
            and parent.get("slow_rolling_parent") is not True
            and parent.get("blocks_child_reversal") is not True
            and gap.get("terminal_blocked_while_gap_expands_below_previous") is not True)


    def _wide_top_value_window(self, details: Mapping[str, Any]) -> bool:
        parent = mapping(details.get("parent_structure"))
        diagnostics = mapping(details.get("diagnostics"))
        age = number(diagnostics.get("current_age_s"))
        return bool(
            parent.get("extended_parent") is True
            or parent.get("slow_rolling_parent") is True
            or (age is not None and age > self.config.fast_handoff_max_arc_age_s)
        )

    def _low_wide_sideways_context(
        self, snapshot: MarketSnapshot, details: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """PID10168: isolate only low, broad, sideways Mountain execution.

        Regular/tall arcs keep the 10c->15c->20c ladder unchanged.  This
        classifier is intentionally narrow: a multi-child parent must have
        lived long enough to be broad, but not long enough to be the 15-minute
        Slow-Rolling/Rail regime; its average EMA9 travel must remain slow and
        its current EMA9/EMA30 separation must still be close to the spine.
        Release/breakout chapters never qualify.
        """
        if (snapshot.metadata.get("release_in_progress") is True
                or snapshot.metadata.get("parallel_release_rail") is True
                or details.get("strong_active_release") is True):
            return None
        parent = mapping(details.get("parent_structure"))
        age = number(parent.get("parent_age_s"))
        amplitude = number(parent.get("parent_amplitude"))
        rate = number(parent.get("parent_average_ema9_rate_btc_s"))
        child_count = parent.get("child_arc_count")
        geometry = mapping(snapshot.metadata.get("current_geometry"))
        ema_gap = number(geometry.get("ema_gap"))
        if ema_gap is None:
            e9, e30 = number(geometry.get("ema9")), number(geometry.get("ema30"))
            ema_gap = e9 - e30 if e9 is not None and e30 is not None else None
        if not (age is not None and amplitude is not None and rate is not None
                and type(child_count) is int and ema_gap is not None):
            return None
        qualified = bool(
            self.config.low_wide_min_parent_age_s <= age <= self.config.low_wide_max_parent_age_s
            and parent.get("slow_rolling_parent") is not True
            and amplitude <= self.config.low_wide_max_parent_amplitude_btc
            and rate <= self.config.low_wide_max_average_ema9_rate_btc_s
            and abs(ema_gap) <= self.config.low_wide_max_abs_ema_gap_btc
            and child_count >= self.config.low_wide_min_child_arcs
        )
        if not qualified:
            return None
        return {
            "qualified": True,
            "basis": "PID20964_LOW_WIDE_PARALLEL_FAKEOUT_V1",
            "parent_id": parent.get("parent_id"),
            "parent_side": parent.get("parent_side"),
            "parent_age_s": age,
            "parent_amplitude_btc": amplitude,
            "parent_average_ema9_rate_btc_s": rate,
            "child_arc_count": child_count,
            "current_abs_ema9_ema30_gap_btc": abs(ema_gap),
            "min_parent_age_s": self.config.low_wide_min_parent_age_s,
            "max_parent_age_s": self.config.low_wide_max_parent_age_s,
            "max_average_ema9_rate_btc_s": self.config.low_wide_max_average_ema9_rate_btc_s,
            "max_abs_ema9_ema30_gap_btc": self.config.low_wide_max_abs_ema_gap_btc,
            "max_parent_amplitude_btc": self.config.low_wide_max_parent_amplitude_btc,
            "min_child_arcs": self.config.low_wide_min_child_arcs,
            "entry_stage1_ask": self.config.low_wide_stage1_ask,
            "entry_stage2_ask": self.config.low_wide_stage2_ask,
            "entry_hard_max_ask": self.config.low_wide_hard_max_ask,
            "profit_arm_roi": self.config.low_wide_profit_arm_roi,
            "profit_trail_fraction": self.config.low_wide_profit_trail_fraction,
            "contract_open_wait_s": self.config.low_wide_contract_open_wait_s,
            "late_min_seconds_left": self.config.low_wide_late_min_seconds_left,
            "late_exception_max_ask": self.config.low_wide_late_exception_max_ask,
            "ema30_directional_trade_authority": False,
        }

    def _low_wide_fakeout_context(
        self, snapshot: MarketSnapshot, details: Mapping[str, Any],
        low_wide: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Require a real outer rejection before a low/wide opposite renter.

        PID20964 showed that the old low/wide class could treat the first local
        shoulder as an edge.  In this territory the contract must first lean
        with the living parent, push/fake outside, then *fail*: failed
        re-extension, meaningful retreat, or stall+hesitation together.  A
        widening EMA9/EMA30 gap below the previous same-side envelope remains
        an explicit NO-ENTRY condition. EMA30 is descriptive only.
        """
        parent = mapping(details.get("parent_structure"))
        owner = _side(details.get("owner_side"))
        parent_side = _side(parent.get("parent_side"))
        gap = mapping(details.get("ema9_ema30_gap_edge_guard"))
        contract_ready = snapshot.contract_age_s >= self.config.low_wide_contract_open_wait_s
        lean_agrees = bool(owner is not None and parent_side is owner)
        rejection = bool(
            details.get("failed_reextension") is True
            or details.get("meaningful_retreat") is True
            or (details.get("stall") is True and details.get("hesitation") is True)
        )
        terminal = bool(
            details.get("terminal_evidence_qualified") is True
            and details.get("mature_edge") is True
        )
        gap_blocked = gap.get("terminal_blocked_while_gap_expands_below_previous") is True
        confirmed = bool(
            low_wide.get("qualified") is True
            and contract_ready
            and lean_agrees
            and terminal
            and rejection
            and not gap_blocked
            and details.get("strong_active_release") is not True
            and details.get("spent_edge") is not True
        )
        return {
            "qualified": confirmed,
            "contract_ready": contract_ready,
            "lean_side": parent_side.value if parent_side is not None else None,
            "owner_side": owner.value if owner is not None else None,
            "lean_agrees_with_parent": lean_agrees,
            "rejection_observed": rejection,
            "terminal_observed": terminal,
            "failed_reextension": details.get("failed_reextension") is True,
            "meaningful_retreat": details.get("meaningful_retreat") is True,
            "stall_and_hesitation": bool(details.get("stall") is True and details.get("hesitation") is True),
            "gap_blocked_while_expanding_below_previous": gap_blocked,
            "current_gap_expanding": gap.get("current_gap_expanding") is True,
            "current_gap_below_previous_arc": gap.get("current_gap_below_previous_arc") is True,
            "basis": "PID20964_WAIT_LEAN_OUTER_FAKEOUT_REJECTION",
        }

    def _fast_narrow_handoff_context(
        self, snapshot: MarketSnapshot, details: Mapping[str, Any], entry_side: Side,
        ask: float | None,
    ) -> dict[str, Any] | None:
        """Return one exact overlap bridge context for a fast/narrow edge.

        Long/extended/slow Mountains are deliberately excluded.  The bridge
        exists only when the new opposite contract is already executable at or
        below the global 20c ceiling and one stable normal-role lot is held.
        """
        if ask is None or not 0 < ask <= self.config.edge_value_max_ask:
            return None
        if snapshot.metadata.get("release_in_progress") is True:
            return None
        parent = mapping(details.get("parent_structure"))
        if (parent.get("extended_parent") is True
                or parent.get("slow_rolling_parent") is True
                or parent.get("blocks_child_reversal") is True):
            return None
        diagnostics = mapping(details.get("diagnostics"))
        age = number(diagnostics.get("current_age_s"))
        terminal = mapping(diagnostics.get("current_ema9_terminal_window"))
        terminal_age = number(terminal.get("age_seconds"))
        if (age is not None and age > self.config.fast_handoff_max_arc_age_s
                or terminal_age is not None
                and terminal_age > self.config.fast_handoff_max_terminal_window_age_s):
            return None
        held = [p for p in snapshot.metadata.get("position_inventory", ())
                if isinstance(p, Mapping) and p.get("ticker") == snapshot.ticker
                and p.get("custody_state", "NORMAL") in ("NORMAL", "RECOVERED_NORMAL")]
        if len(held) != 1:
            return None
        old = held[0]
        old_side = _side(old.get("side"))
        old_role = position_role(old)
        old_is_bridge = bool(mapping(entry_metadata(old).get("fast_handoff_bridge")))
        if (old_side is None or old_side is entry_side
                or old_role not in ("PRIMARY", "TACTICAL")
                or old_role == "TACTICAL" and not old_is_bridge):
            # Legacy/independent tactical renters keep sell-then-buy semantics.
            # A TACTICAL lot may chain the overlap only when it is itself the
            # surviving bridge from the immediately prior fast handoff.
            return None
        new_role = "TACTICAL" if old_role == "PRIMARY" else "PRIMARY"
        return {
            "outgoing_position_id": str(old.get("position_id")),
            "outgoing_opportunity_id": str(old.get("opportunity_id") or ""),
            "outgoing_side": old_side.value,
            "outgoing_role": old_role,
            "incoming_side": entry_side.value,
            "incoming_role": new_role,
            "arc_age_s": age,
            "terminal_window_age_s": terminal_age,
            "global_value_cap": self.config.edge_value_max_ask,
            "parent_extended": False,
            "parent_slow_rolling": False,
            "brief_overlap_only": True,
        }

    @staticmethod
    def _bridge_companion(position: Mapping[str, Any], snapshot: MarketSnapshot) -> Mapping[str, Any] | None:
        pid = str(position.get("position_id") or "")
        for other in snapshot.metadata.get("position_inventory", ()):
            if not isinstance(other, Mapping) or str(other.get("position_id") or "") == pid:
                continue
            bridge = mapping(entry_metadata(other).get("fast_handoff_bridge"))
            if bridge.get("outgoing_position_id") == pid:
                return other
        return None

    def rail_child_arc_value_intent(
        self, snapshot: MarketSnapshot, *, rail_side: Side,
    ) -> ToolIntent | None:
        """One cheap local child-leg rider without reversing the parent Rail.

        PID19792 showed a real ~3 minute child trough inside an established
        DOWN Rail with YES offered in the low teens. The parent correctly
        remained DOWN; the mistake was suppressing the entire local leg. This
        setup is intentionally narrow and never changes territory ownership.
        """
        if not self._active or snapshot.metadata.get("physical_current") is not True:
            return None
        if snapshot.metadata.get("release_in_progress") is True:
            return None
        details = self._details(snapshot)
        owner = _side(details.get("owner_side"))
        if owner is not rail_side:
            return None
        child_side = _opposite(rail_side)
        if child_side is None:
            return None
        diagnostics = mapping(details.get("diagnostics"))
        age = number(diagnostics.get("current_age_s"))
        seconds_left = max(0.0, 900.0 - snapshot.contract_age_s)
        ask = snapshot.ask_for(child_side)
        terminal_cue = bool(
            details.get("stall") is True or details.get("hesitation") is True
            or details.get("failed_reextension") is True or details.get("meaningful_retreat") is True
            or details.get("comparable_slow_edge") is True
            or mapping(details.get("paired_gap_evidence")).get("eligible") is True
        )
        if (details.get("mature_edge") is not True or not terminal_cue
                or details.get("strong_active_release") is True
                or details.get("spent_edge") is True
                or age is None or age < 120.0
                or seconds_left <= 300.0
                or ask is None or not 0 < ask <= 0.16):
            return None
        if snapshot.ticker in self._open_tickers:
            return None
        arc_id = str(details.get("current_arc_id") or "")
        source_ms = number(details.get("source_ms"))
        if not arc_id or source_ms is None:
            return None
        edge_id = str(details.get("edge_id") or f"{arc_id}:RAIL_CHILD:{source_ms:.0f}")
        opportunity = f"{self.territory_id}:RAIL_CHILD:{arc_id}:{child_side.value}:{snapshot.ticker}"
        if (snapshot.ticker, opportunity) in self._filled_opportunities:
            return None
        return ToolIntent(
            tool=self.name, territory_id=self.territory_id, lane=Lane.TACTICAL,
            side=child_side, action=Action.ENTER, opportunity_id=opportunity,
            max_price=0.16, size_tier=self.config.regular_size,
            reason="RAIL_CHILD_ARC_CHEAP_RIDER", source_time=snapshot.now_ts,
            expires_when="LOCAL_CHILD_ARC_EDGE_OR_PARENT_RAIL_TRANSFER",
            metadata={
                "position_role": "TACTICAL", "observed_ask": ask,
                "entry_arc_id": arc_id, "edge_id": edge_id,
                "owner_side": rail_side.value,
                "physical_mission_id": f"RAIL_CHILD:{arc_id}:{child_side.value}",
                "rail_child_arc_value": {
                    "rail_side": rail_side.value, "child_arc_id": arc_id,
                    "source_ms": source_ms, "child_age_s": age,
                    "max_ask": 0.16, "observed_ask": ask,
                    "parent_ownership_transfers": False,
                },
                "entry_geometry_source_ms": source_ms,
                "entry_btc": number(details.get("current_btc")),
                "entry_ema9": number(details.get("current_ema9")),
                "entry_ema30": number(details.get("current_ema30")),
                "floor_policy": floor_policy(self.config),
            },
        )

    def _armed_value_intent(self, snapshot: MarketSnapshot, details: Mapping[str, Any]) -> ToolIntent | None:
        pending = self._armed_value_entry
        if not pending:
            return None
        if snapshot.ticker != pending.get("ticker"):
            self._armed_value_entry = None
            return None
        side = _side(pending.get("side"))
        if side is None:
            self._armed_value_entry = None
            return None
        parent = mapping(details.get("parent_structure"))
        current_owner = _side(details.get("owner_side"))
        parent_side = _side(parent.get("parent_side"))
        old_owner = _side(pending.get("owner_side"))
        # A newly qualified opposite terminal edge supersedes a still-unfilled
        # value hunt. Otherwise keep the earned side alive through the brief
        # crest/trough and the beginning of its new leg instead of canceling it
        # simply because EMA9 has not flipped yet.
        current_candidate = _opposite(current_owner)
        if (details.get("terminal_evidence_qualified") is True
                and current_candidate is not None and current_candidate is not side):
            self._armed_value_entry = None
            return None
        # An earned edge is not permission to keep fishing if the outgoing
        # parent resumes expansion. Cancel the resting hunt and wait for a new
        # physical edge; cheap price alone never revives it.
        gap_guard = mapping(details.get("ema9_ema30_gap_edge_guard"))
        if current_owner is old_owner and (
                details.get("strong_active_release") is True
                or gap_guard.get("terminal_blocked_while_gap_expands_below_previous") is True):
            self._armed_value_entry = None
            return self._wait(snapshot, "MOUNTAIN_ARMED_EDGE_CANCELLED_PARENT_REEXPANDED")
        supported = current_owner in (side, old_owner) or parent_side is side
        if not supported:
            self._armed_value_entry = None
            return None
        seconds_left = max(0.0, 900.0 - snapshot.contract_age_s)
        ask = snapshot.ask_for(side)
        low_wide = pending.get("low_wide_sideways") if isinstance(pending.get("low_wide_sideways"), Mapping) else None
        low_wide_fakeout = (pending.get("low_wide_fakeout")
                            if isinstance(pending.get("low_wide_fakeout"), Mapping) else None)
        late_low_wide = bool(
            low_wide is not None
            and low_wide_fakeout is not None
            and low_wide_fakeout.get("qualified") is True
            and ask is not None and 0 < ask <= self.config.low_wide_late_exception_max_ask
            and seconds_left >= self.config.low_wide_late_min_seconds_left
        )
        if seconds_left <= self.config.rollover_skip_last_s and not late_low_wide:
            self._rollover_pending = {
                "source_ticker": snapshot.ticker, "side": side.value,
                "edge_id": pending.get("edge_id"), "source_ms": pending.get("source_ms"),
                "observed_at": pending.get("observed_at"), "seconds_left": seconds_left,
            }
            self._armed_value_entry = None
            return self._wait(snapshot, "MOUNTAIN_ARMED_EDGE_DEFER_TO_NEXT_CONTRACT_VALUE")
        if ask is None or not 0 < ask < 1:
            return self._wait(snapshot, "MOUNTAIN_ARMED_EDGE_ASK_UNAVAILABLE")
        wide_top = pending.get("wide_top_value_window") is True
        waited = max(0.0, snapshot.now_ts - (number(pending.get("observed_at")) or snapshot.now_ts))
        # PAPER resting-limit ladders. Regular/tall Mountains keep the exact
        # PID21864 10c->15c->20c discipline. Only the separately qualified
        # PID10168 low/wide sideways regime starts near the empirically common
        # broad-edge value and eases 30c->35c->40c.
        if low_wide is not None:
            if waited < self.config.low_wide_stage1_seconds:
                target = self.config.low_wide_stage1_ask
            elif waited < self.config.low_wide_stage2_seconds:
                target = self.config.low_wide_stage2_ask
            else:
                target = self.config.low_wide_hard_max_ask
        elif wide_top:
            if waited < self.config.value_ladder_stage2_seconds:
                target = self.config.value_ladder_stage1_ask
            elif waited < self.config.wide_top_patient_seconds:
                target = self.config.value_ladder_stage2_ask
            else:
                target = self.config.edge_value_max_ask
        else:
            if waited < self.config.value_ladder_stage1_seconds:
                target = self.config.value_ladder_stage1_ask
            elif waited < self.config.value_ladder_stage2_seconds:
                target = self.config.value_ladder_stage2_ask
            else:
                target = self.config.edge_value_max_ask
        if ask > target:
            return self._wait(snapshot,
                "MOUNTAIN_LOW_WIDE_EDGE_AWAIT_PASSIVE_VALUE" if low_wide is not None
                else "MOUNTAIN_WIDE_TOP_PATIENT_LIMIT_AWAIT_VALUE" if wide_top
                else "MOUNTAIN_EDGE_ARMED_AWAIT_SUB20_PULLBACK")
        opportunity = str(pending.get("opportunity_id"))
        if (snapshot.ticker, opportunity) in self._filled_opportunities:
            self._armed_value_entry = None
            return self._wait(snapshot, "MOUNTAIN_EDGE_ALREADY_FILLED")
        self._armed_value_entry = None
        return ToolIntent(
            tool=self.name, territory_id=self.territory_id, lane=Lane.MAIN, side=side,
            action=Action.ENTER, opportunity_id=opportunity, max_price=ask,
            size_tier=(self.config.regular_size if low_wide is not None else self._mountain_size(ask)),
            reason=("MOUNTAIN_LOW_WIDE_SIDEWAYS_VALUE_ENTRY" if low_wide is not None
                    else "MOUNTAIN_WIDE_TOP_PATIENT_VALUE_ENTRY" if wide_top
                    else "MOUNTAIN_ARMED_EDGE_SUB20_VALUE_ENTRY"), source_time=snapshot.now_ts,
            expires_when="NEXT_PARENT_DIRECTION_CHANGE_OR_ROLLOVER",
            metadata={"position_role": "PRIMARY", "observed_ask": ask,
                      "armed_edge_value": dict(pending),
                      "wide_top_value_window": wide_top,
                      "low_wide_sideways_entry": dict(low_wide) if low_wide is not None else None,
                      "low_wide_fakeout_entry": dict(pending.get("low_wide_fakeout") or {}),
                      "wide_top_waited_s": waited,
                      "wide_top_target_ask": target,
                      "floor_policy": self._entry_floor_policy(low_wide),
                      "entry_arc_id": details.get("current_arc_id"),
                      "entry_geometry_source_ms": number(details.get("source_ms")),
                      "entry_btc": number(details.get("current_btc")),
                      "entry_ema9": number(details.get("current_ema9")),
                      "entry_ema30": number(details.get("current_ema30"))})

    def _wait(
        self,
        snapshot: MarketSnapshot,
        reason: str,
    ) -> ToolIntent:
        return ToolIntent(
            tool=self.name,
            territory_id=self.territory_id,
            lane=Lane.MAIN,
            side=_opposite(
                self.owner_side
            ),
            action=Action.WAIT,
            opportunity_id=None,
            max_price=(
                self.config.soft_max_price
            ),
            size_tier=None,
            reason=reason,
            source_time=snapshot.now_ts,
            metadata={"mountain_readiness": {
                "reference_history": self._details(snapshot).get("reference_history"),
                "entry_routes": self._details(snapshot).get("entry_routes"),
                "paired_match_observed": bool((self._details(snapshot).get("paired_gap_evidence") or {}).get("selected_match")),
                "current_slowdown_observed": (self._details(snapshot).get("slowdown") or {}).get("observed"),
                "spent_edge": self._details(snapshot).get("spent_edge"),
            }},
        )

    def on_activate(
        self,
        snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        return self.on_market_event(
            snapshot
        )

    def on_market_event(
        self,
        snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        return self._entry_intents(snapshot)

    def _entry_intents(
        self, snapshot: MarketSnapshot, *, outgoing_opportunity_id: str | None = None,
    ) -> Iterable[ToolIntent]:
        """Mandatory EMA9 terminal-edge relay.

        The detector owns one question only: is the living EMA9 arc at a
        current terminal top/bottom?  Once that answer is yes, this tool does
        not add a second strategy committee: no EMA30 approval, contract
        thesis, soft price ceiling, tactical economics, full-arc label, or
        opening-slice gate.  Buy the opposite leg at the current best ask.
        """
        if not self._active:
            return []
        previous_ticker = self._current_ticker
        rolled_contract = previous_ticker is not None and previous_ticker != snapshot.ticker
        self._current_ticker = snapshot.ticker
        details = self._entry_details(snapshot)

        armed = self._armed_value_intent(snapshot, details)
        if armed is not None:
            return [armed]

        # Rollover continuation is the only non-edge Mountain acquisition in
        # this build. It must come from an exact terminal edge deliberately
        # skipped in the expiring contract, remain physically supported, and
        # appear cheap in the first four minutes of the new contract.
        pending = self._rollover_pending
        if pending is not None and snapshot.ticker != pending.get("source_ticker"):
            if snapshot.contract_age_s > self.config.rollover_reentry_window_s:
                self._rollover_pending = None
            else:
                pending_side = _side(pending.get("side"))
                parent = details.get("parent_structure") if isinstance(details.get("parent_structure"), Mapping) else {}
                parent_side = _side(parent.get("parent_side"))
                current_owner = _side(details.get("owner_side"))
                supported = pending_side is not None and pending_side in (current_owner, parent_side)
                ask = snapshot.ask_for(pending_side) if pending_side is not None else None
                if (supported and ask is not None and 0 < ask <= self.config.rollover_reentry_max_ask
                        and snapshot.ticker not in self._open_tickers):
                    opportunity = (f"{self.territory_id}:ROLLOVER_EDGE:{pending.get('edge_id')}:"
                                   f"{pending_side.value}:{snapshot.ticker}")
                    if (snapshot.ticker, opportunity) not in self._filled_opportunities:
                        return [ToolIntent(
                            tool=self.name, territory_id=self.territory_id, lane=Lane.MAIN,
                            side=pending_side, action=Action.ENTER, opportunity_id=opportunity,
                            max_price=ask, size_tier=self._mountain_size(ask),
                            reason="MOUNTAIN_INHERITED_EDGE_CHEAP_ROLLOVER_ENTRY",
                            source_time=snapshot.now_ts,
                            expires_when="ROLLOVER_VALUE_WINDOW_OR_PARENT_DIRECTION_CHANGES",
                            metadata={
                                "position_role": "PRIMARY", "observed_ask": ask,
                                "rollover_inherited_edge": dict(pending),
                                "entry_arc_id": details.get("current_arc_id"),
                                "entry_geometry_source_ms": number(details.get("source_ms")),
                                "entry_btc": number(details.get("current_btc")),
                                "entry_ema9": number(details.get("current_ema9")),
                                "entry_ema30": number(details.get("current_ema30")),
                                "owner_side": pending_side.value,
                                "physical_mission_id": f"ROLLOVER:{pending.get('edge_id')}:{pending_side.value}",
                                "physical_renewal": {"independent": True,
                                    "renewal_kind": "SKIPPED_LATE_EDGE_NEW_CONTRACT_VALUE",
                                    "observed_at": snapshot.now_ts},
                                "floor_policy": self._entry_floor_policy(),
                            },
                        )]
                # WAIT while the cheap opening value is still possible.
                if rolled_contract or snapshot.contract_age_s <= self.config.rollover_reentry_window_s:
                    return [self._wait(snapshot, "MOUNTAIN_ROLLOVER_EDGE_AWAIT_CHEAP_VALUE")]

        owner = _side(details.get("owner_side")) if "owner_side" in details else self.owner_side
        self.update_owner_side(owner)
        entry_side = _opposite(owner)
        if owner is None or entry_side is None:
            return [self._wait(snapshot, "MOUNTAIN_OWNER_SIDE_UNAVAILABLE")]
        if not details:
            return [self._wait(snapshot, "MOUNTAIN_EDGE_EVIDENCE_UNAVAILABLE")]
        if snapshot.metadata.get("physical_current") is False:
            return [self._wait(snapshot, "MOUNTAIN_PHYSICAL_SOURCE_NOT_CURRENT")]

        terminal_cue = bool(
            details.get("stall") is True
            or details.get("hesitation") is True
            or details.get("failed_reextension") is True
            or details.get("meaningful_retreat") is True
            or (details.get("paired_gap_evidence") or {}).get("eligible") is True
            or details.get("comparable_slow_edge") is True
        )
        if "terminal_evidence_qualified" in details:
            terminal_edge = details.get("terminal_evidence_qualified") is True
        else:
            # Compatibility for compact unit fixtures. Live detector output
            # always carries terminal_evidence_qualified.
            terminal_edge = bool(details.get("mature_edge") is True
                and terminal_cue
                and details.get("strong_active_release") is not True
                and details.get("spent_edge") is not True)
        seconds_left = max(0.0, 900.0 - snapshot.contract_age_s)
        preview_ask = snapshot.ask_for(entry_side)
        cheap_hover = self._cheap_hover_edge(details, preview_ask, seconds_left=seconds_left)

        # PID20964: low/wide parallel terrain has its own execution chapter.
        # It waits through the contract open, lets the parent establish a lean,
        # then requires a real outer fakeout/rejection before it can rent the
        # opposite return leg.  A first shoulder or cheap quote is not an edge.
        low_wide = self._low_wide_sideways_context(snapshot, details)
        low_wide_fakeout = (self._low_wide_fakeout_context(snapshot, details, low_wide)
                            if low_wide is not None else None)
        if low_wide is not None:
            if snapshot.contract_age_s < self.config.low_wide_contract_open_wait_s:
                return [self._wait(snapshot, "MOUNTAIN_LOW_WIDE_OPEN_WAIT_ESTABLISH_LEAN")]
            if not low_wide_fakeout or low_wide_fakeout.get("qualified") is not True:
                return [self._wait(snapshot, "MOUNTAIN_LOW_WIDE_WAIT_OUTER_FAKEOUT_REJECTION")]
            # The fakeout itself is the terminal authority for this terrain.
            terminal_edge = True
            cheap_hover = False

        if not terminal_edge and not cheap_hover:
            return [self._wait(snapshot, "MOUNTAIN_WAIT_FOR_TERMINAL_EMA9_EDGE_NEVER_MIDDLE")]

        late_low_wide = bool(
            low_wide is not None
            and low_wide_fakeout is not None
            and low_wide_fakeout.get("qualified") is True
            and preview_ask is not None
            and 0 < preview_ask <= self.config.low_wide_late_exception_max_ask
            and seconds_left >= self.config.low_wide_late_min_seconds_left
        )
        if (snapshot.entry_allowed and snapshot.contract_age_s < 900.0
                and seconds_left <= self.config.rollover_skip_last_s
                and not late_low_wide):
            edge_id = str(details.get("edge_id") or
                          f"{details.get('current_arc_id') or 'ARC'}:{snapshot.now_ts:.3f}")
            self._rollover_pending = {
                "source_ticker": snapshot.ticker, "side": entry_side.value,
                "edge_id": edge_id, "source_ms": number(details.get("source_ms")),
                "observed_at": snapshot.now_ts, "seconds_left": seconds_left,
            }
            return [self._wait(snapshot, "MOUNTAIN_LATE_EDGE_DEFER_TO_NEXT_CONTRACT_CHEAP_VALUE")]

        ask = snapshot.ask_for(entry_side)
        if ask is None or not 0 < ask < 1:
            return [self._wait(snapshot, "MOUNTAIN_ENTRY_ASK_UNAVAILABLE")]
        small_fast_arc = (not cheap_hover and self._small_fast_arc_edge(snapshot, details, ask))
        fast_bridge = self._fast_narrow_handoff_context(snapshot, details, entry_side, ask)

        exact_handoff_slot = bool(outgoing_opportunity_id
            and self._open_positions.get(snapshot.ticker) == {outgoing_opportunity_id})
        if snapshot.ticker in self._open_tickers and not exact_handoff_slot and fast_bridge is None:
            # Long/wide or expensive edges remain sell-then-buy. Fast/narrow
            # edges with already-cheap opposite value may use the bounded
            # normal-role overlap bridge below.
            return [self._wait(snapshot, "MOUNTAIN_CURRENT_POSITION_EXITS_BEFORE_EDGE_RELAY")]

        edge_id = str(details.get("edge_id") or
                      f"{details.get('current_arc_id') or 'ARC'}:{snapshot.now_ts:.3f}")
        arc_id = str(details.get("current_arc_id") or "")
        mission_id = f"MOUNTAIN_EDGE:{edge_id}:{entry_side.value}"
        opportunity_id = f"{self.territory_id}:{mission_id}:{snapshot.ticker}"
        if (snapshot.ticker, opportunity_id) in self._filled_opportunities:
            return [self._wait(snapshot, "MOUNTAIN_EDGE_ALREADY_FILLED")]

        source_ms = number(details.get("source_ms"))
        wide_top_value = self._wide_top_value_window(details)
        # Regular wide/slow Mountain behavior is unchanged.  Low/wide fakeout
        # territory may trade later only under the explicit very-cheap
        # confirmed-fakeout exception above.
        if wide_top_value and low_wide is None and seconds_left <= 360.0:
            return [self._wait(snapshot, "MOUNTAIN_WIDE_SLOW_EDGE_SKIP_LATE_RETURN_WINDOW")]
        if low_wide is not None and seconds_left < self.config.low_wide_late_min_seconds_left:
            return [self._wait(snapshot, "MOUNTAIN_LOW_WIDE_TOO_LATE_NO_RETURN_WINDOW")]
        if (low_wide is not None and seconds_left <= self.config.rollover_skip_last_s
                and not late_low_wide):
            return [self._wait(snapshot, "MOUNTAIN_LOW_WIDE_LATE_REQUIRES_CHEAP_CONFIRMED_FAKEOUT")]
        needs_patient_value = bool(wide_top_value and low_wide is None and not cheap_hover and not small_fast_arc
            and ask > self.config.wide_top_patient_target_ask)
        if not cheap_hover and not small_fast_arc and fast_bridge is None:
            self._armed_value_entry = {
                "ticker": snapshot.ticker, "side": entry_side.value, "edge_id": edge_id,
                "source_ms": source_ms, "observed_at": snapshot.now_ts,
                "opportunity_id": opportunity_id, "owner_side": owner.value,
                "wide_top_value_window": wide_top_value,
                "low_wide_sideways": dict(low_wide) if low_wide is not None else None,
                "low_wide_fakeout": dict(low_wide_fakeout) if low_wide_fakeout is not None else None,
            }
            return [self._wait(snapshot,
                "MOUNTAIN_LOW_WIDE_EDGE_AWAIT_PASSIVE_VALUE" if low_wide is not None
                else "MOUNTAIN_WIDE_TOP_PATIENT_LIMIT_AWAIT_VALUE" if needs_patient_value
                else "MOUNTAIN_EDGE_ARMED_AWAIT_SUB20_PULLBACK")]
        return [ToolIntent(
            tool=self.name,
            territory_id=self.territory_id,
            lane=Lane.TACTICAL if fast_bridge is not None else Lane.MAIN,
            side=entry_side,
            action=Action.ENTER if fast_bridge is not None else Action.RELAY,
            opportunity_id=opportunity_id,
            max_price=ask,
            size_tier=(self.config.regular_size if small_fast_arc
                       else self._mountain_size(ask, cheap_hover=cheap_hover)),
            reason=("MOUNTAIN_FAST_NARROW_EDGE_PREENTRY_BRIDGE" if fast_bridge is not None
                    else "MOUNTAIN_CHEAP_HOVER_EDGE_RELAY" if cheap_hover
                    else "MOUNTAIN_SMALL_FAST_ARC_EDGE_RELAY" if small_fast_arc
                    else "MOUNTAIN_TERMINAL_EDGE_SUB20_VALUE_RELAY"),
            source_time=snapshot.now_ts,
            expires_when="CURRENT_TERMINAL_EMA9_EDGE_CHANGES",
            metadata={
                "position_role": (fast_bridge.get("incoming_role") if fast_bridge is not None else "PRIMARY"),
                "fast_handoff_bridge": fast_bridge,
                "cheap_hover_edge": cheap_hover,
                "small_fast_arc_edge": small_fast_arc,
                "full_arc_return": False,
                "owner_side": owner.value,
                "observed_ask": ask,
                "entry_arc_id": arc_id or None,
                "physical_mission_id": mission_id,
                "physical_renewal": {
                    "independent": True,
                    "renewal_kind": "TERMINAL_EMA9_EDGE",
                    "observed_at": (source_ms / 1000 if source_ms is not None else snapshot.now_ts),
                },
                "entry_geometry_source_ms": source_ms,
                "entry_btc": number(details.get("current_btc")),
                "entry_ema9": number(details.get("current_ema9")),
                "entry_ema30": number(details.get("current_ema30")),
                "floor_policy": self._entry_floor_policy(),
                "edge_id": edge_id,
                "owner_extreme_btc": number(details.get("owner_extreme_btc")),
                "edge_tolerance_dollars": number(details.get("edge_tolerance_dollars")),
                "terminal_evidence": {
                    "qualified": True,
                    "stall": details.get("stall") is True,
                    "hesitation": details.get("hesitation") is True,
                    "failed_reextension": details.get("failed_reextension") is True,
                    "meaningful_retreat": details.get("meaningful_retreat") is True,
                    "comparable_slow_edge": details.get("comparable_slow_edge") is True,
                },
            },
        )]

    def aligned_entry_intent(self, snapshot: MarketSnapshot) -> ToolIntent | None:
        """Acquire an observed new leg or a new contract slice of that leg.

        A cheap quote alone cannot create this mission. The source must already
        have observed the native leg, current progress and a nonterminal location.
        The exact arc/ticker event stays consumed after an exit.
        """
        self.main_proposal_review = None
        if not self._active or snapshot.metadata.get("physical_current") is not True:
            if "mission_context" in snapshot.metadata:
                self.main_proposal_review = self._main_proposal_diagnostic(snapshot)
            return None
        if "mission_context" in snapshot.metadata:
            # Edge-only Mountain means exactly that.  This check must precede
            # the historical/full-arc helper: otherwise a full-arc label can
            # silently bypass the disabled mid-leg/opening-slice route.
            if not self.config.aligned_leg_entries_enabled:
                self.main_proposal_review = self._main_proposal_diagnostic(snapshot)
                if self.main_proposal_review is not None:
                    self.main_proposal_review.update(decision="NOT_OFFERED",
                        reason="MOUNTAIN_EDGE_ONLY_NO_MIDLEG_ALIGNED_ENTRY")
                return None
            context = mapping(snapshot.metadata.get("mission_context"))
            source = number(context.get("source_ms"))
            if source is not None and any(_full_arc_candidate(context, side.value, source)
                                          for side in (Side.YES, Side.NO)):
                return self._parent_entry_intent(snapshot)
            return self._parent_entry_intent(snapshot)
        if not self.config.aligned_leg_entries_enabled:
            return None
        details = self._details(snapshot)
        geometry = snapshot.metadata.get("current_geometry") or {}
        side = _side(details.get("owner_side"))
        source, known = number(geometry.get("epoch_ms")), number(geometry.get("arc_known_ms"))
        arc = str(geometry.get("arc_id") or "")
        if (side is None or not arc or geometry.get("arc_origin_observed") is not True
                or geometry.get("arc_recognition_basis") != "OBSERVED_6S_9S_EMA9_AND_PROMINENCE"
                or source is None or known is None or known > source
                or not current_source_is_fresh(snapshot, source, max_age_seconds=3.)
                or details.get("terminal_evidence_qualified") is True
                or details.get("mature_edge") is True):
            return None
        sign = 1 if side is Side.YES else -1
        six, nine = number(geometry.get("micro_slope6s")), number(geometry.get("micro_slope9s"))
        if six is None or nine is None or min(sign*six, sign*nine) < 0 or max(sign*six, sign*nine) <= 0:
            return None
        diagnostics = details.get("diagnostics") or {}
        durations = [number(v) for v in diagnostics.get("comparable_durations_s", ())]
        durations = [v for v in durations if v is not None and v > 0]
        age = number(geometry.get("arc_age_sec"))
        # This is entry location, not another delayed confirmation. With no
        # family duration yet, only the received native birth itself qualifies.
        early_leg = (source - known <= 9000 or bool(durations
                     and age is not None and age < .5 * min(durations)))
        opening_slice = 0 <= snapshot.contract_age_s < 240
        if not early_leg and not opening_slice:
            return None
        ask = snapshot.ask_for(side)
        if ask is None or not 0 < ask <= self.config.soft_max_price:
            return None
        opportunity = f"{self.territory_id}:MOUNTAIN_LEG:{arc}:{side.value}:{snapshot.ticker}"
        if (snapshot.ticker, opportunity) in self._filled_opportunities:
            return None
        inventory = [p for p in snapshot.metadata.get("position_inventory", ())
                     if isinstance(p, Mapping) and p.get("ticker") == snapshot.ticker]
        if any(p.get("position_role") == "PRIMARY" or p.get("side") == side.value for p in inventory):
            return None
        mission = f"MOUNTAIN_LEG:{arc}:{side.value}"
        return ToolIntent(self.name, self.territory_id, Lane.MAIN, side, Action.ENTER,
            opportunity, self.config.soft_max_price, self.config.regular_size,
            "MOUNTAIN_OBSERVED_LEG_OPENING_SLICE" if opening_slice else "MOUNTAIN_OBSERVED_NEW_LEG",
            snapshot.now_ts, "CURRENT_LEG_PROGRESS_OR_EARNED_TERMINAL_CHANGES", {
                "position_role": "PRIMARY", "physical_mission_id": mission,
                "physical_renewal": {"independent": True, "renewal_kind": "OBSERVED_LEG_ACQUISITION",
                    "observed_at": source / 1000},
                "entry_arc_id": arc, "entry_geometry_source_ms": source,
                "entry_btc": number(geometry.get("btc_price")),
                "entry_ema9": number(geometry.get("ema9")),
                "entry_ema30": number(geometry.get("ema30")),
                "owner_side": side.value, "observed_ask": ask,
                "aligned_entry_evidence": {"known_ms": known, "source_ms": source,
                    "early_leg": early_leg, "opening_slice": opening_slice,
                    "native_6s": six, "native_9s": nine, "terminal": False},
                "floor_policy": floor_policy(self.config)})

    def _main_proposal_diagnostic(self, snapshot: MarketSnapshot) -> dict[str, Any]:
        """Describe existing proposal gates without changing or granting them.

        Only the exact contract thesis is a MAIN candidate. An opposite local
        return must not acquire that label merely because this route considers
        both sides. All values here are detached scalar observations.
        """
        context = snapshot.metadata.get("mission_context") or {}
        thesis = (context.get("contract") or {}).get("thesis_side")
        side = _side(thesis) if thesis in ("YES", "NO") else None
        candidate = ((context.get("candidates") or {}).get(side.value) or {}) if side else {}
        source = number(context.get("source_ms"))
        ask = snapshot.ask_for(side) if side else None
        parent_id = candidate.get("parent_leg_id")
        review = {"stage": "PHYSICAL_PROPOSAL", "tool": self.name,
            "ticker": snapshot.ticker, "side": side.value if side else None,
            "purpose": "MAIN_CONTRACT", "decision": "NOT_OFFERED",
            "classification": candidate.get("classification", "UNRESOLVED"),
            "reason": "MAIN_PHYSICAL_PROPOSAL_NOT_EMITTED",
            "observed_ask": ask, "max_price": self.config.soft_max_price,
            "source_ms": source, "candidate_source_ms": number(candidate.get("source_ms")),
            "parent_leg_id": parent_id, "swing_id": candidate.get("swing_id"),
            "continuity_generation": context.get("continuity_generation"),
            "qualified_edge": candidate.get("qualified_edge") is True,
            "entry_location_qualified": candidate.get("entry_location_qualified") is True,
            "contract_thesis_side": side.value if side else None,
            "economics": None}
        reason = None
        if side is None:
            reason = "MAIN_CONTRACT_THESIS_UNRESOLVED"
        elif not self._active:
            reason = "MAIN_TOOL_NOT_ACTIVE"
        elif snapshot.metadata.get("physical_current") is not True:
            reason = "MAIN_CURRENT_PHYSICAL_SOURCE_REQUIRED"
        elif (context.get("current") is not True or source is None
                or not current_source_is_fresh(snapshot, source, max_age_seconds=3.)):
            reason = "MAIN_CURRENT_MISSION_CONTEXT_REQUIRED"
        elif candidate.get("classification") not in ("MAIN_CONTINUATION", "PARENT_EDGE_RETURN"):
            reason = "MAIN_PHYSICAL_CLASSIFICATION_UNAVAILABLE"
        elif not (candidate.get("entry_location_qualified") is True or candidate.get("qualified_edge") is True):
            reason = "MAIN_ENTRY_REQUIRES_CURRENT_PHYSICAL_VALUE_LOCATION"
        elif ask is None or not ask > 0:
            reason = "MAIN_ENTRY_ASK_UNAVAILABLE"
        elif ask > self.config.soft_max_price:
            reason = "MAIN_ENTRY_ASK_ABOVE_SOFT_VALUE"
        elif not parent_id:
            reason = "MAIN_PARENT_ID_REQUIRED"
        else:
            inventory = [p for p in snapshot.metadata.get("position_inventory", ())
                         if isinstance(p, Mapping) and p.get("ticker") == snapshot.ticker]
            if any(p.get("side") == side.value and p.get("custody_state") != "LAZARUS"
                   for p in inventory):
                reason = "MAIN_SAME_SIDE_POSITION_ALREADY_OPEN"
            else:
                opportunity = f"{self.territory_id}:PARENT_LEG:{parent_id}:{side.value}:{snapshot.ticker}"
                if (snapshot.ticker, opportunity) in self._filled_opportunities:
                    reason = "MAIN_PARENT_OPPORTUNITY_ALREADY_FILLED"
        if reason is not None:
            review["reason"] = reason
        return review

    def _parent_entry_intent(self, snapshot: MarketSnapshot) -> ToolIntent | None:
        """Use the full-zone route once, otherwise acquire a located MAIN leg.

        The source owns territory and entry location. This tool supplies the
        current quote and exact opportunity; it does not reclassify the zone.
        """
        self.main_proposal_review = self._main_proposal_diagnostic(snapshot)
        context = mapping(snapshot.metadata.get("mission_context"))
        source = number(context.get("source_ms"))
        if (context.get("current") is not True or source is None
                or not current_source_is_fresh(snapshot, source, max_age_seconds=3.)):
            return None
        if any(_full_arc_candidate(context, side.value, source)
               for side in (Side.YES, Side.NO)):
            # Both callers share this same order identity and source-zone
            # decision. A native-child veto cannot create a second full route.
            if self.main_proposal_review is not None:
                self.main_proposal_review.update(decision="DEFERRED",
                    reason="FULL_ARC_ENTRY_ZONE_SELECTED")
            return next((intent for intent in self._entry_intents(snapshot)
                         if intent.action in (Action.ENTER, Action.RELAY)), None)
        if not self.config.aligned_leg_entries_enabled:
            if self.main_proposal_review is not None:
                self.main_proposal_review.update(decision="NOT_OFFERED",
                    reason="MOUNTAIN_EDGE_ONLY_NO_MIDLEG_ALIGNED_ENTRY")
            return None
        side = _side(mapping(context.get("contract")).get("thesis_side"))
        if side is None:
            return None
        candidate = mapping(mapping(context.get("candidates")).get(side.value))
        if (candidate.get("classification") != "MAIN_CONTINUATION"
                or candidate.get("entry_location_qualified") is not True):
            return None
        ask, parent_id = snapshot.ask_for(side), candidate.get("parent_leg_id")
        if ask is None or not 0 < ask <= self.config.soft_max_price or not parent_id:
            return None
        inventory = [position for position in snapshot.metadata.get("position_inventory", ())
                     if isinstance(position, Mapping) and position.get("ticker") == snapshot.ticker]
        if any(position.get("side") == side.value and position.get("custody_state") != "LAZARUS"
               for position in inventory):
            return None
        opportunity = f"{self.territory_id}:PARENT_LEG:{parent_id}:{side.value}:{snapshot.ticker}"
        if (snapshot.ticker, opportunity) in self._filled_opportunities:
            return None
        geometry = mapping(snapshot.metadata.get("current_geometry"))
        if self.main_proposal_review is not None:
            self.main_proposal_review.update(decision="PROPOSED",
                reason="MAIN_PHYSICAL_PROPOSAL_SENT_FOR_PURPOSE_REVIEW")
        return ToolIntent(self.name, self.territory_id, Lane.MAIN, side, Action.ENTER,
            opportunity, self.config.soft_max_price, self.config.regular_size,
            "MOUNTAIN_PARENT_LEG_VALUE_ACQUISITION", snapshot.now_ts,
            "OBSERVED_PARENT_MISSION_OR_CURRENT_VALUE_CHANGES", {
                "physical_mission_id": f"MAIN:{parent_id}:{side.value}",
                "position_role": "PRIMARY", "full_arc_return": False,
                "physical_renewal": {"independent": True,
                    "renewal_kind": "PARENT_SCOPE_ACQUISITION", "observed_at": source / 1000},
                "entry_arc_id": geometry.get("arc_id"), "entry_geometry_source_ms": source,
                "entry_btc": number(geometry.get("btc_price")),
                "entry_ema9": number(geometry.get("ema9")), "entry_ema30": number(geometry.get("ema30")),
                "owner_side": side.value, "observed_ask": ask,
                "aligned_entry_evidence": {"source_ms": source, "parent_leg_id": parent_id,
                    "physical_location": candidate.get("location_evidence"),
                    "recognition_age_is_permission": False, "opening_cutoff_seconds": None},
                "floor_policy": floor_policy(self.config)})

    @staticmethod
    def _terminal_edge_for_side(details: Mapping[str, Any], side: Side | None) -> bool:
        if side is None or _side(details.get("owner_side")) is not side:
            return False
        if "terminal_evidence_qualified" in details:
            return details.get("terminal_evidence_qualified") is True
        terminal_cue = bool(any(details.get(key) is True for key in (
            "stall", "hesitation", "failed_reextension", "meaningful_retreat", "comparable_slow_edge"))
            or (details.get("paired_gap_evidence") or {}).get("eligible") is True)
        return bool(details.get("mature_edge") is True and terminal_cue
            and details.get("strong_active_release") is not True
            and details.get("spent_edge") is not True)

    @classmethod
    def _collection_terminal_for_position(cls, details: Mapping[str, Any],
                                          position: Mapping[str, Any]) -> bool:
        # A Rail child rider is deliberately local: parent-scale gap guards may
        # remain non-terminal while the child leg itself reaches the opposite
        # extreme. Collect it on that real local edge without declaring the
        # parent Rail reversed.
        entry = entry_metadata(position)
        if mapping(entry.get("rail_child_arc_value")):
            side = as_side(position.get("side"))
            terminal_cue = bool(any(details.get(key) is True for key in (
                "stall", "hesitation", "failed_reextension", "meaningful_retreat", "comparable_slow_edge"))
                or mapping(details.get("paired_gap_evidence")).get("eligible") is True)
            return bool(side is not None and _side(details.get("owner_side")) is side
                and details.get("mature_edge") is True and terminal_cue
                and details.get("strong_active_release") is not True
                and details.get("spent_edge") is not True)
        # A small local terminal can earn a separate tactical position while
        # the larger primary leg still advances. Older captures have no
        # distinct collection qualifier, so retain their existing behavior.
        return bool(cls._terminal_edge_for_side(details, as_side(position.get("side")))
            and (position_role(position) == "TACTICAL"
                 or details.get("primary_collection_terminal_qualified") is not False))

    def handoff_intent(self, position: Mapping[str, Any], snapshot: MarketSnapshot) -> ToolIntent | None:
        """Revalidate a terminal sell-then-buy proposal for one exact held lot.

        This only makes the incoming mission visible. Commander/execution must
        finish the outgoing sale, use shared native depth, and prove flatness.
        Partial sales re-call this method; a cached intent has no authority.
        """
        details = self._entry_details(snapshot)
        side = as_side(position.get("side"))
        outgoing_id = str(position.get("opportunity_id") or "")
        position_id = str(position.get("position_id") or "")
        source_ms = number(details.get("source_ms"))
        limit = number(snapshot.metadata.get("geometry_max_source_age_seconds")) or 5.0
        scoped = mission_collection_evidence(position, snapshot)
        collectible = (scoped["collection_qualified"] if scoped["scope_enforced"] else
                       self._collection_terminal_for_position(details, position))
        if (not self._active or str(position.get("ticker") or "") != snapshot.ticker
                or not outgoing_id or not position_id or position.get("custody_state") == "LAZARUS"
                or self._open_positions.get(snapshot.ticker) != {outgoing_id}
                or snapshot.metadata.get("physical_current") is False
                or source_ms is None or not current_source_is_fresh(snapshot, source_ms, max_age_seconds=limit)
                or not collectible):
            return None
        proposed = list(self._entry_intents(snapshot, outgoing_opportunity_id=outgoing_id))
        incoming = next((intent for intent in proposed if intent.action is Action.RELAY), None)
        if (incoming is None or incoming.side is not _opposite(side)
                or not incoming.metadata.get("physical_mission_id") or not incoming.metadata.get("edge_id")):
            return None
        proof = {"outgoing_position_id": position_id, "outgoing_opportunity_id": outgoing_id,
            "ticker": snapshot.ticker, "physical_mission_id": incoming.metadata["physical_mission_id"],
            "edge_id": incoming.metadata["edge_id"], "observed_at": source_ms / 1000,
            "source_ms": source_ms,
            "continuity_generation": snapshot.metadata.get("geometry_continuity_generation"),
            "outgoing_terminal_qualified": True}
        return replace(incoming, metadata={**incoming.metadata, "mountain_handoff": proof})

    def mark_entry_filled(self, opportunity_id: str, *, ticker: str | None = None) -> None:
        ticker = ticker or self._current_ticker
        if ":ROLLOVER_EDGE:" in opportunity_id:
            self._rollover_pending = None
        if ticker is not None:
            self._open_tickers.add(ticker)
            self._open_positions.setdefault(ticker, set()).add(opportunity_id)
            self._filled_opportunities.add((ticker, opportunity_id))
            key = self._offered_missions.get(opportunity_id)
            if key in self._missions:
                state = self._missions[key]
                state.update(consumed=True, active_paid=True, stage="SEEK_RETREAT",
                    consumed_source=state.get("last_source"),
                    post_fill_extreme=state.get("latest_price"))

    def _release_active_mission(self, opportunity_id: str) -> None:
        key = self._offered_missions.get(opportunity_id)
        state = self._missions.get(key)
        if state is not None and opportunity_id.endswith(state["mission_id"]):
            if state.get("active_paid"):
                # A chapter observed while the old attempt was still active
                # cannot be reused after it later failed. Begin new observation
                # from the retirement/detachment location without renewing it.
                state.update(active_paid=False, stage="SEEK_RETREAT",
                    post_fill_extreme=state.get("latest_price"))

    def detach_position_custody(self, ticker: str, opportunity_id: str) -> None:
        """Move this exact lot out of tactical occupancy; its mission stays paid."""
        self._detached_positions.add((ticker, opportunity_id))
        self._release_active_mission(opportunity_id)
        self._open_positions.get(ticker, set()).discard(opportunity_id)
        if not self._open_positions.get(ticker):
            self._open_tickers.discard(ticker)

    def recover_position_custody(self, ticker: str, opportunity_id: str) -> None:
        self._detached_positions.discard((ticker, opportunity_id))
        self._open_positions.setdefault(ticker, set()).add(opportunity_id)
        self._open_tickers.add(ticker)
        mission_key = self._offered_missions.get(opportunity_id)
        state = self._missions.get(mission_key)
        if state is not None and opportunity_id.endswith(state["mission_id"]):
            state.update(active_paid=True, stage="SEEK_RETREAT",
                         post_fill_extreme=state.get("latest_price"))
        key = (ticker, opportunity_id)
        if self._exit_latches.get(key) == "MOUNTAIN_ENTRY_EDGE_PERSISTENT_PHYSICAL_FAILURE":
            self._exit_latches.pop(key, None)
            self._failure_watches.pop(key, None)

    def mark_position_closed(
        self, *, ticker: str | None = None, release_handoff: bool = False,
        opportunity_id: str | None = None,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is not None:
            ids = self._open_positions.get(ticker, set())
            if opportunity_id is None and len(ids) == 1:
                opportunity_id = next(iter(ids))
            if opportunity_id is not None:
                self._release_active_mission(opportunity_id)
                ids.discard(opportunity_id)
                self._detached_positions.discard((ticker, opportunity_id))
                self._exit_latches.pop((ticker, opportunity_id), None)
                self._failure_watches.pop((ticker, opportunity_id), None)
                self._runner_harvest.pop(opportunity_id, None)
            if not ids:
                self._open_tickers.discard(ticker)

    @staticmethod
    def _full_arc_failure_scope(position: Mapping[str, Any], snapshot: MarketSnapshot,
                                details: Mapping[str, Any], entry: Mapping[str, Any],
                                owner: Side | None) -> dict[str, Any]:
        """A native strong flag cannot retire a still-valid full parent return.

        Bind the observed breakout to this lot's anticipated parent and its
        entry-time frozen parent-scale boundary. An old invalidation record
        still needs current price beyond that boundary in the same continuity
        generation; a source gap or another parent's failure supplies nothing.
        """
        mission = mapping(entry.get("mission"))
        context = mapping(snapshot.metadata.get("mission_context"))
        parent = mapping(context.get("parent"))
        geometry = mapping(snapshot.metadata.get("current_geometry"))
        scope_id, generation = mission.get("parent_leg_id"), mission.get("continuity_generation")
        scope = (mapping(mapping(context.get("parents_by_id")).get(scope_id))
                 if isinstance(scope_id, str) else {})
        if parent.get("id") == scope_id:
            scope = parent
        successor = mapping(parent.get("successor"))
        if successor.get("id") == scope_id:
            scope = successor
        side, entry_owner = as_side(position.get("side")), as_side(entry.get("owner_side"))
        source, context_source = number(details.get("source_ms")), number(context.get("source_ms"))
        entry_source, entry_time = number(mission.get("source_ms")), number(position.get("entry_time"))
        known, invalidated = number(scope.get("known_ms")), number(scope.get("invalidated_known_ms"))
        scope_source = number(scope.get("source_ms"))
        resolution = mapping(scope.get("outgoing_breakout_resolution"))
        resolution_source = number(resolution.get("source_ms"))
        resolution_width = number(resolution.get("threshold_btc"))
        anchor = number(scope.get("outgoing_extreme_btc"))
        tolerance = number(scope.get("outgoing_breakout_tolerance_btc"))
        price = number(details.get("current_btc"))
        sign = 1. if entry_owner is Side.YES else -1.
        beyond = sign * (price-anchor) if price is not None and anchor is not None else None
        source_bound = bool(source is not None and source > 0 and context_source == source
            and context.get("current") is True and snapshot.metadata.get("physical_current") is True
            and number(geometry.get("epoch_ms")) == source
            and number(geometry.get("btc_price")) == price
            and number(parent.get("source_ms")) == source
            and position.get("ticker") == snapshot.ticker)
        identity = bool(isinstance(scope_id, str) and scope_id
            and side is not None and as_side(mission.get("side")) is side
            and scope.get("id") == scope_id and as_side(scope.get("side")) is side
            and type(generation) is int and generation >= 0
            and all(type(value) is int and value == generation for value in (
                scope.get("continuity_generation"), context.get("continuity_generation"),
                parent.get("continuity_generation"), snapshot.metadata.get("geometry_continuity_generation")))
            and isinstance(parent.get("id"), str) and bool(parent["id"])
            and scope.get("predecessor_id") == parent["id"] and parent["id"] != scope_id
            and parent.get("status") == "ACTIVE" and parent.get("invalidated") is not True
            and owner is not None and owner is entry_owner and owner is not side
            and as_side(parent.get("side")) is owner)
        invalidation = bool(scope.get("status") == "INVALIDATED" and scope.get("invalidated") is True
            and scope.get("invalidation_reason") == "PARENT_EXTREME_REEXTENDED"
            and known is not None and entry_source is not None and entry_time is not None
            and scope_source is not None and invalidated is not None and source is not None
            and 0 < known <= entry_source <= entry_time*1000 < invalidated <= source
            and known <= scope_source <= invalidated)
        frozen_boundary = bool(resolution.get("basis") == "OBSERVED_PARENT_SCOPE_RANGE_RESOLUTION"
            and resolution_source is not None and resolution_source == known
            and resolution.get("fixed_duration_permission") is False
            and resolution_width is not None and resolution_width > 0
            and tolerance is not None and tolerance >= resolution_width
            and anchor is not None and anchor > 0)
        current_breakout = bool(frozen_boundary and beyond is not None and beyond > tolerance)
        return {"qualified": source_bound and identity and invalidation and current_breakout,
            "scope_id": scope_id, "scope_status": scope.get("status"),
            "predecessor_id": scope.get("predecessor_id"), "current_parent_id": parent.get("id"),
            "continuity_generation": generation, "source_ms": source,
            "current_source_bound": source_bound, "exact_scope_identity": identity,
            "invalidation_verified": invalidation, "invalidated_known_ms": invalidated,
            "invalidation_reason": scope.get("invalidation_reason"),
            "frozen_parent_boundary_verified": frozen_boundary,
            "frozen_anchor_btc": anchor, "frozen_breakout_tolerance_btc": tolerance,
            "current_outward_breakout_btc": beyond,
            "current_price_beyond_frozen_parent_boundary": current_breakout}

    def _failure_evidence(self, position: Mapping[str, Any], snapshot: MarketSnapshot,
                          details: Mapping[str, Any], entry: Mapping[str, Any],
                          owner: Side | None) -> dict[str, Any]:
        key = (str(position.get("ticker") or ""), str(position.get("opportunity_id") or ""))
        entry_owner = as_side(entry.get("owner_side"))
        side = as_side(position.get("side"))
        original = number(entry.get("owner_extreme_btc"))
        extreme = number(details.get("owner_extreme_btc"))
        price = number(details.get("current_btc"))
        source_ms = number(details.get("source_ms"))
        entry_time = number(position.get("entry_time"))
        tolerance = max(0.0, number(entry.get("edge_tolerance_dollars")) or 0.0)
        same_arc = bool(entry.get("entry_arc_id") and entry.get("entry_arc_id") == details.get("current_arc_id"))
        sign = 1.0 if entry_owner is Side.YES else -1.0
        anchor_breached = bool(same_arc and owner is entry_owner and owner is not side
            and original is not None and extreme is not None and sign * (extreme - original) > tolerance)
        current_beyond = bool(anchor_breached and price is not None
                              and sign * (price - original) > tolerance)
        motions = details.get("current_motion") or {}
        recent, longer = motions.get("6") or {}, motions.get("30") or {}
        expansion = bool(current_beyond and recent.get("covered") is True
            and longer.get("covered") is True
            and (number(recent.get("owner_ema9_rate_btc_s")) or 0) > 0
            and (number(longer.get("owner_ema9_rate_btc_s")) or 0) > 0
            and (number(recent.get("owner_price_rate_btc_s")) or 0) > 0
            and (number(longer.get("owner_price_rate_btc_s")) or 0) > 0)
        mission = entry.get("mission")
        full_arc_return = bool(isinstance(mission, Mapping)
                               and mission.get("purpose") == "ARC_RETURN")
        strong_release = details.get("strong_active_release") is True
        # A full-arc return is bought at a broad anticipatory peak/valley.
        # Its old owner may keep creeping outward while EMA9 catches up;
        # positive rates and a small new price record do not invalidate it.
        # Require a breakout of this exact anticipated parent, as well as
        # current strong-release evidence and the original failure conditions.
        parent_failure = (self._full_arc_failure_scope(position, snapshot, details, entry, owner)
                          if full_arc_return else {})
        failure_expansion = bool(expansion and (not full_arc_return
            or strong_release and parent_failure["qualified"]))
        source_age_limit = number(snapshot.metadata.get("geometry_max_source_age_seconds")) or 5.0
        post_entry = bool(source_ms is not None and entry_time is not None
                          and source_ms / 1000 > entry_time
                          and snapshot.metadata.get("physical_current") is not False
                          and current_source_is_fresh(snapshot, source_ms, max_age_seconds=source_age_limit))
        watch = self._failure_watches.get(key)
        if not failure_expansion or not post_entry:
            self._failure_watches.pop(key, None)
            watch = None
        elif watch is None or source_ms - watch["last_source_ms"] > 15000:
            watch = self._failure_watches[key] = {
                "first_breach_source_ms": source_ms, "last_source_ms": source_ms,
                "distinct_observations": 1}
        elif source_ms > watch["last_source_ms"]:
            watch["last_source_ms"] = source_ms
            watch["distinct_observations"] += 1
        elapsed = ((watch["last_source_ms"] - watch["first_breach_source_ms"]) / 1000
                   if watch else 0.0)
        age = snapshot.now_ts - entry_time if entry_time is not None else None
        qualified = bool(watch and elapsed >= self.config.failure_persistence_s
            and watch["distinct_observations"] >= 2 and age is not None
            and age >= self.config.ordinary_min_age_s)
        return {"anchor_breached": anchor_breached, "current_price_beyond_anchor": current_beyond,
                "owner_expansion_persistent": expansion, "post_entry_source_observed": post_entry,
                "full_arc_return": full_arc_return,
                "strong_active_release_required": full_arc_return,
                "current_strong_active_release": strong_release,
                "failure_expansion_qualified": failure_expansion,
                "full_arc_parent_failure": parent_failure,
                "qualified_persistent_failure": qualified, "elapsed_observed_s": elapsed,
                "distinct_observations": watch["distinct_observations"] if watch else 0,
                "first_breach_source_ms": watch["first_breach_source_ms"] if watch else None,
                "last_source_ms": source_ms, "entry_time": entry_time, "position_age_s": age,
                "ordinary_min_age_s": self.config.ordinary_min_age_s,
                "first_exhaustion_review_s": self.config.first_exhaustion_review_s,
                "review_zone_reached": age is not None and age >= self.config.first_exhaustion_review_s,
                "clock_alone_has_exit_authority": False,
                "entry_extreme_btc": original, "current_extreme_btc": extreme,
                "current_btc": price, "edge_tolerance_dollars": tolerance,
                "current_motion": {"6": recent, "30": longer}}

    def manage_position(
        self, position: Mapping[str, Any], snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        side = as_side(position.get("side"))
        ticker = str(position.get("ticker") or "")
        details = self._details(snapshot)
        entry = entry_metadata(position)
        if mapping(entry.get("mission")).get("purpose") == "ARC_RETURN":
            details = self._parent_geometry(snapshot) or details
        owner = _side(details.get("owner_side"))
        scoped = mission_collection_evidence(position, snapshot)
        collectible = (scoped["collection_qualified"] if scoped["scope_enforced"] else
                       self._collection_terminal_for_position(details, position))
        latch_key = (ticker, str(position.get("opportunity_id") or ""))
        opportunity_key = str(position.get("opportunity_id") or "")
        if not position.get("exit_required"):
            # An ordinary proposal which was not accepted as an exit/partial
            # must remain current. In particular a same-candle HOLD cannot
            # leave a phantom sell waiting for the next minute.
            self._exit_latches.pop(latch_key, None)

        parent = mapping(details.get("parent_structure"))
        parent_side = _side(parent.get("parent_side"))
        release_side = _side(snapshot.metadata.get("release_candidate_side"))
        low_wide_position = mapping(entry.get("low_wide_sideways_entry")).get("qualified") is True
        runner_eligible = bool(
            not low_wide_position
            and position_role(position) != "TACTICAL"
            and side is not None
            and (parent_side is side and (parent.get("extended_parent") is True
                                          or parent.get("slow_rolling_parent") is True)
                 or release_side is side and snapshot.metadata.get("release_in_progress") is True
                 or owner is side and details.get("strong_active_release") is True
                 or owner is side and abs(number(mapping(snapshot.metadata.get("current_geometry")).get("ema9_change30")) or 0.0) >= 3.0
                    and details.get("terminal_evidence_qualified") is not True)
        )
        runner = runner_harvest_update(
            self._runner_harvest, position, snapshot, eligible=runner_eligible,
            label="MOUNTAIN_RUNNER")
        companion = self._bridge_companion(position, snapshot)

        action, reason = Action.HOLD, "MOUNTAIN_CARRY_LIVING_LEG_TO_NEXT_EMA9_EDGE"
        if position.get("ticker") != snapshot.ticker:
            reason = "MOUNTAIN_AWAIT_EXACT_CONTRACT_CUSTODY"
        elif opposing_transfer(position, snapshot):
            action, reason = Action.EXIT, "MOUNTAIN_CONFIRMED_OPPOSING_PARENT_TRANSFER"
            self._exit_latches[latch_key] = reason
        elif companion is not None:
            # The cheap opposite bridge is already committed. Retire the old
            # normal-role lot on the next fresh management beat; the overlap is
            # a handoff bridge, never two independent strategic bets.
            action, reason = Action.EXIT, "MOUNTAIN_FAST_HANDOFF_BRIDGE_COMMITTED_EXIT_OUTGOING"
            self._exit_latches[latch_key] = reason
            self._release_active_mission(opportunity_key)
        elif runner.get("exit_now") is True:
            action, reason = Action.EXIT, str(runner.get("exit_reason"))
            self._exit_latches[latch_key] = reason
            self._release_active_mission(opportunity_key)
        elif runner.get("eligible") is True:
            # A proven runway/extended parent is governed by two distinct
            # slowdowns and an uptick harvest, not the ordinary edge/floor.
            reason = ("MOUNTAIN_RUNNER_SECOND_SLOWDOWN_HARVEST_ARMED_AWAIT_UPTICK_PEAK"
                      if runner.get("harvest_armed") else
                      "MOUNTAIN_RUNNER_FIRST_SLOWDOWN_HOLD_FOR_RESUME"
                      if runner.get("slowdown_count") == 1 else
                      "MOUNTAIN_RUNNER_STRUCTURAL_RUNWAY")
        elif collectible:
            entry_side = _opposite(owner)
            ask = snapshot.ask_for(entry_side) if entry_side is not None else None
            fast_bridge = (self._fast_narrow_handoff_context(snapshot, details, entry_side, ask)
                           if entry_side is not None else None)
            if fast_bridge is not None:
                # Give the entry loop one beat to book the already-cheap new
                # side before we sell the outgoing lot.
                reason = "MOUNTAIN_FAST_EDGE_PREENTRY_BRIDGE_WINDOW"
            else:
                action, reason = Action.EXIT, "MOUNTAIN_TERMINAL_EMA9_EDGE_EXIT"
                self._exit_latches[latch_key] = reason
                self._release_active_mission(opportunity_key)
        if latch_key in self._exit_latches:
            action, reason = Action.EXIT, self._exit_latches[latch_key]
        return [position_intent(
            tool=self.name, territory_id=self.territory_id, lane=Lane.MAIN,
            position=position, snapshot=snapshot, action=action, reason=reason,
            config=self.config,
            metadata={"edge_only_custody": True, "mission_collection": scoped,
                      "runner_harvest": runner,
                      "low_wide_sideways_position": low_wide_position,
                      "fast_handoff_companion_position_id": (companion or {}).get("position_id")
                          if isinstance(companion, Mapping) else None},
        )]

    def on_deactivate(
        self,
        snapshot: MarketSnapshot,
        reason: str,
    ) -> Iterable[ToolIntent]:
        self._active = False
        return [
            self._wait(
                snapshot,
                f"MOUNTAIN_DEACTIVATED:{reason}",
            )
        ]


class RollingMountainTool(AlternatingMountainTool):
    """Ordinary Mountain uses the same qualified EMA9 terminal-edge mission.

    A repeated alternating classification is not required to observe a genuine
    peak or valley. The entry evidence and physical attempt consumption stay
    identical; an ordinary price contact does not become an entry route.
    """

    name = "ROLLING_MOUNTAIN"
