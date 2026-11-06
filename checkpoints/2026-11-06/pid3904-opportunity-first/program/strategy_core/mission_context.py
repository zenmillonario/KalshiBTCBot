"""Causal parent/local mission measurements, independent of order execution.

The observed comparison envelope is a coarse direction reference.  This module
persists a separate parent identity across native children and contract rolls.
It also measures the same received path at that parent scale with the existing
Mountain detector. Completed chart closes supply a separately labeled full-leg
comparison envelope and contract scenarios; they are never inserted into the
intraminute detector path.

An anticipated successor is a declared candidate, not an observed reversal.
Its ID is promoted only when a later observed coarse reversal arrives.  Every
origin, recognition, terminal and transition keeps its separate source time.
No order, probability, fixed candle count or four-minute permission is created.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import math
from typing import Any, Mapping, Sequence

from strategy_core.leg_weakness import ParentWeaknessTracker
from strategy_core.parent_references import CompletedBarParentReferences, parent_return_timing_snapshot
from strategy_core.mission_scopes import PARENT_MISSION_PURPOSES, qualified_full_arc_candidate

from strategy_core.detectors.mountain_geometry import (
    ArcEpisode, MountainGeometryConfig, completed_mountain_references, detect_mountain_geometry,
)
from strategy_core.looking_glass import (
    CONTRACT_SECONDS, LookingGlassConfig, build_looking_glass,
)


VERSION = "CAUSAL_MISSION_CONTEXT_V1"
REACQUISITION_BASES = frozenset(("CURRENT_PRIMARY_REACQUISITION",
    "CURRENT_RELEASE_REACQUISITION", "FRESH_CONFIRMED_HANDOFF"))
PAID_ARC_HOLDING_REACQUISITION = "CURRENT_OBSERVED_PAID_ARC_HOLDING_REACQUISITION"
MAX_REACQUISITION_LINKS = 32


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else asdict(value) if is_dataclass(value) else {}


def _side(direction: Any) -> str | None:
    return {"UP": "YES", "DOWN": "NO", "YES": "YES", "NO": "NO"}.get(direction)


def _opposite(side: str | None) -> str | None:
    return {"YES": "NO", "NO": "YES"}.get(side)


def _direction(side: str | None) -> str | None:
    return {"YES": "UP", "NO": "DOWN"}.get(side)


def _sign(side: str) -> int:
    return 1 if side == "YES" else -1


def _empty_terminal(scope: str | None, side: str | None, source_ms: float | None,
                    generation: int, reason: str) -> dict[str, Any]:
    return {"qualified": False, "scope_id": scope, "side": side,
            "source_ms": source_ms, "known_ms": source_ms,
            "continuity_generation": generation, "reason": reason, "evidence": {}}




class MissionContext:
    """Append only received observations and return a detached JSON-safe view.

    ``rows`` should normally be ``DirectPhysicalFrame.new_rows``.  A previously
    received prefix can also be supplied; duplicates are ignored.  Historical
    candles require the same completed/known-at validation as Looking Glass.
    The return value is measurement context; Commander retains all admission,
    inventory, execution, recovery and fee/depth authority.
    """

    def __init__(self, config: MountainGeometryConfig | None = None, *,
                 history_contracts: int = 2, history_seconds: float = 7200.0) -> None:
        self.config = config or MountainGeometryConfig()
        self._lg_config = LookingGlassConfig(history_contracts=history_contracts)
        if not math.isfinite(history_seconds) or history_seconds <= 0:
            raise ValueError("MISSION_CONTEXT_INVALID_HISTORY_SECONDS")
        self.history_seconds = float(history_seconds)
        self._rows: deque[dict[str, Any]] = deque()
        self._parent_rows: deque[dict[str, Any]] = deque()
        self._parents: dict[str, dict[str, Any]] = {}
        self._weakness_trackers: dict[str, ParentWeaknessTracker] = {}
        self._parent: dict[str, Any] | None = None
        self._last: dict[str, Any] | None = None
        self._generation = 0
        self._external_generation: Any = None
        self._serial = 0
        self._reset_reason = "COLD_START"
        self._scoped_cache_key: tuple[Any, ...] | None = None
        self._scoped_cache: dict[str, Any] = {}
        self._past_contract_ranges: list[dict[str, Any]] = []
        self._range_open: float | None = None
        self._seed_candles: tuple[Mapping[str, Any], ...] = ()
        self._range_clock_origin: float | None = None
        self._range_cache_key: tuple[Any, ...] | None = None
        self._held_scope_ids: set[str] = set()
        self._held_missions: tuple[Mapping[str, Any], ...] = ()
        self._last_context: dict[str, Any] | None = None
        self._completed_parent_references: tuple[ArcEpisode, ...] = ()
        self._bar_parent_references = CompletedBarParentReferences(history_seconds=history_seconds)
        self._last_contract_record: dict[str, Any] | None = None

    @staticmethod
    def _main_missions(values: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        result = []
        for raw in values or ():
            mission = _map(raw)
            scope, generation = mission.get("parent_leg_id"), mission.get("continuity_generation")
            if (mission.get("purpose") in PARENT_MISSION_PURPOSES and _side(mission.get("side")) is not None
                    and isinstance(scope, str) and scope and type(generation) is int and generation >= 0
                    and _num(mission.get("source_ms")) is not None):
                result.append(mission)
        return result

    def _pin_held_scopes(self, missions: Sequence[Mapping[str, Any]]) -> None:
        self._held_missions = tuple(deepcopy(m) for m in self._main_missions(missions))
        self._held_scope_ids = {m["parent_leg_id"] for m in self._held_missions}

    def _pinned_scope_chain(self) -> set[str]:
        """Keep the exact held origin and its bounded observed adoption chain."""
        keep = set(self._held_scope_ids)
        for origin in tuple(keep):
            seen, scope = set(), origin
            for _ in range(MAX_REACQUISITION_LINKS + 1):
                if not scope or scope in seen:
                    break
                seen.add(scope)
                keep.add(scope)
                scope = _map(self._parents.get(scope)).get("reacquired_by_parent_id")
        return keep

    @staticmethod
    def _purchased_invalidated_arc(mission: Mapping[str, Any], node: Mapping[str, Any],
                                   source: float) -> bool:
        """Identify one actually held full return whose entry edge was revoked."""
        known, entry, invalidated = (_num(value) for value in (
            node.get("known_ms"), mission.get("source_ms"), node.get("invalidated_known_ms")))
        resolution = _map(node.get("outgoing_breakout_resolution"))
        width = _num(node.get("outgoing_breakout_tolerance_btc"))
        measured = _num(resolution.get("threshold_btc"))
        return bool(mission.get("purpose") == "ARC_RETURN"
            and mission.get("parent_leg_id") == node.get("id")
            and _side(mission.get("side")) == _side(node.get("side")) in ("YES", "NO")
            and type(mission.get("continuity_generation")) is int
            and mission["continuity_generation"] == node.get("continuity_generation")
            and node.get("status") == "INVALIDATED" and node.get("invalidated") is True
            and node.get("invalidation_reason") == "PARENT_EXTREME_REEXTENDED"
            and isinstance(node.get("predecessor_id"), str) and bool(node["predecessor_id"])
            and known is not None and entry is not None and invalidated is not None
            and 0 < known <= entry < invalidated <= source
            and resolution.get("basis") == "OBSERVED_PARENT_SCOPE_RANGE_RESOLUTION"
            and _num(resolution.get("source_ms")) == known
            and resolution.get("fixed_duration_permission") is False
            and measured is not None and measured > 0 and width is not None and width >= measured
            and (_num(node.get("outgoing_extreme_btc")) or 0) > 0
            and _map(node.get("terminal")).get("qualified") is not True)

    def _holding_arc_link(self, mission: Mapping[str, Any], node: Mapping[str, Any],
                          target: Mapping[str, Any], *, source: float,
                          basis: str) -> dict[str, Any] | None:
        """Create holding scope evidence without renewing the rejected entry."""
        if not self._purchased_invalidated_arc(mission, node, source):
            return None
        old_generation, new_generation = node.get("continuity_generation"), target.get("continuity_generation")
        observed, transition = _num(target.get("observed_known_ms")), _num(target.get("transition_known_ms"))
        invalidated = float(node["invalidated_known_ms"])
        current = bool(target.get("id") and target.get("id") != node["id"]
            and target.get("status") == "ACTIVE" and target.get("invalidated") is not True
            and _side(target.get("side")) == _side(node.get("side"))
            and target.get("source_ms") == source
            and type(old_generation) is int and type(new_generation) is int
            and new_generation == self._generation and old_generation <= new_generation
            and observed is not None and invalidated < observed <= source)
        same_parent_return = bool(current and old_generation == new_generation
            and basis == "CURRENT_OBSERVED_PARENT_RETURN_ADOPTION"
            and target.get("previous_id") == node["predecessor_id"]
            and target.get("predecessor_id") == node["predecessor_id"]
            and target.get("origin_observed") is True
            and target.get("basis") in ("OBSERVED_COMPARISON_ENVELOPE", "CONFIRMED_RELEASE_TRANSFER")
            and transition is not None and invalidated < transition <= observed)
        post_gap = bool(current and new_generation > old_generation
            and basis in REACQUISITION_BASES | {PAID_ARC_HOLDING_REACQUISITION})
        if not (same_parent_return or post_gap):
            return None
        return {"from_id": node["id"], "from_generation": old_generation,
            "to_id": target["id"], "to_generation": new_generation,
            "side": node["side"], "source_ms": source, "known_ms": source, "basis": basis,
            "holding_only": True, "purchased_purpose": "ARC_RETURN",
            "entry_source_ms": mission["source_ms"], "from_status": "INVALIDATED",
            "invalidated_known_ms": invalidated, "predecessor_id": node["predecessor_id"],
            "to_previous_id": target.get("previous_id"), "to_transition_known_ms": transition,
            "to_observed_known_ms": observed, "entry_invalidation_preserved": True,
            "gap_path_observed": False, "creates_terminal": False, "renews_entry_permission": False}

    def _valid_holding_arc_link(self, mission: Mapping[str, Any], node: Mapping[str, Any],
                                target: Mapping[str, Any], proof: Mapping[str, Any],
                                source: float) -> bool:
        # Later interruptions/completion of the adopted parent cannot rewrite
        # the already-observed link. Validate its creation-time fields against
        # the retained parent identity and immutable invalidation record.
        known = _num(proof.get("known_ms"))
        observed, transition = _num(target.get("observed_known_ms")), _num(target.get("transition_known_ms"))
        if (node.get("status") == "INTERRUPTED"
                and proof.get("basis") == PAID_ARC_HOLDING_REACQUISITION):
            origin = self._parents.get(mission.get("parent_leg_id"), {})
            prior_source = _num(node.get("source_ms"))
            old_generation, new_generation = node.get("continuity_generation"), target.get("continuity_generation")
            return bool(mission.get("purpose") == "ARC_RETURN"
                and origin.get("side") == mission.get("side") == node.get("side") == target.get("side")
                and origin.get("continuity_generation") == mission.get("continuity_generation")
                and proof.get("holding_only") is True and proof.get("purchased_purpose") == "ARC_RETURN"
                and proof.get("from_status") == "INTERRUPTED"
                and proof.get("entry_source_ms") == mission.get("source_ms")
                and proof.get("gap_path_observed") is False and proof.get("creates_terminal") is False
                and proof.get("renews_entry_permission") is False
                and proof.get("to_previous_id") == target.get("previous_id")
                and proof.get("to_observed_known_ms") == observed
                and known is not None and _num(proof.get("source_ms")) == known <= source
                and prior_source is not None and observed is not None and prior_source < observed <= known
                and type(old_generation) is int and type(new_generation) is int
                and old_generation < new_generation)
        if not self._purchased_invalidated_arc(mission, node, source) or known is None:
            return False
        old_generation, new_generation = node.get("continuity_generation"), target.get("continuity_generation")
        base = bool(proof.get("holding_only") is True and proof.get("purchased_purpose") == "ARC_RETURN"
            and proof.get("from_status") == "INVALIDATED"
            and proof.get("entry_invalidation_preserved") is True
            and proof.get("gap_path_observed") is False and proof.get("creates_terminal") is False
            and proof.get("renews_entry_permission") is False
            and proof.get("entry_source_ms") == mission.get("source_ms")
            and proof.get("invalidated_known_ms") == node.get("invalidated_known_ms")
            and proof.get("predecessor_id") == node.get("predecessor_id")
            and proof.get("to_previous_id") == target.get("previous_id")
            and proof.get("to_observed_known_ms") == observed
            and _num(proof.get("source_ms")) == known <= source
            and observed is not None and float(node["invalidated_known_ms"]) < observed <= known
            and type(old_generation) is int and type(new_generation) is int)
        if not base:
            return False
        if old_generation < new_generation:
            return proof.get("basis") in REACQUISITION_BASES | {PAID_ARC_HOLDING_REACQUISITION}
        return bool(old_generation == new_generation
            and proof.get("basis") == "CURRENT_OBSERVED_PARENT_RETURN_ADOPTION"
            and target.get("previous_id") == node.get("predecessor_id")
            and target.get("predecessor_id") == node.get("predecessor_id")
            and target.get("origin_observed") is True
            and _num(proof.get("to_transition_known_ms")) is not None
            and float(node["invalidated_known_ms"]) < proof["to_transition_known_ms"] <= observed
            # On completion transition_known_ms advances to the observed end.
            and transition is not None and proof["to_transition_known_ms"] <= transition)

    def _adopt_observed_paid_arc_return(self, source: float) -> list[dict[str, Any]]:
        links = []
        parent = self._parent or {}
        for mission in self._held_missions:
            node = self._parents.get(mission["parent_leg_id"])
            if node is None or node.get("reacquired_by_parent_id"):
                continue
            proof = self._holding_arc_link(mission, node, parent, source=source,
                basis="CURRENT_OBSERVED_PARENT_RETURN_ADOPTION")
            if proof:
                node["reacquired_by_parent_id"] = parent["id"]
                node["reacquisition"] = proof
                links.append(deepcopy(proof))
        return links

    def record_reacquisition(self, *, side: Any, source_ms: float,
                             continuity_generation: int, basis: str,
                             held_missions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Adopt a fresh same-side holding scope after observed reacquisition.

        Ordinary reacquisition uses current qualified primary/release evidence.
        An already purchased ARC may also use its current observed same-side
        parent independently of entry territory ownership. A link is a holding
        reference: it does not assert continuity through missing observations,
        create a terminal, renew entry economics, or modify the frozen entry.
        Repeated interruptions append links from the last interrupted scope;
        each edge remains an immutable, timestamped fact in recorded context.
        """
        missions = self._main_missions(held_missions)
        self._pin_held_scopes(missions)
        side = _side(getattr(side, "value", side))
        source = _num(source_ms)
        context, parent = self._last_context, self._parent
        links: list[dict[str, Any]] = []
        reason = "NO_ELIGIBLE_INTERRUPTED_HELD_SCOPE"
        current = bool(context and context.get("current") is True and self._last is not None
            and source is not None and source == self._last["epoch_ms"]
            and context.get("source_ms") == source
            and type(continuity_generation) is int and continuity_generation == self._generation
            and basis in REACQUISITION_BASES | {PAID_ARC_HOLDING_REACQUISITION} and side is not None
            and parent is not None and parent.get("status") == "ACTIVE"
            and parent.get("side") == side and parent.get("continuity_generation") == self._generation
            and parent.get("source_ms") == source and parent.get("invalidated") is not True)
        if not current:
            reason = "CURRENT_OBSERVED_SAME_SIDE_REACQUISITION_REQUIRED"
        else:
            for mission in missions:
                if (_side(mission.get("side")) != side or basis == PAID_ARC_HOLDING_REACQUISITION
                        and mission.get("purpose") != "ARC_RETURN"):
                    continue
                entry_source = _num(mission.get("source_ms"))
                origin = self._parents.get(mission["parent_leg_id"])
                if (origin is None or origin.get("side") != side
                        or origin.get("continuity_generation") != mission["continuity_generation"]
                        or entry_source is None or entry_source > source):
                    continue
                node, seen, previous_known, count = origin, set(), entry_source, 0
                while node.get("reacquired_by_parent_id"):
                    if node["id"] in seen or count >= MAX_REACQUISITION_LINKS:
                        node = None
                        break
                    seen.add(node["id"])
                    proof = _map(node.get("reacquisition"))
                    target = self._parents.get(node["reacquired_by_parent_id"])
                    known, proof_source = _num(proof.get("known_ms")), _num(proof.get("source_ms"))
                    ordinary = bool(node.get("status") == "INTERRUPTED"
                        and type(proof.get("from_generation")) is int
                        and type(proof.get("to_generation")) is int
                        and proof["from_generation"] < proof["to_generation"]
                        and proof.get("basis") in REACQUISITION_BASES)
                    holding = bool(target is not None and self._valid_holding_arc_link(
                        mission, node, target, proof, source))
                    if (not (ordinary or holding) or target is None
                            or proof.get("from_id") != node["id"] or proof.get("to_id") != target["id"]
                            or proof.get("from_generation") != node.get("continuity_generation")
                            or proof.get("to_generation") != target.get("continuity_generation")
                            or type(proof.get("from_generation")) is not int
                            or type(proof.get("to_generation")) is not int
                            or proof.get("side") != side or target.get("side") != side
                            or known is None or proof_source != known
                            or not previous_known <= known <= source):
                        node = None
                        break
                    previous_known, node, count = known, target, count + 1
                if (node is None or count >= MAX_REACQUISITION_LINKS or node["id"] == parent["id"]
                        or type(node.get("continuity_generation")) is not int
                        or node["continuity_generation"] >= self._generation
                        or node.get("side") != side):
                    continue
                if node.get("status") == "INVALIDATED":
                    proof = self._holding_arc_link(mission, node, parent, source=source, basis=basis)
                    if proof is None:
                        continue
                elif node.get("status") == "INTERRUPTED":
                    observed = _num(parent.get("observed_known_ms"))
                    prior_source = _num(node.get("source_ms"))
                    if (basis == PAID_ARC_HOLDING_REACQUISITION and (prior_source is None
                            or observed is None or not prior_source < observed <= source)):
                        continue
                    proof = {"from_id": node["id"], "from_generation": node["continuity_generation"],
                        "to_id": parent["id"], "to_generation": self._generation,
                        "side": side, "known_ms": source, "source_ms": source, "basis": basis,
                        "gap_path_observed": False, "creates_terminal": False,
                        "renews_entry_permission": False}
                    if basis == PAID_ARC_HOLDING_REACQUISITION:
                        proof.update(holding_only=True, purchased_purpose="ARC_RETURN",
                            entry_source_ms=mission["source_ms"], from_status="INTERRUPTED",
                            to_observed_known_ms=observed, to_previous_id=parent.get("previous_id"),
                            to_transition_known_ms=parent.get("transition_known_ms"),
                            to_origin_observed=parent.get("origin_observed") is True)
                else:
                    continue
                node["reacquired_by_parent_id"] = parent["id"]
                node["reacquisition"] = proof
                links.append(deepcopy(proof))
            if links:
                reason = ("PURCHASED_ARC_HOLDING_REACQUIRED" if any(link.get("holding_only") for link in links)
                          else "INTERRUPTED_HELD_SCOPE_REACQUIRED")
        if context is None:
            return {}
        context["parents_by_id"] = self._parents
        context["reacquisition_review"] = {"reason": reason, "basis": basis,
            "source_ms": source, "continuity_generation": continuity_generation,
            "links_created": links, "maximum_chain_links": MAX_REACQUISITION_LINKS}
        return deepcopy(context)

    def _identifier(self) -> str:
        self._serial += 1
        return f"P{self._generation:03d}L{self._serial:06d}"

    def _archive_parent_references(self) -> None:
        completed = completed_mountain_references(list(self._parent_rows), self.config)
        observed = {arc.arc_id: arc for arc in self._completed_parent_references}
        observed.update({arc.arc_id: arc for arc in completed
                    if arc.reference_kind == "SOVEREIGN_EMA9_ARC"
                    and arc.arc_id in self._parents
                    and self._parents[arc.arc_id].get("status") == "COMPLETED"})
        cutoff = (self._last["epoch_ms"] if self._last else 0) - self.history_seconds * 1000
        eligible = [arc for arc in observed.values()
            if arc.completed_known_ms is not None and arc.end_ms >= cutoff]
        bounded = []
        for direction in ("UP", "DOWN"):
            same = sorted((arc for arc in eligible if arc.direction == direction),
                          key=lambda arc: arc.end_ms)
            bounded.extend(same[-self.config.preferred_comparable_count:])
        self._completed_parent_references = tuple(sorted(bounded, key=lambda arc: arc.end_ms))

    def _reset(self, reason: str, generation: int | None = None) -> None:
        self._archive_parent_references()
        if self._parent is not None:
            self._parent.pop("geometry", None)
            self._parent.update(status="INTERRUPTED", supported=False, invalidated=False,
                                interruption_reason=reason)
            self._parent["terminal"] = _empty_terminal(
                self._parent["id"], self._parent["side"],
                self._last["epoch_ms"] if self._last else None,
                self._generation, "CONTINUITY_INTERRUPTED_NOT_A_TERMINAL")
            successor = self._parent.get("successor")
            if successor:
                successor.update(status="INTERRUPTED", supported=False, invalidated=False)
        self._generation = self._generation + 1 if generation is None else generation
        self._rows.clear()
        self._parent_rows.clear()
        self._parent = self._last = None
        self._reset_reason = reason
        self._scoped_cache_key, self._scoped_cache = None, {}
        self._range_cache_key = None
        self._last_contract_record = None

    @staticmethod
    def _coarse_side(row: Mapping[str, Any]) -> str | None:
        comparison = _map(row.get("comparison_arc"))
        source, known = _num(row.get("epoch_ms")), _num(comparison.get("arc_known_ms"))
        # During forward warmup this envelope falls back to native motion.
        # That fallback is not independent evidence for the larger parent.
        if (_num(row.get("struct_slope3m")) is None or source is None
                or known is None or known > source):
            return None
        return _side(comparison.get("arc_direction"))

    def _new_parent(self, row: Mapping[str, Any], side: str, *,
                    previous: Mapping[str, Any] | None = None,
                    seed_basis: str = "OBSERVED_COMPARISON_ENVELOPE") -> dict[str, Any]:
        source = float(row["epoch_ms"])
        anticipated = _map(previous.get("successor")) if previous else {}
        use_anticipated = bool(anticipated.get("status") == "ANTICIPATED"
                               and anticipated.get("side") == side)
        comparison = _map(row.get("comparison_arc"))
        origin = (_num(previous.get("ema9_extreme_source_ms")) if previous
                  else _num(comparison.get("arc_start_ms")))
        origin = origin if origin is not None and origin <= source else source
        origin_point = next((r for r in self._rows if abs(r["epoch_ms"] - origin) <= 1e-3), None)
        parent = {"id": anticipated["id"] if use_anticipated else self._identifier(),
            "side": side, "direction": _direction(side), "status": "ACTIVE",
            "previous_id": previous.get("id") if previous else None,
            "predecessor_id": previous.get("id") if previous else None,
            "known_ms": anticipated["known_ms"] if use_anticipated else source,
            "observed_known_ms": source, "transition_known_ms": source if previous else None,
            "origin_ms": origin, "origin_observed": origin_point is not None and (
                previous is not None or comparison.get("arc_origin_observed") is True),
            "source_ms": source, "continuity_generation": self._generation,
            "basis": seed_basis, "supported": True, "invalidated": False,
            "awaiting_comparison_alignment": seed_basis == "CONFIRMED_RELEASE_TRANSFER",
            "child_ids": [], "comparison_ids": [], "successor": None,
            "origin_ema9": origin_point["ema9"] if origin_point else float(row["ema9"]),
            "origin_btc": origin_point["btc_price"] if origin_point else None,
            "extreme_btc": float(row["btc_price"]), "extreme_source_ms": source,
            "observed_min_btc": float(row["btc_price"]), "observed_max_btc": float(row["btc_price"]),
            "ema9_extreme": float(row["ema9"]), "ema9_extreme_source_ms": source,
            "terminal": _empty_terminal(None, side, source, self._generation, "PARENT_IN_PROGRESS")}
        # Cold-start comparison arcs can be native children of a larger leg
        # whose observed origin is already present in completed minute history.
        # Bind that actual coarse origin once, without relabeling minute closes
        # as received samples or manufacturing pre-attachment weakness.
        history = self._bar_parent_references.active(source) if previous is None else None
        if (history and not parent["origin_observed"] and history["direction"] == parent["direction"]
                and history["known_ms"] <= source
                and 0 <= source - history["last_completed_source_ms"] <= 60_000
                and history["origin_ms"] < origin):
            parent.update(origin_ms=history["origin_ms"], origin_ema9=history["origin_ema9"],
                origin_btc=history["origin_btc"], origin_observed=False,
                origin_resolution="COMPLETED_MINUTE_CLOSES",
                observed_min_btc=min(history["observed_min_btc"], row["btc_price"]),
                observed_max_btc=max(history["observed_max_btc"], row["btc_price"]))
            sign = _sign(side)
            if sign * (history["extreme_btc"] - parent["extreme_btc"]) > 0:
                parent.update(extreme_btc=history["extreme_btc"],
                              extreme_source_ms=history["extreme_source_ms"])
            if sign * (history["ema9_extreme"] - parent["ema9_extreme"]) > 0:
                parent.update(ema9_extreme=history["ema9_extreme"],
                              ema9_extreme_source_ms=history["ema9_extreme_source_ms"])
            parent["active_minute_backbone"] = {**history, "parent_id": parent["id"],
                "side": side, "continuity_generation": self._generation,
                "bound_source_ms": source, "received_start_ms": source,
                "attachment_gap_seconds": (source - history["last_completed_source_ms"]) / 1000,
                "received_origin_observed": False, "gap_path_observed": False,
                "frozen_at_parent_creation": True, "weakness_history_created": False,
                "terminal_history_created": False}
            origin = parent["origin_ms"]
        self._parents[parent["id"]] = parent
        self._parent = parent
        self._weakness_trackers[parent["id"]] = ParentWeaknessTracker(
            parent["id"], side, self._generation,
            min_move=self.config.contact_min_dollars,
            slowdown_window_s=self.config.slowdown_window_s,
            sideways_min_btc_per_s=self.config.sideways_min_btc_per_s,
            sideways_range60_fraction_per_s=self.config.sideways_range60_fraction_per_s,
            range_move_fraction=self.config.contact_range60_fraction,
            max_gap_s=self.config.native_max_gap_s)
        if use_anticipated:
            anticipated.update(status="PROMOTED", promoted_known_ms=source)
        # Raw observed endpoints may precede recognition.  Knowledge does not.
        for point in self._rows:
            if origin <= point["epoch_ms"] <= source:
                self._update_extremes(parent, point)
                self._observe_weakness(parent, point, known_ms=source)
        parent["terminal"]["scope_id"] = parent["id"]
        return parent

    def _observe_weakness(self, parent: dict[str, Any], row: Mapping[str, Any],
                          *, known_ms: float | None = None) -> None:
        """Update a parent once per received price, never from an exit query."""
        tracker = self._weakness_trackers.get(parent["id"])
        if tracker is not None:
            parent["weakness"] = tracker.observe(row, known_ms=known_ms)

    @staticmethod
    def _update_extremes(parent: dict[str, Any], row: Mapping[str, Any]) -> None:
        sign = _sign(parent["side"])
        parent["observed_min_btc"] = min(parent["observed_min_btc"], row["btc_price"])
        parent["observed_max_btc"] = max(parent["observed_max_btc"], row["btc_price"])
        if sign * (row["btc_price"] - parent["extreme_btc"]) > 0:
            parent["extreme_btc"] = row["btc_price"]
            parent["extreme_source_ms"] = row["epoch_ms"]
        if sign * (row["ema9"] - parent["ema9_extreme"]) > 0:
            parent["ema9_extreme"] = row["ema9"]
            parent["ema9_extreme_source_ms"] = row["epoch_ms"]
        parent["source_ms"] = row["epoch_ms"]

    def _transition(self, row: Mapping[str, Any], side: str, *,
                    basis: str = "OBSERVED_COMPARISON_ENVELOPE") -> None:
        previous = self._parent
        if previous is None:
            self._new_parent(row, side, seed_basis=basis)
            return
        source = float(row["epoch_ms"])
        previous.update(status="COMPLETED", supported=False, invalidated=True,
                        transition_known_ms=source, completed_known_ms=source)
        previous.pop("geometry", None)
        previous["terminal"] = {**_empty_terminal(previous["id"], previous["side"],
            source, self._generation, "CONFIRMED_RELEASE_TRANSFER" if basis == "CONFIRMED_RELEASE_TRANSFER"
            else "OBSERVED_PARENT_REVERSAL"), "qualified": True,
            "evidence": {"transition_known_ms": source,
                "extreme_source_ms": previous["extreme_source_ms"],
                "extreme_btc": previous["extreme_btc"],
                "comparison_arc": deepcopy(row.get("comparison_arc")),
                "observed_transition_side": side, "native_id_alone": False}}
        self._new_parent(row, side, previous=previous, seed_basis=basis)

    def _range_boundary(self, parent: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
        excursion = max(0., float(parent.get("observed_max_btc", row["btc_price"]))
                             - float(parent.get("observed_min_btc", row["btc_price"])))
        completed = sorted((p for p in self._parents.values()
            if p.get("status") == "COMPLETED" and p.get("completed_known_ms", math.inf) <= row["epoch_ms"]),
            key=lambda p: p["completed_known_ms"], reverse=True)[:self._lg_config.history_contracts]
        prior_parent_ranges = [{"scope_id": p["id"], "known_ms": p["completed_known_ms"],
            "range_btc": max(0., p["observed_max_btc"] - p["observed_min_btc"])} for p in completed]
        historical = self._past_contract_ranges or prior_parent_ranges
        reference = max([excursion, *(r["range_btc"] for r in historical)])
        threshold = max(self.config.min_retreat_dollars, self.config.retreat_range60_fraction * reference)
        retreat = _sign(parent["side"]) * (parent["extreme_btc"] - row["btc_price"])
        return {"basis": "OBSERVED_PARENT_SCOPE_RANGE_RESOLUTION",
            "observed_parent_excursion_btc": excursion,
            "completed_prior_contract_ranges": deepcopy(self._past_contract_ranges),
            "completed_parent_fallback_ranges": prior_parent_ranges if not self._past_contract_ranges else [],
            "reference_range_btc": reference, "range_fraction": self.config.retreat_range60_fraction,
            "minimum_dollars": self.config.min_retreat_dollars, "threshold_btc": threshold,
            "observed_retreat_btc": retreat, "clears_boundary": retreat >= threshold,
            "source_ms": row["epoch_ms"], "fixed_duration_permission": False}

    @staticmethod
    def _parent_entry_zone(parent: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
        """Describe actual location; elapsed parent age is not a price zone."""
        origin, price, extreme = (_num(value) for value in (
            parent.get("origin_btc"), row.get("btc_price"), parent.get("extreme_btc")))
        side = _side(parent.get("side"))
        source = _num(row.get("epoch_ms"))
        boundary = _map(parent.get("transition_boundary"))
        width = _num(boundary.get("threshold_btc"))
        observed = bool(parent.get("origin_observed") is True and origin is not None)
        located = bool(side and price is not None and extreme is not None and width is not None
            and width > 0 and parent.get("source_ms") == source
            and boundary.get("source_ms") == source)
        sign = _sign(side) if side else 0
        travel = sign * (price - origin) if located and observed else None
        full_travel = sign * (extreme - origin) if located and observed else None
        retreat = sign * (extreme - price) if located else None
        near_origin = bool(travel is not None and abs(travel) <= width)
        near_extreme = bool(retreat is not None and 0 <= retreat <= width)
        return {"basis": "ACTUAL_PARENT_PRICE_ZONE", "parent_id": parent.get("id"),
            "parent_side": side, "source_ms": source,
            "continuity_generation": parent.get("continuity_generation"),
            "origin_ms": parent.get("origin_ms"), "origin_observed": observed,
            "origin_btc": origin, "current_btc": price, "extreme_btc": extreme,
            "directional_travel_from_origin_btc": travel,
            "directional_extreme_travel_btc": full_travel, "retreat_from_extreme_btc": retreat,
            "zone_width_btc": width, "near_origin": near_origin, "near_extreme": near_extreme,
            "location": "ORIGIN_ZONE" if near_origin else "EXTREME_ZONE" if near_extreme
                else "LEG_INTERIOR" if located and observed else "ORIGIN_UNOBSERVED",
            "age_is_location_permission": False}

    def _historical_ranges(self, candles: Sequence[Mapping[str, Any]], opening: float, now: float) -> None:
        self._range_open = opening
        self._past_contract_ranges = []
        for index in range(1, self._lg_config.history_contracts + 1):
            start, end = opening - index * CONTRACT_SECONDS, opening - (index - 1) * CONTRACT_SECONDS
            by_time: dict[float, tuple[float, float, float]] = {}
            conflicts: set[float] = set()
            for raw in candles:
                row = _map(raw)
                ts, known, close = _num(row.get("time")), _num(row.get("known_at")), _num(row.get("close"))
                if (ts is None or ts % 60 or not start <= ts < end or ts + 60 > now
                        or row.get("complete") is not True or row.get("full_minute") is False
                        or known is not None and known > now or "known_at" in row and known is None
                        or close is None or close <= 0):
                    continue
                low, high = _num(row.get("low")), _num(row.get("high"))
                if low is None and high is None:
                    low = high = close  # actual closes only; never invented intraminute extrema
                if low is None or high is None or not 0 < low <= close <= high:
                    continue
                value = (low, high, close)
                if ts in by_time and by_time[ts] != value:
                    conflicts.add(ts)
                by_time[ts] = value
            expected = {start + 60 * offset for offset in range(15)}
            if set(by_time) == expected and not conflicts:
                lows, highs = [v[0] for v in by_time.values()], [v[1] for v in by_time.values()]
                self._past_contract_ranges.append({"start_ts": start, "end_ts": end,
                    "known_by_ts": now, "range_btc": max(highs) - min(lows),
                    "observed_low": min(lows), "observed_high": max(highs),
                    "basis": "COMPLETED_OBSERVED_BAR_RANGE", "minute_count": len(by_time)})

    def _refresh_ranges(self, source_ms: float) -> None:
        """Resolve past scope windows at this row's knowledge boundary.

        Bulk replay must not apply the final checkpoint's completed contract
        range to earlier observations.  Actual native samples can describe an
        already completed window without fabricating a historical candle.
        """
        if self._range_clock_origin is None:
            return
        now = source_ms / 1000
        opening = self._range_clock_origin + math.floor(
            (now - self._range_clock_origin) / CONTRACT_SECONDS) * CONTRACT_SECONDS
        known_seed = max((_num(c.get("known_at")) or (_num(c.get("time")) or 0) + 60
                          for c in self._seed_candles
                          if (_num(c.get("known_at")) or (_num(c.get("time")) or 0) + 60) <= now),
                         default=None)
        key = (opening, known_seed, self._generation)
        if key == self._range_cache_key:
            return
        self._historical_ranges(self._seed_candles, opening, now)
        available = {(r["start_ts"], r["end_ts"]) for r in self._past_contract_ranges}
        tolerance = self.config.native_max_gap_s
        for index in range(1, self._lg_config.history_contracts + 1):
            start, end = opening - index * CONTRACT_SECONDS, opening - (index - 1) * CONTRACT_SECONDS
            if (start, end) in available:
                continue
            points = [p for p in self._rows if start <= p["epoch_ms"] / 1000 <= end]
            if len(points) < 2:
                continue
            first, last = points[0]["epoch_ms"] / 1000, points[-1]["epoch_ms"] / 1000
            max_gap = max((b["epoch_ms"] - a["epoch_ms"]) / 1000 for a, b in zip(points, points[1:]))
            if first - start > tolerance or end - last > tolerance or max_gap > tolerance:
                continue
            low, high = min(p["btc_price"] for p in points), max(p["btc_price"] for p in points)
            self._past_contract_ranges.append({"start_ts": start, "end_ts": end,
                "known_by_ts": now, "range_btc": high - low,
                "observed_low": low, "observed_high": high,
                "basis": "CONTINUOUS_OBSERVED_SOURCE_SAMPLES", "sample_count": len(points),
                "first_source_ms": points[0]["epoch_ms"], "last_source_ms": points[-1]["epoch_ms"],
                "max_source_gap_seconds": max_gap,
                "opening_boundary_gap_seconds": first - start,
                "closing_boundary_gap_seconds": end - last,
                "unobserved_extrema_inferred": False})
        self._range_cache_key = key

    def _append_parent_row(self, row: Mapping[str, Any]) -> None:
        parent = self._parent
        if parent is None:
            return
        self._update_extremes(parent, row)
        self._observe_weakness(parent, row)
        native, coarse = row.get("arc_id"), _map(row.get("comparison_arc")).get("arc_id")
        for key, value in (("child_ids", native), ("comparison_ids", coarse)):
            if value and value not in parent[key]:
                parent[key].append(str(value))
                parent[key] = parent[key][-64:]
        projected = {k: v for k, v in row.items() if k != "comparison_arc"}
        projected.update(arc_id=parent["id"], arc_direction=parent["direction"],
            arc_start_ms=parent["origin_ms"], arc_known_ms=parent["observed_known_ms"],
            arc_origin_observed=parent["origin_observed"], arc_previous_id=parent["previous_id"],
            arc_age_sec=max(0.0, (row["epoch_ms"] - parent["origin_ms"]) / 1000),
            arc_amplitude=abs(parent["ema9_extreme"] - parent["origin_ema9"]),
            arc_start_ema9=parent["origin_ema9"], arc_extreme_ema9=parent["ema9_extreme"],
            arc_extreme_ms=parent["ema9_extreme_source_ms"],
            arc_recognition_basis="OBSERVED_ENVELOPE_HISTORY_ONLY",
            arc_birth_prominence_threshold=_map(row.get("comparison_arc")).get("arc_birth_prominence_threshold"),
            arc_birth_reversal_amount=_map(row.get("comparison_arc")).get("arc_birth_reversal_amount"))
        if self._parent_rows and self._parent_rows[-1]["epoch_ms"] == row["epoch_ms"]:
            # Same-current-source confirmed Release is resolved before intents;
            # earlier emitted observations are never relabeled.
            self._parent_rows[-1] = projected
        else:
            self._parent_rows.append(projected)
        self._freeze_return_timing_reference(parent, row)

    def _freeze_return_timing_reference(self, parent: dict[str, Any], row: Mapping[str, Any]) -> None:
        """Bind actual known timings once; an unavailable origin stays unknown."""
        if parent.get("status") != "ACTIVE" or "return_timing_reference" in parent:
            return
        source = float(row["epoch_ms"])
        available = {arc.arc_id: arc for arc in self._completed_parent_references}
        for arc in completed_mountain_references(list(self._parent_rows), self.config):
            if (arc.reference_kind == "SOVEREIGN_EMA9_ARC"
                    and _map(self._parents.get(arc.arc_id)).get("status") == "COMPLETED"):
                available[arc.arc_id] = arc
        received = [{"id": arc.arc_id, "side": _side(arc.direction), "direction": arc.direction,
            "origin_ms": arc.start_ms, "end_ms": arc.end_ms, "duration_seconds": arc.duration_s,
            "completed_known_ms": arc.completed_known_ms, "origin_observed": arc.origin_observed,
            "complete_observed_path": arc.coverage.get("complete_observed_path") is True,
            "max_source_gap_seconds": arc.coverage.get("completion_max_sample_gap_s",
                                                        arc.coverage.get("max_sample_gap_s"))}
            for arc in available.values() if arc.reference_kind == "SOVEREIGN_EMA9_ARC"
            and arc.end_ms >= source - self.history_seconds * 1000]
        minutes = self._bar_parent_references.envelope(source_ms=source, direction=parent["direction"],
            minimum_count=self.config.minimum_comparable_count,
            preferred_count=self.config.preferred_comparable_count)
        origin = _num(parent.get("origin_ms"))
        path = [point for point in self._rows if origin is not None
                and origin - 1e-3 <= point["epoch_ms"] <= source]
        parent["return_timing_reference"] = parent_return_timing_snapshot(parent,
            source_ms=source, path=path, received_references=received,
            minute_references=minutes["references"], minimum_count=self.config.minimum_comparable_count,
            preferred_count=self.config.preferred_comparable_count,
            max_gap_seconds=self.config.native_max_gap_s)

    def _ingest(self, rows: Sequence[Mapping[str, Any]], now_ms: float) -> str | None:
        for raw in rows:
            row = dict(_map(raw))
            values = {k: _num(row.get(k)) for k in ("epoch_ms", "btc_price", "ema9", "ema30")}
            if any(v is None or v <= 0 for v in values.values()):
                continue
            row.update(values)
            source = row["epoch_ms"]
            known = _num(row.get("known_at_ms"))
            future_ms = self._lg_config.future_skew_seconds * 1000.0
            if source > now_ms + future_ms or known is not None and known > now_ms + future_ms:
                continue
            if self._last is not None and source <= self._last["epoch_ms"]:
                if source == self._last["epoch_ms"] and any(
                    row[k] != self._last[k] for k in ("btc_price", "ema9", "ema30")):
                    return "CONFLICTING_SOURCE_OBSERVATION"
                continue
            if self._last is not None:
                gap = source - self._last["epoch_ms"]
                old_epoch, epoch = self._last.get("connection_epoch"), row.get("connection_epoch")
                if old_epoch is not None and epoch is not None and epoch != old_epoch:
                    self._reset("CONNECTION_EPOCH_CHANGED")
                elif gap > self.config.native_max_gap_s * 1000:
                    self._reset("SOURCE_GAP")
            self._rows.append(row)
            self._refresh_ranges(source)
            coarse = self._coarse_side(row)
            if self._parent is None and coarse:
                self._new_parent(row, coarse)
            elif self._parent is not None:
                self._update_extremes(self._parent, row)
                # The final observed price still belongs to the outgoing
                # scope before a separately confirmed full-parent transfer.
                self._observe_weakness(self._parent, row)
                boundary = self._range_boundary(self._parent, row)
                self._parent["transition_boundary"] = boundary
                if coarse == self._parent["side"]:
                    self._parent["awaiting_comparison_alignment"] = False
                elif (coarse and not self._parent.get("awaiting_comparison_alignment")
                      and boundary["clears_boundary"]
                      and (not self._parent.get("active_minute_backbone")
                           or _num(row.get("struct_slope3m")) is not None
                           and _sign(coarse) * row["struct_slope3m"]
                               >= self._bar_parent_references.prominence_dollars)):
                    self._transition(row, coarse)
            self._append_parent_row(row)
            self._last = row
            cutoff = source - self.history_seconds * 1000
            while self._rows and self._rows[0]["epoch_ms"] < cutoff:
                self._rows.popleft()
            while self._parent_rows and self._parent_rows[0]["epoch_ms"] < cutoff:
                self._parent_rows.popleft()
        return None

    def _local_terminal(self, mountain: Mapping[str, Any], row: Mapping[str, Any],
                        current: bool) -> dict[str, Any]:
        source, scope = float(row["epoch_ms"]), str(row.get("arc_id") or "")
        side = _side(mountain.get("owner_side"))
        result = _empty_terminal(scope or None, side, source, self._generation,
                                 "NO_CURRENT_QUALIFIED_LOCAL_TERMINAL")
        measured = _num(mountain.get("source_ms"))
        qualified = bool(current and scope and side and measured is not None
            and measured == source and mountain.get("current_arc_id") == scope
            and _num(row.get("arc_known_ms")) is not None
            and float(row["arc_known_ms"]) <= source
            and _num(row.get("arc_start_ms")) is not None
            and float(row["arc_start_ms"]) <= source
            and mountain.get("mature_edge") is True
            and mountain.get("terminal_evidence_qualified") is True
            and mountain.get("edge_window_active", True) is True
            and mountain.get("strong_active_release") is not True
            and mountain.get("spent_edge") is not True)
        if qualified:
            retest = _map(_map(mountain.get("primary_collection_evidence")).get("retest_rejection"))
            result.update(qualified=True,
                reason="OBSERVED_RETEST_REJECTION" if self._valid_retest(retest, source)
                else "QUALIFIED_LOCAL_EDGE", evidence={
                    "entry_routes": list(mountain.get("entry_routes") or ()),
                    "retreat_dollars": _num(mountain.get("retreat_dollars")),
                    "owner_extreme_btc": _num(mountain.get("owner_extreme_btc")),
                    "edge_extreme_ms": _num(mountain.get("edge_extreme_ms")),
                    "retest_rejection": deepcopy(retest),
                    "primary_collection_terminal_qualified": mountain.get("primary_collection_terminal_qualified") is True})
        return result

    @staticmethod
    def _valid_retest(proof: Mapping[str, Any], source: float) -> bool:
        times = [_num(proof.get(k)) for k in
                 ("extreme_source_ms", "retreat_source_ms", "retest_source_ms", "current_source_ms")]
        prices = [_num(proof.get(k)) for k in
                  ("extreme_btc", "retreat_btc", "retest_btc", "current_btc")]
        return bool(proof.get("qualified") is True
            and proof.get("endpoints_are_actual_observations") is True
            and all(t is not None and t <= source for t in times)
            and all(p is not None and p > 0 for p in prices)
            and all(a < b for a, b in zip(times, times[1:])))

    def _parent_terminal(self, mountain: Mapping[str, Any], local: Mapping[str, Any],
                         row: Mapping[str, Any], current: bool) -> dict[str, Any]:
        parent = self._parent
        if parent is None:
            return _empty_terminal(None, None, row["epoch_ms"], self._generation, "PARENT_UNKNOWN")
        source = float(row["epoch_ms"])
        result = _empty_terminal(parent["id"], parent["side"], source,
                                 self._generation, "PARENT_IN_PROGRESS")
        parent["entry_edge"] = _empty_terminal(parent["id"], parent["side"], source,
            self._generation, "NO_CURRENT_PARENT_ENTRY_EDGE")
        if not current:
            parent["geometry"] = {"source_ms": source, "current_arc_id": parent["id"],
                "owner_side": parent["side"], "current": False,
                "continuity_generation": self._generation,
                "terminal_evidence_qualified": False, "mature_edge": False,
                "reason": "CURRENT_SOURCE_UNAVAILABLE"}
            result["reason"] = "CURRENT_SOURCE_UNAVAILABLE"
            return result
        boundary = self._range_boundary(parent, row)
        parent["transition_boundary"] = boundary
        tolerance = max(boundary["threshold_btc"], self.config.min_retreat_dollars,
                        _num(mountain.get("edge_tolerance_dollars")) or 0,
                        _num(mountain.get("contact_width")) or 0)
        local_same_side = local.get("qualified") is True and local.get("side") == parent["side"]
        local_extreme = _num(mountain.get("owner_extreme_btc"))
        at_parent_extreme = bool(local_extreme is not None
            and abs(local_extreme - parent["extreme_btc"]) <= tolerance)
        retest = _map(_map(mountain.get("primary_collection_evidence")).get("retest_rejection"))
        witnessed_retest = bool(local_same_side and at_parent_extreme
            and self._valid_retest(retest, source)
            and abs(float(retest["extreme_btc"]) - parent["extreme_btc"]) <= tolerance)
        # Reuse the existing comparable-shape and observed-retest measurements
        # on the independently labeled larger path.  No local reference is
        # silently promoted into this detector's parent reference family.
        cache_key = (parent["id"], source, len(self._parent_rows))
        if self._scoped_cache_key != cache_key:
            references = tuple(arc for arc in self._completed_parent_references
                if arc.completed_known_ms is not None and arc.completed_known_ms <= source
                and source - self.history_seconds * 1000 <= arc.end_ms)
            self._scoped_cache = detect_mountain_geometry(list(self._parent_rows), self.config,
                historical_references=references).tool_metadata()
            self._scoped_cache_key = cache_key
        scoped = deepcopy(self._scoped_cache)
        bar_envelope = self._bar_parent_references.envelope(source_ms=source,
            direction=parent["direction"], minimum_count=self.config.minimum_comparable_count,
            preferred_count=self.config.preferred_comparable_count)
        age = max(0., (source - parent["origin_ms"]) / 1000.)
        ema_extension = abs(parent["ema9_extreme"] - parent["origin_ema9"])
        price_extension = parent["observed_max_btc"] - parent["observed_min_btc"]
        scale_reference = _map(bar_envelope.get("scale_reference"))
        reference_values = {"duration": _num(scale_reference.get("duration_seconds")),
            "ema9_extension": _num(scale_reference.get("ema9_excursion")),
            "price_range": _num(scale_reference.get("observed_close_range"))}
        current_values = {"duration": age, "ema9_extension": ema_extension,
                          "price_range": price_extension}
        scale_progress = {key: current_values[key] / value if value is not None and value > 0 else None
                          for key, value in reference_values.items()}
        covered = _map(scoped.get("current_path_coverage")).get("complete_observed_path") is True
        backbone = _map(parent.get("active_minute_backbone"))
        received = [point for point in self._rows
                    if backbone and backbone["received_start_ms"] <= point["epoch_ms"] <= source]
        received_gaps = [(b["epoch_ms"] - a["epoch_ms"]) / 1000
                         for a, b in zip(received, received[1:])]
        backbone_covered = bool(backbone and backbone["parent_id"] == parent["id"]
            and backbone["continuity_generation"] == self._generation
            and backbone["side"] == parent["side"] and backbone["known_ms"] <= backbone["bound_source_ms"] <= source
            and backbone["complete_minute_coverage"] is True and received_gaps
            and received[0]["epoch_ms"] == backbone["received_start_ms"]
            and received[-1]["epoch_ms"] == source and max(received_gaps) <= self.config.native_max_gap_s)
        slowdown = _map(scoped.get("slowdown"))
        near_extreme = boundary["observed_retreat_btc"] <= boundary["threshold_btc"]
        envelope_mature = bool((bar_envelope["enough_references"] and covered and parent["origin_observed"]
            or backbone_covered and bool(scale_reference)) and all(value is not None
                and value >= self.config.protected_middle_fraction for value in scale_progress.values()))
        envelope_edge = bool(envelope_mature and near_extreme
            and slowdown.get("observed") is True
            and scoped.get("strong_active_release") is not True
            and scoped.get("spent_edge") is not True)
        bar_envelope.update(current_age_seconds=age, current_ema9_extension=ema_extension,
            current_observed_price_range=price_extension, current_path_complete=covered,
            protected_middle_fraction=self.config.protected_middle_fraction,
            scale_progress=scale_progress,
            mature_extension=envelope_mature, near_current_parent_extreme=near_extreme,
            current_slowdown_observed=slowdown.get("observed") is True,
            entry_edge_qualified=envelope_edge,
            comparison_rule="CURRENT_MATURE_ZONE_OF_ONE_ACTUAL_RECENT_FULL_LEG")
        if backbone:
            bar_envelope["active_minute_backbone"] = {**backbone,
                "current_received_path_complete_since_attachment": backbone_covered,
                "received_sample_count": len(received),
                "received_max_gap_seconds": max(received_gaps) if received_gaps else None,
                "current_source_ms": source, "current_parent_extreme_btc": parent["extreme_btc"],
                "current_parent_resolution": deepcopy(boundary),
                "received_path_complete_from_historical_origin": False,
                "one_actual_completed_reference_is_entry_comparison": True,
                "timing_reference_minimum_unchanged": self.config.minimum_comparable_count}
            scoped.update(owner_extreme_btc=parent["extreme_btc"],
                edge_extreme_ms=parent["extreme_source_ms"],
                retreat_dollars=boundary["observed_retreat_btc"],
                retreat_threshold=boundary["threshold_btc"])
        if envelope_edge:
            scoped.update(mature_edge=True, edge_window_active=True,
                terminal_evidence_qualified=True, primary_collection_terminal_qualified=True,
                comparable_slow_edge=slowdown.get("sideways_observed") is True)
            scoped["entry_routes"] = [*(scoped.get("entry_routes") or ()),
                                      "COMPLETED_MINUTE_PARENT_ENVELOPE_EDGE"]
            scoped["primary_collection_evidence"] = {
                **_map(scoped.get("primary_collection_evidence")),
                "completed_minute_parent_envelope_qualified": True,
                "qualification_routes": [*(_map(scoped.get("primary_collection_evidence"))
                    .get("qualification_routes") or ()), "COMPLETED_MINUTE_PARENT_ENVELOPE_EDGE"]}
        scoped["completed_minute_parent_reference"] = bar_envelope
        # A paired price/EMA separation identifies a possible local extreme;
        # it does not establish that the current leg has reached full scale.
        # In particular, a six-second pause must not promote a young rebound
        # into a blind full return merely because its references have parent
        # IDs. Keep the independently measured maturity evidence separate
        # from both entry location and the later collection terminal.
        comparable_mature = (_map(scoped.get("primary_collection_evidence"))
                              .get("comparable_current_leg_mature") is True)
        scoped_current = bool(scoped.get("current_arc_id") == parent["id"]
            and _side(scoped.get("owner_side")) == parent["side"]
            and _num(scoped.get("source_ms")) == source)
        full_leg_scale = {"qualified": scoped_current and (comparable_mature or envelope_mature),
            "basis": "INDEPENDENT_CURRENT_PARENT_SCALE_V1", "parent_id": parent["id"],
            "side": parent["side"], "source_ms": source,
            "comparable_current_leg_mature": comparable_mature,
            "completed_minute_parent_mature": envelope_mature,
            "comparison_family": "received_parent" if comparable_mature else
                "completed_minute_parent" if envelope_mature else None,
            "family_selection": "INDEPENDENT_RECEIVED_MATURITY_FIRST_ELSE_COMPLETED_MINUTE_MATURITY",
            "paired_gap_match_alone_is_permission": False}
        scoped["full_leg_scale_evidence"] = full_leg_scale
        parent["geometry"] = self._compact_parent_geometry(scoped)
        parent["measurements"] = {
            "age_seconds": max(0.0, (source - parent["origin_ms"]) / 1000),
            "ema9_excursion": abs(parent["ema9_extreme"] - parent["origin_ema9"]),
            "comparable_durations_s": list(_map(scoped.get("diagnostics")).get("comparable_durations_s") or ()),
            "source_ms": source, "basis": "ACTUAL_RECEIVED_PARENT_PATH",
            "completed_parent_reference_count": len(self._completed_parent_references),
            "completed_minute_parent_reference": deepcopy(bar_envelope)}
        scoped_qualified = bool(scoped.get("terminal_evidence_qualified") is True
            and scoped.get("primary_collection_terminal_qualified") is True
            and scoped.get("strong_active_release") is not True
            and scoped.get("spent_edge") is not True
            and scoped.get("current_arc_id") == parent["id"]
            and _side(scoped.get("owner_side")) == parent["side"])
        scoped_retest = _map(_map(scoped.get("primary_collection_evidence")).get("retest_rejection"))
        routes = list(scoped.get("entry_routes") or ())
        peak_family = _map(scoped.get("reference_history")).get("selected_peak_reference_family")
        parent_entry = bool(scoped.get("terminal_evidence_qualified") is True
            and scoped.get("mature_edge") is True
            and scoped.get("strong_active_release") is not True
            and scoped.get("spent_edge") is not True
            and scoped.get("current_arc_id") == parent["id"]
            and ("COMPLETED_MINUTE_PARENT_ENVELOPE_EDGE" in routes
                 or "COMPARABLE_SHAPE_DURATION_EDGE" in routes
                 or peak_family == "WHOLE_MOUNTAIN" and full_leg_scale["qualified"]
                 or self._valid_retest(scoped_retest, source)))
        if witnessed_retest or parent_entry:
            # A historical gap match or observed rejection can remain valid
            # after the return is underway. Every fresh full-parent entry
            # still belongs to the current broad extreme, measured at this
            # parent's observed range resolution. End/collection evidence
            # below is independent and can remain valid after leaving it.
            parent["entry_edge"].update(qualified=near_extreme,
                reason="PARENT_ENTRY_OUTSIDE_CURRENT_EXTREME_AREA" if not near_extreme
                       else "OBSERVED_PARENT_RETEST_REJECTION" if witnessed_retest
                       else "PARENT_SCALE_ANTICIPATORY_EDGE",
                evidence={"parent_resolution": boundary, "parent_entry_routes": routes,
                    "near_current_parent_extreme": near_extreme,
                    "selected_peak_reference_family": peak_family,
                    "full_leg_scale_evidence": deepcopy(full_leg_scale),
                    "retest_rejection": deepcopy(retest) if witnessed_retest else deepcopy(scoped_retest),
                    "entry_qualification_is_not_main_collection": True})
        elif (peak_family == "WHOLE_MOUNTAIN"
              and _map(scoped.get("paired_gap_evidence")).get("eligible") is True
              and not full_leg_scale["qualified"]):
            parent["entry_edge"].update(reason="PAIRED_GAP_MATCH_WITHOUT_CURRENT_FULL_LEG_SCALE",
                evidence={"parent_entry_routes": routes,
                    "near_current_parent_extreme": near_extreme,
                    "full_leg_scale_evidence": deepcopy(full_leg_scale),
                    "local_tactical_classification_preserved": True})
        if witnessed_retest or scoped_qualified:
            reason = ("OBSERVED_PARENT_RETEST_REJECTION" if witnessed_retest
                      or scoped_qualified and self._valid_retest(scoped_retest, source)
                      else "PARENT_SCALE_COMPARABLE_TERMINAL")
            result.update(qualified=True, reason=reason, evidence={
                "parent_extreme_btc": parent["extreme_btc"],
                "parent_extreme_source_ms": parent["extreme_source_ms"],
                "local_extreme_at_parent": at_parent_extreme,
                "tolerance_dollars": tolerance,
                "parent_resolution": boundary,
                "retest_rejection": deepcopy(retest) if witnessed_retest else deepcopy(scoped_retest),
                "parent_entry_routes": list(scoped.get("entry_routes") or ()),
                "parent_collection_evidence": deepcopy(scoped.get("primary_collection_evidence") or {}),
                "local_arc_id": row.get("arc_id"), "native_id_alone": False})
        return result

    def _compact_parent_geometry(self, scoped: Mapping[str, Any]) -> dict[str, Any]:
        """Publish current scope measurements without duplicating path proofs."""
        keys = ("source_ms", "current_arc_id", "owner_side", "current_btc", "current_ema9",
            "current_ema30", "owner_extreme_btc", "owner_price_gap", "edge_extreme_ms", "edge_id",
            "edge_tolerance_dollars", "retreat_dollars", "retreat_threshold", "contact_width",
            "arc_origin_ms", "arc_origin_observed", "sample_interval_s", "quality", "detector",
            "mature_edge", "edge_window_active", "stall", "hesitation", "failed_reextension",
            "meaningful_retreat", "strong_active_release", "spent_edge", "shallow_edge_exception",
            "equal_duration_accelerating", "terminal_evidence_qualified", "comparable_slow_edge",
            "primary_collection_terminal_qualified", "current_motion", "slowdown", "entry_routes",
            "current_path_coverage", "current_ema9_terminal_window", "reference_history",
            "primary_collection_evidence", "completed_minute_parent_reference", "full_leg_scale_evidence")
        result = {key: deepcopy(scoped.get(key)) for key in keys}
        result.update(current=True, continuity_generation=self._generation)
        result["paired_gap_evidence"] = {k: deepcopy(v) for k, v in
            _map(scoped.get("paired_gap_evidence")).items()
            if v is None or isinstance(v, (str, int, float, bool))}
        result["diagnostics"] = {"comparable_durations_s": list(
            _map(scoped.get("diagnostics")).get("comparable_durations_s") or ())}
        return result

    def _contract_continuation(self, parent: Mapping[str, Any], *, ticker: str,
                               opening: float, closing: float, source: float | None,
                               current: bool, valid_clock: bool) -> dict[str, Any]:
        """Carry earned physical scope over an actually observed contract roll.

        The new contract still needs a current value location and progress.
        A clock boundary alone cannot create either a new leg or permission.
        """
        stored = _map(parent.get("contract_continuation"))
        valid = bool(current and valid_clock and source is not None and parent
            and parent.get("status") == "ACTIVE" and parent.get("origin_observed") is True
            and parent.get("continuity_generation") == self._generation
            and isinstance(ticker, str) and ticker
            and abs(closing - opening - CONTRACT_SECONDS) <= 1e-6)
        if (valid and stored.get("ticker") == ticker
                and stored.get("parent_leg_id") == parent.get("id")
                and stored.get("continuity_generation") == self._generation):
            return dict(stored)
        prior = self._last_contract_record or {}
        eligible = bool(valid and prior.get("ticker") != ticker
            and prior.get("parent_leg_id") == parent.get("id")
            and prior.get("side") == parent.get("side")
            and prior.get("continuity_generation") == self._generation
            and prior.get("close_ts") == opening
            and _num(prior.get("source_ms")) is not None
            and prior["source_ms"] < opening * 1000 <= source
            and (prior.get("earned_location") is True or prior.get("held_scope") is True))
        if not eligible:
            return {"qualified": False, "ticker": ticker,
                "basis": "OBSERVED_SAME_PARENT_ROLLOVER_REQUIRES_PRIOR_EARNED_SCOPE",
                "opening_time_alone_is_permission": False}
        return {"qualified": True, "ticker": ticker, "from_ticker": prior["ticker"],
            "parent_leg_id": parent["id"], "side": parent["side"],
            "continuity_generation": self._generation, "known_ms": source,
            "prior_source_ms": prior["source_ms"], "opening_ms": opening * 1000,
            "prior_earned_location": prior.get("earned_location") is True,
            "prior_held_scope": prior.get("held_scope") is True,
            "basis": "OBSERVED_SAME_PARENT_ROLLOVER_WITH_PRIOR_EARNED_SCOPE",
            "opening_time_alone_is_permission": False}

    def _current_rail_value(self, metadata: Mapping[str, Any], parent: Mapping[str, Any],
                            row: Mapping[str, Any], *, side: str, current: bool,
                            current_progress: bool, near_ema9: bool,
                            material_return: bool) -> dict[str, Any]:
        """A currently measured Rail earns its own continuation value event.

        A long uninterrupted Rail can have a partial startup origin and no
        completed mountain reversals. Its independently observed persistence,
        current same-side structure and value contact remain usable. A retained
        owner label or near-EMA contact by itself cannot provide this proof.
        """
        detector = _map(metadata.get("rail_detector"))
        sides = detector.get("ema9_sides") or ()
        persistence = _num(metadata.get("persistence_seconds"))
        minimum = _num(detector.get("qualification_min_persistence_s"))
        source = _num(row.get("epoch_ms"))
        sign = _sign(side)
        slopes = [_num(row.get(key)) for key in
                  ("struct_slope3m", "struct_slope6m", "struct_slope9m", "ema30_slope3m")]
        structure = bool(len(sides) == 3 and all(value == side for value in sides)
            and all(value is not None and sign * value > 0 for value in slopes))
        qualified = bool(current and source is not None and parent.get("status") == "ACTIVE"
            and parent.get("side") == side and parent.get("source_ms") == source
            and parent.get("continuity_generation") == self._generation
            and metadata.get("geometry_continuity_generation") == self._generation
            and _num(metadata.get("geometry_last_epoch_ms")) == source
            and _map(metadata.get("territory_detector_summary")).get("rail_established") is True
            and minimum is not None and minimum > 0
            and persistence is not None and persistence >= minimum
            and structure and current_progress and near_ema9 and not material_return)
        return {"qualified": qualified, "basis": "CURRENT_OBSERVED_RAIL_CONTINUATION_VALUE",
            "parent_leg_id": parent.get("id"), "side": side, "source_ms": source,
            "continuity_generation": self._generation,
            "rail_established": _map(metadata.get("territory_detector_summary")).get("rail_established") is True,
            "observed_persistence_seconds": persistence, "required_persistence_seconds": minimum,
            "current_structure_same_side": structure,
            "current_progress_supported": current_progress, "near_living_ema9": near_ema9,
            "material_parent_return_observed": material_return,
            "retained_owner_alone_is_permission": False}

    def _successor(self, terminal: Mapping[str, Any], row: Mapping[str, Any],
                   tolerance: float) -> None:
        parent = self._parent
        if parent is None:
            return
        successor = parent.get("successor")
        boundary = self._range_boundary(parent, row)
        # A full return belongs to the whole parent. Freeze its breakout
        # distance when the edge is first observed; a tiny contact tolerance
        # must not retire that scope on each small new high in a broad top.
        # The frozen distance cannot grow as price moves against the entry.
        breakout_tolerance = (
            (_num(successor.get("outgoing_breakout_tolerance_btc")) if successor else None)
            or max(tolerance, boundary["threshold_btc"]))
        if successor and _sign(parent["side"]) * (
                row["btc_price"] - successor["outgoing_extreme_btc"]) > breakout_tolerance:
            successor.update(status="INVALIDATED", supported=False, invalidated=True,
                invalidated_known_ms=row["epoch_ms"], invalidation_reason="PARENT_EXTREME_REEXTENDED")
            parent["successor"] = None
            successor = None
        if terminal.get("qualified") is True and successor is None:
            side, scope = _opposite(parent["side"]), self._identifier()
            successor = {"id": scope, "side": side, "direction": _direction(side),
                "predecessor_id": parent["id"], "previous_id": parent["id"],
                "known_ms": row["epoch_ms"], "source_ms": row["epoch_ms"],
                "continuity_generation": self._generation, "status": "ANTICIPATED",
                "supported": True, "invalidated": False,
                "outgoing_extreme_btc": parent["extreme_btc"],
                "outgoing_breakout_tolerance_btc": max(tolerance, boundary["threshold_btc"]),
                "outgoing_breakout_resolution": deepcopy(boundary),
                "terminal": _empty_terminal(scope, side, row["epoch_ms"],
                    self._generation, "ANTICIPATED_INCOMING_LEG_HAS_NO_TERMINAL")}
            parent["successor"] = successor
            self._parents[scope] = successor
        if successor:
            successor["source_ms"] = row["epoch_ms"]
            successor["supported"] = terminal.get("qualified") is True

    @staticmethod
    def _scenario_side(paths: Sequence[Mapping[str, Any]], family: str) -> str:
        sides = {p.get("endpoint_side") for p in paths if p.get("family") == family}
        if len(sides) == 1 and sides <= {"YES", "NO"}:
            return next(iter(sides))
        # MIXED means observed paths actually finish on competing sides.
        # A missing target, an at-target endpoint or an unresolved path does
        # not establish that competition and cannot confer a side thesis.
        return "MIXED" if {"YES", "NO"} <= sides else "UNKNOWN"

    def observe(self, metadata: Mapping[str, Any], *, ticker: str, open_ts: float,
                close_ts: float, target: float | None, now_ts: float,
                rows: Sequence[Mapping[str, Any]] = (),
                historical_candles: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
        now = _num(now_ts)
        if now is None or now <= 0:
            raise ValueError("MISSION_CONTEXT_INVALID_NOW")
        if "position_inventory" in metadata:
            self._pin_held_scopes(tuple(_map(_map(p).get("entry_metadata")).get("mission") or {}
                                       for p in metadata.get("position_inventory") or ()))
        geometry = _map(metadata.get("current_geometry"))
        self._range_clock_origin = _num(open_ts)
        if historical_candles:
            self._bar_parent_references.ingest(historical_candles, now_ms=now * 1000)
            self._seed_candles = tuple(dict(_map(c)) for c in historical_candles)
            self._range_cache_key = None
        external = metadata.get("geometry_continuity_generation")
        external = external if isinstance(external, int) and not isinstance(external, bool) and external >= 0 else None
        if self._external_generation is None and external is not None:
            self._generation = external
        elif external is not None and external != self._external_generation:
            acknowledged_local_reset = (external == self._generation
                and self._reset_reason in ("SOURCE_GAP", "CONNECTION_EPOCH_CHANGED"))
            if not acknowledged_local_reset:
                self._reset("GEOMETRY_CONTINUITY_CHANGED", generation=external)
        if external is not None:
            self._external_generation = external
        error = self._ingest([*rows, geometry], now * 1000)
        row = self._last or {}
        source = _num(row.get("epoch_ms"))
        if source is not None:
            self._refresh_ranges(source)
        current = bool(not error and source is not None
            and -self._lg_config.future_skew_seconds <= now - source / 1000 <= 3.0
            and metadata.get("physical_current") is True
            and _num(geometry.get("epoch_ms")) == source
            and all(_num(geometry.get(k)) == row.get(k) for k in ("btc_price", "ema9", "ema30")))
        valid_clock = bool(_num(open_ts) is not None and _num(close_ts) is not None
                           and open_ts <= now < close_ts)
        lg = build_looking_glass({"ticker": ticker, "time": source / 1000 if source else None,
            "close_ts": close_ts, "target": target, "btc": row.get("btc_price"),
            "e9": row.get("ema9"), "e30": row.get("ema30"),
            "fresh": current and valid_clock and abs(close_ts - open_ts - CONTRACT_SECONDS) <= 1e-6},
            candles=historical_candles, now_ts=now, config=self._lg_config)
        if self._parent is None and current:
            seed_side = _side(_map(lg.get("observations")).get("ema9_direction"))
            if seed_side:
                self._new_parent(row, seed_side, seed_basis="OBSERVED_COMPLETED_CLOSE_CONTEXT")
                self._append_parent_row(row)
        confirmed_side = _side(metadata.get("confirmed_release_side"))
        confirmed_release = bool(current and confirmed_side is not None
            and _num(metadata.get("confirmed_release_source_ms")) == source)
        if confirmed_release:
            if self._parent is None or self._parent["side"] != confirmed_side:
                self._transition(row, confirmed_side, basis="CONFIRMED_RELEASE_TRANSFER")
                self._append_parent_row(row)
            self._parent["confirmed_release"] = {"side": confirmed_side,
                "source_ms": source, "basis": "CONFIRMED_RELEASE_TRANSFER"}
        mountain = _map(metadata.get("mountain"))
        local_terminal = (self._local_terminal(mountain, row, current) if row else
                          _empty_terminal(None, None, source, self._generation, "SOURCE_UNAVAILABLE"))
        parent_terminal = (self._parent_terminal(mountain, local_terminal, row, current) if row else
                           _empty_terminal(None, None, source, self._generation, "SOURCE_UNAVAILABLE"))
        if self._parent is not None:
            self._parent["terminal"] = parent_terminal
            self._parent["supported"] = current and not parent_terminal["qualified"]
            if current:
                self._successor(self._parent["entry_edge"], row, max(self.config.contact_min_dollars,
                    _num(mountain.get("contact_width")) or 0,
                    _num(mountain.get("edge_tolerance_dollars")) or 0))
            elif self._parent.get("successor"):
                self._parent["successor"]["supported"] = False
        parent = self._parent or {}
        holding_adoptions = self._adopt_observed_paid_arc_return(source) if current else []
        rollover = self._contract_continuation(parent, ticker=ticker, opening=open_ts,
            closing=close_ts, source=source, current=current, valid_clock=valid_clock)
        if parent and rollover.get("qualified") is True:
            parent["contract_continuation"] = rollover
        local_side = _side(row.get("arc_direction"))
        return_side = _opposite(local_terminal.get("side")) if local_terminal["qualified"] else None
        incoming = _opposite(parent.get("side")) if _map(parent.get("entry_edge")).get("qualified") is True else None
        physical_thesis = incoming or parent.get("side")
        lg_lean = _map(lg.get("thesis")).get("physical_lean")
        scenario = ("CONTINUATION" if physical_thesis == lg_lean else "REVERSAL"
                    if physical_thesis in ("YES", "NO") and lg_lean in ("YES", "NO") else None)
        thesis = self._scenario_side(lg.get("paths") or (), scenario) if scenario else "UNKNOWN"
        candidates: dict[str, Any] = {}
        tolerance = max(self.config.contact_min_dollars, _num(mountain.get("contact_width")) or 0)
        probe = _map(metadata.get("release_probe"))
        expansion = _map(_map(probe.get("diagnostics")).get("expansion_measurement"))
        motions = _map(expansion.get("motion"))
        parent_entry_zone = self._parent_entry_zone(parent, row)
        for side in ("YES", "NO"):
            classification, qualified_edge = "UNRESOLVED", False
            scope_id = parent.get("id")
            reason = "NO_CURRENT_PHYSICAL_MISSION"
            if current and parent.get("side") == side and not parent_terminal["qualified"]:
                classification, reason = "MAIN_CONTINUATION", "PERSISTENT_PARENT_DIRECTION"
            local_supports_parent = bool(current and return_side == side and parent.get("side") == side)
            if current and return_side == side:
                classification, qualified_edge = ("MAIN_CONTINUATION" if local_supports_parent else "LOCAL_RETURN"), True
                reason = "QUALIFIED_INTERNAL_RETURN_SUPPORTS_PARENT" if local_supports_parent else "QUALIFIED_LOCAL_EDGE_PRESERVED_SEPARATELY"
            if current and incoming == side and _map(parent.get("successor")).get("supported") is True:
                classification, qualified_edge = "PARENT_EDGE_RETURN", True
                scope_id = parent["successor"]["id"]
                reason = parent["entry_edge"]["reason"]
            sign = _sign(side)
            progress = [_num(row.get(k)) for k in ("micro_slope6s", "micro_slope9s")]
            current_progress = bool(current and all(v is not None for v in progress)
                and min(sign * v for v in progress) >= 0 and max(sign * v for v in progress) > 0)
            continuation_supported = bool(current and parent.get("side") == side
                and not parent_terminal["qualified"] and (current_progress or local_supports_parent))
            measurements = _map(parent.get("measurements"))
            durations = [_num(v) for v in measurements.get("comparable_durations_s") or ()]
            durations = [v for v in durations if v is not None and v > 0]
            duration_family = "RECEIVED_PARENT_PATH"
            bar_reference = _map(measurements.get("completed_minute_parent_reference"))
            if (len(durations) < self.config.minimum_comparable_count
                    and bar_reference.get("enough_references") is True
                    and bar_reference.get("current_path_complete") is True):
                durations = [_num(r.get("duration_seconds")) for r in
                    bar_reference.get("references") or () if isinstance(r, Mapping)]
                durations = [v for v in durations if v is not None and v > 0]
                duration_family = "COMPLETED_MINUTE_PARENT"
            observed_early_parent = bool(parent.get("origin_observed") is True
                and len(durations) >= self.config.minimum_comparable_count
                and (_num(measurements.get("age_seconds")) or 0)
                    < self.config.protected_middle_fraction * sum(durations) / len(durations))
            near_ema9_value = bool(current and abs(row["btc_price"] - row["ema9"]) <= tolerance)
            material_return = _map(parent.get("transition_boundary")).get("clears_boundary") is True
            inherited_value = bool(rollover.get("qualified") is True
                and current_progress and parent.get("side") == side and not material_return)
            rail_value = self._current_rail_value(metadata, parent, row, side=side,
                current=current, current_progress=current_progress, near_ema9=near_ema9_value,
                material_return=material_return)
            release_progress = []
            for horizon in ("6", "30"):
                motion = _map(motions.get(horizon))
                btc_change, ema_change = _num(motion.get("btc_change")), _num(motion.get("ema9_change"))
                release_progress.append(bool(motion.get("covered") is True
                    and btc_change is not None and ema_change is not None
                    and sign * btc_change > 0 and sign * ema_change > 0))
            observed_release = bool(current and all(release_progress)
                and expansion.get("mountain_strong_active_release") is True
                and _num(_map(probe.get("diagnostics")).get("source_ms")) == source)
            located = bool(qualified_edge or continuation_supported and (
                parent_entry_zone["near_origin"] and current_progress and not material_return or inherited_value
                or rail_value["qualified"]
                or confirmed_release and confirmed_side == side and current_progress))
            candidates[side] = {"classification": classification, "side": side,
                "qualified_edge": qualified_edge, "parent_leg_id": scope_id,
                "swing_id": row.get("arc_id"), "source_ms": source,
                "continuity_generation": self._generation, "reason": reason,
                "continuation_supported": continuation_supported,
                "current_progress_supported": current_progress,
                "local_edge_supports_parent": local_supports_parent,
                "entry_location_qualified": located,
                "location_evidence": {"near_living_ema9": near_ema9_value,
                    "parent_entry_zone": dict(parent_entry_zone),
                    "ema_contact_alone_is_entry_permission": False,
                    "observed_early_parent": observed_early_parent,
                    "observed_early_parent_is_permission": False,
                    "parent_reference_durations_s": durations,
                    "parent_reference_family": duration_family,
                    "material_parent_return_observed": material_return,
                    "inherited_contract_value_location": inherited_value,
                    "current_rail_value": rail_value,
                    "contract_continuation": dict(rollover), "recognition_freshness_used": False,
                    "opening_time_used_as_permission": False},
                "observed_release_continuation": {"qualified": observed_release,
                    "source_ms": source, "side": side,
                    "confirmed_handoff": confirmed_release and confirmed_side == side,
                    "basis": "COVERED_CURRENT_BTC_EMA9_EXPANSION", "requires_confirmed_release_intent": True},
                "contract_thesis_supports_side": thesis == side,
                "destination": {"kind": "EMA9_RETURN" if qualified_edge else "PARENT_TERMINAL",
                    "btc": row.get("ema9") if qualified_edge else None,
                    "tolerance": tolerance, "reference_source_ms": source,
                    "scope_id": row.get("arc_id") if qualified_edge else scope_id}}
            if located and parent.get("side") == side and current:
                parent["last_earned_entry_location"] = {"source_ms": source,
                    "ticker": ticker, "parent_leg_id": parent["id"],
                    "continuity_generation": self._generation,
                    "basis": "QUALIFIED_INTERNAL_VALUE_EDGE" if qualified_edge else
                        "CONFIRMED_RELEASE_TRANSFER" if confirmed_release else
                        "OBSERVED_ROLLOVER_VALUE" if inherited_value else
                        "CURRENT_OBSERVED_RAIL_VALUE" if rail_value["qualified"] else "OBSERVED_EARLY_PARENT"}
        if current and valid_clock and parent and abs(close_ts - open_ts - CONTRACT_SECONDS) <= 1e-6:
            earned = _map(parent.get("last_earned_entry_location"))
            self._last_contract_record = {"ticker": ticker, "open_ts": open_ts, "close_ts": close_ts,
                "source_ms": source, "parent_leg_id": parent["id"], "side": parent["side"],
                "continuity_generation": self._generation,
                "earned_location": earned.get("parent_leg_id") == parent["id"]
                    and earned.get("continuity_generation") == self._generation
                    and _num(earned.get("source_ms")) is not None and earned["source_ms"] <= source,
                "held_scope": parent["id"] in self._pinned_scope_chain()}
        # Retain recent exact scope IDs for current/anticipated/completed holds.
        active_ids = {parent.get("id"), _map(parent.get("successor")).get("id")}
        ordered = sorted(self._parents.values(), key=lambda p: p.get("known_ms") or 0, reverse=True)
        keep = ({p["id"] for p in ordered[:max(8, self.config.preferred_comparable_count * 4)]}
                | active_ids | self._pinned_scope_chain())
        self._parents = {k: v for k, v in self._parents.items() if k in keep}
        self._weakness_trackers = {k: v for k, v in self._weakness_trackers.items() if k in keep}
        target_value = _num(target)
        if target_value is not None and target_value <= 0:
            target_value = None
        signed_gap = row.get("btc_price", 0) - target_value if row and target_value is not None else None
        result = {"version": VERSION, "source_ms": source, "observed_at": now,
            "current": current, "status": "CURRENT" if current else error or "UNAVAILABLE_OR_STALE",
            "continuity_generation": self._generation, "reset_reason": self._reset_reason,
            "execution_authority": False, "probabilities_calibrated": False,
            "parent": parent or None, "parents_by_id": self._parents,
            "local": {"arc_id": row.get("arc_id"), "scope_id": row.get("arc_id"),
                "side": local_side, "origin_ms": row.get("arc_start_ms"),
                "known_ms": row.get("arc_known_ms"), "terminal": local_terminal,
                "remaining_return_btc": _num(mountain.get("owner_price_gap")),
                "contact_width": tolerance, "new_native_is_not_new_parent": True},
            "candidates": candidates,
            "prior_contracts": deepcopy(_map(lg.get("reference_window")).get("contracts") or []),
            "contract": {"ticker": ticker, "open_ts": open_ts, "close_ts": close_ts,
                "target": target_value, "remaining_seconds": max(0.0, close_ts - now) if valid_clock else None,
                "current_signed_target_gap": signed_gap,
                "observed_target_side": "YES" if signed_gap is not None and signed_gap > 0 else (
                    "NO" if signed_gap is not None and signed_gap < 0 else "AT_TARGET" if signed_gap == 0 else "UNKNOWN"),
                "thesis_side": thesis, "physical_thesis_side": physical_thesis,
                "scenario_family": scenario, "basis": "CONDITIONAL_PRIOR_CONTRACT_PATHS_AND_CURRENT_PHYSICAL_SCOPE",
                "reason": "Conditional endpoints support this side." if thesis in ("YES", "NO") else
                          "Current physical purpose has mixed or unavailable conditional endpoints.",
                "settlement_prediction": False, "hard_opening_cutoff_seconds": None,
                "history_status": lg.get("status"), "reference_window": deepcopy(lg.get("reference_window")),
                "prior_contracts": deepcopy(_map(lg.get("reference_window")).get("contracts") or []),
                "scenarios": [{k: p.get(k) for k in ("id", "family", "endpoint_btc", "endpoint_ema9",
                    "endpoint_side", "reference_ids", "reference_known_by_ts", "conditional", "not_a_settlement_prediction")}
                    for p in lg.get("paths") or ()]},
            "renewal": {"parent_leg_id": parent.get("id"), "native_arc_id": row.get("arc_id"),
                "native_change_renews_parent": False, "paid_attempt_registry_changed": False,
                "existing_physical_renewal": deepcopy(metadata.get("physical_renewal"))}}
        if holding_adoptions:
            result["reacquisition_review"] = {"reason": "PURCHASED_ARC_OBSERVED_RETURN_ADOPTED",
                "basis": "CURRENT_OBSERVED_PARENT_RETURN_ADOPTION", "source_ms": source,
                "continuity_generation": self._generation, "links_created": holding_adoptions,
                "maximum_chain_links": MAX_REACQUISITION_LINKS}
        self._last_context = result
        if current and any(m.get("purpose") == "ARC_RETURN" for m in self._held_missions):
            earlier_review = result.get("reacquisition_review")
            linked = self.record_reacquisition(side=parent.get("side"), source_ms=source,
                continuity_generation=self._generation, basis=PAID_ARC_HOLDING_REACQUISITION,
                held_missions=self._held_missions)
            created = _map(linked.get("reacquisition_review")).get("links_created") or []
            if created and earlier_review:
                result["reacquisition_review"]["links_created"] = [
                    *earlier_review.get("links_created", ()), *created]
            elif not created:
                if earlier_review is not None:
                    result["reacquisition_review"] = earlier_review
                else:
                    result.pop("reacquisition_review", None)
        return deepcopy(result)
