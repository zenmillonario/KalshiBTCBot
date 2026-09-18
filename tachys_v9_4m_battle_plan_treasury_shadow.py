"""
TACHYOS V9.4M — BATTLE PLAN / TREASURY / CHAPTER LAB
=====================================================

PAPER ONLY. SHADOW / RESEARCH ONLY.

V9.4M deliberately imports V9.4K (which imports J -> frozen V9.4I authority)
instead of importing V9.4L.  The V9.4L long run showed that the original
Second Spear was too permissive and that full-resolution Settlement Elasticity
created a very large CSV.  M keeps the frozen authority and all J/K observers,
then replaces the L experiments with narrower, cheaper shadow observers:

  1) TREASURY DEFENSE + BOMBE THESIS INTEGRITY
     Track MFE, giveback, structural contradictions, and counterfactual
     'defend treasury' moments after a trade has already proven itself.

  2) CAMPAIGN / CHAPTER LEDGER
     Measure whether a second/third real entry is a genuinely fresh structural
     chapter or continued fighting inside the same chapter.

  3) FIELD MEDIC EVACUATION QUALIFIER
     Observe K's LOCAL_THESIS_TERMINAL_CANDIDATE state and classify whether
     the terminal call is structurally qualified, conflicted, or better treated
     as a treasury-defense question.  It never exits a trade.

  4) SECOND SPEAR V2
     Re-test blocked same-side entry attempts with stricter chapter identity
     and price-quality requirements.  Worse-price chasing is never qualified
     by the V2 shadow policy.

  5) ARC LEG / HARVEST LEDGER + TWIN-PEAK 30-GATE WATCH
     Treat each structural leg as its own measurable battle.  Record the best
     quote excursion, giveback at leg end, and candidate twin-peak/twin-valley
     patterns before an EMA30 gate break.

  6) SETTLEMENT ELASTICITY LITE
     Sample 3/6/9-second quote response only every ~3 seconds instead of every
     market tick, retaining time, target distance, range-normalized distance,
     and quote saturation context without recreating the huge V9.4L file.

Doctrine:
  - A dead position may be abandoned. The battlefield is never abandoned.
  - A profitable position is not automatically finished; treasury defense is
    conditional on structural deterioration.
  - A second/third entry needs a new chapter, not merely a repeated signal.
  - Three deteriorating arms remain a spotlight, never a rule.
  - Poetry can suggest the question; math must answer it.
  - V9.4M NEVER places, blocks, resizes, flips, or closes a paper trade.
"""

from __future__ import annotations

import asyncio
import csv
import math
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import tachys_v9_4k_field_medic_flexible_cage_shadow as k

j = k.j
core = k.core

VERSION = "V9.4M"
ET = k.ET
_START_TS = time.time()
RUN_ID = datetime.now(ET).strftime("M%Y%m%d_%H%M%S")
SESSION_ID = f"{RUN_ID}_PID{os.getpid()}"

os.environ["TACHYOS_V94M_RUN_ID"] = RUN_ID
os.environ["TACHYOS_V94M_SESSION_ID"] = SESSION_ID

COMMON = ["timestamp", "run_id", "session_id"]

TREASURY_LOG = "tachys_treasury_defense_v9_4m.csv"
CAMPAIGN_LOG = "tachys_campaign_ledger_v9_4m.csv"
MEDIC_QUALIFIER_LOG = "tachys_medic_qualifier_v9_4m.csv"
SPEAR_V2_LOG = "tachys_second_spear_v2_v9_4m.csv"
LEG_LOG = "tachys_leg_harvest_v9_4m.csv"
TWIN_GATE_LOG = "tachys_twin_peak_30_gate_v9_4m.csv"
ELASTICITY_LITE_LOG = "tachys_settlement_elasticity_lite_v9_4m.csv"
MANIFEST_LOG = "tachys_run_manifest_v9_4m.csv"

TREASURY_FIELDS = COMMON + [
    "event", "candidate_id", "trade_id", "ticker", "side", "qty",
    "entry_ask", "current_bid", "current_roi", "mfe_roi", "mae_roi",
    "giveback_points", "retain_fraction", "proven_level",
    "thesis_integrity", "contradiction_points", "contradictions",
    "holdability_label", "treasury_state", "shadow_action",
    "candidate_bid", "candidate_roi", "candidate_age_sec", "horizon_sec",
    "mark_bid", "mark_roi", "actual_exit_bid", "actual_exit_roi",
    "actual_exit_pnl", "candidate_vs_actual_pnl_delta",
    "btc_price", "target", "target_distance", "range60", "seconds_left",
    "arc_id", "arc_direction", "price_arc_phase", "remaining_capacity",
    "battlefield_class", "boss_id", "boss_side", "hand_side",
    "cage_state", "dragon_state", "target_migration_state", "note",
]

CAMPAIGN_FIELDS = COMMON + [
    "event", "trade_id", "ticker", "side", "contract_trade_number",
    "entry_ask", "exit_bid", "actual_roi", "actual_pnl", "exit_reason",
    "seconds_since_prior_exit", "prior_trade_id", "prior_side",
    "chapter_score", "chapter_label", "chapter_reasons",
    "arc_id", "prior_arc_id", "arc_direction", "prior_arc_direction",
    "price_arc_phase", "prior_price_arc_phase",
    "boss_id", "prior_boss_id", "boss_side", "prior_boss_side",
    "hand_side", "prior_hand_side", "battlefield_class", "prior_battlefield_class",
    "cage_state", "prior_cage_state", "dragon_state", "prior_dragon_state",
    "target_migration_state", "prior_target_migration_state",
    "target_distance", "prior_target_distance", "seconds_left",
    "signal_grade", "setup_grade", "strategy", "note",
]

MEDIC_FIELDS = COMMON + [
    "event", "trade_id", "ticker", "side", "entry_ask", "current_bid",
    "current_roi", "mfe_roi", "wound_low_bid", "wound_depth",
    "recovery_from_low", "seconds_left", "qualifier_score", "qualifier_label",
    "qualifier_reasons", "arc_direction", "price_arc_phase",
    "boss_side", "hand_side", "battlefield_class", "cage_state",
    "dragon_state", "target_distance", "target_migration_state",
    "treasury_overlap", "note",
]

SPEAR_FIELDS = COMMON + [
    "event", "spear_id", "parent_trade_id", "ticker", "side",
    "candidate_ask", "current_bid", "parent_entry_ask", "parent_current_bid",
    "parent_current_roi", "premium_vs_parent", "price_quality",
    "seconds_since_parent_entry", "seconds_left", "signal_grade", "setup_grade",
    "signal_score", "signal_reason", "chapter_score", "chapter_label",
    "chapter_reasons", "thesis_integrity", "contradiction_points",
    "qualified_v2", "qualification_reasons", "arc_id", "arc_direction",
    "price_arc_phase", "remaining_capacity", "boss_id", "boss_side",
    "hand_side", "battlefield_class", "cage_state", "dragon_state",
    "target_distance", "target_migration_state", "horizon_sec",
    "mark_bid", "shadow_roi", "shadow_mfe_roi", "shadow_mae_roi",
    "parent_active", "exit_reason", "note",
]

LEG_FIELDS = COMMON + [
    "event", "ticker", "leg_id", "arc_id", "direction", "side",
    "start_ts", "end_ts", "duration_sec", "start_btc", "end_btc",
    "btc_move", "btc_amplitude", "start_side_bid", "end_side_bid",
    "max_side_bid", "min_side_bid", "max_quote_roi", "end_quote_roi",
    "quote_giveback_points", "start_target_distance", "end_target_distance",
    "start_seconds_left", "end_seconds_left", "start_phase", "end_phase",
    "start_battlefield", "end_battlefield", "start_cage", "end_cage",
    "start_dragon", "end_dragon", "boss_side", "hand_side",
    "harvest_20_seen", "harvest_30_seen", "harvest_40_seen", "note",
]

TWIN_FIELDS = COMMON + [
    "event", "pattern_id", "ticker", "pattern_type", "point1_ts", "point2_ts",
    "point1_btc", "point2_btc", "valley_or_peak_btc", "point_gap_sec",
    "point2_vs_point1", "range60", "ema30_at_point1", "ema30_at_point2",
    "point1_sep_ema9", "point2_sep_ema9", "weakening_score", "reasons",
    "seconds_left", "target_distance", "watch_age_sec", "gate_price",
    "break_btc", "break_distance", "note",
]

ELASTICITY_FIELDS = COMMON + [
    "ticker", "window_sec", "sample_age_sec", "seconds_left", "time_bucket",
    "btc_price", "target", "target_distance", "abs_target_distance", "range60",
    "target_distance_norm60", "distance_bucket", "yes_ask", "no_ask",
    "yes_bid", "no_bid", "quote_bucket_yes", "quote_bucket_no",
    "btc_change", "yes_bid_change", "no_bid_change", "yes_directional_beta",
    "no_directional_beta", "yes_cents_per_10btc", "no_cents_per_10btc",
    "arc_direction", "price_arc_phase", "battlefield_class", "cage_state",
    "dragon_state", "valid_move", "note",
]

MANIFEST_FIELDS = COMMON + [
    "version", "base_version", "paper_authority", "start_local", "pid",
    "research_layers", "doctrine", "l_imported", "note",
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


def _write(path: str, fields: List[str], row: Dict[str, Any]) -> None:
    payload = {
        "timestamp": row.get("timestamp", _utc()),
        "run_id": RUN_ID,
        "session_id": SESSION_ID,
        **row,
    }
    new_file = (not os.path.exists(path)) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow({field: payload.get(field, "") for field in fields})


def _side_bid(side: str, yes_ask, no_ask) -> Optional[float]:
    try:
        return j._side_bid(side, _f(yes_ask), _f(no_ask))
    except Exception:
        yes = _f(yes_ask)
        no = _f(no_ask)
        if side == "YES" and no is not None:
            return max(0.0, min(1.0, 1.0 - no))
        if side == "NO" and yes is not None:
            return max(0.0, min(1.0, 1.0 - yes))
        return None


def _side_direction(side: str) -> str:
    return "UP" if side == "YES" else "DOWN"


def _opposite_direction(side: str) -> str:
    return "DOWN" if side == "YES" else "UP"


def _position_entry(pos: Dict[str, Any]) -> Optional[float]:
    return _f(_safe(pos, "entry_ask", "ask", "entry_price", "price", "fill_price"))


def _position_trade_id(pos: Dict[str, Any], fallback="") -> str:
    v = _safe(pos, "trade_id", "id", "paper_trade_id", "position_id")
    return str(v) if v not in (None, "") else str(fallback)


def _position_entry_ts(pos: Dict[str, Any]) -> Optional[float]:
    return _f(_safe(pos, "entry_time", "entry_ts", "opened_ts", "open_ts", "ts", "timestamp"))


def _signal_meta(signal: Dict[str, Any]) -> Tuple[str, str, int, str, str]:
    grade = str(_safe(signal, "signal_grade", default="") or "")
    setup = str(_safe(signal, "setup_grade", default="") or "")
    score = _i(_safe(signal, "a_plus_score", "score", default=0), 0)
    reason = str(_safe(signal, "early_exception_reasons", "a_plus_reasons", "reason", "reasons", default="") or "")
    strategy = str(_safe(signal, "strategy", default="CORE") or "CORE")
    return grade, setup, score, reason, strategy


def _quote_bucket(price: Optional[float]) -> str:
    if price is None:
        return "UNKNOWN"
    if price < 0.10:
        return "SATURATED_LOW_LT10"
    if price < 0.30:
        return "LOW_10_30"
    if price < 0.70:
        return "MID_30_70"
    if price < 0.90:
        return "HIGH_70_90"
    return "SATURATED_HIGH_GE90"


def _time_bucket(sec: Optional[float]) -> str:
    if sec is None:
        return "UNKNOWN"
    if sec > 540:
        return ">9M"
    if sec > 360:
        return "6_9M"
    if sec > 180:
        return "3_6M"
    if sec > 90:
        return "90S_3M"
    if sec > 30:
        return "30_90S"
    return "LT30S"


def _distance_bucket(dist: Optional[float], r60: Optional[float]) -> str:
    if dist is None:
        return "UNKNOWN"
    ad = abs(dist)
    if r60 is not None and r60 > 0:
        n = ad / max(1.0, r60)
        if n < 0.5:
            return "NEAR_LT0.5R"
        if n < 1.0:
            return "MID_0.5_1R"
        if n < 2.0:
            return "FAR_1_2R"
        return "VERY_FAR_GE2R"
    if ad < 25:
        return "NEAR_LT25"
    if ad < 75:
        return "MID_25_75"
    return "FAR_GE75"


class V94MShadowBrain:
    def __init__(self):
        self.trade_state: Dict[str, Dict[str, Any]] = {}
        self.treasury_candidates: Dict[str, Dict[str, Any]] = {}
        self.treasury_counter = 0

        self.contract_trade_count: Dict[str, int] = defaultdict(int)
        self.last_exit_by_ticker: Dict[str, Dict[str, Any]] = {}
        self.entry_context_by_trade: Dict[str, Dict[str, Any]] = {}

        self.spear_counter = 0
        self.spears: Dict[str, Dict[str, Any]] = {}
        self.last_spear_signature: Dict[Tuple[str, str, str], Tuple[str, float]] = {}

        self.leg_counter = 0
        self.active_leg: Dict[str, Dict[str, Any]] = {}

        self.market_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1800))
        self.last_turn_ts: Dict[Tuple[str, str], float] = defaultdict(float)
        self.turning_points: Dict[str, deque] = defaultdict(lambda: deque(maxlen=30))
        self.twin_counter = 0
        self.twin_watches: Dict[str, Dict[str, Any]] = {}

        self.elasticity_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=120))
        self.last_elasticity_log: Dict[str, float] = defaultdict(float)

        self.last_treasury_log: Dict[str, float] = defaultdict(float)
        self.last_medic_signature: Dict[str, str] = {}

        self._write_manifest()

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------
    def snapshot(self, ticker: str, yes_ask=None, no_ask=None, close_ts=None, now=None) -> Dict[str, Any]:
        now = time.time() if now is None else float(now)
        snap = dict(getattr(j.brain, "last_snapshot", {}) or {})
        if snap.get("ticker") != ticker:
            try:
                snap = dict(j.brain.snapshot(ticker, yes_ask, no_ask, close_ts, now) or {})
            except Exception:
                snap = dict(getattr(j.brain, "last_snapshot", {}) or {})

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
        pos = positions.get(side)
        if isinstance(pos, dict):
            if ticker is None or str(pos.get("ticker") or "") == str(ticker):
                return pos
        return None

    def _active_positions_for_ticker(self, ticker: str):
        positions = getattr(core, "paper_positions", {}) or {}
        if not isinstance(positions, dict):
            return []
        out = []
        for key, pos in positions.items():
            if not isinstance(pos, dict):
                continue
            pt = str(_safe(pos, "ticker", default="") or "")
            if pt != ticker:
                continue
            side = str(_safe(pos, "side", default=key) or key)
            if side in ("YES", "NO"):
                out.append((side, pos))
        return out

    @staticmethod
    def _context_signature(s: Dict[str, Any]) -> str:
        keys = (
            "arc_id", "arc_direction", "price_arc_phase", "boss_id", "boss_side",
            "hand_side", "battlefield_class", "cage_state", "dragon_state",
            "target_migration_state",
        )
        return "|".join(str(s.get(key) or "") for key in keys)

    @staticmethod
    def _chapter_compare(cur: Dict[str, Any], prior: Optional[Dict[str, Any]]) -> Tuple[int, str, str]:
        if not prior:
            return 9, "FIRST_CHAPTER", "no_prior_chapter"
        score = 0
        reasons = []
        if cur.get("arc_id") and cur.get("arc_id") != prior.get("arc_id"):
            score += 2; reasons.append("new_arc_id")
        if cur.get("arc_direction") and cur.get("arc_direction") != prior.get("arc_direction"):
            score += 1; reasons.append("arc_direction_changed")
        if cur.get("price_arc_phase") and cur.get("price_arc_phase") != prior.get("price_arc_phase"):
            score += 1; reasons.append("phase_changed")
        if cur.get("boss_id") and cur.get("boss_id") != prior.get("boss_id"):
            score += 2; reasons.append("new_boss_id")
        if cur.get("boss_side") and cur.get("boss_side") != prior.get("boss_side"):
            score += 1; reasons.append("boss_side_changed")
        if cur.get("hand_side") and cur.get("hand_side") != prior.get("hand_side"):
            score += 1; reasons.append("hand_changed")
        if cur.get("battlefield_class") and cur.get("battlefield_class") != prior.get("battlefield_class"):
            score += 1; reasons.append("battlefield_changed")
        if cur.get("cage_state") and cur.get("cage_state") != prior.get("cage_state"):
            score += 1; reasons.append("cage_changed")
        if cur.get("dragon_state") and cur.get("dragon_state") != prior.get("dragon_state"):
            score += 1; reasons.append("dragon_changed")
        if cur.get("target_migration_state") and cur.get("target_migration_state") != prior.get("target_migration_state"):
            score += 1; reasons.append("target_migration_changed")
        cd = _f(cur.get("target_distance"))
        pd = _f(prior.get("target_distance"))
        if cd is not None and pd is not None and cd * pd < 0:
            score += 1; reasons.append("target_side_crossed")
        label = "FRESH_CHAPTER" if score >= 5 else ("PARTIAL_RESET" if score >= 3 else "SAME_CHAPTER")
        return score, label, ";".join(reasons) or "context_mostly_unchanged"

    @staticmethod
    def _thesis_integrity(side: str, s: Dict[str, Any]) -> Tuple[int, int, str]:
        contradictions = []
        points = 0
        desired = _side_direction(side)
        arc = s.get("arc_direction")
        if arc in ("UP", "DOWN") and arc != desired:
            points += 2; contradictions.append("arc_opposes")
        if s.get("price_arc_phase") == "CROSS_RESET":
            points += 1; contradictions.append("cross_reset")
        boss = s.get("boss_side")
        if boss in ("YES", "NO") and boss != side:
            points += 2; contradictions.append("boss_opposes")
        hand = s.get("hand_side")
        if hand in ("YES", "NO") and hand != side:
            points += 1; contradictions.append("hand_opposes")
        td = _f(s.get("target_distance"))
        if td is not None:
            if (side == "YES" and td < 0) or (side == "NO" and td > 0):
                points += 1; contradictions.append("target_side_adverse")
        cap = _f(s.get("remaining_capacity"))
        if cap is not None and cap < 0.10:
            points += 1; contradictions.append("low_arc_capacity")
        if s.get("cage_state") == "TRUE_ESCAPE_CANDIDATE":
            points += 1; contradictions.append("true_escape_context")
        integrity = max(0, 9 - points)
        return integrity, points, ";".join(contradictions) or "none"

    # ------------------------------------------------------------------
    # Tick orchestration
    # ------------------------------------------------------------------
    def on_tick(self, ticker, yes_ask=None, no_ask=None, close_ts=None, now=None):
        now = time.time() if now is None else float(now)
        s = self.snapshot(ticker, yes_ask, no_ask, close_ts, now)
        self._record_market_sample(s)
        self._update_leg(s)
        self._detect_turning_points(s)
        self._update_twin_watches(s)
        self._update_treasury(s)
        self._update_medic_qualifier(s)
        self._update_spears(s)
        self._elasticity_lite(s)

    # ------------------------------------------------------------------
    # Treasury Defense / Bombe
    # ------------------------------------------------------------------
    def _trade_state_for(self, tid: str, pos: Dict[str, Any], side: str, s: Dict[str, Any], bid: float) -> Dict[str, Any]:
        entry = _position_entry(pos)
        state = self.trade_state.get(tid)
        if state is None:
            state = {
                "trade_id": tid,
                "ticker": str(pos.get("ticker") or s.get("ticker") or ""),
                "side": side,
                "entry": entry,
                "qty": _i(pos.get("qty"), 0),
                "mfe": -999.0,
                "mae": 999.0,
                "proven": 0,
                "defense_created": False,
                "entry_ts": _position_entry_ts(pos) or s["now"],
            }
            self.trade_state[tid] = state
        roi = (bid - entry) / entry if entry and entry > 0 else 0.0
        state["mfe"] = max(state.get("mfe", roi), roi)
        state["mae"] = min(state.get("mae", roi), roi)
        for level in (20, 30, 40, 50):
            if state["mfe"] >= level / 100.0:
                state["proven"] = max(state.get("proven", 0), level)
        state["last_bid"] = bid
        state["last_roi"] = roi
        state["last_snapshot"] = dict(s)
        return state

    def _update_treasury(self, s: Dict[str, Any]) -> None:
        ticker = str(s.get("ticker") or "")
        now = s["now"]
        for side, pos in self._active_positions_for_ticker(ticker):
            entry = _position_entry(pos)
            bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
            if entry is None or bid is None or entry <= 0:
                continue
            tid = _position_trade_id(pos, f"{ticker}:{side}:{entry:.4f}")
            st = self._trade_state_for(tid, pos, side, s, bid)
            roi = st["last_roi"]
            mfe = st["mfe"]
            giveback = max(0.0, mfe - roi)
            retain = (roi / mfe) if mfe > 1e-9 else None
            integrity, contradictions, why = self._thesis_integrity(side, s)

            if integrity >= 7:
                hold_label = "HIGH_HOLDABILITY"
            elif integrity >= 5:
                hold_label = "MIXED_HOLDABILITY"
            else:
                hold_label = "LOW_HOLDABILITY"

            state = "UNPROVEN"
            action = "OBSERVE_SHADOW"
            if st["proven"] >= 20:
                state = "PROVEN"
                action = "HOLD_OR_DEFEND_RESEARCH"
                if giveback >= 0.12 and (retain is None or retain <= 0.55):
                    state = "TREASURY_GIVEBACK"
                if state == "TREASURY_GIVEBACK" and contradictions >= 2:
                    state = "DEFEND_CANDIDATE"
                    action = "SHADOW_DEFEND_TREASURY"
                elif state == "TREASURY_GIVEBACK" and integrity >= 7:
                    state = "BREATHING_CANDIDATE"
                    action = "SHADOW_ALLOW_BREATHING"

            # Periodic row after the trade is proven, plus state transitions.
            sig = f"{state}|{st['proven']}|{integrity}|{int(giveback*100)}"
            changed = sig != st.get("last_treasury_sig")
            if st["proven"] >= 20 and (changed or now - self.last_treasury_log.get(tid, 0) >= 6.0):
                self._write_treasury_row("ASSESSMENT", st, pos, s, bid, roi, mfe, giveback, retain,
                                         integrity, contradictions, why, hold_label, state, action)
                self.last_treasury_log[tid] = now
                st["last_treasury_sig"] = sig

            if state == "DEFEND_CANDIDATE" and not st.get("defense_created"):
                self.treasury_counter += 1
                cid = f"TD{self.treasury_counter:05d}"
                cand = {
                    "candidate_id": cid, "trade_id": tid, "ticker": ticker, "side": side,
                    "entry": entry, "qty": st.get("qty", 0), "ts": now, "bid": bid,
                    "roi": roi, "mfe": mfe, "mae": st.get("mae", roi),
                    "snapshot": dict(s), "horizons_done": set(), "max_mark_roi": roi,
                    "min_mark_roi": roi, "closed": False,
                }
                self.treasury_candidates[cid] = cand
                st["defense_created"] = True
                st["defense_id"] = cid
                print(f"🏦 TREASURY DEFENSE SHADOW | #{tid} {side} | MFE={mfe:+.1%} now={roi:+.1%} | integrity={integrity}/9")
                self._write_treasury_row("DEFEND_CANDIDATE", st, pos, s, bid, roi, mfe, giveback, retain,
                                         integrity, contradictions, why, hold_label, state, action, candidate=cand)

    def _write_treasury_row(self, event, st, pos, s, bid, roi, mfe, giveback, retain,
                            integrity, contradictions, why, hold_label, state, action,
                            candidate=None, horizon=None, mark_bid=None, mark_roi=None,
                            actual_exit=None):
        candidate = candidate or {}
        actual_exit = actual_exit or {}
        _write(TREASURY_LOG, TREASURY_FIELDS, {
            "event": event, "candidate_id": candidate.get("candidate_id", st.get("defense_id", "")),
            "trade_id": st.get("trade_id"), "ticker": st.get("ticker"), "side": st.get("side"),
            "qty": st.get("qty"), "entry_ask": st.get("entry"), "current_bid": bid,
            "current_roi": roi, "mfe_roi": mfe, "mae_roi": st.get("mae"),
            "giveback_points": giveback, "retain_fraction": retain, "proven_level": st.get("proven"),
            "thesis_integrity": integrity, "contradiction_points": contradictions,
            "contradictions": why, "holdability_label": hold_label,
            "treasury_state": state, "shadow_action": action,
            "candidate_bid": candidate.get("bid"), "candidate_roi": candidate.get("roi"),
            "candidate_age_sec": (s.get("now", time.time()) - candidate.get("ts", s.get("now", time.time()))) if candidate else None,
            "horizon_sec": horizon, "mark_bid": mark_bid, "mark_roi": mark_roi,
            "actual_exit_bid": actual_exit.get("bid"), "actual_exit_roi": actual_exit.get("roi"),
            "actual_exit_pnl": actual_exit.get("pnl"),
            "candidate_vs_actual_pnl_delta": actual_exit.get("delta"),
            "btc_price": s.get("btc_price"), "target": s.get("target"),
            "target_distance": s.get("target_distance"), "range60": s.get("range60"),
            "seconds_left": s.get("seconds_left"), "arc_id": s.get("arc_id"),
            "arc_direction": s.get("arc_direction"), "price_arc_phase": s.get("price_arc_phase"),
            "remaining_capacity": s.get("remaining_capacity"), "battlefield_class": s.get("battlefield_class"),
            "boss_id": s.get("boss_id"), "boss_side": s.get("boss_side"), "hand_side": s.get("hand_side"),
            "cage_state": s.get("cage_state"), "dragon_state": s.get("dragon_state"),
            "target_migration_state": s.get("target_migration_state"),
            "note": "counterfactual only; frozen paper authority unchanged",
        })

    def _update_treasury_candidates(self, s: Dict[str, Any]) -> None:
        # folded into _update_spears call to avoid duplicate bid scans; kept for API clarity
        pass

    # ------------------------------------------------------------------
    # Medic qualifier
    # ------------------------------------------------------------------
    def _update_medic_qualifier(self, s: Dict[str, Any]) -> None:
        ticker = str(s.get("ticker") or "")
        wounds = getattr(k.brain, "wounds", {}) or {}
        if not isinstance(wounds, dict):
            return
        for pkey, w in wounds.items():
            if not isinstance(w, dict) or str(w.get("ticker") or "") != ticker:
                continue
            if w.get("last_state") != "LOCAL_THESIS_TERMINAL_CANDIDATE":
                continue
            side = str(w.get("side") or "")
            if side not in ("YES", "NO"):
                continue
            tid = str(w.get("trade_id") or pkey)
            pos = self._active_position(side, ticker)
            if not pos:
                continue
            entry = _position_entry(pos)
            bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
            if entry is None or bid is None or entry <= 0:
                continue
            st = self._trade_state_for(tid, pos, side, s, bid)
            roi = (bid - entry) / entry
            low = _f(w.get("lowest_bid"), bid) or bid
            wound_depth = max(0.0, (entry - low) / entry)
            recovery = bid - low

            score = 0
            reasons = []
            desired = _side_direction(side)
            if s.get("arc_direction") in ("UP", "DOWN") and s.get("arc_direction") != desired:
                score += 3; reasons.append("arc_opposes")
            else:
                score -= 2; reasons.append("arc_still_aligned")
            td = _f(s.get("target_distance"))
            if td is not None and ((side == "YES" and td < 0) or (side == "NO" and td > 0)):
                score += 2; reasons.append("target_adverse")
            if s.get("price_arc_phase") == "CROSS_RESET":
                score += 1; reasons.append("cross_reset")
            if s.get("boss_side") in ("YES", "NO"):
                if s.get("boss_side") != side:
                    score += 2; reasons.append("boss_opposes")
                else:
                    score -= 1; reasons.append("boss_still_aligned")
            if s.get("hand_side") in ("YES", "NO"):
                if s.get("hand_side") != side:
                    score += 1; reasons.append("hand_opposes")
                else:
                    score -= 1; reasons.append("hand_still_aligned")
            sec = _f(s.get("seconds_left"))
            if sec is not None and sec <= 360:
                score += 1; reasons.append("clock_under_6m")
            if roi <= -0.20:
                score += 1; reasons.append("deep_current_wound")
            treasury_overlap = int(st.get("mfe", 0) >= 0.20)
            if treasury_overlap:
                reasons.append("trade_previously_proven")

            if treasury_overlap and roi >= 0:
                label = "TREASURY_DEFENSE_QUESTION"
            elif score >= 4:
                label = "QUALIFIED_EVACUATION_SHADOW"
            elif score >= 1:
                label = "CONFLICTED_TERMINAL_SHADOW"
            else:
                label = "PATIENCE_OVERRIDE_SHADOW"

            sig = f"{label}|{score}|{round(roi,3)}|{s.get('arc_id')}|{s.get('price_arc_phase')}"
            if self.last_medic_signature.get(tid) == sig:
                continue
            self.last_medic_signature[tid] = sig
            print(f"🩺 M-QUALIFIER | #{tid} {side} | {label} | score={score:+d} ROI={roi:+.1%}")
            _write(MEDIC_QUALIFIER_LOG, MEDIC_FIELDS, {
                "event": "TERMINAL_QUALIFIER", "trade_id": tid, "ticker": ticker, "side": side,
                "entry_ask": entry, "current_bid": bid, "current_roi": roi,
                "mfe_roi": st.get("mfe"), "wound_low_bid": low, "wound_depth": wound_depth,
                "recovery_from_low": recovery, "seconds_left": sec,
                "qualifier_score": score, "qualifier_label": label,
                "qualifier_reasons": ";".join(reasons), "arc_direction": s.get("arc_direction"),
                "price_arc_phase": s.get("price_arc_phase"), "boss_side": s.get("boss_side"),
                "hand_side": s.get("hand_side"), "battlefield_class": s.get("battlefield_class"),
                "cage_state": s.get("cage_state"), "dragon_state": s.get("dragon_state"),
                "target_distance": s.get("target_distance"),
                "target_migration_state": s.get("target_migration_state"),
                "treasury_overlap": treasury_overlap,
                "note": "qualifies K terminal state only; never exits paper trade",
            })

    # ------------------------------------------------------------------
    # Campaign ledger + entry hooks
    # ------------------------------------------------------------------
    def before_entry_attempt(self, ticker: str, side: str, ask: float, signal: Dict[str, Any]) -> Dict[str, Any]:
        s = self.snapshot(ticker, ask if side == "YES" else None, ask if side == "NO" else None, None, time.time())
        active = self._active_position(side, ticker)
        grade, setup, score, reason, strategy = _signal_meta(signal)
        return {
            "ts": time.time(), "ticker": ticker, "side": side, "ask": _f(ask),
            "signal": dict(signal or {}), "snapshot": dict(s), "active_before": dict(active) if active else None,
            "signal_grade": grade, "setup_grade": setup, "signal_score": score,
            "signal_reason": reason, "strategy": strategy,
        }

    def after_entry_attempt(self, ctx: Dict[str, Any], entered: bool) -> None:
        ticker = ctx["ticker"]
        side = ctx["side"]
        s = ctx["snapshot"]
        if entered:
            pos = self._active_position(side, ticker)
            if not pos:
                return
            tid = _position_trade_id(pos, f"{ticker}:{side}:{ctx['ask']}")
            self.contract_trade_count[ticker] += 1
            prior = self.last_exit_by_ticker.get(ticker)
            prior_snap = prior.get("snapshot") if prior else None
            score, label, reasons = self._chapter_compare(s, prior_snap)
            sec_since = None
            if prior and prior.get("ts") is not None:
                sec_since = max(0.0, ctx["ts"] - prior["ts"])
            self.entry_context_by_trade[tid] = dict(s)
            self._trade_state_for(tid, pos, side, s, ctx["ask"])
            _write(CAMPAIGN_LOG, CAMPAIGN_FIELDS, {
                "event": "REAL_ENTRY", "trade_id": tid, "ticker": ticker, "side": side,
                "contract_trade_number": self.contract_trade_count[ticker], "entry_ask": ctx["ask"],
                "seconds_since_prior_exit": sec_since,
                "prior_trade_id": prior.get("trade_id") if prior else "",
                "prior_side": prior.get("side") if prior else "",
                "chapter_score": score, "chapter_label": label, "chapter_reasons": reasons,
                "arc_id": s.get("arc_id"), "prior_arc_id": prior_snap.get("arc_id") if prior_snap else "",
                "arc_direction": s.get("arc_direction"), "prior_arc_direction": prior_snap.get("arc_direction") if prior_snap else "",
                "price_arc_phase": s.get("price_arc_phase"), "prior_price_arc_phase": prior_snap.get("price_arc_phase") if prior_snap else "",
                "boss_id": s.get("boss_id"), "prior_boss_id": prior_snap.get("boss_id") if prior_snap else "",
                "boss_side": s.get("boss_side"), "prior_boss_side": prior_snap.get("boss_side") if prior_snap else "",
                "hand_side": s.get("hand_side"), "prior_hand_side": prior_snap.get("hand_side") if prior_snap else "",
                "battlefield_class": s.get("battlefield_class"), "prior_battlefield_class": prior_snap.get("battlefield_class") if prior_snap else "",
                "cage_state": s.get("cage_state"), "prior_cage_state": prior_snap.get("cage_state") if prior_snap else "",
                "dragon_state": s.get("dragon_state"), "prior_dragon_state": prior_snap.get("dragon_state") if prior_snap else "",
                "target_migration_state": s.get("target_migration_state"),
                "prior_target_migration_state": prior_snap.get("target_migration_state") if prior_snap else "",
                "target_distance": s.get("target_distance"), "prior_target_distance": prior_snap.get("target_distance") if prior_snap else "",
                "seconds_left": s.get("seconds_left"), "signal_grade": ctx.get("signal_grade"),
                "setup_grade": ctx.get("setup_grade"), "strategy": ctx.get("strategy"),
                "note": "real frozen-authority entry; M only labels chapter context",
            })
            return

        # If an actual same-side parent was already active, this is a Second Spear V2 opportunity.
        parent = ctx.get("active_before")
        if parent and str(parent.get("ticker") or "") == ticker:
            self._second_spear_v2_candidate(ctx, parent)

    # ------------------------------------------------------------------
    # Second Spear V2
    # ------------------------------------------------------------------
    def _second_spear_v2_candidate(self, ctx: Dict[str, Any], parent: Dict[str, Any]) -> None:
        s = ctx["snapshot"]
        side = ctx["side"]
        ticker = ctx["ticker"]
        ask = ctx.get("ask")
        parent_entry = _position_entry(parent)
        if ask is None or parent_entry is None or parent_entry <= 0:
            return
        parent_tid = _position_trade_id(parent, f"{ticker}:{side}")
        baseline = self.entry_context_by_trade.get(parent_tid)
        chapter_score, chapter_label, chapter_reasons = self._chapter_compare(s, baseline)
        premium = ask - parent_entry
        if premium <= -0.01:
            quality = "BETTER_PRICE"
        elif premium <= 0.02:
            quality = "SAME_ZONE"
        else:
            quality = "WORSE_PRICE_CHASE"
        integrity, contradiction_points, _ = self._thesis_integrity(side, s)
        grade = ctx.get("signal_grade") or ""
        setup = ctx.get("setup_grade") or ""
        sig_score = ctx.get("signal_score") or 0
        strong = grade in ("A", "A+") or setup == "CONFIRMED" or sig_score >= 5
        sec = _f(s.get("seconds_left"))
        reasons = []
        qualified = True
        if not strong:
            qualified = False; reasons.append("signal_not_strong")
        if quality == "WORSE_PRICE_CHASE":
            qualified = False; reasons.append("worse_price_chase_rejected")
        if chapter_score < 4:
            qualified = False; reasons.append("chapter_not_fresh_enough")
        if sec is None:
            qualified = False; reasons.append("missing_seconds_left")
        elif sec < 60:
            qualified = False; reasons.append("clock_under_60s")
        if integrity < 5:
            qualified = False; reasons.append("low_thesis_integrity")
        if qualified:
            reasons.append("strict_v2_shadow_qualified")

        signature = self._context_signature(s)
        key = (ticker, side, parent_tid)
        prior_sig, prior_ts = self.last_spear_signature.get(key, (None, 0.0))
        now = ctx["ts"]
        if signature == prior_sig and now - prior_ts < 30.0:
            return
        self.last_spear_signature[key] = (signature, now)

        self.spear_counter += 1
        sid = f"SP2{self.spear_counter:05d}"
        parent_bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
        parent_roi = (parent_bid - parent_entry) / parent_entry if parent_bid is not None else None
        cand = {
            "spear_id": sid, "parent_trade_id": parent_tid, "ticker": ticker, "side": side,
            "ask": ask, "ts": now, "qualified": int(qualified), "snapshot": dict(s),
            "signal_grade": ctx.get("signal_grade", ""), "setup_grade": ctx.get("setup_grade", ""),
            "signal_score": ctx.get("signal_score", 0), "signal_reason": ctx.get("signal_reason", ""),
            "horizons_done": set(), "mfe": -999.0, "mae": 999.0, "closed": False,
        }
        self.spears[sid] = cand
        if qualified:
            print(f"⚔️ SECOND SPEAR V2 SHADOW | {sid} parent #{parent_tid} {side} @ {ask:.3f} | {quality} | chapter={chapter_score}")
        self._write_spear("CANDIDATE", cand, s, parent, parent_bid, parent_roi,
                          premium, quality, chapter_score, chapter_label, chapter_reasons,
                          integrity, contradiction_points, ";".join(reasons))

    def _write_spear(self, event, cand, s, parent, parent_bid, parent_roi,
                     premium, quality, chapter_score, chapter_label, chapter_reasons,
                     integrity, contradiction_points, qualification_reasons,
                     horizon=None, mark_bid=None, shadow_roi=None, exit_reason=""):
        grade, setup, score, reason, _ = _signal_meta(cand.get("signal", {}) if isinstance(cand.get("signal"), dict) else {})
        if not grade:
            grade = cand.get("signal_grade", "")
        parent_entry = _position_entry(parent) if parent else None
        entry_ts = _position_entry_ts(parent) if parent else None
        now = _f(s.get("now"), time.time()) or time.time()
        sec_since = (now - entry_ts) if entry_ts is not None else None
        _write(SPEAR_V2_LOG, SPEAR_FIELDS, {
            "event": event, "spear_id": cand.get("spear_id"), "parent_trade_id": cand.get("parent_trade_id"),
            "ticker": cand.get("ticker"), "side": cand.get("side"), "candidate_ask": cand.get("ask"),
            "current_bid": mark_bid, "parent_entry_ask": parent_entry,
            "parent_current_bid": parent_bid, "parent_current_roi": parent_roi,
            "premium_vs_parent": premium, "price_quality": quality,
            "seconds_since_parent_entry": sec_since, "seconds_left": s.get("seconds_left"),
            "signal_grade": cand.get("signal_grade", grade), "setup_grade": cand.get("setup_grade", setup),
            "signal_score": cand.get("signal_score", score), "signal_reason": cand.get("signal_reason", reason),
            "chapter_score": chapter_score, "chapter_label": chapter_label, "chapter_reasons": chapter_reasons,
            "thesis_integrity": integrity, "contradiction_points": contradiction_points,
            "qualified_v2": cand.get("qualified"), "qualification_reasons": qualification_reasons,
            "arc_id": s.get("arc_id"), "arc_direction": s.get("arc_direction"),
            "price_arc_phase": s.get("price_arc_phase"), "remaining_capacity": s.get("remaining_capacity"),
            "boss_id": s.get("boss_id"), "boss_side": s.get("boss_side"), "hand_side": s.get("hand_side"),
            "battlefield_class": s.get("battlefield_class"), "cage_state": s.get("cage_state"),
            "dragon_state": s.get("dragon_state"), "target_distance": s.get("target_distance"),
            "target_migration_state": s.get("target_migration_state"), "horizon_sec": horizon,
            "mark_bid": mark_bid, "shadow_roi": shadow_roi,
            "shadow_mfe_roi": cand.get("mfe"), "shadow_mae_roi": cand.get("mae"),
            "parent_active": int(bool(parent)), "exit_reason": exit_reason,
            "note": "counterfactual only; V2 rejects worse-price chasing by design",
        })

    def _update_spears(self, s: Dict[str, Any]) -> None:
        now = s["now"]
        ticker = str(s.get("ticker") or "")
        for sid, cand in list(self.spears.items()):
            if cand.get("closed") or cand.get("ticker") != ticker:
                continue
            side = cand["side"]
            bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
            if bid is None or not cand.get("ask"):
                continue
            roi = (bid - cand["ask"]) / cand["ask"]
            cand["mfe"] = max(cand.get("mfe", roi), roi)
            cand["mae"] = min(cand.get("mae", roi), roi)
            parent = self._active_position(side, ticker)
            parent_entry = _position_entry(parent) if parent else None
            parent_bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask")) if parent else None
            parent_roi = ((parent_bid - parent_entry) / parent_entry) if parent and parent_bid is not None and parent_entry else None
            baseline = self.entry_context_by_trade.get(cand.get("parent_trade_id"))
            chapter_score, chapter_label, chapter_reasons = self._chapter_compare(s, baseline)
            premium = cand["ask"] - parent_entry if parent_entry is not None else None
            quality = "UNKNOWN"
            if premium is not None:
                quality = "BETTER_PRICE" if premium <= -0.01 else ("SAME_ZONE" if premium <= 0.02 else "WORSE_PRICE_CHASE")
            integrity, cp, _ = self._thesis_integrity(side, s)
            age = now - cand["ts"]
            for h in (15, 30, 60, 120):
                if h in cand["horizons_done"] or age < h:
                    continue
                cand["horizons_done"].add(h)
                self._write_spear(f"OUTCOME_{h}S", cand, s, parent, parent_bid, parent_roi,
                                  premium, quality, chapter_score, chapter_label, chapter_reasons,
                                  integrity, cp, "", horizon=h, mark_bid=bid, shadow_roi=roi)

        # Treasury counterfactual horizons share the same bid scan.
        for cid, cand in list(self.treasury_candidates.items()):
            if cand.get("closed") or cand.get("ticker") != ticker:
                continue
            bid = _side_bid(cand["side"], s.get("yes_ask"), s.get("no_ask"))
            if bid is None:
                continue
            roi = (bid - cand["entry"]) / cand["entry"]
            cand["max_mark_roi"] = max(cand.get("max_mark_roi", roi), roi)
            cand["min_mark_roi"] = min(cand.get("min_mark_roi", roi), roi)
            age = now - cand["ts"]
            for h in (15, 30, 60, 120):
                if h in cand["horizons_done"] or age < h:
                    continue
                cand["horizons_done"].add(h)
                st = self.trade_state.get(cand["trade_id"], {})
                integrity, cp, why = self._thesis_integrity(cand["side"], s)
                hold = "HIGH_HOLDABILITY" if integrity >= 7 else ("MIXED_HOLDABILITY" if integrity >= 5 else "LOW_HOLDABILITY")
                self._write_treasury_row(f"OUTCOME_{h}S", st, {}, s, bid, roi, st.get("mfe", cand["mfe"]),
                                         max(0.0, st.get("mfe", 0) - roi),
                                         (roi / st.get("mfe")) if st.get("mfe", 0) > 1e-9 else None,
                                         integrity, cp, why, hold, "POST_DEFEND_MARK", "COUNTERFACTUAL",
                                         candidate=cand, horizon=h, mark_bid=bid, mark_roi=roi)

    # ------------------------------------------------------------------
    # Arc-leg harvest ledger
    # ------------------------------------------------------------------
    def _update_leg(self, s: Dict[str, Any]) -> None:
        ticker = str(s.get("ticker") or "")
        arc_id = str(s.get("arc_id") or "")
        direction = str(s.get("arc_direction") or "")
        btc = _f(s.get("btc_price"))
        if not ticker or not arc_id or direction not in ("UP", "DOWN") or btc is None:
            return
        side = "YES" if direction == "UP" else "NO"
        bid = _side_bid(side, s.get("yes_ask"), s.get("no_ask"))
        current = self.active_leg.get(ticker)
        if current is None or current.get("arc_id") != arc_id:
            if current is not None:
                self._finalize_leg(current, current.get("last_snapshot", s))
            self.leg_counter += 1
            current = {
                "leg_id": f"LG{self.leg_counter:05d}", "ticker": ticker, "arc_id": arc_id,
                "direction": direction, "side": side, "start_ts": s["now"], "start_btc": btc,
                "min_btc": btc, "max_btc": btc, "start_bid": bid, "min_bid": bid, "max_bid": bid,
                "start_target_distance": _f(s.get("target_distance")), "start_seconds_left": _f(s.get("seconds_left")),
                "start_phase": s.get("price_arc_phase"), "start_battlefield": s.get("battlefield_class"),
                "start_cage": s.get("cage_state"), "start_dragon": s.get("dragon_state"),
                "last_snapshot": dict(s), "harvest20": 0, "harvest30": 0, "harvest40": 0,
            }
            self.active_leg[ticker] = current
        current["min_btc"] = min(current.get("min_btc", btc), btc)
        current["max_btc"] = max(current.get("max_btc", btc), btc)
        if bid is not None:
            current["min_bid"] = bid if current.get("min_bid") is None else min(current["min_bid"], bid)
            current["max_bid"] = bid if current.get("max_bid") is None else max(current["max_bid"], bid)
            if current.get("start_bid") and current["start_bid"] > 0:
                best = (current["max_bid"] - current["start_bid"]) / current["start_bid"]
                current["harvest20"] = int(current["harvest20"] or best >= 0.20)
                current["harvest30"] = int(current["harvest30"] or best >= 0.30)
                current["harvest40"] = int(current["harvest40"] or best >= 0.40)
        current["last_snapshot"] = dict(s)
        current["last_bid"] = bid

    def _finalize_leg(self, leg: Dict[str, Any], s: Dict[str, Any]) -> None:
        end_ts = _f(s.get("now"), time.time()) or time.time()
        end_btc = _f(s.get("btc_price"), leg.get("start_btc"))
        amp = None
        if leg.get("min_btc") is not None and leg.get("max_btc") is not None:
            amp = leg["max_btc"] - leg["min_btc"]
        start_bid = leg.get("start_bid")
        end_bid = leg.get("last_bid")
        max_roi = None
        end_roi = None
        giveback = None
        if start_bid is not None and start_bid > 0:
            if leg.get("max_bid") is not None:
                max_roi = (leg["max_bid"] - start_bid) / start_bid
            if end_bid is not None:
                end_roi = (end_bid - start_bid) / start_bid
            if max_roi is not None and end_roi is not None:
                giveback = max(0.0, max_roi - end_roi)
        _write(LEG_LOG, LEG_FIELDS, {
            "event": "LEG_COMPLETE", "ticker": leg.get("ticker"), "leg_id": leg.get("leg_id"),
            "arc_id": leg.get("arc_id"), "direction": leg.get("direction"), "side": leg.get("side"),
            "start_ts": _utc(leg.get("start_ts")), "end_ts": _utc(end_ts),
            "duration_sec": max(0.0, end_ts - leg.get("start_ts", end_ts)),
            "start_btc": leg.get("start_btc"), "end_btc": end_btc,
            "btc_move": (end_btc - leg.get("start_btc")) if end_btc is not None else None,
            "btc_amplitude": amp, "start_side_bid": start_bid, "end_side_bid": end_bid,
            "max_side_bid": leg.get("max_bid"), "min_side_bid": leg.get("min_bid"),
            "max_quote_roi": max_roi, "end_quote_roi": end_roi, "quote_giveback_points": giveback,
            "start_target_distance": leg.get("start_target_distance"), "end_target_distance": s.get("target_distance"),
            "start_seconds_left": leg.get("start_seconds_left"), "end_seconds_left": s.get("seconds_left"),
            "start_phase": leg.get("start_phase"), "end_phase": s.get("price_arc_phase"),
            "start_battlefield": leg.get("start_battlefield"), "end_battlefield": s.get("battlefield_class"),
            "start_cage": leg.get("start_cage"), "end_cage": s.get("cage_state"),
            "start_dragon": leg.get("start_dragon"), "end_dragon": s.get("dragon_state"),
            "boss_side": s.get("boss_side"), "hand_side": s.get("hand_side"),
            "harvest_20_seen": leg.get("harvest20"), "harvest_30_seen": leg.get("harvest30"),
            "harvest_40_seen": leg.get("harvest40"),
            "note": "structural leg only; does not imply a trade should be taken",
        })

    # ------------------------------------------------------------------
    # Turning points + Twin Peak / Twin Valley -> EMA30 Gate
    # ------------------------------------------------------------------
    def _record_market_sample(self, s: Dict[str, Any]) -> None:
        ticker = str(s.get("ticker") or "")
        btc = _f(s.get("btc_price"))
        if not ticker or btc is None:
            return
        self.market_history[ticker].append({
            "ts": s["now"], "btc": btc, "ema9": _f(s.get("ema9")), "ema30": _f(s.get("ema30")),
            "range60": _f(s.get("range60")), "target_distance": _f(s.get("target_distance")),
            "seconds_left": _f(s.get("seconds_left")), "yes_ask": _f(s.get("yes_ask")),
            "no_ask": _f(s.get("no_ask")),
        })

    def _detect_turning_points(self, s: Dict[str, Any]) -> None:
        ticker = str(s.get("ticker") or "")
        hist = list(self.market_history[ticker])
        if len(hist) < 7:
            return
        now = s["now"]
        # Confirm a turning point roughly 3 seconds after it happens.
        candidates = [x for x in hist if 2.5 <= now - x["ts"] <= 4.5]
        if not candidates:
            return
        c = candidates[-1]
        window = [x for x in hist if abs(x["ts"] - c["ts"]) <= 3.2]
        if len(window) < 5:
            return
        prices = [x["btc"] for x in window]
        r60 = c.get("range60") or _f(s.get("range60"), 1.0) or 1.0
        prominence = max(3.0, 0.09 * max(1.0, r60))
        left = [x["btc"] for x in window if x["ts"] < c["ts"]]
        right = [x["btc"] for x in window if x["ts"] > c["ts"]]
        if not left or not right:
            return
        kind = None
        if c["btc"] >= max(prices) and c["btc"] - max(min(left), min(right)) >= prominence:
            kind = "PEAK"
        elif c["btc"] <= min(prices) and min(max(left), max(right)) - c["btc"] >= prominence:
            kind = "VALLEY"
        if kind is None:
            return
        key = (ticker, kind)
        if c["ts"] - self.last_turn_ts[key] < 9.0:
            return
        self.last_turn_ts[key] = c["ts"]
        point = {**c, "kind": kind}
        self.turning_points[ticker].append(point)
        self._consider_twin_pattern(ticker, kind)

    def _consider_twin_pattern(self, ticker: str, kind: str) -> None:
        pts = [p for p in self.turning_points[ticker] if p.get("kind") == kind]
        if len(pts) < 2:
            return
        p1, p2 = pts[-2], pts[-1]
        gap = p2["ts"] - p1["ts"]
        if not (18 <= gap <= 240):
            return
        hist = [x for x in self.market_history[ticker] if p1["ts"] <= x["ts"] <= p2["ts"]]
        if len(hist) < 5:
            return
        r60 = p2.get("range60") or p1.get("range60") or 1.0
        tol = max(4.0, 0.18 * max(1.0, r60))
        weakening = 0
        reasons = []
        if kind == "PEAK":
            middle = min(x["btc"] for x in hist)
            if p2["btc"] <= p1["btc"] + tol:
                weakening += 2; reasons.append("second_peak_no_clean_extension")
            sep1 = (p1["btc"] - p1["ema9"]) if p1.get("ema9") is not None else None
            sep2 = (p2["btc"] - p2["ema9"]) if p2.get("ema9") is not None else None
            if sep1 is not None and sep2 is not None and sep2 <= sep1:
                weakening += 1; reasons.append("second_peak_weaker_ema9_separation")
            if p1.get("ema30") is not None and p2.get("ema30") is not None and p1["btc"] > p1["ema30"] and p2["btc"] > p2["ema30"]:
                weakening += 1; reasons.append("both_peaks_above_ema30")
            pattern_type = "TWIN_PEAK_DOWN_GATE"
        else:
            middle = max(x["btc"] for x in hist)
            if p2["btc"] >= p1["btc"] - tol:
                weakening += 2; reasons.append("second_valley_no_clean_extension")
            sep1 = (p1["ema9"] - p1["btc"]) if p1.get("ema9") is not None else None
            sep2 = (p2["ema9"] - p2["btc"]) if p2.get("ema9") is not None else None
            if sep1 is not None and sep2 is not None and sep2 <= sep1:
                weakening += 1; reasons.append("second_valley_weaker_ema9_separation")
            if p1.get("ema30") is not None and p2.get("ema30") is not None and p1["btc"] < p1["ema30"] and p2["btc"] < p2["ema30"]:
                weakening += 1; reasons.append("both_valleys_below_ema30")
            pattern_type = "TWIN_VALLEY_UP_GATE"
        if weakening < 3:
            return
        self.twin_counter += 1
        pid = f"TP{self.twin_counter:05d}"
        watch = {
            "pattern_id": pid, "ticker": ticker, "pattern_type": pattern_type,
            "p1": p1, "p2": p2, "middle": middle, "score": weakening,
            "reasons": ";".join(reasons), "ts": p2["ts"], "done": False,
        }
        self.twin_watches[pid] = watch
        print(f"🏔️🏔️ TWIN GEOMETRY SHADOW | {pattern_type} | score={weakening} | {ticker}")
        self._write_twin("CANDIDATE", watch, p2, None)

    def _update_twin_watches(self, s: Dict[str, Any]) -> None:
        ticker = str(s.get("ticker") or "")
        btc = _f(s.get("btc_price"))
        ema30 = _f(s.get("ema30"))
        if btc is None or ema30 is None:
            return
        for pid, w in list(self.twin_watches.items()):
            if w.get("done") or w.get("ticker") != ticker:
                continue
            age = s["now"] - w["ts"]
            if age > 180:
                w["done"] = True
                self._write_twin("EXPIRED_NO_GATE_BREAK", w, s, None)
                continue
            r60 = _f(s.get("range60"), 1.0) or 1.0
            buffer = max(2.0, 0.05 * r60)
            broke = False
            gate = ema30
            if w["pattern_type"] == "TWIN_PEAK_DOWN_GATE" and btc < ema30 - buffer:
                broke = True
            if w["pattern_type"] == "TWIN_VALLEY_UP_GATE" and btc > ema30 + buffer:
                broke = True
            if broke:
                w["done"] = True
                print(f"🚪💥 30 GATE BREAK SHADOW | {w['pattern_type']} | {age:.1f}s after point 2")
                self._write_twin("EMA30_GATE_BREAK", w, s, gate)

    def _write_twin(self, event: str, w: Dict[str, Any], s: Dict[str, Any], gate_price: Optional[float]) -> None:
        p1, p2 = w["p1"], w["p2"]
        _write(TWIN_GATE_LOG, TWIN_FIELDS, {
            "event": event, "pattern_id": w.get("pattern_id"), "ticker": w.get("ticker"),
            "pattern_type": w.get("pattern_type"), "point1_ts": _utc(p1["ts"]), "point2_ts": _utc(p2["ts"]),
            "point1_btc": p1.get("btc"), "point2_btc": p2.get("btc"),
            "valley_or_peak_btc": w.get("middle"), "point_gap_sec": p2["ts"] - p1["ts"],
            "point2_vs_point1": p2["btc"] - p1["btc"], "range60": p2.get("range60"),
            "ema30_at_point1": p1.get("ema30"), "ema30_at_point2": p2.get("ema30"),
            "point1_sep_ema9": (p1["btc"] - p1["ema9"]) if p1.get("ema9") is not None else None,
            "point2_sep_ema9": (p2["btc"] - p2["ema9"]) if p2.get("ema9") is not None else None,
            "weakening_score": w.get("score"), "reasons": w.get("reasons"),
            "seconds_left": s.get("seconds_left"), "target_distance": s.get("target_distance"),
            "watch_age_sec": (_f(s.get("now"), time.time()) or time.time()) - w["ts"],
            "gate_price": gate_price, "break_btc": s.get("btc_price") if event == "EMA30_GATE_BREAK" else None,
            "break_distance": (s.get("btc_price") - gate_price) if event == "EMA30_GATE_BREAK" and gate_price is not None else None,
            "note": "pattern observer only; 3-second confirmation and 9-second turn spacing",
        })

    # ------------------------------------------------------------------
    # Settlement Elasticity Lite
    # ------------------------------------------------------------------
    def _elasticity_lite(self, s: Dict[str, Any]) -> None:
        ticker = str(s.get("ticker") or "")
        now = s["now"]
        btc = _f(s.get("btc_price"))
        yes_ask = _f(s.get("yes_ask"))
        no_ask = _f(s.get("no_ask"))
        if not ticker or btc is None:
            return
        yes_bid = _side_bid("YES", yes_ask, no_ask)
        no_bid = _side_bid("NO", yes_ask, no_ask)
        sample = {
            "ts": now, "btc": btc, "yes_ask": yes_ask, "no_ask": no_ask,
            "yes_bid": yes_bid, "no_bid": no_bid, "target": _f(s.get("target")),
            "target_distance": _f(s.get("target_distance")), "range60": _f(s.get("range60")),
            "seconds_left": _f(s.get("seconds_left")),
        }
        hist = self.elasticity_history[ticker]
        hist.append(sample)
        if now - self.last_elasticity_log[ticker] < 2.8:
            return
        self.last_elasticity_log[ticker] = now
        for window in (3, 6, 9):
            prior = None
            best_err = 999.0
            for row in reversed(hist):
                age = now - row["ts"]
                if age < window - 1.25:
                    continue
                if age > window + 1.75:
                    break
                err = abs(age - window)
                if err < best_err:
                    prior = row; best_err = err
            if prior is None:
                continue
            dbtc = btc - prior["btc"]
            valid = int(abs(dbtc) >= 1.0)
            ychg = (yes_bid - prior["yes_bid"]) if yes_bid is not None and prior.get("yes_bid") is not None else None
            nchg = (no_bid - prior["no_bid"]) if no_bid is not None and prior.get("no_bid") is not None else None
            ybeta = (ychg / dbtc) if valid and ychg is not None else None
            nbeta_raw = (nchg / dbtc) if valid and nchg is not None else None
            nbeta = (-nbeta_raw) if nbeta_raw is not None else None
            td = sample.get("target_distance")
            r60 = sample.get("range60")
            norm = (td / max(1.0, abs(r60))) if td is not None and r60 not in (None, 0) else None
            _write(ELASTICITY_LITE_LOG, ELASTICITY_FIELDS, {
                "ticker": ticker, "window_sec": window, "sample_age_sec": now - prior["ts"],
                "seconds_left": sample.get("seconds_left"), "time_bucket": _time_bucket(sample.get("seconds_left")),
                "btc_price": btc, "target": sample.get("target"), "target_distance": td,
                "abs_target_distance": abs(td) if td is not None else None, "range60": r60,
                "target_distance_norm60": norm, "distance_bucket": _distance_bucket(td, r60),
                "yes_ask": yes_ask, "no_ask": no_ask, "yes_bid": yes_bid, "no_bid": no_bid,
                "quote_bucket_yes": _quote_bucket(yes_bid), "quote_bucket_no": _quote_bucket(no_bid),
                "btc_change": dbtc, "yes_bid_change": ychg, "no_bid_change": nchg,
                "yes_directional_beta": ybeta, "no_directional_beta": nbeta,
                "yes_cents_per_10btc": (ybeta * 1000.0) if ybeta is not None else None,
                "no_cents_per_10btc": (nbeta * 1000.0) if nbeta is not None else None,
                "arc_direction": s.get("arc_direction"), "price_arc_phase": s.get("price_arc_phase"),
                "battlefield_class": s.get("battlefield_class"), "cage_state": s.get("cage_state"),
                "dragon_state": s.get("dragon_state"), "valid_move": valid,
                "note": "3-second sampled lite observer; far smaller than V9.4L full elasticity log",
            })

    # ------------------------------------------------------------------
    # Real exit hook
    # ------------------------------------------------------------------
    def on_real_exit(self, position: Dict[str, Any], bid: float, actual_roi: float, reason: str, pnl: float) -> None:
        if not isinstance(position, dict):
            return
        ticker = str(position.get("ticker") or "")
        side = str(position.get("side") or "")
        tid = _position_trade_id(position, f"{ticker}:{side}")
        snap = dict(getattr(j.brain, "last_snapshot", {}) or {})
        snap["ticker"] = ticker
        snap["now"] = time.time()
        snap["cage_state"] = getattr(k.brain, "last_cage_state", None)
        snap["dragon_state"] = getattr(k.brain, "last_dragon_state", None)
        snap["target_migration_state"] = getattr(k.brain, "last_migration_state", None)

        self.last_exit_by_ticker[ticker] = {
            "ts": time.time(), "trade_id": tid, "side": side, "bid": bid,
            "roi": actual_roi, "pnl": pnl, "reason": reason, "snapshot": dict(snap),
        }

        entry_ctx = self.entry_context_by_trade.get(tid, {})
        score, label, reasons = self._chapter_compare(snap, entry_ctx)
        _write(CAMPAIGN_LOG, CAMPAIGN_FIELDS, {
            "event": "REAL_EXIT", "trade_id": tid, "ticker": ticker, "side": side,
            "contract_trade_number": self.contract_trade_count.get(ticker, 0),
            "entry_ask": _position_entry(position), "exit_bid": bid, "actual_roi": actual_roi,
            "actual_pnl": pnl, "exit_reason": reason, "chapter_score": score,
            "chapter_label": label, "chapter_reasons": reasons,
            "arc_id": snap.get("arc_id"), "arc_direction": snap.get("arc_direction"),
            "price_arc_phase": snap.get("price_arc_phase"), "boss_id": snap.get("boss_id"),
            "boss_side": snap.get("boss_side"), "hand_side": snap.get("hand_side"),
            "battlefield_class": snap.get("battlefield_class"), "cage_state": snap.get("cage_state"),
            "dragon_state": snap.get("dragon_state"), "target_migration_state": snap.get("target_migration_state"),
            "target_distance": snap.get("target_distance"), "seconds_left": snap.get("seconds_left"),
            "signal_grade": position.get("signal_grade"), "setup_grade": position.get("setup_grade"),
            "strategy": position.get("strategy"),
            "note": "real frozen-authority exit; chapter comparison is descriptive only",
        })

        # Close treasury candidate and compare counterfactual exit price.
        st = self.trade_state.get(tid)
        if st:
            cid = st.get("defense_id")
            cand = self.treasury_candidates.get(cid) if cid else None
            if cand and not cand.get("closed"):
                cand["closed"] = True
                delta = None
                qty = _i(position.get("qty"), st.get("qty", 0))
                if cand.get("bid") is not None and bid is not None:
                    delta = (cand["bid"] - bid) * qty
                integrity, cp, why = self._thesis_integrity(side, snap)
                hold = "HIGH_HOLDABILITY" if integrity >= 7 else ("MIXED_HOLDABILITY" if integrity >= 5 else "LOW_HOLDABILITY")
                self._write_treasury_row("ACTUAL_EXIT_MARK", st, position, snap, bid, actual_roi,
                                         st.get("mfe", actual_roi), max(0.0, st.get("mfe", 0) - actual_roi),
                                         (actual_roi / st.get("mfe")) if st.get("mfe", 0) > 1e-9 else None,
                                         integrity, cp, why, hold, "REAL_EXIT", "COMPARE_COUNTERFACTUAL",
                                         candidate=cand, actual_exit={"bid": bid, "roi": actual_roi, "pnl": pnl, "delta": delta})

        # Mark active V2 spears attached to this parent at parent exit.
        for sid, cand in self.spears.items():
            if cand.get("closed") or cand.get("parent_trade_id") != tid:
                continue
            cand["closed"] = True
            mark = _side_bid(cand["side"], snap.get("yes_ask"), snap.get("no_ask"))
            if mark is None:
                mark = bid if cand["side"] == side else None
            roi = ((mark - cand["ask"]) / cand["ask"]) if mark is not None and cand.get("ask") else None
            baseline = self.entry_context_by_trade.get(tid)
            ch_score, ch_label, ch_reasons = self._chapter_compare(snap, baseline)
            integ, cp, _ = self._thesis_integrity(cand["side"], snap)
            premium = cand["ask"] - _position_entry(position) if _position_entry(position) is not None else None
            quality = "UNKNOWN" if premium is None else ("BETTER_PRICE" if premium <= -0.01 else ("SAME_ZONE" if premium <= 0.02 else "WORSE_PRICE_CHASE"))
            self._write_spear("PARENT_EXIT_MARK", cand, snap, None, None, actual_roi,
                              premium, quality, ch_score, ch_label, ch_reasons, integ, cp, "",
                              mark_bid=mark, shadow_roi=roi, exit_reason=reason)

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------
    def _write_manifest(self) -> None:
        _write(MANIFEST_LOG, MANIFEST_FIELDS, {
            "version": VERSION,
            "base_version": "V9.4K -> V9.4J -> V9.4I frozen paper authority",
            "paper_authority": "FROZEN_BASE_ONLY",
            "start_local": _local(_START_TS), "pid": os.getpid(),
            "research_layers": "TREASURY_DEFENSE;BOMBE_INTEGRITY;CAMPAIGN_LEDGER;MEDIC_QUALIFIER;SECOND_SPEAR_V2;LEG_HARVEST;TWIN_30_GATE;ELASTICITY_LITE",
            "doctrine": "Defend proven treasury only when structure deteriorates; new entries require new chapters; wounded is not dead.",
            "l_imported": "NO",
            "note": "M intentionally imports K directly: L Second Spear v1 was weak and L full elasticity was too large.",
        })


brain = V94MShadowBrain()
_HOOKS_INSTALLED = False


def install_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return

    # Install J + K exactly as a normal V9.4K launch would. Frozen V9.4I remains authority.
    k.install_hooks()
    _HOOKS_INSTALLED = True

    # Tick: inherited stack first, M observes afterward.
    original_council = getattr(core, "v94e_kings_council_observer")

    def council_wrapper(ticker, yes_ask, no_ask, close_ts, now=None):
        result = original_council(ticker, yes_ask, no_ask, close_ts, now)
        try:
            brain.on_tick(ticker, yes_ask, no_ask, close_ts, now)
        except Exception as exc:
            print(f"⚠️ V9.4M tick shadow error: {exc}")
        return result

    core.v94e_kings_council_observer = council_wrapper

    # Entry: frozen authority decides first; M only records result / blocked same-side attempt.
    original_enter = getattr(core, "paper_enter")

    def paper_enter_wrapper(ticker, side, ask, signal):
        ctx = None
        try:
            ctx = brain.before_entry_attempt(ticker, side, ask, signal or {})
        except Exception as exc:
            print(f"⚠️ V9.4M pre-entry shadow error: {exc}")
        entered = original_enter(ticker, side, ask, signal)
        try:
            if ctx is not None:
                # preserve signal metadata on V2 candidates
                if ctx.get("active_before"):
                    pass
                brain.after_entry_attempt(ctx, bool(entered))
        except Exception as exc:
            print(f"⚠️ V9.4M entry shadow error: {exc}")
        return entered

    core.paper_enter = paper_enter_wrapper

    # Finalize: inherited stack first; M records comparison afterward.
    original_finalize = getattr(core, "v94b_finalize_trade_shadows")

    def finalize_wrapper(position, bid, actual_roi, reason, pnl):
        result = original_finalize(position, bid, actual_roi, reason, pnl)
        try:
            brain.on_real_exit(position, bid, actual_roi, reason, pnl)
        except Exception as exc:
            print(f"⚠️ V9.4M exit shadow error: {exc}")
        return result

    core.v94b_finalize_trade_shadows = finalize_wrapper


async def main() -> None:
    install_hooks()
    print("=" * 104)
    print(f"TACHYOS {VERSION} — BATTLE PLAN / TREASURY / CHAPTER LAB")
    print(f"RUN ID: {RUN_ID} | SESSION: {SESSION_ID}")
    print("PAPER ONLY | V9.4I paper authority remains FROZEN.")
    print("V9.4J + V9.4K + V9.4M are observer/shadow intelligence only.")
    print("")
    print("🏦 TREASURY DEFENSE: proven-profit giveback vs healthy breathing")
    print("🧩 BOMBE: structural contradictions / thesis integrity")
    print("⚔️ CAMPAIGN LEDGER: same failed chapter vs genuine new chapter")
    print("🩺 MEDIC QUALIFIER: terminal candidate calibration; wounded != dead")
    print("🗡️ SECOND SPEAR V2: stricter chapter + price-quality; no worse-price chasing")
    print("🏔️ ARC LEGS: harvest/carry telemetry + Twin Peak / Twin Valley -> EMA30 gate")
    print("🔥 ELASTICITY LITE: 3/6/9-sec quote response sampled ~every 3 seconds")
    print("")
    print("V9.4L is NOT imported: this avoids recreating its huge elasticity file and weak Spear-v1 layer.")
    print("No V9.4M function may place, block, resize, flip, or close a paper trade.")
    print("=" * 104)
    await core.main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTachyos V9.4M stopped by operator (Ctrl+C).")
