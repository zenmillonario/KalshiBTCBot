#!/usr/bin/env python3
"""
Tachyos Battlefield Router Replay V1
-----------------------------------
OFFLINE / SHADOW ONLY.

Reads one frozen run's existing CSV telemetry and reconstructs a per-trade
router view. It never imports the live bot and never places or changes orders.

Default input:
    runs/tachys_v9_5a_price_freshness_active_treasury

Key questions:
- Was the trade a RAID, ATTACK, CAMPAIGN_CANDIDATE, or WAIT?
- Was it a same-contract re-entry trying to become a new campaign?
- Did Boss / Hand support or contradict the side?
- Did a RAID reach harvest while campaign promotion was becoming plausible?
- Was a structural exit applied to an anticipation thesis?

No third-party packages are required.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

UTC = timezone.utc

DEFAULT_RUN_DIR = Path("runs/tachys_v9_5a_price_freshness_active_treasury")

FILES = {
    "paper": "tachys_paper_trades_v9_2_6.csv",
    "results": "tachys_contract_results_v9_2_6.csv",
    "ledger": "tachys_campaign_ledger_v9_4m.csv",
    "missions": "tachys_trade_missions_v9_4i.csv",
}

STRUCTURAL_EXIT_REASONS = {
    "ANTICIPATION_FAST_FAIL",
    "EMA9_ARC_BROKEN",
    "V92_STRUCTURE_BROKEN",
    "LATE_TARGET_INVALIDATION",
}

TACTICAL_EXIT_PREFIXES = (
    "CORE_SWIRL_",
    "EARLY_TAKE_PROFIT",
    "V95A_ACTIVE_TREASURY",
    "KING_GUARD_DEFEND",
    "V92_PROTECT_BIRD",
)

WAR_RELEASE_DIRECTIVES = {"ACT_IMMEDIATELY", "ACT_FIRST_VALID"}
PROMOTION_BORDER_STATES = {"CHURN_RESOLVING", "BOUNDARY_RELEASE", "CLEAR_TERRITORY"}


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    s = ts.strip()
    if not s:
        return None
    try:
        # Python accepts +00:00 and, on current versions, Z. Normalize Z anyway.
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None


def fnum(v: object) -> Optional[float]:
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def in_window(row: Dict[str, str], start: datetime, end: datetime) -> bool:
    dt = parse_iso(row.get("timestamp", ""))
    return bool(dt and start <= dt <= end)


def choose_latest_campaign_run(ledger: List[Dict[str, str]], requested: Optional[str]) -> str:
    if requested:
        return requested
    latest_by_run: Dict[str, datetime] = {}
    for r in ledger:
        if r.get("event") != "REAL_ENTRY":
            continue
        rid = r.get("run_id", "")
        dt = parse_iso(r.get("timestamp", ""))
        if not rid or not dt:
            continue
        if rid not in latest_by_run or dt > latest_by_run[rid]:
            latest_by_run[rid] = dt
    if not latest_by_run:
        raise RuntimeError("No campaign-ledger REAL_ENTRY rows with run_id were found.")
    return max(latest_by_run.items(), key=lambda kv: kv[1])[0]


def latest_row_by_key(rows: Iterable[Dict[str, str]], event: str) -> Dict[Tuple[str, str], Dict[str, str]]:
    out: Dict[Tuple[str, str], Dict[str, str]] = {}
    for r in rows:
        if r.get("event") != event:
            continue
        key = (r.get("trade_id", ""), r.get("ticker", ""))
        if not key[0] or not key[1]:
            continue
        # Appended run files contain older duplicates. Current frozen run is latest.
        out[key] = r
    return out


def contradiction_class(side: str, boss: str, hand: str, proposed_mission: str) -> str:
    valid = {"YES", "NO"}
    boss_known = boss in valid
    hand_known = hand in valid
    supports = int(boss == side) + int(hand == side)
    known = int(boss_known) + int(hand_known)

    if known == 2 and supports == 2:
        return "C0_ALIGNED"
    if supports == 1:
        return "C1_SPLIT_COMMAND"
    if known == 2 and supports == 0:
        if proposed_mission in {"RAID", "ATTACK"}:
            return "C2_TACTICAL_COUNTERTREND"
        return "C3_AUTHORITY_TRANSFER_CANDIDATE"
    return "C1_UNRESOLVED"


def router_entry_mission(
    legacy_mission: str,
    trade_intent: str,
    contract_trade_number: int,
) -> Tuple[str, str]:
    """
    Conservative replay policy derived from the audit.

    - RAID remains RAID.
    - ATTACK remains ATTACK.
    - SCOUT does not become normal execution authority.
    - Legacy CAMPAIGN is no longer automatically granted campaign persistence.
      Tactical birth modes stay tactical; other modes become candidates first.
    - A same-contract legacy CAMPAIGN is specifically marked as needing a
      campaign reset rather than being silently declared a new campaign.
    """
    if legacy_mission == "RAID":
        return "RAID", "ENTER_RAID_SHADOW"
    if legacy_mission == "ATTACK":
        return "ATTACK", "ENTER_ATTACK_SHADOW"
    if legacy_mission == "SCOUT":
        # Preserve unresolved scouts as research signal. V9.5A scouts were often
        # directionally early even when realized management was poor.
        return "TRANSITION_SCOUT", "LOG_TRANSITION_SCOUT_SHADOW"

    if legacy_mission == "CAMPAIGN":
        if trade_intent in {"EARLY_IMPULSE", "EXHAUSTION_FLIP"}:
            return "ATTACK", "ENTER_ATTACK_SHADOW"
        if contract_trade_number > 1:
            return "CAMPAIGN_CANDIDATE", "WAIT_CAMPAIGN_RESET_SHADOW"
        return "CAMPAIGN_CANDIDATE", "ENTER_CAMPAIGN_CANDIDATE_SHADOW"

    return "WAIT", "WAIT_UNKNOWN_MISSION"


def promotion_readiness_at_harvest(
    side: str,
    harvest_row: Optional[Dict[str, str]],
) -> str:
    """
    One-run shadow hypothesis, deliberately explicit and easy to falsify.

    HIGH when:
    - Hand authority agrees with the trade side, AND
    - churn is resolving / released / clear, OR rollover war directive is
      explicitly releasing on the same side.

    In V9.5A this captured all three harvest-stage trades that later promoted
    into CAMPAIGN, with one false positive and no false negatives.
    """
    if not harvest_row:
        return "NA"

    hand_align = harvest_row.get("hand_authority") == side
    border_good = harvest_row.get("borders_state") in PROMOTION_BORDER_STATES
    war_good = (
        harvest_row.get("war_directive") in WAR_RELEASE_DIRECTIVES
        and harvest_row.get("war_side") == side
    )
    return "HIGH" if hand_align and (border_good or war_good) else "LOW"


def exit_review(
    trade_intent: str,
    active_mission_at_exit: str,
    exit_reason: str,
) -> str:
    if exit_reason in {"EMERGENCY_STOP_60", "EARLY_EMERGENCY_80", "EARLY_SIDEWAYS_EMERGENCY_85"}:
        return "CATASTROPHE_CONTROL"

    if exit_reason.startswith(TACTICAL_EXIT_PREFIXES):
        return "TACTICAL_OR_TREASURY_EXIT"

    if exit_reason in STRUCTURAL_EXIT_REASONS:
        if active_mission_at_exit == "CAMPAIGN":
            return "PARENT_SCALE_REVIEW_REQUIRED"
        if trade_intent == "ANTICIPATION" and active_mission_at_exit not in {"RAID", "ATTACK"}:
            return "PARENT_SCALE_REVIEW_REQUIRED"
        return "LOCAL_INVALIDATION_ALLOWED_FOR_TACTICAL_MISSION"

    return "LEGACY_MANAGER_REVIEW"


def first_by_trade(rows: Iterable[Dict[str, str]], predicate) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for r in rows:
        tid = r.get("trade_id", "")
        if not tid or tid in out or not predicate(r):
            continue
        out[tid] = r
    return out


def last_final_by_trade(rows: Iterable[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for r in rows:
        if r.get("event") == "FINAL" and r.get("trade_id"):
            out[r["trade_id"]] = r
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    ap.add_argument("--campaign-run-id", default=None)
    ap.add_argument("--output", type=Path, default=Path("analysis/router_replay_v1.csv"))
    ap.add_argument("--summary", type=Path, default=Path("analysis/router_replay_v1_summary.json"))
    args = ap.parse_args()

    run_dir = args.run_dir
    paper = read_csv(run_dir / FILES["paper"])
    results = read_csv(run_dir / FILES["results"])
    ledger = read_csv(run_dir / FILES["ledger"])
    missions_all = read_csv(run_dir / FILES["missions"])

    campaign_run = choose_latest_campaign_run(ledger, args.campaign_run_id)
    run_ledger = [r for r in ledger if r.get("run_id") == campaign_run]
    ledger_entries = [r for r in run_ledger if r.get("event") == "REAL_ENTRY"]
    ledger_exits = {r.get("trade_id", ""): r for r in run_ledger if r.get("event") == "REAL_EXIT"}

    if not ledger_entries:
        raise RuntimeError(f"No REAL_ENTRY rows found for campaign run {campaign_run}")

    run_times = [parse_iso(r.get("timestamp", "")) for r in run_ledger]
    run_times = [x for x in run_times if x]
    start = min(run_times) - timedelta(seconds=5)
    end = max(run_times) + timedelta(seconds=5)
    missions = [r for r in missions_all if in_window(r, start, end)]

    paper_entries = latest_row_by_key(paper, "ENTRY")
    paper_exits = latest_row_by_key(paper, "EXIT")
    settlement = {r.get("ticker", ""): r.get("result", "") for r in results if r.get("ticker")}

    mission_assign = first_by_trade(missions, lambda r: r.get("event") == "ASSIGN")
    first_harvest = first_by_trade(missions, lambda r: r.get("shadow_action") == "HARVEST_EDGE_SHADOW")
    first_promotion = first_by_trade(
        missions,
        lambda r: "TO_CAMPAIGN" in (r.get("shadow_action") or ""),
    )
    mission_final = last_final_by_trade(missions)

    rows: List[Dict[str, object]] = []

    for le in ledger_entries:
        tid = le.get("trade_id", "")
        ticker = le.get("ticker", "")
        key = (tid, ticker)
        pe = paper_entries.get(key, {})
        px = paper_exits.get(key, {})
        lx = ledger_exits.get(tid, {})
        ma = mission_assign.get(tid, {})
        mh = first_harvest.get(tid)
        mp = first_promotion.get(tid)
        mf = mission_final.get(tid, {})

        side = le.get("side") or pe.get("side") or ma.get("side") or ""
        trade_intent = pe.get("trade_intent", "") or le.get("strategy", "")
        legacy_mission = ma.get("mission", "UNKNOWN")
        ctn = int(float(le.get("contract_trade_number") or 1))

        proposed_mission, entry_action = router_entry_mission(
            legacy_mission,
            trade_intent,
            ctn,
        )

        boss = le.get("boss_side", "")
        hand = le.get("hand_side", "") or ma.get("hand_authority", "")
        contradiction = contradiction_class(side, boss, hand, proposed_mission)

        transition_candidate = int(
            proposed_mission == "TRANSITION_SCOUT"
            or (
                trade_intent == "ANTICIPATION"
                and contradiction in {
                    "C2_TACTICAL_COUNTERTREND",
                    "C3_AUTHORITY_TRANSFER_CANDIDATE",
                }
            )
        )
        if transition_candidate:
            manager_owner = "TRANSITION_ANTICIPATION_SHADOW"
        elif proposed_mission in {"RAID", "ATTACK"}:
            manager_owner = "RAID_MANAGER_SHADOW"
        elif proposed_mission == "CAMPAIGN_CANDIDATE":
            manager_owner = "CAMPAIGN_CANDIDATE_MANAGER_SHADOW"
        else:
            manager_owner = "NONE"

        promo_readiness = promotion_readiness_at_harvest(side, mh)
        observed_promotion = bool(mp)

        active_exit_mission = mf.get("mission") or legacy_mission
        ex_reason = px.get("reason") or lx.get("exit_reason") or mf.get("actual_exit_reason") or ""
        ex_pnl = fnum(px.get("pnl"))
        if ex_pnl is None:
            ex_pnl = fnum(lx.get("actual_pnl")) or 0.0

        result = settlement.get(ticker, "")
        settle_correct = bool(result and side == result)

        # Router management note at first harvest.
        harvest_action = ""
        if mh:
            if promo_readiness == "HIGH":
                harvest_action = "HOLD_FOR_PROMOTION_SHADOW"
            else:
                harvest_action = "HARVEST_RAID_SHADOW"

        row = {
            "trade_id": tid,
            "timestamp": pe.get("timestamp", "") or le.get("timestamp", ""),
            "ticker": ticker,
            "side": side,
            "contract_trade_number": ctn,
            "entry_intent": trade_intent,
            "setup_grade": pe.get("setup_grade", "") or le.get("setup_grade", ""),
            "legacy_mission": legacy_mission,
            "router_entry_mission": proposed_mission,
            "router_entry_action": entry_action,
            "chapter_label": le.get("chapter_label", ""),
            "chapter_score": le.get("chapter_score", ""),
            "chapter_reasons": le.get("chapter_reasons", ""),
            "boss_side": boss,
            "hand_side": hand,
            "borders_state": ma.get("borders_state", ""),
            "churn_type": ma.get("churn_type", ""),
            "war_directive": ma.get("war_directive", ""),
            "war_side": ma.get("war_side", ""),
            "battlefield_class": le.get("battlefield_class", ""),
            "price_arc_phase": le.get("price_arc_phase", ""),
            "dragon_state": le.get("dragon_state", ""),
            "target_migration_state": le.get("target_migration_state", ""),
            "target_distance": le.get("target_distance", ""),
            "contradiction_class": contradiction,
            "transition_candidate": transition_candidate,
            "router_manager_owner": manager_owner,
            "first_harvest_roi": (mh or {}).get("roi", ""),
            "promotion_readiness_at_harvest": promo_readiness,
            "router_harvest_action": harvest_action,
            "observed_campaign_promotion": int(observed_promotion),
            "observed_promotion_timestamp": (mp or {}).get("timestamp", ""),
            "observed_promotion_roi": (mp or {}).get("roi", ""),
            "active_mission_at_exit": active_exit_mission,
            "actual_exit_reason": ex_reason,
            "router_exit_review": exit_review(trade_intent, active_exit_mission, ex_reason),
            "actual_pnl": ex_pnl,
            "settlement_result": result,
            "settlement_correct": int(settle_correct),
        }
        rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with args.output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # Summary deliberately reports observed arithmetic only. It does not pretend
    # the Router counterfactual is a live backtest.
    summary = {
        "campaign_run_id": campaign_run,
        "trades": len(rows),
        "router_entry_actions": dict(Counter(r["router_entry_action"] for r in rows)),
        "legacy_missions": dict(Counter(r["legacy_mission"] for r in rows)),
        "router_missions": dict(Counter(r["router_entry_mission"] for r in rows)),
        "contradictions": dict(Counter(r["contradiction_class"] for r in rows)),
        "legacy_campaign_entries": sum(r["legacy_mission"] == "CAMPAIGN" for r in rows),
        "same_contract_legacy_campaign_entries": sum(
            r["legacy_mission"] == "CAMPAIGN" and int(r["contract_trade_number"]) > 1
            for r in rows
        ),
        "observed_promotions": sum(int(r["observed_campaign_promotion"]) for r in rows),
        "transition_candidates": sum(int(r["transition_candidate"]) for r in rows),
        "parent_scale_reviews": sum(
            r["router_exit_review"] == "PARENT_SCALE_REVIEW_REQUIRED" for r in rows
        ),
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
