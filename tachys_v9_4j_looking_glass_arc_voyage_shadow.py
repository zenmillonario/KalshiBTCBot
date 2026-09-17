"""
TACHYOS V9.4J — LOOKING GLASS / ARC VOYAGE SHADOW BRAIN
=========================================================

PAPER ONLY.  V9.4J imports the frozen V9.4I engine and attaches observer-only
hooks around existing observer callbacks.  It does NOT grant V9.4J authority to
place, block, resize, flip, or close paper trades.

Research added in V9.4J:
  * persistent run/session id for all V9.4J telemetry
  * PRICE–ARC PHASE + remaining-capacity estimate
  * ENTRY TIMING SHADOW (including WAIT_EMA9_REACTION)
  * ARC ECHO + ARC GRAMMAR / motif memory
  * ARC VOYAGE / SNAKE: LAUNCH -> BODY -> RELEASE
  * BATTLEFIELD CLASS + MICRO/MACRO/BOTH ZOOM GOVERNOR
  * LOOKING GLASS scenario rehearsal + outcome calibration
  * 6/12-contract WAR REPORT
  * ROLLOVER RHYTHM / rollover arc phase
  * PROFIT-LOCK ARC SHIELD shadow + post-exit follow-through

Design doctrine:
  - Three shapes mean SHOWTIME / transition attention, not automatic reversal.
  - Contract boundaries are clock overlays, not structural resets.
  - A direction can be locally correct while the current arc has little edge left.
  - Churn is a battlefield species, not a single condition.
  - All confidence values here are SHADOW research scores until calibrated by outcomes.
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

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

import tachys_v9_4i_rearm_crest_orbit_shadow as core


# ============================================================================
# VERSION / SESSION
# ============================================================================

VERSION = "V9.4J"
ET = ZoneInfo("America/New_York") if ZoneInfo else timezone.utc
_START_TS = time.time()
RUN_ID = datetime.now(ET).strftime("J%Y%m%d_%H%M%S")
SESSION_ID = f"{RUN_ID}_PID{os.getpid()}"
os.environ["TACHYOS_RUN_ID"] = RUN_ID
os.environ["TACHYOS_SESSION_ID"] = SESSION_ID


# ============================================================================
# LOGS — all V9.4J files include run_id/session_id
# ============================================================================

PRICE_ARC_LOG = "tachys_price_arc_phase_v9_4j.csv"
ENTRY_TIMING_LOG = "tachys_entry_timing_v9_4j.csv"
ARC_ECHO_LOG = "tachys_arc_echo_v9_4j.csv"
ARC_GRAMMAR_LOG = "tachys_arc_grammar_v9_4j.csv"
VOYAGE_LOG = "tachys_arc_voyage_v9_4j.csv"
BATTLEFIELD_LOG = "tachys_battlefield_zoom_v9_4j.csv"
LOOKING_GLASS_LOG = "tachys_looking_glass_v9_4j.csv"
WAR_REPORT_LOG = "tachys_war_report_v9_4j.csv"
ROLLOVER_RHYTHM_LOG = "tachys_rollover_rhythm_v9_4j.csv"
PROFIT_LOCK_SHIELD_LOG = "tachys_profit_lock_arc_shield_v9_4j.csv"
RUN_MANIFEST_LOG = "tachys_run_manifest_v9_4j.csv"

COMMON = ["timestamp", "run_id", "session_id"]

PRICE_ARC_FIELDS = COMMON + [
    "ticker", "btc_price", "ema9", "ema30", "target", "range60", "arc_id",
    "arc_direction", "arc_age_sec", "price_ema9_sep", "signed_sep",
    "signed_sep_norm60", "sep_velocity_6s", "price_velocity_6s",
    "peak_signed_sep", "current_arc_amp", "reference_amp", "remaining_capacity",
    "price_arc_phase", "territory_efficiency", "battlefield_class", "zoom_mode",
    "boss_id", "boss_side", "hand_side", "seconds_left"
]

ENTRY_TIMING_FIELDS = COMMON + [
    "event", "trade_id", "ticker", "side", "ask", "strategy", "mission",
    "price_arc_phase", "arc_direction", "remaining_capacity", "signed_sep_norm60",
    "timing_shadow", "battlefield_class", "zoom_mode", "boss_id", "boss_side",
    "hand_side", "seconds_left", "reason"
]

ARC_ECHO_FIELDS = COMMON + [
    "arc_id", "ticker", "direction", "amplitude", "duration_sec", "btc_move",
    "echo_arc_id", "echo_ticker", "echo_score", "amplitude_ratio", "duration_ratio",
    "btc_move_ratio", "lag_arcs", "lag_contracts", "echo_class", "ema30_match",
    "parent_match", "progression_match", "remaining_capacity_at_completion"
]

ARC_GRAMMAR_FIELDS = COMMON + [
    "event", "arc_id", "ticker", "token", "motif", "motif_length",
    "three_shape_spotlight", "double_lobe_bridge", "boss_id", "boss_side",
    "battlefield_class", "reason"
]

VOYAGE_FIELDS = COMMON + [
    "event", "voyage_id", "phase", "ticker", "launch_direction", "latest_arc_id",
    "latest_arc_direction", "latest_arc_amp", "arc_count", "body_arc_count",
    "contracts_seen", "age_sec", "maturity", "release_score", "boss_id",
    "boss_side", "battlefield_class", "btc_start", "btc_now", "net_btc_move",
    "reason"
]

BATTLEFIELD_FIELDS = COMMON + [
    "ticker", "battlefield_class", "territory_state", "churn_type", "box_location",
    "trend_efficiency60", "range60", "price_arc_phase", "remaining_capacity",
    "snake_phase", "snake_maturity", "zoom_mode", "zoom_reason", "target_distance",
    "target_distance_norm60", "boss_id", "boss_side", "hand_side", "handshake_phase",
    "seconds_left"
]

LOOKING_GLASS_FIELDS = COMMON + [
    "event", "glass_id", "ticker", "horizon_sec", "btc_start", "boss_id_start",
    "boss_side_start", "hand_side_start", "battlefield_start", "snake_phase_start",
    "price_arc_phase_start", "continuation_score", "storm_score", "transfer_score",
    "continuation_pct", "storm_pct", "transfer_pct", "top_scenario", "shadow_confidence_pct",
    "calibration_n", "rolling_accuracy_pct", "actual_outcome", "correct", "btc_end",
    "btc_signed_for_boss", "boss_side_end", "hand_side_end", "battlefield_end", "reason"
]

WAR_REPORT_FIELDS = COMMON + [
    "window_contracts", "contracts_count", "first_ticker", "last_ticker", "trades",
    "wins", "losses", "scratches", "win_rate_pct", "pnl", "gross_win", "gross_loss",
    "profit_factor", "avg_win", "avg_loss", "casualties_le_minus5", "raid_trades",
    "raid_pnl", "campaign_trades", "campaign_pnl", "attack_trades", "attack_pnl",
    "scout_trades", "scout_pnl", "storm_trades", "clear_trades", "bosses_seen",
    "war_state", "note"
]

ROLLOVER_FIELDS = COMMON + [
    "event", "ticker", "seconds_left", "threshold", "btc_price", "ema9", "ema30",
    "target", "target_distance", "arc_id", "arc_direction", "price_arc_phase",
    "rhythm_position", "sep_norm60", "sep_velocity_6s", "remaining_capacity",
    "battlefield_class", "zoom_mode", "boss_id", "boss_side", "hand_side",
    "boundary_read_shadow"
]

PROFIT_LOCK_FIELDS = COMMON + [
    "event", "trade_id", "ticker", "side", "exit_reason", "entry_ask", "exit_bid",
    "actual_roi", "actual_pnl", "price_arc_phase", "arc_direction", "remaining_capacity",
    "battlefield_class", "boss_id", "boss_side", "hand_side", "profit_topology",
    "shield_read", "horizon_sec", "later_bid", "bid_change", "hypothetical_roi_change",
    "btc_exit", "btc_later", "reason"
]

MANIFEST_FIELDS = COMMON + [
    "version", "base_version", "paper_authority", "start_local", "pid", "python_note",
    "research_layers"
]


# ============================================================================
# UTILITY
# ============================================================================

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


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _sign(side_or_direction: Optional[str]) -> int:
    if side_or_direction in ("YES", "UP"):
        return 1
    if side_or_direction in ("NO", "DOWN"):
        return -1
    return 0


def _median(values: List[float], default: Optional[float] = None) -> Optional[float]:
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return statistics.median(vals) if vals else default


def _safe_call(name: str, *args, default=None, **kwargs):
    fn = getattr(core, name, None)
    if not callable(fn):
        return default
    try:
        return fn(*args, **kwargs)
    except Exception:
        return default


def _write(path: str, fields: List[str], row: Dict[str, Any]) -> None:
    payload = {"timestamp": row.get("timestamp", _utc()), "run_id": RUN_ID, "session_id": SESSION_ID, **row}
    new = (not os.path.exists(path)) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: payload.get(k, "") for k in fields})


def _active_target() -> Optional[float]:
    active = getattr(core, "active_target", None)
    parse = getattr(core, "parse_target_price", None)
    if callable(parse):
        try:
            return _f(parse(active))
        except Exception:
            pass
    return _f(active)


def _range60(now: float) -> Optional[float]:
    v = _safe_call("btc_range", 60, now, default=None)
    if v is None:
        v = _safe_call("btc_range", 60, default=None)
    return _f(v)


def _change(seconds: int, now: float) -> Optional[float]:
    v = _safe_call("btc_change", seconds, now, default=None)
    if v is None:
        v = _safe_call("btc_change", seconds, default=None)
    return _f(v)


def _eff60(now: float) -> Optional[float]:
    v = _safe_call("btc_trend_efficiency", 60, 5, now, default=None)
    if v is None:
        v = _safe_call("btc_trend_efficiency", 60, 5, default=None)
    return _f(v)


def _mission_from_position(position: Dict[str, Any]) -> str:
    st = position.get("_v94g_mission") or {}
    return str(st.get("mission") or position.get("mission") or "UNKNOWN")


def _profit_topology_from_position(position: Dict[str, Any]) -> str:
    for key in ("_v94d_profit_topology", "_v94d_profit", "profit_topology"):
        obj = position.get(key)
        if isinstance(obj, dict):
            for k in ("state", "topology", "classification", "latest"):
                if obj.get(k):
                    return str(obj.get(k))
        elif obj:
            return str(obj)
    latest = getattr(core, "v94d_latest_profit_topology", None)
    if isinstance(latest, dict):
        return str(latest.get("state") or latest.get("topology") or "UNKNOWN")
    return "UNKNOWN"


def _current_context() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    border = getattr(core, "v94g_latest_border", None) or {}
    boss = getattr(core, "v94h_boss", None) or {}
    hand = getattr(core, "v94e_latest_regime", None) or {}
    orbit_state = getattr(core, "v94h_orbit_state", None) or {}
    orbit = orbit_state.get("latest") if isinstance(orbit_state, dict) else {}
    return border, boss, hand, orbit or {}


def _side_bid(side: str, yes_ask: Optional[float], no_ask: Optional[float]) -> Optional[float]:
    if side == "YES" and no_ask is not None:
        return 1.0 - float(no_ask)
    if side == "NO" and yes_ask is not None:
        return 1.0 - float(yes_ask)
    return None


# ============================================================================
# V9.4J SHADOW BRAIN
# ============================================================================

class V94JShadowBrain:
    def __init__(self) -> None:
        self.last_tick_log = 0.0
        self.last_battle_log = 0.0
        self.last_glass_ts = 0.0
        self.last_glass_key = None
        self.glass_counter = 0
        self.glass_pending: List[Dict[str, Any]] = []
        self.glass_outcomes = 0
        self.glass_correct = 0

        self.sep_history: deque = deque(maxlen=900)
        self.current_arc_id = None
        self.arc_peak_signed_sep = 0.0
        self.arc_history: List[Dict[str, Any]] = []
        self.grammar_tokens: deque = deque(maxlen=12)

        self.voyage_counter = 0
        self.voyage: Optional[Dict[str, Any]] = None

        self.last_ticker: Optional[str] = None
        self.contracts: deque = deque(maxlen=64)
        self.current_contract: Optional[Dict[str, Any]] = None
        self.trade_events: List[Dict[str, Any]] = []
        self.boss_ids_seen: set = set()

        self.rollover_seen: Dict[str, set] = defaultdict(set)
        self.pending_profit_locks: List[Dict[str, Any]] = []
        self.last_snapshot: Dict[str, Any] = {}

        self._write_manifest()

    # ------------------------------------------------------------------
    # Core state snapshot
    # ------------------------------------------------------------------
    def snapshot(self, ticker: str, yes_ask=None, no_ask=None, close_ts=None, now=None) -> Dict[str, Any]:
        now = time.time() if now is None else float(now)
        price = _f(getattr(core, "btc_last_price", None))
        ema9 = _f(getattr(core, "btc_ema_9", None))
        ema30 = _f(getattr(core, "btc_ema_30", None))
        target = _active_target()
        r60 = max(1.0, _range60(now) or 1.0)
        eff = _eff60(now)
        cur_arc = getattr(core, "v93a_current_arc", None) or {}
        arc_id = cur_arc.get("arc_id")
        arc_dir = cur_arc.get("direction")

        if arc_dir not in ("UP", "DOWN"):
            arc_state = _safe_call("ema9_arc_state", now, default={}) or {}
            arc_dir = arc_state.get("direction")

        sign = _sign(arc_dir)
        sep = (price - ema9) if price is not None and ema9 is not None else None
        signed_sep = sep * sign if sep is not None and sign else None
        sep_norm = signed_sep / r60 if signed_sep is not None else None

        if arc_id != self.current_arc_id:
            self.current_arc_id = arc_id
            self.arc_peak_signed_sep = max(0.0, signed_sep or 0.0)
        elif signed_sep is not None:
            self.arc_peak_signed_sep = max(self.arc_peak_signed_sep, signed_sep)

        self.sep_history.append({"ts": now, "signed_sep": signed_sep, "sep": sep, "price": price})
        ago = self._sep_ago(now, 6.0)
        sep_vel = None
        if ago is not None and signed_sep is not None and ago.get("signed_sep") is not None:
            dt = max(0.25, now - float(ago["ts"]))
            sep_vel = (signed_sep - float(ago["signed_sep"])) / dt
        ch6 = _change(6, now)
        price_vel = (ch6 / 6.0 * sign) if ch6 is not None and sign else None

        age = None
        if cur_arc.get("start_ts") is not None:
            age = max(0.0, now - float(cur_arc.get("start_ts")))

        current_amp = None
        start_e9 = _f(cur_arc.get("start_ema9"))
        if ema9 is not None and start_e9 is not None:
            current_amp = abs(ema9 - start_e9)

        same_amps = [
            _f(x.get("amplitude")) for x in self.arc_history[-20:]
            if x.get("direction") == arc_dir and _f(x.get("amplitude")) is not None
        ]
        reference_amp = _median(same_amps[-6:], default=None)
        if reference_amp is None:
            core_arcs = getattr(core, "v93a_completed_arcs", None) or []
            same_amps = [
                _f(x.get("amplitude")) for x in core_arcs[-20:]
                if isinstance(x, dict) and x.get("direction") == arc_dir and _f(x.get("amplitude")) is not None
            ]
            reference_amp = _median(same_amps[-6:], default=None)

        remaining = None
        if current_amp is not None and reference_amp and reference_amp > 0:
            remaining = _clamp(1.0 - current_amp / reference_amp)

        phase = self._price_arc_phase(
            arc_dir=arc_dir, age=age, signed_sep=signed_sep, sep_norm=sep_norm,
            sep_vel=sep_vel, price_vel=price_vel, r60=r60
        )
        if remaining is not None:
            if phase == "RETURN_TO_EMA9":
                remaining *= 0.45
            elif phase == "CROSS_RESET":
                remaining *= 0.10
            elif phase == "PEAK_TROUGH_BUILD":
                remaining *= 0.70
            remaining = _clamp(remaining)

        start_btc = _f(cur_arc.get("start_btc"))
        territory_eff = None
        if price is not None and start_btc is not None and current_amp is not None and current_amp > 0:
            territory_eff = abs(price - start_btc) / max(current_amp, 1.0)

        border, boss, hand, orbit = _current_context()
        battlefield = self._battlefield_class(border, eff, phase)
        target_distance = (price - target) if price is not None and target is not None else None
        target_norm = target_distance / r60 if target_distance is not None else None
        seconds_left = max(0.0, float(close_ts) - now) if isinstance(close_ts, (int, float)) else None
        snake_phase = (self.voyage or {}).get("phase", "NONE")
        snake_maturity = (self.voyage or {}).get("maturity", "NONE")
        zoom, zoom_reason = self._zoom_mode(
            battlefield, phase, target_norm, seconds_left, boss, hand, snake_phase, snake_maturity
        )

        snap = {
            "ticker": ticker, "now": now, "btc_price": price, "ema9": ema9, "ema30": ema30,
            "target": target, "range60": r60, "eff60": eff, "arc_id": arc_id,
            "arc_direction": arc_dir, "arc_age_sec": age, "price_ema9_sep": sep,
            "signed_sep": signed_sep, "signed_sep_norm60": sep_norm, "sep_velocity_6s": sep_vel,
            "price_velocity_6s": price_vel, "peak_signed_sep": self.arc_peak_signed_sep,
            "current_arc_amp": current_amp, "reference_amp": reference_amp,
            "remaining_capacity": remaining, "price_arc_phase": phase,
            "territory_efficiency": territory_eff, "battlefield_class": battlefield,
            "zoom_mode": zoom, "zoom_reason": zoom_reason, "boss_id": boss.get("id"),
            "boss_side": boss.get("side"), "boss_state": boss.get("state"),
            "hand_side": hand.get("authority_side"), "handshake_phase": hand.get("handshake_phase"),
            "territory_state": border.get("territory_state"), "churn_type": border.get("churn_type"),
            "box_location": border.get("box_location") or border.get("location"),
            "orbit": orbit, "seconds_left": seconds_left, "target_distance": target_distance,
            "target_distance_norm60": target_norm, "yes_ask": _f(yes_ask), "no_ask": _f(no_ask),
            "snake_phase": snake_phase, "snake_maturity": snake_maturity,
        }
        self.last_snapshot = snap
        return snap

    def _sep_ago(self, now: float, seconds: float) -> Optional[Dict[str, Any]]:
        if not self.sep_history:
            return None
        target = now - seconds
        return min(self.sep_history, key=lambda x: abs(float(x["ts"]) - target))

    @staticmethod
    def _price_arc_phase(arc_dir, age, signed_sep, sep_norm, sep_vel, price_vel, r60) -> str:
        if arc_dir not in ("UP", "DOWN") or signed_sep is None:
            return "UNKNOWN"
        eps_v = max(0.15, 0.01 * r60)
        norm = sep_norm or 0.0
        if age is not None and age <= 18 and norm > -0.08:
            return "LAUNCH"
        if signed_sep <= 0:
            return "CROSS_RESET"
        if sep_vel is not None and sep_vel < -eps_v:
            return "RETURN_TO_EMA9"
        if norm >= 0.12 and sep_vel is not None and abs(sep_vel) <= eps_v:
            return "PEAK_TROUGH_BUILD"
        if (sep_vel is not None and sep_vel > eps_v) or (price_vel is not None and price_vel > eps_v):
            return "EXTENSION"
        if norm >= 0.05:
            return "EXTENSION_SLOW"
        return "BASE_BUILD"

    @staticmethod
    def _battlefield_class(border: Dict[str, Any], eff60: Optional[float], phase: str) -> str:
        territory = str(border.get("territory_state") or "UNKNOWN")
        churn = str(border.get("churn_type") or "NONE")
        if territory == "CHURN_ACTIVE":
            if churn == "METRONOME_CHURN":
                return "METRONOME_STORM"
            if churn == "COMPRESSION_CHURN":
                return "COMPRESSION_STORM"
            if churn == "MIXED_CHURN":
                return "MIXED_STORM"
            return "UNCLASSIFIED_STORM"
        if territory in ("CHURN_RESOLVING", "BOUNDARY_RELEASE"):
            return "TRANSITION_RELEASE"
        if phase in ("RETURN_TO_EMA9", "CROSS_RESET") and eff60 is not None and eff60 < 0.45:
            return "LOCAL_FOG"
        if eff60 is not None and eff60 >= 0.55:
            return "CLEAN_TERRITORY"
        return "QUIET_TERRITORY"

    @staticmethod
    def _zoom_mode(battlefield, phase, target_norm, seconds_left, boss, hand, snake_phase, snake_maturity):
        reasons = []
        micro = 0
        macro = 0
        if battlefield.endswith("STORM") or battlefield == "LOCAL_FOG":
            micro += 3; reasons.append("storm_micro")
        if seconds_left is not None and seconds_left <= 120:
            micro += 3; reasons.append("late_contract_micro")
        if target_norm is not None and abs(target_norm) <= 0.18:
            micro += 2; reasons.append("target_micro")
        if phase in ("RETURN_TO_EMA9", "CROSS_RESET", "PEAK_TROUGH_BUILD"):
            micro += 2; reasons.append("arc_turn_micro")

        if battlefield in ("CLEAN_TERRITORY", "QUIET_TERRITORY"):
            macro += 2; reasons.append("clean_macro")
        if boss.get("side") in ("YES", "NO"):
            macro += 2; reasons.append("boss_macro")
        if hand.get("authority_side") and hand.get("authority_side") == boss.get("side"):
            macro += 2; reasons.append("hand_boss_alignment")
        if phase in ("LAUNCH", "EXTENSION", "EXTENSION_SLOW"):
            macro += 1; reasons.append("arc_build_macro")
        if snake_phase == "BODY" and snake_maturity in ("MATURE_WATCH", "LONG_BODY"):
            micro += 1; macro += 1; reasons.append("mature_snake_both")

        if micro >= 3 and macro >= 3:
            return "BOTH", ";".join(reasons)
        if micro > macro:
            return "MICRO", ";".join(reasons)
        if macro > micro:
            return "MACRO", ";".join(reasons)
        return "BOTH", ";".join(reasons) or "balanced"

    # ------------------------------------------------------------------
    # Tick observer
    # ------------------------------------------------------------------
    def on_tick(self, ticker: str, yes_ask=None, no_ask=None, close_ts=None, now=None) -> None:
        now = time.time() if now is None else float(now)
        snap = self.snapshot(ticker, yes_ask, no_ask, close_ts, now)
        self._track_contract(ticker, now)
        self._update_profit_lock_outcomes(snap)
        self._update_looking_glass_outcomes(snap)

        if now - self.last_tick_log >= 3.0:
            _write(PRICE_ARC_LOG, PRICE_ARC_FIELDS, {
                **{k: snap.get(k) for k in PRICE_ARC_FIELDS if k not in COMMON},
            })
            self.last_tick_log = now

        if now - self.last_battle_log >= 6.0:
            self._log_battlefield(snap)
            self.last_battle_log = now

        self._looking_glass_rehearsal(snap)
        self._rollover_rhythm(snap)

    def _log_battlefield(self, s: Dict[str, Any]) -> None:
        _write(BATTLEFIELD_LOG, BATTLEFIELD_FIELDS, {
            "ticker": s.get("ticker"), "battlefield_class": s.get("battlefield_class"),
            "territory_state": s.get("territory_state"), "churn_type": s.get("churn_type"),
            "box_location": s.get("box_location"), "trend_efficiency60": s.get("eff60"),
            "range60": s.get("range60"), "price_arc_phase": s.get("price_arc_phase"),
            "remaining_capacity": s.get("remaining_capacity"), "snake_phase": s.get("snake_phase"),
            "snake_maturity": s.get("snake_maturity"), "zoom_mode": s.get("zoom_mode"),
            "zoom_reason": s.get("zoom_reason"), "target_distance": s.get("target_distance"),
            "target_distance_norm60": s.get("target_distance_norm60"), "boss_id": s.get("boss_id"),
            "boss_side": s.get("boss_side"), "hand_side": s.get("hand_side"),
            "handshake_phase": s.get("handshake_phase"), "seconds_left": s.get("seconds_left"),
        })

    # ------------------------------------------------------------------
    # Entry timing
    # ------------------------------------------------------------------
    def entry_shadow(self, ticker: str, side: str, ask: float, signal: Dict[str, Any], entered: bool, position=None) -> None:
        now = time.time()
        s = self.snapshot(ticker, close_ts=None, now=now)
        wanted = "UP" if side == "YES" else "DOWN"
        phase = s.get("price_arc_phase")
        arc_dir = s.get("arc_direction")
        rem = s.get("remaining_capacity")
        action = "TIMING_OK_SHADOW"
        reason = ""

        if arc_dir == wanted and phase == "RETURN_TO_EMA9":
            action = "WAIT_EMA9_REACTION_SHADOW"
            reason = "direction agrees but price is returning toward EMA9; seek cheaper reaction point"
        elif arc_dir != wanted and arc_dir in ("UP", "DOWN") and phase in ("LAUNCH", "EXTENSION", "EXTENSION_SLOW"):
            action = "EARLY_COUNTERARC_SHADOW"
            reason = "entry opposes an unfinished active arc"
        elif phase == "CROSS_RESET":
            action = "WAIT_NEW_ARC_SHADOW"
            reason = "price has crossed/reset EMA9 relationship; new arc not yet established"
        elif rem is not None and rem <= 0.22 and phase in ("PEAK_TROUGH_BUILD", "RETURN_TO_EMA9", "EXTENSION_SLOW"):
            action = "LOW_REMAINING_CAPACITY_SHADOW"
            reason = "direction may be right but estimated arc capacity is low"
        elif s.get("battlefield_class") == "METRONOME_STORM" and s.get("zoom_mode") != "MACRO":
            action = "ELITE_RAID_ONLY_SHADOW"
            reason = "metronome storm: directional army should not infer clean territory"

        tid = position.get("trade_id") if isinstance(position, dict) else ""
        mission = _mission_from_position(position or {}) if position else ""
        _write(ENTRY_TIMING_LOG, ENTRY_TIMING_FIELDS, {
            "event": "ENTERED" if entered else "CANDIDATE", "trade_id": tid, "ticker": ticker,
            "side": side, "ask": ask, "strategy": (signal or {}).get("strategy"), "mission": mission,
            "price_arc_phase": phase, "arc_direction": arc_dir, "remaining_capacity": rem,
            "signed_sep_norm60": s.get("signed_sep_norm60"), "timing_shadow": action,
            "battlefield_class": s.get("battlefield_class"), "zoom_mode": s.get("zoom_mode"),
            "boss_id": s.get("boss_id"), "boss_side": s.get("boss_side"), "hand_side": s.get("hand_side"),
            "seconds_left": (signal or {}).get("seconds_to_close"), "reason": reason,
        })
        if entered and isinstance(position, dict):
            position["_v94j_entry"] = {
                "run_id": RUN_ID, "session_id": SESSION_ID, "phase": phase,
                "remaining_capacity": rem, "timing_shadow": action,
                "battlefield_class": s.get("battlefield_class"), "zoom_mode": s.get("zoom_mode")
            }
        if entered and action != "TIMING_OK_SHADOW":
            print(f"🧭 HUNT TIMING SHADOW | #{tid} {side} | {action} | phase={phase} | rem={rem if rem is not None else 'NA'}")

    # ------------------------------------------------------------------
    # Arc completion: echo, grammar, snake/voyage
    # ------------------------------------------------------------------
    def on_arc_complete(self, arc: Dict[str, Any], ticker: str, now=None) -> None:
        if not isinstance(arc, dict):
            return
        now = time.time() if now is None else float(now)
        enriched = dict(arc)
        enriched["ticker"] = ticker
        enriched["seen_ts"] = now

        self._arc_echo(enriched, now)
        self._arc_grammar(enriched, now)
        self._arc_voyage(enriched, now)
        self.arc_history.append(enriched)
        if len(self.arc_history) > 120:
            del self.arc_history[:-120]

    def _arc_echo(self, arc: Dict[str, Any], now: float) -> None:
        same = [x for x in self.arc_history[-30:] if x.get("direction") == arc.get("direction")]
        if not same:
            return
        amp = max(0.001, _f(arc.get("amplitude"), 0.001) or 0.001)
        dur = max(1.0, _f(arc.get("duration_sec"), 1.0) or 1.0)
        move = _f(arc.get("btc_move"))
        best = None
        for candidate in same:
            ca = max(0.001, _f(candidate.get("amplitude"), 0.001) or 0.001)
            cd = max(1.0, _f(candidate.get("duration_sec"), 1.0) or 1.0)
            ar = amp / ca
            dr = dur / cd
            amp_sim = math.exp(-abs(math.log(ar)))
            dur_sim = math.exp(-abs(math.log(dr)))
            ema_match = int(candidate.get("ema30_relation_at_extreme") == arc.get("ema30_relation_at_extreme"))
            parent_match = int(candidate.get("parent_direction") == arc.get("parent_direction"))
            prog_match = int(candidate.get("crest_progression") == arc.get("crest_progression"))
            score = 100.0 * (0.42 * amp_sim + 0.28 * dur_sim + 0.12 * ema_match + 0.10 * parent_match + 0.08 * prog_match)
            if best is None or score > best[0]:
                best = (score, candidate, ar, dr, ema_match, parent_match, prog_match)
        if best is None:
            return
        score, cand, ar, dr, ema_match, parent_match, prog_match = best
        if ar < 0.72:
            eclass = "CONTRACTING_ECHO"
        elif ar > 1.38:
            eclass = "EXPANDING_ECHO"
        elif score >= 72:
            eclass = "FULL_ECHO"
        else:
            eclass = "FAILED_OR_WEAK_ECHO"

        cm = _f(cand.get("btc_move"))
        bmr = (move / cm) if move is not None and cm not in (None, 0.0) else None
        cand_index = self.arc_history.index(cand) if cand in self.arc_history else max(0, len(self.arc_history)-1)
        lag_arcs = len(self.arc_history) - cand_index
        tickers = [x.get("ticker") for x in self.arc_history[cand_index:] if x.get("ticker")]
        lag_contracts = max(0, len(list(dict.fromkeys(tickers))) - 1)

        _write(ARC_ECHO_LOG, ARC_ECHO_FIELDS, {
            "arc_id": arc.get("arc_id"), "ticker": arc.get("ticker"), "direction": arc.get("direction"),
            "amplitude": amp, "duration_sec": dur, "btc_move": move, "echo_arc_id": cand.get("arc_id"),
            "echo_ticker": cand.get("ticker"), "echo_score": round(score, 2), "amplitude_ratio": round(ar, 4),
            "duration_ratio": round(dr, 4), "btc_move_ratio": bmr, "lag_arcs": lag_arcs,
            "lag_contracts": lag_contracts, "echo_class": eclass, "ema30_match": ema_match,
            "parent_match": parent_match, "progression_match": prog_match,
            "remaining_capacity_at_completion": self.last_snapshot.get("remaining_capacity"),
        })
        if score >= 78 or eclass in ("CONTRACTING_ECHO", "EXPANDING_ECHO"):
            print(f"🪞 ARC ECHO | {arc.get('arc_id')} ↔ {cand.get('arc_id')} | {eclass} | score={score:.0f} | amp×{ar:.2f}")

    def _arc_grammar(self, arc: Dict[str, Any], now: float) -> None:
        direction = arc.get("direction")
        token = "U1" if direction == "UP" else "D1" if direction == "DOWN" else "?"
        double_bridge = 0
        if len(self.arc_history) >= 2:
            a0 = self.arc_history[-2]
            bridge = self.arc_history[-1]
            if a0.get("direction") == direction and bridge.get("direction") not in (None, direction):
                a0amp = _f(a0.get("amplitude"), 0.0) or 0.0
                bamp = _f(bridge.get("amplitude"), 0.0) or 0.0
                camp = _f(arc.get("amplitude"), 0.0) or 0.0
                if min(a0amp, camp) > 0 and bamp <= 0.40 * min(a0amp, camp):
                    token = "U2" if direction == "UP" else "D2"
                    double_bridge = 1
        self.grammar_tokens.append(token)
        motif = "→".join(self.grammar_tokens)
        three_shape = 0
        if len(self.grammar_tokens) >= 3:
            last3 = list(self.grammar_tokens)[-3:]
            three_shape = int(all(t.startswith(last3[0][0]) for t in last3))
        border, boss, _, _ = _current_context()
        battlefield = self.last_snapshot.get("battlefield_class") or self._battlefield_class(border, _eff60(now), "UNKNOWN")
        reason = "THREE_SHAPE_SHOWTIME_NOT_DIRECTION" if three_shape else "MOTIF_MEMORY"
        _write(ARC_GRAMMAR_LOG, ARC_GRAMMAR_FIELDS, {
            "event": "ARC_TOKEN", "arc_id": arc.get("arc_id"), "ticker": arc.get("ticker"),
            "token": token, "motif": motif, "motif_length": len(self.grammar_tokens),
            "three_shape_spotlight": three_shape, "double_lobe_bridge": double_bridge,
            "boss_id": boss.get("id"), "boss_side": boss.get("side"),
            "battlefield_class": battlefield, "reason": reason,
        })
        if three_shape:
            print(f"🎼 ARC GRAMMAR SHOWTIME | {motif} | three-shape spotlight; transition watch only")

    def _arc_voyage(self, arc: Dict[str, Any], now: float) -> None:
        border, boss, _, _ = _current_context()
        battlefield = self.last_snapshot.get("battlefield_class") or self._battlefield_class(border, _eff60(now), "UNKNOWN")
        amp = _f(arc.get("amplitude"), 0.0) or 0.0
        btc_now = _f(getattr(core, "btc_last_price", None))

        if self.voyage is None:
            self.voyage_counter += 1
            self.voyage = {
                "id": f"VJ{self.voyage_counter:04d}", "phase": "LAUNCH", "start_ts": now,
                "start_ticker": arc.get("ticker"), "launch_direction": arc.get("direction"),
                "arcs": [arc], "tickers": {arc.get("ticker")}, "btc_start": _f(arc.get("start_btc"), btc_now),
                "boss_id": boss.get("id"), "maturity": "YOUNG"
            }
            self._log_voyage("START", arc, battlefield, 0.0, "first arc establishes launch", now)
            return

        v = self.voyage
        boss_changed = v.get("boss_id") and boss.get("id") and v.get("boss_id") != boss.get("id")
        if boss_changed and len(v.get("arcs", [])) >= 2:
            self._log_voyage("END_BOSS_CHANGE", arc, battlefield, 0.0, "boss column changed", now)
            self.voyage = None
            self._arc_voyage(arc, now)
            return

        v["arcs"].append(arc)
        v["tickers"].add(arc.get("ticker"))
        arcs = v["arcs"]
        if v["phase"] == "LAUNCH" and arc.get("direction") != v.get("launch_direction"):
            v["phase"] = "BODY"
            self._log_voyage("BODY_ENTER", arc, battlefield, 0.0, "first meaningful counter-arc begins weave", now)

        body_count = max(0, len(arcs) - 1)
        contracts_seen = len([x for x in v["tickers"] if x])
        if body_count >= 6 or contracts_seen >= 6:
            v["maturity"] = "LONG_BODY"
        elif body_count >= 3 or contracts_seen >= 3:
            v["maturity"] = "MATURE_WATCH"
        else:
            v["maturity"] = "YOUNG"

        release_score = 0.0
        if v["phase"] == "BODY" and len(arcs) >= 4:
            prev_amps = [_f(x.get("amplitude"), 0.0) or 0.0 for x in arcs[-4:-1]]
            med = _median([x for x in prev_amps if x > 0], default=0.0) or 0.0
            if med > 0:
                release_score += min(3.0, amp / med)
            if battlefield in ("TRANSITION_RELEASE", "CLEAN_TERRITORY"):
                release_score += 1.5
            cls = str(arc.get("classification") or "")
            if "EXPANDING" in cls:
                release_score += 1.0
            bm = _f(arc.get("btc_move"), 0.0) or 0.0
            if amp > 0 and abs(bm) / amp >= 0.75:
                release_score += 0.75

            if release_score >= 3.0:
                v["phase"] = "RELEASE"
                self._log_voyage("RELEASE_SEEN", arc, battlefield, release_score, "body resolves into expansion/clear territory", now)
                print(f"🐍 ARC VOYAGE RELEASE | {v['id']} | after {body_count} body arcs / {contracts_seen} contracts | score={release_score:.1f}")
            elif v["maturity"] in ("MATURE_WATCH", "LONG_BODY"):
                self._log_voyage("MATURITY_WATCH", arc, battlefield, release_score, "3+ body arcs/contracts: release possible, not required", now)

        elif v["phase"] == "RELEASE":
            release_dir = arcs[-2].get("direction") if len(arcs) >= 2 else arc.get("direction")
            if arc.get("direction") != release_dir and body_count >= 2:
                self._log_voyage("END_AFTER_RELEASE", arc, battlefield, release_score, "counter-arc after release closes voyage", now)
                self.voyage = None
                self._arc_voyage(arc, now)

    def _log_voyage(self, event: str, arc: Dict[str, Any], battlefield: str, release_score: float, reason: str, now: float) -> None:
        v = self.voyage or {}
        arcs = v.get("arcs", [])
        btc_now = _f(getattr(core, "btc_last_price", None))
        btc_start = _f(v.get("btc_start"))
        _write(VOYAGE_LOG, VOYAGE_FIELDS, {
            "event": event, "voyage_id": v.get("id"), "phase": v.get("phase"), "ticker": arc.get("ticker"),
            "launch_direction": v.get("launch_direction"), "latest_arc_id": arc.get("arc_id"),
            "latest_arc_direction": arc.get("direction"), "latest_arc_amp": arc.get("amplitude"),
            "arc_count": len(arcs), "body_arc_count": max(0, len(arcs)-1),
            "contracts_seen": len([x for x in (v.get("tickers") or set()) if x]),
            "age_sec": max(0.0, now - float(v.get("start_ts") or now)), "maturity": v.get("maturity"),
            "release_score": release_score, "boss_id": (getattr(core, "v94h_boss", None) or {}).get("id"),
            "boss_side": (getattr(core, "v94h_boss", None) or {}).get("side"),
            "battlefield_class": battlefield, "btc_start": btc_start, "btc_now": btc_now,
            "net_btc_move": (btc_now-btc_start) if btc_now is not None and btc_start is not None else None,
            "reason": reason,
        })

    # ------------------------------------------------------------------
    # Looking Glass
    # ------------------------------------------------------------------
    def _looking_glass_rehearsal(self, s: Dict[str, Any]) -> None:
        now = s["now"]
        key = (
            s.get("battlefield_class"), s.get("price_arc_phase"), s.get("boss_side"),
            s.get("hand_side"), s.get("snake_phase"), s.get("snake_maturity")
        )
        if now - self.last_glass_ts < 9.0 and key == self.last_glass_key:
            return
        self.last_glass_ts = now
        self.last_glass_key = key

        cont = 1.0; storm = 1.0; transfer = 1.0
        reasons = []
        bf = s.get("battlefield_class")
        phase = s.get("price_arc_phase")
        boss_side = s.get("boss_side")
        hand_side = s.get("hand_side")

        if bf in ("CLEAN_TERRITORY", "QUIET_TERRITORY"):
            cont += 2.5; reasons.append("clean_cont")
        if phase in ("LAUNCH", "EXTENSION", "EXTENSION_SLOW"):
            cont += 2.0; reasons.append("arc_build_cont")
        if boss_side in ("YES", "NO") and hand_side == boss_side:
            cont += 2.0; reasons.append("hand_boss_cont")

        if bf and bf.endswith("STORM"):
            storm += 4.0; reasons.append("storm_active")
        if s.get("snake_phase") == "BODY":
            storm += 1.5; reasons.append("snake_body")
        if s.get("snake_maturity") in ("MATURE_WATCH", "LONG_BODY"):
            storm += 1.0; transfer += 0.5; reasons.append("mature_transition_watch")
        if s.get("target_distance_norm60") is not None and abs(s.get("target_distance_norm60")) <= 0.18:
            storm += 1.0; reasons.append("target_battle")

        if phase in ("RETURN_TO_EMA9", "CROSS_RESET"):
            transfer += 2.0; reasons.append("arc_reset_transfer")
        if boss_side in ("YES", "NO") and hand_side in ("YES", "NO") and hand_side != boss_side:
            transfer += 3.0; reasons.append("hand_challenges_boss")
        if str(s.get("handshake_phase") or "") not in ("", "NONE", "STABLE", "HOLD"):
            transfer += 1.0; reasons.append("handshake_active")
        crest = getattr(core, "v94i_latest_crest_signal", None) or {}
        release_side = crest.get("release_side")
        if release_side in ("YES", "NO") and boss_side in ("YES", "NO") and release_side != boss_side:
            transfer += 1.5; reasons.append("crest_release_challenge")

        weights = [math.exp(cont/2.0), math.exp(storm/2.0), math.exp(transfer/2.0)]
        total = sum(weights)
        pcont, pstorm, ptransfer = [100.0*w/total for w in weights]
        probs = {"CONTINUATION": pcont, "STORM": pstorm, "AUTHORITY_TRANSFER": ptransfer}
        top = max(probs, key=probs.get)
        conf = probs[top]
        acc = 100.0*self.glass_correct/self.glass_outcomes if self.glass_outcomes else None

        self.glass_counter += 1
        gid = f"LG{self.glass_counter:06d}"
        for horizon in (60, 180):
            ev = {
                "id": gid, "created": s["now"], "horizon": horizon, "ticker": s.get("ticker"),
                "btc_start": s.get("btc_price"), "r60": s.get("range60"), "boss_id": s.get("boss_id"),
                "boss_side": boss_side, "hand_side": hand_side, "battlefield": bf,
                "snake_phase": s.get("snake_phase"), "price_arc_phase": phase,
                "scores": (cont, storm, transfer), "probs": probs, "top": top, "confidence": conf,
                "reason": ";".join(reasons)
            }
            self.glass_pending.append(ev)
            _write(LOOKING_GLASS_LOG, LOOKING_GLASS_FIELDS, {
                "event": "REHEARSAL", "glass_id": gid, "ticker": s.get("ticker"), "horizon_sec": horizon,
                "btc_start": s.get("btc_price"), "boss_id_start": s.get("boss_id"), "boss_side_start": boss_side,
                "hand_side_start": hand_side, "battlefield_start": bf, "snake_phase_start": s.get("snake_phase"),
                "price_arc_phase_start": phase, "continuation_score": cont, "storm_score": storm,
                "transfer_score": transfer, "continuation_pct": round(pcont,2), "storm_pct": round(pstorm,2),
                "transfer_pct": round(ptransfer,2), "top_scenario": top, "shadow_confidence_pct": round(conf,2),
                "calibration_n": self.glass_outcomes, "rolling_accuracy_pct": acc,
                "reason": ";".join(reasons) + ";UNCALIBRATED_SHADOW_CONFIDENCE",
            })
        if conf >= 60:
            print(f"🔮 LOOKING GLASS | {top} {conf:.0f}% shadow | {bf} | phase={phase} | calibration n={self.glass_outcomes}")

    def _update_looking_glass_outcomes(self, s: Dict[str, Any]) -> None:
        if not self.glass_pending:
            return
        now = s["now"]
        keep = []
        for ev in self.glass_pending:
            if now - ev["created"] < ev["horizon"]:
                keep.append(ev); continue
            start_boss = ev.get("boss_side")
            end_boss = s.get("boss_side")
            end_hand = s.get("hand_side")
            move = None
            if s.get("btc_price") is not None and ev.get("btc_start") is not None:
                move = s["btc_price"] - ev["btc_start"]
            signed = move * _sign(start_boss) if move is not None and _sign(start_boss) else None
            threshold = max(12.0, 0.45 * float(ev.get("r60") or 1.0))

            if start_boss in ("YES", "NO") and ((end_boss in ("YES","NO") and end_boss != start_boss) or (end_hand in ("YES","NO") and end_hand != start_boss)):
                actual = "AUTHORITY_TRANSFER"
            elif s.get("battlefield_class", "").endswith("STORM") and (signed is None or abs(signed) < threshold):
                actual = "STORM"
            elif signed is not None and signed >= threshold:
                actual = "CONTINUATION"
            elif s.get("battlefield_class", "").endswith("STORM"):
                actual = "STORM"
            else:
                actual = "AMBIGUOUS"

            correct = int(actual == ev.get("top")) if actual != "AMBIGUOUS" else ""
            if actual != "AMBIGUOUS":
                self.glass_outcomes += 1
                self.glass_correct += int(bool(correct))
            acc = 100.0*self.glass_correct/self.glass_outcomes if self.glass_outcomes else None
            cont, storm, transfer = ev["scores"]
            probs = ev["probs"]
            _write(LOOKING_GLASS_LOG, LOOKING_GLASS_FIELDS, {
                "event": "OUTCOME", "glass_id": ev["id"], "ticker": ev.get("ticker"),
                "horizon_sec": ev["horizon"], "btc_start": ev.get("btc_start"),
                "boss_id_start": ev.get("boss_id"), "boss_side_start": start_boss,
                "hand_side_start": ev.get("hand_side"), "battlefield_start": ev.get("battlefield"),
                "snake_phase_start": ev.get("snake_phase"), "price_arc_phase_start": ev.get("price_arc_phase"),
                "continuation_score": cont, "storm_score": storm, "transfer_score": transfer,
                "continuation_pct": round(probs["CONTINUATION"],2), "storm_pct": round(probs["STORM"],2),
                "transfer_pct": round(probs["AUTHORITY_TRANSFER"],2), "top_scenario": ev.get("top"),
                "shadow_confidence_pct": round(ev.get("confidence",0.0),2), "calibration_n": self.glass_outcomes,
                "rolling_accuracy_pct": acc, "actual_outcome": actual, "correct": correct,
                "btc_end": s.get("btc_price"), "btc_signed_for_boss": signed,
                "boss_side_end": end_boss, "hand_side_end": end_hand,
                "battlefield_end": s.get("battlefield_class"), "reason": ev.get("reason"),
            })
        self.glass_pending = keep

    # ------------------------------------------------------------------
    # Rollover rhythm
    # ------------------------------------------------------------------
    def _rollover_rhythm(self, s: Dict[str, Any]) -> None:
        left = s.get("seconds_left")
        ticker = s.get("ticker")
        if left is None or not ticker or left > 180:
            return
        thresholds = (180, 120, 90, 60, 45, 30, 15, 9, 6, 3)
        for th in thresholds:
            if left <= th and th not in self.rollover_seen[ticker]:
                self.rollover_seen[ticker].add(th)
                norm = s.get("signed_sep_norm60")
                vel = s.get("sep_velocity_6s")
                sep_raw_norm = None
                if s.get("price_ema9_sep") is not None and s.get("range60"):
                    sep_raw_norm = s["price_ema9_sep"] / s["range60"]
                if sep_raw_norm is None:
                    rhythm = "UNKNOWN"
                elif abs(sep_raw_norm) <= 0.05:
                    rhythm = "EMA9_CROSS_ZONE"
                elif sep_raw_norm >= 0.15:
                    rhythm = "UPPER_TURN" if vel is not None and vel < 0 else "UPPER_EXPANSION"
                elif sep_raw_norm <= -0.15:
                    rhythm = "LOWER_TURN" if vel is not None and vel > 0 else "LOWER_EXPANSION"
                else:
                    rhythm = "MID_RHYTHM"

                phase = s.get("price_arc_phase")
                if phase == "RETURN_TO_EMA9":
                    read = "BOUNDARY_DURING_RETURN"
                elif phase == "CROSS_RESET":
                    read = "BOUNDARY_DURING_RESET"
                elif phase in ("LAUNCH", "EXTENSION"):
                    read = "BOUNDARY_DURING_BUILD"
                else:
                    read = "BOUNDARY_MID_PHRASE"
                _write(ROLLOVER_RHYTHM_LOG, ROLLOVER_FIELDS, {
                    "event": "THRESHOLD", "ticker": ticker, "seconds_left": left, "threshold": th,
                    "btc_price": s.get("btc_price"), "ema9": s.get("ema9"), "ema30": s.get("ema30"),
                    "target": s.get("target"), "target_distance": s.get("target_distance"),
                    "arc_id": s.get("arc_id"), "arc_direction": s.get("arc_direction"),
                    "price_arc_phase": phase, "rhythm_position": rhythm, "sep_norm60": norm,
                    "sep_velocity_6s": vel, "remaining_capacity": s.get("remaining_capacity"),
                    "battlefield_class": s.get("battlefield_class"), "zoom_mode": s.get("zoom_mode"),
                    "boss_id": s.get("boss_id"), "boss_side": s.get("boss_side"), "hand_side": s.get("hand_side"),
                    "boundary_read_shadow": read,
                })
                if th in (60, 30, 9, 3):
                    print(f"⏳ ROLLOVER RHYTHM T-{th} | {rhythm} | {phase} | {read}")

    # ------------------------------------------------------------------
    # Trade exit / Profit Lock shadow / War report
    # ------------------------------------------------------------------
    def on_trade_exit(self, position: Dict[str, Any], bid, actual_roi, reason, pnl) -> None:
        now = time.time()
        ticker = position.get("ticker")
        side = position.get("side")
        s = self.snapshot(ticker or "", now=now)
        mission = _mission_from_position(position)
        trade = {
            "ts": now, "trade_id": position.get("trade_id"), "ticker": ticker, "side": side,
            "pnl": _f(pnl, 0.0) or 0.0, "roi": _f(actual_roi), "reason": reason,
            "mission": mission, "strategy": position.get("strategy") or position.get("contract_phase") or "UNKNOWN",
            "battlefield": s.get("battlefield_class"), "boss_id": s.get("boss_id")
        }
        self.trade_events.append(trade)
        if self.current_contract and ticker == self.current_contract.get("ticker"):
            self.current_contract["trades"].append(trade)
        if s.get("boss_id"):
            self.boss_ids_seen.add(s.get("boss_id"))

        if "PROFIT_LOCK" in str(reason or "").upper():
            wanted = "UP" if side == "YES" else "DOWN"
            unfinished = (
                s.get("arc_direction") == wanted
                and s.get("price_arc_phase") in ("LAUNCH", "EXTENSION", "EXTENSION_SLOW", "PEAK_TROUGH_BUILD")
                and s.get("battlefield_class") not in ("TRANSITION_RELEASE",)
            )
            topology = _profit_topology_from_position(position)
            if topology == "STRUCTURAL_FAILURE":
                unfinished = False
            shield = "UNFINISHED_ARC_SHADOW" if unfinished else "EXIT_SUPPORTED_SHADOW"
            row = {
                "event": "EXIT", "trade_id": position.get("trade_id"), "ticker": ticker, "side": side,
                "exit_reason": reason, "entry_ask": position.get("entry_ask"), "exit_bid": bid,
                "actual_roi": actual_roi, "actual_pnl": pnl, "price_arc_phase": s.get("price_arc_phase"),
                "arc_direction": s.get("arc_direction"), "remaining_capacity": s.get("remaining_capacity"),
                "battlefield_class": s.get("battlefield_class"), "boss_id": s.get("boss_id"),
                "boss_side": s.get("boss_side"), "hand_side": s.get("hand_side"),
                "profit_topology": topology, "shield_read": shield, "btc_exit": s.get("btc_price"),
                "reason": "observer only; distinguish profit giveback from breathing inside unfinished arc"
            }
            _write(PROFIT_LOCK_SHIELD_LOG, PROFIT_LOCK_FIELDS, row)
            for horizon in (30, 60, 120):
                self.pending_profit_locks.append({
                    "created": now, "horizon": horizon, "trade_id": position.get("trade_id"), "ticker": ticker,
                    "side": side, "exit_bid": _f(bid), "entry_ask": _f(position.get("entry_ask")),
                    "btc_exit": s.get("btc_price"), "base": row
                })
            if unfinished:
                print(f"🛡️ PROFIT-LOCK ARC SHIELD SHADOW | #{position.get('trade_id')} {side} | unfinished arc suspected | phase={s.get('price_arc_phase')}")

    def _update_profit_lock_outcomes(self, s: Dict[str, Any]) -> None:
        if not self.pending_profit_locks:
            return
        now = s["now"]
        keep = []
        for ev in self.pending_profit_locks:
            if now - ev["created"] < ev["horizon"]:
                keep.append(ev); continue
            later_bid = _side_bid(ev["side"], s.get("yes_ask"), s.get("no_ask"))
            bid_change = (later_bid - ev["exit_bid"]) if later_bid is not None and ev.get("exit_bid") is not None else None
            entry = ev.get("entry_ask")
            roi_change = (bid_change / entry) if bid_change is not None and entry not in (None, 0.0) else None
            base = dict(ev["base"])
            base.update({
                "event": "OUTCOME", "horizon_sec": ev["horizon"], "later_bid": later_bid,
                "bid_change": bid_change, "hypothetical_roi_change": roi_change,
                "btc_later": s.get("btc_price"),
            })
            _write(PROFIT_LOCK_SHIELD_LOG, PROFIT_LOCK_FIELDS, base)
        self.pending_profit_locks = keep

    # ------------------------------------------------------------------
    # Contract tracking and War Report
    # ------------------------------------------------------------------
    def _track_contract(self, ticker: str, now: float) -> None:
        if not ticker:
            return
        if self.last_ticker is None:
            self.last_ticker = ticker
            self.current_contract = {"ticker": ticker, "start_ts": now, "trades": [], "boss_ids": set()}
            return
        if ticker == self.last_ticker:
            if self.current_contract and self.last_snapshot.get("boss_id"):
                self.current_contract["boss_ids"].add(self.last_snapshot.get("boss_id"))
            return

        if self.current_contract:
            self.current_contract["end_ts"] = now
            self.contracts.append(self.current_contract)
            self._emit_war_reports()
        self.last_ticker = ticker
        self.current_contract = {"ticker": ticker, "start_ts": now, "trades": [], "boss_ids": set()}

    def _emit_war_reports(self) -> None:
        for n in (6, 12):
            if len(self.contracts) < n:
                continue
            group = list(self.contracts)[-n:]
            trades = [t for c in group for t in c.get("trades", [])]
            if not trades:
                continue
            pnls = [float(t.get("pnl",0.0)) for t in trades]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]
            scratches = len(pnls) - len(wins) - len(losses)
            gross_win = sum(wins)
            gross_loss = abs(sum(losses))
            pf = gross_win/gross_loss if gross_loss > 0 else None
            mission_stats = defaultdict(lambda: [0,0.0])
            storm_trades = 0
            for t in trades:
                m = str(t.get("mission") or "UNKNOWN")
                mission_stats[m][0] += 1
                mission_stats[m][1] += float(t.get("pnl",0.0))
                if str(t.get("battlefield") or "").endswith("STORM"):
                    storm_trades += 1
            pnl = sum(pnls)
            if pnl > 5:
                state = "GAINING_TREASURY"
            elif pnl < -5:
                state = "TAKING_CASUALTIES"
            else:
                state = "HOLDING_GROUND"
            bosses = set()
            for c in group:
                bosses.update(c.get("boss_ids", set()))

            row = {
                "window_contracts": n, "contracts_count": len(group), "first_ticker": group[0].get("ticker"),
                "last_ticker": group[-1].get("ticker"), "trades": len(trades), "wins": len(wins),
                "losses": len(losses), "scratches": scratches, "win_rate_pct": 100*len(wins)/len(trades),
                "pnl": pnl, "gross_win": gross_win, "gross_loss": gross_loss, "profit_factor": pf,
                "avg_win": (gross_win/len(wins)) if wins else None,
                "avg_loss": (sum(losses)/len(losses)) if losses else None,
                "casualties_le_minus5": sum(1 for p in pnls if p <= -5.0),
                "raid_trades": mission_stats["RAID"][0], "raid_pnl": mission_stats["RAID"][1],
                "campaign_trades": mission_stats["CAMPAIGN"][0], "campaign_pnl": mission_stats["CAMPAIGN"][1],
                "attack_trades": mission_stats["ATTACK"][0], "attack_pnl": mission_stats["ATTACK"][1],
                "scout_trades": mission_stats["SCOUT"][0], "scout_pnl": mission_stats["SCOUT"][1],
                "storm_trades": storm_trades, "clear_trades": len(trades)-storm_trades,
                "bosses_seen": len(bosses), "war_state": state,
                "note": "rolling contract war report; descriptive observer only"
            }
            _write(WAR_REPORT_LOG, WAR_REPORT_FIELDS, row)
            print(f"⚔️ WAR REPORT {n}C | {state} | P&L=${pnl:+.2f} | {len(wins)}W/{len(losses)}L | PF={pf:.2f}" if pf is not None else f"⚔️ WAR REPORT {n}C | {state} | P&L=${pnl:+.2f}")

    # ------------------------------------------------------------------
    # Run manifest
    # ------------------------------------------------------------------
    def _write_manifest(self) -> None:
        _write(RUN_MANIFEST_LOG, MANIFEST_FIELDS, {
            "version": VERSION, "base_version": "V9.4I", "paper_authority": "FROZEN_BASE_ONLY",
            "start_local": _local(_START_TS), "pid": os.getpid(), "python_note": "V9.4J launcher imports V9.4I",
            "research_layers": "PRICE_ARC;ENTRY_TIMING;ARC_ECHO;ARC_GRAMMAR;ARC_VOYAGE;BATTLEFIELD;ZOOM;LOOKING_GLASS;WAR_REPORT;ROLLOVER_RHYTHM;PROFIT_LOCK_ARC_SHIELD"
        })


brain = V94JShadowBrain()


# ============================================================================
# MONKEYPATCH HOOKS — observer-only wrappers; return values preserved
# ============================================================================

_HOOKS_INSTALLED = False


def install_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    _HOOKS_INSTALLED = True

    # 1) General tick: King's Council already receives asks + close_ts each observer cycle.
    original_council = getattr(core, "v94e_kings_council_observer")
    def council_wrapper(ticker, yes_ask, no_ask, close_ts, now=None):
        result = original_council(ticker, yes_ask, no_ask, close_ts, now)
        try:
            brain.on_tick(ticker, yes_ask, no_ask, close_ts, now)
        except Exception as exc:
            print(f"⚠️ V9.4J tick shadow error: {exc}")
        return result
    core.v94e_kings_council_observer = council_wrapper

    # 2) Completed EMA9 arc hook.
    original_complete_arc = getattr(core, "_v93a_complete_arc")
    def complete_arc_wrapper(now, ticker, yes_ask, no_ask, target, r60, r180):
        row = original_complete_arc(now, ticker, yes_ask, no_ask, target, r60, r180)
        if isinstance(row, dict):
            try:
                brain.on_arc_complete(row, ticker, now)
            except Exception as exc:
                print(f"⚠️ V9.4J arc shadow error: {exc}")
        return row
    core._v93a_complete_arc = complete_arc_wrapper

    # 3) Paper-entry timing hook.  Never changes decision or return value.
    original_enter = getattr(core, "paper_enter")
    def paper_enter_wrapper(ticker, side, ask, signal):
        entered = original_enter(ticker, side, ask, signal)
        try:
            pos = (getattr(core, "paper_positions", {}) or {}).get(side)
            if not (isinstance(pos, dict) and pos.get("ticker") == ticker):
                pos = None
            brain.entry_shadow(ticker, side, ask, signal or {}, bool(entered), pos)
        except Exception as exc:
            print(f"⚠️ V9.4J entry timing shadow error: {exc}")
        return entered
    core.paper_enter = paper_enter_wrapper

    # 4) Trade-finalization hook. Original finalizers run first and retain authority.
    original_finalize = getattr(core, "v94b_finalize_trade_shadows")
    def finalize_wrapper(position, bid, actual_roi, reason, pnl):
        result = original_finalize(position, bid, actual_roi, reason, pnl)
        try:
            brain.on_trade_exit(position, bid, actual_roi, reason, pnl)
        except Exception as exc:
            print(f"⚠️ V9.4J exit shadow error: {exc}")
        return result
    core.v94b_finalize_trade_shadows = finalize_wrapper


# ============================================================================
# START
# ============================================================================

async def main() -> None:
    install_hooks()
    print("=" * 84)
    print(f"TACHYOS {VERSION} — LOOKING GLASS / ARC VOYAGE SHADOW BRAIN")
    print(f"RUN ID: {RUN_ID} | SESSION: {SESSION_ID}")
    print("PAPER ONLY | V9.4I paper authority frozen | V9.4J outputs are observer/shadow telemetry.")
    print("The V9.4I core banner below is EXPECTED: V9.4J is attached around that frozen engine.")
    print("New council lenses: Snake/Voyage | Price–Arc Phase | Arc Echo/Grammar | Zoom Governor | Looking Glass | War Report.")
    print("=" * 84)
    await core.main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTachyos V9.4J stopped by operator (Ctrl+C).")
