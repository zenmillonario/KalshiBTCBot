"""Shared intent construction for tool-owned position management.

These helpers do not select a strategy, place an order, or apply quote safety.
The active tool supplies its structural HOLD/EXIT; Commander and the PAPER
executor retain objective safety and exact-contract execution authority.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from decimal import Decimal
import math
from typing import Any, Mapping

from strategy_core.mission_scopes import qualified_full_arc_candidate
from strategy_core.position_roles import position_role
from strategy_core.source_freshness import current_source_is_fresh, source_receipt_is_fresh
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


def as_side(value: Any) -> Side | None:
    if isinstance(value, Side):
        return value
    try:
        return Side(str(value).upper())
    except ValueError:
        return None


def number(value: Any) -> float | None:
    try:
        result = float(value) if value is not None and not isinstance(value, bool) else None
        return result if result is not None and math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def entry_metadata(position: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = position.get("entry_metadata") or {}
    return raw if isinstance(raw, Mapping) else {}


def rack_context(snapshot: MarketSnapshot) -> Mapping[str, Any]:
    raw = snapshot.metadata.get("tool_rack") or {}
    return raw if isinstance(raw, Mapping) else {}


def opposing_transfer(position: Mapping[str, Any], snapshot: MarketSnapshot) -> bool:
    side = as_side(position.get("side"))
    release_side = as_side(rack_context(snapshot).get("confirmed_release_side"))
    opposite = side is not None and release_side is not None and side is not release_side
    if not opposite:
        return False
    mission = mapping(entry_metadata(position).get("mission"))
    if mission.get("purpose") != "ARC_RETURN":
        return True
    # A blind return is bought while the outgoing side may still be releasing.
    # That old release is not a reversal of the incoming, not-yet-observed leg.
    # Its genuine frozen-boundary failure has Mountain's separate persistent
    # failure path. Once the held parent actually finishes, its exact completed
    # scope may authorize an opposing transfer under any custody tool.
    scoped = mission_collection_evidence(position, snapshot)
    return bool(scoped["current"] and scoped["scope_status"] == "COMPLETED"
        and scoped["terminal_qualified"] and scoped["collection_qualified"])


def mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    return {}


ORDINARY_PROFIT_EXIT_REASONS = frozenset((
    "MOUNTAIN_NEXT_MATURE_PHYSICAL_EDGE", "HEIST_OPPOSITE_PHYSICAL_BOX_EDGE",
    "HELD_MISSION_PHYSICAL_DESTINATION", "ARC_PROFITABLE_CONTRACT_INTERRUPTION",
))
THIRD_WEAKNESS_COLLECTION_POLICY = "THIRD_DISTINCT_WEAKNESS_V1"
TACTICAL_COLLECTION_POLICY = "TACTICAL_OBSERVED_RETURN_V2"
ARC_CONTRACT_PROFIT_REASON = "ARC_PROFITABLE_CONTRACT_INTERRUPTION"
ARC_CONTRACT_PROFIT_VERSION = "ARC_PROFITABLE_CONTRACT_INTERRUPTION_V1"


def _entry_source_was_observed(mission: Mapping[str, Any], *, source_ms: float,
                               entry_time_ms: float) -> bool:
    """Keep legacy entry ordering; new source-clock lead needs its fill proof."""
    return bool(source_ms <= entry_time_ms or source_receipt_is_fresh(
        mission.get("source_receipt"), now_ts=entry_time_ms / 1000., source_ms=source_ms,
        continuity_generation=mission.get("continuity_generation")))


def _parent_weakness_proof(parent: Mapping[str, Any], *, scope: str, side: Side,
                          generation: int, source_ms: float) -> dict[str, Any]:
    """Read the source-owned episode history; never advance it during review."""
    proof = mapping(parent.get("weakness"))
    count, required = proof.get("count"), proof.get("required_count")
    known = number(proof.get("known_ms"))
    events = proof.get("events")
    valid = bool(proof.get("version") == "PARENT_WEAKNESS_EPISODES_V1"
        and proof.get("scope_id") == scope and as_side(proof.get("side")) is side
        and type(proof.get("continuity_generation")) is int
        and proof.get("continuity_generation") == generation
        and number(proof.get("source_ms")) == source_ms
        and known is not None and 0 < known == source_ms
        and proof.get("continuous") is True
        and type(count) is int and count >= 0 and type(required) is int and required == 3
        and isinstance(events, (list, tuple)) and len(events) == count
        and type(proof.get("third_observed")) is bool
        and proof.get("third_observed") == (count >= required))
    previous_source = previous_known = -math.inf
    identities = set()
    if valid:
        for raw in events:
            event = mapping(raw)
            identity = event.get("id")
            observed, event_known = number(event.get("source_ms")), number(event.get("known_ms"))
            if (not isinstance(identity, str) or not identity or identity in identities
                    or event.get("scope_id") != scope or as_side(event.get("side")) is not side
                    or type(event.get("continuity_generation")) is not int
                    or event.get("continuity_generation") != generation
                    or observed is None or event_known is None
                    or not 0 < observed <= event_known <= known
                    or observed <= previous_source or event_known < previous_known):
                valid = False
                break
            identities.add(identity)
            previous_source, previous_known = observed, event_known
    return {"weakness_proof_valid": valid,
        "weakness_count": count if valid else 0, "weakness_required_count": 3,
        "third_weakness_observed": bool(valid and count >= 3),
        "weakness_events": [dict(mapping(e)) for e in events] if valid else []}


def _confirmed_parent_end(parent: Mapping[str, Any], terminal: Mapping[str, Any],
                          side: Side, *, terminal_valid: bool) -> bool:
    """A witnessed whole-parent reversal is an independent structural end."""
    evidence = mapping(terminal.get("evidence"))
    transition = number(parent.get("transition_known_ms"))
    extreme_source = number(evidence.get("extreme_source_ms"))
    extreme = number(evidence.get("extreme_btc"))
    return bool(terminal_valid and parent.get("status") == "COMPLETED"
        and terminal.get("reason") in ("OBSERVED_PARENT_REVERSAL", "CONFIRMED_RELEASE_TRANSFER")
        and transition is not None and number(evidence.get("transition_known_ms")) == transition
        and as_side(evidence.get("observed_transition_side")) is not None
        and as_side(evidence.get("observed_transition_side")) is not side
        and evidence.get("native_id_alone") is False
        and extreme_source is not None and 0 < extreme_source <= transition
        and extreme is not None and extreme > 0)


def _invalidated_arc_holding_bridge(mission: Mapping[str, Any], previous: Mapping[str, Any],
                                   target: Mapping[str, Any], link: Mapping[str, Any],
                                   *, entry_time_ms: float) -> bool:
    """An observed return can manage an already purchased failed anticipation.

    The original invalidation stays a fact. This bridge grants holding context
    only; it neither retrospectively validates entry nor completes the new leg.
    """
    entry_source = number(mission.get("source_ms"))
    invalidated = number(previous.get("invalidated_known_ms"))
    original_known = number(previous.get("known_ms"))
    known = number(link.get("known_ms"))
    observed = number(target.get("observed_known_ms"))
    resolution = mapping(previous.get("outgoing_breakout_resolution"))
    width = number(previous.get("outgoing_breakout_tolerance_btc"))
    measured_width = number(resolution.get("threshold_btc"))
    before, after = link.get("from_generation"), link.get("to_generation")
    if not (mission.get("purpose") == "ARC_RETURN"
            and previous.get("status") == "INVALIDATED" and previous.get("invalidated") is True
            and previous.get("invalidation_reason") == "PARENT_EXTREME_REEXTENDED"
            and link.get("holding_only") is True and link.get("purchased_purpose") == "ARC_RETURN"
            and link.get("from_status") == "INVALIDATED"
            and link.get("entry_invalidation_preserved") is True
            and link.get("gap_path_observed") is False
            and link.get("creates_terminal") is False and link.get("renews_entry_permission") is False
            and entry_source is not None and number(link.get("entry_source_ms")) == entry_source
            and invalidated is not None and number(link.get("invalidated_known_ms")) == invalidated
            and original_known is not None and known is not None
            and 0 < original_known <= entry_source
            and _entry_source_was_observed(mission, source_ms=entry_source, entry_time_ms=entry_time_ms)
            and max(entry_source, entry_time_ms) < invalidated <= known
            and observed is not None and invalidated < observed <= known
            and number(link.get("to_observed_known_ms")) == observed
            and link.get("to_previous_id") == target.get("previous_id")
            and isinstance(previous.get("predecessor_id"), str) and previous["predecessor_id"]
            and link.get("predecessor_id") == previous["predecessor_id"]
            and resolution.get("basis") == "OBSERVED_PARENT_SCOPE_RANGE_RESOLUTION"
            and number(resolution.get("source_ms")) == original_known
            and resolution.get("fixed_duration_permission") is False
            and measured_width is not None and measured_width > 0
            and width is not None and width >= measured_width
            and (number(previous.get("outgoing_extreme_btc")) or 0) > 0
            and type(before) is int and type(after) is int and 0 <= before <= after):
        return False
    if after > before:
        return link.get("basis") in (
            "CURRENT_PRIMARY_REACQUISITION", "CURRENT_RELEASE_REACQUISITION", "FRESH_CONFIRMED_HANDOFF",
            "CURRENT_OBSERVED_PAID_ARC_HOLDING_REACQUISITION")
    transition = number(link.get("to_transition_known_ms"))
    current_transition = number(target.get("transition_known_ms"))
    return bool(link.get("basis") == "CURRENT_OBSERVED_PARENT_RETURN_ADOPTION"
        and target.get("previous_id") == previous["predecessor_id"]
        and target.get("predecessor_id") == previous["predecessor_id"]
        and target.get("origin_observed") is True
        and target.get("basis") in ("OBSERVED_COMPARISON_ENVELOPE", "CONFIRMED_RELEASE_TRANSFER")
        and link.get("to_previous_id") == target.get("previous_id")
        and number(link.get("to_observed_known_ms")) == observed
        and transition is not None and observed is not None and current_transition is not None
        and invalidated < transition <= observed <= known and transition <= current_transition)


def _interrupted_paid_arc_holding_bridge(
    mission: Mapping[str, Any], previous: Mapping[str, Any],
    target: Mapping[str, Any], link: Mapping[str, Any], *, entry_time_ms: float,
) -> bool:
    """Reconnect paid ARC management without asking the entry rack for a side.

    A fresh same-side observed parent supplies holding context only. The gap
    remains unobserved, and the new parent's own later evidence must earn any
    collection. Neither a different ID nor the position's ownership fills in
    the missing physical path.
    """
    entry_source = number(mission.get("source_ms"))
    known, source = number(link.get("known_ms")), number(link.get("source_ms"))
    observed = number(target.get("observed_known_ms"))
    previous_source = number(previous.get("source_ms"))
    before, after = link.get("from_generation"), link.get("to_generation")
    return bool(mission.get("purpose") == "ARC_RETURN"
        and link.get("basis") == "CURRENT_OBSERVED_PAID_ARC_HOLDING_REACQUISITION"
        and previous.get("status") == "INTERRUPTED"
        and link.get("from_status") == "INTERRUPTED"
        and previous.get("invalidated") is not True
        and mapping(previous.get("terminal")).get("qualified") is not True
        and link.get("holding_only") is True and link.get("purchased_purpose") == "ARC_RETURN"
        and link.get("gap_path_observed") is False
        and link.get("creates_terminal") is False and link.get("renews_entry_permission") is False
        and entry_source is not None and number(link.get("entry_source_ms")) == entry_source
        and known is not None and source == known and observed is not None
        and _entry_source_was_observed(mission, source_ms=entry_source, entry_time_ms=entry_time_ms)
        and max(entry_source, entry_time_ms) < observed <= known
        and previous_source is not None and previous_source < observed
        and number(link.get("to_observed_known_ms")) == observed
        and link.get("to_previous_id") == target.get("previous_id")
        and type(before) is int and type(after) is int and 0 <= before < after)


def _prior_cross_observed(snapshot: MarketSnapshot) -> bool:
    """Require two witnessed crossings in the current continuous segment.

    The flag alone, a sign across missing data, or a future pivot supplies no
    holding evidence. This is permission to breathe through a crossing; it
    never creates entry or collection authority.
    """
    cross = mapping(snapshot.metadata.get("ema9_ema30_cross_context"))
    latest = mapping(cross.get("latest_observed_cross"))
    previous = mapping(cross.get("previous_observed_cross"))
    source = number(cross.get("source_ms"))
    latest_time = number(latest.get("known_source_ms"))
    previous_time = number(previous.get("known_source_ms"))
    max_age = number(snapshot.metadata.get("geometry_max_source_age_seconds")) or 5.
    return bool(cross.get("previous_observed_cross_present") is True
        and source is not None and current_source_is_fresh(snapshot, source, max_age_seconds=max_age)
        and latest_time is not None and previous_time is not None
        and previous_time < latest_time <= source
        and latest.get("observed_continuously") is True
        and previous.get("observed_continuously") is True
        and latest.get("continuity_segment") is not None
        and latest.get("continuity_segment") == previous.get("continuity_segment")
        and as_side(latest.get("direction")) is not None
        and as_side(previous.get("direction")) is not None
        and as_side(latest.get("direction")) is not as_side(previous.get("direction")))


def _tactical_full_lot_sale(position: Mapping[str, Any], snapshot: MarketSnapshot,
                            side: Side) -> dict[str, Any]:
    """Current executable paper opportunity, including both actual fee bases."""
    # The executor imports recovery/management, so import its shared price
    # arithmetic at evaluation time rather than create an import cycle.
    from strategy_core.paper_execution import PriceLevel, _sweep, nominal_taker_fee

    native = mapping(snapshot.metadata.get("native_depth"))
    mark = mapping(snapshot.metadata.get("paper_exit_mark"))
    execution_state = mapping(snapshot.metadata.get("paper_execution_state"))
    quote_ts = number(snapshot.metadata.get("quote_observed_ts"))
    quantity = position.get("qty")
    cost, entry_fee = number(position.get("cost")), number(position.get("entry_fee_remaining"))
    proof: dict[str, Any] = {"qualified": False, "quote_id": snapshot.metadata.get("quote_id"),
        "quantity": quantity, "full_quantity_visible": False, "net_after_fees": None,
        "fee_model": "NOMINAL_0.07_CEIL_CENT_PAPER_ASSUMPTION",
        "depth_basis": "EXECUTOR_REMAINING_EXACT_QUOTE_BID",
        "remaining_depth_mark_valid": False}
    if (not snapshot.quote_current or not snapshot.can_sell(side)
            or native.get("ticker") != snapshot.ticker
            or not proof["quote_id"] or native.get("quote_id") != proof["quote_id"]
            or quote_ts is None or not 0 <= snapshot.now_ts - quote_ts <= 3.
            or type(quantity) is not int or quantity < 1
            or cost is None or cost <= 0 or entry_fee is None or entry_fee < 0):
        return proof
    # Native snapshots describe exchange depth before our PAPER fills. Only
    # the writer owns consumption of that exact quote; a raw full-lot mark
    # cannot grant a profitable sale after another fill has used its top bid.
    mark_valid = bool(mark.get("version") == "PAPER_REMAINING_EXIT_MARK_V1"
        and mark.get("current") is True and mark.get("remaining_depth_applied") is True
        and mark.get("position_id") == str(position.get("position_id"))
        and mark.get("ticker") == snapshot.ticker and as_side(mark.get("side")) is side
        and mark.get("quote_id") == proof["quote_id"]
        and number(mark.get("quote_observed_ts")) == quote_ts
        and number(mark.get("evaluated_at")) == snapshot.now_ts
        and type(mark.get("quantity")) is int and mark["quantity"] == quantity
        and number(mark.get("cost")) == cost and number(mark.get("entry_fee_remaining")) == entry_fee
        and type(mark.get("journal_seq")) is int and mark["journal_seq"] >= 0
        and mark["journal_seq"] == execution_state.get("journal_seq")
        and isinstance(mark.get("journal_sha256"), str) and len(mark["journal_sha256"]) == 64
        and mark["journal_sha256"] == execution_state.get("journal_sha256")
        and isinstance(mark.get("used_bid_levels"), Mapping))
    if not mark_valid:
        return proof
    used = dict(mark["used_bid_levels"])
    if any(number(price) is None or not 0 < number(price) < 1
           or type(amount) is not int or amount < 0 for price, amount in used.items()):
        return proof
    proof.update(remaining_depth_mark_valid=True, journal_seq=mark["journal_seq"],
        journal_sha256=mark["journal_sha256"], used_bid_levels=used)
    levels = []
    for raw in native.get("yes_bids" if side is Side.YES else "no_bids") or ():
        if isinstance(raw, Mapping):
            price, depth = number(raw.get("price")), number(raw.get("quantity"))
        elif isinstance(raw, (tuple, list)) and len(raw) == 2:
            price, depth = number(raw[0]), number(raw[1])
        else:
            return proof
        if price is None or depth is None or not 0 < price < 1 or depth <= 0:
            return proof
        levels.append(PriceLevel(price, depth))
    try:
        sale = _sweep(tuple(levels), quantity, buy=False, used=used)
    except ValueError:
        return proof
    if not sale or not sale["full_quantity_visible"]:
        return proof
    fee = nominal_taker_fee(quantity, sale["price"])
    net = sale["amount"] - Decimal(str(cost)) - Decimal(str(entry_fee)) - fee
    if (mark.get("full_quantity_visible") is not True
            or number(mark.get("full_lot_bid")) != float(sale["price"])
            or number(mark.get("net_after_fees")) != float(net)
            or number(mark.get("exit_fee")) != float(fee)):
        proof["remaining_depth_mark_valid"] = False
        return proof
    proof.update(qualified=net > 0, full_quantity_visible=True,
        full_lot_bid=float(sale["price"]), net_after_fees=float(net), exit_fee=float(fee))
    return proof


def _arc_timing_reference(position: Mapping[str, Any], parent: Mapping[str, Any], *, source: float,
                          generation: int, side: Side) -> dict[str, Any]:
    """Validate the immutable entry-earned family, without later switching.

    These are observed duration analogues, not a guaranteed future finishing
    time. A missing initial origin/path cannot acquire permission later.
    """
    reference = mapping(parent.get("return_timing_reference"))
    origin, bound = number(parent.get("origin_ms")), number(reference.get("bind_source_ms"))
    coverage = mapping(reference.get("current_path_coverage"))
    minimum = reference.get("minimum_count")
    entry = entry_metadata(position)
    mission = mapping(entry.get("mission"))
    scale = mapping(entry.get("arc_entry_scale"))
    scale_proof = mapping(scale.get("qualification_evidence"))
    selected = scale.get("comparison_family")
    result = {"qualified": False, "reason": "FROZEN_OBSERVED_PARENT_TIMING_REQUIRED",
        "reference": dict(reference), "entry_scale": dict(scale),
        "reference_family": None, "reference_ids": [],
        "parent_origin_ms": origin, "shortest_reference_duration_seconds": None,
        "earliest_reference_finish_ts": None}
    entry_source = number(mission.get("source_ms"))
    received = scale_proof.get("comparable_current_leg_mature") is True
    minutes = scale_proof.get("completed_minute_parent_mature") is True
    earned_family = "received_parent" if received else "completed_minute_parent" if minutes else None
    if not (scale.get("version") == "ARC_ENTRY_SCALE_V1" and scale.get("qualified") is True
            and scale.get("frozen_at_entry") is True and scale.get("later_family_switch_allowed") is False
            and mission.get("purpose") == "ARC_RETURN"
            and isinstance(scale.get("parent_id"), str) and bool(scale["parent_id"])
            and as_side(scale.get("side")) is not None and as_side(scale.get("side")) is not side
            and scale.get("incoming_parent_id") == mission.get("parent_leg_id")
            and as_side(scale.get("incoming_side")) is side
            and as_side(mission.get("side")) is side
            and entry_source is not None and number(scale.get("source_ms")) == entry_source
            and type(scale.get("continuity_generation")) is int
            and scale["continuity_generation"] == mission.get("continuity_generation")
            and (not entry.get("entry_arc_id") or entry["entry_arc_id"] == scale["parent_id"])
            and selected is not None and selected == earned_family
            and scale.get("qualification_basis") == ("INDEPENDENT_RECEIVED_PARENT_MATURITY"
                if selected == "received_parent" else "INDEPENDENT_COMPLETED_MINUTE_PARENT_MATURITY")
            and scale_proof.get("qualified") is True
            and scale_proof.get("basis") == "INDEPENDENT_CURRENT_PARENT_SCALE_V1"
            and scale_proof.get("parent_id") == scale["parent_id"]
            and as_side(scale_proof.get("side")) is as_side(scale.get("side"))
            and number(scale_proof.get("source_ms")) == entry_source
            and scale_proof.get("continuity_generation") == scale["continuity_generation"]
            and scale_proof.get("comparison_family") == selected):
        result["reason"] = "IMMUTABLE_ENTRY_EARNED_ARC_SCALE_FAMILY_REQUIRED"
        return result
    if not (reference.get("version") == "PARENT_RETURN_TIMING_REFERENCE_V1"
            and reference.get("parent_id") == parent.get("id")
            and as_side(reference.get("side")) is side
            and type(reference.get("continuity_generation")) is int
            and reference["continuity_generation"] == generation
            and parent.get("origin_observed") is True and reference.get("origin_observed") is True
            and origin is not None and number(reference.get("origin_ms")) == origin
            and bound is not None and 0 < origin <= bound <= source
            and reference.get("bind_kind") == "ACTIVE_OBSERVED_PARENT"
            and reference.get("current_path_complete") is True
            and coverage.get("observed_from_start") is True
            and coverage.get("source_continuous") is True
            and number(coverage.get("first_source_ms")) == origin
            and number(coverage.get("last_source_ms")) == bound
            and type(coverage.get("sample_count")) is int and coverage["sample_count"] >= 2
            and type(minimum) is int and minimum >= 2):
        return result
    families = mapping(reference.get("families"))
    eligible = {}
    for name in ("received_parent", "completed_minute_parent"):
        family = mapping(families.get(name))
        rows = family.get("references")
        if not isinstance(rows, (tuple, list)) or family.get("reference_count") != len(rows):
            return result
        identities = set()
        durations = []
        for raw in rows:
            row = mapping(raw)
            start, end, known, duration = (number(row.get(k)) for k in
                ("origin_ms", "end_ms", "completed_known_ms", "duration_seconds"))
            identity = row.get("id")
            if not (isinstance(identity, str) and identity and identity not in identities
                    and as_side(row.get("side")) is side
                    and row.get("direction") == ("UP" if side is Side.YES else "DOWN")
                    and row.get("origin_observed") is True
                    and start is not None and end is not None and known is not None
                    and 0 < start < end <= known <= bound and duration is not None and duration > 0
                    and abs(duration - (end - start) / 1000.) <= 1e-6
                    and (row.get("complete_observed_path") is True if name == "received_parent"
                         else row.get("complete_minute_coverage") is True
                            and number(row.get("resolution_seconds")) == 60.)):
                return result
            identities.add(identity)
            durations.append(duration)
        if type(family.get("enough_references")) is not bool \
                or family["enough_references"] != (len(rows) >= minimum):
            return result
        eligible[name] = (list(identities), durations) if len(rows) >= minimum else None
    if not eligible.get(selected):
        result["reason"] = "SUFFICIENT_ENTRY_EARNED_FROZEN_REFERENCE_FAMILY_REQUIRED"
        return result
    ids, durations = eligible[selected]
    shortest = min(durations)
    result.update(qualified=True, reason="FROZEN_OBSERVED_DURATION_COMPARISON",
        reference_family=selected, reference_ids=sorted(ids),
        shortest_reference_duration_seconds=shortest,
        earliest_reference_finish_ts=origin / 1000. + shortest)
    return result


def _arc_contract_interruption(position: Mapping[str, Any], snapshot: MarketSnapshot,
                               parent: Mapping[str, Any], scoped: Mapping[str, Any],
                               *, source: float, generation: int, side: Side) -> dict[str, Any]:
    """A current profitable rollover exception, not a manufactured leg end."""
    close = number(position.get("close_ts"))
    filled = number(position.get("entry_time"))
    result: dict[str, Any] = {"version": ARC_CONTRACT_PROFIT_VERSION, "qualified": False,
        "reason": "CURRENT_NORMAL_ARC_HOLDING_REQUIRED", "position_id": str(position.get("position_id")),
        "ticker": position.get("ticker"), "side": side.value, "quantity": position.get("qty"),
        "cost": position.get("cost"), "entry_fee_remaining": position.get("entry_fee_remaining"),
        "scope_id": parent.get("id"), "source_ms": source, "evaluated_at": snapshot.now_ts,
        "continuity_generation": generation, "close_ts": close,
        "remaining_seconds": close - snapshot.now_ts if close is not None else None,
        "parent_completed": False, "entry_permission_renewed": False,
        "historical_comparison_only": True, "future_minimum_or_maximum_used": False}
    context = mapping(snapshot.metadata.get("mission_context"))
    if not (scoped.get("purpose") == "ARC_RETURN" and scoped.get("valid") is True
            and scoped.get("current") is True and scoped.get("scope_status") == "ACTIVE"
            and scoped.get("weakness_proof_valid") is True and not scoped.get("collection_qualified")
            and parent.get("status") == "ACTIVE" and parent.get("invalidated") is not True
            and mapping(context.get("parent")).get("id") == parent.get("id")
            and position.get("custody_state", "NORMAL") in ("NORMAL", "RECOVERED_NORMAL")
            and position.get("floor_bid") is None and not position.get("exit_required")
            and close is not None and snapshot.now_ts < close and filled is not None
            and entry_candle_evidence(position, snapshot)["entry_candle_complete"]):
        return result
    geometry = mapping(parent.get("geometry"))
    path = mapping(geometry.get("current_path_coverage"))
    origin = number(parent.get("origin_ms"))
    if not (geometry.get("current") is True and number(geometry.get("source_ms")) == source
            and geometry.get("current_arc_id") == parent.get("id")
            and as_side(geometry.get("owner_side")) is side
            and path.get("complete_observed_path") is True
            and path.get("source_continuous") is True and path.get("origin_observed") is True
            and path.get("endpoints_are_actual_observations") is True
            and number(path.get("first_source_ms")) == origin
            and number(path.get("last_source_ms")) == source
            and geometry.get("strong_active_release") is not True):
        result["reason"] = "CURRENT_CONTIGUOUS_HELD_PARENT_PATH_REQUIRED"
        return result
    timing = _arc_timing_reference(position, parent, source=source, generation=generation, side=side)
    result.update({k: timing[k] for k in ("reference_family", "reference_ids", "parent_origin_ms",
        "shortest_reference_duration_seconds", "earliest_reference_finish_ts")})
    result["timing_reference"] = timing["reference"]
    result["entry_scale"] = timing["entry_scale"]
    if not timing["qualified"] or close >= timing["earliest_reference_finish_ts"]:
        result["reason"] = timing["reason"] if not timing["qualified"] else "COMPARABLE_PARENT_FITS_CONTRACT"
        return result
    weakness = mapping(parent.get("weakness"))
    active = mapping(weakness.get("active_episode"))
    events = scoped.get("weakness_events") or []
    latest = mapping(events[-1]) if events else {}
    event_source, known = number(active.get("source_ms")), number(active.get("known_ms"))
    resolution = number(active.get("weakness_velocity_resolution_btc_s"))
    if not (active and weakness.get("rearmed") is False and weakness.get("last_gap") is None
            and active.get("event_id") == latest.get("id")
            and event_source is not None and known is not None
            and filled * 1000. < event_source <= known <= source
            and event_source == number(latest.get("source_ms"))
            and known == number(latest.get("known_ms"))
            and resolution is not None and resolution >= 0):
        result["reason"] = "ACTIVE_POST_ENTRY_WEAKNESS_REQUIRED"
        return result
    motions = mapping(geometry.get("current_motion"))
    current_rates = []
    sign = 1 if side is Side.YES else -1
    for horizon in ("6", "12"):
        motion = mapping(motions.get(horizon))
        start, first, current = (number(motion.get(k)) for k in
                                 ("start_source_ms", "first_price", "current_price"))
        if not (motion.get("covered") is True and motion.get("source_continuous") is True
                and motion.get("endpoints_are_actual_observations") is True
                and motion.get("complete_observed_path") is True
                and number(motion.get("source_ms")) == source
                and number(motion.get("last_source_ms")) == source
                and start is not None and filled * 1000. <= start < source
                and first is not None and current is not None
                and current == number(geometry.get("current_btc"))):
            result["reason"] = "CURRENT_WEAKNESS_MOTION_COVERAGE_REQUIRED"
            return result
        current_rates.append(sign * (current - first) / ((source - start) / 1000.))
    if max(current_rates) > resolution:
        result["reason"] = "CURRENT_PARENT_ADVANCE_HAS_RESUMED"
        return result
    result.update(active_weakness_event_id=active["event_id"], active_weakness_source_ms=event_source,
        current_owner_price_rates=current_rates, weakness_velocity_resolution_btc_s=resolution)
    sale = _tactical_full_lot_sale(position, snapshot, side)
    mark = mapping(snapshot.metadata.get("paper_exit_mark"))
    peak = number(position.get("peak_bid"))
    result.update(current_full_lot_sale=sale, quote_id=snapshot.metadata.get("quote_id"),
        quote_observed_ts=snapshot.metadata.get("quote_observed_ts"), observed_peak_bid=peak,
        current_full_lot_bid=sale.get("full_lot_bid"), net_after_fees=sale.get("net_after_fees"))
    if not sale["qualified"]:
        result["reason"] = "CURRENT_FULL_REMAINING_LOT_POSITIVE_NET_REQUIRED"
        return result
    if (peak is None or mark.get("peak_basis") != "EXECUTOR_OBSERVED_FULL_LOT_BID"
            or number(mark.get("observed_peak_bid")) != peak
            or not peak > sale["full_lot_bid"]):
        result["reason"] = "OBSERVED_FULL_LOT_BID_GIVEBACK_REQUIRED"
        return result
    result.update(qualified=True, reason=ARC_CONTRACT_PROFIT_REASON)
    return result


def _observed_tactical_return(position: Mapping[str, Any], snapshot: MarketSnapshot,
                               *, source: float, entry_source: float,
                               initial: float | None, reached: bool) -> dict[str, Any]:
    """A purchased local return needs its own observed path and end.

    The entry's native ID often describes the *outgoing* leg. It cannot also
    be required to name the opposite incoming return. Conversely a new ID,
    target contact, price percentage or a source reset alone proves no end.
    """
    side = as_side(position.get("side"))
    sign = 1 if side is Side.YES else -1
    entry = entry_metadata(position)
    geometry = mapping(snapshot.metadata.get("current_geometry"))
    context = mapping(snapshot.metadata.get("mission_context"))
    local = mapping(context.get("local"))
    mountain = mapping(snapshot.metadata.get("mountain"))
    coverage = mapping(mountain.get("current_path_coverage"))
    terminal = mapping(local.get("terminal"))
    current_generation = context.get("continuity_generation")
    scope = local.get("arc_id")
    origin, known = number(local.get("origin_ms")), number(local.get("known_ms"))
    extreme, extreme_ms = number(mountain.get("owner_extreme_btc")), number(mountain.get("edge_extreme_ms"))
    btc, width = number(geometry.get("btc_price")), number(mountain.get("contact_width"))
    fill_ms = (number(position.get("entry_time")) or math.inf) * 1000.
    proof: dict[str, Any] = {"version": TACTICAL_COLLECTION_POLICY,
        "source_ms": source, "incoming_scope_id": scope,
        "entry_outgoing_scope_id": mapping(entry.get("mission")).get("swing_id"),
        "continuity_generation": current_generation, "incoming_path_proven": False,
        "post_entry_favorable_travel": None, "return_retreat": None,
        "destination_reached": reached, "observed_terminal": False,
        "destination_exhausted": False, "collection_authority": None,
        "native_id_alone": False, "automatic_take_profit": False}
    entry_geometry = mapping(entry.get("entry_geometry"))
    same_incoming_at_entry = (entry_geometry.get("arc_id") == scope
        and entry_geometry.get("arc_direction") == ("UP" if side is Side.YES else "DOWN"))
    path_proven = bool(side is not None and initial is not None and btc is not None
        and width is not None and width > 0 and extreme is not None and extreme_ms is not None
        and isinstance(scope, str) and scope and local.get("scope_id") == scope
        and as_side(local.get("side")) is side and as_side(mountain.get("owner_side")) is side
        and mountain.get("current_arc_id") == scope and geometry.get("arc_id") == scope
        and number(mountain.get("source_ms")) == source == number(geometry.get("epoch_ms"))
        and number(mountain.get("current_btc")) == btc
        and origin is not None and known is not None and 0 < origin <= known <= source
        and number(geometry.get("arc_start_ms")) == origin == number(mountain.get("arc_origin_ms"))
        and number(geometry.get("arc_known_ms")) == known
        and (known >= entry_source or same_incoming_at_entry)
        and geometry.get("arc_origin_observed") is True
        and mountain.get("arc_origin_observed") is True
        and coverage.get("complete_observed_path") is True
        and coverage.get("source_continuous") is True
        and coverage.get("endpoints_are_actual_observations") is True
        and coverage.get("origin_observed") is True
        and number(coverage.get("first_source_ms")) == origin
        and number(coverage.get("last_source_ms")) == source
        and max(origin, entry_source, fill_ms) <= extreme_ms <= source
        and (extreme - initial) * sign >= width and (btc - initial) * sign > 0)
    proof["incoming_path_proven"] = path_proven
    if not path_proven:
        return proof
    travel, retreat = (extreme - initial) * sign, (extreme - btc) * sign
    proof.update(post_entry_favorable_travel=travel, return_retreat=retreat,
        actual_extreme_btc=extreme, actual_extreme_source_ms=extreme_ms, contact_width=width)
    at, terminal_known = number(terminal.get("source_ms")), number(terminal.get("known_ms"))
    observed_terminal = bool(terminal.get("qualified") is True
        and terminal.get("scope_id") == scope and as_side(terminal.get("side")) is side
        and terminal.get("continuity_generation") == current_generation
        and at == source == terminal_known and extreme_ms <= at
        and mountain.get("mature_edge") is True
        and mountain.get("terminal_evidence_qualified") is True
        and mountain.get("edge_window_active", True) is True
        and mountain.get("spent_edge") is not True
        and mountain.get("strong_active_release") is not True)
    # Reaching the frozen local destination while actively advancing is not
    # collection. A real retreat at that destination must be observed over
    # both covered short windows and the actual post-entry extreme.
    rejecting = True
    motion_proof = {}
    for seconds in (6, 12):
        motion = mapping(mapping(mountain.get("current_motion")).get(str(seconds)))
        start, first = number(motion.get("start_source_ms")), number(motion.get("first_price"))
        valid = bool(motion.get("covered") is True and motion.get("source_continuous") is True
            and motion.get("endpoints_are_actual_observations") is True
            and number(motion.get("source_ms")) == source
            and number(motion.get("current_price")) == btc
            and start is not None and max(origin, fill_ms) <= start < source
            and first is not None and (btc - first) * sign <= 0)
        motion_proof[str(seconds)] = {"covered_rejection": valid,
            "source_ms": source, "start_source_ms": start,
            "held_side_price_change": (btc - first) * sign if first is not None else None}
        rejecting = rejecting and valid
    exhausted = bool(reached and retreat >= width and rejecting
        and mountain.get("strong_active_release") is not True)
    authority = "OBSERVED_TACTICAL_RETURN_END" if observed_terminal else (
        "TACTICAL_DESTINATION_EXHAUSTED" if exhausted else None)
    proof.update(observed_terminal=observed_terminal, destination_exhausted=exhausted,
        collection_authority=authority, current_motion=motion_proof)
    return proof


def mission_collection_evidence(
    position: Mapping[str, Any], snapshot: MarketSnapshot,
) -> dict[str, Any]:
    """Collection proof for the exact persistent purpose of this held lot.

    A native arc or a PRIMARY/TACTICAL inventory label cannot silently change
    that purpose. Main holdings and full arc returns need their own parent
    terminal. A bounded tactical return keeps its frozen physical destination
    across intervening native turns. Recovery qualification deliberately does
    not use these predicates.
    """
    entry = entry_metadata(position)
    mission = mapping(entry.get("mission"))
    context = mapping(snapshot.metadata.get("mission_context"))
    enforced = "mission" in entry or "mission_context" in snapshot.metadata
    side = as_side(position.get("side"))
    purpose = mission.get("purpose")
    result: dict[str, Any] = {
        "scope_enforced": enforced, "valid": False, "current": False,
        "purpose": purpose, "scope_id": None, "scope_status": "UNKNOWN",
        "parent_leg_id": mission.get("parent_leg_id"), "swing_id": mission.get("swing_id"),
        "held_side": side.value if side else None, "source_ms": context.get("source_ms"),
        "continuity_generation": context.get("continuity_generation"),
        "terminal_qualified": False, "terminal_reason": None,
        "destination_reached": False, "collection_qualified": False,
        "parent_supported": False, "parent_invalidated": False,
        "prior_cross_observed": False, "prior_cross_hold": False,
        "collection_policy": mission.get("collection_policy"),
        "collection_authority": None, "collection_hold_reason": None,
        "weakness_proof_valid": False, "weakness_count": 0,
        "weakness_required_count": 3, "third_weakness_observed": False,
        "weakness_events": [],
        "destination": dict(mapping(mission.get("destination"))),
        "reason": "LEGACY_UNSCOPED_COLLECTION" if not enforced else "HELD_MISSION_IDENTITY_REQUIRED",
    }
    if not enforced:
        return result
    source = number(context.get("source_ms"))
    entry_source = number(mission.get("source_ms"))
    entry_time = number(position.get("entry_time"))
    generation = mission.get("continuity_generation")
    parent_scoped = purpose in ("MAIN_CONTRACT", "ARC_RETURN")
    scope = mission.get("parent_leg_id") if parent_scoped else mission.get("swing_id")
    if (purpose not in ("MAIN_CONTRACT", "ARC_RETURN", "TACTICAL_RETURN") or side is None
            or as_side(mission.get("side")) is not side
            or not isinstance(scope, str) or not scope
            or entry_source is None or entry_time is None
            or not _entry_source_was_observed(mission, source_ms=entry_source,
                                             entry_time_ms=entry_time * 1000.)
            or type(generation) is not int or generation < 0):
        return result
    result.update(valid=True, scope_id=scope, reason="HELD_MISSION_CURRENT_CONTEXT_REQUIRED")
    max_age = number(snapshot.metadata.get("geometry_max_source_age_seconds")) or 5.
    close_ts = number(position.get("close_ts"))
    current_generation = context.get("continuity_generation")
    if (context.get("current") is not True or snapshot.metadata.get("physical_current") is False
            or source is None or source < entry_source
            or not current_source_is_fresh(snapshot, source, max_age_seconds=max_age)
            or type(current_generation) is not int or current_generation < generation
            or snapshot.metadata.get("geometry_continuity_generation", current_generation) != current_generation
            or position.get("ticker") != snapshot.ticker
            or close_ts is not None and snapshot.now_ts >= close_ts):
        return result
    result["current"] = True
    terminal_not_before = entry_source

    def terminal_valid(terminal: Mapping[str, Any], *, completed: bool = False,
                       transition_known_ms: float | None = None) -> bool:
        at = number(terminal.get("source_ms"))
        known = number(terminal.get("known_ms", at))
        return bool(terminal.get("qualified") is True
            and terminal.get("scope_id") == scope
            and as_side(terminal.get("side")) is side
            and type(terminal.get("continuity_generation")) is int
            and terminal.get("continuity_generation") == generation
            and at is not None and known is not None
            and terminal_not_before <= at <= known <= source
            and (completed and transition_known_ms is not None
                 and known <= transition_known_ms <= source
                 or not completed and 0 <= (source - at) / 1000. <= max_age))

    parent = mapping(context.get("parent"))
    if parent_scoped:
        parents = mapping(context.get("parents_by_id"))
        scoped_parent = mapping(parents.get(scope))
        if parent.get("id") == scope:
            scoped_parent = parent
        successor = mapping(parent.get("successor"))
        if successor.get("id") == scope:
            scoped_parent = successor
        if (current_generation != generation or scoped_parent.get("reacquired_by_parent_id")) \
                and scoped_parent.get("status") != "COMPLETED":
            # A reset supplies no completion evidence. A recorded same-side
            # physical holding link can connect this paid ARC to a later
            # observed parent without new entry-tool ownership. Each further
            # gap still requires a causal link; IDs alone cannot renew scope.
            chain = []
            visited = set()
            for _ in range(32):
                if (generation == current_generation and not scoped_parent.get("reacquired_by_parent_id")) \
                        or scoped_parent.get("status") == "COMPLETED":
                    break
                link = mapping(scoped_parent.get("reacquisition"))
                next_id = link.get("to_id")
                next_generation = link.get("to_generation")
                known = number(link.get("known_ms"))
                observed = number(link.get("source_ms"))
                next_parent = mapping(parents.get(next_id))
                if parent.get("id") == next_id:
                    next_parent = parent
                next_known = number(next_parent.get("known_ms"))
                interrupted_link = bool(scoped_parent.get("status") == "INTERRUPTED"
                    and type(next_generation) is int and generation < next_generation
                    and link.get("basis") in (
                        "CURRENT_PRIMARY_REACQUISITION", "CURRENT_RELEASE_REACQUISITION",
                        "FRESH_CONFIRMED_HANDOFF"))
                held_return_link = (_invalidated_arc_holding_bridge(
                    mission, scoped_parent, next_parent, link, entry_time_ms=entry_time * 1000.)
                    or _interrupted_paid_arc_holding_bridge(
                        mission, scoped_parent, next_parent, link, entry_time_ms=entry_time * 1000.))
                valid_link = bool(scope not in visited
                    and scoped_parent.get("id") == scope
                    and (interrupted_link or held_return_link)
                    and as_side(scoped_parent.get("side")) is side
                    and link.get("from_id") == scope
                    and type(link.get("from_generation")) is int
                    and link.get("from_generation") == generation
                    and isinstance(next_id, str) and next_id
                    and scoped_parent.get("reacquired_by_parent_id") == next_id
                    and type(next_generation) is int
                    and generation <= next_generation <= current_generation
                    and as_side(link.get("side")) is side
                    and known is not None and observed is not None
                    and terminal_not_before <= observed <= known <= source
                    and next_parent.get("id") == next_id
                    and as_side(next_parent.get("side")) is side
                    and type(next_parent.get("continuity_generation")) is int
                    and next_parent.get("continuity_generation") == next_generation
                    and next_known is not None and next_known <= known)
                if not valid_link:
                    result.update(reason="HELD_PARENT_REACQUISITION_NOT_VERIFIED")
                    return result
                visited.add(scope)
                chain.append(dict(link))
                scope, generation, scoped_parent = next_id, next_generation, next_parent
                terminal_not_before = known
            if (scoped_parent.get("status") not in ("ACTIVE", "COMPLETED")
                    or scoped_parent.get("status") == "ACTIVE" and generation != current_generation):
                result.update(reason="HELD_PARENT_REACQUISITION_NOT_VERIFIED")
                return result
            result.update(scope_id=scope, reacquisition_chain=chain,
                          scope_generation=generation)
        if scoped_parent.get("id") != scope or as_side(scoped_parent.get("side")) is not side:
            result.update(reason="HELD_PARENT_SCOPE_NOT_CURRENTLY_OBSERVED")
            return result
        status = str(scoped_parent.get("status") or "ACTIVE").upper()
        result["scope_status"] = status
        if status == "ANTICIPATED":
            known = number(scoped_parent.get("known_ms"))
            if (known is None or known > entry_source
                    or scoped_parent.get("predecessor_id") != parent.get("id")):
                result.update(valid=False, reason="HELD_SUCCESSOR_IDENTITY_NOT_VERIFIED")
                return result
            # The outgoing parent's terminal never closes the anticipated
            # incoming lot, even while its EMA9 has not visibly curled yet.
            result.update(reason="HELD_SUCCESSOR_AWAITS_OBSERVED_PARENT")
        else:
            terminal = mapping(scoped_parent.get("terminal"))
            completed = status == "COMPLETED"
            qualified = terminal_valid(terminal, completed=completed,
                transition_known_ms=number(scoped_parent.get("transition_known_ms")))
            strict_third = mission.get("collection_policy") == THIRD_WEAKNESS_COLLECTION_POLICY
            collection, authority, hold_reason = qualified, "LEGACY_PARENT_TERMINAL" if qualified else None, None
            if strict_third:
                weakness_source = (number(scoped_parent.get("transition_known_ms"))
                                   if completed else source)
                result.update(_parent_weakness_proof(scoped_parent, scope=scope, side=side,
                    generation=generation, source_ms=weakness_source or source))
                confirmed_end = _confirmed_parent_end(scoped_parent, terminal, side,
                                                      terminal_valid=qualified)
                third_collection = bool(status == "ACTIVE" and qualified
                    and result["third_weakness_observed"])
                # A smooth, complete arc may only weaken once at its peak.
                # Its exact outgoing parent terminal plus the independently
                # qualified incoming full-arc scope is a distinct handoff
                # authority; it never manufactures extra weakness episodes.
                opposite = Side.NO if side is Side.YES else Side.YES
                full_arc_handoff = bool(status == "ACTIVE" and qualified
                    and result["weakness_proof_valid"] and result["weakness_count"] >= 1
                    and parent.get("id") == scope
                    and parent.get("continuity_generation") == generation == current_generation
                    and number(terminal.get("source_ms")) == source
                    and number(terminal.get("known_ms", source)) == source
                    and qualified_full_arc_candidate(context, opposite, source))
                collection = confirmed_end or third_collection or full_arc_handoff
                authority = ("CONFIRMED_PARENT_END" if confirmed_end
                    else "SPENT_PARENT_THIRD_DISTINCT_WEAKNESS" if third_collection
                    else "MATURE_FULL_ARC_HANDOFF" if full_arc_handoff else None)
                if not collection:
                    hold_reason = ("HELD_PARENT_WEAKNESS_PROOF_REQUIRED"
                        if not result["weakness_proof_valid"]
                        else "HELD_PARENT_AWAITS_THIRD_DISTINCT_WEAKNESS"
                        if qualified and not result["third_weakness_observed"]
                        else "HELD_PARENT_LEG_STILL_LIVING" if not qualified
                        else "HELD_PARENT_CONFIRMED_END_NOT_VERIFIED")
            result.update(terminal_qualified=qualified,
                terminal_reason=terminal.get("reason") if qualified else None,
                collection_qualified=collection, collection_authority=authority,
                collection_hold_reason=hold_reason,
                parent_supported=bool(not collection and (
                    scoped_parent.get("supported") is True
                    or strict_third and status == "ACTIVE" and scoped_parent.get("invalidated") is not True)),
                parent_invalidated=scoped_parent.get("invalidated") is True,
                reason=("HELD_PARENT_CONFIRMED_END" if authority == "CONFIRMED_PARENT_END"
                    else "HELD_PARENT_SPENT_THIRD_DISTINCT_WEAKNESS" if authority == "SPENT_PARENT_THIRD_DISTINCT_WEAKNESS"
                    else "HELD_PARENT_MATURE_FULL_ARC_HANDOFF" if authority == "MATURE_FULL_ARC_HANDOFF"
                    else "HELD_PARENT_TERMINAL_QUALIFIED" if collection
                    else hold_reason or "HELD_PARENT_LEG_STILL_LIVING"))
            if purpose == "ARC_RETURN" and strict_third and not collection:
                interruption = _arc_contract_interruption(position, snapshot, scoped_parent, result,
                    source=source, generation=generation, side=side)
                result["contract_interruption"] = interruption
                if interruption["qualified"]:
                    # Contract time can interrupt a still-living purchased
                    # return. Do not rewrite its terminal, weakness count,
                    # original mission, or paid-entry latch to explain this.
                    result.update(collection_qualified=True,
                        collection_authority=ARC_CONTRACT_PROFIT_REASON,
                        collection_hold_reason=None, reason=ARC_CONTRACT_PROFIT_REASON)
    else:
        result["scope_status"] = "FROZEN_RETURN_DESTINATION"
        destination = mapping(mission.get("destination"))
        target, tolerance = number(destination.get("btc")), number(destination.get("tolerance"))
        reference_source = number(destination.get("reference_source_ms", entry_source))
        geometry = mapping(snapshot.metadata.get("current_geometry"))
        btc, geometry_source = number(geometry.get("btc_price")), number(geometry.get("epoch_ms"))
        initial = number(mapping(entry.get("entry_geometry")).get("btc_price", entry.get("entry_btc")))
        sign = 1 if side is Side.YES else -1
        destination_valid = bool(destination.get("kind") in ("EMA9_RETURN", "BOX_EDGE")
            and target is not None and tolerance is not None and tolerance >= 0
            and reference_source is not None and reference_source <= entry_source
            and initial is not None and (target - initial) * sign > 0)
        reached = bool(destination_valid and btc is not None and geometry_source is not None
            and entry_source <= geometry_source <= source
            and current_source_is_fresh(snapshot, geometry_source, max_age_seconds=max_age)
            and (btc - initial) * sign > 0 and (btc - target) * sign >= -tolerance)
        terminal = mapping(mapping(context.get("local")).get("terminal"))
        # A newly observed endpoint can reach an entry-time frozen target
        # after a gap. A native terminal cannot cross that missing history.
        qualified = current_generation == generation and terminal_valid(terminal)
        if mission.get("collection_policy") == TACTICAL_COLLECTION_POLICY:
            proof = _observed_tactical_return(position, snapshot, source=source,
                entry_source=entry_source, initial=initial, reached=reached)
            sale = _tactical_full_lot_sale(position, snapshot, side)
            authority = proof.get("collection_authority")
            collect = bool(destination_valid and authority and sale["qualified"])
            hold_reason = ("TACTICAL_FULL_LOT_POSITIVE_NET_BID_REQUIRED" if authority
                else "TACTICAL_RETURN_STILL_ADVANCING_OR_END_UNPROVEN")
            result.update(destination_reached=reached,
                terminal_qualified=proof["observed_terminal"],
                terminal_reason=terminal.get("reason") if proof["observed_terminal"] else None,
                collection_qualified=collect, collection_authority=authority if collect else None,
                collection_hold_reason=None if collect else hold_reason,
                tactical_return_proof=proof, tactical_full_lot_sale=sale,
                reason=authority if collect else hold_reason if destination_valid
                    else "HELD_RETURN_DESTINATION_NOT_VERIFIED")
        else:
            # Preserve immutable policies on old restored lots. New missions
            # explicitly opt into observed-return collection at admission.
            result.update(destination_reached=reached, terminal_qualified=qualified,
                terminal_reason=terminal.get("reason") if qualified else None,
                collection_qualified=reached or qualified,
                reason="HELD_RETURN_DESTINATION_REACHED" if reached else
                    "HELD_SWING_TERMINAL_QUALIFIED" if qualified else
                    "HELD_RETURN_DESTINATION_NOT_YET_REACHED" if destination_valid else
                    "HELD_RETURN_DESTINATION_NOT_VERIFIED")

    cross = _prior_cross_observed(snapshot)
    cross_hold = bool(cross and not result["collection_qualified"]
        and not result["parent_invalidated"]
        and (result["parent_supported"] or result["scope_status"] in
             ("ANTICIPATED", "FROZEN_RETURN_DESTINATION")))
    result.update(prior_cross_observed=cross, prior_cross_hold=cross_hold)
    if cross_hold:
        result["reason"] = "PRIOR_CROSS_LIVING_MISSION_BREATHES"
    return result


def entry_candle_evidence(position: Mapping[str, Any], snapshot: MarketSnapshot) -> dict[str, Any]:
    """Compare actual source minutes with the exact filled entry minute.

    A 30-second holding age is not a completed candle. A source sample from
    the preceding minute also cannot move a fill just after the boundary back
    into that old candle. Missing/stale current observations do not establish
    a new source candle; hard exits and armed floors are resolved separately.
    """
    entry = entry_metadata(position)
    geometry = mapping(snapshot.metadata.get("current_geometry"))
    entry_geometry = mapping(entry.get("entry_geometry"))
    entry_time = number(position.get("entry_time"))
    entry_source = number(entry_geometry.get("epoch_ms", entry.get("entry_geometry_source_ms")))
    current_source = number(geometry.get("epoch_ms", snapshot.metadata.get("geometry_last_epoch_ms")))
    if current_source is None:
        current_source = number(mapping(snapshot.metadata.get("mountain")).get("source_ms"))
    fill_bar = math.floor(entry_time / 60.) * 60000. if entry_time is not None else None
    entry_source_valid = bool(entry_source is not None and entry_time is not None
        and (0 <= entry_time - entry_source / 1000. <= 5.
             or source_receipt_is_fresh(entry.get("entry_source_receipt"),
                 now_ts=entry_time, source_ms=entry_source)))
    source_bar = math.floor(entry_source / 60000.) * 60000. if entry_source_valid else None
    entry_bar = max(fill_bar, source_bar) if source_bar is not None else fill_bar
    source_current = bool(current_source is not None
        and snapshot.metadata.get("physical_current") is not False
        and current_source_is_fresh(snapshot, current_source,
            max_age_seconds=number(snapshot.metadata.get("geometry_max_source_age_seconds")) or 5.))
    current_bar = math.floor(current_source / 60000.) * 60000. if source_current else None
    # A received source timestamp just ahead of the local minute must not
    # finish the filled entry candle before the actual local boundary.
    local_bar = math.floor(snapshot.now_ts / 60.) * 60000.
    complete = bool(entry_bar is not None and current_bar is not None
                    and current_bar > entry_bar and local_bar > entry_bar)
    return {"bar_seconds": 60, "entry_time": entry_time,
        "entry_source_epoch_ms": entry_source if entry_source_valid else None,
        "entry_source_candle_start_ms": source_bar, "entry_fill_candle_start_ms": fill_bar,
        "entry_candle_start_ms": entry_bar, "current_source_epoch_ms": current_source,
        "current_source_candle_start_ms": current_bar, "current_source_is_fresh": source_current,
        "entry_candle_complete": complete,
        "same_entry_candle": bool(entry_bar is not None and current_bar == entry_bar),
        "entry_candle_basis": "RECORDED_SOURCE_AND_EXACT_FILL" if entry_source_valid
            else "EXACT_FILL_TIMESTAMP_CURRENT_SOURCE_REQUIRED"}


def strategy_exit_hold_reason(
    position: Mapping[str, Any], snapshot: MarketSnapshot, reason: str,
) -> str | None:
    """A new strategy sale needs a later observed entry candle.

    Apply this before creating an exit latch or committing EXIT_PENDING. A
    deferred failure/transfer must be re-evaluated from a later current frame;
    it cannot leave a hidden obligation behind. Already accepted exits retain
    authority. Official settlement and independently committed floor execution
    are outer custody/execution obligations, not new tool sale proposals.
    """
    if position.get("exit_required"):
        return None
    if reason == "MOUNTAIN_TERMINAL_EMA9_EDGE_EXIT":
        # The Mountain detector is the sole strategic edge authority in the
        # edge-only build.  Once the next terminal EMA9 edge is current, a
        # second minimum-hold/entry-candle gate would turn a valid corner into
        # a missed relay.
        return None
    candle = entry_candle_evidence(position, snapshot)
    if not candle["entry_candle_complete"]:
        return ("ORDINARY_PROFIT_WAIT_FOR_NEXT_OBSERVED_ENTRY_CANDLE"
                if reason in ORDINARY_PROFIT_EXIT_REASONS
                else "STRATEGY_EXIT_WAIT_FOR_NEXT_OBSERVED_ENTRY_CANDLE")
    if reason in ORDINARY_PROFIT_EXIT_REASONS:
        mission = mission_collection_evidence(position, snapshot)
        if mission["scope_enforced"]:
            return None if mission["collection_qualified"] else str(mission["reason"])
    if (reason == "MOUNTAIN_NEXT_MATURE_PHYSICAL_EDGE"
            and position_role(position) != "TACTICAL"
            and mapping(snapshot.metadata.get("mountain")).get(
                "primary_collection_terminal_qualified") is False):
        # The same location can admit a bounded counter-fade without proving
        # that this primary's living leg has ended. Source supplies separate
        # collection proof; an advancing paired-gap stall cannot manufacture it.
        return "PRIMARY_LEG_BREATHES_THROUGH_TACTICAL_EDGE"
    return None


def ordinary_profit_hold_reason(
    position: Mapping[str, Any], snapshot: MarketSnapshot, reason: str,
) -> str | None:
    """Compatibility name for the all-strategy-sale holding guard."""
    return strategy_exit_hold_reason(position, snapshot, reason)


def physical_management_evidence(
    position: Mapping[str, Any], snapshot: MarketSnapshot,
) -> dict[str, Any]:
    """Current held-direction evidence, independent of the lagging arc label.

    A return can already be advancing toward/through its first EMA9 reclaim
    while the historical outgoing arc is still the canonical owner. Neither
    contact, an old travelled distance, nor a green option quote proves that
    the return is complete. Conversely, a flat frame is not proof of advance.
    All observations here belong to this exact captured physical frame.
    """
    md = snapshot.metadata
    geometry = mapping(md.get("current_geometry"))
    probe = mapping(md.get("release_probe"))
    mountain = mapping(md.get("mountain"))
    diagnostics = mapping(mountain.get("diagnostics"))
    heist = mapping(md.get("heist"))
    side = as_side(position.get("side"))
    sign = 1 if side is Side.YES else -1
    btc = number(geometry.get("btc_price", probe.get("btc")))
    ema9 = number(geometry.get("ema9", probe.get("ema9")))
    scale = max(1.0, number(geometry.get("range60", probe.get("range60"))) or 1.0)
    epoch = number(geometry.get("epoch_ms", md.get("geometry_last_epoch_ms")))
    current = bool(side is not None and md.get("physical_current") is not False
                   and btc is not None and ema9 is not None
                   and (epoch is None or current_source_is_fresh(snapshot, epoch,
                        max_age_seconds=number(md.get("geometry_max_source_age_seconds")) or 5.0)))
    owner = as_side(mountain.get("owner_side")) or as_side(probe.get("arc_side"))
    release_side = as_side(rack_context(snapshot).get("confirmed_release_side"))
    micro = [number(geometry.get(key)) for key in
             ("micro_slope3s", "micro_slope6s", "micro_slope9s")]
    short_motion = number(geometry.get("btc_change6"))
    if short_motion is None:
        short_motion = number(geometry.get("btc_change9"))
    medium_motion = number(geometry.get("btc_change30"))
    long_motion = number(geometry.get("btc_change60"))
    short_signed = short_motion * sign if short_motion is not None else None
    medium_signed = medium_motion * sign if medium_motion is not None else None
    long_signed = long_motion * sign if long_motion is not None else None
    price_signed = (btc - ema9) * sign if btc is not None and ema9 is not None else None
    price_eps = max(.02, .005 * scale)
    ema_eps = max(.002, .0005 * scale)
    micro_held = sum(value is not None and value * sign > ema_eps for value in micro)
    micro_adverse = sum(value is not None and value * sign < -ema_eps for value in micro)
    short_side = as_side(probe.get("short_struct_side"))
    medium_side = as_side(probe.get("medium_struct_side"))
    micro_side = as_side(probe.get("micro_side"))
    expanding = (mountain.get("strong_active_release") is True
                 or str(probe.get("arc_phase", geometry.get("arc_phase", ""))).upper()
                 in ("EXPANDING", "BUILDING", "ACCELERATING"))
    opposite_expansion = bool(current and owner is not None and owner is not side
        and expanding and short_side is not None and short_side is not side
        and (micro_side is not None and micro_side is not side or micro_adverse >= 2)
        and price_signed is not None and price_signed < -max(1.0, .05 * scale))
    accepted_opposite = bool(release_side is not None and release_side is not side)
    hard_adverse = bool(opposite_expansion and (accepted_opposite or
        (medium_side is not None and medium_side is not side
         and mountain.get("strong_active_release") is True)))
    # `spent_edge` is an entry-location flag meaning the old return has
    # already reached EMA9; it is not a held-leg terminal classifier. The
    # qualified terminal detector instead proves the owned next mature edge
    # with its present stall/failed extension and excludes active expansion.
    terminal = bool(current and owner is side
        and mountain.get("terminal_evidence_qualified") is True
        and mountain.get("strong_active_release") is not True)
    legacy_collection_terminal = bool(terminal and (position_role(position) == "TACTICAL"
        or mountain.get("primary_collection_terminal_qualified") is not False))
    mission = mission_collection_evidence(position, snapshot)
    collection_terminal = bool(current and mission["collection_qualified"]
        if mission["scope_enforced"] else legacy_collection_terminal)
    advancing_return = bool(current and not hard_adverse and not terminal
        and short_signed is not None and short_signed > price_eps
        and medium_signed is not None and medium_signed > price_eps)
    deep_adverse_break = bool(current and price_signed is not None
        and price_signed < -max(2., .12 * scale) and micro_adverse >= 2
        and short_signed is not None and short_signed < -max(2., .12 * scale)
        and medium_signed is not None and medium_signed < -max(3., .20 * scale))
    internal_breath = bool(current and owner is side and short_side is side
                          and not deep_adverse_break and not hard_adverse and not terminal)
    # A first short pullback/weak patch need not end the living parent leg.
    # Affirmative current medium structure can support that breath even while
    # the short interval turns against it. A verified terminal or hard release
    # remains independent exit authority; an EMA cross alone supplies neither.
    supported_pullback = bool(current and owner is side and medium_side is side
                              and not deep_adverse_break and not hard_adverse and not terminal)
    context = rack_context(snapshot)
    release_breath = bool(current and context.get("custody_tool") == "RELEASE_WATCHER"
        and release_side is side and not hard_adverse and not terminal and not deep_adverse_break
        and medium_signed is not None and medium_signed > price_eps
        and (long_signed is not None and long_signed > price_eps
             or medium_side is side or price_signed is not None and price_signed >= -price_eps))
    # Profit management belongs to this held lot's retained manager. A
    # handoff is an event, not a signal that must recur on each ordinary
    # pullback. Keep the old recovery-support predicate separate below:
    # this correction does not redesign Lazarus qualification/restoration.
    retained_release_breath = bool(current and context.get("custody_tool") == "RELEASE_WATCHER"
        and not accepted_opposite and not hard_adverse and not terminal and not deep_adverse_break
        and medium_signed is not None and medium_signed > price_eps
        and (long_signed is not None and long_signed > price_eps
             or medium_side is side or price_signed is not None and price_signed >= -price_eps))
    initial_btc = number(mapping(entry_metadata(position).get("entry_geometry")).get("btc_price"))
    progress_since_entry = (btc - initial_btc) * sign if btc is not None and initial_btc is not None else None
    # An anticipatory incoming leg can already have made actual post-entry
    # progress while the outgoing canonical owner has not changed. One flat
    # six-second sample does not erase observed 30/60-second continuation.
    # Neither old pre-entry travel nor a favorable option quote supplies this
    # proof; current physical location and post-entry progress are required.
    advancing_leg_pause = bool(current and not accepted_opposite and not hard_adverse
        and not terminal and not deep_adverse_break
        and progress_since_entry is not None and progress_since_entry > price_eps
        and medium_signed is not None and medium_signed > price_eps
        and long_signed is not None and long_signed > price_eps
        and price_signed is not None and price_signed >= -max(2., .12 * scale))
    living_leg = bool(current and not terminal and not hard_adverse and owner is side
        and (internal_breath or supported_pullback or (price_signed is not None and price_signed >= -price_eps
             and (micro_held >= 1 or micro_side is side)
             and (short_signed is None or short_signed >= -price_eps))))
    primary_edge_breath = bool(current and terminal and not collection_terminal
        and (not mission["scope_enforced"] or mission["purpose"] in ("MAIN_CONTRACT", "ARC_RETURN")
             and mission["parent_supported"])
        and not accepted_opposite and not hard_adverse and not deep_adverse_break
        and medium_signed is not None and medium_signed > price_eps
        and (long_signed is not None and long_signed > price_eps
             or medium_side is side or price_signed is not None and price_signed >= -price_eps))
    # Native weakness may occur inside the held parent or return mission.
    # It cannot create a new profit floor behind the scoped collection guard.
    # Existing committed floors and direct structural exits remain separate.
    weak = bool(current and (collection_terminal or
        not mission["scope_enforced"] and deep_adverse_break))
    mission_breath = bool(current and mission["scope_enforced"] and mission["valid"]
        and mission["current"] and not mission["collection_qualified"]
        and not mission["parent_invalidated"] and not accepted_opposite and not hard_adverse
        and (mission["parent_supported"] or mission["prior_cross_hold"]
             or mission["scope_status"] == "FROZEN_RETURN_DESTINATION"
                and progress_since_entry is not None and progress_since_entry > price_eps
                and medium_signed is not None and medium_signed > price_eps))
    swing = mapping(md.get("recovery_swing_terrain"))
    swing_time = number(swing.get("observed_ts"))
    alternating = bool(swing.get("active") is True and swing_time is not None
                       and current_source_is_fresh(snapshot, swing_time * 1000., max_age_seconds=5.))
    credible_terrain = bool(current and (alternating or heist.get("qualified_box") is True))
    arc_age = number(geometry.get("arc_age_sec", diagnostics.get("current_age_s")))
    terrain_replaced = bool(current and not credible_terrain and not advancing_return
        and owner is not None and owner is not side and arc_age is not None and arc_age >= 60.
        and short_side is not None and short_side is not side
        and medium_side is not None and medium_side is not side
        and price_signed is not None and price_signed < -max(2., .10 * scale)
        and short_signed is not None and short_signed < -price_eps and micro_adverse >= 2
        and medium_signed is not None and medium_signed < -max(2., .10 * scale)
        and long_signed is not None and long_signed < -max(3., .20 * scale))
    # Target evidence, when supplied, must be verified for the exact held
    # contract. Display-only strikes and a cheap binary bid do not qualify.
    target = mapping(md.get("verified_settlement_geometry"))
    target_price = number(target.get("target"))
    target_time = number(target.get("observed_ts"))
    seconds_left = float(position.get("close_ts", snapshot.now_ts)) - snapshot.now_ts
    terminal_impossible = bool(current and target.get("verified") is True
        and target.get("ticker") == position.get("ticker")
        and target_time is not None and 0 <= snapshot.now_ts - target_time <= 3
        and target_price is not None and 0 < seconds_left <= 60
        and (btc - target_price) * sign < -max(8.0, .75 * scale))
    return {
        "physical_current": current, "source_epoch_ms": epoch,
        "continuity_generation": md.get("geometry_continuity_generation", 0),
        "held_side": side.value if side else None, "owner_side": owner.value if owner else None,
        "btc": btc, "ema9": ema9, "range60": scale,
        "held_price_minus_ema9": price_signed,
        "held_btc_change_short": short_signed, "held_btc_change30": medium_signed,
        "held_btc_change60": long_signed, "held_micro_count": micro_held,
        "adverse_micro_count": micro_adverse,
        "ordinary_internal_breath": internal_breath, "deep_adverse_break": deep_adverse_break,
        "ordinary_supported_pullback": supported_pullback,
        "release_owned_pullback_breath": release_breath,
        "retained_release_profit_breath": retained_release_breath,
        "advancing_leg_pause": advancing_leg_pause,
        "primary_leg_breathes_through_tactical_edge": primary_edge_breath,
        "mission_leg_breathing": mission_breath,
        "prior_cross_holding_qualified": mission["prior_cross_hold"],
        "mission_collection": mission,
        "held_btc_progress_since_entry": progress_since_entry,
        "advancing_return": advancing_return, "living_leg": living_leg,
        "held_side_supported": advancing_return or living_leg or release_breath,
        "healthy_leg_breathing": bool((advancing_return or living_leg or release_breath
                                  or retained_release_breath or advancing_leg_pause
                                  or primary_edge_breath or mission_breath)
                                  and not (mission["scope_enforced"] and collection_terminal)),
        "weak_or_spent": weak, "verified_terminal": collection_terminal,
        "entry_terminal_qualified": terminal,
        "accepted_opposing_transfer": accepted_opposite,
        "hard_adverse_release": hard_adverse, "terminal_impossibility": terminal_impossible,
        "credible_recovery_terrain": credible_terrain,
        "recovery_terrain_physically_replaced": terrain_replaced,
        "alternating_recent_arcs": alternating,
        "recent_swing_evidence": dict(swing),
        "qualified_recovery_box": heist.get("qualified_box") is True,
        "entry_candle": entry_candle_evidence(position, snapshot),
        "ema9_ema30_cross_context": dict(mapping(md.get("ema9_ema30_cross_context"))),
    }


def _sideways_no_terrain(snapshot: MarketSnapshot | None) -> bool:
    """Existing detector evidence for the operator-authorized flat/no-terrain floor.

    No new sideways threshold is invented here.  The rule activates only when
    the existing Commander/Tool-Rack ownership is UNKNOWN (no terrain owns the
    market) and the existing Heist diagnostics already say the observed motion
    is sideways enough.
    """
    if snapshot is None:
        return False
    md = mapping(snapshot.metadata)
    strategy = mapping(md.get("commander_strategy"))
    rack = mapping(md.get("tool_rack"))
    territory = str(strategy.get("owned_territory") or rack.get("owned_territory") or "UNKNOWN").upper()
    heist = mapping(md.get("heist"))
    diagnostics = mapping(heist.get("diagnostics"))
    return bool(territory in ("", "UNKNOWN") and diagnostics.get("sideways_enough") is True)


def floor_policy(config: Any, *, position: Mapping[str, Any] | None = None,
                 snapshot: MarketSnapshot | None = None) -> dict[str, Any]:
    """Tool policy sent as explicit, mechanical instructions to execution.

    The executor evaluates the supplied mechanical instructions; it never
    diagnoses a healthy leg or terminal. Numeric profit milestones do not
    create physical collection authority. Existing committed floors and
    accepted exit obligations remain binding and can never be loosened here.
    """
    evidence = (physical_management_evidence(position, snapshot)
                if position is not None and snapshot is not None else {})
    if getattr(config, "edge_only_custody", False):
        sideways_no_terrain = _sideways_no_terrain(snapshot)
        if sideways_no_terrain:
            # Explicit operator authorization 2026-11-01: in a sideways market
            # with no owned terrain, do not grant runner-style giveback.  If the
            # existing structural top has not already collected the position,
            # +100% executable ROI receives one tight 3% peak-bid trail.  No
            # additional 5%/2% terrain-independent runner bands are injected.
            return {
                "arm_roi": 999.0,
                "trail_fraction": .03,
                "min_age_s": 0.0,
                "immediate_arm_roi": 1.0,
                "first_arm_allowed": False,
                "first_arm_from_current_bid": True,
                "roi_trail_tiers": [[1.0, .03]],
                "tighten_armed_to": None,
                "profit_protection_state": "SIDEWAYS_NO_TERRAIN_100_PERCENT_3_PERCENT_PEAK_LOCK",
                "profit_policy_revision": "OPERATOR_AUTHORIZED_SIDEWAYS_NO_TERRAIN_100_3_V1",
                "management_evidence": evidence,
            }
        # Outside the specifically authorized sideways/no-terrain case, retain
        # the previously authorized Mountain floor schedule unchanged.
        return {
            "arm_roi": 999.0,
            "trail_fraction": .05,
            "min_age_s": 0.0,
            "immediate_arm_roi": 1.0,
            "first_arm_allowed": False,
            "first_arm_from_current_bid": True,
            "roi_trail_tiers": [[1.0, .05], [1.5, .03], [6.0, .02]],
            "tighten_armed_to": None,
            "profit_protection_state": "MOUNTAIN_EDGE_TO_EDGE_WITH_100_PERCENT_PEAK_LOCK",
            "profit_policy_revision": "MOUNTAIN_EDGE_100_5_150_3_V2_RESTORED",
            "management_evidence": evidence,
        }
    after_entry_candle = (mapping(evidence.get("entry_candle")).get("entry_candle_complete")
                          if position is not None and snapshot is not None else False)
    mission = mapping(evidence.get("mission_collection"))
    conditional_contract_profit = mission.get("collection_authority") == ARC_CONTRACT_PROFIT_REASON
    physical_collection = bool(after_entry_candle and evidence.get("physical_current")
                               and evidence.get("weak_or_spent") and not conditional_contract_profit)
    role = position_role(position or {})
    base_band = .05 if role == "TACTICAL" else config.floor_trail_fraction
    # Earned executable profit is protected mechanically even while the physical
    # leg remains alive. Structure controls runway and may tighten protection;
    # it no longer decides whether a +100%/+150% winner receives any floor.
    tiers = [[1.0, .05], [1.5, .03], [6.0, .02]]
    ordinary_arm = physical_collection
    state = ("PRESERVE_COMMITTED_FLOOR" if position is not None and position.get("floor_bid") is not None
             else "PROFITABLE_CONTRACT_INTERRUPTION_RECHECK_REQUIRED" if conditional_contract_profit
             else "ENTRY_CANDLE_BREATHING_UNTIL_100_PERCENT_PEAK_LOCK" if not after_entry_candle
             else "CURRENT_PHYSICAL_COLLECTION_PLUS_PEAK_LOCK" if physical_collection
             else "LIVING_LEG_BREATHING_WITH_100_PERCENT_PEAK_LOCK" if evidence.get("healthy_leg_breathing")
             else "AWAIT_CURRENT_PHYSICAL_COLLECTION_WITH_100_PERCENT_PEAK_LOCK")
    return {
        "arm_roi": config.floor_arm_roi,
        "trail_fraction": base_band,
        "min_age_s": config.floor_min_age_s,
        "immediate_arm_roi": 1.0,
        "first_arm_allowed": ordinary_arm,
        "first_arm_from_current_bid": True,
        "roi_trail_tiers": tiers,
        "tighten_armed_to": .03 if physical_collection and evidence.get("verified_terminal") else None,
        "profit_protection_state": state,
        "profit_policy_revision": "PID19832_EARNED_PEAK_LOCK_100_5_150_3",
        "management_evidence": evidence,
    }




def runner_harvest_update(
    state_store: dict[str, dict[str, Any]],
    position: Mapping[str, Any],
    snapshot: MarketSnapshot,
    *,
    eligible: bool,
    label: str,
    min_uptick: float = 0.01,
    harvest_downtick: float = 0.01,
) -> dict[str, Any]:
    """Track two distinct physical slowdowns, then harvest the next bid uptick.

    This is deliberately custody-only.  It never creates an entry, changes the
    parent direction, or declares a slowdown from elapsed time.  A slowdown is
    counted only from the current Mountain detector while the held side is the
    living EMA9 owner.  Slowdown #2 is not enough by itself to sell: the held
    contract must first print a favorable executable-bid uptick, after which a
    real downtick from that new peak earns collection.
    """
    key = str(position.get("opportunity_id") or position.get("position_id") or "")
    side = as_side(position.get("side"))
    if not eligible or not key or side is None:
        if key:
            state_store.pop(key, None)
        return {"eligible": False, "label": label, "exit_now": False}

    mountain = mapping(snapshot.metadata.get("mountain"))
    owner = as_side(mountain.get("owner_side"))
    slowdown = mapping(mountain.get("slowdown"))
    slowdown_now = bool(owner is side and slowdown.get("observed") is True)
    source_ms = number(mountain.get("source_ms"))
    bid = snapshot.bid_for(side)

    # Runner custody is a *winner-development* privilege, never a mechanism
    # for managing a losing position.  The prior implementation could count
    # two slowdowns immediately after a Rail entry and harvest below basis
    # (PID21864 #10).  Do not start the runner state machine until executable
    # peak/current value has first developed at least +65% gross.  Before that
    # point ordinary structural custody/protection remains in force.
    entry_price = number(position.get("entry_price"))
    recorded_peak = number(position.get("peak_bid"))
    peak_for_gate = max([v for v in (recorded_peak, bid) if v is not None], default=None)
    peak_roi = ((peak_for_gate / entry_price) - 1.0
                if entry_price not in (None, 0.0) and peak_for_gate is not None else None)
    if peak_roi is None or peak_roi < 0.65:
        state_store.pop(key, None)
        return {
            "eligible": False, "label": label, "exit_now": False,
            "runner_profit_gate": 0.65, "peak_roi": peak_roi,
            "reason": "RUNNER_AWAIT_MEANINGFUL_PROFIT_DEVELOPMENT",
        }

    state = state_store.setdefault(key, {
        "slowdown_count": 0,
        "in_slowdown": False,
        "resumed_after_first": False,
        "harvest_armed": False,
        "uptick_started": False,
        "harvest_peak_bid": None,
        "harvest_baseline_bid": None,
        "last_bid": None,
        "last_source_ms": None,
    })

    # Only a new physical observation may start/end a slowdown episode. Quote
    # updates can still advance the post-second-slowdown harvest peak below.
    new_physical = source_ms is None or state.get("last_source_ms") != source_ms
    if new_physical:
        if slowdown_now and not state["in_slowdown"]:
            if state["slowdown_count"] == 0:
                state["slowdown_count"] = 1
            elif state.get("resumed_after_first"):
                state["slowdown_count"] = 2
                state["harvest_armed"] = True
                state["harvest_baseline_bid"] = bid
            state["in_slowdown"] = True
        elif not slowdown_now and state["in_slowdown"]:
            state["in_slowdown"] = False
            if state["slowdown_count"] >= 1:
                state["resumed_after_first"] = True
        state["last_source_ms"] = source_ms

    exit_now = False
    exit_reason = None
    if state["harvest_armed"] and bid is not None:
        last_bid = number(state.get("last_bid"))
        baseline = number(state.get("harvest_baseline_bid"))
        peak = number(state.get("harvest_peak_bid"))
        if not state["uptick_started"]:
            reference = baseline if baseline is not None else last_bid
            if reference is not None and bid >= reference + min_uptick:
                state["uptick_started"] = True
                state["harvest_peak_bid"] = bid
        else:
            if peak is None or bid > peak:
                state["harvest_peak_bid"] = bid
                peak = bid
            elif peak - bid >= harvest_downtick:
                exit_now = True
                exit_reason = f"{label}_SECOND_SLOWDOWN_UPTICK_PEAK_HARVEST"
        state["last_bid"] = bid
    elif bid is not None:
        state["last_bid"] = bid

    return {
        "eligible": True,
        "label": label,
        "slowdown_count": int(state["slowdown_count"]),
        "in_slowdown": bool(state["in_slowdown"]),
        "resumed_after_first": bool(state["resumed_after_first"]),
        "harvest_armed": bool(state["harvest_armed"]),
        "uptick_started": bool(state["uptick_started"]),
        "harvest_baseline_bid": state.get("harvest_baseline_bid"),
        "harvest_peak_bid": state.get("harvest_peak_bid"),
        "current_bid": bid,
        "exit_now": exit_now,
        "exit_reason": exit_reason,
        "ordinary_percent_floor_bypassed": False,
        "runner_profit_gate": 0.65,
        "peak_roi": peak_roi,
        "first_slowdown_is_hold": True,
        "second_slowdown_arms_harvest_not_exit": True,
    }


def apply_runner_floor_bypass(policy: dict[str, Any], runner: Mapping[str, Any]) -> dict[str, Any]:
    """Runner/Leviathan status is descriptive and may not disable protection.

    Slowdowns, resumptions and post-slowdown peaks remain useful Commander
    evidence, but the +100/+150/+600 earned floor remains available regardless
    of custody label.
    """
    if runner.get("eligible") is True:
        policy = dict(policy)
        policy["runner_observation"] = dict(runner)
        policy["profit_protection_state"] = (
            str(policy.get("profit_protection_state") or "EARNED_PROFIT_PROTECTION")
            + "_RUNNER_EVIDENCE_ONLY"
        )
    return policy

def position_intent(
    *,
    tool: str,
    territory_id: str,
    lane: Lane,
    position: Mapping[str, Any],
    snapshot: MarketSnapshot,
    action: Action,
    reason: str,
    config: Any,
    metadata: Mapping[str, Any] | None = None,
) -> ToolIntent:
    policy = floor_policy(config, position=position, snapshot=snapshot)
    runner = mapping((metadata or {}).get("runner_harvest"))
    policy = apply_runner_floor_bypass(policy, runner)
    # No terrain-specific percentage-floor regime is allowed to replace the
    # approved earned +100/+150/+600 protection. Low-motion/parallel terrain
    # is harvested by Commander from Leg Ledger MFE evidence instead.
    scoped = mapping(mapping(policy.get("management_evidence")).get("mission_collection"))
    if (scoped.get("collection_authority") == ARC_CONTRACT_PROFIT_REASON
            and (action is Action.HOLD or reason in ORDINARY_PROFIT_EXIT_REASONS)):
        action, reason = Action.EXIT, ARC_CONTRACT_PROFIT_REASON
        metadata = {**(metadata or {}),
            "arc_contract_interruption": dict(mapping(scoped.get("contract_interruption")))}
    deferred_reason = strategy_exit_hold_reason(position, snapshot, reason) if action is Action.EXIT else None
    if deferred_reason:
        metadata = {**(metadata or {}), "deferred_strategy_exit_reason": reason,
                    **({"deferred_ordinary_exit_reason": reason}
                       if reason in ORDINARY_PROFIT_EXIT_REASONS else {})}
        action, reason = Action.HOLD, deferred_reason
    if (action is Action.HOLD and reason == "MOUNTAIN_CARRY_LIVING_LEG"
            and scoped.get("scope_enforced")
            and (not scoped.get("valid") or not scoped.get("current")
                 or scoped.get("scope_status") != "ACTIVE")):
        # A current market or matching side is not a verified held leg. Keep
        # the HOLD, but do not publish an UNKNOWN/invalidated scope as living.
        metadata = {**(metadata or {}), "unverified_held_leg_reason": scoped.get("reason")}
        reason = "MOUNTAIN_HELD_LEG_NOT_CURRENTLY_VERIFIED"
    # Heist collection remains structural/adaptive Commander evidence; no
    # fixed +50/+65 floor schedule is injected here.
    return ToolIntent(
        tool=tool,
        territory_id=territory_id,
        lane=lane,
        side=as_side(position.get("side")),
        action=action,
        opportunity_id=position.get("opportunity_id"),
        max_price=None,
        size_tier=None,
        reason=reason,
        source_time=snapshot.now_ts,
        metadata={"floor_policy": policy,
                  **(metadata or {})},
    )
