"""Commander-owned qualified fade evidence.

Fades are secondary opportunities.  This module never treats cheapness as a
motive and never has execution authority.  It exposes only physically earned
counter-opportunities to OneCommander:

* repeatable Heist outer-edge return;
* a later (not first) pullback opportunity in a leg with demonstrated return
  behaviour and a mature local extreme;
* an explicitly observed failed Rail excursion/fakeout;
* an explicitly observed unsupported anomaly candle that failed to extend.

Rail/anomaly qualification deliberately consumes descriptive evidence from the
relevant observer.  It does not invent a numeric anomaly threshold here.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _side(value: Any) -> Side | None:
    if isinstance(value, Side):
        return value
    text = str(value).upper() if value is not None else ""
    return Side(text) if text in ("YES", "NO") else None


def _opposite(side: Side) -> Side:
    return Side.NO if side is Side.YES else Side.YES


def _source_time(snapshot: MarketSnapshot) -> float:
    value = snapshot.metadata.get("geometry_last_epoch_ms")
    try:
        source = float(value) / 1000.0
        if math.isfinite(source):
            return source
    except (TypeError, ValueError, OverflowError):
        pass
    return snapshot.now_ts


def _candidate(snapshot: MarketSnapshot, *, family: str, side: Side,
               reason: str, evidence: Mapping[str, Any], identity: str) -> ToolIntent | None:
    ask = snapshot.ask_for(side)
    if ask is None or not 0 < ask < 1:
        return None
    # There is intentionally no universal fade-price ceiling here.  Price is
    # evaluated only after the physical opportunity exists.  The current ask
    # is used as the executable limit for this one causal decision beat.
    return ToolIntent(
        tool="ONE_COMMANDER_QUALIFIED_FADE",
        territory_id=f"COMMANDER:{family}",
        lane=Lane.TACTICAL,
        side=side,
        action=Action.ENTER,
        opportunity_id=f"COMMANDER_FADE:{family}:{identity}:{snapshot.ticker}",
        max_price=float(ask),
        size_tier=10.0,
        reason=reason,
        source_time=_source_time(snapshot),
        expires_when="PHYSICAL_FADE_EVIDENCE_CHANGES",
        metadata={
            "commander_primary_candidate": True,
            "commander_candidate_family": family,
            "qualified_fade": True,
            "fade_evidence": dict(evidence),
            "price_policy": "PHYSICAL_MOTIVE_FIRST_CURRENT_EXECUTABLE_VALUE",
            "observed_ask": ask,
            "position_role": "TACTICAL",
            "physical_mission_id": f"COMMANDER_FADE:{family}:{identity}:{side.value}",
            "physical_renewal": {
                "independent": True,
                "renewal_kind": ("HEIST_NEW_EDGE_VISIT" if family == "HEIST_OUTER_RETURN"
                                 else "RETREAT_RETEST_REJECTION"),
                "observed_at": _source_time(snapshot),
            },
        },
    )


def qualified_fade_candidates(snapshot: MarketSnapshot) -> list[ToolIntent]:
    out: list[ToolIntent] = []
    meta = snapshot.metadata
    mountain = _map(meta.get("mountain"))
    echo = _map(meta.get("leg_echo"))

    # 1) Proven bounded Heist excursion.  The box itself demonstrates return
    # behaviour; a current outer-edge visit earns the return side.
    heist = _map(meta.get("heist"))
    if heist.get("qualified_box") is True and heist.get("release_confirmed") is not True:
        box_id = str(heist.get("box_id") or "BOX")
        visit = str(heist.get("visit_id") or "VISIT")
        if heist.get("at_upper_edge") is True:
            c = _candidate(snapshot, family="HEIST_OUTER_RETURN", side=Side.NO,
                           reason="COMMANDER_QUALIFIED_HEIST_UPPER_RETURN",
                           evidence={"box_id": box_id, "visit_id": visit, "edge": "UPPER"},
                           identity=f"{box_id}:{visit}:UPPER")
            if c: out.append(c)
        elif heist.get("at_lower_edge") is True:
            c = _candidate(snapshot, family="HEIST_OUTER_RETURN", side=Side.YES,
                           reason="COMMANDER_QUALIFIED_HEIST_LOWER_RETURN",
                           evidence={"box_id": box_id, "visit_id": visit, "edge": "LOWER"},
                           identity=f"{box_id}:{visit}:LOWER")
            if c: out.append(c)

    # 2) Later pullback fade.  A first breath is not enough.  The current leg
    # must have already demonstrated at least one completed pullback OR the
    # comparable-history ledger must show repeated pullbacks, and the current
    # same-direction child must itself be at a mature local extreme.
    leg_side = _side(echo.get("side"))
    current_child = _map(echo.get("live_current_child"))
    current_child_side = _side(current_child.get("side"))
    live_pullbacks = int(echo.get("live_pullback_count") or 0)
    try:
        median_pullbacks = float(echo.get("median_pullback_count"))
    except (TypeError, ValueError):
        median_pullbacks = 0.0
    mature_local_extreme = bool(
        mountain.get("mature_edge") is True
        or mountain.get("terminal_evidence_qualified") is True
        or mountain.get("failed_reextension") is True
    )
    release_active = bool(meta.get("release_in_progress") is True or mountain.get("strong_active_release") is True)
    later_pullback_evidence = live_pullbacks >= 1 or median_pullbacks >= 2.0
    if (leg_side is not None and current_child_side is leg_side
            and later_pullback_evidence and mature_local_extreme and not release_active):
        side = _opposite(leg_side)
        parent = _map(mountain.get("parent_structure"))
        identity = str(parent.get("parent_id") or echo.get("live_leg_id") or mountain.get("current_arc_id") or "LEG")
        c = _candidate(snapshot, family="MATURE_LEG_PULLBACK_FADE", side=side,
                       reason="COMMANDER_QUALIFIED_LATER_PULLBACK_FADE",
                       evidence={
                           "leg_side": leg_side.value,
                           "live_completed_pullbacks": live_pullbacks,
                           "median_comparable_pullbacks": median_pullbacks,
                           "median_pullback_btc": echo.get("median_pullback_btc"),
                           "median_pullback_duration_s": echo.get("median_pullback_duration_s"),
                           "mature_local_extreme": True,
                       }, identity=identity)
        if c: out.append(c)

    # 3) Rail failed excursion/fakeout.  Qualification is supplied by a causal
    # observer that compares the excursion with the established Rail corridor.
    # This module does not create its own arbitrary corridor threshold.
    fakeout = _map(meta.get("rail_fakeout_evidence"))
    fakeout_side = _side(fakeout.get("return_side"))
    if (fakeout.get("qualified") is True and fakeout.get("failed_to_establish") is True
            and fakeout_side is not None and meta.get("release_in_progress") is not True):
        identity = str(fakeout.get("excursion_id") or fakeout.get("rail_id") or "RAIL_FAKEOUT")
        c = _candidate(snapshot, family="RAIL_FAKEOUT_RENTER", side=fakeout_side,
                       reason="COMMANDER_QUALIFIED_RAIL_FAILED_EXCURSION",
                       evidence=fakeout, identity=identity)
        if c: out.append(c)

    # 4) Unsupported out-of-family candle.  The candle observer must first
    # establish both anomaly and failure to extend; a large candle by itself is
    # never fade permission.
    anomaly = _map(meta.get("anomaly_candle_evidence"))
    anomaly_side = _side(anomaly.get("return_side"))
    if (anomaly.get("qualified") is True and anomaly.get("unsupported_by_prior_release") is True
            and anomaly.get("failed_to_extend") is True and anomaly_side is not None
            and meta.get("release_in_progress") is not True):
        identity = str(anomaly.get("event_id") or "ANOMALY")
        c = _candidate(snapshot, family="ANOMALY_CANDLE_FADE", side=anomaly_side,
                       reason="COMMANDER_QUALIFIED_UNSUPPORTED_ANOMALY_FADE",
                       evidence=anomaly, identity=identity)
        if c: out.append(c)

    return out
