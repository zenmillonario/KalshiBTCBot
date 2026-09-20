from __future__ import annotations

import argparse
import csv
import hashlib
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

DEFAULT_RUNS = [
    "runs/tachys_v9_5a_price_freshness_active_treasury",
    "runs/2026-09-19_v9_5a_late_mature_shadow_5h",
    "runs/2026-09-20_v9_5a_swirl_orbit_long_01",
]

FILES = {
    "paper": "tachys_paper_trades_v9_2_6.csv",
    "results": "tachys_contract_results_v9_2_6.csv",
    "timing": "tachys_entry_timing_v9_4j.csv",
    "missions": "tachys_trade_missions_v9_4i.csv",
    "campaign": "tachys_campaign_ledger_v9_4m.csv",
    "freshness": "tachys_price_freshness_v9_5a.csv",
}

OUT_FIELDS = [
    "run_label", "run_dir", "paper_entry_ts", "ticker", "trade_id", "side", "entry_ask",
    "trade_intent", "strategy", "setup_grade", "signal_grade",
    "exit_ts", "exit_bid", "exit_reason", "pnl", "mfe_pct", "mae_pct",
    "settlement_result", "settlement_correct",
    "price_arc_phase", "arc_direction", "remaining_capacity", "timing_shadow",
    "battlefield_class", "zoom_mode", "boss_side", "hand_side",
    "war_directive", "war_side", "authority_agreement_count",
    "authority_opposition_count", "churn_type", "territory_state",
    "v95a_gate_action", "v95a_gate_reason", "v95a_aligned_with_leg",
    "detector_leg_age_sec", "chapter_label", "chapter_score",
    "dragon_state", "cage_state", "target_distance", "seconds_left",
    "late_mature_anticipation_shadow", "swirling_anticipation_shadow",
    "router_state_v1_replay", "router_action_v1_replay", "router_reason_v1_replay",
    "join_timing_dt_ms", "join_mission_dt_ms", "join_campaign_dt_ms",
    "join_freshness_dt_ms",
]

SUMMARY_FIELDS = [
    "run_label", "group_type", "group_value", "n", "pnl", "wins", "losses",
    "settlement_known", "settlement_correct", "settlement_accuracy",
    "avg_mfe_pct", "avg_mae_pct",
]


def fnum(v) -> Optional[float]:
    try:
        if v in (None, ""):
            return None
        x = float(v)
        if math.isnan(x):
            return None
        return x
    except Exception:
        return None


def read_csv(path: Path) -> List[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def parse_ts(value: str, paper_local: bool = False) -> Optional[float]:
    if not value:
        return None
    s = value.strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ET if paper_local else ZoneInfo("UTC"))
        return dt.timestamp()
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            dt = datetime.strptime(s, fmt)
            dt = dt.replace(tzinfo=ET if paper_local else ZoneInfo("UTC"))
            return dt.timestamp()
        except Exception:
            continue
    return None


def paper_fingerprint(run_dir: Path) -> Optional[str]:
    p = run_dir / FILES["paper"]
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ask_close(a, b, tol=0.015) -> bool:
    aa = fnum(a)
    bb = fnum(b)
    if aa is None or bb is None:
        return True
    return abs(aa - bb) <= tol


def nearest_row(
    entry: dict,
    rows: Iterable[dict],
    *,
    event: Optional[str] = None,
    max_dt: float = 3.0,
    ask_field: Optional[str] = None,
) -> Tuple[Optional[dict], Optional[float]]:
    ets = parse_ts(entry.get("timestamp", ""), paper_local=True)
    if ets is None:
        return None, None
    best = None
    best_dt = None
    for row in rows:
        if event is not None and str(row.get("event") or "") != event:
            continue
        if row.get("ticker") != entry.get("ticker"):
            continue
        if row.get("side") and str(row.get("side")) != str(entry.get("side")):
            continue
        if ask_field is not None and not ask_close(entry.get("entry_ask"), row.get(ask_field)):
            continue
        rts = parse_ts(row.get("timestamp", ""), paper_local=False)
        if rts is None:
            continue
        dt = abs(rts - ets)
        if dt <= max_dt and (best_dt is None or dt < best_dt):
            best = row
            best_dt = dt
    return best, best_dt


def nearest_exit(entry: dict, exits: Iterable[dict]) -> Optional[dict]:
    ets = parse_ts(entry.get("timestamp", ""), paper_local=True)
    if ets is None:
        return None
    best = None
    best_dt = None
    for row in exits:
        if row.get("ticker") != entry.get("ticker"):
            continue
        if str(row.get("side") or "") != str(entry.get("side") or ""):
            continue
        if row.get("trade_id") and entry.get("trade_id") and row.get("trade_id") != entry.get("trade_id"):
            continue
        rts = parse_ts(row.get("timestamp", ""), paper_local=True)
        if rts is None or rts < ets:
            continue
        dt = rts - ets
        if dt > 20 * 60:
            continue
        if best_dt is None or dt < best_dt:
            best = row
            best_dt = dt
    return best


def settlement_for(entry: dict, results: Iterable[dict]) -> str:
    matches = [r for r in results if r.get("ticker") == entry.get("ticker")]
    return str(matches[-1].get("result") or "") if matches else ""


def authority_counts(side: str, boss: str, hand: str, war: str) -> Tuple[int, int]:
    vals = [x for x in (boss, hand, war) if x in ("YES", "NO")]
    agree = sum(1 for x in vals if x == side)
    oppose = sum(1 for x in vals if x != side)
    return agree, oppose


def classify_router_state(row: dict) -> Tuple[str, str, str]:
    """Replay-only structural classifier. It does not use realized P&L."""
    phase = row.get("price_arc_phase") or ""
    timing = row.get("timing_shadow") or ""
    directive = row.get("war_directive") or ""
    agree = int(row.get("authority_agreement_count") or 0)
    rem = fnum(row.get("remaining_capacity"))
    battlefield = row.get("battlefield_class") or ""

    if phase == "CROSS_RESET" or timing == "WAIT_NEW_ARC_SHADOW":
        if agree <= 1 or directive == "CHOP_QUARANTINE":
            return (
                "HINGE_WAIT",
                "WAIT",
                "old arc/reset unresolved; proposed side lacks enough contextual release support",
            )
        return (
            "RELEASE_ARMED",
            "WAIT",
            "reset detected with contextual support; wait for actual new-arc/release evidence",
        )

    if timing == "WAIT_EMA9_REACTION_SHADOW" or phase == "RETURN_TO_EMA9":
        return (
            "PULLBACK_WAIT",
            "WAIT",
            "direction may be valid but price is returning toward EMA9/value",
        )

    if timing == "LOW_REMAINING_CAPACITY_SHADOW" or (
        rem is not None and rem <= 0.22 and phase in ("PEAK_TROUGH_BUILD", "EXTENSION_SLOW")
    ):
        return (
            "MID_PLAY_CLOSED",
            "BLOCK",
            "estimated remaining arc capacity is low; do not board a mature play",
        )

    if timing in ("EARLY_COUNTERARC_SHADOW", "ELITE_RAID_ONLY_SHADOW"):
        return (
            "TACTICAL_COUNTERWAVE_ONLY",
            "TACTICAL_ONLY",
            "candidate is not proven as a clean parent campaign entry",
        )

    if "STORM" in battlefield and agree <= 1:
        return (
            "NO_TRADE",
            "WAIT",
            "storm terrain plus weak contextual agreement; require release evidence",
        )

    return (
        "ENTRY_WINDOW_CANDIDATE",
        "ALLOW_CANDIDATE",
        "no replay-only hold state identified; still requires final live-router evidence",
    )


def build_features(run_dir: Path, run_label: str) -> List[dict]:
    data = {k: read_csv(run_dir / v) for k, v in FILES.items()}
    entries = [r for r in data["paper"] if r.get("event") == "ENTRY"]
    exits = [r for r in data["paper"] if r.get("event") == "EXIT"]

    out = []
    for e in entries:
        timing, dt_timing = nearest_row(e, data["timing"], event="ENTERED", max_dt=3.0, ask_field="ask")
        mission, dt_mission = nearest_row(e, data["missions"], event="ASSIGN", max_dt=3.0, ask_field="entry_ask")
        campaign, dt_campaign = nearest_row(e, data["campaign"], event="REAL_ENTRY", max_dt=3.0, ask_field="entry_ask")
        fresh, dt_fresh = nearest_row(e, data["freshness"], event="ENTRY_GATE", max_dt=3.0, ask_field="ask")
        x = nearest_exit(e, exits)
        settle = settlement_for(e, data["results"])

        timing = timing or {}
        mission = mission or {}
        campaign = campaign or {}
        fresh = fresh or {}
        x = x or {}

        boss = timing.get("boss_side") or campaign.get("boss_side") or ""
        hand = timing.get("hand_side") or campaign.get("hand_side") or ""
        war = mission.get("war_side") or ""
        agree, oppose = authority_counts(e.get("side") or "", boss, hand, war)

        row = {
            "run_label": run_label,
            "run_dir": str(run_dir),
            "paper_entry_ts": e.get("timestamp", ""),
            "ticker": e.get("ticker", ""),
            "trade_id": e.get("trade_id", ""),
            "side": e.get("side", ""),
            "entry_ask": e.get("entry_ask", ""),
            "trade_intent": e.get("trade_intent", ""),
            "strategy": e.get("strategy", ""),
            "setup_grade": e.get("setup_grade", ""),
            "signal_grade": e.get("signal_grade", ""),
            "exit_ts": x.get("timestamp", ""),
            "exit_bid": x.get("exit_bid", ""),
            "exit_reason": x.get("reason", ""),
            "pnl": x.get("pnl", ""),
            "mfe_pct": x.get("mfe_pct", ""),
            "mae_pct": x.get("mae_pct", ""),
            "settlement_result": settle,
            "settlement_correct": int(bool(settle) and settle == e.get("side")) if settle else "",
            "price_arc_phase": timing.get("price_arc_phase", ""),
            "arc_direction": timing.get("arc_direction", ""),
            "remaining_capacity": timing.get("remaining_capacity", fresh.get("remaining_capacity", "")),
            "timing_shadow": timing.get("timing_shadow", ""),
            "battlefield_class": timing.get("battlefield_class", fresh.get("battlefield_class", "")),
            "zoom_mode": timing.get("zoom_mode", ""),
            "boss_side": boss,
            "hand_side": hand,
            "war_directive": mission.get("war_directive", ""),
            "war_side": war,
            "authority_agreement_count": agree,
            "authority_opposition_count": oppose,
            "churn_type": mission.get("churn_type", ""),
            "territory_state": mission.get("borders_state", ""),
            "v95a_gate_action": fresh.get("gate_action", ""),
            "v95a_gate_reason": fresh.get("gate_reason", ""),
            "v95a_aligned_with_leg": fresh.get("aligned_with_leg", ""),
            "detector_leg_age_sec": fresh.get("leg_age_sec", ""),
            "chapter_label": campaign.get("chapter_label", fresh.get("chapter_label", "")),
            "chapter_score": campaign.get("chapter_score", fresh.get("chapter_score", "")),
            "dragon_state": fresh.get("dragon_state", campaign.get("dragon_state", "")),
            "cage_state": fresh.get("cage_state", campaign.get("cage_state", "")),
            "target_distance": fresh.get("target_distance", e.get("target_distance", "")),
            "seconds_left": fresh.get("seconds_left", e.get("seconds_to_close", "")),
            "late_mature_anticipation_shadow": fresh.get("late_mature_anticipation_shadow", ""),
            "swirling_anticipation_shadow": fresh.get("swirling_anticipation_shadow", ""),
            "join_timing_dt_ms": round(dt_timing * 1000, 1) if dt_timing is not None else "",
            "join_mission_dt_ms": round(dt_mission * 1000, 1) if dt_mission is not None else "",
            "join_campaign_dt_ms": round(dt_campaign * 1000, 1) if dt_campaign is not None else "",
            "join_freshness_dt_ms": round(dt_fresh * 1000, 1) if dt_fresh is not None else "",
        }
        state, action, reason = classify_router_state(row)
        row["router_state_v1_replay"] = state
        row["router_action_v1_replay"] = action
        row["router_reason_v1_replay"] = reason
        out.append(row)
    return out


def summarize(rows: List[dict], run_label: str, group_type: str, key: str) -> List[dict]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        groups[str(r.get(key) or "(blank)")].append(r)

    out = []
    for value, items in sorted(groups.items()):
        pnls = [fnum(x.get("pnl")) for x in items]
        pnls = [x for x in pnls if x is not None]
        mfes = [fnum(x.get("mfe_pct")) for x in items]
        mfes = [x for x in mfes if x is not None]
        maes = [fnum(x.get("mae_pct")) for x in items]
        maes = [x for x in maes if x is not None]
        settled = [x for x in items if x.get("settlement_correct") not in ("", None)]
        correct = sum(int(x.get("settlement_correct") or 0) for x in settled)
        out.append({
            "run_label": run_label,
            "group_type": group_type,
            "group_value": value,
            "n": len(items),
            "pnl": round(sum(pnls), 3),
            "wins": sum(1 for x in pnls if x > 0),
            "losses": sum(1 for x in pnls if x < 0),
            "settlement_known": len(settled),
            "settlement_correct": correct,
            "settlement_accuracy": round(correct / len(settled), 4) if settled else "",
            "avg_mfe_pct": round(mean(mfes), 3) if mfes else "",
            "avg_mae_pct": round(mean(maes), 3) if maes else "",
        })
    return out


def write_csv(path: Path, rows: List[dict], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def fmt_money(v: float) -> str:
    return "$" + f"{v:+.2f}"


def make_report(rows: List[dict], duplicate_notes: List[str], out_path: Path) -> None:
    total_pnl = sum(fnum(r.get("pnl")) or 0.0 for r in rows)
    by_state = defaultdict(list)
    by_action = defaultdict(list)
    by_run = defaultdict(list)
    for r in rows:
        by_state[r["router_state_v1_replay"]].append(r)
        by_action[r["router_action_v1_replay"]].append(r)
        by_run[r["run_label"]].append(r)

    lines = [
        "# Entry Authority Router V1 — Replay Feature Report",
        "",
        "This report is a structural replay, not a claim that the V1 states are ready for live authority.",
        "Joins use timestamp+ticker+side+ask rather than trade_id alone.",
        "",
        f"Rows: {len(rows)}",
        f"Current-engine realized P&L represented: {fmt_money(total_pnl)}",
        "",
    ]
    if duplicate_notes:
        lines += ["## Duplicate archives skipped", ""]
        lines += [f"- {x}" for x in duplicate_notes]
        lines.append("")

    lines += ["## By run", ""]
    for run, items in sorted(by_run.items()):
        pnl = sum(fnum(x.get("pnl")) or 0.0 for x in items)
        lines.append(f"- {run}: N={len(items)} P&L={fmt_money(pnl)}")
    lines.append("")

    lines += ["## Router replay states", ""]
    for state, items in sorted(by_state.items()):
        pnl = sum(fnum(x.get("pnl")) or 0.0 for x in items)
        known = [x for x in items if x.get("settlement_correct") not in ("", None)]
        correct = sum(int(x.get("settlement_correct") or 0) for x in known)
        lines.append(
            f"- {state}: N={len(items)} current-engine P&L={fmt_money(pnl)} "
            f"settlement={correct}/{len(known)}"
        )
    lines.append("")

    lines += ["## Action buckets", ""]
    for action, items in sorted(by_action.items()):
        pnl = sum(fnum(x.get("pnl")) or 0.0 for x in items)
        lines.append(f"- {action}: N={len(items)} current-engine P&L={fmt_money(pnl)}")
    lines += [
        "",
        "## Important limitation",
        "",
        "Subtracting the P&L of WAIT/BLOCK rows is only a deletion diagnostic. "
        "It is not a valid strategy backtest because waiting can create a later entry at a different price, "
        "and blocking one trade can change re-entry state and subsequent trades.",
        "",
        "The next replay step is path-aware: follow each WAIT candidate until release, pullback, invalidation, "
        "or contract close and compare the later opportunity with the original entry.",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "run_dirs",
        nargs="*",
        default=DEFAULT_RUNS,
        help="Archived run directories. Defaults to the three V9.5A research runs.",
    )
    ap.add_argument("--out-dir", default="analysis/router_v1_replay")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    all_rows: List[dict] = []
    duplicate_notes: List[str] = []
    seen_hashes: Dict[str, str] = {}

    for raw in args.run_dirs:
        run_dir = Path(raw)
        fp = paper_fingerprint(run_dir)
        if fp is None:
            print(f"SKIP missing paper ledger: {run_dir}")
            continue
        if fp in seen_hashes:
            duplicate_notes.append(f"{run_dir} duplicates {seen_hashes[fp]}")
            print(f"SKIP duplicate archive: {run_dir} == {seen_hashes[fp]}")
            continue
        seen_hashes[fp] = str(run_dir)
        label = run_dir.name
        rows = build_features(run_dir, label)
        all_rows.extend(rows)
        print(f"{label}: {len(rows)} entries reconstructed")

    write_csv(out_dir / "router_v1_features.csv", all_rows, OUT_FIELDS)

    summary_rows: List[dict] = []
    for run_label in sorted(set(r["run_label"] for r in all_rows)):
        rr = [r for r in all_rows if r["run_label"] == run_label]
        summary_rows += summarize(rr, run_label, "router_state", "router_state_v1_replay")
        summary_rows += summarize(rr, run_label, "router_action", "router_action_v1_replay")
        summary_rows += summarize(rr, run_label, "timing_shadow", "timing_shadow")
        summary_rows += summarize(rr, run_label, "authority_agreement", "authority_agreement_count")
        summary_rows += summarize(rr, run_label, "v95a_gate_reason", "v95a_gate_reason")

    summary_rows += summarize(all_rows, "ALL_RUNS", "router_state", "router_state_v1_replay")
    summary_rows += summarize(all_rows, "ALL_RUNS", "router_action", "router_action_v1_replay")
    summary_rows += summarize(all_rows, "ALL_RUNS", "timing_shadow", "timing_shadow")
    summary_rows += summarize(all_rows, "ALL_RUNS", "authority_agreement", "authority_agreement_count")
    summary_rows += summarize(all_rows, "ALL_RUNS", "v95a_gate_reason", "v95a_gate_reason")

    write_csv(out_dir / "router_v1_summary.csv", summary_rows, SUMMARY_FIELDS)
    make_report(all_rows, duplicate_notes, out_dir / "router_v1_report.md")

    print()
    print(f"WROTE {out_dir / 'router_v1_features.csv'}")
    print(f"WROTE {out_dir / 'router_v1_summary.csv'}")
    print(f"WROTE {out_dir / 'router_v1_report.md'}")


if __name__ == "__main__":
    main()
