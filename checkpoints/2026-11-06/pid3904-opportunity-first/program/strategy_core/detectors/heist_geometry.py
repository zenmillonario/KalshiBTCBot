from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from strategy_core.types import Side


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        result = float(value)
        return result if math.isfinite(result) and not isinstance(value, bool) else None
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
    max_box_range_price_fraction: float = 0.0015
    compression_drift_fraction: float = 0.20
    parallel_drift_difference_fraction: float = 0.10
    lean_min_drift_fraction: float = 0.08
    # PID23160: a wide first-pass box is a WATCH unless the EMA pair has
    # genuinely settled and the current 30s excursion is no longer a living
    # directional move. Classic repeatedly revisited Heist is unaffected.
    wide_max_ema9_drift_fraction: float = 0.12
    wide_max_ema30_drift_fraction: float = 0.45
    wide_max_btc30_fraction: float = 0.10
    wide_max_btc60_fraction: float = 0.14
    wide_quiet_ema9_30_fraction: float = 0.005
    wide_quiet_ema9_60_fraction: float = 0.007
    wide_min_center_traversals: int = 2


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
            "lower": self.lower,
            "upper": self.upper,
            "edge_tolerance": self.edge_tolerance,
            "current_zone": self.diagnostics.get("current_zone"),
            "lean_side": (
                self.lean_side.value
                if self.lean_side
                else None
            ),
            "lean_evidence": self.diagnostics.get("lean_evidence"),
            "release_confirmed": False,
            "detector": "TOOL_RACK_RAW_SIDEWAYS_BOX_V1",
            "repeatability_proof": self.diagnostics.get("repeatability_proof"),
            "diagnostics": {key: value for key, value in self.diagnostics.items()
                            if key != "repeatability_proof"},
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
    # Brief INNER excursions do not complete an edge visit. A revisit must be
    # separated by center traversal or the opposite edge, not a boundary wiggle.
    visits = _physical_visits(compressed)
    lower = sum(zone == "LOWER" for _, zone in visits)
    upper = sum(zone == "UPPER" for _, zone in visits)
    centers = sum(zone == "CENTER" for _, zone in visits)
    return lower, upper, centers


def _physical_visits(
    compressed: Sequence[tuple[float, str]],
) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for ts, zone in compressed:
        if zone == "INNER":
            continue
        if not out or out[-1][1] != zone:
            out.append((ts, zone))
    return out


def _current_visit_id(
    compressed: Sequence[tuple[float, str]],
) -> str | None:
    if not compressed:
        return None
    _, current_zone = compressed[-1]
    if current_zone not in ("LOWER", "UPPER"):
        return None
    visits = _physical_visits(compressed)
    ts, zone = visits[-1]
    if zone not in ("LOWER", "UPPER"):
        return None
    return f"{zone}:{int(ts)}"


def _current_ema9_lean(rows: Sequence[Mapping[str, Any]], box_range: float,
                      cfg: HeistGeometryConfig) -> tuple[Side | None, dict[str, Any]]:
    """Describe the observed current leg, never average it with old EMA30 drift.

    The box window earns repeatability; its old slope is not the direction of
    the present swing. Three covered EMA9 horizons must agree before a side
    receives the favored-size label. This classification does not veto a
    separately qualified counter swing or a blind full-arc return.
    """
    end = _num(rows[-1].get("epoch_ms")) if rows else None
    last_e9 = _num(rows[-1].get("ema9")) if rows else None
    proof: dict[str, Any] = {"version": "CURRENT_EMA9_LEG_LEAN_V2",
        "source_ms": end, "side": None, "status": "UNAVAILABLE",
        "basis": "COVERED_CURRENT_EMA9_6_30_60_SECONDS", "horizons": {},
        "historical_ema30_can_override": False}
    if end is None or last_e9 is None:
        return None, proof
    signs = []
    for seconds in (6, 30, 60):
        before = [i for i, row in enumerate(rows)
                  if (t := _num(row.get("epoch_ms"))) is not None
                  and t <= end - seconds * 1000.]
        if not before:
            return None, proof
        samples = rows[before[-1]:]
        times = [_num(row.get("epoch_ms")) for row in samples]
        values = [_num(row.get("ema9")) for row in samples]
        epochs = [row.get("connection_epoch") for row in samples]
        # Epoch-less isolated detector fixtures remain descriptive only.
        epoch_known = epochs[0] is not None
        covered = bool(all(t is not None for t in times)
            and all(v is not None for v in values)
            and all(a < b <= a + 15000. for a, b in zip(times, times[1:]))
            and (not epoch_known or all(e == epochs[0] for e in epochs))
            and end - seconds * 1000. - times[0] <= 15000.)
        if not covered:
            return None, proof
        duration = (end - times[0]) / 1000.
        change = last_e9 - values[0]
        # Retain the existing box-relative drift resolution, scaled to the
        # actual observed horizon instead of assigning direction to dust.
        resolution = cfg.lean_min_drift_fraction * box_range * duration / max(
            cfg.min_observed_span_s, duration)
        sign = 1 if change > resolution else -1 if change < -resolution else 0
        signs.append(sign)
        proof["horizons"][str(seconds)] = {"source_ms": end,
            "start_source_ms": times[0], "observed_duration_s": duration,
            "ema9_change": change, "resolution": resolution, "covered": True,
            "connection_epoch": epochs[0] if epoch_known else None,
            "single_connection_epoch": epoch_known}
    side = Side.YES if all(s == 1 for s in signs) else Side.NO if all(s == -1 for s in signs) else None
    proof.update(side=side.value if side else None,
        status="DIRECTIONAL" if side else "NEUTRAL" if all(s == 0 for s in signs) else "MIXED")
    return side, proof


def _covered_recent_motion(rows: Sequence[Mapping[str, Any]],
                           *, seconds: float = 30.0) -> tuple[float, float] | None:
    """Price and EMA9 changes from the same observed 30s source path.

    Never infer a turn from a future sample, an unbridged reconnect, or a gap
    between distant candles. This is a *wide-box territory qualification*,
    not a trading recommendation or an adviser's veto.
    """
    if not rows:
        return None
    end = _num(rows[-1].get("epoch_ms"))
    if end is None:
        return None
    start_at = None
    for i, row in enumerate(rows):
        t = _num(row.get("epoch_ms"))
        if t is not None and t <= end - seconds * 1000.0:
            start_at = i
    if start_at is None:
        return None
    selected = rows[start_at:]
    times = [_num(r.get("epoch_ms")) for r in selected]
    values = [_num(r.get("btc_price")) for r in selected]
    ema = [_num(r.get("ema9")) for r in selected]
    if (any(v is None for v in times + values + ema)
            or any(not 0 < b-a <= 15000.0 for a,b in zip(times,times[1:]))):
        return None
    epochs = [r.get("connection_epoch") for r in selected]
    if epochs[0] is not None and any(x != epochs[0] for x in epochs):
        return None
    assert values[0] is not None and values[-1] is not None
    assert ema[0] is not None and ema[-1] is not None
    return values[-1] - values[0], ema[-1] - ema[0]


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
    # "Tight" is structural, not an arbitrary BTC-dollar/price-percent cap:
    # the same bounded walls must be revisited, while the EMA pair is either
    # compressed or parallel. This keeps Heist from claiming broad trends.
    tight_box = True
    compression = bool(
        abs(e9_drift) <= cfg.compression_drift_fraction * box_range
        and abs(e30_drift) <= cfg.max_ema30_drift_fraction * box_range
    )
    parallel_emas = bool(
        abs(e9_drift - e30_drift) <= cfg.parallel_drift_difference_fraction * box_range
        and (e9_drift == 0 or e30_drift == 0 or e9_drift * e30_drift > 0)
    )
    heist_environment = bool(sideways_enough and tight_box and (compression or parallel_emas))
    if not heist_environment:
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
    classic_qualified = bool(
        lower_visits >= cfg.minimum_lower_visits
        and upper_visits >= cfg.minimum_upper_visits
        and centers >= cfg.minimum_center_traversals
    )
    # PID23160: the former wide route accepted one excursion across a very
    # broad directional Mountain, because the box RANGE made EMA drift look
    # negligible. Mere first wall visits are not sufficient evidence of an
    # established alternating Heist. Preserve a genuinely quiet, parallel
    # wide-box possibility with observed bilateral visits and center revisits,
    # but do not grant it ownership during active 30s directional expansion.
    # Its failure remains compression WATCH; classic repeatable boxes do not
    # inherit these conservative wide-only requirements.
    recent_motion = _covered_recent_motion(rows)
    motion60 = _covered_recent_motion(rows, seconds=60.)
    wide_current_calm = bool(
        recent_motion is not None and motion60 is not None
        and (abs(recent_motion[0]) <= cfg.wide_max_btc30_fraction * box_range
             or abs(recent_motion[1]) <= cfg.wide_quiet_ema9_30_fraction * box_range)
        and (abs(motion60[0]) <= cfg.wide_max_btc60_fraction * box_range
             or abs(motion60[1]) <= cfg.wide_quiet_ema9_60_fraction * box_range)
    )
    wide_heist_qualified = bool(
        not classic_qualified
        and span_s >= max(300.0, 2.0 * cfg.min_observed_span_s)
        and box_range >= 1.25 * min_range
        and lower_visits >= 1 and upper_visits >= 1
        and centers >= cfg.wide_min_center_traversals
        and abs(e9_drift) <= cfg.wide_max_ema9_drift_fraction * box_range
        and abs(e30_drift) <= cfg.wide_max_ema30_drift_fraction * box_range
        and wide_current_calm
    )
    qualified = bool(classic_qualified or wide_heist_qualified)

    # Compression can be physically obvious before the repeatable box is
    # qualified. In that state the correct action is WAIT, not invent an edge.
    compression_unresolved = bool(
        heist_environment
        and not qualified
        and (
            lower_visits >= 1
            or upper_visits >= 1
        )
    )

    lean_side, lean_evidence = _current_ema9_lean(rows, box_range, cfg)

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

    # Preserve the actual observations that earned repeatability. A controller
    # can then distinguish a new box after a release from an old box label.
    # Only the last required visits of each kind are needed for that proof;
    # unlike the display tail of compressed_zones, INNER noise cannot truncate
    # a required opposite-wall visit from the evidence.
    visits = _physical_visits(compressed)
    required = {"LOWER": cfg.minimum_lower_visits, "UPPER": cfg.minimum_upper_visits,
                "CENTER": cfg.minimum_center_traversals}
    supporting_visits = sorted(
        item for zone, count in required.items()
        for item in [visit for visit in visits if visit[1] == zone][-max(1, count):]
    )
    epochs = [row.get("connection_epoch") for row in rows]
    same_epoch = bool(epochs and epochs[0] is not None
                      and all(epoch == epochs[0] for epoch in epochs))
    times = [float(item[0]) for item in pairs]
    proof = {"source": "OBSERVED_HEIST_REPEATABILITY_V1",
        "window_start_ms": first_ts, "window_end_ms": last_ts,
        "observed_span_s": span_s, "observed_samples": len(pairs),
        "connection_epoch": epochs[0] if same_epoch else None,
        "single_connection_epoch": same_epoch,
        "strict_source_times": all(a < b for a, b in zip(times, times[1:])),
        "lower": lower, "upper": upper, "edge_tolerance": edge_tolerance,
        "ema9_drift": e9_drift, "ema30_drift": e30_drift,
        "tight_box": tight_box, "compression": compression,
        "parallel_emas": parallel_emas, "heist_environment": heist_environment,
        "lower_visits": lower_visits, "upper_visits": upper_visits,
        "center_traversals": centers,
        "classic_qualified": classic_qualified,
        "wide_heist_qualified": wide_heist_qualified,
        "repeatability_visits": [{"epoch_ms": ts, "zone": zone}
                                 for ts, zone in supporting_visits]}

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
            "lean_evidence": lean_evidence,
            "sideways_enough": sideways_enough,
            "tight_box": tight_box,
            "compression": compression,
            "parallel_emas": parallel_emas,
            "heist_environment": heist_environment,
            "classic_qualified": classic_qualified,
            "wide_heist_qualified": wide_heist_qualified,
            "compressed_zones": compressed[-16:],
            "current_zone": current_zone,
            "minimum_box_range": min_range,
            "repeatability_proof": proof,
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
