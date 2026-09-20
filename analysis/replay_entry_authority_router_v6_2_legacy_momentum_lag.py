from __future__ import annotations

import bisect
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Tuple

import replay_entry_authority_router_v3_hard_release as v3
import replay_entry_authority_router_v4_release_economics as v4

RUN_DIRS = v4.RUN_DIRS
V61_FEATURES = Path(
    "analysis/router_v6_1_historical_interference_audit/"
    "router_v6_1_historical_interference_features.csv"
)

OUT_DIR = Path("analysis/router_v6_2_legacy_momentum_lag_audit")
OUT_FEATURES = OUT_DIR / "router_v6_2_legacy_momentum_lag_features.csv"
OUT_REPORT = OUT_DIR / "router_v6_2_legacy_momentum_lag_report.md"

# Frozen legacy Core rules. These are copied exactly from the active ancestry.
EARLY_ENTRY_ASK = 0.40
CONFIRMED_ENTRY_ASK = 0.50
MAX_ENTRY_ASK = 0.80
EARLY_MOM_90_75 = 0.01
EARLY_MOM_90_60 = 0.03
CONFIRMED_MOM_90_75 = 0.02
CONFIRMED_MOM_90_60 = 0.05
PRICE_LOOKBACK_TOLERANCE_SEC = 3.0

FIELDS = [
    "run_label","trade_id","ticker","stale_side","transfer_side",
    "transfer_relation","transfer_source","transfer_ts","transfer_release_ask",
    "settlement_result","epoch_window_sec","historical_path_interfered",
    "transfer_p90","transfer_p75","transfer_p60",
    "transfer_m90_75","transfer_m90_60","legacy_state_at_transfer",
    "legacy_qualified_in_epoch","first_legacy_qual_ts","first_legacy_qual_delay_sec",
    "first_legacy_qual_ask","first_legacy_qual_grade",
    "first_legacy_p90","first_legacy_p75","first_legacy_p60",
    "first_legacy_m90_75","first_legacy_m90_60",
    "first_legacy_settlement_correct","first_legacy_hold_roi","first_legacy_hold_pnl_10",
    "logged_core_signal_seen","logged_preentry_seen","v95a_final_attempt_seen",
    "quote_points_in_epoch","quote_files_used",
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


def parse_quote_ts(row: dict) -> Optional[float]:
    epoch_ms = fnum(row.get("epoch_ms"))
    if epoch_ms is not None:
        return epoch_ms / 1000.0
    raw = str(row.get("timestamp") or "")
    if not raw:
        return None
    aware = ("+" in raw[10:] or raw.endswith("Z"))
    return v3.parse_ts(raw, paper_local=not aware)


def csv_header(path: Path) -> List[str]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            return next(csv.reader(fh), [])
    except Exception:
        return []


def load_quote_series(
    run_dir: Path,
    tickers: set[str],
) -> Tuple[Dict[str, Dict[str, List[Tuple[float,float]]]], int]:
    """
    Build a best-effort archived top-of-book series from every CSV that exposes
    timestamp+ticker+yes_ask+no_ask. This reuses the same archive policy as V4.

    Duplicate telemetry rows are harmless; we collapse exact (millisecond, side)
    duplicates after sorting.
    """
    raw: Dict[str, Dict[str, List[Tuple[float,float]]]] = {
        t: {"YES": [], "NO": []} for t in tickers
    }
    used_files = 0

    required = {"timestamp", "ticker", "yes_ask", "no_ask"}
    for path in sorted(run_dir.glob("*.csv")):
        header = csv_header(path)
        if not required.issubset(set(header)):
            continue

        file_used = False
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    ticker = str(row.get("ticker") or "")
                    if ticker not in tickers:
                        continue
                    ts = parse_quote_ts(row)
                    if ts is None:
                        continue
                    ya = fnum(row.get("yes_ask"))
                    na = fnum(row.get("no_ask"))
                    if ya is not None:
                        raw[ticker]["YES"].append((ts, ya))
                        file_used = True
                    if na is not None:
                        raw[ticker]["NO"].append((ts, na))
                        file_used = True
            if file_used:
                used_files += 1
        except Exception as exc:
            print(f"WARN quote scan failed {path.name}: {exc}")

    out: Dict[str, Dict[str, List[Tuple[float,float]]]] = {
        t: {"YES": [], "NO": []} for t in tickers
    }

    for ticker in tickers:
        for side in ("YES", "NO"):
            pts = sorted(raw[ticker][side], key=lambda x: x[0])
            dedup: List[Tuple[float,float]] = []
            seen = set()
            for ts, px in pts:
                # Millisecond identity prevents the same observer snapshot from
                # being repeated across multiple archived shadow logs.
                key = (round(ts, 3), round(px, 6))
                if key in seen:
                    continue
                seen.add(key)
                dedup.append((ts, px))
            out[ticker][side] = dedup

    return out, used_files


def nearest_price(
    series: List[Tuple[float,float]],
    target_ts: float,
    tolerance: float = PRICE_LOOKBACK_TOLERANCE_SEC,
) -> Optional[float]:
    if not series:
        return None
    times = [x[0] for x in series]
    i = bisect.bisect_left(times, target_ts)
    candidates = []
    if i < len(series):
        candidates.append(series[i])
    if i > 0:
        candidates.append(series[i-1])
    if not candidates:
        return None
    ts, px = min(candidates, key=lambda x: abs(x[0] - target_ts))
    if abs(ts - target_ts) > tolerance:
        return None
    return px


def legacy_eval(
    current_ask: Optional[float],
    p90: Optional[float],
    p75: Optional[float],
    p60: Optional[float],
) -> Tuple[str, Optional[str], Optional[float], Optional[float]]:
    if current_ask is None:
        return "NO_CURRENT_QUOTE", None, None, None
    if p90 is None or p75 is None or p60 is None:
        return "NO_90_75_60_HISTORY", None, None, None

    m90_75 = p75 - p90
    m90_60 = p60 - p90

    if current_ask < EARLY_ENTRY_ASK:
        return "ASK_BELOW_40C", None, m90_75, m90_60
    if current_ask > MAX_ENTRY_ASK:
        return "ASK_ABOVE_80C", None, m90_75, m90_60
    if current_ask <= p75 or current_ask <= p60:
        return "NO_CONTINUATION", None, m90_75, m90_60

    confirmed = (
        current_ask >= CONFIRMED_ENTRY_ASK
        and m90_75 >= CONFIRMED_MOM_90_75
        and m90_60 >= CONFIRMED_MOM_90_60
    )
    early = (
        m90_75 >= EARLY_MOM_90_75
        and m90_60 >= EARLY_MOM_90_60
    )

    if confirmed:
        return "QUALIFIED_CONFIRMED", "CONFIRMED", m90_75, m90_60
    if early:
        return "QUALIFIED_EARLY", "EARLY", m90_75, m90_60
    return "MOMENTUM_TOO_WEAK", None, m90_75, m90_60


def settlement_math(
    side: str,
    ask: Optional[float],
    settlement: str,
) -> Tuple[str, Optional[float], Optional[float]]:
    if ask is None or ask <= 0 or settlement not in ("YES", "NO"):
        return "", None, None
    correct = int(side == settlement)
    roi = ((1.0 - ask) / ask) if correct else -1.0
    return str(correct), roi, 10.0 * roi


def main():
    if not V61_FEATURES.exists():
        raise SystemExit(
            f"Missing {V61_FEATURES}. Run replay_entry_authority_router_v6_1_historical_interference.py first."
        )

    source = read_csv(V61_FEATURES)
    by_run: Dict[str, List[dict]] = defaultdict(list)
    for r in source:
        by_run[r["run_label"]].append(r)

    out = []

    for run_label, rows in by_run.items():
        run_dir = RUN_DIRS.get(run_label)
        if run_dir is None or not run_dir.exists():
            print(f"SKIP missing run {run_label}")
            continue

        tickers = {str(r.get("ticker") or "") for r in rows if r.get("ticker")}
        quotes, files_used = load_quote_series(run_dir, tickers)

        qualified_n = 0
        at_transfer_n = 0

        for r in rows:
            ticker = str(r.get("ticker") or "")
            side = str(r.get("transfer_side") or "")
            series = quotes.get(ticker, {}).get(side, [])
            transfer_ts = v3.parse_ts(r.get("transfer_ts", ""), paper_local=False)
            epoch_window = fnum(r.get("epoch_window_sec"))

            if transfer_ts is None or epoch_window is None:
                continue

            epoch_end = transfer_ts + max(0.0, epoch_window)
            release_ask = fnum(r.get("transfer_release_ask"))

            tp90 = nearest_price(series, transfer_ts - 90.0)
            tp75 = nearest_price(series, transfer_ts - 75.0)
            tp60 = nearest_price(series, transfer_ts - 60.0)
            transfer_state, transfer_grade, tm1575, tm1560 = legacy_eval(
                release_ask, tp90, tp75, tp60
            )
            if transfer_grade:
                at_transfer_n += 1

            # Reconstruct the earliest moment inside this transfer epoch at which
            # the frozen 90/75/60 Core detector itself would have qualified.
            # This deliberately stops before downstream arc/context/paper gates.
            first = None
            quote_points = 0
            for ts, ask in series:
                if ts <= transfer_ts:
                    continue
                if ts > epoch_end:
                    break
                quote_points += 1
                p90 = nearest_price(series, ts - 90.0)
                p75 = nearest_price(series, ts - 75.0)
                p60 = nearest_price(series, ts - 60.0)
                state, grade, m1575, m1560 = legacy_eval(ask, p90, p75, p60)
                if grade:
                    first = {
                        "ts": ts, "ask": ask, "grade": grade, "state": state,
                        "p90": p90, "p75": p75, "p60": p60,
                        "m90_75": m1575, "m90_60": m1560,
                    }
                    break

            if first:
                qualified_n += 1

            settlement = str(r.get("settlement_result") or "")
            first_correct, first_roi, first_pnl = settlement_math(
                side,
                first.get("ask") if first else None,
                settlement,
            )

            out.append({
                "run_label": run_label,
                "trade_id": r.get("trade_id", ""),
                "ticker": ticker,
                "stale_side": r.get("stale_side", ""),
                "transfer_side": side,
                "transfer_relation": r.get("transfer_relation", ""),
                "transfer_source": r.get("transfer_source", ""),
                "transfer_ts": r.get("transfer_ts", ""),
                "transfer_release_ask": r.get("transfer_release_ask", ""),
                "settlement_result": settlement,
                "epoch_window_sec": r.get("epoch_window_sec", ""),
                "historical_path_interfered": r.get("historical_authority_path_interfered", ""),
                "transfer_p90": tp90 if tp90 is not None else "",
                "transfer_p75": tp75 if tp75 is not None else "",
                "transfer_p60": tp60 if tp60 is not None else "",
                "transfer_m90_75": round(tm1575, 6) if tm1575 is not None else "",
                "transfer_m90_60": round(tm1560, 6) if tm1560 is not None else "",
                "legacy_state_at_transfer": transfer_state,
                "legacy_qualified_in_epoch": int(first is not None),
                "first_legacy_qual_ts": (
                    v3.datetime.fromtimestamp(first["ts"], v3.ZoneInfo("UTC")).isoformat()
                    if first else ""
                ),
                "first_legacy_qual_delay_sec": (
                    round(first["ts"] - transfer_ts, 3) if first else ""
                ),
                "first_legacy_qual_ask": first.get("ask", "") if first else "",
                "first_legacy_qual_grade": first.get("grade", "") if first else "",
                "first_legacy_p90": first.get("p90", "") if first else "",
                "first_legacy_p75": first.get("p75", "") if first else "",
                "first_legacy_p60": first.get("p60", "") if first else "",
                "first_legacy_m90_75": round(first["m90_75"], 6) if first and first.get("m90_75") is not None else "",
                "first_legacy_m90_60": round(first["m90_60"], 6) if first and first.get("m90_60") is not None else "",
                "first_legacy_settlement_correct": first_correct,
                "first_legacy_hold_roi": round(first_roi, 6) if first_roi is not None else "",
                "first_legacy_hold_pnl_10": round(first_pnl, 4) if first_pnl is not None else "",
                "logged_core_signal_seen": int(int(r.get("transfer_side_signal_count") or 0) > 0),
                "logged_preentry_seen": int(int(r.get("transfer_side_preentry_count") or 0) > 0),
                "v95a_final_attempt_seen": r.get("v95a_final_entry_attempt_seen", "0"),
                "quote_points_in_epoch": quote_points,
                "quote_files_used": files_used,
            })

        print(
            f"{run_label}: epochs={len(rows)} "
            f"legacy-qualified-at-transfer={at_transfer_n} "
            f"legacy-qualified-sometime-in-epoch={qualified_n} "
            f"quote_files_used={files_used}"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_FEATURES.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)

    total = len(out)
    at_transfer = [r for r in out if str(r.get("legacy_state_at_transfer","")).startswith("QUALIFIED_")]
    quals = [r for r in out if str(r.get("legacy_qualified_in_epoch")) == "1"]
    clean = [r for r in out if str(r.get("historical_path_interfered")) == "0"]
    clean_quals = [r for r in clean if str(r.get("legacy_qualified_in_epoch")) == "1"]

    settled = [r for r in quals if r.get("first_legacy_settlement_correct") not in ("", None)]
    correct = sum(int(r.get("first_legacy_settlement_correct") or 0) for r in settled)
    pnl = sum(fnum(r.get("first_legacy_hold_pnl_10")) or 0.0 for r in quals)

    states = defaultdict(list)
    for r in out:
        states[str(r.get("legacy_state_at_transfer") or "(blank)")].append(r)

    lines = [
        "# Router V6.2 — Legacy 90/75/60 Momentum Lag Audit",
        "",
        "Purpose: isolate the frozen Core detector from downstream paper authority.",
        "",
        "For each Hand/Boundary transfer epoch, this replay reconstructs the legacy evaluate_strategy() inputs from archived YES/NO ask telemetry and asks:",
        "1. Would the frozen 90/75/60 detector qualify the transfer side at the transfer moment?",
        "2. If not, when is the first moment it would qualify before the next transfer or contract close?",
        "",
        "Rules reproduced exactly:",
        "- ask must be 0.40–0.80",
        "- current ask must exceed both 75s and 60s reference asks",
        "- EARLY: 90→75 >= 1c and 90→60 >= 3c",
        "- CONFIRMED: ask >= 0.50, 90→75 >= 2c, 90→60 >= 5c",
        "- archived reference quote must be within 3s of its requested lookback, matching get_price_at()",
        "",
        f"Transfer epochs audited: {total}",
        f"Legacy Core already qualified at transfer: {len(at_transfer)}/{total}",
        f"Legacy Core qualified at any point in transfer epoch: {len(quals)}/{total}",
        f"Clean/no-path-interference epochs qualified at any point: {len(clean_quals)}/{len(clean)}",
        f"Settlement correctness at first reconstructed legacy qualification: {correct}/{len(settled)}",
        f"$10 hold sum from first reconstructed legacy qualification: {pnl:+.2f}",
        "",
        "## Legacy state exactly at transfer",
        "",
    ]

    for state, items in sorted(states.items()):
        c = sum(
            int(str(x.get("transfer_side") or "") == str(x.get("settlement_result") or ""))
            for x in items if x.get("settlement_result") in ("YES","NO")
        )
        known = sum(1 for x in items if x.get("settlement_result") in ("YES","NO"))
        lines.append(f"- {state}: N={len(items)} transfer-side-settlement={c}/{known}")

    lines += ["", "## Per epoch", ""]

    for r in out:
        lines.append(
            f"- {r['run_label']} #{r['trade_id']} {r['ticker']} "
            f"{r['transfer_relation']} {r['transfer_source']} -> {r['transfer_side']} "
            f"| ask={r['transfer_release_ask']} "
            f"| atTransfer={r['legacy_state_at_transfer']} "
            f"| firstLegacy={r['first_legacy_qual_delay_sec'] or 'NONE'}s "
            f"ask={r['first_legacy_qual_ask'] or 'NA'} "
            f"grade={r['first_legacy_qual_grade'] or 'NA'} "
            f"| pathInterference={r['historical_path_interfered']} "
            f"loggedCore={r['logged_core_signal_seen']} "
            f"preentry={r['logged_preentry_seen']} finalAttempt={r['v95a_final_attempt_seen']} "
            f"| settle={r['settlement_result']} hold$10={r['first_legacy_hold_pnl_10'] or 'NA'}"
        )

    lines += [
        "",
        "## Discipline",
        "",
        "- This is an audit of the existing legacy detector, not a new entry detector.",
        "- Reconstructed qualification means only evaluate_strategy() would have passed; downstream phase, arc, structural, mutex, cooldown, and paper gates are intentionally excluded.",
        "- If profitable transfer epochs remain invisible to this reconstructed detector, that is direct evidence that the 90/75/60 proposal generator can lag the battlefield reset.",
        "- If it qualifies quickly but no logged CORE signal/final attempt appears, the loss occurs downstream in the permission path instead.",
        "- No V9.5A authority changes.",
        "",
    ]

    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print()
    print(f"WROTE {OUT_FEATURES}")
    print(f"WROTE {OUT_REPORT}")


if __name__ == "__main__":
    main()
