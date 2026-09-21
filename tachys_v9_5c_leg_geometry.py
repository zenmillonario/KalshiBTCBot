"""
TACHYOS V9.5C — LEG GEOMETRY / DUAL-SIDE AUTHORITY / WHOLE-LEG EXIT GATE
=======================================================================

PAPER ONLY.

Canonical doctrine:
- EMA30 is the spine.
- EMA9 return slope + transfer + opposite-side build are one continuous leg.
- YES and NO are evaluated every tactical cycle.
- Parent is context, not tactical candidate selection.
- Mature old-side continuation is disarmed when a credible return slope begins.
- Target Height + Time Capacity + Rollover Continuity are part of the leg.
- Failed target breaks/reclaims can disarm the wrong side and re-arm the other.
- V9.5A Active Treasury is proposal-only.
- Every non-emergency exit passes one Whole-Leg Exit Authority gate.
"""

from __future__ import annotations

import asyncio
import csv
import math
import os
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import tachys_v9_5b_level2_intermission_thesis_shield as b

rs2 = b.rs2
r = b.r
a = b.a
m = b.m
k = b.k
j = b.j
core = b.core

VERSION = "V9.5C"
ET = m.ET
_START_TS = time.time()
RUN_ID = datetime.now(ET).strftime("C%Y%m%d_%H%M%S")
SESSION_ID = f"{RUN_ID}_PID{os.getpid()}"

os.environ["TACHYOS_V95C_RUN_ID"] = RUN_ID
os.environ["TACHYOS_V95C_SESSION_ID"] = SESSION_ID

RETURN_CONFIRM_SEC = 3.0
FAST_ENTRY_CONFIRM_SEC = 1.0
STANDARD_ENTRY_CONFIRM_SEC = 3.0
EXPIRY_ENTRY_CONFIRM_SEC = 0.5
ARM_TTL_SEC = 18.0

ENTRY_ARM_SCORE = 6
FAST_ENTRY_SCORE = 9
STANDARD_ENTRY_SCORE = 7
EXPIRY_ENTRY_SCORE = 7
ENTRY_MIN_LEAD = 2

ENTRY_MIN_ASK = 0.18
ENTRY_MAX_ASK = 0.82
EXPIRY_MAX_ASK = 0.88
MAX_REPRICE_ABS = 0.09
MAX_REPRICE_PCT = 0.25
MAX_V95C_ENTRIES_PER_SIDE_CONTRACT = 3

ROLLOVER_PREARM_SEC = 30.0
TARGET_FAKEOUT_WINDOW_SEC = 30.0
TARGET_ACCEPT_HOLD_SEC = 6.0

DEFAULT_LEG_DURATION_SEC = 90.0
MIN_LEG_DURATION_SEC = 30.0
MAX_LEG_DURATION_SEC = 240.0
LEG_HISTORY_MAX = 18

WHOLE_LEG_OPPOSITE_EXIT_SCORE = 7
WHOLE_LEG_OPPOSITE_EXIT_CONFIRM_SEC = 3.0
TERMINAL_TARGET_SEC = 60.0
EMERGENCY_HARD_ROI = -0.60

LEG_LOG = "tachys_leg_geometry_v9_5c.csv"
TACTICAL_LOG = "tachys_dual_side_authority_v9_5c.csv"
EXIT_LOG = "tachys_whole_leg_exit_authority_v9_5c.csv"
ROLLOVER_LOG = "tachys_rollover_continuity_v9_5c.csv"
MANIFEST_LOG = "tachys_run_manifest_v9_5c.csv"

LEG_FIELDS = [
    "timestamp","run_id","session_id","event","ticker","leg_id","leg_side","leg_state",
    "leg_age_sec","origin_side","regeneration_state","btc_price","target_price","target_height",
    "seconds_left","ema9","ema30","ema_gap","ema9_slope3","ema9_slope6","ema9_slope9",
    "ema9_curvature","ema30_slope6","ema30_slope30","gap_delta3","gap_delta6","gap_delta9",
    "current_amplitude","peak_amplitude","prior_leg_amplitude","transfer_ts",
    "estimated_leg_seconds_remaining","time_capacity_ratio","time_capacity_state",
    "rollover_state","inherited_leg_id","next_target","wick_rejection",
    "target_event","target_hold_sec","note"
]

TACTICAL_FIELDS = [
    "timestamp","run_id","session_id","event","ticker","side","other_side","ask","state",
    "arm_ts","arm_age_sec","arm_ask","score","other_score","score_lead","reasons","blocks",
    "parent_side","leg_id","leg_side","leg_state","regeneration_state","target_height",
    "target_event","seconds_left","time_capacity_state","rollover_state","prearmed_side",
    "btc_change3","btc_change6","btc_change9","btc_change30","btc_change60",
    "trend_eff60","volume_ratio","wick_rejection","legacy_strategy","decision","note"
]

EXIT_FIELDS = [
    "timestamp","run_id","session_id","event","trade_id","ticker","side","entry_ask",
    "current_bid","roi","mfe_roi","proposed_exit_reason","gate_ruling","final_action",
    "leg_id","leg_side","leg_state","regeneration_state","target_height","target_event",
    "target_hold_sec","seconds_left","estimated_leg_seconds_remaining","time_capacity_ratio",
    "time_capacity_state","yes_score","no_score","opposite_score","wick_rejection","note"
]

ROLLOVER_FIELDS = [
    "timestamp","run_id","session_id","event","from_ticker","to_ticker","leg_id","leg_side",
    "leg_state","leg_age_sec","target_height_old","next_target","prearmed_side",
    "time_capacity_state","estimated_leg_seconds_remaining","note"
]

MANIFEST_FIELDS = [
    "timestamp","run_id","session_id","version","base_version","paper_authority",
    "start_local","pid","dual_side","leg_geometry","target_height","time_capacity",
    "rollover_continuity","active_treasury","exit_authority","note"
]


def _utc(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else float(ts)
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _local(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else float(ts)
    return datetime.fromtimestamp(ts, ET).isoformat()


def _f(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if v is None or v == "":
            return default
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _i(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def _write(path: str, fields: List[str], row: Dict[str, Any]) -> None:
    payload = {
        "timestamp": row.get("timestamp", _utc()),
        "run_id": RUN_ID,
        "session_id": SESSION_ID,
        **row,
    }
    new_file = (not os.path.exists(path)) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new_file:
            w.writeheader()
        w.writerow({k: payload.get(k, "") for k in fields})


def _opposite(side: str) -> str:
    return "NO" if side == "YES" else "YES" if side == "NO" else "NONE"


def _sign_for_side(side: str) -> int:
    return 1 if side == "YES" else -1 if side == "NO" else 0


def _side_from_signed(v: Optional[float]) -> str:
    if v is None:
        return "NONE"
    return "YES" if v > 0 else "NO" if v < 0 else "NONE"


def _ask_for(side: str, yes_ask, no_ask) -> Optional[float]:
    return _f(yes_ask if side == "YES" else no_ask if side == "NO" else None)


def _bid_for(side: str, yes_ask, no_ask) -> Optional[float]:
    try:
        return a._side_bid(side, yes_ask, no_ask)
    except Exception:
        if side == "YES" and no_ask is not None:
            return 1.0 - float(no_ask)
        if side == "NO" and yes_ask is not None:
            return 1.0 - float(yes_ask)
        return None


def _target_price() -> Optional[float]:
    try:
        return _f(core.parse_target_price(core.active_target))
    except Exception:
        return _f(getattr(core, "v94b_active_target_value", None))


def _history_nearest(seconds_ago: float, now: float) -> Optional[Dict[str, Any]]:
    hist = list(getattr(core, "v91_history", []) or [])
    if not hist:
        return None
    target = now - seconds_ago
    try:
        return min(hist, key=lambda x: abs(float(x.get("ts", now)) - target))
    except Exception:
        return None


def _delta(prev: Optional[Dict[str, Any]], cur: float, key: str) -> Optional[float]:
    if not prev:
        return None
    p = _f(prev.get(key))
    return None if p is None else cur - p


def _safe_median(vals: List[float], default: float) -> float:
    vals = [float(x) for x in vals if x is not None and math.isfinite(float(x))]
    return statistics.median(vals) if vals else default


class LegGeometryAuthority:
    def __init__(self) -> None:
        self.leg_counter = 0
        self.active_leg: Optional[Dict[str, Any]] = None
        self.completed_legs: List[Dict[str, Any]] = []
        self.return_candidate: Optional[Dict[str, Any]] = None
        self.regen_candidate: Optional[Dict[str, Any]] = None
        self.last_ticker: Optional[str] = None
        self.last_target_side: Optional[str] = None
        self.last_target_cross_ts: Optional[float] = None
        self.target_hold_since: Optional[float] = None
        self.prearm: Optional[Dict[str, Any]] = None
        self.arms: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.entry_count: Dict[Tuple[str, str], int] = {}
        self.last_scores: Dict[str, int] = {"YES": 0, "NO": 0}
        self.last_score_reasons: Dict[str, List[str]] = {"YES": [], "NO": []}
        self.last_context: Dict[str, Any] = {}
        self.last_leg_emit_sig: Optional[Tuple[Any, ...]] = None
        self.last_leg_emit_ts: float = 0.0
        self.last_tactical_emit: Dict[str, Tuple[Any, ...]] = {}
        self.last_tactical_emit_ts: Dict[str, float] = {}
        self._write_manifest()

    def _write_manifest(self) -> None:
        _write(MANIFEST_LOG, MANIFEST_FIELDS, {
            "version": VERSION,
            "base_version": "V9.5B archive -> V9.5A/RS1/RS2 control stack",
            "paper_authority": "LEG_GEOMETRY_DUAL_SIDE_AND_WHOLE_LEG_EXIT",
            "start_local": _local(_START_TS),
            "pid": os.getpid(),
            "dual_side": 1,
            "leg_geometry": 1,
            "target_height": 1,
            "time_capacity": 1,
            "rollover_continuity": 1,
            "active_treasury": "PROPOSAL_ONLY",
            "exit_authority": "CENTRAL_WHOLE_LEG_GATE",
            "note": "EMA30=Spine; EMA9 return+transfer+build=one leg.",
        })

    def _snapshot(self, ticker: str, yes_ask=None, no_ask=None, close_ts=None, now=None) -> Dict[str, Any]:
        now = time.time() if now is None else float(now)
        try:
            s = dict(m.brain.snapshot(ticker, yes_ask, no_ask, close_ts, now) or {})
        except Exception:
            s = dict(getattr(j.brain, "last_snapshot", {}) or {})
        s["ticker"] = ticker
        s["now"] = now
        return s

    def _parent_side(self, snap: Dict[str, Any]) -> str:
        for v in (snap.get("boss_side"), snap.get("hand_side")):
            side = str(v or "").upper()
            if side in ("YES", "NO"):
                return side
        reg = getattr(core, "v94e_latest_regime", {}) or {}
        side = str(reg.get("authority_side") or "").upper()
        return side if side in ("YES", "NO") else "NONE"

    def _structural(self) -> Dict[str, Any]:
        return dict(getattr(core, "v94b_latest_structural_snap", {}) or {})

    def _formation(self, now: float) -> Dict[str, Any]:
        try:
            return dict(core._v94d_current_formation_context(now) or {})
        except Exception:
            return {}

    def _seconds_left(self, close_ts, snap: Dict[str, Any], now: float) -> Optional[float]:
        if isinstance(close_ts, (int, float)):
            return max(0.0, float(close_ts) - now)
        return _f(snap.get("seconds_left"))

    def _btc_metrics(self, now: float) -> Dict[str, Any]:
        def change(sec):
            try:
                return _f(core.btc_change(sec, now), 0.0) or 0.0
            except TypeError:
                return _f(core.btc_change(sec), 0.0) or 0.0
            except Exception:
                return 0.0

        def rng(sec):
            try:
                return _f(core.btc_range(sec, now), 1.0) or 1.0
            except TypeError:
                return _f(core.btc_range(sec), 1.0) or 1.0
            except Exception:
                return 1.0

        try:
            eff60 = _f(core.btc_trend_efficiency(60, 5, now))
        except TypeError:
            try:
                eff60 = _f(core.btc_trend_efficiency(60, 5))
            except Exception:
                eff60 = None
        except Exception:
            eff60 = None

        try:
            vol = _f(core.recent_volume_ratio(5))
        except Exception:
            vol = None

        return {
            "ch3": change(3), "ch6": change(6), "ch9": change(9),
            "ch30": change(30), "ch60": change(60),
            "r60": max(1.0, rng(60)), "eff60": eff60, "vol": vol,
        }

    def _wick_rejection(self) -> str:
        candles = list(getattr(core, "btc_completed_candles", []) or [])[-3:]
        upper = lower = 0
        for c in candles:
            o = _f(c.get("open")); h = _f(c.get("high"))
            l = _f(c.get("low")); cl = _f(c.get("close"))
            if None in (o, h, l, cl):
                continue
            width = max(1e-9, h-l)
            if (h-max(o,cl))/width >= 0.30:
                upper += 1
            if (min(o,cl)-l)/width >= 0.30:
                lower += 1
        if upper >= 2 and upper > lower:
            return "UPPER_REJECTION"
        if lower >= 2 and lower > upper:
            return "LOWER_REJECTION"
        if upper and lower:
            return "MIXED_WICKS"
        if upper:
            return "UPPER_WICK"
        if lower:
            return "LOWER_WICK"
        return "NONE"

    def _target_state(self, btc: Optional[float], target: Optional[float], now: float) -> Dict[str, Any]:
        if btc is None or target is None:
            return {"height": None, "side": "NONE", "event": "NONE", "hold": 0.0}
        height = btc-target
        side = "YES" if height > 0 else "NO" if height < 0 else "ON"
        event = "NONE"
        if side in ("YES","NO"):
            if self.last_target_side in ("YES","NO") and side != self.last_target_side:
                age = None if self.last_target_cross_ts is None else now-self.last_target_cross_ts
                self.last_target_cross_ts = now
                self.target_hold_since = now
                event = "TARGET_RECLAIM_REVERSAL" if age is not None and age <= TARGET_FAKEOUT_WINDOW_SEC else "TARGET_CROSS"
            elif self.last_target_side is None:
                self.last_target_cross_ts = now
                self.target_hold_since = now
            self.last_target_side = side
        hold = 0.0 if self.target_hold_since is None else max(0.0, now-self.target_hold_since)
        if event == "NONE" and side in ("YES","NO") and hold >= TARGET_ACCEPT_HOLD_SEC:
            event = f"TARGET_ACCEPTED_{side}"
        return {"height": height, "side": side, "event": event, "hold": hold}

    def _ema_geometry(self, now: float) -> Optional[Dict[str, Any]]:
        btc = _f(getattr(core, "btc_last_price", None))
        e9 = _f(getattr(core, "btc_ema_9", None))
        e30 = _f(getattr(core, "btc_ema_30", None))
        if btc is None or e9 is None or e30 is None:
            return None
        p3=_history_nearest(3,now); p6=_history_nearest(6,now)
        p9=_history_nearest(9,now); p30=_history_nearest(30,now)
        gap=e9-e30
        e9d3=_delta(p3,e9,"e9"); e9d6=_delta(p6,e9,"e9"); e9d9=_delta(p9,e9,"e9")
        e30d6=_delta(p6,e30,"e30"); e30d30=_delta(p30,e30,"e30")
        gd3=_delta(p3,gap,"gap"); gd6=_delta(p6,gap,"gap"); gd9=_delta(p9,gap,"gap")
        curvature = None if e9d3 is None or e9d9 is None else e9d3-(e9d9/3.0)
        return {
            "btc":btc,"e9":e9,"e30":e30,"gap":gap,
            "e9d3":e9d3,"e9d6":e9d6,"e9d9":e9d9,
            "e30d6":e30d6,"e30d30":e30d30,
            "gd3":gd3,"gd6":gd6,"gd9":gd9,"curvature":curvature
        }

    def _return_side_candidate(self, g: Dict[str,Any], r60: float) -> str:
        if None in (g.get("e9d3"),g.get("e9d6"),g.get("gd6")):
            return "NONE"
        gap=g["gap"]
        if abs(gap) < max(1.5,0.05*r60):
            return "NONE"
        conv=max(0.75,0.02*r60)
        if gap > 0 and g["e9d3"] < 0 and g["e9d6"] < 0 and g["gd6"] < -conv:
            return "NO"
        if gap < 0 and g["e9d3"] > 0 and g["e9d6"] > 0 and g["gd6"] > conv:
            return "YES"
        return "NONE"

    def _typical_leg_duration(self) -> float:
        vals=[]
        for leg in self.completed_legs[-LEG_HISTORY_MAX:]:
            d=_f(leg.get("duration_sec"))
            if d is not None and MIN_LEG_DURATION_SEC <= d <= MAX_LEG_DURATION_SEC:
                vals.append(d)
        return max(MIN_LEG_DURATION_SEC,min(MAX_LEG_DURATION_SEC,_safe_median(vals,DEFAULT_LEG_DURATION_SEC)))

    def _new_leg(self, side: str, state: str, ticker: str, now: float, g: Dict[str,Any],
                 target_height: Optional[float], origin_side: str, inherited_leg_id: str="") -> Dict[str,Any]:
        self.leg_counter += 1
        return {
            "leg_id":f"LG{self.leg_counter:05d}","side":side,"state":state,"ticker":ticker,
            "start_ts":now,"origin_side":origin_side,"peak_amp":abs(g["gap"]),
            "prior_leg_amp":self.active_leg.get("peak_amp") if isinstance(self.active_leg,dict) else None,
            "transfer_ts":None,"target_height_start":target_height,"target_height_transfer":None,
            "regeneration_state":"NONE","inherited_leg_id":inherited_leg_id,"last_state_change_ts":now
        }

    def _complete_active_leg(self, now: float, reason: str) -> None:
        if not isinstance(self.active_leg,dict):
            return
        leg=dict(self.active_leg)
        leg["duration_sec"]=max(0.0,now-float(leg.get("start_ts") or now))
        leg["end_reason"]=reason
        self.completed_legs.append(leg)
        self.completed_legs=self.completed_legs[-LEG_HISTORY_MAX:]

    def _time_capacity(self, leg: Dict[str,Any], seconds_left: Optional[float], now: float):
        typical=self._typical_leg_duration()
        progress={
            "LEG_START":0.10,"RETURN_SLOPE":0.22,"EMA30_APPROACH":0.38,"TRANSFER":0.50,
            "OPPOSITE_BUILD":0.66,"EXPANSION":0.82,"MATURE":0.95
        }.get(str(leg.get("state")),0.25)
        age=max(0.0,now-float(leg.get("start_ts") or now))
        remaining=min(max(0.0,typical-age) if age>9 else typical,max(0.0,typical*(1-progress))+9.0)
        if seconds_left is None:
            return remaining,None,"UNKNOWN"
        ratio=seconds_left/max(1.0,remaining)
        if seconds_left <= 0:
            state="ROLLOVER_CONTINUATION_ACTIVE"
        elif ratio >= 1.20:
            state="ENOUGH_TIME_THIS_CONTRACT"
        elif ratio >= 0.70:
            state="MARGINAL_TIME"
        else:
            state="LEG_INCOMPLETE_EXPECT_ROLLOVER"
        return remaining,ratio,state

    def _update_leg(self,ticker,g,metrics,target,seconds_left,now):
        r60=metrics["r60"]; gap=g["gap"]; gap_side=_side_from_signed(gap)
        return_side=self._return_side_candidate(g,r60)
        approach=max(2.0,0.12*r60); transfer=max(1.0,0.04*r60); build=max(3.0,0.20*r60)

        if self.active_leg is None:
            seed=return_side if return_side in ("YES","NO") else gap_side
            if seed not in ("YES","NO"):
                seed=target.get("side") if target.get("side") in ("YES","NO") else "YES"
            self.active_leg=self._new_leg(seed,"RETURN_SLOPE" if return_side==seed else "EXPANSION",
                                          ticker,now,g,target.get("height"),_opposite(seed))

        current_side=str(self.active_leg.get("side") or "")
        if return_side in ("YES","NO") and return_side != current_side:
            if not self.return_candidate or self.return_candidate.get("side") != return_side:
                self.return_candidate={"side":return_side,"since":now}
            age=now-float(self.return_candidate.get("since") or now)
            reclaim=target.get("event")=="TARGET_RECLAIM_REVERSAL" and target.get("side")==return_side
            if age >= RETURN_CONFIRM_SEC or reclaim:
                inherited=self.active_leg.get("leg_id","")
                self._complete_active_leg(now,"RETURN_SLOPE_HANDOFF")
                self.active_leg=self._new_leg(return_side,"RETURN_SLOPE",ticker,now,g,target.get("height"),
                                              current_side,inherited)
                self.return_candidate=None
                self.regen_candidate=None
        elif return_side == current_side:
            self.return_candidate=None

        leg=self.active_leg
        leg["ticker"]=ticker
        leg["peak_amp"]=max(_f(leg.get("peak_amp"),0.0) or 0.0,abs(gap))
        side=str(leg.get("side") or "")
        origin=str(leg.get("origin_side") or _opposite(side))
        gap_matches_leg=gap_side==side

        if not gap_matches_leg:
            if abs(gap) <= transfer:
                state="TRANSFER"
            elif abs(gap) <= approach:
                state="EMA30_APPROACH"
            else:
                state="RETURN_SLOPE"

            gd6=g.get("gd6"); e9d6=g.get("e9d6")
            regen=False
            if origin=="YES" and gap>0 and gd6 is not None and e9d6 is not None:
                regen=gd6>max(0.75,0.02*r60) and e9d6>0
            elif origin=="NO" and gap<0 and gd6 is not None and e9d6 is not None:
                regen=gd6<-max(0.75,0.02*r60) and e9d6<0

            if regen:
                if not self.regen_candidate or self.regen_candidate.get("side")!=origin:
                    self.regen_candidate={"side":origin,"since":now}
                elif now-float(self.regen_candidate.get("since") or now) >= RETURN_CONFIRM_SEC:
                    failed=leg.get("leg_id","")
                    self._complete_active_leg(now,"RETURN_SLOPE_FAILED_REGENERATION")
                    self.active_leg=self._new_leg(origin,"EXPANSION",ticker,now,g,target.get("height"),side,failed)
                    self.active_leg["regeneration_state"]="REGENERATION_CONFIRMED"
                    leg=self.active_leg; state="EXPANSION"; self.regen_candidate=None
            else:
                self.regen_candidate=None
        else:
            if leg.get("transfer_ts") is None:
                leg["transfer_ts"]=now
                leg["target_height_transfer"]=target.get("height")
            gd6=g.get("gd6")
            expanding=gd6 is not None and ((side=="YES" and gd6>0) or (side=="NO" and gd6<0))
            age_transfer=max(0.0,now-float(leg.get("transfer_ts") or now))
            if abs(gap)<=build or age_transfer<=12:
                state="OPPOSITE_BUILD"
            elif expanding:
                state="EXPANSION"
            else:
                age=max(0.0,now-float(leg.get("start_ts") or now))
                extended=abs(gap)>=max(5.0,0.55*r60)
                state="MATURE" if age>=0.70*self._typical_leg_duration() or extended else "EXPANSION"

        if state != leg.get("state"):
            leg["state"]=state
            leg["last_state_change_ts"]=now

        rem,ratio,cap=self._time_capacity(leg,seconds_left,now)
        leg["estimated_remaining"]=rem; leg["time_capacity_ratio"]=ratio; leg["time_capacity_state"]=cap
        leg["target_height"]=target.get("height"); leg["target_event"]=target.get("event"); leg["target_hold"]=target.get("hold")

        rollover="NONE"
        if seconds_left is not None and seconds_left <= ROLLOVER_PREARM_SEC:
            if cap=="LEG_INCOMPLETE_EXPECT_ROLLOVER":
                rollover="ROLLOVER_CONTINUATION_ACTIVE"
                self.prearm={"side":side,"leg_id":leg.get("leg_id"),"ts":now,"from_ticker":ticker}
            elif leg.get("state")=="MATURE" and return_side in ("YES","NO") and return_side!=side:
                rollover=f"PREARM_{return_side}"
                self.prearm={"side":return_side,"leg_id":leg.get("leg_id"),"ts":now,"from_ticker":ticker}
        leg["rollover_state"]=rollover
        return leg

    def _handle_rollover(self,ticker,target_height,now):
        if self.last_ticker is None:
            self.last_ticker=ticker
            return
        if ticker==self.last_ticker:
            return
        leg=self.active_leg or {}
        _write(ROLLOVER_LOG,ROLLOVER_FIELDS,{
            "event":"LEG_CARRIED_ACROSS_ROLLOVER","from_ticker":self.last_ticker,"to_ticker":ticker,
            "leg_id":leg.get("leg_id"),"leg_side":leg.get("side"),"leg_state":leg.get("state"),
            "leg_age_sec":max(0.0,now-float(leg.get("start_ts") or now)) if leg else None,
            "target_height_old":leg.get("target_height"),"next_target":_f(getattr(core,"v94b_active_target_value",None)),
            "prearmed_side":(self.prearm or {}).get("side"),"time_capacity_state":leg.get("time_capacity_state"),
            "estimated_leg_seconds_remaining":leg.get("estimated_remaining"),
            "note":"Contract fencepost changed; Leg Geometry remains continuous and target is remapped."
        })
        if leg:
            leg["ticker"]=ticker
            leg["inherited_leg_id"]=leg.get("leg_id")
            leg["target_height"]=target_height
            leg["rollover_state"]="ROLLOVER_CONTINUATION_ACTIVE"
        self.arms.clear()
        self.last_ticker=ticker

    def _score_side(self,side,parent,leg,g,metrics,target,struct,form,wick,seconds_left):
        score=0; reasons=[]; blocks=[]; sign=_sign_for_side(side); opp=_opposite(side)
        leg_side=str(leg.get("side") or ""); state=str(leg.get("state") or "")

        if leg_side==side:
            pts={"RETURN_SLOPE":4,"EMA30_APPROACH":5,"TRANSFER":6,"OPPOSITE_BUILD":6,
                 "EXPANSION":5,"MATURE":2,"LEG_START":2}.get(state,2)
            score+=pts; reasons.append(f"LEG_{state}")
        elif leg_side==opp and state in ("RETURN_SLOPE","EMA30_APPROACH","TRANSFER","OPPOSITE_BUILD","EXPANSION"):
            score-=5; blocks.append("ACTIVE_OPPOSITE_LEG")

        if side==str(leg.get("origin_side") or "") and state in ("RETURN_SLOPE","EMA30_APPROACH","TRANSFER","OPPOSITE_BUILD") \
                and leg.get("regeneration_state")!="REGENERATION_CONFIRMED":
            score-=4; blocks.append("OLD_SIDE_CONTINUATION_DISARMED")

        height=_f(target.get("height"))
        if height is not None:
            if height*sign>0:
                score+=2; reasons.append("TARGET_HEIGHT_FAVORABLE")
                if abs(height)>=0.25*metrics["r60"]:
                    score+=1; reasons.append("TARGET_HEIGHT_MEANINGFUL")
            elif height*sign<0 and seconds_left is not None and seconds_left<=60:
                score-=2; blocks.append("LATE_TARGET_HEIGHT_AGAINST")

        tev=str(target.get("event") or "NONE")
        if tev=="TARGET_RECLAIM_REVERSAL" and target.get("side")==side:
            score+=4; reasons.append("TARGET_RECLAIM_REVERSAL")
        elif tev==f"TARGET_ACCEPTED_{side}":
            score+=2; reasons.append("TARGET_ACCEPTED")
        elif tev==f"TARGET_ACCEPTED_{opp}":
            score-=2; blocks.append("TARGET_ACCEPTED_AGAINST")

        fast=0
        for key in ("ch3","ch6","ch9"):
            if metrics[key]*sign>max(2.0,0.025*metrics["r60"]):
                fast+=1
        if fast:
            score+=min(3,fast); reasons.append(f"FAST_369_{fast}")

        if metrics["ch30"]*sign>max(6.0,0.10*metrics["r60"]):
            score+=1; reasons.append("MOVE30")
        if metrics["eff60"] is not None and metrics["eff60"]>=0.60 and metrics["ch60"]*sign>0:
            score+=1; reasons.append("EFF60_ALIGNED")
        if g.get("e9d6") is not None and g["e9d6"]*sign>0:
            score+=1; reasons.append("EMA9_SLOPE")
        if (g["btc"]-g["e9"])*sign>0:
            score+=1; reasons.append("PRICE_VS_EMA9")

        if wick=="LOWER_REJECTION" and side=="YES":
            score+=2; reasons.append("LOWER_WICK_REJECTION")
        elif wick=="UPPER_REJECTION" and side=="NO":
            score+=2; reasons.append("UPPER_WICK_REJECTION")
        elif wick=="LOWER_WICK" and side=="YES":
            score+=1; reasons.append("LOWER_WICK")
        elif wick=="UPPER_WICK" and side=="NO":
            score+=1; reasons.append("UPPER_WICK")

        if metrics["vol"] is not None and metrics["vol"]>=1.5 and metrics["ch6"]*sign>0:
            score+=1; reasons.append("VOLUME_CONFIRM")

        sb=str(struct.get("structural_bias") or "NEUTRAL").upper()
        if sb==side:
            score+=1; reasons.append("STRUCTURAL_BIAS")
        elif sb==opp:
            score-=1; blocks.append("STRUCTURAL_BIAS_OPPOSES")

        fgeo=str(form.get("formation") or "").upper()
        freg=str(form.get("regime") or "").upper()
        if side=="YES" and any(x in fgeo for x in ("RISING","ASCENDING")) and freg in ("TREND","RELEASE","REVERSAL","PULLBACK"):
            score+=1; reasons.append("FORMATION")
        if side=="NO" and any(x in fgeo for x in ("FALLING","DESCENDING")) and freg in ("TREND","RELEASE","REVERSAL","PULLBACK"):
            score+=1; reasons.append("FORMATION")

        if parent==side:
            score+=1; reasons.append("PARENT_CONTEXT")

        if self.prearm and self.prearm.get("side")==side and self.prearm.get("from_ticker")!=leg.get("ticker"):
            score+=3; reasons.append("ROLLOVER_PREARM")

        return score,reasons,blocks

    def _entry_signal(self,side,parent,leg,struct,metrics,seconds_left,decision):
        elapsed=None if seconds_left is None else max(0.0,900.0-min(900.0,seconds_left))
        return {
            "setup_grade":"LEG","signal_grade":"A+" if decision in ("FAST_LEG","EXPIRY_TARGET","ROLLOVER_PREARM") else "A",
            "strategy":"V95C_LEG_GEOMETRY","trade_intent":"LEG","market_regime":f"LEG_{leg.get('state')}",
            "seconds_to_close":seconds_left,"contract_elapsed_seconds":elapsed,
            "btc_price":_f(getattr(core,"btc_last_price",None)),"btc_ema_9":_f(getattr(core,"btc_ema_9",None)),
            "btc_ema_30":_f(getattr(core,"btc_ema_30",None)),"target_price":struct.get("target_price",_target_price()),
            "target_distance":leg.get("target_height"),"btc_range_60s":metrics["r60"],
            "btc_change_60s":metrics["ch60"],"btc_trend_efficiency_60s":metrics["eff60"],
            "ema9_arc_stage":leg.get("state"),"ema9_arc_direction":"UP" if side=="YES" else "DOWN",
            "early_exception":True,"early_exception_reasons":f"V95C_{decision};LEG_{leg.get('state')}",
            "early_trade":bool(elapsed is not None and elapsed<600),"session":"V95C","daypart":"",
            "et_hour":datetime.now(ET).hour
        }

    def _active_position(self,ticker):
        for side in ("YES","NO"):
            p=(getattr(core,"paper_positions",{}) or {}).get(side)
            if isinstance(p,dict) and str(p.get("ticker") or "")==str(ticker):
                return p
        return None

    def _emit_leg(self,ticker,leg,g,target,seconds_left,wick,now):
        sig=(leg.get("leg_id"),leg.get("state"),leg.get("side"),
             round(_f(target.get("height"),0.0) or 0.0,0),leg.get("time_capacity_state"),leg.get("rollover_state"))
        if sig==self.last_leg_emit_sig and now-self.last_leg_emit_ts<3:
            return
        self.last_leg_emit_sig=sig; self.last_leg_emit_ts=now
        _write(LEG_LOG,LEG_FIELDS,{
            "event":"LEG_STATE","ticker":ticker,"leg_id":leg.get("leg_id"),"leg_side":leg.get("side"),
            "leg_state":leg.get("state"),"leg_age_sec":max(0.0,now-float(leg.get("start_ts") or now)),
            "origin_side":leg.get("origin_side"),"regeneration_state":leg.get("regeneration_state"),
            "btc_price":g["btc"],"target_price":_target_price(),"target_height":target.get("height"),
            "seconds_left":seconds_left,"ema9":g["e9"],"ema30":g["e30"],"ema_gap":g["gap"],
            "ema9_slope3":g.get("e9d3"),"ema9_slope6":g.get("e9d6"),"ema9_slope9":g.get("e9d9"),
            "ema9_curvature":g.get("curvature"),"ema30_slope6":g.get("e30d6"),"ema30_slope30":g.get("e30d30"),
            "gap_delta3":g.get("gd3"),"gap_delta6":g.get("gd6"),"gap_delta9":g.get("gd9"),
            "current_amplitude":abs(g["gap"]),"peak_amplitude":leg.get("peak_amp"),
            "prior_leg_amplitude":leg.get("prior_leg_amp"),"transfer_ts":_utc(leg.get("transfer_ts")) if leg.get("transfer_ts") else "",
            "estimated_leg_seconds_remaining":leg.get("estimated_remaining"),"time_capacity_ratio":leg.get("time_capacity_ratio"),
            "time_capacity_state":leg.get("time_capacity_state"),"rollover_state":leg.get("rollover_state"),
            "inherited_leg_id":leg.get("inherited_leg_id"),"next_target":_f(getattr(core,"v94b_waypoint_target",None)),
            "wick_rejection":wick,"target_event":target.get("event"),"target_hold_sec":target.get("hold"),
            "note":"EMA30=Spine; return slope + transfer + opposite build are one leg."
        })

    def _emit_tactical(self,ticker,side,ask,state,score,other_score,reasons,blocks,parent,leg,target,metrics,seconds_left,wick,decision="",legacy_strategy="",force=False):
        arm=self.arms.get((ticker,side)) or {}
        sig=(state,score,other_score,round(ask or -1,2),decision,leg.get("state"),leg.get("side"))
        now=time.time()
        if not force and self.last_tactical_emit.get(side)==sig and now-self.last_tactical_emit_ts.get(side,0)<3:
            return
        self.last_tactical_emit[side]=sig; self.last_tactical_emit_ts[side]=now
        _write(TACTICAL_LOG,TACTICAL_FIELDS,{
            "event":"TACTICAL_STATE","ticker":ticker,"side":side,"other_side":_opposite(side),"ask":ask,
            "state":state,"arm_ts":_utc(arm.get("ts")) if arm.get("ts") else "",
            "arm_age_sec":now-float(arm.get("ts") or now) if arm else None,"arm_ask":arm.get("ask"),
            "score":score,"other_score":other_score,"score_lead":score-other_score,
            "reasons":";".join(reasons),"blocks":";".join(blocks),"parent_side":parent,
            "leg_id":leg.get("leg_id"),"leg_side":leg.get("side"),"leg_state":leg.get("state"),
            "regeneration_state":leg.get("regeneration_state"),"target_height":target.get("height"),
            "target_event":target.get("event"),"seconds_left":seconds_left,
            "time_capacity_state":leg.get("time_capacity_state"),"rollover_state":leg.get("rollover_state"),
            "prearmed_side":(self.prearm or {}).get("side"),"btc_change3":metrics["ch3"],
            "btc_change6":metrics["ch6"],"btc_change9":metrics["ch9"],"btc_change30":metrics["ch30"],
            "btc_change60":metrics["ch60"],"trend_eff60":metrics["eff60"],"volume_ratio":metrics["vol"],
            "wick_rejection":wick,"legacy_strategy":legacy_strategy,"decision":decision,
            "note":"Dual-side tactical authority; parent is context only."
        })

    def on_tick(self,ticker,yes_ask,no_ask,close_ts=None,now=None):
        now=time.time() if now is None else float(now)
        snap=self._snapshot(ticker,yes_ask,no_ask,close_ts,now)
        g=self._ema_geometry(now)
        if not g:
            return
        metrics=self._btc_metrics(now)
        seconds_left=self._seconds_left(close_ts,snap,now)
        target=self._target_state(g["btc"],_target_price(),now)
        self._handle_rollover(ticker,target.get("height"),now)
        leg=self._update_leg(ticker,g,metrics,target,seconds_left,now)
        struct=self._structural(); form=self._formation(now); parent=self._parent_side(snap); wick=self._wick_rejection()

        ys,yr,yb=self._score_side("YES",parent,leg,g,metrics,target,struct,form,wick,seconds_left)
        ns,nr,nb=self._score_side("NO",parent,leg,g,metrics,target,struct,form,wick,seconds_left)
        self.last_scores={"YES":ys,"NO":ns}; self.last_score_reasons={"YES":yr,"NO":nr}
        self.last_context={"ticker":ticker,"parent":parent,"leg":dict(leg),"geom":dict(g),"metrics":dict(metrics),
                           "target":dict(target),"seconds_left":seconds_left,"wick":wick,
                           "yes_ask":yes_ask,"no_ask":no_ask}
        self._emit_leg(ticker,leg,g,target,seconds_left,wick,now)

        scores={"YES":ys,"NO":ns}; reasons={"YES":yr,"NO":nr}; blocks={"YES":yb,"NO":nb}
        for side in ("YES","NO"):
            other=_opposite(side); ask=_ask_for(side,yes_ask,no_ask)
            if ask is None or ask<=0:
                continue
            score=scores[side]; other_score=scores[other]; key=(ticker,side)
            qualifies=score>=ENTRY_ARM_SCORE and score-other_score>=ENTRY_MIN_LEAD \
                and "ACTIVE_OPPOSITE_LEG" not in blocks[side] \
                and "OLD_SIDE_CONTINUATION_DISARMED" not in blocks[side]

            if not qualifies:
                self.arms.pop(key,None)
                self._emit_tactical(ticker,side,ask,"WATCH",score,other_score,reasons[side],blocks[side],
                                    parent,leg,target,metrics,seconds_left,wick)
                continue

            arm=self.arms.get(key)
            if arm is None:
                arm={"ts":now,"ask":ask}; self.arms[key]=arm
                self._emit_tactical(ticker,side,ask,"ARMED",score,other_score,reasons[side],blocks[side],
                                    parent,leg,target,metrics,seconds_left,wick,force=True)

            age=now-float(arm.get("ts") or now); arm_ask=_f(arm.get("ask"),ask) or ask
            if age>ARM_TTL_SEC:
                self.arms.pop(key,None); continue
            max_ask=EXPIRY_MAX_ASK if seconds_left is not None and seconds_left<=60 else ENTRY_MAX_ASK
            if ask<ENTRY_MIN_ASK or ask>max_ask:
                continue
            reprice=ask-arm_ask
            if reprice>=MAX_REPRICE_ABS and reprice/arm_ask>=MAX_REPRICE_PCT:
                self.arms.pop(key,None)
                self._emit_tactical(ticker,side,ask,"STAND_DOWN",score,other_score,reasons[side],blocks[side],
                                    parent,leg,target,metrics,seconds_left,wick,decision="NO_CHASE",force=True)
                continue
            if self._active_position(ticker):
                continue
            if self.entry_count.get(key,0)>=MAX_V95C_ENTRIES_PER_SIDE_CONTRACT:
                continue

            expiry=seconds_left is not None and seconds_left<=60 and target.get("side")==side \
                and score>=EXPIRY_ENTRY_SCORE and age>=EXPIRY_ENTRY_CONFIRM_SEC
            fast=score>=FAST_ENTRY_SCORE and age>=FAST_ENTRY_CONFIRM_SEC
            standard=score>=STANDARD_ENTRY_SCORE and age>=STANDARD_ENTRY_CONFIRM_SEC
            prearmed=self.prearm and self.prearm.get("side")==side and self.prearm.get("from_ticker")!=ticker and age>=0.5
            decision="EXPIRY_TARGET" if expiry else "ROLLOVER_PREARM" if prearmed else "FAST_LEG" if fast else "STANDARD_LEG" if standard else ""
            if not decision:
                continue

            signal=self._entry_signal(side,parent,leg,struct,metrics,seconds_left,decision)
            signal["price"]=ask
            old_cd=getattr(core,"PAPER_REENTRY_COOLDOWN",None)
            try:
                if old_cd is not None:
                    core.PAPER_REENTRY_COOLDOWN=0
                entered=bool(core.paper_enter(ticker,side,ask,signal))
            finally:
                if old_cd is not None:
                    core.PAPER_REENTRY_COOLDOWN=old_cd

            if entered:
                self.entry_count[key]=self.entry_count.get(key,0)+1
                pos=(getattr(core,"paper_positions",{}) or {}).get(side)
                if isinstance(pos,dict):
                    pos["_v95c_leg_id"]=leg.get("leg_id"); pos["_v95c_leg_side"]=leg.get("side")
                    pos["_v95c_entry_leg_state"]=leg.get("state"); pos["_v95c_decision"]=decision
                self.arms.clear()
                self._emit_tactical(ticker,side,ask,"ENTERED",score,other_score,reasons[side],blocks[side],
                                    parent,leg,target,metrics,seconds_left,wick,decision=decision,force=True)

    def allow_entry(self,ticker,side,signal):
        if str((signal or {}).get("strategy") or "").startswith("V95C"):
            return True,"V95C_AUTHORITY"
        ctx=self.last_context if self.last_context.get("ticker")==ticker else {}
        leg=ctx.get("leg") or {}
        if not leg:
            return True,"NO_LEG_CONTEXT"
        active=str(leg.get("side") or ""); state=str(leg.get("state") or "")
        if active in ("YES","NO") and side!=active and state in ("RETURN_SLOPE","EMA30_APPROACH","TRANSFER","OPPOSITE_BUILD","EXPANSION") \
                and leg.get("regeneration_state")!="REGENERATION_CONFIRMED":
            return False,"BLOCK_STALE_OLD_SIDE_AGAINST_ACTIVE_LEG"
        return True,"ALLOW"

    def _treasury_proposal(self,ticker,side,position):
        try:
            tid=m._position_trade_id(position,f"{ticker}:{side}")
            st=m.brain.trade_state.get(tid); cid=st.get("defense_id") if isinstance(st,dict) else None
            cand=m.brain.treasury_candidates.get(cid) if cid else None
            return isinstance(cand,dict) and not cand.get("closed")
        except Exception:
            return False

    def exit_gate(self,ticker,side,position,yes_ask,no_ask,now):
        ctx=self.last_context if self.last_context.get("ticker")==ticker else {}
        leg=dict(ctx.get("leg") or self.active_leg or {}); target=dict(ctx.get("target") or {})
        metrics=dict(ctx.get("metrics") or {}); seconds_left=_f(ctx.get("seconds_left")); wick=str(ctx.get("wick") or "NONE")
        bid=_bid_for(side,yes_ask,no_ask); entry=_f(position.get("entry_ask"))
        roi=((bid-entry)/entry) if bid is not None and entry not in (None,0) else None
        peak=(_f(position.get("mfe_pct"),0.0) or 0.0)/100.0
        opp=_opposite(side); opp_score=self.last_scores.get(opp,0)
        proposed="V95A_ACTIVE_TREASURY_DEFEND" if self._treasury_proposal(ticker,side,position) else ""
        ruling="HOLD_LEG_DEVELOPING"; final="HOLD"

        if roi is not None and roi<=EMERGENCY_HARD_ROI:
            ruling="EMERGENCY_BYPASS"; final="ALLOW_INHERITED_EMERGENCY"
        else:
            leg_side=str(leg.get("side") or ""); state=str(leg.get("state") or "")
            tev=str(target.get("event") or "NONE"); tside=str(target.get("side") or "NONE")
            if tev=="TARGET_RECLAIM_REVERSAL" and tside==opp and opp_score>=WHOLE_LEG_OPPOSITE_EXIT_SCORE:
                ruling="EXIT_OPPOSITE_LEG_CONFIRMED"; final="EXIT"; proposed=proposed or "TARGET_RECLAIM_REVERSAL"
            elif leg_side==opp and state in ("RETURN_SLOPE","EMA30_APPROACH","TRANSFER","OPPOSITE_BUILD","EXPANSION") \
                    and opp_score>=WHOLE_LEG_OPPOSITE_EXIT_SCORE:
                age=max(0.0,now-float(leg.get("start_ts") or now))
                if age>=WHOLE_LEG_OPPOSITE_EXIT_CONFIRM_SEC:
                    ruling="EXIT_OPPOSITE_LEG_CONFIRMED"; final="EXIT"; proposed=proposed or "OPPOSITE_LEG"
            elif seconds_left is not None and seconds_left<=TERMINAL_TARGET_SEC:
                height=_f(target.get("height")); r60=_f(metrics.get("r60"),1.0) or 1.0
                against=height is not None and height*_sign_for_side(side)<0
                meaningful=height is not None and abs(height)>=max(8.0,0.15*r60)
                if against and meaningful and (tev==f"TARGET_ACCEPTED_{opp}" or opp_score>=WHOLE_LEG_OPPOSITE_EXIT_SCORE):
                    ruling="EXIT_TIME_TARGET_TERMINAL"; final="EXIT"; proposed=proposed or "TIME_TARGET_TERMINAL"
            elif leg_side==side and state in ("RETURN_SLOPE","EMA30_APPROACH","TRANSFER"):
                ruling="HOLD_RETURN_SLOPE_EXPECTED"

        row={
            "event":"EXIT_GATE","trade_id":position.get("trade_id"),"ticker":ticker,"side":side,
            "entry_ask":entry,"current_bid":bid,"roi":roi,"mfe_roi":peak,"proposed_exit_reason":proposed,
            "gate_ruling":ruling,"final_action":final,"leg_id":leg.get("leg_id"),"leg_side":leg.get("side"),
            "leg_state":leg.get("state"),"regeneration_state":leg.get("regeneration_state"),
            "target_height":target.get("height"),"target_event":target.get("event"),"target_hold_sec":target.get("hold"),
            "seconds_left":seconds_left,"estimated_leg_seconds_remaining":leg.get("estimated_remaining"),
            "time_capacity_ratio":leg.get("time_capacity_ratio"),"time_capacity_state":leg.get("time_capacity_state"),
            "yes_score":self.last_scores.get("YES"),"no_score":self.last_scores.get("NO"),"opposite_score":opp_score,
            "wick_rejection":wick,"note":"All non-emergency exits route through Whole-Leg Exit Authority."
        }
        _write(EXIT_LOG,EXIT_FIELDS,row)
        return row

    def _suppress_advisory_exits(self):
        replacements={
            "ANTICIPATION_FAST_FAIL_SECONDS":-1.0,"KING_GUARD_ARM_MFE":999.0,
            "V85_STRUCTURAL_STOP_MIN_AGE":1e9,"V84_SWIRL_LOCK_MFE":999.0,"V84_SWIRL_SNIP_TP":999.0,
            "BIRD_17_TRIGGER":999.0,"BIRD_20_TRIGGER":999.0,"BIRD_23_TRIGGER":999.0,
            "V92_STRUCTURAL_EXIT_MIN_AGE":1e9,"V92_PROTECT_MFE":999.0,"PROVEN_MFE_PROTECT":999.0,
            "THESIS_INVALIDATION_MAX_ROI":-999.0,"CORE_SIDEWAYS_TP_ROI":999.0,
            "CORE_SIDEWAYS_TP_MID_ROI":999.0,"LATE_PROFIT_TP_ROI":999.0,
            "EARLY_TAKE_PROFIT_ROI":999.0,"TRAIL_ACTIVATE_ROI":999.0,
            "LATE_RISK_WINDOW_SECONDS":-1.0,"PROVEN_RECOVERY_MIN_SECONDS_LEFT":-1.0
        }
        old={}
        for name,value in replacements.items():
            if hasattr(core,name):
                old[name]=getattr(core,name); setattr(core,name,value)
        return old

    @staticmethod
    def _restore_globals(old):
        for name,value in old.items():
            setattr(core,name,value)

    def execute_central_exit(self,position,yes_ask,no_ask,ruling):
        side=str(position.get("side") or ""); bid=_bid_for(side,yes_ask,no_ask)
        if side not in ("YES","NO") or bid is None:
            return False
        qty=_i(position.get("qty"),0); cost=_f(position.get("cost"),0.0) or 0.0
        pnl=qty*bid-cost; entry=_f(position.get("entry_ask"))
        roi=((bid-entry)/entry) if entry not in (None,0) else 0.0
        reason=f"V95C_{ruling}"
        if pnl<0 and position.get("v85_countertrend_entry"):
            try: core.v85_last_failed_countertrend[side]=time.time()
            except Exception: pass
        core.paper_realized_pnl+=pnl
        core.log_paper_event("EXIT",position,bid,reason)
        core.record_contract_trade(position,bid,pnl,reason)
        try: core.v94b_finalize_trade_shadows(position,bid,roi,reason,pnl)
        except Exception as exc: print(f"V9.5C finalize error: {exc}")
        core.paper_positions[side]=None; core.last_paper_exit_time[side]=time.time()
        print(f"V9.5C WHOLE-LEG EXIT | #{position.get('trade_id')} {side} @ {bid:.3f} | {ruling} | PnL=USD {pnl:+.2f}")
        return True


brain=LegGeometryAuthority()
_HOOKS_INSTALLED=False


def install_v95c_hooks():
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    _HOOKS_INSTALLED=True

    original_eval_entry=a.brain.evaluate_entry
    def v95a_entry_eval_wrapper(ticker,side,ask,signal):
        if str((signal or {}).get("strategy") or "").startswith("V95C"):
            return False,{"gate_action":"ALLOW","gate_reason":"V95C_LEG_GEOMETRY_AUTHORITY",
                          "leg_id":(brain.active_leg or {}).get("leg_id"),"leg_age_sec":0,
                          "leg_start_bid":None,"premium_abs":None,"premium_pct":None,"chapter_label":"V95C"}
        return original_eval_entry(ticker,side,ask,signal)
    a.brain.evaluate_entry=v95a_entry_eval_wrapper

    def treasury_proposal_only(ticker,yes_ask,no_ask):
        return 0
    a.brain.apply_active_treasury=treasury_proposal_only

    original_mission=getattr(core,"v94g_trade_mission_observer")
    def mission_wrapper(ticker,yes_ask,no_ask,now=None):
        result=original_mission(ticker,yes_ask,no_ask,now)
        try:
            brain.on_tick(ticker,yes_ask,no_ask,getattr(core,"v94b_active_close_ts",None),
                          time.time() if now is None else float(now))
        except Exception as exc:
            print(f"V9.5C Leg Geometry error: {exc}")
        return result
    core.v94g_trade_mission_observer=mission_wrapper

    original_enter=getattr(core,"paper_enter")
    def paper_enter_wrapper(ticker,side,ask,signal):
        allowed,reason=brain.allow_entry(ticker,side,signal or {})
        if not allowed:
            print(f"V9.5C ENTRY BLOCK | {side} @ {float(ask):.3f} | {reason}")
            return False
        return original_enter(ticker,side,ask,signal)
    core.paper_enter=paper_enter_wrapper

    original_manage=getattr(core,"paper_manage")
    def paper_manage_wrapper(ticker,yes_ask,no_ask):
        pos=brain._active_position(ticker); gate=None; old={}
        if isinstance(pos,dict):
            side=str(pos.get("side") or "")
            try:
                gate=brain.exit_gate(ticker,side,pos,yes_ask,no_ask,time.time())
            except Exception as exc:
                print(f"V9.5C exit gate error: {exc}")
                gate={"gate_ruling":"EMERGENCY_BYPASS","final_action":"ALLOW_INHERITED_EMERGENCY"}
            if gate.get("final_action")=="HOLD":
                old=brain._suppress_advisory_exits()
        try:
            result=original_manage(ticker,yes_ask,no_ask)
        finally:
            if old:
                brain._restore_globals(old)
        if isinstance(pos,dict):
            side=str(pos.get("side") or "")
            still=(getattr(core,"paper_positions",{}) or {}).get(side) is pos
            if still and gate and gate.get("final_action")=="EXIT":
                brain.execute_central_exit(pos,yes_ask,no_ask,str(gate.get("gate_ruling")))
        return result
    core.paper_manage=paper_manage_wrapper


async def main():
    a.install_hooks()
    r.install_router_shadow_hooks()
    rs2.install_rs2_hooks()

    # V9.5B Level-2/Thesis-Shield hooks intentionally NOT installed.
    install_v95c_hooks()

    print("="*118)
    print("TACHYOS V9.5C — LEG GEOMETRY / DUAL-SIDE AUTHORITY / WHOLE-LEG EXIT GATE")
    print(f"RUN ID: {RUN_ID} | SESSION: {SESSION_ID}")
    print("PAPER ONLY | V9.5B opposite-parent Level-2 and path-specific Thesis Shield are superseded.")
    print("")
    print("EMA30 = SPINE | EMA9 return slope + transfer + opposite build = ONE LEG")
    print("YES and NO evaluated every tactical cycle; parent is context only.")
    print("Mature old-side continuation disarmed on credible return slope.")
    print("Old side regains authority only after REGENERATION_CONFIRMED.")
    print("Target Height + Time Capacity + Rollover Continuity are inside the leg.")
    print("Failed target break/reclaim can immediately reverse tactical authority.")
    print("V9.5A Active Treasury = proposal only.")
    print("Every non-emergency exit passes Whole-Leg Exit Authority.")
    print("")
    print(f"LEG LOG      : {LEG_LOG}")
    print(f"TACTICAL LOG : {TACTICAL_LOG}")
    print(f"EXIT LOG     : {EXIT_LOG}")
    print(f"ROLLOVER LOG : {ROLLOVER_LOG}")
    print("="*118)
    await core.main()


if __name__=="__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTachyos V9.5C stopped by operator (Ctrl+C).")
