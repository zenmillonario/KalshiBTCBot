"""Completed-minute comparison history for observed full parent legs.

Bars stay bars. Their closes and EMA values are never inserted into the live
intraminute path. A bounded, first-known archive preserves completed historical
legs across moving history windows and transport resets. Its envelope is a
separate physical comparison route, not a claim about a future reversal.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def parent_return_timing_snapshot(parent: Mapping[str, Any], *, source_ms: float,
        path: Sequence[Mapping[str, Any]], received_references: Sequence[Mapping[str, Any]],
        minute_references: Sequence[Mapping[str, Any]], minimum_count: int,
        preferred_count: int, max_gap_seconds: float) -> dict[str, Any]:
    """Freeze known completed timings at one actually observed activation.

    This record is descriptive holding evidence. It creates no entry, end,
    weakness or elapsed-time permission. The caller stores it once, including
    an unavailable result; later history cannot enrich an earlier decision.
    Different sampling resolutions remain independent families.
    """
    side = parent.get("side")
    direction = {"YES": "UP", "NO": "DOWN"}.get(side)
    origin = _number(parent.get("origin_ms"))
    generation = parent.get("continuity_generation")
    source = _number(source_ms)
    scope_valid = bool(source is not None and origin is not None and 0 < origin <= source
        and parent.get("status") == "ACTIVE" and parent.get("id")
        and parent.get("source_ms") == source and direction is not None
        and type(generation) is int and generation >= 0)
    times = [_number(row.get("epoch_ms")) for row in path]
    valid_times = bool(times and all(value is not None for value in times))
    gaps = [(b - a) / 1000. for a, b in zip(times, times[1:])] if valid_times else []
    from_start = bool(valid_times and origin is not None and abs(times[0] - origin) <= 1e-3)
    contiguous = bool(gaps and min(gaps) > 0 and max(gaps) <= max_gap_seconds)
    complete = bool(scope_valid and parent.get("origin_observed") is True
        and from_start and contiguous and times[-1] == source)

    def family(records: Sequence[Mapping[str, Any]], name: str) -> dict[str, Any]:
        distinct = {}
        for record in records:
            start, end, known, duration = (_number(record.get(key)) for key in
                ("origin_ms", "end_ms", "completed_known_ms", "duration_seconds"))
            covered = (record.get("complete_observed_path") is True if name == "received_parent"
                       else record.get("complete_minute_coverage") is True
                       and record.get("resolution_seconds") == 60.)
            completion_source = _number(record.get("completion_source_ms"))
            if (not scope_valid or not record.get("id") or record.get("direction") != direction
                    or record.get("side", side) != side or record.get("origin_observed") is not True
                    or not covered or None in (start, end, known, duration)
                    or not 0 < start < end <= known <= source or duration <= 0
                    or name == "completed_minute_parent" and (completion_source is None
                        or not end <= completion_source <= known)
                    or abs(duration - (end - start) / 1000.) > 1e-6):
                continue
            summary = {"id": str(record["id"]), "side": side, "direction": direction,
                "origin_ms": start, "end_ms": end, "duration_seconds": duration,
                "completed_known_ms": known, "origin_observed": True}
            if name == "received_parent":
                summary.update(complete_observed_path=True,
                    max_source_gap_seconds=record.get("max_source_gap_seconds"),
                    resolution="ACTUAL_RECEIVED_OBSERVATIONS")
            else:
                summary.update(complete_minute_coverage=True, resolution_seconds=60.,
                    completion_source_ms=completion_source,
                    intraminute_path_claimed=False)
            # Two labels for the same observed turn are not two references.
            distinct[(direction, end)] = summary
        selected = sorted(distinct.values(), key=lambda item: (item["end_ms"], item["completed_known_ms"]))[-preferred_count:]
        return {"family": "RECEIVED_COMPLETED_PARENT" if name == "received_parent" else "COMPLETED_MINUTE_PARENT",
            "reference_count": len(selected), "minimum_count": minimum_count,
            "enough_references": len(selected) >= minimum_count, "references": selected}

    families = {"received_parent": family(received_references, "received_parent"),
                "completed_minute_parent": family(minute_references, "completed_minute_parent")}
    selected_family = next((key for key in ("received_parent", "completed_minute_parent")
                            if families[key]["enough_references"]), None)
    return {"version": "PARENT_RETURN_TIMING_REFERENCE_V1", "parent_id": parent.get("id"),
        "side": side, "continuity_generation": generation, "origin_ms": origin,
        "origin_observed": parent.get("origin_observed") is True,
        "bind_source_ms": source, "bind_kind": "ACTIVE_OBSERVED_PARENT",
        "current_path_complete": complete,
        "current_path_coverage": {"observed_from_start": from_start,
            "source_continuous": contiguous, "sample_count": len(times),
            "first_source_ms": times[0] if valid_times else None,
            "last_source_ms": times[-1] if valid_times else None,
            "max_sample_gap_s": max(gaps) if gaps else None},
        "minimum_count": minimum_count, "families": families,
        "selected_family": selected_family,
        "selection_reason": "ELIGIBLE_RECEIVED_PARENT_FAMILY" if selected_family == "received_parent"
            else "RECEIVED_FAMILY_INSUFFICIENT_USE_SEPARATE_COMPLETED_MINUTES"
            if selected_family == "completed_minute_parent" else "NO_SUFFICIENT_COMPLETED_TIMING_FAMILY",
        "qualified": complete and selected_family is not None,
        "frozen_at_first_active_observation": True, "later_enrichment_allowed": False,
        "entry_authority": False, "terminal_authority": False, "weakness_authority": False}


class CompletedBarParentReferences:
    """Actual minute-close EMA envelopes with explicit completion knowledge."""
    def __init__(self, *, history_seconds: float = 7200., prominence_dollars: float = 5.) -> None:
        if (not math.isfinite(history_seconds) or history_seconds <= 0
                or not math.isfinite(prominence_dollars) or prominence_dollars <= 0):
            raise ValueError("INVALID_COMPLETED_PARENT_REFERENCE_CONFIGURATION")
        self.history_seconds = float(history_seconds)
        # Same physical minimum prominence as the direct observer, not a
        # fitted candle count or a new trade-admission price threshold.
        self.prominence_dollars = float(prominence_dollars)
        self._bars: dict[float, dict[str, Any]] = {}
        self._signature: tuple | None = None
        self._cache_key: tuple | None = None
        self._cache: tuple[dict[str, Any], ...] = ()
        self._active_cache: dict[str, Any] | None = None

    def ingest(self, candles: Sequence[Mapping[str, Any]], *, now_ms: float) -> None:
        # The producer can re-send the same immutable as-of history on every
        # native quote. First-known records do not acquire later revised EMAs.
        if _number(now_ms) is None:
            return
        cutoff = now_ms - self.history_seconds * 1000
        eligible = []
        for raw in candles:
            if not isinstance(raw, Mapping):
                continue
            ts, known, close, e9, e30 = (_number(raw.get(k)) for k in
                                        ("time", "known_at", "close", "e9", "e30"))
            if (None in (ts, known, close, e9, e30) or ts % 60
                    or raw.get("complete") is not True or raw.get("full_minute") is not True
                    or min(close, e9, e30) <= 0 or known < ts + 60
                    or max(known, ts + 60) * 1000 > now_ms
                    or (ts + 60) * 1000 < cutoff):
                continue
            eligible.append((ts, known, close, e9, e30, raw))
        # Cache only presently admissible records. A future-known record in
        # an otherwise identical supplied list can become admissible later.
        signature = tuple(row[:5] for row in eligible)
        expired = [key for key, row in self._bars.items() if row["source_ms"] < cutoff]
        if signature == self._signature:
            for key in expired:
                del self._bars[key]
            if expired:
                self._cache_key = None
            return
        self._signature = signature
        changed = False
        for ts, known, close, e9, e30, raw in eligible:
            if ts in self._bars:
                continue
            self._bars[ts] = {"time": ts, "source_ms": (ts + 60) * 1000,
                "known_ms": known * 1000, "btc_close": close, "ema9": e9, "ema30": e30,
                "source": raw.get("source"), "quality": raw.get("quality"),
                "resolution_seconds": 60., "intraminute_path_claimed": False}
            changed = True
        for key in expired:
            del self._bars[key]
        if changed or expired:
            self._cache_key = None

    def completed(self, source_ms: float) -> tuple[dict[str, Any], ...]:
        points = [row for _, row in sorted(self._bars.items())
                  if row["known_ms"] <= source_ms and row["source_ms"] <= source_ms
                  and row["source_ms"] >= source_ms - self.history_seconds * 1000]
        key = tuple((r["source_ms"], r["known_ms"]) for r in points)
        if key == self._cache_key:
            return self._cache
        state = None
        previous = None
        legs: list[dict[str, Any]] = []
        segment: list[dict[str, Any]] = []
        for row in points:
            if previous is not None and row["source_ms"] - previous["source_ms"] != 60_000:
                state = None
                segment = []
            segment.append(row)
            if state is None:
                if len(segment) >= 2 and row["ema9"] != segment[0]["ema9"]:
                    sign = 1 if row["ema9"] > segment[0]["ema9"] else -1
                    state = {"sign": sign, "origin": segment[0], "extreme": row,
                             "origin_observed": False}
                previous = row
                continue
            sign = state["sign"]
            extreme = state["extreme"]
            if sign * (row["ema9"] - extreme["ema9"]) >= 0:
                if sign * (row["ema9"] - extreme["ema9"]) > 0:
                    state["extreme"] = row
                previous = row
                continue
            # A single tiny opposite close does not create a full leg. The
            # observed three-minute EMA displacement and existing physical
            # prominence must agree on the completed reversal.
            coarse = row["ema9"] - segment[-4]["ema9"] if len(segment) >= 4 else None
            if (sign * (extreme["ema9"] - row["ema9"]) < self.prominence_dollars
                    or coarse is None or sign * coarse >= 0):
                previous = row
                continue
            origin = state["origin"]
            path = [p for p in segment if origin["source_ms"] <= p["source_ms"] <= extreme["source_ms"]]
            height = sign * (extreme["ema9"] - origin["ema9"])
            if state["origin_observed"] and height >= self.prominence_dollars and len(path) >= 2:
                prices = [p["btc_close"] for p in path]
                legs.append({"id": f"MINUTE_PARENT:{int(origin['source_ms'])}:{int(extreme['source_ms'])}",
                    "family": "COMPLETED_MINUTE_PARENT", "direction": "UP" if sign > 0 else "DOWN",
                    "origin_ms": origin["source_ms"], "end_ms": extreme["source_ms"],
                    "completed_known_ms": max(p["known_ms"] for p in segment
                                               if origin["source_ms"] <= p["source_ms"] <= row["source_ms"]),
                    "completion_source_ms": row["source_ms"],
                    "duration_seconds": (extreme["source_ms"] - origin["source_ms"]) / 1000,
                    "ema9_excursion": height, "observed_close_range": max(prices) - min(prices),
                    "origin": dict(origin), "extreme": dict(extreme), "completion": dict(row),
                    "bar_count": len(path), "resolution_seconds": 60.,
                    "complete_minute_coverage": True, "origin_observed": True,
                    "intraminute_path_claimed": False})
            state = {"sign": -sign, "origin": extreme, "extreme": row, "origin_observed": True}
            previous = row
        active = None
        if state is not None and state["origin_observed"]:
            origin, extreme = state["origin"], state["extreme"]
            path = [p for p in segment if origin["source_ms"] <= p["source_ms"]]
            if len(path) >= 2:
                sign = state["sign"]
                prices = [p["btc_close"] for p in path]
                price_extreme = min(path, key=lambda p: sign * -p["btc_close"])
                active = {"id": f"MINUTE_ACTIVE:{int(origin['source_ms'])}:{sign}",
                    "family": "ACTIVE_COMPLETED_MINUTE_PARENT", "direction": "UP" if sign > 0 else "DOWN",
                    "origin_ms": origin["source_ms"], "origin_ema9": origin["ema9"],
                    "origin_btc": origin["btc_close"], "origin_observed_at_minute_resolution": True,
                    "ema9_extreme": extreme["ema9"], "ema9_extreme_source_ms": extreme["source_ms"],
                    "extreme_btc": price_extreme["btc_close"], "extreme_source_ms": price_extreme["source_ms"],
                    "observed_min_btc": min(prices), "observed_max_btc": max(prices),
                    "last_completed_source_ms": path[-1]["source_ms"],
                    "known_ms": max(p["known_ms"] for p in path),
                    "bar_count": len(path), "complete_minute_coverage": True,
                    "resolution_seconds": 60., "intraminute_path_claimed": False,
                    "origin": dict(origin), "last_completed": dict(path[-1])}
        self._active_cache = active
        self._cache_key, self._cache = key, tuple(legs)
        return self._cache

    def active(self, source_ms: float) -> dict[str, Any] | None:
        """Known, still-active minute leg; no inferred received path."""
        self.completed(source_ms)
        return dict(self._active_cache) if self._active_cache else None

    def envelope(self, *, source_ms: float, direction: str, minimum_count: int,
                 preferred_count: int) -> dict[str, Any]:
        records = [leg for leg in self.completed(source_ms) if leg["direction"] == direction]
        records = records[-preferred_count:]
        summaries = [{k: record[k] for k in (
            "id", "direction", "origin_ms", "end_ms", "completed_known_ms",
            "completion_source_ms", "duration_seconds", "ema9_excursion", "observed_close_range",
            "bar_count", "resolution_seconds", "complete_minute_coverage", "origin_observed")}
            for record in records]
        # Keep all dimensions on one actual broad leg. Independent maxima can
        # construct a duration/height/range combination that never occurred.
        # The longest recent full leg also prevents a short internal return
        # from replacing the broader terrain merely because it finished last.
        scale_reference = max(summaries, key=lambda record:
            (record["duration_seconds"], record["end_ms"], record["id"]), default=None)
        return {"family": "COMPLETED_MINUTE_PARENT", "reference_count": len(records),
                "minimum_required": minimum_count, "enough_references": len(records) >= minimum_count,
                "references": summaries, "resolution_seconds": 60.,
                "scale_reference": dict(scale_reference) if scale_reference else None,
                "scale_reference_selection": "LONGEST_ACTUAL_RECENT_COMPLETED_FULL_LEG",
                "maximum_history_age_seconds": self.history_seconds,
                "independent_axis_maxima_are_entry_thresholds": False,
                "duration_upper_seconds": max((r["duration_seconds"] for r in records), default=None),
                "ema9_extension_upper": max((r["ema9_excursion"] for r in records), default=None),
                "close_range_upper": max((r["observed_close_range"] for r in records), default=None),
                "source_ms": source_ms, "intraminute_path_claimed": False,
                "knowledge_rule": "FIRST_KNOWN_COMPLETED_MINUTE_RECORDS_ONLY"}
