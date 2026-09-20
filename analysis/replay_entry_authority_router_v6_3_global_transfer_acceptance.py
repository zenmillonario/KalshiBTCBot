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
OUT_DIR = Path("analysis/router_v6_3_global_transfer_acceptance")
OUT_FEATURES = OUT_DIR / "router_v6_3_global_transfer_acceptance_features.csv"
OUT_SUMMARY = OUT_DIR / "router_v6_3_global_transfer_acceptance_summary.csv"
OUT_REPORT = OUT_DIR / "router_v6_3_global_transfer_acceptance_report.md"

# Pre-existing value bounds. V6.3 does NOT optimize them.
EXISTING_MIN_ACCEPTED_ASK = 0.20  # V9.4G V94G_FIRST_VALID_MIN_ASK
EXISTING_MAX_ACCEPTED_ASK = 0.80  # V9.4G V94G_FIRST_VALID_MAX_ASK / legacy MAX_ENTRY_ASK
QUOTE_WINDOW_SEC = 9.0            # same reconstruction window used by V4
TRANSFER_CLUSTER_SEC = 9.0        # de-dup close same-side Hand/Boundary emissions

FEATURE_FIELDS = [
    "run_label","cluster_id","ticker","side","cluster_sources","event_count",
    "transfer_ts","transfer_details","quote_found","quote_ts","quote_distance_sec",
    "quote_source","yes_ask","no_ask","transfer_side_ask","seconds_left",
    "inside_existing_20_80_band","price_bin","time_left_bin",
    "settlement_result","settlement_correct","settlement_hold_roi",
    "settlement_hold_pnl_10",
]

SUMMARY_FIELDS = [
    "run_label","group_type","group_value","n","quote_n","accepted_n",
    "settlement_known","settlement_correct","settlement_accuracy",
    "avg_ask","avg_seconds_left","hold_pnl_10_sum","hold_roi_avg",
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


def csv_header(path: Path) -> List[str]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            return next(csv.reader(fh), [])
    except Exception:
        return []


def map_side(v: str) -> str:
    s = str(v or "").upper()
    if s in ("YES","UP"):
        return "YES"
    if s in ("NO","DOWN"):
        return "NO"
    return ""


def regime_side(v: str) -> str:
    s = str(v or "").upper()
    if s.startswith("UP_"):
        return "YES"
    if s.startswith("DOWN_"):
        return "NO"
    return ""


def parse_quote_ts(row: dict) -> Optional[float]:
    epoch_ms = fnum(row.get("epoch_ms"))
    if epoch_ms is not None:
        return epoch_ms / 1000.0
    raw = str(row.get("timestamp") or "")
    if not raw:
        return None
    aware = ("+" in raw[10:] or raw.endswith("Z"))
    return v3.parse_ts(raw, paper_local=not aware)


def settlement_map(run_dir: Path) -> Dict[str,str]:
    out = {}
    for r in read_csv(run_dir / v3.FILES["results"]):
        ticker = str(r.get("ticker") or "")
        result = str(r.get("result") or "").upper()
        if ticker and result in ("YES","NO"):
            out[ticker] = result
    return out


def raw_transfer_events(run_dir: Path) -> List[dict]:
    events = []

    # Boundary: require the actual directional release transition, not every
    # subsequent observer row that continues to display BOUNDARY_RELEASE.
    for r in read_csv(run_dir / v3.FILES["borders"]):
        if str(r.get("territory_state") or "") != "BOUNDARY_RELEASE":
            continue
        if str(r.get("transition_reason") or "") != "CHURN_RELEASED":
            continue
        side = map_side(r.get("release_side"))
        ts = v3.parse_ts(r.get("timestamp", ""), paper_local=False)
        if not side or ts is None:
            continue
        events.append({
            "ts": ts,
            "timestamp": r.get("timestamp", ""),
            "ticker": str(r.get("ticker") or ""),
            "side": side,
            "source": "BOUNDARY_RELEASE",
            "detail": ";".join(filter(None, [
                str(r.get("transition_reason") or ""),
                str(r.get("churn_type") or ""),
                str(r.get("location") or ""),
                str(r.get("hand_regime") or ""),
                str(r.get("hand_authority") or ""),
            ])),
        })

    # Hand: true authority transfer only.
    for r in read_csv(run_dir / v3.FILES["hand"]):
        trans = str(r.get("transition_event") or "")
        if "->" not in trans:
            continue
        before, after = trans.split("->", 1)
        side = map_side(r.get("authority_side"))
        if not side:
            continue
        before_side = regime_side(before)
        after_side = regime_side(after)
        if after_side != side or before_side == side:
            continue
        ts = v3.parse_ts(r.get("timestamp", ""), paper_local=False)
        if ts is None:
            continue
        events.append({
            "ts": ts,
            "timestamp": r.get("timestamp", ""),
            "ticker": str(r.get("ticker") or ""),
            "side": side,
            "source": "HAND_AUTHORITY_TRANSFER",
            "detail": trans,
        })

    events.sort(key=lambda x: (x["ticker"], x["ts"], x["source"]))
    return events


def cluster_transfers(events: List[dict]) -> List[dict]:
    """
    De-dup near-simultaneous same-side Hand/Boundary evidence into one candidate
    battlefield epoch. An intervening opposite-side event always starts a new
    epoch; we never merge across it.
    """
    by_ticker = defaultdict(list)
    for e in events:
        by_ticker[e["ticker"]].append(e)

    out = []
    counter = 0

    for ticker, vals in by_ticker.items():
        vals.sort(key=lambda x: x["ts"])
        current = None
        for e in vals:
            if (
                current is not None
                and e["side"] == current["side"]
                and e["ts"] - current["last_ts"] <= TRANSFER_CLUSTER_SEC
            ):
                current["events"].append(e)
                current["last_ts"] = e["ts"]
                continue

            if current is not None:
                counter += 1
                current["cluster_id"] = f"GT{counter:05d}"
                out.append(current)

            current = {
                "ticker": ticker,
                "side": e["side"],
                "ts": e["ts"],
                "last_ts": e["ts"],
                "events": [e],
            }

        if current is not None:
            counter += 1
            current["cluster_id"] = f"GT{counter:05d}"
            out.append(current)

    out.sort(key=lambda x: x["ts"])
    return out


def target_key(t: dict) -> Tuple[str,str]:
    return (t["cluster_id"], t["ticker"])


def scan_quotes(run_dir: Path, clusters: List[dict]) -> Dict[Tuple[str,str],dict]:
    by_ticker = defaultdict(list)
    for c in clusters:
        by_ticker[c["ticker"]].append(c)

    best = {}
    eligible = 0
    scanned = 0
    required = {"timestamp","ticker","yes_ask","no_ask"}

    for path in sorted(run_dir.glob("*.csv")):
        header = csv_header(path)
        if not required.issubset(set(header)):
            continue
        eligible += 1
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    ticker = str(row.get("ticker") or "")
                    targets = by_ticker.get(ticker)
                    if not targets:
                        continue
                    ts = parse_quote_ts(row)
                    if ts is None:
                        continue
                    ya = fnum(row.get("yes_ask"))
                    na = fnum(row.get("no_ask"))
                    if ya is None and na is None:
                        continue

                    seconds_left = fnum(row.get("seconds_left"))
                    if seconds_left is None:
                        seconds_left = fnum(row.get("seconds_to_close"))

                    for c in targets:
                        d = abs(ts - c["ts"])
                        if d > QUOTE_WINDOW_SEC:
                            continue
                        key = target_key(c)
                        cur = best.get(key)
                        if cur is None or d < cur["distance"]:
                            best[key] = {
                                "timestamp": row.get("timestamp",""),
                                "epoch": ts,
                                "distance": d,
                                "yes_ask": ya,
                                "no_ask": na,
                                "seconds_left": seconds_left,
                                "source": path.name,
                            }
            scanned += 1
        except Exception as exc:
            print(f"WARN quote scan failed {path.name}: {exc}")

    print(f"  quote tapes eligible={eligible} scanned={scanned}")
    return best


def price_bin(v: Optional[float]) -> str:
    if v is None:
        return "NO_QUOTE"
    if v < .20:
        return "LT20C"
    if v < .40:
        return "20_40C"
    if v < .55:
        return "40_55C"
    if v < .70:
        return "55_70C"
    if v <= .80:
        return "70_80C"
    return "GT80C"


def time_bin(v: Optional[float]) -> str:
    if v is None:
        return "UNKNOWN"
    if v < 60:
        return "LT60S"
    if v < 180:
        return "60_180S"
    if v < 300:
        return "180_300S"
    return "GE300S"


def build_features() -> List[dict]:
    all_out = []

    for run_label, run_dir in RUN_DIRS.items():
        if not run_dir.exists():
            print(f"SKIP missing run: {run_label}")
            continue

        raw = raw_transfer_events(run_dir)
        clusters = cluster_transfers(raw)
        quotes = scan_quotes(run_dir, clusters)
        settlements = settlement_map(run_dir)

        accepted_n = 0
        quote_n = 0

        for c in clusters:
            q = quotes.get(target_key(c))
            ask = None
            if q:
                ask = q.get("yes_ask") if c["side"] == "YES" else q.get("no_ask")
            if ask is not None:
                quote_n += 1

            accepted = int(
                ask is not None
                and EXISTING_MIN_ACCEPTED_ASK <= ask <= EXISTING_MAX_ACCEPTED_ASK
            )
            accepted_n += accepted

            settlement = settlements.get(c["ticker"], "")
            correct = ""
            hold_roi = None
            hold_pnl = None
            if ask is not None and ask > 0 and settlement in ("YES","NO"):
                correct = int(c["side"] == settlement)
                hold_roi = ((1.0 - ask) / ask) if correct else -1.0
                hold_pnl = 10.0 * hold_roi

            sources = sorted({e["source"] for e in c["events"]})
            details = " | ".join(
                f"{e['source']}:{e.get('detail','')}" for e in c["events"]
            )

            row = {
                "run_label": run_label,
                "cluster_id": c["cluster_id"],
                "ticker": c["ticker"],
                "side": c["side"],
                "cluster_sources": "+".join(sources),
                "event_count": len(c["events"]),
                "transfer_ts": c["events"][0]["timestamp"],
                "transfer_details": details,
                "quote_found": int(ask is not None),
                "quote_ts": q.get("timestamp","") if q else "",
                "quote_distance_sec": round(q["distance"],3) if q else "",
                "quote_source": q.get("source","") if q else "",
                "yes_ask": q.get("yes_ask","") if q else "",
                "no_ask": q.get("no_ask","") if q else "",
                "transfer_side_ask": ask if ask is not None else "",
                "seconds_left": q.get("seconds_left","") if q else "",
                "inside_existing_20_80_band": accepted,
                "price_bin": price_bin(ask),
                "time_left_bin": time_bin(q.get("seconds_left") if q else None),
                "settlement_result": settlement,
                "settlement_correct": correct,
                "settlement_hold_roi": round(hold_roi,6) if hold_roi is not None else "",
                "settlement_hold_pnl_10": round(hold_pnl,4) if hold_pnl is not None else "",
            }
            all_out.append(row)

        print(
            f"{run_label}: raw_transfers={len(raw)} clustered_epochs={len(clusters)} "
            f"quotes={quote_n}/{len(clusters)} accepted20_80={accepted_n}"
        )

    return all_out


def summarize(rows: List[dict], run_label: str, group_type: str, key: str) -> List[dict]:
    groups = defaultdict(list)
    for r in rows:
        val = str(r.get(key) if r.get(key) not in ("",None) else "(blank)")
        groups[val].append(r)

    out = []
    for val, items in sorted(groups.items()):
        quoted = [x for x in items if str(x.get("quote_found")) == "1"]
        accepted = [x for x in quoted if str(x.get("inside_existing_20_80_band")) == "1"]
        known = [x for x in accepted if x.get("settlement_correct") not in ("",None)]
        correct = sum(int(x.get("settlement_correct") or 0) for x in known)

        asks = [fnum(x.get("transfer_side_ask")) for x in accepted]
        asks = [x for x in asks if x is not None]
        lefts = [fnum(x.get("seconds_left")) for x in accepted]
        lefts = [x for x in lefts if x is not None]
        rois = [fnum(x.get("settlement_hold_roi")) for x in accepted]
        rois = [x for x in rois if x is not None]
        pnls = [fnum(x.get("settlement_hold_pnl_10")) for x in accepted]
        pnls = [x for x in pnls if x is not None]

        out.append({
            "run_label": run_label,
            "group_type": group_type,
            "group_value": val,
            "n": len(items),
            "quote_n": len(quoted),
            "accepted_n": len(accepted),
            "settlement_known": len(known),
            "settlement_correct": correct,
            "settlement_accuracy": round(correct/len(known),4) if known else "",
            "avg_ask": round(mean(asks),4) if asks else "",
            "avg_seconds_left": round(mean(lefts),2) if lefts else "",
            "hold_pnl_10_sum": round(sum(pnls),3) if pnls else "",
            "hold_roi_avg": round(mean(rois),4) if rois else "",
        })
    return out


def write_csv(path: Path, rows: List[dict], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def report_group(lines: List[str], rows: List[dict], title: str, key: str) -> None:
    groups = defaultdict(list)
    for r in rows:
        val = str(r.get(key) if r.get(key) not in ("",None) else "(blank)")
        groups[val].append(r)

    lines += [f"## {title}", ""]
    for val, items in sorted(groups.items()):
        quoted = [x for x in items if str(x.get("quote_found")) == "1"]
        accepted = [x for x in quoted if str(x.get("inside_existing_20_80_band")) == "1"]
        known = [x for x in accepted if x.get("settlement_correct") not in ("",None)]
        correct = sum(int(x.get("settlement_correct") or 0) for x in known)
        pnl = sum(fnum(x.get("settlement_hold_pnl_10")) or 0.0 for x in accepted)
        avgask = mean([fnum(x.get("transfer_side_ask")) for x in accepted]) if accepted else None
        lines.append(
            f"- {val}: N={len(items)} quotes={len(quoted)} accepted={len(accepted)} "
            f"settlement={correct}/{len(known)} "
            + (f"askAvg={avgask:.3f} " if avgask is not None else "askAvg=NA ")
            + f"$10HoldSum={pnl:+.2f}"
        )
    lines.append("")


def make_report(rows: List[dict]) -> None:
    quoted = [r for r in rows if str(r.get("quote_found")) == "1"]
    accepted = [r for r in quoted if str(r.get("inside_existing_20_80_band")) == "1"]
    known = [r for r in accepted if r.get("settlement_correct") not in ("",None)]
    correct = sum(int(r.get("settlement_correct") or 0) for r in known)
    pnl = sum(fnum(r.get("settlement_hold_pnl_10")) or 0.0 for r in accepted)

    outside = [r for r in quoted if str(r.get("inside_existing_20_80_band")) == "0"]
    outside_known = [r for r in outside if r.get("settlement_correct") not in ("",None)]
    outside_correct = sum(int(r.get("settlement_correct") or 0) for r in outside_known)

    lines = [
        "# Router V6.3 — Global Hand/Boundary Transfer Acceptance Replay",
        "",
        "Purpose: test the V5 transfer hypothesis outside the 28 stale PULLBACK_WAIT cases.",
        "",
        "Universe:",
        "- every true HAND authority transfer in the three archived runs;",
        "- every directional BOUNDARY_RELEASE row whose transition_reason is CHURN_RELEASED;",
        "- near-simultaneous same-side transfer evidence is clustered within 9s to avoid double-counting one battlefield epoch.",
        "",
        "The acceptance band is pre-existing, not optimized here:",
        "- V9.4G V94G_FIRST_VALID_MIN_ASK = 0.20",
        "- V9.4G V94G_FIRST_VALID_MAX_ASK = 0.80",
        "- legacy MAX_ENTRY_ASK = 0.80",
        "",
        f"Global clustered transfer epochs: {len(rows)}",
        f"Quotes reconstructed: {len(quoted)}/{len(rows)}",
        f"Inside existing 0.20–0.80 band: {len(accepted)}",
        f"Accepted-band settlement correctness: {correct}/{len(known)}",
        f"Accepted-band simple $10 hold sum: {pnl:+.2f}",
        f"Outside-band directional correctness (economics not endorsed): {outside_correct}/{len(outside_known)}",
        "",
        "Counterfactual economics buy the transfer side at the nearest reconstructed ask and hold to settlement. No fees, fills, Treasury, stops, or management are modeled.",
        "",
    ]

    report_group(lines, rows, "By transfer evidence", "cluster_sources")
    report_group(lines, rows, "By price", "price_bin")
    report_group(lines, rows, "By time remaining", "time_left_bin")
    report_group(lines, rows, "By run", "run_label")

    lines += [
        "## Interpretation discipline",
        "",
        "- This is the first broad test of transfer+market-acceptance outside the stale-pullback selection that generated V5.",
        "- HAND/BOUNDARY are existing structural observers; V6.3 adds no new detector.",
        "- The 0.20–0.80 band predates this replay and is not tuned to these outcomes.",
        "- Multiple transfer epochs can occur in one contract; each is a new structural epoch, not a resurrection of an old signal.",
        "- Settlement hold is intentionally crude and cannot be treated as expected live P&L.",
        "- No V9.5A authority changes.",
        "",
    ]

    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main():
    rows = build_features()
    write_csv(OUT_FEATURES, rows, FEATURE_FIELDS)

    summary = []
    labels = sorted(set(r["run_label"] for r in rows))
    for label in labels:
        rr = [r for r in rows if r["run_label"] == label]
        for gt,key in [
            ("source","cluster_sources"),
            ("price","price_bin"),
            ("time","time_left_bin"),
        ]:
            summary += summarize(rr, label, gt, key)

    for gt,key in [
        ("source","cluster_sources"),
        ("price","price_bin"),
        ("time","time_left_bin"),
        ("run","run_label"),
    ]:
        summary += summarize(rows, "ALL_RUNS", gt, key)

    write_csv(OUT_SUMMARY, summary, SUMMARY_FIELDS)
    make_report(rows)

    print()
    print(f"WROTE {OUT_FEATURES}")
    print(f"WROTE {OUT_SUMMARY}")
    print(f"WROTE {OUT_REPORT}")


if __name__ == "__main__":
    main()
