"""Causal physical measurements from a direct BTC feed, independent of R22.

EMA values are produced by the market-data feed. This module measures their
shape; it has no strategy permissions, account, executor, or network client.
Prominence and arc-phase formulas preserve the audited observer's definitions.
The 3/6/9-minute dollar changes use the current frozen EMA and actual received
history at that horizon, removing the old first-sample-of-minute endpoint lag.
This is an explicit measurement change, not a bitwise replay of old geometry.

Only received samples are observed. Minute-close seeds can initialize EMAs in
the feed, but are never represented here as invented intraminute arc history.
An arc reversal is recognized now, with the prior extreme as its physical
origin; previously emitted rows are never backdated or relabelled.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from strategy_core.config_loader import ToolConfigBundle, load_default_tool_configs
from strategy_core.detectors.heist_geometry import detect_heist_geometry
from strategy_core.detectors.mountain_geometry import detect_mountain_geometry
from strategy_core.detectors.rail_geometry import detect_rail_geometry
from strategy_core.detectors.release_geometry import build_release_probe
from strategy_core.router import PhysicalEvidence
from strategy_core.types import MarketSnapshot, Side


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _direction(value: float | None, epsilon: float = 0.0) -> str | None:
    if value is None or abs(value) <= epsilon:
        return None
    return "UP" if value > 0 else "DOWN"


@dataclass(frozen=True)
class PhysicalConfig:
    history_seconds: float = 7200.0
    gap_reset_seconds: float = 15.0
    max_source_age_seconds: float = 5.0
    minimum_arc_prominence_dollars: float = 5.0
    arc_prominence_range60_fraction: float = 0.12
    minute_horizon_tolerance_seconds: float = 2.0

    @classmethod
    def load(cls, path: Path | None = None) -> "PhysicalConfig":
        path = path or Path(__file__).with_name("config") / "physical.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{key: float(raw[key]) for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class DirectPhysicalFrame:
    evidence: PhysicalEvidence
    metadata: Mapping[str, Any]
    latest_row: Mapping[str, Any] | None
    new_rows: tuple[Mapping[str, Any], ...]
    current: bool


class CausalGeometry:
    def __init__(self, config: PhysicalConfig | None = None) -> None:
        self.config = config or PhysicalConfig.load()
        self.rows: deque[dict[str, Any]] = deque()
        self._ticks: deque[dict[str, Any]] = deque()
        self._minutes: deque[dict[str, Any]] = deque()
        self._last_ts: float | None = None
        self._epoch: Any = None
        self._arc: dict[str, Any] | None = None
        self._arc_serial = 0
        self._reset_serial = 0
        self.reset_reason = "COLD_START_REAL_OBSERVATIONS_ONLY"

    def _reset(self, reason: str) -> None:
        self.rows.clear()
        self._ticks.clear()
        self._minutes.clear()
        self._arc = None
        self._reset_serial += 1
        self.reset_reason = reason

    @staticmethod
    def _delta(history: Sequence[Mapping[str, Any]], seconds: float,
               key: str, tolerance: float = 0.0, now_ts: float | None = None) -> float | None:
        if not history:
            return None
        now = float(history[-1]["ts"]) if now_ts is None else now_ts
        target = now - seconds
        # A requested 3/6/9-minute measurement is not a shorter warmup span.
        if float(history[0]["ts"]) > target + tolerance:
            return None
        prior = min(history, key=lambda row: abs(float(row["ts"]) - target))
        return float(history[-1][key]) - float(prior[key])

    @staticmethod
    def _phase(direction: str | None, s3: float | None,
               s6: float | None, s9: float | None) -> str:
        if direction not in ("UP", "DOWN"):
            return "BASE"
        sign = 1 if direction == "UP" else -1
        a3, a6, a9 = ((value or 0.0) * sign for value in (s3, s6, s9))
        if a3 < 0 and a6 < 0:
            return "ROLLING"
        if a3 < 0 <= a6 or a3 > 0 and a6 > 0 and a3 < 0.45 * max(abs(a6), 1e-9):
            return "CREST_FORMING" if direction == "UP" else "TROUGH_FORMING"
        if a3 > 0 and a6 > 0 and a3 < a6:
            return "MATURE"
        if a3 > a6 > 0:
            return "EXPANDING"
        return "BUILDING" if max(a3, a6, a9) > 0 else "BASE"

    def append(self, raw: Mapping[str, Any]) -> dict[str, Any] | None:
        values = {key: _finite(raw.get(key)) for key in ("epoch_ms", "btc_price", "ema9", "ema30")}
        if any(value is None for value in values.values()):
            return None
        ts = values["epoch_ms"] / 1000.0
        if any(values[key] <= 0 for key in ("btc_price", "ema9", "ema30")):
            return None
        if self._last_ts is not None and ts <= self._last_ts:
            return None
        epoch = raw.get("connection_epoch")
        if self._last_ts is not None:
            if self._epoch is not None and epoch is not None and epoch != self._epoch:
                self._reset("BTC_CONNECTION_EPOCH_CHANGED")
            elif ts - self._last_ts > self.config.gap_reset_seconds:
                self._reset("BTC_OBSERVATION_GAP")
        self._last_ts, self._epoch = ts, epoch
        tick = {"ts": ts, "btc": values["btc_price"], "e9": values["ema9"], "e30": values["ema30"]}
        self._ticks.append(tick)
        while self._ticks and self._ticks[0]["ts"] < ts - 600:
            self._ticks.popleft()
        minute = int(ts // 60)
        if not self._minutes or self._minutes[-1]["minute"] != minute:
            self._minutes.append({**tick, "minute": minute})
        while self._minutes and self._minutes[0]["ts"] < ts - self.config.history_seconds:
            self._minutes.popleft()
        r60_values = [point["btc"] for point in self._ticks if point["ts"] >= ts - 60]
        r180_values = [point["btc"] for point in self._ticks if point["ts"] >= ts - 180]
        r60 = max(1.0, max(r60_values) - min(r60_values))
        tolerance = self.config.minute_horizon_tolerance_seconds
        slopes = [self._delta(self._ticks, seconds, "e9", tolerance, ts) for seconds in (180, 360, 540)]
        s30 = self._delta(self._ticks, 180, "e30", tolerance, ts)
        micro = [self._delta(self._ticks, seconds, "e9", 0.5) for seconds in (3, 6, 9)]
        direction_now = _direction(slopes[0] if slopes[0] is not None else micro[-1])
        threshold = max(self.config.minimum_arc_prominence_dollars,
                        self.config.arc_prominence_range60_fraction * r60)
        if self._arc is None and direction_now:
            self._arc_serial += 1
            self._arc = {"id": f"G{self._reset_serial:03d}A{self._arc_serial:06d}",
                         "direction": direction_now, "start_ts": ts, "start_e9": tick["e9"],
                         "extreme_e9": tick["e9"], "extreme_ts": ts}
        elif self._arc is not None:
            arc = self._arc
            if (arc["direction"] == "UP" and tick["e9"] > arc["extreme_e9"] or
                    arc["direction"] == "DOWN" and tick["e9"] < arc["extreme_e9"]):
                arc["extreme_e9"], arc["extreme_ts"] = tick["e9"], ts
            reversal = (arc["extreme_e9"] - tick["e9"]) * (1 if arc["direction"] == "UP" else -1)
            if direction_now and direction_now != arc["direction"] and reversal >= threshold:
                self._arc_serial += 1
                self._arc = {"id": f"G{self._reset_serial:03d}A{self._arc_serial:06d}",
                             "direction": direction_now, "start_ts": arc["extreme_ts"],
                             "start_e9": arc["extreme_e9"], "extreme_e9": tick["e9"], "extreme_ts": ts}
        arc = self._arc or {}
        direction = arc.get("direction", direction_now)
        row = {**values, "connection_epoch": epoch, "source_sequence": raw.get("sequence_num"),
               "struct_slope3m": slopes[0], "struct_slope6m": slopes[1], "struct_slope9m": slopes[2],
               "ema30_slope3m": s30, "micro_slope3s": micro[0], "micro_slope6s": micro[1],
               "micro_slope9s": micro[2], "btc_change9": self._delta(self._ticks, 9, "btc", 0.5),
               "range60": r60, "range180": max(1.0, max(r180_values) - min(r180_values)),
               "ema_gap": tick["e9"] - tick["e30"], "arc_id": arc.get("id"),
               "arc_direction": direction or "NONE", "arc_phase": self._phase(direction, *slopes),
               "arc_age_sec": max(0.0, ts - arc.get("start_ts", ts)),
               "arc_amplitude": abs(arc.get("extreme_e9", tick["e9"]) - arc.get("start_e9", tick["e9"])),
               "arc_prominence_threshold": threshold,
               "parent_direction": _direction(s30, 0.01) or "NONE",
               "measurement_source": "DIRECT_CAUSAL_BTC_EMA9_V1",
               "observed_history_seconds": ts - self._minutes[0]["ts"],
               "geometry_reset": self.reset_reason}
        self.rows.append(row)
        while self.rows and self.rows[0]["epoch_ms"] < (ts - self.config.history_seconds) * 1000:
            self.rows.popleft()
        return row


class DirectPhysicalSource:
    """Produce the same tool detector inputs without any run-file dependency."""
    def __init__(self, configs: ToolConfigBundle | None = None,
                 physical_config: PhysicalConfig | None = None) -> None:
        self.configs = configs or load_default_tool_configs()
        self.geometry = CausalGeometry(physical_config)
        self._last_qualified_heist = None
        self._reset_seen = 0

    def invalidate(self, reason: str) -> None:
        if self.geometry.rows:
            self.geometry._reset(reason)
        self._last_qualified_heist = None

    def observe(self, raw_rows: Sequence[Mapping[str, Any]], *, now_ts: float) -> DirectPhysicalFrame:
        new_rows = []
        for row in raw_rows:
            added = self.geometry.append(row)
            if added is not None:
                new_rows.append(added)
        if self._reset_seen != self.geometry._reset_serial:
            self._last_qualified_heist = None
            self._reset_seen = self.geometry._reset_serial
        rows = list(self.geometry.rows)
        rail = detect_rail_geometry(rows, self.configs.rail_detector)
        mountain = detect_mountain_geometry(rows, self.configs.mountain_detector)
        heist = detect_heist_geometry(rows, self.configs.heist_detector)
        if heist.qualified_box:
            self._last_qualified_heist = heist
        release = build_release_probe(rows, heist=self._last_qualified_heist or heist, mountain=mountain)
        last = rows[-1] if rows else None
        age = now_ts - last["epoch_ms"] / 1000 if last else None
        current = age is not None and 0 <= age <= self.geometry.config.max_source_age_seconds
        qualified_heist = heist.qualified_box and not rail.qualified_rail
        qualified_mountain = mountain.qualified_alternating_mountain and not rail.qualified_rail and not qualified_heist
        compression = heist.compression_unresolved and not rail.qualified_rail and not qualified_heist and not qualified_mountain
        parent = last.get("parent_direction") if last else None
        rolling = (rail.side is Side.YES and parent == "UP" or rail.side is Side.NO and parent == "DOWN")
        evidence = PhysicalEvidence(
            ema9_direction=rail.side, ema30_direction=rail.ema30_side,
            ema_pair_parallel=rail.ema_pair_parallel, directional_residence=rail.directional_residence,
            contracts_persistent=rail.persistence_seconds / 900.0,
            alternating_mountain=qualified_mountain,
            rolling_mountain=bool(rolling and not qualified_mountain and not qualified_heist),
            qualified_heist=qualified_heist, compression_unresolved=compression)
        metadata = {"source": "DIRECT_BTC_AND_NATIVE_KALSHI", "physical_current": current,
                    "geometry_age_seconds": age, "geometry_rows_used": len(rows),
                    "geometry_last_epoch_ms": last["epoch_ms"] if last else None,
                    "geometry_reset_reason": self.geometry.reset_reason,
                    "geometry_continuity_generation": self.geometry._reset_serial,
                    "observed_history_seconds": last["observed_history_seconds"] if last else 0.0,
                    "persistence_seconds": rail.persistence_seconds,
                    "rail_alignment_fraction": rail.persistence_alignment_fraction,
                    "rail_residence_fraction": rail.persistence_residence_fraction,
                    "rail_detector": dict(rail.diagnostics),
                    "mountain": mountain.tool_metadata(), "heist": heist.tool_metadata(),
                    "release_probe": release,
                    "territory_detector_summary": {"rail_established": rail.qualified_rail,
                        "qualified_heist": qualified_heist, "qualified_mountain": qualified_mountain,
                        "compression_unresolved": compression},
                    "legacy_strategy_routes_used": False, "r22_process_required": False}
        return DirectPhysicalFrame(evidence, metadata, last, tuple(new_rows), current)
