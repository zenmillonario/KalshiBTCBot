"""
TACHYOS V9.5D — CAMPAIGN AUTHORITY / WINNER HARVEST / STATE LIFECYCLE
=====================================================================

PAPER ONLY.

V9.5D supervises the proven V9.5C Leg Geometry layer.

Primary corrections from the V9.5C overnight forensic:
- Campaign Authority sits above local Leg Geometry to stop YES/NO ping-pong.
- Rollover Pre-Arm expires/consumes and cannot authorize stale entries.
- Winner Harvest lets strong winners run and harvests mature plateaus.
- Exit Court demotes local opposite-leg and legacy exits beneath campaign truth.
- Confirmed opposite campaign may enter before the old side exits (one position per side).
"""

from __future__ import annotations

import asyncio
import csv
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import tachys_v9_5c_leg_geometry as c
import tachys_execution_shadow_v9_5d as exshadow

core = c.core
a = c.a
r = c.r
rs2 = c.rs2
ET = c.ET

VERSION = "V9.5D"
_START_TS = time.time()
RUN_ID = datetime.now(ET).strftime("D%Y%m%d_%H%M%S")
SESSION_ID = f"{RUN_ID}_PID{os.getpid()}"

os.environ["TACHYOS_V95D_RUN_ID"] = RUN_ID
os.environ["TACHYOS_V95D_SESSION_ID"] = SESSION_ID

# ---------------------------------------------------------------------------
# FORENSICALLY JUSTIFIED PARAMETERS
# ---------------------------------------------------------------------------

CAMPAIGN_TRANSFER_CONFIRM_SEC = 9.0
CAMPAIGN_STRONG_FORMATION_CONFIRM_SEC = 6.0
CAMPAIGN_FLIP_HYSTERESIS_SEC = 9.0
CAMPAIGN_FLIP_WINDOW_SEC = 300.0
CAMPAIGN_MAX_SOFT_FLIPS = 2
CAMPAIGN_MIN_SCORE_LEAD = 2

PREARM_TTL_SEC = 60.0
NEXT_LEG_PREP_WINDOW_SEC = 180.0
NEXT_LEG_HIGH_EXTENSION_RATIO = 0.35

WINNER_ARM_MFE_PCT = 50.0
WINNER_MAJOR_MFE_PCT = 75.0
WINNER_PLATEAU_SEC = 9.0
WINNER_MEANINGFUL_NEW_HIGH_PCT = 1.0
WINNER_TARGET_PROGRESS_DOLLARS = 3.0
WINNER_LARGE_GIVEBACK_PCT = 15.0

TERMINAL_TARGET_SEC = 60.0
EMERGENCY_HARD_ROI = -0.60

CAMPAIGN_LOG = "tachys_campaign_authority_v9_5d.csv"
WINNER_LOG = "tachys_winner_harvest_v9_5d.csv"
EXIT_COURT_LOG = "tachys_exit_court_v9_5d.csv"
PREARM_LOG = "tachys_prearm_lifecycle_v9_5d.csv"
MANIFEST_LOG = "tachys_run_manifest_v9_5d.csv"

CAMPAIGN_FIELDS = [
    "timestamp","run_id","session_id","event","ticker","campaign_id","campaign_side",
    "campaign_state","campaign_age_sec","candidate_side","candidate_since","candidate_age_sec",
    "yes_score","no_score","score_lead","leg_id","leg_side","leg_state","target_height",
    "target_event","btc_change3","btc_change6","btc_change9","ema_gap","gap_delta6",
    "aligned_369_count","separation_ok","target_decisive","transfer_confirmed",
    "flip_count","seconds_since_last_flip","ruling","reasons"
]

WINNER_FIELDS = [
    "timestamp","run_id","session_id","event","trade_id","ticker","side","entry_ask",
    "current_bid","roi_pct","mfe_pct","seconds_since_mfe_high","last_mfe_high",
    "campaign_side","campaign_state","leg_state","target_height","btc_change3",
    "btc_change6","btc_change9","target_progress_age_sec","winner_state",
    "harvest_timer_age","ruling","reasons"
]

EXIT_FIELDS = [
    "timestamp","run_id","session_id","event","trade_id","ticker","side","entry_ask",
    "current_bid","roi_pct","mfe_pct","proposed_reason","proposal_source","winner_state",
    "campaign_side","campaign_state","target_terminal_state","court_ruling","final_action",
    "reasons"
]

PREARM_FIELDS = [
    "timestamp","run_id","session_id","event","ticker","prearm_side","created_ts","age_sec",
    "state","use_count","invalidated_reason","originating_leg_id","from_ticker","to_ticker",
    "next_leg_prep_side","next_leg_conviction","reasons"
]

MANIFEST_FIELDS = [
    "timestamp","run_id","session_id","version","base_version","start_local","pid",
    "campaign_authority","prearm_ttl_sec","winner_harvest","exit_court",
    "parallel_transition","execution_shadow","note"
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


def _sign(side: str) -> int:
    return 1 if side == "YES" else -1 if side == "NO" else 0


def _bid(side: str, yes_ask, no_ask) -> Optional[float]:
    return c._bid_for(side, yes_ask, no_ask)


def _safe_age(ts: Optional[float], now: float) -> float:
    return 0.0 if not ts else max(0.0, now - float(ts))


class CampaignSupervisor:
    def __init__(self) -> None:
        self.campaign_counter = 0
        self.campaign_id = ""
        self.campaign_side = "NONE"
        self.campaign_state = "CAMPAIGN_NONE"
        self.campaign_started_ts: Optional[float] = None
        self.transfer_candidate: Optional[Dict[str, Any]] = None
        self.last_flip_ts: Optional[float] = None
        self.flip_times: List[float] = []
        self.last_ticker: Optional[str] = None
        self.last_campaign_sig: Optional[Tuple[Any, ...]] = None
        self.last_campaign_emit_ts = 0.0

        self.prearm: Optional[Dict[str, Any]] = None
        self.next_leg_prep_side = "NONE"
        self.next_leg_conviction = "NONE"
        self.next_leg_reasons: List[str] = []
        self.last_prep_print_sig: Optional[Tuple[str, str]] = None

        self.winner_state: Dict[str, Dict[str, Any]] = {}
        self.last_exit_court: Dict[str, Dict[str, Any]] = {}

        self._write_manifest()

    def _write_manifest(self) -> None:
        _write(MANIFEST_LOG, MANIFEST_FIELDS, {
            "version": VERSION,
            "base_version": "V9.5C Leg Geometry",
            "start_local": _local(_START_TS),
            "pid": os.getpid(),
            "campaign_authority": 1,
            "prearm_ttl_sec": PREARM_TTL_SEC,
            "winner_harvest": 1,
            "exit_court": 1,
            "parallel_transition": 1,
            "execution_shadow": 1,
            "note": "V9.5D supervises V9.5C perception; PAPER ONLY; execution reality shadow has zero authority.",
        })

    # ------------------------------------------------------------------
    # CAMPAIGN AUTHORITY
    # ------------------------------------------------------------------

    def _new_campaign(self, side: str, now: float, reason: str) -> None:
        self.campaign_counter += 1
        self.campaign_id = f"CP{self.campaign_counter:05d}"
        self.campaign_side = side
        self.campaign_state = f"CAMPAIGN_{side}"
        self.campaign_started_ts = now
        self.transfer_candidate = None
        print(f"🧭 V9.5D CAMPAIGN | {self.campaign_id} {side} | {reason}")

    def _alignment_369(self, side: str, metrics: Dict[str, Any]) -> int:
        sign = _sign(side)
        r60 = max(1.0, _f(metrics.get("r60"), 1.0) or 1.0)
        threshold = max(1.5, 0.015 * r60)
        count = 0
        for key in ("ch3", "ch6", "ch9"):
            v = _f(metrics.get(key), 0.0) or 0.0
            if v * sign > threshold:
                count += 1
        return count

    def _target_decisive(self, side: str, target: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        event = str(target.get("event") or "NONE")
        if event == "TARGET_RECLAIM_REVERSAL" and target.get("side") == side:
            return True
        if event == f"TARGET_ACCEPTED_{side}":
            return True
        height = _f(target.get("height"))
        r60 = max(1.0, _f(metrics.get("r60"), 1.0) or 1.0)
        return bool(height is not None and height * _sign(side) >= max(8.0, 0.12 * r60))

    def _separation_ok(self, side: str, geom: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        gd6 = _f(geom.get("gd6"))
        if gd6 is None:
            return False
        r60 = max(1.0, _f(metrics.get("r60"), 1.0) or 1.0)
        threshold = max(0.5, 0.015 * r60)
        return gd6 * _sign(side) > threshold

    def _ema9_formation_confirmed(self, side: str, leg: Dict[str, Any],
                                  geom: Dict[str, Any], metrics: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        The EMA9 formation is the guide. A single opposite candle may warn,
        but it cannot flip the campaign.

        Normal confirmation requires the Leg Geometry to progress beyond a
        bare RETURN_SLOPE. An early leap is still allowed when the EMA9 itself
        is clearly turning with curvature + 6/9-second slope + 3/6/9 agreement.
        """
        sign = _sign(side)
        state = str(leg.get("state") or "")
        e9d3 = _f(geom.get("e9d3"), 0.0) or 0.0
        e9d6 = _f(geom.get("e9d6"), 0.0) or 0.0
        e9d9 = _f(geom.get("e9d9"), 0.0) or 0.0
        curvature = _f(geom.get("curvature"), 0.0) or 0.0
        r60 = max(1.0, _f(metrics.get("r60"), 1.0) or 1.0)
        slope_min = max(0.5, 0.01 * r60)
        curve_min = max(0.25, 0.004 * r60)
        align = self._alignment_369(side, metrics)

        progressed = state in ("EMA30_APPROACH", "TRANSFER", "OPPOSITE_BUILD", "EXPANSION")
        slope_agree = (e9d6 * sign >= slope_min) and (e9d9 * sign >= slope_min)
        curvature_agree = curvature * sign >= curve_min
        fast_slope_agree = e9d3 * sign >= 0.0

        reasons: List[str] = []
        if progressed:
            reasons.append(f"FORMATION_PROGRESS_{state}")
        if slope_agree:
            reasons.append("EMA9_SLOPE_6_9")
        if curvature_agree:
            reasons.append("EMA9_CURVATURE_TURN")
        if align >= 2:
            reasons.append(f"369_ALIGN_{align}")

        strong_early_turn = (
            state == "RETURN_SLOPE"
            and slope_agree
            and curvature_agree
            and fast_slope_agree
            and align >= 3
        )
        if strong_early_turn:
            reasons.append("STRONG_RETURN_SLOPE_OVERRIDE")

        return (progressed or strong_early_turn), reasons

    def _strong_transfer(self, side: str, align: int, separation: bool, target_decisive: bool,
                         formation_confirmed: bool) -> bool:
        return formation_confirmed and align >= 3 and separation and target_decisive

    def _recent_flip_count(self, now: float) -> int:
        self.flip_times = [x for x in self.flip_times if now - x <= CAMPAIGN_FLIP_WINDOW_SEC]
        return len(self.flip_times)

    def _confirm_transfer(self, side: str, now: float, reasons: List[str]) -> None:
        old = self.campaign_side
        self.flip_times.append(now)
        self.last_flip_ts = now
        self._new_campaign(side, now, f"TRANSFER {old}->{side}: {';'.join(reasons)}")
        self.campaign_state = f"CAMPAIGN_TRANSFER_CONFIRMED_{side}"

    def observe_context(self, ticker: str, leg: Dict[str, Any], geom: Dict[str, Any],
                        target: Dict[str, Any], seconds_left: Optional[float],
                        wick: str, now: float) -> None:
        ctx = c.brain.last_context or {}
        metrics = dict(ctx.get("metrics") or {})
        ys = int(c.brain.last_scores.get("YES", 0))
        ns = int(c.brain.last_scores.get("NO", 0))

        # Detect contract fencepost, then materialize any prepared state.
        if self.last_ticker is None:
            self.last_ticker = ticker
        elif ticker != self.last_ticker:
            old_ticker = self.last_ticker
            self.last_ticker = ticker
            self.transfer_candidate = None
            if self.next_leg_prep_side in ("YES", "NO") and self.next_leg_conviction == "HIGH":
                self._create_prearm(
                    self.next_leg_prep_side, now, old_ticker, ticker,
                    str(leg.get("leg_id") or ""), "HIGH_NEXT_LEG_PREP"
                )
            elif isinstance(c.brain.prearm, dict):
                inherited_side = str(c.brain.prearm.get("side") or "")
                if inherited_side in ("YES", "NO"):
                    self._create_prearm(
                        inherited_side, now,
                        str(c.brain.prearm.get("from_ticker") or old_ticker), ticker,
                        str(c.brain.prearm.get("leg_id") or leg.get("leg_id") or ""),
                        "V95C_INHERITED_PREARM"
                    )
            self.next_leg_prep_side = "NONE"
            self.next_leg_conviction = "NONE"
            self.next_leg_reasons = []

        self._update_prearm_lifecycle(ticker, leg, target, now)

        # Establish campaign from the current most-likely leg if needed.
        leg_side = str(leg.get("side") or "NONE")
        if self.campaign_side not in ("YES", "NO"):
            if leg_side in ("YES", "NO"):
                self._new_campaign(leg_side, now, "INITIAL_LEG_GEOMETRY")
            else:
                return

        candidate = _opposite(self.campaign_side)
        scores = {"YES": ys, "NO": ns}
        lead = scores[candidate] - scores[self.campaign_side]
        align = self._alignment_369(candidate, metrics)
        separation = self._separation_ok(candidate, geom, metrics)
        target_decisive = self._target_decisive(candidate, target, metrics)
        formation_confirmed, formation_reasons = self._ema9_formation_confirmed(
            candidate, leg, geom, metrics
        )
        leg_support = leg_side == candidate

        # RETURN_SLOPE alone may ARM awareness but cannot normally transfer the
        # campaign. The EMA9 formation must either progress toward/through the
        # Spine or present a strong curvature+slope early-turn override.
        evidence = (
            lead >= CAMPAIGN_MIN_SCORE_LEAD
            and align >= 2
            and (separation or target_decisive)
            and leg_support
            and formation_confirmed
        )
        strong = self._strong_transfer(candidate, align, separation, target_decisive, formation_confirmed)
        in_hysteresis = self.last_flip_ts is not None and now - self.last_flip_ts < CAMPAIGN_FLIP_HYSTERESIS_SEC
        overflip = self._recent_flip_count(now) >= CAMPAIGN_MAX_SOFT_FLIPS

        reasons = []
        if lead >= CAMPAIGN_MIN_SCORE_LEAD: reasons.append(f"SCORE_LEAD_{lead:+d}")
        if align >= 2: reasons.append(f"369_ALIGN_{align}")
        if separation: reasons.append("SPINE_SEPARATION")
        if target_decisive: reasons.append("TARGET_DECISIVE")
        if leg_support: reasons.append(f"LEG_{leg.get('state')}")
        reasons.extend(formation_reasons)

        if evidence and (not in_hysteresis or strong) and (not overflip or strong):
            if not self.transfer_candidate or self.transfer_candidate.get("side") != candidate:
                self.transfer_candidate = {"side": candidate, "since": now, "reasons": reasons}
                self.campaign_state = f"CAMPAIGN_TRANSFER_ARMED_{candidate}"
            else:
                age = now - float(self.transfer_candidate.get("since") or now)
                required = (
                    CAMPAIGN_STRONG_FORMATION_CONFIRM_SEC
                    if "STRONG_RETURN_SLOPE_OVERRIDE" in formation_reasons
                    else CAMPAIGN_TRANSFER_CONFIRM_SEC
                )
                if age >= required:
                    self._confirm_transfer(candidate, now, reasons)
        else:
            if self.transfer_candidate and self.transfer_candidate.get("side") == candidate:
                self.transfer_candidate = None
            self.campaign_state = f"CAMPAIGN_{self.campaign_side}"

        self._update_next_leg_prep(ticker, leg, geom, metrics, target, seconds_left, now)
        self._emit_campaign(ticker, leg, geom, metrics, target, now, lead, align, separation, target_decisive)

    def _emit_campaign(self, ticker, leg, geom, metrics, target, now, lead, align, separation, target_decisive):
        candidate = self.transfer_candidate or {}
        sig = (
            self.campaign_id, self.campaign_side, self.campaign_state,
            candidate.get("side"), int(lead), int(align), bool(separation), bool(target_decisive)
        )
        if sig == self.last_campaign_sig and now - self.last_campaign_emit_ts < 3.0:
            return
        self.last_campaign_sig = sig
        self.last_campaign_emit_ts = now
        _write(CAMPAIGN_LOG, CAMPAIGN_FIELDS, {
            "event": "CAMPAIGN_STATE",
            "ticker": ticker,
            "campaign_id": self.campaign_id,
            "campaign_side": self.campaign_side,
            "campaign_state": self.campaign_state,
            "campaign_age_sec": _safe_age(self.campaign_started_ts, now),
            "candidate_side": candidate.get("side", ""),
            "candidate_since": _utc(candidate.get("since")) if candidate.get("since") else "",
            "candidate_age_sec": _safe_age(candidate.get("since"), now) if candidate else "",
            "yes_score": c.brain.last_scores.get("YES"),
            "no_score": c.brain.last_scores.get("NO"),
            "score_lead": lead,
            "leg_id": leg.get("leg_id"),
            "leg_side": leg.get("side"),
            "leg_state": leg.get("state"),
            "target_height": target.get("height"),
            "target_event": target.get("event"),
            "btc_change3": metrics.get("ch3"),
            "btc_change6": metrics.get("ch6"),
            "btc_change9": metrics.get("ch9"),
            "ema_gap": geom.get("gap"),
            "gap_delta6": geom.get("gd6"),
            "aligned_369_count": align,
            "separation_ok": int(bool(separation)),
            "target_decisive": int(bool(target_decisive)),
            "transfer_confirmed": int(self.campaign_state.startswith("CAMPAIGN_TRANSFER_CONFIRMED")),
            "flip_count": self._recent_flip_count(now),
            "seconds_since_last_flip": _safe_age(self.last_flip_ts, now) if self.last_flip_ts else "",
            "ruling": self.campaign_state,
            "reasons": ";".join(candidate.get("reasons") or []),
        })

    # ------------------------------------------------------------------
    # NEXT LEG PREPARATION + PREARM LIFECYCLE
    # ------------------------------------------------------------------

    def _update_next_leg_prep(self, ticker, leg, geom, metrics, target, seconds_left, now):
        if seconds_left is None or seconds_left > NEXT_LEG_PREP_WINDOW_SEC:
            return
        side = self.campaign_side
        if side not in ("YES", "NO"):
            return

        state = str(leg.get("state") or "")
        gap = abs(_f(geom.get("gap"), 0.0) or 0.0)
        r60 = max(1.0, _f(metrics.get("r60"), 1.0) or 1.0)
        extension = gap / r60
        current_align = self._alignment_369(side, metrics)
        target_owns_current = self._target_decisive(side, target, metrics)

        prep_side = "NONE"
        conviction = "NONE"
        reasons: List[str] = []

        # Mature/extended leg: prepare the natural return to the Spine.
        if state == "MATURE" and extension >= NEXT_LEG_HIGH_EXTENSION_RATIO and current_align >= 2:
            prep_side = _opposite(side)
            conviction = "HIGH" if target_owns_current else "MEDIUM"
            reasons = ["MATURE_EXTENDED_LEG", f"EXTENSION_{extension:.2f}", f"CURRENT_369_{current_align}"]
            if target_owns_current:
                reasons.append("CURRENT_CONTRACT_TARGET_OWNED")
        # Unfinished active leg: prepare continuation through rollover.
        elif str(leg.get("time_capacity_state") or "") == "LEG_INCOMPLETE_EXPECT_ROLLOVER":
            prep_side = str(leg.get("side") or side)
            conviction = "HIGH" if prep_side == side and current_align >= 2 else "MEDIUM"
            reasons = ["LEG_INCOMPLETE_EXPECT_ROLLOVER"]

        changed = (prep_side, conviction) != (self.next_leg_prep_side, self.next_leg_conviction)
        self.next_leg_prep_side = prep_side
        self.next_leg_conviction = conviction
        self.next_leg_reasons = reasons

        if changed and prep_side in ("YES", "NO") and conviction == "HIGH":
            sig = (prep_side, conviction)
            if sig != self.last_prep_print_sig:
                self.last_prep_print_sig = sig
                print(f"📣 PREPARE {prep_side} — NEXT LEG LIKELY — HIGH CONVICTION | {';'.join(reasons)}")

    def _create_prearm(self, side: str, now: float, from_ticker: str, to_ticker: str,
                       leg_id: str, reason: str) -> None:
        self.prearm = {
            "side": side,
            "created_ts": now,
            "state": "PREARM_FRESH",
            "use_count": 0,
            "invalidated_reason": "",
            "originating_leg_id": leg_id,
            "from_ticker": from_ticker,
            "to_ticker": to_ticker,
            "reason": reason,
        }
        # Synchronize V9.5C's prearm object, but reset its timestamp at rollover.
        c.brain.prearm = {"side": side, "leg_id": leg_id, "ts": now, "from_ticker": from_ticker}
        self._log_prearm(to_ticker, now, "PREARM_CREATED", reason)

    def _update_prearm_lifecycle(self, ticker: str, leg: Dict[str, Any], target: Dict[str, Any], now: float) -> None:
        if not isinstance(self.prearm, dict):
            return
        if self.prearm.get("state") != "PREARM_FRESH":
            return

        age = _safe_age(self.prearm.get("created_ts"), now)
        if age > PREARM_TTL_SEC:
            self.prearm["state"] = "PREARM_EXPIRED"
            self.prearm["invalidated_reason"] = "TTL_60S"
            c.brain.prearm = None
            self._log_prearm(ticker, now, "PREARM_EXPIRED", "TTL_60S")
            return

        side = str(self.prearm.get("side") or "")
        # Strong decisive target acceptance against the prepared side invalidates it.
        opp = _opposite(side)
        if target.get("event") == f"TARGET_ACCEPTED_{opp}" and str(leg.get("side") or "") == opp:
            self.prearm["state"] = "PREARM_INVALIDATED"
            self.prearm["invalidated_reason"] = "NEW_CONTRACT_TARGET_AND_LEG_OPPOSE"
            c.brain.prearm = None
            self._log_prearm(ticker, now, "PREARM_INVALIDATED", self.prearm["invalidated_reason"])

    def _log_prearm(self, ticker: str, now: float, event: str, reason: str) -> None:
        p = self.prearm or {}
        _write(PREARM_LOG, PREARM_FIELDS, {
            "event": event,
            "ticker": ticker,
            "prearm_side": p.get("side"),
            "created_ts": _utc(p.get("created_ts")) if p.get("created_ts") else "",
            "age_sec": _safe_age(p.get("created_ts"), now) if p else "",
            "state": p.get("state", "PREARM_NONE"),
            "use_count": p.get("use_count", 0),
            "invalidated_reason": p.get("invalidated_reason", ""),
            "originating_leg_id": p.get("originating_leg_id", ""),
            "from_ticker": p.get("from_ticker", ""),
            "to_ticker": p.get("to_ticker", ""),
            "next_leg_prep_side": self.next_leg_prep_side,
            "next_leg_conviction": self.next_leg_conviction,
            "reasons": reason,
        })

    def prearm_entry_allowed(self, ticker: str, side: str, signal: Dict[str, Any], now: float) -> Tuple[bool, str]:
        reasons = str(signal.get("early_exception_reasons") or "")
        is_rollover = "ROLLOVER_PREARM" in reasons
        if not is_rollover:
            return True, "NOT_PREARM_ENTRY"

        if not isinstance(self.prearm, dict):
            c.brain.prearm = None
            return False, "PREARM_MISSING"
        if self.prearm.get("state") != "PREARM_FRESH":
            c.brain.prearm = None
            return False, f"PREARM_{self.prearm.get('state')}"
        if self.prearm.get("side") != side:
            return False, "PREARM_SIDE_MISMATCH"
        age = _safe_age(self.prearm.get("created_ts"), now)
        if age > PREARM_TTL_SEC:
            self.prearm["state"] = "PREARM_EXPIRED"
            self.prearm["invalidated_reason"] = "TTL_60S"
            c.brain.prearm = None
            self._log_prearm(ticker, now, "PREARM_EXPIRED", "ENTRY_ATTEMPT_AFTER_TTL")
            return False, "PREARM_EXPIRED"
        if int(self.prearm.get("use_count") or 0) >= 1:
            self.prearm["state"] = "PREARM_USED"
            c.brain.prearm = None
            return False, "PREARM_ALREADY_USED"
        return True, "PREARM_FRESH"

    def mark_prearm_used(self, ticker: str, now: float) -> None:
        if not isinstance(self.prearm, dict):
            return
        self.prearm["use_count"] = int(self.prearm.get("use_count") or 0) + 1
        self.prearm["state"] = "PREARM_USED"
        c.brain.prearm = None
        self._log_prearm(ticker, now, "PREARM_USED", "FIRST_SUCCESSFUL_ENTRY_CONSUMED")

    # ------------------------------------------------------------------
    # ENTRY COURT
    # ------------------------------------------------------------------

    def entry_allowed(self, ticker: str, side: str, signal: Dict[str, Any], now: float) -> Tuple[bool, str, bool]:
        pre_ok, pre_reason = self.prearm_entry_allowed(ticker, side, signal, now)
        if not pre_ok:
            return False, pre_reason, False

        reasons = str(signal.get("early_exception_reasons") or "")
        is_prearm = "ROLLOVER_PREARM" in reasons and pre_reason == "PREARM_FRESH"

        # Normal tactical entries must follow the campaign.
        if self.campaign_side in ("YES", "NO") and side != self.campaign_side:
            # A fresh high-conviction prearm gets controlled leap-of-faith authority.
            if is_prearm:
                ctx = c.brain.last_context or {}
                metrics = dict(ctx.get("metrics") or {})
                align = self._alignment_369(side, metrics)
                score_lead = int(c.brain.last_scores.get(side, 0)) - int(c.brain.last_scores.get(_opposite(side), 0))
                if align >= 2 and score_lead >= 0:
                    return True, "FRESH_PREARM_OVERRIDE", True
            return False, f"CAMPAIGN_{self.campaign_side}_STICKY", False

        return True, f"CAMPAIGN_{self.campaign_side}_ALIGNED", is_prearm

    # ------------------------------------------------------------------
    # WINNER HARVEST
    # ------------------------------------------------------------------

    def _winner_record(self, position: Dict[str, Any], now: float) -> Dict[str, Any]:
        tid = str(position.get("trade_id"))
        rec = self.winner_state.get(tid)
        if rec is None:
            rec = {
                "last_mfe": _f(position.get("mfe_pct"), 0.0) or 0.0,
                "last_high_ts": now,
                "last_target_best": None,
                "last_target_progress_ts": now,
                "state": "WINNER_NONE",
                "harvest_since": None,
            }
            self.winner_state[tid] = rec
        return rec

    def winner_ruling(self, ticker: str, side: str, position: Dict[str, Any],
                       yes_ask, no_ask, now: float) -> Dict[str, Any]:
        bid = _bid(side, yes_ask, no_ask)
        entry = _f(position.get("entry_ask"))
        roi_pct = None if bid is None or entry in (None, 0) else ((bid - entry) / entry) * 100.0
        existing_mfe = _f(position.get("mfe_pct"), 0.0) or 0.0
        current_mfe = max(existing_mfe, roi_pct if roi_pct is not None else existing_mfe)
        rec = self._winner_record(position, now)

        if current_mfe >= rec["last_mfe"] + WINNER_MEANINGFUL_NEW_HIGH_PCT:
            rec["last_mfe"] = current_mfe
            rec["last_high_ts"] = now
            rec["harvest_since"] = None
            rec["state"] = "WINNER_EXPANDING"

        ctx = c.brain.last_context if (c.brain.last_context or {}).get("ticker") == ticker else {}
        metrics = dict(ctx.get("metrics") or {})
        target = dict(ctx.get("target") or {})
        leg = dict(ctx.get("leg") or {})

        height = _f(target.get("height"))
        favorable_height = None if height is None else height * _sign(side)
        if favorable_height is not None:
            best = rec.get("last_target_best")
            if best is None or favorable_height >= best + WINNER_TARGET_PROGRESS_DOLLARS:
                rec["last_target_best"] = favorable_height
                rec["last_target_progress_ts"] = now

        high_age = _safe_age(rec.get("last_high_ts"), now)
        target_age = _safe_age(rec.get("last_target_progress_ts"), now)
        align = self._alignment_369(side, metrics)
        drawdown = current_mfe - (roi_pct if roi_pct is not None else current_mfe)
        campaign_aligned = self.campaign_side == side
        candidate_against = bool(self.transfer_candidate and self.transfer_candidate.get("side") == _opposite(side))

        ruling = "NO_WINNER_ACTION"
        reasons: List[str] = []

        if current_mfe < WINNER_ARM_MFE_PCT:
            rec["state"] = "WINNER_NONE"
            rec["harvest_since"] = None
        else:
            if high_age < WINNER_PLATEAU_SEC or align >= 2 or (campaign_aligned and target_age < WINNER_PLATEAU_SEC):
                rec["state"] = "WINNER_EXPANDING"
                rec["harvest_since"] = None
                ruling = "HOLD_WINNER_EXPANDING"
                if high_age < WINNER_PLATEAU_SEC: reasons.append("FRESH_MFE_PROGRESS")
                if align >= 2: reasons.append(f"369_STRENGTH_{align}")
                if target_age < WINNER_PLATEAU_SEC: reasons.append("TARGET_PROGRESS")
            else:
                if rec.get("harvest_since") is None:
                    # Plateau clock begins at the last meaningful MFE high,
                    # not after we finally notice the plateau.
                    rec["harvest_since"] = rec.get("last_high_ts") or now
                harvest_age = _safe_age(rec.get("harvest_since"), now)
                rec["state"] = "WINNER_HARVEST_WATCH"
                reasons.append(f"NO_HIGH_{high_age:.1f}s")
                if align <= 1: reasons.append("369_DECAY")
                if target_age >= WINNER_PLATEAU_SEC: reasons.append("TARGET_STALLED")
                if candidate_against: reasons.append("OPPOSITE_TRANSFER_ARMED")
                if drawdown >= WINNER_LARGE_GIVEBACK_PCT: reasons.append(f"GIVEBACK_{drawdown:.1f}pp")

                weak_count = sum([
                    align <= 1,
                    target_age >= WINNER_PLATEAU_SEC,
                    candidate_against,
                    drawdown >= WINNER_LARGE_GIVEBACK_PCT,
                    not campaign_aligned,
                ])
                if harvest_age >= WINNER_PLATEAU_SEC and weak_count >= 2:
                    rec["state"] = "WINNER_PLATEAU_9S"
                    ruling = "WINNER_HARVEST_EXIT"
                elif current_mfe >= WINNER_MAJOR_MFE_PCT and high_age >= WINNER_PLATEAU_SEC and weak_count >= 3:
                    rec["state"] = "WINNER_PLATEAU_9S"
                    ruling = "WINNER_HARVEST_EXIT"
                else:
                    ruling = "WATCH_WINNER_PLATEAU"

        row = {
            "event": "WINNER_STATE",
            "trade_id": position.get("trade_id"),
            "ticker": ticker,
            "side": side,
            "entry_ask": entry,
            "current_bid": bid,
            "roi_pct": roi_pct,
            "mfe_pct": current_mfe,
            "seconds_since_mfe_high": high_age,
            "last_mfe_high": rec.get("last_mfe"),
            "campaign_side": self.campaign_side,
            "campaign_state": self.campaign_state,
            "leg_state": leg.get("state"),
            "target_height": height,
            "btc_change3": metrics.get("ch3"),
            "btc_change6": metrics.get("ch6"),
            "btc_change9": metrics.get("ch9"),
            "target_progress_age_sec": target_age,
            "winner_state": rec.get("state"),
            "harvest_timer_age": _safe_age(rec.get("harvest_since"), now) if rec.get("harvest_since") else "",
            "ruling": ruling,
            "reasons": ";".join(reasons),
        }
        _write(WINNER_LOG, WINNER_FIELDS, row)
        return row

    # ------------------------------------------------------------------
    # EXIT COURT
    # ------------------------------------------------------------------

    def exit_court(self, ticker: str, side: str, position: Dict[str, Any],
                   yes_ask, no_ask, now: float) -> Dict[str, Any]:
        winner = self.winner_ruling(ticker, side, position, yes_ask, no_ask, now)
        bid = _bid(side, yes_ask, no_ask)
        entry = _f(position.get("entry_ask"))
        roi = None if bid is None or entry in (None, 0) else (bid - entry) / entry
        mfe = _f(winner.get("mfe_pct"), 0.0) or 0.0

        ctx = c.brain.last_context if (c.brain.last_context or {}).get("ticker") == ticker else {}
        target = dict(ctx.get("target") or {})
        seconds_left = _f(ctx.get("seconds_left"))
        opp = _opposite(side)

        final = "HOLD"
        ruling = "HOLD_CAMPAIGN"
        reasons: List[str] = []
        terminal = "NONE"

        if roi is not None and roi <= EMERGENCY_HARD_ROI:
            final = "ALLOW_INHERITED_EMERGENCY"
            ruling = "EMERGENCY_BYPASS"
            reasons.append("HARD_EMERGENCY")
        elif winner.get("ruling") == "WINNER_HARVEST_EXIT":
            final = "EXIT"
            ruling = "WINNER_HARVEST_EXIT"
            reasons.append("WINNER_STOPPED_PAYING")
        elif self.campaign_side == opp and self.campaign_state.startswith("CAMPAIGN_TRANSFER_CONFIRMED"):
            final = "EXIT"
            ruling = "CAMPAIGN_TRANSFER_EXIT"
            reasons.append(f"CAMPAIGN_NOW_{opp}")
        elif seconds_left is not None and seconds_left <= TERMINAL_TARGET_SEC:
            height = _f(target.get("height"))
            if height is not None and height * _sign(side) < 0:
                event = str(target.get("event") or "")
                if event == f"TARGET_ACCEPTED_{opp}" or abs(height) >= 8.0:
                    final = "EXIT"
                    ruling = "TERMINAL_TARGET_EXIT"
                    terminal = f"TARGET_{opp}_CONTROL"
                    reasons.append("FINAL_MINUTE_TARGET_AGAINST")
        else:
            reasons.append(f"CAMPAIGN_{self.campaign_side}_HOLDS")

        row = {
            "event": "EXIT_COURT",
            "trade_id": position.get("trade_id"),
            "ticker": ticker,
            "side": side,
            "entry_ask": entry,
            "current_bid": bid,
            "roi_pct": None if roi is None else roi * 100.0,
            "mfe_pct": mfe,
            "proposed_reason": "",
            "proposal_source": "V95C_LOCAL_LEG_AND_LEGACY_DEMOTED",
            "winner_state": winner.get("winner_state"),
            "campaign_side": self.campaign_side,
            "campaign_state": self.campaign_state,
            "target_terminal_state": terminal,
            "court_ruling": ruling,
            "final_action": final,
            "reasons": ";".join(reasons),
        }
        _write(EXIT_COURT_LOG, EXIT_FIELDS, row)
        self.last_exit_court[str(position.get("trade_id"))] = row
        return row

    def execute_exit(self, position: Dict[str, Any], yes_ask, no_ask, ruling: str) -> bool:
        side = str(position.get("side") or "")
        bid = _bid(side, yes_ask, no_ask)
        if side not in ("YES", "NO") or bid is None:
            return False
        qty = int(float(position.get("qty") or 0))
        cost = _f(position.get("cost"), 0.0) or 0.0
        pnl = qty * bid - cost
        entry = _f(position.get("entry_ask"))
        roi = 0.0 if entry in (None, 0) else (bid - entry) / entry
        reason = f"V95D_{ruling}"

        if pnl < 0 and position.get("v85_countertrend_entry"):
            try:
                core.v85_last_failed_countertrend[side] = time.time()
            except Exception:
                pass

        core.paper_realized_pnl += pnl
        core.log_paper_event("EXIT", position, bid, reason)
        core.record_contract_trade(position, bid, pnl, reason)
        try:
            core.v94b_finalize_trade_shadows(position, bid, roi, reason, pnl)
        except Exception as exc:
            print(f"V9.5D finalize error: {exc}")

        core.paper_positions[side] = None
        core.last_paper_exit_time[side] = time.time()
        print(
            f"⚖️ V9.5D EXIT COURT | #{position.get('trade_id')} {side} @ {bid:.3f} "
            f"| {ruling} | PnL=USD {pnl:+.2f}"
        )
        return True


supervisor = CampaignSupervisor()
execution_shadow = exshadow.ExecutionShadow(core, RUN_ID, SESSION_ID)
_HOOKS_INSTALLED = False


# ---------------------------------------------------------------------------
# LEGACY EXIT SUPPRESSION
# ---------------------------------------------------------------------------

def _suppress_ordinary_legacy_exits() -> Dict[str, Any]:
    replacements = {
        "ANTICIPATION_FAST_FAIL_SECONDS": -1.0,
        "KING_GUARD_ARM_MFE": 999.0,
        "V923_PROVEN_20_FLOOR": -999.0,
        "V923_PROVEN_30_FLOOR": -999.0,
        "V923_PROVEN_50_FLOOR": -999.0,
        "V85_STRUCTURAL_STOP_MIN_AGE": 1e9,
        "V84_SWIRL_LOCK_MFE": 999.0,
        "V84_SWIRL_SNIP_TP": 999.0,
        "BIRD_17_TRIGGER": 999.0,
        "BIRD_20_TRIGGER": 999.0,
        "BIRD_23_TRIGGER": 999.0,
        "V92_STRUCTURAL_EXIT_MIN_AGE": 1e9,
        "V92_PROTECT_MFE": 999.0,
        "PROVEN_MFE_PROTECT": 999.0,
        "THESIS_INVALIDATION_MAX_ROI": -999.0,
        "CORE_SIDEWAYS_TP_ROI": 999.0,
        "CORE_SIDEWAYS_TP_MID_ROI": 999.0,
        "LATE_PROFIT_TP_ROI": 999.0,
        "EARLY_TAKE_PROFIT_ROI": 999.0,
        "TRAIL_ACTIVATE_ROI": 999.0,
        "LATE_RISK_WINDOW_SECONDS": -1.0,
        "PROVEN_RECOVERY_MIN_SECONDS_LEFT": -1.0,
        "EMA9_ARC_EXIT_MANAGEMENT": False,
    }
    old: Dict[str, Any] = {}
    for name, value in replacements.items():
        if hasattr(core, name):
            old[name] = getattr(core, name)
            setattr(core, name, value)
    return old


def _restore(old: Dict[str, Any]) -> None:
    for name, value in old.items():
        setattr(core, name, value)


# ---------------------------------------------------------------------------
# HOOK INSTALLATION
# ---------------------------------------------------------------------------

def install_v95d_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    _HOOKS_INSTALLED = True

    # 1) Observe campaign state before V9.5C's entry loop acts.
    original_emit_leg = c.brain._emit_leg

    def emit_leg_wrapper(ticker, leg, geom, target, seconds_left, wick, now):
        try:
            supervisor.observe_context(ticker, leg, geom, target, seconds_left, wick, now)
        except Exception as exc:
            print(f"⚠️ V9.5D campaign observer error: {exc}")
        return original_emit_leg(ticker, leg, geom, target, seconds_left, wick, now)

    c.brain._emit_leg = emit_leg_wrapper

    # 2) V9.5C's any-position mutex is replaced by the base engine's
    # one-position-per-side rule plus V9.5D Campaign Authority.
    def v95d_active_position_passthrough(ticker):
        return None

    c.brain._active_position = v95d_active_position_passthrough

    # 3) Disable V9.5C's local-opposite-leg exit authority.
    def v95c_exit_demoted(ticker, side, position, yes_ask, no_ask, now):
        return {
            "gate_ruling": "V95C_LOCAL_EXIT_DEMOTED",
            "final_action": "HOLD",
            "trade_id": position.get("trade_id"),
        }

    c.brain.exit_gate = v95c_exit_demoted

    # 4) Entry court.
    original_enter = core.paper_enter

    def paper_enter_wrapper(ticker, side, ask, signal):
        now = time.time()
        signal = dict(signal or {})

        try:
            allowed, reason, prearm_override = supervisor.entry_allowed(ticker, side, signal, now)
        except Exception as exc:
            print(f"⚠️ V9.5D entry court error; blocking experimental entry: {exc}")
            return False

        if not allowed:
            print(f"🧱 V9.5D ENTRY BLOCK | {side} @ {float(ask):.3f} | {reason}")
            return False

        # Preserve V9.5C bypass behavior while identifying V9.5D in telemetry.
        base_strategy = str(signal.get("strategy") or "V95C_LEG_GEOMETRY")
        if base_strategy.startswith("V95C"):
            signal["strategy"] = "V95C_V95D_CAMPAIGN"
        signal["early_exception_reasons"] = (
            (signal.get("early_exception_reasons") or "")
            + (";" if signal.get("early_exception_reasons") else "")
            + f"V95D_{reason}"
        )

        opposite = _opposite(side)
        opp_pos = (getattr(core, "paper_positions", {}) or {}).get(opposite)
        parallel = (
            isinstance(opp_pos, dict)
            and str(opp_pos.get("ticker") or "") == str(ticker)
            and (supervisor.campaign_side == side or prearm_override)
        )

        old_mutex = None
        if parallel and hasattr(core, "v923_mutex_entry_ok"):
            old_mutex = core.v923_mutex_entry_ok
            core.v923_mutex_entry_ok = lambda _ticker, _side, _now=None: (True, "V95D_PARALLEL_TRANSITION")
            print(f"↔️ V9.5D PARALLEL TRANSITION | existing {opposite} + new {side} candidate")

        try:
            entered = bool(original_enter(ticker, side, ask, signal))
        finally:
            if old_mutex is not None:
                core.v923_mutex_entry_ok = old_mutex

        if entered:
            pos = (getattr(core, "paper_positions", {}) or {}).get(side)
            if isinstance(pos, dict):
                pos["_v95d_campaign_id"] = supervisor.campaign_id
                pos["_v95d_campaign_side"] = supervisor.campaign_side
                pos["_v95d_entry_reason"] = reason
                pos["_v95d_parallel_transition"] = bool(parallel)
                try:
                    execution_shadow.on_entry(
                        pos, ticker, side, ask, now=time.time()
                    )
                except Exception as exc:
                    print(f"⚠️ V9.5D execution-shadow entry error: {exc}")
            if prearm_override or "ROLLOVER_PREARM" in str(signal.get("early_exception_reasons") or ""):
                supervisor.mark_prearm_used(ticker, now)

        return entered

    core.paper_enter = paper_enter_wrapper

    # 5) Exit Court wraps the already-installed V9.5C manager.
    original_manage = core.paper_manage

    def paper_manage_wrapper(ticker, yes_ask, no_ask):
        now = time.time()
        try:
            execution_shadow.observe(ticker, yes_ask, no_ask, now)
        except Exception as exc:
            print(f"⚠️ V9.5D execution-shadow quote error: {exc}")

        positions: List[Tuple[str, Dict[str, Any]]] = []
        courts: Dict[str, Dict[str, Any]] = {}

        for side in ("YES", "NO"):
            p = (getattr(core, "paper_positions", {}) or {}).get(side)
            if isinstance(p, dict) and str(p.get("ticker") or "") == str(ticker):
                positions.append((side, p))
                try:
                    courts[side] = supervisor.exit_court(ticker, side, p, yes_ask, no_ask, now)
                except Exception as exc:
                    print(f"⚠️ V9.5D Exit Court error for {side}: {exc}")
                    courts[side] = {
                        "court_ruling": "EMERGENCY_BYPASS",
                        "final_action": "ALLOW_INHERITED_EMERGENCY",
                    }

        # Ordinary inherited exits become proposals. Hard emergency exits remain live.
        old = _suppress_ordinary_legacy_exits() if positions else {}
        try:
            result = original_manage(ticker, yes_ask, no_ask)
        finally:
            if old:
                _restore(old)

        # If an inherited hard-emergency path closed a position, capture its
        # execution reality before doing anything else. Ordinary inherited exits
        # remain suppressed by Exit Court.
        for side, p in positions:
            still = (getattr(core, "paper_positions", {}) or {}).get(side) is p
            if not still:
                try:
                    execution_shadow.on_exit(
                        p, ticker, side, _bid(side, yes_ask, no_ask),
                        "INHERITED_EMERGENCY_EXIT", now=time.time(),
                        yes_ask=yes_ask, no_ask=no_ask,
                    )
                except Exception as exc:
                    print(f"⚠️ V9.5D execution-shadow inherited-exit error: {exc}")

        # Execute V9.5D court rulings only if the inherited emergency manager
        # did not already close the position.
        for side, p in positions:
            still = (getattr(core, "paper_positions", {}) or {}).get(side) is p
            court = courts.get(side) or {}
            if still and court.get("final_action") == "EXIT":
                ruling = str(court.get("court_ruling"))
                if supervisor.execute_exit(p, yes_ask, no_ask, ruling):
                    try:
                        execution_shadow.on_exit(
                            p, ticker, side, _bid(side, yes_ask, no_ask),
                            f"V95D_{ruling}", now=time.time(),
                            yes_ask=yes_ask, no_ask=no_ask,
                        )
                    except Exception as exc:
                        print(f"⚠️ V9.5D execution-shadow exit error: {exc}")

        return result

    core.paper_manage = paper_manage_wrapper


async def main() -> None:
    # Install the same proven V9.5C stack first.
    a.install_hooks()
    r.install_router_shadow_hooks()
    rs2.install_rs2_hooks()
    c.install_v95c_hooks()

    # Then supersede authority with V9.5D.
    install_v95d_hooks()

    print("=" * 118)
    print("TACHYOS V9.5D — CAMPAIGN AUTHORITY / WINNER HARVEST / EXIT COURT")
    print(f"RUN ID: {RUN_ID} | SESSION: {SESSION_ID}")
    print("PAPER ONLY | V9.5C Leg Geometry remains the perception layer.")
    print("")
    print("🧭 CAMPAIGN AUTHORITY: EMA9 formation guides transfer; opposite candles are evidence, not authority.")
    print("⏳ PREARM TTL: rollover memory expires in 60s and is consumed after first use.")
    print("🏁 WINNER HARVEST: strong winners breathe; mature plateaus are collected.")
    print("⚖️ EXIT COURT: local opposite-leg + legacy exits are proposals, not sovereign exits.")
    print("↔️ PARALLEL TRANSITION: one position per side may overlap after confirmed transfer.")
    print("📣 NEXT LEG PREP: current-contract side and next-leg side are tracked separately.")
    print("🪞 EXECUTION SHADOW: 0/250/500/1000ms L2 fill + fee-adjusted live P/L; ZERO authority.")
    print("")
    print(f"CAMPAIGN LOG : {CAMPAIGN_LOG}")
    print(f"WINNER LOG   : {WINNER_LOG}")
    print(f"EXIT COURT   : {EXIT_COURT_LOG}")
    print(f"PREARM LOG   : {PREARM_LOG}")
    print(f"EXEC QUOTES  : {exshadow.QUOTE_LOG}")
    print(f"EXEC TRADES  : {exshadow.TRADE_LOG}")
    print("=" * 118)

    await core.main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTachyos V9.5D stopped by operator (Ctrl+C).")
