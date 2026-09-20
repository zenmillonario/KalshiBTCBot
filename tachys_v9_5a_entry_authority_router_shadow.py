from __future__ import annotations

import asyncio
import csv
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import tachys_v9_5a_price_freshness_active_treasury as a

core = a.core
m = a.m
j = m.j

VERSION = "V9.5A-RS1"
ROUTER_LOG = "tachys_entry_authority_router_shadow_v9_5a_rs1.csv"

# Research-only trajectory expiration from the replay work.
# This has ZERO paper authority in RS1.
RESEARCH_EXPIRY_SEC = 9.0

# Existing value bounds already present in the frozen ancestry.
EXISTING_MIN_ACCEPTED_ASK = 0.20
EXISTING_MAX_ACCEPTED_ASK = 0.80

FIELDS = [
    "timestamp","event","version","ticker","side","source",
    "recognition_epoch_id","recognition_source","recognition_ts",
    "recognition_age_sec","recognition_first_ask","expired9",
    "prior_state","transfer_id","transfer_relation","transfer_ts",
    "transfer_age_sec","transfer_ask","accepted_20_80",
    "acceptance_delay_sec","proposal_delay_sec","proposal_ask",
    "proposal_strategy","proposal_trade_intent","proposal_signal_grade",
    "proposal_setup_grade","proposal_would_reach_v95a",
    "price_arc_phase","arc_id","arc_direction","arc_age_sec",
    "remaining_capacity","battlefield_class","zoom_mode",
    "boss_side","hand_side","territory_state","churn_type",
    "cage_state","dragon_state","seconds_left","target_distance",
    "active_same_side_position","active_opposite_position",
    "note",
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
    new = (not os.path.exists(ROUTER_LOG)) or os.path.getsize(ROUTER_LOG) == 0
    with open(ROUTER_LOG, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: payload.get(k, "") for k in FIELDS})


def _side_from_regime(v: Any) -> str:
    s = str(v or "").upper()
    if s.startswith("UP_"):
        return "YES"
    if s.startswith("DOWN_"):
        return "NO"
    return ""


def _snapshot(ticker: str, yes_ask=None, no_ask=None, close_ts=None, now=None) -> Dict[str, Any]:
    now = time.time() if now is None else float(now)
    try:
        return dict(m.brain.snapshot(ticker, yes_ask, no_ask, close_ts, now) or {})
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


class RouterShadow:
    def __init__(self) -> None:
        self.recognition: Dict[Tuple[str,str], Dict[str,Any]] = {}
        self.transfer: Dict[Tuple[str,str], Dict[str,Any]] = {}
        self.transfer_counter = 0
        self.last_hand_side: Dict[str,str] = {}
        self.boundary_active: Dict[str, Optional[Tuple[Any,...]]] = {}

    def _state_for_side(self, ticker: str, side: str, now: float) -> Dict[str,Any]:
        rec = self.recognition.get((ticker, side))
        if not rec:
            return {
                "recognition_epoch_id": "",
                "recognition_source": "",
                "recognition_ts": "",
                "recognition_age_sec": "",
                "recognition_first_ask": "",
                "expired9": 0,
                "prior_state": "NO_DIRECTIONAL_ANCESTRY",
            }
        age = max(0.0, now - float(rec["ts"]))
        expired = int(age >= RESEARCH_EXPIRY_SEC)
        return {
            "recognition_epoch_id": rec.get("epoch_id",""),
            "recognition_source": rec.get("source",""),
            "recognition_ts": _utc(rec["ts"]),
            "recognition_age_sec": round(age, 3),
            "recognition_first_ask": rec.get("ask",""),
            "expired9": expired,
            "prior_state": "WINDOW_EXPIRED" if expired else "WINDOW_YOUNG",
        }

    def _common(self, ticker: str, side: str, snap: Dict[str,Any], now: float) -> Dict[str,Any]:
        same, opp = _positions(ticker, side)
        return {
            **self._state_for_side(ticker, side, now),
            "price_arc_phase": snap.get("price_arc_phase"),
            "arc_id": snap.get("arc_id"),
            "arc_direction": snap.get("arc_direction"),
            "arc_age_sec": snap.get("arc_age_sec"),
            "remaining_capacity": snap.get("remaining_capacity"),
            "battlefield_class": snap.get("battlefield_class"),
            "zoom_mode": snap.get("zoom_mode"),
            "boss_side": snap.get("boss_side"),
            "hand_side": snap.get("hand_side"),
            "territory_state": (getattr(core, "v94g_latest_border", {}) or {}).get("territory_state"),
            "churn_type": (getattr(core, "v94g_latest_border", {}) or {}).get("churn_type"),
            "cage_state": snap.get("cage_state"),
            "dragon_state": snap.get("dragon_state"),
            "seconds_left": snap.get("seconds_left"),
            "target_distance": snap.get("target_distance"),
            "active_same_side_position": same,
            "active_opposite_position": opp,
        }

    def note_recognition(self, ticker: str, side: str, ask: float, source: str, now: float) -> None:
        mem = (getattr(core, "v94c_preentry_memory", {}) or {}).get((ticker, side))
        epoch_id = mem.get("epoch_id") if isinstance(mem, dict) else ""
        key = (ticker, side)
        prior = self.recognition.get(key)

        is_new_epoch = prior is None or (epoch_id and epoch_id != prior.get("epoch_id"))
        if not is_new_epoch:
            return

        first_ts = _f(mem.get("first_ts")) if isinstance(mem, dict) else None
        first_ask = _f(mem.get("first_directional_ask")) if isinstance(mem, dict) else None
        ts = first_ts if first_ts is not None else now
        px = first_ask if first_ask is not None else ask

        rec = {
            "ts": ts,
            "ask": px,
            "source": source,
            "epoch_id": epoch_id or f"RSREC:{ticker}:{side}:{ts:.3f}",
            "expiry_logged": False,
        }
        self.recognition[key] = rec

        snap = _snapshot(ticker, yes_ask=ask if side=="YES" else None,
                         no_ask=ask if side=="NO" else None, now=now)
        _write({
            "event": "FIRST_DIRECTIONAL_SHADOW",
            "ticker": ticker,
            "side": side,
            "source": source,
            **self._common(ticker, side, snap, now),
            "note": "Prospective recognition clock only; no paper authority.",
        })

    def update_expiry(self, ticker: str, now: float, yes_ask=None, no_ask=None, close_ts=None) -> None:
        for side in ("YES","NO"):
            rec = self.recognition.get((ticker, side))
            if not rec or rec.get("expiry_logged"):
                continue
            age = now - float(rec["ts"])
            if age < RESEARCH_EXPIRY_SEC:
                continue
            rec["expiry_logged"] = True
            snap = _snapshot(ticker, yes_ask, no_ask, close_ts, now)
            _write({
                "event": "WINDOW_EXPIRED_SHADOW",
                "ticker": ticker,
                "side": side,
                "source": "TRAJECTORY_CLOCK",
                **self._common(ticker, side, snap, now),
                "note": "9s replay boundary observed prospectively; no entry is blocked.",
            })

    def note_transfer(self, ticker: str, side: str, source: str, ask: Optional[float],
                      snap: Dict[str,Any], now: float, detail: str="") -> None:
        if side not in ("YES","NO"):
            return

        self.transfer_counter += 1
        transfer_id = f"RST{self.transfer_counter:05d}"
        rec = self.recognition.get((ticker, side))
        prior_age = (now - float(rec["ts"])) if rec else None

        # Any prior transfer on either side of this ticker is superseded.
        for k in list(self.transfer):
            if k[0] == ticker:
                self.transfer.pop(k, None)

        relation = "NO_PRIOR_DIRECTIONAL"
        if rec:
            relation = "EXPIRED_REVALIDATION" if prior_age is not None and prior_age >= RESEARCH_EXPIRY_SEC else "YOUNG_RECOGNITION_TRANSFER"

        accepted = int(
            ask is not None
            and EXISTING_MIN_ACCEPTED_ASK <= ask <= EXISTING_MAX_ACCEPTED_ASK
        )

        st = {
            "id": transfer_id,
            "ticker": ticker,
            "side": side,
            "source": source,
            "ts": now,
            "ask": ask,
            "accepted_ts": now if accepted else None,
            "accepted_ask": ask if accepted else None,
            "relation": relation,
            "recognition_age_at_transfer": prior_age,
        }
        self.transfer[(ticker, side)] = st

        _write({
            "event": "TRANSFER_ARMED_SHADOW",
            "ticker": ticker,
            "side": side,
            "source": source,
            "transfer_id": transfer_id,
            "transfer_relation": relation,
            "transfer_ts": _utc(now),
            "transfer_age_sec": round(prior_age,3) if prior_age is not None else "",
            "transfer_ask": ask if ask is not None else "",
            "accepted_20_80": accepted,
            "acceptance_delay_sec": 0.0 if accepted else "",
            **self._common(ticker, side, snap, now),
            "note": detail or "Structural transfer arms research epoch only.",
        })

        if accepted:
            _write({
                "event": "TRANSFER_ACCEPTED_SHADOW",
                "ticker": ticker,
                "side": side,
                "source": source,
                "transfer_id": transfer_id,
                "transfer_relation": relation,
                "transfer_ts": _utc(now),
                "transfer_age_sec": round(prior_age,3) if prior_age is not None else "",
                "transfer_ask": ask,
                "accepted_20_80": 1,
                "acceptance_delay_sec": 0.0,
                **self._common(ticker, side, snap, now),
                "note": "Existing 20c-80c value band satisfied at transfer; still shadow only.",
            })

    def update_acceptance(self, ticker: str, yes_ask, no_ask, close_ts, now: float) -> None:
        for side in ("YES","NO"):
            st = self.transfer.get((ticker, side))
            if not st or st.get("accepted_ts") is not None:
                continue
            ask = _f(yes_ask if side=="YES" else no_ask)
            if ask is None or not (EXISTING_MIN_ACCEPTED_ASK <= ask <= EXISTING_MAX_ACCEPTED_ASK):
                continue
            st["accepted_ts"] = now
            st["accepted_ask"] = ask
            snap = _snapshot(ticker, yes_ask, no_ask, close_ts, now)
            _write({
                "event": "TRANSFER_ACCEPTED_SHADOW",
                "ticker": ticker,
                "side": side,
                "source": st.get("source"),
                "transfer_id": st.get("id"),
                "transfer_relation": st.get("relation"),
                "transfer_ts": _utc(st["ts"]),
                "transfer_age_sec": round(st.get("recognition_age_at_transfer"),3)
                    if st.get("recognition_age_at_transfer") is not None else "",
                "transfer_ask": st.get("ask"),
                "accepted_20_80": 1,
                "acceptance_delay_sec": round(now - st["ts"],3),
                **self._common(ticker, side, snap, now),
                "note": "First post-transfer entry into existing 20c-80c band; shadow only.",
            })

    def note_proposal(self, ticker: str, side: str, ask: float, signal: Dict[str,Any], now: float) -> None:
        st = self.transfer.get((ticker, side))
        snap = _snapshot(ticker,
                         yes_ask=ask if side=="YES" else None,
                         no_ask=ask if side=="NO" else None,
                         close_ts=(signal or {}).get("close_ts"),
                         now=now)
        accepted = int(EXISTING_MIN_ACCEPTED_ASK <= float(ask) <= EXISTING_MAX_ACCEPTED_ASK)

        _write({
            "event": "LEGACY_PROPOSAL_SHADOW",
            "ticker": ticker,
            "side": side,
            "source": "LEGACY_PAPER_ENTER",
            "transfer_id": st.get("id") if st else "",
            "transfer_relation": st.get("relation") if st else "NO_ACTIVE_TRANSFER_EPOCH",
            "transfer_ts": _utc(st["ts"]) if st else "",
            "transfer_age_sec": round(st.get("recognition_age_at_transfer"),3)
                if st and st.get("recognition_age_at_transfer") is not None else "",
            "transfer_ask": st.get("ask") if st else "",
            "accepted_20_80": accepted,
            "acceptance_delay_sec": (
                round((st.get("accepted_ts") or now) - st["ts"],3)
                if st and (st.get("accepted_ts") is not None or accepted) else ""
            ),
            "proposal_delay_sec": round(now - st["ts"],3) if st else "",
            "proposal_ask": ask,
            "proposal_strategy": (signal or {}).get("strategy"),
            "proposal_trade_intent": (signal or {}).get("trade_intent"),
            "proposal_signal_grade": (signal or {}).get("signal_grade"),
            "proposal_setup_grade": (signal or {}).get("setup_grade"),
            "proposal_would_reach_v95a": 1,
            **self._common(ticker, side, snap, now),
            "note": "Observed final legacy proposal before V9.5A inherited decision; shadow does not alter it.",
        })

    def on_tick(self, ticker: str, yes_ask, no_ask, close_ts, now: float) -> None:
        self.update_expiry(ticker, now, yes_ask, no_ask, close_ts)

        snap = _snapshot(ticker, yes_ask, no_ask, close_ts, now)

        # True Hand authority change, prospectively detected from stable authority.
        hand = getattr(core, "v94e_latest_regime", {}) or {}
        cur_hand = str(hand.get("authority_side") or "")
        prev_hand = self.last_hand_side.get(ticker, "")
        if cur_hand in ("YES","NO") and prev_hand in ("YES","NO") and cur_hand != prev_hand:
            ask = _f(yes_ask if cur_hand=="YES" else no_ask)
            self.note_transfer(
                ticker, cur_hand, "HAND_AUTHORITY_TRANSFER",
                ask, snap, now,
                f"{prev_hand}->{cur_hand};{hand.get('transition_event') or ''}",
            )
        if cur_hand in ("YES","NO"):
            self.last_hand_side[ticker] = cur_hand

        # Actual Boundary release transition only; suppress repeated state rows.
        border = getattr(core, "v94g_latest_border", {}) or {}
        if (
            str(border.get("territory_state") or "") == "BOUNDARY_RELEASE"
            and str(border.get("transition_reason") or "") == "CHURN_RELEASED"
            and str(border.get("release_side") or "") in ("YES","NO")
        ):
            bside = str(border.get("release_side"))
            sig = (
                bside,
                border.get("episode_id"),
                border.get("location"),
                border.get("seconds_since_prior_churn"),
            )
            if self.boundary_active.get(ticker) != sig:
                self.boundary_active[ticker] = sig
                ask = _f(yes_ask if bside=="YES" else no_ask)
                self.note_transfer(
                    ticker, bside, "BOUNDARY_RELEASE",
                    ask, snap, now,
                    f"CHURN_RELEASED;{border.get('churn_type') or 'NONE'};{border.get('location') or ''}",
                )
        else:
            self.boundary_active[ticker] = None

        self.update_acceptance(ticker, yes_ask, no_ask, close_ts, now)


brain = RouterShadow()
_HOOKS_INSTALLED = False


def install_router_shadow_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    _HOOKS_INSTALLED = True

    # Wrap the existing pre-entry memory writer so the earliest current-epoch
    # directional recognition can be clocked prospectively.
    original_note = getattr(core, "v94c_note_preentry_candidate")
    def preentry_wrapper(ticker, side, ask, source, structurally_valid=None, now=None):
        ts = time.time() if now is None else float(now)
        result = original_note(ticker, side, ask, source, structurally_valid, now)
        try:
            brain.note_recognition(ticker, side, float(ask), str(source or ""), ts)
        except Exception as exc:
            print(f"⚠️ RS1 recognition shadow error: {exc}")
        return result
    core.v94c_note_preentry_candidate = preentry_wrapper

    # Tick hook runs after the complete inherited V9.5A/M/J/K/I observer stack.
    original_council = getattr(core, "v94e_kings_council_observer")
    def council_wrapper(ticker, yes_ask, no_ask, close_ts, now=None):
        result = original_council(ticker, yes_ask, no_ask, close_ts, now)
        ts = time.time() if now is None else float(now)
        try:
            brain.on_tick(ticker, yes_ask, no_ask, close_ts, ts)
        except Exception as exc:
            print(f"⚠️ RS1 tick shadow error: {exc}")
        return result
    core.v94e_kings_council_observer = council_wrapper

    # Final proposal observation. This wraps V9.5A's actual paper-entry doorway
    # but ALWAYS returns its inherited result unchanged.
    original_enter = getattr(core, "paper_enter")
    def paper_enter_wrapper(ticker, side, ask, signal):
        try:
            brain.note_proposal(ticker, side, float(ask), signal or {}, time.time())
        except Exception as exc:
            print(f"⚠️ RS1 proposal shadow error: {exc}")
        return original_enter(ticker, side, ask, signal)
    core.paper_enter = paper_enter_wrapper


async def main() -> None:
    # Freeze inherited V9.5A authority exactly as-is, then attach RS1 outside it.
    a.install_hooks()
    install_router_shadow_hooks()

    print("=" * 108)
    print(f"TACHYOS {VERSION} — ENTRY AUTHORITY ROUTER PROSPECTIVE SHADOW")
    print("PAPER ONLY | V9.5A AUTHORITY IS UNCHANGED.")
    print("RS1 OBSERVES: FIRST_DIRECTIONAL CLOCK -> 9s EXPIRED -> HAND/BOUNDARY TRANSFER ->")
    print("20c-80c MARKET ACCEPTANCE -> LEGACY PROPOSAL HANDSHAKE.")
    print("RS1 cannot place, block, resize, flip, close, or manage any paper trade.")
    print(f"LOG: {ROUTER_LOG}")
    print("=" * 108)

    await core.main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTachyos V9.5A-RS1 stopped by operator (Ctrl+C).")
