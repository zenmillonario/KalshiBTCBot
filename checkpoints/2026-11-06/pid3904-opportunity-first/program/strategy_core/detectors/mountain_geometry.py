from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, replace
import math
from statistics import mean, median
from typing import Any, Mapping, Sequence

from strategy_core.types import Side


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _direction(value: Any) -> str | None:
    text = str(value or "").upper()
    return text if text in ("UP", "DOWN") else None


def _side(direction: str | None) -> Side | None:
    if direction == "UP":
        return Side.YES
    if direction == "DOWN":
        return Side.NO
    return None


@dataclass(frozen=True)
class MountainGeometryConfig:
    protected_middle_fraction: float = 0.60
    minimum_comparable_count: int = 2
    preferred_comparable_count: int = 4
    edge_window_min_s: float = 90.0
    edge_window_max_s: float = 360.0
    edge_window_duration_fraction: float = 0.35
    edge_tolerance_range60_fraction: float = 0.08
    retreat_range60_fraction: float = 0.12
    min_retreat_dollars: float = 2.0
    # Compatibility only: elapsed age / a phase label cannot establish maturity.
    mature_phase_fallback_min_age_s: float = 60.0
    # Backbone §0C / §0D resolutions. Provisional PAPER measurements, not
    # calibrated profitability thresholds or a required all-yes entry grade.
    gap_relative_tolerance: float = 0.18
    height_relative_tolerance: float = 0.20
    normalized_shape_tolerance: float = 0.25
    native_max_gap_s: float = 15.0
    slowdown_window_s: float = 6.0
    sideways_min_btc_per_s: float = 0.15
    sideways_range60_fraction_per_s: float = 0.01
    contact_min_dollars: float = 3.0
    contact_range60_fraction: float = 0.12
    expansion_ratio: float = 1.10
    # Parent-envelope governance: ordinary/tight Mountains remain untouched
    # through six minutes. Beyond that, child arcs cannot reverse a still-live
    # larger parent until the parent shape itself earns a terminal. A parent
    # spanning one full 15-minute contract is managed as Slow Rolling/Rail-like.
    parent_guard_min_age_s: float = 360.0
    slow_rolling_min_age_s: float = 900.0
    parent_shape_progress_fraction: float = 0.60


@dataclass(frozen=True)
class ArcEpisode:
    arc_id: str
    direction: str
    start_ms: float
    end_ms: float
    duration_s: float
    max_btc: float | None
    min_btc: float | None
    last_btc: float | None
    max_ema9: float | None
    min_ema9: float | None
    last_phase: str
    max_age_s: float
    max_amplitude: float
    prominence_threshold: float
    completed_known_ms: float | None
    native_reversal_observed: bool
    path_rows: tuple[Mapping[str, Any], ...]
    coverage: Mapping[str, Any]
    peak_pairs: tuple[Mapping[str, Any], ...]
    origin_observed: bool = True
    reference_kind: str = "SOVEREIGN_EMA9_ARC"


@dataclass(frozen=True)
class MountainGeometryDetection:
    qualified_alternating_mountain: bool
    owner_side: Side | None
    current_arc_id: str | None
    mature_edge: bool
    edge_window_active: bool
    stall: bool
    hesitation: bool
    failed_reextension: bool
    meaningful_retreat: bool
    strong_active_release: bool
    comparable_duration_mean_s: float | None
    comparable_duration_median_s: float | None
    comparable_count: int
    maturity_progress: float | None
    edge_age_s: float | None
    owner_extreme_btc: float | None
    retreat_dollars: float | None
    edge_tolerance_dollars: float | None
    edge_window_s: float | None
    edge_id: str | None
    diagnostics: Mapping[str, Any]

    def tool_metadata(self) -> dict[str, Any]:
        promoted = (
            "source_ms", "current_btc", "current_ema9", "current_ema30",
            "owner_price_gap", "contact_width", "spent_edge",
            "shallow_edge_exception", "current_motion", "slowdown",
            "equal_duration_accelerating", "terminal_evidence_qualified",
            "retreat_threshold", "sample_interval_s", "edge_extreme_ms",
            "arc_origin_ms", "entry_routes", "paired_gap_evidence",
            "ema9_ema30_gap_edge_guard", "parent_structure",
            "shape_comparisons", "current_path_coverage",
            "arc_origin_observed", "reference_history",
            "current_ema9_terminal_window",
            "comparable_slow_edge",
            "scale_progress", "return_leg_reference",
            "primary_collection_terminal_qualified", "primary_collection_evidence",
        )
        return {
            "qualified_alternating_mountain": self.qualified_alternating_mountain,
            "owner_side": (
                self.owner_side.value
                if self.owner_side
                else None
            ),
            "mature_edge": self.mature_edge,
            "edge_window_active": self.edge_window_active,
            "stall": self.stall,
            "hesitation": self.hesitation,
            "failed_reextension": self.failed_reextension,
            "meaningful_retreat": self.meaningful_retreat,
            "strong_active_release": self.strong_active_release,
            "edge_id": self.edge_id,
            "current_arc_id": self.current_arc_id,
            "owner_extreme_btc": self.owner_extreme_btc,
            "edge_tolerance_dollars": self.edge_tolerance_dollars,
            "retreat_dollars": self.retreat_dollars,
            "quality": "REGULAR",
            "detector": "TOOL_RACK_CAUSAL_COMPARABLE_EDGE_V4_CURRENT_TERMINAL",
            **{key: self.diagnostics.get(key) for key in promoted},
            # Large paired/path proofs occur once in each decision frame.
            "diagnostics": {key: value for key, value in self.diagnostics.items()
                            if key not in promoted},
        }


def _coverage(rows: Sequence[Mapping[str, Any]], start_ms: float,
              max_gap_s: float) -> dict[str, Any]:
    times = [float(row["epoch_ms"]) for row in rows]
    gaps = [(b - a) / 1000.0 for a, b in zip(times, times[1:])]
    full_start = bool(times and abs(times[0] - start_ms) < 1e-3)
    continuous = bool(gaps and min(gaps) > 0 and max(gaps) <= max_gap_s)
    return {"observed_from_start": full_start, "source_continuous": continuous,
            "sample_count": len(times), "first_source_ms": times[0] if times else None,
            "last_source_ms": times[-1] if times else None,
            "max_sample_gap_s": max(gaps) if gaps else None,
            "complete_observed_path": full_start and continuous,
            "endpoints_are_actual_observations": True}


def _pair(row: Mapping[str, Any], kind: str) -> dict[str, Any] | None:
    ts, btc, e9, e30 = (_num(row.get(key)) for key in ("epoch_ms", "btc_price", "ema9", "ema30"))
    if None in (ts, btc, e9, e30):
        return None
    return {"kind": kind, "source_ms": ts, "btc": btc, "ema9": e9, "ema30": e30,
            "signed_ema_gap_btc": e9 - e30, "signed_price_gap_btc": btc - e9}


def _episodes(rows: Sequence[Mapping[str, Any]],
              config: MountainGeometryConfig) -> list[ArcEpisode]:
    groups: list[list[Mapping[str, Any]]] = []
    current: list[Mapping[str, Any]] = []
    current_id: str | None = None

    for row in rows:
        arc_id = str(row.get("arc_id") or "").strip()
        direction = _direction(row.get("arc_direction"))
        if not arc_id or direction is None:
            continue
        if current and arc_id != current_id:
            groups.append(current)
            current = []
        current_id = arc_id
        current.append(row)
    if current:
        groups.append(current)

    out: list[ArcEpisode] = []
    source_times = [float(row["epoch_ms"]) for row in rows]
    for group_index, group in enumerate(groups):
        first = group[0]
        last = group[-1]
        arc_id = str(first.get("arc_id") or "")
        direction = _direction(first.get("arc_direction"))
        if not arc_id or direction is None:
            continue

        epoch_values = [
            value
            for value in (_num(row.get("epoch_ms")) for row in group)
            if value is not None
        ]
        if not epoch_values:
            continue

        btc_values = [
            value
            for value in (_num(row.get("btc_price")) for row in group)
            if value is not None
        ]
        ema_values = [
            value
            for value in (_num(row.get("ema9")) for row in group)
            if value is not None
        ]
        if not ema_values:
            continue
        ages = [
            value
            for value in (_num(row.get("arc_age_sec")) for row in group)
            if value is not None
        ]
        amplitudes = [
            value
            for value in (_num(row.get("arc_amplitude")) for row in group)
            if value is not None
        ]
        prominence = [
            value
            for value in (
                _num(row.get("arc_prominence_threshold"))
                for row in group
            )
            if value is not None
        ]

        sign = 1.0 if direction == "UP" else -1.0
        last_epoch_ms = max(epoch_values)
        prominence_threshold = max(prominence or [0.0])
        origins = [_num(row.get("arc_start_ms")) for row in group]
        inferred = [_num(row.get("epoch_ms")) - 1000 * (_num(row.get("arc_age_sec")) or 0)
                    for row in group if _num(row.get("epoch_ms")) is not None]
        origin_ms = next((value for value in origins if value is not None), min(inferred))
        # An algorithm starts observing a live leg at launch/reconnect. That
        # timestamp is not evidence that the physical leg began there.
        origin_observed = first.get("arc_origin_observed") is not False
        if "arc_origin_observed" not in first and first.get("measurement_source"):
            origin_observed = bool(group_index > 0 and origin_ms < min(epoch_values))
        # A reversal is known only at a later actual observation. Use the raw
        # EMA9 turning point, not a label's ending timestamp, as the endpoint.
        start_index = bisect_left(source_times, origin_ms - 1e-3)
        end_index = bisect_right(source_times, last_epoch_ms)
        full_rows = [row for row in rows[start_index:end_index] if _num(row.get("ema9")) is not None]
        extreme_row = max(full_rows, key=lambda row: sign * float(row["ema9"])) if full_rows else last
        completed_known_ms = None
        if group_index + 1 < len(groups):
            following = groups[group_index + 1]
            if _direction(following[0].get("arc_direction")) != direction:
                next_birth = following[0]
                observed_birth_threshold = _num(next_birth.get("arc_birth_prominence_threshold"))
                source_bound_birth = bool(next_birth.get("arc_previous_id") == arc_id
                    and next_birth.get("arc_recognition_basis") in (
                        "OBSERVED_6S_9S_EMA9_AND_PROMINENCE", "OBSERVED_ENVELOPE_HISTORY_ONLY")
                    and observed_birth_threshold is not None and observed_birth_threshold > 0
                    and (_num(next_birth.get("arc_birth_reversal_amount")) or 0) >= observed_birth_threshold)
                completion_threshold = observed_birth_threshold if source_bound_birth else prominence_threshold
                for candidate in following:
                    e9 = _num(candidate.get("ema9"))
                    if e9 is not None and sign * (float(extreme_row["ema9"]) - e9) >= max(completion_threshold, 1e-9):
                        completed_known_ms = _num(candidate.get("epoch_ms"))
                        break
        endpoint_ms = float(extreme_row["epoch_ms"]) if completed_known_ms is not None else last_epoch_ms
        path = tuple(row for row in full_rows if float(row["epoch_ms"]) <= endpoint_ms)
        coverage = _coverage(path, origin_ms, config.native_max_gap_s)
        coverage.update(origin_observed=origin_observed,
                        complete_observed_path=coverage["complete_observed_path"] and origin_observed)
        native_reversal = completed_known_ms is not None
        if completed_known_ms is not None:
            completion_rows = rows[start_index:bisect_right(source_times, completed_known_ms)]
            completion_coverage = _coverage(completion_rows, origin_ms, config.native_max_gap_s)
            native_reversal = bool(path and sign * (float(extreme_row["ema9"]) - float(path[0]["ema9"])) > 0
                and all(_num(row.get("ema9")) is not None
                        and sign * (float(row["ema9"]) - float(extreme_row["ema9"])) <= 1e-9
                        for row in completion_rows))
            coverage.update(completion_known_ms=completed_known_ms,
                completion_source_continuous=completion_coverage["source_continuous"],
                completion_max_sample_gap_s=completion_coverage["max_sample_gap_s"],
                native_extreme_preserved_to_completion=native_reversal,
                complete_observed_path=coverage["complete_observed_path"]
                    and completion_coverage["complete_observed_path"] and native_reversal)
        paired = []
        if completed_known_ms is not None and path:
            selectors = (
                ("EMA9_EXTREME", lambda row: sign * float(row["ema9"])),
                ("PRICE_EXTREME", lambda row: sign * float(row["btc_price"])),
                ("EMA_GAP_EXTREME", lambda row: sign * (float(row["ema9"]) - float(row["ema30"]))),
                ("PRICE_GAP_EXTREME", lambda row: sign * (float(row["btc_price"]) - float(row["ema9"]))),
            )
            valid_pairs = [row for row in path if _pair(row, "") is not None]
            for kind, select in selectors:
                if valid_pairs:
                    paired.append(_pair(max(valid_pairs, key=select), kind))
        out.append(
            ArcEpisode(
                arc_id=arc_id,
                direction=direction,
                start_ms=origin_ms,
                end_ms=endpoint_ms,
                duration_s=max(0.0, (endpoint_ms - origin_ms) / 1000.0),
                max_btc=max(btc_values) if btc_values else None,
                min_btc=min(btc_values) if btc_values else None,
                last_btc=_num(last.get("btc_price")),
                max_ema9=max(ema_values) if ema_values else None,
                min_ema9=min(ema_values) if ema_values else None,
                last_phase=str(last.get("arc_phase") or "").upper(),
                max_age_s=max(ages) if ages else 0.0,
                max_amplitude=max(amplitudes) if amplitudes else 0.0,
                prominence_threshold=prominence_threshold,
                completed_known_ms=completed_known_ms,
                native_reversal_observed=native_reversal,
                path_rows=path,
                coverage=coverage,
                peak_pairs=tuple(paired),
                origin_observed=origin_observed,
            )
        )
    return out


def _native_completed_references(rows: Sequence[Mapping[str, Any]],
                                 config: MountainGeometryConfig) -> list[ArcEpisode]:
    """Completed smaller EMA9 arcs are descriptive history, never missions.

    Backbone §0C explicitly permits these inside a retained sovereign arc.
    Both actual covered 6s/9s EMA9 intervals must confirm a meaningful reversal.
    Only received values are used; the first partial leg and unfinished final
    leg are excluded. No price-child turn or resampled point enters the history.
    """
    valid = [row for row in rows if all(_num(row.get(key)) is not None
             for key in ("epoch_ms", "ema9", "ema30", "btc_price"))]
    times = [float(row["epoch_ms"]) for row in valid]
    breaks = [0]
    for i in range(1, len(valid)):
        broken = (times[i] <= times[i - 1]
            or times[i] - times[i - 1] > config.native_max_gap_s * 1000
            or valid[i].get("connection_epoch") != valid[i - 1].get("connection_epoch"))
        breaks.append(breaks[-1] + int(broken))
    state: dict[str, Any] | None = None
    completed: list[ArcEpisode] = []
    for i, row in enumerate(valid):
        if i and breaks[i] != breaks[i - 1]:
            state = None
        e9 = float(row["ema9"])
        directions = []
        for seconds in (6, 9):
            before = bisect_right(times, times[i] - seconds * 1000, 0, i) - 1
            if before < 0 or breaks[i] != breaks[before]:
                directions.append(None)
                continue
            delta = e9 - float(valid[before]["ema9"])
            directions.append("UP" if delta > 0 else "DOWN" if delta < 0 else None)
        direction = directions[0] if directions[0] == directions[1] else None
        threshold = max(1e-9, _num(row.get("arc_prominence_threshold")) or 5.0)
        if state is None:
            if direction is not None:
                state = {"direction": direction, "start_index": i, "extreme_index": i,
                         "origin_observed": False}
            continue
        sign = 1 if state["direction"] == "UP" else -1
        extreme_index = state["extreme_index"]
        if sign * (e9 - float(valid[extreme_index]["ema9"])) > 0:
            state["extreme_index"] = extreme_index = i
        extreme_e9 = float(valid[extreme_index]["ema9"])
        if direction is None or direction == state["direction"] or sign * (extreme_e9 - e9) < threshold:
            continue
        start_index = state["start_index"]
        path = tuple(valid[start_index:extreme_index + 1])
        completion_rows = valid[start_index:i + 1]
        origin_ms, endpoint_ms = times[start_index], times[extreme_index]
        coverage = _coverage(path, origin_ms, config.native_max_gap_s)
        completion_coverage = _coverage(completion_rows, origin_ms, config.native_max_gap_s)
        height = sign * (extreme_e9 - float(valid[start_index]["ema9"]))
        complete = bool(state["origin_observed"] and height >= threshold
            and coverage["complete_observed_path"] and completion_coverage["complete_observed_path"])
        coverage.update(origin_observed=state["origin_observed"],
            complete_observed_path=complete, completion_known_ms=times[i],
            completion_source_continuous=completion_coverage["source_continuous"],
            completion_max_sample_gap_s=completion_coverage["max_sample_gap_s"],
            native_extreme_preserved_to_completion=True,
            confirmation_windows_s=[6, 9], completion_prominence_dollars=threshold)
        if complete:
            selectors = (
                ("EMA9_EXTREME", lambda item: sign * float(item["ema9"])),
                ("PRICE_EXTREME", lambda item: sign * float(item["btc_price"])),
                ("EMA_GAP_EXTREME", lambda item: sign * (float(item["ema9"]) - float(item["ema30"]))),
                ("PRICE_GAP_EXTREME", lambda item: sign * (float(item["btc_price"]) - float(item["ema9"]))),
            )
            pairs = tuple(_pair(max(path, key=select), kind) for kind, select in selectors)
            completed.append(ArcEpisode(
                arc_id=f"NATIVE:{int(origin_ms)}:{state['direction']}",
                direction=state["direction"], start_ms=origin_ms, end_ms=endpoint_ms,
                duration_s=(endpoint_ms - origin_ms) / 1000,
                max_btc=max(float(item["btc_price"]) for item in path),
                min_btc=min(float(item["btc_price"]) for item in path),
                last_btc=float(path[-1]["btc_price"]),
                max_ema9=max(float(item["ema9"]) for item in path),
                min_ema9=min(float(item["ema9"]) for item in path),
                last_phase="OBSERVED_NATIVE_COMPLETION", max_age_s=(endpoint_ms - origin_ms) / 1000,
                max_amplitude=height, prominence_threshold=threshold,
                completed_known_ms=times[i], native_reversal_observed=True,
                path_rows=path, coverage=coverage, peak_pairs=pairs,
                origin_observed=True, reference_kind="DESCRIPTIVE_NATIVE_EMA9_ARC"))
        # A witnessed approach plus reversal proves the next origin. If the
        # approach itself was a tiny cold fragment, its endpoint stays unknown.
        state = {"direction": direction, "start_index": extreme_index,
                 "extreme_index": i, "origin_observed": height >= threshold}
    return completed


def completed_mountain_references(rows: Sequence[Mapping[str, Any]],
                                  config: MountainGeometryConfig | None = None) -> tuple[ArcEpisode, ...]:
    """Immutable, already-known observations eligible to survive a reconnect."""
    cfg = config or MountainGeometryConfig()
    candidates = _episodes(rows, cfg) + _native_completed_references(rows, cfg) + _comparison_episodes(rows, cfg)
    return tuple(arc for arc in candidates if arc.completed_known_ms is not None
        and arc.native_reversal_observed and arc.origin_observed
        and arc.duration_s > 0 and arc.coverage.get("complete_observed_path") is True)


def _comparison_episodes(rows: Sequence[Mapping[str, Any]],
                         config: MountainGeometryConfig) -> list[ArcEpisode]:
    """Larger received envelopes remain descriptive comparison history only."""
    described = [{**row, **row["comparison_arc"]} for row in rows
                 if isinstance(row.get("comparison_arc"), Mapping)
                 and row["comparison_arc"].get("entry_authority") is False
                 and row["comparison_arc"].get("exit_authority") is False
                 and row["comparison_arc"].get("renews_paid_mission") is False]
    return [replace(arc, reference_kind="OBSERVED_EMA9_ENVELOPE") for arc in _episodes(described, config)]


def _alternates(episodes: Sequence[ArcEpisode]) -> bool:
    recent = list(episodes[-5:])
    if len(recent) < 4:
        return False
    return all(
        recent[i].direction != recent[i - 1].direction
        for i in range(1, len(recent))
    )


def _sample_interval_s(rows: Sequence[Mapping[str, Any]]) -> float:
    values = [
        value
        for value in (_num(row.get("epoch_ms")) for row in rows[-30:])
        if value is not None
    ]
    diffs = [
        (b - a) / 1000.0
        for a, b in zip(values, values[1:])
        if b > a
    ]
    if not diffs:
        return 5.0
    # "One native beat" should follow the current source cadence, not be
    # inflated by a historical gap earlier in the arc. Use the shortest recent
    # positive beat with a conservative upper cap.
    return min(30.0, max(1.0, min(diffs[-10:])))


def _motion(rows: Sequence[Mapping[str, Any]], seconds: float,
            sign: float, config: MountainGeometryConfig) -> dict[str, Any]:
    """Covered actual endpoints; no interpolation or shorter warmup window."""
    if not rows:
        return {"covered": False}
    end_ms = float(rows[-1]["epoch_ms"])
    cutoff = end_ms - seconds * 1000
    index = next((i for i in range(len(rows) - 1, -1, -1)
                  if float(rows[i]["epoch_ms"]) <= cutoff), None)
    if index is None:
        return {"covered": False, "window_s": seconds, "source_ms": end_ms}
    use = rows[index:]
    first, last = use[0], use[-1]
    coverage = _coverage(use, float(first["epoch_ms"]), config.native_max_gap_s)
    elapsed = (end_ms - float(first["epoch_ms"])) / 1000
    out = {**coverage, "covered": coverage["source_continuous"] and elapsed >= seconds,
           "window_s": seconds, "source_ms": end_ms,
           "start_source_ms": float(first["epoch_ms"]), "observed_duration_s": elapsed}
    for key, name in (("btc_price", "price"), ("ema9", "ema9"), ("ema30", "ema30")):
        a, b = _num(first.get(key)), _num(last.get(key))
        out["first_" + name] = a
        out["current_" + name] = b
        out["owner_" + name + "_rate_btc_s"] = sign * (b - a) / elapsed if a is not None and b is not None and elapsed > 0 else None
    first_e9, first_e30 = out.get("first_ema9"), out.get("first_ema30")
    current_e9, current_e30 = out.get("current_ema9"), out.get("current_ema30")
    if None not in (first_e9, first_e30, current_e9, current_e30) and elapsed > 0:
        first_gap = sign * (first_e9 - first_e30)
        current_gap = sign * (current_e9 - current_e30)
        out.update(first_owner_ema_gap_btc=first_gap, current_owner_ema_gap_btc=current_gap,
                   owner_ema_gap_rate_btc_s=(current_gap - first_gap) / elapsed)
    else:
        out.update(first_owner_ema_gap_btc=None, current_owner_ema_gap_btc=None,
                   owner_ema_gap_rate_btc_s=None)
    return out


def _slowdown(motions: Mapping[str, Mapping[str, Any]], range60: float,
              config: MountainGeometryConfig, sign: float) -> dict[str, Any]:
    current = motions[str(int(config.slowdown_window_s))]
    combined = motions[str(int(config.slowdown_window_s * 2))]
    resolution = max(config.sideways_min_btc_per_s,
                     config.sideways_range60_fraction_per_s * range60)
    out: dict[str, Any] = {"observed": None, "sideways_velocity_resolution_btc_s": resolution,
                          "positive_rate_reduction_resolution": config.gap_relative_tolerance}
    if not current.get("covered") or not combined.get("covered"):
        return out
    elapsed = (current["start_source_ms"] - combined["start_source_ms"]) / 1000.0
    rate = current.get("owner_price_rate_btc_s")
    first, prior = current.get("first_price"), combined.get("first_price")
    if elapsed <= 0 or None in (rate, first, prior):
        return out
    prior_rate = sign * (first - prior) / elapsed
    reduction = 1 - rate / prior_rate if prior_rate > 0 else None
    slowed = bool(prior_rate > 0 and rate > 0 and reduction >= config.gap_relative_tolerance)
    out.update(observed=slowed or abs(rate) <= resolution or rate < 0,
               current_owner_price_rate_btc_s=rate, previous_owner_price_rate_btc_s=prior_rate,
               outward_rate_reduction_fraction=reduction, positive_outward_rate_slowing=slowed,
               sideways_observed=abs(rate) <= resolution, owner_price_retreat_observed=rate < 0,
               current_interval=dict(current), previous_start_source_ms=combined["start_source_ms"],
               previous_end_source_ms=current["start_source_ms"], previous_observed_duration_s=elapsed)
    return out


def _shape_comparison(current: ArcEpisode, prior: ArcEpisode,
                      config: MountainGeometryConfig) -> dict[str, Any]:
    """Compare both observed EMA9 paths over the SAME elapsed physical age.

    Five actual source samples describe normalized shape. Their actual times
    and values remain visible; no resampled or interpolated candles are made.
    Size/shape select comparable references, and the duration envelope measures
    maturity. The separate paired-gap route does not require these answers.
    """
    report: dict[str, Any] = {"arc_id": prior.arc_id, "duration_s": prior.duration_s,
        "completion_known_ms": prior.completed_known_ms, "coverage": dict(prior.coverage),
        "shape_comparable": False, "reason": "INCOMPLETE_OBSERVED_PATH"}
    if not current.coverage["complete_observed_path"] or not prior.coverage["complete_observed_path"]:
        return report
    span = min(current.duration_s, prior.duration_s)
    if span <= 0:
        return report
    samples = []
    for fraction in (0, .25, .5, .75, 1):
        c = min(current.path_rows, key=lambda row: abs(float(row["epoch_ms"]) - current.start_ms - fraction * span * 1000))
        p = min(prior.path_rows, key=lambda row: abs(float(row["epoch_ms"]) - prior.start_ms - fraction * span * 1000))
        samples.append({"elapsed_target_s": fraction * span,
                        "current_source_ms": float(c["epoch_ms"]), "prior_source_ms": float(p["epoch_ms"]),
                        "current_ema9": float(c["ema9"]), "prior_ema9": float(p["ema9"])})
    sign = 1 if current.direction == "UP" else -1
    current_height = sign * (samples[-1]["current_ema9"] - samples[0]["current_ema9"])
    prior_height = sign * (samples[-1]["prior_ema9"] - samples[0]["prior_ema9"])
    report.update(equal_age_s=span, actual_samples=samples,
                  current_equal_age_height=current_height, prior_equal_age_height=prior_height)
    if current_height <= 0 or prior_height <= 0:
        report["reason"] = "NO_COMPARABLE_OUTWARD_PATH"
        return report
    height_difference = abs(current_height - prior_height) / prior_height
    distances = [abs(sign * (sample["current_ema9"] - samples[0]["current_ema9"]) / current_height
                     - sign * (sample["prior_ema9"] - samples[0]["prior_ema9"]) / prior_height)
                 for sample in samples]
    distance = mean(distances)
    comparable = (height_difference <= config.height_relative_tolerance
                  and distance <= config.normalized_shape_tolerance)
    report.update(shape_comparable=comparable, height_relative_difference=height_difference,
                  normalized_shape_distance=distance,
                  height_relative_tolerance=config.height_relative_tolerance,
                  normalized_shape_tolerance=config.normalized_shape_tolerance,
                  reason="OBSERVED_EQUAL_AGE_COMPARABLE" if comparable else "OBSERVED_DIFFERENT_SHAPE_OR_SCALE")
    return report


def _paired_gap_evidence(priors: Sequence[ArcEpisode], last: Mapping[str, Any],
                         motions: Mapping[str, Mapping[str, Any]], slowdown: Mapping[str, Any],
                         sign: float, config: MountainGeometryConfig) -> dict[str, Any]:
    current_pair = _pair(last, "CURRENT")
    references = [arc for arc in priors if arc.coverage["complete_observed_path"]
                  and arc.native_reversal_observed and arc.peak_pairs]
    matches = []
    if current_pair:
        gap, price_gap = current_pair["signed_ema_gap_btc"], current_pair["signed_price_gap_btc"]
        for arc in references:
            for pair in arc.peak_pairs:
                pg, ppg = pair["signed_ema_gap_btc"], pair["signed_price_gap_btc"]
                if gap * pg <= 0 or sign * price_gap <= 0 or sign * ppg <= 0:
                    continue
                dg, dp = abs(gap - pg) / abs(pg), abs(price_gap - ppg) / abs(ppg)
                if dg <= config.gap_relative_tolerance and dp <= config.gap_relative_tolerance:
                    matches.append({"arc_id": arc.arc_id, "completion_known_ms": arc.completed_known_ms,
                                    "actual_paired_snapshot": dict(pair), "ema_gap_relative_difference": dg,
                                    "price_gap_relative_difference": dp})
    matches.sort(key=lambda item: (item["actual_paired_snapshot"]["source_ms"], item["completion_known_ms"]), reverse=True)
    selected = matches[0] if matches else None
    steep = None
    if selected and all(motions[str(seconds)].get("covered") for seconds in (6, 30, 60)):
        rates = [motions[str(seconds)].get("owner_ema9_rate_btc_s") for seconds in (6, 30, 60)]
        if all(rate is not None for rate in rates):
            threshold = config.gap_relative_tolerance * sign * selected["actual_paired_snapshot"]["signed_price_gap_btc"]
            steep = all(rate * 60 >= threshold for rate in rates)
    enough = len(references) >= config.minimum_comparable_count
    return {"eligible": bool(enough and selected and slowdown.get("observed") is True and steep is not True),
            "reference_count": len(references), "references": [
                {"arc_id": arc.arc_id, "start_ms": arc.start_ms, "end_ms": arc.end_ms,
                 "reference_kind": arc.reference_kind, "origin_observed": arc.origin_observed,
                 "completion_known_ms": arc.completed_known_ms, "coverage": dict(arc.coverage),
                 "peak_pairs": list(arc.peak_pairs)} for arc in references],
            "matches": matches, "selected_match": selected, "current_pair": current_pair,
            "current_slowdown": dict(slowdown), "steep_observed": steep,
            "gap_relative_tolerance": config.gap_relative_tolerance,
            "steepness_formula": "ALL_CURRENT_6_30_60_EMA9_RATES_TIMES_60_GE_GAP_RESOLUTION_TIMES_MATCHED_OUTWARD_PRICE_GAP",
            "shape_age_height_prerequisites": False,
            "measurement_calibration": "INHERITED_PROVISIONAL_PAPER_NOT_PROFITABILITY_FIT"}


def _previous_same_direction_gap_envelope(
    references: Sequence[ArcEpisode], sign: float, current_gap: float | None,
    motions: Mapping[str, Mapping[str, Any]], config: MountainGeometryConfig,
) -> dict[str, Any]:
    """Current arc cannot be terminal while its EMA9/EMA30 separation is still opening.

    The most recent completed sovereign same-direction arc is the physical
    comparison. A smaller mountain is still a mountain: it may terminate below
    that prior gap once the current separation stops expanding or retreats. The
    prior gap is therefore not a minimum-size requirement; it is only a guard
    against declaring a top/bottom early while the living gap is still opening.
    """
    previous = None
    for arc in reversed(references):
        pairs = [pair for pair in arc.peak_pairs if pair.get("kind") == "EMA_GAP_EXTREME"]
        if not pairs:
            continue
        candidate = max((sign * float(pair["signed_ema_gap_btc"]) for pair in pairs), default=None)
        if candidate is not None and candidate > 0:
            previous = {"arc_id": arc.arc_id, "completion_known_ms": arc.completed_known_ms,
                        "outward_gap_btc": candidate, "source_ms": pairs[0].get("source_ms")}
            break
    short = motions.get(str(int(config.slowdown_window_s)), {})
    rate = _num(short.get("owner_ema_gap_rate_btc_s"))
    expanding = bool(short.get("covered") and rate is not None and rate > 0)
    below_previous = bool(previous is not None and current_gap is not None
                          and current_gap < previous["outward_gap_btc"])
    blocked = bool(expanding and below_previous)
    return {
        "previous_completed_arc": previous,
        "current_outward_gap_btc": current_gap,
        "current_gap_rate_btc_s": rate,
        "current_gap_window_s": config.slowdown_window_s,
        "current_gap_expanding": expanding,
        "current_gap_below_previous_arc": below_previous,
        "terminal_blocked_while_gap_expands_below_previous": blocked,
        "small_mountain_may_terminate_after_expansion_stops": True,
        "ema30_has_trade_authority": False,
    }



def _parent_envelope_state(
    rows: Sequence[Mapping[str, Any]], current: ArcEpisode,
    references: Sequence[ArcEpisode], config: MountainGeometryConfig,
) -> dict[str, Any]:
    """Describe the larger EMA9 envelope that owns child arcs.

    Small/tight Mountains keep their existing edge behavior.  Once the same
    observed parent envelope survives beyond the normal 3–6 minute Mountain
    chapter, a child crest/trough is breathing unless the *parent* shape has
    reached a comparable mature scale and is itself retreating/flattening.
    The parent becomes Slow Rolling after one full 15-minute contract.
    """
    last = rows[-1] if rows else {}
    parent = last.get("comparison_arc") if isinstance(last.get("comparison_arc"), Mapping) else {}
    direction = _direction(parent.get("arc_direction"))
    side = _side(direction)
    age = _num(parent.get("arc_age_sec")) or 0.0
    amplitude = _num(parent.get("arc_amplitude")) or 0.0
    parent_start_ms = _num(parent.get("arc_start_ms"))
    child_arc_ids = {str(row.get("arc_id")) for row in rows
                     if row.get("arc_id") and _num(row.get("epoch_ms")) is not None
                     and (parent_start_ms is None or _num(row.get("epoch_ms")) >= parent_start_ms)}
    child_arc_count = len(child_arc_ids)
    same_as_child = bool(direction is not None and direction == current.direction)
    if direction is None:
        return {
            "available": False, "parent_id": None, "parent_direction": None,
            "parent_side": None, "parent_age_s": 0.0, "parent_amplitude": 0.0,
            "same_direction_as_child": False, "extended_parent": False,
            "slow_rolling_parent": False, "parent_terminal_ready": False,
            "blocks_child_reversal": False, "prior_long_parent_count": 0,
            "child_arc_count": 0, "parent_average_ema9_rate_btc_s": None,
        }

    long_refs = [arc for arc in references
        if arc.reference_kind == "OBSERVED_EMA9_ENVELOPE"
        and arc.direction == direction and arc.duration_s >= config.parent_guard_min_age_s
        and arc.completed_known_ms is not None]
    # One physical envelope should only appear once even if retained across a
    # reconnect/archive merge.
    long_refs = list({(arc.direction, arc.end_ms): arc for arc in long_refs}.values())
    long_refs = sorted(long_refs, key=lambda arc: arc.end_ms)[-config.preferred_comparable_count:]
    ref_duration = median([arc.duration_s for arc in long_refs]) if long_refs else None
    ref_amplitude = median([arc.max_amplitude for arc in long_refs]) if long_refs else None
    age_ratio = age / ref_duration if ref_duration not in (None, 0) else None
    amplitude_ratio = amplitude / ref_amplitude if ref_amplitude not in (None, 0) else None
    ratios = [value for value in (age_ratio, amplitude_ratio) if value is not None]
    shape_progress = max(ratios) if ratios else None

    sign = 1.0 if direction == "UP" else -1.0
    parent_motions = {str(int(seconds)): _motion(rows, seconds, sign, config)
                      for seconds in (6.0, 30.0, 60.0)}
    m30 = parent_motions["30"]
    m60 = parent_motions["60"]
    price_rate = _num(m30.get("owner_price_rate_btc_s"))
    gap_rate = _num(m30.get("owner_ema_gap_rate_btc_s"))
    e9_rate = _num(m30.get("owner_ema9_rate_btc_s"))
    price_rate60 = _num(m60.get("owner_price_rate_btc_s"))
    gap_rate60 = _num(m60.get("owner_ema_gap_rate_btc_s"))
    resolution = max(config.sideways_min_btc_per_s,
                     config.sideways_range60_fraction_per_s * max(1.0, _num(last.get("range60")) or 1.0))
    # Parent terminality is parent-scale.  A six/30-second flat beat cannot
    # declare the parent finished while the 60-second EMA gap is still opening
    # in the owner direction (PID22736 #5).
    parent_turning = bool(
        m30.get("covered") is True and m60.get("covered") is True
        and price_rate is not None and gap_rate is not None
        and price_rate60 is not None and gap_rate60 is not None
        and price_rate <= resolution and gap_rate <= 0
        and price_rate60 <= resolution and gap_rate60 <= 0
    )
    extended = bool(same_as_child and age >= config.parent_guard_min_age_s)
    shape_ready = bool(long_refs and shape_progress is not None
                       and shape_progress >= config.parent_shape_progress_fraction)
    terminal_ready = bool(extended and shape_ready and parent_turning)
    slow = bool(age >= config.slow_rolling_min_age_s and not terminal_ready)
    blocks = bool(extended and not terminal_ready)
    return {
        "available": True,
        "parent_id": parent.get("arc_id"),
        "parent_direction": direction,
        "parent_side": side.value if side else None,
        "parent_phase": parent.get("arc_phase"),
        "parent_age_s": age,
        "parent_amplitude": amplitude,
        "parent_average_ema9_rate_btc_s": amplitude / age if age > 0 else None,
        "child_arc_count": child_arc_count,
        "same_direction_as_child": same_as_child,
        "extended_parent": extended,
        "slow_rolling_parent": slow,
        "parent_terminal_ready": terminal_ready,
        "blocks_child_reversal": blocks,
        "guard_min_age_s": config.parent_guard_min_age_s,
        "slow_rolling_min_age_s": config.slow_rolling_min_age_s,
        "shape_progress_required": config.parent_shape_progress_fraction,
        "shape_progress": shape_progress,
        "age_ratio_to_previous_long_parent": age_ratio,
        "amplitude_ratio_to_previous_long_parent": amplitude_ratio,
        "prior_long_parent_count": len(long_refs),
        "prior_long_parents": [{
            "arc_id": arc.arc_id,
            "duration_s": arc.duration_s,
            "amplitude": arc.max_amplitude,
            "completion_known_ms": arc.completed_known_ms,
        } for arc in long_refs],
        "reference_duration_median_s": ref_duration,
        "reference_amplitude_median": ref_amplitude,
        "parent_turning_or_flat": parent_turning,
        "parent_motion": parent_motions,
        "parent_price_rate_30s_btc_s": price_rate,
        "parent_ema9_rate_30s_btc_s": e9_rate,
        "parent_gap_rate_30s_btc_s": gap_rate,
        "parent_price_rate_60s_btc_s": price_rate60,
        "parent_gap_rate_60s_btc_s": gap_rate60,
        "sideways_velocity_resolution_btc_s": resolution,
        "child_arcs_are_breathing_while_blocked": blocks,
        "ema30_has_directional_trade_authority": False,
    }


def _observed_retest_rejection(
    pairs: Sequence[tuple[float, float]], *, extreme_ms: float | None,
    extreme_btc: float | None, sign: float, retreat_threshold: float,
    edge_tolerance: float, slowdown: Mapping[str, Any],
) -> dict[str, Any]:
    """A current rejection after an actual retreat and same-extreme retest.

    Merely returning toward an old peak is not a failed extension. Distinct
    received observations must show the departure, the retest, and another
    meaningful departure. The final motion must still be rejecting/flat;
    renewed positive advance cannot inherit a stale rejection.
    """
    retreat = retest = None
    if extreme_ms is not None and extreme_btc is not None:
        for timestamp, price in pairs:
            if timestamp <= extreme_ms:
                continue
            distance = sign * (extreme_btc - price)
            if retreat is None:
                if distance >= retreat_threshold:
                    retreat = (timestamp, price)
                continue
            if retest is None and sign * (retreat[1] - price) > 0:
                retreat = (timestamp, price)
            if (timestamp > retreat[0] and distance <= edge_tolerance
                    and sign * (price - retreat[1]) >= retreat_threshold):
                retest = (timestamp, price)
    current = pairs[-1] if pairs else None
    rejected_distance = (sign * (retest[1] - current[1])
        if retest is not None and current is not None and current[0] > retest[0] else None)
    current_rejecting = bool(slowdown.get("owner_price_retreat_observed") is True
                            or slowdown.get("sideways_observed") is True)
    qualified = bool(rejected_distance is not None
                     and rejected_distance >= retreat_threshold and current_rejecting)
    return {"qualified": qualified,
        "extreme_source_ms": extreme_ms, "extreme_btc": extreme_btc,
        "retreat_source_ms": retreat[0] if retreat else None,
        "retreat_btc": retreat[1] if retreat else None,
        "retest_source_ms": retest[0] if retest else None,
        "retest_btc": retest[1] if retest else None,
        "current_source_ms": current[0] if current else None,
        "current_btc": current[1] if current else None,
        "rejection_from_retest_dollars": rejected_distance,
        "meaningful_movement_dollars": retreat_threshold,
        "current_rejecting_or_flat": current_rejecting,
        "endpoints_are_actual_observations": True}


def detect_mountain_geometry(
    rows: Sequence[Mapping[str, Any]],
    config: MountainGeometryConfig | None = None,
    *,
    historical_references: Sequence[ArcEpisode] = (),
) -> MountainGeometryDetection:
    cfg = config or MountainGeometryConfig()
    # Duplicate/nonfinite timestamps cannot manufacture beats or completions.
    clean_rows = []
    last_time = None
    for row in rows:
        ts = _num(row.get("epoch_ms"))
        if ts is not None and (last_time is None or ts > last_time):
            clean_rows.append(row)
            last_time = ts
    rows = clean_rows
    episodes = _episodes(rows, cfg)
    if not episodes:
        return MountainGeometryDetection(
            qualified_alternating_mountain=False,
            owner_side=None,
            current_arc_id=None,
            mature_edge=False,
            edge_window_active=False,
            stall=False,
            hesitation=False,
            failed_reextension=False,
            meaningful_retreat=False,
            strong_active_release=False,
            comparable_duration_mean_s=None,
            comparable_duration_median_s=None,
            comparable_count=0,
            maturity_progress=None,
            edge_age_s=None,
            owner_extreme_btc=None,
            retreat_dollars=None,
            edge_tolerance_dollars=None,
            edge_window_s=None,
            edge_id=None,
            diagnostics={"reason": "NO_ARC_EPISODES"},
        )

    current = episodes[-1]
    owner_side = _side(current.direction)
    current_rows = list(current.path_rows)
    if not current_rows:
        current_rows = [row for row in rows if str(row.get("arc_id") or "") == current.arc_id]
    last = current_rows[-1]
    last_ms = _num(last.get("epoch_ms"))
    last_btc = _num(last.get("btc_price"))
    range60 = max(1.0, _num(last.get("range60")) or 1.0)

    all_references = sorted(
        [*historical_references, *episodes[:-1], *_native_completed_references(rows, cfg),
         *_comparison_episodes(rows, cfg)],
        key=lambda episode: (episode.end_ms, episode.completed_known_ms or float("inf")))
    # Keep one causal eligibility pool across both directions.  Same-direction
    # predecessors feed maturity/shape comparison, while opposite-direction
    # predecessors feed settlement-runway evidence.  PID23072 exposed a subtle
    # starvation bug here: the old ``valid_references`` pool was pre-filtered to
    # the current direction and the later return-leg query asked that same pool
    # for the opposite direction, which can only return zero rows.
    eligible_references = [episode for episode in all_references
        if episode.duration_s > 0
        and episode.completed_known_ms is not None
        and episode.completed_known_ms <= (last_ms or 0.0)
        and episode.origin_observed and episode.native_reversal_observed
        and episode.coverage.get("complete_observed_path") is True]
    valid_references = [episode for episode in eligible_references
        if episode.direction == current.direction]
    # The whole-Mountain shape envelope stays separate from smaller native
    # peak-gap comparison history (§0C). Neither can manufacture paid missions.
    prior_same = [
        episode
        for episode in valid_references
        if episode.reference_kind == "SOVEREIGN_EMA9_ARC"
    ][-cfg.preferred_comparable_count:]
    # Two descriptions of one actual turning point are not two predecessors.
    prior_same = list({(arc.direction, arc.end_ms): arc for arc in prior_same}.values())
    envelope_references = [arc for arc in valid_references
        if arc.reference_kind == "OBSERVED_EMA9_ENVELOPE"][-cfg.preferred_comparable_count:]
    envelope_references = list({(arc.direction, arc.end_ms): arc for arc in envelope_references}.values())
    shape_families = {"CURRENT_NATIVE_ARC": [_shape_comparison(current, prior, cfg) for prior in prior_same],
        "OBSERVED_ENVELOPE": [_shape_comparison(current, prior, cfg) for prior in envelope_references]}
    # Each observed scale supplies its own last-four family. Child arcs cannot
    # evict a larger completed envelope, and one actual turn is never counted
    # twice by mixing the two descriptions into one maturity denominator.
    eligible_shape_families = [name for name, reports in shape_families.items()
                              if sum(item["shape_comparable"] for item in reports) >= cfg.minimum_comparable_count]
    selected_shape_family = max(eligible_shape_families or shape_families,
        key=lambda name: (sum(item["shape_comparable"] for item in shape_families[name]),
                          max((item["completion_known_ms"] for item in shape_families[name]
                               if item["shape_comparable"]), default=0.0)))
    shape_comparisons = shape_families[selected_shape_family]
    durations = [item["duration_s"] for item in shape_comparisons if item["shape_comparable"]]
    comparable_mean = mean(durations) if durations else None
    comparable_median = median(durations) if durations else None
    sign = 1.0 if current.direction == "UP" else -1.0
    horizons = sorted({6.0, 12.0, 30.0, 60.0, cfg.slowdown_window_s, cfg.slowdown_window_s * 2})
    motions = {str(int(seconds)): _motion(rows, seconds, sign, cfg) for seconds in horizons}
    slowdown = _slowdown(motions, range60, cfg, sign)
    parent_structure = _parent_envelope_state(rows, current, all_references, cfg)
    native_distinct = {(arc.direction, arc.end_ms): arc for arc in valid_references
                       if arc.reference_kind == "DESCRIPTIVE_NATIVE_EMA9_ARC"}
    native_references = sorted(native_distinct.values(), key=lambda arc: arc.end_ms)[-cfg.preferred_comparable_count:]
    # The whole-Mountain and smaller native families describe different scale.
    # A cluster of tiny native turns cannot evict every genuine whole-arc peak.
    # Each family independently needs >=2 distinct completed observations. Of
    # the available matches, the most recent actual peak wins BEFORE steepness
    # is considered, so renaming an older family cannot evade current steepness.
    pools = {"WHOLE_MOUNTAIN": prior_same, "DESCRIPTIVE_NATIVE_EMA9": native_references}
    if envelope_references:
        pools["OBSERVED_EMA9_ENVELOPE"] = envelope_references
    reports = {name: _paired_gap_evidence(arcs, last, motions, slowdown, sign, cfg)
               for name, arcs in pools.items()}
    available = [name for name, report in reports.items()
                 if report["reference_count"] >= cfg.minimum_comparable_count and report["selected_match"]]
    if available:
        selected_pool = max(available, key=lambda name: (
            reports[name]["selected_match"]["actual_paired_snapshot"]["source_ms"],
            reports[name]["selected_match"]["completion_known_ms"]))
    else:
        selected_pool = max(reports, key=lambda name: reports[name]["reference_count"])
    paired_references = pools[selected_pool]
    paired_gap = {**reports[selected_pool], "selected_reference_family": selected_pool,
        "reference_family_selection": "MOST_RECENT_ACTUAL_MATCH_BEFORE_STEEPNESS_AMONG_INDEPENDENTLY_SUFFICIENT_FAMILIES",
        "reference_families": {name: {
            "reference_count": report["reference_count"],
            "distinct_physical_turns": [[arc.direction, arc.end_ms] for arc in pools[name]],
            "references": report["references"] if name != selected_pool else "SEE_SELECTED_REFERENCES",
            "matches": report["matches"], "selected_match": report["selected_match"],
            "selected": name == selected_pool,
        } for name, report in reports.items()}}

    current_age = max(
        current.max_age_s,
        (
            (current.end_ms - current.start_ms) / 1000.0
            if current.end_ms >= current.start_ms
            else 0.0
        ),
    )

    progress = (
        current_age / comparable_mean
        if comparable_mean not in (None, 0)
        else None
    )
    # A paired EMA/price-gap resemblance is useful edge evidence, but it must
    # not manufacture a peak while the living arc is still less than halfway
    # through both the duration and amplitude of recent comparable arcs.
    selected_refs = prior_same if selected_shape_family == "CURRENT_NATIVE_ARC" else envelope_references
    selected_by_id = {arc.arc_id: arc for arc in selected_refs}
    comparable_amplitudes = [
        selected_by_id[item["arc_id"]].max_amplitude
        for item in shape_comparisons
        if item.get("shape_comparable") is True
        and item.get("arc_id") in selected_by_id
        and selected_by_id[item["arc_id"]].max_amplitude > 0
    ]
    comparable_amplitude_mean = mean(comparable_amplitudes) if comparable_amplitudes else None
    amplitude_progress = (
        current.max_amplitude / comparable_amplitude_mean
        if comparable_amplitude_mean not in (None, 0) else None
    )
    prehalf_scale_veto = bool(
        len(durations) >= cfg.minimum_comparable_count
        and len(comparable_amplitudes) >= cfg.minimum_comparable_count
        and progress is not None and amplitude_progress is not None
        and progress < 0.50 and amplitude_progress < 0.50
    )
    # Scale is context, not destiny.  The old hard <50% rule correctly caught
    # PID23072 #8 while it was still expanding, but it could also suppress a
    # genuinely smaller/faster Mountain such as #1.  A below-half arc may earn
    # maturity only when actual 30s/60s price motion has reversed and EMA9 has
    # also stopped advancing on 30s.  Paired-gap resemblance alone still cannot
    # manufacture the turn.
    m30, m60 = motions.get("30") or {}, motions.get("60") or {}
    causal_prehalf_turn = bool(
        prehalf_scale_veto
        and m30.get("covered") is True and m60.get("covered") is True
        and (_num(m30.get("owner_price_rate_btc_s")) or 0.0) <= 0
        and (_num(m60.get("owner_price_rate_btc_s")) or 0.0) <= 0
        and (_num(m30.get("owner_ema9_rate_btc_s")) or 0.0) <= 0
    )

    # Recent completed arcs in the *return* direction provide the causal
    # settlement travel evidence.  Use the broader observed EMA9 envelope when
    # at least two such parent-scale references exist; otherwise fall back to
    # sovereign EMA9 arcs during warmup.  TP displacement is BTC-price distance,
    # so compare it with observed BTC excursion rather than EMA9 amplitude.
    return_envelopes = [arc for arc in eligible_references
                        if arc.reference_kind == "OBSERVED_EMA9_ENVELOPE"
                        and arc.direction != current.direction]
    return_sovereign = [arc for arc in eligible_references
                        if arc.reference_kind == "SOVEREIGN_EMA9_ARC"
                        and arc.direction != current.direction]
    return_pool = return_envelopes if len(return_envelopes) >= cfg.minimum_comparable_count else return_sovereign
    return_refs = return_pool[-cfg.preferred_comparable_count:]
    return_refs = list({(arc.direction, arc.end_ms): arc for arc in return_refs}.values())

    return_legs = []
    for arc in return_refs:
        if arc.max_btc is None or arc.min_btc is None or arc.duration_s <= 0:
            continue
        btc_amplitude = max(0.0, float(arc.max_btc) - float(arc.min_btc))
        if btc_amplitude <= 0:
            continue
        return_legs.append({
            "arc_id": arc.arc_id,
            "reference_kind": arc.reference_kind,
            "btc_amplitude_btc": btc_amplitude,
            "duration_s": arc.duration_s,
            "average_btc_speed_btc_s": btc_amplitude / arc.duration_s,
            "completion_known_ms": arc.completed_known_ms,
        })
    return_amps = [leg["btc_amplitude_btc"] for leg in return_legs]
    return_durations = [leg["duration_s"] for leg in return_legs]
    return_speeds = [leg["average_btc_speed_btc_s"] for leg in return_legs]
    return_leg_reference = {
        "count": len(return_legs),
        "median_amplitude_btc": median(return_amps) if return_amps else None,
        "median_duration_s": median(return_durations) if return_durations else None,
        "median_speed_btc_s": median(return_speeds) if return_speeds else None,
        "max_amplitude_btc": max(return_amps) if return_amps else None,
        "max_speed_btc_s": max(return_speeds) if return_speeds else None,
        "min_duration_s": min(return_durations) if return_durations else None,
        "arc_ids": [leg["arc_id"] for leg in return_legs],
        "legs": return_legs,
        "basis": ("LAST_COMPLETED_OPPOSITE_DIRECTION_PARENT_MOUNTAINS"
                  if return_pool is return_envelopes
                  else "LAST_COMPLETED_OPPOSITE_DIRECTION_SOVEREIGN_MOUNTAINS_WARMUP"),
        "capacity_policy": "REQUIRED_TP_DISTANCE_MUST_FIT_DEMONSTRATED_SAME_SCALE_BTC_TRAVEL_AND_PACE",
    }

    phase = str(last.get("arc_phase") or "").upper()
    physical_mature_phase = phase in {
        "MATURE",
        "CREST_FORMING",
        "TROUGH_FORMING",
        "ROLLING",
    }

    mature_by_comparison = bool(
        len(durations) >= cfg.minimum_comparable_count
        and comparable_mean is not None
        and current_age
        >= cfg.protected_middle_fraction * comparable_mean
    )
    # PID16280 #4–12: a 60s phase fallback bypassed a measured 356s leg's
    # protected middle. Missing predecessors are Unknown, never a shorter leg.
    mature_by_phase_fallback = False
    mature_by_paired_gap = bool(paired_gap["eligible"] and (not prehalf_scale_veto or causal_prehalf_turn))
    mature_by_causal_turn = bool(causal_prehalf_turn)
    physically_mature = bool(mature_by_comparison or mature_by_paired_gap or mature_by_causal_turn)

    btc_pairs = [
        (
            _num(row.get("epoch_ms")),
            _num(row.get("btc_price")),
        )
        for row in current_rows
    ]
    btc_pairs = [
        (ts, price)
        for ts, price in btc_pairs
        if ts is not None and price is not None
    ]

    if current.direction == "UP":
        extreme_btc = max((price for _, price in btc_pairs), default=None)
    else:
        extreme_btc = min((price for _, price in btc_pairs), default=None)

    extreme_candidates = [
        (ts, price)
        for ts, price in btc_pairs
        if extreme_btc is not None and price == extreme_btc
    ]
    extreme_ts = (
        # Equal-price retests belong to the existing physical extreme. Only a
        # strict new high/low starts another turn attempt; repeated timestamps
        # at the same price must not mint new opportunities.
        extreme_candidates[0][0]
        if extreme_candidates
        else None
    )

    edge_age_s = (
        max(0.0, (last_ms - extreme_ts) / 1000.0)
        if last_ms is not None and extreme_ts is not None
        else None
    )

    # PID3216 starvation repair: a real parent hover must be able to prove
    # maturity instead of waiting for maturity before stall/hover evidence is
    # even considered.  Reuse the already-audited 30-second causal-turn
    # measurements: the current phase must be physically terminal-like, the
    # short 6/12-second slowdown must be sideways, and both BTC and EMA9 must
    # have stopped advancing in the living parent direction over 30 seconds.
    # This does not permit a still-expanding #8-style arc: positive 30-second
    # BTC or EMA9 owner-rate keeps this route false.
    m30_hover = motions.get("30") or {}
    sample_interval = _sample_interval_s(current_rows)
    causal_hover_maturity = bool(
        physical_mature_phase
        and current.coverage.get("complete_observed_path") is True
        and slowdown.get("observed") is True
        and slowdown.get("sideways_observed") is True
        and m30_hover.get("covered") is True
        and (_num(m30_hover.get("owner_price_rate_btc_s")) or 0.0) <= 0
        and (_num(m30_hover.get("owner_ema9_rate_btc_s")) or 0.0) <= 0
        and edge_age_s is not None
        and edge_age_s >= max(1.0, sample_interval * 0.8)
    )
    effective_physically_mature = bool(physically_mature or causal_hover_maturity)

    edge_tolerance = max(
        2.0,
        cfg.edge_tolerance_range60_fraction * range60,
    )
    retreat_threshold = max(
        cfg.min_retreat_dollars,
        cfg.retreat_range60_fraction * range60,
        0.25 * max(current.prominence_threshold, 0.0),
    )

    if (
        extreme_btc is None
        or last_btc is None
    ):
        retreat = None
    elif current.direction == "UP":
        retreat = max(0.0, extreme_btc - last_btc)
    else:
        retreat = max(0.0, last_btc - extreme_btc)

    if comparable_mean is not None:
        edge_window_s = min(
            cfg.edge_window_max_s,
            max(
                cfg.edge_window_min_s,
                cfg.edge_window_duration_fraction * comparable_mean,
            ),
        )
    else:
        edge_window_s = cfg.edge_window_min_s

    # A mature EMA9 arc may reach its current terminal/retest well after an
    # earlier BTC overshoot. That old absolute price record is still useful
    # for retreat depth and paid-attempt identity, but must not expire a later
    # causally observed EMA9 edge. This independent route requires current
    # slowdown and a recently observed actual EMA9 extreme; it cannot create
    # maturity or renew the mission by changing its clock.
    ema_pairs = [(float(row["epoch_ms"]), value) for row in current_rows
                 if (value := _num(row.get("ema9"))) is not None]
    ema_extreme = (max if sign > 0 else min)((value for _, value in ema_pairs), default=None)
    ema_extreme_ms = next((ts for ts, value in ema_pairs if value == ema_extreme), None)
    ema_edge_age = ((last_ms - ema_extreme_ms) / 1000.0
                    if last_ms is not None and ema_extreme_ms is not None else None)
    current_ema_terminal = bool(mature_by_comparison
        and current.coverage.get("complete_observed_path") is True
        and slowdown.get("observed") is True
        and ema_edge_age is not None and 0 <= ema_edge_age <= edge_window_s)
    edge_window_active = bool(
        effective_physically_mature
        and (mature_by_paired_gap
             or current_ema_terminal
             or edge_age_s is not None and edge_age_s <= edge_window_s)
    )

    stall = bool(
        edge_window_active
        and edge_age_s is not None
        and edge_age_s >= max(1.0, sample_interval * 0.8)
    )

    meaningful_retreat = bool(
        edge_window_active
        and retreat is not None
        and retreat >= retreat_threshold
    )

    after_extreme = [
        (ts, price)
        for ts, price in btc_pairs
        if extreme_ts is not None and ts > extreme_ts
    ]
    failed_reextension = False
    if len(after_extreme) >= 2 and extreme_btc is not None:
        prices = [price for _, price in after_extreme]
        if current.direction == "UP":
            moved_away = min(prices) <= extreme_btc - retreat_threshold
            returned_near = prices[-1] >= extreme_btc - edge_tolerance
            no_new_high = max(prices) <= extreme_btc
            failed_reextension = moved_away and returned_near and no_new_high
        else:
            moved_away = max(prices) >= extreme_btc + retreat_threshold
            returned_near = prices[-1] <= extreme_btc + edge_tolerance
            no_new_low = min(prices) >= extreme_btc
            failed_reextension = moved_away and returned_near and no_new_low

    hesitation = bool(
        edge_window_active
        and physical_mature_phase
        and stall
        and (
            retreat is None
            or retreat < retreat_threshold
        )
    )

    # Slopes are dollar CHANGES, not rates: compare adjacent equal 180s spans.
    # A genuinely exhausted extension can relay before EMA9 finishes curling;
    # an old expanding label cannot veto observed current slowdown indefinitely.
    s3 = _num(last.get("struct_slope3m"))
    s6 = _num(last.get("struct_slope6m"))
    a3 = (s3 or 0.0) * sign
    a6 = (s6 or 0.0) * sign
    previous3 = a6 - a3
    equal_duration_accelerating = bool(s3 is not None and s6 is not None
        and a3 > 0 and previous3 > 0 and a3 >= cfg.expansion_ratio * previous3)
    strong_active_release = bool(
        paired_gap["steep_observed"] is True
        or (
            equal_duration_accelerating
            and slowdown.get("observed") is not True
            and retreat is not None
            and retreat <= edge_tolerance
        )
    )

    e9, e30 = _num(last.get("ema9")), _num(last.get("ema30"))
    current_outward_ema_gap = sign * (e9 - e30) if e9 is not None and e30 is not None else None
    gap_envelope = _previous_same_direction_gap_envelope(
        prior_same, sign, current_outward_ema_gap, motions, cfg)
    price_gap = sign * (last_btc - e9) if last_btc is not None and e9 is not None else None
    contact_width = max(cfg.contact_min_dollars, cfg.contact_range60_fraction * range60)
    peak_row = next((row for row in current_rows if _num(row.get("epoch_ms")) == extreme_ts), {})
    peak_e9 = _num(peak_row.get("ema9"))
    peak_gap = sign * (extreme_btc - peak_e9) if extreme_btc is not None and peak_e9 is not None else None
    # A small genuine edge may originate close to EMA9. Preserve that shallow
    # near-extreme case; it must remain on the outward side and cannot re-buy a
    # large return after its original gap has already been travelled (#15).
    shallow_exception = bool(price_gap is not None and price_gap > 0
        and peak_gap is not None and 0 < peak_gap <= contact_width
        and retreat is not None and retreat <= edge_tolerance)
    spent_edge = bool(price_gap is not None and price_gap <= contact_width and not shallow_exception)

    mature_edge = bool(
        effective_physically_mature
        and edge_window_active
        and extreme_btc is not None
        and not spent_edge
    )

    # A broad peak can keep making tiny new highs/lows while its outward
    # advance has already become sideways. Those new records reset edge_age
    # to zero, so the strict no-new-extreme stall predicate cannot recognize
    # this shape. Use the already observed comparable path and covered current
    # slowdown here; neither EMA direction reversal nor a future candle is
    # required. An ordinary middle or continuing strong release cannot qualify.
    comparable_slow_edge = bool(mature_edge and mature_by_comparison
        and current.coverage.get("complete_observed_path") is True
        and slowdown.get("observed") is True
        and slowdown.get("sideways_observed") is True
        and not strong_active_release)
    # Operator-authorized PID2672 correction: paired-gap similarity is a
    # briefing/prepare signal, never paid terminal evidence by itself.  It may
    # establish where Commander should fish cheaply, but the living arc still
    # needs a current causal turn (hover/stall, hesitation, meaningful retreat,
    # failed re-extension, or the already-audited comparable sideways route).
    # This closes the #4 false-peak path where BTC+EMA9 were still advancing
    # outward while a historical gap match alone pronounced the top.
    paired_gap_prepare_alert = bool(mature_by_paired_gap)
    terminal_entry = bool(mature_edge and not strong_active_release
        and gap_envelope["terminal_blocked_while_gap_expands_below_previous"] is not True
        and parent_structure["blocks_child_reversal"] is not True
        and (stall or hesitation or meaningful_retreat or failed_reextension
             or comparable_slow_edge))
    retest_rejection = _observed_retest_rejection(btc_pairs,
        extreme_ms=extreme_ts, extreme_btc=extreme_btc, sign=sign,
        retreat_threshold=retreat_threshold, edge_tolerance=edge_tolerance,
        slowdown=slowdown)
    # A possible counter-swing can coexist with a living primary leg. A
    # paired-gap match plus relative deceleration (or a brief flat beat) alone
    # is sufficient entry evidence, but does not prove that the primary leg
    # has ended. Collection instead needs current shape/duration maturity at
    # the observed scale, or a meaningful exhausted retest progression.
    # Neither route waits for an EMA9 curl or an absolute elapsed duration.
    comparable_collection = bool(mature_by_comparison and slowdown.get("observed") is True)
    paired_collection = bool(mature_by_paired_gap and retest_rejection["qualified"])
    primary_collection = bool(terminal_entry and (comparable_collection or paired_collection))

    edge_id = (
        f"{current.arc_id}:"
        f"{int(extreme_ts or current.end_ms)}"
        if extreme_btc is not None
        else None
    )

    diagnostics = {
        "phase": phase,
        "current_age_s": current_age,
        "comparable_durations_s": durations,
        "mature_by_comparison": mature_by_comparison,
        "mature_by_phase_fallback": mature_by_phase_fallback,
        "mature_by_paired_gap": mature_by_paired_gap,
        "mature_by_causal_turn": mature_by_causal_turn,
        "mature_by_causal_hover": causal_hover_maturity,
        "effective_physically_mature": effective_physically_mature,
        "comparable_slow_edge": comparable_slow_edge,
        "scale_progress": {
            "duration_ratio_to_comparable_mean": progress,
            "amplitude_ratio_to_comparable_mean": amplitude_progress,
            "current_amplitude_btc": current.max_amplitude,
            "comparable_amplitude_mean_btc": comparable_amplitude_mean,
            "prehalf_scale_veto": prehalf_scale_veto,
            "causal_prehalf_turn": causal_prehalf_turn,
            "hard_floor_fraction": None,
            "basis": "BELOW_HALF_SCALE_REQUIRES_CAUSAL_PRICE_AND_EMA9_TURN_NOT_PAIRED_GAP_ALONE",
        },
        "return_leg_reference": return_leg_reference,
        "source_ms": last_ms,
        "arc_origin_ms": current.start_ms,
        "arc_origin_observed": current.origin_observed,
        "edge_extreme_ms": extreme_ts,
        "current_ema9_terminal_window": {
            "qualified": current_ema_terminal,
            "actual_extreme_ema9": ema_extreme,
            "actual_extreme_source_ms": ema_extreme_ms,
            "age_seconds": ema_edge_age,
            "window_seconds": edge_window_s,
            "current_slowdown_observed": slowdown.get("observed") is True,
            "maturity_source": "COMPARABLE_SHAPE_DURATION",
            "renews_paid_mission": False,
            "price_extreme_identity_preserved": True,
        },
        "current_btc": last_btc, "current_ema9": e9, "current_ema30": e30,
        "owner_price_gap": price_gap, "extreme_owner_price_gap": peak_gap,
        "contact_width": contact_width, "spent_edge": spent_edge,
        "shallow_edge_exception": shallow_exception,
        "current_motion": motions, "slowdown": slowdown,
        "current_owner_180s_advance": a3 if s3 is not None else None,
        "previous_owner_180s_advance": previous3 if s3 is not None and s6 is not None else None,
        "equal_duration_accelerating": equal_duration_accelerating,
        "shape_comparisons": shape_comparisons,
        "completed_same_direction_reference_count": len(prior_same),
        "reference_history": {
            "completed_whole_mountain_count": len(prior_same),
            "completed_peak_gap_reference_count": len(paired_references),
            "selected_peak_reference_family": selected_pool,
            "whole_peak_reference_count": len(prior_same),
            "native_peak_reference_count": len(native_references),
            "descriptive_native_reference_count": sum(
                arc.reference_kind == "DESCRIPTIVE_NATIVE_EMA9_ARC" for arc in paired_references),
            "retained_completed_reference_count": sum(
                arc in historical_references for arc in paired_references),
            "minimum_required": cfg.minimum_comparable_count,
            "no_interpolation_or_gap_stitching": True,
            "descriptive_references_renew_missions": False,
            "shape_reference_selection": "INDEPENDENT_LAST_FOUR_OBSERVED_SCALE_FAMILIES",
            "selected_shape_family": selected_shape_family,
            "shape_family_counts": {name: sum(item["shape_comparable"] for item in reports)
                                    for name, reports in shape_families.items()},
            "envelope_reference_count": len(envelope_references),
            "selected_shape_comparable_count": len(durations),
        },
        "paired_gap_evidence": paired_gap,
        "paired_gap_prepare_alert": paired_gap_prepare_alert,
        "paired_gap_trade_authority": False,
        "ema9_ema30_gap_edge_guard": gap_envelope,
        "parent_structure": parent_structure,
        "current_path_coverage": dict(current.coverage),
        "entry_routes": [name for name, eligible in (
            ("COMPARABLE_SHAPE_DURATION_EDGE", mature_by_comparison),
            ("PAIRED_GAP_PREPARE_ALERT_ONLY", paired_gap_prepare_alert),
            ("COMPARABLE_SHAPE_SIDEWAYS_EDGE", comparable_slow_edge)) if eligible],
        "terminal_evidence_qualified": terminal_entry,
        "primary_collection_terminal_qualified": primary_collection,
        "primary_collection_evidence": {
            "basis": "CURRENT_SCALE_MATURITY_OR_OBSERVED_RETEST_REJECTION_V1",
            "entry_terminal_qualified": terminal_entry,
            "comparable_current_leg_mature": mature_by_comparison,
            "current_slowdown_observed": slowdown.get("observed") is True,
            "current_arc_age_s": current_age,
            "current_path_complete": current.coverage.get("complete_observed_path") is True,
            "paired_gap_only": bool(mature_by_paired_gap and not mature_by_comparison),
            "retest_rejection": retest_rejection,
            "qualification_routes": [name for name, eligible in (
                ("COMPARABLE_CURRENT_LEG_TERMINAL", comparable_collection),
                ("PAIRED_PEAK_RETEST_REJECTION", paired_collection)) if eligible and terminal_entry],
            "tactical_entry_authority_changed": False,
            "ema9_curl_required": False,
            "absolute_minimum_duration_s": None,
        },
        "range60": range60,
        "retreat_threshold": retreat_threshold,
        "sample_interval_s": sample_interval,
        "alternating_recent_arcs": _alternates(episodes),
    }

    return MountainGeometryDetection(
        qualified_alternating_mountain=_alternates(episodes),
        owner_side=owner_side,
        current_arc_id=current.arc_id,
        mature_edge=mature_edge,
        edge_window_active=edge_window_active,
        stall=stall,
        hesitation=hesitation,
        failed_reextension=failed_reextension,
        meaningful_retreat=meaningful_retreat,
        strong_active_release=strong_active_release,
        comparable_duration_mean_s=comparable_mean,
        comparable_duration_median_s=comparable_median,
        comparable_count=len(durations),
        maturity_progress=progress,
        edge_age_s=edge_age_s,
        owner_extreme_btc=extreme_btc,
        retreat_dollars=retreat,
        edge_tolerance_dollars=edge_tolerance,
        edge_window_s=edge_window_s,
        edge_id=edge_id,
        diagnostics=diagnostics,
    )
