"""Causal evidence for Rail fakeouts and unsupported anomaly candles.

Zero trading authority.  The observations are history-relative: no fixed BTC
stretch or candle multiplier is introduced here. OneCommander may use the
result only through the qualified-fade evidence layer.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Any, Mapping, Sequence

from strategy_core.types import MarketSnapshot, Side


def _map(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _num(v: Any) -> float | None:
    if isinstance(v, bool): return None
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _side(v: Any) -> Side | None:
    if isinstance(v, Side): return v
    t=str(v).upper() if v is not None else ""
    return Side(t) if t in ("YES","NO") else None


def _bar_value(bar: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value=_num(bar.get(key))
        if value is not None: return value
    return None


def build_rail_fakeout_evidence(snapshot: MarketSnapshot,
                                rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    strategy=_map(snapshot.metadata.get("commander_strategy"))
    territory=str(strategy.get("owned_territory") or "")
    side=_side(strategy.get("owned_side"))
    echo=_map(snapshot.metadata.get("leg_echo"))
    if territory not in ("UP_RAIL","DOWN_RAIL") or side is None or len(rows) < 8:
        return {"qualified":False,"execution_authority":False,"reason":"NO_ESTABLISHED_RAIL_HISTORY"}
    try:
        typical=float(echo.get("median_pullback_btc"))
        if not math.isfinite(typical) or typical <= 0: raise ValueError
    except (TypeError, ValueError):
        return {"qualified":False,"execution_authority":False,"reason":"NO_COMPARABLE_PULLBACK_HISTORY"}
    last_ms=_num(rows[-1].get("epoch_ms"))
    if last_ms is None:
        return {"qualified":False,"execution_authority":False,"reason":"NO_CAUSAL_TIME"}
    cutoff=last_ms-450_000.0  # user-approved approximately half-contract Rail evidence horizon
    values=[]
    sign=1.0 if side is Side.YES else -1.0
    for row in rows:
        ts=_num(row.get("epoch_ms")); btc=_num(row.get("btc_price")); ema9=_num(row.get("ema9"))
        if ts is None or btc is None or ema9 is None or ts < cutoff: continue
        values.append((ts, sign*(btc-ema9), btc, ema9))
    if len(values) < 8:
        return {"qualified":False,"execution_authority":False,"reason":"INSUFFICIENT_HALF_CONTRACT_ROWS"}
    # Find the most extreme outward excursion and its pre-existing corridor.
    peak_idx=max(range(len(values)), key=lambda i: values[i][1])
    if peak_idx < 3 or peak_idx >= len(values)-1:
        return {"qualified":False,"execution_authority":False,"reason":"NO_COMPLETED_OUT_OF_CORRIDOR_EXCURSION"}
    prior_max=max(v[1] for v in values[:peak_idx])
    peak=values[peak_idx][1]
    current=values[-1][1]
    retreat=peak-current
    exceeded=peak > prior_max
    returned_inside=current <= prior_max
    qualified=bool(exceeded and returned_inside and retreat >= typical
                   and snapshot.metadata.get("release_in_progress") is not True)
    return {
        "version":"RAIL_FAKEOUT_EVIDENCE_V1","execution_authority":False,
        "qualified":qualified,"failed_to_establish":qualified,
        "rail_side":side.value,"return_side":("NO" if side is Side.YES else "YES"),
        "rail_id":f"{territory}:{strategy.get('active_tool') or ''}",
        "excursion_id":f"RAILX:{int(values[peak_idx][0])}",
        "prior_corridor_extreme_btc_from_ema9":prior_max,
        "outward_excursion_btc_from_ema9":peak,
        "current_btc_from_ema9":current,
        "observed_retreat_btc":retreat,"median_comparable_pullback_btc":typical,
        "reason":"FAILED_OUT_OF_CORRIDOR_EXCURSION" if qualified else "EXCURSION_NOT_YET_FAILED",
    }


def build_anomaly_candle_evidence(snapshot: MarketSnapshot,
                                  candles: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    bars=[b for b in candles if isinstance(b, Mapping)]
    if len(bars) < 7:
        return {"qualified":False,"execution_authority":False,"reason":"INSUFFICIENT_COMPLETED_CANDLE_HISTORY"}
    # Use the penultimate completed candle as the anomaly candidate and the
    # latest completed candle as causal follow-through/failure evidence.
    candidate=bars[-2]; follow=bars[-1]; prior=bars[-7:-2]
    def ohlc(bar):
        return (_bar_value(bar,"open","o"), _bar_value(bar,"high","h"),
                _bar_value(bar,"low","l"), _bar_value(bar,"close","c"))
    co,ch,cl,cc=ohlc(candidate); fo,fh,fl,fc=ohlc(follow)
    prior_ohlc=[ohlc(b) for b in prior]
    if any(v is None for v in (co,ch,cl,cc,fo,fh,fl,fc)) or any(any(v is None for v in row) for row in prior_ohlc):
        return {"qualified":False,"execution_authority":False,"reason":"CANDLE_FIELDS_UNAVAILABLE"}
    crange=ch-cl
    prior_ranges=[h-l for o,h,l,c in prior_ohlc]
    if crange <= 0 or not prior_ranges:
        return {"qualified":False,"execution_authority":False,"reason":"NO_CANDLE_RANGE"}
    out_of_family=crange > max(prior_ranges)
    direction=Side.YES if cc>co else Side.NO if cc<co else None
    if direction is None:
        return {"qualified":False,"execution_authority":False,"reason":"ANOMALY_DIRECTION_UNRESOLVED"}
    prior_lean=abs(prior_ohlc[-1][3]-prior_ohlc[0][0])
    unsupported=prior_lean < crange and snapshot.metadata.get("release_in_progress") is not True
    if direction is Side.YES:
        failed=fh <= ch and fc < cc
        return_side=Side.NO
    else:
        failed=fl >= cl and fc > cc
        return_side=Side.YES
    qualified=bool(out_of_family and unsupported and failed)
    return {
        "version":"ANOMALY_CANDLE_EVIDENCE_V1","execution_authority":False,
        "qualified":qualified,"unsupported_by_prior_release":unsupported,
        "failed_to_extend":failed,"return_side":return_side.value,
        "event_id":f"ANOM:{candidate.get('epoch_ms') or candidate.get('timestamp') or len(bars)}",
        "candle_direction":direction.value,"candle_range_btc":crange,
        "largest_prior_five_range_btc":max(prior_ranges),"prior_five_net_lean_btc":prior_lean,
        "reason":"OUT_OF_FAMILY_CANDLE_FAILED_FOLLOWTHROUGH" if qualified else "NO_QUALIFIED_ANOMALY_FADE",
    }


def build_counter_evidence(snapshot: MarketSnapshot, *, rows=(), historical_candles=()) -> dict[str, Any]:
    return {
        "rail_fakeout_evidence": build_rail_fakeout_evidence(snapshot, rows),
        "anomaly_candle_evidence": build_anomaly_candle_evidence(snapshot, historical_candles),
    }
