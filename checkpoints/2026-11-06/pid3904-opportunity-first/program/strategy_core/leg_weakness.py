"""Causal, parent-scoped weakness episodes from actual price observations.

A pause is counted once. Another episode requires a material new outward
push after observed recovery or renewed advance, not cumulative slow drift.
This module never decides an exit: the consumer must separately prove that
the held parent is spent.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
import math
from typing import Any, Mapping


VERSION = "PARENT_WEAKNESS_EPISODES_V1"


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


class ParentWeaknessTracker:
    """Count independent breaths, not repeated evaluations of one breath.

    ``known_ms`` may be later than an observation when a parent is recognized
    from an already received prefix. All points and events retain both times.
    Neither a candle boundary nor an EMA/quote/contract field has authority.
    """

    def __init__(self, scope_id: str, side: Any, continuity_generation: int, *,
                 min_move: float = 3., slowdown_window_s: float = 6.,
                 context_window_s: float = 30., range_window_s: float = 60.,
                 sideways_min_btc_per_s: float = .15,
                 sideways_range60_fraction_per_s: float = .01,
                 max_gap_s: float = 15., range_move_fraction: float = .12):
        side = getattr(side, "value", side)
        side = {"UP": "YES", "DOWN": "NO", "YES": "YES", "NO": "NO"}.get(side)
        values = (min_move, slowdown_window_s, context_window_s, range_window_s,
                  sideways_min_btc_per_s, sideways_range60_fraction_per_s,
                  max_gap_s, range_move_fraction)
        if (not isinstance(scope_id, str) or not scope_id or side is None
                or type(continuity_generation) is not int or continuity_generation < 0
                or any(_number(v) is None for v in values)
                or min_move <= 0 or slowdown_window_s <= 0
                or context_window_s <= slowdown_window_s or range_window_s <= 0
                or sideways_min_btc_per_s < 0 or sideways_range60_fraction_per_s < 0
                or max_gap_s <= 0 or range_move_fraction < 0):
            raise ValueError("INVALID_PARENT_WEAKNESS_CONFIG")
        self.scope_id, self.side = scope_id, side
        self.continuity_generation = continuity_generation
        self.min_move = float(min_move)
        self.slowdown_window_s = float(slowdown_window_s)
        self.context_window_s = float(context_window_s)
        self.range_window_s = float(range_window_s)
        self.sideways_min_btc_per_s = float(sideways_min_btc_per_s)
        self.sideways_range60_fraction_per_s = float(sideways_range60_fraction_per_s)
        self.max_gap_s, self.range_move_fraction = float(max_gap_s), float(range_move_fraction)
        self._sign = 1 if side == "YES" else -1
        self._points: deque[dict[str, float]] = deque()
        self._events: list[dict[str, Any]] = []
        self._serial = 0
        self._source_ms: float | None = None
        self._known_ms: float | None = None
        self._push_anchor: dict[str, float] | None = None
        self._extreme: dict[str, float] | None = None
        self._active: dict[str, Any] | None = None
        self._last_rearm: dict[str, Any] | None = None
        self._push_observed = False
        self._rearmed = False
        self._continuous = True
        self._last_gap: dict[str, float] | None = None

    def snapshot(self) -> dict[str, Any]:
        return deepcopy({"version": VERSION, "scope_id": self.scope_id,
            "side": self.side, "continuity_generation": self.continuity_generation,
            "source_ms": self._source_ms, "known_ms": self._known_ms,
            "count": len(self._events), "required_count": 3,
            "third_observed": len(self._events) >= 3, "events": self._events,
            "active_episode": self._active, "rearmed": self._rearmed,
            "continuous": self._continuous, "last_rearm": self._last_rearm,
            "last_gap": self._last_gap})

    def _range(self, source: float) -> float:
        prices = [p["btc"] for p in self._points
                  if p["source_ms"] >= source - self.range_window_s * 1000.]
        return max(prices) - min(prices) if prices else 0.

    def _slowdown(self, source: float, observed_range: float) -> dict[str, Any]:
        recent_cutoff = source - self.slowdown_window_s * 1000.
        context_cutoff = source - self.context_window_s * 1000.
        recent = next((p for p in reversed(self._points)
                       if p["source_ms"] <= recent_cutoff), None)
        previous = next((p for p in reversed(self._points)
                         if p["source_ms"] <= context_cutoff), None)
        resolution = max(self.sideways_min_btc_per_s,
                         self.sideways_range60_fraction_per_s * observed_range)
        result: dict[str, Any] = {"covered": False, "qualified": False,
            "sideways_velocity_resolution_btc_s": resolution}
        if recent is None or previous is None or recent["source_ms"] <= previous["source_ms"]:
            return result
        current = self._points[-1]
        current_dt = (source - recent["source_ms"]) / 1000.
        prior_dt = (recent["source_ms"] - previous["source_ms"]) / 1000.
        rate = self._sign * (current["btc"] - recent["btc"]) / current_dt
        prior_rate = self._sign * (recent["btc"] - previous["btc"]) / prior_dt
        # The preceding push must actually have been advancing faster than
        # the sideways resolution, entirely after the preceding rearm. A
        # window containing the old push cannot describe a new weakness.
        after_rearm = (self._last_rearm is None
                       or previous["source_ms"] >= self._last_rearm["source_ms"])
        result.update(covered=True, qualified=bool(after_rearm and prior_rate > resolution
            and rate <= resolution and rate < prior_rate),
            current_owner_rate_btc_s=rate, previous_owner_rate_btc_s=prior_rate,
            current_start=deepcopy(recent), previous_start=deepcopy(previous),
            current_end=deepcopy(current), current_duration_s=current_dt,
            previous_duration_s=prior_dt, after_material_rearm=after_rearm)
        return result

    def observe(self, row: Mapping[str, Any], known_ms: Any = None) -> dict[str, Any]:
        if not isinstance(row, Mapping):
            return self.snapshot()
        source, price = _number(row.get("epoch_ms")), _number(row.get("btc_price"))
        known = _number(source if known_ms is None else known_ms)
        if (source is None or source < 0 or price is None or price <= 0
                or known is None or known < source
                or self._source_ms is not None and source <= self._source_ms
                or self._known_ms is not None and known < self._known_ms):
            return self.snapshot()

        if self._source_ms is not None and source - self._source_ms > self.max_gap_s * 1000.:
            self._last_gap = {"from_source_ms": self._source_ms, "to_source_ms": source,
                              "observed_gap_s": (source - self._source_ms) / 1000.}
            self._points.clear()
            self._events.clear()
            self._push_anchor = self._extreme = self._active = self._last_rearm = None
            self._push_observed = self._rearmed = self._continuous = False

        self._source_ms, self._known_ms = source, known
        point = {"source_ms": source, "known_ms": known, "btc": price}
        self._points.append(point)
        cutoff = source - max(self.context_window_s, self.range_window_s) * 1000.
        # Keep one actual endpoint preceding the requested window; do not
        # interpolate the absent boundary or silently shorten the window.
        while len(self._points) > 1 and self._points[1]["source_ms"] <= cutoff:
            self._points.popleft()
        observed_range = self._range(source)
        tolerance = max(self.min_move, self.range_move_fraction * observed_range)
        if self._push_anchor is None:
            self._push_anchor = self._extreme = point
            return self.snapshot()
        if not self._push_observed and self._sign * (price - self._push_anchor["btc"]) < 0:
            self._push_anchor = self._extreme = point
        if self._sign * (price - self._extreme["btc"]) > 0:
            self._extreme = point
        excursion = self._sign * (self._extreme["btc"] - self._push_anchor["btc"])
        if excursion >= tolerance:
            self._push_observed = True
            self._continuous = True
            if self._active is None:
                self._rearmed = True

        if self._active is not None:
            recovery = self._active["recovery_anchor"]
            if self._sign * (price - recovery["btc"]) < 0:
                self._active["recovery_anchor"] = deepcopy(point)
            prior_extreme = self._active["outward_extreme"]
            retreat = self._sign * (prior_extreme["btc"] - price)
            if self._active["meaningful_pullback"] is None and retreat >= tolerance:
                self._active["meaningful_pullback"] = {
                    "source_ms": source, "known_ms": known,
                    "outward_extreme": deepcopy(prior_extreme),
                    "retreat_anchor": deepcopy(point),
                    "retreat_btc": retreat, "move_tolerance": tolerance}
            motion = self._slowdown(source, observed_range)
            frozen_resolution = self._active["weakness_velocity_resolution_btc_s"]
            renewed_advance = bool(motion["covered"]
                and motion["current_start"]["source_ms"] >= self._active["source_ms"]
                and motion["current_owner_rate_btc_s"] > frozen_resolution)
            pullback_recovered = bool(self._active["meaningful_pullback"]
                and source > self._active["meaningful_pullback"]["source_ms"])
            # Slow creep can accumulate several dollars while the dynamic
            # range/resolution contracts. It is still the same weak patch.
            # Freeze its original velocity resolution until a new push is
            # actually observed, or witness an actual pullback and recovery.
            if (self._sign * (price - prior_extreme["btc"]) >= tolerance
                    and (pullback_recovered or renewed_advance)):
                self._push_anchor = deepcopy(self._active["recovery_anchor"])
                self._last_rearm = {"source_ms": source, "known_ms": known,
                    "previous_event_id": self._active["event_id"],
                    "recovery_anchor": deepcopy(self._push_anchor),
                    "previous_outward_extreme": deepcopy(prior_extreme),
                    "renewed_push_endpoint": deepcopy(point), "move_tolerance": tolerance,
                    "basis": "OBSERVED_PULLBACK_RECOVERY" if pullback_recovered
                             else "OBSERVED_RENEWED_ADVANCE",
                    "meaningful_pullback": deepcopy(self._active["meaningful_pullback"]),
                    "frozen_weakness_velocity_resolution_btc_s": frozen_resolution,
                    "renewed_advance_motion": deepcopy(motion) if renewed_advance else None}
                self._active = None
                self._rearmed = True
            # A recovery cannot also count as another weakness on the same
            # observation, even if an older covered window remains slow.
            return self.snapshot()

        if not self._push_observed:
            return self.snapshot()
        retreat = self._sign * (self._extreme["btc"] - price)
        motion = self._slowdown(source, observed_range)
        trigger = ("MEANINGFUL_PULLBACK" if retreat >= tolerance else
                   "COVERED_SLOWDOWN" if motion["qualified"] else None)
        if trigger is None:
            return self.snapshot()
        self._serial += 1
        event = {"id": f"{self.scope_id}:W{self._serial}", "scope_id": self.scope_id,
            "side": self.side, "continuity_generation": self.continuity_generation,
            "source_ms": source, "known_ms": known, "trigger": trigger,
            "push_anchor": deepcopy(self._push_anchor),
            "outward_extreme": deepcopy(self._extreme), "recovery_anchor": deepcopy(point),
            "move_tolerance": tolerance, "observed_range_btc": observed_range,
            "outward_push_btc": excursion, "retreat_btc": retreat,
            "motion": motion, "rearm_evidence": deepcopy(self._last_rearm)}
        self._events.append(event)
        self._active = {"event_id": event["id"], "source_ms": source, "known_ms": known,
            "outward_extreme": deepcopy(self._extreme), "recovery_anchor": deepcopy(point),
            "weakness_velocity_resolution_btc_s": motion["sideways_velocity_resolution_btc_s"],
            "meaningful_pullback": {"source_ms": source, "known_ms": known,
                "outward_extreme": deepcopy(self._extreme), "retreat_anchor": deepcopy(point),
                "retreat_btc": retreat, "move_tolerance": tolerance}
                if retreat >= tolerance else None}
        self._rearmed = False
        return self.snapshot()
