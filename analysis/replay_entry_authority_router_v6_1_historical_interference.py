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
V6_FEATURES = Path("analysis/router_v6_transfer_proposal_replay/router_v6_transfer_proposal_features.csv")

OUT_DIR = Path("analysis/router_v6_1_historical_interference_audit")
OUT_FEATURES = OUT_DIR / "router_v6_1_historical_interference_features.csv"
OUT_REPORT = OUT_DIR / "router_v6_1_historical_interference_report.md"

SIGNAL_FILE = "tachys_signals_v9_2_6.csv"
PREENTRY_FILE = "tachys_preentry_value_memory_v9_4i.csv"
PAPER_FILE = "tachys_paper_trades_v9_2_6.csv"
REENTRY_COOLDOWN_SEC = 20.0  # existing PAPER_REENTRY_COOLDOWN in frozen core

FIELDS = [
    "run_label","trade_id","ticker","stale_side","transfer_side","transfer_relation",
    "transfer_source","transfer_ts","transfer_release_ask","settlement_result",
    "epoch_window_sec","epoch_end_ts",
    "historical_stale_trade_active_at_transfer",
    "transfer_side_slot_occupied_at_transfer","transfer_side_occupant_trade_id",
    "transfer_side_occupant_ticker","opposite_same_ticker_active_at_transfer",
    "opposite_occupant_trade_id","seconds_since_transfer_side_exit",
    "reentry_cooldown_active_at_transfer","historical_authority_path_interfered",
    "transfer_side_signal_count","opposite_side_signal_count",
    "first_transfer_side_signal_ts","first_transfer_side_signal_delay_sec",
    "first_transfer_side_signal_ask","first_transfer_side_signal_grade",
    "first_transfer_side_signal_strategy","first_transfer_side_signal_reasons",
    "transfer_side_preentry_count","first_transfer_side_preentry_event",
    "first_transfer_side_preentry_source","first_transfer_side_preentry_ts",
    "first_transfer_side_preentry_delay_sec","first_transfer_side_preentry_ask",
    "v95a_final_entry_attempt_seen",
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


def paper_ts(row: dict) -> Optional[float]:
    return v3.parse_ts(row.get("timestamp", ""), paper_local=True)


def signal_ts(row: dict) -> Optional[float]:
    # Legacy signal CSV timestamps are naive local ET.
    return v3.parse_ts(row.get("timestamp", ""), paper_local=True)


def utc_ts(row: dict) -> Optional[float]:
    return v3.parse_ts(row.get("timestamp", ""), paper_local=False)


def build_position_intervals(rows: List[dict]) -> List[dict]:
    entries = []
    exits_by_key: Dict[Tuple[str, str, str], List[Tuple[float, dict]]] = defaultdict(list)

    for r in rows:
        ts = paper_ts(r)
        if ts is None:
            continue
        key = (
            str(r.get("trade_id") or ""),
            str(r.get("ticker") or ""),
            str(r.get("side") or ""),
        )
        if r.get("event") == "EXIT":
            exits_by_key[key].append((ts, r))

    for vals in exits_by_key.values():
        vals.sort(key=lambda x: x[0])

    for r in rows:
        if r.get("event") != "ENTRY":
            continue
        ets = paper_ts(r)
        if ets is None:
            continue
        key = (
            str(r.get("trade_id") or ""),
            str(r.get("ticker") or ""),
            str(r.get("side") or ""),
        )
        exit_ts = None
        exit_row = None
        for xts, xr in exits_by_key.get(key, []):
            if xts >= ets:
                exit_ts = xts
                exit_row = xr
                break
        entries.append({
            "trade_id": key[0],
            "ticker": key[1],
            "side": key[2],
            "entry_ts": ets,
            "exit_ts": exit_ts,
            "entry_row": r,
            "exit_row": exit_row,
        })
    return entries


def active_intervals(intervals: List[dict], ts: float) -> List[dict]:
    return [
        x for x in intervals
        if x["entry_ts"] <= ts and (x["exit_ts"] is None or ts < x["exit_ts"])
    ]


def most_recent_exit(intervals: List[dict], side: str, ts: float) -> Optional[float]:
    xs = [
        x["exit_ts"] for x in intervals
        if x["side"] == side and x["exit_ts"] is not None and x["exit_ts"] <= ts
    ]
    return max(xs) if xs else None


def rows_in_epoch(rows: List[dict], parse_fn, ticker: str, start_ts: float, end_ts: float) -> List[dict]:
    out = []
    for r in rows:
        if str(r.get("ticker") or "") != ticker:
            continue
        ts = parse_fn(r)
        if ts is None or ts <= start_ts or ts > end_ts:
            continue
        rr = dict(r)
        rr["_ts"] = ts
        out.append(rr)
    out.sort(key=lambda x: x["_ts"])
    return out


def main():
    if not V6_FEATURES.exists():
        raise SystemExit(
            f"Missing {V6_FEATURES}. Run replay_entry_authority_router_v6_transfer_proposal.py first."
        )

    source = read_csv(V6_FEATURES)
    out = []

    by_run: Dict[str, List[dict]] = defaultdict(list)
    for r in source:
        by_run[r["run_label"]].append(r)

    for run_label, items in by_run.items():
        run_dir = RUN_DIRS.get(run_label)
        if run_dir is None or not run_dir.exists():
            print(f"SKIP missing run {run_label}")
            continue

        paper_rows = read_csv(run_dir / PAPER_FILE)
        signal_rows = read_csv(run_dir / SIGNAL_FILE)
        preentry_rows = read_csv(run_dir / PREENTRY_FILE)
        intervals = build_position_intervals(paper_rows)

        interference_n = 0
        raw_signal_n = 0
        preentry_n = 0

        for r in items:
            transfer_ts = v3.parse_ts(r.get("transfer_ts", ""), paper_local=False)
            epoch_window = fnum(r.get("epoch_window_sec"))
            if transfer_ts is None or epoch_window is None:
                continue
            epoch_end = transfer_ts + max(0.0, epoch_window)

            ticker = str(r.get("ticker") or "")
            tid = str(r.get("trade_id") or "")
            stale_side = str(r.get("stale_side") or "")
            transfer_side = str(r.get("transfer_side") or "")
            opposite = "NO" if transfer_side == "YES" else "YES"

            active = active_intervals(intervals, transfer_ts)
            stale_active = any(
                x["trade_id"] == tid and x["ticker"] == ticker and x["side"] == stale_side
                for x in active
            )

            side_occ = next((x for x in active if x["side"] == transfer_side), None)
            opp_same = next(
                (x for x in active if x["side"] == opposite and x["ticker"] == ticker),
                None
            )

            recent_exit = most_recent_exit(intervals, transfer_side, transfer_ts)
            since_exit = transfer_ts - recent_exit if recent_exit is not None else None
            cooldown = bool(since_exit is not None and 0 <= since_exit < REENTRY_COOLDOWN_SEC)

            interfered = bool(side_occ is not None or opp_same is not None or cooldown)
            if interfered:
                interference_n += 1

            epoch_signals = rows_in_epoch(
                signal_rows, signal_ts, ticker, transfer_ts, epoch_end
            )
            same_signals = [x for x in epoch_signals if str(x.get("side") or "") == transfer_side]
            opp_signals = [x for x in epoch_signals if str(x.get("side") or "") == opposite]
            first_sig = same_signals[0] if same_signals else None
            if first_sig:
                raw_signal_n += 1

            epoch_pre = rows_in_epoch(
                preentry_rows, utc_ts, ticker, transfer_ts, epoch_end
            )
            same_pre = [x for x in epoch_pre if str(x.get("side") or "") == transfer_side]
            first_pre = same_pre[0] if same_pre else None
            if first_pre:
                preentry_n += 1

            out.append({
                "run_label": run_label,
                "trade_id": tid,
                "ticker": ticker,
                "stale_side": stale_side,
                "transfer_side": transfer_side,
                "transfer_relation": r.get("transfer_relation", ""),
                "transfer_source": r.get("transfer_source", ""),
                "transfer_ts": r.get("transfer_ts", ""),
                "transfer_release_ask": r.get("transfer_release_ask", ""),
                "settlement_result": r.get("settlement_result", ""),
                "epoch_window_sec": r.get("epoch_window_sec", ""),
                "epoch_end_ts": v3.datetime.fromtimestamp(
                    epoch_end, v3.ZoneInfo("UTC")
                ).isoformat(),
                "historical_stale_trade_active_at_transfer": int(stale_active),
                "transfer_side_slot_occupied_at_transfer": int(side_occ is not None),
                "transfer_side_occupant_trade_id": side_occ["trade_id"] if side_occ else "",
                "transfer_side_occupant_ticker": side_occ["ticker"] if side_occ else "",
                "opposite_same_ticker_active_at_transfer": int(opp_same is not None),
                "opposite_occupant_trade_id": opp_same["trade_id"] if opp_same else "",
                "seconds_since_transfer_side_exit": round(since_exit, 3) if since_exit is not None else "",
                "reentry_cooldown_active_at_transfer": int(cooldown),
                "historical_authority_path_interfered": int(interfered),
                "transfer_side_signal_count": len(same_signals),
                "opposite_side_signal_count": len(opp_signals),
                "first_transfer_side_signal_ts": first_sig.get("timestamp", "") if first_sig else "",
                "first_transfer_side_signal_delay_sec": round(first_sig["_ts"] - transfer_ts, 3) if first_sig else "",
                "first_transfer_side_signal_ask": first_sig.get("current_ask", "") if first_sig else "",
                "first_transfer_side_signal_grade": first_sig.get("signal_grade", "") if first_sig else "",
                "first_transfer_side_signal_strategy": first_sig.get("strategy", "") if first_sig else "",
                "first_transfer_side_signal_reasons": first_sig.get("early_exception_reasons", "") if first_sig else "",
                "transfer_side_preentry_count": len(same_pre),
                "first_transfer_side_preentry_event": first_pre.get("event", "") if first_pre else "",
                "first_transfer_side_preentry_source": first_pre.get("source", "") if first_pre else "",
                "first_transfer_side_preentry_ts": first_pre.get("timestamp", "") if first_pre else "",
                "first_transfer_side_preentry_delay_sec": round(first_pre["_ts"] - transfer_ts, 3) if first_pre else "",
                "first_transfer_side_preentry_ask": first_pre.get("ask", "") if first_pre else "",
                "v95a_final_entry_attempt_seen": r.get("proposal_found", "0"),
            })

        print(
            f"{run_label}: transfer_epochs={len(items)} "
            f"path_interference={interference_n} raw_core_signal_seen={raw_signal_n} "
            f"preentry_seen={preentry_n}"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_FEATURES.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)

    total = len(out)
    interfered = [r for r in out if str(r["historical_authority_path_interfered"]) == "1"]
    raw = [r for r in out if int(r["transfer_side_signal_count"] or 0) > 0]
    pre = [r for r in out if int(r["transfer_side_preentry_count"] or 0) > 0]
    final = [r for r in out if str(r["v95a_final_entry_attempt_seen"]) == "1"]

    lines = [
        "# Router V6.1 — Historical Path Interference Audit",
        "",
        "Purpose: test whether V6's missing post-transfer ENTRY_GATE proposals were genuinely absent opportunities or artifacts of the historical trading path.",
        "",
        "Why this matters: the V6 replay observes logs from a world in which the stale historical trade was actually taken. In the proposed router world, many of those stale trades would have been blocked, so position occupancy, mutex state, and the 20s same-side re-entry cooldown can differ.",
        "",
        f"Transfer epochs audited: {total}",
        f"Historical authority path interfered at transfer: {len(interfered)}/{total}",
        f"Transfer-side CORE signal seen later in epoch: {len(raw)}/{total}",
        f"Transfer-side pre-entry memory event seen later in epoch: {len(pre)}/{total}",
        f"V9.5A final ENTRY_GATE attempt seen later in epoch: {len(final)}/{total}",
        "",
        "## Per epoch",
        "",
    ]

    for r in out:
        lines.append(
            f"- {r['run_label']} #{r['trade_id']} {r['ticker']} "
            f"{r['transfer_relation']} {r['transfer_source']} -> {r['transfer_side']} "
            f"| staleActive={r['historical_stale_trade_active_at_transfer']} "
            f"sideOccupied={r['transfer_side_slot_occupied_at_transfer']} "
            f"oppSameTicker={r['opposite_same_ticker_active_at_transfer']} "
            f"cooldown={r['reentry_cooldown_active_at_transfer']} "
            f"| coreSignals={r['transfer_side_signal_count']} "
            f"oppSignals={r['opposite_side_signal_count']} "
            f"preentry={r['transfer_side_preentry_count']} "
            f"finalAttempt={r['v95a_final_entry_attempt_seen']}"
        )

    lines += [
        "",
        "## Discipline",
        "",
        "- A missing V9.5A ENTRY_GATE row is not automatically evidence that the legacy engine failed to perceive the new chapter.",
        "- If the historical stale position was still occupying the transfer side, the replay path is contaminated for counterfactual re-entry.",
        "- Raw CORE signal and pre-entry telemetry are inspected because they can reveal recognition even when final paper authority could not re-enter.",
        "- This audit does not change V9.5A authority and does not promote a new threshold.",
        "",
    ]

    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print()
    print(f"WROTE {OUT_FEATURES}")
    print(f"WROTE {OUT_REPORT}")


if __name__ == "__main__":
    main()
