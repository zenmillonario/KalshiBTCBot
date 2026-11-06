"""Mountain-only Commander entry candidates.

Last-resort PAPER reset requested 2026-10-31: every non-Mountain entry family is
paused.  Only two Commander-owned entry species exist:

1. MOUNTAIN_EDGE -- a genuine parent-scale top/bottom, return side, ask < 20c.
2. MOUNTAIN_CONTRACT_LEG -- the Mountain/Rolling-Mountain leg that current TP +
   comparable parent geometry says is likely to own the contract, ask < 40c,
   and only at a rollover/start-leg location or at the genuine edge that starts
   the favored bounce.  Never arbitrary mid-leg.

This module creates candidates only. OneCommander remains the sole strategy
authority and paper_execution remains the sole executor.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from strategy_core.directional_parent import directional_parent_evidence
from strategy_core.source_freshness import current_source_is_fresh
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent

MOUNTAIN_EDGE_MAX = 0.20
MOUNTAIN_CONTRACT_LEG_MAX = 0.40
# Operator-authorized 2026-11-01 narrow exception: when a genuine parent
# terminal coincides with the new-contract rollover and TP favors the return,
# the return side may be boarded at the start below 50c. This does not raise
# any ordinary Mountain/Rail/Heist/Release ceiling.
MOUNTAIN_ROLLOVER_TERMINAL_RETURN_MAX = 0.50
MOUNTAIN_ROLLOVER_TERMINAL_RETURN_WINDOW_S = 60.0
# Operator-authorized rollover continuation: when the same physical Mountain
# leg clearly began before the ticker boundary and remains young/live, the new
# contract may be boarded immediately in the first minute up to 55c. This is a
# location-specific opening allowance, never a generic Mountain price ceiling.
MOUNTAIN_ROLLOVER_CONTINUATION_MAX = 0.55
MOUNTAIN_ROLLOVER_CONTINUATION_WINDOW_S = 60.0
MOUNTAIN_ROLLOVER_MAX_AGE_S = 240.0
MOUNTAIN_ROLLOVER_REACH_FRACTION = 0.50
# Settlement runway is regime-aware, not a fixed late-contract prohibition.
# With sufficient recent opposite-direction Mountain history we compare required
# TP travel with demonstrated amplitude/speed at every entry.  The 5m value is
# only the conservative fallback when there is not enough comparable history.
MOUNTAIN_INSUFFICIENT_HISTORY_LATE_S = 300.0
MOUNTAIN_RETURN_REACH_FRACTION = 0.85
MOUNTAIN_RETURN_MIN_REFERENCES = 2
MOUNTAIN_SETTLEMENT_AVERAGE_WINDOW_S = 60.0
MOUNTAIN_ONLY_MODE = False
# PID19996: preserve the established parent's opening opportunity through the
# existing first-five-minute search.  A deferred premium opening returns to
# the already-authorized normal Rail value ceiling, never a wider allowance.
OPENING_RAIL_FISHING_WINDOW_S = 300.0
OPENING_RAIL_VALUE_MAX = 0.35


def _return_seed_floor_policy() -> dict[str, Any]:
    """Protect a real return without harvesting the first repricing beat.

    PID14312 #1 proved that a level-match return could double inside twelve
    seconds and then run to settlement.  The first 30 seconds therefore breathe;
    +100% protection remains after that, while an exceptional +150% same-window
    move may still arm immediately.
    """
    return {
        "arm_roi": 1.0,
        "trail_fraction": 0.05,
        "min_age_s": 30.0,
        "immediate_arm_roi": 1.5,
        "first_arm_allowed": True,
        "first_arm_from_current_bid": True,
        "roi_trail_tiers": [[1.5, 0.03], [6.0, 0.02]],
        "profit_policy_revision": "PID14312_RETURN_SEED_30S_BREATHING_100_5_150_3",
    }


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _side(value: Any) -> Side | None:
    if isinstance(value, Side):
        return value
    text = str(value).upper() if value is not None else ""
    return Side(text) if text in ("YES", "NO") else None


def _opposite(side: Side) -> Side:
    return Side.NO if side is Side.YES else Side.YES


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _source_time(snapshot: MarketSnapshot) -> float:
    value = snapshot.metadata.get("geometry_last_epoch_ms")
    try:
        source = float(value) / 1000.0
        if math.isfinite(source):
            return source
    except (TypeError, ValueError, OverflowError):
        pass
    return snapshot.now_ts



def _ask_below(snapshot: MarketSnapshot, side: Side, ceiling: float) -> bool:
    ask = _num(snapshot.ask_for(side))
    return bool(ask is not None and ask > 0 and ask < ceiling)

def _approved_size(snapshot: MarketSnapshot, *, family: str, side: Side) -> float:
    """Preserve the explicit $10/$15/$25 sizing doctrine conservatively."""
    ask = _num(snapshot.ask_for(side))
    if ask is None or ask <= 0:
        return 10.0
    if family == "MOUNTAIN_EDGE" and ask < MOUNTAIN_EDGE_MAX:
        return 25.0
    if ask < 0.30:
        return 15.0
    return 10.0


def _candidate(snapshot: MarketSnapshot, *, family: str, side: Side,
               max_price: float, reason: str, evidence: Mapping[str, Any],
               floor_policy_override: Mapping[str, Any] | None = None,
               size_override: float | None = None) -> ToolIntent:
    source_time = _source_time(snapshot)
    generation = snapshot.metadata.get("geometry_continuity_generation")
    identity = evidence.get("identity") or evidence.get("edge_id") or evidence.get("arc_id")
    if not identity:
        identity = f"{int(source_time * 1000)}:{generation}"
    return ToolIntent(
        tool="ONE_COMMANDER_PRIMARY",
        territory_id=str(family),
        lane=Lane.MAIN,
        side=side,
        action=Action.ENTER,
        opportunity_id=f"COMMANDER:{family}:{side.value}:{identity}",
        max_price=max_price,
        size_tier=(float(size_override) if size_override is not None else _approved_size(snapshot, family=family, side=side)),
        reason=reason,
        source_time=source_time,
        metadata={
            "commander_primary_candidate": True,
            "commander_candidate_family": family,
            "mountain_only_mode": True,
            "commander_price_policy": {
                "max_price": max_price,
                "basis": "MOUNTAIN_EXTREME_VALUE" if family == "MOUNTAIN_EDGE"
                         else "MOUNTAIN_CONTRACT_WINNING_LEG",
            },
            "physical_mission_id": f"COMMANDER:{family}:{side.value}:{identity}",
            "physical_renewal": {
                "independent": True,
                "renewal_kind": "NEW_ARC" if family == "MOUNTAIN_EDGE" else "CONTRACT_OWNERSHIP_LEG",
                "observed_at": source_time,
            },
            "commander_physical_evidence": dict(evidence),
            "floor_policy": dict(floor_policy_override or {
                # Operator-authorized Mountain profit protection restored.
                # Once the full-lot executable bid reaches +100% ROI, protect
                # it with the previously approved 5% peak-bid trail. Tighten
                # to 3% at +150% ROI and 2% at +600% ROI.
                "arm_roi": 1.0,
                "trail_fraction": 0.05,
                "min_age_s": 0.0,
                "immediate_arm_roi": 1.0,
                "first_arm_from_current_bid": True,
                "roi_trail_tiers": [[1.5, 0.03], [6.0, 0.02]],
                "profit_policy_revision": "OPERATOR_AUTHORIZED_100_5_150_3_600_2_RESTORE_V1",
            }),
            "position_role": "PRIMARY",
        },
    )


def current_mountain_terminal(mountain: Mapping[str, Any]) -> bool:
    """Require the *current* physical terminal window, not a stale armed latch.

    PID8868 proved that an older edge id could remain armed after the live arc
    resumed expanding.  A paid edge or structural collection therefore needs
    all three current detector statements at once.
    """
    return bool(
        mountain.get("terminal_evidence_qualified") is True
        and mountain.get("mature_edge") is True
        and mountain.get("edge_window_active") is True
    )


def _mountain_context(snapshot: MarketSnapshot) -> tuple[bool, bool, Mapping[str, Any], Mapping[str, Any], Side | None]:
    mountain = _map(snapshot.metadata.get("mountain"))
    parent = _map(mountain.get("parent_structure"))
    strategy = _map(snapshot.metadata.get("commander_strategy"))
    territory = str(strategy.get("owned_territory") or "")
    lifecycle = _gap_lifecycle(snapshot)
    gap_stage = str(lifecycle.get("stage") or "UNKNOWN")
    gap_side = _side(lifecycle.get("current_side"))
    persistent_gap = bool(
        gap_stage in {"MATURE", "ROLLING"}
        and gap_side is not None
        and lifecycle.get("continued_on_latest_cross_side") is not False
    )

    # PID8868 live packets often retained valid ALTERNATING_MOUNTAIN ownership
    # while the fresh-detector qualifier was false.  PID3296 exposed the mirror
    # failure: a long-lived MATURE/ROLLING EMA9 gap could be relabelled Rail/Heist
    # by a local child arc, causing the dormant specialist label to suppress the
    # only paid Mountain path.  In Mountain-only mode those labels are telemetry;
    # a persistent EMA9 gap keeps Mountain evaluation alive.  The gap clock does
    # NOT itself authorize a trade -- paid branches still require physical turn,
    # value and TP/runway proof below.
    mountain_owned = territory in {"ALTERNATING_MOUNTAIN", "ROLLING_MOUNTAIN"}
    explicit_other_owner = bool(territory and not mountain_owned and not persistent_gap)
    qualified = bool(
        not explicit_other_owner and (
            mountain.get("qualified_alternating_mountain") is True
            or territory == "ALTERNATING_MOUNTAIN"
            or persistent_gap
        )
    )
    rolling = bool(
        not explicit_other_owner and (
            territory == "ROLLING_MOUNTAIN"
            or gap_stage == "ROLLING"
            or parent.get("slow_rolling_parent") is True
            or parent.get("extended_parent") is True and parent.get("child_arc_count", 0) >= 2
        )
    )
    owner = _side(mountain.get("owner_side")) or _side(strategy.get("owned_side"))
    return qualified, rolling, mountain, parent, owner


def _rollover_target_reachable(tp: Mapping[str, Any], parent: Mapping[str, Any], owner: Side) -> tuple[bool, float | None, float | None]:
    """Conservative contract-win fallback while TP ownership is still unresolved.

    At PID8868 20:15:27 ET the inherited DOWN Mountain needed only ~$2.36 to
    cross TP while the living parent had already demonstrated ~$19.35.  The TP
    classifier did not flip to STARTING_LEG_FAVORED until the NO quote was no
    longer cheap.  Treat an inherited start leg as reachable when it is already
    on the winning side or when the remaining move is at most half of proven
    parent/comparable amplitude.
    """
    observed = _side(tp.get("observed_target_side"))
    required = _num(tp.get("required_move_to_target_btc"))
    capacities = [
        value for value in (
            _num(parent.get("parent_amplitude")),
            _num(tp.get("comparable_parent_amplitude_btc")),
        ) if value is not None and value > 0
    ]
    capacity = max(capacities) if capacities else None
    if observed is owner:
        return True, required, capacity
    if required is None or required < 0 or capacity is None:
        return False, required, capacity
    return required <= MOUNTAIN_ROLLOVER_REACH_FRACTION * capacity, required, capacity




def _remaining_seconds(snapshot: MarketSnapshot, tp: Mapping[str, Any]) -> float:
    value = _num(tp.get("remaining_seconds"))
    if value is not None:
        return max(0.0, value)
    return max(0.0, 900.0 - float(snapshot.contract_age_s))


def _gap_lifecycle(snapshot: MarketSnapshot) -> Mapping[str, Any]:
    cross = _map(snapshot.metadata.get("ema9_ema30_cross_context"))
    return _map(cross.get("gap_lifecycle"))


def ema9_continuation_precedent(snapshot: MarketSnapshot) -> Mapping[str, Any]:
    """Positive evidence that the current EMA9 leg deserves continuation room.

    This is briefing/candidate-quality evidence, never a specialist veto.  It
    recognizes either (a) a fresh same-side EMA9/EMA30 SPROUT, (b) a current
    EMA9 Mountain arc strongly approaching the spine after prior continuously
    observed crossings proved that comparable arcs can pass through it, or
    (c) a directly observed BUILDING/EXPANDING arc whose TP ownership already
    agrees with that side.  Any current terminal/hesitation/retreat retires the
    precedent immediately.
    """
    mountain = _map(snapshot.metadata.get("mountain"))
    strategy = _map(snapshot.metadata.get("commander_strategy"))
    owner = _side(mountain.get("owner_side")) or _side(strategy.get("owned_side"))
    cross = _map(snapshot.metadata.get("ema9_ema30_cross_context"))
    lifecycle = _map(cross.get("gap_lifecycle"))
    current_gap_side = _side(lifecycle.get("current_side") or cross.get("current_side"))
    stage = str(lifecycle.get("stage") or "UNKNOWN").upper()
    motion = _map(mountain.get("current_motion"))
    m30, m60 = _map(motion.get("30")), _map(motion.get("60"))
    geometry = _map(snapshot.metadata.get("current_geometry"))
    arc_direction = str(geometry.get("arc_direction") or "").upper()
    arc_side = Side.YES if arc_direction == "UP" else Side.NO if arc_direction == "DOWN" else None
    arc_phase = str(geometry.get("arc_phase") or "").upper()
    direct_arc_support = bool(owner is not None and arc_side is owner
                              and arc_phase in {"BUILDING", "EXPANDING", "MATURE", "ROLLING"})
    tp = _map(snapshot.metadata.get("tp_geometry"))
    tp_side = _side(tp.get("contract_ownership_side"))
    tp_status = str(tp.get("contract_ownership") or "UNRESOLVED").upper()
    tp_support = bool(owner is not None and tp_side is owner
                      and tp_status in {"STARTING_LEG_FAVORED", "BOUNCE_FAVORED"})

    def positive_rates(row: Mapping[str, Any]) -> bool:
        price = _num(row.get("owner_price_rate_btc_s"))
        ema9 = _num(row.get("owner_ema9_rate_btc_s"))
        return bool(row.get("covered") is True and price is not None and ema9 is not None
                    and price > 0 and ema9 > 0)

    current_motion_supports = positive_rates(m30) and positive_rates(m60)
    weakness = bool(
        mountain.get("terminal_evidence_qualified") is True
        or mountain.get("parent_terminal_ready") is True
        or mountain.get("stall") is True
        or mountain.get("hesitation") is True
        or mountain.get("failed_reextension") is True
        or mountain.get("meaningful_retreat") is True
    )
    release_side = _side(snapshot.metadata.get("release_candidate_side"))
    release_same = bool(snapshot.metadata.get("release_in_progress") is True
                        and owner is not None and release_side is owner)
    recent_crossings = cross.get("recent_crossings")
    recent_crossings = recent_crossings if isinstance(recent_crossings, (list, tuple)) else ()
    prior_owner_cross = bool(owner is not None and any(
        _side(_map(row).get("direction")) is owner for row in recent_crossings[:-1] or recent_crossings
    ))
    prior_owner_cross = bool(prior_owner_cross
        or (cross.get("previous_observed_cross_present") is True
            and int(cross.get("observed_cross_count") or 0) >= 2))
    gap_abs = (_num(lifecycle.get("current_abs_gap_btc"))
               or abs(_num(cross.get("current_signed_gap_btc")) or 0.0))
    near_spine = gap_abs <= 40.0

    basis = "NO_CURRENT_CONTINUATION_PRECEDENT"
    qualified = False
    continuation_motion = bool(current_motion_supports or direct_arc_support)
    if owner is not None and not weakness and continuation_motion:
        if release_same:
            qualified, basis = True, "CONFIRMED_RELEASE_CONTINUATION"
        elif current_gap_side is owner and stage in {"SPROUT", "DEVELOPING"}:
            qualified, basis = True, "FRESH_SAME_SIDE_EMA9_SPROUT"
        elif direct_arc_support and tp_support and near_spine:
            qualified, basis = True, "CURRENT_ARC_TP_CONTINUATION"
        elif (current_gap_side is not None and current_gap_side is not owner
              and prior_owner_cross and near_spine):
            qualified, basis = True, "COMPARABLE_PRIOR_EMA9_CROSS_CONTINUATION"

    return {
        "qualified": qualified,
        "side": owner.value if owner is not None else None,
        "basis": basis,
        "gap_side": current_gap_side.value if current_gap_side is not None else None,
        "gap_stage": stage,
        "gap_abs_btc": gap_abs,
        "prior_same_side_cross_observed": prior_owner_cross,
        "current_motion_supports": current_motion_supports,
        "direct_arc_support": direct_arc_support,
        "arc_side": arc_side.value if arc_side is not None else None,
        "arc_phase": arc_phase,
        "tp_support": tp_support,
        "tp_side": tp_side.value if tp_side is not None else None,
        "tp_status": tp_status,
        "weakness_observed": weakness,
        "release_same_side": release_same,
        "entry_authority": False,
        "veto_authority": False,
    }


def _established_parent_transfer_ready(snapshot: MarketSnapshot, side: Side) -> bool:
    """Existing terminal/TP transfer proof for an established opposite parent.

    Historical parent evidence and a short continuation precedent describe
    different scales.  PID17224 proved that a brief BTC bounce can retire the
    latter without retiring a still-separated, continuously observed parent.
    Keep this existing proof independent of that short classifier's result.
    """
    # PID21672 #2: an inherited NO gap can outlive a genuinely confirmed
    # YES parent transfer.  Historical EMA9-gap residence is context, never
    # authority to purchase the old side after the current mission has moved.
    # Scope: ordinary Commander MAIN Mountain entries only (caller applies
    # this function to that family); no tactical Heist or Release veto.
    mission = _map(_map(snapshot.metadata.get("mission_context")).get("parent"))
    geometry = _map(snapshot.metadata.get("current_geometry"))
    mission_source = _num(mission.get("source_ms"))
    geometry_source = _num(geometry.get("epoch_ms"))
    mission_side = _side(mission.get("side"))
    current_generation = snapshot.metadata.get("geometry_continuity_generation")
    terminal = _map(mission.get("terminal"))
    current_confirmed_opposite = bool(
        mission_side is not None and mission_side is not side
        and mission.get("status") == "ACTIVE"
        and mission.get("supported") is True
        and mission.get("invalidated") is not True
        and mission.get("basis") == "CONFIRMED_RELEASE_TRANSFER"
        and mission.get("continuity_generation") == current_generation
        and mission_source is not None and geometry_source is not None
        and abs(mission_source - geometry_source) < 0.001
        and snapshot.metadata.get("physical_current") is True
        and terminal.get("qualified") is not True
    )
    if current_confirmed_opposite:
        return False
    historical_parent = directional_parent_evidence(snapshot)
    mountain = _map(snapshot.metadata.get("mountain"))
    if (historical_parent.get("qualified") is True
            and historical_parent.get("side") != side.value
            and not (snapshot.metadata.get("release_confirmed_current") is True
                     and str(snapshot.metadata.get("release_candidate_side") or "").upper()
                         == side.value)):
        tp = _map(snapshot.metadata.get("tp_geometry"))
        geo = _map(snapshot.metadata.get("current_geometry"))
        sign = 1.0 if side is Side.YES else -1.0
        btc30 = _num(geo.get("btc_change30"))
        ema30 = _num(geo.get("ema9_change30"))
        return bool(mountain.get("terminal_evidence_qualified") is True
            and mountain.get("edge_window_active") is True
            and (mountain.get("failed_reextension") is True
                 or mountain.get("meaningful_retreat") is True)
            and btc30 is not None and sign * btc30 > 0
            and ema30 is not None and sign * ema30 >= 0
            and _side(tp.get("contract_ownership_side")) is side)
    return True


def _authorized_inherited_opening_leg(intent: ToolIntent, snapshot: MarketSnapshot) -> bool:
    """Retain the separately authorized first-minute *earned* continuation.

    PID17588 #5 is a recorded positive: the NO EMA9 native arc and inherited
    rolling gap began before rollover and were still physically advancing
    when a 51c opening quote arrived. The PID21672 ordinary #2 proposal was
    93 seconds into a fresh contract, with neither this first-minute location
    nor the narrowly authorized INHERITED_YOUNG continuation species.
    An active opposite comparison parent alone cannot silently revoke this
    old exception, but the exception must never enable a generic cheap fade.
    """
    if (intent.reason != "COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION"
            or intent.side is None):
        return False
    evidence = _map(intent.metadata.get("commander_physical_evidence"))
    inherited = _map(evidence.get("inherited_leg_live"))
    gap = _map(evidence.get("gap_inheritance"))
    geometry = _map(snapshot.metadata.get("current_geometry"))
    contract_age = _num(snapshot.contract_age_s)
    arc_start = _num(geometry.get("arc_start_ms"))
    btc6, ema6 = _num(geometry.get("btc_change6")), _num(geometry.get("ema9_change6"))
    ask = _num(snapshot.ask_for(intent.side))
    expected_arc = "UP" if intent.side is Side.YES else "DOWN"
    sign = 1.0 if intent.side is Side.YES else -1.0
    return bool(
        evidence.get("entry_location") == "INHERITED_YOUNG_LEG_FIRST_MINUTE"
        and evidence.get("opening_continuation") is True
        and inherited.get("basis") == "INHERITED_LEG_STILL_CAUSALLY_LIVE"
        and inherited.get("price_still_advancing") is True
        and inherited.get("ema9_still_advancing") is True
        and inherited.get("spent") is False
        and gap.get("inherited") is True
        and gap.get("same_side_as_owner") is True
        and snapshot.metadata.get("physical_current") is True
        and geometry.get("arc_direction") == expected_arc
        and contract_age is not None and 0 <= contract_age < MOUNTAIN_ROLLOVER_CONTINUATION_WINDOW_S
        and arc_start is not None and arc_start < (snapshot.now_ts - contract_age) * 1000.0
        and btc6 is not None and sign * btc6 > 0
        and ema6 is not None and sign * ema6 > 0
        and ask is not None and 0 < ask <= MOUNTAIN_ROLLOVER_CONTINUATION_MAX
    )


def main_return_matches_established_parent(
    intent: ToolIntent, snapshot: MarketSnapshot,
) -> bool:
    """One Commander quality rule for ordinary Mountain MAIN entry species.

    Apply before creating a positive MAIN briefing and before Commander's
    primary-family shortcut.  The family determines this scope: relabelling
    its role/lane cannot make an ordinary Mountain return a tactical Heist.
    Confirmed Release and the separately bounded tactical species retain
    their own existing admission rules. No timer or price threshold is added.
    """
    if (intent.action not in (Action.ENTER, Action.RELAY) or intent.side is None
            or intent.metadata.get("commander_primary_candidate") is not True
            or str(intent.metadata.get("commander_candidate_family") or "")
                not in {"MOUNTAIN_EDGE", "MOUNTAIN_CONTRACT_LEG"}):
        return True
    # Existing PID17588 physically earned rollover opening is a separate
    # authorized location, not the generic MAIN Mountain target-reaching case.
    if _authorized_inherited_opening_leg(intent, snapshot):
        return True
    return _established_parent_transfer_ready(snapshot, intent.side)


def positive_candidate_matches_continuation(
    intent: ToolIntent, snapshot: MarketSnapshot, *, confirmed_release_side: Side | None = None,
) -> bool:
    """Keep positive briefings coherent with current parent/continuation proof.

    Ordinary MAIN candidates first retain established-parent quality even
    when a brief local reversal leaves the continuation classifier unqualified.
    The existing newborn/current-leg rules below remain intact for advisers:
    a confirmed Release may transfer the leg, while an earned anticipatory
    edge uses <=20c with weakness or <=5c at an extended pre-weakness edge.
    """
    if not heist_sprout_fade_ready(intent, snapshot):
        return False
    if not main_return_matches_established_parent(intent, snapshot):
        return False
    precedent = ema9_continuation_precedent(snapshot)
    if precedent.get("qualified") is not True or intent.side is None:
        return True
    side = _side(precedent.get("side"))
    if side is None or intent.side is side:
        return True
    if confirmed_release_side is intent.side and intent.tool == "RELEASE_WATCHER":
        return True
    if not _established_parent_transfer_ready(snapshot, intent.side):
        return False
    mountain = _map(snapshot.metadata.get("mountain"))
    ask = _num(snapshot.ask_for(intent.side))
    parent = _map(mountain.get("parent_structure"))
    full_scale = _map(mountain.get("full_leg_scale_evidence"))
    completed_ref = _map(mountain.get("completed_minute_parent_reference"))
    parent_age = (_num(parent.get("parent_age_s"))
                  or _num(_map(parent.get("measurements")).get("age_seconds"))
                  or _num(_map(mountain.get("diagnostics")).get("parent_age_s")))
    extended = bool(parent.get("extended_parent") is True
                    or full_scale.get("qualified") is True
                    or completed_ref.get("mature_extension") is True
                    or (parent_age is not None and parent_age >= 360.0))
    weakness = bool(mountain.get("terminal_evidence_qualified") is True
                    or mountain.get("mature_edge") is True
                    or mountain.get("stall") is True
                    or mountain.get("hesitation") is True
                    or mountain.get("failed_reextension") is True
                    or mountain.get("meaningful_retreat") is True)
    earned_return = bool(ask is not None and ask > 0 and (
        (weakness and ask <= MOUNTAIN_EDGE_MAX)
        or (extended and ask <= 0.05)
    ))
    return earned_return


def _first_counterfade_has_reversal_proof(snapshot: MarketSnapshot, return_side: Side,
                                           mountain: Mapping[str, Any]) -> bool:
    """PID8552: do not send the *first* opposite entry briefing on price alone.

    A finished parent top/bottom plus its current failed extension / retreat is
    valid anticipatory evidence; otherwise require actual short BTC+EMA9
    reversal in the return direction (green on DOWN / red on UP), not just a
    fresh extreme or a cheap opposite quote. Advisers remain silent; this is
    not an external veto after Commander chooses an action.
    """
    geo = _map(snapshot.metadata.get("current_geometry"))
    sign = 1.0 if return_side is Side.YES else -1.0
    btc6 = _num(geo.get("btc_change6"))
    btc9 = _num(geo.get("btc_change9"))
    ema6 = _num(geo.get("ema9_change6"))
    observed_turn = bool(btc6 is not None and ema6 is not None
                         and sign * btc6 > 0 and sign * ema6 >= 0
                         and (btc9 is None or sign * btc9 >= 0))
    earned_terminal = bool(mountain.get("terminal_evidence_qualified") is True
        and mountain.get("mature_edge") is True
        and mountain.get("edge_window_active") is True
        and (mountain.get("stall") is True or mountain.get("failed_reextension") is True
             or mountain.get("meaningful_retreat") is True))
    return bool(observed_turn or earned_terminal)


def _late_counter_return_has_runway(snapshot: MarketSnapshot, return_side: Side) -> bool:
    """Late opposite entries need explicit target support, not merely 0.6c.

    Above 120 seconds the existing regime-aware rules apply. Inside the final
    two minutes only a current contract-owning opposite return can qualify.
    """
    if 900.0 - snapshot.contract_age_s > 120.0:
        return True
    tp = _map(snapshot.metadata.get("tp_geometry"))
    return bool(_side(tp.get("contract_ownership_side")) is return_side
        and tp.get("contract_ownership") in {"BOUNCE_FAVORED", "STARTING_LEG_FAVORED"})


def _counter_parent_return_briefing_ready(
    snapshot: MarketSnapshot, side: Side, mountain: Mapping[str, Any],
) -> bool:
    """PID17744: only *brief* an early counter-leg after a real physical turn.

    A directional gap with current-contract TP on that same side is parent
    context even before the 900s historical-flow classifier graduates it to
    RAIL/ROLLING. Its first local counter-color candle is not a full return.
    This is a positive candidate-quality check inside the single Commander,
    never another specialist WAIT/veto after Commander has approved a trade.

    A developed counter-arc with both 30s BTC reversal and short BTC+EMA9 turn
    remains eligible early (PID17744 #11). A genuine parent terminal can also
    qualify after TP actually transfers. Against intact old-side TP, however,
    late (<5m) speculative returns do not claim settlement runway from price.
    """
    gap = _gap_lifecycle(snapshot)
    gap_side = _side(gap.get("current_side"))
    stage = str(gap.get("stage") or "").upper()
    tp = _map(snapshot.metadata.get("tp_geometry"))
    tp_side = _side(tp.get("contract_ownership_side"))
    tp_favors_parent = str(tp.get("contract_ownership") or "").upper() in {
        "STARTING_LEG_FAVORED", "BOUNCE_FAVORED"
    }
    if (gap_side is None or gap_side is side or tp_side is not gap_side
            or not tp_favors_parent
            or stage not in {"DEVELOPING", "MATURE", "ROLLING", "INHERITED_OR_UNOBSERVED_CROSS"}
            or (gap.get("observed_cross_on_current_segment") is True
                and gap.get("continued_on_latest_cross_side") is False)
            or gap.get("touching_spine") is True):
        return True

    geo = _map(snapshot.metadata.get("current_geometry"))
    abs_gap = _num(gap.get("current_abs_gap_btc"))
    if abs_gap is None:
        abs_gap = abs(_num(geo.get("ema_gap")) or 0.0)
    range180 = _num(geo.get("range180")) or 0.0
    # Near the EMA spine, the previous owner is no longer a clear directional
    # parent. Do not fossilize it merely because an old gap-age label survives.
    if abs_gap < max(15.0, 0.16 * range180):
        return True

    sign = 1.0 if side is Side.YES else -1.0
    btc6 = _num(geo.get("btc_change6"))
    btc9 = _num(geo.get("btc_change9"))
    btc30 = _num(geo.get("btc_change30"))
    ema6 = _num(geo.get("ema9_change6"))
    range60 = _num(geo.get("range60")) or 0.0
    # A lone 6s bounce against a continuing 30s parent is exactly the
    # PID17744 #12/#13/#14/#15 failure, however cheap the contract becomes.
    developed_counter_arc = bool(
        btc6 is not None and sign * btc6 > 0
        and btc9 is not None and sign * btc9 > 0
        and ema6 is not None and sign * ema6 > 0
        and btc30 is not None
        and sign * btc30 >= max(4.0, 0.18 * range60)
    )
    parent = _map(mountain.get("parent_structure"))
    real_parent_handoff = bool(
        parent.get("parent_terminal_ready") is True
        and (parent.get("parent_turning_or_flat") is True
             or mountain.get("failed_reextension") is True)
        and developed_counter_arc
    )
    remaining = max(0.0, 900.0 - snapshot.contract_age_s)
    if remaining <= 300.0:
        # An intact opposite parent still owns the TP: a late scalp pop is not
        # evidence of a contract-winning return. These can be researched in
        # Quote Echo shadow, not advertised as a MAIN/Extreme entry window.
        return bool(real_parent_handoff)
    return bool(developed_counter_arc or real_parent_handoff)


def _sprout_reversal_ready(snapshot: MarketSnapshot, mountain: Mapping[str, Any], owner: Side) -> tuple[bool, dict[str, Any]]:
    """Fresh post-cross gaps get breathing room, but the clock never vetoes a real turn.

    A SPROUT is the first half-contract after a continuously observed EMA9/EMA30
    cross on the living side.  A micro stall/paired-gap resemblance is not enough
    to fade it while parent motion is still outward.  Actual price+EMA9 retreat,
    meaningful retreat, or failed re-extension can still terminate it early.
    """
    lifecycle = _gap_lifecycle(snapshot)
    stage = str(lifecycle.get("stage") or "UNKNOWN")
    same_side = lifecycle.get("current_side") == owner.value
    motions = _map(mountain.get("current_motion"))
    m30, m60 = _map(motions.get("30")), _map(motions.get("60"))
    price30, ema30 = _num(m30.get("owner_price_rate_btc_s")), _num(m30.get("owner_ema9_rate_btc_s"))
    price60, ema60 = _num(m60.get("owner_price_rate_btc_s")), _num(m60.get("owner_ema9_rate_btc_s"))
    causal_turn = bool(
        mountain.get("meaningful_retreat") is True
        or mountain.get("failed_reextension") is True
        or (m30.get("covered") is True and price30 is not None and ema30 is not None
            and price30 <= 0 and ema30 <= 0)
        or (m60.get("covered") is True and price60 is not None and ema60 is not None
            and price60 <= 0 and ema60 <= 0)
    )
    proof = {
        "stage": stage,
        "gap_age_seconds": _num(lifecycle.get("age_seconds_since_observed_cross")),
        "same_side_as_owner": same_side,
        "gap_expanding_6s": lifecycle.get("gap_expanding_6s") is True,
        "owner_price_rate_30s": price30,
        "owner_ema9_rate_30s": ema30,
        "owner_price_rate_60s": price60,
        "owner_ema9_rate_60s": ema60,
        "meaningful_retreat": mountain.get("meaningful_retreat") is True,
        "failed_reextension": mountain.get("failed_reextension") is True,
        "causal_turn_observed": causal_turn,
        "clock_alone_has_trade_authority": False,
    }
    if stage != "SPROUT" or not same_side:
        proof["basis"] = "NOT_FRESH_SAME_SIDE_SPROUT"
        return True, proof
    ok = causal_turn
    proof["basis"] = "SPROUT_CAUSAL_TURN_PROVED" if ok else "SPROUT_STILL_BREATHING_NO_PARENT_TURN"
    return ok, proof


def heist_sprout_fade_ready(intent: ToolIntent, snapshot: MarketSnapshot) -> bool:
    """A calibrated box visit cannot alone fade an expanding newborn EMA9 leg.

    PID10656 #3/#4 were later Heist visits, but both opposed a current,
    continuously witnessed SPROUT with outward BTC and EMA9 motion.  Keep the
    existing causal-turn test at both positive briefing and Commander entry
    admission, before any later-Heist exception.  An age/box/mature-edge label
    alone supplies neither a turn nor this restriction.  Real measured turns,
    confirmed corrective transfers, balanced boxes and non-Heist routes retain
    their existing checks; this function creates no entry permission.
    """
    if (intent.tool != "MARKET_HEIST" or intent.side is None
            or intent.action not in (Action.ENTER, Action.RELAY)):
        return True
    mountain = _map(snapshot.metadata.get("mountain"))
    owner = _side(mountain.get("owner_side"))
    if owner is None or intent.side is owner:
        return True
    cross = _map(snapshot.metadata.get("ema9_ema30_cross_context"))
    lifecycle = _map(cross.get("gap_lifecycle"))
    if (lifecycle.get("stage") != "SPROUT"
            or lifecycle.get("current_side") != owner.value
            or lifecycle.get("latest_cross_observed_continuously") is not True
            or lifecycle.get("continued_on_latest_cross_side") is not True):
        return True
    geometry = _map(snapshot.metadata.get("current_geometry"))
    source = _num(geometry.get("epoch_ms"))
    if (snapshot.metadata.get("physical_current") is not True or source is None
            or _num(cross.get("source_ms")) != source
            or _num(mountain.get("source_ms")) != source
            or not current_source_is_fresh(snapshot, source, max_age_seconds=3.)):
        # Unknown/stale context does not become a new strategic authority.
        # Existing source/book admission still decides whether any order may run.
        return True
    if (snapshot.metadata.get("release_confirmed_current") is True
            and _side(snapshot.metadata.get("release_candidate_side")) is intent.side):
        return True
    # Owner-relative rates belong to this current Mountain observation. A
    # stale/mismatched subrow cannot supply a turn that defeats the current
    # outward row. The mission-parent label alone cannot reorient these rates.
    motion = _map(mountain.get("current_motion"))
    current_motion = {h:row for h in ("30", "60")
        if _num((row := _map(motion.get(h))).get("source_ms")) == source}
    reversal_ready, _ = _sprout_reversal_ready(
        snapshot, {**mountain, "current_motion": current_motion}, owner)
    if reversal_ready:
        return True
    for horizon in ("30", "60"):
        row = _map(current_motion.get(horizon))
        price_rate = _num(row.get("owner_price_rate_btc_s"))
        ema9_rate = _num(row.get("owner_ema9_rate_btc_s"))
        if (row.get("covered") is True
                and price_rate is not None and ema9_rate is not None
                and price_rate > 0 and ema9_rate > 0):
            return False
    return True


def heist_stalled_edge_earned(intent: ToolIntent, snapshot: MarketSnapshot) -> bool:
    """PID19616 #7: pause-only is not a return inside an expanding EMA9 leg.

    Tight scope: only the stalled-parallel-edge *fallback*, opposite an
    observed native parent, at a current Heist outer edge. If both the 6s BTC
    and EMA9 barely paused while 9s BTC and 30s EMA9 still strongly push with
    the parent, there has been no new return motion to lend this fallback an
    entry. Steep-edge exhaustion entries (#4/#6) remain eligible, as do actual
    6s turns and other genuine bounded Heist species. Missing or stale native
    source cannot supply this extra negative inference.
    """
    if (intent.tool != "MARKET_HEIST" or intent.reason != "HEIST_PARALLEL_STALLED_EDGE_RETURN"
            or intent.action not in (Action.ENTER, Action.RELAY) or intent.side is None):
        return True
    geo = _map(snapshot.metadata.get("current_geometry"))
    mountain = _map(snapshot.metadata.get("mountain"))
    heist = _map(snapshot.metadata.get("heist"))
    source_ms = _num(geo.get("epoch_ms"))
    parent = _side(mountain.get("owner_side"))
    if (snapshot.metadata.get("physical_current") is not True or source_ms is None
            or not current_source_is_fresh(snapshot, source_ms, max_age_seconds=3.0)
            or parent is None or intent.side is parent
            or geo.get("parent_direction") != ("UP" if parent is Side.YES else "DOWN")
            or heist.get("qualified_box") is not True
            or heist.get("current_zone") not in ("UPPER", "LOWER")):
        return True
    change6 = _num(geo.get("btc_change6"))
    change9 = _num(geo.get("btc_change9"))
    change30 = _num(geo.get("btc_change30"))
    ema6 = _num(geo.get("ema9_change6"))
    ema30 = _num(geo.get("ema9_change30"))
    if any(value is None for value in (change6, change9, change30, ema6, ema30)):
        return True
    sign = 1.0 if parent is Side.YES else -1.0
    # A small actual opposite turn remains available to existing quality
    # checks; the negative is an almost-flat pause after a large parent push.
    unresolved_microstall = (abs(change6) <= max(2.0, 0.05 * abs(change9))
        and abs(ema6) <= max(0.5, 0.05 * abs(ema30)))
    strong_parent = (sign * change9 >= 35.0 and sign * change30 >= 75.0
        and sign * ema30 >= 15.0)
    return not (unresolved_microstall and strong_parent)


def _return_settlement_feasible(
    snapshot: MarketSnapshot, tp: Mapping[str, Any], mountain: Mapping[str, Any], return_side: Side,
) -> tuple[bool, dict[str, Any]]:
    """Continuous regime-aware TP/runway test for Mountain return legs.

    Settlement distance is BTC spot distance, so the strongest evidence is not a
    generic EMA amplitude threshold.  We ask whether recent *parent-scale return
    Mountains* actually demonstrated at least the required BTC excursion and a
    pace capable of covering that same-scale distance inside the remaining
    contract time.  Small fast child wiggles cannot extrapolate themselves into
    proof of a much larger settlement move.

    The detector supplies the last 3-5 return legs as ``legs``.  For each leg
    whose observed BTC excursion was at least the required move, estimate the
    time to that required distance from that leg's demonstrated average pace.
    The fastest qualifying same-scale precedent is the capacity proof.  This is
    naturally regime-adaptive: $300-$800 Mountains can validate late entries;
    an $80-$100 chapter cannot claim the same capacity from a tiny fast wobble.

    Older aggregate reference fields remain a compatibility fallback for tests
    and warm-start packets.  With insufficient comparable history, only the
    final five minutes are conservatively refused; earlier entries remain
    unknown rather than being declared impossible.
    """
    remaining = _remaining_seconds(snapshot, tp)
    observed = _side(tp.get("observed_target_side"))
    required = _num(tp.get("required_move_to_target_btc"))
    reference = _map(mountain.get("return_leg_reference"))
    if not reference:
        reference = _map(_map(mountain.get("diagnostics")).get("return_leg_reference"))
    raw_legs = reference.get("legs") if isinstance(reference.get("legs"), (list, tuple)) else ()
    legs: list[dict[str, Any]] = []
    for raw in raw_legs:
        leg = _map(raw)
        amplitude = _num(leg.get("btc_amplitude_btc"))
        duration = _num(leg.get("duration_s"))
        speed = _num(leg.get("average_btc_speed_btc_s"))
        if amplitude is None or amplitude <= 0 or duration is None or duration <= 0:
            continue
        if speed is None or speed <= 0:
            speed = amplitude / duration
        legs.append({
            "arc_id": leg.get("arc_id"),
            "reference_kind": leg.get("reference_kind"),
            "btc_amplitude_btc": amplitude,
            "duration_s": duration,
            "average_btc_speed_btc_s": speed,
        })

    count = len(legs) if legs else int(_num(reference.get("count")) or 0)
    median_amp = _num(reference.get("median_amplitude_btc"))
    median_speed = _num(reference.get("median_speed_btc_s"))
    demonstrated_amp = _num(reference.get("max_amplitude_btc")) or median_amp
    demonstrated_speed = _num(reference.get("max_speed_btc_s")) or median_speed

    evidence = {
        "remaining_seconds": remaining,
        "insufficient_history_late_seconds": MOUNTAIN_INSUFFICIENT_HISTORY_LATE_S,
        "observed_target_side": observed.value if observed else None,
        "return_side": return_side.value,
        "required_move_to_target_btc": required,
        "reference_count": count,
        "reference_basis": reference.get("basis"),
        "reference_median_amplitude_btc": median_amp,
        "reference_median_speed_btc_s": median_speed,
        "reference_max_amplitude_btc": _num(reference.get("max_amplitude_btc")),
        "reference_max_speed_btc_s": _num(reference.get("max_speed_btc_s")),
        "demonstrated_amplitude_btc": demonstrated_amp,
        "demonstrated_speed_btc_s": demonstrated_speed,
        "regime_adaptive": True,
        "same_scale_leg_count": 0,
        "same_scale_legs": [],
        "settlement_average_window_seconds": MOUNTAIN_SETTLEMENT_AVERAGE_WINDOW_S,
    }
    if observed is return_side:
        # Being one tick on the intended side of TP is not the same as owning
        # settlement. PID3296 #2 entered NO only ~$6 below TP with ~96s left;
        # the recent 60s BTC range was ~$9.7 and the live 6s BTC+EMA9 motion
        # had already turned back toward YES. The old unconditional shortcut
        # treated that fragile possession as guaranteed runway.
        #
        # Keep this regime-adaptive: require the current margin, plus only
        # directionally demonstrated extension available before the final RTI
        # averaging window, to cover roughly one recent 60s BTC range. In a
        # $300-$800 fast chapter a strong same-side move can therefore validate
        # a late position; in a tight chapter a thin TP margin cannot.
        geometry = _map(snapshot.metadata.get("current_geometry"))
        recent_range = _num(geometry.get("range60"))
        if recent_range is None or recent_range <= 0:
            recent_range = _num(geometry.get("range180"))
        sign = 1.0 if return_side is Side.YES else -1.0
        btc6 = _num(geometry.get("btc_change6"))
        ema6 = _num(geometry.get("ema9_change6"))
        btc30 = _num(geometry.get("btc_change30"))
        btc60 = _num(geometry.get("btc_change60"))
        side_btc6 = sign * btc6 if btc6 is not None else None
        side_ema6 = sign * ema6 if ema6 is not None else None
        rates = []
        if btc30 is not None:
            rates.append(sign * btc30 / 30.0)
        if btc60 is not None:
            rates.append(sign * btc60 / 60.0)
        positive_rates = [rate for rate in rates if rate > 0]
        conservative_side_rate = min(positive_rates) if positive_rates else 0.0
        causal_hold = bool(side_btc6 is not None and side_ema6 is not None
                           and side_btc6 >= 0 and side_ema6 >= 0)
        pre_average_seconds = max(0.0, remaining - MOUNTAIN_SETTLEMENT_AVERAGE_WINDOW_S)
        projected_extension = (conservative_side_rate * pre_average_seconds
                               if causal_hold else 0.0)
        projected_margin = (required or 0.0) + projected_extension
        required_buffer = recent_range if recent_range is not None and recent_range > 0 else None
        robust = bool(required_buffer is None or projected_margin >= required_buffer)
        evidence.update({
            "target_possession_margin_btc": required,
            "recent_range_buffer_btc": required_buffer,
            "pre_settlement_average_seconds": pre_average_seconds,
            "side_btc_change6": side_btc6,
            "side_ema9_change6": side_ema6,
            "causal_hold_or_extension": causal_hold,
            "conservative_side_rate_btc_s": conservative_side_rate,
            "projected_same_side_extension_btc": projected_extension,
            "projected_target_margin_btc": projected_margin,
        })
        evidence["basis"] = ("RETURN_SIDE_TARGET_POSSESSION_ROBUST"
                             if robust else "RETURN_SIDE_TARGET_POSSESSION_FRAGILE")
        return robust, evidence
    if required is None or required <= 0:
        evidence["basis"] = "TARGET_DISTANCE_UNKNOWN_OR_ZERO"
        return remaining > MOUNTAIN_INSUFFICIENT_HISTORY_LATE_S, evidence

    if count >= MOUNTAIN_RETURN_MIN_REFERENCES and legs:
        qualifying = []
        for leg in legs:
            if leg["btc_amplitude_btc"] + 1e-9 < required:
                continue
            scaled_time = required / leg["average_btc_speed_btc_s"]
            qualifying.append({**leg, "scaled_time_to_required_s": scaled_time})
        evidence["same_scale_leg_count"] = len(qualifying)
        evidence["same_scale_legs"] = qualifying
        if not qualifying:
            evidence["basis"] = "TP_DISTANCE_EXCEEDS_RECENT_PARENT_RETURN_SCALE"
            return False, evidence
        # PID1172 #3: one old monster leg must not make a far-TP return look
        # ordinary when the current chapter's median excursion is much smaller.
        # If the requested move is more than 2x the recent median parent return,
        # require at least two same-scale precedents.  Fast/high-volatility
        # chapters naturally pass once their median scale expands.
        if (median_amp is not None and median_amp > 0
                and required > 2.0 * median_amp and len(qualifying) < 2):
            evidence["outlier_guard_multiple_of_median"] = required / median_amp
            evidence["outlier_guard_required_same_scale_legs"] = 2
            evidence["basis"] = "TP_DISTANCE_SUPPORTED_ONLY_BY_SINGLE_OUTLIER_LEG"
            return False, evidence
        # Use the most recent same-scale precedent, not the fastest cherry-picked
        # older leg.  That keeps the proof tied to the current volatility chapter.
        # Kalshi settlement is based on the final 60-second RTI average, so a
        # leg that could merely touch TP with a few seconds left is not equivalent
        # to demonstrated settlement runway.
        precedent = qualifying[-1]
        travel_time = precedent["scaled_time_to_required_s"]
        required_total = travel_time + MOUNTAIN_SETTLEMENT_AVERAGE_WINDOW_S
        evidence["best_same_scale_arc_id"] = precedent.get("arc_id")
        evidence["best_scaled_time_to_required_s"] = travel_time
        evidence["most_recent_same_scale_arc_id"] = precedent.get("arc_id")
        evidence["required_total_runway_seconds"] = required_total
        evidence["required_speed_btc_s"] = required / remaining if remaining > 0 else None
        ok = required_total <= remaining
        evidence["basis"] = ("PROVEN_RETURN_LEG_CAN_REACH_TP"
                             if ok else "TP_BEYOND_PROVEN_RETURN_RUNWAY")
        return ok, evidence

    # Compatibility/warmup fallback for packets that do not yet carry the
    # per-leg ledger.  Do not extrapolate a tiny high-speed leg to a larger TP
    # move: both demonstrated amplitude and time capacity must cover it.
    if (count < MOUNTAIN_RETURN_MIN_REFERENCES or demonstrated_amp is None or demonstrated_amp <= 0
            or demonstrated_speed is None or demonstrated_speed <= 0):
        ok = remaining > MOUNTAIN_INSUFFICIENT_HISTORY_LATE_S
        evidence["basis"] = ("EARLY_ENTRY_RETURN_HISTORY_INSUFFICIENT_UNKNOWN"
                             if ok else "INSUFFICIENT_PROVEN_RETURN_RUNWAY")
        return ok, evidence
    time_capacity = demonstrated_speed * remaining * MOUNTAIN_RETURN_REACH_FRACTION
    amplitude_capacity = demonstrated_amp * MOUNTAIN_RETURN_REACH_FRACTION
    reachable = min(time_capacity, amplitude_capacity)
    evidence.update(time_capacity_btc=time_capacity, amplitude_capacity_btc=amplitude_capacity,
                    proven_reachable_btc=reachable,
                    required_speed_btc_s=required / remaining if remaining > 0 else None)
    ok = required <= reachable
    evidence["basis"] = "PROVEN_RETURN_LEG_CAN_REACH_TP" if ok else "TP_BEYOND_PROVEN_RETURN_RUNWAY"
    return ok, evidence



def _tp_junction_return_policy(
    snapshot: MarketSnapshot,
    tp: Mapping[str, Any],
    side: Side,
    runway_ok: bool,
    runway_evidence: Mapping[str, Any],
) -> tuple[bool, bool, dict[str, Any]]:
    """Return (junction_allowed, runway_override, evidence).

    TP between EMA9/EMA30 remains a strong late/tight warning, but the operator
    explicitly authorized less authority earlier in the contract.  The junction
    can become advisory only when the proposed return is the TP model's own
    BOUNCE_FAVORED side and current comparable parent scale is large enough to
    cover the required TP move with more than the existing 5-minute late fallback
    remaining.  This is deliberately narrow: it does not relax non-junction
    runway, rollover, price ceilings, or late entries.
    """
    if tp.get("target_between_ema9_ema30") is not True:
        return True, False, {"junction": False, "basis": "TP_NOT_IN_EMA_JUNCTION"}
    remaining = _num(runway_evidence.get("remaining_seconds"))
    required = _num(tp.get("required_move_to_target_btc"))
    comparable = _num(tp.get("comparable_parent_amplitude_btc"))
    ownership = str(tp.get("contract_ownership") or "UNRESOLVED")
    ownership_side = _side(tp.get("contract_ownership_side"))
    evidence = {
        "junction": True,
        "remaining_seconds": remaining,
        "late_junction_seconds": MOUNTAIN_INSUFFICIENT_HISTORY_LATE_S,
        "required_move_to_target_btc": required,
        "comparable_parent_amplitude_btc": comparable,
        "contract_ownership": ownership,
        "contract_ownership_side": ownership_side.value if ownership_side else None,
        "runway_basis": runway_evidence.get("basis"),
        "runway_ok_before_junction_policy": runway_ok,
    }
    # If the return side already robustly owns the target, the junction is no
    # longer a reason to veto the entry.
    if runway_ok and runway_evidence.get("basis") == "RETURN_SIDE_TARGET_POSSESSION_ROBUST":
        evidence["basis"] = "TP_JUNCTION_ADVISORY_TARGET_ALREADY_ROBUST"
        return True, False, evidence
    # Earlier entries may use the current TP model's BOUNCE_FAVORED conclusion
    # as a junction-specific override when the comparable parent scale itself
    # covers the required move.  Final-5-minute/tight entries do not get this
    # relaxation; they still need ordinary proven runway.
    early_scale_override = bool(
        remaining is not None and remaining > MOUNTAIN_INSUFFICIENT_HISTORY_LATE_S
        and ownership == "BOUNCE_FAVORED" and ownership_side is side
        and required is not None and required > 0
        and comparable is not None and comparable + 1e-9 >= required
    )
    if early_scale_override:
        evidence["basis"] = "TP_JUNCTION_ADVISORY_EARLY_BOUNCE_FAVORED_PARENT_SCALE"
        evidence["runway_override"] = not runway_ok
        return True, not runway_ok, evidence
    # A junction with ordinary proven runway may be advisory when that proof
    # leaves the same existing 15% reserve used by return-capacity logic.
    required_total = _num(runway_evidence.get("required_total_runway_seconds"))
    ample_proven = bool(
        runway_ok and remaining is not None and required_total is not None
        and required_total <= MOUNTAIN_RETURN_REACH_FRACTION * remaining
    )
    if ample_proven:
        evidence["basis"] = "TP_JUNCTION_ADVISORY_AMPLY_PROVEN_RUNWAY"
        return True, False, evidence
    evidence["basis"] = "TP_JUNCTION_HARD_WHEN_LATE_TIGHT_OR_UNPROVEN"
    return False, False, evidence

def settlement_runway_for_side(snapshot: MarketSnapshot, side: Side) -> tuple[bool, dict[str, Any]]:
    """Public regime-aware late-entry runway proof for reactivated tools.

    Mountain return entries already carry opposite-direction parent references.
    A same-direction Rail continuation instead needs same-side recent leg history;
    use the causal Leg Performance Ledger rows when available, then delegate to
    the exact same settlement/runway calculation used by Mountain.  This helper
    has evidence authority only and does not create an entry by itself.
    """
    tp = _map(snapshot.metadata.get("tp_geometry"))
    mountain = dict(_map(snapshot.metadata.get("mountain")))
    owner = _side(mountain.get("owner_side"))
    if owner is side:
        echo = _map(snapshot.metadata.get("leg_echo"))
        raw_rows = echo.get("completed_comparable_legs")
        rows = raw_rows if isinstance(raw_rows, (list, tuple)) else ()
        legs: list[dict[str, Any]] = []
        for raw in rows[-5:]:
            row = _map(raw)
            if _side(row.get("side")) is not side:
                continue
            amplitude = _num(row.get("btc_amplitude"))
            duration = _num(row.get("duration_s"))
            if amplitude is None or amplitude <= 0 or duration is None or duration <= 0:
                continue
            legs.append({
                "arc_id": row.get("leg_id"),
                "reference_kind": "LEG_PERFORMANCE_LEDGER_SAME_SIDE",
                "btc_amplitude_btc": amplitude,
                "duration_s": duration,
                "average_btc_speed_btc_s": amplitude / duration,
            })
        amps = [leg["btc_amplitude_btc"] for leg in legs]
        speeds = [leg["average_btc_speed_btc_s"] for leg in legs]
        reference = {
            "count": len(legs),
            "median_amplitude_btc": sorted(amps)[len(amps)//2] if amps else None,
            "median_speed_btc_s": sorted(speeds)[len(speeds)//2] if speeds else None,
            "max_amplitude_btc": max(amps) if amps else None,
            "max_speed_btc_s": max(speeds) if speeds else None,
            "legs": legs,
            "basis": "LAST_COMPLETED_SAME_DIRECTION_LEG_LEDGER",
        }
        mountain["return_leg_reference"] = reference
    ok, evidence = _return_settlement_feasible(snapshot, tp, mountain, side)
    return ok, {**evidence, "requested_side": side.value,
                "tool_reactivation_runway": True}


def _gap_preexisted_current_contract(snapshot: MarketSnapshot, parent: Mapping[str, Any], owner: Side) -> tuple[bool, dict[str, Any]]:
    """The current EMA9/EMA30 gap direction must actually predate rollover.

    Arc identity can span an EMA9/EMA30 cross. PID23072 #7 had a ~388s DOWN
    arc but only a ~29s NO gap: that NO separation sprouted *inside* the new
    contract and therefore was not an inherited DOWN leg. Conversely PID8868
    had a ~289s NO gap only ~28s into the contract, so the gap really did
    pre-exist rollover. This is provenance, not a minimum-age trading rule.
    """
    lifecycle = _gap_lifecycle(snapshot)
    stage = str(lifecycle.get("stage") or "UNKNOWN")
    current_side = str(lifecycle.get("current_side") or "")
    gap_age = _num(lifecycle.get("age_seconds_since_observed_cross"))
    contract_age = float(snapshot.contract_age_s)
    same_side = current_side == owner.value
    if same_side and gap_age is not None:
        inherited = gap_age + 2.0 >= contract_age
        basis = "GAP_CROSSED_BEFORE_CONTRACT_OPEN" if inherited else "GAP_SPROUTED_AFTER_CONTRACT_OPEN"
    elif same_side and stage in {"MATURE", "ROLLING", "INHERITED_OR_UNOBSERVED_CROSS"} and parent.get("extended_parent") is True:
        inherited = True
        basis = "LONG_PARENT_GAP_PREHISTORY_INHERITED"
    else:
        inherited = False
        basis = "CURRENT_GAP_INHERITANCE_UNPROVED"
    return inherited, {
        "stage": stage,
        "current_side": current_side or None,
        "owner_side": owner.value,
        "same_side_as_owner": same_side,
        "gap_age_seconds": gap_age,
        "contract_age_seconds": contract_age,
        "inherited": inherited,
        "basis": basis,
        "clock_alone_has_trade_authority": False,
    }


def _inherited_leg_still_live(snapshot: MarketSnapshot, mountain: Mapping[str, Any], parent: Mapping[str, Any], owner: Side) -> tuple[bool, dict[str, Any]]:
    """Do not buy rollover continuation after the inherited leg is already spent.

    Price may pull back while EMA9 still advances -- that can be healthy value.
    What is forbidden is the PID23072 #7 shape: mature inherited direction,
    parent no longer advancing, price retreating, yet rollover calls it a fresh
    STARTING_LEG.  EMA9/gap lifecycle are context; no single clock label decides.
    """
    motions = _map(mountain.get("current_motion"))
    m30, m60 = _map(motions.get("30")), _map(motions.get("60"))
    p30, e30 = _num(m30.get("owner_price_rate_btc_s")), _num(m30.get("owner_ema9_rate_btc_s"))
    p60, e60 = _num(m60.get("owner_price_rate_btc_s")), _num(m60.get("owner_ema9_rate_btc_s"))
    slowdown = _map(mountain.get("slowdown"))
    lifecycle = _gap_lifecycle(snapshot)
    same_gap_side = lifecycle.get("current_side") == owner.value
    ema_advancing = any(v is not None and v > 0 for v in (e30, e60))
    price_advancing = any(v is not None and v > 0 for v in (p30, p60))
    retreating = slowdown.get("owner_price_retreat_observed") is True or all(
        v is not None and v <= 0 for v in (p30, p60))
    terminal = bool(parent.get("parent_terminal_ready") is True
                    or mountain.get("primary_collection_terminal_qualified") is True)
    covered = bool(m30.get("covered") is True or m60.get("covered") is True)
    current_geometry = _map(snapshot.metadata.get("current_geometry"))
    abs_gap = abs(_num(current_geometry.get("ema_gap")) or _num(lifecycle.get("current_abs_gap_btc")) or 0.0)
    range60 = _num(current_geometry.get("range60"))
    spine_width = max(0.50, 0.08 * range60) if range60 is not None and range60 > 0 else 0.50
    gap_collapsed = abs_gap <= spine_width
    phase = str(_map(mountain.get("diagnostics")).get("phase") or current_geometry.get("arc_phase") or "").upper()
    mature_old_leg = phase in {"MATURE", "CREST_FORMING", "TROUGH_FORMING", "ROLLING"}
    # A pullback can be healthy while a separated EMA9 parent still owns the
    # leg.  The PID23072 #7 failure is specifically a mature inherited arc whose
    # gap has collapsed back to the spine while price retreats: that is a spent
    # old chapter, not a new starting leg.  A still-separated gap can remain a
    # valid value pullback even if short-window price/EMA9 momentarily retrace.
    # PID3860: a wide *lagging* EMA9/EMA30 gap is not permission to buy the
    # outgoing leg after a mature top has begun a substantial return.  Demand
    # both meaningful 30s/60s price retreat and a non-advancing EMA9 at the
    # longer horizon; an ordinary one-wick pullback remains valid.  This is a
    # negative continuation control, NOT opposite-side entry authority.
    pronounced_mature_retreat = bool(
        covered and mature_old_leg and retreating
        and p30 is not None and p30 <= -(12.0 / 30.0)
        and p60 is not None and p60 <= -(25.0 / 60.0)
        and e60 is not None and e60 <= 0.0
        and not price_advancing
    )
    spent = bool(terminal or pronounced_mature_retreat
                 or (covered and retreating and mature_old_leg and gap_collapsed
                     and not price_advancing))
    proof = {
        "owner_side": owner.value,
        "owner_price_rate_30s": p30, "owner_ema9_rate_30s": e30,
        "owner_price_rate_60s": p60, "owner_ema9_rate_60s": e60,
        "ema9_still_advancing": ema_advancing, "price_still_advancing": price_advancing,
        "owner_price_retreating": retreating,
        "parent_terminal_ready": parent.get("parent_terminal_ready") is True,
        "collection_terminal_ready": mountain.get("primary_collection_terminal_qualified") is True,
        "gap_stage": lifecycle.get("stage"), "gap_same_side_as_owner": same_gap_side,
        "gap_expanding_6s": lifecycle.get("gap_expanding_6s") is True,
        "current_abs_ema_gap_btc": abs_gap,
        "spine_contact_width_btc": spine_width,
        "gap_collapsed_to_spine": gap_collapsed,
        "arc_phase": phase,
        "mature_old_leg": mature_old_leg,
        "pronounced_mature_price_retreat": pronounced_mature_retreat,
        "motion_covered": covered,
        "spent": spent,
    }
    if not covered:
        proof["basis"] = "ROLLOVER_CONTINUATION_MOTION_UNKNOWN"
        return False, proof
    proof["basis"] = "INHERITED_LEG_STILL_CAUSALLY_LIVE" if not spent else "INHERITED_LEG_ALREADY_SPENT_OR_TURNING"
    return not spent, proof



def _persistent_gap_pullback_context(
    snapshot: MarketSnapshot, mountain: Mapping[str, Any], child_owner: Side,
) -> tuple[bool, Side | None, dict[str, Any]]:
    """Recognize a child pullback terminal inside a long-lived EMA9 gap.

    The user's gap-lifecycle distinction is parent context, never clock-only
    authority.  A MATURE/ROLLING gap can support same-gap continuation only
    when the current local Mountain is the opposite-side child, the gap remains
    physically separated from the spine, and that child has actually stopped
    advancing and begun to turn back toward the gap side.

    This closes PID3296 starvation without reopening mid-child entries: at
    08:31 EST the ROLLING YES gap had a terminating NO child and a +6s BTC/EMA9
    turn; at the earlier violent 05:17 pullback the child was still advancing
    hard until the causal turn appeared.
    """
    lifecycle = _gap_lifecycle(snapshot)
    stage = str(lifecycle.get("stage") or "UNKNOWN")
    gap_side = _side(lifecycle.get("current_side"))
    geometry = _map(snapshot.metadata.get("current_geometry"))
    abs_gap = _num(lifecycle.get("current_abs_gap_btc"))
    if abs_gap is None:
        raw_gap = _num(geometry.get("ema_gap"))
        abs_gap = abs(raw_gap) if raw_gap is not None else None
    range60 = _num(geometry.get("range60"))
    spine_width = max(0.50, 0.08 * range60) if range60 is not None and range60 > 0 else 0.50
    separated = bool(abs_gap is not None and abs_gap > spine_width)
    continuous_side = lifecycle.get("continued_on_latest_cross_side") is not False
    opposite_child = bool(gap_side is not None and gap_side is not child_owner)

    btc6 = _num(geometry.get("btc_change6"))
    ema6 = _num(geometry.get("ema9_change6"))
    if child_owner is Side.NO:
        micro_turn = bool(btc6 is not None and ema6 is not None and btc6 >= 0 and ema6 >= 0)
    else:
        micro_turn = bool(btc6 is not None and ema6 is not None and btc6 <= 0 and ema6 <= 0)
    causal_turn = bool(
        micro_turn
        or mountain.get("meaningful_retreat") is True
        or mountain.get("failed_reextension") is True
    )
    stage_ok = stage in {"MATURE", "ROLLING"}
    terminal = current_mountain_terminal(mountain)
    ok = bool(stage_ok and gap_side is not None and opposite_child and continuous_side
              and separated and terminal and causal_turn
              and mountain.get("strong_active_release") is not True)
    proof = {
        "gap_stage": stage,
        "gap_side": gap_side.value if gap_side else None,
        "child_owner_side": child_owner.value,
        "opposite_child": opposite_child,
        "continued_on_latest_cross_side": continuous_side,
        "gap_age_seconds": _num(lifecycle.get("age_seconds_since_observed_cross")),
        "current_abs_gap_btc": abs_gap,
        "spine_contact_width_btc": spine_width,
        "gap_separated_from_spine": separated,
        "terminal": terminal,
        "btc_change6": btc6,
        "ema9_change6": ema6,
        "micro_turn_to_gap_side": micro_turn,
        "meaningful_retreat": mountain.get("meaningful_retreat") is True,
        "failed_reextension": mountain.get("failed_reextension") is True,
        "causal_child_turn": causal_turn,
        "strong_active_release": mountain.get("strong_active_release") is True,
        "clock_alone_has_trade_authority": False,
    }
    if not stage_ok:
        proof["basis"] = "GAP_NOT_YET_MATURE"
    elif not opposite_child:
        proof["basis"] = "CURRENT_CHILD_ALREADY_MATCHES_GAP_SIDE"
    elif not continuous_side:
        proof["basis"] = "GAP_CROSS_CONTINUITY_UNPROVED"
    elif not separated:
        proof["basis"] = "GAP_COLLAPSED_TO_SPINE"
    elif not terminal:
        proof["basis"] = "CHILD_PULLBACK_NOT_AT_CURRENT_TERMINAL"
    elif not causal_turn:
        proof["basis"] = "CHILD_PULLBACK_STILL_ADVANCING"
    elif mountain.get("strong_active_release") is True:
        proof["basis"] = "OPPOSITE_RELEASE_STILL_ACTIVE"
    else:
        proof["basis"] = "PERSISTENT_GAP_CHILD_TERMINAL_TURN"
    return ok, gap_side, proof

def _opening_rail_context(snapshot: MarketSnapshot) -> dict[str, Any]:
    """Describe an inherited parent and its current child motion, not a trade.

    Local DOWN/UP children, terminal *watch* flags and Rail/Mountain display
    changes do not retire the sovereign parent.  Its actual identity, source
    continuity and an affirmative transfer do.  EMA30 supplies no slope vote.
    """
    md = snapshot.metadata
    geometry = _map(md.get("current_geometry"))
    mission_parent = _map(_map(md.get("mission_context")).get("parent"))
    history = directional_parent_evidence(snapshot)
    side = _side(history.get("side"))
    sign = 1.0 if side is Side.YES else -1.0
    values = {key: _num(geometry.get(key))
              for key in ("btc_change6", "btc_change9", "ema9_change6")}
    native = str(geometry.get("current_native_direction") or "").upper()
    current_direction = "UP" if side is Side.YES else "DOWN"
    opposed_direction = "DOWN" if side is Side.YES else "UP"
    covered = side is not None and all(value is not None for value in values.values())
    pulling_back = bool(covered and native == opposed_direction
                        and all(sign * value < 0 for value in values.values()))
    rejoining = bool(covered and native == current_direction
                    and all(sign * value > 0 for value in values.values()))
    age = _num(snapshot.contract_age_s)
    source_ms = _num(geometry.get("epoch_ms"))
    residence_start = _num(history.get("observed_residence_start_source_ms"))
    generation = md.get("geometry_continuity_generation")
    parent_id = mission_parent.get("id")
    early = age is not None and 0 <= age <= OPENING_RAIL_FISHING_WINDOW_S
    inherited = bool(source_ms is not None and residence_start is not None
                     and age is not None and residence_start < source_ms - age * 1000.0)
    parent_valid = bool(isinstance(parent_id, str) and parent_id
        and _side(mission_parent.get("side")) is side
        and str(mission_parent.get("status") or "").upper() == "ACTIVE"
        and mission_parent.get("invalidated") is not True
        and mission_parent.get("continuity_generation") == generation
        and _num(mission_parent.get("source_ms")) == source_ms)
    source_current = bool(source_ms is not None and md.get("physical_current") is True
        and type(generation) is int and generation >= 0
        and current_source_is_fresh(snapshot, source_ms, max_age_seconds=5.0))
    qualified = bool(early and history.get("qualified") is True and side is not None
                     and inherited and parent_valid and source_current)
    identity = (snapshot.ticker, parent_id, side.value if side else None,
                generation, residence_start, geometry.get("connection_epoch"))
    return {"qualified": qualified, "early": early, "side": side,
            "inherited": inherited, "parent_valid": parent_valid,
            "source_current": source_current, "identity": identity,
            "parent_id": parent_id, "source_ms": source_ms,
            "residence_start_source_ms": residence_start,
            "continuity_generation": generation, "contract_age_s": age,
            "pulling_back": pulling_back, "rejoining": rejoining,
            "native_direction": native, "motion": values, "history": history}


def _is_opening_parent_continuation(intent: ToolIntent, side: Side | None) -> bool:
    """Cover equivalent Commander and Rail-adviser admission routes."""
    if (side is None or intent.side is not side
            or intent.action not in (Action.ENTER, Action.RELAY)):
        return False
    return bool(
        intent.metadata.get("commander_primary_candidate") is True
        and intent.metadata.get("commander_candidate_family") == "MOUNTAIN_CONTRACT_LEG"
        or intent.tool == "RAIL"
            and intent.reason in {"RAIL_MAIN_VALUE", "RAIL_EMA9_DIP_VALUE"})


def opening_rail_pullback_denial(intent: ToolIntent, snapshot: MarketSnapshot) -> str | None:
    """Do not buy a continuing parent's early dip while current motion opposes it.

    This is deliberately independent of retained watch state: another route,
    adviser or freshly constructed Commander cannot bypass the same current
    evidence.  A neutral settling sample is not an opposing continuation.
    """
    context = _opening_rail_context(snapshot)
    if (context["early"] and context["history"].get("qualified") is True
            and context["pulling_back"]
            and _is_opening_parent_continuation(intent, context["side"])):
        return "COMMANDER_OPENING_RAIL_DIP_KEEP_FISHING"
    return None


class OpeningRailValueWatch:
    """Commander-owned memory of an earned premium opening deferred on a dip.

    WAIT never consumes the opening.  The original parent, ticker, residence
    and source generation stay bound while its child dips/rejoins.  Only a
    current <=35c rejoin with existing TP/runway proof may publish a new
    candidate, including after the old 60-second premium window has closed.
    """

    def __init__(self) -> None:
        self.state: dict[str, Any] | None = None
        self._latest_identity: tuple[Any, ...] | None = None
        self._latest_source_ms: float | None = None
        self._consumed_identities: set[tuple[Any, ...]] = set()

    def observe(self, snapshot: MarketSnapshot,
                intents: tuple[ToolIntent, ...] | list[ToolIntent] = ()) -> dict[str, Any]:
        context = _opening_rail_context(snapshot)
        if not context["qualified"]:
            self.state = None
            return context
        if context["identity"] in self._consumed_identities:
            self.state = None
            return {**context, "qualified": False, "already_filled": True}
        if (self._latest_identity == context["identity"] and self._latest_source_ms is not None
                and context["source_ms"] < self._latest_source_ms):
            self.state = None
            return {**context, "qualified": False, "source_backstep": True}
        if self._latest_identity != context["identity"]:
            self.state = None
        self._latest_identity = context["identity"]
        self._latest_source_ms = context["source_ms"]
        side = context["side"]
        ask = _num(snapshot.ask_for(side))
        if self.state is None and context["pulling_back"]:
            # Arm only an otherwise-earned premium first-minute opening.  A
            # pre-entry wiggle with no eligible opening cannot latch a blanket
            # delay onto the next good entry (PID19996 winners #1 and #2).
            earned = next((intent for intent in intents
                if _is_opening_parent_continuation(intent, side)
                and _map(intent.metadata.get("commander_physical_evidence")).get("opening_continuation") is True
                and context["contract_age_s"] <= MOUNTAIN_ROLLOVER_CONTINUATION_WINDOW_S
                and ask is not None and MOUNTAIN_CONTRACT_LEG_MAX < ask <= MOUNTAIN_ROLLOVER_CONTINUATION_MAX
                and intent.max_price is not None and ask <= intent.max_price), None)
            if earned is not None:
                identity = (f"OPENING_RAIL_VALUE:{snapshot.ticker}:{context['parent_id']}:"
                            f"{context['continuity_generation']}:{context['residence_start_source_ms']}:"
                            f"{context['identity'][-1]}")
                self.state = {"identity": context["identity"], "side": side,
                    "parent_id": context["parent_id"], "mission_id": identity,
                    "deferred_mission_id": earned.metadata.get("physical_mission_id"),
                    "deferred_reason": earned.reason, "deferred_ask": ask,
                    "deferred_source_ms": context["source_ms"],
                    "deferred_contract_age_s": context["contract_age_s"],
                    "lowest_observed_ask": ask, "last_source_ms": context["source_ms"]}
        if self.state is not None:
            self.state["last_source_ms"] = context["source_ms"]
            if ask is not None and ask > 0:
                self.state["lowest_observed_ask"] = min(self.state["lowest_observed_ask"], ask)
        return context

    def _ready(self, snapshot: MarketSnapshot, context: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
        if self.state is None or not context["qualified"]:
            return False, {}
        side = context["side"]
        ask = _num(snapshot.ask_for(side))
        tp = _map(snapshot.metadata.get("tp_geometry"))
        opposing_tp = bool(tp.get("contract_ownership") in {"STARTING_LEG_FAVORED", "BOUNCE_FAVORED"}
            and _side(tp.get("contract_ownership_side")) not in (None, side))
        runway, runway_evidence = settlement_runway_for_side(snapshot, side)
        ready = bool(context["rejoining"] and ask is not None and 0 < ask <= OPENING_RAIL_VALUE_MAX
            and ask < self.state["deferred_ask"] and not opposing_tp
            and tp.get("target_between_ema9_ema30") is not True and runway)
        return ready, {"return_runway": runway_evidence, "opposing_tp_ownership": opposing_tp}

    def entry_denial(self, intent: ToolIntent, snapshot: MarketSnapshot) -> str | None:
        denial = opening_rail_pullback_denial(intent, snapshot)
        if denial is not None:
            return denial
        context = self.observe(snapshot)
        if intent.reason == "COMMANDER_OPENING_RAIL_DIP_VALUE_REJOIN" and self.state is None:
            return "COMMANDER_OPENING_RAIL_CURRENT_WATCH_REQUIRED"
        if intent.reason == "COMMANDER_OPENING_RAIL_DIP_VALUE_REJOIN":
            evidence = _map(intent.metadata.get("commander_physical_evidence"))
            expected_mission = (f"COMMANDER:MOUNTAIN_CONTRACT_LEG:{self.state['side'].value}:"
                                f"{self.state['mission_id']}")
            source_time = _num(intent.source_time)
            if (intent.side is not self.state["side"]
                    or intent.metadata.get("physical_mission_id") != expected_mission
                    or evidence.get("identity") != self.state["mission_id"]
                    or evidence.get("parent_id") != self.state["parent_id"]
                    or evidence.get("continuity_generation") != context["continuity_generation"]
                    or evidence.get("observed_residence_start_source_ms") != context["residence_start_source_ms"]
                    or evidence.get("source_connection_epoch") != context["identity"][-1]
                    or evidence.get("deferred_source_ms") != self.state["deferred_source_ms"]
                    or evidence.get("deferred_mission_id") != self.state["deferred_mission_id"]
                    or source_time is None
                    or abs(source_time * 1000. - context["source_ms"]) > .001
                    or evidence.get("current_source_ms") != context["source_ms"]
                    or not current_source_is_fresh(snapshot, source_time * 1000., max_age_seconds=5.0)):
                return "COMMANDER_OPENING_RAIL_CURRENT_WATCH_IDENTITY_REQUIRED"
        if self.state is not None and _is_opening_parent_continuation(intent, context["side"]):
            ready, _ = self._ready(snapshot, context)
            if not ready:
                return "COMMANDER_OPENING_RAIL_WAIT_FOR_VALUE_REJOIN"
        return None

    def candidate(self, snapshot: MarketSnapshot) -> ToolIntent | None:
        context = self.observe(snapshot)
        ready, proof = self._ready(snapshot, context)
        if not ready or self.state is None:
            return None
        state = self.state
        return _candidate(snapshot, family="MOUNTAIN_CONTRACT_LEG", side=context["side"],
            max_price=OPENING_RAIL_VALUE_MAX, size_override=25.0,
            reason="COMMANDER_OPENING_RAIL_DIP_VALUE_REJOIN",
            evidence={"identity": state["mission_id"], "parent_id": state["parent_id"],
                "entry_side": context["side"].value, "entry_location": "INHERITED_PARENT_OPENING_DIP_REJOIN",
                "opening_rail_fishing": True, "contract_age_s": context["contract_age_s"],
                "search_window_s": OPENING_RAIL_FISHING_WINDOW_S,
                "deferred_source_ms": state["deferred_source_ms"],
                "deferred_contract_age_s": state["deferred_contract_age_s"],
                "deferred_ask": state["deferred_ask"], "deferred_reason": state["deferred_reason"],
                "deferred_mission_id": state["deferred_mission_id"],
                "lowest_observed_ask": state["lowest_observed_ask"],
                "current_ask": snapshot.ask_for(context["side"]),
                "observed_residence_start_source_ms": context["residence_start_source_ms"],
                "continuity_generation": context["continuity_generation"],
                "source_connection_epoch": context["identity"][-1],
                "current_source_ms": context["source_ms"],
                "current_native_direction": context["native_direction"],
                "current_rejoin": dict(context["motion"]), "historical_flow": dict(context["history"]),
                "clock_alone_has_trade_authority": False, **proof})

    def consume(self, intent: ToolIntent, *, ticker: str) -> tuple[str, ...]:
        if (self.state is None or self.state["identity"][0] != ticker
                or not _is_opening_parent_continuation(intent, self.state["side"])):
            return ()
        missions = tuple(value for value in (self.state["deferred_mission_id"],
            f"COMMANDER:MOUNTAIN_CONTRACT_LEG:{self.state['side'].value}:{self.state['mission_id']}")
            if isinstance(value, str) and value)
        self._consumed_identities.add(self.state["identity"])
        self.state = None
        return missions


def physical_entry_candidates(snapshot: MarketSnapshot, *,
                              opening_watch: OpeningRailValueWatch | None = None,
                              consumed_missions: set[tuple[str, str]] | None = None) -> tuple[ToolIntent, ...]:
    """Publish ordinary MAIN candidates with the same parent-quality proof.

    Every internal branch, including early level-match/extreme returns, passes
    here.  A later unqualified continuation classifier cannot create an escape
    from current established-parent quality at this positive-briefing boundary.
    """
    candidates = tuple(intent for intent in _physical_entry_candidates(snapshot)
                       if main_return_matches_established_parent(intent, snapshot)
                       and (consumed_missions is None or
                            (snapshot.ticker, str(intent.metadata.get("physical_mission_id") or ""))
                            not in consumed_missions))
    if opening_watch is not None:
        opening_watch.observe(snapshot, candidates)
        rejoin = opening_watch.candidate(snapshot)
        if rejoin is not None and main_return_matches_established_parent(rejoin, snapshot):
            candidates += (rejoin,)
        return tuple(intent for intent in candidates
                     if opening_watch.entry_denial(intent, snapshot) is None)
    return tuple(intent for intent in candidates
                 if opening_rail_pullback_denial(intent, snapshot) is None)


def _recent_level_return_location_ready(snapshot: MarketSnapshot, match: Mapping[str, Any]) -> bool:
    """PID19616 #3: an overshot completed level is not a defended retest.

    The historical detector can describe a broad old low/high cluster using
    25% of the 180s range. A $25 first-class Mountain return instead needs
    contemporaneous proximity to the **same** completed level it cites.
    A wide far-side break cannot be rescued merely by a six-second bounce.
    This is a positive Commander candidate-quality condition, not a tool veto.
    """
    geometry = _map(snapshot.metadata.get("current_geometry"))
    current = _num(geometry.get("btc_price"))
    anchor = _num(match.get("anchor"))
    distance = _num(match.get("distance_btc"))
    age = _num(match.get("age_s"))
    anchor_time = _num(match.get("anchor_time"))
    # The old authorized completed-minute references are 4–30 minutes old.
    if (anchor is None or age is None or not 240.0 <= age <= 1800.0
            or anchor_time is None or anchor_time > snapshot.now_ts):
        return False
    if current is not None:
        distance = current - anchor  # Native current price outranks a cached distance.
    if distance is None:
        return False
    range60 = _num(geometry.get("range60"))
    proximity = max(20.0, 0.25 * range60) if range60 is not None and range60 > 0 else 20.0
    return abs(distance) <= proximity


def _counterparent_level_rejection_sustained(snapshot: MarketSnapshot, side: Side) -> bool:
    """PID23160 #1: a single cheap bounce cannot declare an old level rejected.

    Applies only when a **fresh native parent** remains opposite the return.
    Demands physical return-side progress across 6, 9 and 30 seconds, rather
    than promotion of a one-candle echo during a living EMA9 leg. A genuine
    near-level, sustained rejection (including PID18244 #6 NO) stays valid.
    Unknown or stale parent does not gain authority from this rule; it leaves
    the existing parent/runway and source-current admission controls intact.
    """
    md = _map(snapshot.metadata)
    if md.get("physical_current") is not True:
        return True  # Old source/currentness checks retain their own authority.
    geo = _map(md.get("current_geometry"))
    # `current_native_direction` is a micro child, and can read UP during
    # a confirmed DOWN EMA9-gap parent (PID23160 #1). Use the source-observed
    # EMA9-gap chapter and actual signed gap, not the micro direction.
    lifecycle = _map(_map(md.get("ema9_ema30_cross_context")).get("gap_lifecycle"))
    side_name = str(lifecycle.get("current_side") or "").upper()
    gap = _num(geo.get("ema_gap"))
    source_ms = _num(geo.get("epoch_ms"))
    if gap is None or source_ms is None:
        # Historical approved controls predate high-frequency geometry packets.
        # They are not contemporary 6/9/30s source evidence, so this NEW
        # restriction cannot retroactively change their prior authorization.
        # Complete modern packets are evaluated strictly below.
        return True
    if abs(source_ms - snapshot.now_ts * 1000.0) > 3000.0:
        return False
    parent = Side.YES if side_name == "YES" else Side.NO if side_name == "NO" else None
    if gap is not None and parent is not None:
        if (gap > 0 and parent is Side.NO) or (gap < 0 and parent is Side.YES):
            return False  # Conflicting direct current physical source is never entry proof.
    if parent is None or parent is side:
        return True
    mountain = _map(md.get("mountain"))
    if mountain.get("terminal_evidence_qualified") is True:
        return True  # Terminal proof uses the already-approved mature-edge path.
    sign = 1.0 if side is Side.YES else -1.0
    btc6 = _num(geo.get("btc_change6"))
    btc9 = _num(geo.get("btc_change9"))
    btc30 = _num(geo.get("btc_change30"))
    ema6 = _num(geo.get("ema9_change6"))
    if any(x is None for x in (btc6, btc9, btc30, ema6)):
        return False
    turn9 = sign * btc9
    return bool(turn9 >= 10.0
                and sign * btc6 >= 0.30 * turn9
                and sign * btc30 >= 0.50 * turn9
                and sign * ema6 > 0.0)


def _mature_premium_opening_has_fresh_momentum(
    snapshot: MarketSnapshot, side: Side, residence_age_s: float | None,
    ask: float | None,
) -> bool:
    """PID19616 #8: age identifies a transition WATCH, not opening authority.

    For an already >2.5-contract inherited parent, a premium first-minute
    entry must show with-side *net* 60s BTC advance, not merely 30s direction.
    Less expensive value entries and younger proven openings keep their
    existing admission rules. Never require reversal or end a mature Rail.
    """
    if (residence_age_s is None or residence_age_s < 2.5 * 900.0
            or ask is None or ask <= OPENING_RAIL_VALUE_MAX):
        return True
    geo = _map(snapshot.metadata.get("current_geometry"))
    change60 = _num(geo.get("btc_change60"))
    range60 = _num(geo.get("range60"))
    if change60 is None or range60 is None or range60 <= 0:
        return False
    sign = 1.0 if side is Side.YES else -1.0
    return sign * change60 >= max(12.0, 0.20 * range60)



def _preopen_observed_ema9_sprout_continuation(
    snapshot: MarketSnapshot, historical_flow: Mapping[str, Any],
) -> tuple[Side, dict[str, Any]] | None:
    """PID10760: strictly source-witnessed *pre-open momentum*, not a fake Rail.

    A 15-minute ticker can become actionable after its BTC geometry started
    moving, while the native EMA9 gap has not yet established an old parent.
    The old >15min residence proof must NEVER be fabricated from this short
    history. This separate, exceptional first-minute Mountain-contract-leg
    candidate requires a truly current pre-open-spanning source segment,
    synchronized near-spine EMA9 turn, independently positive BTC6/9/30/60
    and EMA9 6/30/60 evidence, current Mountain child, and explicit TP
    starting-leg ownership. Source/quote/entry constraints remain intact.

    User-authorized rollover exception only; ordinary first-minute WAIT and
    the stronger historical inherited Rail route are unchanged.
    """
    md = snapshot.metadata
    geo = _map(md.get("current_geometry"))
    cross = _map(md.get("ema9_ema30_cross_context"))
    lifecycle = _map(cross.get("gap_lifecycle"))
    coverage = _map(cross.get("coverage"))
    mountain = _map(md.get("mountain"))
    parent = _map(mountain.get("parent_structure"))
    tp = _map(md.get("tp_geometry"))
    child = _side(mountain.get("owner_side"))
    if (md.get("physical_current") is not True
            or not snapshot.quote_current or not snapshot.depth_available
            or not snapshot.entry_allowed
            or child is None
            or historical_flow.get("qualified") is True
            or md.get("release_in_progress") is True
            or md.get("release_confirmed_current") is True
            or mountain.get("terminal_evidence_qualified") is True
            or parent.get("parent_terminal_ready") is True
            or tp.get("target_between_ema9_ema30") is True
            or tp.get("contract_ownership") != "STARTING_LEG_FAVORED"
            or _side(tp.get("contract_ownership_side")) is not child
            or geo.get("arc_origin_observed") is not True
            or geo.get("arc_direction") != ("UP" if child is Side.YES else "DOWN")
            or geo.get("current_native_direction") != ("UP" if child is Side.YES else "DOWN")
            or lifecycle.get("observed_side_residence_continuous") is not True
            or coverage.get("connection_epoch") != geo.get("connection_epoch")
            or geo.get("connection_epoch") is None):
        return None
    age = _num(snapshot.contract_age_s)
    ask = _num(snapshot.ask_for(child))
    source = _num(geo.get("epoch_ms"))
    cross_source = _num(cross.get("source_ms"))
    first = _num(coverage.get("first_source_ms"))
    last = _num(coverage.get("last_source_ms"))
    observed = _num(coverage.get("sample_count"))
    maximum_gap_s = _num(coverage.get("max_observed_source_gap_seconds"))
    starting_source = _num(geo.get("arc_start_ms"))
    arc_age = _num(geo.get("arc_age_sec"))
    range60 = _num(geo.get("range60"))
    gap = _num(geo.get("ema_gap"))
    current = _num(geo.get("btc_price"))
    ema9 = _num(geo.get("ema9"))
    ema30 = _num(geo.get("ema30"))
    required_move = _num(tp.get("required_move_to_target_btc"))
    numbers = (age, ask, source, cross_source, first, last, observed,
               maximum_gap_s, starting_source, arc_age, range60,
               gap, current, ema9, ema30, required_move)
    if any(x is None for x in numbers):
        return None
    sign = 1.0 if child is Side.YES else -1.0
    if (not 20.0 <= age <= 59.0
            or not 0 < ask <= MOUNTAIN_ROLLOVER_CONTINUATION_MAX
            or not 12.0 <= arc_age <= 59.0
            or not first < (snapshot.now_ts - age - 30.0) * 1000.0
            or first >= source or not 40 <= observed
            or not 0 <= maximum_gap_s <= 5.0
            or not abs(source - cross_source) <= 1.0
            or not abs(source - last) <= 1000.0
            or not current_source_is_fresh(snapshot, source, max_age_seconds=3.0)
            or not first <= starting_source <= source
            or not range60 > 0 or not abs(ema9 - ema30 - gap) < 0.05
            # A strong established opposite gap cannot be rebranded as a turn.
            or not -10.0 <= sign * gap <= 8.0
            or not 0 <= sign * required_move <= max(18.0, 0.5 * range60)):
        return None
    btc = {h: _num(geo.get("btc_change"+h)) for h in ("6", "9", "30", "60")}
    ema = {h: _num(geo.get("ema9_change"+h)) for h in ("6", "30", "60")}
    turn = _num(_map(cross.get("current_gap_motion_6s")).get("signed_gap_change_btc"))
    if (any(v is None for v in (*btc.values(), *ema.values(), turn))
            or sign * btc["6"] < 12.0
            or sign * btc["9"] < 12.0
            or sign * btc["30"] < 15.0
            or sign * btc["60"] < max(20.0, .45 * range60)
            or sign * ema["6"] < 3.0
            or sign * ema["30"] < 4.0
            or sign * ema["60"] < 4.0
            or sign * turn < 2.0):
        return None
    return child, {
        "identity": f"SOURCE_OBSERVED_PREOPEN:{geo.get('arc_id')}:{child.value}:{geo.get('connection_epoch')}",
        "entry_location": "PREOPEN_OBSERVED_YOUNG_EMA9_CONTINUATION",
        "opening_continuation": True,
        "historical_parent_qualified": False,
        "preopen_source_coverage_start_ms": first,
        "preopen_source_coverage_last_ms": last,
        "source_connection_epoch": geo.get("connection_epoch"),
        "observed_btc_change60": btc["60"],
        "observed_ema9_change60": ema["60"],
        "current_arc_age_s": arc_age,
        "contract_age_s": age,
        "gap_side": lifecycle.get("current_side"),
        "gap_btc": gap,
        "tp_ownership": tp.get("contract_ownership"),
        "required_move_to_target_btc": required_move,
        "return_ask": ask,
        "causal_parent_claim": "CURRENT_EMA9_CHILD_ONLY_NOT_MATURE_INHERITED_PARENT",
    }


def _current_ema9_renewed_flow_rejoin(snapshot: MarketSnapshot) -> tuple[Side, dict[str, Any]] | None:
    """PID23160: measured with-EMA9 rejoin, not a generic mid-leg chase.

    A strong nine-second continuation can follow a real thirty-second lull
    within a still-young, observed native EMA9 parent. Require physical
    proximity to EMA9, favorable TP and target runway, *current* momentum,
    and an inexpensive native quote. This may operate while an unproven wide
    Heist reports center; the Heist classifier is evidence, not a veto.
    Once the window is spent, WAIT for the next earned location. No specialist
    WAIT creates or suppresses this Commander-positive proposal.
    """
    md = snapshot.metadata
    if (md.get("source") != "DIRECT_BTC_AND_NATIVE_KALSHI"
            or md.get("physical_current") is not True
            or not snapshot.quote_current or not snapshot.depth_available
            or not snapshot.entry_allowed
            or md.get("release_in_progress") is True
            or md.get("release_confirmed_current") is True):
        return None
    geo = _map(md.get("current_geometry"))
    mountain = _map(md.get("mountain"))
    parent = _map(mountain.get("parent_structure"))
    tp = _map(md.get("tp_geometry"))
    native_parent = str(geo.get("parent_direction") or "").upper()
    side = Side.YES if native_parent in {"UP", "YES"} else Side.NO if native_parent in {"DOWN", "NO"} else None
    if side is None:
        return None
    expected = "UP" if side is Side.YES else "DOWN"
    if (geo.get("arc_direction") != expected
            or geo.get("current_native_direction") != expected
            or geo.get("arc_origin_observed") is not True
            or mountain.get("terminal_evidence_qualified") is True
            or parent.get("parent_terminal_ready") is True
            or tp.get("target_between_ema9_ema30") is True
            or tp.get("contract_ownership") != "STARTING_LEG_FAVORED"
            or _side(tp.get("contract_ownership_side")) is not side):
        return None
    src = _num(geo.get("epoch_ms"))
    arc_age = _num(geo.get("arc_age_sec"))
    range60 = _num(geo.get("range60"))
    range180 = _num(geo.get("range180"))
    spot = _num(geo.get("btc_price"))
    e9 = _num(geo.get("ema9"))
    e30 = _num(geo.get("ema30"))
    gap = _num(geo.get("ema_gap"))
    ask = _num(snapshot.ask_for(side))
    capacity = _num(tp.get("comparable_parent_amplitude_btc"))
    required = _num(tp.get("required_move_to_target_btc"))
    age = _num(snapshot.contract_age_s)
    btc = {h: _num(geo.get("btc_change"+h)) for h in ("6","9","30","60")}
    ema6,ema30 = _num(geo.get("ema9_change6")),_num(geo.get("ema9_change30"))
    numbers = (src, arc_age, range60, range180, spot, e9, e30, gap,
               ask, capacity, required, age, ema6, ema30, *btc.values())
    if any(v is None for v in numbers):
        return None
    sign = 1.0 if side is Side.YES else -1.0
    progress60 = sign * btc["60"]
    progress30 = sign * btc["30"]
    contact_distance = abs(spot - e9)
    if (not current_source_is_fresh(snapshot, src, max_age_seconds=3.0)
            or not 120.0 <= age <= 660.0
            or not 45.0 <= arc_age <= 150.0
            or not range60 >= 20.0 or not range180 >= range60
            or not 0.0 < ask <= 0.30
            or not 8.0 <= sign * gap <= 0.25 * range180
            or not abs(e9-e30-gap) <= 0.1
            or not contact_distance <= 0.50 * range60
            or not 0.0 < required <= 0.50 * capacity
            or not progress60 >= max(20.0, 0.50 * range60)
            or not 0.0 <= progress30 <= 0.35 * progress60
            or not sign * btc["9"] >= max(10.0, 0.20 * range60)
            or not sign * btc["6"] >= max(5.0, 0.12 * range60)
            or not sign * ema6 >= max(1.0, 0.05 * range60)
            or not sign * ema30 >= 0.05 * range60):
        return None
    return side, {"identity":f"OBSERVED_REJOIN:{snapshot.ticker}:{geo.get('arc_id')}:{side.value}",
        "entry_side":side.value,"entry_location":"CURRENT_EMA9_RENEWED_PARENT_REJOIN",
        "with_ema9":True,"current_source_ms":src,"current_arc_id":geo.get("arc_id"),
        "current_arc_age_s":arc_age,"price_to_ema9_btc":contact_distance,
        "range60":range60,"btc_change6":btc["6"],"btc_change9":btc["9"],
        "btc_change30":btc["30"],"btc_change60":btc["60"],
        "ema9_change6":ema6,"ema9_change30":ema30,"target_remaining_btc":required,
        "comparable_parent_amplitude_btc":capacity,
        "heist_owner_cannot_veto_current_ema9":True,
        "opening_exception":False,"premium_exception":False,
        "risk_tier":"REGULAR_10_DOLLAR_ONLY"}


def _physical_entry_candidates(snapshot: MarketSnapshot) -> tuple[ToolIntent, ...]:
    """Build Mountain / Rolling-Mountain proposals for the shared quality check."""
    if snapshot.metadata.get("physical_current") is False:
        return ()

    # FAST RETURN PHASE — operator authorization 2026-11-03.
    # Any fresh parent-scale extreme on an already-extended Mountain opens the
    # opposite return side when that contract is executable at <=20c. This is
    # evaluated before Heist/Release overlay suppression so those latches have
    # zero veto authority over the physically-earned return phase.
    raw_mountain = _map(snapshot.metadata.get("mountain"))
    historical_flow = directional_parent_evidence(snapshot)
    raw_parent = _map(raw_mountain.get("parent_structure"))
    raw_tp = _map(snapshot.metadata.get("tp_geometry"))
    raw_target_junction = raw_tp.get("target_between_ema9_ema30") is True
    raw_strategy = _map(snapshot.metadata.get("commander_strategy"))
    raw_owner = _side(raw_mountain.get("owner_side")) or _side(raw_strategy.get("owned_side"))
    # PID15740: a witnessed continuous inherited UP/DOWN residence can remain
    # valid although the ORIGINAL EMA9/EMA30 crossing predates process startup.
    # At a fresh ticker start, honor the already-authorized <=55c exception
    # only when current physical leg, TP, gap and target all agree.
    opening_geo = _map(snapshot.metadata.get("current_geometry"))
    opening_tp_side = _side(raw_tp.get("contract_ownership_side"))
    opening_owner = _side(historical_flow.get("side"))
    opening_arc_age = _num(opening_geo.get("arc_age_sec"))
    opening_parent = _map(raw_parent)
    opening_btc30 = _num(opening_geo.get("btc_change30"))
    opening_ema30 = _num(opening_geo.get("ema9_change30"))
    opening_contract_age = float(snapshot.contract_age_s)
    opening_ask = (_num(snapshot.ask_for(opening_owner))
                   if opening_owner is not None else None)
    opening_sign = 1.0 if opening_owner is Side.YES else -1.0
    opening_residence_start = _num(historical_flow.get("observed_residence_start_source_ms"))
    source_time_ms = _num(opening_geo.get("epoch_ms"))
    if (historical_flow.get("qualified") is True
            and opening_owner is not None
            and 0.0 <= opening_contract_age <= MOUNTAIN_ROLLOVER_CONTINUATION_WINDOW_S
            and opening_arc_age is not None and opening_arc_age > opening_contract_age + 1.0
            and opening_residence_start is not None and source_time_ms is not None
            and opening_residence_start < source_time_ms - opening_contract_age * 1000.0
            and str(opening_geo.get("arc_direction") or "").upper()
                == ("UP" if opening_owner is Side.YES else "DOWN")
            and opening_btc30 is not None and opening_sign * opening_btc30 > 0
            and opening_ema30 is not None and opening_sign * opening_ema30 > 0
            and opening_parent.get("parent_terminal_ready") is not True
            and raw_mountain.get("terminal_evidence_qualified") is not True
            and not raw_target_junction
            and raw_tp.get("contract_ownership") == "STARTING_LEG_FAVORED"
            and opening_tp_side is opening_owner
            and opening_ask is not None
            and 0 < opening_ask <= MOUNTAIN_ROLLOVER_CONTINUATION_MAX
            and _mature_premium_opening_has_fresh_momentum(
                snapshot, opening_owner,
                _num(historical_flow.get("observed_residence_age_s")), opening_ask)):
        return (_candidate(snapshot, family="MOUNTAIN_CONTRACT_LEG",
            side=opening_owner, max_price=MOUNTAIN_ROLLOVER_CONTINUATION_MAX,
            reason="COMMANDER_OBSERVED_INHERITED_PARENT_FIRST_MINUTE_CONTINUATION",
            size_override=25.0,
            evidence={
                "identity": f"OBSERVED_PARENT:{opening_owner.value}:{snapshot.ticker}",
                "entry_location": "INHERITED_YOUNG_LEG_FIRST_MINUTE",
                "opening_continuation": True,
                "entry_side": opening_owner.value,
                "contract_age_s": opening_contract_age,
                "current_arc_age_s": opening_arc_age,
                "observed_residence_start_source_ms": opening_residence_start,
                "tp_ownership": raw_tp.get("contract_ownership"),
                "return_ask": opening_ask,
                "historical_flow": dict(historical_flow),
                "same_side_runway": "TP_STARTING_LEG_FAVORED",
            }),)
    # PID10760: a precontract-observed BTC/EMA9 turn can outlive ticker
    # discovery even when a reset child is too young to be an inherited Rail.
    # Do not fabricate a >=900s EMA9 parent, broaden early open pricing, or
    # waive TP/runway. This is a separate strictly current positive MAIN
    # opening location with the existing $25 exceptional tier.
    preopen = _preopen_observed_ema9_sprout_continuation(snapshot, historical_flow)
    if preopen is not None:
        preopen_side, preopen_proof = preopen
        return (_candidate(snapshot, family="MOUNTAIN_CONTRACT_LEG",
            side=preopen_side, max_price=MOUNTAIN_ROLLOVER_CONTINUATION_MAX,
            reason="COMMANDER_OBSERVED_PREOPEN_EMA9_SPROUT_CONTINUATION",
            size_override=25.0, evidence=preopen_proof),)

    # An inexpensive renewed *same-parent* episode may be available while
    # an unresolved wide Heist owns the display. This requires direct current
    # proof from BTC+EMA9/TP, not a directional label or an adviser vote. It
    # cannot override a true terminal Mountain or a fully spent parent.
    rejoin = _current_ema9_renewed_flow_rejoin(snapshot)
    if rejoin is not None:
        rejoin_side, rejoin_evidence = rejoin
        return (_candidate(snapshot, family="MOUNTAIN_CONTRACT_LEG",
            side=rejoin_side, max_price=0.30,
            reason="COMMANDER_CURRENT_EMA9_RENEWED_PARENT_REJOIN",
            size_override=10.0, evidence=rejoin_evidence),)

    if raw_owner is not None:
        full_scale = _map(raw_mountain.get("full_leg_scale_evidence"))
        completed_ref = _map(raw_mountain.get("completed_minute_parent_reference"))
        diagnostics = _map(raw_mountain.get("diagnostics"))
        parent_measurements = _map(raw_parent.get("measurements"))
        parent_age = (_num(raw_parent.get("parent_age_s"))
                      or _num(parent_measurements.get("age_seconds"))
                      or _num(diagnostics.get("parent_age_s"))
                      or _num(diagnostics.get("current_age_s")))
        extended = bool(
            full_scale.get("qualified") is True
            or completed_ref.get("mature_extension") is True
            or raw_parent.get("extended_parent") is True
            or (parent_age is not None and parent_age >= 360.0
                and str(raw_parent.get("parent_phase") or "").upper() in {"MATURE", "ROLLING"})
        )
        source_ms = (_num(raw_mountain.get("source_ms"))
                     or _num(diagnostics.get("source_ms"))
                     or snapshot.now_ts * 1000.0)
        extreme_ms = (_num(raw_mountain.get("edge_extreme_ms"))
                      or _num(raw_parent.get("extreme_source_ms"))
                      or _num(diagnostics.get("edge_extreme_ms")))
        timestamp_fresh_extreme = bool(
            extreme_ms is not None and source_ms is not None
            and -2000.0 <= source_ms - extreme_ms <= 90000.0
        )
        current_edge_fresh = bool(
            raw_mountain.get("edge_window_active") is True
            or raw_mountain.get("terminal_evidence_qualified") is True
            or (raw_mountain.get("mature_edge") is True and raw_mountain.get("edge_id"))
        )
        fresh_extreme = bool(timestamp_fresh_extreme or current_edge_fresh)
        # PID14156 #2: neither the historical parent's age nor a cheap
        # opposing quote turns a newborn 12.49-second child arc with a 2.21s
        # extreme into a mature terminal Mountain edge. PID17588 #2 is an
        # approved actual 60.45s current DOWN arc with 27s elapsed since its
        # extreme, but its recorder predates the full-scale-evidence field.
        # Therefore retain its source-observed one-minute current-arc proof;
        # do not require an added metadata field that did not yet exist.
        current_geometry = _map(snapshot.metadata.get("current_geometry"))
        current_arc_age = _num(current_geometry.get("arc_age_sec"))
        current_arc_id = str(current_geometry.get("arc_id") or "")
        recorded_arc_id = str(raw_mountain.get("current_arc_id") or "")
        observed_extreme_age = ((source_ms - extreme_ms) / 1000.0
                                if source_ms is not None and extreme_ms is not None
                                else None)
        observed_parent_scale = bool(
            current_arc_age is not None and current_arc_age >= 45.0
            and observed_extreme_age is not None and observed_extreme_age >= 15.0
            and current_arc_id and current_arc_id == recorded_arc_id
            and current_geometry.get("arc_origin_observed") is True
            and raw_mountain.get("source_ms") is not None
            and abs(float(raw_mountain.get("source_ms")) - float(current_geometry.get("epoch_ms") or 0)) <= 3000.0
        )
        current_parent_scale = bool(
            full_scale.get("qualified") is True
            or completed_ref.get("mature_extension") is True
            or observed_parent_scale
            or (raw_mountain.get("mature_edge") is True
                and raw_mountain.get("terminal_evidence_qualified") is True
                and (raw_mountain.get("edge_window_active") is True
                     or raw_mountain.get("edge_id")))
        )
        return_side = _opposite(raw_owner)
        return_ask = _num(snapshot.ask_for(return_side))
        # A cheap opposing ask on a child top is not permission to fade a
        # still-separated 3-4-contract parent.  Wait for an *actual* gap
        # collapse/transfer; the historical parent then ceases to qualify.
        if (historical_flow.get("qualified") is not True
                and extended and fresh_extreme and current_parent_scale
                and not raw_target_junction and return_ask is not None
                and 0.0 < return_ask <= MOUNTAIN_EDGE_MAX
                and raw_mountain.get("spent_edge") is not True
                and _first_counterfade_has_reversal_proof(snapshot, return_side, raw_mountain)
                and _counter_parent_return_briefing_ready(snapshot, return_side, raw_mountain)
                and _late_counter_return_has_runway(snapshot, return_side)):
            edge_id = str(raw_mountain.get("edge_id") or raw_mountain.get("current_arc_id")
                          or f"EXTREME:{int(extreme_ms or source_ms)}")
            return (_candidate(
                snapshot, family="MOUNTAIN_EDGE", side=return_side,
                max_price=MOUNTAIN_EDGE_MAX,
                reason="COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN",
                evidence={
                    "identity": edge_id, "edge_id": edge_id,
                    "outgoing_owner_side": raw_owner.value,
                    "entry_side": return_side.value,
                    "entry_location": "FRESH_EXTENDED_MOUNTAIN_EXTREME",
                    "fresh_extreme": True, "extended_mountain": True,
                    "extreme_source_ms": extreme_ms, "current_source_ms": source_ms,
                    "extreme_age_s": ((source_ms - extreme_ms) / 1000.0
                                      if extreme_ms is not None and source_ms is not None else None),
                    "return_ask": return_ask,
                    "full_leg_scale_evidence": dict(full_scale),
                    "completed_minute_parent_reference": dict(completed_ref),
                    "return_runway": {
                        "fast_return_override": True,
                        "basis": "OPERATOR_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20",
                        "ordinary_runway_veto_authority": False,
                    },
                    "overlay_veto_authority": False,
                    "release_wait_veto_authority": False,
                }, floor_policy_override=_return_seed_floor_policy()),)

    # PID7412 WITH-WIND PULLBACK — a long Rolling Mountain / Rail parent
    # and its shallow opposing child are DIFFERENT scales.  This route hunts
    # the established gap side when the child dips toward EMA9 and starts
    # returning, rather than fading the healthy parent because the opposite
    # contract is cheap.  Actual TP/runway and executable value still matter.
    if historical_flow.get("qualified") is True and not raw_target_junction:
        flow_side = _side(historical_flow.get("side"))
        geometry = _map(snapshot.metadata.get("current_geometry"))
        tp = _map(snapshot.metadata.get("tp_geometry"))
        current_arc = str(geometry.get("arc_direction") or "").upper()
        counter_child = bool(flow_side is Side.YES and current_arc == "DOWN"
                             or flow_side is Side.NO and current_arc == "UP")
        btc = _num(geometry.get("btc_price"))
        ema9 = _num(geometry.get("ema9"))
        r60 = _num(geometry.get("range60"))
        btc6 = _num(geometry.get("btc_change6"))
        e6 = _num(geometry.get("ema9_change6"))
        sign = 1.0 if flow_side is Side.YES else -1.0
        near_ema9 = bool(btc is not None and ema9 is not None
                            and r60 is not None and r60 > 0
                            and abs(btc-ema9) <= 0.65*r60)
        causal_rejoin = bool(btc6 is not None and e6 is not None
                             and r60 is not None and r60 > 0
                             and sign*btc6 > 0 and sign*e6 >= -.02*r60)
        tp_side = _side(tp.get("contract_ownership_side"))
        tp_agrees = bool(tp_side is flow_side and tp.get("contract_ownership") in
                         {"STARTING_LEG_FAVORED", "BOUNCE_FAVORED"})
        required = _num(tp.get("required_move_to_target_btc"))
        capacity = _num(tp.get("comparable_parent_amplitude_btc"))
        reachable = bool(required is not None and required >= 0 and capacity is not None
                         and capacity > 0 and required <= capacity)
        asking = _num(snapshot.ask_for(flow_side)) if flow_side is not None else None
        if (flow_side is not None and counter_child and near_ema9 and causal_rejoin
                and tp_agrees and reachable
                and raw_parent.get("parent_terminal_ready") is not True
                and (900.0 - snapshot.contract_age_s) > 180.0
                and asking is not None and 0 < asking < MOUNTAIN_CONTRACT_LEG_MAX):
            child_id = str(geometry.get("arc_id") or raw_mountain.get("current_arc_id")
                           or "PULLBACK")
            return (_candidate(snapshot, family="MOUNTAIN_CONTRACT_LEG", side=flow_side,
                max_price=MOUNTAIN_CONTRACT_LEG_MAX,
                reason="COMMANDER_DIRECTIONAL_PARENT_PULLBACK_REJOIN",
                size_override=(15.0 if asking <= .35 else 10.0),
                evidence={
                    "identity":f"{historical_flow['side']}:{child_id}:REJOIN",
                    "entry_location":"PERSISTENT_PARENT_SHALLOW_CHILD_REJOIN",
                    "directional_parent":dict(historical_flow),
                    "child_arc_id":child_id, "opposite_child_observed":True,
                    "btc_change6":btc6,"ema9_change6":e6,
                    "near_ema9":near_ema9,"tp_ownership_side":tp_side.value,
                    "required_move_btc":required,"capacity_btc":capacity,
                    "with_wind":True, "no_specialist_veto":True,
                }),)

    # RECENT LEVEL-MATCH RETURN — operator authorization 2026-11-03.
    # A current retest of a completed prior low/high from the last 4-30 minutes
    # can open the opposite return side directly when that contract is <=20c
    # and current short-horizon BTC/EMA9 motion has begun rejecting the level.
    # This positive Commander admission is evaluated before Mountain/Heist/
    # Release WAIT states; those waits become telemetry only for this setup.
    ex = _map(snapshot.metadata.get("historical_extreme_release"))
    recent_match = _map(ex.get("recent_level_match"))
    recent_side = _side(recent_match.get("side"))
    if recent_side is not None and not raw_target_junction:
        level_ask = _num(snapshot.ask_for(recent_side))
        geometry = _map(snapshot.metadata.get("current_geometry"))
        mountain_now = _map(snapshot.metadata.get("mountain"))
        sign = 1.0 if recent_side is Side.YES else -1.0
        btc6 = _num(geometry.get("btc_change6"))
        btc9 = _num(geometry.get("btc_change9"))
        ema6 = _num(geometry.get("ema9_change6"))
        short_turn = bool(
            (btc6 is not None and sign * btc6 > 0)
            and (ema6 is None or sign * ema6 >= 0)
            and (btc9 is None or sign * btc9 >= 0)
        )
        rejection = bool(
            short_turn
            or mountain_now.get("failed_reextension") is True
            or mountain_now.get("stall") is True
            or mountain_now.get("hesitation") is True
            or mountain_now.get("meaningful_retreat") is True
        )
        old_owner = _side(mountain_now.get("owner_side"))
        if (level_ask is not None and 0.0 < level_ask <= MOUNTAIN_EDGE_MAX
                and _recent_level_return_location_ready(snapshot, recent_match)
                and _counterparent_level_rejection_sustained(snapshot, recent_side)
                and rejection and old_owner is not recent_side
                and mountain_now.get("spent_edge") is not True
                and _first_counterfade_has_reversal_proof(snapshot, recent_side, mountain_now)
                and _counter_parent_return_briefing_ready(snapshot, recent_side, mountain_now)
                and _late_counter_return_has_runway(snapshot, recent_side)):
            anchor = _num(recent_match.get("anchor"))
            anchor_time = _num(recent_match.get("anchor_time"))
            identity = f"LEVEL:{recent_side.value}:{int(anchor_time or snapshot.now_ts)}:{anchor}"
            return (_candidate(
                snapshot, family="MOUNTAIN_EDGE", side=recent_side,
                max_price=MOUNTAIN_EDGE_MAX,
                reason="COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN",
                evidence={
                    "identity": identity,
                    "entry_side": recent_side.value,
                    "entry_location": "RECENT_LEVEL_MATCH_RETURN",
                    "recent_level_match": dict(recent_match),
                    "return_ask": level_ask,
                    "btc_change6": btc6, "btc_change9": btc9, "ema9_change6": ema6,
                    "rejection_proven": True,
                    "ordinary_tool_wait_veto_authority": False,
                    "overlay_veto_authority": False,
                    "release_wait_veto_authority": False,
                    "runway_veto_authority": False,
                }, floor_policy_override=_return_seed_floor_policy()),)

    # Operator-authorized hierarchy: during a live parallel-Heist excursion,
    # Heist owns the quick local return mission while Mountain stays reserved
    # for the wider/taller parent structure.  This avoids two reversal engines
    # competing on the same small wobble.  The overlay disappears on release,
    # invalidation, center completion, or rollover, so this is not a permanent
    # Mountain veto.
    strategy = _map(snapshot.metadata.get("commander_strategy"))
    active_overlays = strategy.get("active_overlays")
    if (isinstance(active_overlays, (list, tuple, set))
            and "MARKET_HEIST" in active_overlays
            and historical_flow.get("qualified") is not True):
        return ()

    qualified, rolling, mountain, parent, owner = _mountain_context(snapshot)
    if not (qualified or rolling) or owner is None:
        return ()

    tp = _map(snapshot.metadata.get("tp_geometry"))
    ownership = str(tp.get("contract_ownership") or "UNRESOLVED")
    ownership_side = _side(tp.get("contract_ownership_side"))
    target_in_ema_junction = tp.get("target_between_ema9_ema30") is True

    terminal = current_mountain_terminal(mountain)
    strong_release = mountain.get("strong_active_release") is True
    edge_id = mountain.get("edge_id") or mountain.get("current_arc_id")
    results: list[ToolIntent] = []

    # MATURE/ROLLING gap continuation at a completed opposite child pullback.
    # This is the missing PID3296 route: the long-lived EMA9 gap is parent
    # context, while the local opposite Mountain supplies the value window.
    # Age alone never enters; current child terminal + causal turn + TP runway
    # + <40c value are all mandatory.  EMA30 slope/territory labels cannot veto
    # because EMA30 remains spine/context only in this Mountain-only release.
    persistent_candidate_side: Side | None = None
    persistent_ready, persistent_side, persistent_proof = _persistent_gap_pullback_context(
        snapshot, mountain, owner)
    if (persistent_ready and persistent_side is not None and not target_in_ema_junction):
        persistent_runway, persistent_runway_evidence = _return_settlement_feasible(
            snapshot, tp, mountain, persistent_side)
        ownership_contradiction = bool(
            ownership in {"STARTING_LEG_FAVORED", "BOUNCE_FAVORED"}
            and ownership_side is not None and ownership_side is not persistent_side
        )
        if (persistent_runway and not ownership_contradiction
                and _ask_below(snapshot, persistent_side, MOUNTAIN_CONTRACT_LEG_MAX)):
            results.append(_candidate(
                snapshot, family="MOUNTAIN_CONTRACT_LEG", side=persistent_side,
                max_price=MOUNTAIN_CONTRACT_LEG_MAX,
                reason="COMMANDER_ROLLING_MOUNTAIN_PULLBACK_OWNS_CONTRACT",
                evidence={
                    "identity": f"{edge_id}:GAP:{persistent_side.value}",
                    "edge_id": edge_id,
                    "outgoing_child_side": owner.value,
                    "entry_side": persistent_side.value,
                    "entry_location": "PERSISTENT_GAP_CHILD_TERMINAL",
                    "contract_ownership": ownership,
                    "contract_ownership_side": ownership_side.value if ownership_side else None,
                    "persistent_gap_pullback": persistent_proof,
                    "return_runway": persistent_runway_evidence,
                    "ema_gap_lifecycle": dict(_gap_lifecycle(snapshot)),
                }))
            persistent_candidate_side = persistent_side

    # True parent edge. If the resulting bounce is specifically the contract-
    # winning leg, it normally uses the <40c contract-leg ceiling. A narrow
    # operator-authorized rollover exception allows <50c only when this exact
    # already-earned terminal coincides with the first minute of the new
    # contract and TP favors the return. Smaller quick rollover arcs use the
    # operator-authorized +40% arm / 3% peak trail, not monster-runner custody.
    if terminal and not strong_release:
        return_side = _opposite(owner)
        sprout_ready, sprout_evidence = _sprout_reversal_ready(snapshot, mountain, owner)
        late_feasible, late_evidence = _return_settlement_feasible(snapshot, tp, mountain, return_side)
        junction_allowed, junction_runway_override, junction_evidence = _tp_junction_return_policy(
            snapshot, tp, return_side, late_feasible, late_evidence)
        effective_runway = bool(late_feasible or junction_runway_override)
        bounce_owns_contract = ownership == "BOUNCE_FAVORED" and ownership_side is return_side
        diagnostics_now = _map(mountain.get("diagnostics"))
        current_age_now = _num(diagnostics_now.get("current_age_s"))
        parent_age_now = _num(parent.get("parent_age_s"))
        contract_age_now = float(snapshot.contract_age_s)
        terminal_predates_rollover = bool(
            current_age_now is not None and current_age_now > contract_age_now + 1.0
            or parent_age_now is not None and parent_age_now > contract_age_now + 1.0
        )
        rollover_terminal_return = bool(
            bounce_owns_contract
            and 0.0 <= contract_age_now <= MOUNTAIN_ROLLOVER_TERMINAL_RETURN_WINDOW_S
            and terminal_predates_rollover
        )
        family = "MOUNTAIN_CONTRACT_LEG" if bounce_owns_contract else "MOUNTAIN_EDGE"
        max_price = (MOUNTAIN_ROLLOVER_TERMINAL_RETURN_MAX if rollover_terminal_return
                     else MOUNTAIN_CONTRACT_LEG_MAX if bounce_owns_contract else MOUNTAIN_EDGE_MAX)
        reason = ("COMMANDER_ROLLOVER_TERMINAL_RETURN_START" if rollover_terminal_return
                  else "COMMANDER_MOUNTAIN_BOUNCE_OWNS_CONTRACT" if bounce_owns_contract
                  else "COMMANDER_MOUNTAIN_TRUE_EDGE_RETURN")
        quick_floor = ({
            "arm_roi": 0.40,
            "trail_fraction": 0.03,
            "min_age_s": 0.0,
            "immediate_arm_roi": 0.40,
            "first_arm_from_current_bid": True,
            "roi_trail_tiers": [],
            "profit_policy_revision": "OPERATOR_AUTHORIZED_SMALL_ARC_40_ARM_3_TRAIL_V1",
        } if rollover_terminal_return else None)
        if (return_side is not persistent_candidate_side
                and sprout_ready and junction_allowed and effective_runway
                and _ask_below(snapshot, return_side, max_price)):
            results.append(_candidate(
                snapshot, family=family, side=return_side, max_price=max_price,
                reason=reason, floor_policy_override=quick_floor,
                evidence={
                    "identity": edge_id,
                    "edge_id": edge_id,
                    "outgoing_owner_side": owner.value,
                    "entry_side": return_side.value,
                    "terminal": True,
                    "contract_ownership": ownership,
                    "contract_ownership_side": ownership_side.value if ownership_side else None,
                    "entry_location": ("ROLLOVER_TERMINAL_RETURN_START"
                                       if rollover_terminal_return else "TRUE_PARENT_EDGE"),
                    "rollover_terminal_return": rollover_terminal_return,
                    "contract_age_s": contract_age_now,
                    "terminal_predates_rollover": terminal_predates_rollover,
                    "return_runway": late_evidence,
                    "late_return_runway": late_evidence,
                    "tp_junction_policy": junction_evidence,
                    "ema_gap_lifecycle": dict(_gap_lifecycle(snapshot)),
                    "sprout_reversal_proof": sprout_evidence,
                }))

    # Contract-start / rollover leg. This is the only non-terminal Mountain leg
    # entry in the reset. The same live arc must already have existed before the
    # current contract opened, and TP/comparable geometry must say that starting
    # leg is favored. No arbitrary mid-leg entry is allowed.
    diagnostics = _map(mountain.get("diagnostics"))
    current_age = _num(diagnostics.get("current_age_s"))
    parent_age = _num(parent.get("parent_age_s"))
    contract_age = float(snapshot.contract_age_s)
    inherited_current_arc = bool(
        current_age is not None and current_age > contract_age + 1.0
        or parent_age is not None and parent_age > contract_age + 1.0
    )
    explicit_starting_owner = bool(
        ownership == "STARTING_LEG_FAVORED" and ownership_side is owner
    )
    target_reachable, required_move, demonstrated_capacity = _rollover_target_reachable(tp, parent, owner)
    rollover_contract_leg = bool(explicit_starting_owner or target_reachable)
    rollover_window = 0.0 <= contract_age <= MOUNTAIN_ROLLOVER_MAX_AGE_S
    parent_not_terminal = parent.get("parent_terminal_ready") is not True
    inherited_live, inherited_live_evidence = _inherited_leg_still_live(snapshot, mountain, parent, owner)
    gap_inherited, gap_inherited_evidence = _gap_preexisted_current_contract(snapshot, parent, owner)
    opening_continuation = bool(
        inherited_current_arc and 0.0 <= contract_age <= MOUNTAIN_ROLLOVER_CONTINUATION_WINDOW_S
        and inherited_live and gap_inherited and parent_not_terminal and rollover_contract_leg
    )
    rollover_entry_ceiling = (MOUNTAIN_ROLLOVER_CONTINUATION_MAX
                              if opening_continuation else MOUNTAIN_CONTRACT_LEG_MAX)
    owner_ask = _num(snapshot.ask_for(owner))
    owner_price_ok = bool(owner_ask is not None and owner_ask > 0
                          and owner_ask <= rollover_entry_ceiling)
    if (not terminal and inherited_current_arc and rollover_window and parent_not_terminal
            and inherited_live and gap_inherited and not target_in_ema_junction and rollover_contract_leg
            and owner_price_ok):
        basis = "TP_STARTING_LEG_FAVORED" if explicit_starting_owner else "TARGET_REACHABLE_FROM_INHERITED_PARENT"
        results.append(_candidate(
            snapshot, family="MOUNTAIN_CONTRACT_LEG", side=owner,
            max_price=rollover_entry_ceiling,
            reason=("COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION"
                    if opening_continuation and owner_ask is not None and owner_ask > MOUNTAIN_CONTRACT_LEG_MAX else
                    "COMMANDER_MOUNTAIN_STARTING_LEG_OWNS_CONTRACT"
                    if explicit_starting_owner else
                    "COMMANDER_MOUNTAIN_ROLLOVER_TARGET_REACHABLE"),
            size_override=(25.0 if opening_continuation else None),
            evidence={
                "identity": mountain.get("current_arc_id") or parent.get("parent_id"),
                "arc_id": mountain.get("current_arc_id"),
                "entry_side": owner.value,
                "current_arc_age_s": current_age,
                "parent_age_s": parent_age,
                "contract_age_s": contract_age,
                "rollover_max_age_s": MOUNTAIN_ROLLOVER_MAX_AGE_S,
                "contract_ownership": ownership,
                "contract_ownership_side": ownership_side.value if ownership_side else None,
                "contract_leg_basis": basis,
                "required_move_to_target_btc": required_move,
                "demonstrated_parent_capacity_btc": demonstrated_capacity,
                "reach_fraction": MOUNTAIN_ROLLOVER_REACH_FRACTION,
                "entry_location": ("INHERITED_YOUNG_LEG_FIRST_MINUTE"
                                   if opening_continuation else "INHERITED_LEG_AT_CONTRACT_ROLLOVER"),
                "opening_continuation": opening_continuation,
                "rollover_entry_ceiling": rollover_entry_ceiling,
                "rolling_mountain": rolling,
                "inherited_leg_live": inherited_live_evidence,
                "gap_inheritance": gap_inherited_evidence,
                "ema_gap_lifecycle": dict(_gap_lifecycle(snapshot)),
            }))

    unique: dict[tuple[str, str, str], ToolIntent] = {}
    for intent in results:
        key = (str(intent.metadata.get("commander_candidate_family")),
               intent.side.value if intent.side else "",
               str(intent.metadata.get("physical_mission_id")))
        unique[key] = intent
    return tuple(unique.values())


def historical_extreme_release_candidates(snapshot: MarketSnapshot) -> list[ToolIntent]:
    """Small early scout at a proven historical extreme before full Release.

    Location alone has zero authority.  Require current opposite reversal on
    both 6s/9s, failed re-extension, a non-terminal old owner, and <=15c value.
    The scout can later be promoted by Commander if Release confirms.
    """
    ex = _map(snapshot.metadata.get("historical_extreme_release"))
    if ex.get("qualified") is not True:
        return []
    side = _side(ex.get("side"))
    if side is None:
        return []
    g = _map(snapshot.metadata.get("current_geometry"))
    m = _map(snapshot.metadata.get("mountain"))
    sign = 1.0 if side is Side.YES else -1.0
    vals=[]
    for key in ("btc_change6","btc_change9","ema9_change6"):
        v=_num(g.get(key)); vals.append(v)
    if any(v is None for v in vals):
        return []
    btc6, btc9, ema6 = vals
    reversal = bool(sign*btc6 > 0 and sign*btc9 > 0 and sign*ema6 >= 0)
    failed = bool(m.get("failed_reextension") is True or m.get("stall") is True or m.get("hesitation") is True)
    if (not reversal or not failed or m.get("strong_active_release") is True
            or not _late_counter_return_has_runway(snapshot, side)
            or not _counter_parent_return_briefing_ready(snapshot, side, m)):
        return []
    owner = _side(m.get("owner_side"))
    if owner is side:
        return []
    ask=snapshot.ask_for(side)
    if ask is None or ask <= 0 or ask > 0.15:
        return []
    source=_num(g.get("epoch_ms"))
    source_time=(source/1000.0 if source is not None else snapshot.now_ts)
    identity=f"{int(source or snapshot.now_ts*1000)}:{ex.get('prior_low_anchor')}:{ex.get('prior_high_anchor')}"
    return [ToolIntent(tool="ONE_COMMANDER_PRIMARY", territory_id="HISTORICAL_EXTREME_RELEASE_PREP",
        lane=Lane.TACTICAL, side=side, action=Action.ENTER,
        opportunity_id=f"COMMANDER:HISTORICAL_EXTREME_RELEASE_PREP:{side.value}:{identity}",
        max_price=0.15, size_tier=15.0, reason="COMMANDER_HISTORICAL_EXTREME_RELEASE_PREP_SCOUT",
        source_time=source_time, expires_when="EXTREME_FAILS_OR_RELEASE_CONFIRMS", metadata={
            "commander_primary_candidate":True,
            "commander_candidate_family":"HISTORICAL_EXTREME_RELEASE_PREP",
            "historical_extreme_release":dict(ex),
            "position_role":"TACTICAL",
            "floor_policy":{"arm_roi":0.60,"trail_fraction":0.10,"min_age_s":0.0,
                            "immediate_arm_roi":0.60,"first_arm_from_current_bid":True,
                            "roi_trail_tiers":[[1.0,0.07],[2.0,0.05]],
                            "profit_policy_revision":"EXTREME_RELEASE_PREP_PROMOTABLE_V2"}})]



def edge_heist_candidates(snapshot: MarketSnapshot) -> list[ToolIntent]:
    """Tactical micro-Heist at an armed Mountain extreme while MAIN is still calculating.

    Direction comes only from the parent Mountain edge: UP top -> NO return,
    DOWN bottom -> YES return. Quote oscillation grants timing/value, never
    direction. At most two quote cycles are admitted per physical edge.
    """
    mountain = _map(snapshot.metadata.get("mountain"))
    if not mountain or mountain.get("strong_active_release") is True:
        return []
    owner = _side(mountain.get("owner_side"))
    if owner is None:
        raw_owner = (_map(mountain.get("current_arc")).get("direction")
                     or mountain.get("current_side")
                     or _map(mountain.get("diagnostics")).get("current_side"))
        text = str(raw_owner or "").upper()
        owner = Side.YES if text in ("YES", "UP") else Side.NO if text in ("NO", "DOWN") else None
    if owner is None:
        return []

    collection = _map(mountain.get("primary_collection_evidence"))
    retest = _map(collection.get("retest_rejection"))
    edge_armed = bool(
        mountain.get("mature_edge") is True
        or mountain.get("edge_window_active") is True
        or collection.get("comparable_current_leg_mature") is True
        or retest.get("qualified") is True
    )
    if not edge_armed:
        return []

    side = _opposite(owner)
    if not _counter_parent_return_briefing_ready(snapshot, side, mountain):
        return []
    q = _map(snapshot.metadata.get("quote_wave"))
    sides = _map(q.get("sides"))
    brief = _map(sides.get(side.value))
    series = brief.get("series") if isinstance(brief.get("series"), list) else []
    if not brief.get("available") or len(series) < 4:
        return []
    low = _num(brief.get("low_ask")); high = _num(brief.get("high_ask"))
    current = _num(snapshot.ask_for(side))
    if low is None or high is None or current is None or low <= 0 or high <= low:
        return []
    swing = high - low
    swing_fraction = swing / max(low, 0.01)
    if swing_fraction < 0.35 or current > 0.35:
        return []

    cheap_threshold = low + 0.25 * swing
    high_threshold = low + 0.65 * swing
    if current > cheap_threshold + 1e-9:
        return []

    # One cycle is a genuine cheap -> high -> cheap reversion. Adjacent quote
    # updates do not count as separate swings. Cap at two cycles per edge.
    cycles = 0
    saw_cheap = False
    saw_high_after_cheap = False
    last_cycle_time = None
    for row in series:
        row = _map(row)
        ask = _num(row.get("ask")); ts = _num(row.get("time"))
        if ask is None or ts is None:
            continue
        if ask <= cheap_threshold:
            if saw_high_after_cheap:
                cycles += 1
                last_cycle_time = ts
                saw_high_after_cheap = False
                saw_cheap = True
            else:
                saw_cheap = True
        elif saw_cheap and ask >= high_threshold:
            saw_high_after_cheap = True
    if cycles < 1 or cycles > 2 or last_cycle_time is None or snapshot.now_ts - last_cycle_time > 8.0:
        return []

    edge_id = str(mountain.get("edge_id") or mountain.get("current_edge_id")
                  or mountain.get("current_arc_id") or int(_source_time(snapshot)*1000))
    opportunity = f"EDGE_HEIST:{snapshot.ticker}:{side.value}:{edge_id}:CYCLE{cycles}"
    source_time = _source_time(snapshot)
    return [ToolIntent(
        tool="EDGE_HEIST", territory_id="MOUNTAIN_EDGE_HEIST", lane=Lane.TACTICAL,
        side=side, action=Action.ENTER, opportunity_id=opportunity, max_price=0.35,
        size_tier=10.0, reason="COMMANDER_MOUNTAIN_EDGE_HEIST_QUOTE_SWING",
        source_time=source_time, expires_when="EDGE_BREAKS_OR_MAIN_RETURN_CONFIRMS", metadata={
            "commander_primary_candidate": True,
            "commander_candidate_family": "EDGE_HEIST",
            "physical_mission_id": opportunity,
            "position_role": "TACTICAL",
            "edge_heist": {
                "version": "EDGE_HEIST_V1", "edge_id": edge_id,
                "outgoing_owner": owner.value, "return_side": side.value,
                "low_ask": low, "high_ask": high, "current_ask": current,
                "swing_fraction": swing_fraction, "cycle": cycles,
                "cheap_threshold": cheap_threshold, "high_threshold": high_threshold,
                "max_cycles_per_edge": 2, "max_hold_s": 180.0,
            },
            "floor_policy": {
                "arm_roi": 0.40, "trail_fraction": 0.08, "min_age_s": 0.0,
                "immediate_arm_roi": 0.40, "first_arm_allowed": True,
                "first_arm_from_current_bid": True,
                "roi_trail_tiers": [[1.0, 0.05], [2.0, 0.03]],
                "profit_policy_revision": "EDGE_HEIST_40_ARM_PROMOTABLE_V1",
            },
            "commander_physical_evidence": {
                "identity": edge_id, "physical_basis": "MOUNTAIN_EDGE_QUOTE_OSCILLATION",
                "edge_armed": True, "outgoing_owner": owner.value,
            },
        }
    )]

def quote_wave_scalp_candidates(snapshot: MarketSnapshot) -> list[ToolIntent]:
    """Commander-owned tiny tactical quote renter at an already-earned decision area.

    Quote behavior selects timing/value only. Direction must already come from
    a qualified Heist outer wall or current mature Mountain terminal.
    """
    q = _map(snapshot.metadata.get("quote_wave"))
    sides = _map(q.get("sides"))
    heist = _map(snapshot.metadata.get("heist"))
    mountain = _map(snapshot.metadata.get("mountain"))
    geometry = _map(snapshot.metadata.get("current_geometry"))

    side: Side | None = None
    physical_basis = None
    identity = None
    if heist.get("qualified_box") is True and bool(heist.get("at_lower_edge")) != bool(heist.get("at_upper_edge")):
        side = Side.YES if heist.get("at_lower_edge") is True else Side.NO
        physical_basis = "HEIST_OUTER_WALL"
        identity = f"{heist.get('box_id')}:{heist.get('visit_id')}"
    elif current_mountain_terminal(mountain):
        raw_owner = (_map(mountain.get("current_arc")).get("direction") or mountain.get("current_side")
                     or _map(mountain.get("diagnostics")).get("current_side"))
        owner_text = str(raw_owner or "").upper()
        owner = (Side.YES if owner_text in ("YES", "UP") else
                 Side.NO if owner_text in ("NO", "DOWN") else None)
        if owner is not None:
            side = _opposite(owner)
            physical_basis = "MOUNTAIN_TERMINAL"
            identity = str(mountain.get("edge_id") or mountain.get("current_edge_id") or geometry.get("epoch_ms"))
    if side is None:
        return []

    brief = _map(sides.get(side.value))
    series = brief.get("series") if isinstance(brief.get("series"), list) else []
    if not brief.get("available") or len(series) < 4:
        return []
    entry_max = 0.08
    min_spread = 0.05
    min_peak = 0.13
    current_ask = _num(snapshot.ask_for(side))
    low = _num(brief.get("low_ask"))
    high = _num(brief.get("high_ask"))
    if (current_ask is None or current_ask <= 0 or current_ask > entry_max
            or low is None or high is None or high < min_peak or high-low < min_spread):
        return []

    # Count distinct cheap revisits separated by a >=5c reprice. A cluster of
    # adjacent cheap quotes is one visit, not repeated evidence.
    visits = 0
    armed_high = True
    last_cheap_time = None
    for row in series:
        ask = _num(_map(row).get("ask"))
        ts = _num(_map(row).get("time"))
        if ask is None or ts is None:
            continue
        if ask >= min_peak:
            armed_high = True
        elif ask <= entry_max and armed_high:
            visits += 1
            last_cheap_time = ts
            armed_high = False
    if visits < 2 or last_cheap_time is None or snapshot.now_ts-last_cheap_time > 6.0:
        return []

    # Side must not be the currently confirmed Release side's opposite; a quote
    # scalp may rent indecision, never fade a live breakout/Leviathan.
    release_side = _side(snapshot.metadata.get("release_candidate_side"))
    if snapshot.metadata.get("release_in_progress") is True and release_side is not None and side is not release_side:
        return []

    source_time = _source_time(snapshot)
    opportunity = f"QUOTE_WAVE_SCALP:{snapshot.ticker}:{side.value}:{identity}:{int(last_cheap_time)}"
    return [ToolIntent(tool="QUOTE_WAVE", territory_id="QUOTE_WAVE_TACTICAL", lane=Lane.TACTICAL,
        side=side, action=Action.ENTER, opportunity_id=opportunity, max_price=entry_max,
        size_tier=10.0, reason="COMMANDER_QUOTE_WAVE_REPRICE_SCALP", source_time=source_time,
        expires_when="CHEAP_REVISIT_OR_DECISION_AREA_ENDS", metadata={
            "commander_primary_candidate": True,
            "commander_candidate_family": "QUOTE_WAVE_SCALP",
            "physical_mission_id": opportunity,
            "position_role": "TACTICAL",
            "quote_wave_scalp": {"version": "QUOTE_WAVE_SCALP_V1",
                "physical_basis": physical_basis, "low_ask": low, "high_ask": high,
                "ask_range": high-low, "cheap_revisits": visits, "entry_max_ask": entry_max,
                "min_reprice_spread": min_spread, "min_peak_ask": min_peak,
                "max_hold_s": 120.0},
            "floor_policy": {"arm_roi": 0.60, "trail_fraction": 0.10, "min_age_s": 0.0,
                "immediate_arm_roi": 0.60, "first_arm_allowed": True,
                "first_arm_from_current_bid": True,
                "roi_trail_tiers": [[1.0, 0.07], [2.0, 0.05]],
                "profit_policy_revision": "QUOTE_WAVE_SCALP_60_ARM_10_100_7_200_5_V1"},
            "commander_physical_evidence": {"identity": identity, "physical_basis": physical_basis},
        })]
