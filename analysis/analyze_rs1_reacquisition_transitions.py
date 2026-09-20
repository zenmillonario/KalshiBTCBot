from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import List, Optional

PERSIST = Path("analysis/rs1_battlefield_persistence_01/rs1_battlefield_persistence.csv")
TRADES = Path("analysis/rs1_prospective_01/rs1_trade_join.csv")

OUT_DIR = Path("analysis/rs1_reacquisition_transitions_01")
OUT_CSV = OUT_DIR / "rs1_reacquisition_transitions.csv"
OUT_REPORT = OUT_DIR / "rs1_reacquisition_transitions_report.md"


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


def summarize(rows: List[dict], label: str) -> str:
    pnl = sum(fnum(r.get("reentry_pnl")) or 0.0 for r in rows)
    wins = sum(1 for r in rows if (fnum(r.get("reentry_pnl")) or 0.0) > 0)
    settle = sum(1 for r in rows if str(r.get("reentry_settlement_correct") or "") == "1")
    cheaper_known = [r for r in rows if str(r.get("reentry_cheaper") or "") in ("0", "1")]
    cheaper = sum(1 for r in cheaper_known if str(r.get("reentry_cheaper")) == "1")
    delays = [fnum(r.get("reentry_delay_sec")) for r in rows]
    delays = [x for x in delays if x is not None]
    med_delay = f"{median(delays):.1f}s" if delays else "n/a"
    return (
        f"- {label}: N={len(rows)} reentryWins={wins}/{len(rows)} "
        f"reentryPnL=${pnl:+.2f} settlementCorrect={settle}/{len(rows)} "
        f"cheaper={cheaper}/{len(cheaper_known)} medianDelay={med_delay}"
    )


def main() -> None:
    persist = read_csv(PERSIST)
    trades = read_csv(TRADES)
    by_id = {str(r.get("trade_id") or ""): r for r in trades}

    rows = []
    for p in persist:
        if str(p.get("same_side_reentry") or "") != "1":
            continue
        rid = str(p.get("same_side_reentry_trade_id") or "")
        r = by_id.get(rid)
        if not r:
            continue

        parent_pnl = fnum(p.get("actual_pnl")) or 0.0
        re_pnl = fnum(r.get("actual_pnl")) or 0.0
        new_arc = str(p.get("same_side_proposal_new_arc") or "")
        cheaper = str(p.get("same_side_reentry_cheaper_than_original") or "")

        rows.append({
            "parent_trade_id": p.get("trade_id", ""),
            "parent_outcome_class": p.get("outcome_class", ""),
            "parent_side": p.get("side", ""),
            "parent_entry_ask": p.get("entry_ask", ""),
            "parent_exit_reason": p.get("exit_reason", ""),
            "parent_pnl": parent_pnl,
            "parent_settlement_correct": p.get("settlement_correct", ""),
            "parent_arc_id": p.get("original_arc_id", ""),
            "parent_arc_direction": p.get("original_arc_direction", ""),
            "reentry_trade_id": rid,
            "reentry_entry_ask": r.get("entry_ask", ""),
            "reentry_pnl": re_pnl,
            "reentry_profitable": int(re_pnl > 0),
            "reentry_settlement_correct": r.get("settlement_correct", ""),
            "reentry_exit_reason": r.get("exit_reason", ""),
            "reentry_delay_sec": p.get("same_side_reentry_delay_sec", ""),
            "reentry_cheaper": cheaper,
            "price_improvement_cents": p.get("same_side_reentry_improvement_cents", ""),
            "new_arc": new_arc,
            "reentry_arc_id": p.get("same_side_proposal_arc_id", ""),
            "reentry_arc_direction": p.get("same_side_proposal_arc_direction", ""),
            "reentry_sequence_count": p.get("same_side_proposal_sequence_count", ""),
            "reentry_crest": p.get("same_side_proposal_crest", ""),
            "reentry_battlefield": p.get("same_side_proposal_battlefield", ""),
            "reentry_churn": p.get("same_side_proposal_churn", ""),
            "reentry_dragon": p.get("same_side_proposal_dragon", ""),
            "first_post_exit_proposal_relation": p.get("first_post_exit_proposal_relation", ""),
            "transition_pair_pnl": parent_pnl + re_pnl,
        })

    groups = defaultdict(list)
    for r in rows:
        groups[(r["parent_outcome_class"], r["new_arc"])].append(r)

    right = [r for r in rows if r["parent_outcome_class"] == "RIGHT_SIDE_LOSS"]
    wrong = [r for r in rows if r["parent_outcome_class"] == "WRONG_SIDE_LOSS"]

    lines = [
        "# RS1 Reacquisition Transition Forensics",
        "",
        "This pass studies only actual same-side re-entries after a losing exit. It is transition-level evidence, not a new entry rule or authority change.",
        "",
        "## Actual same-side re-entry transitions",
        "",
        summarize(rows, "ALL"),
        summarize(right, "RIGHT_SIDE_LOSS parent"),
        summarize(wrong, "WRONG_SIDE_LOSS parent"),
        "",
        "## Parent correctness x arc reset",
        "",
    ]

    order = [
        ("RIGHT_SIDE_LOSS", "1", "Correct-side parent -> NEW arc"),
        ("RIGHT_SIDE_LOSS", "0", "Correct-side parent -> SAME arc"),
        ("WRONG_SIDE_LOSS", "1", "Wrong-side parent -> NEW arc"),
        ("WRONG_SIDE_LOSS", "0", "Wrong-side parent -> SAME arc"),
    ]
    for k1, k2, label in order:
        subset = groups.get((k1, k2), [])
        if subset:
            lines.append(summarize(subset, label))

    lines += [
        "",
        "## Transition detail",
        "",
    ]
    for r in rows:
        lines.append(
            f"- #{r['parent_trade_id']} -> #{r['reentry_trade_id']} "
            f"{r['parent_outcome_class']} {r['parent_side']} "
            f"newArc={r['new_arc']} seq={r['reentry_sequence_count']} crest={r['reentry_crest']} "
            f"ask {r['parent_entry_ask']} -> {r['reentry_entry_ask']} "
            f"cheaper={r['reentry_cheaper']} delay={r['reentry_delay_sec']}s "
            f"reentryPnL=${(fnum(r['reentry_pnl']) or 0):+.2f} "
            f"reentrySettlementCorrect={r['reentry_settlement_correct']} "
            f"exit={r['reentry_exit_reason']}"
        )

    lines += [
        "",
        "## Interpretation discipline",
        "",
        "- A new arc is tested as structural regeneration after a dead position; it is not assumed to prove direction.",
        "- Parent settlement correctness is known only after the contract settles and therefore cannot be used prospectively as a feature.",
        "- This tiny RS1 transition set is useful for architecture design, not threshold fitting.",
        "- Same-arc retry versus new-arc regeneration is deliberately separated because the watched contract showed both behaviors.",
        "- Price improvement is descriptive only. A structurally regenerated opportunity may reappear at a worse price, and a cheaper retry may still be bad.",
        "- Any future implementation should remain shadow-only first and should preserve V9.5A trading authority.",
        "",
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["empty"]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    right_new = groups.get(("RIGHT_SIDE_LOSS", "1"), [])
    right_same = groups.get(("RIGHT_SIDE_LOSS", "0"), [])
    wrong_new = groups.get(("WRONG_SIDE_LOSS", "1"), [])

    def wins(xs):
        return sum(1 for r in xs if int(r["reentry_profitable"]) == 1)

    print(f"reentry transitions={len(rows)}")
    print(f"right-side parent: new-arc {wins(right_new)}/{len(right_new)} profitable; same-arc {wins(right_same)}/{len(right_same)} profitable")
    print(f"wrong-side parent: new-arc {wins(wrong_new)}/{len(wrong_new)} profitable")
    print(f"WROTE {OUT_CSV}")
    print(f"WROTE {OUT_REPORT}")


if __name__ == "__main__":
    main()
