"""
TACHYOS V9.4L — SECOND SPEAR / SETTLEMENT ELASTICITY LAB
========================================================

PAPER ONLY.

V9.4L imports V9.4K and adds two observer-only research layers around the
same frozen V9.4I paper authority:

1) SECOND SPEAR
   Study whether a second SAME-SIDE position would have been useful while a
   real paper position was already open.

   It records:
     - same-side attempted entries while a parent position is active
     - signal grade / A+ score
     - parent live ROI and premium difference
     - REPEATED_ECHO vs PARTIAL_REFRESH vs NEW_STRUCTURAL_CHAPTER
     - independent shadow MFE/MAE
     - 15/30/60/120-second outcomes
     - counterfactual result if the child exited with the parent
     - contract-rollover mark
     - real EXIT -> RELOAD behavior taken by the frozen authority

2) SETTLEMENT ELASTICITY
   Measure how strongly Kalshi YES/NO prices react to similar BTC moves as:
     - settlement approaches
     - BTC approaches / leaves the target
     - recent BTC range changes
     - contract certainty changes

   Quote response is logged over 3 / 6 / 9 second windows with raw continuous
   clock and target-distance variables retained for later calibration.

Doctrine:
  - Reinforcement is not averaging down by default.
  - A stronger repeated signal is not automatically a new structural chapter.
  - A worse nominal quote can still be a better trade after structure resets.
  - Time changes the meaning of the same BTC displacement.
  - Target distance changes the meaning of the same amount of time.
  - V9.4L never places, blocks, resizes, flips, or closes a paper trade.
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

import tachys_v9_4k_field_medic_flexible_cage_shadow as k

j = k.j
core = k.core

VERSION = "V9.4L"
ET = k.ET
_START_TS = time.time()
RUN_ID = datetime.now(ET).strftime("L%Y%m%d_%H%M%S")
SESSION_ID = f"{RUN_ID}_PID{os.getpid()}"

os.environ["TACHYOS_V94L_RUN_ID"] = RUN_ID
os.environ["TACHYOS_V94L_SESSION_ID"] = SESSION_ID

COMMON = ["timestamp", "run_id", "session_id"]

SECOND_SPEAR_LOG = "tachys_second_spear_v9_4l.csv"
ELASTICITY_LOG = "tachys_settlement_elasticity_v9_4l.csv"
MANIFEST_LOG = "tachys_run_manifest_v9_4l.csv"

SECOND_SPEAR_FIELDS = COMMON + [
    "event", "spear_id", "parent_trade_id", "ticker", "side",
    "candidate_ask", "candidate_bid", "signal_grade", "setup_grade",
    "a_plus_score", "signal_reason", "strong_candidate",
    "parent_entry_ask", "parent_live_bid", "parent_live_roi",
    "premium_vs_parent_entry", "seconds_since_parent_entry",
    "seconds_left", "btc_price", "target", "target_distance", "range60",
    "arc_id", "arc_direction", "price_arc_phase", "remaining_capacity",
    "battlefield_class", "zoom_mode", "boss_id", "boss_side", "hand_side",
    "cage_state", "dragon_state", "target_migration_state",
    "chapter_change_score", "chapter_label", "chapter_reasons",
    "spawned_shadow_child", "shadow_age_sec", "current_bid",
    "shadow_roi", "shadow_mfe_roi", "shadow_mae_roi",
    "btc_move_from_candidate", "target_distance_change",
    "parent_active", "parent_current_roi", "horizon_sec", "policy",
    "result_label", "exit_reason", "note",
]

ELASTICITY_FIELDS = COMMON + [
    "ticker", "seconds_left", "clock_bucket", "btc_price", "target",
    "target_distance", "abs_target_distance", "range60",
    "target_distance_norm60", "distance_bucket",
    "yes_ask", "no_ask", "yes_bid", "no_bid",
    "window_sec", "sample_age_sec", "btc_change",
    "yes_bid_change", "no_bid_change",
    "yes_beta_per_btc_dollar", "no_beta_per_btc_dollar",
    "yes_directional_beta", "no_directional_beta",
    "yes_cents_per_10btc", "no_cents_per_10btc",
    "local_yes_beta_90s", "local_no_beta_90s",
    "quote_sum", "quote_overround",
    "price_arc_phase", "arc_direction", "battlefield_class",
    "cage_state", "dragon_state", "target_migration_state",
    "valid_move", "note",
]

MANIFEST_FIELDS = COMMON + [
    "version", "base_version", "paper_authority", "start_local", "pid",
    "research_layers", "second_spear_doctrine", "elasticity_doctrine",
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
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _i(x: Any, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def _safe(obj: Any, *keys: str, default=None):
    if not isinstance(obj, dict):
        return default
    for key in keys:
        if key in obj and obj.get(key) not in (None, ""):
            return obj.get(key)
    return default


def _median(values, default=None):
    vals = []
    for value in values:
        v = _f(value)
        if v is not None:
            vals.append(v)
    return statistics.median(vals) if vals else default


def _write(path: str, fields: List[str], row: Dict[str, Any]) -> None:
    payload = {
        "timestamp": row.get("timestamp", _utc()),
        "run_id": RUN_ID,
        "session_id": SESSION_ID,
        **row,
    }
    new_file = (not os.path.exists(path)) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow({field: payload.get(field, "") for field in fields})


def _side_bid(side: str, yes_ask, no_ask) -> Optional[float]:
    return k._side_bid(side, _f(yes_ask), _f(no_ask))


def _position_entry(pos: Dict[str, Any]) -> Optional[float]:
    return k._position_entry(pos)


def _position_trade_id(pos: Dict[str, Any], fallback="") -> str:
    return k._position_trade_id(pos, fallback)


def _position_entry_ts(pos: Dict[str, Any]) -> Optional[float]:
    return k._position_entry_ts(pos)


def _clock_bucket(seconds_left: Optional[float]) -> str:
    sec = _f(seconds_left)
    if sec is None:
        return "UNKNOWN"
    if sec > 540:
        return "GT_9M"
    if sec > 360:
        return "6_TO_9M"
    if sec > 180:
        return "3_TO_6M"
    if sec > 90:
        return "90S_TO_3M"
    if sec > 30:
        return "30_TO_90S"
    return "LT_30S"


def _distance_bucket(target_distance: Optional[float], range60: Optional[float]) -> str:
    d = _f(target_distance)
    r = _f(range60)
    if d is None or r is None or r <= 0:
        return "UNKNOWN"
    x = abs(d) / max(1.0, r)
    if x <= 0.25:
        return "ON_TARGET"
    if x <= 0.75:
        return "NEAR_TARGET"
    if x <= 1.50:
        return "MID_DISTANCE"
    return "FAR_TARGET"


def _grade(signal: Dict[str, Any]) -> Tuple[str, str, int, str]:
    signal = signal if isinstance(signal, dict) else {}
    signal_grade = str(_safe(signal, "signal_grade", "grade", default="") or "")
    setup_grade = str(_safe(signal, "setup_grade", default="") or "")
    score = _i(_safe(signal, "a_plus_score", "score", default=0), 0)
    reason = str(
        _safe(
            signal,
            "early_exception_reasons",
            "a_plus_reasons",
            "reason",
            "reasons",
            default="",
        )
        or ""
    )
    return signal_grade, setup_grade, score, reason


class V94LShadowBrain:
    def __init__(self):
        self.market_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=4000))
        self.beta_history = {"YES": deque(maxlen=3000), "NO": deque(maxlen=3000)}

        self.parent_context: Dict[str, Dict[str, Any]] = {}
        self.spear_counter = 0
        self.spears: Dict[str, Dict[str, Any]] = {}
        self.last_spawn_ts: Dict[Tuple[str, str], float] = {}
        self.last_candidate_signature: Dict[Tuple[str, str], str] = {}

        self.last_real_exit: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.last_ticker: Optional[str] = None
        self.last_snapshot_by_ticker: Dict[str, Dict[str, Any]] = {}

        self._write_manifest()

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------
    def _snapshot(self, ticker: str, yes_ask=None, no_ask=None, close_ts=None, now=None) -> Dict[str, Any]:
        now = time.time() if now is None else float(now)
        snap = dict(j.brain.last_snapshot or {})
        if snap.get("ticker") != ticker:
            try:
                snap = dict(j.brain.snapshot(ticker, yes_ask, no_ask, close_ts, now) or {})
            except Exception:
                snap = dict(j.brain.last_snapshot or {})

        snap["now"] = now
        snap["ticker"] = ticker
        if yes_ask is not None:
            snap["yes_ask"] = _f(yes_ask)
        if no_ask is not None:
            snap["no_ask"] = _f(no_ask)

        snap["cage_state"] = getattr(k.brain, "last_cage_state", None)
        snap["dragon_state"] = getattr(k.brain, "last_dragon_state", None)
        snap["target_migration_state"] = getattr(k.brain, "last_migration_state", None)
        return snap

    def _active_position(self, side: str, ticker: Optional[str] = None) -> Optional[Dict[str, Any]]:
        positions = getattr(core, "paper_positions", {}) or {}
        if not isinstance(positions, dict):
            return None

        direct = positions.get(side)
        if isinstance(direct, dict):
            if ticker is None or str(direct.get("ticker") or "") == str(ticker):
                return direct

        for key, pos in positions.items():
            if not isinstance(pos, dict):
                continue
            pside = str(_safe(pos, "side", default=key) or key)
            if pside != side:
                continue
            if ticker is not None and str(pos.get("ticker") or "") != str(ticker):
                continue
            return pos
        return None

    @staticmethod
    def _context_signature(s: Dict[str, Any]) -> str:
        return "|".join(
            str(s.get(key) or "")
            for key in (
                "arc_id", "price_arc_phase", "battlefield_class", "boss_id",
                "boss_side", "hand_side", "cage_state", "dragon_state",
            )
        )

    # ------------------------------------------------------------------
    # Main market tick
    # ------------------------------------------------------------------
    def on_tick(self, ticker, yes_ask=None, no_ask=None, close_ts=None, now=None):
        now = time.time() if now is None else float(now)
        s = self._snapshot(ticker, yes_ask, no_ask, close_ts, now)

        if self.last_ticker and ticker and ticker != self.last_ticker:
            prior = self.last_snapshot_by_ticker.get(self.last_ticker)
            if prior:
                self._finalize_contract_spears(self.last_ticker, prior, now)

        self.last_ticker = ticker or self.last_ticker
        self.last_snapshot_by_ticker[ticker] = dict(s)

        self._record_elasticity_sample(s)
        self._update_spears(s)

    # ------------------------------------------------------------------
    # Settlement Elasticity
    # ------------------------------------------------------------------
    def _record_elasticity_sample(self, s: Dict[str, Any]) -> None:
        ticker = str(s.get("ticker") or "")
        now = _f(s.get("now"))
        btc = _f(s.get("btc_price"))
        yes_ask = _f(s.get("yes_ask"))
        no_ask = _f(s.get("no_ask"))
        if not ticker or now is None or btc is None:
            return

        yes_bid = _side_bid("YES", yes_ask, no_ask)
        no_bid = _side_bid("NO", yes_ask, no_ask)
        target = _f(s.get("target"))
        target_distance = _f(s.get("target_distance"))
        if target_distance is None and target is not None:
            target_distance = btc - target
        range60 = _f(s.get("range60"))

        sample = {
            "ts": now,
            "ticker": ticker,
            "btc": btc,
            "target": target,
            "target_distance": target_distance,
            "range60": range60,
            "seconds_left": _f(s.get("seconds_left")),
            "yes_ask": yes_ask,
            "no_ask": no_ask,
            "yes_bid": yes_bid,
            "no_bid": no_bid,
            "price_arc_phase": s.get("price_arc_phase"),
            "arc_direction": s.get("arc_direction"),
            "battlefield_class": s.get("battlefield_class"),
            "cage_state": s.get("cage_state"),
            "dragon_state": s.get("dragon_state"),
            "target_migration_state": s.get("target_migration_state"),
        }
        hist = self.market_history[ticker]
        hist.append(sample)

        for window in (3, 6, 9):
            prior = self._nearest_prior(hist, now, window)
            if prior is not None:
                self._log_elasticity_window(sample, prior, window)

    @staticmethod
    def _nearest_prior(hist: deque, now: float, desired_sec: int) -> Optional[Dict[str, Any]]:
        best = None
        best_err = float("inf")
        for row in reversed(hist):
            age = now - row["ts"]
            if age < max(0.5, desired_sec - 1.75):
                continue
            if age > desired_sec + 1.75:
                break
            err = abs(age - desired_sec)
            if err < best_err:
                best = row
                best_err = err
        return best

    def _local_beta(self, side: str, now: float) -> Optional[float]:
        vals = [
            row["beta"]
            for row in self.beta_history[side]
            if now - row["ts"] <= 90 and row.get("beta") is not None
        ]
        return _median(vals, None)

    def _log_elasticity_window(self, cur: Dict[str, Any], prior: Dict[str, Any], window: int) -> None:
        now = cur["ts"]
        dt = now - prior["ts"]
        dbtc = cur["btc"] - prior["btc"]

        yes_change = None
        no_change = None
        if cur.get("yes_bid") is not None and prior.get("yes_bid") is not None:
            yes_change = cur["yes_bid"] - prior["yes_bid"]
        if cur.get("no_bid") is not None and prior.get("no_bid") is not None:
            no_change = cur["no_bid"] - prior["no_bid"]

        valid_move = int(abs(dbtc) >= 1.0)
        yes_beta = yes_change / dbtc if valid_move and yes_change is not None else None
        no_beta = no_change / dbtc if valid_move and no_change is not None else None

        yes_directional = yes_beta
        no_directional = (-no_beta) if no_beta is not None else None

        if valid_move and yes_directional is not None:
            self.beta_history["YES"].append({"ts": now, "beta": abs(yes_directional)})
        if valid_move and no_directional is not None:
            self.beta_history["NO"].append({"ts": now, "beta": abs(no_directional)})

        local_yes = self._local_beta("YES", now)
        local_no = self._local_beta("NO", now)

        target_distance = cur.get("target_distance")
        range60 = cur.get("range60")
        norm = None
        if target_distance is not None and range60 not in (None, 0):
            norm = target_distance / max(1.0, abs(range60))

        quote_sum = None
        overround = None
        if cur.get("yes_ask") is not None and cur.get("no_ask") is not None:
            quote_sum = cur["yes_ask"] + cur["no_ask"]
            overround = quote_sum - 1.0

        _write(ELASTICITY_LOG, ELASTICITY_FIELDS, {
            "ticker": cur["ticker"],
            "seconds_left": cur.get("seconds_left"),
            "clock_bucket": _clock_bucket(cur.get("seconds_left")),
            "btc_price": cur.get("btc"),
            "target": cur.get("target"),
            "target_distance": target_distance,
            "abs_target_distance": abs(target_distance) if target_distance is not None else None,
            "range60": range60,
            "target_distance_norm60": norm,
            "distance_bucket": _distance_bucket(target_distance, range60),
            "yes_ask": cur.get("yes_ask"),
            "no_ask": cur.get("no_ask"),
            "yes_bid": cur.get("yes_bid"),
            "no_bid": cur.get("no_bid"),
            "window_sec": window,
            "sample_age_sec": dt,
            "btc_change": dbtc,
            "yes_bid_change": yes_change,
            "no_bid_change": no_change,
            "yes_beta_per_btc_dollar": yes_beta,
            "no_beta_per_btc_dollar": no_beta,
            "yes_directional_beta": yes_directional,
            "no_directional_beta": no_directional,
            "yes_cents_per_10btc": abs(yes_directional) * 1000.0 if yes_directional is not None else None,
            "no_cents_per_10btc": abs(no_directional) * 1000.0 if no_directional is not None else None,
            "local_yes_beta_90s": local_yes,
            "local_no_beta_90s": local_no,
            "quote_sum": quote_sum,
            "quote_overround": overround,
            "price_arc_phase": cur.get("price_arc_phase"),
            "arc_direction": cur.get("arc_direction"),
            "battlefield_class": cur.get("battlefield_class"),
            "cage_state": cur.get("cage_state"),
            "dragon_state": cur.get("dragon_state"),
            "target_migration_state": cur.get("target_migration_state"),
            "valid_move": valid_move,
            "note": "observer only; raw seconds and target distance retained for later calibration",
        })

    # ------------------------------------------------------------------
    # Second Spear — entry attempt observer
    # ------------------------------------------------------------------
    def before_entry_attempt(self, ticker: str, side: str, ask, signal: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        s = self._snapshot(ticker, now=now)
        parent = self._active_position(side, ticker)
        return {
            "now": now,
            "snapshot": s,
            "parent_before": dict(parent) if isinstance(parent, dict) else None,
            "signal": dict(signal or {}),
            "ask": _f(ask),
            "ticker": ticker,
            "side": side,
        }

    def after_entry_attempt(self, ctx: Dict[str, Any], entered: bool) -> None:
        ticker = str(ctx.get("ticker") or "")
        side = str(ctx.get("side") or "")
        ask = _f(ctx.get("ask"))
        now = _f(ctx.get("now"), time.time()) or time.time()
        signal = ctx.get("signal") or {}
        s = self._snapshot(ticker, now=now)

        if entered:
            pos = self._active_position(side, ticker)
            if isinstance(pos, dict):
                tid = _position_trade_id(pos, f"{ticker}:{side}:{now:.3f}")
                self._register_parent_entry(tid, pos, s, ask, signal, now)
                self._detect_real_reload(tid, pos, s, ask, signal, now)
            return

        parent = ctx.get("parent_before")
        if not isinstance(parent, dict):
            return

        parent_tid = _position_trade_id(parent, f"{ticker}:{side}:PARENT")
        parent_entry = _position_entry(parent)
        parent_entry_ts = _position_entry_ts(parent)
        parent_bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
        parent_roi = None
        if parent_entry not in (None, 0.0) and parent_bid is not None:
            parent_roi = (parent_bid - parent_entry) / parent_entry

        signal_grade, setup_grade, score, reason = _grade(signal)
        strong = int(
            signal_grade.upper() in ("A", "A+")
            or setup_grade.upper() in ("A", "A+", "CONFIRMED")
            or score >= 5
        )

        chapter_score, chapter_label, chapter_reasons = self._chapter_change(
            parent_tid, ticker, side, s
        )

        key = (ticker, side)
        cooldown_elapsed = now - self.last_spawn_ts.get(key, 0.0)
        spawn = bool(
            strong
            and (
                chapter_label == "NEW_STRUCTURAL_CHAPTER"
                or cooldown_elapsed >= 30.0
            )
        )

        candidate_bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
        premium_delta = ask - parent_entry if ask is not None and parent_entry is not None else None

        common = self._spear_context_row(
            parent_tid, ticker, side, ask, candidate_bid,
            signal_grade, setup_grade, score, reason, strong,
            parent_entry, parent_bid, parent_roi, premium_delta,
            (now - parent_entry_ts) if parent_entry_ts else None,
            s, chapter_score, chapter_label, chapter_reasons,
        )

        spear_id = ""
        if spawn and ask is not None and ask > 0:
            self.spear_counter += 1
            spear_id = f"SP{self.spear_counter:05d}"
            self.last_spawn_ts[key] = now
            self.last_candidate_signature[key] = self._context_signature(s)
            self.spears[spear_id] = {
                "spear_id": spear_id,
                "parent_trade_id": parent_tid,
                "ticker": ticker,
                "side": side,
                "entry_ask": ask,
                "created": now,
                "btc_entry": _f(s.get("btc_price")),
                "target_distance_entry": _f(s.get("target_distance")),
                "mfe": 0.0,
                "mae": 0.0,
                "last_bid": candidate_bid,
                "horizons_done": set(),
                "parent_exit_marked": False,
                "contract_finalized": False,
                "base": dict(common),
            }
            print(
                f"🗡️ SECOND SPEAR SHADOW | {spear_id} | parent #{parent_tid} {side} "
                f"| ask={ask:.3f} | {chapter_label} | score={score}"
            )

        _write(SECOND_SPEAR_LOG, SECOND_SPEAR_FIELDS, {
            **common,
            "event": "CONCURRENT_CANDIDATE",
            "spear_id": spear_id,
            "spawned_shadow_child": int(bool(spear_id)),
            "policy": "OBSERVE_CANDIDATE",
            "note": "no paper authority; reinforcement research only",
        })

    def _register_parent_entry(self, trade_id, pos, s, ask, signal, now):
        signal_grade, setup_grade, score, reason = _grade(signal)
        self.parent_context[trade_id] = {
            "trade_id": trade_id,
            "ticker": str(pos.get("ticker") or s.get("ticker") or ""),
            "side": str(pos.get("side") or ""),
            "entry_ts": _position_entry_ts(pos) or now,
            "entry_ask": _position_entry(pos) or ask,
            "arc_id": s.get("arc_id"),
            "price_arc_phase": s.get("price_arc_phase"),
            "battlefield_class": s.get("battlefield_class"),
            "boss_id": s.get("boss_id"),
            "boss_side": s.get("boss_side"),
            "hand_side": s.get("hand_side"),
            "cage_state": s.get("cage_state"),
            "dragon_state": s.get("dragon_state"),
            "signature": self._context_signature(s),
            "signal_grade": signal_grade,
            "setup_grade": setup_grade,
            "score": score,
            "reason": reason,
        }

    def _chapter_change(self, parent_tid, ticker, side, s):
        parent = self.parent_context.get(parent_tid)
        reasons = []
        score = 0

        if parent is None:
            current_sig = self._context_signature(s)
            last_sig = self.last_candidate_signature.get((ticker, side))
            if last_sig and current_sig == last_sig:
                return 0, "REPEATED_ECHO", "same_candidate_signature"
            return 1, "PARTIAL_REFRESH", "parent_entry_context_unavailable"

        parent_arc = str(parent.get("arc_id") or "")
        current_arc = str(s.get("arc_id") or "")
        if parent_arc and current_arc and current_arc != parent_arc:
            score += 2
            reasons.append("new_arc_id")

        if s.get("price_arc_phase") != parent.get("price_arc_phase"):
            score += 1
            reasons.append("phase_changed")
        if s.get("battlefield_class") != parent.get("battlefield_class"):
            score += 1
            reasons.append("battlefield_changed")

        if s.get("boss_id") and parent.get("boss_id") and s.get("boss_id") != parent.get("boss_id"):
            score += 2
            reasons.append("new_boss_id")
        else:
            if s.get("boss_side") != parent.get("boss_side"):
                score += 1
                reasons.append("boss_side_changed")
            if s.get("hand_side") != parent.get("hand_side"):
                score += 1
                reasons.append("hand_side_changed")

        if s.get("cage_state") != parent.get("cage_state"):
            score += 1
            reasons.append("cage_changed")
        if s.get("dragon_state") != parent.get("dragon_state"):
            score += 1
            reasons.append("dragon_state_changed")

        if "new_arc_id" in reasons or "new_boss_id" in reasons or score >= 3:
            label = "NEW_STRUCTURAL_CHAPTER"
        elif score >= 1:
            label = "PARTIAL_REFRESH"
        else:
            label = "REPEATED_ECHO"

        return score, label, ";".join(reasons) or "no_material_structural_change"

    @staticmethod
    def _spear_context_row(
        parent_tid, ticker, side, candidate_ask, candidate_bid,
        signal_grade, setup_grade, score, reason, strong,
        parent_entry, parent_bid, parent_roi, premium_delta,
        seconds_since_parent_entry, s, chapter_score, chapter_label,
        chapter_reasons,
    ):
        return {
            "parent_trade_id": parent_tid,
            "ticker": ticker,
            "side": side,
            "candidate_ask": candidate_ask,
            "candidate_bid": candidate_bid,
            "signal_grade": signal_grade,
            "setup_grade": setup_grade,
            "a_plus_score": score,
            "signal_reason": reason,
            "strong_candidate": strong,
            "parent_entry_ask": parent_entry,
            "parent_live_bid": parent_bid,
            "parent_live_roi": parent_roi,
            "premium_vs_parent_entry": premium_delta,
            "seconds_since_parent_entry": seconds_since_parent_entry,
            "seconds_left": s.get("seconds_left"),
            "btc_price": s.get("btc_price"),
            "target": s.get("target"),
            "target_distance": s.get("target_distance"),
            "range60": s.get("range60"),
            "arc_id": s.get("arc_id"),
            "arc_direction": s.get("arc_direction"),
            "price_arc_phase": s.get("price_arc_phase"),
            "remaining_capacity": s.get("remaining_capacity"),
            "battlefield_class": s.get("battlefield_class"),
            "zoom_mode": s.get("zoom_mode"),
            "boss_id": s.get("boss_id"),
            "boss_side": s.get("boss_side"),
            "hand_side": s.get("hand_side"),
            "cage_state": s.get("cage_state"),
            "dragon_state": s.get("dragon_state"),
            "target_migration_state": s.get("target_migration_state"),
            "chapter_change_score": chapter_score,
            "chapter_label": chapter_label,
            "chapter_reasons": chapter_reasons,
        }

    # ------------------------------------------------------------------
    # Second Spear lifecycle
    # ------------------------------------------------------------------
    def _update_spears(self, s: Dict[str, Any]) -> None:
        now = _f(s.get("now"), time.time()) or time.time()
        ticker = str(s.get("ticker") or "")

        for spear in list(self.spears.values()):
            if spear.get("contract_finalized") or spear.get("ticker") != ticker:
                continue

            side = spear["side"]
            bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
            if bid is None:
                continue

            entry = spear["entry_ask"]
            roi = (bid - entry) / entry if entry else None
            if roi is not None:
                spear["mfe"] = max(spear.get("mfe", 0.0), roi)
                spear["mae"] = min(spear.get("mae", 0.0), roi)
            spear["last_bid"] = bid

            parent = self._active_position(side, ticker)
            parent_active = False
            parent_roi = None
            if isinstance(parent, dict):
                parent_tid = _position_trade_id(parent, "")
                parent_active = parent_tid == spear["parent_trade_id"]
                pentry = _position_entry(parent)
                if parent_active and pentry not in (None, 0.0):
                    parent_roi = (bid - pentry) / pentry

            age = now - spear["created"]
            for horizon in (15, 30, 60, 120):
                if age >= horizon and horizon not in spear["horizons_done"]:
                    spear["horizons_done"].add(horizon)
                    self._spear_outcome(
                        spear, s, f"OUTCOME_{horizon}S", horizon, bid, roi,
                        parent_active, parent_roi, "STACK_HOLD_HORIZON",
                        self._roi_label(roi),
                        note="independent second-spear mark; parent authority unchanged",
                    )

    def _spear_outcome(
        self, spear, s, event, horizon, bid, roi, parent_active,
        parent_roi, policy, result_label, exit_reason="", note="",
    ):
        btc_now = _f(s.get("btc_price"))
        td_now = _f(s.get("target_distance"))
        btc_move = None
        td_change = None
        if btc_now is not None and spear.get("btc_entry") is not None:
            btc_move = btc_now - spear["btc_entry"]
        if td_now is not None and spear.get("target_distance_entry") is not None:
            td_change = td_now - spear["target_distance_entry"]

        _write(SECOND_SPEAR_LOG, SECOND_SPEAR_FIELDS, {
            **spear.get("base", {}),
            "event": event,
            "spear_id": spear["spear_id"],
            "spawned_shadow_child": 1,
            "shadow_age_sec": max(0.0, (_f(s.get("now"), time.time()) or time.time()) - spear["created"]),
            "current_bid": bid,
            "shadow_roi": roi,
            "shadow_mfe_roi": spear.get("mfe"),
            "shadow_mae_roi": spear.get("mae"),
            "btc_move_from_candidate": btc_move,
            "target_distance_change": td_change,
            "parent_active": int(bool(parent_active)),
            "parent_current_roi": parent_roi,
            "horizon_sec": horizon,
            "policy": policy,
            "result_label": result_label,
            "exit_reason": exit_reason,
            "note": note,
        })

    @staticmethod
    def _roi_label(roi: Optional[float]) -> str:
        if roi is None:
            return "UNKNOWN"
        if roi > 0.01:
            return "WIN"
        if roi < -0.01:
            return "LOSS"
        return "FLAT"

    def on_real_exit(self, position, bid, actual_roi, reason, pnl) -> None:
        if not isinstance(position, dict):
            return
        ticker = str(position.get("ticker") or "")
        side = str(position.get("side") or "")
        if side not in ("YES", "NO"):
            return

        now = time.time()
        tid = _position_trade_id(position, f"{ticker}:{side}:EXIT")
        exit_bid = _f(bid)
        exit_roi = _f(actual_roi)
        exit_pnl = _f(pnl)

        self.last_real_exit[(ticker, side)] = {
            "trade_id": tid,
            "ts": now,
            "bid": exit_bid,
            "roi": exit_roi,
            "pnl": exit_pnl,
            "reason": str(reason or ""),
        }

        s = self._snapshot(ticker, now=now)
        for spear in self.spears.values():
            if spear.get("ticker") != ticker or spear.get("side") != side:
                continue
            if spear.get("parent_trade_id") != tid or spear.get("parent_exit_marked"):
                continue

            spear["parent_exit_marked"] = True
            child_roi = None
            if exit_bid is not None and spear.get("entry_ask"):
                child_roi = (exit_bid - spear["entry_ask"]) / spear["entry_ask"]

            self._spear_outcome(
                spear, s, "PARENT_EXIT_MARK", None, exit_bid, child_roi,
                False, exit_roi, "STACK_INHERIT_PARENT_EXIT",
                self._roi_label(child_roi), str(reason or ""),
                "counterfactual only; child was never a real paper position",
            )

    def _detect_real_reload(self, new_trade_id, pos, s, ask, signal, now):
        ticker = str(pos.get("ticker") or s.get("ticker") or "")
        side = str(pos.get("side") or "")
        prior = self.last_real_exit.get((ticker, side))
        if not prior:
            return

        age = now - prior["ts"]
        if age < 0 or age > 600:
            return

        signal_grade, setup_grade, score, reason = _grade(signal)
        current_bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))

        _write(SECOND_SPEAR_LOG, SECOND_SPEAR_FIELDS, {
            "event": "REAL_RELOAD_ENTRY",
            "parent_trade_id": prior.get("trade_id"),
            "ticker": ticker,
            "side": side,
            "candidate_ask": ask,
            "candidate_bid": current_bid,
            "signal_grade": signal_grade,
            "setup_grade": setup_grade,
            "a_plus_score": score,
            "signal_reason": reason,
            "strong_candidate": int(
                signal_grade.upper() in ("A", "A+")
                or setup_grade.upper() in ("A", "A+", "CONFIRMED")
                or score >= 5
            ),
            "parent_live_bid": prior.get("bid"),
            "parent_live_roi": prior.get("roi"),
            "seconds_since_parent_entry": age,
            "seconds_left": s.get("seconds_left"),
            "btc_price": s.get("btc_price"),
            "target": s.get("target"),
            "target_distance": s.get("target_distance"),
            "range60": s.get("range60"),
            "arc_id": s.get("arc_id"),
            "arc_direction": s.get("arc_direction"),
            "price_arc_phase": s.get("price_arc_phase"),
            "remaining_capacity": s.get("remaining_capacity"),
            "battlefield_class": s.get("battlefield_class"),
            "zoom_mode": s.get("zoom_mode"),
            "boss_id": s.get("boss_id"),
            "boss_side": s.get("boss_side"),
            "hand_side": s.get("hand_side"),
            "cage_state": s.get("cage_state"),
            "dragon_state": s.get("dragon_state"),
            "target_migration_state": s.get("target_migration_state"),
            "chapter_label": "REAL_EXIT_THEN_RELOAD",
            "chapter_reasons": f"prior_exit_reason={prior.get('reason')}",
            "spawned_shadow_child": 0,
            "shadow_age_sec": age,
            "parent_active": 0,
            "parent_current_roi": prior.get("roi"),
            "policy": "EXIT_AND_RELOAD_REAL_AUTHORITY",
            "exit_reason": prior.get("reason"),
            "note": f"new real trade #{new_trade_id} after same-side exit; descriptive only",
        })

        print(
            f"🔄 REAL RELOAD OBSERVED | old #{prior.get('trade_id')} -> "
            f"new #{new_trade_id} {side} | {age:.1f}s after exit"
        )

    def _finalize_contract_spears(self, ticker: str, s: Dict[str, Any], now: float) -> None:
        s = dict(s)
        s["now"] = now
        for spear in self.spears.values():
            if spear.get("ticker") != ticker or spear.get("contract_finalized"):
                continue

            bid = spear.get("last_bid")
            roi = None
            if bid is not None and spear.get("entry_ask"):
                roi = (bid - spear["entry_ask"]) / spear["entry_ask"]

            btc = _f(s.get("btc_price"))
            target = _f(s.get("target"))
            settle_side = None
            if btc is not None and target is not None:
                settle_side = "YES" if btc >= target else "NO"

            self._spear_outcome(
                spear, s, "CONTRACT_ROLLOVER_MARK", None, bid, roi,
                False, None, "STACK_HOLD_TO_ROLLOVER", self._roi_label(roi),
                note=f"last observable bid before rollover; proxy_settlement_side={settle_side}",
            )
            spear["contract_finalized"] = True

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------
    def _write_manifest(self) -> None:
        _write(MANIFEST_LOG, MANIFEST_FIELDS, {
            "version": VERSION,
            "base_version": "V9.4K -> V9.4J -> V9.4I frozen paper authority",
            "paper_authority": "FROZEN_BASE_ONLY",
            "start_local": _local(_START_TS),
            "pid": os.getpid(),
            "research_layers": "SECOND_SPEAR;SETTLEMENT_ELASTICITY",
            "second_spear_doctrine":
                "Reinforcement requires a fresh reason; repeated A+ is not automatically a new chapter.",
            "elasticity_doctrine":
                "The same BTC displacement has different quote meaning as clock and target distance change.",
        })


brain = V94LShadowBrain()
_HOOKS_INSTALLED = False


def install_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return

    # Install J + K exactly as a normal V9.4K launch would.
    k.install_hooks()
    _HOOKS_INSTALLED = True

    # 1) General market tick. K/J/base run first; L only observes afterward.
    original_council = getattr(core, "v94e_kings_council_observer")

    def council_wrapper(ticker, yes_ask, no_ask, close_ts, now=None):
        result = original_council(ticker, yes_ask, no_ask, close_ts, now)
        try:
            brain.on_tick(ticker, yes_ask, no_ask, close_ts, now)
        except Exception as exc:
            print(f"⚠️ V9.4L tick shadow error: {exc}")
        return result

    core.v94e_kings_council_observer = council_wrapper

    # 2) Entry attempt. J/base make the decision first; L only records result.
    original_enter = getattr(core, "paper_enter")

    def paper_enter_wrapper(ticker, side, ask, signal):
        ctx = None
        try:
            ctx = brain.before_entry_attempt(ticker, side, ask, signal or {})
        except Exception as exc:
            print(f"⚠️ V9.4L pre-entry shadow error: {exc}")

        entered = original_enter(ticker, side, ask, signal)

        try:
            if ctx is not None:
                brain.after_entry_attempt(ctx, bool(entered))
        except Exception as exc:
            print(f"⚠️ V9.4L Second Spear shadow error: {exc}")
        return entered

    core.paper_enter = paper_enter_wrapper

    # 3) Trade finalization. K/base finalize first; L logs counterfactual afterward.
    original_finalize = getattr(core, "v94b_finalize_trade_shadows")

    def finalize_wrapper(position, bid, actual_roi, reason, pnl):
        result = original_finalize(position, bid, actual_roi, reason, pnl)
        try:
            brain.on_real_exit(position, bid, actual_roi, reason, pnl)
        except Exception as exc:
            print(f"⚠️ V9.4L exit shadow error: {exc}")
        return result

    core.v94b_finalize_trade_shadows = finalize_wrapper


async def main() -> None:
    install_hooks()
    print("=" * 100)
    print(f"TACHYOS {VERSION} — SECOND SPEAR / SETTLEMENT ELASTICITY LAB")
    print(f"RUN ID: {RUN_ID} | SESSION: {SESSION_ID}")
    print("PAPER ONLY | V9.4I paper authority remains FROZEN.")
    print("V9.4J + V9.4K + V9.4L are observer/shadow intelligence only.")
    print("")
    print("SECOND SPEAR:")
    print("  Study HOLD_ONE vs STACK_SECOND vs EXIT_AND_RELOAD.")
    print("  A repeated A+ signal is NOT automatically a fresh structural chapter.")
    print("")
    print("SETTLEMENT ELASTICITY:")
    print("  Measure YES/NO quote response to BTC over 3/6/9 seconds, conditioned on")
    print("  time remaining + target distance + recent range.")
    print("")
    print("No V9.4L function may place, block, resize, flip, or close a paper trade.")
    print("=" * 100)
    await core.main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTachyos V9.4L stopped by operator (Ctrl+C).")
