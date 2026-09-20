from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Tuple

import replay_entry_authority_router_v3_hard_release as v3
import replay_entry_authority_router_v4_release_economics as v4

RUN_DIRS = v4.RUN_DIRS
V3_FEATURES = v4.V3_FEATURES

OUT_DIR = Path("analysis/router_v5_epoch_transfer_replay")
OUT_FEATURES = OUT_DIR / "router_v5_epoch_transfer_features.csv"
OUT_SUMMARY = OUT_DIR / "router_v5_epoch_transfer_summary.csv"
OUT_REPORT = OUT_DIR / "router_v5_epoch_transfer_report.md"

# Epoch-reset-capable events are intentionally narrower than V3 "hard release".
# These are explicit battlefield authority/territory state transitions.
EPOCH_TRANSFER_SOURCES = {
    "HAND_AUTHORITY_TRANSFER",
    "BOUNDARY_RELEASE",
}

FEATURE_FIELDS = [
    "run_label","trade_id","ticker",
    "stale_side","historical_entry_ask","historical_pnl",
    "prevalidation_delay_sec","ask_inflation_from_first_cents",
    "settlement_result","settlement_correct_for_stale_side",
    "transfer_found","transfer_side","transfer_relation",
    "transfer_source","transfer_ts","transfer_delay_sec","transfer_detail",
    "transfer_quote_ts","transfer_quote_distance_sec","transfer_quote_source",
    "transfer_yes_ask","transfer_no_ask","transfer_side_ask",
    "entry_seconds_left","transfer_seconds_left_est",
    "transfer_price_bin","transfer_time_left_bin","transfer_delay_bin",
    "under_existing_80c_cap",
    "settlement_correct_for_transfer_side",
    "settlement_hold_roi","settlement_hold_pnl_10",
]

SUMMARY_FIELDS = [
    "run_label","group_type","group_value","n","transfer_n","quote_n",
    "settlement_known","settlement_correct","settlement_accuracy",
    "avg_transfer_ask","avg_transfer_delay_sec","avg_seconds_left",
    "settlement_hold_pnl_10_sum","settlement_hold_roi_avg",
]


def fnum(v) -> Optional[float]:
    try:
        if v in (None, ""):
            return None
        x=float(v)
        return None if math.isnan(x) else x
    except Exception:
        return None


def read_csv(path: Path) -> List[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r",newline="",encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def transfer_relation(stale_side: str, transfer_side: str) -> str:
    if not transfer_side:
        return "NO_TRANSFER"
    return "SAME_SIDE_CONTINUATION_RESET" if transfer_side == stale_side else "OPPOSITE_SIDE_REVERSAL_RESET"


def price_bin(v: Optional[float]) -> str:
    if v is None:
        return "NO_QUOTE"
    if v < .40:
        return "LT40C"
    if v < .55:
        return "40_55C"
    if v < .70:
        return "55_70C"
    if v <= .80:
        return "70_80C"
    return "GT80C"


def left_bin(v: Optional[float]) -> str:
    if v is None:
        return "UNKNOWN"
    if v < 60:
        return "LT60S"
    if v < 180:
        return "60_180S"
    if v < 300:
        return "180_300S"
    return "GE300S"


def delay_bin(v: Optional[float]) -> str:
    if v is None:
        return "NO_TRANSFER"
    if v <= 9:
        return "LE9S"
    if v <= 30:
        return "9_30S"
    if v <= 90:
        return "30_90S"
    if v <= 180:
        return "90_180S"
    return "GT180S"


def load_epoch_transfer_events(run_dir: Path) -> List[dict]:
    data={k:v3.read_csv(run_dir/fn) for k,fn in v3.FILES.items()}
    events=v3.build_hard_events(data)
    return [e for e in events if e.get("source") in EPOCH_TRANSFER_SOURCES]


def first_transfer(events: List[dict], ticker: str, start_ts: float, end_ts: float) -> Optional[dict]:
    for ev in events:
        if ev["ts"] <= start_ts:
            continue
        if ev["ts"] > end_ts:
            break
        if ev.get("ticker") == ticker:
            return ev
    return None


def build_features() -> List[dict]:
    rows=read_csv(V3_FEATURES)
    selected=[
        r for r in rows
        if str(r.get("stale9")) == "1"
        and r.get("initial_state") == "PULLBACK_WAIT"
    ]

    by_run=defaultdict(list)
    for r in selected:
        by_run[r["run_label"]].append(r)

    out=[]
    for run_label, items in by_run.items():
        run_dir=RUN_DIRS.get(run_label)
        if run_dir is None or not run_dir.exists():
            print(f"SKIP missing run {run_label}")
            continue

        events=load_epoch_transfer_events(run_dir)
        paper=v4.load_paper_entries(run_dir)

        targets=[]
        staging=[]
        for r in items:
            tid=str(r.get("trade_id") or "")
            ticker=str(r.get("ticker") or "")
            p=paper.get((tid,ticker),{})
            entry_ts=v3.parse_ts(r.get("paper_entry_ts",""),paper_local=True)
            entry_left=fnum(p.get("seconds_to_close"))
            if entry_left is None:
                entry_left=fnum(p.get("seconds_left"))

            end_ts=None
            if entry_ts is not None and entry_left is not None:
                end_ts=entry_ts+max(0.0,entry_left)

            ev=None
            if entry_ts is not None and end_ts is not None:
                ev=first_transfer(events,ticker,entry_ts,end_ts)

            s={"row":r,"paper":p,"entry_ts":entry_ts,"entry_left":entry_left,"event":ev}
            staging.append(s)
            if ev:
                targets.append({
                    "run_label":run_label,
                    "trade_id":tid,
                    "ticker":ticker,
                    "_release_epoch":ev["ts"],
                })

        quote_map=v4.scan_quotes(run_dir,targets) if targets else {}
        print(f"{run_label}: stale pullbacks={len(items)} epoch-transfers={sum(1 for s in staging if s['event'])}")

        for s in staging:
            r=s["row"]; ev=s["event"]; entry_ts=s["entry_ts"]; entry_left=s["entry_left"]
            tid=str(r.get("trade_id") or "")
            ticker=str(r.get("ticker") or "")
            stale_side=str(r.get("side") or "")

            q=None
            if ev:
                q=quote_map.get((run_label,tid,ticker))

            transfer_side=str(ev.get("side") or "") if ev else ""
            release_ask=None
            if q and transfer_side:
                release_ask=q.get("yes_ask") if transfer_side=="YES" else q.get("no_ask")

            delay=None
            if ev and entry_ts is not None:
                delay=ev["ts"]-entry_ts

            left=None
            if entry_left is not None and delay is not None:
                left=max(0.0,entry_left-delay)

            settlement=str(r.get("settlement_result") or "")
            correct_transfer=""
            hold_roi=None
            hold_pnl=None
            if transfer_side and settlement in ("YES","NO"):
                correct_transfer=int(transfer_side==settlement)
                if release_ask is not None and release_ask > 0:
                    hold_roi=((1.0-release_ask)/release_ask) if transfer_side==settlement else -1.0
                    hold_pnl=10.0*hold_roi

            out.append({
                "run_label":run_label,
                "trade_id":tid,
                "ticker":ticker,
                "stale_side":stale_side,
                "historical_entry_ask":r.get("entry_ask",""),
                "historical_pnl":r.get("actual_pnl",""),
                "prevalidation_delay_sec":r.get("prevalidation_delay_sec",""),
                "ask_inflation_from_first_cents":r.get("ask_inflation_from_first_cents",""),
                "settlement_result":settlement,
                "settlement_correct_for_stale_side":r.get("settlement_correct",""),
                "transfer_found":int(ev is not None),
                "transfer_side":transfer_side,
                "transfer_relation":transfer_relation(stale_side,transfer_side),
                "transfer_source":ev.get("source","") if ev else "",
                "transfer_ts":ev.get("timestamp","") if ev else "",
                "transfer_delay_sec":round(delay,3) if delay is not None else "",
                "transfer_detail":ev.get("detail","") if ev else "",
                "transfer_quote_ts":q.get("timestamp","") if q else "",
                "transfer_quote_distance_sec":round(q.get("distance"),3) if q else "",
                "transfer_quote_source":q.get("source","") if q else "",
                "transfer_yes_ask":q.get("yes_ask","") if q else "",
                "transfer_no_ask":q.get("no_ask","") if q else "",
                "transfer_side_ask":release_ask if release_ask is not None else "",
                "entry_seconds_left":entry_left if entry_left is not None else "",
                "transfer_seconds_left_est":round(left,3) if left is not None else "",
                "transfer_price_bin":price_bin(release_ask),
                "transfer_time_left_bin":left_bin(left),
                "transfer_delay_bin":delay_bin(delay),
                "under_existing_80c_cap":int(release_ask is not None and release_ask <= .80),
                "settlement_correct_for_transfer_side":correct_transfer,
                "settlement_hold_roi":round(hold_roi,6) if hold_roi is not None else "",
                "settlement_hold_pnl_10":round(hold_pnl,4) if hold_pnl is not None else "",
            })

    return out


def summarize(rows: List[dict], run_label: str, group_type: str, key: str) -> List[dict]:
    groups=defaultdict(list)
    for r in rows:
        value=r.get(key)
        groups[str(value if value not in ("",None) else "(blank)")].append(r)

    out=[]
    for value,items in sorted(groups.items()):
        transfers=[x for x in items if str(x.get("transfer_found"))=="1"]
        quoted=[x for x in transfers if fnum(x.get("transfer_side_ask")) is not None]
        settled=[x for x in transfers if x.get("settlement_correct_for_transfer_side") not in ("",None)]
        correct=sum(int(x.get("settlement_correct_for_transfer_side") or 0) for x in settled)
        asks=[fnum(x.get("transfer_side_ask")) for x in quoted]
        asks=[x for x in asks if x is not None]
        delays=[fnum(x.get("transfer_delay_sec")) for x in transfers]
        delays=[x for x in delays if x is not None]
        lefts=[fnum(x.get("transfer_seconds_left_est")) for x in transfers]
        lefts=[x for x in lefts if x is not None]
        rois=[fnum(x.get("settlement_hold_roi")) for x in quoted]
        rois=[x for x in rois if x is not None]
        pnls=[fnum(x.get("settlement_hold_pnl_10")) for x in quoted]
        pnls=[x for x in pnls if x is not None]

        out.append({
            "run_label":run_label,
            "group_type":group_type,
            "group_value":value,
            "n":len(items),
            "transfer_n":len(transfers),
            "quote_n":len(quoted),
            "settlement_known":len(settled),
            "settlement_correct":correct,
            "settlement_accuracy":round(correct/len(settled),4) if settled else "",
            "avg_transfer_ask":round(mean(asks),4) if asks else "",
            "avg_transfer_delay_sec":round(mean(delays),3) if delays else "",
            "avg_seconds_left":round(mean(lefts),3) if lefts else "",
            "settlement_hold_pnl_10_sum":round(sum(pnls),3) if pnls else "",
            "settlement_hold_roi_avg":round(mean(rois),4) if rois else "",
        })
    return out


def write_csv(path: Path, rows: List[dict], fields: List[str]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=fields,extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def report_group(lines: List[str], rows: List[dict], title: str, key: str) -> None:
    groups=defaultdict(list)
    for r in rows:
        v=r.get(key)
        groups[str(v if v not in ("",None) else "(blank)")].append(r)
    lines.extend([f"## {title}",""])
    for value,items in sorted(groups.items()):
        transfers=[x for x in items if str(x.get("transfer_found"))=="1"]
        quoted=[x for x in transfers if fnum(x.get("transfer_side_ask")) is not None]
        settled=[x for x in transfers if x.get("settlement_correct_for_transfer_side") not in ("",None)]
        correct=sum(int(x.get("settlement_correct_for_transfer_side") or 0) for x in settled)
        pnl=sum(fnum(x.get("settlement_hold_pnl_10")) or 0 for x in quoted)
        avgask=mean([fnum(x.get("transfer_side_ask")) for x in quoted]) if quoted else None
        avgleft=mean([fnum(x.get("transfer_seconds_left_est")) for x in transfers if fnum(x.get("transfer_seconds_left_est")) is not None]) if transfers else None
        text=f"- {value}: N={len(items)} transfers={len(transfers)} quotes={len(quoted)} settlement={correct}/{len(settled)} "
        text += f"askAvg={avgask:.3f} " if avgask is not None else "askAvg=NA "
        text += f"leftAvg={avgleft:.1f}s " if avgleft is not None else "leftAvg=NA "
        text += f"$10HoldSum={pnl:+.2f}"
        lines.append(text)
    lines.append("")


def make_report(rows: List[dict]) -> None:
    transfers=[r for r in rows if str(r.get("transfer_found"))=="1"]
    quotes=[r for r in transfers if fnum(r.get("transfer_side_ask")) is not None]
    lines=[
        "# Entry Authority Router V5 — Epoch Transfer Replay",
        "",
        "Scope: all stale >=9s PULLBACK_WAIT historical entries.",
        "",
        "Epoch-reset-capable evidence is intentionally narrow:",
        "- HAND_AUTHORITY_TRANSFER",
        "- directional BOUNDARY_RELEASE",
        "",
        "Failed-Regeneration, Crest, and War Council remain evidence, but they are not treated here as sufficient by themselves to reset opportunity ancestry.",
        "",
        f"Stale pullback cases: {len(rows)}",
        f"Epoch transfers found before contract close: {len(transfers)}",
        f"Transfer quotes reconstructed: {len(quotes)}/{len(transfers)}",
        "",
        "Counterfactual economics: buy the transfer side at the reconstructed ask and hold to settlement with a $10 stake. This does not model fills, fees, Treasury, exits, or management.",
        "",
    ]

    report_group(lines,rows,"By transfer relation","transfer_relation")
    report_group(lines,rows,"By transfer source","transfer_source")
    report_group(lines,rows,"By existing 80c price cap","under_existing_80c_cap")
    report_group(lines,rows,"By transfer price","transfer_price_bin")
    report_group(lines,rows,"By time remaining","transfer_time_left_bin")
    report_group(lines,rows,"By transfer delay from stale historical entry","transfer_delay_bin")

    lines += [
        "## Interpretation discipline",
        "",
        "- The historical stale signal is not revived. A qualifying transfer starts a candidate new opportunity epoch.",
        "- SAME_SIDE_CONTINUATION_RESET means battlefield authority reasserted the stale side after the old window had expired.",
        "- OPPOSITE_SIDE_REVERSAL_RESET means authority transferred to the opposite side; this is a new reversal chapter, not a flip of the old signal.",
        "- The existing 0.80 max-entry cap is reported because it predates this replay; it is not a post-hoc V5 threshold.",
        "- Small samples remain research evidence only. No V9.5A authority changes.",
        "",
    ]
    OUT_REPORT.write_text("\n".join(lines),encoding="utf-8")


def main():
    rows=build_features()
    write_csv(OUT_FEATURES,rows,FEATURE_FIELDS)

    summary=[]
    for label in sorted(set(r["run_label"] for r in rows)):
        rr=[r for r in rows if r["run_label"]==label]
        for gt,key in [
            ("relation","transfer_relation"),
            ("source","transfer_source"),
            ("existing_80c_cap","under_existing_80c_cap"),
            ("price","transfer_price_bin"),
            ("time_left","transfer_time_left_bin"),
            ("delay","transfer_delay_bin"),
        ]:
            summary += summarize(rr,label,gt,key)

    for gt,key in [
        ("relation","transfer_relation"),
        ("source","transfer_source"),
        ("existing_80c_cap","under_existing_80c_cap"),
        ("price","transfer_price_bin"),
        ("time_left","transfer_time_left_bin"),
        ("delay","transfer_delay_bin"),
    ]:
        summary += summarize(rows,"ALL_RUNS",gt,key)

    write_csv(OUT_SUMMARY,summary,SUMMARY_FIELDS)
    make_report(rows)

    print()
    print(f"WROTE {OUT_FEATURES}")
    print(f"WROTE {OUT_SUMMARY}")
    print(f"WROTE {OUT_REPORT}")


if __name__=="__main__":
    main()
