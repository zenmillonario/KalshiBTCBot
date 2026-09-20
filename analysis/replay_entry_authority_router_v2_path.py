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
    "freshness": "tachys_price_freshness_v9_5a.csv",
    "preentry": "tachys_preentry_value_memory_v9_4i.csv",
    "lateness": "tachys_move_lateness_v9_4i.csv",
    "price_arc": "tachys_price_arc_phase_v9_4j.csv",
}

OUT_FIELDS = [
    "run_label", "paper_entry_ts", "ticker", "trade_id", "side", "entry_ask",
    "trade_intent", "strategy", "actual_pnl", "actual_exit_reason", "mfe_pct", "mae_pct",
    "settlement_result", "settlement_correct",
    "initial_router_state", "initial_timing_shadow", "initial_phase", "initial_arc_direction",
    "initial_remaining_capacity", "initial_battlefield", "initial_boss_side", "initial_hand_side",
    "first_directional_ask", "first_valid_ask", "best_valid_ask",
    "epoch_age_sec", "post_valid_wait_sec", "prevalidation_delay_sec",
    "ask_inflation_from_first_cents", "ask_inflation_from_best_cents",
    "legacy_lateness_class", "legacy_lateness_score", "legacy_lateness_components",
    "prevalidation_delay_bin", "first_directional_reprice_bin",
    "first_phase_exit_ts", "first_phase_exit_delay_sec", "first_phase_exit",
    "same_side_release_ts", "same_side_release_delay_sec", "same_side_release_phase",
    "same_side_release_remaining_capacity", "same_side_release_btc",
    "opposite_release_ts", "opposite_release_delay_sec", "opposite_release_phase",
    "opposite_release_remaining_capacity", "opposite_release_btc",
    "resolution_order",
    "next_same_side_valid_ts", "next_same_side_valid_delay_sec", "next_same_side_valid_ask",
    "next_same_side_ask_delta_cents", "next_same_side_hold_roi_if_settled",
    "next_opposite_valid_ts", "next_opposite_valid_delay_sec", "next_opposite_valid_ask",
    "next_opposite_hold_roi_if_settled",
]

SUMMARY_FIELDS = [
    "run_label", "group_type", "group_value", "n", "actual_pnl", "wins", "losses",
    "settlement_known", "settlement_correct", "settlement_accuracy",
    "avg_mfe_pct", "avg_mae_pct", "avg_prevalidation_delay_sec",
    "avg_first_directional_reprice_cents",
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
    s = str(value).strip()
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


def fingerprint(run_dir: Path) -> Optional[str]:
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


def nearest_entry_row(
    entry: dict,
    rows: Iterable[dict],
    *,
    event: Optional[str] = None,
    ask_field: Optional[str] = None,
    max_dt: float = 3.0,
) -> Tuple[Optional[dict], Optional[float]]:
    ets = parse_ts(entry.get("timestamp", ""), paper_local=True)
    if ets is None:
        return None, None
    best, best_dt = None, None
    for row in rows:
        if event is not None and str(row.get("event") or "") != event:
            continue
        if row.get("ticker") != entry.get("ticker"):
            continue
        if row.get("side") and str(row.get("side")) != str(entry.get("side")):
            continue
        if ask_field and not ask_close(entry.get("entry_ask"), row.get(ask_field)):
            continue
        rts = parse_ts(row.get("timestamp", ""), paper_local=False)
        if rts is None:
            continue
        dt = abs(rts - ets)
        if dt <= max_dt and (best_dt is None or dt < best_dt):
            best, best_dt = row, dt
    return best, best_dt


def nearest_exit(entry: dict, exits: Iterable[dict]) -> Optional[dict]:
    ets = parse_ts(entry.get("timestamp", ""), paper_local=True)
    if ets is None:
        return None
    best, best_dt = None, None
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
        if dt <= 20 * 60 and (best_dt is None or dt < best_dt):
            best, best_dt = row, dt
    return best


def settlement_for(entry: dict, results: Iterable[dict]) -> str:
    rows = [r for r in results if r.get("ticker") == entry.get("ticker")]
    return str(rows[-1].get("result") or "") if rows else ""


def initial_router_state(timing: dict) -> str:
    phase = str(timing.get("price_arc_phase") or "")
    action = str(timing.get("timing_shadow") or "")
    rem = fnum(timing.get("remaining_capacity"))
    battlefield = str(timing.get("battlefield_class") or "")

    if phase == "CROSS_RESET" or action == "WAIT_NEW_ARC_SHADOW":
        return "HINGE_WAIT"
    if phase == "RETURN_TO_EMA9" or action == "WAIT_EMA9_REACTION_SHADOW":
        return "PULLBACK_WAIT"
    if action == "LOW_REMAINING_CAPACITY_SHADOW" or (
        rem is not None and rem <= 0.22 and phase in ("PEAK_TROUGH_BUILD", "EXTENSION_SLOW")
    ):
        return "MID_PLAY_CLOSED"
    if action in ("EARLY_COUNTERARC_SHADOW", "ELITE_RAID_ONLY_SHADOW"):
        return "TACTICAL_COUNTERWAVE_ONLY"
    if "STORM" in battlefield:
        return "UNRESOLVED_STORM"
    return "UNCLASSIFIED_ENTRY"


def delay_bin(v: Optional[float]) -> str:
    if v is None:
        return "NA"
    if v < 3:
        return "LT3S"
    if v < 6:
        return "3_6S"
    if v < 9:
        return "6_9S"
    if v < 15:
        return "9_15S"
    return "GE15S"


def reprice_bin(v: Optional[float]) -> str:
    if v is None:
        return "NA"
    if v <= 0:
        return "LE0C"
    if v < 3:
        return "0_3C"
    if v < 6:
        return "3_6C"
    if v < 9:
        return "6_9C"
    if v < 15:
        return "9_15C"
    return "GE15C"


def release_candidate(row: dict, wanted: str) -> bool:
    phase = str(row.get("price_arc_phase") or "")
    direction = str(row.get("arc_direction") or "")
    rem = fnum(row.get("remaining_capacity"))
    if direction != wanted:
        return False
    if phase not in ("LAUNCH", "EXTENSION", "EXTENSION_SLOW", "PEAK_TROUGH_BUILD"):
        return False
    # Do not require a hard capacity threshold here; this is descriptive replay.
    # Capacity is logged for later comparison.
    return rem is None or rem > 0.0


def first_future_arc(
    rows: List[dict],
    ticker: str,
    start_ts: float,
    end_ts: float,
    predicate,
) -> Optional[dict]:
    best = None
    for row in rows:
        if row.get("ticker") != ticker:
            continue
        ts = parse_ts(row.get("timestamp", ""), paper_local=False)
        if ts is None or ts <= start_ts or ts > end_ts:
            continue
        if predicate(row):
            if best is None or ts < best["_ts"]:
                best = dict(row)
                best["_ts"] = ts
    return best


def first_future_valid(
    rows: List[dict],
    ticker: str,
    side: str,
    start_ts: float,
    end_ts: float,
) -> Optional[dict]:
    best = None
    for row in rows:
        if row.get("ticker") != ticker or row.get("side") != side:
            continue
        if row.get("event") not in ("FIRST_VALID", "BEST_VALID"):
            continue
        if str(row.get("structurally_valid") or "") not in ("1", "True", "true"):
            continue
        ts = parse_ts(row.get("timestamp", ""), paper_local=False)
        if ts is None or ts <= start_ts + 0.5 or ts > end_ts:
            continue
        if best is None or ts < best["_ts"]:
            best = dict(row)
            best["_ts"] = ts
    return best


def hold_roi(ask: Optional[float], side: str, settlement: str) -> Optional[float]:
    if ask is None or ask <= 0 or not settlement:
        return None
    return ((1.0 - ask) / ask) if side == settlement else -1.0


def build_run(run_dir: Path, run_label: str) -> List[dict]:
    d = {k: read_csv(run_dir / fn) for k, fn in FILES.items()}
    entries = [r for r in d["paper"] if r.get("event") == "ENTRY"]
    exits = [r for r in d["paper"] if r.get("event") == "EXIT"]
    out = []

    for e in entries:
        ets = parse_ts(e.get("timestamp", ""), paper_local=True)
        if ets is None:
            continue

        timing, _ = nearest_entry_row(e, d["timing"], event="ENTERED", ask_field="ask", max_dt=3.0)
        fresh, _ = nearest_entry_row(e, d["freshness"], event="ENTRY_GATE", ask_field="ask", max_dt=3.0)
        pre, _ = nearest_entry_row(e, d["preentry"], event="PAPER_ENTRY", ask_field="ask", max_dt=3.0)
        late, _ = nearest_entry_row(e, d["lateness"], ask_field="entry_ask", max_dt=3.0)
        x = nearest_exit(e, exits) or {}
        settlement = settlement_for(e, d["results"])

        timing = timing or {}
        fresh = fresh or {}
        pre = pre or {}
        late = late or {}

        seconds_left = fnum(e.get("seconds_to_close"))
        if seconds_left is None:
            seconds_left = fnum(fresh.get("seconds_left"))
        end_ts = ets + (seconds_left if seconds_left is not None else 15 * 60)

        wanted = "UP" if e.get("side") == "YES" else "DOWN"
        opposite = "DOWN" if wanted == "UP" else "UP"

        phase_exit = first_future_arc(
            d["price_arc"], e.get("ticker", ""), ets, end_ts,
            lambda r: str(r.get("price_arc_phase") or "") != str(timing.get("price_arc_phase") or "")
        )
        same_release = first_future_arc(
            d["price_arc"], e.get("ticker", ""), ets, end_ts,
            lambda r: release_candidate(r, wanted)
        )
        opp_release = first_future_arc(
            d["price_arc"], e.get("ticker", ""), ets, end_ts,
            lambda r: release_candidate(r, opposite)
        )

        next_same = first_future_valid(d["preentry"], e.get("ticker", ""), e.get("side", ""), ets, end_ts)
        opp_side = "NO" if e.get("side") == "YES" else "YES"
        next_opp = first_future_valid(d["preentry"], e.get("ticker", ""), opp_side, ets, end_ts)

        same_ts = same_release.get("_ts") if same_release else None
        opp_ts = opp_release.get("_ts") if opp_release else None
        if same_ts is None and opp_ts is None:
            resolution = "NO_RELEASE_SEEN"
        elif opp_ts is None or (same_ts is not None and same_ts < opp_ts):
            resolution = "SAME_SIDE_RELEASE_FIRST"
        elif same_ts is None or opp_ts < same_ts:
            resolution = "OPPOSITE_RELEASE_FIRST"
        else:
            resolution = "SIMULTANEOUS_RELEASE"

        epoch_age = fnum(pre.get("epoch_age_sec"))
        post_valid_wait = fnum(pre.get("candidate_age_sec"))
        prevalidation_delay = None
        if epoch_age is not None and post_valid_wait is not None:
            prevalidation_delay = max(0.0, epoch_age - post_valid_wait)

        reprice_first = fnum(pre.get("ask_inflation_from_first_cents"))
        entry_ask = fnum(e.get("entry_ask"))

        same_valid_ask = fnum(next_same.get("ask")) if next_same else None
        opp_valid_ask = fnum(next_opp.get("ask")) if next_opp else None

        row = {
            "run_label": run_label,
            "paper_entry_ts": e.get("timestamp", ""),
            "ticker": e.get("ticker", ""),
            "trade_id": e.get("trade_id", ""),
            "side": e.get("side", ""),
            "entry_ask": e.get("entry_ask", ""),
            "trade_intent": e.get("trade_intent", ""),
            "strategy": e.get("strategy", ""),
            "actual_pnl": x.get("pnl", ""),
            "actual_exit_reason": x.get("reason", ""),
            "mfe_pct": x.get("mfe_pct", ""),
            "mae_pct": x.get("mae_pct", ""),
            "settlement_result": settlement,
            "settlement_correct": int(bool(settlement) and settlement == e.get("side")) if settlement else "",
            "initial_router_state": initial_router_state(timing),
            "initial_timing_shadow": timing.get("timing_shadow", ""),
            "initial_phase": timing.get("price_arc_phase", ""),
            "initial_arc_direction": timing.get("arc_direction", ""),
            "initial_remaining_capacity": timing.get("remaining_capacity", fresh.get("remaining_capacity", "")),
            "initial_battlefield": timing.get("battlefield_class", fresh.get("battlefield_class", "")),
            "initial_boss_side": timing.get("boss_side", ""),
            "initial_hand_side": timing.get("hand_side", ""),
            "first_directional_ask": pre.get("first_directional_ask", ""),
            "first_valid_ask": pre.get("first_valid_ask", ""),
            "best_valid_ask": pre.get("best_valid_ask", ""),
            "epoch_age_sec": epoch_age if epoch_age is not None else "",
            "post_valid_wait_sec": post_valid_wait if post_valid_wait is not None else "",
            "prevalidation_delay_sec": prevalidation_delay if prevalidation_delay is not None else "",
            "ask_inflation_from_first_cents": reprice_first if reprice_first is not None else "",
            "ask_inflation_from_best_cents": pre.get("ask_inflation_from_best_cents", ""),
            "legacy_lateness_class": late.get("classification", ""),
            "legacy_lateness_score": late.get("score", ""),
            "legacy_lateness_components": late.get("components", ""),
            "prevalidation_delay_bin": delay_bin(prevalidation_delay),
            "first_directional_reprice_bin": reprice_bin(reprice_first),
            "first_phase_exit_ts": phase_exit.get("timestamp", "") if phase_exit else "",
            "first_phase_exit_delay_sec": round(phase_exit["_ts"] - ets, 3) if phase_exit else "",
            "first_phase_exit": phase_exit.get("price_arc_phase", "") if phase_exit else "",
            "same_side_release_ts": same_release.get("timestamp", "") if same_release else "",
            "same_side_release_delay_sec": round(same_ts - ets, 3) if same_ts else "",
            "same_side_release_phase": same_release.get("price_arc_phase", "") if same_release else "",
            "same_side_release_remaining_capacity": same_release.get("remaining_capacity", "") if same_release else "",
            "same_side_release_btc": same_release.get("btc_price", "") if same_release else "",
            "opposite_release_ts": opp_release.get("timestamp", "") if opp_release else "",
            "opposite_release_delay_sec": round(opp_ts - ets, 3) if opp_ts else "",
            "opposite_release_phase": opp_release.get("price_arc_phase", "") if opp_release else "",
            "opposite_release_remaining_capacity": opp_release.get("remaining_capacity", "") if opp_release else "",
            "opposite_release_btc": opp_release.get("btc_price", "") if opp_release else "",
            "resolution_order": resolution,
            "next_same_side_valid_ts": next_same.get("timestamp", "") if next_same else "",
            "next_same_side_valid_delay_sec": round(next_same["_ts"] - ets, 3) if next_same else "",
            "next_same_side_valid_ask": same_valid_ask if same_valid_ask is not None else "",
            "next_same_side_ask_delta_cents": (
                round((same_valid_ask - entry_ask) * 100, 3)
                if same_valid_ask is not None and entry_ask is not None else ""
            ),
            "next_same_side_hold_roi_if_settled": (
                round(hold_roi(same_valid_ask, e.get("side", ""), settlement), 4)
                if hold_roi(same_valid_ask, e.get("side", ""), settlement) is not None else ""
            ),
            "next_opposite_valid_ts": next_opp.get("timestamp", "") if next_opp else "",
            "next_opposite_valid_delay_sec": round(next_opp["_ts"] - ets, 3) if next_opp else "",
            "next_opposite_valid_ask": opp_valid_ask if opp_valid_ask is not None else "",
            "next_opposite_hold_roi_if_settled": (
                round(hold_roi(opp_valid_ask, opp_side, settlement), 4)
                if hold_roi(opp_valid_ask, opp_side, settlement) is not None else ""
            ),
        }
        out.append(row)

    return out


def summarize(rows: List[dict], run_label: str, group_type: str, key: str) -> List[dict]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        groups[str(r.get(key) or "(blank)")].append(r)

    out = []
    for value, items in sorted(groups.items()):
        pnls = [fnum(x.get("actual_pnl")) for x in items]
        pnls = [x for x in pnls if x is not None]
        mfes = [fnum(x.get("mfe_pct")) for x in items]
        mfes = [x for x in mfes if x is not None]
        maes = [fnum(x.get("mae_pct")) for x in items]
        maes = [x for x in maes if x is not None]
        delays = [fnum(x.get("prevalidation_delay_sec")) for x in items]
        delays = [x for x in delays if x is not None]
        reprices = [fnum(x.get("ask_inflation_from_first_cents")) for x in items]
        reprices = [x for x in reprices if x is not None]
        settled = [x for x in items if x.get("settlement_correct") not in ("", None)]
        correct = sum(int(x.get("settlement_correct") or 0) for x in settled)
        out.append({
            "run_label": run_label,
            "group_type": group_type,
            "group_value": value,
            "n": len(items),
            "actual_pnl": round(sum(pnls), 3),
            "wins": sum(1 for x in pnls if x > 0),
            "losses": sum(1 for x in pnls if x < 0),
            "settlement_known": len(settled),
            "settlement_correct": correct,
            "settlement_accuracy": round(correct / len(settled), 4) if settled else "",
            "avg_mfe_pct": round(mean(mfes), 3) if mfes else "",
            "avg_mae_pct": round(mean(maes), 3) if maes else "",
            "avg_prevalidation_delay_sec": round(mean(delays), 3) if delays else "",
            "avg_first_directional_reprice_cents": round(mean(reprices), 3) if reprices else "",
        })
    return out


def write_csv(path: Path, rows: List[dict], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def money(v: float) -> str:
    return "$" + f"{v:+.2f}"


def report(rows: List[dict], dupes: List[str], path: Path) -> None:
    total = sum(fnum(r.get("actual_pnl")) or 0.0 for r in rows)
    lines = [
        "# Entry Authority Router V2 — Path / Recognition Replay",
        "",
        "Purpose: measure the movie, especially the time between first directional evidence, first structural validity, actual entry, and later arc resolution.",
        "",
        f"Rows: {len(rows)}",
        f"Current-engine realized P&L represented: {money(total)}",
        "",
    ]

    if dupes:
        lines += ["## Duplicate archives skipped", ""]
        lines += [f"- {d}" for d in dupes]
        lines.append("")

    def emit(title: str, key: str):
        groups = defaultdict(list)
        for r in rows:
            groups[str(r.get(key) or "(blank)")].append(r)
        lines.extend([f"## {title}", ""])
        for val, items in sorted(groups.items()):
            pnl = sum(fnum(x.get("actual_pnl")) or 0.0 for x in items)
            known = [x for x in items if x.get("settlement_correct") not in ("", None)]
            correct = sum(int(x.get("settlement_correct") or 0) for x in known)
            lines.append(f"- {val}: N={len(items)} P&L={money(pnl)} settlement={correct}/{len(known)}")
        lines.append("")

    emit("Prevalidation delay bins", "prevalidation_delay_bin")
    emit("Repricing from first directional evidence", "first_directional_reprice_bin")
    emit("Initial router state", "initial_router_state")
    emit("Which release appeared first after entry", "resolution_order")
    emit("Legacy lateness class", "legacy_lateness_class")

    lines += [
        "## Interpretation discipline",
        "",
        "- Prevalidation delay begins at first directional evidence, not at first structural approval.",
        "- Repricing from first directional evidence measures how much Kalshi moved while Tachys was deciding.",
        "- Later release ordering is descriptive. It does not prove a hypothetical entry would have filled or been managed identically.",
        "- No threshold in this report is paper authority.",
        "",
        "The next step is to inspect the high-loss combinations, then write a governor rule only if the same structural pattern repeats across independent runs.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dirs", nargs="*", default=DEFAULT_RUNS)
    ap.add_argument("--out-dir", default="analysis/router_v2_path_replay")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    seen: Dict[str, str] = {}
    dupes: List[str] = []
    all_rows: List[dict] = []

    for raw in args.run_dirs:
        run_dir = Path(raw)
        fp = fingerprint(run_dir)
        if fp is None:
            print(f"SKIP missing paper ledger: {run_dir}")
            continue
        if fp in seen:
            dupes.append(f"{run_dir} duplicates {seen[fp]}")
            print(f"SKIP duplicate archive: {run_dir} == {seen[fp]}")
            continue
        seen[fp] = str(run_dir)
        rows = build_run(run_dir, run_dir.name)
        all_rows.extend(rows)
        print(f"{run_dir.name}: {len(rows)} entries reconstructed")

    write_csv(out_dir / "router_v2_path_features.csv", all_rows, OUT_FIELDS)

    summaries: List[dict] = []
    groupings = [
        ("initial_router_state", "initial_router_state"),
        ("prevalidation_delay", "prevalidation_delay_bin"),
        ("first_directional_reprice", "first_directional_reprice_bin"),
        ("resolution_order", "resolution_order"),
        ("legacy_lateness_class", "legacy_lateness_class"),
    ]
    for label in sorted(set(r["run_label"] for r in all_rows)):
        rr = [r for r in all_rows if r["run_label"] == label]
        for group_type, key in groupings:
            summaries += summarize(rr, label, group_type, key)
    for group_type, key in groupings:
        summaries += summarize(all_rows, "ALL_RUNS", group_type, key)

    write_csv(out_dir / "router_v2_path_summary.csv", summaries, SUMMARY_FIELDS)
    report(all_rows, dupes, out_dir / "router_v2_path_report.md")

    print()
    print(f"WROTE {out_dir / 'router_v2_path_features.csv'}")
    print(f"WROTE {out_dir / 'router_v2_path_summary.csv'}")
    print(f"WROTE {out_dir / 'router_v2_path_report.md'}")


if __name__ == "__main__":
    main()
