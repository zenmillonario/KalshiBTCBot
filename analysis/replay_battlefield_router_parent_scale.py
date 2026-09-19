#!/usr/bin/env python3
"""
Tachyos Battlefield Router — Parent-Scale Evidence Replay
=========================================================
OFFLINE / SHADOW ONLY.

Purpose:
- audit same-contract Campaign reset evidence,
- separate local/micro structural breaks from parent-scale corroboration,
- reuse existing V9.5A telemetry only,
- never import the live/paper trading engine,
- never place, block, resize, flip, or close a trade.

This is not a new detector. It is an evidence router over existing:
Campaign Ledger, Trade Mission, Looking Glass/Arc Voyage, EMA Arc ancestry,
Boss/Hand state, Borders/War Council snapshots, Target distance, and settlement
results for after-the-fact evaluation.

The output deliberately keeps "evidence" separate from "authority".
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from replay_battlefield_router_v2 import (
    choose_latest_run_id,
    derive_ledger_window,
    fnum,
    parse_iso,
    read_csv,
)

DEFAULT_RUN_DIR = Path("runs/tachys_v9_5a_price_freshness_active_treasury")

PAPER_FILE = "tachys_paper_trades_v9_2_6.csv"
RESULTS_FILE = "tachys_contract_results_v9_2_6.csv"
MISSIONS_FILE = "tachys_trade_missions_v9_4i.csv"
LEDGER_FILE = "tachys_campaign_ledger_v9_4m.csv"
ARCS_FILE = "tachys_ema_arcs_v9_4i.csv"
VOYAGE_FILE = "tachys_arc_voyage_v9_4j.csv"

STRUCTURAL_EXIT_REASONS = {
    "ANTICIPATION_FAST_FAIL",
    "EMA9_ARC_BROKEN",
    "V92_STRUCTURE_BROKEN",
    "LATE_TARGET_INVALIDATION",
}

TACTICAL_PROVENANCE = {
    "EARLY_IMPULSE",
    "ARC_RIDER",
    "EXHAUSTION_FLIP",
}

ACTIVE_WAR_DIRECTIVES = {
    "ACT_IMMEDIATELY",
    "ACT_FIRST_VALID",
}

RESET_BORDER_STATES = {
    "BOUNDARY_RELEASE",
}

TRANSITION_BORDER_STATES = {
    "CHURN_RESOLVING",
    "BOUNDARY_RELEASE",
}

MATURE_VOYAGE_STATES = {
    "MATURE_WATCH",
    "LONG_BODY",
}


def trade_key(row: Dict[str, str]) -> Tuple[str, str]:
    return row.get("trade_id", ""), row.get("ticker", "")


def side_from_direction(direction: str) -> str:
    if direction == "UP":
        return "YES"
    if direction == "DOWN":
        return "NO"
    return ""


def opposite(side: str) -> str:
    return "NO" if side == "YES" else "YES" if side == "NO" else ""


def reason_set(row: Dict[str, str]) -> set[str]:
    raw = row.get("chapter_reasons", "") or ""
    return {x for x in raw.split(";") if x}


def latest_before(rows: List[Dict[str, str]], timestamp: str) -> Dict[str, str]:
    """
    Rows are expected to be sorted by ISO-8601 UTC timestamp.
    String ordering is safe for the frozen observer logs used here.
    """
    last: Dict[str, str] = {}
    for row in rows:
        ts = row.get("timestamp", "")
        if ts and ts <= timestamp:
            last = row
        elif ts and ts > timestamp:
            break
    return last


def rows_by_trade(rows: Iterable[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    out: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        tid = row.get("trade_id", "")
        if tid:
            out[tid].append(row)
    for tid in out:
        out[tid].sort(key=lambda r: r.get("timestamp", ""))
    return dict(out)


def first_event(rows: List[Dict[str, str]], event: str) -> Dict[str, str]:
    for row in rows:
        if row.get("event") == event:
            return row
    return {}


def last_event_before(
    rows: List[Dict[str, str]],
    timestamp: str,
) -> Dict[str, str]:
    last: Dict[str, str] = {}
    for row in rows:
        ts = row.get("timestamp", "")
        if ts and ts <= timestamp:
            last = row
        elif ts and ts > timestamp:
            break
    return last


def bool_int(v: bool) -> int:
    return 1 if v else 0


def first_num(*values: object, default: Optional[float] = None) -> Optional[float]:
    for value in values:
        n = fnum(value)
        if n is not None:
            return n
    return default


def campaign_reset_evidence(
    entry: Dict[str, str],
    mission_assign: Dict[str, str],
    arc_by_id: Dict[str, Dict[str, str]],
    voyage_at_entry: Dict[str, str],
) -> Dict[str, object]:
    """
    Evidence-only campaign reset audit.

    A same-contract re-entry does NOT earn Campaign rights merely because
    a new micro arc, phase, cage, dragon, or battlefield label appeared.

    "MULTI_CATEGORY_RESET_REVIEW" is intentionally not permission.
    """
    side = entry.get("side", "")
    reasons = reason_set(entry)

    current_arc = arc_by_id.get(entry.get("arc_id", ""), {})
    prior_arc = arc_by_id.get(entry.get("prior_arc_id", ""), {})

    current_parent_side = side_from_direction(current_arc.get("parent_direction", ""))
    prior_parent_side = side_from_direction(prior_arc.get("parent_direction", ""))

    boss_changed_to_side = (
        "boss_side_changed" in reasons
        and entry.get("boss_side") == side
    )
    hand_changed_to_side = (
        "hand_changed" in reasons
        and entry.get("hand_side") == side
    )
    authority_transfer_to_side = boss_changed_to_side or hand_changed_to_side

    authority_transfer_against = (
        (
            "boss_side_changed" in reasons
            and entry.get("boss_side") == opposite(side)
        )
        or (
            "hand_changed" in reasons
            and entry.get("hand_side") == opposite(side)
        )
    )

    parent_ema_transfer_to_side = bool(
        current_parent_side
        and prior_parent_side
        and current_parent_side == side
        and prior_parent_side != side
    )

    boundary_release_to_side = bool(
        mission_assign.get("borders_state") in RESET_BORDER_STATES
        and mission_assign.get("hand_authority") == side
    )

    sustained_clear_to_side = bool(
        mission_assign.get("borders_state") == "CLEAR_TERRITORY"
        and mission_assign.get("hand_authority") == side
        and mission_assign.get("war_side") == side
        and mission_assign.get("war_directive") in ACTIVE_WAR_DIRECTIVES
    )

    voyage_side = side_from_direction(voyage_at_entry.get("launch_direction", ""))
    looking_glass_launch_to_side = bool(
        voyage_side == side
        and voyage_at_entry.get("phase") == "LAUNCH"
    )

    categories = {
        "AUTHORITY_TRANSFER": authority_transfer_to_side,
        "PARENT_EMA_TRANSFER": parent_ema_transfer_to_side,
        "BORDER_RELEASE": boundary_release_to_side or sustained_clear_to_side,
        "LOOKING_GLASS_LAUNCH": looking_glass_launch_to_side,
    }
    major_count = sum(bool_int(v) for v in categories.values())

    contract_trade_number = int(fnum(entry.get("contract_trade_number")) or 1)

    if contract_trade_number <= 1:
        status = "FIRST_ENTRY"
    elif major_count >= 2:
        status = "MULTI_CATEGORY_RESET_REVIEW"
    elif major_count == 1:
        status = "SINGLE_CATEGORY_ONLY"
    else:
        status = "NO_CAMPAIGN_RESET"

    return {
        "reset_status": status,
        "reset_major_count": major_count,
        "reset_authority_transfer_to_side": bool_int(authority_transfer_to_side),
        "reset_authority_transfer_against": bool_int(authority_transfer_against),
        "reset_parent_ema_transfer_to_side": bool_int(parent_ema_transfer_to_side),
        "reset_boundary_release_to_side": bool_int(
            boundary_release_to_side or sustained_clear_to_side
        ),
        "reset_looking_glass_launch_to_side": bool_int(looking_glass_launch_to_side),
        "reset_current_parent_side": current_parent_side,
        "reset_prior_parent_side": prior_parent_side,
        "reset_voyage_id": voyage_at_entry.get("voyage_id", ""),
        "reset_voyage_phase": voyage_at_entry.get("phase", ""),
        "reset_voyage_launch_side": voyage_side,
        "reset_evidence_categories": ";".join(
            name for name, present in categories.items() if present
        ),
    }


def parent_scale_exit_evidence(
    entry: Dict[str, str],
    exit_row: Dict[str, str],
    paper_entry: Dict[str, str],
    paper_exit: Dict[str, str],
    mission_at_exit: Dict[str, str],
    arc_by_id: Dict[str, Dict[str, str]],
    voyage_at_exit: Dict[str, str],
) -> Dict[str, object]:
    """
    Build a scale-aware evidence vector.

    Important:
    - Settlement result is NOT used here.
    - No exit is changed.
    - The small high-opposition heuristic is research-only and is emitted
      specifically so it can be falsified before any authority is considered.
    """
    side = exit_row.get("side", "") or entry.get("side", "")
    entry_mode = paper_entry.get("trade_intent", "") or "UNKNOWN"
    exit_reason = exit_row.get("exit_reason", "") or paper_exit.get("reason", "")
    structural = exit_reason in STRUCTURAL_EXIT_REASONS

    arc = arc_by_id.get(exit_row.get("arc_id", ""), {})
    current_arc_side = side_from_direction(exit_row.get("arc_direction", ""))
    parent_side = side_from_direction(arc.get("parent_direction", ""))

    boss_side = exit_row.get("boss_side", "")
    hand_side = exit_row.get("hand_side", "")

    authority_against = bool(
        boss_side in {"YES", "NO"}
        and hand_side in {"YES", "NO"}
        and boss_side != side
        and hand_side != side
    )

    authority_support = bool(
        boss_side == side and hand_side == side
    )

    parent_ema_against = bool(parent_side and parent_side != side)
    parent_ema_support = bool(parent_side == side)

    border_state = mission_at_exit.get("borders_state", "")
    border_resolving = border_state in TRANSITION_BORDER_STATES
    border_clear_against = bool(
        border_state == "CLEAR_TERRITORY"
        and mission_at_exit.get("hand_authority") in {"YES", "NO"}
        and mission_at_exit.get("hand_authority") != side
    )

    war_directive = mission_at_exit.get("war_directive", "")
    war_side = mission_at_exit.get("war_side", "")
    war_action_against = bool(
        war_directive in ACTIVE_WAR_DIRECTIVES
        and war_side in {"YES", "NO"}
        and war_side != side
    )
    war_action_support = bool(
        war_directive in ACTIVE_WAR_DIRECTIVES
        and war_side == side
    )

    target_distance = first_num(
        paper_exit.get("target_distance"),
        exit_row.get("target_distance"),
        default=0.0,
    ) or 0.0
    target_favorable_margin = target_distance if side == "YES" else -target_distance
    target_support = target_favorable_margin >= 0.0
    target_against = target_favorable_margin < 0.0

    seconds_left = first_num(
        paper_exit.get("seconds_to_close"),
        entry.get("seconds_left"),
        default=None,
    )

    current_arc_support = bool(current_arc_side == side)

    voyage_side = side_from_direction(voyage_at_exit.get("launch_direction", ""))
    old_voyage_mature_against = bool(
        voyage_side in {"YES", "NO"}
        and voyage_side != side
        and voyage_at_exit.get("maturity") in MATURE_VOYAGE_STATES
    )
    voyage_support = bool(voyage_side == side)

    battlefield_transition = (
        exit_row.get("battlefield_class") == "TRANSITION_RELEASE"
    )

    classification = arc.get("classification", "") or ""
    failed_local_thesis = bool(
        (side == "YES" and "FAILED_RECOVERY" in classification)
        or (side == "NO" and "FAILED_BREAKDOWN" in classification)
    )

    opposition_categories = {
        "AUTHORITY_AGAINST": authority_against,
        "PARENT_EMA_AGAINST": parent_ema_against,
        "CLEAR_TERRITORY_AGAINST": border_clear_against,
        "WAR_ACTION_AGAINST": war_action_against,
    }
    parent_opposition_count = sum(bool_int(v) for v in opposition_categories.values())

    transition_support_categories = {
        "PARENT_EMA_SUPPORT": parent_ema_support,
        "BORDER_RESOLVING": border_resolving,
        "BATTLEFIELD_TRANSITION": battlefield_transition,
        "OLD_VOYAGE_MATURE": old_voyage_mature_against,
        "TARGET_SUPPORT": target_support,
    }
    transition_support_count = sum(
        bool_int(v) for v in transition_support_categories.values()
    )

    # Deliberately conservative falsification heuristic:
    # only calls something a candidate parent break when three independent
    # parent/terrain opposition categories agree and no transition-support
    # category remains. This is NOT an exit command.
    high_opposition_parent_break_candidate = bool(
        structural
        and entry_mode == "ANTICIPATION"
        and parent_opposition_count >= 3
        and transition_support_count == 0
    )

    if not structural:
        scale_review = "EXISTING_MANAGER"
    elif entry_mode in TACTICAL_PROVENANCE:
        scale_review = "TACTICAL_MANAGER_OWNS"
    elif exit_reason == "LATE_TARGET_INVALIDATION":
        scale_review = "SETTLEMENT_SCALE_REVIEW"
    elif entry_mode == "ANTICIPATION":
        scale_review = "ANTICIPATION_PARENT_EVIDENCE_REVIEW"
    else:
        scale_review = "LOCAL_OR_PARENT_SCALE_REVIEW"

    return {
        "exit_is_structural_family": bool_int(structural),
        "exit_scale_review": scale_review,
        "exit_authority_against": bool_int(authority_against),
        "exit_authority_support": bool_int(authority_support),
        "exit_parent_ema_against": bool_int(parent_ema_against),
        "exit_parent_ema_support": bool_int(parent_ema_support),
        "exit_current_arc_side": current_arc_side,
        "exit_current_arc_support": bool_int(current_arc_support),
        "exit_border_state": border_state,
        "exit_border_resolving": bool_int(border_resolving),
        "exit_border_clear_against": bool_int(border_clear_against),
        "exit_war_directive": war_directive,
        "exit_war_side": war_side,
        "exit_war_action_against": bool_int(war_action_against),
        "exit_war_action_support": bool_int(war_action_support),
        "exit_target_favorable_margin": target_favorable_margin,
        "exit_target_support": bool_int(target_support),
        "exit_target_against": bool_int(target_against),
        "exit_seconds_left": seconds_left if seconds_left is not None else "",
        "exit_voyage_id": voyage_at_exit.get("voyage_id", ""),
        "exit_voyage_phase": voyage_at_exit.get("phase", ""),
        "exit_voyage_launch_side": voyage_side,
        "exit_voyage_maturity": voyage_at_exit.get("maturity", ""),
        "exit_old_voyage_mature_against": bool_int(old_voyage_mature_against),
        "exit_voyage_support": bool_int(voyage_support),
        "exit_battlefield_transition": bool_int(battlefield_transition),
        "exit_failed_local_thesis": bool_int(failed_local_thesis),
        "exit_parent_opposition_count": parent_opposition_count,
        "exit_parent_opposition_categories": ";".join(
            name for name, present in opposition_categories.items() if present
        ),
        "exit_transition_support_count": transition_support_count,
        "exit_transition_support_categories": ";".join(
            name for name, present in transition_support_categories.items() if present
        ),
        "exit_high_opposition_parent_break_candidate": bool_int(
            high_opposition_parent_break_candidate
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    ap.add_argument("--campaign-run-id", default=None)
    ap.add_argument("--voyage-run-id", default=None)
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("analysis/router_parent_scale_replay.csv"),
    )
    ap.add_argument(
        "--summary",
        type=Path,
        default=Path("analysis/router_parent_scale_summary.json"),
    )
    args = ap.parse_args()

    run_dir = args.run_dir

    paper = read_csv(run_dir / PAPER_FILE)
    results = read_csv(run_dir / RESULTS_FILE)
    missions_all = read_csv(run_dir / MISSIONS_FILE)
    ledger_all = read_csv(run_dir / LEDGER_FILE)
    arcs = read_csv(run_dir / ARCS_FILE)
    voyage_all = read_csv(run_dir / VOYAGE_FILE, optional=True)

    campaign_run_id = args.campaign_run_id
    if not campaign_run_id:
        campaign_run_id = choose_latest_run_id(
            ledger_all,
            "REAL_ENTRY",
            prefix="M",
        )
    if not campaign_run_id:
        raise RuntimeError("Could not identify Campaign Ledger run_id.")

    ledger = [r for r in ledger_all if r.get("run_id") == campaign_run_id]
    if not ledger:
        raise RuntimeError(f"No Campaign Ledger rows for {campaign_run_id}")

    start, end = derive_ledger_window(ledger_all, campaign_run_id)
    missions = []
    for row in missions_all:
        dt = parse_iso(row.get("timestamp", ""))
        if dt and start and end and start <= dt <= end:
            missions.append(row)

    voyage_run_id = args.voyage_run_id
    if not voyage_run_id and campaign_run_id.startswith("M"):
        voyage_run_id = "J" + campaign_run_id[1:]

    if voyage_run_id:
        voyage = [r for r in voyage_all if r.get("run_id") == voyage_run_id]
    else:
        voyage = voyage_all
    voyage.sort(key=lambda r: r.get("timestamp", ""))

    mission_by_trade = rows_by_trade(missions)

    paper_entry_by_key: Dict[Tuple[str, str], Dict[str, str]] = {}
    paper_exit_by_key: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in paper:
        k = trade_key(row)
        if row.get("event") == "ENTRY":
            paper_entry_by_key[k] = row
        elif row.get("event") == "EXIT":
            paper_exit_by_key[k] = row

    settlement_by_ticker = {
        r.get("ticker", ""): r.get("result", "")
        for r in results
        if r.get("ticker")
    }

    arc_by_id = {
        r.get("arc_id", ""): r
        for r in arcs
        if r.get("arc_id")
    }

    ledger_entries = {
        trade_key(r): r
        for r in ledger
        if r.get("event") == "REAL_ENTRY"
    }
    ledger_exits = {
        trade_key(r): r
        for r in ledger
        if r.get("event") == "REAL_EXIT"
    }

    rows: List[Dict[str, object]] = []

    for k, entry in sorted(
        ledger_entries.items(),
        key=lambda kv: int(fnum(kv[1].get("trade_id")) or 0),
    ):
        tid, ticker = k
        exit_row = ledger_exits.get(k, {})
        paper_entry = paper_entry_by_key.get(k, {})
        paper_exit = paper_exit_by_key.get(k, {})

        mission_rows = mission_by_trade.get(tid, [])
        mission_assign = first_event(mission_rows, "ASSIGN")
        exit_ts = exit_row.get("timestamp", "") or entry.get("timestamp", "")
        mission_at_exit = last_event_before(mission_rows, exit_ts)

        voyage_at_entry = latest_before(voyage, entry.get("timestamp", ""))
        voyage_at_exit = latest_before(voyage, exit_ts)

        reset = campaign_reset_evidence(
            entry,
            mission_assign,
            arc_by_id,
            voyage_at_entry,
        )
        exit_ev = parent_scale_exit_evidence(
            entry,
            exit_row,
            paper_entry,
            paper_exit,
            mission_at_exit,
            arc_by_id,
            voyage_at_exit,
        )

        actual_pnl = fnum(exit_row.get("actual_pnl"))
        if actual_pnl is None:
            actual_pnl = first_num(paper_exit.get("pnl"), default=0.0) or 0.0

        settlement = settlement_by_ticker.get(ticker, "")
        side = entry.get("side", "") or paper_entry.get("side", "")
        settlement_correct = int(bool(settlement and settlement == side))

        rows.append({
            "trade_id": tid,
            "ticker": ticker,
            "entry_timestamp": paper_entry.get("timestamp", "") or entry.get("timestamp", ""),
            "exit_timestamp": paper_exit.get("timestamp", "") or exit_row.get("timestamp", ""),
            "side": side,
            "contract_trade_number": int(
                fnum(entry.get("contract_trade_number")) or 1
            ),
            "entry_mode": paper_entry.get("trade_intent", "") or "UNKNOWN",
            "strategy": paper_entry.get("strategy", "") or entry.get("strategy", ""),
            "legacy_mission": mission_assign.get("mission", ""),
            "chapter_label": entry.get("chapter_label", ""),
            "chapter_reasons": entry.get("chapter_reasons", ""),
            "entry_boss_side": entry.get("boss_side", ""),
            "entry_hand_side": entry.get("hand_side", ""),
            "entry_battlefield_class": entry.get("battlefield_class", ""),
            "exit_reason": exit_row.get("exit_reason", "") or paper_exit.get("reason", ""),
            "exit_boss_side": exit_row.get("boss_side", ""),
            "exit_hand_side": exit_row.get("hand_side", ""),
            "exit_battlefield_class": exit_row.get("battlefield_class", ""),
            "actual_pnl": actual_pnl,
            "settlement_result": settlement,
            "settlement_correct": settlement_correct,
            **reset,
            **exit_ev,
        })

    if not rows:
        raise RuntimeError("No replay rows produced.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    reentries = [r for r in rows if int(r["contract_trade_number"]) > 1]
    legacy_reentry_campaigns = [
        r for r in reentries if r["legacy_mission"] == "CAMPAIGN"
    ]
    structural = [r for r in rows if int(r["exit_is_structural_family"]) == 1]
    anticipation_structural = [
        r for r in structural if r["entry_mode"] == "ANTICIPATION"
    ]
    first_anticipation_structural = [
        r for r in anticipation_structural
        if int(r["contract_trade_number"]) == 1
    ]
    high_opp = [
        r for r in anticipation_structural
        if int(r["exit_high_opposition_parent_break_candidate"]) == 1
    ]

    reset_counts = Counter(r["reset_status"] for r in reentries)

    summary = {
        "run_dir": str(run_dir),
        "campaign_run_id": campaign_run_id,
        "voyage_run_id": voyage_run_id,
        "trades": len(rows),
        "same_contract_reentries": len(reentries),
        "same_contract_reset_status": dict(reset_counts),
        "same_contract_multi_category_reset_reviews": sum(
            r["reset_status"] == "MULTI_CATEGORY_RESET_REVIEW"
            for r in reentries
        ),
        "legacy_same_contract_campaigns": {
            "n": len(legacy_reentry_campaigns),
            "pnl": round(
                sum(float(r["actual_pnl"]) for r in legacy_reentry_campaigns),
                3,
            ),
            "settlement_correct": sum(
                int(r["settlement_correct"]) for r in legacy_reentry_campaigns
            ),
            "with_multi_category_reset_review": sum(
                r["reset_status"] == "MULTI_CATEGORY_RESET_REVIEW"
                for r in legacy_reentry_campaigns
            ),
            "trade_ids": [r["trade_id"] for r in legacy_reentry_campaigns],
        },
        "structural_exit_family": {
            "n": len(structural),
            "pnl": round(sum(float(r["actual_pnl"]) for r in structural), 3),
            "settlement_correct": sum(
                int(r["settlement_correct"]) for r in structural
            ),
            "by_reason": dict(Counter(r["exit_reason"] for r in structural)),
        },
        "anticipation_structural_exit_family": {
            "n": len(anticipation_structural),
            "pnl": round(
                sum(float(r["actual_pnl"]) for r in anticipation_structural),
                3,
            ),
            "settlement_correct": sum(
                int(r["settlement_correct"]) for r in anticipation_structural
            ),
        },
        "first_anticipation_structural_exit_family": {
            "n": len(first_anticipation_structural),
            "pnl": round(
                sum(float(r["actual_pnl"]) for r in first_anticipation_structural),
                3,
            ),
            "settlement_correct": sum(
                int(r["settlement_correct"])
                for r in first_anticipation_structural
            ),
        },
        "high_opposition_parent_break_candidate_shadow": {
            "n": len(high_opp),
            "pnl": round(sum(float(r["actual_pnl"]) for r in high_opp), 3),
            "settlement_correct": sum(
                int(r["settlement_correct"]) for r in high_opp
            ),
            "trade_ids": [r["trade_id"] for r in high_opp],
            "note": (
                "Research-only falsification heuristic. It does not change "
                "paper authority or prove a parent break."
            ),
        },
    }

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote {args.output}")
    print(f"Wrote {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
