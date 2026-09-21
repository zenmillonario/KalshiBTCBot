r"""
TACHYOS COMMAND DECK V3 — LEG GEOMETRY
=====================================
READ ONLY. No Tachyos imports. No API calls. No trading writes.
"""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

APP_VERSION = "Command Deck V3"
ET = ZoneInfo("America/New_York")
BASE_DIR = Path(__file__).resolve().parent
MAX_READ_BYTES = 3_000_000

FILES = {
    "leg": "tachys_leg_geometry_v9_5c.csv",
    "tactical": "tachys_dual_side_authority_v9_5c.csv",
    "exit": "tachys_whole_leg_exit_authority_v9_5c.csv",
    "rollover_c": "tachys_rollover_continuity_v9_5c.csv",
    "manifest_c": "tachys_run_manifest_v9_5c.csv",
    "paper": "tachys_paper_trades_v9_2_6.csv",
    "price_arc": "tachys_price_arc_phase_v9_4j.csv",
    "battlefield": "tachys_battlefield_zoom_v9_4j.csv",
    "looking_glass": "tachys_looking_glass_v9_4j.csv",
    "reentry": "tachys_reentry_watch_v9_4k.csv",
    "structural": "tachys_structural_events_v9_2_6.csv",
    "formation": "tachys_formation_handoff_v9_4i.csv",
    "router": "tachys_entry_authority_router_shadow_v9_5a_rs1.csv",
    "battle_memory": "tachys_battlefield_thesis_memory_v9_5a_rs2.csv",
}

EVENT_DRIVEN = {"exit", "rollover_c", "reentry", "battle_memory"}

st.set_page_config(
    page_title="Tachyos Command Deck V3",
    page_icon="🧱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: .8rem; padding-bottom: 2rem;}
      [data-testid="stMetric"] {
          border: 1px solid rgba(128,128,128,.25);
          border-radius: 10px;
          padding: 9px 11px;
          background: rgba(128,128,128,.05);
      }
      .deck-banner {
          border: 1px solid rgba(128,128,128,.28);
          border-radius: 12px;
          padding: 12px 16px;
          margin-bottom: 10px;
      }
      .small-note {opacity:.72; font-size:.82rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

def path_for(key: str) -> Path:
    return BASE_DIR / FILES[key]

def age_seconds(path: Path) -> Optional[float]:
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None

def human_age(sec: Optional[float]) -> str:
    if sec is None:
        return "missing"
    if sec < 2:
        return "now"
    if sec < 60:
        return f"{sec:.0f}s"
    if sec < 3600:
        return f"{sec/60:.1f}m"
    return f"{sec/3600:.1f}h"

def _trim_partial(raw: bytes) -> bytes:
    if not raw or raw.endswith(b"\n") or raw.endswith(b"\r"):
        return raw
    cut = raw.rfind(b"\n")
    return raw[:cut+1] if cut >= 0 else raw

def read_tail(path: Path, rows: int = 1000, max_bytes: int = MAX_READ_BYTES) -> pd.DataFrame:
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
                start = max(len(header), size-max_bytes)
                f.seek(start)
                if start > len(header):
                    f.readline()
                raw = header + f.read()
        raw = _trim_partial(raw)
        if not raw.strip():
            return pd.DataFrame()
        df = pd.read_csv(io.BytesIO(raw), on_bad_lines="skip", low_memory=False)
        return df.tail(rows).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

def latest(df: pd.DataFrame):
    return None if df.empty else df.iloc[-1]

def num(v, default=None):
    try:
        if v is None or pd.isna(v) or v == "":
            return default
        return float(v)
    except Exception:
        return default

def txt(v, default="—"):
    if v is None:
        return default
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    s = str(v).strip()
    return s if s else default

def money(v, dec=2):
    x = num(v)
    return "—" if x is None else f"USD {x:,.{dec}f}"

def quote(v):
    x = num(v)
    return "—" if x is None else f"{x:.3f}"

def secs(v):
    x = num(v)
    if x is None:
        return "—"
    x = max(0, int(round(x)))
    return f"{x//60:02d}:{x%60:02d}"

def discover_quote():
    paths = []
    for p in BASE_DIR.glob("tachys_*.csv"):
        try:
            with p.open("r", encoding="utf-8", newline="") as f:
                header = next(csv.reader([f.readline()]), [])
            cols = set(x.strip() for x in header)
            if {"yes_ask","no_ask"}.issubset(cols):
                paths.append(p)
        except Exception:
            pass
    paths.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for p in paths:
        df = read_tail(p, rows=20, max_bytes=500_000)
        if df.empty:
            continue
        good = df.dropna(subset=["yes_ask","no_ask"], how="all") if {"yes_ask","no_ask"}.issubset(df.columns) else pd.DataFrame()
        if not good.empty:
            return good.iloc[-1], p.name, age_seconds(p)
    return None, None, None

@st.cache_data(ttl=.35, show_spinner=False)
def load_frames(_stamp: int):
    return {key: read_tail(path_for(key), 1500 if key in ("leg","tactical","exit") else 600)
            for key in FILES}

with st.sidebar:
    st.markdown("## 🧱 Command Deck")
    st.caption(f"{APP_VERSION} · READ ONLY")
    st.markdown("EMA30 = **Spine**  \nEMA9 = **Leg Geometry**")
    auto = st.toggle("Auto refresh", True)
    refresh = st.slider("Refresh every", 1, 10, 2)
    chart_rows = st.slider("Chart samples", 180, 1800, 900, step=180)
    st.divider()
    st.code(str(BASE_DIR), language=None)

frames = load_frames(int(time.time()*2))
leg = latest(frames["leg"])
tactical = frames["tactical"]
exit_row = latest(frames["exit"])
paper = frames["paper"].copy()
quote_row, quote_source, quote_age = discover_quote()

current_ticker = txt(leg.get("ticker") if leg is not None else None)

st.markdown(
    f"""
    <div class="deck-banner">
      <div style="font-size:1.45rem;font-weight:800;">🧱 TACHYOS COMMAND DECK — LEG GEOMETRY</div>
      <div class="small-note">READ ONLY · {APP_VERSION} · {current_ticker}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if leg is None:
    st.warning("Waiting for V9.5C Leg Geometry telemetry.")
else:
    row1 = st.columns(7)
    row1[0].metric("Leg Side", txt(leg.get("leg_side")))
    row1[1].metric("Leg State", txt(leg.get("leg_state")))
    row1[2].metric("Target Height", money(leg.get("target_height")))
    row1[3].metric("Time Left", secs(leg.get("seconds_left")))
    row1[4].metric("Time Capacity", txt(leg.get("time_capacity_state")))
    row1[5].metric("Rollover", txt(leg.get("rollover_state")))
    row1[6].metric("Wicks", txt(leg.get("wick_rejection")))

    row2 = st.columns(7)
    row2[0].metric("EMA9", money(leg.get("ema9")))
    row2[1].metric("EMA30 Spine", money(leg.get("ema30")))
    row2[2].metric("EMA Gap", money(leg.get("ema_gap")))
    row2[3].metric("EMA9 Slope 6s", money(leg.get("ema9_slope6")))
    row2[4].metric("EMA30 Slope 30s", money(leg.get("ema30_slope30")))
    row2[5].metric("Leg Remaining", secs(leg.get("estimated_leg_seconds_remaining")))
    row2[6].metric("Regeneration", txt(leg.get("regeneration_state")))

yes_row = no_row = None
if not tactical.empty and "ticker" in tactical.columns and "side" in tactical.columns:
    cur = tactical[tactical["ticker"].astype(str) == str(current_ticker)]
    yes_row = latest(cur[cur["side"].astype(str) == "YES"])
    no_row = latest(cur[cur["side"].astype(str) == "NO"])

st.subheader("Dual-Side Tactical Authority")
a1 = st.columns(6)
a1[0].metric("YES Score", "—" if yes_row is None else txt(yes_row.get("score")))
a1[1].metric("YES State", "—" if yes_row is None else txt(yes_row.get("state")))
a1[2].metric("YES Ask", quote(None if quote_row is None else quote_row.get("yes_ask")))
a1[3].metric("NO Score", "—" if no_row is None else txt(no_row.get("score")))
a1[4].metric("NO State", "—" if no_row is None else txt(no_row.get("state")))
a1[5].metric("NO Ask", quote(None if quote_row is None else quote_row.get("no_ask")))

if yes_row is not None:
    st.caption(f"YES: {txt(yes_row.get('reasons'),'')} | blocks: {txt(yes_row.get('blocks'),'')}")
if no_row is not None:
    st.caption(f"NO: {txt(no_row.get('reasons'),'')} | blocks: {txt(no_row.get('blocks'),'')}")

st.subheader("Whole-Leg Exit Authority")
if exit_row is None:
    st.info("No exit-gate event yet. This feed is event-driven.")
else:
    e = st.columns(6)
    e[0].metric("Trade", f"#{txt(exit_row.get('trade_id'))} {txt(exit_row.get('side'))}")
    e[1].metric("Gate Ruling", txt(exit_row.get("gate_ruling")))
    e[2].metric("Final Action", txt(exit_row.get("final_action")))
    e[3].metric("ROI", "—" if num(exit_row.get("roi")) is None else f"{num(exit_row.get('roi')):+.1%}")
    e[4].metric("Proposed Exit", txt(exit_row.get("proposed_exit_reason")))
    e[5].metric("Opposite Score", txt(exit_row.get("opposite_score")))

open_trade = None
if not paper.empty and "event" in paper.columns and {"ticker","trade_id"}.issubset(paper.columns):
    paper["_event"] = paper["event"].astype(str).str.upper()
    paper["_key"] = paper["ticker"].astype(str) + ":" + paper["trade_id"].astype(str)
    exits = set(paper.loc[paper["_event"]=="EXIT","_key"])
    entries = paper[(paper["_event"]=="ENTRY") & (~paper["_key"].isin(exits))]
    open_trade = latest(entries)

st.subheader("Current Position")
if open_trade is None:
    st.info("No open paper position detected.")
else:
    p = st.columns(6)
    p[0].metric("Trade", f"#{txt(open_trade.get('trade_id'))} {txt(open_trade.get('side'))}")
    p[1].metric("Entry", quote(open_trade.get("entry_ask")))
    p[2].metric("Qty", txt(open_trade.get("qty")))
    p[3].metric("Strategy", txt(open_trade.get("strategy")))
    p[4].metric("Intent", txt(open_trade.get("trade_intent")))
    p[5].metric("Target Dist. at Entry", money(open_trade.get("target_distance")))

if quote_source:
    st.caption(f"Quote source: {quote_source} · {human_age(quote_age)}")

st.subheader("Geometry Relative to Target")
chart = frames["price_arc"].tail(chart_rows).copy()
if chart.empty or "timestamp" not in chart.columns:
    st.info("Waiting for continuous geometry feed.")
else:
    chart["_ts"] = pd.to_datetime(chart["timestamp"], errors="coerce", utc=True)
    chart = chart.dropna(subset=["_ts"]).set_index("_ts")
    target_col = "target" if "target" in chart.columns else "target_price" if "target_price" in chart.columns else None
    cols = [c for c in ["btc_price","ema9","ema30"] if c in chart.columns]
    if target_col and cols:
        target_vals = pd.to_numeric(chart[target_col], errors="coerce")
        rel = pd.DataFrame(index=chart.index)
        for c in cols:
            rel[c+"_vs_target"] = pd.to_numeric(chart[c], errors="coerce") - target_vals
        rel["target"] = 0.0
        st.line_chart(rel, use_container_width=True, height=390)
        st.caption("Values are dollars above/below the active Kalshi target. Target = zero.")
    else:
        st.info("Target-relative chart waiting for target + EMA columns.")

tab_leg, tab_tactical, tab_exit, tab_roll, tab_trades, tab_health = st.tabs(
    ["Leg Timeline","Tactical YES/NO","Exit Authority","Rollover","Trades","Feed Health"]
)

with tab_leg:
    df = frames["leg"]
    if df.empty:
        st.info("Waiting for V9.5C leg log.")
    else:
        keep = [c for c in [
            "timestamp","ticker","leg_id","leg_side","leg_state","leg_age_sec",
            "target_height","seconds_left","ema_gap","ema9_slope6","ema30_slope30",
            "current_amplitude","peak_amplitude","time_capacity_state",
            "estimated_leg_seconds_remaining","rollover_state","wick_rejection",
            "target_event","regeneration_state"
        ] if c in df.columns]
        st.dataframe(df.tail(100)[keep], hide_index=True, use_container_width=True)

with tab_tactical:
    df = frames["tactical"]
    if df.empty:
        st.info("Waiting for dual-side authority log.")
    else:
        keep = [c for c in [
            "timestamp","ticker","side","state","ask","score","other_score","score_lead",
            "leg_side","leg_state","target_height","target_event","seconds_left",
            "time_capacity_state","rollover_state","prearmed_side","decision","reasons","blocks"
        ] if c in df.columns]
        st.dataframe(df.tail(120)[keep], hide_index=True, use_container_width=True)

with tab_exit:
    df = frames["exit"]
    if df.empty:
        st.info("No Whole-Leg Exit events yet.")
    else:
        keep = [c for c in [
            "timestamp","trade_id","ticker","side","roi","mfe_roi","proposed_exit_reason",
            "gate_ruling","final_action","leg_side","leg_state","target_height","target_event",
            "seconds_left","time_capacity_state","yes_score","no_score","opposite_score"
        ] if c in df.columns]
        st.dataframe(df.tail(120)[keep], hide_index=True, use_container_width=True)

with tab_roll:
    df = frames["rollover_c"]
    if df.empty:
        st.info("No V9.5C rollover event yet.")
    else:
        st.dataframe(df.tail(50), hide_index=True, use_container_width=True)

with tab_trades:
    if paper.empty:
        st.info("No paper trade telemetry.")
    else:
        keep = [c for c in [
            "timestamp","event","trade_id","ticker","side","entry_ask","exit_bid",
            "pnl","roi_pct","reason","mfe_pct","mae_pct","strategy","trade_intent"
        ] if c in paper.columns]
        st.dataframe(paper.tail(100)[keep], hide_index=True, use_container_width=True)

with tab_health:
    rows = []
    for key, filename in FILES.items():
        p = path_for(key)
        age = age_seconds(p)
        mode = "event-driven" if key in EVENT_DRIVEN else "continuous/active"
        status = "waiting for event" if key in EVENT_DRIVEN and not p.exists() else (
            "missing" if not p.exists() else "live" if age is not None and age < 20 else "idle"
        )
        rows.append({
            "feed": key, "mode": mode, "status": status, "file": filename,
            "age": human_age(age), "bytes": p.stat().st_size if p.exists() else 0
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("Event-driven feeds are not unhealthy merely because no file exists before their first event.")

st.caption(
    f"Rendered {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')} · READ ONLY"
)

if auto:
    time.sleep(refresh)
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()
