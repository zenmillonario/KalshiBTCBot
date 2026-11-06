"""Causal opportunity observations owned by the single Commander.

An excursion is a WATCH, not an order.  This module supplies the Commander's
shared positive admission contract and remembers physical excursions between
book callbacks.  It has no executor, account access, independent veto or
position-management authority.  Future prices and eventual outcomes are never
inputs.  All thresholds below reuse existing Mountain/Heist/value definitions.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import math
from typing import Any, Mapping

from strategy_core.commander_candidates import (
    _candidate, _current_ema9_renewed_flow_rejoin,
    _recent_level_return_location_ready, _counterparent_level_rejection_sustained,
    _return_settlement_feasible, _inherited_leg_still_live,
    _preopen_observed_ema9_sprout_continuation, physical_entry_candidates,
    current_mountain_terminal, settlement_runway_for_side,
)
from strategy_core.directional_parent import directional_parent_evidence
from strategy_core.mission_scopes import qualified_full_arc_candidate
from strategy_core.source_freshness import current_source_is_fresh
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


REVISION = "OPPORTUNITY_FIRST_COMMANDER_V1"


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _side(value: Any) -> Side | None:
    if isinstance(value, Side):
        return value
    return {"YES": Side.YES, "UP": Side.YES, "NO": Side.NO, "DOWN": Side.NO}.get(str(value).upper())


def _sign(side: Side) -> float:
    return 1.0 if side is Side.YES else -1.0


def _json_safe(value: Any) -> Any:
    """Return a detached JSON audit even when a rejected input is nonfinite."""
    if isinstance(value,Mapping):
        return {str(k):_json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value,float):
        return value if math.isfinite(value) else None
    if value is None or isinstance(value,(str,int,bool)):
        return value
    return str(value)


def _source(snapshot: MarketSnapshot) -> float | None:
    return _num(_map(snapshot.metadata.get("current_geometry")).get("epoch_ms"))


def _current(snapshot: MarketSnapshot) -> bool:
    """Missing/inconsistent source is WAIT, including direct decide() callers."""
    md = snapshot.metadata
    source, captured = _source(snapshot), _num(md.get("geometry_last_epoch_ms"))
    return bool(md.get("physical_current") is True and source is not None
        and captured is not None and abs(source - captured) <= .001
        and type(md.get("geometry_continuity_generation")) is int
        and md["geometry_continuity_generation"] >= 0
        and current_source_is_fresh(snapshot, source, max_age_seconds=3.0))


def current_parent(snapshot: MarketSnapshot) -> dict[str, Any]:
    """Name the current observed EMA9 parent and its separate local child.

    A current confirmed transfer takes precedence over an old gap.  Historical
    same-side residence is otherwise useful parent evidence; EMA30 slope never
    chooses a trade.  Unauthenticated mission labels are not parent proof.
    """
    md = snapshot.metadata
    g = _map(md.get("current_geometry"))
    m = _map(md.get("mountain"))
    p = _map(m.get("parent_structure"))
    context = _map(md.get("mission_context"))
    mission = _map(context.get("parent"))
    source = _source(snapshot)
    mission_source = _num(mission.get("source_ms"))
    known = _num(mission.get("known_ms"))
    valid_mission = bool(source is not None and mission_source is not None
        and abs(source - mission_source) <= .001
        and context.get("current") is True and _num(context.get("source_ms")) == source
        and context.get("continuity_generation") == md.get("geometry_continuity_generation")
        and mission.get("status") == "ACTIVE" and known is not None and 0 <= known <= source
        and mission.get("invalidated") is not True
        and mission.get("continuity_generation") == md.get("geometry_continuity_generation"))
    history = directional_parent_evidence(snapshot)
    side = None
    identity = None
    basis = "UNKNOWN_PARENT"
    if valid_mission and mission.get("basis") == "CONFIRMED_RELEASE_TRANSFER":
        side, identity, basis = _side(mission.get("side")), mission.get("id"), "CURRENT_CONFIRMED_RELEASE_PARENT"
    elif history.get("qualified") is True:
        side = _side(history.get("side"))
        identity = (mission.get("id") if valid_mission and _side(mission.get("side")) is side
                    else p.get("parent_id") if _side(p.get("parent_side")) is side else None)
        if not identity:
            identity = f"RESIDENCE:{history.get('observed_residence_start_source_ms')}:{history.get('gap_side')}"
        basis = "OBSERVED_DIRECTIONAL_PARENT_HISTORY"
    elif valid_mission:
        side, identity, basis = _side(mission.get("side")), mission.get("id"), "CURRENT_SOURCE_BOUND_MISSION_PARENT"
    elif (g.get("arc_origin_observed") is True and g.get("arc_id")
          and _num(g.get("arc_age_sec")) is not None):
        side = _side(g.get("parent_direction")) or _side(p.get("parent_side"))
        identity = p.get("parent_id") or g.get("arc_id")
        basis = "CURRENT_OBSERVED_EMA9_PARENT"
    mission_origin = _num(mission.get("origin_ms")) if valid_mission and identity == mission.get("id") else None
    parent_age = ((source-mission_origin)/1000.0 if source is not None and mission_origin is not None
                  and mission_origin <= source else _num(p.get("parent_age_s")))
    return {"id": str(identity) if identity else None, "side": side.value if side else None,
        "basis": basis, "known": bool(identity and side), "source_ms": source,
        "supported": mission.get("supported") if valid_mission else None,
        "child_id": g.get("arc_id"), "child_side": (_side(g.get("arc_direction")).value
            if _side(g.get("arc_direction")) else None),
        "parent_age_s": parent_age,
        "comparison_envelope_age_s": _num(p.get("parent_age_s")),
        "parent_terminal": p.get("parent_terminal_ready") is True,
        "historical_direction_qualified": history.get("qualified") is True}


def _same_source(snapshot: MarketSnapshot, value: Any) -> bool:
    source, other = _source(snapshot), _num(value)
    return source is not None and other is not None and abs(source - other) <= .001


def _confirmed_opposite_release(snapshot: MarketSnapshot, side: Side) -> bool:
    md=snapshot.metadata
    m=_map(md.get("mountain"))
    release_side=_side(md.get("release_candidate_side"))
    confirmed=bool(md.get("release_confirmed_current") is True
        or _map(md.get("commander_strategy")).get("handoff_confirmed") is True)
    return bool(confirmed and release_side is not None and release_side is not side
        or m.get("strong_active_release") is True and _same_source(snapshot,m.get("source_ms"))
           and _side(m.get("owner_side")) is not None and _side(m.get("owner_side")) is not side)


def real_heist(snapshot: MarketSnapshot) -> tuple[bool, dict[str, Any]]:
    """Repeated observed bilateral walls, not a wide one-pass envelope."""
    h = _map(snapshot.metadata.get("heist"))
    proof = _map(h.get("repeatability_proof"))
    lower, upper, width = _num(h.get("lower")), _num(h.get("upper")), None
    if lower is not None and upper is not None:
        width = upper - lower
    counts = {key: _num(proof.get(key)) for key in ("lower_visits", "upper_visits", "center_traversals")}
    observations = proof.get("repeatability_visits")
    observations = observations if isinstance(observations, (list, tuple)) else ()
    end = _source(snapshot)
    actual = {zone: [] for zone in ("LOWER", "UPPER", "CENTER")}
    valid_times = True
    for observation in observations:
        row = _map(observation)
        stamp = _num(row.get("epoch_ms"))
        zone = str(row.get("zone") or "")
        if stamp is None or end is None or stamp > end:
            valid_times = False
        elif zone in actual:
            actual[zone].append(stamp)
    repeated = bool(all(counts[k] is not None and counts[k] >= 2 for k in counts)
        and all(len(set(actual[z])) >= 2 for z in actual))
    geometry = bool(proof.get("tight_box") is True and proof.get("heist_environment") is True
        and (proof.get("compression") is True or proof.get("parallel_emas") is True)
        and width is not None and width > 0)
    current = bool(_same_source(snapshot, proof.get("window_end_ms"))
        and proof.get("strict_source_times") is True and valid_times
        and proof.get("single_connection_epoch") is True
        and proof.get("connection_epoch") == _map(snapshot.metadata.get("current_geometry")).get("connection_epoch"))
    releasing = bool(_map(snapshot.metadata.get("mountain")).get("strong_active_release") is True
        or snapshot.metadata.get("release_in_progress") is True
        or snapshot.metadata.get("release_confirmed_current") is True
        or h.get("release_confirmed") is True)
    boundary_match = bool(lower == _num(proof.get("lower")) and upper == _num(proof.get("upper")))
    spot = _num(_map(snapshot.metadata.get("current_geometry")).get("btc_price"))
    tolerance = _num(proof.get("edge_tolerance"))
    inside = bool(spot is not None and tolerance is not None and tolerance > 0
        and lower is not None and upper is not None and lower-tolerance <= spot <= upper+tolerance)
    valid = bool(h.get("qualified_box") is True and repeated and geometry and current
        and boundary_match and inside and not releasing)
    return valid, {"box_id": h.get("box_id"), "visit_id": h.get("visit_id"),
        "lower": lower, "upper": upper, "width_btc": width,
        "lower_visits": counts["lower_visits"], "upper_visits": counts["upper_visits"],
        "center_traversals": counts["center_traversals"], "current_source": current,
        "repeated_both_walls": repeated, "compression_or_parallel": geometry,
        "current_boundary_match": boundary_match, "current_price_inside_bounded_range": inside,
        "current_zone": h.get("current_zone"), "release_active": releasing,
        "reason": ("REPEATED_CURRENT_BOUNDED_HEIST" if valid
                   else "OPPORTUNITY_DIRECTIONAL_RELEASE_CANCELS_HEIST_RETURN" if releasing
                   else "OPPORTUNITY_HEIST_REPEATED_BILATERAL_WALLS_REQUIRED")}


def _small_terminal_return(snapshot: MarketSnapshot, side: Side) -> tuple[bool, dict[str, Any]]:
    """Actual small terminal arc; old wide-box names cannot supply its proof.

    PID14156's lower return is preserved by the observed excursion and present
    6/9-second rebound, not by pretending that its one-visit box was repeated.
    The first still-falling observation fails this same predicate.
    """
    md = snapshot.metadata
    g, m, h = (_map(md.get(name)) for name in ("current_geometry", "mountain", "heist"))
    gap = _map(_map(md.get("ema9_ema30_cross_context")).get("gap_lifecycle"))
    p = _map(m.get("parent_structure"))
    sign = _sign(side)
    age = _num(g.get("arc_age_sec"))
    retreat, threshold = _num(m.get("retreat_dollars")), _num(m.get("retreat_threshold"))
    extreme_age = ((_source(snapshot) - float(m["edge_extreme_ms"])) / 1000.0
                   if _source(snapshot) is not None and _num(m.get("edge_extreme_ms")) is not None else None)
    values = [_num(g.get(k)) for k in ("btc_change6", "btc_change9", "ema9_change6")]
    same_gap = bool(_side(gap.get("current_side")) is side
        and gap.get("observed_side_residence_continuous") is True
        and (_num(gap.get("observed_side_residence_seconds")) or 0) >= 120.0)
    current_wall = bool(h.get("at_lower_edge") is True if side is Side.YES else h.get("at_upper_edge") is True)
    physical_return = bool(all(v is not None for v in values)
        and sign * values[0] >= 6.0 and sign * values[1] >= 6.0 and sign * values[2] >= 1.0)
    valid = bool(g.get("arc_origin_observed") is True and g.get("arc_id") == m.get("current_arc_id")
        and _same_source(snapshot, m.get("source_ms"))
        and _side(g.get("arc_direction")) is not side and _side(g.get("arc_direction")) is not None
        and age is not None and age >= 45.0 and extreme_age is not None and 0 <= extreme_age <= 90.0
        and retreat is not None and threshold is not None and threshold > 0 and retreat >= threshold
        and current_wall and same_gap and physical_return
        and p.get("slow_rolling_parent") is not True and m.get("strong_active_release") is not True
        and md.get("release_in_progress") is not True and md.get("release_confirmed_current") is not True)
    return valid, {"basis": "OBSERVED_SMALL_TERMINAL_ARC_RETURN", "arc_id": g.get("arc_id"),
        "arc_age_s": age, "extreme_age_s": extreme_age, "retreat_btc": retreat,
        "retreat_threshold_btc": threshold, "actual_current_wall": current_wall,
        "current_joint_return": physical_return, "same_observed_gap_side": same_gap}


def mountain_return(snapshot: MarketSnapshot, side: Side, intent: ToolIntent) -> tuple[bool, dict[str, Any]]:
    md = snapshot.metadata
    g, m = _map(md.get("current_geometry")), _map(md.get("mountain"))
    p = _map(m.get("parent_structure"))
    diagnostic = _map(m.get("diagnostics"))
    scale = _map(m.get("full_leg_scale_evidence"))
    completed = _map(m.get("completed_minute_parent_reference"))
    outgoing = _side(m.get("owner_side")) or _side(g.get("arc_direction"))
    evidence = _map(intent.metadata.get("commander_physical_evidence"))
    match = (_map(_map(md.get("historical_extreme_release")).get("recent_level_match"))
             or _map(evidence.get("recent_level_match")))
    # A level supplied by the candidate must still be a current defended level
    # at the same observed BTC price. A stale extreme cannot authorize itself.
    matched = bool(_side(match.get("side")) is side
        and _recent_level_return_location_ready(snapshot, match)
        and _counterparent_level_rejection_sustained(snapshot, side))
    sign = _sign(side)
    btc6, btc9, ema6 = (_num(g.get(k)) for k in ("btc_change6", "btc_change9", "ema9_change6"))
    turn = bool(btc6 is not None and btc9 is not None and ema6 is not None
        and sign * btc6 > 0 and sign * btc9 > 0 and sign * ema6 >= 0)
    defended_level = bool(matched and turn)
    age = _num(g.get("arc_age_sec"))
    extreme = _num(m.get("edge_extreme_ms"))
    source = _source(snapshot)
    extreme_age = (source - extreme) / 1000.0 if source is not None and extreme is not None else None
    p30 = _map(_map(m.get("current_motion")).get("30"))
    observed_30_return = bool(_same_source(snapshot, p30.get("source_ms"))
        and p30.get("covered") is True and p30.get("source_continuous") is True
        and (_num(p30.get("owner_price_rate_btc_s")) or 0.0) < 0
        and (_num(p30.get("owner_ema9_rate_btc_s")) or 0.0) <= 0)
    retreat, threshold = _num(m.get("retreat_dollars")), _num(m.get("retreat_threshold"))
    observed_smaller_terminal = bool(g.get("arc_origin_observed") is True
        and g.get("arc_id") == m.get("current_arc_id") and age is not None and age >= 45.0
        and extreme_age is not None and 15.0 <= extreme_age <= 90.0
        and retreat is not None and threshold is not None and threshold > 0 and retreat >= threshold
        and p.get("extended_parent") is True and observed_30_return and turn)
    comparison_mature = bool(diagnostic.get("mature_by_comparison") is True
        or diagnostic.get("mature_by_causal_turn") is True
        or diagnostic.get("mature_by_causal_hover") is True
        or _map(m.get("primary_collection_evidence")).get("comparable_current_leg_mature") is True
        or _map(_map(m.get("primary_collection_evidence")).get("retest_rejection")).get("qualified") is True
        or scale.get("qualified") is True and _same_source(snapshot, scale.get("source_ms"))
        or completed.get("mature_extension") is True and _same_source(snapshot, completed.get("source_ms")))
    terminal = bool(current_mountain_terminal(m) and comparison_mature
        and (m.get("stall") is True or m.get("hesitation") is True
             or m.get("failed_reextension") is True or m.get("meaningful_retreat") is True
             or m.get("comparable_slow_edge") is True))
    # The sovereign parent may be older than the current native child. Use
    # its authenticated completed-scale proof with actual current rejection;
    # do not demand that the child itself grow into a second mature parent.
    context = _map(md.get("mission_context"))
    mission_parent = _map(context.get("parent"))
    parent_edge = _map(mission_parent.get("entry_edge"))
    parent_evidence = _map(parent_edge.get("evidence"))
    parent_scale = _map(parent_evidence.get("full_leg_scale_evidence"))
    resolution = _map(parent_evidence.get("parent_resolution"))
    observed = _num(resolution.get("observed_parent_excursion_btc"))
    reference = _num(resolution.get("reference_range_btc"))
    parent_rejection = bool(qualified_full_arc_candidate(context,side,source)
        and parent_evidence.get("near_current_parent_extreme") is True
        and parent_scale.get("qualified") is True and _same_source(snapshot,parent_scale.get("source_ms"))
        and parent_scale.get("parent_id") == mission_parent.get("id")
        and parent_scale.get("side") == mission_parent.get("side")
        and _same_source(snapshot,resolution.get("source_ms"))
        and observed is not None and reference is not None and reference > 0 and observed >= .6*reference
        and turn and sign*btc6 >= 6.0 and sign*btc9 >= 6.0
        and retreat is not None and threshold is not None and threshold > 0 and retreat >= threshold)
    small, small_proof = _small_terminal_return(snapshot, side)
    known_edge = bool(outgoing is not None and outgoing is not side
        and _same_source(snapshot, m.get("source_ms")) and m.get("spent_edge") is not True)
    expanding_release = bool(m.get("strong_active_release") is True
        or md.get("release_in_progress") is True or md.get("release_confirmed_current") is True)
    # A fresh actual terminal/defended level may precede an EMA cosmetic flip;
    # a source-expanding release, however, cannot be faded by a generic scout.
    valid = bool(known_edge and not expanding_release
        and (terminal or parent_rejection or defended_level or observed_smaller_terminal or small))
    return valid, {"current_edge": known_edge, "outgoing_side": outgoing.value if outgoing else None,
        "parent_id": p.get("parent_id"), "child_arc_id": g.get("arc_id"),
        "current_terminal_with_comparable_maturity": terminal,
        "source_bound_parent_scale_with_current_rejection": parent_rejection,
        "defended_level_with_current_rejection": defended_level,
        "observed_smaller_terminal": observed_smaller_terminal,
        "validated_small_wall_return": small, "small_terminal_proof": small_proof if small else None,
        "current_30s_return": observed_30_return, "current_joint_short_return": turn,
        "arc_age_s": age, "extreme_age_s": extreme_age,
        "retreat_btc": retreat, "retreat_threshold_btc": threshold,
        "release_active": expanding_release,
        "reason": ("CURRENT_PHYSICAL_MOUNTAIN_RETURN" if valid
                   else "OPPORTUNITY_MOUNTAIN_PARENT_TERMINAL_PROOF_REQUIRED")}


def return_runway(snapshot: MarketSnapshot, side: Side, *, allow_local: bool) -> tuple[bool, dict[str, Any]]:
    """Separate a measurable local return from a claim to win settlement.

    A small genuine return may rent the path back toward current EMA9.  That
    target is frozen here, and its distance must fit the already observed
    excursion and actual current/prior return pace.  It receives no implied
    permission to hold an opposite contract to settlement.  Within the final
    five minutes the existing full TP/runway rule retains precedence.
    """
    md = snapshot.metadata
    m, tp, g = (_map(md.get(k)) for k in ("mountain", "tp_geometry", "current_geometry"))
    target, spot = _num(tp.get("target")),_num(g.get("btc_price"))
    if target is None or spot is None:
        return False,{"basis":"CURRENT_BTC_TARGET_REQUIRED"}
    actual_side = Side.YES if spot >= target else Side.NO
    actual_tp={**tp,"observed_target_side":actual_side.value,
               "required_move_to_target_btc":abs(target-spot),"signed_gap_btc":spot-target}
    settled, settlement = _return_settlement_feasible(snapshot, actual_tp, m, side)
    # The older helper's early UNKNOWN result is permission to keep observing,
    # not affirmative proof of an attainable full target.
    settled = bool(settled and settlement.get("basis") in
        {"PROVEN_RETURN_LEG_CAN_REACH_TP","RETURN_SIDE_TARGET_POSSESSION_ROBUST"})
    if settled:
        return True, {"target_kind": "CONTRACT_TARGET", "target_crossing_feasible":True,
            "settlement_ownership_claim": actual_side is side, **settlement}
    remaining = _num(tp.get("remaining_seconds"))
    if remaining is None:
        remaining = max(0.0,900-snapshot.contract_age_s)
    ask, bid, spot, e9, observed_range = (_num(x) for x in (
        snapshot.ask_for(side), snapshot.bid_for(side), g.get("btc_price"), g.get("ema9"), g.get("range180")))
    if (not allow_local or remaining <= 300 or any(x is None for x in (ask,bid,spot,e9,observed_range))
            or not 0 < bid <= ask <= .20 or not snapshot.quote_current or not snapshot.depth_available):
        return False, settlement
    distance = _sign(side)*(e9-spot)
    b6,b9 = _num(g.get("btc_change6")),_num(g.get("btc_change9"))
    if b6 is None or b9 is None or _sign(side)*b6 <= 0 or _sign(side)*b9 <= 0:
        return False, settlement
    speeds = [_sign(side)*b6/6.,_sign(side)*b9/9.]
    reference = _map(m.get("return_leg_reference"))
    historical_speed = _num(reference.get("median_speed_btc_s"))
    if historical_speed is not None and historical_speed > 0:
        speeds.append(historical_speed)
    pace = min(speeds)
    travel_s = distance/pace if pace > 0 else math.inf
    valid = bool(0 < distance <= observed_range and travel_s+60.0 < remaining)
    return valid, {"basis": "CURRENT_LOCAL_EMA9_RETURN_WITH_OBSERVED_PACE" if valid else "LOCAL_RETURN_RUNWAY_NOT_PROVEN",
        "target_kind": "TACTICAL_FROZEN_EMA9_CONTACT", "target_btc": e9, "source_ms": _source(snapshot),
        "remaining_distance_btc": distance, "observed_excursion_btc": observed_range,
        "conservative_observed_return_speed_btc_s": pace, "observed_pace_travel_seconds": travel_s,
        "remaining_seconds": remaining, "ask": ask, "bid": bid,
        "settlement_ownership_claim": False, "full_target_review": settlement,
        "future_price_or_fill_claim": False}


def _fresh_parent_value_start(snapshot: MarketSnapshot, side: Side) -> bool:
    """A current observed first leg after handoff, within existing start scale.

    This is a source-bound parent beginning, not a Rail label.  It keeps the
    45–150s observed start-leg scale already used by the renewed-flow route,
    adding systematic MAIN evaluation after the first five minutes.
    """
    g = _map(snapshot.metadata.get("current_geometry"))
    p = _map(_map(snapshot.metadata.get("mountain")).get("parent_structure"))
    age, p_age, spot, e9, r60 = (_num(x) for x in (g.get("arc_age_sec"),current_parent(snapshot).get("parent_age_s"),
        g.get("btc_price"),g.get("ema9"),g.get("range60")))
    if (not 300 <= snapshot.contract_age_s < 780 or not g.get("arc_origin_observed")
            or any(x is None for x in (age,p_age,spot,e9,r60)) or r60 <= 0
            or not 45 <= age <= 150 or not 0 < p_age <= 150
            or _side(g.get("arc_direction")) is not side or _side(g.get("parent_direction")) is not side
            or p.get("parent_terminal_ready") is True or abs(spot-e9) > .65*r60):
        return False
    motion = [_num(g.get(k)) for k in ("btc_change6","btc_change9","btc_change30","btc_change60",
                                       "ema9_change6","ema9_change30","ema9_change60")]
    return bool(all(x is not None and _sign(side)*x > 0 for x in motion)
        and _sign(side)*motion[0] >= max(2.,.12*r60))


def main_runway(snapshot: MarketSnapshot, side: Side) -> tuple[bool, dict[str, Any]]:
    """Current continuation pace is distinct from old opposite-return scale.

    A qualified located MAIN opportunity may use current observed 30/60s
    continuation pace and present TP ownership. It still needs the full target
    and settlement averaging time. This describes feasible distance/time, not
    a future-price prediction, guaranteed settlement or fabricated fill.
    """
    tp, g = _map(snapshot.metadata.get("tp_geometry")), _map(snapshot.metadata.get("current_geometry"))
    target, spot, remaining = (_num(v) for v in (tp.get("target"),g.get("btc_price"),tp.get("remaining_seconds")))
    if any(v is None for v in (target,spot,remaining)) or remaining <= 60:
        return False, {"basis": "CURRENT_BTC_TARGET_AND_SETTLEMENT_WINDOW_REQUIRED"}
    sign = _sign(side)
    distance = max(0.0,sign*(target-spot))
    actual_side = Side.YES if spot >= target else Side.NO
    target_proof = {"actual_target_side": actual_side.value, "target": target, "current_btc": spot,
        "remaining_move_btc": distance, "currently_beyond_target": actual_side is side,
        "descriptive_shape_side": tp.get("contract_ownership_side"),
        "shape_label_is_settlement_ownership": False}
    # Normalize the comparator's input to actual current distance. A shape
    # label cannot replace a still-required 100 BTC crossing late in a ticker.
    actual_tp = {**tp, "required_move_to_target_btc": abs(target-spot),
        "contract_ownership_side": actual_side.value,
        "observed_target_side": actual_side.value, "signed_gap_btc":spot-target,
        "contract_ownership": "STARTING_LEG_FAVORED" if actual_side is side else "TARGET_CROSSING_REQUIRED"}
    normalized = replace(snapshot, metadata={**snapshot.metadata,"tp_geometry":actual_tp})
    valid, prior = settlement_runway_for_side(normalized, side)
    if valid and prior.get("basis") in {"PROVEN_RETURN_LEG_CAN_REACH_TP","RETURN_SIDE_TARGET_POSSESSION_ROBUST"}:
        return True, {**prior, **target_proof}
    if actual_side is side:
        # Thin/fragile current possession cannot become robust just because
        # the remaining crossing distance is mathematically zero.
        return False,{**prior,**target_proof}
    changes = [_num(g.get(k)) for k in ("btc_change30","btc_change60","ema9_change30","ema9_change60")]
    if any(v is None for v in changes):
        return False, {**prior,**target_proof}
    if not all(sign*v > 0 for v in changes):
        return False, {**prior,**target_proof}
    pace = min(sign*changes[0]/30.0,sign*changes[1]/60.0)
    travel_s = distance/pace
    valid = bool(travel_s+60.0 <= remaining)
    return valid, {"basis": "CURRENT_PARENT_CONTINUATION_TARGET_RUNWAY" if valid else "CURRENT_PARENT_TARGET_TOO_FAR",
        "side": side.value, **target_proof,
        "observed_conservative_price_pace_btc_s": pace, "observed_pace_travel_seconds": travel_s,
        "settlement_average_window_seconds": 60.0, "remaining_seconds": remaining,
        "reference_return_review": prior, "future_settlement_guaranteed": False}


_OPENING_REASONS = frozenset({
    "COMMANDER_OBSERVED_INHERITED_PARENT_FIRST_MINUTE_CONTINUATION",
    "COMMANDER_OBSERVED_PREOPEN_EMA9_SPROUT_CONTINUATION",
    "COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION",
    "COMMANDER_MOUNTAIN_STARTING_LEG_OWNS_CONTRACT",
    "COMMANDER_MOUNTAIN_ROLLOVER_TARGET_REACHABLE",
    "COMMANDER_ROLLOVER_TERMINAL_RETURN_START",
})


def _opening(snapshot: MarketSnapshot, intent: ToolIntent) -> tuple[bool, dict[str, Any]]:
    evidence = _map(intent.metadata.get("commander_physical_evidence"))
    age = _num(snapshot.contract_age_s)
    m = _map(snapshot.metadata.get("mountain"))
    p = _map(m.get("parent_structure"))
    g = _map(snapshot.metadata.get("current_geometry"))
    if intent.reason not in _OPENING_REASONS or age is None or not 0 <= age <= 240 or intent.side is None:
        return False, {"reason": "NO_AUTHORIZED_OPENING_SPECIES"}
    matching = [candidate for candidate in physical_entry_candidates(snapshot)
                if candidate.reason == intent.reason and candidate.side is intent.side
                and candidate.opportunity_id == intent.opportunity_id
                and candidate.max_price == intent.max_price]
    if not matching:
        return False, {"reason": "CURRENT_OPENING_FACTORY_EVIDENCE_REQUIRED"}
    source = _source(snapshot)
    arc_start = _num(g.get("arc_start_ms"))
    arc_age = _num(g.get("arc_age_sec"))
    predated = bool(arc_start is not None and source is not None and arc_start < source-age*1000
        or arc_age is not None and arc_age > age+1)
    # The pre-open sprout uses its independently recorded pre-open BTC history,
    # since the currently recognized EMA9 child can be younger than the ticker.
    preopen_result = _preopen_observed_ema9_sprout_continuation(snapshot, directional_parent_evidence(snapshot))
    preopen = bool(intent.reason == "COMMANDER_OBSERVED_PREOPEN_EMA9_SPROUT_CONTINUATION"
        and preopen_result is not None and preopen_result[0] is intent.side)
    terminal_return = evidence.get("rollover_terminal_return") is True
    if terminal_return:
        valid, proof = mountain_return(snapshot, intent.side, intent)
        return bool(valid and predated and age <= 60), {"basis": "INHERITED_TERMINAL_RETURN", **proof}
    live, proof = _inherited_leg_still_live(snapshot, m, p, intent.side)
    tp = _map(snapshot.metadata.get("tp_geometry"))
    aligned_tp = _side(tp.get("contract_ownership_side")) is intent.side
    # The existing target-reachable species carries an actual physical
    # capacity calculation instead of asserting transferred TP ownership.
    capacity = _num(evidence.get("demonstrated_parent_capacity_btc"))
    required = _num(evidence.get("required_move_to_target_btc"))
    reachable = bool(required is not None and capacity is not None and 0 <= required <= .5*capacity)
    b30, e30 = _num(g.get("btc_change30")), _num(g.get("ema9_change30"))
    causal_flow = bool(b30 is not None and e30 is not None
        and _sign(intent.side)*b30 > 0 and _sign(intent.side)*e30 > 0)
    return bool((predated or preopen) and (live or preopen)
        and (aligned_tp or reachable) and not p.get("parent_terminal_ready")), {
        "basis": "AUTHORIZED_CAUSAL_ROLLOVER", "predates_contract": predated,
        "preopen_observed_sprout": preopen, "current_flow": causal_flow,
        "inherited_leg_live": proof, "target_agrees": aligned_tp, "target_reachable": reachable}


@dataclass
class ExcursionWatch:
    identity: str
    ticker: str
    generation: int
    parent_id: str
    parent_side: str
    return_side: str
    first_source_ms: float
    last_source_ms: float
    extreme_btc: float
    extreme_source_ms: float
    threshold_btc: float
    origin_child_id: str = ""
    opposite_child_id: str | None = None
    completed_return_observed: bool = False
    state: str = "PREPARE"
    reason: str = "PRONOUNCED_EXCURSION_RETURN_WATCH"
    distinct_source_samples: int = 1
    reextensions: int = 0
    max_retreat_btc: float = 0.0
    consumed: bool = False


class OpportunityBook:
    """Finite physical memory; only OneCommander calls admission/consumption."""

    def __init__(self, *, opening_value_watch: Any = None) -> None:
        self._opening_value_watch = opening_value_watch
        self._frame: tuple[Any, ...] | None = None
        self._physical_frame: tuple[Any, ...] | None = None
        self._watches: dict[tuple[Any, ...], ExcursionWatch] = {}
        self._active: dict[tuple[Any, ...], ExcursionWatch] = {}
        self._history: deque[dict[str, Any]] = deque(maxlen=180)
        self._proposals: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._latest: dict[str, Any] = {}
        self._main_identity: tuple[Any, ...] | None = None
        self._main_dip: dict[str, Any] | None = None
        self._main_high: float | None = None
        self._consumed_main: set[str] = set()
        self._consumed_opportunities: set[str] = set()

    @property
    def review(self) -> dict[str, Any]:
        if not self._latest:
            return {"revision": REVISION, "state": "NOT_EVALUATED", "execution_authority": "ONE_COMMANDER"}
        return _json_safe({**self._latest, "candidates": [dict(v) for v in self._proposals.values()],
            "watches": [self._watch_summary(w) for w in list(self._watches.values())[-8:]]})

    @staticmethod
    def _key(intent: ToolIntent) -> tuple[Any, ...]:
        return (intent.tool, intent.reason, intent.opportunity_id, intent.side.value if intent.side else None)

    @staticmethod
    def _watch_summary(w: ExcursionWatch) -> dict[str, Any]:
        return {key: getattr(w, key) for key in w.__dataclass_fields__}

    def observe(self, snapshot: MarketSnapshot) -> None:
        md = snapshot.metadata
        source = _source(snapshot)
        parent = current_parent(snapshot)
        frame = (snapshot.ticker, source, md.get("geometry_continuity_generation"), snapshot.now_ts,
                 snapshot.yes_ask, snapshot.no_ask, md.get("quote_id"))
        if frame == self._frame:
            return
        self._frame = frame
        self._proposals = {}
        age = _num(snapshot.contract_age_s) or 0.0
        side = _side(parent.get("side"))
        tp = _map(md.get("tp_geometry"))
        spot = _num(_map(md.get("current_geometry")).get("btc_price"))
        target = _num(tp.get("target"))
        actual_target_side = ((Side.YES if spot >= target else Side.NO).value
            if spot is not None and target is not None else None)
        cadence = ("OPENING_OBSERVATION" if age < 60 else "EXCURSION_OBSERVATION" if age < 300
                   else "MAIN_VALUE_SEARCH" if age < 450 else "SECOND_HALF_ALIGNMENT_REVIEW" if age < 780
                   else "FINAL_RUNWAY_REVIEW")
        ask = _num(snapshot.ask_for(side)) if side else None
        main_reason = ("SOURCE_NOT_CURRENT" if not _current(snapshot) else "EMA9_PARENT_UNKNOWN" if not side
                       else "TP_EMA_JUNCTION" if tp.get("target_between_ema9_ema30") is True
                       else "MAIN_NORMAL_SEARCH_BEGINS_AFTER_300S" if age < 300
                       else "MAIN_ASK_ABOVE_REGULAR_VALUE" if ask is not None and ask > .35
                       else "WAIT_FOR_PHYSICAL_VALUE_REJOIN")
        self._latest = {"revision": REVISION, "ticker": snapshot.ticker, "source_ms": source,
            "continuity_generation": md.get("geometry_continuity_generation"), "observed_at": snapshot.now_ts,
            "state": "WAIT", "cadence": cadence, "parent": parent,
            "main_alignment": {"parent_side": parent.get("side"), "parent_id": parent.get("id"),
                "target_side": actual_target_side, "observed_target_side": actual_target_side,
                "descriptive_shape_side": tp.get("contract_ownership_side"),
                "target": _num(tp.get("target")), "required_move_btc": _num(tp.get("required_move_to_target_btc")),
                "remaining_seconds": _num(tp.get("remaining_seconds")) or max(0.0, 900-age),
                "ask": ask, "regular_value_ceiling": .35, "reason": main_reason,
                "qualified": False, "entry_required": False},
            "execution_authority": "ONE_COMMANDER", "outcome_input": False}
        physical_frame = (snapshot.ticker, source, md.get("geometry_continuity_generation"))
        if not _current(snapshot):
            for watch in self._active.values():
                watch.state, watch.reason = "WAIT", "SOURCE_CONTINUITY_NOT_CURRENT"
            self._main_dip = None
            return
        if physical_frame == self._physical_frame:
            return
        previous_frame = self._physical_frame
        self._physical_frame = physical_frame
        if previous_frame is not None and (physical_frame[2] != previous_frame[2]
                or source is not None and previous_frame[1] is not None and source < previous_frame[1]):
            for watch in self._active.values():
                watch.state, watch.reason = "WAIT", "SOURCE_CONTINUITY_CHANGED"
            self._active.clear()
            self._history.clear()
            self._main_dip = None
        g, m = _map(md.get("current_geometry")), _map(md.get("mountain"))
        btc = _num(g.get("btc_price"))
        if source is None or btc is None:
            return
        self._history.append({"source_ms": source, "btc": btc, "ema9": _num(g.get("ema9")),
            "ticker": snapshot.ticker, "parent_id": parent.get("id")})
        self._observe_main(snapshot, parent, btc, source)
        outgoing = _side(m.get("owner_side")) or _side(g.get("arc_direction"))
        p = _map(m.get("parent_structure"))
        parent_id = str(parent.get("id") or p.get("parent_id") or "")
        extreme = _num(m.get("owner_extreme_btc"))
        extreme_ms = _num(m.get("edge_extreme_ms"))
        amplitude = _num(g.get("arc_amplitude"))
        prominence = _num(g.get("arc_prominence_threshold")) or _num(g.get("arc_birth_prominence_threshold"))
        threshold = _num(m.get("retreat_threshold")) or prominence
        pronounced = bool(outgoing and parent_id and extreme is not None and extreme_ms is not None
            and extreme_ms <= source and threshold is not None and threshold > 0
            and amplitude is not None and prominence is not None and amplitude >= prominence
            and g.get("arc_origin_observed") is True)
        for key, watch in list(self._active.items()):
            if watch.ticker != snapshot.ticker or watch.generation != physical_frame[2] or watch.parent_id != parent_id:
                watch.state, watch.reason = "WAIT", "CONTRACT_OR_PARENT_CHANGED"
                del self._active[key]
                continue
            child_side = _side(g.get("arc_direction"))
            retreat = _sign(Side(watch.parent_side))*(watch.extreme_btc-btc)
            if (child_side is not None and child_side.value == watch.return_side
                    and g.get("arc_origin_observed") is True
                    and g.get("arc_id") and g.get("arc_id") != watch.origin_child_id
                    and retreat >= watch.threshold_btc):
                watch.completed_return_observed = True
                watch.opposite_child_id = str(g["arc_id"])
        if not pronounced:
            return
        key = (snapshot.ticker, physical_frame[2], parent_id, outgoing.value)
        watch = self._active.get(key)
        sign = _sign(outgoing)
        new_physical_excursion = bool(watch is not None and watch.completed_return_observed
            and g.get("arc_id") not in {watch.origin_child_id,watch.opposite_child_id}
            and _side(g.get("arc_direction")) is outgoing
            and g.get("arc_origin_observed") is True
            and _num(g.get("arc_start_ms")) is not None
            and float(g["arc_start_ms"]) > watch.first_source_ms)
        if new_physical_excursion:
            watch.state, watch.reason = "WAIT", "RETURN_COMPLETED_NEW_PHYSICAL_EXCURSION"
            watch = None
        if watch is None:
            identity = f"EXCURSION:{snapshot.ticker}:{physical_frame[2]}:{parent_id}:{outgoing.value}:{int(extreme_ms)}"
            watch = ExcursionWatch(identity, snapshot.ticker, physical_frame[2], parent_id,
                outgoing.value, (Side.NO if outgoing is Side.YES else Side.YES).value,
                source, source, extreme, extreme_ms, threshold, origin_child_id=str(g.get("arc_id") or ""))
            self._active[key] = watch
            self._watches[(identity,)] = watch
            if len(self._watches) > 32:
                del self._watches[next(iter(self._watches))]
        else:
            watch.distinct_source_samples += 1
            watch.last_source_ms = source
            outward = sign*(extreme-watch.extreme_btc)
            if outward > 0:
                # The old watch is cancelled/reset on re-extension. Its stable
                # identity stays consumed after a fill; a fresh timestamp or
                # another callback cannot manufacture a new paid opportunity.
                watch.extreme_btc, watch.extreme_source_ms = extreme, extreme_ms
                watch.max_retreat_btc = 0.0
                watch.reextensions += 1
                watch.state = "WAIT" if watch.consumed else "PREPARE"
                watch.reason = "SAME_PARENT_REEXTENSION_CANCELLED_PRIOR_RETURN"
            watch.max_retreat_btc = max(watch.max_retreat_btc, sign*(watch.extreme_btc-btc))
        release = bool(m.get("strong_active_release") is True or md.get("release_in_progress") is True)
        if release:
            watch.state, watch.reason = "WAIT", "DIRECTIONAL_BREAKOUT_CANCELLED_COUNTERWATCH"
        elif not watch.consumed:
            watch.state = "PREPARE"
            self._latest["state"] = "PREPARE"

    def _observe_main(self, snapshot: MarketSnapshot, parent: Mapping[str, Any], btc: float, source: float) -> None:
        side = _side(parent.get("side"))
        identity = (snapshot.ticker, snapshot.metadata.get("geometry_continuity_generation"), parent.get("id"), parent.get("side"))
        if identity != self._main_identity or side is None:
            self._main_identity, self._main_dip = identity, None
            self._main_high = _sign(side)*btc if side else None
        if side is None:
            return
        price = _sign(side)*btc
        g = _map(snapshot.metadata.get("current_geometry"))
        threshold = max(2.0, .12*(_num(g.get("range60")) or 0.0))
        if self._main_high is None:
            self._main_high = price
        if price >= self._main_high:
            self._main_high = price
            # Once the original outward high is recovered, that value window
            # is spent even when its earlier ask was too expensive to fill.
            # A later cheap quote cannot revive the old dip in mid-leg.
            if self._main_dip:
                self._main_dip = None
        if self._main_high-price >= threshold:
            if self._main_dip is None:
                self._main_dip = {"id": f"REJOIN:{snapshot.ticker}:{identity[1]}:{parent.get('id')}:{int(source)}",
                    "start_source_ms": source, "low": price, "depth_btc": self._main_high-price,
                    "threshold_btc": threshold, "consumed": False}
            else:
                self._main_dip["low"] = min(self._main_dip["low"], price)
                self._main_dip["depth_btc"] = max(self._main_dip["depth_btc"], self._main_high-price)

    def main_candidate(self, snapshot: MarketSnapshot) -> ToolIntent | None:
        """After five minutes, rejoin a measured current-parent value dip."""
        self.observe(snapshot)
        if not _current(snapshot) or not 300.0 <= snapshot.contract_age_s < 780.0:
            return None
        parent = current_parent(snapshot)
        side = _side(parent.get("side"))
        dip = self._main_dip
        if side is None:
            return None
        fresh_start = _fresh_parent_value_start(snapshot, side)
        fresh_identity = f"PARENT_START:{snapshot.ticker}:{snapshot.metadata.get('geometry_continuity_generation')}:{parent.get('id')}"
        if fresh_start and fresh_identity in self._consumed_main:
            fresh_start = False
        valid_dip = bool(dip and not dip.get("consumed") and dip["id"] not in self._consumed_main)
        if not valid_dip and not fresh_start:
            return None
        md = snapshot.metadata
        g, m, tp = (_map(md.get(k)) for k in ("current_geometry", "mountain", "tp_geometry"))
        if (parent.get("parent_terminal") or current_mountain_terminal(m)
                or _confirmed_opposite_release(snapshot,side) or tp.get("target_between_ema9_ema30") is True
                or _num(tp.get("target")) is None):
            return None
        ask, btc, e9, r60 = (_num(v) for v in (snapshot.ask_for(side), g.get("btc_price"), g.get("ema9"), g.get("range60")))
        values = [_num(g.get(k)) for k in ("btc_change6", "btc_change9", "ema9_change6", "ema9_change30")]
        if any(v is None for v in (ask, btc, e9, r60, *values)):
            return None
        sign = _sign(side)
        if (not 0 < ask <= .35 or r60 <= 0 or abs(btc-e9) > .65*r60
                or sign*values[0] < max(2.0, .12*r60) or sign*values[1] <= 0
                or sign*values[2] <= 0 or sign*values[3] <= 0
                or not fresh_start and (sign*btc-dip["low"] < dip["threshold_btc"]
                    or (_source(snapshot) or 0) <= dip["start_source_ms"])):
            return None
        runway, proof = main_runway(snapshot, side)
        if not runway:
            self._latest["main_alignment"]["reason"] = "MAIN_REJOIN_TARGET_RUNWAY_NOT_PROVEN"
            return None
        return _candidate(snapshot, family="MOUNTAIN_CONTRACT_LEG", side=side,
            max_price=.35, reason="COMMANDER_OPPORTUNITY_MAIN_EMA9_VALUE_REJOIN",
            size_override=10.0, evidence={"identity": fresh_identity if fresh_start else dip["id"],
                "entry_location": "OBSERVED_CURRENT_PARENT_VALUE_START" if fresh_start else "OBSERVED_PARENT_PULLBACK_REJOIN",
                "parent_id": parent["id"], "parent_side": side.value, "child_arc_id": g.get("arc_id"),
                "dip_start_source_ms": dip["start_source_ms"] if valid_dip else None,
                "dip_depth_btc": dip["depth_btc"] if valid_dip else None,
                "dip_threshold_btc": dip["threshold_btc"] if valid_dip else None,
                "return_from_dip_btc": sign*btc-dip["low"] if valid_dip else None,
                "current_source_ms": _source(snapshot), "return_runway": proof,
                "no_clock_only_entry": True, "no_generic_midleg_chase": True})

    def qualify(self, intent: ToolIntent, snapshot: MarketSnapshot, *, confirmed_release: bool = False) -> dict[str, Any]:
        self.observe(snapshot)
        key = self._key(intent)
        side = intent.side
        parent = current_parent(snapshot)
        tp = _map(snapshot.metadata.get("tp_geometry"))
        proof: dict[str, Any] = {"revision": REVISION, "qualified": False, "species": None,
            "tool": intent.tool, "candidate_reason": intent.reason, "opportunity_id": intent.opportunity_id,
            "side": side.value if side else None, "parent_id": parent.get("id"),
            "parent_side": parent.get("side"), "child_id": parent.get("child_id"),
            "ticker": snapshot.ticker, "source_ms": _source(snapshot),
            "continuity_generation": snapshot.metadata.get("geometry_continuity_generation"),
            "contract_age_s": snapshot.contract_age_s,
            "remaining_seconds": _num(tp.get("remaining_seconds")) or max(0.0,900-snapshot.contract_age_s),
            "target": _num(tp.get("target")), "required_move_btc": _num(tp.get("required_move_to_target_btc")),
            "bid": snapshot.bid_for(side) if side else None, "ask": snapshot.ask_for(side) if side else None,
            "depth_available": snapshot.depth_available, "price_limit": intent.max_price,
            "size_tier": intent.size_tier, "reason": "OPPORTUNITY_NO_POSITIVE_SPECIES"}

        def finish(reason: str, *, species: str | None = None, valid: bool = False, evidence: Any = None) -> dict[str, Any]:
            proof.update(reason=reason, species=species, qualified=valid, evidence=evidence or {})
            watch = self._watch_for(snapshot, side)
            identity = None
            if watch is not None and species == "MOUNTAIN_RETURN":
                proof["watch_id"] = watch.identity
                proof["watch_state"] = watch.state
                identity = watch.identity
                if watch.consumed:
                    proof.update(qualified=False, reason="OPPORTUNITY_PHYSICAL_EXCURSION_ALREADY_FILLED")
            if species == "REAL_HEIST_RETURN":
                heist = _map(snapshot.metadata.get("heist"))
                visit = heist.get("visit_id") or intent.metadata.get("visit_id")
                if visit:
                    identity = f"HEIST:{snapshot.ticker}:{proof['continuity_generation']}:{side.value}:{visit}"
            elif species == "MAIN_EMA9_REJOIN":
                e = _map(intent.metadata.get("commander_physical_evidence"))
                if _fresh_parent_value_start(snapshot, side):
                    identity = f"PARENT_START:{snapshot.ticker}:{proof['continuity_generation']}:{parent.get('id')}"
                elif self._main_dip and e.get("identity") == self._main_dip.get("id"):
                    identity = self._main_dip["id"]
                else:
                    identity = f"PARENT_REJOIN:{snapshot.ticker}:{proof['continuity_generation']}:{parent.get('id')}:{parent.get('child_id')}"
            elif species in {"ALREADY_AUTHORIZED_ROLLOVER","RELEASE_HANDOFF"}:
                identity = f"{species}:{snapshot.ticker}:{proof['continuity_generation']}:{parent.get('id')}:{side.value}"
            if identity:
                proof["physical_opportunity_id"] = identity
                if identity in self._consumed_opportunities:
                    proof.update(qualified=False, reason="OPPORTUNITY_PHYSICAL_EXCURSION_ALREADY_FILLED")
            self._proposals[key] = proof
            if proof["qualified"] and species in {"MAIN_EMA9_REJOIN", "ALREADY_AUTHORIZED_ROLLOVER", "RELEASE_HANDOFF"}:
                self._latest["main_alignment"].update(qualified=True, reason="QUALIFIED_ALIGNED_OPPORTUNITY",
                    species=species, opportunity_id=intent.opportunity_id)
            return dict(proof)

        if intent.action not in (Action.ENTER, Action.RELAY) or side is None:
            return finish("OPPORTUNITY_NOT_AN_ENTRY")
        if not _current(snapshot):
            return finish("OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED")
        intent_age = snapshot.now_ts-intent.source_time
        if not math.isfinite(intent_age) or intent_age > 3 or intent_age < -2:
            return finish("OPPORTUNITY_CURRENT_CANDIDATE_SOURCE_REQUIRED")
        if tp.get("target_between_ema9_ema30") is True:
            return finish("OPPORTUNITY_TP_EMA_JUNCTION_WAIT")
        if _num(tp.get("target")) is None or proof["remaining_seconds"] <= 0:
            return finish("OPPORTUNITY_CURRENT_TARGET_AND_RUNWAY_REQUIRED")
        if confirmed_release:
            # The confirmed handoff is already the controller's measured
            # boundary-break + residence transfer, not an EMA crossover.
            strategy = _map(snapshot.metadata.get("commander_strategy"))
            release = _map(intent.metadata.get("release_entry_proof"))
            observed_at = _num(release.get("observed_at"))
            release_current = bool(observed_at is not None and _source(snapshot) is not None
                and abs(observed_at*1000.0-_source(snapshot)) <= 1.0)
            transfer = bool(release.get("qualified") is True
                and release.get("boundary_break") is True and release.get("directional_expansion") is True
                and (release.get("new_side_residence") is True or release.get("old_owner_failed_reextension") is True)
                and _side(release.get("candidate_side")) is side)
            runway, runway_proof = main_runway(snapshot,side)
            if (strategy.get("handoff_confirmed") is True
                    and _side(snapshot.metadata.get("release_candidate_side")) is side
                    and release_current and transfer and runway):
                return finish("CURRENT_CONFIRMED_RELEASE_HANDOFF", species="RELEASE_HANDOFF", valid=True,
                    evidence={"controller_handoff_confirmed": True, "candidate_side": side.value,
                              "release_entry_proof": dict(release), "target_runway":runway_proof})
            return finish("OPPORTUNITY_CURRENT_MEASURED_RELEASE_TRANSFER_REQUIRED", species="RELEASE_HANDOFF",
                evidence={"current_release_source":release_current,"measured_transfer":transfer,"target_runway":runway_proof})
        opening, opening_proof = _opening(snapshot, intent)
        if opening:
            return finish("CURRENT_AUTHORIZED_ROLLOVER", species="ALREADY_AUTHORIZED_ROLLOVER", valid=True,
                          evidence=opening_proof)
        # One current, previously earned opening watch is shared across its
        # Commander and equivalent Rail descriptions. The watch rechecks its
        # original inherited parent, exact source, value cap and present turn.
        # A reason string, saved candidate or ordinary early Rail cannot arm it.
        opening_value = (self._opening_value_watch.candidate(snapshot)
                         if self._opening_value_watch is not None else None)
        if (opening_value is not None and opening_value.side is side
                and (intent.reason == "COMMANDER_OPENING_RAIL_DIP_VALUE_REJOIN"
                     or intent.tool == "RAIL" and intent.reason in {"RAIL_MAIN_VALUE","RAIL_EMA9_DIP_VALUE"})
                and self._opening_value_watch.entry_denial(intent,snapshot) is None):
            runway, runway_proof = main_runway(snapshot,side)
            if runway:
                return finish("CURRENT_AUTHORIZED_OPENING_VALUE_REJOIN", species="MAIN_EMA9_REJOIN",valid=True,
                    evidence={"opening_value_watch":dict(_map(opening_value.metadata.get("commander_physical_evidence"))),
                              "return_runway":runway_proof})
        if snapshot.contract_age_s < 60:
            return finish("OPPORTUNITY_FIRST_MINUTE_WAIT_EARNED_EXCEPTION_REQUIRED")
        family = str(intent.metadata.get("commander_candidate_family") or "")
        return_family = family in {"MOUNTAIN_EDGE", "HISTORICAL_EXTREME_RELEASE_PREP", "EDGE_HEIST", "QUOTE_WAVE_SCALP"}
        heist_family = intent.tool == "MARKET_HEIST" or family in {"EDGE_HEIST", "QUOTE_WAVE_SCALP"}
        if heist_family:
            real, box = real_heist(snapshot)
            h = _map(snapshot.metadata.get("heist"))
            geometry=_map(snapshot.metadata.get("current_geometry"))
            btc=_num(geometry.get("btc_price"))
            lower,upper,tolerance=(_num(v) for v in (h.get("lower"),h.get("upper"),
                _map(h.get("repeatability_proof")).get("edge_tolerance")))
            physical_edge=bool(all(v is not None for v in (btc,lower,upper,tolerance))
                and (btc<=lower+tolerance if side is Side.YES else btc>=upper-tolerance))
            outer = bool(physical_edge and (h.get("at_lower_edge") is True if side is Side.YES else h.get("at_upper_edge") is True))
            parallel = _map(intent.metadata.get("parallel_return_evidence"))
            b6,e6=_num(geometry.get("btc_change6")),_num(geometry.get("ema9_change6"))
            returning_visit = bool(intent.metadata.get("parallel_return_entry") is True
                and h.get("current_zone") == "INNER" and intent.metadata.get("visit_id")
                and _same_source(snapshot,parallel.get("source_ms"))
                and parallel.get("armed_zone") == ("LOWER" if side is Side.YES else "UPPER")
                and parallel.get("return_confirmed") is True and parallel.get("current_zone") == "INNER"
                and b6 is not None and e6 is not None and _sign(side)*b6>0 and _sign(side)*e6>=0
                and _num(parallel.get("btc_change6")) == b6 and _num(parallel.get("ema9_change6")) == e6)
            if real and (outer or returning_visit):
                current_visit = h.get("visit_id")
                intent_visit = intent.metadata.get("visit_id")
                if current_visit and intent_visit and current_visit != intent_visit:
                    return finish("OPPORTUNITY_CURRENT_PHYSICAL_HEIST_VISIT_REQUIRED", species="REAL_HEIST_RETURN", evidence=box)
                return finish("CURRENT_REPEATED_HEIST_RETURN", species="REAL_HEIST_RETURN", valid=True, evidence=box)
            small, small_proof = _small_terminal_return(snapshot, side)
            if small:
                runway, runway_proof = return_runway(snapshot, side, allow_local=True)
                if runway:
                    return finish("CURRENT_VALIDATED_SMALL_TERMINAL_RETURN", species="MOUNTAIN_RETURN", valid=True,
                        evidence={**small_proof, "heist_qualified": False, "return_runway": runway_proof})
            # A Mountain-edge quote species may have genuine parent terminal
            # proof even though it is not a repeated Heist.
            if not return_family:
                return finish(box["reason"], species="REAL_HEIST_RETURN", evidence=box)
        if return_family or (family == "MOUNTAIN_CONTRACT_LEG"
                and _map(intent.metadata.get("commander_physical_evidence")).get("terminal") is True):
            earned, edge = mountain_return(snapshot, side, intent)
            if not earned:
                return finish(edge["reason"], species="MOUNTAIN_RETURN", evidence=edge)
            runway, runway_proof = return_runway(snapshot, side, allow_local=True)
            if not runway:
                return finish("OPPORTUNITY_RETURN_TARGET_RUNWAY_NOT_PROVEN", species="MOUNTAIN_RETURN",
                    evidence={**edge, "return_runway": runway_proof})
            return finish("CURRENT_PHYSICAL_MOUNTAIN_RETURN", species="MOUNTAIN_RETURN", valid=True,
                evidence={**edge, "return_runway": runway_proof})
        if family == "MOUNTAIN_CONTRACT_LEG" or intent.tool == "RAIL":
            g, m = _map(snapshot.metadata.get("current_geometry")), _map(snapshot.metadata.get("mountain"))
            if parent.get("side") != side.value or parent.get("parent_terminal"):
                return finish("OPPORTUNITY_MAIN_CURRENT_EMA9_PARENT_REQUIRED", species="MAIN_EMA9_REJOIN")
            evidence = _map(intent.metadata.get("commander_physical_evidence"))
            if snapshot.contract_age_s < 300 and intent.reason != "COMMANDER_OPENING_RAIL_DIP_VALUE_REJOIN":
                return finish("OPPORTUNITY_MAIN_OBSERVE_UNTIL_300S", species="MAIN_EMA9_REJOIN")
            # Located existing pullback/rejoin routes retain their measured
            # predicates. RAIL_MAIN_VALUE cannot use a label + cheap ask alone.
            renewed = _current_ema9_renewed_flow_rejoin(snapshot)
            native_locations = {"PERSISTENT_PARENT_SHALLOW_CHILD_REJOIN", "PERSISTENT_GAP_CHILD_TERMINAL"}
            current_native_location = bool(evidence.get("entry_location") in native_locations
                and any(c.side is side and c.reason == intent.reason
                    and _map(c.metadata.get("commander_physical_evidence")).get("entry_location") == evidence.get("entry_location")
                    for c in physical_entry_candidates(snapshot)))
            measured_main = self.main_candidate(snapshot)
            measured_dip_location = bool(measured_main is not None and measured_main.side is side)
            known_location = bool(renewed is not None and renewed[0] is side
                or _fresh_parent_value_start(snapshot, side)
                or measured_dip_location or current_native_location
                or intent.reason == "COMMANDER_OPENING_RAIL_DIP_VALUE_REJOIN")
            if not known_location:
                return finish("OPPORTUNITY_MAIN_PHYSICAL_VALUE_REJOIN_REQUIRED", species="MAIN_EMA9_REJOIN")
            runway, runway_proof = main_runway(snapshot, side)
            if not runway:
                return finish("OPPORTUNITY_MAIN_TARGET_RUNWAY_NOT_PROVEN", species="MAIN_EMA9_REJOIN", evidence=runway_proof)
            return finish("CURRENT_EMA9_PARENT_VALUE_REJOIN", species="MAIN_EMA9_REJOIN", valid=True,
                          evidence={"location": evidence.get("entry_location"), "return_runway": runway_proof})
        return finish("OPPORTUNITY_NO_POSITIVE_SPECIES")

    def _watch_for(self, snapshot: MarketSnapshot, side: Side | None) -> ExcursionWatch | None:
        for watch in reversed(list(self._active.values())):
            if watch.ticker == snapshot.ticker and side is not None and watch.return_side == side.value:
                return watch
        return None

    def annotate(self, intent: ToolIntent, snapshot: MarketSnapshot, *, confirmed_release: bool = False) -> ToolIntent:
        proof = self.qualify(intent, snapshot, confirmed_release=confirmed_release)
        return replace(intent, metadata={**intent.metadata, "commander_opportunity": proof})

    def result(self, snapshot: MarketSnapshot, decision: Any, positions: Mapping[str, Any] | None = None) -> None:
        self.observe(snapshot)
        self._latest["decision"] = {"action": decision.action.value, "reason": decision.reason,
            "opportunity_id": decision.intent.opportunity_id if decision.intent else None}
        if decision.action in (Action.ENTER, Action.RELAY):
            self._latest["state"] = "ENTER"
            watch = self._watch_for(snapshot, decision.intent.side if decision.intent else None)
            if watch and not watch.consumed:
                watch.state, watch.reason = "ENTER", "COMMANDER_ADMITTED_PENDING_EXECUTION"
        if positions:
            side = self._latest["main_alignment"].get("parent_side")
            aligned = any((p.get("ticker") if isinstance(p, Mapping) else getattr(p,"ticker",None)) == snapshot.ticker
                and _side(p.get("side") if isinstance(p,Mapping) else getattr(p,"side",None)) is _side(side)
                for p in positions.values()) if side else False
            self._latest["main_alignment"]["aligned_position_already_held"] = aligned
            if aligned:
                self._latest["main_alignment"]["reason"] = "CURRENT_ALIGNED_LOT_ALREADY_HELD"
        if self._latest["main_alignment"].get("qualified") and decision.action is Action.WAIT:
            self._latest["main_alignment"]["missed_opportunity_reason"] = decision.reason

    def consume(self, intent: ToolIntent, *, ticker: str) -> None:
        proof = _map(intent.metadata.get("commander_opportunity"))
        physical_identity = proof.get("physical_opportunity_id")
        if isinstance(physical_identity,str) and proof.get("ticker") == ticker:
            self._consumed_opportunities.add(physical_identity)
        watch_id = proof.get("watch_id")
        for watch in self._watches.values():
            if watch.ticker == ticker and watch.identity == watch_id:
                watch.consumed, watch.state, watch.reason = True, "FILLED", "PHYSICAL_EXCURSION_BOOKED_ONCE"
        evidence = _map(intent.metadata.get("commander_physical_evidence"))
        identity = evidence.get("identity")
        if isinstance(identity,str) and identity.startswith("PARENT_START:"):
            self._consumed_main.add(identity)
        if self._main_dip and identity == self._main_dip["id"] and ticker == self._main_identity[0]:
            self._main_dip["consumed"] = True
            self._consumed_main.add(str(identity))

