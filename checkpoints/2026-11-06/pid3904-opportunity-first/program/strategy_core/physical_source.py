"""Causal physical measurements from a direct BTC feed, independent of R22.

EMA values are produced by the market-data feed. This module measures their
shape; it has no strategy permissions, account, executor, or network client.
Prominence preserves the audited observer's definition. Arc phase compares
adjacent equal-duration EMA9 advances, never a three-minute change with the
overlapping six-minute total.
The 3/6/9-minute dollar changes use the current frozen EMA and actual received
history at that horizon, removing the old first-sample-of-minute endpoint lag.
This is an explicit measurement change, not a bitwise replay of old geometry.

Only received samples are observed. Minute-close seeds can initialize EMAs in
the feed, but are never represented here as invented intraminute arc history.
An arc reversal is recognized from current native EMA9 motion and observed
prominence, with the prior extreme as its physical origin; the slower 180s
change remains trend context. Previously emitted rows are never backdated or
relabelled. A recognized physical arc is not itself an entry or an instruction
to abandon an independently managed living position.
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
from strategy_core.detectors.mountain_geometry import (
    ArcEpisode, MountainGeometryConfig, completed_mountain_references,
    detect_mountain_geometry,
)
from strategy_core.detectors.rail_geometry import detect_rail_geometry
from strategy_core.detectors.release_geometry import build_release_probe
from strategy_core.router import PhysicalEvidence
from strategy_core.recovery import recent_swing_evidence
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


def ema9_ema30_cross_context(rows: Sequence[Mapping[str, Any]], *,
                            max_gap_seconds: float = 15.0) -> dict[str, Any]:
    """Source-observed spine crossings are context, never trade authority.

    A crossing is known at the first received nonzero opposite gap. Exact
    touches retain their actual sample count; no interpolated crossing time is
    invented. A source gap/epoch change clears the transition anchor, so signs
    on opposite sides of missing history cannot manufacture a witnessed cross.
    """
    points: list[dict[str, Any]] = []
    crossings: list[dict[str, Any]] = []
    anchor = previous = None
    segment = 0
    zero_samples = 0
    for row in rows:
        ts, e9, e30 = (_finite(row.get(key)) for key in ("epoch_ms", "ema9", "ema30"))
        if None in (ts, e9, e30):
            anchor = previous = None
            zero_samples = 0
            segment += 1
            continue
        epoch = row.get("connection_epoch")
        if previous is not None and (ts <= previous["source_ms"]
                or ts - previous["source_ms"] > max_gap_seconds * 1000
                or epoch != previous["connection_epoch"]):
            anchor = None
            zero_samples = 0
            segment += 1
        gap = e9 - e30
        side = "YES" if gap > 0 else "NO" if gap < 0 else None
        point = {"source_ms": ts, "ema9": e9, "ema30": e30,
                 "signed_gap_btc": gap, "side": side,
                 "connection_epoch": epoch, "continuity_segment": segment,
                 "arc_id_at_observation": row.get("arc_id")}
        if side is None:
            zero_samples += 1
        else:
            if anchor is not None and side != anchor["side"]:
                crossings.append({"direction": side, "known_source_ms": ts,
                    "before": dict(anchor), "after": dict(point),
                    "zero_gap_samples_between": zero_samples,
                    "continuity_segment": segment, "observed_continuously": True,
                    "interpolated_crossing_time": None})
            anchor = point
            zero_samples = 0
        points.append(point)
        previous = point
    if not points:
        return {"zero_authority": True, "source_ms": None, "observed_at": None,
                "previous_observed_cross_present": False, "recent_crossings": [],
                "history_before_segment": "UNKNOWN"}
    last = points[-1]
    current_segment = last["continuity_segment"]
    current_points = [point for point in points if point["continuity_segment"] == current_segment]
    current_crossings = [cross for cross in crossings if cross["continuity_segment"] == current_segment]
    latest = current_crossings[-1] if current_crossings else None
    previous_cross = current_crossings[-2] if len(current_crossings) >= 2 else None
    origin_ms = _finite(rows[-1].get("arc_start_ms"))
    prior6 = next((point for point in reversed(current_points)
                   if point["source_ms"] <= last["source_ms"] - 6000), None)
    motion = {"covered": prior6 is not None,
              "start_source_ms": prior6["source_ms"] if prior6 else None,
              "end_source_ms": last["source_ms"],
              "actual_elapsed_seconds": (last["source_ms"] - prior6["source_ms"]) / 1000 if prior6 else None,
              "signed_gap_change_btc": last["signed_gap_btc"] - prior6["signed_gap_btc"] if prior6 else None,
              "ema9_change_btc": last["ema9"] - prior6["ema9"] if prior6 else None}
    continued = bool(latest and last["side"] == latest["direction"])
    gap_age_s = ((last["source_ms"] - latest["known_source_ms"]) / 1000.0
                 if continued and latest is not None else None)
    # A cross may have happened BEFORE process startup. Never invent that
    # crossing timestamp, but do preserve actual uninterrupted residence on
    # the current side from the first native sample we really received.
    # A source/epoch break or an EMA spine touch starts a new residence.
    residence = []
    if last["side"] in {"YES", "NO"}:
        for point in reversed(current_points):
            if point["side"] != last["side"]:
                break
            residence.append(point)
    residence_start_ms = residence[-1]["source_ms"] if residence else None
    residence_s = ((last["source_ms"] - residence_start_ms) / 1000.0
                   if residence_start_ms is not None else None)
    # EMA9 gap lifecycle is descriptive context, never trade authority.  The
    # operator distinguishes the fresh post-cross "sprout" from a gap that has
    # survived one or more full 15-minute contracts.  Time alone cannot create
    # an entry or terminate a leg; it only tells Commander how much normal
    # breathing to expect before treating a local wobble as a parent reversal.
    contract_s = 900.0
    if last["side"] is None:
        gap_stage = "TOUCHING_SPINE"
    elif gap_age_s is None:
        gap_stage = "INHERITED_OR_UNOBSERVED_CROSS"
    elif gap_age_s < 0.5 * contract_s:
        gap_stage = "SPROUT"
    elif gap_age_s < contract_s:
        gap_stage = "DEVELOPING"
    elif gap_age_s < 2.0 * contract_s:
        gap_stage = "MATURE"
    else:
        gap_stage = "ROLLING"
    owner_sign = 1.0 if last["side"] == "YES" else -1.0 if last["side"] == "NO" else 0.0
    gap_change_6s = motion.get("signed_gap_change_btc")
    owner_gap_change_6s = (owner_sign * gap_change_6s
                           if owner_sign and gap_change_6s is not None else None)
    gap_lifecycle = {
        "stage": gap_stage,
        "age_seconds_since_observed_cross": gap_age_s,
        "age_contracts": gap_age_s / contract_s if gap_age_s is not None else None,
        "observed_side_residence_seconds": residence_s,
        "observed_side_residence_start_source_ms": residence_start_ms,
        "observed_side_residence_samples": len(residence),
        "observed_side_residence_continuous": bool(residence and len(residence) >= 2),
        "observed_cross_on_current_segment": latest is not None,
        "residence_is_cross_timestamp": False,
        "sprout_boundary_seconds": 0.5 * contract_s,
        "mature_boundary_seconds": contract_s,
        "rolling_boundary_seconds": 2.0 * contract_s,
        "current_side": last["side"],
        "current_abs_gap_btc": abs(last["signed_gap_btc"]),
        "owner_gap_change_6s_btc": owner_gap_change_6s,
        "gap_expanding_6s": owner_gap_change_6s is not None and owner_gap_change_6s > 0,
        "latest_cross_observed_continuously": bool(latest and latest.get("observed_continuously") is True),
        "continued_on_latest_cross_side": continued,
        "classification_only": True,
        "clock_has_trade_authority": False,
    }
    return {"zero_authority": True, "source_ms": last["source_ms"],
        "observed_at": last["source_ms"] / 1000,
        "current_signed_gap_btc": last["signed_gap_btc"], "current_side": last["side"],
        "current_arc_id": rows[-1].get("arc_id"), "current_arc_origin_ms": origin_ms,
        "touching_spine": last["side"] is None,
        "previous_observed_cross_present": previous_cross is not None,
        "latest_observed_cross": latest, "previous_observed_cross": previous_cross,
        "recent_crossings": current_crossings[-4:],
        "observed_cross_count": len(current_crossings),
        "current_leg_cross_count": sum(origin_ms is not None and cross["known_source_ms"] >= origin_ms
                                        for cross in current_crossings),
        "continued_on_latest_cross_side": continued,
        "current_gap_motion_6s": motion,
        "gap_lifecycle": gap_lifecycle,
        "coverage": {"first_source_ms": current_points[0]["source_ms"],
                     "last_source_ms": last["source_ms"], "sample_count": len(current_points),
                     "connection_epoch": last["connection_epoch"],
                     "max_observed_source_gap_seconds": max(
                         ((b["source_ms"] - a["source_ms"]) / 1000
                          for a, b in zip(current_points, current_points[1:])), default=None),
                     "max_allowed_source_gap_seconds": max_gap_seconds},
        "history_before_segment": "UNKNOWN", "cross_alone_renews_mission": False,
        "cross_alone_terminates_owner": False}


@dataclass(frozen=True)
class PhysicalConfig:
    history_seconds: float = 7200.0
    gap_reset_seconds: float = 15.0
    max_source_age_seconds: float = 5.0
    max_future_skew_seconds: float = 2.0
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
    def __init__(self, config: PhysicalConfig | None = None, *,
                 mountain_config: MountainGeometryConfig | None = None) -> None:
        self.config = config or PhysicalConfig.load()
        self._mountain_config = mountain_config or MountainGeometryConfig()
        self._historical_references: tuple[ArcEpisode, ...] = ()
        self.rows: deque[dict[str, Any]] = deque()
        self._ticks: deque[dict[str, Any]] = deque()
        self._minutes: deque[dict[str, Any]] = deque()
        self._last_ts: float | None = None
        self._epoch: Any = None
        self._arc: dict[str, Any] | None = None
        self._arc_serial = 0
        # A slower observed envelope remains a comparison family. It never
        # selects current direction, creates a mission, or manages inventory.
        self._comparison_arc: dict[str, Any] | None = None
        self._comparison_serial = 0
        self._reset_serial = 0
        self.reset_reason = "COLD_START_REAL_OBSERVATIONS_ONLY"

    def _reset(self, reason: str) -> None:
        # A transport reset invalidates present continuity, not a completed
        # historical observation already proved before the gap. Interrupted and
        # cold-origin arcs never enter this bounded archive.
        completed = completed_mountain_references(list(self.rows), self._mountain_config)
        known = {(arc.direction, arc.end_ms, arc.reference_kind): arc
                 for arc in (*self._historical_references, *completed)}
        self._historical_references = tuple(known.values())
        if self._last_ts is not None:
            self.historical_references(self._last_ts)
        self.rows.clear()
        self._ticks.clear()
        self._minutes.clear()
        self._arc = None
        self._comparison_arc = None
        self._reset_serial += 1
        self.reset_reason = reason

    def historical_references(self, now_ts: float) -> tuple[ArcEpisode, ...]:
        cutoff = (now_ts - self.config.history_seconds) * 1000
        eligible = [arc for arc in self._historical_references
                    if arc.completed_known_ms is not None
                    and cutoff <= arc.end_ms <= arc.completed_known_ms <= now_ts * 1000]
        bounded = []
        for direction in ("UP", "DOWN"):
            for kind in ("SOVEREIGN_EMA9_ARC", "DESCRIPTIVE_NATIVE_EMA9_ARC", "OBSERVED_EMA9_ENVELOPE"):
                same = sorted((arc for arc in eligible
                    if arc.direction == direction and arc.reference_kind == kind),
                    key=lambda arc: arc.end_ms)
                bounded.extend(same[-self._mountain_config.preferred_comparable_count:])
        self._historical_references = tuple(sorted(bounded, key=lambda arc: arc.end_ms))
        return self._historical_references

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
        previous3 = a6 - a3
        if a3 < 0 and a6 < 0:
            return "ROLLING"
        if a3 < 0 <= a6 or a3 > 0 and previous3 > 0 and a3 < 0.45 * previous3:
            return "CREST_FORMING" if direction == "UP" else "TROUGH_FORMING"
        if s3 is not None and s6 is not None and a3 > 1.10 * previous3 > 0:
            return "EXPANDING"
        if s3 is not None and s6 is not None and a3 > 0 and previous3 > 0:
            return "MATURE"
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
        native6, native9 = _direction(micro[1]), _direction(micro[2])
        # Current geometry must not wait for the sign of a different, much
        # longer lookback. Both covered native spans must agree; flat/mixed
        # motion retains the observed arc. Prominence below still prevents a
        # quote twitch or tiny EMA hesitation from minting another arc.
        direction_now = native9 if native6 is not None and native6 == native9 else None
        threshold = max(self.config.minimum_arc_prominence_dollars,
                        self.config.arc_prominence_range60_fraction * r60)
        if self._arc is None and direction_now:
            self._arc_serial += 1
            self._arc = {"id": f"G{self._reset_serial:03d}A{self._arc_serial:06d}",
                         "direction": direction_now, "start_ts": ts, "known_ts": ts,
                         "origin_observed": False,
                         "start_e9": tick["e9"],
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
                             "direction": direction_now, "start_ts": arc["extreme_ts"], "known_ts": ts,
                             "origin_observed": abs(arc["extreme_e9"] - arc["start_e9"]) >= threshold,
                             "previous_id": arc["id"],
                             "birth_prominence_threshold": threshold,
                             "birth_reversal_amount": reversal,
                             "start_e9": arc["extreme_e9"], "extreme_e9": tick["e9"], "extreme_ts": ts}
        arc = self._arc or {}
        direction = arc.get("direction", direction_now)
        envelope_direction = _direction(slopes[0] if slopes[0] is not None else micro[-1])
        if self._comparison_arc is None and envelope_direction:
            self._comparison_serial += 1
            self._comparison_arc = {"id": f"E{self._reset_serial:03d}A{self._comparison_serial:06d}",
                "direction": envelope_direction, "start_ts": ts, "known_ts": ts,
                "origin_observed": False, "start_e9": tick["e9"],
                "extreme_e9": tick["e9"], "extreme_ts": ts}
        elif self._comparison_arc is not None:
            comparison = self._comparison_arc
            if (comparison["direction"] == "UP" and tick["e9"] > comparison["extreme_e9"] or
                    comparison["direction"] == "DOWN" and tick["e9"] < comparison["extreme_e9"]):
                comparison["extreme_e9"], comparison["extreme_ts"] = tick["e9"], ts
            retreat = (comparison["extreme_e9"] - tick["e9"]) * (1 if comparison["direction"] == "UP" else -1)
            if envelope_direction and envelope_direction != comparison["direction"] and retreat >= threshold:
                self._comparison_serial += 1
                self._comparison_arc = {"id": f"E{self._reset_serial:03d}A{self._comparison_serial:06d}",
                    "direction": envelope_direction, "start_ts": comparison["extreme_ts"], "known_ts": ts,
                    "origin_observed": abs(comparison["extreme_e9"] - comparison["start_e9"]) >= threshold,
                    "previous_id": comparison["id"], "birth_prominence_threshold": threshold,
                    "birth_reversal_amount": retreat, "start_e9": comparison["extreme_e9"],
                    "extreme_e9": tick["e9"], "extreme_ts": ts}
        comparison = self._comparison_arc or {}
        reference_arc = {"arc_id": comparison.get("id"),
            "arc_direction": comparison.get("direction", "NONE"),
            "arc_phase": self._phase(comparison.get("direction"), *slopes),
            "arc_start_ms": comparison.get("start_ts", ts) * 1000,
            "arc_known_ms": comparison.get("known_ts", ts) * 1000,
            "arc_origin_observed": comparison.get("origin_observed", False),
            "arc_previous_id": comparison.get("previous_id"),
            "arc_birth_prominence_threshold": comparison.get("birth_prominence_threshold"),
            "arc_birth_reversal_amount": comparison.get("birth_reversal_amount"),
            "arc_age_sec": max(0.0, ts - comparison.get("start_ts", ts)),
            "arc_amplitude": abs(comparison.get("extreme_e9", tick["e9"]) - comparison.get("start_e9", tick["e9"])),
            "arc_recognition_basis": "OBSERVED_ENVELOPE_HISTORY_ONLY",
            "entry_authority": False, "exit_authority": False, "renews_paid_mission": False}
        row = {**values, "connection_epoch": epoch, "source_sequence": raw.get("sequence_num"),
               "struct_slope3m": slopes[0], "struct_slope6m": slopes[1], "struct_slope9m": slopes[2],
               "ema30_slope3m": s30, "micro_slope3s": micro[0], "micro_slope6s": micro[1],
               "micro_slope9s": micro[2], "btc_change9": self._delta(self._ticks, 9, "btc", 0.5),
               "btc_change6": self._delta(self._ticks, 6, "btc", 0.5),
               "btc_change30": self._delta(self._ticks, 30, "btc", 0.5),
               "btc_change60": self._delta(self._ticks, 60, "btc", 0.5),
               "ema9_change6": micro[1],
               "ema9_change30": self._delta(self._ticks, 30, "e9", 0.5),
               "ema9_change60": self._delta(self._ticks, 60, "e9", 0.5),
               "range60": r60, "range180": max(1.0, max(r180_values) - min(r180_values)),
               "ema_gap": tick["e9"] - tick["e30"], "arc_id": arc.get("id"),
               "arc_direction": direction or "NONE", "arc_phase": self._phase(direction, *slopes),
               "arc_start_ms": arc.get("start_ts", ts) * 1000.0,
               "arc_origin_observed": arc.get("origin_observed", False),
               "arc_known_ms": arc.get("known_ts", ts) * 1000.0,
               "arc_previous_id": arc.get("previous_id"),
               "arc_birth_prominence_threshold": arc.get("birth_prominence_threshold"),
               "arc_birth_reversal_amount": arc.get("birth_reversal_amount"),
               "arc_start_ema9": arc.get("start_e9"),
               "arc_extreme_ms": arc.get("extreme_ts", ts) * 1000.0,
               "arc_extreme_ema9": arc.get("extreme_e9"),
               "arc_age_sec": max(0.0, ts - arc.get("start_ts", ts)),
               "arc_amplitude": abs(arc.get("extreme_e9", tick["e9"]) - arc.get("start_e9", tick["e9"])),
               "arc_prominence_threshold": threshold,
               "current_native_direction": direction_now or "NONE",
               "arc_recognition_basis": "OBSERVED_6S_9S_EMA9_AND_PROMINENCE",
               "trend_direction_180s": _direction(slopes[0]) or "NONE",
               "comparison_arc": reference_arc,
               "parent_direction": _direction(s30, 0.01) or "NONE",
               "measurement_source": "DIRECT_CAUSAL_BTC_EMA9_V2_NATIVE_CURRENT_LEG",
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
        self.geometry = CausalGeometry(physical_config, mountain_config=self.configs.mountain_detector)
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
        historical_references = self.geometry.historical_references(now_ts)
        mountain = detect_mountain_geometry(rows, self.configs.mountain_detector,
                                           historical_references=historical_references)
        heist = detect_heist_geometry(rows, self.configs.heist_detector)
        previous_heist = self._last_qualified_heist
        if heist.qualified_box:
            self._last_qualified_heist = heist
        release = build_release_probe(rows, heist=self._last_qualified_heist or heist, mountain=mountain)
        last = rows[-1] if rows else None
        age = now_ts - last["epoch_ms"] / 1000 if last else None
        # Exchange/feed timestamps can arrive slightly ahead of the local wall clock
        # because the two clocks are not perfectly synchronized.  Treat a small,
        # bounded negative age as current; only materially future-dated geometry
        # is invalid.  The ordinary stale ceiling remains unchanged.
        current = bool(age is not None
            and -self.geometry.config.max_future_skew_seconds <= age
            and age <= self.geometry.config.max_source_age_seconds)
        # Heist is earned by its own tight repeated box. A parallel EMA30
        # environment may describe that box but cannot veto it as "Rail".
        qualified_heist = heist.qualified_box
        # EMA30/Rail is spine/context only. A living EMA9 Mountain is never
        # suppressed merely because the EMA pair also looks rail-like.
        qualified_mountain = mountain.qualified_alternating_mountain and not qualified_heist
        # Ordinary Mountain does not need the Rail compass.  Parent-scale
        # governance is separate: a >6m parent blocks child counter-relays, and
        # a genuine rail-like launch / >=15m Slow Rolling parent may hand trade
        # authority to Rail only in the same parent direction.
        meaningful_arc = bool(last and mountain.owner_side is not None
            and (last.get("arc_amplitude") or 0) >= (last.get("arc_prominence_threshold") or 5.0))
        parent = mountain.diagnostics.get("parent_structure") or {}
        parent_side = Side(parent["parent_side"]) if parent.get("parent_side") in ("YES", "NO") else None
        # PID20964: a low/wide multi-swing parent that remains close to the
        # spine is not promoted to Rail merely because the EMA pair is
        # parallel.  It owns a WAIT->LEAN->FAKEOUT->RETURN chapter until a
        # genuine box escape/release.  EMA30 remains descriptive only.
        mcfg = self.configs.mountain
        parent_age = parent.get("parent_age_s")
        parent_amp = parent.get("parent_amplitude")
        parent_rate = parent.get("parent_average_ema9_rate_btc_s")
        parent_children = parent.get("child_arc_count")
        current_gap = last.get("ema_gap") if last else None
        if current_gap is None and last:
            e9, e30 = last.get("ema9"), last.get("ema30")
            current_gap = (e9 - e30) if e9 is not None and e30 is not None else None
        low_wide_parent_context = bool(
            isinstance(parent_age, (int, float))
            and isinstance(parent_amp, (int, float))
            and isinstance(parent_rate, (int, float))
            and type(parent_children) is int
            and isinstance(current_gap, (int, float))
            and mcfg.low_wide_min_parent_age_s <= parent_age <= mcfg.low_wide_max_parent_age_s
            and parent.get("slow_rolling_parent") is not True
            and parent_amp <= mcfg.low_wide_max_parent_amplitude_btc
            and parent_rate <= mcfg.low_wide_max_average_ema9_rate_btc_s
            and abs(current_gap) <= mcfg.low_wide_max_abs_ema_gap_btc
            and parent_children >= mcfg.low_wide_min_child_arcs
        )
        rail_geometry_launch = bool(parent_side is not None
            and not low_wide_parent_context
            and rail.side is parent_side and rail.ema_pair_parallel and rail.directional_residence
            and rail.persistence_seconds >= self.configs.rail_detector.early_launch_min_persistence_s
            and rail.gap_maintaining_or_expanding
            and parent.get("parent_terminal_ready") is not True)
        slow_parent_launch = bool(parent_side is not None
            and parent.get("slow_rolling_parent") is True
            and parent.get("parent_terminal_ready") is not True)

        # A genuine escape from an already-qualified parallel Heist is the
        # beginning of a Rail chapter, not one more box fade. The breakout
        # direction comes from the living EMA9 Mountain and the observed box
        # boundary; EMA30/parallelism only describes the environment.
        parallel_release_side = None
        prior = previous_heist if previous_heist is not None else self._last_qualified_heist
        prior_diag = prior.diagnostics if prior is not None else {}
        latest_btc = last.get("btc_price") if last else None
        if (prior is not None and prior.qualified_box
                and prior_diag.get("parallel_emas") is True
                and latest_btc is not None and mountain.owner_side is not None):
            tol = prior.edge_tolerance or 0.0
            if (mountain.owner_side is Side.YES and prior.upper is not None
                    and latest_btc > prior.upper + tol):
                parallel_release_side = Side.YES
            elif (mountain.owner_side is Side.NO and prior.lower is not None
                    and latest_btc < prior.lower - tol):
                parallel_release_side = Side.NO
        parallel_release_rail = parallel_release_side is not None
        rail_launch = rail_geometry_launch or slow_parent_launch or parallel_release_rail
        rail_launch_side = parallel_release_side if parallel_release_rail else parent_side
        rolling = meaningful_arc and not qualified_mountain and not qualified_heist
        compression = (heist.compression_unresolved
                       and not qualified_heist and not qualified_mountain and not rolling)
        evidence = PhysicalEvidence(
            ema9_direction=rail.side, ema30_direction=rail.ema30_side,
            mountain_direction=mountain.owner_side,
            ema_pair_parallel=rail.ema_pair_parallel, directional_residence=rail.directional_residence,
            # EMA30 remains spine/context.  Rail authority is explicit and
            # parent-scale only; the generic persistence field cannot silently
            # promote an ordinary/tight Mountain.
            contracts_persistent=0.0,
            alternating_mountain=qualified_mountain,
            rolling_mountain=rolling,
            qualified_heist=(qualified_heist and not parallel_release_rail), compression_unresolved=compression,
            rail_launch_qualified=rail_launch, rail_launch_side=rail_launch_side if rail_launch else None,
            parent_extended=parent.get("extended_parent") is True,
            parent_slow_rolling=parent.get("slow_rolling_parent") is True,
            parent_terminal_ready=parent.get("parent_terminal_ready") is True)
        metadata = {"source": "DIRECT_BTC_AND_NATIVE_KALSHI", "physical_current": current,
                    "geometry_age_seconds": age, "geometry_rows_used": len(rows),
                    "geometry_max_source_age_seconds": self.geometry.config.max_source_age_seconds,
                    "geometry_max_future_skew_seconds": self.geometry.config.max_future_skew_seconds,
                    "geometry_last_epoch_ms": last["epoch_ms"] if last else None,
                    "geometry_reset_reason": self.geometry.reset_reason,
                    "geometry_continuity_generation": self.geometry._reset_serial,
                    "observed_history_seconds": last["observed_history_seconds"] if last else 0.0,
                    "persistence_seconds": rail.persistence_seconds,
                    "rail_alignment_fraction": rail.persistence_alignment_fraction,
                    "rail_residence_fraction": rail.persistence_residence_fraction,
                    "rail_detector": dict(rail.diagnostics),
                    "current_geometry": dict(last) if last else {},
                    "ema9_ema30_cross_context": ema9_ema30_cross_context(
                        rows, max_gap_seconds=self.geometry.config.gap_reset_seconds),
                    "recovery_swing_terrain": recent_swing_evidence(
                        rows, now_ts=last["epoch_ms"] / 1000 if last else now_ts),
                    "mountain": mountain.tool_metadata(),
                    "heist": {**heist.tool_metadata(),
                              "release_confirmed": parallel_release_rail,
                              "release_side": parallel_release_side.value if parallel_release_side else None},
                    "parallel_release_rail": parallel_release_rail,
                    "parallel_release_side": parallel_release_side.value if parallel_release_side else None,
                    "release_probe": release,
                    "territory_detector_summary": {"rail_established": rail.qualified_rail,
                        "rail_launch_qualified": rail_launch,
                        "rail_geometry_launch": rail_geometry_launch,
                        "low_wide_parent_context": low_wide_parent_context,
                        "slow_parent_launch": slow_parent_launch,
                        "parallel_release_rail": parallel_release_rail,
                        "parallel_release_side": parallel_release_side.value if parallel_release_side else None,
                        "qualified_heist": (qualified_heist and not parallel_release_rail),
                        "qualified_mountain": qualified_mountain,
                        "compression_unresolved": compression},
                    "legacy_strategy_routes_used": False, "r22_process_required": False}
        return DirectPhysicalFrame(evidence, metadata, last, tuple(new_rows), current)
