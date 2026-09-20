from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

RUN_DIRS = {
    "tachys_v9_5a_price_freshness_active_treasury": Path("runs/tachys_v9_5a_price_freshness_active_treasury"),
    "2026-09-19_v9_5a_late_mature_shadow_5h": Path("runs/2026-09-19_v9_5a_late_mature_shadow_5h"),
    "2026-09-20_v9_5a_swirl_orbit_long_01": Path("runs/2026-09-20_v9_5a_swirl_orbit_long_01"),
}

V3_FEATURES = Path("analysis/router_v3_hard_release_replay/router_v3_hard_release_features.csv")
OUT_DIR = Path("analysis/router_v4_release_economics_replay")
OUT_FEATURES = OUT_DIR / "router_v4_release_economics_features.csv"
OUT_SUMMARY = OUT_DIR / "router_v4_release_economics_summary.csv"
OUT_REPORT = OUT_DIR / "router_v4_release_economics_report.md"

QUOTE_WINDOW_SEC = 9.0

FEATURE_FIELDS = [
    "run_label","trade_id","ticker","side","initial_state","stale9",
    "historical_entry_ts","historical_entry_ask","historical_pnl",
    "prevalidation_delay_sec","ask_inflation_from_first_cents",
    "settlement_result","settlement_correct",
    "hard_release_order","release_source","release_ts","release_delay_sec","release_detail",
    "release_quote_ts","release_quote_distance_sec","release_quote_source",
    "release_yes_ask","release_no_ask","release_side_ask",
    "release_vs_historical_entry_cents","release_vs_first_directional_cents",
    "entry_seconds_left","release_seconds_left_est",
    "settlement_hold_roi","settlement_hold_pnl_10",
    "release_timing_bin","release_price_bin","quote_found",
]

SUMMARY_FIELDS = [
    "run_label","group_type","group_value","n","quote_n",
    "settlement_known","settlement_correct","settlement_accuracy",
    "avg_release_ask","avg_release_vs_entry_cents","avg_release_delay_sec",
    "settlement_hold_pnl_10_sum","settlement_hold_roi_avg",
]


def read_csv(path: Path) -> List[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def fnum(v) -> Optional[float]:
    try:
        if v in (None, ""):
            return None
        x = float(v)
        return None if math.isnan(x) else x
    except Exception:
        return None


def parse_ts(v: str, naive_tz=UTC) -> Optional[float]:
    if not v:
        return None
    s = str(v).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=naive_tz)
        return dt.timestamp()
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=naive_tz)
            return dt.timestamp()
        except Exception:
            continue
    return None


def csv_header(path: Path) -> List[str]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            return next(csv.reader(fh), [])
    except Exception:
        return []


def load_paper_entries(run_dir: Path) -> Dict[str, dict]:
    rows = read_csv(run_dir / "tachys_paper_trades_v9_2_6.csv")
    out = {}
    for r in rows:
        if r.get("event") != "ENTRY":
            continue
        tid = str(r.get("trade_id") or "")
        if tid:
            out[tid] = r
    return out


def first_directional_ask(run_dir: Path, ticker: str, side: str, entry_ts: float) -> Optional[float]:
    path = run_dir / "tachys_preentry_value_memory_v9_4i.csv"
    if not path.exists():
        return None
    best = None
    best_ts = None
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r.get("ticker") != ticker or r.get("side") != side:
                continue
            if r.get("event") != "FIRST_DIRECTIONAL":
                continue
            ts = parse_ts(r.get("timestamp", ""), UTC)
            if ts is None or ts > entry_ts:
                continue
            if entry_ts - ts > 180.0:
                continue
            if best_ts is None or ts > best_ts:
                best_ts = ts
                best = fnum(r.get("ask"))
    return best


def release_timing_bin(v: Optional[float]) -> str:
    if v is None:
        return "NO_RELEASE"
    if v <= 9:
        return "LE9S"
    if v <= 30:
        return "9_30S"
    if v <= 90:
        return "30_90S"
    if v <= 180:
        return "90_180S"
    return "GT180S"


def release_price_bin(v: Optional[float]) -> str:
    if v is None:
        return "NO_QUOTE"
    if v < .40:
        return "LT40C"
    if v < .55:
        return "40_55C"
    if v < .70:
        return "55_70C"
    if v < .80:
        return "70_80C"
    return "GE80C"


def target_key(r: dict) -> Tuple[str, str, str]:
    return (r["run_label"], r["trade_id"], r["ticker"])


def scan_quotes(run_dir: Path, targets: List[dict]) -> Dict[Tuple[str,str,str], dict]:
    # Search every archived CSV that actually exposes timestamp+ticker+YES/NO asks.
    # Keep only the nearest quote to each target hard-release time.
    by_ticker: Dict[str, List[dict]] = defaultdict(list)
    for t in targets:
        if t.get("_release_epoch") is not None:
            by_ticker[t["ticker"]].append(t)

    best: Dict[Tuple[str,str,str], dict] = {}
    inspected = 0
    eligible = 0

    for path in sorted(run_dir.glob("*.csv")):
        header = csv_header(path)
        required = {"timestamp","ticker","yes_ask","no_ask"}
        if not required.issubset(set(header)):
            continue
        eligible += 1
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    ticker = str(row.get("ticker") or "")
                    candidates = by_ticker.get(ticker)
                    if not candidates:
                        continue

                    # Most V9.4 shadow logs are aware UTC. Legacy/core ledgers may be
                    # naive ET. If an epoch_ms field is present, it wins.
                    epoch_ms = fnum(row.get("epoch_ms"))
                    if epoch_ms is not None:
                        ts = epoch_ms / 1000.0
                    else:
                        raw = str(row.get("timestamp") or "")
                        # ISO strings with offset/Z parse exactly. Naive timestamps in
                        # legacy tapes were written in local ET.
                        aware = ("+" in raw[10:] or raw.endswith("Z"))
                        ts = parse_ts(raw, UTC if aware else ET)
                    if ts is None:
                        continue

                    ya = fnum(row.get("yes_ask"))
                    na = fnum(row.get("no_ask"))
                    if ya is None and na is None:
                        continue

                    for t in candidates:
                        rt = t["_release_epoch"]
                        d = abs(ts - rt)
                        if d > QUOTE_WINDOW_SEC:
                            continue
                        key = target_key(t)
                        cur = best.get(key)
                        if cur is None or d < cur["distance"]:
                            best[key] = {
                                "timestamp": raw,
                                "epoch": ts,
                                "distance": d,
                                "yes_ask": ya,
                                "no_ask": na,
                                "source": path.name,
                            }
            inspected += 1
        except Exception as exc:
            print(f"WARN quote scan failed {path.name}: {exc}")

    print(f"  quote tapes eligible={eligible} scanned={inspected}")
    return best


def build_features() -> List[dict]:
    if not V3_FEATURES.exists():
        raise SystemExit(
            f"Missing {V3_FEATURES}. Run replay_entry_authority_router_v3_hard_release.py first."
        )

    v3 = read_csv(V3_FEATURES)
    selected = [
        r for r in v3
        if str(r.get("stale9")) == "1"
        and r.get("initial_state") == "PULLBACK_WAIT"
        and r.get("hard_release_order") == "SAME_HARD_RELEASE_FIRST"
        and r.get("same_hard_release_ts")
    ]

    all_out: List[dict] = []
    by_run: Dict[str, List[dict]] = defaultdict(list)

    for r in selected:
        rr = dict(r)
        rr["_release_epoch"] = parse_ts(r.get("same_hard_release_ts",""), UTC)
        by_run[r["run_label"]].append(rr)

    for run_label, targets in by_run.items():
        run_dir = RUN_DIRS.get(run_label)
        if run_dir is None or not run_dir.exists():
            print(f"SKIP unknown/missing run: {run_label}")
            continue

        print(f"{run_label}: {len(targets)} stale pullback same-release cases")
        quotes = scan_quotes(run_dir, targets)
        paper = load_paper_entries(run_dir)

        for r in targets:
            tid = str(r.get("trade_id") or "")
            p = paper.get(tid, {})
            hist_entry = fnum(r.get("entry_ask"))
            release_delay = fnum(r.get("same_hard_release_delay_sec"))
            entry_seconds_left = fnum(p.get("seconds_to_close"))
            if entry_seconds_left is None:
                entry_seconds_left = fnum(p.get("seconds_left"))
            release_seconds_left = None
            if entry_seconds_left is not None and release_delay is not None:
                release_seconds_left = max(0.0, entry_seconds_left - release_delay)

            hist_ts = parse_ts(r.get("paper_entry_ts",""), ET)
            first_ask = first_directional_ask(run_dir, r["ticker"], r["side"], hist_ts) if hist_ts else None

            q = quotes.get(target_key(r))
            release_ask = None
            if q:
                release_ask = q.get("yes_ask") if r["side"] == "YES" else q.get("no_ask")

            vs_entry = None
            if release_ask is not None and hist_entry is not None:
                vs_entry = (release_ask - hist_entry) * 100.0
            vs_first = None
            if release_ask is not None and first_ask is not None:
                vs_first = (release_ask - first_ask) * 100.0

            settlement = str(r.get("settlement_result") or "")
            hold_roi = None
            hold_pnl10 = None
            if release_ask is not None and release_ask > 0 and settlement in ("YES","NO"):
                hold_roi = ((1.0 - release_ask) / release_ask) if settlement == r["side"] else -1.0
                hold_pnl10 = 10.0 * hold_roi

            out = {
                "run_label": run_label,
                "trade_id": tid,
                "ticker": r["ticker"],
                "side": r["side"],
                "initial_state": r.get("initial_state",""),
                "stale9": r.get("stale9",""),
                "historical_entry_ts": r.get("paper_entry_ts",""),
                "historical_entry_ask": r.get("entry_ask",""),
                "historical_pnl": r.get("actual_pnl",""),
                "prevalidation_delay_sec": r.get("prevalidation_delay_sec",""),
                "ask_inflation_from_first_cents": r.get("ask_inflation_from_first_cents",""),
                "settlement_result": settlement,
                "settlement_correct": r.get("settlement_correct",""),
                "hard_release_order": r.get("hard_release_order",""),
                "release_source": r.get("same_hard_release_source",""),
                "release_ts": r.get("same_hard_release_ts",""),
                "release_delay_sec": r.get("same_hard_release_delay_sec",""),
                "release_detail": r.get("same_hard_release_detail",""),
                "release_quote_ts": q.get("timestamp","") if q else "",
                "release_quote_distance_sec": round(q["distance"],3) if q else "",
                "release_quote_source": q.get("source","") if q else "",
                "release_yes_ask": q.get("yes_ask","") if q else "",
                "release_no_ask": q.get("no_ask","") if q else "",
                "release_side_ask": release_ask if release_ask is not None else "",
                "release_vs_historical_entry_cents": round(vs_entry,3) if vs_entry is not None else "",
                "release_vs_first_directional_cents": round(vs_first,3) if vs_first is not None else "",
                "entry_seconds_left": entry_seconds_left if entry_seconds_left is not None else "",
                "release_seconds_left_est": round(release_seconds_left,3) if release_seconds_left is not None else "",
                "settlement_hold_roi": round(hold_roi,6) if hold_roi is not None else "",
                "settlement_hold_pnl_10": round(hold_pnl10,4) if hold_pnl10 is not None else "",
                "release_timing_bin": release_timing_bin(release_delay),
                "release_price_bin": release_price_bin(release_ask),
                "quote_found": int(release_ask is not None),
            }
            all_out.append(out)

    return all_out


def summarize(rows: List[dict], run_label: str, group_type: str, key: str) -> List[dict]:
    groups: Dict[str,List[dict]] = defaultdict(list)
    for r in rows:
        groups[str(r.get(key) if r.get(key) not in ("",None) else "(blank)")].append(r)

    out=[]
    for value, items in sorted(groups.items()):
        quoted=[x for x in items if fnum(x.get("release_side_ask")) is not None]
        settled=[x for x in items if x.get("settlement_correct") not in ("",None)]
        correct=sum(int(x.get("settlement_correct") or 0) for x in settled)
        asks=[fnum(x.get("release_side_ask")) for x in quoted]
        asks=[x for x in asks if x is not None]
        ves=[fnum(x.get("release_vs_historical_entry_cents")) for x in quoted]
        ves=[x for x in ves if x is not None]
        delays=[fnum(x.get("release_delay_sec")) for x in items]
        delays=[x for x in delays if x is not None]
        rois=[fnum(x.get("settlement_hold_roi")) for x in quoted]
        rois=[x for x in rois if x is not None]
        pnls=[fnum(x.get("settlement_hold_pnl_10")) for x in quoted]
        pnls=[x for x in pnls if x is not None]
        out.append({
            "run_label":run_label,
            "group_type":group_type,
            "group_value":value,
            "n":len(items),
            "quote_n":len(quoted),
            "settlement_known":len(settled),
            "settlement_correct":correct,
            "settlement_accuracy":round(correct/len(settled),4) if settled else "",
            "avg_release_ask":round(mean(asks),4) if asks else "",
            "avg_release_vs_entry_cents":round(mean(ves),3) if ves else "",
            "avg_release_delay_sec":round(mean(delays),3) if delays else "",
            "settlement_hold_pnl_10_sum":round(sum(pnls),3) if pnls else "",
            "settlement_hold_roi_avg":round(mean(rois),4) if rois else "",
        })
    return out


def write_csv(path: Path, rows: List[dict], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=fields,extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def make_report(rows: List[dict]) -> None:
    quoted=[r for r in rows if fnum(r.get("release_side_ask")) is not None]
    lines=[
        "# Entry Authority Router V4 — Hard Release Economics",
        "",
        "Scope: only stale >=9s PULLBACK_WAIT historical entries whose first hard release after entry was same-side.",
        "",
        f"Cases: {len(rows)}",
        f"Release quotes reconstructed within ±{QUOTE_WINDOW_SEC:.0f}s: {len(quoted)}/{len(rows)}",
        "",
        "The settlement-hold calculation is counterfactual and deliberately simple: enter at the reconstructed release ask and hold to settlement. It does not simulate Treasury, stops, fills, slippage, or management.",
        "",
    ]

    def emit(title: str, key: str):
        groups=defaultdict(list)
        for r in rows:
            groups[str(r.get(key) if r.get(key) not in ("",None) else "(blank)")].append(r)
        lines.extend([f"## {title}",""])
        for val,items in sorted(groups.items()):
            q=[x for x in items if fnum(x.get("release_side_ask")) is not None]
            pnl=sum(fnum(x.get("settlement_hold_pnl_10")) or 0 for x in q)
            known=[x for x in items if x.get("settlement_correct") not in ("",None)]
            correct=sum(int(x.get("settlement_correct") or 0) for x in known)
            avga=mean([fnum(x.get("release_side_ask")) for x in q]) if q else None
            avgd=mean([fnum(x.get("release_delay_sec")) for x in items if fnum(x.get("release_delay_sec")) is not None]) if items else None
            lines.append(
                f"- {val}: N={len(items)} quotes={len(q)} settlement={correct}/{len(known)} "
                f"releaseAskAvg={avga:.3f} " if avga is not None else
                f"- {val}: N={len(items)} quotes={len(q)} settlement={correct}/{len(known)} releaseAskAvg=NA "
            )
            # Patch the last line with delay and hold result without complex formatting branch.
            base=lines.pop()
            base += f"delayAvg={avgd:.1f}s " if avgd is not None else "delayAvg=NA "
            base += f"$10HoldSum={pnl:+.2f}"
            lines.append(base)
        lines.append("")

    emit("By release timing", "release_timing_bin")
    emit("By hard-release provenance", "release_source")
    emit("By release price", "release_price_bin")

    lines += [
        "## Discipline",
        "",
        "- Hard release is a possible new chapter, not retroactive validation of the stale historical entry.",
        "- A release that arrives with poor economics can still be directionally right and economically untradable.",
        "- A release quote reconstructed from another telemetry tape is accepted only within the stated time window and its source is retained.",
        "- No result here changes V9.5A authority.",
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
            ("release_timing","release_timing_bin"),
            ("release_source","release_source"),
            ("release_price","release_price_bin"),
        ]:
            summary += summarize(rr,label,gt,key)
    for gt,key in [
        ("release_timing","release_timing_bin"),
        ("release_source","release_source"),
        ("release_price","release_price_bin"),
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
