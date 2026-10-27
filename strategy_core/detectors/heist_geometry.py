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


@dataclass(frozen=True)
class HeistGeometryConfig:
    candidate_windows_s: tuple[float, ...] = (180.0, 360.0, 540.0, 720.0)
    min_observed_span_s: float = 150.0
    min_box_range_dollars: float = 20.0
    prominence_multiple: float = 2.0
    edge_band_fraction: float = 0.12
    edge_band_min_dollars: float = 3.0
    center_low_fraction: float = 0.35
    center_high_fraction: float = 0.65
    minimum_lower_visits: int = 2
    minimum_upper_visits: int = 2
    minimum_center_traversals: int = 2
    max_ema9_drift_fraction: float = 0.45
    max_ema30_drift_fraction: float = 0.30
    lean_min_drift_fraction: float = 0.08


@dataclass(frozen=True)
class HeistGeometryDetection:
    qualified_box: bool
    compression_unresolved: bool
    lower: float | None
    upper: float | None
    box_range: float | None
    edge_tolerance: float | None
    lower_visits: int
    upper_visits: int
    center_traversals: int
    at_lower_edge: bool
    at_upper_edge: bool
    lean_side: Side | None
    box_id: str | None
    visit_id: str | None
    selected_window_s: float | None
    diagnostics: Mapping[str, Any]

    def tool_metadata(self) -> dict[str, Any]:
        return {
            "qualified_box": self.qualified_box,
            "at_lower_edge": self.at_lower_edge,
            "at_upper_edge": self.at_upper_edge,
            "box_id": self.box_id,
            "visit_id": self.visit_id,
            "lean_side": (
                self.lean_side.value
                if self.lean_side
                else None
            ),
            "release_confirmed": False,
            "detector": "TOOL_RACK_RAW_SIDEWAYS_BOX_V1",
            "diagnostics": dict(self.diagnostics),
        }


def _zone(
    price: float,
    lower: float,
    upper: float,
    edge_tolerance: float,
    cfg: HeistGeometryConfig,
) -> str:
    box_range = max(upper - lower, 1e-9)
    if price <= lower + edge_tolerance:
        return "LOWER"
    if price >= upper - edge_tolerance:
        return "UPPER"
    position = (price - lower) / box_range
    if cfg.center_low_fraction <= position <= cfg.center_high_fraction:
        return "CENTER"
    return "INNER"


def _compressed_zones(zones: Sequence[tuple[float, str]]) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for ts, zone in zones:
        if not out or out[-1][1] != zone:
            out.append((ts, zone))
    return out


def _visit_counts(compressed: Sequence[tuple[float, str]]) -> tuple[int, int, int]:
    lower = sum(zone == "LOWER" for _, zone in compressed)
    upper = sum(zone == "UPPER" for _, zone in compressed)
    centers = sum(zone == "CENTER" for _, zone in compressed)
    return lower, upper, centers


def _current_visit_id(
    compressed: Sequence[tuple[float, str]],
) -> str | None:
    if not compressed:
        return None
    ts, zone = compressed[-1]
    if zone not in ("LOWER", "UPPER"):
        return None
    return f"{zone}:{int(ts)}"


def _candidate(
    rows: Sequence[Mapping[str, Any]],
    cfg: HeistGeometryConfig,
) -> HeistGeometryDetection | None:
    pairs = [
        (
            _num(row.get("epoch_ms")),
            _num(row.get("btc_price")),
            _num(row.get("ema9")),
            _num(row.get("ema30")),
            _num(row.get("arc_prominence_threshold")),
        )
        for row in rows
    ]
    pairs = [
        item
        for item in pairs
        if item[0] is not None and item[1] is not None
    ]
    if len(pairs) < 6:
        return None

    first_ts = pairs[0][0]
    last_ts = pairs[-1][0]
    assert first_ts is not None and last_ts is not None
    span_s = max(0.0, (last_ts - first_ts) / 1000.0)
    if span_s < cfg.min_observed_span_s:
        return None

    prices = [item[1] for item in pairs if item[1] is not None]
    lower = min(prices)
    upper = max(prices)
    box_range = upper - lower

    prominence_values = [
        item[4]
        for item in pairs
        if item[4] is not None
    ]
    prominence = (
        prominence_values[-1]
        if prominence_values
        else 0.0
    )
    min_range = max(
        cfg.min_box_range_dollars,
        cfg.prominence_multiple * max(prominence, 0.0),
    )
    if box_range < min_range:
        return None

    e9_values = [
        item[2]
        for item in pairs
        if item[2] is not None
    ]
    e30_values = [
        item[3]
        for item in pairs
        if item[3] is not None
    ]
    e9_drift = (
        e9_values[-1] - e9_values[0]
        if len(e9_values) >= 2
        else 0.0
    )
    e30_drift = (
        e30_values[-1] - e30_values[0]
        if len(e30_values) >= 2
        else 0.0
    )

    sideways_enough = bool(
        abs(e9_drift) <= cfg.max_ema9_drift_fraction * box_range
        and abs(e30_drift) <= cfg.max_ema30_drift_fraction * box_range
    )
    if not sideways_enough:
        return None

    edge_tolerance = max(
        cfg.edge_band_min_dollars,
        cfg.edge_band_fraction * box_range,
    )

    zones = [
        (
            float(ts),
            _zone(
                float(price),
                lower,
                upper,
                edge_tolerance,
                cfg,
            ),
        )
        for ts, price, _, _, _ in pairs
        if ts is not None and price is not None
    ]
    compressed = _compressed_zones(zones)
    lower_visits, upper_visits, centers = _visit_counts(compressed)

    current_zone = compressed[-1][1] if compressed else "INNER"
    qualified = bool(
        lower_visits >= cfg.minimum_lower_visits
        and upper_visits >= cfg.minimum_upper_visits
        and centers >= cfg.minimum_center_traversals
    )

    # Compression can be physically obvious before the repeatable box is
    # qualified. In that state the correct action is WAIT, not invent an edge.
    compression_unresolved = bool(
        sideways_enough
        and not qualified
        and (
            lower_visits >= 1
            or upper_visits >= 1
        )
    )

    lean_side: Side | None = None
    combined_drift = 0.5 * e9_drift + 0.5 * e30_drift
    if abs(combined_drift) >= cfg.lean_min_drift_fraction * box_range:
        lean_side = Side.YES if combined_drift > 0 else Side.NO

    first_box_ts = int(float(first_ts))
    # Quantize boundaries by edge tolerance so small rolling-window changes do
    # not manufacture a different box identity every beat.
    lower_bucket = round(lower / edge_tolerance)
    upper_bucket = round(upper / edge_tolerance)
    box_id = (
        f"BOX:{lower_bucket}:{upper_bucket}:{first_box_ts}"
        if qualified or compression_unresolved
        else None
    )

    return HeistGeometryDetection(
        qualified_box=qualified,
        compression_unresolved=compression_unresolved,
        lower=lower,
        upper=upper,
        box_range=box_range,
        edge_tolerance=edge_tolerance,
        lower_visits=lower_visits,
        upper_visits=upper_visits,
        center_traversals=centers,
        at_lower_edge=current_zone == "LOWER",
        at_upper_edge=current_zone == "UPPER",
        lean_side=lean_side,
        box_id=box_id,
        visit_id=_current_visit_id(compressed),
        selected_window_s=span_s,
        diagnostics={
            "ema9_drift": e9_drift,
            "ema30_drift": e30_drift,
            "sideways_enough": sideways_enough,
            "compressed_zones": compressed[-16:],
            "minimum_box_range": min_range,
        },
    )


def detect_heist_geometry(
    rows: Sequence[Mapping[str, Any]],
    config: HeistGeometryConfig | None = None,
) -> HeistGeometryDetection:
    cfg = config or HeistGeometryConfig()
    valid_ts = [
        value
        for value in (_num(row.get("epoch_ms")) for row in rows)
        if value is not None
    ]
    if not valid_ts:
        return HeistGeometryDetection(
            False, False, None, None, None, None, 0, 0, 0,
            False, False, None, None, None, None,
            {"reason": "NO_TIMESTAMPED_GEOMETRY"},
        )

    last_ts = valid_ts[-1]
    unresolved: HeistGeometryDetection | None = None

    for window_s in cfg.candidate_windows_s:
        cutoff = last_ts - window_s * 1000.0
        window_rows = [
            row
            for row in rows
            if (
                (_num(row.get("epoch_ms")) or -1.0)
                >= cutoff
            )
        ]
        candidate = _candidate(window_rows, cfg)
        if candidate is None:
            continue
        if candidate.qualified_box:
            return HeistGeometryDetection(
                **{
                    **candidate.__dict__,
                    "selected_window_s": window_s,
                }
            )
        if candidate.compression_unresolved and unresolved is None:
            unresolved = HeistGeometryDetection(
                **{
                    **candidate.__dict__,
                    "selected_window_s": window_s,
                }
            )

    if unresolved is not None:
        return unresolved

    return HeistGeometryDetection(
        False, False, None, None, None, None, 0, 0, 0,
        False, False, None, None, None, None,
        {"reason": "NO_REPEATABLE_SIDEWAYS_BOX"},
    )
