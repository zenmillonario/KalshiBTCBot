from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from strategy_core.detectors.heist_geometry import HeistGeometryDetection
from strategy_core.detectors.mountain_geometry import MountainGeometryDetection
from strategy_core.tools.release import ReleaseEvidence
from strategy_core.types import Side, Territory


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _side_from_value(value: float | None, eps: float = 0.0) -> Side | None:
    if value is None:
        return None
    if value > eps:
        return Side.YES
    if value < -eps:
        return Side.NO
    return None


def _arc_side(value: Any) -> Side | None:
    text = str(value or "").upper()
    if text == "UP":
        return Side.YES
    if text == "DOWN":
        return Side.NO
    return None


def _opposite(side: Side | None) -> Side | None:
    if side is Side.YES:
        return Side.NO
    if side is Side.NO:
        return Side.YES
    return None


@dataclass(frozen=True)
class ReleaseGeometryConfig:
    ema9_cross_range60_fraction: float = 0.08
    min_cross_dollars: float = 2.0
    new_side_residence_fraction: float = 0.65
    new_side_stack_fraction: float = 0.55
    heist_break_edge_tolerance_fraction: float = 0.35


@dataclass(frozen=True)
class ReleaseProbe:
    btc: float | None
    ema9: float | None
    ema30: float | None
    range60: float
    arc_side: Side | None
    arc_phase: str
    short_struct_side: Side | None
    medium_struct_side: Side | None
    micro_side: Side | None
    yes_residence_fraction: float
    no_residence_fraction: float
    yes_stack_fraction: float
    no_stack_fraction: float
    heist_lower: float | None
    heist_upper: float | None
    heist_edge_tolerance: float | None
    mountain_extreme_btc: float | None
    mountain_edge_age_s: float | None
    diagnostics: Mapping[str, Any]


@dataclass(frozen=True)
class ReleaseGeometryDetection:
    evidence: ReleaseEvidence
    boundary_name: str
    diagnostics: Mapping[str, Any]


def _observed_change(rows: Sequence[Mapping[str, Any]], seconds: float) -> dict[str, Any]:
    """Measure actual received endpoints; a missing interval is not growth."""
    points = [(ts, btc, e9, row.get("connection_epoch")) for row in rows
              if (ts := _num(row.get("epoch_ms"))) is not None
              and (btc := _num(row.get("btc_price"))) is not None
              and (e9 := _num(row.get("ema9"))) is not None]
    if not points:
        return {"covered": False, "requested_seconds": seconds}
    last = points[-1]
    start = next((point for point in reversed(points) if point[0] <= last[0] - seconds * 1000), None)
    if start is None:
        return {"covered": False, "requested_seconds": seconds}
    segment = [point for point in points if point[0] >= start[0]]
    continuous = all(0 < b[0] - a[0] <= 15000 and a[3] == b[3]
                     for a, b in zip(segment, segment[1:]))
    elapsed = (last[0] - start[0]) / 1000.0
    return {"covered": continuous, "requested_seconds": seconds,
            "start_source_ms": start[0], "end_source_ms": last[0],
            "actual_elapsed_seconds": elapsed,
            "btc_change": last[1] - start[1], "ema9_change": last[2] - start[2],
            "btc_rate": (last[1] - start[1]) / elapsed,
            "ema9_rate": (last[2] - start[2]) / elapsed}


def build_release_probe(
    rows: Sequence[Mapping[str, Any]],
    *,
    heist: HeistGeometryDetection | None = None,
    mountain: MountainGeometryDetection | None = None,
) -> ReleaseProbe:
    if not rows:
        return ReleaseProbe(
            None, None, None, 1.0, None, "", None, None, None,
            0.0, 0.0, 0.0, 0.0,
            None, None, None, None, None,
            {"reason": "NO_ROWS"},
        )

    last = rows[-1]
    last_ms = _num(last.get("epoch_ms"))
    recent = []
    if last_ms is not None:
        cutoff = last_ms - 90_000.0
        recent = [
            row for row in rows
            if (_num(row.get("epoch_ms")) or -1.0) >= cutoff
        ]
    if not recent:
        recent = list(rows[-30:])

    yes_res = no_res = yes_stack = no_stack = usable = 0
    for row in recent:
        btc = _num(row.get("btc_price"))
        e9 = _num(row.get("ema9"))
        e30 = _num(row.get("ema30"))
        if btc is None or e9 is None or e30 is None:
            continue
        usable += 1
        if btc >= e9:
            yes_res += 1
        if btc <= e9:
            no_res += 1
        if btc >= e9 >= e30:
            yes_stack += 1
        if btc <= e9 <= e30:
            no_stack += 1

    denom = max(1, usable)

    # Zero is an observed pause, not permission to substitute another signal.
    micro = next((value for key in ("micro_slope9s", "micro_slope6s", "btc_change9")
                  if (value := _num(last.get(key))) is not None), None)
    motion = {str(seconds): _observed_change(rows, seconds) for seconds in (6, 30, 60)}

    return ReleaseProbe(
        btc=_num(last.get("btc_price")),
        ema9=_num(last.get("ema9")),
        ema30=_num(last.get("ema30")),
        range60=max(1.0, _num(last.get("range60")) or 1.0),
        arc_side=_arc_side(last.get("arc_direction")),
        arc_phase=str(last.get("arc_phase") or "").upper(),
        short_struct_side=_side_from_value(
            _num(last.get("struct_slope3m")),
            eps=0.02,
        ),
        medium_struct_side=_side_from_value(
            _num(last.get("struct_slope6m")),
            eps=0.02,
        ),
        micro_side=_side_from_value(micro, eps=0.0),
        yes_residence_fraction=yes_res / denom,
        no_residence_fraction=no_res / denom,
        yes_stack_fraction=yes_stack / denom,
        no_stack_fraction=no_stack / denom,
        heist_lower=(heist.lower if heist else None),
        heist_upper=(heist.upper if heist else None),
        heist_edge_tolerance=(heist.edge_tolerance if heist else None),
        mountain_extreme_btc=(
            mountain.owner_extreme_btc if mountain else None
        ),
        mountain_edge_age_s=(
            mountain.edge_age_s if mountain else None
        ),
        diagnostics={
            "recent_rows": usable,
            "arc_phase": str(last.get("arc_phase") or "").upper(),
            "source_ms": last_ms,
            "expansion_measurement": {
                "basis": "CURRENT_RECEIVED_BTC_EMA9_ADVANCE_V1",
                "motion": motion,
                "mountain_strong_active_release": bool(mountain and mountain.strong_active_release),
                "ordinary_arc_change_is_release": False,
            },
            "native_turn_observed": bool(last.get("arc_origin_observed") is True
                and _num(last.get("arc_known_ms")) is not None
                and _num(last.get("arc_start_ms")) is not None),
        },
    )


def detect_release_for_owner(
    probe: ReleaseProbe,
    *,
    owner_territory: Territory,
    owner_side: Side | None,
    config: ReleaseGeometryConfig | None = None,
) -> ReleaseGeometryDetection:
    cfg = config or ReleaseGeometryConfig()
    # A neutral Heist can release either direction. Directional territories
    # normally hand off to the opposite side.
    candidate: Side | None = None
    boundary_break = False
    boundary_name = "NONE"

    if owner_territory is Territory.MARKET_HEIST:
        if (
            probe.btc is not None
            and probe.heist_upper is not None
            and probe.heist_edge_tolerance is not None
            and probe.btc
            > probe.heist_upper
            + cfg.heist_break_edge_tolerance_fraction
            * probe.heist_edge_tolerance
        ):
            candidate = Side.YES
            boundary_break = True
            boundary_name = "HEIST_UPPER_BREAK"
        elif (
            probe.btc is not None
            and probe.heist_lower is not None
            and probe.heist_edge_tolerance is not None
            and probe.btc
            < probe.heist_lower
            - cfg.heist_break_edge_tolerance_fraction
            * probe.heist_edge_tolerance
        ):
            candidate = Side.NO
            boundary_break = True
            boundary_name = "HEIST_LOWER_BREAK"
    else:
        candidate = _opposite(owner_side)
        cross_tolerance = max(
            cfg.min_cross_dollars,
            cfg.ema9_cross_range60_fraction * probe.range60,
        )
        if (
            candidate is Side.YES
            and probe.btc is not None
            and probe.ema9 is not None
            and probe.btc >= probe.ema9 + cross_tolerance
        ):
            boundary_break = True
            boundary_name = "PRICE_ABOVE_EMA9_AGAINST_OLD_OWNER"
        elif (
            candidate is Side.NO
            and probe.btc is not None
            and probe.ema9 is not None
            and probe.btc <= probe.ema9 - cross_tolerance
        ):
            boundary_break = True
            boundary_name = "PRICE_BELOW_EMA9_AGAINST_OLD_OWNER"

    if candidate is None:
        return ReleaseGeometryDetection(
            ReleaseEvidence(),
            boundary_name,
            {"reason": "NO_RELEASE_CANDIDATE"},
        )

    residence = (
        probe.yes_residence_fraction
        if candidate is Side.YES
        else probe.no_residence_fraction
    )
    stack = (
        probe.yes_stack_fraction
        if candidate is Side.YES
        else probe.no_stack_fraction
    )

    legacy_directional_expansion = bool(
        probe.short_struct_side is candidate
        and (
            probe.micro_side is candidate
            or probe.arc_phase in ("BUILDING", "EXPANDING")
        )
    )

    measurement = probe.diagnostics.get("expansion_measurement")
    if isinstance(measurement, Mapping):
        motions = measurement.get("motion", {})
        motions = motions if isinstance(motions, Mapping) else {}
        short = motions.get("6", {})
        current = motions.get("30", {})
        long = motions.get("60", {})
        sign = 1.0 if candidate is Side.YES else -1.0
        covered = all(isinstance(item, Mapping) and item.get("covered") is True
                      for item in (short, current, long))
        e6 = sign * (_num(short.get("ema9_change")) or 0.0)
        b6 = sign * (_num(short.get("btc_change")) or 0.0)
        e30 = sign * (_num(current.get("ema9_change")) or 0.0)
        b30 = sign * (_num(current.get("btc_change")) or 0.0)
        e60 = sign * (_num(long.get("ema9_change")) or 0.0)
        previous = e60 - e30
        current_seconds = _num(current.get("actual_elapsed_seconds")) or 0.0
        previous_seconds = (_num(long.get("actual_elapsed_seconds")) or 0.0) - current_seconds
        min_ema_advance = max(cfg.min_cross_dollars, .20 * probe.range60)
        min_btc_advance = max(cfg.min_cross_dollars, cfg.ema9_cross_range60_fraction * probe.range60)
        native_accelerating = bool(covered and current_seconds > 0 and previous_seconds > 0
                                  and previous > 0 and e30 / current_seconds >= 1.10 * previous / previous_seconds
                                  and e30 >= min_ema_advance)
        independently_strong = measurement.get("mountain_strong_active_release") is True
        sustained_separation = bool(covered and stack >= cfg.new_side_stack_fraction
            and e30 >= min_ema_advance and previous > 0
            and e60 >= 2 * min_ema_advance
            and probe.btc is not None and probe.ema9 is not None
            and sign * (probe.btc - probe.ema9) >= max(cfg.min_cross_dollars,
                cfg.ema9_cross_range60_fraction * probe.range60))
        # A phase string, three-minute sign, or newly assigned arc ID is not
        # exceptional expansion. Require current actual forward movement and
        # either independently measured strong geometry or growing substantial
        # native advance. An ordinary turn has its own Mountain route.
        directional_expansion = bool(covered and probe.arc_side is candidate
            and e6 > 0 and b6 > 0 and e30 > 0 and b30 >= min_btc_advance
            and (independently_strong or native_accelerating or sustained_separation))
        expansion_details = {"measured": True, "covered": covered,
            "held_ema9_6s": e6, "held_btc_6s": b6, "held_ema9_30s": e30,
            "held_btc_30s": b30, "previous_ema9_30s": previous,
            "minimum_ema9_advance": min_ema_advance,
            "minimum_btc_advance": min_btc_advance,
            "native_accelerating": native_accelerating,
            "sustained_separation": sustained_separation,
            "current_observed_seconds": current_seconds,
            "previous_observed_seconds": previous_seconds,
            "independent_strong_geometry": independently_strong}
    else:
        # Older observer adapters and explicit hand-built unit probes retain
        # their schema. DirectPhysicalSource always supplies measured evidence.
        directional_expansion = legacy_directional_expansion
        expansion_details = {"measured": False, "basis": "LEGACY_PROBE_SCHEMA"}

    # "Failed re-extension" is not synonymous with "an opposite arc exists".
    # Require a developed opposite arc plus an actual boundary transfer.
    # BUILDING/EXPANDING alone remains ordinary Mountain/leg geometry.
    old_owner_failed_reextension = bool(
        probe.arc_side is candidate
        and probe.arc_phase in ("MATURE", "CREST_FORMING", "TROUGH_FORMING", "ROLLING")
        and boundary_break
    )

    new_side_residence = bool(
        residence >= cfg.new_side_residence_fraction
        and (
            probe.short_struct_side is candidate
            or stack >= cfg.new_side_stack_fraction
        )
    )

    # Explicitly distinguish mere owner slowdown from transfer evidence.
    first_slowdown_only = bool(
        not boundary_break
        and probe.arc_side is owner_side
        and probe.arc_phase
        in ("MATURE", "CREST_FORMING", "TROUGH_FORMING", "ROLLING")
    )

    return ReleaseGeometryDetection(
        evidence=ReleaseEvidence(
            candidate_side=candidate,
            boundary_break=boundary_break,
            directional_expansion=directional_expansion,
            old_owner_failed_reextension=old_owner_failed_reextension,
            new_side_residence=new_side_residence,
            first_slowdown_only=first_slowdown_only,
        ),
        boundary_name=boundary_name,
        diagnostics={
            "candidate": candidate.value,
            "residence_fraction": residence,
            "stack_fraction": stack,
            "arc_side": (
                probe.arc_side.value if probe.arc_side else None
            ),
            "short_struct_side": (
                probe.short_struct_side.value
                if probe.short_struct_side else None
            ),
            "micro_side": (
                probe.micro_side.value if probe.micro_side else None
            ),
            "directional_expansion_evidence": expansion_details,
        },
    )
