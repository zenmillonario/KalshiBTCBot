"""
TACHYOS V9.4K — FIELD MEDIC / FLEXIBLE CAGE / CHOP RESOLUTION LAB
================================================================

PAPER ONLY.  V9.4K imports V9.4J, installs every V9.4J observer unchanged,
then adds a second observer-only layer around the same frozen V9.4I paper engine.

NO V9.4K function may place, block, resize, flip, or close a paper trade.

Primary research questions:
  1) Can we distinguish a recoverable wound from a genuinely dead local thesis?
  2) How many realistic oscillation / rescue passes remain before settlement?
  3) Is price still inside a FLEXIBLE CAGE, merely overshooting it, or truly escaping?
  4) Can TARGET MIGRATION identify anchored chop vs a relocated battlefield?
  5) Can the DANCE OF DRAGONS be measured without requiring EMA9/EMA30 crosses?
  6) Does the first large excursion mark CHOP TERMINATION, and does its recoil
     reveal pioneer continuation vs failed invasion / authority transfer?
  7) After evacuation, can Tachyos keep watching the battlefield and identify
     a genuinely NEW thesis rather than confusing "eventually right" with
     "the original trade was still valid"?

Doctrine:
  - A wounded position is not automatically a dead position.
  - A dead position may be abandoned.  The battlefield is never abandoned.
  - Contract boundaries are clock overlays, not structural resets.
  - Flexible Cage edges are elastic; excursions are not automatically escapes.
  - First excursion is a transition alert, not a directional command.
  - All V9.4K outputs are SHADOW / RESEARCH ONLY.
"""

from __future__ import annotations

import asyncio
import csv
import math
import os
import statistics
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import tachys_v9_4j_looking_glass_arc_voyage_shadow as j

core = j.core

VERSION = "V9.4K"
ET = j.ET
_START_TS = time.time()
RUN_ID = datetime.now(ET).strftime("K%Y%m%d_%H%M%S")
SESSION_ID = f"{RUN_ID}_PID{os.getpid()}"

# K has its own ids, while J keeps its own J ids in the inherited telemetry.
os.environ["TACHYOS_V94K_RUN_ID"] = RUN_ID
os.environ["TACHYOS_V94K_SESSION_ID"] = SESSION_ID

COMMON = ["timestamp", "run_id", "session_id"]

FLEX_CAGE_LOG = "tachys_flexible_cage_v9_4k.csv"
FIELD_MEDIC_LOG = "tachys_field_medic_v9_4k.csv"
RESCUE_GLASS_LOG = "tachys_looking_glass_rescue_v9_4k.csv"
TARGET_MIGRATION_LOG = "tachys_target_migration_v9_4k.csv"
DRAGON_DANCE_LOG = "tachys_dragon_dance_v9_4k.csv"
CHOP_RESOLUTION_LOG = "tachys_chop_resolution_v9_4k.csv"
TIDE_CLOCK_LOG = "tachys_tide_clock_v9_4k.csv"
REENTRY_WATCH_LOG = "tachys_reentry_watch_v9_4k.csv"
MANIFEST_LOG = "tachys_run_manifest_v9_4k.csv"

FLEX_CAGE_FIELDS = COMMON + [
    "ticker","btc_price","target","ema9","ema30","range60","lookback_sec",
    "cage_low","cage_high","cage_center","cage_width","cage_state",
    "edge_distance","edge_overshoot","escape_direction","escape_evidence",
    "dragon_state","dragon_score","target_migration_state","trend_eff60",
    "price_arc_phase","arc_direction","seconds_left","reason"
]

FIELD_MEDIC_FIELDS = COMMON + [
    "event","trade_id","ticker","side","entry_ask","current_bid","roi",
    "wound_age_sec","wound_depth","lowest_bid","recovery_from_low",
    "recovery_fraction","medic_state","shadow_action","cage_state",
    "rescue_capacity","usable_half_swings","half_cycle_sec","next_favorable_eta_sec",
    "breakeven_gap","quote_beta_per_btc_dollar","btc_move_needed_for_breakeven",
    "recent_favorable_btc_leg","rescue_feasible","target_distance",
    "target_migration_state","dragon_state","battlefield_class",
    "price_arc_phase","arc_direction","boss_side","hand_side","seconds_left","reason"
]

RESCUE_GLASS_FIELDS = COMMON + [
    "trade_id","ticker","side","current_bid","entry_ask","roi","horizon",
    "half_cycle_sec","usable_half_swings","current_arc_direction",
    "current_arc_age_sec","next_favorable_eta_sec","recent_favorable_btc_leg",
    "btc_move_needed_for_breakeven","rescue_pass_score","lean_score",
    "adverse_escape_score","top_scenario","rescue_capacity","cage_state",
    "target_migration_state","dragon_state","seconds_left","reason"
]

TARGET_MIGRATION_FIELDS = COMMON + [
    "event","ticker","target","prior_target","step_1","net_2","net_3","net_4",
    "path_2","path_3","path_4","efficiency_2","efficiency_3","efficiency_4",
    "migration_state","anchored_under_15_hint","range60","battlefield_class","reason"
]

DRAGON_DANCE_FIELDS = COMMON + [
    "ticker","btc_price","ema9","ema30","ema_gap","ema_gap_norm60",
    "ema_gap_velocity","gap_velocity_reversals_120s","price_mid_crosses_120s",
    "ema_crosses_180s","target_migration_state","trend_eff60",
    "dragon_score","dragon_state","requires_ema_cross","reason"
]

CHOP_RESOLUTION_FIELDS = COMMON + [
    "event","ticker","arc_id","direction","arc_amplitude","arc_btc_move",
    "reference_amp","arc_expansion_ratio","prior_arc_direction",
    "prior_arc_amplitude","counterforce_ratio","dragon_state","cage_state",
    "target_migration_state","resolution_state","first_excursion_direction",
    "reason"
]

TIDE_CLOCK_FIELDS = COMMON + [
    "trade_id","ticker","side","seconds_left","target_distance",
    "half_cycle_sec","current_arc_direction","current_arc_age_sec",
    "half_swings_remaining","closing_swing","last_realistic_rescue",
    "price_arc_phase","battlefield_class","cage_state","reason"
]

REENTRY_FIELDS = COMMON + [
    "event","watch_id","trade_id","ticker","side","exit_bid","exit_roi","exit_pnl",
    "seconds_since_exit","current_bid","entry_ask","boss_side","hand_side",
    "arc_direction","price_arc_phase","cage_state","dragon_state",
    "target_distance","reclaim_score","watch_state","reason"
]

MANIFEST_FIELDS = COMMON + [
    "version","base_version","paper_authority","start_local","pid","research_layers","charter"
]


def _utc(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else ts
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _local(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else ts
    return datetime.fromtimestamp(ts, ET).isoformat()


def _f(x: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def _i(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _median(values, default=None):
    vals = []
    for v in values:
        try:
            v = float(v)
            if math.isfinite(v):
                vals.append(v)
        except Exception:
            pass
    return statistics.median(vals) if vals else default


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _sign(x: Optional[str]) -> int:
    if x in ("YES", "UP"):
        return 1
    if x in ("NO", "DOWN"):
        return -1
    return 0


def _write(path: str, fields: List[str], row: Dict[str, Any]) -> None:
    payload = {"timestamp": row.get("timestamp", _utc()), "run_id": RUN_ID,
               "session_id": SESSION_ID, **row}
    new = (not os.path.exists(path)) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: payload.get(k, "") for k in fields})


def _safe(obj: Any, *keys: str, default=None):
    if not isinstance(obj, dict):
        return default
    for k in keys:
        if k in obj and obj.get(k) not in (None, ""):
            return obj.get(k)
    return default


def _position_entry(pos: Dict[str, Any]) -> Optional[float]:
    return _f(_safe(pos, "entry_ask", "ask", "entry_price", "price", "fill_price"))


def _position_trade_id(pos: Dict[str, Any], fallback="") -> str:
    v = _safe(pos, "trade_id", "id", "paper_trade_id", "position_id")
    return str(v) if v not in (None, "") else str(fallback)


def _position_entry_ts(pos: Dict[str, Any]) -> Optional[float]:
    return _f(_safe(pos, "entry_ts", "opened_ts", "open_ts", "ts", "timestamp"))


def _side_bid(side: str, yes_ask, no_ask) -> Optional[float]:
    return j._side_bid(side, _f(yes_ask), _f(no_ask))


class V94KShadowBrain:
    def __init__(self):
        self.price_history = deque(maxlen=4000)
        self.side_bid_history = {"YES": deque(maxlen=1500), "NO": deque(maxlen=1500)}
        self.target_history = deque(maxlen=24)
        self.seen_target_tickers = set()

        self.last_flex_log = 0.0
        self.last_dragon_log = 0.0
        self.last_medic_log: Dict[str, float] = {}
        self.last_rescue_log: Dict[str, float] = {}
        self.last_tide_log: Dict[str, float] = {}

        self.last_dragon_state = None
        self.last_cage_state = None
        self.last_migration_state = "UNKNOWN"

        self.wounds: Dict[str, Dict[str, Any]] = {}
        self.reentry_watches: Dict[str, Dict[str, Any]] = {}
        self.watch_counter = 0

        self.first_excursion: Optional[Dict[str, Any]] = None
        self.last_completed_arc: Optional[Dict[str, Any]] = None

        self._write_manifest()

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------
    def on_tick(self, ticker, yes_ask=None, no_ask=None, close_ts=None, now=None):
        now = time.time() if now is None else float(now)
        # J has already run when K is attached outside J's council wrapper.
        s = dict(j.brain.last_snapshot or j.brain.snapshot(ticker, yes_ask, no_ask, close_ts, now))
        s["now"] = now
        s["ticker"] = ticker
        s["yes_ask"] = _f(yes_ask)
        s["no_ask"] = _f(no_ask)

        self._record_market_sample(s)
        self._target_migration(s)
        dragon = self._dragon_dance(s)
        cage = self._flexible_cage(s, dragon)

        s.update(dragon)
        s.update(cage)
        s["target_migration_state"] = self.last_migration_state

        self._field_medics(s)
        self._tide_clock(s)
        self._update_reentry_watches(s)

        if now - self.last_flex_log >= 6.0:
            self._log_flexible_cage(s)
            self.last_flex_log = now
        if now - self.last_dragon_log >= 9.0:
            self._log_dragon(s)
            self.last_dragon_log = now

    def _record_market_sample(self, s):
        now = s["now"]
        price = _f(s.get("btc_price"))
        ema9 = _f(s.get("ema9"))
        ema30 = _f(s.get("ema30"))
        target = _f(s.get("target"))
        if price is None:
            return
        midpoint = ((ema9 + ema30) / 2.0) if ema9 is not None and ema30 is not None else None
        gap = (ema9 - ema30) if ema9 is not None and ema30 is not None else None
        self.price_history.append({
            "ts": now, "price": price, "ema9": ema9, "ema30": ema30,
            "target": target, "midpoint": midpoint, "gap": gap,
            "gap_abs": abs(gap) if gap is not None else None,
            "rel_mid": (price - midpoint) if midpoint is not None else None,
        })
        for side in ("YES", "NO"):
            bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
            if bid is not None:
                self.side_bid_history[side].append({"ts": now, "bid": bid, "btc": price})

    # ------------------------------------------------------------------
    # Target Migration Clock
    # ------------------------------------------------------------------
    def _target_migration(self, s):
        ticker = str(s.get("ticker") or "")
        target = _f(s.get("target"))
        if not ticker or target is None or ticker in self.seen_target_tickers:
            return
        self.seen_target_tickers.add(ticker)
        prior = self.target_history[-1]["target"] if self.target_history else None
        self.target_history.append({"ticker": ticker, "target": target, "ts": s["now"]})

        vals = [x["target"] for x in self.target_history]
        def metrics(k):
            if len(vals) < k + 1:
                return (None, None, None)
            seg = vals[-(k+1):]
            steps = [seg[i] - seg[i-1] for i in range(1, len(seg))]
            net = seg[-1] - seg[0]
            path = sum(abs(x) for x in steps)
            eff = abs(net) / path if path > 1e-9 else 0.0
            return net, path, eff

        net2, path2, eff2 = metrics(2)
        net3, path3, eff3 = metrics(3)
        net4, path4, eff4 = metrics(4)
        step1 = target - prior if prior is not None else None

        # $15 is retained as the operator's exploratory observation, not authority.
        anchored_hint = int(net4 is not None and abs(net4) <= 15.0)
        state = "INSUFFICIENT_HISTORY"
        if net4 is not None:
            if anchored_hint or (eff4 is not None and eff4 <= 0.25):
                state = "ANCHORED_OR_WANDERING"
            elif eff4 is not None and eff4 >= 0.70 and abs(net4) >= 30.0:
                state = "DIRECTIONAL_MIGRATION"
            elif abs(net4) >= 45.0:
                state = "EDGE_RELOCATION"
            else:
                state = "SLOW_MIGRATION"
        elif step1 is not None:
            state = "SMALL_STEP" if abs(step1) <= 15.0 else "LARGE_STEP"

        self.last_migration_state = state
        _write(TARGET_MIGRATION_LOG, TARGET_MIGRATION_FIELDS, {
            "event": "NEW_TARGET", "ticker": ticker, "target": target,
            "prior_target": prior, "step_1": step1,
            "net_2": net2, "net_3": net3, "net_4": net4,
            "path_2": path2, "path_3": path3, "path_4": path4,
            "efficiency_2": eff2, "efficiency_3": eff3, "efficiency_4": eff4,
            "migration_state": state, "anchored_under_15_hint": anchored_hint,
            "range60": s.get("range60"), "battlefield_class": s.get("battlefield_class"),
            "reason": "raw target migration; $15 retained only as exploratory hint"
        })
        if prior is not None:
            print(f"🎯 TARGET MIGRATION | step={step1:+.2f} | 4C={net4 if net4 is not None else 'NA'} | {state}")

    # ------------------------------------------------------------------
    # Dance of Dragons — crossover NOT required
    # ------------------------------------------------------------------
    def _window(self, seconds, now):
        return [x for x in self.price_history if now - x["ts"] <= seconds]

    @staticmethod
    def _sign_changes(vals, eps=0.0):
        signs = []
        for v in vals:
            if v is None:
                continue
            if v > eps:
                sg = 1
            elif v < -eps:
                sg = -1
            else:
                continue
            if not signs or sg != signs[-1]:
                signs.append(sg)
        return max(0, len(signs)-1)

    def _dragon_dance(self, s):
        now = s["now"]
        r60 = max(1.0, _f(s.get("range60"), 1.0) or 1.0)
        w120 = self._window(120, now)
        w180 = self._window(180, now)

        gap = None
        if _f(s.get("ema9")) is not None and _f(s.get("ema30")) is not None:
            gap = _f(s.get("ema9")) - _f(s.get("ema30"))
        gap_abs = abs(gap) if gap is not None else None
        gap_norm = gap_abs / r60 if gap_abs is not None else None

        velocities = []
        prev = None
        for x in w120:
            if x.get("gap_abs") is None:
                continue
            if prev is not None:
                dt = max(0.25, x["ts"] - prev["ts"])
                velocities.append((x["gap_abs"] - prev["gap_abs"]) / dt)
            prev = x
        gap_vel = velocities[-1] if velocities else None
        vel_reversals = self._sign_changes(velocities, eps=max(0.03, 0.001*r60))
        mid_crosses = self._sign_changes([x.get("rel_mid") for x in w120], eps=max(0.5, 0.01*r60))
        ema_crosses = self._sign_changes([x.get("gap") for x in w180], eps=max(0.1, 0.002*r60))

        eff = _f(s.get("eff60"))
        score = 0
        reasons = []
        if gap_norm is not None and gap_norm <= 0.28:
            score += 2; reasons.append("small_ema_gap")
        if vel_reversals >= 2:
            score += 2; reasons.append("gap_breathing_reversals")
        if mid_crosses >= 2:
            score += 2; reasons.append("price_weaves_shared_ema_zone")
        if self.last_migration_state in ("ANCHORED_OR_WANDERING", "SMALL_STEP"):
            score += 2; reasons.append("target_anchored")
        if eff is not None and eff <= 0.48:
            score += 1; reasons.append("low_efficiency")
        if ema_crosses >= 1:
            score += 1; reasons.append("ema_cross_supporting_not_required")

        if score >= 6:
            state = "DRAGONS_ENTANGLED"
        elif score >= 4:
            state = "DRAGONS_SWIRLING"
        elif gap_norm is not None and gap_norm >= 0.55 and eff is not None and eff >= 0.55:
            state = "DRAGONS_SEPARATED"
        else:
            state = "DRAGONS_UNCLEAR"

        if state != self.last_dragon_state:
            print(f"🐉 DRAGON DANCE | {state} | score={score} | crosses={ema_crosses} | mid-weaves={mid_crosses}")
            self.last_dragon_state = state

        return {
            "ema_gap": gap, "ema_gap_norm60": gap_norm, "ema_gap_velocity": gap_vel,
            "gap_velocity_reversals_120s": vel_reversals,
            "price_mid_crosses_120s": mid_crosses, "ema_crosses_180s": ema_crosses,
            "dragon_score": score, "dragon_state": state,
            "dragon_reason": ";".join(reasons) or "insufficient_structure"
        }

    # ------------------------------------------------------------------
    # Flexible Cage — elastic edge, not a hard range
    # ------------------------------------------------------------------
    def _flexible_cage(self, s, dragon):
        now = s["now"]
        # Use older observations so the current poke does not instantly redraw its own cage.
        base = [x for x in self._window(180, now) if now - x["ts"] >= 9.0]
        prices = [x["price"] for x in base if x.get("price") is not None]
        if len(prices) < 12:
            return {
                "cage_low": None, "cage_high": None, "cage_center": None, "cage_width": None,
                "cage_state": "FORMING", "edge_distance": None, "edge_overshoot": None,
                "escape_direction": None, "escape_evidence": 0, "cage_reason": "insufficient_history"
            }
        lo, hi = min(prices), max(prices)
        center = _median(prices, (lo+hi)/2.0)
        width = max(1.0, hi-lo)
        price = _f(s.get("btc_price"))
        edge_zone = max(3.0, 0.15*width)
        soft_buffer = max(5.0, 0.22*width)

        state = "CENTER"
        edge_distance = min(abs(price-lo), abs(hi-price)) if price is not None else None
        overshoot = 0.0
        direction = None
        if price is not None:
            if lo <= price <= hi:
                state = "EDGE" if min(price-lo, hi-price) <= edge_zone else "CENTER"
            else:
                if price > hi:
                    overshoot = price-hi; direction = "UP"
                else:
                    overshoot = lo-price; direction = "DOWN"
                state = "SOFT_OVERSHOOT" if overshoot <= soft_buffer else "OUTSIDE_UNCONFIRMED"

        eff = _f(s.get("eff60"))
        gap_norm = _f(dragon.get("ema_gap_norm60"))
        arc_dir = s.get("arc_direction")
        evidence = 0
        reasons = []
        if direction and arc_dir == direction:
            evidence += 1; reasons.append("arc_points_out")
        if eff is not None and eff >= 0.58:
            evidence += 1; reasons.append("efficient_move")
        if gap_norm is not None and gap_norm >= 0.42:
            evidence += 1; reasons.append("ema_separation")
        if dragon.get("dragon_state") == "DRAGONS_SEPARATED":
            evidence += 1; reasons.append("dragons_separated")
        if self.last_migration_state in ("DIRECTIONAL_MIGRATION", "EDGE_RELOCATION"):
            evidence += 1; reasons.append("target_migrating")

        if state == "OUTSIDE_UNCONFIRMED" and evidence >= 3:
            state = "TRUE_ESCAPE_CANDIDATE"
        elif state == "OUTSIDE_UNCONFIRMED":
            state = "ELASTIC_OVERSHOOT"

        if state != self.last_cage_state:
            print(f"🧭 FLEXIBLE CAGE | {state} | escape={direction or '-'} | evidence={evidence}")
            self.last_cage_state = state

        return {
            "cage_low": lo, "cage_high": hi, "cage_center": center, "cage_width": width,
            "cage_state": state, "edge_distance": edge_distance, "edge_overshoot": overshoot,
            "escape_direction": direction, "escape_evidence": evidence,
            "cage_reason": ";".join(reasons) or "elastic_range_context"
        }

    # ------------------------------------------------------------------
    # Rescue geometry
    # ------------------------------------------------------------------
    def _half_cycle(self):
        arcs = list(j.brain.arc_history[-10:])
        durs = [_f(a.get("duration_sec")) for a in arcs]
        durs = [x for x in durs if x is not None and 6 <= x <= 600]
        return _median(durs[-6:], None)

    def _recent_favorable_leg(self, side):
        vals = []
        desired = "UP" if side == "YES" else "DOWN"
        for a in j.brain.arc_history[-10:]:
            if a.get("direction") != desired:
                continue
            m = _f(a.get("btc_move"))
            if m is not None:
                vals.append(abs(m))
        return _median(vals[-5:], None)

    def _quote_beta(self, side, now):
        hist = [x for x in self.side_bid_history[side] if now - x["ts"] <= 90]
        vals = []
        for a, b in zip(hist[:-1], hist[1:]):
            dbtc = abs(b["btc"] - a["btc"])
            dbid = abs(b["bid"] - a["bid"])
            if dbtc >= 1.0 and dbid > 0:
                vals.append(dbid / dbtc)
        return _median(vals[-30:], None)

    def _rescue_geometry(self, side, entry, bid, s):
        half = self._half_cycle()
        sec = _f(s.get("seconds_left"))
        arc_dir = s.get("arc_direction")
        arc_age = _f(s.get("arc_age_sec"), 0.0) or 0.0
        favorable_dir = "UP" if side == "YES" else "DOWN"

        usable = (sec / half) if sec is not None and half and half > 0 else None
        if half:
            eta = 0.0 if arc_dir == favorable_dir else max(3.0, half - min(arc_age, half))
        else:
            eta = None

        gap = max(0.0, entry-bid)
        beta = self._quote_beta(side, s["now"])
        btc_needed = (gap / beta) if beta and beta > 0 else None
        recent_leg = self._recent_favorable_leg(side)
        feasible = None
        if btc_needed is not None and recent_leg is not None and usable is not None:
            feasible = int(usable >= 0.75 and recent_leg >= 0.85*btc_needed)

        cage = s.get("cage_state")
        score = 0
        reasons = []
        if cage in ("CENTER","EDGE","SOFT_OVERSHOOT","ELASTIC_OVERSHOOT"):
            score += 2; reasons.append("cage_intact")
        if usable is not None:
            if usable >= 3:
                score += 2; reasons.append("many_half_swings")
            elif usable >= 1.3:
                score += 1; reasons.append("some_half_swings")
            elif usable < 0.7:
                score -= 2; reasons.append("clock_nearly_spent")
        if arc_dir == favorable_dir:
            score += 1; reasons.append("current_swing_favorable")
        if self.last_migration_state in ("ANCHORED_OR_WANDERING","SMALL_STEP"):
            score += 1; reasons.append("stationary_battlefield")
        if feasible == 1:
            score += 2; reasons.append("recent_leg_can_cover_gap")
        if cage == "TRUE_ESCAPE_CANDIDATE" and s.get("escape_direction") not in (None, favorable_dir):
            score -= 4; reasons.append("escape_against")

        if score >= 6:
            cap = "WIDE"
        elif score >= 3:
            cap = "MODERATE"
        elif score >= 1:
            cap = "LAST_OR_THIN"
        else:
            cap = "NONE"

        return {
            "half_cycle_sec": half, "usable_half_swings": usable,
            "next_favorable_eta_sec": eta, "breakeven_gap": gap,
            "quote_beta_per_btc_dollar": beta,
            "btc_move_needed_for_breakeven": btc_needed,
            "recent_favorable_btc_leg": recent_leg, "rescue_feasible": feasible,
            "rescue_capacity": cap, "rescue_score": score,
            "rescue_reason": ";".join(reasons)
        }

    # ------------------------------------------------------------------
    # Field Medic — distinguish wounded, healing, dead-local-thesis
    # ------------------------------------------------------------------
    def _field_medics(self, s):
        positions = getattr(core, "paper_positions", {}) or {}
        if not isinstance(positions, dict):
            return
        active_keys = set()
        for key, pos in list(positions.items()):
            if not isinstance(pos, dict):
                continue
            ticker = str(_safe(pos, "ticker", default=s.get("ticker")) or "")
            if ticker != s.get("ticker"):
                continue
            side = str(_safe(pos, "side", default=key) or key)
            if side not in ("YES","NO"):
                continue
            entry = _position_entry(pos)
            bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
            if entry is None or bid is None or entry <= 0:
                continue
            tid = _position_trade_id(pos, f"{ticker}:{side}:{entry:.4f}")
            pkey = f"{ticker}|{side}|{tid}"
            active_keys.add(pkey)
            roi = (bid-entry)/entry

            w = self.wounds.get(pkey)
            if roi < -0.01 and w is None:
                w = {
                    "start_ts": s["now"], "lowest_bid": bid, "start_bid": bid,
                    "entry": entry, "trade_id": tid, "ticker": ticker, "side": side,
                    "last_state": None, "recovered_once": False,
                }
                self.wounds[pkey] = w
                self._medic_event("WOUNDED", w, bid, roi, s, None,
                                  "position crossed into meaningful underwater state")
            if w is None:
                continue

            w["lowest_bid"] = min(_f(w.get("lowest_bid"), bid), bid)
            low = w["lowest_bid"]
            denom = max(0.001, entry-low)
            recovery = bid-low
            recovery_fraction = _clamp(recovery/denom, 0.0, 2.0)
            wound_age = s["now"] - w["start_ts"]
            geom = self._rescue_geometry(side, entry, bid, s)

            if roi >= 0:
                medic = "FIT_FOR_DUTY"
                action = "BACK_TO_BATTLE_SHADOW"
                reason = "quote recovered to entry-or-better"
                w["recovered_once"] = True
            elif recovery_fraction >= 0.65:
                medic = "HEALING"
                action = "PATIENCE_SHADOW"
                reason = "large recovery from wound low"
            elif recovery_fraction >= 0.25:
                medic = "STABILIZING"
                action = "STABILIZE_SHADOW"
                reason = "partial recovery from wound low"
            else:
                medic = "BLEEDING"
                action = "WATCH_RESCUE_SHADOW"
                reason = "little recovery from wound low"

            favorable_dir = "UP" if side == "YES" else "DOWN"
            escape_against = (
                s.get("cage_state") == "TRUE_ESCAPE_CANDIDATE"
                and s.get("escape_direction") not in (None, favorable_dir)
            )
            if escape_against and geom["rescue_capacity"] in ("NONE","LAST_OR_THIN"):
                medic = "LOCAL_THESIS_TERMINAL_CANDIDATE"
                action = "EVACUATE_SHADOW"
                reason = "true-escape evidence against + thin rescue capacity"
            elif geom["rescue_capacity"] == "NONE" and _f(s.get("seconds_left"), 9999) < 120 and roi < 0:
                medic = "CLOCK_CRITICAL"
                action = "EVACUATE_OR_LAST_PASS_SHADOW"
                reason = "insufficient clock for normal rescue cycle"

            if medic != w.get("last_state"):
                print(f"🩺 FIELD MEDIC | #{tid} {side} | {medic} | ROI={roi:+.1%} | rescue={geom['rescue_capacity']}")
                w["last_state"] = medic
                self._medic_event("STATE_CHANGE", w, bid, roi, s, geom, reason,
                                  medic_state=medic, shadow_action=action,
                                  recovery_fraction=recovery_fraction)

            # Periodic research row.
            if s["now"] - self.last_medic_log.get(pkey, 0) >= 9.0:
                self._medic_event("ASSESSMENT", w, bid, roi, s, geom, reason,
                                  medic_state=medic, shadow_action=action,
                                  recovery_fraction=recovery_fraction)
                self.last_medic_log[pkey] = s["now"]
            if s["now"] - self.last_rescue_log.get(pkey, 0) >= 9.0:
                self._rescue_glass(w, bid, roi, s, geom)
                self.last_rescue_log[pkey] = s["now"]

        # keep wound records through finalize hook; don't silently delete active data here

    def _medic_event(self, event, w, bid, roi, s, geom, reason,
                     medic_state=None, shadow_action=None, recovery_fraction=None):
        geom = geom or self._rescue_geometry(w["side"], w["entry"], bid, s)
        low = _f(w.get("lowest_bid"), bid)
        _write(FIELD_MEDIC_LOG, FIELD_MEDIC_FIELDS, {
            "event": event, "trade_id": w.get("trade_id"), "ticker": w.get("ticker"),
            "side": w.get("side"), "entry_ask": w.get("entry"), "current_bid": bid,
            "roi": roi, "wound_age_sec": max(0.0, s["now"]-w["start_ts"]),
            "wound_depth": max(0.0, (w["entry"]-low)/w["entry"]),
            "lowest_bid": low, "recovery_from_low": bid-low,
            "recovery_fraction": recovery_fraction,
            "medic_state": medic_state or w.get("last_state") or "WOUNDED",
            "shadow_action": shadow_action or "OBSERVE_SHADOW",
            "cage_state": s.get("cage_state"), "rescue_capacity": geom.get("rescue_capacity"),
            "usable_half_swings": geom.get("usable_half_swings"),
            "half_cycle_sec": geom.get("half_cycle_sec"),
            "next_favorable_eta_sec": geom.get("next_favorable_eta_sec"),
            "breakeven_gap": geom.get("breakeven_gap"),
            "quote_beta_per_btc_dollar": geom.get("quote_beta_per_btc_dollar"),
            "btc_move_needed_for_breakeven": geom.get("btc_move_needed_for_breakeven"),
            "recent_favorable_btc_leg": geom.get("recent_favorable_btc_leg"),
            "rescue_feasible": geom.get("rescue_feasible"),
            "target_distance": s.get("target_distance"),
            "target_migration_state": self.last_migration_state,
            "dragon_state": s.get("dragon_state"),
            "battlefield_class": s.get("battlefield_class"),
            "price_arc_phase": s.get("price_arc_phase"),
            "arc_direction": s.get("arc_direction"), "boss_side": s.get("boss_side"),
            "hand_side": s.get("hand_side"), "seconds_left": s.get("seconds_left"),
            "reason": reason + (";" + geom.get("rescue_reason","") if geom.get("rescue_reason") else "")
        })

    def _rescue_glass(self, w, bid, roi, s, geom):
        rescue = max(0.0, float(geom.get("rescue_score") or 0))
        lean = 0.0
        adverse = 0.0
        favorable = "UP" if w["side"] == "YES" else "DOWN"
        if s.get("arc_direction") == favorable:
            lean += 2
        if s.get("boss_side") == w["side"]:
            lean += 2
        if s.get("hand_side") == w["side"]:
            lean += 2
        if self.last_migration_state == "DIRECTIONAL_MIGRATION":
            if (_f(s.get("target_distance"), 0) or 0) * _sign(w["side"]) > 0:
                lean += 1
            else:
                adverse += 1
        if s.get("cage_state") == "TRUE_ESCAPE_CANDIDATE":
            if s.get("escape_direction") == favorable:
                lean += 2
            else:
                adverse += 4
        if s.get("dragon_state") == "DRAGONS_ENTANGLED":
            rescue += 1
        if geom.get("rescue_capacity") == "NONE":
            adverse += 2

        scores = {"RESCUE_PASS": rescue, "LEAN_DEVELOPMENT": lean, "ADVERSE_ESCAPE": adverse}
        top = max(scores, key=scores.get)
        _write(RESCUE_GLASS_LOG, RESCUE_GLASS_FIELDS, {
            "trade_id": w.get("trade_id"), "ticker": w.get("ticker"), "side": w.get("side"),
            "current_bid": bid, "entry_ask": w.get("entry"), "roi": roi,
            "horizon": "NEXT_PASS", "half_cycle_sec": geom.get("half_cycle_sec"),
            "usable_half_swings": geom.get("usable_half_swings"),
            "current_arc_direction": s.get("arc_direction"),
            "current_arc_age_sec": s.get("arc_age_sec"),
            "next_favorable_eta_sec": geom.get("next_favorable_eta_sec"),
            "recent_favorable_btc_leg": geom.get("recent_favorable_btc_leg"),
            "btc_move_needed_for_breakeven": geom.get("btc_move_needed_for_breakeven"),
            "rescue_pass_score": rescue, "lean_score": lean,
            "adverse_escape_score": adverse, "top_scenario": top,
            "rescue_capacity": geom.get("rescue_capacity"), "cage_state": s.get("cage_state"),
            "target_migration_state": self.last_migration_state,
            "dragon_state": s.get("dragon_state"), "seconds_left": s.get("seconds_left"),
            "reason": "scenario ranking only; not calibrated probability"
        })

    # ------------------------------------------------------------------
    # Tide Clock — closing swing vs remaining time
    # ------------------------------------------------------------------
    def _tide_clock(self, s):
        sec = _f(s.get("seconds_left"))
        if sec is None or sec > 180:
            return
        positions = getattr(core, "paper_positions", {}) or {}
        if not isinstance(positions, dict):
            return
        half = self._half_cycle()
        half_remaining = (sec/half) if half else None
        for key, pos in list(positions.items()):
            if not isinstance(pos, dict):
                continue
            side = str(_safe(pos, "side", default=key) or key)
            if side not in ("YES","NO"):
                continue
            ticker = str(_safe(pos, "ticker", default=s.get("ticker")) or "")
            if ticker != s.get("ticker"):
                continue
            tid = _position_trade_id(pos, f"{ticker}:{side}")
            pkey = f"{ticker}|{side}|{tid}"
            if s["now"] - self.last_tide_log.get(pkey, 0) < 3.0:
                continue
            self.last_tide_log[pkey] = s["now"]
            desired = "UP" if side == "YES" else "DOWN"
            phase = s.get("price_arc_phase")
            if phase in ("RETURN_TO_EMA9","CROSS_RESET"):
                swing = "TURN_WINDOW"
            elif s.get("arc_direction") == desired:
                swing = "SWING_FAVORABLE"
            elif s.get("arc_direction") in ("UP","DOWN"):
                swing = "SWING_ADVERSE"
            else:
                swing = "SWING_UNKNOWN"
            last = int(half_remaining is not None and half_remaining < 1.35)
            if last and swing == "SWING_FAVORABLE":
                print(f"🌊 TIDE CLOCK | #{tid} {side} | LAST REALISTIC RESCUE / favorable swing | {sec:.0f}s left")
            _write(TIDE_CLOCK_LOG, TIDE_CLOCK_FIELDS, {
                "trade_id": tid, "ticker": ticker, "side": side, "seconds_left": sec,
                "target_distance": s.get("target_distance"), "half_cycle_sec": half,
                "current_arc_direction": s.get("arc_direction"),
                "current_arc_age_sec": s.get("arc_age_sec"),
                "half_swings_remaining": half_remaining, "closing_swing": swing,
                "last_realistic_rescue": last, "price_arc_phase": phase,
                "battlefield_class": s.get("battlefield_class"),
                "cage_state": s.get("cage_state"),
                "reason": "time + local swing phase; settlement proxy remains separate"
            })

    # ------------------------------------------------------------------
    # Arc inflation / first excursion / violent counter-arc
    # ------------------------------------------------------------------
    def on_arc_complete(self, arc: Dict[str, Any], ticker: str, now=None):
        if not isinstance(arc, dict):
            return
        now = time.time() if now is None else float(now)
        amp = _f(arc.get("amplitude"), 0.0) or 0.0
        btc_move = _f(arc.get("btc_move"))
        recent = list(j.brain.arc_history[-8:])
        prior_amps = [_f(a.get("amplitude")) for a in recent[:-1] if _f(a.get("amplitude")) is not None]
        ref = _median(prior_amps[-5:], None)
        expansion = amp/ref if ref and ref > 0 else None

        prev = self.last_completed_arc
        counter = None
        if prev and prev.get("direction") != arc.get("direction"):
            pa = _f(prev.get("amplitude"))
            if pa and pa > 0:
                counter = amp/pa

        dragon = self.last_dragon_state or "UNKNOWN"
        cage = self.last_cage_state or "UNKNOWN"
        event = "ARC_COMPLETE"
        state = "NORMAL_ARC"
        reason = []
        if expansion is not None and expansion >= 1.50:
            event = "ARC_INFLATION"
            state = "FIRST_EXCURSION_ALERT" if dragon in ("DRAGONS_ENTANGLED","DRAGONS_SWIRLING") else "EXPANDING_ARC"
            reason.append("large_vs_recent_arcs")
            if self.first_excursion is None or now - self.first_excursion.get("ts",0) > 1800:
                self.first_excursion = {"ts": now, "direction": arc.get("direction"), "arc_id": arc.get("arc_id")}
        if counter is not None and counter >= 0.80:
            event = "VIOLENT_COUNTER_ARC"
            state = "EDGE_STRESS_TEST"
            reason.append("counter_arc_ge_80pct_prior")
            if self.first_excursion:
                reason.append("tests_first_excursion")

        if self.first_excursion and now - self.first_excursion["ts"] <= 900:
            if arc.get("direction") == self.first_excursion["direction"] and prev and prev.get("direction") != arc.get("direction") and counter is not None and counter < 0.75:
                state = "PIONEER_SIDE_REGENERATING"
                reason.append("same_side_rebuild_after_recoil")
            elif arc.get("direction") != self.first_excursion["direction"] and expansion is not None and expansion >= 1.30:
                state = "FAILED_INVASION_AUTHORITY_TRANSFER_CANDIDATE"
                reason.append("opposite_side_expands_after_first_excursion")

        _write(CHOP_RESOLUTION_LOG, CHOP_RESOLUTION_FIELDS, {
            "event": event, "ticker": ticker, "arc_id": arc.get("arc_id"),
            "direction": arc.get("direction"), "arc_amplitude": amp, "arc_btc_move": btc_move,
            "reference_amp": ref, "arc_expansion_ratio": expansion,
            "prior_arc_direction": prev.get("direction") if prev else None,
            "prior_arc_amplitude": prev.get("amplitude") if prev else None,
            "counterforce_ratio": counter, "dragon_state": dragon, "cage_state": cage,
            "target_migration_state": self.last_migration_state,
            "resolution_state": state,
            "first_excursion_direction": self.first_excursion.get("direction") if self.first_excursion else None,
            "reason": ";".join(reason) or "arc baseline"
        })
        if event != "ARC_COMPLETE":
            print(f"⚔️ CHOP RESOLUTION | {event} | {arc.get('direction')} | amp×{expansion:.2f}" if expansion else f"⚔️ CHOP RESOLUTION | {event}")
        self.last_completed_arc = dict(arc)

    # ------------------------------------------------------------------
    # Position exit: local thesis may die; battlefield watch continues
    # ------------------------------------------------------------------
    def on_trade_exit(self, position, bid, actual_roi, reason, pnl):
        if not isinstance(position, dict):
            return
        ticker = str(position.get("ticker") or (j.brain.last_snapshot or {}).get("ticker") or "")
        side = str(position.get("side") or "")
        if side not in ("YES","NO"):
            # Sometimes side is implicit in position store; infer from keys only if possible.
            for candidate in ("YES","NO"):
                if _position_entry(position) is not None:
                    # leave unknown rather than guess if no explicit side
                    pass
            return
        entry = _position_entry(position)
        tid = _position_trade_id(position, f"{ticker}:{side}")
        exit_bid = _f(bid)
        exit_roi = _f(actual_roi)
        exit_pnl = _f(pnl)
        pkey = f"{ticker}|{side}|{tid}"

        w = self.wounds.get(pkey)
        if w:
            s = dict(j.brain.last_snapshot or {})
            s["now"] = time.time()
            s["cage_state"] = self.last_cage_state
            s["dragon_state"] = self.last_dragon_state
            s["target_migration_state"] = self.last_migration_state
            self._medic_event("EVACUATED", w, exit_bid or 0.0, exit_roi or 0.0, s, None,
                              f"paper authority exit preserved:{reason}",
                              medic_state="EVACUATED_LOCAL_THESIS",
                              shadow_action="BATTLEFIELD_WATCH_CONTINUES")
            self.wounds.pop(pkey, None)

        # Negative/scratch exits become re-entry watches. Winners can be studied elsewhere.
        if (exit_pnl is not None and exit_pnl <= 0.0) or (exit_roi is not None and exit_roi <= 0.0):
            self.watch_counter += 1
            wid = f"RW{self.watch_counter:05d}"
            self.reentry_watches[wid] = {
                "watch_id": wid, "trade_id": tid, "ticker": ticker, "side": side,
                "entry_ask": entry, "exit_bid": exit_bid, "exit_roi": exit_roi,
                "exit_pnl": exit_pnl, "exit_ts": time.time(), "last_state": "EVACUATED_WATCHING"
            }
            self._reentry_event(self.reentry_watches[wid], j.brain.last_snapshot or {},
                                "EVACUATED_WATCHING", 0, f"local position ended:{reason}")

    def _update_reentry_watches(self, s):
        now = s["now"]
        dead = []
        for wid, w in list(self.reentry_watches.items()):
            age = now - w["exit_ts"]
            if age > 900 or (w.get("ticker") and w["ticker"] != s.get("ticker") and age > 180):
                dead.append(wid)
                continue
            if w.get("ticker") != s.get("ticker"):
                continue
            side = w["side"]
            bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
            if bid is None:
                continue
            score = 0
            reasons = []
            desired = "UP" if side == "YES" else "DOWN"
            if s.get("boss_side") == side:
                score += 2; reasons.append("boss_reclaims_side")
            if s.get("hand_side") == side:
                score += 2; reasons.append("hand_reclaims_side")
            if s.get("arc_direction") == desired:
                score += 1; reasons.append("arc_points_side")
            td = _f(s.get("target_distance"))
            if td is not None and td * _sign(side) > 0:
                score += 1; reasons.append("btc_on_side_of_target")
            if w.get("exit_bid") is not None and bid >= float(w["exit_bid"]) + 0.08:
                score += 1; reasons.append("quote_reclaims_exit_plus8c")
            if self.last_cage_state in ("CENTER","EDGE","SOFT_OVERSHOOT","ELASTIC_OVERSHOOT"):
                score += 1; reasons.append("battlefield_still_revisitable")

            if score >= 6:
                state = "NEW_THESIS_CANDIDATE"
            elif score >= 4:
                state = "TERRITORY_RECLAIMED_WATCH"
            elif score >= 2:
                state = "RECLAMATION_STIRRING"
            else:
                state = "EVACUATED_WATCHING"

            if state != w.get("last_state"):
                self._reentry_event(w, s, state, score, ";".join(reasons) or "no reclaim")
                w["last_state"] = state
                if state == "NEW_THESIS_CANDIDATE":
                    print(f"🕯️ RE-ENTRY WATCH | #{w['trade_id']} {side} | NEW THESIS CANDIDATE | score={score}")
        for wid in dead:
            self.reentry_watches.pop(wid, None)

    def _reentry_event(self, w, s, state, score, reason):
        side = w.get("side")
        bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask")) if isinstance(s, dict) else None
        _write(REENTRY_WATCH_LOG, REENTRY_FIELDS, {
            "event": "STATE", "watch_id": w.get("watch_id"), "trade_id": w.get("trade_id"),
            "ticker": w.get("ticker"), "side": side, "exit_bid": w.get("exit_bid"),
            "exit_roi": w.get("exit_roi"), "exit_pnl": w.get("exit_pnl"),
            "seconds_since_exit": max(0.0, time.time()-w.get("exit_ts", time.time())),
            "current_bid": bid, "entry_ask": w.get("entry_ask"),
            "boss_side": s.get("boss_side") if isinstance(s,dict) else None,
            "hand_side": s.get("hand_side") if isinstance(s,dict) else None,
            "arc_direction": s.get("arc_direction") if isinstance(s,dict) else None,
            "price_arc_phase": s.get("price_arc_phase") if isinstance(s,dict) else None,
            "cage_state": self.last_cage_state, "dragon_state": self.last_dragon_state,
            "target_distance": s.get("target_distance") if isinstance(s,dict) else None,
            "reclaim_score": score, "watch_state": state,
            "reason": reason + ";new thesis required before any future authority"
        })

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------
    def _log_flexible_cage(self, s):
        _write(FLEX_CAGE_LOG, FLEX_CAGE_FIELDS, {
            "ticker": s.get("ticker"), "btc_price": s.get("btc_price"), "target": s.get("target"),
            "ema9": s.get("ema9"), "ema30": s.get("ema30"), "range60": s.get("range60"),
            "lookback_sec": 180, "cage_low": s.get("cage_low"), "cage_high": s.get("cage_high"),
            "cage_center": s.get("cage_center"), "cage_width": s.get("cage_width"),
            "cage_state": s.get("cage_state"), "edge_distance": s.get("edge_distance"),
            "edge_overshoot": s.get("edge_overshoot"), "escape_direction": s.get("escape_direction"),
            "escape_evidence": s.get("escape_evidence"), "dragon_state": s.get("dragon_state"),
            "dragon_score": s.get("dragon_score"), "target_migration_state": self.last_migration_state,
            "trend_eff60": s.get("eff60"), "price_arc_phase": s.get("price_arc_phase"),
            "arc_direction": s.get("arc_direction"), "seconds_left": s.get("seconds_left"),
            "reason": s.get("cage_reason")
        })

    def _log_dragon(self, s):
        _write(DRAGON_DANCE_LOG, DRAGON_DANCE_FIELDS, {
            "ticker": s.get("ticker"), "btc_price": s.get("btc_price"),
            "ema9": s.get("ema9"), "ema30": s.get("ema30"),
            "ema_gap": s.get("ema_gap"), "ema_gap_norm60": s.get("ema_gap_norm60"),
            "ema_gap_velocity": s.get("ema_gap_velocity"),
            "gap_velocity_reversals_120s": s.get("gap_velocity_reversals_120s"),
            "price_mid_crosses_120s": s.get("price_mid_crosses_120s"),
            "ema_crosses_180s": s.get("ema_crosses_180s"),
            "target_migration_state": self.last_migration_state,
            "trend_eff60": s.get("eff60"), "dragon_score": s.get("dragon_score"),
            "dragon_state": s.get("dragon_state"), "requires_ema_cross": 0,
            "reason": s.get("dragon_reason")
        })

    def _write_manifest(self):
        _write(MANIFEST_LOG, MANIFEST_FIELDS, {
            "version": VERSION, "base_version": "V9.4J -> V9.4I frozen paper authority",
            "paper_authority": "FROZEN_BASE_ONLY", "start_local": _local(_START_TS),
            "pid": os.getpid(),
            "research_layers": "FLEXIBLE_CAGE;FIELD_MEDIC;RESCUE_GLASS;TARGET_MIGRATION;"
                               "DRAGON_DANCE;CHOP_RESOLUTION;TIDE_CLOCK;REENTRY_WATCH",
            "charter": "A dead position may be abandoned. The battlefield is never abandoned."
        })


brain = V94KShadowBrain()
_HOOKS_INSTALLED = False


def install_hooks():
    """
    Install J first, then wrap J's already-wrapped core callbacks.
    Every original return value is preserved.  K has no paper authority.
    """
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    j.install_hooks()
    _HOOKS_INSTALLED = True

    original_council = getattr(core, "v94e_kings_council_observer")
    def council_wrapper(ticker, yes_ask, no_ask, close_ts, now=None):
        result = original_council(ticker, yes_ask, no_ask, close_ts, now)
        try:
            brain.on_tick(ticker, yes_ask, no_ask, close_ts, now)
        except Exception as exc:
            print(f"⚠️ V9.4K Field Medic tick shadow error: {exc}")
        return result
    core.v94e_kings_council_observer = council_wrapper

    original_complete_arc = getattr(core, "_v93a_complete_arc")
    def complete_arc_wrapper(now, ticker, yes_ask, no_ask, target, r60, r180):
        row = original_complete_arc(now, ticker, yes_ask, no_ask, target, r60, r180)
        if isinstance(row, dict):
            try:
                brain.on_arc_complete(row, ticker, now)
            except Exception as exc:
                print(f"⚠️ V9.4K chop-resolution shadow error: {exc}")
        return row
    core._v93a_complete_arc = complete_arc_wrapper

    original_finalize = getattr(core, "v94b_finalize_trade_shadows")
    def finalize_wrapper(position, bid, actual_roi, reason, pnl):
        result = original_finalize(position, bid, actual_roi, reason, pnl)
        try:
            brain.on_trade_exit(position, bid, actual_roi, reason, pnl)
        except Exception as exc:
            print(f"⚠️ V9.4K Field Medic finalize shadow error: {exc}")
        return result
    core.v94b_finalize_trade_shadows = finalize_wrapper


async def main():
    install_hooks()
    print("=" * 94)
    print(f"TACHYOS {VERSION} — FIELD MEDIC / FLEXIBLE CAGE / CHOP RESOLUTION LAB")
    print(f"RUN ID: {RUN_ID} | SESSION: {SESSION_ID}")
    print("PAPER ONLY | V9.4I paper authority remains frozen | V9.4J + V9.4K are shadow intelligence.")
    print("Priority: recoverable wound vs dead local thesis; rescue capacity; target migration; Dragon Dance;")
    print("          first excursion / recoil; Tide Clock; and NEW-thesis re-entry watch after evacuation.")
    print("CHARTER: A dead position may be abandoned. The battlefield is never abandoned.")
    print("=" * 94)
    await core.main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTachyos V9.4K stopped by operator (Ctrl+C).")
