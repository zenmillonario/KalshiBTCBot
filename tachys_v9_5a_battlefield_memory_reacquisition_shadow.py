from __future__ import annotations

import asyncio
import csv
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import tachys_v9_5a_entry_authority_router_shadow as r

core = r.core
m = r.m
j = r.j

VERSION = "V9.5A-RS2"
LOG_FILE = "tachys_battlefield_thesis_memory_v9_5a_rs2.csv"

FIELDS = [
    "timestamp","event","version","ticker","side",
    "memory_id","memory_age_sec","exit_trade_id","exit_reason","exit_pnl",
    "exit_arc_id","exit_arc_direction","exit_price_arc_phase",
    "exit_battlefield_class","exit_churn_type","exit_dragon_state",
    "exit_target_distance","exit_pt_state",
    "proposal_ask","proposal_result","proposal_arc_id","proposal_arc_direction",
    "arc_relation","price_arc_phase","battlefield_class","churn_type",
    "dragon_state","boss_side","hand_side","remaining_capacity",
    "seconds_left","target_distance","pt_state","active_same_side_position",
    "active_opposite_position","note",
]


def _utc(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else float(ts)
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _f(v: Any, default=None):
    try:
        if v in (None, ""):
            return default
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _write(row: Dict[str, Any]) -> None:
    payload = {"timestamp": row.get("timestamp") or _utc(), "version": VERSION, **row}
    new = (not os.path.exists(LOG_FILE)) or os.path.getsize(LOG_FILE) == 0
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: payload.get(k, "") for k in FIELDS})


def _pt_state(side: str, target_distance: Any) -> str:
    td = _f(target_distance)
    if td is None:
        return "PT_UNKNOWN"
    if td == 0:
        return "PT_TOUCH"
    if side == "YES":
        return "PT_OWNED" if td > 0 else "PT_ATTACK"
    if side == "NO":
        return "PT_OWNED" if td < 0 else "PT_ATTACK"
    return "PT_UNKNOWN"


def _snapshot(ticker: str, side: str = "", ask: Optional[float] = None) -> Dict[str, Any]:
    try:
        if side == "YES":
            return dict(m.brain.snapshot(ticker, yes_ask=ask, now=time.time()) or {})
        if side == "NO":
            return dict(m.brain.snapshot(ticker, no_ask=ask, now=time.time()) or {})
        return dict(m.brain.snapshot(ticker, now=time.time()) or {})
    except Exception:
        return dict(getattr(j.brain, "last_snapshot", {}) or {})


def _positions(ticker: str, side: str) -> Tuple[int, int]:
    pos = getattr(core, "paper_positions", {}) or {}
    same = pos.get(side) if isinstance(pos, dict) else None
    opp_side = "NO" if side == "YES" else "YES"
    opp = pos.get(opp_side) if isinstance(pos, dict) else None
    same_on_ticker = int(isinstance(same, dict) and same.get("ticker") == ticker)
    opp_on_ticker = int(isinstance(opp, dict) and opp.get("ticker") == ticker)
    return same_on_ticker, opp_on_ticker


class BattlefieldMemoryShadow:
    """
    Prospective research-only separation of POSITION state from BATTLEFIELD THESIS state.

    A losing same-contract position may die while a thesis memory remains WATCHING.
    The memory has ZERO paper authority. It can only log later same-side proposals,
    whether they are on the same arc or a new arc, and whether PT is already owned
    or is still being attacked.
    """

    def __init__(self) -> None:
        self.counter = 0
        self.memory: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def arm_from_exit(
        self,
        position: Dict[str, Any],
        exit_bid: Optional[float],
        reason: str,
        now: float,
    ) -> None:
        ticker = str(position.get("ticker") or "")
        side = str(position.get("side") or "")
        if not ticker or side not in ("YES", "NO") or exit_bid is None:
            return

        qty = int(_f(position.get("qty"), 0) or 0)
        cost = _f(position.get("cost"), 0.0) or 0.0
        pnl = qty * float(exit_bid) - cost

        # RS2 studies loss recovery inside the same contract. Contract-close loss
        # has no same-contract battlefield left to reacquire.
        if pnl >= 0 or str(reason or "") == "CONTRACT_CLOSE":
            if pnl >= 0:
                prior = self.memory.pop((ticker, side), None)
                if prior:
                    snap = _snapshot(ticker, side)
                    _write({
                        "event": "THESIS_MEMORY_RESOLVED_PROFIT",
                        "ticker": ticker,
                        "side": side,
                        **self._memory_fields(prior, now),
                        **self._snapshot_fields(ticker, side, snap),
                        "note": "A profitable exit resolves this same-contract thesis memory; shadow only.",
                    })
            return

        snap = _snapshot(ticker, side)
        self.counter += 1
        memory_id = f"RSM{self.counter:05d}"
        st = {
            "memory_id": memory_id,
            "armed_ts": now,
            "ticker": ticker,
            "side": side,
            "exit_trade_id": position.get("trade_id"),
            "exit_reason": reason,
            "exit_pnl": pnl,
            "exit_arc_id": snap.get("arc_id"),
            "exit_arc_direction": snap.get("arc_direction"),
            "exit_price_arc_phase": snap.get("price_arc_phase"),
            "exit_battlefield_class": snap.get("battlefield_class"),
            "exit_churn_type": (getattr(core, "v94g_latest_border", {}) or {}).get("churn_type"),
            "exit_dragon_state": snap.get("dragon_state"),
            "exit_target_distance": snap.get("target_distance", position.get("target_distance")),
        }
        st["exit_pt_state"] = _pt_state(side, st["exit_target_distance"])
        self.memory[(ticker, side)] = st

        _write({
            "event": "THESIS_MEMORY_ARMED",
            "ticker": ticker,
            "side": side,
            **self._memory_fields(st, now),
            **self._snapshot_fields(ticker, side, snap),
            "note": (
                "Losing position died; same-contract battlefield thesis remains WATCHING in RS2 shadow. "
                "No entry, exit, block, resize, or hold authority."
            ),
        })

    def _memory_fields(self, st: Dict[str, Any], now: float) -> Dict[str, Any]:
        return {
            "memory_id": st.get("memory_id"),
            "memory_age_sec": round(max(0.0, now - float(st.get("armed_ts") or now)), 3),
            "exit_trade_id": st.get("exit_trade_id"),
            "exit_reason": st.get("exit_reason"),
            "exit_pnl": st.get("exit_pnl"),
            "exit_arc_id": st.get("exit_arc_id"),
            "exit_arc_direction": st.get("exit_arc_direction"),
            "exit_price_arc_phase": st.get("exit_price_arc_phase"),
            "exit_battlefield_class": st.get("exit_battlefield_class"),
            "exit_churn_type": st.get("exit_churn_type"),
            "exit_dragon_state": st.get("exit_dragon_state"),
            "exit_target_distance": st.get("exit_target_distance"),
            "exit_pt_state": st.get("exit_pt_state"),
        }

    def _snapshot_fields(
        self,
        ticker: str,
        side: str,
        snap: Dict[str, Any],
        ask: Optional[float] = None,
    ) -> Dict[str, Any]:
        same, opp = _positions(ticker, side)
        td = snap.get("target_distance")
        return {
            "proposal_ask": ask if ask is not None else "",
            "proposal_arc_id": snap.get("arc_id"),
            "proposal_arc_direction": snap.get("arc_direction"),
            "price_arc_phase": snap.get("price_arc_phase"),
            "battlefield_class": snap.get("battlefield_class"),
            "churn_type": (getattr(core, "v94g_latest_border", {}) or {}).get("churn_type"),
            "dragon_state": snap.get("dragon_state"),
            "boss_side": snap.get("boss_side"),
            "hand_side": snap.get("hand_side"),
            "remaining_capacity": snap.get("remaining_capacity"),
            "seconds_left": snap.get("seconds_left"),
            "target_distance": td,
            "pt_state": _pt_state(side, td),
            "active_same_side_position": same,
            "active_opposite_position": opp,
        }

    def observe_proposal(
        self,
        ticker: str,
        side: str,
        ask: float,
        signal: Dict[str, Any],
        original_enter,
    ):
        now = time.time()
        st = self.memory.get((ticker, side))
        opp_side = "NO" if side == "YES" else "YES"
        opp_mem = self.memory.get((ticker, opp_side))
        snap = _snapshot(ticker, side, ask)

        if st:
            proposal_arc = str(snap.get("arc_id") or "")
            exit_arc = str(st.get("exit_arc_id") or "")
            relation = (
                "NEW_ARC"
                if proposal_arc and exit_arc and proposal_arc != exit_arc
                else "SAME_ARC"
                if proposal_arc and exit_arc and proposal_arc == exit_arc
                else "ARC_UNKNOWN"
            )
            _write({
                "event": "REACQUISITION_PROPOSAL_SHADOW",
                "ticker": ticker,
                "side": side,
                **self._memory_fields(st, now),
                **self._snapshot_fields(ticker, side, snap, ask),
                "arc_relation": relation,
                "note": (
                    "Same-side proposal after a losing exit. RS2 records arc regeneration and PT battlefield state only; "
                    "it does not alter inherited V9.5A authority."
                ),
            })
        elif opp_mem:
            _write({
                "event": "OPPOSITE_CHALLENGE_SHADOW",
                "ticker": ticker,
                "side": side,
                **self._memory_fields(opp_mem, now),
                **self._snapshot_fields(ticker, side, snap, ask),
                "arc_relation": "OPPOSITE_SIDE_CHALLENGE",
                "note": "Opposite-side proposal challenged an armed thesis memory; shadow only.",
            })

        result = original_enter(ticker, side, ask, signal)

        if st:
            post = _snapshot(ticker, side, ask)
            proposal_arc = str(post.get("arc_id") or "")
            exit_arc = str(st.get("exit_arc_id") or "")
            relation = (
                "NEW_ARC"
                if proposal_arc and exit_arc and proposal_arc != exit_arc
                else "SAME_ARC"
                if proposal_arc and exit_arc and proposal_arc == exit_arc
                else "ARC_UNKNOWN"
            )
            _write({
                "event": "REACQUISITION_RESULT_SHADOW",
                "ticker": ticker,
                "side": side,
                **self._memory_fields(st, time.time()),
                **self._snapshot_fields(ticker, side, post, ask),
                "arc_relation": relation,
                "proposal_result": int(bool(result)),
                "note": "Inherited paper_enter result observed after the reacquisition proposal; RS2 did not influence it.",
            })

        return result


brain = BattlefieldMemoryShadow()
_HOOKS_INSTALLED = False


def install_rs2_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    _HOOKS_INSTALLED = True

    # Observe every actual EXIT through the frozen core logger. The original logger
    # remains authoritative and is always called.
    original_log = getattr(core, "log_paper_event")

    def log_wrapper(event, position, exit_bid=None, reason=""):
        result = original_log(event, position, exit_bid, reason)
        if str(event or "") == "EXIT":
            try:
                brain.arm_from_exit(position, exit_bid, str(reason or ""), time.time())
            except Exception as exc:
                print(f"⚠️ RS2 exit-memory shadow error: {exc}")
        return result

    core.log_paper_event = log_wrapper

    # Observe proposals after the complete inherited V9.5A + RS1 stack is installed.
    original_enter = getattr(core, "paper_enter")

    def paper_enter_wrapper(ticker, side, ask, signal):
        try:
            return brain.observe_proposal(
                ticker, side, float(ask), signal or {}, original_enter
            )
        except Exception as exc:
            # Shadow failure must never change paper behavior.
            print(f"⚠️ RS2 reacquisition shadow error: {exc}")
            return original_enter(ticker, side, ask, signal)

    core.paper_enter = paper_enter_wrapper


async def main() -> None:
    # Freeze V9.5A authority, attach RS1 observation, then attach RS2 outside both.
    r.a.install_hooks()
    r.install_router_shadow_hooks()
    install_rs2_hooks()

    print("=" * 112)
    print(f"TACHYOS {VERSION} — BATTLEFIELD THESIS MEMORY / REACQUISITION SHADOW")
    print("PAPER ONLY | V9.5A AUTHORITY IS UNCHANGED.")
    print("")
    print("RS2 separates POSITION state from BATTLEFIELD THESIS state:")
    print("LOSING EXIT -> THESIS MEMORY WATCHING -> SAME/NEW ARC PROPOSAL -> PT OWNED/ATTACK -> inherited result")
    print("")
    print("RS2 cannot place, block, resize, flip, close, hold, or manage any paper trade.")
    print(f"LOG: {LOG_FILE}")
    print("=" * 112)

    await core.main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTachyos V9.5A-RS2 stopped by operator (Ctrl+C).")
