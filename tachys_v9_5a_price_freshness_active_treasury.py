"""
TACHYOS V9.5A — PRICE FRESHNESS / ACTIVE TREASURY
=================================================

PAPER ONLY.

V9.5A is the first post-V9.4M authority experiment. It imports the complete
V9.4M observer stack unchanged, then promotes exactly two researched ideas into
paper-trading authority:

1) LEG PRICE FRESHNESS ENTRY GATE
   When an entry agrees with the active structural leg, do not chase a quote
   after too much of that leg has already been repriced. The first experiment
   blocks only when ALL conditions are true:
       - ask is at least 25% above the active leg's starting side bid
       - ask is at least 9 cents above that starting side bid
       - the active leg is at least 90 seconds old
   Counter-leg / reversal entries are not blocked by this gate. If no reliable
   active-leg baseline exists, the legacy paper authority is allowed to decide.

2) ACTIVE TREASURY DEFENSE
   V9.4M's first DEFEND_CANDIDATE now has paper-exit authority. The M rule only
   creates a candidate after a trade has proven >=20% MFE, given back >=12
   percentage points, retained <=55% of peak ROI, and accumulated at least two
   structural contradiction points. BREATHING_CANDIDATE remains HOLD.

Everything else remains unchanged:
   - sizing unchanged
   - legacy emergency stops unchanged
   - Medic remains shadow
   - Campaign Ledger remains context only
   - Second Spear V2 remains shadow
   - Twin Gate remains shadow
   - Elasticity Lite remains shadow

The V9.4M observers remain as the control/intelligence layer. V9.5A additionally
logs every price-freshness decision and counterfactual outcomes for blocked
entries so the new authority can be audited against the old behavior.
"""

from __future__ import annotations

import asyncio
import csv
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import tachys_v9_4m_battle_plan_treasury_shadow as m

k = m.k
j = m.j
core = m.core

VERSION = "V9.5A"
ET = m.ET
_START_TS = time.time()
RUN_ID = datetime.now(ET).strftime("A%Y%m%d_%H%M%S")
SESSION_ID = f"{RUN_ID}_PID{os.getpid()}"

os.environ["TACHYOS_V95A_RUN_ID"] = RUN_ID
os.environ["TACHYOS_V95A_SESSION_ID"] = SESSION_ID

# ---------------------------------------------------------------------------
# Promoted PAPER-authority experiment parameters
# ---------------------------------------------------------------------------

# Evidence from V9.4M: aligned entries that had repriced >=25% from the active
# leg start were strongly loss-concentrated. A 9-cent absolute floor prevents
# tiny-baseline percentage noise from being treated as a chase. Requiring the
# leg to be at least 90s old preserves young displacement/impulse legs.
PRICE_FRESHNESS_MAX_PREMIUM_PCT = 0.25
PRICE_FRESHNESS_MIN_PREMIUM_ABS = 0.09
PRICE_FRESHNESS_MIN_LEG_AGE_SEC = 90.0

BLOCK_OUTCOME_HORIZONS = (15, 30, 60, 120)

PRICE_FRESHNESS_LOG = "tachys_price_freshness_v9_5a.csv"
ACTIVE_TREASURY_LOG = "tachys_active_treasury_v9_5a.csv"
MANIFEST_LOG = "tachys_run_manifest_v9_5a.csv"

PRICE_FIELDS = [
    "timestamp", "run_id", "session_id", "event", "candidate_id",
    "ticker", "side", "ask", "signal_grade", "setup_grade", "strategy",
    "gate_action", "gate_reason", "aligned_with_leg",
    "leg_id", "arc_id", "leg_direction", "leg_side", "leg_age_sec",
    "leg_start_bid", "leg_max_bid", "leg_min_bid",
    "premium_abs", "premium_pct", "premium_pct_threshold",
    "premium_abs_threshold", "leg_age_threshold_sec", "chapter_score",
    "chapter_label", "chapter_reasons", "seconds_left", "target_distance",
    "remaining_capacity", "price_arc_phase", "battlefield_class",
    "cage_state", "dragon_state", "horizon_sec", "current_bid",
    "shadow_roi", "shadow_mfe_roi", "shadow_mae_roi", "note",
]

TREASURY_FIELDS = [
    "timestamp", "run_id", "session_id", "event", "candidate_id",
    "trade_id", "ticker", "side", "qty", "entry_ask", "exit_bid",
    "exit_roi", "exit_pnl", "mfe_roi", "giveback_points",
    "proven_level", "thesis_integrity", "contradiction_points",
    "holdability_label", "seconds_left", "arc_id", "arc_direction",
    "price_arc_phase", "remaining_capacity", "battlefield_class",
    "boss_side", "hand_side", "cage_state", "dragon_state",
    "target_distance", "reason", "note",
]

MANIFEST_FIELDS = [
    "timestamp", "run_id", "session_id", "version", "base_version",
    "paper_authority", "start_local", "pid", "price_premium_pct",
    "price_premium_abs", "price_min_leg_age_sec", "treasury_authority",
    "unchanged_authority", "research_layers", "note",
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
        writer.writerow({key: payload.get(key, "") for key in fields})


def _side_bid(side: str, yes_ask, no_ask) -> Optional[float]:
    return m._side_bid(side, yes_ask, no_ask)


def _trade_id(position: Dict[str, Any]) -> str:
    return m._position_trade_id(
        position,
        f"{position.get('ticker', '')}:{position.get('side', '')}",
    )


class V95AAuthority:
    def __init__(self) -> None:
        self.price_counter = 0
        self.blocked: Dict[str, Dict[str, Any]] = {}
        self._write_manifest()

    def _write_manifest(self) -> None:
        _write(MANIFEST_LOG, MANIFEST_FIELDS, {
            "version": VERSION,
            "base_version": "V9.4M -> V9.4K -> V9.4J -> V9.4I",
            "paper_authority": "V9.5A_PRICE_FRESHNESS_AND_ACTIVE_TREASURY",
            "start_local": _local(_START_TS),
            "pid": os.getpid(),
            "price_premium_pct": PRICE_FRESHNESS_MAX_PREMIUM_PCT,
            "price_premium_abs": PRICE_FRESHNESS_MIN_PREMIUM_ABS,
            "price_min_leg_age_sec": PRICE_FRESHNESS_MIN_LEG_AGE_SEC,
            "treasury_authority": "FIRST_V94M_DEFEND_CANDIDATE_EXITS_PAPER_POSITION",
            "unchanged_authority": "SIZING;LEGACY_STOPS;CORE;EARLY_IMPULSE;HANDOFF",
            "research_layers": (
                "V94M_CONTROL;MEDIC_SHADOW;CAMPAIGN_CONTEXT;SECOND_SPEAR_V2_SHADOW;"
                "TWIN_GATE_SHADOW;ELASTICITY_LITE_SHADOW"
            ),
            "note": (
                "First authority promotion after V9.4M. Two changes only: "
                "late-leg price chase may block entry; Treasury DEFEND_CANDIDATE may exit."
            ),
        })

    def _snapshot(self, ticker: str, side: str, ask: float) -> Dict[str, Any]:
        try:
            if side == "YES":
                return dict(m.brain.snapshot(ticker, yes_ask=ask) or {})
            return dict(m.brain.snapshot(ticker, no_ask=ask) or {})
        except Exception:
            return dict(getattr(j.brain, "last_snapshot", {}) or {})

    def _chapter_context(self, ticker: str, snap: Dict[str, Any]) -> Tuple[int, str, str]:
        prior = m.brain.last_exit_by_ticker.get(ticker)
        prior_snap = prior.get("snapshot") if isinstance(prior, dict) else None
        try:
            return m.brain._chapter_compare(snap, prior_snap)
        except Exception:
            return (9, "FIRST_CHAPTER", "chapter_context_unavailable")

    def evaluate_entry(
        self,
        ticker: str,
        side: str,
        ask: float,
        signal: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any]]:
        now = time.time()
        snap = self._snapshot(ticker, side, ask)
        leg = m.brain.active_leg.get(ticker)
        grade, setup, _score, _sig_reason, strategy = m._signal_meta(signal or {})
        chapter_score, chapter_label, chapter_reasons = self._chapter_context(ticker, snap)

        aligned = False
        start_bid = None
        premium_abs = None
        premium_pct = None
        leg_age = None
        gate_reason = "ALLOW_NO_RELIABLE_ACTIVE_LEG"
        block = False

        if isinstance(leg, dict):
            leg_side = str(leg.get("side") or "")
            leg_direction = str(leg.get("direction") or "")
            aligned = leg_side == side and leg_direction in ("UP", "DOWN")
            start_bid = _f(leg.get("start_bid"))
            start_ts = _f(leg.get("start_ts"))
            if start_ts is not None:
                leg_age = max(0.0, now - start_ts)

            if not aligned:
                gate_reason = "ALLOW_COUNTER_LEG_OR_REVERSAL"
            elif start_bid is None or start_bid <= 0:
                gate_reason = "ALLOW_NO_VALID_LEG_START_BID"
            else:
                premium_abs = float(ask) - start_bid
                premium_pct = premium_abs / start_bid
                block = (
                    leg_age is not None
                    and leg_age >= PRICE_FRESHNESS_MIN_LEG_AGE_SEC
                    and premium_abs >= PRICE_FRESHNESS_MIN_PREMIUM_ABS
                    and premium_pct >= PRICE_FRESHNESS_MAX_PREMIUM_PCT
                )
                if block:
                    gate_reason = "BLOCK_LATE_LEG_CHASE"
                elif leg_age is not None and leg_age < PRICE_FRESHNESS_MIN_LEG_AGE_SEC:
                    gate_reason = "ALLOW_LEG_STILL_YOUNG"
                else:
                    gate_reason = "ALLOW_LEG_PRICE_FRESH"

        self.price_counter += 1
        cid = f"PF{self.price_counter:05d}"

        info = {
            "candidate_id": cid,
            "ticker": ticker,
            "side": side,
            "ask": float(ask),
            "signal_grade": grade,
            "setup_grade": setup,
            "strategy": strategy,
            "gate_action": "BLOCK" if block else "ALLOW",
            "gate_reason": gate_reason,
            "aligned_with_leg": int(aligned),
            "leg_id": leg.get("leg_id") if isinstance(leg, dict) else "",
            "arc_id": leg.get("arc_id") if isinstance(leg, dict) else snap.get("arc_id"),
            "leg_direction": leg.get("direction") if isinstance(leg, dict) else "",
            "leg_side": leg.get("side") if isinstance(leg, dict) else "",
            "leg_age_sec": leg_age,
            "leg_start_bid": start_bid,
            "leg_max_bid": leg.get("max_bid") if isinstance(leg, dict) else None,
            "leg_min_bid": leg.get("min_bid") if isinstance(leg, dict) else None,
            "premium_abs": premium_abs,
            "premium_pct": premium_pct,
            "premium_pct_threshold": PRICE_FRESHNESS_MAX_PREMIUM_PCT,
            "premium_abs_threshold": PRICE_FRESHNESS_MIN_PREMIUM_ABS,
            "leg_age_threshold_sec": PRICE_FRESHNESS_MIN_LEG_AGE_SEC,
            "chapter_score": chapter_score,
            "chapter_label": chapter_label,
            "chapter_reasons": chapter_reasons,
            "seconds_left": snap.get("seconds_left", signal.get("seconds_to_close")),
            "target_distance": snap.get("target_distance", signal.get("target_distance")),
            "remaining_capacity": snap.get("remaining_capacity"),
            "price_arc_phase": snap.get("price_arc_phase"),
            "battlefield_class": snap.get("battlefield_class"),
            "cage_state": snap.get("cage_state"),
            "dragon_state": snap.get("dragon_state"),
            "note": (
                "V9.5A PAPER authority entry gate; old V9.4M authority is retained as "
                "counterfactual telemetry for blocked entries."
            ),
        }
        _write(PRICE_FRESHNESS_LOG, PRICE_FIELDS, {"event": "ENTRY_GATE", **info})

        if block:
            info.update({
                "ts": now,
                "horizons_done": set(),
                "mfe": -999.0,
                "mae": 999.0,
                "last_bid": None,
                "closed": False,
            })
            self.blocked[cid] = info

        return block, info

    def update_blocked_outcomes(
        self,
        ticker: str,
        yes_ask,
        no_ask,
        now: Optional[float] = None,
    ) -> None:
        now = time.time() if now is None else float(now)
        for cid, cand in list(self.blocked.items()):
            if cand.get("closed"):
                continue

            if cand.get("ticker") != ticker:
                cand["closed"] = True
                self._write_price_outcome("BLOCK_END_CONTRACT", cand, None, now, None)
                continue

            bid = _side_bid(cand["side"], yes_ask, no_ask)
            if bid is None or not cand.get("ask"):
                continue

            roi = (bid - cand["ask"]) / cand["ask"]
            cand["last_bid"] = bid
            cand["mfe"] = max(cand.get("mfe", roi), roi)
            cand["mae"] = min(cand.get("mae", roi), roi)

            age = now - cand["ts"]
            for horizon in BLOCK_OUTCOME_HORIZONS:
                if horizon in cand["horizons_done"] or age < horizon:
                    continue
                cand["horizons_done"].add(horizon)
                self._write_price_outcome(
                    f"BLOCK_OUTCOME_{horizon}S", cand, bid, now, horizon
                )

            if age >= max(BLOCK_OUTCOME_HORIZONS):
                cand["closed"] = True

    def _write_price_outcome(
        self,
        event: str,
        cand: Dict[str, Any],
        bid: Optional[float],
        now: float,
        horizon: Optional[int],
    ) -> None:
        mark_bid = bid if bid is not None else cand.get("last_bid")
        roi = None
        if mark_bid is not None and cand.get("ask"):
            roi = (mark_bid - cand["ask"]) / cand["ask"]
        _write(PRICE_FRESHNESS_LOG, PRICE_FIELDS, {
            "event": event,
            **{
                key: cand.get(key)
                for key in PRICE_FIELDS
                if key not in ("timestamp", "run_id", "session_id", "event")
            },
            "horizon_sec": horizon,
            "current_bid": mark_bid,
            "shadow_roi": roi,
            "shadow_mfe_roi": cand.get("mfe"),
            "shadow_mae_roi": cand.get("mae"),
            "note": "Counterfactual outcome of entry blocked by V9.5A price freshness authority.",
        })

    def apply_active_treasury(self, ticker: str, yes_ask, no_ask) -> int:
        """Exit positions for which V9.4M has already created DEFEND_CANDIDATE."""
        closed = 0
        positions = getattr(core, "paper_positions", {}) or {}

        for side in ("YES", "NO"):
            position = positions.get(side)
            if not isinstance(position, dict) or position.get("ticker") != ticker:
                continue

            tid = _trade_id(position)
            st = m.brain.trade_state.get(tid)
            if not isinstance(st, dict):
                continue

            cid = st.get("defense_id")
            cand = m.brain.treasury_candidates.get(cid) if cid else None
            if not isinstance(cand, dict) or cand.get("closed"):
                continue

            bid = _side_bid(side, yes_ask, no_ask)
            entry = _f(position.get("entry_ask"))
            qty = _i(position.get("qty"), 0)
            cost = _f(position.get("cost"), 0.0) or 0.0
            if bid is None or entry is None or entry <= 0 or qty <= 0:
                continue

            roi = (bid - entry) / entry
            value = qty * bid
            pnl = value - cost

            # Keep base paper telemetry consistent although we exit before the
            # inherited paper_manage() gets its normal turn on this tick.
            position["mfe_pct"] = max(
                _f(position.get("mfe_pct"), 0.0) or 0.0,
                roi * 100.0,
            )
            position["mae_pct"] = min(
                _f(position.get("mae_pct"), 0.0) or 0.0,
                roi * 100.0,
            )

            snap = dict(cand.get("snapshot") or {})
            try:
                integrity, contradiction_points, _why = m.brain._thesis_integrity(side, snap)
            except Exception:
                integrity, contradiction_points = None, None
            holdability = (
                "HIGH_HOLDABILITY"
                if integrity is not None and integrity >= 7
                else "MIXED_HOLDABILITY"
                if integrity is not None and integrity >= 5
                else "LOW_HOLDABILITY"
                if integrity is not None
                else ""
            )
            reason = "V95A_ACTIVE_TREASURY_DEFEND"

            _write(ACTIVE_TREASURY_LOG, TREASURY_FIELDS, {
                "event": "ACTIVE_EXIT",
                "candidate_id": cid,
                "trade_id": tid,
                "ticker": ticker,
                "side": side,
                "qty": qty,
                "entry_ask": entry,
                "exit_bid": bid,
                "exit_roi": roi,
                "exit_pnl": pnl,
                "mfe_roi": st.get("mfe"),
                "giveback_points": max(
                    0.0,
                    (_f(st.get("mfe"), roi) or roi) - roi,
                ),
                "proven_level": st.get("proven"),
                "thesis_integrity": integrity,
                "contradiction_points": contradiction_points,
                "holdability_label": holdability,
                "seconds_left": snap.get("seconds_left"),
                "arc_id": snap.get("arc_id"),
                "arc_direction": snap.get("arc_direction"),
                "price_arc_phase": snap.get("price_arc_phase"),
                "remaining_capacity": snap.get("remaining_capacity"),
                "battlefield_class": snap.get("battlefield_class"),
                "boss_side": snap.get("boss_side"),
                "hand_side": snap.get("hand_side"),
                "cage_state": snap.get("cage_state"),
                "dragon_state": snap.get("dragon_state"),
                "target_distance": snap.get("target_distance"),
                "reason": reason,
                "note": (
                    "V9.5A promoted the first V9.4M DEFEND_CANDIDATE "
                    "to paper-exit authority."
                ),
            })

            if pnl < 0 and position.get("v85_countertrend_entry"):
                try:
                    core.v85_last_failed_countertrend[side] = time.time()
                except Exception:
                    pass

            core.paper_realized_pnl += pnl
            core.log_paper_event("EXIT", position, bid, reason)
            core.record_contract_trade(position, bid, pnl, reason)

            peak_roi = (_f(position.get("mfe_pct"), 0.0) or 0.0) / 100.0
            print(
                f"🏦💰 V9.5A ACTIVE TREASURY EXIT | #{position.get('trade_id')} {side} "
                f"@ {bid:.3f} | peak={peak_roi:.1%} now={roi:+.1%} "
                f"| P&L=${pnl:+.2f} | total=${core.paper_realized_pnl:+.2f}"
            )

            try:
                # Already wrapped by K and M after install_hooks(), so inherited
                # finalizers plus M's REAL_EXIT comparison still fire.
                core.v94b_finalize_trade_shadows(position, bid, roi, reason, pnl)
            except Exception as exc:
                print(f"⚠️ V9.5A treasury finalize error: {exc}")

            core.paper_positions[side] = None
            core.last_paper_exit_time[side] = time.time()
            closed += 1

        return closed


brain = V95AAuthority()
_HOOKS_INSTALLED = False


def install_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return

    # Install the complete V9.4M observer stack first.
    m.install_hooks()
    _HOOKS_INSTALLED = True

    # M tick processing runs first; then V9.5A updates the blocked-entry control.
    original_council = getattr(core, "v94e_kings_council_observer")

    def council_wrapper(ticker, yes_ask, no_ask, close_ts, now=None):
        result = original_council(ticker, yes_ask, no_ask, close_ts, now)
        try:
            brain.update_blocked_outcomes(ticker, yes_ask, no_ask, now)
        except Exception as exc:
            print(f"⚠️ V9.5A blocked-entry outcome error: {exc}")
        return result

    core.v94e_kings_council_observer = council_wrapper

    # Promote price freshness to paper ENTRY authority.
    # original_enter is M's wrapper, so allowed entries retain all M telemetry.
    original_enter = getattr(core, "paper_enter")

    def paper_enter_wrapper(ticker, side, ask, signal):
        try:
            block, info = brain.evaluate_entry(ticker, side, ask, signal or {})
        except Exception as exc:
            # Fail open: an experiment-layer exception must not silently change
            # the inherited paper strategy.
            print(
                f"⚠️ V9.5A price-freshness gate error; "
                f"inherited authority allowed: {exc}"
            )
            return original_enter(ticker, side, ask, signal)

        if block:
            # Preserve M's view of a blocked attempt, especially Second Spear V2
            # if a same-side parent position is already active.
            try:
                ctx = m.brain.before_entry_attempt(ticker, side, ask, signal or {})
                m.brain.after_entry_attempt(ctx, False)
            except Exception as exc:
                print(f"⚠️ V9.5A M-control blocked-attempt logging error: {exc}")

            print(
                f"🚫 V9.5A LATE-LEG CHASE BLOCK | {side} @ {ask:.3f} "
                f"| leg={info.get('leg_id') or '?'} "
                f"age={(_f(info.get('leg_age_sec'), 0.0) or 0.0):.0f}s "
                f"| startBid={(_f(info.get('leg_start_bid'), 0.0) or 0.0):.3f} "
                f"| premium={(_f(info.get('premium_abs'), 0.0) or 0.0):+.3f} "
                f"({(_f(info.get('premium_pct'), 0.0) or 0.0):+.1%}) "
                f"| chapter={info.get('chapter_label')}"
            )
            return False

        return original_enter(ticker, side, ask, signal)

    core.paper_enter = paper_enter_wrapper

    # Promote M Treasury DEFEND_CANDIDATE to paper EXIT authority. M's on_tick
    # runs earlier in the same market update through the Council hook.
    original_manage = getattr(core, "paper_manage")

    def paper_manage_wrapper(ticker, yes_ask, no_ask):
        try:
            brain.apply_active_treasury(ticker, yes_ask, no_ask)
        except Exception as exc:
            print(
                f"⚠️ V9.5A active treasury error; "
                f"inherited manager continues: {exc}"
            )
        return original_manage(ticker, yes_ask, no_ask)

    core.paper_manage = paper_manage_wrapper


async def main() -> None:
    install_hooks()
    print("=" * 104)
    print(f"TACHYOS {VERSION} — PRICE FRESHNESS / ACTIVE TREASURY")
    print(f"RUN ID: {RUN_ID} | SESSION: {SESSION_ID}")
    print("PAPER ONLY | V9.5A HAS LIMITED PAPER AUTHORITY.")
    print("")
    print(
        "🚫 ACTIVE ENTRY GATE: aligned leg chase blocked at age >=90s "
        "when premium >=25% AND >=9c"
    )
    print(
        "🏦 ACTIVE TREASURY: V9.4M DEFEND_CANDIDATE now exits "
        "the paper position"
    )
    print(
        "🧪 CONTROL: blocked entries are tracked counterfactually "
        "at 15/30/60/120s"
    )
    print("🩺 Medic remains shadow | 🗡️ Second Spear V2 remains shadow")
    print("🏔️ Twin Gate remains shadow | 🔥 Elasticity Lite remains shadow")
    print("")
    print(
        "UNCHANGED: sizing, legacy emergency stops, Core, Early Impulse, "
        "and Handoff logic."
    )
    print("=" * 104)
    await core.main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTachyos V9.5A stopped by operator (Ctrl+C).")
