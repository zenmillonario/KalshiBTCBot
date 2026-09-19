#!/usr/bin/env python3
"""
Offline Battlefield Router Shadow replay.

Research only. This file DOES NOT import or call the trading engine and cannot
place paper/live orders. It consumes frozen CSV telemetry and produces a
router-oriented replay table plus a JSON summary.

Example:
  python research/replay_battlefield_router_shadow.py ^
    --run-dir runs/tachys_v9_5a_price_freshness_active_treasury ^
    --start-local "2026-09-18 19:33:35" ^
    --out-prefix router_v1_v95a

The point is not to optimize a new strategy. The point is to expose:
- campaign/chapter identity,
- mission at birth,
- later campaign promotion,
- contradiction between trade side and Boss/Hand,
- first raid-harvest opportunity,
- whether management killed a settlement-correct thesis,
- first-entry vs same-contract re-entry.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


PAPER = "tachys_paper_trades_v9_2_6.csv"
MISSIONS = "tachys_trade_missions_v9_4i.csv"
LEDGER = "tachys_campaign_ledger_v9_4m.csv"
TIMING = "tachys_entry_timing_v9_4j.csv"
RESULTS = "tachys_contract_results_v9_2_6.csv"

HARVEST_ACTION = "HARVEST_EDGE_SHADOW"
PROMOTION_ACTIONS = {"RAID_TO_CAMPAIGN_SHADOW", "ATTACK_TO_CAMPAIGN_SHADOW"}


def read_csv(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fnum(v, default=None):
    try:
        if v is None or str(v).strip() == "":
            return default
        return float(v)
    except Exception:
        return default


def in_run_local(row: dict, start_local: Optional[str]) -> bool:
    if not start_local:
        return True
    ts = (row.get("timestamp") or "").strip()
    # paper/results use YYYY-MM-DD HH:MM:SS local time.
    return ts >= start_local


def run_id_matches(row: dict, suffix: Optional[str]) -> bool:
    if not suffix:
        return True
    rid = row.get("run_id") or ""
    return rid.endswith(suffix)


def contradiction(side: str, boss: str, hand: str, mission: str) -> str:
    valid = {"YES", "NO"}
    if boss not in valid or hand not in valid:
        return "C0_UNRESOLVED"
    agree = int(side == boss) + int(side == hand)
    if agree == 2:
        return "C0_ALIGNED"
    if agree == 1:
        return "C1_LOCAL_DISSENT"
    if mission in {"RAID", "SCOUT", "ATTACK"}:
        return "C2_TACTICAL_COUNTERTREND"
    return "C3_AUTHORITY_TRANSFER_CANDIDATE"


def manager_for(mission: str, entry_mode: str, seconds_left: Optional[float]) -> str:
    # Research routing only. 180s marks a settlement-candidate zone, not an
    # automatic live/paper authority transfer.
    if seconds_left is not None and seconds_left <= 180:
        return "SETTLEMENT_CANDIDATE_MANAGER"
    if mission == "CAMPAIGN":
        return "CAMPAIGN_MANAGER"
    if mission == "CAMPAIGN_CANDIDATE":
        return "RAID_MANAGER_UNTIL_PROMOTION"
    if mission in {"RAID", "ATTACK", "SCOUT"}:
        return "RAID_MANAGER"
    if entry_mode == "EARLY_IMPULSE":
        return "IMPULSE_MANAGER"
    return "UNRESOLVED_MANAGER"


def entry_mode_from(entry: dict) -> str:
    intent = (entry.get("trade_intent") or "").strip()
    strategy = (entry.get("strategy") or "").strip()
    if intent:
        return intent
    if "HANDOFF" in strategy:
        return "HANDOFF"
    if "IMPULSE" in strategy:
        return "EARLY_IMPULSE"
    return "UNKNOWN"


def summarize(rows: List[dict]) -> dict:
    def agg(items: Iterable[dict]) -> dict:
        xs = list(items)
        pnl = sum(fnum(x.get("actual_pnl"), 0.0) or 0.0 for x in xs)
        w = sum((fnum(x.get("actual_pnl"), 0.0) or 0.0) > 0 for x in xs)
        l = sum((fnum(x.get("actual_pnl"), 0.0) or 0.0) < 0 for x in xs)
        return {"n": len(xs), "wins": w, "losses": l, "pnl": round(pnl, 3)}

    first = [x for x in rows if x.get("contract_trade_number") == "1"]
    later = [x for x in rows if x.get("contract_trade_number") != "1"]
    immediate_campaign = [x for x in rows if x.get("assigned_mission") == "CAMPAIGN"]
    promoted = [x for x in rows if x.get("promoted_to_campaign") == "1"]
    correct_lost = [
        x for x in rows
        if x.get("settlement_correct") == "1" and (fnum(x.get("actual_pnl"), 0) or 0) < 0
    ]

    by_router_mission = {}
    for key in sorted({x.get("router_birth_mission") for x in rows}):
        by_router_mission[key] = agg(x for x in rows if x.get("router_birth_mission") == key)

    by_chapter = {}
    for key in sorted({x.get("chapter_label") for x in rows}):
        by_chapter[key] = agg(x for x in rows if x.get("chapter_label") == key)

    return {
        "rows": len(rows),
        "first_entries": agg(first),
        "same_contract_reentries": agg(later),
        "immediate_campaign_assignments": agg(immediate_campaign),
        "eventually_promoted_to_campaign": agg(promoted),
        "settlement_correct_but_lost": agg(correct_lost),
        "by_router_birth_mission": by_router_mission,
        "by_chapter": by_chapter,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--start-local", default=None,
                    help='Filter paper/results local timestamps, e.g. "2026-09-18 19:33:35"')
    ap.add_argument("--run-id-suffix", default=None,
                    help='Optional suffix for observer run_id, e.g. "20260918_193335"')
    ap.add_argument("--out-prefix", default="battlefield_router_shadow")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    paper = [r for r in read_csv(run_dir / PAPER) if in_run_local(r, args.start_local)]
    missions = read_csv(run_dir / MISSIONS)
    ledger = read_csv(run_dir / LEDGER)
    timing = read_csv(run_dir / TIMING)
    results = [r for r in read_csv(run_dir / RESULTS) if in_run_local(r, args.start_local)]

    if args.run_id_suffix:
        ledger = [r for r in ledger if run_id_matches(r, args.run_id_suffix)]
        timing = [r for r in timing if run_id_matches(r, args.run_id_suffix)]

    entries = {r["trade_id"]: r for r in paper if r.get("event") == "ENTRY"}
    exits = {r["trade_id"]: r for r in paper if r.get("event") == "EXIT"}
    result_by_ticker = {r.get("ticker"): r.get("result") for r in results if r.get("ticker")}

    mission_assign = {}
    mission_final = {}
    mission_events = defaultdict(list)
    for r in missions:
        tid = r.get("trade_id")
        if not tid or tid not in entries:
            continue
        mission_events[tid].append(r)
        if r.get("event") == "ASSIGN" and tid not in mission_assign:
            mission_assign[tid] = r
        if r.get("event") == "FINAL":
            mission_final[tid] = r

    ledger_entry = {}
    for r in ledger:
        tid = r.get("trade_id")
        if tid in entries and r.get("event") == "REAL_ENTRY":
            ledger_entry[tid] = r

    timing_entry = {}
    for r in timing:
        tid = r.get("trade_id")
        if tid in entries and r.get("event") == "ENTERED":
            timing_entry[tid] = r

    # Fallback contract trade number if Campaign Ledger is unavailable.
    contract_counts = defaultdict(int)
    trade_numbers = {}
    for e in sorted(entries.values(), key=lambda x: x.get("timestamp") or ""):
        ticker = e.get("ticker")
        contract_counts[ticker] += 1
        trade_numbers[e["trade_id"]] = contract_counts[ticker]

    rows = []
    for tid, e in sorted(entries.items(), key=lambda kv: int(kv[0])):
        ex = exits.get(tid, {})
        le = ledger_entry.get(tid, {})
        te = timing_entry.get(tid, {})
        ma = mission_assign.get(tid, {})

        events = sorted(mission_events.get(tid, []), key=lambda x: x.get("timestamp") or "")
        promotion = next((x for x in events if x.get("shadow_action") in PROMOTION_ACTIONS), None)
        first_harvest = next((x for x in events if x.get("shadow_action") == HARVEST_ACTION), None)

        assigned = ma.get("mission") or te.get("mission") or "UNKNOWN"

        # Router V1 does not grant full campaign status at birth.
        # Existing immediate CAMPAIGN becomes CAMPAIGN_CANDIDATE until evidence
        # later earns promotion. Existing tactical missions remain tactical.
        if assigned == "CAMPAIGN":
            router_birth = "CAMPAIGN_CANDIDATE"
        else:
            router_birth = assigned

        side = e.get("side") or ""
        boss = te.get("boss_side") or le.get("boss_side") or ""
        hand = te.get("hand_side") or le.get("hand_side") or ma.get("hand_authority") or ""
        cclass = contradiction(side, boss, hand, router_birth)

        seconds_left = fnum(e.get("seconds_to_close"), fnum(te.get("seconds_left")))
        entry_mode = entry_mode_from(e)

        # At the instant of first harvest, promotion only counts if it has
        # already happened. This avoids future leakage.
        harvest_action = ""
        if first_harvest:
            promo_before_harvest = bool(
                promotion and (promotion.get("timestamp") or "") <= (first_harvest.get("timestamp") or "")
            )
            harvest_action = "HOLD_FOR_EARNED_CAMPAIGN" if promo_before_harvest else "HARVEST_RAID_SHADOW"

        settle = result_by_ticker.get(e.get("ticker")) or ""
        settlement_correct = "1" if settle and side == settle else ("0" if settle else "")

        actual_pnl = fnum(ex.get("pnl"), 0.0) or 0.0
        correct_but_lost = "1" if settlement_correct == "1" and actual_pnl < 0 else "0"

        exit_reason = ex.get("reason") or ""
        if exit_reason in {"EMA9_ARC_BROKEN", "ANTICIPATION_FAST_FAIL"}:
            observed_invalidation = "MICRO_OR_LEG_BREAK"
        elif exit_reason in {"V92_STRUCTURE_BROKEN", "KING_GUARD_FAILSAFE"}:
            observed_invalidation = "STRUCTURAL_BREAK"
        elif exit_reason == "LATE_TARGET_INVALIDATION":
            observed_invalidation = "SETTLEMENT_BREAK"
        elif exit_reason:
            observed_invalidation = "MANAGER_OTHER"
        else:
            observed_invalidation = ""

        contract_trade_number = le.get("contract_trade_number") or str(trade_numbers.get(tid, ""))

        row = {
            "trade_id": tid,
            "entry_timestamp": e.get("timestamp"),
            "ticker": e.get("ticker"),
            "side": side,
            "contract_trade_number": contract_trade_number,
            "entry_mode": entry_mode,
            "assigned_mission": assigned,
            "router_birth_mission": router_birth,
            "promoted_to_campaign": "1" if promotion else "0",
            "promotion_timestamp": promotion.get("timestamp") if promotion else "",
            "promotion_action": promotion.get("shadow_action") if promotion else "",
            "chapter_label": le.get("chapter_label") or "",
            "chapter_score": le.get("chapter_score") or "",
            "chapter_reasons": le.get("chapter_reasons") or "",
            "boss_side": boss,
            "hand_side": hand,
            "contradiction_class": cclass,
            "battlefield_class": te.get("battlefield_class") or le.get("battlefield_class") or "",
            "price_arc_phase": te.get("price_arc_phase") or le.get("price_arc_phase") or "",
            "arc_direction": te.get("arc_direction") or le.get("arc_direction") or "",
            "timing_shadow": te.get("timing_shadow") or "",
            "borders_state": ma.get("borders_state") or "",
            "churn_type": ma.get("churn_type") or "",
            "seconds_left_entry": "" if seconds_left is None else seconds_left,
            "manager_at_birth": manager_for(router_birth, entry_mode, seconds_left),
            "first_harvest_timestamp": first_harvest.get("timestamp") if first_harvest else "",
            "first_harvest_roi": first_harvest.get("roi") if first_harvest else "",
            "router_harvest_action": harvest_action,
            "actual_exit_timestamp": ex.get("timestamp") or "",
            "actual_exit_reason": exit_reason,
            "actual_pnl": actual_pnl,
            "observed_invalidation_scale": observed_invalidation,
            "settlement_result": settle,
            "settlement_correct": settlement_correct,
            "settlement_correct_but_lost": correct_but_lost,
        }
        rows.append(row)

    out_csv = Path(f"{args.out_prefix}.csv")
    out_json = Path(f"{args.out_prefix}_summary.json")
    if rows:
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    summary = summarize(rows)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote {out_csv}")
    print(f"Wrote {out_json}")


if __name__ == "__main__":
    main()
