from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

RUN_DIR = Path("runs/2026-09-20_v9_5a_rs1_entry_authority_router_shadow_01")
RS1_FILE = RUN_DIR / "tachys_entry_authority_router_shadow_v9_5a_rs1.csv"
PAPER_FILE = RUN_DIR / "tachys_paper_trades_v9_2_6.csv"
RESULTS_FILE = RUN_DIR / "tachys_contract_results_v9_2_6.csv"

OUT_DIR = Path("analysis/rs1_prospective_01")
OUT_TRADES = OUT_DIR / "rs1_trade_join.csv"
OUT_TRANSFERS = OUT_DIR / "rs1_transfer_forensics.csv"
OUT_REPORT = OUT_DIR / "rs1_prospective_report.md"

OBSERVED_CONTRACT = "KXBTC15M-26SEP200315-15"

TRADE_FIELDS = [
    "trade_id","ticker","side","entry_ts","entry_ask","qty","actual_pnl","actual_roi_pct",
    "exit_reason","mfe_pct","mae_pct","settlement_result","settlement_correct",
    "hold_to_settlement_pnl","proposal_ts","proposal_delay_from_recognition_sec",
    "proposal_recognition_age_sec","proposal_expired9","proposal_prior_state",
    "proposal_transfer_id","proposal_transfer_relation","proposal_transfer_age_sec",
    "proposal_accepted_20_80","proposal_price_arc_phase","proposal_arc_id",
    "proposal_arc_direction","proposal_arc_age_sec","proposal_remaining_capacity",
    "proposal_battlefield_class","proposal_zoom_mode","proposal_boss_side",
    "proposal_hand_side","proposal_territory_state","proposal_churn_type",
    "proposal_cage_state","proposal_dragon_state","proposal_seconds_left",
    "proposal_target_distance","proposal_trade_intent","proposal_strategy",
    "proposal_signal_grade","proposal_setup_grade",
]

TRANSFER_FIELDS = [
    "transfer_id","ticker","side","source","transfer_ts","transfer_relation",
    "transfer_age_sec","transfer_ask","transfer_prior_state","accepted_at_transfer",
    "acceptance_seen","acceptance_delay_sec","accepted_ask",
    "proposal_seen","first_proposal_ts","proposal_delay_sec","proposal_ask",
    "proposal_trade_intent","proposal_strategy","proposal_expired9",
    "proposal_battlefield_class","proposal_churn_type","proposal_dragon_state",
    "settlement_result","settlement_correct","hold_from_transfer_pnl_10",
    "hold_from_accepted_pnl_10",
]


def read_csv(path: Path) -> List[dict]:
    if not path.exists():
        raise SystemExit(f"Missing {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def fnum(v) -> Optional[float]:
    try:
        if v in (None, ""):
            return None
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def parse_ts(v: str, paper_local: bool = False) -> Optional[float]:
    if not v:
        return None
    s = str(v).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        if dt.tzinfo is None:
            from zoneinfo import ZoneInfo
            dt = dt.replace(tzinfo=ZoneInfo("America/New_York") if paper_local else timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def write_csv(path: Path, rows: List[dict], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def settlement_map(rows: List[dict]) -> Dict[str,str]:
    out = {}
    for r in rows:
        ticker = str(r.get("ticker") or "")
        result = str(r.get("result") or "").upper()
        if ticker and result in ("YES","NO"):
            out[ticker] = result
    return out


def pair_paper_trades(rows: List[dict]) -> List[dict]:
    exits = defaultdict(list)
    for r in rows:
        if r.get("event") != "EXIT":
            continue
        key = (str(r.get("trade_id") or ""), str(r.get("ticker") or ""), str(r.get("side") or ""))
        ts = parse_ts(r.get("timestamp",""), paper_local=True)
        if ts is not None:
            exits[key].append((ts,r))
    for v in exits.values():
        v.sort(key=lambda x:x[0])

    out = []
    for e in rows:
        if e.get("event") != "ENTRY":
            continue
        key = (str(e.get("trade_id") or ""), str(e.get("ticker") or ""), str(e.get("side") or ""))
        ets = parse_ts(e.get("timestamp",""), paper_local=True)
        x = None
        if ets is not None:
            for xts, xr in exits.get(key,[]):
                if xts >= ets:
                    x = xr
                    break
        out.append({"entry":e,"exit":x,"entry_ts":ets})
    return out


def nearest_proposal(entry: dict, ets: float, proposals: List[dict]) -> Optional[dict]:
    ticker = str(entry.get("ticker") or "")
    side = str(entry.get("side") or "")
    ask = fnum(entry.get("entry_ask"))
    best = None
    best_dt = None
    for p in proposals:
        if p.get("ticker") != ticker or p.get("side") != side:
            continue
        pts = parse_ts(p.get("timestamp",""), paper_local=False)
        if pts is None:
            continue
        dt = abs(pts - ets)
        if dt > 3.0:
            continue
        pa = fnum(p.get("proposal_ask"))
        if ask is not None and pa is not None and abs(ask-pa) > 0.021:
            continue
        if best_dt is None or dt < best_dt:
            best = p
            best_dt = dt
    return best


def pnl10(side: str, ask: Optional[float], settlement: str) -> Optional[float]:
    if ask is None or ask <= 0 or settlement not in ("YES","NO"):
        return None
    return 10.0 * (((1.0-ask)/ask) if side == settlement else -1.0)


def trade_join(rs: List[dict], paper: List[dict], settlements: Dict[str,str]) -> List[dict]:
    proposals = [r for r in rs if r.get("event") == "LEGACY_PROPOSAL_SHADOW"]
    out = []
    for t in pair_paper_trades(paper):
        e, x, ets = t["entry"], t["exit"], t["entry_ts"]
        if ets is None:
            continue
        p = nearest_proposal(e, ets, proposals)
        side = str(e.get("side") or "")
        ticker = str(e.get("ticker") or "")
        settlement = settlements.get(ticker,"")
        entry_ask = fnum(e.get("entry_ask"))
        qty = fnum(e.get("qty")) or 0.0
        hold = None
        if entry_ask is not None and settlement in ("YES","NO"):
            hold = qty * ((1.0-entry_ask) if settlement == side else -entry_ask)

        row = {
            "trade_id": e.get("trade_id",""),
            "ticker": ticker,
            "side": side,
            "entry_ts": e.get("timestamp",""),
            "entry_ask": e.get("entry_ask",""),
            "qty": e.get("qty",""),
            "actual_pnl": x.get("pnl","") if x else "",
            "actual_roi_pct": x.get("roi_pct","") if x else "",
            "exit_reason": x.get("reason","") if x else "",
            "mfe_pct": x.get("mfe_pct","") if x else "",
            "mae_pct": x.get("mae_pct","") if x else "",
            "settlement_result": settlement,
            "settlement_correct": int(bool(settlement) and side == settlement) if settlement else "",
            "hold_to_settlement_pnl": round(hold,4) if hold is not None else "",
        }

        if p:
            row.update({
                "proposal_ts": p.get("timestamp",""),
                "proposal_delay_from_recognition_sec": p.get("proposal_delay_sec",""),
                "proposal_recognition_age_sec": p.get("recognition_age_sec",""),
                "proposal_expired9": p.get("expired9",""),
                "proposal_prior_state": p.get("prior_state",""),
                "proposal_transfer_id": p.get("transfer_id",""),
                "proposal_transfer_relation": p.get("transfer_relation",""),
                "proposal_transfer_age_sec": p.get("transfer_age_sec",""),
                "proposal_accepted_20_80": p.get("accepted_20_80",""),
                "proposal_price_arc_phase": p.get("price_arc_phase",""),
                "proposal_arc_id": p.get("arc_id",""),
                "proposal_arc_direction": p.get("arc_direction",""),
                "proposal_arc_age_sec": p.get("arc_age_sec",""),
                "proposal_remaining_capacity": p.get("remaining_capacity",""),
                "proposal_battlefield_class": p.get("battlefield_class",""),
                "proposal_zoom_mode": p.get("zoom_mode",""),
                "proposal_boss_side": p.get("boss_side",""),
                "proposal_hand_side": p.get("hand_side",""),
                "proposal_territory_state": p.get("territory_state",""),
                "proposal_churn_type": p.get("churn_type",""),
                "proposal_cage_state": p.get("cage_state",""),
                "proposal_dragon_state": p.get("dragon_state",""),
                "proposal_seconds_left": p.get("seconds_left",""),
                "proposal_target_distance": p.get("target_distance",""),
                "proposal_trade_intent": p.get("proposal_trade_intent",""),
                "proposal_strategy": p.get("proposal_strategy",""),
                "proposal_signal_grade": p.get("proposal_signal_grade",""),
                "proposal_setup_grade": p.get("proposal_setup_grade",""),
            })
        out.append(row)
    return out


def transfer_forensics(rs: List[dict], settlements: Dict[str,str]) -> List[dict]:
    armed = [r for r in rs if r.get("event") == "TRANSFER_ARMED_SHADOW"]
    accepted = defaultdict(list)
    proposals = defaultdict(list)
    for r in rs:
        tid = str(r.get("transfer_id") or "")
        if not tid:
            continue
        if r.get("event") == "TRANSFER_ACCEPTED_SHADOW":
            accepted[tid].append(r)
        elif r.get("event") == "LEGACY_PROPOSAL_SHADOW":
            proposals[tid].append(r)

    out = []
    for a in armed:
        tid = str(a.get("transfer_id") or "")
        accs = sorted(accepted.get(tid,[]), key=lambda r: parse_ts(r.get("timestamp",""),False) or 10**20)
        props = sorted(proposals.get(tid,[]), key=lambda r: parse_ts(r.get("timestamp",""),False) or 10**20)
        acc = accs[0] if accs else None
        prop = props[0] if props else None

        ticker = str(a.get("ticker") or "")
        side = str(a.get("side") or "")
        settlement = settlements.get(ticker,"")
        transfer_ask = fnum(a.get("transfer_ask"))
        accepted_ask = fnum(acc.get("transfer_ask")) if acc else None

        transfer_hold = pnl10(side,transfer_ask,settlement)
        accepted_hold = pnl10(side,accepted_ask,settlement)

        row = {
            "transfer_id": tid,
            "ticker": ticker,
            "side": side,
            "source": a.get("source",""),
            "transfer_ts": a.get("timestamp",""),
            "transfer_relation": a.get("transfer_relation",""),
            "transfer_age_sec": a.get("transfer_age_sec",""),
            "transfer_ask": a.get("transfer_ask",""),
            "transfer_prior_state": a.get("prior_state",""),
            "accepted_at_transfer": int(str(a.get("accepted_20_80") or "0") == "1"),
            "acceptance_seen": int(bool(acc)),
            "acceptance_delay_sec": acc.get("acceptance_delay_sec","") if acc else "",
            "accepted_ask": accepted_ask if accepted_ask is not None else "",
            "proposal_seen": int(bool(prop)),
            "first_proposal_ts": prop.get("timestamp","") if prop else "",
            "proposal_delay_sec": prop.get("proposal_delay_sec","") if prop else "",
            "proposal_ask": prop.get("proposal_ask","") if prop else "",
            "proposal_trade_intent": prop.get("proposal_trade_intent","") if prop else "",
            "proposal_strategy": prop.get("proposal_strategy","") if prop else "",
            "proposal_expired9": prop.get("expired9","") if prop else "",
            "proposal_battlefield_class": prop.get("battlefield_class","") if prop else "",
            "proposal_churn_type": prop.get("churn_type","") if prop else "",
            "proposal_dragon_state": prop.get("dragon_state","") if prop else "",
            "settlement_result": settlement,
            "settlement_correct": int(bool(settlement) and side == settlement) if settlement else "",
            "hold_from_transfer_pnl_10": round(transfer_hold,4) if transfer_hold is not None else "",
            "hold_from_accepted_pnl_10": round(accepted_hold,4) if accepted_hold is not None else "",
        }
        out.append(row)
    return out


def group_trade(rows: List[dict], key: str) -> List[str]:
    groups = defaultdict(list)
    for r in rows:
        groups[str(r.get(key) or "(blank)")].append(r)
    lines = []
    for val, items in sorted(groups.items()):
        pnls = [fnum(x.get("actual_pnl")) for x in items]
        pnls = [x for x in pnls if x is not None]
        wins = sum(1 for x in pnls if x > 0)
        known = [x for x in items if x.get("settlement_correct") not in ("",None)]
        correct = sum(int(x.get("settlement_correct") or 0) for x in known)
        lines.append(
            f"- {val}: N={len(items)} actualPnL=$" + f"{sum(pnls):+.2f} "
            f"wins={wins}/{len(pnls)} settlement={correct}/{len(known)}"
        )
    return lines


def make_report(rs: List[dict], trades: List[dict], transfers: List[dict], settlements: Dict[str,str]) -> None:
    events = Counter(str(r.get("event") or "") for r in rs)
    pnls = [fnum(r.get("actual_pnl")) for r in trades]
    pnls = [x for x in pnls if x is not None]
    wins = sum(1 for x in pnls if x > 0)
    losses = sum(1 for x in pnls if x < 0)

    expired = [r for r in trades if str(r.get("proposal_expired9")) == "1"]
    young = [r for r in trades if str(r.get("proposal_expired9")) == "0"]
    matched = [r for r in trades if r.get("proposal_ts")]

    accepted = [r for r in transfers if str(r.get("acceptance_seen")) == "1"]
    proposed = [r for r in transfers if str(r.get("proposal_seen")) == "1"]
    accepted_proposed = [r for r in accepted if str(r.get("proposal_seen")) == "1"]

    transfer_known = [r for r in transfers if r.get("settlement_correct") not in ("",None)]
    transfer_correct = sum(int(r.get("settlement_correct") or 0) for r in transfer_known)
    accepted_known = [r for r in accepted if r.get("settlement_correct") not in ("",None)]
    accepted_correct = sum(int(r.get("settlement_correct") or 0) for r in accepted_known)

    obs = [r for r in trades if r.get("ticker") == OBSERVED_CONTRACT]

    lines = [
        "# RS1 Prospective Entry-Authority Run — First Forensic Pass",
        "",
        f"Run folder: {RUN_DIR}",
        "",
        "## Run headline",
        "",
        f"- RS1 event rows: {len(rs)}",
        f"- Paper entries paired: {len(trades)}",
        f"- Matched to RS1 legacy proposals: {len(matched)}/{len(trades)}",
        "- Realized paper P&L: $" + f"{sum(pnls):+.2f}",
        f"- Paper wins/losses: {wins}/{losses}",
        f"- Settled contracts recorded: {len(settlements)}",
        "",
        "## RS1 event counts",
        "",
    ]
    for k,v in sorted(events.items()):
        lines.append(f"- {k}: {v}")

    lines += [
        "",
        "## Opportunity age at actual paper entries",
        "",
        f"- Young (<9s research clock): N={len(young)} actualPnL=$" + f"{sum(fnum(r.get('actual_pnl')) or 0 for r in young):+.2f}",
        f"- Expired (>=9s research clock): N={len(expired)} actualPnL=$" + f"{sum(fnum(r.get('actual_pnl')) or 0 for r in expired):+.2f}",
        "",
        "## Paper entries by battlefield class",
        "",
        *group_trade(trades,"proposal_battlefield_class"),
        "",
        "## Paper entries by churn type",
        "",
        *group_trade(trades,"proposal_churn_type"),
        "",
        "## Paper entries by dragon state",
        "",
        *group_trade(trades,"proposal_dragon_state"),
        "",
        "## Prospective structural transfers",
        "",
        f"- TRANSFER_ARMED: {len(transfers)}",
        f"- Transfer side later/at-once accepted in existing 20c–80c band: {len(accepted)}/{len(transfers)}",
        f"- Transfer epoch later received a legacy proposal: {len(proposed)}/{len(transfers)}",
        f"- Accepted transfer epoch later received a legacy proposal: {len(accepted_proposed)}/{len(accepted)}",
        f"- Raw transfer-side settlement correctness: {transfer_correct}/{len(transfer_known)}",
        f"- Accepted transfer-side settlement correctness: {accepted_correct}/{len(accepted_known)}",
        "",
        "### By transfer source",
        "",
    ]

    by_source = defaultdict(list)
    for r in transfers:
        by_source[r.get("source") or "(blank)"].append(r)
    for src, items in sorted(by_source.items()):
        known = [x for x in items if x.get("settlement_correct") not in ("",None)]
        corr = sum(int(x.get("settlement_correct") or 0) for x in known)
        acc = sum(int(x.get("acceptance_seen") or 0) for x in items)
        prop = sum(int(x.get("proposal_seen") or 0) for x in items)
        lines.append(f"- {src}: N={len(items)} accepted={acc} proposals={prop} settlement={corr}/{len(known)}")

    lines += [
        "",
        f"## Observed compression contract: {OBSERVED_CONTRACT}",
        "",
    ]
    for r in obs:
        lines.append(
            f"- Trade #{r['trade_id']} {r['side']} @ {r['entry_ask']} "
            "actual=$" + f"{fnum(r.get('actual_pnl')) or 0:+.2f} "
            f"exit={r.get('exit_reason')} MFE={r.get('mfe_pct')} MAE={r.get('mae_pct')} "
            f"battlefield={r.get('proposal_battlefield_class')} "
            f"churn={r.get('proposal_churn_type')} dragon={r.get('proposal_dragon_state')} "
            f"age={r.get('proposal_recognition_age_sec')} expired9={r.get('proposal_expired9')} "
            f"settle={r.get('settlement_result')} holdToSettle={r.get('hold_to_settlement_pnl')}"
        )

    lines += [
        "",
        "## Interpretation discipline",
        "",
        "- RS1 was prospective and shadow-only; V9.5A paper authority remained unchanged.",
        "- The 9-second boundary is still a research clock, not promoted authority.",
        "- Transfer and 20c–80c acceptance are context, not an entry rule.",
        "- Settlement-hold counterfactuals ignore Treasury, fills, fees, and active management.",
        "- The next pass should specifically test the observed PT/EMA/price compression -> snake -> mountain/leg sequence, including rollover continuity, without inventing a new detector before existing telemetry is exhausted.",
        "",
    ]

    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rs = read_csv(RS1_FILE)
    paper = read_csv(PAPER_FILE)
    results = read_csv(RESULTS_FILE)
    settlements = settlement_map(results)

    trades = trade_join(rs,paper,settlements)
    transfers = transfer_forensics(rs,settlements)

    write_csv(OUT_TRADES,trades,TRADE_FIELDS)
    write_csv(OUT_TRANSFERS,transfers,TRANSFER_FIELDS)
    make_report(rs,trades,transfers,settlements)

    print(f"RS1 rows={len(rs)}")
    print(f"paper entries={len(trades)}")
    print(f"transfers={len(transfers)}")
    print(f"WROTE {OUT_TRADES}")
    print(f"WROTE {OUT_TRANSFERS}")
    print(f"WROTE {OUT_REPORT}")


if __name__ == "__main__":
    main()
