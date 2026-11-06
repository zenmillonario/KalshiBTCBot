"""Detached Looking Glass context and conditional Hurricane paths.

This module reads completed chart observations. It neither imports an engine
nor creates intents, fills, readiness conditions, settlement predictions or
probabilities. Historical contract profiles are translated to today's observed
anchor and replayed under three explicitly mechanical assumptions. Their
future points are hypothetical; the source observations remain unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
import math
from typing import Any


VERSION = "LOOKING_GLASS_V2_ACTIVE_PATTERN"
CONTRACT_SECONDS = 900.0


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _mapping(value: Any) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _side(value: float) -> str:
    return "YES" if value > 0 else "NO" if value < 0 else "AT_TARGET"


@dataclass(frozen=True)
class LookingGlassConfig:
    minimum_gross_roi: float = 0.40
    history_contracts: int = 2
    future_skew_seconds: float = 2.0

    def __post_init__(self) -> None:
        value = _number(self.minimum_gross_roi)
        if value is None or value < 0:
            raise ValueError("LOOKING_GLASS_INVALID_MINIMUM_GROSS_ROI")
        if (isinstance(self.history_contracts, bool)
                or not isinstance(self.history_contracts, int)
                or self.history_contracts not in (1, 2)):
            raise ValueError("LOOKING_GLASS_HISTORY_CONTRACTS_MUST_BE_ONE_OR_TWO")
        skew = _number(self.future_skew_seconds)
        if skew is None or skew < 0 or skew > 5:
            raise ValueError("LOOKING_GLASS_INVALID_FUTURE_SKEW_SECONDS")
        object.__setattr__(self, "minimum_gross_roi", value)
        object.__setattr__(self, "future_skew_seconds", skew)


def _config(value: LookingGlassConfig | Mapping | None) -> LookingGlassConfig:
    if value is None:
        return LookingGlassConfig()
    if isinstance(value, LookingGlassConfig):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("LOOKING_GLASS_INVALID_CONFIGURATION")
    unknown = set(value) - {"minimum_gross_roi", "history_contracts", "future_skew_seconds"}
    if unknown:
        raise ValueError("LOOKING_GLASS_UNKNOWN_CONFIGURATION_FIELD")
    return LookingGlassConfig(**dict(value))


def _completed_points(candles: Sequence[Mapping], emas: Sequence[Mapping],
                      asof: float) -> tuple[list[dict], dict]:
    """Use completed closes only, with a separate as-of knowledge check.

    Inline EMA values belong to the completed candle. If absent, a matching
    published EMA row may supply them. Conflicting duplicate rows are excluded
    rather than choosing a later value. No current OHLC extreme is converted
    into an invented historical tick.
    """
    ema_by_time: dict[float, tuple[float, float]] = {}
    ema_conflicts: set[float] = set()
    skipped = {"future_or_unfinished": 0, "invalid": 0, "conflicting": 0}
    for raw in emas or ():
        row = _mapping(raw)
        ts = _number(row.get("time"))
        known = _number(row.get("known_at"))
        e9, e30 = _number(row.get("e9")), _number(row.get("e30"))
        if (ts is None or ts < 0 or ts % 60 or ts + 60 > asof
                or "known_at" in row and known is None
                or known is not None and known > asof):
            continue
        if e9 is None or e30 is None or min(e9, e30) <= 0:
            continue
        pair = (e9, e30)
        if ts in ema_by_time and ema_by_time[ts] != pair:
            ema_conflicts.add(ts)
        ema_by_time[ts] = pair

    by_time: dict[float, dict] = {}
    conflicts: set[float] = set()
    for raw in candles or ():
        row = _mapping(raw)
        ts = _number(row.get("time"))
        known = _number(row.get("known_at"))
        if (ts is None or ts < 0 or ts % 60 or row.get("complete") is not True
                or "known_at" in row and known is None
                or ts + 60 > asof or known is not None and known > asof):
            skipped["future_or_unfinished"] += 1
            continue
        btc = _number(row.get("close"))
        e9, e30 = _number(row.get("e9")), _number(row.get("e30"))
        inline = e9 is not None and e30 is not None
        if not inline:
            if ts in ema_conflicts:
                conflicts.add(ts)
                continue
            pair = ema_by_time.get(ts)
            if pair is not None:
                e9, e30 = pair
        if btc is None or e9 is None or e30 is None or min(btc, e9, e30) <= 0:
            skipped["invalid"] += 1
            continue
        point = {"time": ts + 60.0, "btc": btc, "e9": e9, "e30": e30,
                 "known_at": known if known is not None else ts + 60.0,
                 "quality": str(row.get("quality") or row.get("source") or "COMPLETED_CLOSE"),
                 "ema_basis": "COMPLETED_CANDLE" if inline else "MATCHING_PUBLISHED_EMA"}
        prior = by_time.get(ts)
        if prior is not None and any(prior[key] != point[key] for key in ("btc", "e9", "e30")):
            conflicts.add(ts)
        by_time[ts] = point
    skipped["conflicting"] = len(conflicts)
    return [by_time[key] for key in sorted(by_time) if key not in conflicts], skipped


def _interpolate_past(points: Sequence[Mapping], at: float) -> dict | None:
    """Linear construction between witnessed completed closes, not a tick."""
    for point in points:
        if point["time"] == at:
            return {key: point[key] for key in ("time", "btc", "e9", "e30")}
    for a, b in zip(points, points[1:]):
        if a["time"] < at < b["time"] and b["time"] - a["time"] <= 60.0:
            fraction = (at - a["time"]) / (b["time"] - a["time"])
            return {"time": at, **{key: a[key] + fraction * (b[key] - a[key])
                                     for key in ("btc", "e9", "e30")}}
    return None


def _profile(points: Sequence[Mapping], start: float, end: float,
             targets: Sequence[Mapping], asof: float, index: int) -> dict:
    rows = [dict(point) for point in points if start <= point["time"] <= end]
    expected = [start + 60 * offset for offset in range(16)]
    available = {row["time"] for row in rows}
    missing = [time for time in expected if time not in available]
    target = next((_mapping(row) for row in targets or ()
                   if _number(_mapping(row).get("close_ts")) == end
                   and _number(_mapping(row).get("start_ts")) == start
                   and _number(_mapping(row).get("observed_at")) is not None
                   and float(row["observed_at"]) <= asof), {})
    identifier = str(target.get("ticker") or f"PRIOR_CONTRACT_{index}:{int(start)}:{int(end)}")
    return {"id": identifier, "start_ts": start, "end_ts": end,
            "contract_metadata_observed": bool(target), "point_count": len(rows),
            "status": "COMPLETE" if not missing else "PARTIAL",
            "missing_close_times": missing, "points": rows}


def _observations(points: Sequence[Mapping], market: Mapping, asof: float,
                  reference_start: float) -> dict:
    history = [row for row in points if reference_start <= row["time"] <= asof]
    # Keep only the continuous suffix reaching the current observation.
    current = {"time": asof, "btc": market.get("btc"), "e9": market.get("e9"),
               "e30": market.get("e30")}
    tail: list[Mapping] = [current]
    for row in reversed(history):
        if row["time"] == tail[0]["time"]:
            continue
        if not 0 < tail[0]["time"] - row["time"] <= 60.0:
            break
        tail.insert(0, row)
    recent = [row for row in tail if row["time"] >= asof - 180]
    first = recent[0] if recent else current
    elapsed = asof - first["time"]
    e9_delta = current["e9"] - first["e9"] if elapsed > 0 else None
    btc_delta = current["btc"] - first["btc"] if elapsed > 0 else None
    changes = [b["btc"] - a["btc"] for a, b in zip(tail, tail[1:])]
    nonzero = [_sign(change) for change in changes if change != 0]
    turns = sum(a != b for a, b in zip(nonzero, nonzero[1:]))
    traveled = sum(abs(value) for value in changes)
    net = tail[-1]["btc"] - tail[0]["btc"] if len(tail) > 1 else None
    efficiency = abs(net) / traveled if net is not None and traveled > 0 and math.isfinite(traveled) else None
    direction = "UP" if e9_delta is not None and e9_delta > 0 else (
        "DOWN" if e9_delta is not None and e9_delta < 0 else "FLAT" if elapsed > 0 else "UNKNOWN")
    regime = "OBSERVED_ONE_WAY" if nonzero and not turns else (
        "OBSERVED_SWINGS" if turns else "QUIET_OR_INSUFFICIENT")
    return {"ema9_direction": direction,
            "ema9_slope_per_min": _number(e9_delta / elapsed * 60) if elapsed > 0 else None,
            "ema9_measurement_seconds": elapsed, "btc_motion": btc_delta,
            "price_ema9_gap": current["btc"] - current["e9"],
            "ema9_ema30_gap": current["e9"] - current["e30"],
            "continuous_context_seconds": asof - tail[0]["time"],
            "turn_count": turns, "path_efficiency": efficiency, "regime": regime,
            "measurement_only": True}


def _paths(profiles: Sequence[Mapping], market: Mapping, observations: Mapping,
           asof: float, opening: float, close: float) -> list[dict]:
    result = []
    elapsed = asof - opening
    lean = {"UP": 1, "DOWN": -1}.get(observations.get("ema9_direction"), 0)
    if observations.get("ema9_direction") == "UNKNOWN":
        return result
    for profile in profiles:
        if profile["status"] != "COMPLETE":
            continue
        prior_now = profile["start_ts"] + elapsed
        origin = _interpolate_past(profile["points"], prior_now)
        if origin is None:
            continue
        past_tail = [row for row in profile["points"] if row["time"] > prior_now]
        if not past_tail:
            continue
        final = past_tail[-1]
        prior_lean = _sign(final["e9"] - origin["e9"])
        orientation = lean / prior_lean if lean and prior_lean else None
        families = (("CONTINUATION", "Continuation of the observed EMA9 lean"),
                    ("ROTATION_STALL", "Rotation with no terminal displacement"),
                    ("REVERSAL", "Opposing return stress case")) if orientation is not None else (
                        ("ROTATION_STALL", "Rotation only; current EMA9 direction is flat"
                         if not lean else "Rotation only; prior remainder has no net EMA9 direction"),)
        for family, label in families:
            points = [{"time": asof, "btc": market["btc"], "e9": market["e9"]}]
            for row in past_tail:
                # Subtract the historical timestamps before adding the live
                # anchor. Explicitly pin expiry so fractional Unix epochs do
                # not lose a fraction of a microsecond through cancellation.
                terminal = row["time"] == profile["end_ts"]
                offset = close - asof if terminal else row["time"] - prior_now
                future = close if terminal else asof + offset
                fraction = offset / (close - asof)
                values = {}
                for key in ("btc", "e9"):
                    delta = row[key] - origin[key]
                    if family == "ROTATION_STALL":
                        delta -= fraction * (final[key] - origin[key])
                    else:
                        delta *= orientation * (-1 if family == "REVERSAL" else 1)
                    values[key] = market[key] + delta
                if any(not math.isfinite(value) or value <= 0 for value in values.values()):
                    points = []
                    break
                points.append({"time": min(close, future), **values})
            if len(points) < 2:
                continue
            endpoint = points[-1]
            target = market.get("target")
            result.append({"id": f"{profile['id']}:{family}", "family": family,
                "label": label, "points": points, "reference_ids": [profile["id"]],
                "reference_start_ts": profile["start_ts"], "reference_end_ts": profile["end_ts"],
                "reference_phase_ts": prior_now, "reference_known_by_ts": asof,
                "historical_close_interpolation": prior_now % 60 != 0,
                "current_contract_phase_seconds": elapsed,
                "orientation_to_current_ema9": orientation if family != "ROTATION_STALL" else None,
                "reference_ema9_remainder_direction": {1: "UP", -1: "DOWN", 0: "FLAT"}[prior_lean],
                "conditional": True, "status": "HYPOTHETICAL_PATH",
                "e9_projection_basis": "TRANSLATED_HISTORICAL_EMA9_TRACE_NOT_RECOMPUTED_FORECAST",
                "assumption": "REPLAY_PRIOR_REMAINDER" if family == "CONTINUATION" else (
                    "REMOVE_PRIOR_REMAINDER_NET_MOVEMENT" if family == "ROTATION_STALL" else
                    "MIRROR_PRIOR_REMAINDER_AGAINST_CURRENT_LEAN"),
                "endpoint_btc": endpoint["btc"], "endpoint_ema9": endpoint["e9"],
                "endpoint_side": _side(endpoint["btc"] - target) if target is not None else "UNKNOWN",
                "not_a_settlement_prediction": True})
    return result


def _pattern_analogue(profiles: Sequence[Mapping], kind: str, direction: str,
                     observations: Mapping, market: Mapping) -> dict | None:
    """Translate one observed leg/arc segment once, without stretching/repetition.

    Full profile paths are preferable. This finite fallback lets a rail remain
    a rail when the rest of the prior contract later turned. Arc candidates
    must contain an already witnessed EMA9 turn and both sides of that turn.
    A contract boundary can cut either end of a segment; it does not establish
    a completed physical leg. Only the included candle observations are final.
    """
    desired = 1 if direction == "UP" else -1
    asof, close = market["time"], market["close_ts"]
    arcs = kind in ("ALTERNATING_MOUNTAIN", "ROLLING_MOUNTAIN", "MARKET_HEIST")
    candidates = []
    for profile in profiles:
        rows = profile["points"]
        runs, start, sign = [], 0, 0
        for index in range(1, len(rows)):
            current = _sign(rows[index]["e9"] - rows[index - 1]["e9"])
            if current and sign and current != sign:
                runs.append(rows[start:index])
                start = index - 1
            if current:
                sign = current
        runs.append(rows[start:])
        segments = [a + b[1:] for a, b in zip(runs, runs[1:])
                    if len(a) >= 2 and len(b) >= 2] if arcs else runs
        for rows in segments:
            if len(rows) < 3 or rows[-1]["time"] - rows[0]["time"] < 120:
                continue
            first_sign = next((_sign(b["e9"] - a["e9"]) for a, b in zip(rows, rows[1:])
                               if b["e9"] != a["e9"]), 0)
            if not first_sign:
                continue
            orientation = desired / first_sign
            end = min(rows[-1]["time"], rows[0]["time"] + close - asof)
            endpoint = _interpolate_past(rows, end)
            if endpoint is None:
                continue
            used = [row for row in rows if row["time"] < end] + [endpoint]
            signs = [_sign(b["e9"] - a["e9"]) for a, b in zip(used, used[1:])
                     if b["e9"] != a["e9"]]
            turns = sum(a != b for a, b in zip(signs, signs[1:]))
            if len(used) < 3 or arcs and turns < 1:
                continue
            origin = used[0]
            points = [{"time": min(close, asof + row["time"] - origin["time"]),
                       **{key: market[key] + orientation * (row[key] - origin[key])
                          for key in ("btc", "e9")}} for row in used]
            if any(not math.isfinite(row[key]) or row[key] <= 0
                   for row in points for key in ("btc", "e9")):
                continue
            first_rate = abs((used[1]["e9"] - origin["e9"]) * 60 /
                             (used[1]["time"] - origin["time"]))
            score = (first_sign != desired,
                     abs(first_rate - abs(observations.get("ema9_slope_per_min") or 0.0)),
                     -end, str(profile["id"]))
            candidates.append((score, {"id": f"PATTERN:{profile['id']}:{int(origin['time'])}:{int(end)}:{direction}",
                "family": "PATTERN", "label": "Observed historical arc segment" if arcs else "Observed historical leg segment",
                "conditional": True, "status": "HYPOTHETICAL_PATH", "points": points,
                "horizon_ts": points[-1]["time"], "ends_at_contract_close": points[-1]["time"] == close,
                "reference_ids": [profile["id"]], "reference_start_ts": origin["time"],
                "reference_end_ts": end, "reference_known_by_ts": asof,
                "reference_phase_ts": origin["time"], "orientation_to_current_ema9": orientation,
                "historical_close_interpolation": end % 60 != 0,
                "historical_ema9_turns": turns, "time_stretched": False, "repeated": False,
                "assumption": "MIRROR_COMPLETED_PRIOR_SHAPE_ONCE" if orientation < 0 else "TRANSLATE_COMPLETED_PRIOR_SHAPE_ONCE",
                "e9_projection_basis": "TRANSLATED_HISTORICAL_EMA9_TRACE_NOT_RECOMPUTED_FORECAST",
                "not_a_settlement_prediction": True}))
    return min(candidates, key=lambda row: row[0])[1] if candidates else None


def _active_pattern(context: Mapping | None, paths: list[dict],
                    observations: Mapping, market: Mapping, now: float,
                    profiles: Sequence[Mapping]) -> dict:
    """Select one existing analogue that actually matches the reported pattern.

    This is a presentation choice, not a territory detector. A current supported
    parent and fresh sprout take precedence over a local Heist box. A crossing
    alone never becomes a confirmed release. Paths retain their original shape,
    magnitude, timestamps and provenance; no smooth mountain is invented when
    neither completed prior profile contains a comparable remainder.
    """
    raw = _mapping(context)
    source = _number(raw.get("source_ts"))
    observed = _number(raw.get("observed_at"))
    result = {"status": "UNAVAILABLE", "key": None, "kind": None,
              "label": "Active pattern unavailable", "direction": None,
              "path_id": None, "source_ts": source, "territory": raw.get("owned_territory"),
              "continuity_generation": raw.get("continuity_generation"),
              "conditional": True, "execution_authority": False,
              "reason": "Current engine pattern context is required."}
    if (not raw or raw.get("physical_current") is not True
            or raw.get("ticker") != market.get("ticker")
            or source is None or abs(source - market["time"]) > 1e-6
            or observed is None or not 0 <= now - observed <= 5
            or source > now + 2 or now - source > 3):
        return result
    territory = str(raw.get("owned_territory") or "UNKNOWN")
    side = raw.get("owned_side")
    direction = {"YES": "UP", "NO": "DOWN"}.get(side)
    kind = territory
    labels = {"UP_RAIL": "Up rail continuation", "DOWN_RAIL": "Down rail continuation",
              "ALTERNATING_MOUNTAIN": "Alternating mountain · next arc",
              "ROLLING_MOUNTAIN": "Rolling mountain · next arc",
              "MARKET_HEIST": "Heist · next rotation"}
    label = labels.get(kind)
    identity = str(raw.get("territory_id") or territory)
    mission, gap = _mapping(raw.get("mission")), _mapping(raw.get("gap"))
    parent_source = _number(mission.get("source_ts"))
    gap_source = _number(gap.get("source_ts"))
    parent_side = mission.get("side")
    parent_current = bool(mission.get("current") is True and mission.get("supported") is True
        and mission.get("invalidated") is False and mission.get("status") == "ACTIVE"
        and mission.get("terminal") is False and mission.get("current_progress_supported") is True
        and parent_side in ("YES", "NO") and parent_source is not None
        and abs(parent_source - source) <= 1e-6)
    fresh_leg = bool(parent_current and gap_source is not None and abs(gap_source - source) <= 1e-6
        and gap.get("stage") in ("SPROUT", "DEVELOPING") and gap.get("side") == parent_side
        and gap.get("continued_on_latest_cross_side") is True)
    if raw.get("handoff_confirmed") is True and raw.get("release_candidate_side") in ("YES", "NO"):
        kind, side = "RELEASE", raw["release_candidate_side"]
        direction = {"YES": "UP", "NO": "DOWN"}[side]
        label = "Release " + direction.lower() + " · continuation"
    elif fresh_leg:
        kind, side = "FRESH_LEG", parent_side
        direction = {"YES": "UP", "NO": "DOWN"}[side]
        label = "Fresh " + direction.lower() + " leg · continuation"
        identity = str(mission.get("parent_id") or identity)
    elif territory == "RELEASE_TRANSITION" or raw.get("release_in_progress") is True:
        kind, side = "RELEASE_FORMING", raw.get("release_candidate_side")
        direction = {"YES": "UP", "NO": "DOWN"}.get(side)
        label = "Release " + (direction.lower() + " " if direction else "") + "watch · forming"
    elif territory in ("ALTERNATING_MOUNTAIN", "ROLLING_MOUNTAIN", "MARKET_HEIST"):
        # The next arc begins with the observed local EMA9 leg, not an old
        # territory side. The parent remains separately visible in Nautilus.
        direction = raw.get("current_direction") if raw.get("current_direction") in ("UP", "DOWN") else observations.get("ema9_direction")
    if not label or direction not in ("UP", "DOWN"):
        result["reason"] = "No directional active pattern is established by the engine."
        return result
    result.update(kind=kind, key=f"{kind}:{identity}:{direction}", label=label, direction=direction,
                  reason="No comparable completed historical shape for this pattern and contract phase.")
    desired = 1 if direction == "UP" else -1
    comparable = []
    for path in paths:
        values = [row["e9"] for row in path["points"]]
        changes = [b - a for a, b in zip(values, values[1:])]
        signs = [_sign(value) for value in changes if abs(value) > 1e-9]
        if not signs or signs[0] != desired:
            continue
        turns = sum(a != b for a, b in zip(signs, signs[1:]))
        travel = sum(abs(value) for value in changes)
        efficiency = abs(values[-1] - values[0]) / travel if travel else 0.0
        rail_like = kind in ("UP_RAIL", "DOWN_RAIL", "FRESH_LEG", "RELEASE", "RELEASE_FORMING")
        if rail_like and (path["family"] == "ROTATION_STALL" or turns or signs[-1] != desired):
            continue
        if kind in ("ALTERNATING_MOUNTAIN", "ROLLING_MOUNTAIN") and turns < 1:
            continue
        if kind == "MARKET_HEIST" and (path["family"] != "ROTATION_STALL" or turns < 1):
            continue
        first, second = path["points"][:2]
        rate = (second["e9"] - first["e9"]) * 60 / (second["time"] - first["time"])
        current_rate = observations.get("ema9_slope_per_min") or 0.0
        # Deterministic closeness is a display selector, never a win score.
        comparable.append((abs(abs(rate) - abs(current_rate)), -path["reference_end_ts"],
                           str(path["id"]), path, turns, efficiency))
    if not comparable:
        fallback = (_pattern_analogue(profiles, kind, direction, observations, market)
                    if observations.get("ema9_direction") in ("UP", "DOWN") else None)
        if fallback is None:
            return result
        paths.append(fallback)
        result.update(status="READY", path_id=fallback["id"], reference_ids=fallback["reference_ids"],
            reference_end_ts=fallback["reference_end_ts"], horizon_ts=fallback["horizon_ts"],
            historical_ema9_turns=fallback["historical_ema9_turns"],
            reason="One observed historical leg or arc segment, translated to now; it stops at that segment's duration or this contract's close.",
            basis="ENGINE_PATTERN_WITH_FINITE_COMPLETED_PRIOR_SHAPE", selection_is_probability=False,
            mirrored=fallback["orientation_to_current_ema9"] < 0,
            local_context=territory, confirmed_release=kind == "RELEASE")
        return result
    _, _, _, chosen, turns, efficiency = min(comparable, key=lambda row: row[:3])
    result.update(status="READY", path_id=chosen["id"], reference_ids=chosen["reference_ids"],
        reference_end_ts=chosen["reference_end_ts"], historical_ema9_turns=turns,
        horizon_ts=chosen["points"][-1]["time"],
        mirrored=chosen["orientation_to_current_ema9"] is not None and
            chosen["orientation_to_current_ema9"] * (-1 if chosen["family"] == "REVERSAL" else 1) < 0,
        historical_ema9_efficiency=efficiency,
        reason="Matching completed historical trace, translated to the current observation; conditional on this pattern continuing.",
        basis="ENGINE_PATTERN_WITH_COMPLETED_PRIOR_PROFILE_SHAPE", selection_is_probability=False,
        local_context=territory, confirmed_release=kind == "RELEASE")
    return result


def _historical_excursion(rows: Sequence[Mapping], ticker: str, side: str,
                          opening: float, now: float) -> dict | None:
    prefix = side.lower()
    ordered = sorted((_mapping(row) for row in rows or ()
                      if _mapping(row).get("ticker") == ticker
                      and _number(_mapping(row).get("time")) is not None
                      and opening <= float(row["time"]) <= now), key=lambda row: float(row["time"]))
    lowest = None
    best = None
    seen = set()
    for row in ordered:
        identity = row.get("quote_id")
        if not isinstance(identity, str) or not identity or identity in seen:
            continue
        seen.add(identity)
        ask, bid = _number(row.get(prefix + "_ask")), _number(row.get(prefix + "_bid"))
        ts = float(row["time"])
        if ask is None or bid is None or not 0 < bid <= ask < 1:
            continue
        if lowest is not None and ts > lowest["time"]:
            roi = bid / lowest["ask"] - 1
            if not math.isfinite(roi):
                continue
            if best is None or roi > best["gross_roi"]:
                best = {"ticker": ticker, "side": side, "entry_ask": lowest["ask"],
                        "entry_quote_id": lowest["quote_id"], "entry_time": lowest["time"],
                        "exit_bid": bid, "exit_quote_id": identity, "exit_time": ts,
                        "gross_roi": roi, "source": "OBSERVED_CHRONOLOGICAL_NATIVE_QUOTES",
                        "scope": "BEST_OBSERVED_ASK_THEN_LATER_BID_IN_CURRENT_CONTRACT",
                        "physical_swing_identity": None,
                        "full_lot_depth_proven": False, "fees_included": False,
                        "future_prediction": False, "not_a_fill": True,
                        "does_not_qualify_new_entry": True}
        if lowest is None or ask < lowest["ask"]:
            lowest = {"ask": ask, "time": ts, "quote_id": identity}
    return best


def _swings(quote: Mapping, history: Sequence[Mapping], ticker: str,
            opening: float, now: float, minimum: float, future_skew_seconds: float = 0.0) -> dict:
    result = {"minimum_gross_roi": minimum, "measurement": "RETURN_ON_ENTRY_PRICE",
              "adjustable": True, "automatic_take_profit": False,
              "future_bid_estimate_available": False, "sides": {}}
    qtime = _number(quote.get("time", quote.get("observed_wall")))
    fresh = bool(quote.get("fresh") is True and quote.get("ticker") == ticker
                 and qtime is not None and -future_skew_seconds <= now - qtime <= 3
                 and opening <= qtime)
    for side in ("YES", "NO"):
        value = _number(quote.get(side.lower() + "_ask")) if fresh else None
        bid = _number(quote.get(side.lower() + "_bid")) if fresh else None
        entry = value if value is not None and bid is not None and 0 < bid <= value < 1 else None
        required = float(Decimal(str(entry)) * (Decimal(1) + Decimal(str(minimum)))) if entry is not None else None
        if required is not None and not math.isfinite(required):
            required = None
        excursion = _historical_excursion(history, ticker, side, opening, now)
        status = "UNAVAILABLE" if entry is None else (
            "TARGET_ABOVE_ONE" if entry * (1 + minimum) > 1 else "NOT_ASSESSED")
        result["sides"][side] = {"entry_ask": entry, "required_exit_bid": required,
            "required_bid_basis": "ARITHMETIC_HURDLE_NOT_A_TICK_ROUNDED_ORDER",
            "status": status, "historical_excursion": excursion,
            "historical_filter_result": "INSUFFICIENT_QUOTE_HISTORY" if excursion is None else (
                "AT_OR_ABOVE_FILTER" if excursion["gross_roi"] + 1e-12 >= minimum else "BELOW_FILTER"),
            "entry_depth_proven": False, "exit_depth_proven": False, "fees_included": False,
            "reason": "A future executable bid and physical swing still require assessment."
                if status == "NOT_ASSESSED" else "Current exact-contract quote unavailable."
                if status == "UNAVAILABLE" else "The gross review hurdle exceeds binary par value."}
    return result


def build_looking_glass(market: Mapping, candles: Sequence[Mapping] = (),
                        emas: Sequence[Mapping] = (), targets: Sequence[Mapping] = (),
                        quote: Mapping | None = None, quote_history: Sequence[Mapping] = (),
                        *, now_ts: float,
                        pattern_context: Mapping | None = None,
                        config: LookingGlassConfig | Mapping | None = None) -> dict:
    """Return bounded, source-time-causal display context with zero authority.

    All temporal values are UTC epoch seconds. A candle's ``time`` denotes its
    opening minute; its close is usable only after ``time + 60`` and explicit
    ``known_at`` when supplied. Seed or chart data never becomes a fictitious
    intraminute path. Configuration changes presentation/review arithmetic only.
    """
    cfg = _config(config)
    now = _number(now_ts)
    if now is None or now < 0:
        raise ValueError("LOOKING_GLASS_INVALID_ASOF_TIME")
    original = _mapping(market)
    m = {key: _number(original.get(key)) for key in ("time", "btc", "e9", "e30", "target", "close_ts")}
    ticker = str(original.get("ticker") or "")
    asof = m["time"]
    close = m["close_ts"]
    opening = close - CONTRACT_SECONDS if close is not None else None
    valid_values = all(m[key] is not None and m[key] > 0 for key in ("btc", "e9", "e30"))
    physical_fresh = bool(original.get("fresh") is True and asof is not None
                          and -cfg.future_skew_seconds <= now - asof <= 3 and valid_values)
    clock_valid = bool(opening is not None and asof is not None
                       and opening <= asof <= now + cfg.future_skew_seconds
                       and now < close and close - now <= CONTRACT_SECONDS)
    if m["target"] is not None and m["target"] <= 0:
        m["target"] = None
    result = {"version": VERSION, "status": "UNAVAILABLE", "source_ts": asof,
        "valid_until": min(asof + 3, close) if physical_fresh and clock_valid else None,
        "ticker": ticker, "close_ts": close, "execution_authority": False,
        "can_veto": False, "can_order": False, "probabilities_calibrated": False,
        "reference_window": {"start_ts": None, "end_ts": opening,
            "requested_seconds": cfg.history_contracts * CONTRACT_SECONDS,
            "observed_seconds": 0, "point_count": 0, "completed_prior_contracts": 0,
            "directional_reference_contracts": 0, "directional_reference_coverage": "UNAVAILABLE",
            "gaps": [], "coverage": "UNAVAILABLE", "contracts": []},
        "observations": {}, "thesis": {"side": "UNKNOWN", "physical_lean": "UNKNOWN",
            "continuation_side": "UNKNOWN", "endpoint_sides": [], "settlement_prediction": False,
            "reason": "Current source, contract clock and observed history are required."},
        "timing": {"mode": "INSUFFICIENT_CONTEXT", "hard_cutoff_seconds": None,
            "reason": "No four-minute deadline is applied; timing follows observed structure and executable value."},
        "paths": [], "active_pattern": {"status": "UNAVAILABLE", "path_id": None,
            "label": "Active pattern unavailable", "conditional": True, "execution_authority": False,
            "reason": "Current physical observations and contract identity are required."},
        "swing_review": _swings(_mapping(quote), quote_history, ticker,
            opening if opening is not None else now, now, cfg.minimum_gross_roi, cfg.future_skew_seconds),
        "notes": ["Conditional historical-path exercises; no probabilities or order authority.",
            "EMA9 lines are translated historical traces, not recursively recomputed from hypothetical BTC paths.",
            "Coinbase/chart BTC and EMA9 are physical context, not the contract's official settlement series.",
            "Known current target only; no next-contract target is invented.",
            "Gross 40% (or configured) swing review is separate from fees, depth and exit policy."]}
    if not physical_fresh:
        result["status"] = "STALE" if asof is not None and valid_values else "UNAVAILABLE"
        result["thesis"]["reason"] = "Current physical observations are unavailable or stale."
        return result
    if not clock_valid or not ticker:
        result["thesis"]["reason"] = "Exact current contract clock or identity is unavailable."
        return result
    points, rejected = _completed_points(candles, emas, asof)
    reference_start = opening - cfg.history_contracts * CONTRACT_SECONDS
    profiles = [_profile(points, opening - index * CONTRACT_SECONDS,
                         opening - (index - 1) * CONTRACT_SECONDS, targets, asof, index)
                for index in range(1, cfg.history_contracts + 1)]
    usable = [profile for profile in profiles if profile["status"] == "COMPLETE"]
    observed = [point for point in points if reference_start <= point["time"] <= opening]
    gaps = [{"start_ts": a["time"], "end_ts": b["time"],
             "seconds": b["time"] - a["time"]}
            for a, b in zip(observed, observed[1:]) if b["time"] - a["time"] > 60]
    covered = sum(b["time"] - a["time"] for a, b in zip(observed, observed[1:])
                  if b["time"] - a["time"] == 60)
    result["reference_window"] = {"start_ts": reference_start, "end_ts": opening,
        "requested_seconds": cfg.history_contracts * CONTRACT_SECONDS,
        "observed_seconds": covered, "point_count": len(observed),
        "completed_prior_contracts": len(usable), "gaps": gaps,
        "coverage": "COMPLETE" if len(usable) == cfg.history_contracts else "PARTIAL" if observed else "UNAVAILABLE",
        "contracts": [{key: value for key, value in profile.items() if key != "points"} for profile in profiles],
        "excluded_observations": rejected, "basis": "COMPLETED_OBSERVED_MINUTE_CLOSES"}
    observations = _observations(points, m, asof, reference_start)
    result["observations"] = observations
    result["timing"] = {"mode": observations["regime"], "hard_cutoff_seconds": None,
        "contract_age_seconds": asof - opening,
        "reason": "Observed one-way progress can spend early value; there is no minute-four expiry."
            if observations["regime"] == "OBSERVED_ONE_WAY" else
            "Observed swings may offer later value; each actual edge and current quote still needs review."
            if observations["regime"] == "OBSERVED_SWINGS" else
            "Observed direction or excursion is insufficient; no timed entry is manufactured."}
    result["paths"] = _paths(usable, m, observations, asof, opening, close)
    result["active_pattern"] = _active_pattern(pattern_context, result["paths"], observations,
                                                {**m, "ticker": ticker}, now, usable)
    directional_count = len({path["reference_ids"][0] for path in result["paths"]
                             if path["family"] == "CONTINUATION"})
    result["reference_window"]["directional_reference_contracts"] = directional_count
    result["reference_window"]["directional_reference_coverage"] = (
        "COMPLETE" if directional_count == cfg.history_contracts else
        "PARTIAL" if directional_count else "UNAVAILABLE")
    endpoints = sorted({path["endpoint_side"] for path in result["paths"] if path["family"] != "PATTERN"})
    continuation = sorted({path["endpoint_side"] for path in result["paths"]
                           if path["family"] == "CONTINUATION"})
    overall = endpoints[0] if len(endpoints) == 1 and endpoints[0] in ("YES", "NO") else (
        "MIXED" if endpoints and "UNKNOWN" not in endpoints else "UNKNOWN")
    if observations["ema9_direction"] not in ("UP", "DOWN") or not continuation:
        overall = "UNKNOWN"
    continuation_side = continuation[0] if len(continuation) == 1 else "MIXED" if continuation else "UNKNOWN"
    result["thesis"] = {"side": overall,
        "physical_lean": {"UP": "YES", "DOWN": "NO"}.get(observations["ema9_direction"], "UNKNOWN"),
        "continuation_side": continuation_side, "endpoint_sides": endpoints,
        "settlement_prediction": False, "reason": "Conditional endpoints straddle the current target."
            if overall == "MIXED" else "All displayed conditional endpoints are on this side of the current target."
            if overall in ("YES", "NO") else "No supported current-target path conclusion is available.",
        "basis": "CONDITIONAL_ENDPOINTS_NOT_WIN_PROBABILITY"}
    result["status"] = "READY" if (directional_count == cfg.history_contracts and result["paths"]
                                   and observations["ema9_direction"] in ("UP", "DOWN")) else (
        "PARTIAL" if result["paths"] else "UNAVAILABLE")
    if not usable:
        result["thesis"]["reason"] = "No complete, contiguous prior-contract profile is available."
    elif observations["ema9_direction"] == "UNKNOWN":
        result["thesis"]["reason"] = "Current continuous EMA9 movement is unavailable; old profiles cannot supply it."
    elif observations["ema9_direction"] == "FLAT":
        result["thesis"]["reason"] = "Current EMA9 direction is flat; only conditional rotation paths are shown."
    elif not directional_count:
        result["thesis"]["reason"] = "Prior reference remainders have no net EMA9 direction; only conditional rotation paths are shown."
    elif directional_count < cfg.history_contracts:
        result["thesis"]["reason"] = (
            f"Only {directional_count} of {cfg.history_contracts} prior contracts supports directional scenarios. "
            + result["thesis"]["reason"])
    return result
