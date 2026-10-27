from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from strategy_core.types import Side


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _sign_side(
    value: float | None,
    eps: float,
) -> Side | None:
    if value is None:
        return None
    if value > eps:
        return Side.YES
    if value < -eps:
        return Side.NO
    return None


@dataclass(frozen=True)
class RailGeometryConfig:
    ema9_slope_epsilon: float = 0.02
    ema30_slope_epsilon: float = 0.01
    current_residence_window_s: float = 900.0
    current_residence_min_fraction: float = 0.62
    current_residence_min_samples: int = 8
    persistence_windows_s: tuple[float, ...] = (
        1800.0,
        1500.0,
        1200.0,
        900.0,
        720.0,
        600.0,
    )
    persistence_alignment_min_fraction: float = 0.70
    persistence_residence_min_fraction: float = 0.60
    persistence_min_samples: int = 8
    qualification_min_persistence_s: float = 900.0


@dataclass(frozen=True)
class RailGeometryDetection:
    side: Side | None
    ema30_side: Side | None
    ema_pair_parallel: bool
    directional_residence: bool
    current_residence_fraction: float
    persistence_seconds: float
    persistence_alignment_fraction: float
    persistence_residence_fraction: float
    qualified_rail: bool
    diagnostics: Mapping[str, Any]


def detect_rail_geometry(
    rows: Sequence[Mapping[str, Any]],
    config: RailGeometryConfig | None = None,
) -> RailGeometryDetection:
    cfg = config or RailGeometryConfig()
    if not rows:
        return RailGeometryDetection(
            None, None, False, False, 0.0, 0.0, 0.0, 0.0, False,
            {"reason": "NO_GEOMETRY_ROWS"},
        )

    last = rows[-1]
    last_ms = _num(last.get("epoch_ms"))

    ema9_sides = [
        _sign_side(
            _num(last.get(field)),
            cfg.ema9_slope_epsilon,
        )
        for field in (
            "struct_slope3m",
            "struct_slope6m",
            "struct_slope9m",
        )
    ]
    nonnull = [side for side in ema9_sides if side is not None]
    side = (
        nonnull[0]
        if nonnull
        and all(candidate is nonnull[0] for candidate in nonnull)
        else None
    )

    ema30_side = _sign_side(
        _num(last.get("ema30_slope3m")),
        cfg.ema30_slope_epsilon,
    )

    if last_ms is not None:
        cutoff = (
            last_ms
            - cfg.current_residence_window_s * 1000.0
        )
        recent = [
            row
            for row in rows
            if (
                (_num(row.get("epoch_ms")) or -1.0)
                >= cutoff
            )
        ]
    else:
        recent = list(rows[-90:])

    residence_votes = 0
    residence_total = 0
    if side is not None:
        for row in recent:
            btc = _num(row.get("btc_price"))
            e9 = _num(row.get("ema9"))
            e30 = _num(row.get("ema30"))
            if btc is None or e9 is None or e30 is None:
                continue
            residence_total += 1
            if side is Side.YES and btc >= e9 >= e30:
                residence_votes += 1
            elif side is Side.NO and btc <= e9 <= e30:
                residence_votes += 1

    current_residence_fraction = (
        residence_votes / residence_total
        if residence_total
        else 0.0
    )
    directional_residence = bool(
        residence_total >= cfg.current_residence_min_samples
        and current_residence_fraction
        >= cfg.current_residence_min_fraction
    )

    ema_pair_parallel = bool(
        side is not None
        and side is ema30_side
        and directional_residence
    )

    persistence_seconds = 0.0
    persistence_alignment_fraction = 0.0
    persistence_residence_fraction = 0.0

    if ema_pair_parallel and last_ms is not None:
        for window_s in cfg.persistence_windows_s:
            cutoff = last_ms - window_s * 1000.0
            window_rows = [
                row
                for row in rows
                if (
                    (_num(row.get("epoch_ms")) or -1.0)
                    >= cutoff
                )
            ]
            if len(window_rows) < cfg.persistence_min_samples:
                continue

            aligned = 0
            resident = 0
            usable = 0
            first_ms: float | None = None

            for row in window_rows:
                ts = _num(row.get("epoch_ms"))
                btc = _num(row.get("btc_price"))
                e9 = _num(row.get("ema9"))
                e30 = _num(row.get("ema30"))
                if (
                    ts is None
                    or btc is None
                    or e9 is None
                    or e30 is None
                ):
                    continue

                s9 = _sign_side(
                    _num(row.get("struct_slope3m")),
                    cfg.ema9_slope_epsilon,
                )
                s30 = _sign_side(
                    _num(row.get("ema30_slope3m")),
                    cfg.ema30_slope_epsilon,
                )

                if first_ms is None:
                    first_ms = ts
                usable += 1

                if s9 is side and s30 is side:
                    aligned += 1

                if (
                    (side is Side.YES and btc >= e9 >= e30)
                    or (side is Side.NO and btc <= e9 <= e30)
                ):
                    resident += 1

            if (
                usable < cfg.persistence_min_samples
                or first_ms is None
            ):
                continue

            align_fraction = aligned / usable
            residence_fraction = resident / usable
            span_s = max(
                0.0,
                (last_ms - first_ms) / 1000.0,
            )

            if (
                align_fraction
                >= cfg.persistence_alignment_min_fraction
                and residence_fraction
                >= cfg.persistence_residence_min_fraction
            ):
                persistence_seconds = span_s
                persistence_alignment_fraction = align_fraction
                persistence_residence_fraction = residence_fraction
                break

    qualified = bool(
        ema_pair_parallel
        and persistence_seconds
        >= cfg.qualification_min_persistence_s
    )

    return RailGeometryDetection(
        side=side,
        ema30_side=ema30_side,
        ema_pair_parallel=ema_pair_parallel,
        directional_residence=directional_residence,
        current_residence_fraction=current_residence_fraction,
        persistence_seconds=persistence_seconds,
        persistence_alignment_fraction=persistence_alignment_fraction,
        persistence_residence_fraction=persistence_residence_fraction,
        qualified_rail=qualified,
        diagnostics={
            "residence_samples": residence_total,
            "ema9_sides": [
                candidate.value
                if candidate is not None
                else None
                for candidate in ema9_sides
            ],
            "qualification_min_persistence_s": (
                cfg.qualification_min_persistence_s
            ),
        },
    )
