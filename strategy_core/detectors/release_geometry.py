from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from strategy_core.detectors.heist_geometry import HeistGeometryDetection
from strategy_core.detectors.mountain_geometry import MountainGeometryDetection
from strategy_core.tools.release import ReleaseEvidence
from strategy_core.types import Side, Territory


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
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

    micro = (
        _num(last.get("micro_slope9s"))
        or _num(last.get("btc_change9"))
        or _num(last.get("micro_slope6s"))
    )

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

    directional_expansion = bool(
        probe.short_struct_side is candidate
        and (
            probe.micro_side is candidate
            or probe.arc_phase in ("BUILDING", "EXPANDING")
        )
    )

    old_owner_failed_reextension = bool(
        probe.arc_side is candidate
        and probe.arc_phase
        in (
            "BUILDING",
            "MATURE",
            "CREST_FORMING",
            "TROUGH_FORMING",
            "ROLLING",
            "EXPANDING",
        )
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
        },
    )
