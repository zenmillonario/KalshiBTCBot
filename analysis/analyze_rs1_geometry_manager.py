from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

RUN_DIR = Path("runs/2026-09-20_v9_5a_rs1_entry_authority_router_shadow_01")
RS1 = RUN_DIR / "tachys_entry_authority_router_shadow_v9_5a_rs1.csv"
PAPER = RUN_DIR / "tachys_paper_trades_v9_2_6.csv"
RESULTS = RUN_DIR / "tachys_contract_results_v9_2_6.csv"
HANDOFF = RUN_DIR / "tachys_formation_handoff_v9_4i.csv"
ARCS = RUN_DIR / "tachys_ema_arcs_v9_4i.csv"

OUT_DIR = Path("analysis/rs1_geometry_manager_01")
OUT_REPORT = OUT_DIR / "rs1_geometry_manager_report.md"
OUT_TRADES = OUT_DIR / "rs1_geometry_trade_features.csv"
OUT_ROLLOVERS = OUT_DIR / "rs1_rollover_geometry.csv"

OBS_TICKER = "KXBTC15M-26SEP200315-15"


def read_csv(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def fnum(v) -> Optional[float]:
    try:
        if v in (None, ""):
            return None
        s = str(v).replace("$","").replace(",","").strip()
        x = float(s)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def ts(v: str, paper_local: bool = False) -> Optional[float]:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z","+00:00"))
        if d.tzinfo is None:
            from zoneinfo import ZoneInfo
            d = d.replace(tzinfo=ZoneInfo("America/New_York") if paper_local else timezone.utc)
        return d.timestamp()
    except Exception:
        return None


def write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in rows for k in r}) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def settlement_map(rows: List[dict]) -> dict:
    out = {}
    for r in rows:
        t = str(r.get("ticker") or "")
        result = str(r.get("result") or "").upper()
        if t and result in ("YES","NO"):
            out[t] = result
    return out


def pair_entries(paper: List[dict], start: float, end: float) -> List[dict]:
    exits = defaultdict(list)
    for r in paper:
        if r.get("event") != "EXIT":
            continue
        key = (r.get("trade_id"), r.get("ticker"), r.get("side"))
        x = ts(r.get("timestamp",""), True)
        if x is not None:
            exits[key].append((x,r))
    for vals in exits.values():
        vals.sort(key=lambda z:z[0])

    out = []
    for e in paper:
        if e.get("event") != "ENTRY":
            continue
        et = ts(e.get("timestamp",""), True)
        if et is None or et < start or et > end + 3:
            continue
        key = (e.get("trade_id"), e.get("ticker"), e.get("side"))
        xrow = None
        for xt,x in exits.get(key,[]):
            if xt >= et:
                xrow = x
                break
        out.append({"e":e,"x":xrow,"ts":et})
    return out


def nearest_proposal(e: dict, et: float, props: List[dict]) -> Optional[dict]:
    best = None
    bestdt = None
    ask = fnum(e.get("entry_ask"))
    for p in props:
        if p.get("ticker") != e.get("ticker") or p.get("side") != e.get("side"):
            continue
        pt = ts(p.get("timestamp",""), False)
        if pt is None:
            continue
        d = abs(pt-et)
        if d > 3:
            continue
        pa = fnum(p.get("proposal_ask"))
        if ask is not None and pa is not None and abs(ask-pa) > .021:
            continue
        if bestdt is None or d < bestdt:
            best,bestdt = p,d
    return best


def geometry(e: dict) -> dict:
    btc = fnum(e.get("btc_price"))
    ema9 = fnum(e.get("btc_ema_9_1m"))
    ema30 = fnum(e.get("btc_ema_30_1m"))
    target = fnum(e.get("target"))
    r60 = fnum(e.get("btc_range_60s"))

    pts = [x for x in (btc,ema9,ema30,target) if x is not None]
    span = max(pts)-min(pts) if len(pts)==4 else None
    span_norm = span/r60 if span is not None and r60 and r60 > 0 else None
    ema_gap = abs(ema9-ema30) if ema9 is not None and ema30 is not None else None
    pt_ema_center = abs(target-(ema9+ema30)/2) if target is not None and ema9 is not None and ema30 is not None else None
    price_pt = abs(btc-target) if btc is not None and target is not None else None
    target_inside_ema = ""
    price_inside_ema = ""
    if target is not None and ema9 is not None and ema30 is not None:
        lo,hi = sorted((ema9,ema30))
        target_inside_ema = int(lo <= target <= hi)
    if btc is not None and ema9 is not None and ema30 is not None:
        lo,hi = sorted((ema9,ema30))
        price_inside_ema = int(lo <= btc <= hi)

    return {
        "btc":btc,"ema9":ema9,"ema30":ema30,"target":target,"range60":r60,
        "pt_ema_price_span":span,"pt_ema_price_span_norm60":span_norm,
        "ema_gap_abs":ema_gap,"pt_to_ema_center_abs":pt_ema_center,
        "price_to_pt_abs":price_pt,"target_inside_ema_band":target_inside_ema,
        "price_inside_ema_band":price_inside_ema,
    }


def build_trade_features(rs: List[dict], paper: List[dict], results: dict, start: float, end: float) -> List[dict]:
    props = [r for r in rs if r.get("event")=="LEGACY_PROPOSAL_SHADOW"]
    rows = []
    for item in pair_entries(paper,start,end):
        e,x,et = item["e"],item["x"],item["ts"]
        p = nearest_proposal(e,et,props) or {}
        g = geometry(e)
        side = str(e.get("side") or "")
        settle = results.get(str(e.get("ticker") or ""),"")
        actual = fnum(x.get("pnl")) if x else None
        correct = int(side==settle) if settle in ("YES","NO") else ""
        qty = fnum(e.get("qty")) or 0
        ask = fnum(e.get("entry_ask"))
        hold = None
        if ask is not None and settle:
            hold = qty*((1-ask) if side==settle else -ask)
        rows.append({
            "trade_id":e.get("trade_id"),"ticker":e.get("ticker"),"side":side,
            "entry_ts":e.get("timestamp"),"entry_ask":ask,"actual_pnl":actual,
            "exit_reason":x.get("reason") if x else "","mfe_pct":fnum(x.get("mfe_pct")) if x else None,
            "mae_pct":fnum(x.get("mae_pct")) if x else None,
            "settlement_result":settle,"settlement_correct":correct,
            "hold_to_settlement_pnl":hold,
            "manager_leakage_vs_hold":(hold-actual) if hold is not None and actual is not None else None,
            "trade_intent":e.get("trade_intent"),"strategy":e.get("strategy"),
            "market_regime":e.get("market_regime"),
            "proposal_age_sec":fnum(p.get("recognition_age_sec")),
            "proposal_expired9":p.get("expired9",""),
            "battlefield":p.get("battlefield_class",""),"churn":p.get("churn_type",""),
            "dragon":p.get("dragon_state",""),"arc_phase":p.get("price_arc_phase",""),
            **g,
        })
    return rows


def tercile_labels(rows: List[dict], key: str) -> tuple[float,float]:
    vals = sorted(fnum(r.get(key)) for r in rows if fnum(r.get(key)) is not None)
    if len(vals)<3:
        return (float("nan"),float("nan"))
    return vals[len(vals)//3], vals[(2*len(vals))//3]


def summarize_group(rows: List[dict], label: str) -> str:
    pnls=[fnum(r.get("actual_pnl")) for r in rows if fnum(r.get("actual_pnl")) is not None]
    known=[r for r in rows if r.get("settlement_correct") not in ("",None)]
    corr=sum(int(r.get("settlement_correct") or 0) for r in known)
    wrong_mgmt=[r for r in rows if str(r.get("settlement_correct"))=="1" and (fnum(r.get("actual_pnl")) or 0)<0]
    leak=sum(fnum(r.get("manager_leakage_vs_hold")) or 0 for r in wrong_mgmt)
    return f"- {label}: N={len(rows)} PnL=${sum(pnls):+.2f} settlement={corr}/{len(known)} correct-side-losers={len(wrong_mgmt)} leakageVsHold=${leak:+.2f}"


def rollover_rows(handoff: List[dict], settlements: dict, start: float, end: float, trades: List[dict]) -> List[dict]:
    out=[]
    for r in handoff:
        if r.get("event")!="ROLLOVER_REMAP":
            continue
        rt=ts(r.get("timestamp",""),False)
        if rt is None or rt<start or rt>end:
            continue
        btc=fnum(r.get("btc_price")); e9=fnum(r.get("ema9")); e30=fnum(r.get("ema30")); pt=fnum(r.get("target"))
        pts=[x for x in (btc,e9,e30,pt) if x is not None]
        span=max(pts)-min(pts) if len(pts)==4 else None
        target_inside=""
        if pt is not None and e9 is not None and e30 is not None:
            lo,hi=sorted((e9,e30)); target_inside=int(lo<=pt<=hi)
        to_ticker=str(r.get("to_ticker") or "")
        future=[t for t in trades if t.get("ticker")==to_ticker and (ts(t.get("entry_ts",""),True) or -1)>=rt]
        future.sort(key=lambda t: ts(t.get("entry_ts",""),True) or 10**20)
        first=future[0] if future else None
        first_delay=(ts(first["entry_ts"],True)-rt) if first else None
        out.append({
            "timestamp":r.get("timestamp"),"from_ticker":r.get("from_ticker"),"to_ticker":to_ticker,
            "formation_continuity":r.get("formation_continuity"),
            "inherited_formation":r.get("inherited_formation"),"inherited_maturity":r.get("inherited_maturity"),
            "inherited_regime":r.get("inherited_regime"),"inherited_macro":r.get("inherited_macro"),
            "current_formation":r.get("current_formation"),"current_maturity":r.get("current_maturity"),
            "current_regime":r.get("current_regime"),"current_macro":r.get("current_macro"),
            "target":pt,"btc":btc,"ema9":e9,"ema30":e30,"pt_ema_price_span":span,
            "target_inside_ema_band":target_inside,"yes_ask":r.get("yes_ask"),"no_ask":r.get("no_ask"),
            "settlement_result":settlements.get(to_ticker,""),
            "first_trade_id":first.get("trade_id") if first else "",
            "first_trade_side":first.get("side") if first else "",
            "first_trade_delay_sec":round(first_delay,3) if first_delay is not None else "",
            "first_trade_pnl":first.get("actual_pnl") if first else "",
        })
    return out


def arc_window(arcs: List[dict], start: float, end: float) -> List[dict]:
    out=[]
    for r in arcs:
        et=ts(r.get("end_time",""),False)
        if et is not None and start<=et<=end:
            out.append(r)
    return out


def main() -> None:
    rs=read_csv(RS1); paper=read_csv(PAPER); result_rows=read_csv(RESULTS)
    handoff=read_csv(HANDOFF); arcs=read_csv(ARCS)
    times=[ts(r.get("timestamp",""),False) for r in rs]
    times=[x for x in times if x is not None]
    start,end=min(times),max(times)
    results=settlement_map(result_rows)

    trades=build_trade_features(rs,paper,results,start,end)
    q1,q2=tercile_labels(trades,"pt_ema_price_span_norm60")
    for r in trades:
        v=fnum(r.get("pt_ema_price_span_norm60"))
        if v is None:
            r["geometry_tercile"]="UNKNOWN"
        elif v<=q1:
            r["geometry_tercile"]="TIGHTEST_THIRD"
        elif v<=q2:
            r["geometry_tercile"]="MIDDLE_THIRD"
        else:
            r["geometry_tercile"]="WIDEST_THIRD"

    rolls=rollover_rows(handoff,results,start,end,trades)
    run_arcs=arc_window(arcs,start,end)

    correct_losers=[r for r in trades if str(r.get("settlement_correct"))=="1" and (fnum(r.get("actual_pnl")) or 0)<0]
    leakage=sum(fnum(r.get("manager_leakage_vs_hold")) or 0 for r in correct_losers)

    lines=[
        "# RS1 Geometry + Manager Forensics",
        "",
        "This pass tests the user's PT/EMA/price encounter idea using existing telemetry only. No new detector and no authority change.",
        "",
        "## Direction vs management",
        "",
        f"- RS1 trades: {len(trades)}",
        f"- Correct settlement side but realized loss: {len(correct_losers)}",
        f"- Aggregate counterfactual improvement if those individual trades had instead been held to settlement: ${leakage:+.2f}",
        "",
        "### Correct-side losing trades by exit reason",
        "",
    ]
    byexit=defaultdict(list)
    for r in correct_losers: byexit[r.get("exit_reason") or "(blank)"].append(r)
    for k,v in sorted(byexit.items(), key=lambda z:(-len(z[1]),z[0])):
        lines.append(summarize_group(v,k))

    lines += ["","## PT-EMA-price geometry at entry","",
              f"Normalized span tercile cut points: tight <= {q1:.3f}, middle <= {q2:.3f}, widest > {q2:.3f}",
              ""]
    for label in ("TIGHTEST_THIRD","MIDDLE_THIRD","WIDEST_THIRD","UNKNOWN"):
        grp=[r for r in trades if r.get("geometry_tercile")==label]
        if grp: lines.append(summarize_group(grp,label))

    lines += ["","### Exact EMA-band relationships",""]
    for key in ("target_inside_ema_band","price_inside_ema_band"):
        yes=[r for r in trades if str(r.get(key))=="1"]
        no=[r for r in trades if str(r.get(key))=="0"]
        lines.append(summarize_group(yes,f"{key}=1"))
        lines.append(summarize_group(no,f"{key}=0"))

    lines += ["","## Swirl/compression manager check",""]
    for key,val in [
        ("battlefield","COMPRESSION_STORM"),
        ("churn","COMPRESSION_CHURN"),
        ("dragon","DRAGONS_SWIRLING"),
        ("dragon","DRAGONS_ENTANGLED"),
    ]:
        grp=[r for r in trades if r.get(key)==val]
        lines.append(summarize_group(grp,f"{key}:{val}"))

    obs=[r for r in trades if r.get("ticker")==OBS_TICKER]
    lines += ["",f"## Watched contract {OBS_TICKER}",""]
    for r in obs:
        lines.append(
            f"- #{r['trade_id']} {r['side']} @{r['entry_ask']} actual=${(fnum(r.get('actual_pnl')) or 0):+.2f} "
            f"settle={r['settlement_result']} hold=${(fnum(r.get('hold_to_settlement_pnl')) or 0):+.2f} "
            f"span={r.get('pt_ema_price_span')} norm60={r.get('pt_ema_price_span_norm60')} "
            f"EMA-gap={r.get('ema_gap_abs')} PT-center={r.get('pt_to_ema_center_abs')} "
            f"battle={r.get('battlefield')} churn={r.get('churn')} dragon={r.get('dragon')} exit={r.get('exit_reason')}"
        )

    lines += ["","## Rollover continuity","",
              f"- ROLLOVER_REMAP events in RS1 window: {len(rolls)}",
              f"- New PT landed inside EMA9/EMA30 band: {sum(1 for r in rolls if str(r.get('target_inside_ema_band'))=='1')}/{len(rolls)}",
              ""]
    cont=Counter(r.get("formation_continuity") or "(blank)" for r in rolls)
    for k,v in cont.most_common():
        lines.append(f"- {k}: {v}")

    lines += ["","## Existing mountain/arc telemetry","",
              f"- Completed EMA arcs in RS1 window: {len(run_arcs)}"]
    seq=Counter()
    prog=Counter()
    for r in run_arcs:
        c=fnum(r.get("sequence_count"))
        if c is None: seq["UNKNOWN"]+=1
        elif c>=4: seq["4+"]+=1
        else: seq[str(int(c))]+=1
        prog[str(r.get("crest_progression") or "NONE")]+=1
    for k in ("1","2","3","4+","UNKNOWN"):
        if seq[k]: lines.append(f"- sequence_count {k}: {seq[k]}")
    lines.append("")
    lines.append("Crest progression:")
    for k,v in prog.most_common():
        lines.append(f"- {k}: {v}")

    lines += ["","## Discipline","",
              "- Geometry terciles are descriptive rank buckets, not proposed thresholds.",
              "- Hold-to-settlement is a manager diagnostic, not a recommendation to hold every trade.",
              "- Rollover preserves the underlying BTC/EMA formation; this report treats the new PT as a remap, not a reset.",
              "- Existing arc sequence_count / crest_progression telemetry is used as the first machine proxy for the 'little mountains'; no separate mountain detector is introduced here.",
              ""]

    OUT_DIR.mkdir(parents=True,exist_ok=True)
    write_csv(OUT_TRADES,trades)
    write_csv(OUT_ROLLOVERS,rolls)
    OUT_REPORT.write_text("\n".join(lines),encoding="utf-8")

    print(f"RS1 trades={len(trades)} correct-side-losers={len(correct_losers)}")
    print(f"rollovers={len(rolls)} completed_arcs={len(run_arcs)}")
    print(f"WROTE {OUT_TRADES}")
    print(f"WROTE {OUT_ROLLOVERS}")
    print(f"WROTE {OUT_REPORT}")


if __name__=="__main__":
    main()
