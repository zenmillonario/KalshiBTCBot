r"""
TACHYOS COMMAND DECK V2 — READ-ONLY BATTLE COCKPIT
============================================

Purpose
-------
A separate Streamlit dashboard for Tachyos BTC/Kalshi paper research.

Safety / research integrity
---------------------------
* READ ONLY: this file never imports the Tachyos trading engine.
* It never writes to Tachyos CSVs.
* It never calls Kalshi/Coinbase.
* It never places, blocks, resizes, flips, or closes a paper trade.
* It only reads telemetry files already being produced in this folder.

Drop this file in C:\KalshiBTCBot and run:
    python -m streamlit run tachyos_cockpit.py

Optional Windows launcher:
    START_TACHYOS_COCKPIT.bat
"""

from __future__ import annotations

import csv
import html
import io
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

APP_VERSION = "Command Deck V2"
ET = ZoneInfo("America/New_York")
BASE_DIR = Path(__file__).resolve().parent

FILES = {
    "price_arc": "tachys_price_arc_phase_v9_4j.csv",
    "battlefield": "tachys_battlefield_zoom_v9_4j.csv",
    "looking_glass": "tachys_looking_glass_v9_4j.csv",
    "arc_grammar": "tachys_arc_grammar_v9_4j.csv",
    "voyage": "tachys_arc_voyage_v9_4j.csv",
    "entry_timing": "tachys_entry_timing_v9_4j.csv",
    "war_report": "tachys_war_report_v9_4j.csv",
    "rollover": "tachys_rollover_rhythm_v9_4j.csv",
    "profit_shield": "tachys_profit_lock_arc_shield_v9_4j.csv",
    "paper_trades": "tachys_paper_trades_v9_2_6.csv",
    "signals": "tachys_signals_v9_2_6.csv",
    "flash": "tachys_flash_v9_2_6.csv",
    "structural": "tachys_structural_events_v9_2_6.csv",
    "council": "tachys_kings_council_v9_4i.csv",
    "regime": "tachys_regime_handshake_v9_4i.csv",
    "formation": "tachys_formation_handoff_v9_4i.csv",
    "level2": "tachys_level2_battle_council_v9_5b.csv",
    "thesis_shield_v95b": "tachys_thesis_shield_v9_5b.csv",
    "latency_v95b": "tachys_latency_accounting_v9_5b.csv",
    "rollover_memory_v95b": "tachys_rollover_memory_v9_5b.csv",
    "router_v95a": "tachys_entry_authority_router_shadow_v9_5a_rs1.csv",
    "battle_memory_v95a": "tachys_battlefield_thesis_memory_v9_5a_rs2.csv",
    "price_freshness_v95a": "tachys_price_freshness_v9_5a.csv",
    "reentry_watch": "tachys_reentry_watch_v9_4k.csv",
    "invalidation": "tachys_invalidation_persistence_v9_4i.csv",
    "catastrophic": "tachys_catastrophic_risk_shadow_v9_4i.csv",
}

MAX_READ_BYTES = 3_000_000


# ---------------------------------------------------------------------------
# STREAMLIT PAGE / CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Tachyos Command Deck",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.0rem; padding-bottom: 2rem;}
      [data-testid="stMetric"] {
          border: 1px solid rgba(128,128,128,.25);
          border-radius: 10px;
          padding: 10px 12px;
          background: rgba(128,128,128,.05);
      }
      .tachyos-banner {
          border: 1px solid rgba(128,128,128,.28);
          border-radius: 12px;
          padding: 12px 16px;
          margin-bottom: 10px;
      }
      .tiny {opacity:.72; font-size:.82rem;}
      .status-good {font-weight:700;}
      .terminal {
          border: 1px solid rgba(128,128,128,.25);
          border-radius: 10px;
          padding: 10px 12px;
          font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          font-size: .82rem;
          max-height: 430px;
          overflow-y: auto;
          white-space: pre-wrap;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# SAFE READ HELPERS
# ---------------------------------------------------------------------------

def path_for(key: str) -> Path:
    return BASE_DIR / FILES[key]


def file_age_seconds(path: Path) -> Optional[float]:
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None


def human_age(seconds: Optional[float]) -> str:
    if seconds is None:
        return "missing"
    if seconds < 2:
        return "now"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def _trim_partial_last_line(raw: bytes) -> bytes:
    """Drop a possibly half-written final CSV line during concurrent append."""
    if not raw:
        return raw
    if raw.endswith(b"\n") or raw.endswith(b"\r"):
        return raw
    cut = raw.rfind(b"\n")
    return raw[: cut + 1] if cut >= 0 else raw


def read_csv_tail(
    path: Path,
    rows: int = 1500,
    max_bytes: int = MAX_READ_BYTES,
) -> pd.DataFrame:
    """
    Read the tail of an actively appended CSV without loading a giant file.

    We always preserve the header. If we seek into the middle of a file, the
    first partial row is discarded. A half-written last line is also discarded.
    """
    if not path.exists():
        return pd.DataFrame()

    try:
        size = path.stat().st_size
        if size <= 0:
            return pd.DataFrame()

        with path.open("rb") as f:
            header = f.readline()
            if size <= max_bytes:
                f.seek(0)
                raw = f.read()
            else:
                start = max(len(header), size - max_bytes)
                f.seek(start)
                if start > len(header):
                    f.readline()  # discard partial first row
                body = f.read()
                raw = header + body

        raw = _trim_partial_last_line(raw)
        if not raw.strip():
            return pd.DataFrame()

        df = pd.read_csv(
            io.BytesIO(raw),
            on_bad_lines="skip",
            low_memory=False,
        )
        if df.empty:
            return df
        return df.tail(rows).reset_index(drop=True)

    except (OSError, PermissionError, pd.errors.ParserError, UnicodeDecodeError):
        # The producer may have the file between writes for a few milliseconds.
        # A missed dashboard refresh is safer than touching the producer.
        return pd.DataFrame()


def numeric(value, default=None):
    try:
        if value is None or pd.isna(value) or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def text_value(value, default="—") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    s = str(value).strip()
    return s if s else default


def latest_row(df: pd.DataFrame) -> Optional[pd.Series]:
    return None if df.empty else df.iloc[-1]


def fmt_money(value, decimals=2) -> str:
    x = numeric(value)
    return "—" if x is None else f"${x:,.{decimals}f}"


def fmt_quote(value) -> str:
    x = numeric(value)
    return "—" if x is None else f"{x:.3f}"


def fmt_pct(value, decimals=1) -> str:
    x = numeric(value)
    return "—" if x is None else f"{x:+.{decimals}f}%"


def fmt_seconds(value) -> str:
    x = numeric(value)
    if x is None:
        return "—"
    x = max(0, int(round(x)))
    return f"{x // 60:02d}:{x % 60:02d}"


def et_timestamp(value) -> str:
    if value is None or str(value).strip() == "":
        return "—"
    raw = str(value).strip()
    try:
        ts = pd.Timestamp(raw)
        if ts.tzinfo is None:
            # Legacy/core logs are local ET timestamps.
            ts = ts.tz_localize(ET)
        else:
            ts = ts.tz_convert(ET)
        return ts.strftime("%H:%M:%S")
    except Exception:
        return raw[-8:] if len(raw) >= 8 else raw


def row_timestamp_for_sort(value) -> float:
    """Normalize mixed UTC-aware and legacy ET-naive timestamps for event tape."""
    if value is None or str(value).strip() == "":
        return 0.0
    try:
        ts = pd.Timestamp(str(value).strip())
        if ts.tzinfo is None:
            ts = ts.tz_localize(ET)
        return ts.timestamp()
    except Exception:
        return 0.0


def first_present(row: Optional[pd.Series], names: Iterable[str], default="—"):
    if row is None:
        return default
    for name in names:
        if name in row.index:
            value = row.get(name)
            if value is not None:
                try:
                    if pd.isna(value):
                        continue
                except Exception:
                    pass
                if str(value).strip() != "":
                    return value
    return default


# ---------------------------------------------------------------------------
# QUOTE SOURCE DISCOVERY
# ---------------------------------------------------------------------------

def discover_quote_sources() -> list[Path]:
    """
    Find Tachyos CSVs that expose both YES and NO asks.

    This deliberately avoids importing Tachyos or hard-wiring the source.
    The freshest compatible file wins.
    """
    candidates: list[Path] = []
    for path in BASE_DIR.glob("tachys_*.csv"):
        try:
            with path.open("r", encoding="utf-8", newline="") as f:
                header = next(csv.reader([f.readline()]), [])
            cols = {c.strip() for c in header}
            if {"yes_ask", "no_ask"}.issubset(cols):
                candidates.append(path)
        except (OSError, StopIteration, UnicodeDecodeError):
            continue
    return candidates


def freshest_quote_snapshot():
    paths = discover_quote_sources()
    paths.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

    for path in paths:
        df = read_csv_tail(path, rows=30, max_bytes=500_000)
        if df.empty or not {"yes_ask", "no_ask"}.issubset(df.columns):
            continue
        good = df.dropna(subset=["yes_ask", "no_ask"], how="all")
        if good.empty:
            continue
        row = good.iloc[-1]
        return row, path.name, file_age_seconds(path)

    # Explicit fallback to known flash file if discovery found nothing.
    path = path_for("flash")
    df = read_csv_tail(path, rows=30, max_bytes=500_000)
    if not df.empty and {"yes_ask", "no_ask"}.issubset(df.columns):
        return df.iloc[-1], path.name, file_age_seconds(path)

    return None, None, None


# ---------------------------------------------------------------------------
# TRADE STATE
# ---------------------------------------------------------------------------

def trade_key(row: pd.Series) -> tuple[str, str]:
    return (
        text_value(row.get("ticker"), ""),
        text_value(row.get("trade_id"), ""),
    )


def build_trade_state(trades: pd.DataFrame):
    if trades.empty or "event" not in trades.columns:
        return None, pd.DataFrame(), pd.DataFrame()

    work = trades.copy()
    work["_event"] = work["event"].astype(str).str.upper()
    work["_key"] = work.apply(trade_key, axis=1)

    exits = work[work["_event"] == "EXIT"].copy()
    entries = work[work["_event"] == "ENTRY"].copy()

    exited_keys = set(exits["_key"])
    open_entries = entries[~entries["_key"].isin(exited_keys)]
    open_trade = open_entries.iloc[-1] if not open_entries.empty else None

    return open_trade, exits, work


def current_trade_mark(open_trade, quote_row, quote_age):
    if open_trade is None:
        return None

    side = text_value(open_trade.get("side"), "")
    entry = numeric(open_trade.get("entry_ask"))
    qty = numeric(open_trade.get("qty"))
    if quote_row is None or quote_age is None or quote_age > 30 or entry is None:
        return None

    yes_ask = numeric(quote_row.get("yes_ask"))
    no_ask = numeric(quote_row.get("no_ask"))

    if side == "YES" and no_ask is not None:
        exit_bid = 1.0 - no_ask
    elif side == "NO" and yes_ask is not None:
        exit_bid = 1.0 - yes_ask
    else:
        return None

    roi_pct = ((exit_bid - entry) / entry) * 100.0 if entry else None
    pnl = (qty * (exit_bid - entry)) if qty is not None else None
    return {"exit_bid": exit_bid, "roi_pct": roi_pct, "pnl": pnl}


# ---------------------------------------------------------------------------
# LIVE EVENT TAPE
# ---------------------------------------------------------------------------

def summarize_event(row: pd.Series, source: str) -> str:
    parts = []

    event = first_present(row, ["event", "condition", "state", "phase"], "")
    if event != "—" and str(event).strip():
        parts.append(str(event))

    side = first_present(row, ["side", "candidate_side", "boss_side", "boss_side_start"], "")
    if side != "—" and str(side).strip():
        parts.append(str(side))

    for col in (
        "token",
        "motif",
        "top_scenario",
        "timing_shadow",
        "shield_read",
        "shield_state",
        "state",
        "decision_path",
        "parent_side",
        "candidate_side",
        "formation_memory_side",
        "watch_state",
        "gate_action",
        "gate_reason",
        "battlefield_class",
        "snake_phase",
        "war_state",
    ):
        if col in row.index:
            val = text_value(row.get(col), "")
            if val and val != "—":
                parts.append(f"{col}={val}")

    reason = first_present(row, ["reason", "note", "exit_reason"], "")
    if reason != "—" and str(reason).strip():
        reason_s = str(reason).replace("\n", " ").strip()
        parts.append(reason_s[:160])

    if not parts:
        # Generic fallback: show a few non-empty values without dumping the row.
        skip = {"timestamp", "run_id", "session_id"}
        for col, value in row.items():
            if col in skip:
                continue
            val = text_value(value, "")
            if val:
                parts.append(f"{col}={val}")
            if len(parts) >= 3:
                break

    return " | ".join(parts)[:300]


def build_event_tape(frames: dict[str, pd.DataFrame], limit=22) -> list[dict]:
    events = []
    source_keys = [
        "level2",
        "thesis_shield_v95b",
        "rollover_memory_v95b",
        "paper_trades",
        "router_v95a",
        "battle_memory_v95a",
        "price_freshness_v95a",
        "reentry_watch",
        "structural",
        "formation",
        "entry_timing",
        "arc_grammar",
        "voyage",
        "looking_glass",
        "profit_shield",
    ]
    labels = {
        "level2": "L2",
        "thesis_shield_v95b": "T-SHLD",
        "rollover_memory_v95b": "R-MEM",
        "paper_trades": "PAPER",
        "router_v95a": "ROUTER",
        "battle_memory_v95a": "B-MEM",
        "price_freshness_v95a": "FRESH",
        "reentry_watch": "REENTRY",
        "structural": "STRUCT",
        "formation": "FORM",
        "entry_timing": "ENTRY",
        "arc_grammar": "ARC",
        "voyage": "SNAKE",
        "looking_glass": "GLASS",
        "profit_shield": "P-SHLD",
    }

    for key in source_keys:
        df = frames.get(key, pd.DataFrame())
        if df.empty or "timestamp" not in df.columns:
            continue

        # Event-oriented logs only; last few rows from each are enough.
        for _, row in df.tail(12).iterrows():
            raw_ts = row.get("timestamp")
            events.append(
                {
                    "_sort": row_timestamp_for_sort(raw_ts),
                    "time": et_timestamp(raw_ts),
                    "source": labels.get(key, key.upper()),
                    "detail": summarize_event(row, key),
                }
            )

    events.sort(key=lambda x: x["_sort"], reverse=True)
    return events[:limit]


# ---------------------------------------------------------------------------
# LOAD CURRENT TELEMETRY
# ---------------------------------------------------------------------------

@st.cache_data(ttl=0.35, show_spinner=False)
def load_frames(_stamp: int):
    # _stamp intentionally changes each refresh and keeps Streamlit honest.
    return {
        "price_arc": read_csv_tail(path_for("price_arc"), rows=2200),
        "battlefield": read_csv_tail(path_for("battlefield"), rows=400),
        "looking_glass": read_csv_tail(path_for("looking_glass"), rows=400),
        "arc_grammar": read_csv_tail(path_for("arc_grammar"), rows=120),
        "voyage": read_csv_tail(path_for("voyage"), rows=120),
        "entry_timing": read_csv_tail(path_for("entry_timing"), rows=180),
        "war_report": read_csv_tail(path_for("war_report"), rows=60),
        "rollover": read_csv_tail(path_for("rollover"), rows=120),
        "profit_shield": read_csv_tail(path_for("profit_shield"), rows=120),
        "paper_trades": read_csv_tail(path_for("paper_trades"), rows=6000),
        "signals": read_csv_tail(path_for("signals"), rows=500),
        "flash": read_csv_tail(path_for("flash"), rows=250),
        "structural": read_csv_tail(path_for("structural"), rows=250),
        "council": read_csv_tail(path_for("council"), rows=250),
        "regime": read_csv_tail(path_for("regime"), rows=250),
        "formation": read_csv_tail(path_for("formation"), rows=250),
        "level2": read_csv_tail(path_for("level2"), rows=700),
        "thesis_shield_v95b": read_csv_tail(path_for("thesis_shield_v95b"), rows=500),
        "latency_v95b": read_csv_tail(path_for("latency_v95b"), rows=300),
        "rollover_memory_v95b": read_csv_tail(path_for("rollover_memory_v95b"), rows=250),
        "router_v95a": read_csv_tail(path_for("router_v95a"), rows=500),
        "battle_memory_v95a": read_csv_tail(path_for("battle_memory_v95a"), rows=500),
        "price_freshness_v95a": read_csv_tail(path_for("price_freshness_v95a"), rows=500),
        "reentry_watch": read_csv_tail(path_for("reentry_watch"), rows=500),
        "invalidation": read_csv_tail(path_for("invalidation"), rows=300),
        "catastrophic": read_csv_tail(path_for("catastrophic"), rows=300),
    }


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## ⚔️ Command Deck")
    st.caption(f"{APP_VERSION} · observer only")
    st.markdown(
        "**READ ONLY**  \n"
        "No Tachyos imports. No API calls. No writes to trading telemetry."
    )

    auto_refresh = st.toggle("Auto refresh", value=True)
    refresh_seconds = st.slider(
        "Refresh every",
        min_value=1,
        max_value=10,
        value=2,
        step=1,
        format="%d sec",
    )
    chart_rows = st.slider(
        "Chart samples",
        min_value=180,
        max_value=1800,
        value=900,
        step=180,
    )
    st.divider()
    st.caption("Watching folder")
    st.code(str(BASE_DIR), language=None)

frames = load_frames(int(time.time() * 2))

price = latest_row(frames["price_arc"])
battle = latest_row(frames["battlefield"])
voyage = latest_row(frames["voyage"])
glass = latest_row(frames["looking_glass"])
grammar = latest_row(frames["arc_grammar"])
war = latest_row(frames["war_report"])
level2_latest = latest_row(frames["level2"])
shield_latest = latest_row(frames["thesis_shield_v95b"])
latency_latest = latest_row(frames["latency_v95b"])
rollover_memory_latest = latest_row(frames["rollover_memory_v95b"])
quote_row, quote_source, quote_age = freshest_quote_snapshot()

current_ticker = text_value(
    first_present(price, ["ticker"], first_present(battle, ["ticker"], "—"))
)

paper_trades = frames["paper_trades"]
open_trade, exits, all_trade_events = build_trade_state(paper_trades)
mark = current_trade_mark(open_trade, quote_row, quote_age)


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

st.markdown(
    f"""
    <div class="tachyos-banner">
      <div style="font-size:1.45rem;font-weight:800;">⚔️ TACHYOS COMMAND DECK</div>
      <div class="tiny">READ-ONLY OBSERVER · {html.escape(APP_VERSION)} · {html.escape(current_ticker)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

primary_age = file_age_seconds(path_for("price_arc"))
if primary_age is None:
    st.warning(
        f"No live V9.4J price/arc feed found yet at {FILES['price_arc']}. "
        "The cockpit is safe to leave open; panels will populate when the file appears."
    )
elif primary_age > 20:
    st.warning(
        f"Primary V9.4J telemetry is {human_age(primary_age)} old. "
        "Tachyos may be stopped, between writes, or this cockpit may not be in the repo root."
    )


# ---------------------------------------------------------------------------
# TOP MARKET STRIP
# ---------------------------------------------------------------------------

btc = first_present(price, ["btc_price"], first_present(quote_row, ["btc_price"], None))
target = first_present(price, ["target"], first_present(quote_row, ["target_price"], None))
seconds_left = first_present(
    price,
    ["seconds_left"],
    first_present(quote_row, ["seconds_left"], None),
)
ema9 = first_present(price, ["ema9"], first_present(quote_row, ["ema9"], None))
ema30 = first_present(price, ["ema30"], first_present(quote_row, ["ema30"], None))

btc_f = numeric(btc)
target_f = numeric(target)
ema9_f = numeric(ema9)
ema30_f = numeric(ema30)
distance = None if btc_f is None or target_f is None else btc_f - target_f
ema_gap = None if ema9_f is None or ema30_f is None else ema9_f - ema30_f

yes_ask = numeric(quote_row.get("yes_ask")) if quote_row is not None else None
no_ask = numeric(quote_row.get("no_ask")) if quote_row is not None else None
quote_fresh = quote_age is not None and quote_age <= 30

cols = st.columns(7)
cols[0].metric("BTC/USD", fmt_money(btc, 2), fmt_money(distance, 2) if distance is not None else None)
cols[1].metric("Target", fmt_money(target, 2))
cols[2].metric("Time Left", fmt_seconds(seconds_left))
cols[3].metric("EMA9", fmt_money(ema9, 2))
cols[4].metric("EMA30", fmt_money(ema30, 2), fmt_money(ema_gap, 2) if ema_gap is not None else None)
cols[5].metric("YES Ask", fmt_quote(yes_ask) if quote_fresh else "—")
cols[6].metric("NO Ask", fmt_quote(no_ask) if quote_fresh else "—")

if quote_source:
    st.caption(
        f"Kalshi quote source: {quote_source} · freshness {human_age(quote_age)}"
        + ("" if quote_fresh else " · stale quote hidden from live P&L")
    )


# ---------------------------------------------------------------------------
# CURRENT POSITION + BATTLEFIELD
# ---------------------------------------------------------------------------

left, right = st.columns([1.05, 1.35])

with left:
    st.subheader("Current Position")

    if open_trade is None:
        st.info("No open paper position detected.")
    else:
        side = text_value(open_trade.get("side"))
        trade_id = text_value(open_trade.get("trade_id"))
        entry_ask = numeric(open_trade.get("entry_ask"))
        qty = numeric(open_trade.get("qty"))
        stake = numeric(open_trade.get("cost"))
        strategy = text_value(open_trade.get("strategy"))
        intent = text_value(open_trade.get("trade_intent"))

        a, b, c = st.columns(3)
        a.metric("Trade", f"#{trade_id} {side}")
        b.metric("Entry", fmt_quote(entry_ask))
        c.metric("Stake", fmt_money(stake, 2))

        d, e, f = st.columns(3)
        d.metric("Qty", "—" if qty is None else f"{qty:g}")
        if mark:
            e.metric("Live Bid*", fmt_quote(mark["exit_bid"]))
            f.metric("Live P&L*", fmt_money(mark["pnl"], 2), fmt_pct(mark["roi_pct"]))
        else:
            e.metric("Live Bid*", "—")
            f.metric("Live P&L*", "—")

        st.caption(f"{strategy} · intent {intent}")
        st.caption("*Estimated only when a YES/NO quote source is ≤30 seconds old.")

        # Show this trade's milestone / management tape.
        if not all_trade_events.empty:
            key = trade_key(open_trade)
            own = all_trade_events[all_trade_events["_key"] == key].tail(12).copy()
            keep = [
                c for c in
                ["timestamp", "event", "exit_bid", "pnl", "roi_pct", "reason", "mfe_pct", "mae_pct"]
                if c in own.columns
            ]
            if keep:
                st.dataframe(own[keep], hide_index=True, use_container_width=True)

with right:
    st.subheader("Battlefield")

    battlefield_class = first_present(battle, ["battlefield_class"])
    territory_state = first_present(battle, ["territory_state"])
    churn_type = first_present(battle, ["churn_type"])
    box_location = first_present(battle, ["box_location"])
    zoom_mode = first_present(battle, ["zoom_mode"])
    price_arc_phase = first_present(battle, ["price_arc_phase"], first_present(price, ["price_arc_phase"]))
    remaining_capacity = first_present(
        battle, ["remaining_capacity"], first_present(price, ["remaining_capacity"])
    )
    snake_phase = first_present(battle, ["snake_phase"], first_present(voyage, ["phase"]))
    snake_maturity = first_present(battle, ["snake_maturity"], first_present(voyage, ["maturity"]))
    boss_side = first_present(battle, ["boss_side"], first_present(price, ["boss_side"]))
    hand_side = first_present(battle, ["hand_side"], first_present(price, ["hand_side"]))
    handshake = first_present(battle, ["handshake_phase"])
    efficiency = first_present(battle, ["trend_efficiency60"])
    range60 = first_present(battle, ["range60"], first_present(price, ["range60"]))

    r1 = st.columns(4)
    r1[0].metric("Battlefield", text_value(battlefield_class))
    r1[1].metric("Territory", text_value(territory_state))
    r1[2].metric("Churn", text_value(churn_type))
    r1[3].metric("Zoom", text_value(zoom_mode))

    r2 = st.columns(4)
    r2[0].metric("Boss", text_value(boss_side))
    r2[1].metric("Hand", text_value(hand_side))
    r2[2].metric("Handshake", text_value(handshake))
    r2[3].metric("Snake", text_value(snake_phase))

    r3 = st.columns(4)
    r3[0].metric("Arc Phase", text_value(price_arc_phase))
    rc = numeric(remaining_capacity)
    r3[1].metric("Remaining Cap.", "—" if rc is None else f"{rc:.2f}")
    sm = numeric(snake_maturity)
    r3[2].metric("Snake Maturity", "—" if sm is None else f"{sm:.2f}")
    eff = numeric(efficiency)
    r3[3].metric("Trend Eff.", "—" if eff is None else f"{eff:.2f}")

    st.caption(
        f"Box: {text_value(box_location)} · 60s BTC range: "
        f"{fmt_money(range60, 2)}"
    )



# ---------------------------------------------------------------------------
# LEVEL-2 BATTLE COUNCIL / THESIS SHIELD
# ---------------------------------------------------------------------------

st.subheader("Level-2 Battle Council")

l2_df = frames["level2"]
if not l2_df.empty and "ticker" in l2_df.columns and current_ticker != "—":
    l2_current = l2_df[l2_df["ticker"].astype(str) == str(current_ticker)]
    _l2_current_row = latest_row(l2_current)
    l2_row = _l2_current_row if _l2_current_row is not None else level2_latest
else:
    l2_row = level2_latest

if l2_row is None:
    st.info("Waiting for V9.5B Level-2 telemetry. The Deck remains compatible with older runs.")
else:
    parent_side = text_value(l2_row.get("parent_side"))
    tactical_side = text_value(l2_row.get("candidate_side"))
    l2_state = text_value(l2_row.get("state"))
    l2_score = numeric(l2_row.get("score"))
    family_count = numeric(l2_row.get("family_count"))
    arm_age = numeric(l2_row.get("arm_age_sec"))
    decision_path = text_value(l2_row.get("decision_path"))
    recognition_source = text_value(l2_row.get("recognition_source"))
    recognition_age = numeric(l2_row.get("recognition_age_sec"))
    recognition_ask = numeric(l2_row.get("recognition_first_ask"))
    arm_ask = numeric(l2_row.get("arm_ask"))
    current_l2_ask = numeric(l2_row.get("ask"))
    formation_memory_side = text_value(l2_row.get("formation_memory_side"))
    formation_memory_age = numeric(l2_row.get("formation_memory_age_sec"))
    deadline_left = None if arm_age is None else max(0.0, 9.0 - arm_age)

    z1 = st.columns(6)
    z1[0].metric("Strategic Parent", parent_side)
    z1[1].metric("Tactical Side", tactical_side)
    z1[2].metric("Level-2 State", l2_state)
    z1[3].metric("Council Score", "—" if l2_score is None else f"{l2_score:.0f}")
    z1[4].metric("Families", "—" if family_count is None else f"{family_count:.0f}")
    z1[5].metric("3/6/9 Deadline", "—" if deadline_left is None else f"{deadline_left:.1f}s")

    z2 = st.columns(6)
    z2[0].metric("Decision Path", decision_path)
    z2[1].metric("Observer First", recognition_source)
    z2[2].metric("Recognition Age", "—" if recognition_age is None else f"{recognition_age:.1f}s")
    z2[3].metric("Recognition Ask", fmt_quote(recognition_ask))
    z2[4].metric("Arm Ask", fmt_quote(arm_ask))
    edge_now = None if current_l2_ask is None or arm_ask is None else (current_l2_ask - arm_ask) * 100.0
    z2[5].metric("Edge vs Arm", "—" if edge_now is None else f"{edge_now:+.1f}¢")

    st.caption(
        f"Evidence families: {text_value(l2_row.get('families'))} · "
        f"Formation memory: {formation_memory_side}"
        + ("" if formation_memory_age is None else f" ({formation_memory_age:.1f}s)")
        + f" · reason: {text_value(l2_row.get('decision_result'), text_value(l2_row.get('reasons'), ''))}"
    )

st.markdown("#### Thesis Shield")
shield_df = frames["thesis_shield_v95b"]
shield_row = shield_latest
if open_trade is not None and not shield_df.empty and "trade_id" in shield_df.columns:
    own_shield = shield_df[shield_df["trade_id"].astype(str) == str(open_trade.get("trade_id"))]
    if not own_shield.empty:
        shield_row = latest_row(own_shield)

if shield_row is None:
    st.caption("No V9.5B Thesis Shield state yet.")
else:
    sh = st.columns(6)
    sh[0].metric("Shield", text_value(shield_row.get("shield_state")))
    sh[1].metric("Trade", f"#{text_value(shield_row.get('trade_id'))} {text_value(shield_row.get('side'))}")
    sh[2].metric("Entry Age", fmt_seconds(shield_row.get("entry_age_sec")))
    sh[3].metric("Catastrophic Pts", text_value(shield_row.get("catastrophic_points")))
    sh[4].metric("Hold Authority", text_value(shield_row.get("hold_authority")))
    sh[5].metric("Structural Bias", text_value(shield_row.get("structural_bias")))
    st.caption(text_value(shield_row.get("catastrophic_reasons"), "No catastrophic release reasons."))

# ---------------------------------------------------------------------------
# MAIN CHART
# ---------------------------------------------------------------------------

st.subheader("Continuous BTC Geometry")

chart = frames["price_arc"].tail(chart_rows).copy()
required = {"timestamp", "btc_price"}
if chart.empty or not required.issubset(chart.columns):
    st.info("Waiting for V9.4J price/arc samples.")
else:
    chart["_ts"] = pd.to_datetime(chart["timestamp"], errors="coerce", utc=True)
    chart = chart.dropna(subset=["_ts"]).set_index("_ts")

    plot_cols = [
        c for c in ["btc_price", "ema9", "ema30", "target"]
        if c in chart.columns
    ]
    for c in plot_cols:
        chart[c] = pd.to_numeric(chart[c], errors="coerce")

    if plot_cols:
        st.line_chart(chart[plot_cols], use_container_width=True, height=390)
        st.caption(
            "BTC price + EMA9 + EMA30 + Kalshi target. Contract boundaries remain "
            "fenceposts; the geometry is shown continuously across the selected samples."
        )


# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------

tab_trades, tab_council, tab_shield, tab_latency, tab_glass, tab_arc, tab_war, tab_tape, tab_health = st.tabs(
    [
        "Trades",
        "Battle Council",
        "Thesis Shield",
        "Latency",
        "Looking Glass",
        "Arc / Snake",
        "War Report",
        "Live Tape",
        "Feed Health",
    ]
)

with tab_trades:
    st.markdown("#### Current Contract")
    if all_trade_events.empty:
        st.info("No paper-trade telemetry yet.")
    else:
        contract = all_trade_events[all_trade_events["ticker"].astype(str) == current_ticker].copy()
        show_cols = [
            c for c in
            [
                "timestamp", "event", "trade_id", "side", "entry_ask", "exit_bid",
                "pnl", "roi_pct", "reason", "mfe_pct", "mae_pct", "trade_intent",
                "cumulative_pnl",
            ]
            if c in contract.columns
        ]
        if contract.empty:
            st.info("No paper trades in the current contract yet.")
        else:
            st.dataframe(
                contract.tail(30)[show_cols],
                hide_index=True,
                use_container_width=True,
            )

    st.markdown("#### Last Completed Trades")
    if exits.empty:
        st.info("No completed paper trades detected.")
    else:
        recent = exits.tail(12).copy()
        if "pnl" in recent.columns:
            pnl_num = pd.to_numeric(recent["pnl"], errors="coerce")
            recent.insert(
                min(4, len(recent.columns)),
                "result",
                pnl_num.apply(
                    lambda x: "WIN" if pd.notna(x) and x > 0
                    else ("LOSS" if pd.notna(x) and x < 0 else "SCRATCH")
                ),
            )
        keep = [
            c for c in
            [
                "trade_id", "ticker", "side", "result", "entry_ask", "exit_bid",
                "pnl", "roi_pct", "reason", "mfe_pct", "mae_pct", "cumulative_pnl",
            ]
            if c in recent.columns
        ]
        st.dataframe(recent[keep], hide_index=True, use_container_width=True)


with tab_council:
    st.markdown("#### Level-2 Decisions")
    l2 = frames["level2"].copy()
    if l2.empty:
        st.info("Waiting for V9.5B Level-2 telemetry.")
    else:
        keep = [
            c for c in [
                "timestamp", "event", "ticker", "parent_side", "candidate_side",
                "state", "ask", "arm_ask", "arm_age_sec", "score", "family_count",
                "families", "primary_trigger", "decision_path", "decision_result",
                "recognition_source", "recognition_age_sec", "recognition_first_ask",
                "formation_memory_side", "formation_memory_age_sec",
                "parent_leg_stale", "parent_leg_premium_abs", "price_reprice_abs",
                "reasons", "contradictions",
            ] if c in l2.columns
        ]
        st.dataframe(l2.tail(80)[keep], hide_index=True, use_container_width=True)

    st.markdown("#### Rollover Memory")
    rm = frames["rollover_memory_v95b"].copy()
    if rm.empty:
        st.caption("No V9.5B rollover-memory events yet.")
    else:
        keep = [
            c for c in [
                "timestamp", "event", "from_ticker", "to_ticker", "side",
                "memory_kind", "memory_age_sec", "formation",
                "formation_maturity", "local_regime", "parent_side",
                "target_event", "structural_bias", "note",
            ] if c in rm.columns
        ]
        st.dataframe(rm.tail(30)[keep], hide_index=True, use_container_width=True)

with tab_shield:
    st.markdown("#### Thesis Protection")
    shdf = frames["thesis_shield_v95b"].copy()
    if shdf.empty:
        st.info("Waiting for V9.5B Thesis Shield telemetry.")
    else:
        keep = [
            c for c in [
                "timestamp", "trade_id", "ticker", "side", "entry_age_sec",
                "entry_ask", "current_bid", "roi", "shield_state",
                "catastrophic_points", "catastrophic_reasons", "hold_authority",
                "own_structural_score", "opposite_structural_score",
                "structural_bias", "target_event", "ema30_event", "target_distance",
            ] if c in shdf.columns
        ]
        st.dataframe(shdf.tail(80)[keep], hide_index=True, use_container_width=True)

    st.markdown("#### Supporting Exit Witnesses")
    witness_frames = [
        ("Invalidation Persistence", frames["invalidation"]),
        ("Catastrophic Risk", frames["catastrophic"]),
    ]
    for label, df in witness_frames:
        st.markdown(f"**{label}**")
        if df.empty:
            st.caption("No telemetry.")
        else:
            st.dataframe(df.tail(18), hide_index=True, use_container_width=True)

with tab_latency:
    st.markdown("#### Observer → Level 2 → Entry")
    lat = frames["latency_v95b"].copy()
    if lat.empty:
        st.info("Waiting for V9.5B latency accounting.")
    else:
        keep = [
            c for c in [
                "timestamp", "trade_id", "ticker", "side", "strategy",
                "observer_source", "observer_to_entry_sec",
                "observer_ask", "entry_ask", "observer_edge_lost_cents",
                "arm_id", "arm_to_entry_sec", "arm_ask",
                "arm_edge_lost_cents", "decision_path",
            ] if c in lat.columns
        ]
        st.dataframe(lat.tail(60)[keep], hide_index=True, use_container_width=True)

        obs_delay = pd.to_numeric(lat.get("observer_to_entry_sec"), errors="coerce") if "observer_to_entry_sec" in lat.columns else pd.Series(dtype=float)
        arm_delay = pd.to_numeric(lat.get("arm_to_entry_sec"), errors="coerce") if "arm_to_entry_sec" in lat.columns else pd.Series(dtype=float)
        obs_edge = pd.to_numeric(lat.get("observer_edge_lost_cents"), errors="coerce") if "observer_edge_lost_cents" in lat.columns else pd.Series(dtype=float)
        mm = st.columns(3)
        mm[0].metric("Median Observer→Entry", "—" if obs_delay.dropna().empty else f"{obs_delay.dropna().median():.1f}s")
        mm[1].metric("Median Arm→Entry", "—" if arm_delay.dropna().empty else f"{arm_delay.dropna().median():.1f}s")
        mm[2].metric("Median Edge Lost", "—" if obs_edge.dropna().empty else f"{obs_edge.dropna().median():+.1f}¢")

    st.markdown("#### Battlefield Reacquisition")
    re = frames["reentry_watch"].copy()
    if re.empty:
        st.caption("No Reentry Watch telemetry.")
    else:
        keep = [
            c for c in [
                "timestamp", "trade_id", "ticker", "side", "seconds_since_exit",
                "current_bid", "boss_side", "hand_side", "arc_direction",
                "price_arc_phase", "reclaim_score", "watch_state", "reason",
            ] if c in re.columns
        ]
        st.dataframe(re.tail(40)[keep], hide_index=True, use_container_width=True)

with tab_glass:
    st.markdown("#### Looking Glass — research scores, not calibrated probabilities")
    if glass is None:
        st.info("Waiting for Looking Glass telemetry.")
    else:
        g1 = st.columns(4)
        g1[0].metric("Top Scenario", text_value(glass.get("top_scenario")))
        g1[1].metric(
            "Shadow Confidence",
            fmt_pct(glass.get("shadow_confidence_pct")).replace("+", ""),
        )
        g1[2].metric(
            "Rolling Accuracy",
            fmt_pct(glass.get("rolling_accuracy_pct")).replace("+", ""),
        )
        g1[3].metric("Horizon", fmt_seconds(glass.get("horizon_sec")))

        g2 = st.columns(3)
        for col, metric, label in [
            ("continuation_score", g2[0], "Continuation Score"),
            ("storm_score", g2[1], "Storm Score"),
            ("transfer_score", g2[2], "Transfer Score"),
        ]:
            val = numeric(glass.get(col))
            metric.metric(label, "—" if val is None else f"{val:.2f}")

        lg = frames["looking_glass"].tail(20).copy()
        keep = [
            c for c in
            [
                "timestamp", "event", "horizon_sec", "top_scenario",
                "shadow_confidence_pct", "rolling_accuracy_pct",
                "actual_outcome", "correct", "battlefield_start",
                "snake_phase_start", "price_arc_phase_start", "reason",
            ]
            if c in lg.columns
        ]
        if keep:
            st.dataframe(lg[keep], hide_index=True, use_container_width=True)

with tab_arc:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Arc Grammar")
        if grammar is None:
            st.info("Waiting for Arc Grammar.")
        else:
            st.metric("Latest Token", text_value(grammar.get("token")))
            st.metric("Motif", text_value(grammar.get("motif")))
            st.metric("Three-Shape Spotlight", text_value(grammar.get("three_shape_spotlight")))
            ag = frames["arc_grammar"].tail(16)
            keep = [
                c for c in
                ["timestamp", "event", "token", "motif", "motif_length",
                 "three_shape_spotlight", "battlefield_class", "reason"]
                if c in ag.columns
            ]
            if keep:
                st.dataframe(ag[keep], hide_index=True, use_container_width=True)

    with c2:
        st.markdown("#### Arc Voyage / Snake")
        if voyage is None:
            st.info("Waiting for Arc Voyage.")
        else:
            st.metric("Voyage", text_value(voyage.get("voyage_id")))
            st.metric("Phase", text_value(voyage.get("phase")))
            st.metric("Contracts Seen", text_value(voyage.get("contracts_seen")))
            st.metric("Arc Count", text_value(voyage.get("arc_count")))
            vv = frames["voyage"].tail(14)
            keep = [
                c for c in
                ["timestamp", "event", "voyage_id", "phase", "launch_direction",
                 "latest_arc_direction", "latest_arc_amp", "arc_count",
                 "contracts_seen", "maturity", "release_score", "net_btc_move", "reason"]
                if c in vv.columns
            ]
            if keep:
                st.dataframe(vv[keep], hide_index=True, use_container_width=True)

with tab_war:
    if war is None:
        st.info("Waiting for 6/12-contract War Report telemetry.")
    else:
        w1 = st.columns(5)
        w1[0].metric("Window", text_value(war.get("window_contracts")))
        w1[1].metric("Trades", text_value(war.get("trades")))
        w1[2].metric("W / L / S", f"{text_value(war.get('wins'))} / {text_value(war.get('losses'))} / {text_value(war.get('scratches'))}")
        w1[3].metric("P&L", fmt_money(war.get("pnl"), 2))
        pf = numeric(war.get("profit_factor"))
        w1[4].metric("Profit Factor", "—" if pf is None else f"{pf:.2f}")

        w2 = st.columns(4)
        w2[0].metric("War State", text_value(war.get("war_state")))
        w2[1].metric("Casualties ≤ -$5", text_value(war.get("casualties_le_minus5")))
        w2[2].metric("Campaign P&L", fmt_money(war.get("campaign_pnl"), 2))
        w2[3].metric("Raid P&L", fmt_money(war.get("raid_pnl"), 2))
        st.caption(text_value(war.get("note"), ""))

        wr = frames["war_report"].tail(12)
        keep = [
            c for c in
            [
                "timestamp", "window_contracts", "contracts_count", "trades",
                "wins", "losses", "scratches", "pnl", "profit_factor",
                "casualties_le_minus5", "war_state", "note",
            ]
            if c in wr.columns
        ]
        if keep:
            st.dataframe(wr[keep], hide_index=True, use_container_width=True)

with tab_tape:
    tape = build_event_tape(frames, limit=28)
    if not tape:
        st.info("Waiting for event telemetry.")
    else:
        lines = []
        for event in reversed(tape):
            lines.append(
                f"{event['time']}  [{event['source']:<6}]  {event['detail']}"
            )
        st.markdown(
            '<div class="terminal">' + html.escape("\n".join(lines)) + "</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "This is a reconstructed telemetry tape, not stdout capture. "
            "It requires no modification to the running Tachyos process."
        )

with tab_health:
    st.markdown("#### Feed Health")
    health_rows = []
    for key in [
        "level2", "thesis_shield_v95b", "latency_v95b", "rollover_memory_v95b",
        "router_v95a", "battle_memory_v95a", "price_freshness_v95a",
        "reentry_watch", "invalidation", "catastrophic", "formation",
        "price_arc", "battlefield", "paper_trades", "looking_glass",
        "arc_grammar", "voyage", "entry_timing", "war_report",
        "structural", "council",
    ]:
        path = path_for(key)
        age = file_age_seconds(path)
        health_rows.append(
            {
                "feed": key,
                "file": path.name,
                "exists": path.exists(),
                "age": human_age(age),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    st.dataframe(pd.DataFrame(health_rows), hide_index=True, use_container_width=True)

    st.markdown("#### Discovered YES/NO quote feeds")
    quote_sources = discover_quote_sources()
    if quote_sources:
        qrows = [
            {
                "file": p.name,
                "age": human_age(file_age_seconds(p)),
                "bytes": p.stat().st_size,
            }
            for p in sorted(
                quote_sources,
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        ]
        st.dataframe(pd.DataFrame(qrows), hide_index=True, use_container_width=True)
    else:
        st.caption("No file with both yes_ask and no_ask columns discovered yet.")

    st.caption(
        "The cockpit tolerates missing files and partial last CSV rows. "
        "If a producer is between writes, the dashboard simply skips that refresh."
    )


# ---------------------------------------------------------------------------
# REFRESH LOOP
# ---------------------------------------------------------------------------

st.caption(
    f"Last dashboard render: {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')} · "
    f"primary feed age {human_age(primary_age)}"
)

if auto_refresh:
    time.sleep(refresh_seconds)
    try:
        st.rerun()
    except AttributeError:  # old Streamlit fallback
        st.experimental_rerun()
