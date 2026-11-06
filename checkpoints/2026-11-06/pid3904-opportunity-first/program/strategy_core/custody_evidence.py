"""Commander custody evidence.

Pure evidence synthesis for a held PAPER position.  Specialists may still
publish HOLD/EXIT opinions, but this module summarizes current physical
ownership, TP context, and last-3/5 leg economics for OneCommander.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Any, Mapping

from strategy_core.types import MarketSnapshot, Side
from strategy_core.commander_candidates import current_mountain_terminal
from strategy_core.leg_ledger import validated_contract_opportunities
from strategy_core.source_freshness import current_source_is_fresh


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _side(value: Any) -> str | None:
    if isinstance(value, Side):
        return value.value
    text = str(value).upper() if value is not None else ""
    return text if text in ("YES", "NO") else None


def build_custody_evidence(position: Mapping[str, Any], snapshot: MarketSnapshot) -> dict[str, Any]:
    held_side = _side(position.get("side"))
    side_enum = Side(held_side) if held_side in ("YES", "NO") else None
    bid = snapshot.bid_for(side_enum) if side_enum is not None else None
    entry = _num(position.get("entry_price"))
    roi = (bid / entry - 1.0) if bid is not None and entry not in (None, 0) else None

    strategy = _map(snapshot.metadata.get("commander_strategy"))
    mountain = _map(snapshot.metadata.get("mountain"))
    heist = _map(snapshot.metadata.get("heist"))
    echo = _map(snapshot.metadata.get("leg_echo"))
    tp = _map(snapshot.metadata.get("tp_geometry"))
    mission = _map(snapshot.metadata.get("mission_context"))
    parent = _map(mission.get("parent"))
    parent_status = str(parent.get("status") or "").upper()
    parent_side = _side(parent.get("side")) if parent_status not in {"COMPLETED", "INVALIDATED"} else None
    structure = _map(mountain.get("parent_structure"))
    structural_parent = (_side(structure.get("parent_side"))
                         if structure.get("parent_terminal_ready") is not True else None)

    owner_side = parent_side or structural_parent or _side(strategy.get("owned_side")) or _side(mountain.get("owner_side"))
    release_side = _side(snapshot.metadata.get("release_candidate_side"))
    opposing_release = bool(snapshot.metadata.get("release_in_progress") is True
                            and release_side is not None and held_side is not None
                            and release_side != held_side)

    entry_meta = _map(position.get("entry_metadata"))
    entry_family = str(entry_meta.get("commander_candidate_family") or
                       position.get("territory_id") or "").upper()
    entry_mission = _map(entry_meta.get("mission"))
    role = str(position.get("position_role") or entry_meta.get("position_role") or "PRIMARY").upper()
    main_parent_position = bool(role == "PRIMARY" and (
        str(position.get("tool") or "").upper() in {"RAIL", "RELEASE_WATCHER"}
        or entry_family == "MOUNTAIN_CONTRACT_LEG"
        or entry_mission.get("purpose") == "MAIN_CONTRACT"))

    # PID3904 #4/#6: the held owner was taken from the MAIN mission parent,
    # while the terminal flag came from a different, much smaller child arc.
    # Keep ownership and collection evidence on the same actual physical leg.
    # An authenticated active aligned parent supplies its own geometry even
    # when that geometry says the parent has not reached a terminal edge.
    current_geometry = _map(snapshot.metadata.get("current_geometry"))
    source_ms = _num(current_geometry.get("epoch_ms"))
    generation = snapshot.metadata.get("geometry_continuity_generation")
    parent_geometry = _map(parent.get("geometry"))
    aligned_main_parent = bool(main_parent_position and parent.get("id")
        and parent_status == "ACTIVE" and parent.get("invalidated") is not True
        and parent.get("supported") is True and parent_side == held_side)
    parent_geometry_current = bool(aligned_main_parent and source_ms is not None
        and snapshot.metadata.get("physical_current") is True
        and mission.get("current") is True and parent_geometry.get("current") is True
        and _num(mission.get("source_ms")) == source_ms
        and _num(parent.get("source_ms")) == source_ms
        and _num(parent_geometry.get("source_ms")) == source_ms
        and type(generation) is int and generation >= 0
        and mission.get("continuity_generation") == generation
        and parent.get("continuity_generation") == generation
        and parent_geometry.get("continuity_generation") == generation
        and parent_geometry.get("current_arc_id") == parent.get("id")
        and _side(parent_geometry.get("owner_side")) == held_side
        and all(_num(current_geometry.get(raw)) is not None
                and _num(current_geometry.get(raw)) > 0
                and _num(parent_geometry.get(measured)) == _num(current_geometry.get(raw))
                for measured, raw in (("current_btc", "btc_price"),
                                      ("current_ema9", "ema9"), ("current_ema30", "ema30")))
        and current_source_is_fresh(snapshot, source_ms, max_age_seconds=3.0))
    collection_mountain = (parent_geometry if parent_geometry_current else {}) if main_parent_position else mountain
    collection_scope = ("CURRENT_MAIN_PARENT" if parent_geometry_current else "MAIN_PARENT_UNVERIFIED"
                        ) if main_parent_position else "CURRENT_LOCAL_LEG"
    collection_owner_side = _side(collection_mountain.get("owner_side"))

    # Collection is intentionally stricter than admission.  The detector
    # exposes primary_collection_terminal_qualified specifically so an entry
    # edge/brief stall cannot also cut a healthy winner early. Older fixtures
    # without the field retain the prior terminal behavior for compatibility.
    collection_signal = collection_mountain.get("primary_collection_terminal_qualified")
    if collection_signal is None:
        collection_signal = collection_mountain.get("terminal_evidence_qualified")
    terminal = bool(
        collection_signal is True
        and collection_mountain.get("mature_edge") is True
        and collection_mountain.get("edge_window_active") is True
    )
    # Entry evidence cannot immediately become exit evidence.  A structural
    # terminal collection requires a terminal extreme observed after entry,
    # not the same/stale edge that existed when the lot was purchased.
    entry_time = _num(position.get("entry_time"))
    edge_id = str(collection_mountain.get("edge_id") or "")
    entry_evidence = _map(entry_meta.get("commander_physical_evidence"))
    entry_edge_id = str(entry_evidence.get("edge_id") or "")
    same_entry_edge = bool(edge_id and entry_edge_id and edge_id == entry_edge_id)
    edge_source_ms = None
    if ":" in edge_id:
        try:
            edge_source_ms = float(edge_id.rsplit(":", 1)[1])
        except (TypeError, ValueError):
            edge_source_ms = None
    terminal_newer_than_entry = bool(
        entry_time is None
        or edge_source_ms is None
        or edge_source_ms > entry_time * 1000.0
    )
    if main_parent_position:
        actual_extreme_ms = _num(collection_mountain.get("edge_extreme_ms"))
        terminal_newer_than_entry = bool(entry_time is not None and edge_source_ms is not None
            and math.isfinite(edge_source_ms) and source_ms is not None and actual_extreme_ms is not None
            and edge_id.rsplit(":", 1)[0] == str(parent.get("id"))
            and abs(actual_extreme_ms - edge_source_ms) < 1.0
            and entry_time * 1000.0 < actual_extreme_ms <= source_ms)
    held_terminal = bool(
        terminal and terminal_newer_than_entry and not same_entry_edge
        and owner_side is not None and owner_side == held_side
        and collection_owner_side == held_side
    )

    heist_far_edge = bool(
        heist.get("qualified_box") is True and held_side is not None and (
            held_side == "YES" and heist.get("at_upper_edge") is True
            or held_side == "NO" and heist.get("at_lower_edge") is True
        )
    )

    # Quote-level research from comparable physical legs.  Each excursion has
    # its own exact ticker basis; old mixed-contract scalar ROI is untrusted.
    # One long leg with several rollover contracts still contributes one leg
    # to the history count, using its median of independently valid returns.
    # These top-of-book observations do not prove full-lot executable fills.
    potential_rois = []
    historical_opportunities = []
    excluded_history_rows = 0
    for row in echo.get("completed_comparable_legs") or ():
        if not isinstance(row, Mapping):
            continue
        opportunities = validated_contract_opportunities(row, held_side)
        if opportunities:
            historical_opportunities.extend(opportunities)
            potential_rois.append(median(opportunity["potential_roi_from_best_observed_basis"]
                                         for opportunity in opportunities))
        else:
            excluded_history_rows += 1
    median_mfe = median(potential_rois) if potential_rois else None
    low_motion_history = bool(len(potential_rois) >= 3 and median_mfe is not None and .35 <= median_mfe <= .80)
    large_directional_history = bool(len(potential_rois) >= 3 and median_mfe is not None and median_mfe > .80)

    age_ratio = _num(echo.get("live_age_ratio"))
    amplitude_ratio = _num(echo.get("live_amplitude_ratio"))
    comparable_developing = bool(
        owner_side == held_side
        and ((age_ratio is not None and age_ratio < 1.0)
             or (amplitude_ratio is not None and amplitude_ratio < 1.0))
    )
    slowdown = _map(mountain.get("slowdown"))
    stalled = bool(mountain.get("stall") is True or mountain.get("hesitation") is True
                   or slowdown.get("observed") is True)

    # Operator-authorized high-profit skim: ordinary Mountain / rollover winners
    # may collect while the exact full-lot executable bid is still sitting at
    # the already-recorded +100% (or better) peak and the living leg stalls.
    # No new timer or arbitrary near-peak band is invented here: `stall` is the
    # existing physical hover evidence and equality to the executor-observed
    # peak keeps this strictly "at the top". Confirmed/strong Release custody
    # remains excluded so monster runners are not choked by this ordinary rule.
    exit_mark = _map(snapshot.metadata.get("paper_exit_mark"))
    full_lot_bid = (_num(exit_mark.get("full_lot_bid"))
                    if exit_mark.get("current") is True
                    and exit_mark.get("full_quantity_visible") is True else None)
    peak_bid = _num(position.get("peak_bid"))
    floor_bid = _num(position.get("floor_bid"))
    peak_roi = (peak_bid / entry - 1.0) if peak_bid is not None and entry not in (None, 0) else None
    ordinary_mountain = bool(
        str(position.get("tool") or "").upper() == "ONE_COMMANDER_PRIMARY"
        and entry_family in ("MOUNTAIN_EDGE", "MOUNTAIN_CONTRACT_LEG")
    )
    peak_hover_signal = bool(mountain.get("stall") is True or mountain.get("hesitation") is True)
    exact_peak_hover = bool(
        ordinary_mountain
        and floor_bid is not None
        and peak_roi is not None and peak_roi >= 1.0
        and full_lot_bid is not None and peak_bid is not None
        and abs(full_lot_bid - peak_bid) <= 1e-12
        and peak_hover_signal
        and mountain.get("strong_active_release") is not True
        and not opposing_release
    )

    # PID3860 operator refinement: prefer a *current* fee-positive full-lot
    # harvest over giving back a stalled, non-breakout excursion.  This is not
    # a profit-target timer and cannot cash out the first wobble.  A Mountain
    # needs an observed failed re-extension (which requires distinct retreat
    # and retest source observations), and a Heist needs repeatable bilateral
    # wall history and the reached opposite edge.  Neither a generic stall
    # nor a quoted prior peak constitutes sellable profit.
    territory = str(strategy.get("owned_territory") or "").upper()
    heist_diag = _map(heist.get("diagnostics"))
    genuine_repeated_heist = bool(
        territory == "MARKET_HEIST"
        and heist.get("qualified_box") is True
        and heist_diag.get("classic_qualified") is True
        and (_num(heist_diag.get("lower_visits")) or 0) >= 2
        and (_num(heist_diag.get("upper_visits")) or 0) >= 2
        and heist_far_edge
    )
    mature_failed_mountain = bool(
        territory == "ALTERNATING_MOUNTAIN"
        and ordinary_mountain
        and mountain.get("mature_edge") is True
        and mountain.get("edge_window_active") is True
        and mountain.get("failed_reextension") is True
    )
    mark_net = _num(exit_mark.get("net_after_fees"))
    current_quote_peak = bool(
        exit_mark.get("version") == "PAPER_REMAINING_EXIT_MARK_V1"
        and exit_mark.get("ticker") == snapshot.ticker
        and str(exit_mark.get("position_id")) == str(position.get("position_id"))
        and exit_mark.get("current") is True
        and exit_mark.get("full_quantity_visible") is True
        and mark_net is not None and mark_net > 0
        and peak_bid is not None and full_lot_bid is not None
        and abs(full_lot_bid - peak_bid) <= 1e-12
    )
    first_stall_not_enough = bool(
        mountain.get("failed_reextension") is True
        or genuine_repeated_heist and mountain.get("stall") is True
           and mountain.get("hesitation") is True
    )
    fee_positive_mature_hover = bool(
        snapshot.metadata.get("physical_current") is True
        and entry_time is not None and snapshot.now_ts - entry_time >= 30.0
        and current_quote_peak and first_stall_not_enough
        and (mature_failed_mountain or genuine_repeated_heist)
        and territory not in ("UP_RAIL", "DOWN_RAIL", "ROLLING_MOUNTAIN", "RELEASE_TRANSITION")
        and mountain.get("strong_active_release") is not True
        and snapshot.metadata.get("release_in_progress") is not True
        and not opposing_release
    )

    # PID14048: a source-observed mature Mountain can reach its executable
    # high-water bid *before* the physical stall becomes measurable. Do not
    # require the exact high and a later two-sided slowdown on the same tick.
    # The offer at collection is still the CURRENT full-lot executable bid;
    # a historical best bid is never treated as an actual exit price. Preserve
    # the first-wobble WAIT and the stronger running Rail/Release custody.
    geometry = _map(snapshot.metadata.get("current_geometry"))
    physical_parent_direction = _side(geometry.get("parent_direction"))
    held_motion_sign = 1.0 if held_side == "YES" else -1.0 if held_side == "NO" else 0.0
    btc_nine = _num(geometry.get("btc_change9"))
    ema_six = _num(geometry.get("ema9_change6"))
    confirmed_opposite_motion = bool(
        held_motion_sign
        and btc_nine is not None and ema_six is not None
        and btc_nine * held_motion_sign <= -5.0
        and ema_six * held_motion_sign <= -0.6
    )
    current_positive_near_peak = bool(
        exit_mark.get("version") == "PAPER_REMAINING_EXIT_MARK_V1"
        and exit_mark.get("ticker") == snapshot.ticker
        and str(exit_mark.get("position_id")) == str(position.get("position_id"))
        and exit_mark.get("current") is True
        and exit_mark.get("full_quantity_visible") is True
        and snapshot.quote_current is True
        and snapshot.can_sell(side_enum)
        and full_lot_bid is not None and peak_bid is not None and peak_bid > 0
        and full_lot_bid <= peak_bid + 1e-12
        and peak_bid - full_lot_bid <= 0.04 + 1e-12
        and full_lot_bid >= peak_bid * 0.92
        and mark_net is not None and mark_net > 0
    )
    mature_stall_near_peak = bool(
        snapshot.metadata.get("physical_current") is True
        and entry_time is not None and snapshot.now_ts - entry_time >= 30.0
        and ordinary_mountain and territory == "ALTERNATING_MOUNTAIN"
        and mountain.get("mature_edge") is True
        and mountain.get("edge_window_active") is True
        and mountain.get("stall") is True
        and peak_roi is not None and peak_roi >= 0.30
        and current_positive_near_peak and confirmed_opposite_motion
        and mountain.get("strong_active_release") is not True
        and snapshot.metadata.get("release_in_progress") is not True
        and not opposing_release
    )

    low_motion_mfe_reached = bool(
        low_motion_history and roi is not None and median_mfe is not None
        and roi + 1e-12 >= median_mfe and (stalled or heist_far_edge)
    )

    # Mountain-only custody reset: non-Mountain exit systems are paused.
    # The normal structural exit is the held Mountain leg's next genuine
    # terminal edge.  Earned executable floors remain objective protection in
    # paper_execution and are intentionally separate from this recommendation.
    if exact_peak_hover:
        recommendation, reason = "COLLECT", "COMMANDER_HIGH_PROFIT_PEAK_HOVER_COLLECT"
    elif fee_positive_mature_hover:
        recommendation, reason = "COLLECT", "COMMANDER_FEE_POSITIVE_MATURE_EXCURSION_HOVER"
    elif mature_stall_near_peak:
        recommendation, reason = "COLLECT", "COMMANDER_MATURE_STALL_CURRENT_PROFIT_NEAR_PEAK"
    elif main_parent_position and not parent_geometry_current:
        recommendation, reason = "HOLD", "COMMANDER_MAIN_PARENT_COLLECTION_UNVERIFIED"
    elif held_terminal:
        recommendation, reason = "COLLECT", "COMMANDER_MOUNTAIN_ONLY_HELD_LEG_TERMINAL_EDGE"
    elif comparable_developing or owner_side == held_side:
        recommendation, reason = "HOLD", "COMMANDER_MOUNTAIN_ONLY_LEG_STILL_ACTIVE"
    else:
        recommendation, reason = "HOLD", "COMMANDER_MOUNTAIN_ONLY_WAIT_FOR_TRUE_EDGE"

    return {
        "version": "COMMANDER_CUSTODY_EVIDENCE_V1",
        "execution_authority": False,
        "held_side": held_side,
        "current_bid": bid,
        "entry_price": entry,
        "current_roi": roi,
        "current_full_lot_bid": full_lot_bid,
        "executor_peak_bid": peak_bid,
        "executor_floor_bid": floor_bid,
        "executor_peak_roi": peak_roi,
        "exact_peak_hover_collect": exact_peak_hover,
        "fee_positive_mature_hover_collect": fee_positive_mature_hover,
        "mature_stall_near_peak_collect": mature_stall_near_peak,
        "mature_stall_near_peak_current_bid": full_lot_bid,
        "mature_stall_near_peak_opposing_motion": confirmed_opposite_motion,
        "fee_positive_current_mark": mark_net,
        "mature_failed_mountain": mature_failed_mountain,
        "genuine_repeated_heist": genuine_repeated_heist,
        "first_stall_not_enough": first_stall_not_enough,
        "current_owner_side": owner_side,
        "opposing_release": opposing_release,
        "held_leg_terminal": held_terminal,
        "collection_scope": collection_scope,
        "collection_owner_side": collection_owner_side,
        "collection_parent_id": parent.get("id") if main_parent_position else None,
        "collection_parent_geometry_current": parent_geometry_current,
        "terminal_newer_than_entry": terminal_newer_than_entry,
        "terminal_edge_source_ms": edge_source_ms,
        "entry_edge_id": entry_edge_id or None,
        "same_entry_edge": same_entry_edge,
        "heist_far_edge": heist_far_edge,
        "comparable_leg_count": len(potential_rois),
        "historical_opportunity_count": len(historical_opportunities),
        "historical_opportunities": historical_opportunities,
        "excluded_historical_leg_rows": excluded_history_rows,
        "historical_roi_aggregation": "MEDIAN_OF_LEG_MEDIANS_OF_EXACT_TICKER_QUOTE_OPPORTUNITIES",
        "historical_median_potential_roi": median_mfe,
        "low_motion_history_35_80": low_motion_history,
        "large_directional_history": large_directional_history,
        "live_age_ratio": age_ratio,
        "live_amplitude_ratio": amplitude_ratio,
        "tp": dict(tp),
        "recommendation": recommendation,
        "reason": reason,
    }
