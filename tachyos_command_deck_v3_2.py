r"""
TACHYOS COMMAND DECK V3.2 — CAMPAIGN COCKPIT / LEG GEOMETRY
==========================================================
READ ONLY. No Tachyos imports. No API calls. No trading writes.
"""

from __future__ import annotations

import csv
import html
import io
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

APP_VERSION = "Command Deck V3.2"
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
    "campaign": "tachys_campaign_authority_v9_5d.csv",
    "winner": "tachys_winner_harvest_v9_5d.csv",
    "exit_court": "tachys_exit_court_v9_5d.csv",
    "prearm": "tachys_prearm_lifecycle_v9_5d.csv",
    "manifest_d": "tachys_run_manifest_v9_5d.csv",
}

EVENT_DRIVEN = {"exit", "rollover_c", "reentry", "battle_memory", "winner", "exit_court", "prearm"}

st.set_page_config(
    page_title="Tachyos Command Deck V3.2",
    page_icon="🧱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {
          padding-top: .25rem;
          padding-bottom: 1.6rem;
          max-width: 100%;
      }
      header[data-testid="stHeader"] {height: 2.2rem;}
      [data-testid="stMetric"] {
          border: 1px solid rgba(128,128,128,.24);
          border-radius: 9px;
          padding: 8px 10px;
          background: rgba(128,128,128,.045);
      }
      [data-testid="stMetricLabel"] {font-size: .78rem;}
      [data-testid="stMetricValue"] {font-size: 1.55rem;}
      .deck-banner {
          border-bottom: 1px solid rgba(128,128,128,.28);
          padding: 2px 2px 7px 2px;
          margin-bottom: 8px;
      }
      .deck-title {
          font-size: 1.18rem;
          font-weight: 800;
          letter-spacing: .02em;
      }
      .small-note {
          opacity: .70;
          font-size: .77rem;
      }
      .position-box {
          border: 1px solid rgba(128,128,128,.28);
          border-radius: 12px;
          padding: 14px 16px;
          background: rgba(128,128,128,.045);
          margin-bottom: 10px;
      }
      .position-title {
          font-size: .82rem;
          opacity: .75;
          margin-bottom: 2px;
      }
      .position-head {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 22px;
          align-items: start;
      }
      .position-main {
          font-size: 2.15rem;
          line-height: 1.05;
          font-weight: 850;
      }
      .position-pnl-wrap {
          text-align: right;
          min-width: 180px;
      }
      .position-pnl-label {
          font-size: .76rem;
          opacity: .66;
          margin-bottom: 2px;
      }
      .position-pnl {
          font-size: 2.15rem;
          line-height: 1.05;
          font-weight: 900;
          white-space: nowrap;
      }
      .pnl-positive {color: #33d17a;}
      .pnl-negative {color: #ff5c5c;}
      .pnl-flat {color: #c7c7c7;}
      .position-details {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
          margin-top: 14px;
          padding-top: 10px;
          border-top: 1px solid rgba(128,128,128,.16);
      }
      .position-detail-label {
          font-size: .72rem;
          opacity: .62;
          margin-bottom: 1px;
      }
      .position-detail-value {
          font-size: .98rem;
          font-weight: 700;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
      }
      .position-sub {
          margin-top: 8px;
          font-size: .90rem;
          line-height: 1.4;
          opacity: .82;
      }
      .recent-title {
          font-size: 1.08rem;
          font-weight: 750;
          margin: 6px 0 5px 0;
      }
      .recent-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 1.00rem;
      }
      .recent-table th {
          text-align: left;
          opacity: .68;
          font-size: .78rem;
          padding: 5px 6px;
          border-bottom: 1px solid rgba(128,128,128,.25);
      }
      .recent-table td {
          padding: 7px 6px;
          border-bottom: 1px solid rgba(128,128,128,.13);
          vertical-align: top;
      }
      .reason-cell {
          font-size: .84rem;
          opacity: .82;
          max-width: 250px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
      }
      .win {font-weight: 800; color: #33d17a;}
      .loss {font-weight: 800; color: #ff5c5c;}
      .section-rule {
          margin: 10px 0 5px 0;
          border-top: 1px solid rgba(128,128,128,.22);
      }
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


def live_mark(open_trade, quote_row):
    if open_trade is None or quote_row is None:
        return None
    side = txt(open_trade.get("side"), "")
    entry = num(open_trade.get("entry_ask"))
    qty = num(open_trade.get("qty"))
    yes_ask = num(quote_row.get("yes_ask"))
    no_ask = num(quote_row.get("no_ask"))
    if side == "YES" and no_ask is not None:
        bid = 1.0 - no_ask
    elif side == "NO" and yes_ask is not None:
        bid = 1.0 - yes_ask
    else:
        return None
    if entry is None:
        return None
    pnl = None if qty is None else qty * (bid-entry)
    roi = None if entry == 0 else (bid-entry)/entry
    return {"bid": bid, "pnl": pnl, "roi": roi}


def recent_trade_table(exits: pd.DataFrame, count: int = 7) -> str:
    if exits.empty:
        return '<div class="small-note">No completed trades yet.</div>'
    rows = []
    for _, r in exits.tail(count).iloc[::-1].iterrows():
        pnl = num(r.get("pnl"))
        css = "win" if pnl is not None and pnl > 0 else "loss" if pnl is not None and pnl < 0 else ""
        reason = html.escape(txt(r.get("reason"), ""))
        if len(reason) > 34:
            reason = reason[:31] + "..."
        rows.append(
            "<tr>"
            f"<td>#{html.escape(txt(r.get('trade_id')))}</td>"
            f"<td><b>{html.escape(txt(r.get('side')))}</b></td>"
            f"<td>{quote(r.get('entry_ask'))}</td>"
            f"<td>{quote(r.get('exit_bid'))}</td>"
            f"<td class='{css}'>{money(pnl)}</td>"
            f"<td class='reason-cell'>{reason}</td>"
            "</tr>"
        )
    return (
        '<table class="recent-table">'
        "<thead><tr><th>#</th><th>Side</th><th>Entry</th><th>Exit</th><th>P/L</th><th>Reason</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


@st.cache_data(ttl=.35, show_spinner=False)
def load_frames(_stamp: int):
    return {
        key: read_tail(path_for(key), 1500 if key in ("leg","tactical","exit") else 600)
        for key in FILES
    }


with st.sidebar:
    st.markdown("## 🧱 Command Deck")
    st.caption(f"{APP_VERSION} · READ ONLY")
    st.markdown("EMA30 = **Spine**  \nEMA9 = **Leg Geometry**")
    auto = st.toggle("Auto refresh", True)
    refresh = st.slider("Refresh every", 1, 10, 2)
    chart_rows = st.slider("Chart samples", 180, 1800, 900, step=180)
    recent_count = st.slider("Recent trades", 4, 10, 7)
    st.divider()
    st.code(str(BASE_DIR), language=None)


frames = load_frames(int(time.time()*2))
leg = latest(frames["leg"])
tactical = frames["tactical"]
exit_row = latest(frames["exit"])
campaign_row = latest(frames["campaign"])
winner_row = latest(frames["winner"])
exit_court_row = latest(frames["exit_court"])
prearm_row = latest(frames["prearm"])
paper = frames["paper"].copy()
quote_row, quote_source, quote_age = discover_quote()

current_ticker = txt(leg.get("ticker") if leg is not None else None)

# Paper position + completed trades
open_trade = None
exits = pd.DataFrame()
if not paper.empty and "event" in paper.columns and {"ticker","trade_id"}.issubset(paper.columns):
    paper["_event"] = paper["event"].astype(str).str.upper()
    paper["_key"] = paper["ticker"].astype(str) + ":" + paper["trade_id"].astype(str)
    exits = paper[paper["_event"]=="EXIT"].copy()
    exited_keys = set(exits["_key"])
    entries = paper[(paper["_event"]=="ENTRY") & (~paper["_key"].isin(exited_keys))]
    open_trade = latest(entries)

mark = live_mark(open_trade, quote_row)

# Latest YES/NO tactical states
yes_row = no_row = None
if not tactical.empty and "ticker" in tactical.columns and "side" in tactical.columns:
    cur = tactical[tactical["ticker"].astype(str) == str(current_ticker)]
    yes_row = latest(cur[cur["side"].astype(str) == "YES"])
    no_row = latest(cur[cur["side"].astype(str) == "NO"])

st.markdown(
    f"""
    <div class="deck-banner">
      <div class="deck-title">🧱 TACHYOS COMMAND DECK · {current_ticker}</div>
      <div class="small-note">READ ONLY · {APP_VERSION} · V9.5C LEG GEOMETRY</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# TOP COCKPIT: POSITION + RECENT TRADES LEFT / SQUARE CHART RIGHT
# ---------------------------------------------------------------------------

left, right = st.columns([0.48, 0.52], gap="large")

with left:
    st.markdown("### Current Position")
    if open_trade is None:
        st.markdown(
            """
            <div class="position-box">
              <div class="position-title">PAPER POSITION</div>
              <div class="position-main">NO OPEN POSITION</div>
              <div class="position-sub">Waiting for the next authorized leg entry.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        side = txt(open_trade.get("side"))
        trade_id = txt(open_trade.get("trade_id"))
        entry = quote(open_trade.get("entry_ask"))
        qty = txt(open_trade.get("qty"))
        strategy = html.escape(txt(open_trade.get("strategy")))
        intent = html.escape(txt(open_trade.get("trade_intent")))
        live_bid = quote(mark.get("bid")) if mark else "—"
        live_pnl_value = mark.get("pnl") if mark else None
        live_roi_value = mark.get("roi") if mark else None
        live_pnl = money(live_pnl_value) if mark else "—"
        live_roi = "—" if live_roi_value is None else f"{live_roi_value:+.1%}"
        pnl_class = (
            "pnl-positive" if live_pnl_value is not None and live_pnl_value > 0
            else "pnl-negative" if live_pnl_value is not None and live_pnl_value < 0
            else "pnl-flat"
        )
        gate = (
            txt(exit_court_row.get("court_ruling"))
            if exit_court_row is not None and txt(exit_court_row.get("trade_id"), "") == trade_id
            else txt(exit_row.get("gate_ruling")) if exit_row is not None and txt(exit_row.get("trade_id"), "") == trade_id
            else "—"
        )

        st.markdown(
            f"""
            <div class="position-box">
              <div class="position-title">TRADE #{html.escape(trade_id)}</div>
              <div class="position-head">
                <div>
                  <div class="position-main">{html.escape(side)} · ENTRY {entry}</div>
                  <div class="position-sub">{strategy} · {intent}</div>
                </div>
                <div class="position-pnl-wrap">
                  <div class="position-pnl-label">LIVE P/L</div>
                  <div class="position-pnl {pnl_class}">{live_pnl} · {live_roi}</div>
                </div>
              </div>
              <div class="position-details">
                <div>
                  <div class="position-detail-label">LIVE BID</div>
                  <div class="position-detail-value">{live_bid}</div>
                </div>
                <div>
                  <div class="position-detail-label">QTY</div>
                  <div class="position-detail-value">{html.escape(qty)}</div>
                </div>
                <div>
                  <div class="position-detail-label">EXIT GATE</div>
                  <div class="position-detail-value">{html.escape(gate)}</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if quote_source:
        st.caption(f"Live quote: {quote_source} · {human_age(quote_age)}")

    st.markdown('<div class="recent-title">Recent Trades</div>', unsafe_allow_html=True)
    st.markdown(recent_trade_table(exits, recent_count), unsafe_allow_html=True)

with right:
    st.markdown("### Geometry Relative to Target")
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
            st.line_chart(rel, use_container_width=True, height=535)
            st.caption("Dollars above/below Kalshi target. Target = zero. Contract rollover remains a fencepost, not a geometry reset.")
        else:
            st.info("Target-relative chart waiting for target + EMA columns.")

st.markdown('<div class="section-rule"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# LOWER COCKPIT: LEG / TACTICAL / EXIT REASONING
# ---------------------------------------------------------------------------

st.markdown("## Campaign Authority")

if campaign_row is None:
    st.info("Waiting for V9.5D Campaign Authority telemetry.")
else:
    cp = st.columns(8)
    cp[0].metric("Campaign Side", txt(campaign_row.get("campaign_side")))
    cp[1].metric("Campaign State", txt(campaign_row.get("campaign_state")))
    cp[2].metric("Candidate", txt(campaign_row.get("candidate_side")))
    cp[3].metric("Candidate Age", secs(campaign_row.get("candidate_age_sec")))
    cp[4].metric("Flip Count", txt(campaign_row.get("flip_count")))
    cp[5].metric("YES Score", txt(campaign_row.get("yes_score")))
    cp[6].metric("NO Score", txt(campaign_row.get("no_score")))
    cp[7].metric("369 Align", txt(campaign_row.get("aligned_369_count")))
    st.caption(
        f"Campaign {txt(campaign_row.get('campaign_id'))} · "
        f"Leg {txt(campaign_row.get('leg_side'))}/{txt(campaign_row.get('leg_state'))} · "
        f"Target {money(campaign_row.get('target_height'))} · "
        f"{txt(campaign_row.get('reasons'), '')}"
    )

st.markdown("## Pre-Arm / Winner Harvest")

pw = st.columns(8)
pw[0].metric("Pre-Arm", "—" if prearm_row is None else txt(prearm_row.get("prearm_side")))
pw[1].metric("Pre-Arm State", "—" if prearm_row is None else txt(prearm_row.get("state")))
pw[2].metric("Pre-Arm Age", "—" if prearm_row is None else secs(prearm_row.get("age_sec")))
pw[3].metric("Use Count", "—" if prearm_row is None else txt(prearm_row.get("use_count")))
pw[4].metric("Winner State", "—" if winner_row is None else txt(winner_row.get("winner_state")))
pw[5].metric("Winner MFE", "—" if winner_row is None or num(winner_row.get("mfe_pct")) is None else f"{num(winner_row.get('mfe_pct')):+.1f}%")
pw[6].metric("Since MFE High", "—" if winner_row is None else secs(winner_row.get("seconds_since_mfe_high")))
pw[7].metric("Harvest Ruling", "—" if winner_row is None else txt(winner_row.get("ruling")))

st.markdown("## Exit Court")

if exit_court_row is None:
    st.info("No V9.5D Exit Court event yet.")
else:
    ec = st.columns(7)
    ec[0].metric("Trade", f"#{txt(exit_court_row.get('trade_id'))} {txt(exit_court_row.get('side'))}")
    ec[1].metric("Court Ruling", txt(exit_court_row.get("court_ruling")))
    ec[2].metric("Final Action", txt(exit_court_row.get("final_action")))
    ec[3].metric("ROI", "—" if num(exit_court_row.get("roi_pct")) is None else f"{num(exit_court_row.get('roi_pct')):+.1f}%")
    ec[4].metric("MFE", "—" if num(exit_court_row.get("mfe_pct")) is None else f"{num(exit_court_row.get('mfe_pct')):+.1f}%")
    ec[5].metric("Campaign", txt(exit_court_row.get("campaign_side")))
    ec[6].metric("Winner", txt(exit_court_row.get("winner_state")))
    st.caption(txt(exit_court_row.get("reasons"), ""))

st.markdown("## Leg Geometry")

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

st.markdown("## Dual-Side Tactical Authority")
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

st.markdown("## V9.5C Underlay Exit Telemetry")
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

# ---------------------------------------------------------------------------
# DETAIL TABS
# ---------------------------------------------------------------------------

tab_campaign, tab_winner, tab_court, tab_prearm, tab_leg, tab_tactical, tab_exit, tab_roll, tab_trades, tab_health = st.tabs(
    ["Campaign","Winner Harvest","Exit Court","Pre-Arm","Leg Timeline","Tactical YES/NO","V9.5C Exit","Rollover","All Trades","Feed Health"]
)

with tab_campaign:
    df = frames["campaign"]
    if df.empty:
        st.info("Waiting for Campaign Authority telemetry.")
    else:
        st.dataframe(df.tail(140), hide_index=True, use_container_width=True, height=420)

with tab_winner:
    df = frames["winner"]
    if df.empty:
        st.info("No Winner Harvest telemetry yet.")
    else:
        st.dataframe(df.tail(140), hide_index=True, use_container_width=True, height=420)

with tab_court:
    df = frames["exit_court"]
    if df.empty:
        st.info("No V9.5D Exit Court telemetry yet.")
    else:
        st.dataframe(df.tail(140), hide_index=True, use_container_width=True, height=420)

with tab_prearm:
    df = frames["prearm"]
    if df.empty:
        st.info("No V9.5D Pre-Arm lifecycle event yet.")
    else:
        st.dataframe(df.tail(100), hide_index=True, use_container_width=True, height=420)

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
        st.dataframe(df.tail(100)[keep], hide_index=True, use_container_width=True, height=420)

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
        st.dataframe(df.tail(120)[keep], hide_index=True, use_container_width=True, height=420)

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
        st.dataframe(df.tail(120)[keep], hide_index=True, use_container_width=True, height=420)

with tab_roll:
    df = frames["rollover_c"]
    if df.empty:
        st.info("No V9.5C rollover event yet.")
    else:
        st.dataframe(df.tail(50), hide_index=True, use_container_width=True, height=420)

with tab_trades:
    if paper.empty:
        st.info("No paper trade telemetry.")
    else:
        keep = [c for c in [
            "timestamp","event","trade_id","ticker","side","entry_ask","exit_bid",
            "pnl","roi_pct","reason","mfe_pct","mae_pct","strategy","trade_intent"
        ] if c in paper.columns]
        st.dataframe(paper.tail(120)[keep], hide_index=True, use_container_width=True, height=440)

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
            "feed": key,
            "mode": mode,
            "status": status,
            "file": filename,
            "age": human_age(age),
            "bytes": p.stat().st_size if p.exists() else 0,
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
