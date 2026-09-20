from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import List, Optional
from zoneinfo import ZoneInfo

RUN_DIR = Path("runs/2026-09-20_v9_5a_rs1_entry_authority_router_shadow_01")
TRADE_JOIN = Path("analysis/rs1_prospective_01/rs1_trade_join.csv")
PAPER = RUN_DIR / "tachys_paper_trades_v9_2_6.csv"
ROUTER = RUN_DIR / "tachys_entry_authority_router_shadow_v9_5a_rs1.csv"
ARCS = RUN_DIR / "tachys_ema_arcs_v9_4i.csv"

OUT_DIR = Path("analysis/rs1_battlefield_persistence_01")
OUT_CSV = OUT_DIR / "rs1_battlefield_persistence.csv"
OUT_REPORT = OUT_DIR / "rs1_battlefield_persistence_report.md"

ET = ZoneInfo("America/New_York")


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


def to_ts(v: str, local_et: bool = False) -> Optional[float]:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=ET if local_et else timezone.utc)
        return d.timestamp()
    except Exception:
        return None


def outcome_class(tr: dict) -> str:
    pnl = fnum(tr.get("actual_pnl")) or 0.0
    correct = str(tr.get("settlement_correct") or "")
    if correct == "1" and pnl > 0:
        return "RIGHT_SIDE_WIN"
    if correct == "1" and pnl < 0:
        return "RIGHT_SIDE_LOSS"
    if correct == "0" and pnl > 0:
        return "WRONG_SIDE_WIN"
    if correct == "0" and pnl < 0:
        return "WRONG_SIDE_LOSS"
    return "FLAT_OR_UNKNOWN"


def pair_exit_rows(paper: List[dict], trades: List[dict]) -> dict:
    exits = defaultdict(list)
    for r in paper:
        if str(r.get("event") or "") != "EXIT":
            continue
        x = to_ts(r.get("timestamp", ""), local_et=True)
        if x is None:
            continue
        key = (
            str(r.get("trade_id") or ""),
            str(r.get("ticker") or ""),
            str(r.get("side") or ""),
        )
        exits[key].append((x, r))
    for vals in exits.values():
        vals.sort(key=lambda z: z[0])

    out = {}
    for tr in trades:
        et = to_ts(tr.get("entry_ts", ""), local_et=True)
        if et is None:
            continue
        key = (
            str(tr.get("trade_id") or ""),
            str(tr.get("ticker") or ""),
            str(tr.get("side") or ""),
        )
        for xt, xr in exits.get(key, []):
            if xt >= et:
                out[key] = (xt, xr)
                break
    return out


def router_index(rows: List[dict]) -> dict:
    by_ticker = defaultdict(list)
    for r in rows:
        x = to_ts(r.get("timestamp", ""), local_et=False)
        if x is None:
            continue
        rr = dict(r)
        rr["_ts"] = x
        by_ticker[str(r.get("ticker") or "")].append(rr)
    for vals in by_ticker.values():
        vals.sort(key=lambda r: r["_ts"])
    return by_ticker


def trade_index(trades: List[dict]) -> dict:
    by_ticker = defaultdict(list)
    for tr in trades:
        x = to_ts(tr.get("entry_ts", ""), local_et=True)
        if x is None:
            continue
        rr = dict(tr)
        rr["_entry_ts"] = x
        by_ticker[str(tr.get("ticker") or "")].append(rr)
    for vals in by_ticker.values():
        vals.sort(key=lambda r: r["_entry_ts"])
    return by_ticker


def first_after(rows: List[dict], after_ts: float, pred) -> Optional[dict]:
    for r in rows:
        if r["_ts"] <= after_ts:
            continue
        if pred(r):
            return r
    return None


def first_trade_after(rows: List[dict], after_ts: float, pred) -> Optional[dict]:
    for r in rows:
        if r["_entry_ts"] <= after_ts:
            continue
        if pred(r):
            return r
    return None


def secs(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return b - a


def cheaper(old_ask, new_ask) -> str:
    a = fnum(old_ask)
    b = fnum(new_ask)
    if a is None or b is None:
        return ""
    return "1" if b < a else "0"


def price_improvement_cents(old_ask, new_ask) -> Optional[float]:
    a = fnum(old_ask)
    b = fnum(new_ask)
    if a is None or b is None:
        return None
    return (a - b) * 100.0


def bool_count(rows: List[dict], field: str) -> str:
    known = [r for r in rows if str(r.get(field) or "") in ("0", "1")]
    yes = sum(1 for r in known if str(r.get(field)) == "1")
    return f"{yes}/{len(known)}"


def nonblank_count(rows: List[dict], field: str) -> str:
    return f"{sum(1 for r in rows if str(r.get(field) or '') != '')}/{len(rows)}"


def median_field(rows: List[dict], field: str, digits: int = 1) -> str:
    vals = [fnum(r.get(field)) for r in rows]
    vals = [x for x in vals if x is not None]
    return "n/a" if not vals else f"{median(vals):.{digits}f}"


def write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in rows for k in r}) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    trades = read_csv(TRADE_JOIN)
    paper = read_csv(PAPER)
    router = read_csv(ROUTER)
    arcs = read_csv(ARCS)

    exit_map = pair_exit_rows(paper, trades)
    by_ticker_router = router_index(router)
    by_ticker_trades = trade_index(trades)
    arc_by_id = {str(r.get("arc_id") or ""): r for r in arcs if r.get("arc_id")}

    out = []
    for tr in trades:
        cls = outcome_class(tr)
        if cls not in ("RIGHT_SIDE_LOSS", "WRONG_SIDE_LOSS"):
            continue

        ticker = str(tr.get("ticker") or "")
        side = str(tr.get("side") or "")
        key = (str(tr.get("trade_id") or ""), ticker, side)
        exit_pair = exit_map.get(key)
        if not exit_pair:
            continue

        exit_ts, exit_row = exit_pair
        rr = by_ticker_router.get(ticker, [])
        tt = by_ticker_trades.get(ticker, [])

        same_rec = first_after(
            rr, exit_ts,
            lambda r: str(r.get("side") or "") == side
            and str(r.get("event") or "") == "FIRST_DIRECTIONAL_SHADOW",
        )
        same_prop = first_after(
            rr, exit_ts,
            lambda r: str(r.get("side") or "") == side
            and str(r.get("event") or "") == "LEGACY_PROPOSAL_SHADOW",
        )
        opp_prop = first_after(
            rr, exit_ts,
            lambda r: str(r.get("side") or "") not in ("", side)
            and str(r.get("event") or "") == "LEGACY_PROPOSAL_SHADOW",
        )
        any_prop = first_after(
            rr, exit_ts,
            lambda r: str(r.get("event") or "") == "LEGACY_PROPOSAL_SHADOW",
        )
        same_entry = first_trade_after(
            tt, exit_ts,
            lambda r: str(r.get("side") or "") == side,
        )
        opp_entry = first_trade_after(
            tt, exit_ts,
            lambda r: str(r.get("side") or "") not in ("", side),
        )

        same_arc = arc_by_id.get(str((same_prop or {}).get("arc_id") or ""), {})
        any_prop_relation = ""
        if any_prop:
            any_prop_relation = "SAME" if str(any_prop.get("side") or "") == side else "OPPOSITE"

        original_arc_id = str(tr.get("proposal_arc_id") or "")
        same_prop_arc_id = str((same_prop or {}).get("arc_id") or "")
        new_arc = ""
        if same_prop_arc_id:
            new_arc = "1" if same_prop_arc_id != original_arc_id else "0"

        settlement_correct = str(tr.get("settlement_correct") or "")
        same_reentry_correct = ""
        if same_entry:
            same_reentry_correct = str(same_entry.get("settlement_correct") or "")

        row = {
            "trade_id": tr.get("trade_id", ""),
            "ticker": ticker,
            "side": side,
            "outcome_class": cls,
            "entry_ask": tr.get("entry_ask", ""),
            "actual_pnl": tr.get("actual_pnl", ""),
            "exit_reason": tr.get("exit_reason", ""),
            "settlement_result": tr.get("settlement_result", ""),
            "settlement_correct": settlement_correct,
            "entry_ts": tr.get("entry_ts", ""),
            "exit_ts": exit_row.get("timestamp", ""),
            "exit_bid": exit_row.get("exit_bid", ""),
            "seconds_left_at_exit": exit_row.get("seconds_to_close", ""),
            "original_arc_id": original_arc_id,
            "original_arc_direction": tr.get("proposal_arc_direction", ""),
            "original_arc_age_sec": tr.get("proposal_arc_age_sec", ""),
            "original_battlefield": tr.get("proposal_battlefield_class", ""),
            "original_churn": tr.get("proposal_churn_type", ""),
            "original_dragon": tr.get("proposal_dragon_state", ""),
            "same_side_recognition_after_exit": "1" if same_rec else "0",
            "same_side_recognition_delay_sec": secs(exit_ts, (same_rec or {}).get("_ts")),
            "same_side_recognition_ask": (same_rec or {}).get("recognition_first_ask", ""),
            "same_side_proposal_after_exit": "1" if same_prop else "0",
            "same_side_proposal_delay_sec": secs(exit_ts, (same_prop or {}).get("_ts")),
            "same_side_proposal_ask": (same_prop or {}).get("proposal_ask", ""),
            "same_side_proposal_cheaper_than_original": cheaper(tr.get("entry_ask"), (same_prop or {}).get("proposal_ask")),
            "same_side_proposal_improvement_cents": price_improvement_cents(tr.get("entry_ask"), (same_prop or {}).get("proposal_ask")),
            "same_side_proposal_arc_id": same_prop_arc_id,
            "same_side_proposal_new_arc": new_arc,
            "same_side_proposal_arc_direction": (same_prop or {}).get("arc_direction", ""),
            "same_side_proposal_arc_age_sec": (same_prop or {}).get("arc_age_sec", ""),
            "same_side_proposal_battlefield": (same_prop or {}).get("battlefield_class", ""),
            "same_side_proposal_churn": (same_prop or {}).get("churn_type", ""),
            "same_side_proposal_dragon": (same_prop or {}).get("dragon_state", ""),
            "same_side_proposal_seconds_left": (same_prop or {}).get("seconds_left", ""),
            "same_side_proposal_sequence_count": same_arc.get("sequence_count", ""),
            "same_side_proposal_crest": same_arc.get("crest_progression", ""),
            "same_side_proposal_amplitude_ratio": same_arc.get("amplitude_ratio", ""),
            "first_post_exit_proposal_relation": any_prop_relation,
            "first_post_exit_proposal_delay_sec": secs(exit_ts, (any_prop or {}).get("_ts")),
            "first_post_exit_proposal_side": (any_prop or {}).get("side", ""),
            "first_opposite_proposal_delay_sec": secs(exit_ts, (opp_prop or {}).get("_ts")),
            "first_opposite_proposal_ask": (opp_prop or {}).get("proposal_ask", ""),
            "same_side_reentry": "1" if same_entry else "0",
            "same_side_reentry_delay_sec": secs(exit_ts, (same_entry or {}).get("_entry_ts")),
            "same_side_reentry_ask": (same_entry or {}).get("entry_ask", ""),
            "same_side_reentry_cheaper_than_original": cheaper(tr.get("entry_ask"), (same_entry or {}).get("entry_ask")),
            "same_side_reentry_improvement_cents": price_improvement_cents(tr.get("entry_ask"), (same_entry or {}).get("entry_ask")),
            "same_side_reentry_trade_id": (same_entry or {}).get("trade_id", ""),
            "same_side_reentry_outcome_correct": same_reentry_correct,
            "opposite_reentry": "1" if opp_entry else "0",
            "opposite_reentry_delay_sec": secs(exit_ts, (opp_entry or {}).get("_entry_ts")),
            "opposite_reentry_trade_id": (opp_entry or {}).get("trade_id", ""),
        }
        out.append(row)

    right = [r for r in out if r["outcome_class"] == "RIGHT_SIDE_LOSS"]
    wrong = [r for r in out if r["outcome_class"] == "WRONG_SIDE_LOSS"]

    def section(label: str, rows: List[dict]) -> List[str]:
        first_rel = Counter(str(r.get("first_post_exit_proposal_relation") or "NONE") for r in rows)
        return [
            f"## {label}",
            "",
            f"- Trades: {len(rows)}",
            f"- Same-side directional recognition after exit: {bool_count(rows, 'same_side_recognition_after_exit')}",
            f"- Same-side legacy proposal after exit: {bool_count(rows, 'same_side_proposal_after_exit')}",
            f"- Same-side proposal was cheaper than original entry: {bool_count(rows, 'same_side_proposal_cheaper_than_original')}",
            f"- Same-side proposal arrived on a new arc: {bool_count(rows, 'same_side_proposal_new_arc')}",
            f"- Same-side paper re-entry occurred: {bool_count(rows, 'same_side_reentry')}",
            f"- Same-side re-entry was cheaper than original entry: {bool_count(rows, 'same_side_reentry_cheaper_than_original')}",
            f"- Median delay to same-side recognition: {median_field(rows, 'same_side_recognition_delay_sec')}s",
            f"- Median delay to same-side proposal: {median_field(rows, 'same_side_proposal_delay_sec')}s",
            f"- Median same-side proposal price improvement: {median_field(rows, 'same_side_proposal_improvement_cents')}c",
            f"- First post-exit proposal relation: " + ", ".join(f"{k}={v}" for k, v in first_rel.items()),
            "",
        ]

    lines = [
        "# RS1 Battlefield Persistence / Reacquisition Forensics",
        "",
        "This pass asks whether a losing position ended while the same contract-side thesis later reappeared. It uses only existing RS1 router, paper-trade, and EMA-arc telemetry. No detector or authority change is introduced.",
        "",
    ]
    lines += section("Correct-side losing exits", right)
    lines += section("Wrong-side losing exits", wrong)

    lines += [
        "## Correct-side losing exit detail",
        "",
    ]
    for r in right:
        lines.append(
            f"- #{r['trade_id']} {r['ticker']} {r['side']} exit={r['exit_reason']} "
            f"sameRec={r['same_side_recognition_after_exit']} recDelay={r['same_side_recognition_delay_sec']} "
            f"sameProp={r['same_side_proposal_after_exit']} propDelay={r['same_side_proposal_delay_sec']} "
            f"propAsk={r['same_side_proposal_ask']} improve={r['same_side_proposal_improvement_cents']}c "
            f"newArc={r['same_side_proposal_new_arc']} seq={r['same_side_proposal_sequence_count']} "
            f"crest={r['same_side_proposal_crest']} firstProp={r['first_post_exit_proposal_relation']} "
            f"reentry={r['same_side_reentry']} reentryDelay={r['same_side_reentry_delay_sec']} "
            f"reentryAsk={r['same_side_reentry_ask']}"
        )

    lines += [
        "",
        "## Wrong-side losing exit detail",
        "",
    ]
    for r in wrong:
        lines.append(
            f"- #{r['trade_id']} {r['ticker']} {r['side']} exit={r['exit_reason']} "
            f"sameRec={r['same_side_recognition_after_exit']} recDelay={r['same_side_recognition_delay_sec']} "
            f"sameProp={r['same_side_proposal_after_exit']} propDelay={r['same_side_proposal_delay_sec']} "
            f"propAsk={r['same_side_proposal_ask']} improve={r['same_side_proposal_improvement_cents']}c "
            f"newArc={r['same_side_proposal_new_arc']} seq={r['same_side_proposal_sequence_count']} "
            f"crest={r['same_side_proposal_crest']} firstProp={r['first_post_exit_proposal_relation']} "
            f"reentry={r['same_side_reentry']} reentryDelay={r['same_side_reentry_delay_sec']} "
            f"reentryAsk={r['same_side_reentry_ask']}"
        )

    lines += [
        "",
        "## Discipline",
        "",
        "- A later same-side proposal is evidence that the proposal engine revisited the thesis; it is not proof the earlier exit was wrong.",
        "- Cheaper reappearance is a value-reset diagnostic, not a re-entry rule.",
        "- Wrong-side losing trades are kept as the control group so battlefield persistence cannot be mistaken for edge by itself.",
        "- Same-contract persistence is tested first. Rollover continuity remains a separate parent-formation question.",
        "- The architecture question is whether Tachys should preserve thesis memory after a position dies, then require fresh structure and value before any reacquisition.",
        "",
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUT_CSV, out)
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"losing exits={len(out)} right_side={len(right)} wrong_side={len(wrong)}")
    print(
        "right side persistence "
        f"recognition={sum(r['same_side_recognition_after_exit']=='1' for r in right)}/{len(right)} "
        f"proposal={sum(r['same_side_proposal_after_exit']=='1' for r in right)}/{len(right)} "
        f"reentry={sum(r['same_side_reentry']=='1' for r in right)}/{len(right)}"
    )
    print(
        "wrong side persistence "
        f"recognition={sum(r['same_side_recognition_after_exit']=='1' for r in wrong)}/{len(wrong)} "
        f"proposal={sum(r['same_side_proposal_after_exit']=='1' for r in wrong)}/{len(wrong)} "
        f"reentry={sum(r['same_side_reentry']=='1' for r in wrong)}/{len(wrong)}"
    )
    print(f"WROTE {OUT_CSV}")
    print(f"WROTE {OUT_REPORT}")


if __name__ == "__main__":
    main()
