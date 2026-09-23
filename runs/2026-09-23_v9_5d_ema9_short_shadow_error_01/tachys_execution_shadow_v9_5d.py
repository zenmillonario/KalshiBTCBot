"""
TACHYOS V9.5D — EXECUTION REALITY SHADOW
========================================

PAPER / SHADOW ONLY. ZERO trading authority.

Purpose:
- Keep Tachyos' paper decision exactly unchanged.
- Observe what each paper entry/exit might have looked like as an immediately
  executable Kalshi taker order.
- Reprice the same decision at 0 / 250 / 500 / 1000 ms after the paper action.
- Walk the locally maintained Level-2 book to estimate partial fills and VWAP.
- Apply a configurable estimate of Kalshi general taker fees.
- Produce a fee/slippage/depth-adjusted "simulated live" P/L for forensic work.

This layer NEVER places, blocks, resizes, cancels, flips, or exits a trade.
"""

from __future__ import annotations

import csv
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


VERSION = "V9.5D-EXECUTION-SHADOW"
LATENCY_HORIZONS_MS = (0, 250, 500, 1000)
PRIMARY_LATENCY_MS = 500

# Current general event-contract taker formula at implementation time:
# fee ~= 0.07 * multiplier * contracts * P * (1-P)
# We round UP to the next cent as a conservative estimate.
# Keep these parameters isolated because Kalshi can change fees or apply
# series-specific multipliers.
TAKER_FEE_RATE = 0.07
TAKER_MULTIPLIER = 1.0
FEE_ROUND_TO_CENT = True

QUOTE_LOG = "tachys_execution_shadow_quotes_v9_5d.csv"
TRADE_LOG = "tachys_execution_shadow_trades_v9_5d.csv"

QUOTE_FIELDS = [
    "timestamp","run_id","session_id","version","event","trade_id","ticker","side",
    "action","horizon_ms","observed_age_ms","paper_price","qty","top_price","top_size",
    "filled_qty","fill_ratio","vwap","worst_price","levels_used","full_fill",
    "book_source","estimated_fee","note"
]

TRADE_FIELDS = [
    "timestamp","run_id","session_id","version","event","trade_id","ticker","side",
    "horizon_ms","primary_scenario","paper_qty","paper_entry","paper_exit",
    "paper_gross_pnl","entry_fill_qty","exit_fill_qty","live_qty",
    "entry_fill_ratio","exit_fill_ratio","live_entry_vwap","live_exit_vwap",
    "entry_fee","exit_fee","live_gross_pnl","live_net_pnl",
    "friction_vs_paper","live_minus_paper","note"
]


def _utc(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else float(ts)
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _f(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if v is None or v == "":
            return default
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _write(path: str, fields: List[str], row: Dict[str, Any],
           run_id: str, session_id: str) -> None:
    payload = {
        "timestamp": row.get("timestamp", _utc()),
        "run_id": run_id,
        "session_id": session_id,
        "version": VERSION,
        **row,
    }
    new_file = (not os.path.exists(path)) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new_file:
            w.writeheader()
        w.writerow({k: payload.get(k, "") for k in fields})


def _opposite(side: str) -> str:
    return "NO" if side == "YES" else "YES" if side == "NO" else "NONE"


def _side_bid(side: str, yes_ask, no_ask) -> Optional[float]:
    if side == "YES":
        v = _f(no_ask)
        return None if v is None else max(0.0, min(1.0, 1.0 - v))
    if side == "NO":
        v = _f(yes_ask)
        return None if v is None else max(0.0, min(1.0, 1.0 - v))
    return None


def _side_ask(side: str, yes_ask, no_ask) -> Optional[float]:
    return _f(yes_ask if side == "YES" else no_ask if side == "NO" else None)


def _ceil_cent(v: float) -> float:
    return math.ceil(max(0.0, v) * 100.0 - 1e-12) / 100.0


def estimated_taker_fee(qty: float, price: Optional[float]) -> float:
    p = _f(price)
    q = max(0.0, _f(qty, 0.0) or 0.0)
    if p is None or q <= 0:
        return 0.0
    p = max(0.0, min(1.0, p))
    raw = TAKER_MULTIPLIER * TAKER_FEE_RATE * q * p * (1.0 - p)
    return _ceil_cent(raw) if FEE_ROUND_TO_CENT else raw


class ExecutionShadow:
    def __init__(self, core, run_id: str, session_id: str) -> None:
        self.core = core
        self.run_id = run_id
        self.session_id = session_id
        self.trades: Dict[str, Dict[str, Any]] = {}
        self.last_yes_ask: Optional[float] = None
        self.last_no_ask: Optional[float] = None

    # ------------------------------------------------------------------
    # BOOK / FILL MODEL
    # ------------------------------------------------------------------

    def _native_book(self, side: str) -> Dict[float, float]:
        book = getattr(self.core, "kalshi_book", {}) or {}
        raw = book.get(side.lower(), {}) if isinstance(book, dict) else {}
        if not isinstance(raw, dict):
            return {}
        out: Dict[float, float] = {}
        for p, q in raw.items():
            pf, qf = _f(p), _f(q)
            if pf is not None and qf is not None and qf > 0:
                out[round(pf, 4)] = qf
        return out

    def _levels(self, side: str, action: str,
                yes_ask=None, no_ask=None) -> Tuple[List[Tuple[float, float]], str]:
        """
        Kalshi observer book stores native YES and NO bids.

        BUY YES asks = 1 - NO bids
        BUY NO  asks = 1 - YES bids
        SELL YES bids = YES bids
        SELL NO  bids = NO bids
        """
        action = action.upper()
        if action == "BUY":
            opp_book = self._native_book(_opposite(side))
            levels = [
                (max(0.0, min(1.0, 1.0 - p)), q)
                for p, q in opp_book.items()
            ]
            levels.sort(key=lambda x: x[0])
            if levels:
                return levels, "L2_COMPLEMENT_ASKS"
            fallback = _side_ask(side, yes_ask, no_ask)
        else:
            same_book = self._native_book(side)
            levels = [(p, q) for p, q in same_book.items()]
            levels.sort(key=lambda x: x[0], reverse=True)
            if levels:
                return levels, "L2_NATIVE_BIDS"
            fallback = _side_bid(side, yes_ask, no_ask)

        if fallback is not None:
            # Fallback has no trustworthy displayed depth. We can record the top
            # quote, but must not pretend the full requested quantity is fillable.
            return [(fallback, 0.0)], "TOP_ONLY_DEPTH_UNKNOWN"
        return [], "NO_BOOK"

    def _walk(self, side: str, action: str, qty: int,
              yes_ask=None, no_ask=None) -> Dict[str, Any]:
        levels, source = self._levels(side, action, yes_ask, no_ask)
        qty = max(0, int(qty or 0))
        if not levels or qty <= 0:
            return {
                "top_price": levels[0][0] if levels else None,
                "top_size": levels[0][1] if levels else None,
                "filled_qty": 0.0,
                "fill_ratio": 0.0,
                "vwap": None,
                "worst_price": None,
                "levels_used": 0,
                "full_fill": False,
                "book_source": source,
            }

        # When only top price is known and depth is unknown, do NOT fabricate
        # fillability. This is deliberately conservative.
        if source == "TOP_ONLY_DEPTH_UNKNOWN":
            return {
                "top_price": levels[0][0],
                "top_size": None,
                "filled_qty": 0.0,
                "fill_ratio": 0.0,
                "vwap": None,
                "worst_price": None,
                "levels_used": 0,
                "full_fill": False,
                "book_source": source,
            }

        remaining = float(qty)
        filled = 0.0
        notional = 0.0
        worst = None
        used = 0
        for price, available in levels:
            if remaining <= 1e-9:
                break
            take = min(remaining, max(0.0, float(available)))
            if take <= 0:
                continue
            filled += take
            notional += take * price
            remaining -= take
            worst = price
            used += 1

        return {
            "top_price": levels[0][0],
            "top_size": levels[0][1],
            "filled_qty": filled,
            "fill_ratio": filled / qty if qty else 0.0,
            "vwap": (notional / filled) if filled > 0 else None,
            "worst_price": worst,
            "levels_used": used,
            "full_fill": filled + 1e-9 >= qty,
            "book_source": source,
        }

    # ------------------------------------------------------------------
    # EVENT CAPTURE
    # ------------------------------------------------------------------

    def _capture(self, rec: Dict[str, Any], action: str, horizon_ms: int,
                 now: float, yes_ask=None, no_ask=None) -> Dict[str, Any]:
        side = rec["side"]
        qty = rec["qty"]
        action_key = action.lower()
        anchor = rec["entry_ts"] if action == "BUY" else rec.get("exit_ts")
        age_ms = 0.0 if anchor is None else max(0.0, (now - float(anchor)) * 1000.0)
        snap = self._walk(side, action, qty, yes_ask, no_ask)
        paper_price = rec["paper_entry"] if action == "BUY" else rec.get("paper_exit")
        fee = estimated_taker_fee(snap["filled_qty"], snap["vwap"])
        payload = {
            "event": f"{action}_QUOTE",
            "trade_id": rec["trade_id"],
            "ticker": rec["ticker"],
            "side": side,
            "action": action,
            "horizon_ms": horizon_ms,
            "observed_age_ms": age_ms,
            "paper_price": paper_price,
            "qty": qty,
            **snap,
            "estimated_fee": fee,
            "note": "shadow only; no trading authority",
        }
        _write(QUOTE_LOG, QUOTE_FIELDS, payload, self.run_id, self.session_id)
        rec[f"{action_key}_snaps"][horizon_ms] = payload
        return payload

    def _current_top(self) -> Tuple[Optional[float], Optional[float]]:
        try:
            l2 = dict(self.core.level2_snapshot(time.time()) or {})
            ya = _f(l2.get("yes_ask"))
            # level2_snapshot historically exposes YES ask directly. Derive NO
            # ask from YES bid if present.
            yb = _f(l2.get("yes_bid"))
            na = None if yb is None else max(0.0, min(1.0, 1.0 - yb))
            return ya, na
        except Exception:
            return self.last_yes_ask, self.last_no_ask

    def on_entry(self, position: Dict[str, Any], ticker: str, side: str,
                 paper_ask: float, now: Optional[float] = None,
                 yes_ask=None, no_ask=None) -> None:
        now = time.time() if now is None else float(now)
        tid = str(position.get("trade_id"))
        if not tid or tid in self.trades:
            return
        qty = int(float(position.get("qty") or 0))
        rec = {
            "trade_id": tid,
            "ticker": ticker,
            "side": side,
            "qty": qty,
            "paper_entry": _f(paper_ask),
            "paper_exit": None,
            "entry_ts": now,
            "exit_ts": None,
            "entry_snaps": {},
            "exit_snaps": {},
            "summary_done": set(),
            "exit_reason": "",
        }
        self.trades[tid] = rec

        if yes_ask is None and no_ask is None:
            yes_ask, no_ask = self._current_top()
        self._capture(rec, "BUY", 0, now, yes_ask, no_ask)

    def on_exit(self, position: Dict[str, Any], ticker: str, side: str,
                paper_bid: Optional[float], reason: str,
                now: Optional[float] = None,
                yes_ask=None, no_ask=None) -> None:
        now = time.time() if now is None else float(now)
        tid = str(position.get("trade_id"))
        if not tid:
            return
        rec = self.trades.get(tid)
        if rec is None:
            # Defensive recovery if the process attached after the entry.
            rec = {
                "trade_id": tid,
                "ticker": ticker,
                "side": side,
                "qty": int(float(position.get("qty") or 0)),
                "paper_entry": _f(position.get("entry_ask")),
                "paper_exit": None,
                "entry_ts": _f(position.get("entry_time"), now) or now,
                "exit_ts": None,
                "entry_snaps": {},
                "exit_snaps": {},
                "summary_done": set(),
                "exit_reason": "",
            }
            self.trades[tid] = rec

        # Idempotent: first observed paper exit owns the anchor.
        if rec.get("exit_ts") is not None:
            return
        rec["paper_exit"] = _f(paper_bid)
        rec["exit_ts"] = now
        rec["exit_reason"] = reason

        if yes_ask is None and no_ask is None:
            yes_ask, no_ask = self._current_top()
        self._capture(rec, "SELL", 0, now, yes_ask, no_ask)
        self._finalize_available(rec)

    def observe(self, ticker: str, yes_ask, no_ask,
                now: Optional[float] = None) -> None:
        now = time.time() if now is None else float(now)
        self.last_yes_ask = _f(yes_ask)
        self.last_no_ask = _f(no_ask)

        for rec in list(self.trades.values()):
            if str(rec.get("ticker")) != str(ticker):
                continue

            entry_age_ms = max(0.0, (now - float(rec["entry_ts"])) * 1000.0)
            for h in LATENCY_HORIZONS_MS[1:]:
                if h not in rec["entry_snaps"] and entry_age_ms >= h:
                    self._capture(rec, "BUY", h, now, yes_ask, no_ask)

            exit_ts = rec.get("exit_ts")
            if exit_ts is not None:
                exit_age_ms = max(0.0, (now - float(exit_ts)) * 1000.0)
                for h in LATENCY_HORIZONS_MS[1:]:
                    if h not in rec["exit_snaps"] and exit_age_ms >= h:
                        self._capture(rec, "SELL", h, now, yes_ask, no_ask)
                self._finalize_available(rec)

    # ------------------------------------------------------------------
    # P/L RECONSTRUCTION
    # ------------------------------------------------------------------

    def _finalize_available(self, rec: Dict[str, Any]) -> None:
        if rec.get("paper_exit") is None:
            return
        qty = int(rec.get("qty") or 0)
        paper_entry = _f(rec.get("paper_entry"))
        paper_exit = _f(rec.get("paper_exit"))
        paper_pnl = None
        if paper_entry is not None and paper_exit is not None:
            paper_pnl = qty * (paper_exit - paper_entry)

        for h in LATENCY_HORIZONS_MS:
            if h in rec["summary_done"]:
                continue
            en = rec["entry_snaps"].get(h)
            ex = rec["exit_snaps"].get(h)
            if not en or not ex:
                continue

            entry_fill = _f(en.get("filled_qty"), 0.0) or 0.0
            exit_fill = _f(ex.get("filled_qty"), 0.0) or 0.0
            live_qty = min(float(qty), entry_fill, exit_fill)
            entry_vwap = _f(en.get("vwap"))
            exit_vwap = _f(ex.get("vwap"))

            live_gross = None
            entry_fee = 0.0
            exit_fee = 0.0
            live_net = None
            if live_qty > 0 and entry_vwap is not None and exit_vwap is not None:
                live_gross = live_qty * (exit_vwap - entry_vwap)
                entry_fee = estimated_taker_fee(live_qty, entry_vwap)
                exit_fee = estimated_taker_fee(live_qty, exit_vwap)
                live_net = live_gross - entry_fee - exit_fee

            friction = None
            live_minus = None
            if paper_pnl is not None and live_net is not None:
                friction = paper_pnl - live_net
                live_minus = live_net - paper_pnl

            row = {
                "event": "TRADE_EXECUTION_SHADOW",
                "trade_id": rec["trade_id"],
                "ticker": rec["ticker"],
                "side": rec["side"],
                "horizon_ms": h,
                "primary_scenario": int(h == PRIMARY_LATENCY_MS),
                "paper_qty": qty,
                "paper_entry": paper_entry,
                "paper_exit": paper_exit,
                "paper_gross_pnl": paper_pnl,
                "entry_fill_qty": entry_fill,
                "exit_fill_qty": exit_fill,
                "live_qty": live_qty,
                "entry_fill_ratio": en.get("fill_ratio"),
                "exit_fill_ratio": ex.get("fill_ratio"),
                "live_entry_vwap": entry_vwap,
                "live_exit_vwap": exit_vwap,
                "entry_fee": entry_fee,
                "exit_fee": exit_fee,
                "live_gross_pnl": live_gross,
                "live_net_pnl": live_net,
                "friction_vs_paper": friction,
                "live_minus_paper": live_minus,
                "note": (
                    f"exit={rec.get('exit_reason','')}; "
                    "taker/depth/fee shadow; unmatched quantity is not fabricated"
                ),
            }
            _write(TRADE_LOG, TRADE_FIELDS, row, self.run_id, self.session_id)
            rec["summary_done"].add(h)

            if h == PRIMARY_LATENCY_MS and live_net is not None:
                print(
                    f"🪞 EXEC SHADOW | #{rec['trade_id']} {rec['side']} | "
                    f"paper={paper_pnl:+.2f} live500={live_net:+.2f} "
                    f"| qty {live_qty:.0f}/{qty} | friction={friction:+.2f}"
                )
