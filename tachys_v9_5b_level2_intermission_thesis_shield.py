"""
TACHYOS V9.5B — LEVEL-2 BATTLE COUNCIL / INTERMISSION AUTHORITY / THESIS SHIELD
================================================================================

PAPER ONLY.

V9.5B imports the complete V9.5A-RS2 stack unchanged, then adds three tightly
scoped paper experiments derived from the RS2 forensic review:

1) LEVEL-2 BATTLE COUNCIL
   Existing observers may PRESENT evidence, but no single observer can enter a
   trade. A tactical side opposite the strategic parent must earn a composite
   decision across independent evidence families.

2) 3 / 6 / 9 INTERMISSION CLOCK
   A decisive four-family composite may execute after 3 seconds; a standard
   three-family composite after 6 seconds. By 9 seconds an armed idea must act
   or stand down. Price that reprices >9c AND >25% from the arm quote is not
   chased.

3) THESIS SHIELD V1
   During the first 120 seconds, ordinary fast-fail / structural invalidation
   paths are delayed while the thesis remains structurally intact. Emergency,
   expiry and proven-profit protection remain available. Catastrophic structural
   agreement can release the shield early.

Strategic doctrine:
    Parent != current play.
    Boss remains strategic parent.
    Tactical opposite legs can be authorized as INTERMISSIONS without forcing
    a sovereignty transfer.

All upstream V9.5A, RS1 and RS2 telemetry remains installed for control.
"""

from __future__ import annotations

import asyncio
import csv
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import tachys_v9_5a_battlefield_memory_reacquisition_shadow as rs2

r = rs2.r
a = r.a
m = a.m
k = m.k
j = m.j
core = m.core

VERSION = "V9.5B"
ET = m.ET
_START_TS = time.time()
RUN_ID = datetime.now(ET).strftime("B%Y%m%d_%H%M%S")
SESSION_ID = f"{RUN_ID}_PID{os.getpid()}"

os.environ["TACHYOS_V95B_RUN_ID"] = RUN_ID
os.environ["TACHYOS_V95B_SESSION_ID"] = SESSION_ID

# ---------------------------------------------------------------------------
# Evidence-backed experiment parameters
# ---------------------------------------------------------------------------

L2_ARM_SCORE = 4
L2_ARM_FAMILIES = 2
L2_STANDARD_SCORE = 6
L2_STANDARD_FAMILIES = 3
L2_DECISIVE_SCORE = 8
L2_DECISIVE_FAMILIES = 4

L2_DECISIVE_WAIT_SEC = 3.0
L2_STANDARD_WAIT_SEC = 6.0
L2_DECISION_DEADLINE_SEC = 9.0
L2_ARM_TTL_SEC = 36.0

L2_MIN_ASK = 0.20
L2_MAX_ASK = 0.80
L2_MAX_ARM_REPRICE_ABS = 0.09
L2_MAX_ARM_REPRICE_PCT = 0.25
L2_MAX_INTERMISSION_PER_SIDE_PER_CONTRACT = 2
L2_REENTRY_COOLDOWN_SEC = 36.0

FORMATION_MEMORY_TTL_SEC = 180.0
STRUCTURAL_MEMORY_TTL_SEC = 90.0
THESIS_PROTECTION_SEC = 120.0

LEVEL2_LOG = "tachys_level2_battle_council_v9_5b.csv"
SHIELD_LOG = "tachys_thesis_shield_v9_5b.csv"
LATENCY_LOG = "tachys_latency_accounting_v9_5b.csv"
ROLLOVER_LOG = "tachys_rollover_memory_v9_5b.csv"
MANIFEST_LOG = "tachys_run_manifest_v9_5b.csv"

LEVEL2_FIELDS = [
    "timestamp", "run_id", "session_id", "event", "arm_id", "ticker",
    "parent_side", "candidate_side", "state", "ask", "arm_ask",
    "arm_age_sec", "score", "family_count", "families", "primary_trigger",
    "reasons", "contradictions", "decision_path", "decision_result",
    "seconds_left", "target_distance", "target_event", "target_side",
    "structural_bias", "own_structural_score", "opposite_structural_score",
    "formation", "formation_maturity", "local_regime", "formation_failure",
    "formation_memory_side", "formation_memory_age_sec", "arc_id",
    "arc_direction", "price_arc_phase", "ema_gap", "ema30_slope6",
    "ema30_delta30", "recognition_source", "recognition_age_sec",
    "recognition_first_ask", "parent_leg_stale", "parent_leg_age_sec",
    "parent_leg_premium_abs", "parent_leg_premium_pct", "price_reprice_abs",
    "price_reprice_pct", "active_position_side", "entry_count_side",
    "note",
]

SHIELD_FIELDS = [
    "timestamp", "run_id", "session_id", "event", "trade_id", "ticker",
    "side", "entry_age_sec", "entry_ask", "current_bid", "roi",
    "shield_state", "catastrophic_points", "catastrophic_reasons",
    "hold_authority", "own_structural_score", "opposite_structural_score",
    "structural_bias", "target_event", "ema30_event", "target_distance",
    "legacy_fast_fail_disabled", "legacy_structural_min_age_sec",
    "legacy_ema9_invalidation_suppressed", "note",
]

LATENCY_FIELDS = [
    "timestamp", "run_id", "session_id", "event", "trade_id", "ticker",
    "side", "strategy", "observer_source", "observer_ts", "observer_ask",
    "observer_to_entry_sec", "observer_edge_lost_cents", "arm_id", "arm_ts",
    "arm_ask", "arm_to_entry_sec", "arm_edge_lost_cents", "entry_ask",
    "decision_path", "note",
]

ROLLOVER_FIELDS = [
    "timestamp", "run_id", "session_id", "event", "from_ticker", "to_ticker",
    "side", "memory_kind", "memory_age_sec", "source_ticker", "formation",
    "formation_maturity", "local_regime", "parent_side", "target_event",
    "structural_bias", "note",
]

MANIFEST_FIELDS = [
    "timestamp", "run_id", "session_id", "version", "base_version",
    "paper_authority", "start_local", "pid", "adjudication_clock",
    "intermission_rule", "thesis_shield_sec", "price_no_chase",
    "max_intermission_per_side", "unchanged_authority", "note",
]


def _utc(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else float(ts)
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _local(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else float(ts)
    return datetime.fromtimestamp(ts, ET).isoformat()


def _f(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        value = float(value)
        return value if math.isfinite(value) else default
    except Exception:
        return default


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _write(path: str, fields, row: Dict[str, Any]) -> None:
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


def _opposite(side: str) -> str:
    return "NO" if side == "YES" else "YES" if side == "NO" else "NONE"


def _side_from_direction(direction: Any) -> str:
    direction = str(direction or "").upper()
    if direction == "UP":
        return "YES"
    if direction == "DOWN":
        return "NO"
    return "NONE"


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


class V95BBattleCouncil:
    def __init__(self) -> None:
        self.arm_counter = 0
        self.arms: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.formation_memory: Dict[str, Dict[str, Any]] = {}
        self.structural_memory: Dict[str, Dict[str, Any]] = {}
        self.observer_seen: Dict[Tuple[str, str], str] = {}
        self.entry_count: Dict[Tuple[str, str], int] = {}
        self.last_intermission_entry_ts: Dict[Tuple[str, str], float] = {}
        self.last_ticker: Optional[str] = None
        self.last_parent_by_ticker: Dict[str, str] = {}
        self.last_level2_emit: Dict[Tuple[str, str], Tuple[Any, ...]] = {}
        self.last_level2_emit_ts: Dict[Tuple[str, str], float] = {}
        self.last_shield_emit: Dict[str, Tuple[Any, ...]] = {}
        self.last_shield_emit_ts: Dict[str, float] = {}
        self.pending_entry_context: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._write_manifest()

    def _write_manifest(self) -> None:
        _write(MANIFEST_LOG, MANIFEST_FIELDS, {
            "version": VERSION,
            "base_version": "V9.5A-RS2 -> V9.5A-RS1 -> V9.5A -> V9.4M",
            "paper_authority": "LEVEL2_INTERMISSION_AND_THESIS_SHIELD_V1",
            "start_local": _local(_START_TS),
            "pid": os.getpid(),
            "adjudication_clock": "3S_DECISIVE;6S_STANDARD;9S_DECISION_DEADLINE",
            "intermission_rule": "TACTICAL_SIDE_MUST_OPPOSE_STRATEGIC_PARENT",
            "thesis_shield_sec": THESIS_PROTECTION_SEC,
            "price_no_chase": ">=9c_AND_>=25pct_FROM_ARM_ASK",
            "max_intermission_per_side": L2_MAX_INTERMISSION_PER_SIDE_PER_CONTRACT,
            "unchanged_authority": (
                "V95A_PRICE_FRESHNESS;V95A_TREASURY;LEGACY_EMERGENCY;CONTRACT_CLOSE;"
                "CORE;EARLY_IMPULSE;HANDOFF;SIZING"
            ),
            "note": (
                "Forensic promotion: Structural, Formation, Price Freshness, Flash and Arc/EMA "
                "may present to Level 2. No single observer has unilateral entry authority."
            ),
        })

    def _snapshot(self, ticker: str, yes_ask=None, no_ask=None) -> Dict[str, Any]:
        try:
            return dict(m.brain.snapshot(ticker, yes_ask=yes_ask, no_ask=no_ask) or {})
        except Exception:
            return dict(getattr(j.brain, "last_snapshot", {}) or {})

    def _parent_side(self, snap: Dict[str, Any]) -> str:
        boss = str(snap.get("boss_side") or "").upper()
        if boss in ("YES", "NO"):
            return boss
        hand = str(snap.get("hand_side") or "").upper()
        if hand in ("YES", "NO"):
            return hand
        try:
            hand2 = str((getattr(core, "v94e_latest_regime", {}) or {}).get("authority_side") or "").upper()
            if hand2 in ("YES", "NO"):
                return hand2
        except Exception:
            pass
        return "NONE"

    def _formation_context(self, now: float) -> Dict[str, Any]:
        try:
            return dict(core._v94d_current_formation_context(now) or {})
        except Exception:
            return {}

    def _structural_context(self) -> Dict[str, Any]:
        return dict(getattr(core, "v94b_latest_structural_snap", {}) or {})

    def _formation_direction_side(self, geometry: Any) -> str:
        name = str(geometry or "").upper()
        if "FALLING" in name or "DESCENDING" in name:
            return "NO"
        if "RISING" in name or "ASCENDING" in name:
            return "YES"
        return "NONE"

    def _formation_failure_release_side(self, form: Dict[str, Any], parent: str) -> str:
        if parent in ("YES", "NO"):
            return _opposite(parent)
        direction = self._formation_direction_side(form.get("formation"))
        return _opposite(direction) if direction in ("YES", "NO") else "NONE"

    def _live_memory(self, store: Dict[str, Dict[str, Any]], side: str, ttl: float, now: float) -> Optional[Dict[str, Any]]:
        mem = store.get(side)
        if not isinstance(mem, dict):
            return None
        if now - float(mem.get("ts") or now) > ttl:
            store.pop(side, None)
            return None
        return mem

    def _refresh_memories(
        self,
        ticker: str,
        parent: str,
        form: Dict[str, Any],
        struct: Dict[str, Any],
        now: float,
    ) -> None:
        maturity = str(form.get("maturity") or "").upper()
        local = str(form.get("regime") or "").upper()
        failure = str(form.get("failure") or "NONE").upper()
        if maturity == "FAILED" or local == "REVERSAL" or failure not in ("", "NONE", "WARMING"):
            release_side = self._formation_failure_release_side(form, parent)
            if release_side in ("YES", "NO"):
                self.formation_memory[release_side] = {
                    "ts": now,
                    "ticker": ticker,
                    "side": release_side,
                    "formation": form.get("formation"),
                    "maturity": form.get("maturity"),
                    "regime": form.get("regime"),
                    "failure": form.get("failure"),
                    "parent_side": parent,
                }

        target_event = str(struct.get("target_event") or "").upper()
        target_side = str(struct.get("target_side") or "").upper()
        if target_event == "TARGET_FALSE_BREAK_RECLAIM" and target_side in ("YES", "NO"):
            self.structural_memory[target_side] = {
                "ts": now,
                "ticker": ticker,
                "side": target_side,
                "target_event": target_event,
                "structural_bias": struct.get("structural_bias"),
            }

    def _reconcile_sovereignty(self, ticker: str, parent: str, now: float) -> None:
        """Resolve tactical memories when their side becomes the strategic parent."""
        if parent not in ("YES", "NO"):
            return
        prior = self.last_parent_by_ticker.get(ticker)
        self.last_parent_by_ticker[ticker] = parent
        if prior not in ("YES", "NO") or prior == parent:
            return

        for store, kind in (
            (self.formation_memory, "FORMATION_FAILURE_REVERSAL"),
            (self.structural_memory, "TARGET_FALSE_BREAK_RECLAIM"),
        ):
            mem = store.get(parent)
            if not isinstance(mem, dict):
                continue
            _write(ROLLOVER_LOG, ROLLOVER_FIELDS, {
                "event": "MEMORY_RESOLVED_BY_SOVEREIGNTY",
                "from_ticker": ticker,
                "to_ticker": ticker,
                "side": parent,
                "memory_kind": kind,
                "memory_age_sec": round(max(0.0, now - float(mem.get("ts") or now)), 3),
                "source_ticker": mem.get("ticker"),
                "formation": mem.get("formation"),
                "formation_maturity": mem.get("maturity"),
                "local_regime": mem.get("regime"),
                "parent_side": parent,
                "target_event": mem.get("target_event"),
                "structural_bias": mem.get("structural_bias"),
                "note": f"Strategic parent changed {prior}->{parent}; tactical memory on the new sovereign side is resolved.",
            })
            store.pop(parent, None)

    def _handle_rollover(self, ticker: str, parent: str, now: float) -> None:
        old = self.last_ticker
        if old is None:
            self.last_ticker = ticker
            return
        if old == ticker:
            return

        for side in ("YES", "NO"):
            fmem = self._live_memory(self.formation_memory, side, FORMATION_MEMORY_TTL_SEC, now)
            if fmem:
                _write(ROLLOVER_LOG, ROLLOVER_FIELDS, {
                    "event": "FORMATION_MEMORY_CARRIED",
                    "from_ticker": old,
                    "to_ticker": ticker,
                    "side": side,
                    "memory_kind": "FORMATION_FAILURE_REVERSAL",
                    "memory_age_sec": round(now - float(fmem.get("ts") or now), 3),
                    "source_ticker": fmem.get("ticker"),
                    "formation": fmem.get("formation"),
                    "formation_maturity": fmem.get("maturity"),
                    "local_regime": fmem.get("regime"),
                    "parent_side": parent,
                    "note": "Formation warning survived contract rollover; fresh label does not erase inherited microstructure.",
                })
            smem = self._live_memory(self.structural_memory, side, STRUCTURAL_MEMORY_TTL_SEC, now)
            if smem:
                _write(ROLLOVER_LOG, ROLLOVER_FIELDS, {
                    "event": "STRUCTURAL_MEMORY_CARRIED",
                    "from_ticker": old,
                    "to_ticker": ticker,
                    "side": side,
                    "memory_kind": "TARGET_FALSE_BREAK_RECLAIM",
                    "memory_age_sec": round(now - float(smem.get("ts") or now), 3),
                    "source_ticker": smem.get("ticker"),
                    "parent_side": parent,
                    "target_event": smem.get("target_event"),
                    "structural_bias": smem.get("structural_bias"),
                    "note": "Target-interaction memory survived contract rollover.",
                })

        # Contract-local arms and counts do not cross the fencepost; memories do.
        self.arms = {key: val for key, val in self.arms.items() if key[0] == ticker}
        self.last_ticker = ticker

    def note_observer_recognition(self, ticker: str, side: str, ask: float, source: str, now: float) -> None:
        if side not in ("YES", "NO"):
            return
        rec = (getattr(r.brain, "recognition", {}) or {}).get((ticker, side))
        if not isinstance(rec, dict):
            return
        epoch = str(rec.get("epoch_id") or "")
        key = (ticker, side)
        if epoch and self.observer_seen.get(key) == epoch:
            return
        self.observer_seen[key] = epoch
        _write(LEVEL2_LOG, LEVEL2_FIELDS, {
            "event": "OBSERVER_FIRST_PRESENT",
            "ticker": ticker,
            "candidate_side": side,
            "ask": _f(rec.get("ask"), ask),
            "state": "PRESENTED",
            "recognition_source": rec.get("source") or source,
            "recognition_age_sec": max(0.0, now - float(rec.get("ts") or now)),
            "recognition_first_ask": rec.get("ask"),
            "note": "Raw observer recognition presented to Level 2; no unilateral authority.",
        })

    def _recognition(self, ticker: str, side: str, now: float) -> Dict[str, Any]:
        rec = (getattr(r.brain, "recognition", {}) or {}).get((ticker, side))
        if not isinstance(rec, dict):
            return {}
        return {
            **rec,
            "age": max(0.0, now - float(rec.get("ts") or now)),
        }

    def _parent_leg_staleness(self, ticker: str, parent: str, yes_ask, no_ask, now: float) -> Dict[str, Any]:
        leg = (getattr(m.brain, "active_leg", {}) or {}).get(ticker)
        out = {
            "stale": False,
            "age": None,
            "premium_abs": None,
            "premium_pct": None,
        }
        if not isinstance(leg, dict) or parent not in ("YES", "NO"):
            return out
        if str(leg.get("side") or "") != parent:
            return out
        start_bid = _f(leg.get("start_bid"))
        start_ts = _f(leg.get("start_ts"))
        current_ask = _ask_for(parent, yes_ask, no_ask)
        if start_bid is None or start_bid <= 0 or start_ts is None or current_ask is None:
            return out
        age = max(0.0, now - start_ts)
        premium_abs = current_ask - start_bid
        premium_pct = premium_abs / start_bid
        stale = (
            age >= a.PRICE_FRESHNESS_MIN_LEG_AGE_SEC
            and premium_abs >= a.PRICE_FRESHNESS_MIN_PREMIUM_ABS
            and premium_pct >= a.PRICE_FRESHNESS_MAX_PREMIUM_PCT
        )
        out.update({"stale": stale, "age": age, "premium_abs": premium_abs, "premium_pct": premium_pct})
        return out

    def _active_position_side(self, ticker: str) -> str:
        for side, pos in (getattr(core, "paper_positions", {}) or {}).items():
            if isinstance(pos, dict) and str(pos.get("ticker") or "") == str(ticker):
                return str(pos.get("side") or side)
        return "NONE"

    def _evidence(
        self,
        ticker: str,
        candidate: str,
        parent: str,
        yes_ask,
        no_ask,
        snap: Dict[str, Any],
        form: Dict[str, Any],
        struct: Dict[str, Any],
        now: float,
    ) -> Dict[str, Any]:
        score = 0
        families: Dict[str, int] = {}
        reasons = []
        contradictions = []
        primary = False
        opposite = _opposite(candidate)

        # STRUCTURE ----------------------------------------------------------
        own_key = "yes_structural_score" if candidate == "YES" else "no_structural_score"
        opp_key = "no_structural_score" if candidate == "YES" else "yes_structural_score"
        own_score = _i(struct.get(own_key), 0)
        opp_score = _i(struct.get(opp_key), 0)
        structural_bias = str(struct.get("structural_bias") or "NEUTRAL").upper()
        target_event = str(struct.get("target_event") or "NONE").upper()
        target_side = str(struct.get("target_side") or "NONE").upper()
        s_points = 0
        if structural_bias == candidate:
            s_points += 2; reasons.append("STRUCTURAL_BIAS")
        elif structural_bias == opposite:
            contradictions.append("STRUCTURAL_BIAS_OPPOSES")
        if target_event == "TARGET_FALSE_BREAK_RECLAIM" and target_side == candidate:
            s_points += 2; primary = True; reasons.append("TARGET_FALSE_BREAK_RECLAIM")
        elif target_event == f"TARGET_ACCEPTED_{candidate}":
            s_points += 1; reasons.append("TARGET_ACCEPTED")
        if own_score >= opp_score + 1:
            s_points += 1; reasons.append("STRUCTURAL_SCORE_EDGE")
        if s_points:
            families["STRUCTURE"] = s_points
            score += s_points

        smem = self._live_memory(self.structural_memory, candidate, STRUCTURAL_MEMORY_TTL_SEC, now)
        if smem and target_event != "TARGET_FALSE_BREAK_RECLAIM":
            families["STRUCTURE"] = families.get("STRUCTURE", 0) + 1
            score += 1
            primary = True
            reasons.append("TARGET_FALSE_BREAK_MEMORY")

        # FORMATION ----------------------------------------------------------
        f_points = 0
        fmem = self._live_memory(self.formation_memory, candidate, FORMATION_MEMORY_TTL_SEC, now)
        if fmem:
            f_points += 2; primary = True; reasons.append("FORMATION_FAILURE_MEMORY")
        formation_side = self._formation_direction_side(form.get("formation"))
        local = str(form.get("regime") or "").upper()
        maturity = str(form.get("maturity") or "").upper()
        if formation_side == candidate and local in ("TREND", "RELEASE", "PULLBACK", "REVERSAL"):
            f_points += 1; reasons.append("FORMATION_POINTS_SIDE")
        if maturity == "FAILED" and candidate == _opposite(parent):
            f_points += 1; primary = True; reasons.append("FORMATION_FAILED_PARENT")
        if f_points:
            families["FORMATION"] = f_points
            score += f_points

        # ARC / EMA ----------------------------------------------------------
        ae_points = 0
        arc_side = _side_from_direction(snap.get("arc_direction"))
        if arc_side == candidate:
            ae_points += 1; reasons.append("ARC_DIRECTION")
        btc = _f(getattr(core, "btc_last_price", None))
        ema9 = _f(getattr(core, "btc_ema_9", None))
        if btc is not None and ema9 is not None:
            price_side = "YES" if btc > ema9 else "NO" if btc < ema9 else "NONE"
            if price_side == candidate:
                ae_points += 1; reasons.append("PRICE_VS_EMA9")
        slope30 = _f(struct.get("ema30_delta30"))
        if slope30 is not None:
            slope_side = "YES" if slope30 > 0 else "NO" if slope30 < 0 else "NONE"
            if slope_side == candidate:
                ae_points += 1; reasons.append("EMA30_30S_SLOPE")
        gap_motion = str(struct.get("gap_motion") or "").upper()
        if candidate == _opposite(parent) and gap_motion == "COLLAPSING_FAST":
            ae_points += 1; reasons.append("PARENT_GAP_COLLAPSE")
        if ae_points:
            families["ARC_EMA"] = ae_points
            score += ae_points

        # PRICE FRESHNESS ----------------------------------------------------
        stale = self._parent_leg_staleness(ticker, parent, yes_ask, no_ask, now)
        if stale["stale"] and candidate == _opposite(parent):
            families["FRESHNESS"] = 2
            score += 2
            primary = True
            reasons.append("STALE_PARENT_LEG")

        # FLASH / observer-first recognition --------------------------------
        rec = self._recognition(ticker, candidate, now)
        if rec:
            age = _f(rec.get("age"), 999.0) or 999.0
            if age <= 9.0:
                families["FLASH"] = 2
                score += 2
                reasons.append("FRESH_RECOGNITION_9S")
                if len(families) >= 2:
                    primary = True
            elif age <= 36.0:
                families["FLASH"] = 1
                score += 1
                reasons.append("RECOGNITION_36S")

        return {
            "score": score,
            "families": families,
            "family_count": len(families),
            "reasons": reasons,
            "contradictions": contradictions,
            "primary": primary,
            "own_score": own_score,
            "opp_score": opp_score,
            "structural_bias": structural_bias,
            "target_event": target_event,
            "target_side": target_side,
            "formation_memory": fmem,
            "recognition": rec,
            "stale": stale,
        }

    def _emit_level2(
        self,
        ticker: str,
        candidate: str,
        parent: str,
        state: str,
        ask: Optional[float],
        snap: Dict[str, Any],
        form: Dict[str, Any],
        struct: Dict[str, Any],
        ev: Dict[str, Any],
        now: float,
        arm: Optional[Dict[str, Any]] = None,
        event: str = "COUNCIL_STATE",
        decision_path: str = "",
        decision_result: str = "",
        note: str = "",
        force: bool = False,
    ) -> None:
        key = (ticker, candidate)
        arm_age = None if not arm else max(0.0, now - float(arm.get("ts") or now))
        arm_ask = None if not arm else _f(arm.get("ask"))
        reprice_abs = None
        reprice_pct = None
        if ask is not None and arm_ask not in (None, 0):
            reprice_abs = ask - arm_ask
            reprice_pct = reprice_abs / arm_ask
        rec = ev.get("recognition") or {}
        fmem = ev.get("formation_memory") or {}
        stale = ev.get("stale") or {}
        active_position_side = self._active_position_side(ticker)
        signature = (
            state, ev.get("score"), tuple(sorted((ev.get("families") or {}).keys())),
            round(ask or -1, 2), decision_path, decision_result,
        )
        if not force:
            last_sig = self.last_level2_emit.get(key)
            last_ts = self.last_level2_emit_ts.get(key, 0.0)
            if signature == last_sig and now - last_ts < 3.0:
                return
        self.last_level2_emit[key] = signature
        self.last_level2_emit_ts[key] = now

        _write(LEVEL2_LOG, LEVEL2_FIELDS, {
            "event": event,
            "arm_id": arm.get("arm_id") if arm else "",
            "ticker": ticker,
            "parent_side": parent,
            "candidate_side": candidate,
            "state": state,
            "ask": ask,
            "arm_ask": arm_ask,
            "arm_age_sec": arm_age,
            "score": ev.get("score"),
            "family_count": ev.get("family_count"),
            "families": ";".join(sorted((ev.get("families") or {}).keys())),
            "primary_trigger": int(bool(ev.get("primary"))),
            "reasons": ";".join(ev.get("reasons") or []),
            "contradictions": ";".join(ev.get("contradictions") or []),
            "decision_path": decision_path,
            "decision_result": decision_result,
            "seconds_left": snap.get("seconds_left"),
            "target_distance": struct.get("target_distance", snap.get("target_distance")),
            "target_event": ev.get("target_event"),
            "target_side": ev.get("target_side"),
            "structural_bias": ev.get("structural_bias"),
            "own_structural_score": ev.get("own_score"),
            "opposite_structural_score": ev.get("opp_score"),
            "formation": form.get("formation"),
            "formation_maturity": form.get("maturity"),
            "local_regime": form.get("regime"),
            "formation_failure": form.get("failure"),
            "formation_memory_side": fmem.get("side"),
            "formation_memory_age_sec": (
                max(0.0, now - float(fmem.get("ts") or now)) if fmem else None
            ),
            "arc_id": snap.get("arc_id"),
            "arc_direction": snap.get("arc_direction"),
            "price_arc_phase": snap.get("price_arc_phase"),
            "ema_gap": struct.get("ema_gap"),
            "ema30_slope6": struct.get("ema30_slope6"),
            "ema30_delta30": struct.get("ema30_delta30"),
            "recognition_source": rec.get("source"),
            "recognition_age_sec": rec.get("age"),
            "recognition_first_ask": rec.get("ask"),
            "parent_leg_stale": int(bool(stale.get("stale"))),
            "parent_leg_age_sec": stale.get("age"),
            "parent_leg_premium_abs": stale.get("premium_abs"),
            "parent_leg_premium_pct": stale.get("premium_pct"),
            "price_reprice_abs": reprice_abs,
            "price_reprice_pct": reprice_pct,
            "active_position_side": active_position_side,
            "entry_count_side": self.entry_count.get(key, 0),
            "note": note,
        })

    def _signal_for_entry(
        self,
        ticker: str,
        side: str,
        parent: str,
        snap: Dict[str, Any],
        form: Dict[str, Any],
        struct: Dict[str, Any],
        ev: Dict[str, Any],
        decision_path: str,
        now: float,
    ) -> Dict[str, Any]:
        close_ts = _f(getattr(core, "v94b_active_close_ts", None))
        seconds_left = max(0.0, close_ts - now) if close_ts is not None else _f(snap.get("seconds_left"))
        elapsed = None
        if seconds_left is not None:
            elapsed = max(0.0, 900.0 - min(900.0, seconds_left))
        try:
            eff60 = core.btc_trend_efficiency(60, 5)
        except Exception:
            eff60 = None
        try:
            r30 = core.btc_range(30)
            r60 = core.btc_range(60)
            r180 = core.btc_range(180)
            ch60 = core.btc_change(60)
        except Exception:
            r30 = r60 = r180 = ch60 = None

        return {
            "setup_grade": "CONFIRMED",
            "signal_grade": "A+" if decision_path == "DECISIVE_3S" else "A",
            "strategy": "LEVEL2_INTERMISSION",
            "market_regime": f"PARENT_{parent}_INTERMISSION_{side}",
            "trade_intent": "INTERMISSION",
            "seconds_to_close": seconds_left,
            "contract_elapsed_seconds": elapsed,
            "btc_price": _f(getattr(core, "btc_last_price", None)),
            "btc_ema_9": _f(getattr(core, "btc_ema_9", None)),
            "btc_ema_30": _f(getattr(core, "btc_ema_30", None)),
            "target_price": struct.get("target_price"),
            "target_distance": struct.get("target_distance"),
            "btc_range_30s": r30,
            "btc_range_60s": r60,
            "btc_range_180s": r180,
            "btc_change_60s": ch60,
            "btc_trend_efficiency_60s": eff60,
            "ema9_arc_stage": struct.get("ema9_arc_stage"),
            "ema9_arc_direction": struct.get("ema9_arc_direction"),
            "early_exception": True,
            "early_exception_reasons": (
                "V95B_LEVEL2_INTERMISSION;"
                + decision_path
                + ";"
                + ";".join(ev.get("reasons") or [])
            ),
            "early_trade": bool(elapsed is not None and elapsed < getattr(core, "EARLY_PROFIT_WINDOW_SECONDS", 180)),
            "session": "V95B_LEVEL2",
            "daypart": "",
            "et_hour": datetime.now(ET).hour,
        }

    def _stand_down(self, key: Tuple[str, str], reason: str, ticker: str, candidate: str,
                    parent: str, ask: Optional[float], snap: Dict[str, Any], form: Dict[str, Any],
                    struct: Dict[str, Any], ev: Dict[str, Any], now: float, arm: Dict[str, Any]) -> None:
        self._emit_level2(
            ticker, candidate, parent, "STAND_DOWN", ask, snap, form, struct, ev, now,
            arm=arm, event="INTERMISSION_STAND_DOWN", decision_result=reason,
            note="Level 2 explicitly stood down; no inherited authority was bypassed.", force=True,
        )
        self.arms.pop(key, None)

    def on_tick(self, ticker: str, yes_ask, no_ask, now: Optional[float] = None) -> None:
        now = time.time() if now is None else float(now)
        snap = self._snapshot(ticker, yes_ask, no_ask)
        parent = self._parent_side(snap)
        struct = self._structural_context()
        form = self._formation_context(now)
        self._handle_rollover(ticker, parent, now)
        self._reconcile_sovereignty(ticker, parent, now)
        self._refresh_memories(ticker, parent, form, struct, now)

        if parent not in ("YES", "NO"):
            return
        candidate = _opposite(parent)
        ask = _ask_for(candidate, yes_ask, no_ask)
        if ask is None or ask <= 0:
            return

        ev = self._evidence(ticker, candidate, parent, yes_ask, no_ask, snap, form, struct, now)
        key = (ticker, candidate)
        arm = self.arms.get(key)

        qualifies_arm = (
            ev["score"] >= L2_ARM_SCORE
            and ev["family_count"] >= L2_ARM_FAMILIES
            and ev["primary"]
        )

        if not qualifies_arm:
            if arm:
                self._stand_down(key, "SIGNAL_FADED", ticker, candidate, parent, ask, snap, form, struct, ev, now, arm)
            else:
                self._emit_level2(
                    ticker, candidate, parent, "WATCH", ask, snap, form, struct, ev, now,
                    note="Composite below ARM threshold."
                )
            return

        if arm is None:
            self.arm_counter += 1
            arm = {
                "arm_id": f"L2A{self.arm_counter:05d}",
                "ts": now,
                "ask": ask,
                "parent_side": parent,
                "side": candidate,
                "max_score": ev["score"],
                "max_families": ev["family_count"],
                "decision_path": "",
            }
            self.arms[key] = arm
            self._emit_level2(
                ticker, candidate, parent, "ARMED", ask, snap, form, struct, ev, now,
                arm=arm, event="INTERMISSION_ARMED",
                note="Strategic parent retained; tactical opposite side armed for 3/6/9 adjudication.", force=True,
            )
        else:
            arm["max_score"] = max(_i(arm.get("max_score"), 0), ev["score"])
            arm["max_families"] = max(_i(arm.get("max_families"), 0), ev["family_count"])

        age = max(0.0, now - float(arm.get("ts") or now))
        arm_ask = _f(arm.get("ask"), ask) or ask
        reprice_abs = ask - arm_ask
        reprice_pct = reprice_abs / arm_ask if arm_ask > 0 else 0.0

        if age > L2_ARM_TTL_SEC:
            self._stand_down(key, "ARM_TTL_EXPIRED", ticker, candidate, parent, ask, snap, form, struct, ev, now, arm)
            return
        if reprice_abs >= L2_MAX_ARM_REPRICE_ABS and reprice_pct >= L2_MAX_ARM_REPRICE_PCT:
            self._stand_down(key, "PRICE_ESCAPED_NO_CHASE", ticker, candidate, parent, ask, snap, form, struct, ev, now, arm)
            return
        if ask < L2_MIN_ASK or ask > L2_MAX_ASK:
            self._emit_level2(
                ticker, candidate, parent, "ARMED_PRICE_OUTSIDE_WINDOW", ask, snap, form, struct, ev, now,
                arm=arm, decision_result="WAIT_ACCEPTED_PRICE_WINDOW",
                note="Composite remains visible but Level 2 will not pay outside the 20c-80c research window."
            )
            if age >= L2_DECISION_DEADLINE_SEC:
                self._stand_down(key, "PRICE_OUTSIDE_WINDOW_AT_9S", ticker, candidate, parent, ask, snap, form, struct, ev, now, arm)
            return

        occupied = self._active_position_side(ticker)
        if occupied in ("YES", "NO"):
            if age >= L2_DECISION_DEADLINE_SEC:
                self._stand_down(
                    key, "POSITION_OCCUPIED_AT_9S", ticker, candidate, parent, ask,
                    snap, form, struct, ev, now, arm
                )
            else:
                self._emit_level2(
                    ticker, candidate, parent, "ARMED_POSITION_OCCUPIED", ask, snap, form, struct, ev, now,
                    arm=arm, decision_result=f"ACTIVE_{occupied}",
                    note="Position blocks execution; Level 2 must still rule by the 9-second deadline."
                )
            return

        count = self.entry_count.get(key, 0)
        if count >= L2_MAX_INTERMISSION_PER_SIDE_PER_CONTRACT:
            self._stand_down(key, "CONTRACT_INTERMISSION_LIMIT", ticker, candidate, parent, ask, snap, form, struct, ev, now, arm)
            return
        last_entry = self.last_intermission_entry_ts.get(key, 0.0)
        if now - last_entry < L2_REENTRY_COOLDOWN_SEC:
            if age >= L2_DECISION_DEADLINE_SEC:
                self._stand_down(
                    key, "COOLDOWN_ACTIVE_AT_9S", ticker, candidate, parent, ask,
                    snap, form, struct, ev, now, arm
                )
            else:
                self._emit_level2(
                    ticker, candidate, parent, "ARMED_COOLDOWN", ask, snap, form, struct, ev, now,
                    arm=arm, decision_result="36S_INTERMISSION_COOLDOWN",
                )
            return

        decisive = (
            age >= L2_DECISIVE_WAIT_SEC
            and ev["score"] >= L2_DECISIVE_SCORE
            and ev["family_count"] >= L2_DECISIVE_FAMILIES
        )
        standard = (
            age >= L2_STANDARD_WAIT_SEC
            and ev["score"] >= L2_STANDARD_SCORE
            and ev["family_count"] >= L2_STANDARD_FAMILIES
        )

        decision_path = "DECISIVE_3S" if decisive else "STANDARD_6S" if standard else ""
        if not decision_path:
            if age >= L2_DECISION_DEADLINE_SEC:
                self._stand_down(key, "NINE_SECOND_DEADLINE", ticker, candidate, parent, ask, snap, form, struct, ev, now, arm)
            else:
                self._emit_level2(
                    ticker, candidate, parent, "ARMED", ask, snap, form, struct, ev, now,
                    arm=arm, decision_result="AWAIT_3_6_9_CONFIRMATION",
                )
            return

        arm["decision_path"] = decision_path
        signal = self._signal_for_entry(ticker, candidate, parent, snap, form, struct, ev, decision_path, now)
        self.pending_entry_context[key] = {
            "arm": dict(arm),
            "decision_path": decision_path,
            "ev": dict(ev),
            "parent": parent,
        }
        entered = False
        try:
            entered = bool(core.paper_enter(ticker, candidate, float(ask), signal))
        finally:
            self.pending_entry_context.pop(key, None)

        if entered:
            self.entry_count[key] = count + 1
            self.last_intermission_entry_ts[key] = now
            pos = (getattr(core, "paper_positions", {}) or {}).get(candidate)
            if isinstance(pos, dict):
                pos["_v95b_arm_id"] = arm.get("arm_id")
                pos["_v95b_parent_side"] = parent
                pos["_v95b_decision_path"] = decision_path
                pos["_v95b_level2_score"] = ev.get("score")
                pos["_v95b_level2_families"] = ";".join(sorted((ev.get("families") or {}).keys()))
            self._emit_level2(
                ticker, candidate, parent, "ENTERED", ask, snap, form, struct, ev, now,
                arm=arm, event="INTERMISSION_ENTERED", decision_path=decision_path,
                decision_result="PAPER_ENTRY_ACCEPTED",
                note="Level-2 tactical intermission entered; Boss sovereignty was not transferred.", force=True,
            )
            self.arms.pop(key, None)
        else:
            self._emit_level2(
                ticker, candidate, parent, "ENTRY_REJECTED", ask, snap, form, struct, ev, now,
                arm=arm, event="INTERMISSION_ENTRY_REJECTED", decision_path=decision_path,
                decision_result="INHERITED_ENTRY_DOOR_REJECTED",
                note="V9.5B decision reached the inherited paper doorway but upstream authority rejected it.", force=True,
            )
            self.arms.pop(key, None)

    def after_entry(self, ticker: str, side: str, ask: float, signal: Dict[str, Any], entered: bool, now: float) -> None:
        if not entered:
            return
        pos = (getattr(core, "paper_positions", {}) or {}).get(side)
        if not isinstance(pos, dict):
            return
        tid = pos.get("trade_id")
        rec = self._recognition(ticker, side, now)
        pending = self.pending_entry_context.get((ticker, side)) or {}
        arm = pending.get("arm") or {}
        strategy = str(signal.get("strategy") or pos.get("strategy") or "")

        observer_ts = _f(rec.get("ts"))
        observer_ask = _f(rec.get("ask"))
        arm_ts = _f(arm.get("ts"))
        arm_ask = _f(arm.get("ask"))
        _write(LATENCY_LOG, LATENCY_FIELDS, {
            "event": "ENTRY_LATENCY",
            "trade_id": tid,
            "ticker": ticker,
            "side": side,
            "strategy": strategy,
            "observer_source": rec.get("source") if rec else "",
            "observer_ts": _utc(observer_ts) if observer_ts is not None else "",
            "observer_ask": observer_ask,
            "observer_to_entry_sec": (now - observer_ts) if observer_ts is not None else None,
            "observer_edge_lost_cents": ((ask - observer_ask) * 100.0) if observer_ask is not None else None,
            "arm_id": arm.get("arm_id"),
            "arm_ts": _utc(arm_ts) if arm_ts is not None else "",
            "arm_ask": arm_ask,
            "arm_to_entry_sec": (now - arm_ts) if arm_ts is not None else None,
            "arm_edge_lost_cents": ((ask - arm_ask) * 100.0) if arm_ask is not None else None,
            "entry_ask": ask,
            "decision_path": pending.get("decision_path") or pos.get("_v95b_decision_path") or "LEGACY",
            "note": "Observer-first and coherent-arm clocks are separate by design.",
        })

    def _catastrophic_points(self, side: str, struct: Dict[str, Any]) -> Tuple[int, list[str], str, int, int]:
        opposite = _opposite(side)
        own_key = "yes_structural_score" if side == "YES" else "no_structural_score"
        opp_key = "no_structural_score" if side == "YES" else "yes_structural_score"
        hold_key = "yes_hold_authority" if side == "YES" else "no_hold_authority"
        own = _i(struct.get(own_key), 0)
        opp = _i(struct.get(opp_key), 0)
        hold = str(struct.get(hold_key) or "UNKNOWN").upper()
        points = 0
        reasons = []
        target_event = str(struct.get("target_event") or "NONE").upper()
        structural_bias = str(struct.get("structural_bias") or "NEUTRAL").upper()
        ema30_event = str(struct.get("ema30_event") or "NONE").upper()
        if target_event == f"TARGET_ACCEPTED_{opposite}":
            points += 2; reasons.append("TARGET_ACCEPTED_AGAINST")
        if structural_bias == opposite and opp >= own + 5:
            points += 2; reasons.append("STRUCTURAL_BIAS_STRONGLY_AGAINST")
        if (side == "YES" and ema30_event == "EMA30_ACCEPTED_BELOW") or (side == "NO" and ema30_event == "EMA30_ACCEPTED_ABOVE"):
            points += 2; reasons.append("EMA30_ACCEPTED_AGAINST")
        if hold == "INVALIDATE" and own <= 1 and opp >= own + 3:
            points += 1; reasons.append("HOLD_AUTHORITY_INVALIDATE")
        return points, reasons, hold, own, opp

    def prepare_thesis_shield(self, ticker: str, yes_ask, no_ask, now: float) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        originals = {
            "ANTICIPATION_FAST_FAIL_SECONDS": getattr(core, "ANTICIPATION_FAST_FAIL_SECONDS", None),
            "V92_STRUCTURAL_EXIT_MIN_AGE": getattr(core, "V92_STRUCTURAL_EXIT_MIN_AGE", None),
            "V85_STRUCTURAL_STOP_MIN_AGE": getattr(core, "V85_STRUCTURAL_STOP_MIN_AGE", None),
            "THESIS_INVALIDATION_MAX_ROI": getattr(core, "THESIS_INVALIDATION_MAX_ROI", None),
        }
        applied: Dict[str, Any] = {}
        struct = self._structural_context()
        positions = getattr(core, "paper_positions", {}) or {}

        for side in ("YES", "NO"):
            pos = positions.get(side)
            if not isinstance(pos, dict) or str(pos.get("ticker") or "") != str(ticker):
                continue
            entry_ts = _f(pos.get("entry_time"), _f(pos.get("entry_ts"), now)) or now
            age = max(0.0, now - entry_ts)
            entry = _f(pos.get("entry_ask"))
            bid = _bid_for(side, yes_ask, no_ask)
            roi = ((bid - entry) / entry) if bid is not None and entry not in (None, 0) else None
            points, reasons, hold, own, opp = self._catastrophic_points(side, struct)
            catastrophic = points >= 4
            active = age < THESIS_PROTECTION_SEC and not catastrophic
            state = "ACTIVE" if active else "RELEASED_CATASTROPHIC" if catastrophic and age < THESIS_PROTECTION_SEC else "EXPIRED"

            if active:
                if originals["ANTICIPATION_FAST_FAIL_SECONDS"] is not None:
                    core.ANTICIPATION_FAST_FAIL_SECONDS = -1.0
                    applied["ANTICIPATION_FAST_FAIL_SECONDS"] = -1.0
                if originals["V92_STRUCTURAL_EXIT_MIN_AGE"] is not None:
                    core.V92_STRUCTURAL_EXIT_MIN_AGE = max(float(originals["V92_STRUCTURAL_EXIT_MIN_AGE"]), THESIS_PROTECTION_SEC)
                    applied["V92_STRUCTURAL_EXIT_MIN_AGE"] = core.V92_STRUCTURAL_EXIT_MIN_AGE
                if originals["V85_STRUCTURAL_STOP_MIN_AGE"] is not None:
                    core.V85_STRUCTURAL_STOP_MIN_AGE = max(float(originals["V85_STRUCTURAL_STOP_MIN_AGE"]), THESIS_PROTECTION_SEC)
                    applied["V85_STRUCTURAL_STOP_MIN_AGE"] = core.V85_STRUCTURAL_STOP_MIN_AGE
                if originals["THESIS_INVALIDATION_MAX_ROI"] is not None:
                    core.THESIS_INVALIDATION_MAX_ROI = -999.0
                    applied["THESIS_INVALIDATION_MAX_ROI"] = -999.0

            tid = str(pos.get("trade_id") or f"{ticker}:{side}")
            signature = (state, points, hold, own, opp, round(age, -1))
            last_sig = self.last_shield_emit.get(tid)
            last_ts = self.last_shield_emit_ts.get(tid, 0.0)
            if signature != last_sig or now - last_ts >= 6.0:
                self.last_shield_emit[tid] = signature
                self.last_shield_emit_ts[tid] = now
                _write(SHIELD_LOG, SHIELD_FIELDS, {
                    "event": "SHIELD_STATE",
                    "trade_id": pos.get("trade_id"),
                    "ticker": ticker,
                    "side": side,
                    "entry_age_sec": age,
                    "entry_ask": entry,
                    "current_bid": bid,
                    "roi": roi,
                    "shield_state": state,
                    "catastrophic_points": points,
                    "catastrophic_reasons": ";".join(reasons),
                    "hold_authority": hold,
                    "own_structural_score": own,
                    "opposite_structural_score": opp,
                    "structural_bias": struct.get("structural_bias"),
                    "target_event": struct.get("target_event"),
                    "ema30_event": struct.get("ema30_event"),
                    "target_distance": struct.get("target_distance"),
                    "legacy_fast_fail_disabled": int(active),
                    "legacy_structural_min_age_sec": THESIS_PROTECTION_SEC if active else "",
                    "legacy_ema9_invalidation_suppressed": int(active),
                    "note": (
                        "Young thesis protected from ordinary fast-fail/structural invalidation; "
                        "emergency, expiry, contract-close and proven-profit protection remain available."
                        if active else
                        "Shield released; inherited management has normal authority."
                    ),
                })
        return originals, applied

    @staticmethod
    def restore_thesis_shield(originals: Dict[str, Any]) -> None:
        for name, value in originals.items():
            if value is not None:
                setattr(core, name, value)


brain = V95BBattleCouncil()
_HOOKS_INSTALLED = False


def install_v95b_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    _HOOKS_INSTALLED = True

    # Observer-first recognition: inherited RS1 writes first; V9.5B then presents
    # that same epoch to Level 2. No source receives unilateral authority.
    original_note = getattr(core, "v94c_note_preentry_candidate")

    def preentry_wrapper(ticker, side, ask, source, structurally_valid=None, now=None):
        ts = time.time() if now is None else float(now)
        result = original_note(ticker, side, ask, source, structurally_valid, now)
        try:
            brain.note_observer_recognition(ticker, side, float(ask), str(source or ""), ts)
        except Exception as exc:
            print(f"⚠️ V9.5B recognition presentation error: {exc}")
        return result

    core.v94c_note_preentry_candidate = preentry_wrapper

    # Run Level 2 after Boss / orbital / rollover / mission observers have had
    # their turn, immediately before paper management on the same top-of-book tick.
    original_mission = getattr(core, "v94g_trade_mission_observer")

    def mission_wrapper(ticker, yes_ask, no_ask, now=None):
        result = original_mission(ticker, yes_ask, no_ask, now)
        ts = time.time() if now is None else float(now)
        try:
            brain.on_tick(ticker, yes_ask, no_ask, ts)
        except Exception as exc:
            print(f"⚠️ V9.5B Level-2 council error: {exc}")
        return result

    core.v94g_trade_mission_observer = mission_wrapper

    # Honest latency accounting wraps the full inherited V9.5A-RS2 doorway.
    original_enter = getattr(core, "paper_enter")

    def paper_enter_wrapper(ticker, side, ask, signal):
        entered = original_enter(ticker, side, ask, signal)
        try:
            brain.after_entry(ticker, side, float(ask), signal or {}, bool(entered), time.time())
        except Exception as exc:
            print(f"⚠️ V9.5B latency accounting error: {exc}")
        return entered

    core.paper_enter = paper_enter_wrapper

    # Thesis Shield wraps V9.5A Treasury + inherited legacy management. It only
    # changes young-thesis invalidation constants for the duration of one manage
    # call, then restores the frozen upstream values.
    original_manage = getattr(core, "paper_manage")

    def paper_manage_wrapper(ticker, yes_ask, no_ask):
        originals = {}
        try:
            originals, _applied = brain.prepare_thesis_shield(ticker, yes_ask, no_ask, time.time())
        except Exception as exc:
            print(f"⚠️ V9.5B Thesis Shield preparation error; inherited manager continues: {exc}")
            return original_manage(ticker, yes_ask, no_ask)

        try:
            return original_manage(ticker, yes_ask, no_ask)
        finally:
            try:
                if originals:
                    brain.restore_thesis_shield(originals)
            except Exception as exc:
                print(f"⚠️ V9.5B Thesis Shield restore error: {exc}")

    core.paper_manage = paper_manage_wrapper


async def main() -> None:
    # Preserve the tested authority chain, then add V9.5B outside it.
    r.a.install_hooks()
    r.install_router_shadow_hooks()
    rs2.install_rs2_hooks()
    install_v95b_hooks()

    print("=" * 118)
    print(f"TACHYOS {VERSION} — LEVEL-2 BATTLE COUNCIL / INTERMISSION AUTHORITY / THESIS SHIELD")
    print(f"RUN ID: {RUN_ID} | SESSION: {SESSION_ID}")
    print("PAPER ONLY | V9.5A + RS1 + RS2 CONTROL TELEMETRY RETAINED.")
    print("")
    print("⚔️ PARENT != CURRENT PLAY: Boss sovereignty is strategic; Level 2 may authorize the opposite tactical intermission.")
    print("🧠 LEVEL 2: STRUCTURE + FORMATION + ARC/EMA + FRESHNESS + FLASH are evidence families, not solo triggers.")
    print("3️⃣ / 6️⃣ / 9️⃣ : decisive composite after 3s, standard after 6s, act-or-stand-down by 9s.")
    print("🚫 NO CHASE: >9c AND >25% repricing from arm quote stands down.")
    print(f"🛡️ THESIS SHIELD: ordinary young-thesis invalidation delayed for {THESIS_PROTECTION_SEC:.0f}s unless catastrophe agrees.")
    print("🧬 FORMATION MEMORY: failure/reversal warnings persist 180s and survive contract rollover.")
    print("📏 LATENCY: observer-first and Level-2-arm clocks are recorded separately.")
    print("")
    print(f"LEVEL2 LOG: {LEVEL2_LOG}")
    print(f"SHIELD LOG: {SHIELD_LOG}")
    print(f"LATENCY LOG: {LATENCY_LOG}")
    print(f"ROLLOVER LOG: {ROLLOVER_LOG}")
    print("=" * 118)

    await core.main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTachyos V9.5B stopped by operator (Ctrl+C).")
