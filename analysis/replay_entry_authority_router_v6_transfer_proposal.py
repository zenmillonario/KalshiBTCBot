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
V5_FEATURES = Path("analysis/router_v5_epoch_transfer_replay/router_v5_epoch_transfer_features.csv")
OUT_DIR = Path("analysis/router_v6_transfer_proposal_replay")
OUT_FEATURES = OUT_DIR / "router_v6_transfer_proposal_features.csv"
OUT_SUMMARY = OUT_DIR / "router_v6_transfer_proposal_summary.csv"
OUT_REPORT = OUT_DIR / "router_v6_transfer_proposal_report.md"

PRICE_FRESHNESS_FILE = "tachys_price_freshness_v9_5a.csv"

# IMPORTANT: these are not new V6-optimized thresholds.
# 0.20 already exists in V9.4G as V94G_FIRST_VALID_MIN_ASK.
# 0.80 already exists in V9.4G as V94G_FIRST_VALID_MAX_ASK and in the legacy engine
# as MAX_ENTRY_ASK. V6 only audits this pre-existing acceptance band.
EXISTING_MIN_ACCEPTED_ASK = 0.20
EXISTING_MAX_ACCEPTED_ASK = 0.80

EPOCH_TRANSFER_SOURCES = {"HAND_AUTHORITY_TRANSFER", "BOUNDARY_RELEASE"}

FEATURE_FIELDS = [
    "run_label","trade_id","ticker","stale_side",
    "transfer_side","transfer_relation","transfer_source","transfer_ts",
    "transfer_release_ask","transfer_seconds_left_est","settlement_result",
    "next_transfer_ts","epoch_window_sec",
    "proposal_found","proposal_ts","proposal_delay_sec","proposal_ask",
    "proposal_strategy","proposal_trade_intent","proposal_gate_action","proposal_gate_reason",
    "proposal_remaining_capacity","proposal_price_arc_phase","proposal_battlefield_class",
    "proposal_dragon_state","proposal_chapter_label",
    "proposal_in_existing_20_80_band","proposal_vs_release_cents",
    "proposal_settlement_correct","proposal_hold_roi","proposal_hold_pnl_10",
    "accepted_proposal_found","accepted_proposal_ts","accepted_proposal_delay_sec",
    "accepted_proposal_ask","accepted_strategy","accepted_trade_intent",
    "accepted_gate_action","accepted_gate_reason","accepted_vs_release_cents",
    "accepted_settlement_correct","accepted_hold_roi","accepted_hold_pnl_10",
    "accepted_delay_bin","accepted_price_bin",
]

SUMMARY_FIELDS = [
    "run_label","group_type","group_value","n","proposal_n","accepted_n",
    "settlement_known","settlement_correct","settlement_accuracy",
    "avg_accepted_ask","avg_accepted_delay_sec","accepted_hold_pnl_10_sum",
    "accepted_hold_roi_avg",
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


def in_existing_band(ask: Optional[float]) -> bool:
    return (
        ask is not None
        and EXISTING_MIN_ACCEPTED_ASK <= ask <= EXISTING_MAX_ACCEPTED_ASK
    )


def delay_bin(v: Optional[float]) -> str:
    if v is None:
        return "NO_ACCEPTED_PROPOSAL"
    if v <= 3:
        return "LE3S"
    if v <= 9:
        return "3_9S"
    if v <= 30:
        return "9_30S"
    if v <= 90:
        return "30_90S"
    return "GT90S"


def price_bin(v: Optional[float]) -> str:
    if v is None:
        return "NO_ACCEPTED_PROPOSAL"
    if v < .40:
        return "20_40C"
    if v < .55:
        return "40_55C"
    if v < .70:
        return "55_70C"
    return "70_80C"


def load_transfer_events(run_dir: Path) -> List[dict]:
    data = {k: v3.read_csv(run_dir / fn) for k, fn in v3.FILES.items()}
    return [
        e for e in v3.build_hard_events(data)
        if e.get("source") in EPOCH_TRANSFER_SOURCES
    ]


def next_transfer_ts(events: List[dict], ticker: str, after_ts: float, close_ts: float) -> Optional[float]:
    for ev in events:
        if ev["ts"] <= after_ts:
            continue
        if ev["ts"] > close_ts:
            break
        if ev.get("ticker") == ticker:
            return ev["ts"]
    return None


def load_entry_gate_candidates(run_dir: Path) -> List[dict]:
    rows = read_csv(run_dir / PRICE_FRESHNESS_FILE)
    out = []
    for r in rows:
        if str(r.get("event") or "") != "ENTRY_GATE":
            continue
        ts = v3.parse_ts(r.get("timestamp", ""), paper_local=False)
        ask = fnum(r.get("ask"))
        if ts is None or ask is None:
            continue
        rr = dict(r)
        rr["_ts"] = ts
        rr["_ask"] = ask
        out.append(rr)
    out.sort(key=lambda x: x["_ts"])
    return out


def first_candidate(
    candidates: List[dict],
    ticker: str,
    side: str,
    start_ts: float,
    end_ts: float,
    accepted_only: bool = False,
) -> Optional[dict]:
    for r in candidates:
        ts = r["_ts"]
        if ts <= start_ts:
            continue
        if ts > end_ts:
            break
        if r.get("ticker") != ticker or r.get("side") != side:
            continue
        if accepted_only and not in_existing_band(r["_ask"]):
            continue
        return r
    return None


def settlement_math(side: str, ask: Optional[float], settlement: str) -> Tuple[str, Optional[float], Optional[float]]:
    if ask is None or ask <= 0 or settlement not in ("YES", "NO"):
        return "", None, None
    correct = int(side == settlement)
    roi = ((1.0 - ask) / ask) if correct else -1.0
    return str(correct), roi, 10.0 * roi


def build_features() -> List[dict]:
    if not V5_FEATURES.exists():
        raise SystemExit(
            f"Missing {V5_FEATURES}. Run replay_entry_authority_router_v5_epoch_transfer.py first."
        )

    v5 = read_csv(V5_FEATURES)
    transfer_rows = [r for r in v5 if str(r.get("transfer_found")) == "1"]

    by_run: Dict[str, List[dict]] = defaultdict(list)
    for r in transfer_rows:
        by_run[r["run_label"]].append(r)

    out = []

    for run_label, rows in by_run.items():
        run_dir = RUN_DIRS.get(run_label)
        if run_dir is None or not run_dir.exists():
            print(f"SKIP missing run {run_label}")
            continue

        transfer_events = load_transfer_events(run_dir)
        candidates = load_entry_gate_candidates(run_dir)
        paper = v4.load_paper_entries(run_dir)

        found = 0
        accepted = 0

        for r in rows:
            tid = str(r.get("trade_id") or "")
            ticker = str(r.get("ticker") or "")
            side = str(r.get("transfer_side") or "")
            transfer_ts = v3.parse_ts(r.get("transfer_ts", ""), paper_local=False)
            release_ask = fnum(r.get("transfer_side_ask"))

            p = paper.get((tid, ticker), {})
            hist_entry_ts = v3.parse_ts(p.get("timestamp", ""), paper_local=True)
            entry_left = fnum(p.get("seconds_to_close"))
            if entry_left is None:
                entry_left = fnum(p.get("seconds_left"))

            close_ts = None
            if hist_entry_ts is not None and entry_left is not None:
                close_ts = hist_entry_ts + max(0.0, entry_left)

            if transfer_ts is None or close_ts is None:
                epoch_end = transfer_ts if transfer_ts is not None else 0.0
                nxt = None
            else:
                nxt = next_transfer_ts(transfer_events, ticker, transfer_ts, close_ts)
                epoch_end = min(close_ts, nxt) if nxt is not None else close_ts

            prop = None
            acc = None
            if transfer_ts is not None and epoch_end > transfer_ts:
                prop = first_candidate(candidates, ticker, side, transfer_ts, epoch_end, accepted_only=False)
                acc = first_candidate(candidates, ticker, side, transfer_ts, epoch_end, accepted_only=True)

            if prop:
                found += 1
            if acc:
                accepted += 1

            prop_ask = prop["_ask"] if prop else None
            acc_ask = acc["_ask"] if acc else None
            prop_delay = (prop["_ts"] - transfer_ts) if prop and transfer_ts is not None else None
            acc_delay = (acc["_ts"] - transfer_ts) if acc and transfer_ts is not None else None

            prop_correct, prop_roi, prop_pnl = settlement_math(side, prop_ask, str(r.get("settlement_result") or ""))
            acc_correct, acc_roi, acc_pnl = settlement_math(side, acc_ask, str(r.get("settlement_result") or ""))

            prop_vs_release = (prop_ask - release_ask) * 100.0 if prop_ask is not None and release_ask is not None else None
            acc_vs_release = (acc_ask - release_ask) * 100.0 if acc_ask is not None and release_ask is not None else None

            out.append({
                "run_label": run_label,
                "trade_id": tid,
                "ticker": ticker,
                "stale_side": r.get("stale_side", ""),
                "transfer_side": side,
                "transfer_relation": r.get("transfer_relation", ""),
                "transfer_source": r.get("transfer_source", ""),
                "transfer_ts": r.get("transfer_ts", ""),
                "transfer_release_ask": r.get("transfer_side_ask", ""),
                "transfer_seconds_left_est": r.get("transfer_seconds_left_est", ""),
                "settlement_result": r.get("settlement_result", ""),
                "next_transfer_ts": (
                    v3.datetime.fromtimestamp(nxt, v3.ZoneInfo("UTC")).isoformat()
                    if nxt is not None else ""
                ),
                "epoch_window_sec": round(epoch_end - transfer_ts, 3) if transfer_ts is not None and epoch_end >= transfer_ts else "",
                "proposal_found": int(prop is not None),
                "proposal_ts": prop.get("timestamp", "") if prop else "",
                "proposal_delay_sec": round(prop_delay, 3) if prop_delay is not None else "",
                "proposal_ask": prop_ask if prop_ask is not None else "",
                "proposal_strategy": prop.get("strategy", "") if prop else "",
                "proposal_trade_intent": prop.get("trade_intent", "") if prop else "",
                "proposal_gate_action": prop.get("gate_action", "") if prop else "",
                "proposal_gate_reason": prop.get("gate_reason", "") if prop else "",
                "proposal_remaining_capacity": prop.get("remaining_capacity", "") if prop else "",
                "proposal_price_arc_phase": prop.get("price_arc_phase", "") if prop else "",
                "proposal_battlefield_class": prop.get("battlefield_class", "") if prop else "",
                "proposal_dragon_state": prop.get("dragon_state", "") if prop else "",
                "proposal_chapter_label": prop.get("chapter_label", "") if prop else "",
                "proposal_in_existing_20_80_band": int(in_existing_band(prop_ask)),
                "proposal_vs_release_cents": round(prop_vs_release, 3) if prop_vs_release is not None else "",
                "proposal_settlement_correct": prop_correct,
                "proposal_hold_roi": round(prop_roi, 6) if prop_roi is not None else "",
                "proposal_hold_pnl_10": round(prop_pnl, 4) if prop_pnl is not None else "",
                "accepted_proposal_found": int(acc is not None),
                "accepted_proposal_ts": acc.get("timestamp", "") if acc else "",
                "accepted_proposal_delay_sec": round(acc_delay, 3) if acc_delay is not None else "",
                "accepted_proposal_ask": acc_ask if acc_ask is not None else "",
                "accepted_strategy": acc.get("strategy", "") if acc else "",
                "accepted_trade_intent": acc.get("trade_intent", "") if acc else "",
                "accepted_gate_action": acc.get("gate_action", "") if acc else "",
                "accepted_gate_reason": acc.get("gate_reason", "") if acc else "",
                "accepted_vs_release_cents": round(acc_vs_release, 3) if acc_vs_release is not None else "",
                "accepted_settlement_correct": acc_correct,
                "accepted_hold_roi": round(acc_roi, 6) if acc_roi is not None else "",
                "accepted_hold_pnl_10": round(acc_pnl, 4) if acc_pnl is not None else "",
                "accepted_delay_bin": delay_bin(acc_delay),
                "accepted_price_bin": price_bin(acc_ask),
            })

        print(
            f"{run_label}: transfers={len(rows)} "
            f"post-transfer proposals={found} accepted-band proposals={accepted}"
        )

    return out


def summarize(rows: List[dict], run_label: str, group_type: str, key: str) -> List[dict]:
    groups = defaultdict(list)
    for r in rows:
        value = r.get(key)
        groups[str(value if value not in ("", None) else "(blank)")].append(r)

    out = []
    for value, items in sorted(groups.items()):
        props = [x for x in items if str(x.get("proposal_found")) == "1"]
        accepted = [x for x in items if str(x.get("accepted_proposal_found")) == "1"]
        settled = [x for x in accepted if x.get("accepted_settlement_correct") not in ("", None)]
        correct = sum(int(x.get("accepted_settlement_correct") or 0) for x in settled)

        asks = [fnum(x.get("accepted_proposal_ask")) for x in accepted]
        asks = [x for x in asks if x is not None]
        delays = [fnum(x.get("accepted_proposal_delay_sec")) for x in accepted]
        delays = [x for x in delays if x is not None]
        rois = [fnum(x.get("accepted_hold_roi")) for x in accepted]
        rois = [x for x in rois if x is not None]
        pnls = [fnum(x.get("accepted_hold_pnl_10")) for x in accepted]
        pnls = [x for x in pnls if x is not None]

        out.append({
            "run_label": run_label,
            "group_type": group_type,
            "group_value": value,
            "n": len(items),
            "proposal_n": len(props),
            "accepted_n": len(accepted),
            "settlement_known": len(settled),
            "settlement_correct": correct,
            "settlement_accuracy": round(correct / len(settled), 4) if settled else "",
            "avg_accepted_ask": round(mean(asks), 4) if asks else "",
            "avg_accepted_delay_sec": round(mean(delays), 3) if delays else "",
            "accepted_hold_pnl_10_sum": round(sum(pnls), 3) if pnls else "",
            "accepted_hold_roi_avg": round(mean(rois), 4) if rois else "",
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
        value = r.get(key)
        groups[str(value if value not in ("", None) else "(blank)")].append(r)

    lines.extend([f"## {title}", ""])
    for value, items in sorted(groups.items()):
        props = [x for x in items if str(x.get("proposal_found")) == "1"]
        accepted = [x for x in items if str(x.get("accepted_proposal_found")) == "1"]
        settled = [x for x in accepted if x.get("accepted_settlement_correct") not in ("", None)]
        correct = sum(int(x.get("accepted_settlement_correct") or 0) for x in settled)
        pnl = sum(fnum(x.get("accepted_hold_pnl_10")) or 0.0 for x in accepted)
        avgask = mean([fnum(x.get("accepted_proposal_ask")) for x in accepted]) if accepted else None
        avgdelay = mean([fnum(x.get("accepted_proposal_delay_sec")) for x in accepted]) if accepted else None

        line = (
            f"- {value}: N={len(items)} proposals={len(props)} accepted={len(accepted)} "
            f"settlement={correct}/{len(settled)} "
        )
        line += f"askAvg={avgask:.3f} " if avgask is not None else "askAvg=NA "
        line += f"delayAvg={avgdelay:.1f}s " if avgdelay is not None else "delayAvg=NA "
        line += f"$10HoldSum={pnl:+.2f}"
        lines.append(line)
    lines.append("")


def make_report(rows: List[dict]) -> None:
    props = [r for r in rows if str(r.get("proposal_found")) == "1"]
    accepted = [r for r in rows if str(r.get("accepted_proposal_found")) == "1"]

    lines = [
        "# Entry Authority Router V6 — Transfer → Proposal Handshake",
        "",
        "Scope: the first Hand/Boundary transfer epoch found by V5 for each stale >=9s PULLBACK_WAIT case.",
        "",
        "V6 does not assume we can magically fill at the transfer instant. It asks whether the existing V9.5A proposal stream later presented the transfer side during that same transfer epoch.",
        "",
        "Acceptance audit uses the already-existing 0.20–0.80 band:",
        "- V9.4G V94G_FIRST_VALID_MIN_ASK = 0.20",
        "- V9.4G V94G_FIRST_VALID_MAX_ASK = 0.80",
        "- legacy MAX_ENTRY_ASK = 0.80",
        "",
        f"Transfer epochs: {len(rows)}",
        f"Any post-transfer proposal before next transfer/close: {len(props)}",
        f"Post-transfer proposal inside existing 0.20–0.80 band: {len(accepted)}",
        "",
        "Counterfactual economics buy the first accepted-band proposal and hold to settlement with a $10 stake. This still does not model fills, fees, Treasury, stops, or active management.",
        "",
    ]

    report_group(lines, rows, "By transfer relation", "transfer_relation")
    report_group(lines, rows, "By transfer source", "transfer_source")
    report_group(lines, rows, "By accepted-proposal delay", "accepted_delay_bin")
    report_group(lines, rows, "By accepted-proposal price", "accepted_price_bin")

    lines += [
        "## Government interpretation",
        "",
        "- Old opportunity expiration is unchanged.",
        "- Hand/Boundary transfer creates RELEASE_ARMED / a candidate new epoch; it does not itself force an entry.",
        "- The legacy engine remains the proposal generator.",
        "- The router can require a proposal on the transfer side while that transfer epoch is still current.",
        "- The existing value band is audited here as market acceptance, not invented from V5 outcomes.",
        "- A later Hand/Boundary transfer ends the current candidate epoch and starts a new one.",
        "- No V9.5A authority changes.",
        "",
    ]
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main():
    rows = build_features()
    write_csv(OUT_FEATURES, rows, FEATURE_FIELDS)

    summary = []
    for label in sorted(set(r["run_label"] for r in rows)):
        rr = [r for r in rows if r["run_label"] == label]
        for gt, key in [
            ("relation", "transfer_relation"),
            ("source", "transfer_source"),
            ("accepted_delay", "accepted_delay_bin"),
            ("accepted_price", "accepted_price_bin"),
        ]:
            summary += summarize(rr, label, gt, key)

    for gt, key in [
        ("relation", "transfer_relation"),
        ("source", "transfer_source"),
        ("accepted_delay", "accepted_delay_bin"),
        ("accepted_price", "accepted_price_bin"),
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
