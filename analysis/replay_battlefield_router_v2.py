#!/usr/bin/env python3
"""
Tachyos Battlefield Router Replay V2
====================================
OFFLINE / SHADOW ONLY.

V2 incorporates the cross-run J/K/M/V9.5A audit:

- no trade begins with full CAMPAIGN rights,
- ATTACK does not auto-promote to CAMPAIGN,
- EARLY_IMPULSE stays tactical,
- ARC_RIDER keeps its working manager,
- SCOUT becomes TRANSITION_SCOUT,
- counterterrain ANTICIPATION gets a transition overlay,
- RAID -> CAMPAIGN is the primary promotion path,
- same-contract re-entry is allowed, but Campaign reset is explicit.

This script never imports the live bot and never places/changes orders.
Standard-library only.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

UTC = timezone.utc

DEFAULT_RUN_DIR = Path("runs/tachys_v9_5a_price_freshness_active_treasury")

PAPER_FILE = "tachys_paper_trades_v9_2_6.csv"
RESULTS_FILE = "tachys_contract_results_v9_2_6.csv"
MISSIONS_FILE = "tachys_trade_missions_v9_4i.csv"
TIMING_FILE = "tachys_entry_timing_v9_4j.csv"
LEDGER_FILE = "tachys_campaign_ledger_v9_4m.csv"

TACTICAL_PROVENANCE = {"EARLY_IMPULSE", "EXHAUSTION_FLIP"}
PROMOTION_ELIGIBLE_PROVENANCE = {"ANTICIPATION", "ARC_RIDER", "CORE"}

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


def read_csv(path: Path, optional: bool = False) -> List[Dict[str, str]]:
    if not path.exists():
        if optional:
            return []
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    s = str(ts).strip()
    if not s:
        return None
    try:
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


def choose_latest_run_id(rows: List[Dict[str, str]], event: str, prefix: Optional[str] = None) -> Optional[str]:
    latest: Dict[str, datetime] = {}
    for r in rows:
        if event and r.get("event") != event:
            continue
        rid = r.get("run_id", "")
        if not rid:
            continue
        if prefix and not rid.startswith(prefix):
            continue
        dt = parse_iso(r.get("timestamp", ""))
        if not dt:
            continue
        if rid not in latest or dt > latest[rid]:
            latest[rid] = dt
    if not latest:
        return None
    return max(latest.items(), key=lambda kv: kv[1])[0]


def derive_ledger_window(ledger_rows: List[Dict[str, str]], run_id: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    selected = [r for r in ledger_rows if r.get("run_id") == run_id]
    times = [parse_iso(r.get("timestamp", "")) for r in selected]
    times = [t for t in times if t]
    if not times:
        return None, None
    return min(times) - timedelta(seconds=5), max(times) + timedelta(seconds=5)


def in_window(row: Dict[str, str], start: Optional[datetime], end: Optional[datetime]) -> bool:
    if start is None or end is None:
        return True
    dt = parse_iso(row.get("timestamp", ""))
    return bool(dt and start <= dt <= end)


def last_by_trade(rows: Iterable[Dict[str, str]], predicate) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for r in rows:
        tid = r.get("trade_id", "")
        if tid and predicate(r):
            out[tid] = r
    return out


def first_by_trade(rows: Iterable[Dict[str, str]], predicate) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for r in rows:
        tid = r.get("trade_id", "")
        if tid and tid not in out and predicate(r):
            out[tid] = r
    return out


def contradiction_class(side: str, boss: str, hand: str, mission: str) -> str:
    valid = {"YES", "NO"}
    known = int(boss in valid) + int(hand in valid)
    supports = int(boss == side) + int(hand == side)

    if known == 2 and supports == 2:
        return "C0_ALIGNED"
    if supports == 1:
        return "C1_SPLIT_COMMAND"
    if known == 2 and supports == 0:
        if mission in {"RAID", "ATTACK"}:
            return "C2_TACTICAL_COUNTERTREND"
        return "C3_AUTHORITY_TRANSFER_CANDIDATE"
    return "C1_UNRESOLVED"


def router_initial_state(
    legacy_mission: str,
    entry_mode: str,
    contract_trade_number: int,
) -> Tuple[str, str]:
    if legacy_mission == "RAID":
        return "RAID", "ENTER_RAID_SHADOW"

    if legacy_mission == "ATTACK":
        return "ATTACK", "ENTER_ATTACK_SHADOW"

    if legacy_mission == "SCOUT":
        return "TRANSITION_SCOUT", "LOG_TRANSITION_SCOUT_SHADOW"

    if legacy_mission == "CAMPAIGN":
        # Tactical birth modes never receive Campaign persistence at entry.
        if entry_mode in TACTICAL_PROVENANCE:
            return "ATTACK", "RECLASSIFY_CAMPAIGN_TO_ATTACK_SHADOW"

        if contract_trade_number > 1:
            return "CAMPAIGN_CANDIDATE", "WAIT_CAMPAIGN_RESET_SHADOW"

        return "CAMPAIGN_CANDIDATE", "LOG_CAMPAIGN_CANDIDATE_SHADOW"

    return "TRANSITION_SCOUT", "LOG_UNKNOWN_MISSION_SHADOW"


def transition_overlay(entry_mode: str, mission: str, contradiction: str) -> str:
    if mission == "TRANSITION_SCOUT":
        return "TRANSITION_SCOUT"

    if (
        entry_mode == "ANTICIPATION"
        and contradiction in {"C2_TACTICAL_COUNTERTREND", "C3_AUTHORITY_TRANSFER_CANDIDATE"}
    ):
        return "TRANSITION_ANTICIPATION"

    return "NONE"


def manager_owner(entry_mode: str, mission: str, overlay: str) -> str:
    if entry_mode == "EARLY_IMPULSE":
        return "EARLY_IMPULSE_MANAGER_SHADOW"

    if entry_mode == "ARC_RIDER":
        return "ARC_RIDER_MANAGER_SHADOW"

    if overlay == "TRANSITION_ANTICIPATION":
        return "TRANSITION_ANTICIPATION_MANAGER_SHADOW"

    if mission == "CAMPAIGN_CANDIDATE":
        return "PARENT_THESIS_MANAGER_SHADOW"

    if mission in {"RAID", "ATTACK"}:
        return "RAID_MANAGER_SHADOW"

    if mission == "TRANSITION_SCOUT":
        return "OBSERVER_ONLY"

    return "UNASSIGNED"


def promotion_eligibility(entry_mode: str, initial_mission: str) -> str:
    if initial_mission != "RAID":
        return "NO"

    if entry_mode in TACTICAL_PROVENANCE:
        return "NO"

    if entry_mode in PROMOTION_ELIGIBLE_PROVENANCE:
        return "REVIEW"

    return "NO"


def promotion_readiness_at_harvest(side: str, row: Optional[Dict[str, str]]) -> str:
    if not row:
        return "NA"

    hand_align = row.get("hand_authority") == side
    border_good = row.get("borders_state") in PROMOTION_BORDER_STATES
    war_good = (
        row.get("war_directive") in WAR_RELEASE_DIRECTIVES
        and row.get("war_side") == side
    )

    return "HIGH" if hand_align and (border_good or war_good) else "LOW"


def harvest_action(
    entry_mode: str,
    initial_mission: str,
    readiness: str,
    has_harvest: bool,
) -> str:
    if not has_harvest:
        return ""

    if initial_mission != "RAID":
        return "NON_RAID_HARVEST_EVENT"

    if entry_mode == "ARC_RIDER":
        return "KEEP_ARC_RIDER_MANAGER"

    if entry_mode == "EARLY_IMPULSE":
        return "KEEP_EARLY_IMPULSE_MANAGER"

    if entry_mode == "ANTICIPATION":
        return (
            "HOLD_FOR_PROMOTION_REVIEW"
            if readiness == "HIGH"
            else "HARVEST_CANDIDATE_ONLY"
        )

    return "HARVEST_RAID_SHADOW"


def observed_promotion_review(
    original_mission: str,
    entry_mode: str,
    promotion_row: Optional[Dict[str, str]],
) -> str:
    if not promotion_row:
        return ""

    if original_mission == "ATTACK":
        return "BLOCK_ATTACK_TO_CAMPAIGN_SHADOW"

    if entry_mode in TACTICAL_PROVENANCE:
        return "BLOCK_TACTICAL_PROVENANCE_PROMOTION_SHADOW"

    if original_mission == "RAID":
        return "CAMPAIGN_PROMOTION_REVIEW_SHADOW"

    return "PROMOTION_REVIEW_SHADOW"


def exit_review(
    entry_mode: str,
    original_mission: str,
    observed_final_mission: str,
    exit_reason: str,
) -> str:
    if exit_reason in {"EMERGENCY_STOP_60", "EARLY_EMERGENCY_80", "EARLY_SIDEWAYS_EMERGENCY_85"}:
        return "CATASTROPHE_CONTROL"

    if exit_reason.startswith(TACTICAL_EXIT_PREFIXES):
        return "TACTICAL_OR_TREASURY_EXIT"

    if exit_reason in STRUCTURAL_EXIT_REASONS:
        if observed_final_mission == "CAMPAIGN":
            return "PARENT_SCALE_REVIEW_REQUIRED"
        if entry_mode == "ANTICIPATION" and original_mission not in {"RAID", "ATTACK"}:
            return "PARENT_SCALE_REVIEW_REQUIRED"
        return "LOCAL_INVALIDATION_ALLOWED_BUT_LOG_SCALE"

    return "LEGACY_MANAGER_REVIEW"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    ap.add_argument("--campaign-run-id", default=None)
    ap.add_argument("--timing-run-id", default=None)
    ap.add_argument("--output", type=Path, default=Path("analysis/router_replay_v2.csv"))
    ap.add_argument("--summary", type=Path, default=Path("analysis/router_replay_v2_summary.json"))
    args = ap.parse_args()

    run_dir = args.run_dir

    paper = read_csv(run_dir / PAPER_FILE)
    results = read_csv(run_dir / RESULTS_FILE)
    missions_all = read_csv(run_dir / MISSIONS_FILE)
    timing_all = read_csv(run_dir / TIMING_FILE)
    ledger_all = read_csv(run_dir / LEDGER_FILE, optional=True)

    campaign_run_id = args.campaign_run_id
    ledger_entries: List[Dict[str, str]] = []
    ledger_exit: Dict[str, Dict[str, str]] = {}
    mission_start = mission_end = None

    if ledger_all:
        if not campaign_run_id:
            campaign_run_id = choose_latest_run_id(ledger_all, "REAL_ENTRY", prefix="M")
        if campaign_run_id:
            selected_ledger = [r for r in ledger_all if r.get("run_id") == campaign_run_id]
            ledger_entries = [r for r in selected_ledger if r.get("event") == "REAL_ENTRY"]
            ledger_exit = {
                r.get("trade_id", ""): r
                for r in selected_ledger
                if r.get("event") == "REAL_EXIT"
            }
            mission_start, mission_end = derive_ledger_window(ledger_all, campaign_run_id)

    missions = [
        r for r in missions_all
        if in_window(r, mission_start, mission_end)
    ]

    timing_run_id = args.timing_run_id
    if not timing_run_id and campaign_run_id and campaign_run_id.startswith("M"):
        timing_run_id = "J" + campaign_run_id[1:]

    if timing_run_id:
        timing = [r for r in timing_all if r.get("run_id") == timing_run_id]
    else:
        latest_timing_run = choose_latest_run_id(timing_all, "ENTERED", prefix="J")
        timing = (
            [r for r in timing_all if r.get("run_id") == latest_timing_run]
            if latest_timing_run
            else timing_all
        )

    timing_entry = last_by_trade(timing, lambda r: r.get("event") == "ENTERED")
    mission_assign = first_by_trade(missions, lambda r: r.get("event") == "ASSIGN")
    mission_final = last_by_trade(missions, lambda r: r.get("event") == "FINAL")
    first_harvest = first_by_trade(missions, lambda r: r.get("shadow_action") == "HARVEST_EDGE_SHADOW")
    first_promotion = first_by_trade(missions, lambda r: "TO_CAMPAIGN" in (r.get("shadow_action") or ""))

    # Paper files in frozen folders may be cumulative. If a campaign ledger is
    # available, use its trade/ticker keys to select the latest matching paper rows.
    paper_entry_by_key: Dict[Tuple[str, str], Dict[str, str]] = {}
    paper_exit_by_key: Dict[Tuple[str, str], Dict[str, str]] = {}
    for r in paper:
        key = (r.get("trade_id", ""), r.get("ticker", ""))
        if r.get("event") == "ENTRY":
            paper_entry_by_key[key] = r
        elif r.get("event") == "EXIT":
            paper_exit_by_key[key] = r

    if ledger_entries:
        base_entries = ledger_entries
    else:
        # J/K archives predate Campaign Ledger. Infer contract trade number.
        counts: Dict[str, int] = {}
        base_entries = []
        for r in paper:
            if r.get("event") != "ENTRY":
                continue
            ticker = r.get("ticker", "")
            counts[ticker] = counts.get(ticker, 0) + 1
            x = dict(r)
            x["contract_trade_number"] = str(counts[ticker])
            x["chapter_label"] = "UNKNOWN"
            x["chapter_score"] = ""
            x["chapter_reasons"] = ""
            ti = timing_entry.get(r.get("trade_id", ""), {})
            x["boss_side"] = ti.get("boss_side", "")
            x["hand_side"] = ti.get("hand_side", "")
            x["battlefield_class"] = ti.get("battlefield_class", "")
            x["price_arc_phase"] = ti.get("price_arc_phase", "")
            x["dragon_state"] = ""
            x["target_migration_state"] = ""
            base_entries.append(x)

    settlement = {
        r.get("ticker", ""): r.get("result", "")
        for r in results
        if r.get("ticker")
    }

    rows: List[Dict[str, object]] = []

    for base in base_entries:
        tid = base.get("trade_id", "")
        ticker = base.get("ticker", "")
        key = (tid, ticker)

        pe = paper_entry_by_key.get(key, base)
        px = paper_exit_by_key.get(key, {})
        ma = mission_assign.get(tid, {})
        mf = mission_final.get(tid, {})
        ti = timing_entry.get(tid, {})
        harvest = first_harvest.get(tid)
        promotion = first_promotion.get(tid)

        side = base.get("side") or pe.get("side") or ma.get("side") or ""
        entry_mode = pe.get("trade_intent", "") or "UNKNOWN"
        ctn = int(float(base.get("contract_trade_number") or 1))
        original_mission = ma.get("mission", "UNKNOWN")

        initial_mission, entry_action = router_initial_state(
            original_mission,
            entry_mode,
            ctn,
        )

        boss = base.get("boss_side", "") or ti.get("boss_side", "")
        hand = base.get("hand_side", "") or ti.get("hand_side", "") or ma.get("hand_authority", "")

        contradiction = contradiction_class(side, boss, hand, initial_mission)
        overlay = transition_overlay(entry_mode, initial_mission, contradiction)
        owner = manager_owner(entry_mode, initial_mission, overlay)
        promo_eligible = promotion_eligibility(entry_mode, initial_mission)

        readiness = promotion_readiness_at_harvest(side, harvest)
        h_action = harvest_action(entry_mode, initial_mission, readiness, bool(harvest))
        p_review = observed_promotion_review(original_mission, entry_mode, promotion)

        exit_reason = px.get("reason", "") or mf.get("actual_exit_reason", "")
        final_mission = mf.get("mission", "") or original_mission
        actual_pnl = fnum(px.get("pnl"))
        if actual_pnl is None:
            actual_pnl = fnum(mf.get("actual_pnl")) or 0.0

        settle_result = settlement.get(ticker, "")
        settle_correct = int(bool(settle_result and settle_result == side))

        rows.append({
            "trade_id": tid,
            "timestamp": pe.get("timestamp", "") or base.get("timestamp", ""),
            "ticker": ticker,
            "side": side,
            "contract_trade_number": ctn,
            "entry_mode": entry_mode,
            "setup_grade": pe.get("setup_grade", "") or base.get("setup_grade", ""),
            "legacy_mission": original_mission,
            "router_initial_mission": initial_mission,
            "router_entry_action": entry_action,
            "transition_overlay": overlay,
            "router_manager_owner": owner,
            "promotion_eligibility": promo_eligible,
            "chapter_label": base.get("chapter_label", ""),
            "chapter_score": base.get("chapter_score", ""),
            "chapter_reasons": base.get("chapter_reasons", ""),
            "boss_side": boss,
            "hand_side": hand,
            "borders_state": ma.get("borders_state", ""),
            "churn_type": ma.get("churn_type", ""),
            "war_directive": ma.get("war_directive", ""),
            "war_side": ma.get("war_side", ""),
            "battlefield_class": base.get("battlefield_class", "") or ti.get("battlefield_class", ""),
            "price_arc_phase": base.get("price_arc_phase", "") or ti.get("price_arc_phase", ""),
            "contradiction_class": contradiction,
            "first_harvest_roi": (harvest or {}).get("roi", ""),
            "promotion_readiness_at_harvest": readiness,
            "router_harvest_action": h_action,
            "observed_promotion": int(bool(promotion)),
            "observed_promotion_action": (promotion or {}).get("shadow_action", ""),
            "router_promotion_review": p_review,
            "observed_final_mission": final_mission,
            "actual_exit_reason": exit_reason,
            "router_exit_review": exit_review(entry_mode, original_mission, final_mission, exit_reason),
            "actual_pnl": actual_pnl,
            "settlement_result": settle_result,
            "settlement_correct": settle_correct,
        })

    if not rows:
        raise RuntimeError("No replay rows were produced.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    summary = {
        "run_dir": str(run_dir),
        "campaign_run_id": campaign_run_id,
        "timing_run_id": timing_run_id,
        "trades": len(rows),
        "legacy_missions": dict(Counter(r["legacy_mission"] for r in rows)),
        "router_initial_missions": dict(Counter(r["router_initial_mission"] for r in rows)),
        "entry_actions": dict(Counter(r["router_entry_action"] for r in rows)),
        "entry_modes": dict(Counter(r["entry_mode"] for r in rows)),
        "contradictions": dict(Counter(r["contradiction_class"] for r in rows)),
        "transition_overlays": dict(Counter(r["transition_overlay"] for r in rows)),
        "manager_owners": dict(Counter(r["router_manager_owner"] for r in rows)),
        "promotion_eligible": sum(r["promotion_eligibility"] == "REVIEW" for r in rows),
        "observed_promotions": sum(int(r["observed_promotion"]) for r in rows),
        "blocked_attack_promotions": sum(
            r["router_promotion_review"] == "BLOCK_ATTACK_TO_CAMPAIGN_SHADOW"
            for r in rows
        ),
        "settlement_correct": sum(int(r["settlement_correct"]) for r in rows),
        "settlement_known": sum(bool(r["settlement_result"]) for r in rows),
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
