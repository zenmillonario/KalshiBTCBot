from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Mapping, Sequence

from strategy_core.types import Side


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
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
    mature_phase_fallback_min_age_s: float = 60.0


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
        return {
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
            "quality": "REGULAR",
            "detector": "TOOL_RACK_RAW_EMA9_ARC_EDGE_V1",
            "diagnostics": dict(self.diagnostics),
        }


def _episodes(rows: Sequence[Mapping[str, Any]]) -> list[ArcEpisode]:
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
    for group in groups:
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

        out.append(
            ArcEpisode(
                arc_id=arc_id,
                direction=direction,
                start_ms=min(epoch_values),
                end_ms=max(epoch_values),
                duration_s=max(
                    (
                        max(epoch_values) - min(epoch_values)
                    ) / 1000.0,
                    max(ages) if ages else 0.0,
                ),
                max_btc=max(btc_values) if btc_values else None,
                min_btc=min(btc_values) if btc_values else None,
                last_btc=_num(last.get("btc_price")),
                max_ema9=max(ema_values) if ema_values else None,
                min_ema9=min(ema_values) if ema_values else None,
                last_phase=str(last.get("arc_phase") or "").upper(),
                max_age_s=max(ages) if ages else 0.0,
                max_amplitude=max(amplitudes) if amplitudes else 0.0,
                prominence_threshold=max(prominence) if prominence else 0.0,
            )
        )
    return out


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
    return median(diffs) if diffs else 5.0


def detect_mountain_geometry(
    rows: Sequence[Mapping[str, Any]],
    config: MountainGeometryConfig | None = None,
) -> MountainGeometryDetection:
    cfg = config or MountainGeometryConfig()
    episodes = _episodes(rows)
    if not episodes:
        return MountainGeometryDetection(
            False, None, None, False, False, False, False, False,
            False, False, None, None, 0, None, None, None, None,
            None, None, None, None, {"reason": "NO_ARC_EPISODES"},
        )

    current = episodes[-1]
    owner_side = _side(current.direction)
    current_rows = [
        row
        for row in rows
        if str(row.get("arc_id") or "").strip() == current.arc_id
    ]
    last = current_rows[-1]
    last_ms = _num(last.get("epoch_ms"))
    last_btc = _num(last.get("btc_price"))
    range60 = max(1.0, _num(last.get("range60")) or 1.0)

    prior_same = [
        episode
        for episode in episodes[:-1]
        if episode.direction == current.direction
        and episode.duration_s > 0
    ][-cfg.preferred_comparable_count:]
    durations = [episode.duration_s for episode in prior_same]
    comparable_mean = mean(durations) if durations else None
    comparable_median = median(durations) if durations else None

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
    mature_by_phase_fallback = bool(
        len(durations) < cfg.minimum_comparable_count
        and physical_mature_phase
        and current_age >= cfg.mature_phase_fallback_min_age_s
        and current.max_amplitude >= max(
            current.prominence_threshold,
            0.0,
        )
    )
    physically_mature = mature_by_comparison or mature_by_phase_fallback

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
        extreme_candidates[-1][0]
        if extreme_candidates
        else None
    )

    edge_age_s = (
        max(0.0, (last_ms - extreme_ts) / 1000.0)
        if last_ms is not None and extreme_ts is not None
        else None
    )

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

    edge_window_active = bool(
        physically_mature
        and edge_age_s is not None
        and edge_age_s <= edge_window_s
    )

    sample_interval = _sample_interval_s(current_rows)
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

    # EXPANDING is the original geometry observer's physical "still extending"
    # phase. BUILDING with short slope outrunning medium slope is also treated
    # as active release/extension rather than an edge to fade.
    s3 = _num(last.get("struct_slope3m"))
    s6 = _num(last.get("struct_slope6m"))
    sign = 1.0 if current.direction == "UP" else -1.0
    a3 = (s3 or 0.0) * sign
    a6 = (s6 or 0.0) * sign
    strong_active_release = bool(
        phase == "EXPANDING"
        or (
            phase == "BUILDING"
            and a3 > 0
            and a6 > 0
            and a3 >= 1.10 * max(a6, 1e-9)
            and retreat is not None
            and retreat <= edge_tolerance
        )
    )

    mature_edge = bool(
        physically_mature
        and edge_window_active
        and extreme_btc is not None
    )

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
