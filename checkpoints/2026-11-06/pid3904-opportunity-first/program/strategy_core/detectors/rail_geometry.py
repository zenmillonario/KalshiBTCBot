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
    current_residence_window_s: float = 450.0
    current_residence_min_fraction: float = 0.62
    current_residence_min_samples: int = 8
    persistence_windows_s: tuple[float, ...] = (
        900.0,
        720.0,
        600.0,
        450.0,
    )
    persistence_alignment_min_fraction: float = 0.70
    persistence_residence_min_fraction: float = 0.60
    persistence_min_samples: int = 8
    qualification_min_persistence_s: float = 450.0
    # Rail is a chapter, not a short local alignment. Inspect roughly two
    # contracts of causal EMA9 arc history and refuse Rail when a recent
    # opposite arc recovered at least the governing ~55% leg-break amount.
    chapter_history_window_s: float = 2700.0
    opposite_arc_break_fraction: float = 0.55
    min_same_direction_arcs: int = 1
    # Earlier Rail launch is allowed only when the physical parent/EMA pair is
    # already persistently rail-like; Tool Rack still requires parent agreement.
    early_launch_min_persistence_s: float = 450.0


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
    gap_start: float | None
    gap_end: float | None
    gap_maintaining_or_expanding: bool
    qualified_rail: bool
    diagnostics: Mapping[str, Any]


def detect_rail_geometry(
    rows: Sequence[Mapping[str, Any]],
    config: RailGeometryConfig | None = None,
) -> RailGeometryDetection:
    cfg = config or RailGeometryConfig()
    if not rows:
        return RailGeometryDetection(
            None, None, False, False, 0.0, 0.0, 0.0, 0.0, None, None, False, False,
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

    # User doctrine: an emerging Rail only needs about half a contract of
    # directional residence when the EMA9-EMA30 gap is maintaining or slowly
    # expanding.  This is descriptive geometry, not trade authority.
    gap_start = None
    gap_end = None
    gap_maintaining_or_expanding = False
    if side is not None and last_ms is not None:
        cutoff = last_ms - 450.0 * 1000.0
        gap_samples = []
        sign = 1.0 if side is Side.YES else -1.0
        for row in rows:
            ts = _num(row.get("epoch_ms"))
            e9 = _num(row.get("ema9"))
            e30 = _num(row.get("ema30"))
            if ts is None or ts < cutoff or e9 is None or e30 is None:
                continue
            gap_samples.append((ts, sign * (e9 - e30)))
        if len(gap_samples) >= 2:
            gap_start = gap_samples[0][1]
            gap_end = gap_samples[-1][1]
            gap_maintaining_or_expanding = bool(gap_end >= gap_start)

    # Broader chapter-history check. A genuine Rail may breathe, but it should
    # not contain a recent opposite EMA9 arc comparable in scale to the current
    # directional chapter. That is alternating-Mountain evidence instead.
    chapter_cutoff = (last_ms - cfg.chapter_history_window_s * 1000.0) if last_ms is not None else None
    arc_amplitudes: dict[tuple[str, str], float] = {}
    if side is not None:
        for row in rows:
            ts = _num(row.get("epoch_ms"))
            if chapter_cutoff is not None and (ts is None or ts < chapter_cutoff):
                continue
            aid = str(row.get("arc_id") or "")
            direction = str(row.get("arc_direction") or "").upper()
            amp = _num(row.get("arc_amplitude"))
            if not aid or direction not in ("UP", "DOWN") or amp is None:
                continue
            key = (aid, direction)
            arc_amplitudes[key] = max(arc_amplitudes.get(key, 0.0), abs(amp))
    same_dir = "UP" if side is Side.YES else "DOWN"
    opp_dir = "DOWN" if same_dir == "UP" else "UP"
    same_arcs = [(aid, amp) for (aid, direction), amp in arc_amplitudes.items()
                 if direction == same_dir]
    same_max = max((amp for aid, amp in same_arcs), default=0.0)
    same_arc_count = len(same_arcs)
    opposite_max = max((amp for (aid, direction), amp in arc_amplitudes.items()
                        if direction == opp_dir), default=0.0)
    chapter_history_available = bool(same_max > 0)
    opposite_recovery_fraction = (opposite_max / same_max) if same_max > 0 else None
    chapter_consistent = bool(
        chapter_history_available
        and same_arc_count >= cfg.min_same_direction_arcs
        and (opposite_recovery_fraction is None
             or opposite_recovery_fraction < cfg.opposite_arc_break_fraction)
    )

    qualified = bool(
        ema_pair_parallel
        and persistence_seconds >= cfg.qualification_min_persistence_s
        and gap_maintaining_or_expanding
        and chapter_consistent
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
        gap_start=gap_start,
        gap_end=gap_end,
        gap_maintaining_or_expanding=gap_maintaining_or_expanding,
        qualified_rail=qualified,
        diagnostics={
            "residence_samples": residence_total,
            "ema9_sides": [
                candidate.value
                if candidate is not None
                else None
                for candidate in ema9_sides
            ],
            "qualification_min_persistence_s": cfg.qualification_min_persistence_s,
            "recognition_basis": "HALF_CONTRACT_RESIDENCE_PLUS_MAINTAINED_OR_EXPANDING_GAP",
            "gap_start": gap_start,
            "gap_end": gap_end,
            "gap_maintaining_or_expanding": gap_maintaining_or_expanding,
            "chapter_history_window_s": cfg.chapter_history_window_s,
            "chapter_same_direction_max_arc_amplitude": same_max,
            "chapter_opposite_max_arc_amplitude": opposite_max,
            "chapter_opposite_recovery_fraction": opposite_recovery_fraction,
            "chapter_history_available": chapter_history_available,
        "same_direction_arc_count": same_arc_count,
        "min_same_direction_arcs": cfg.min_same_direction_arcs,
            "chapter_consistent": chapter_consistent,
            "chapter_disqualifier": ("RECENT_OPPOSITE_ARC_RECOVERED_55PCT_OR_MORE"
                                     if not chapter_consistent else None),
        },
    )
