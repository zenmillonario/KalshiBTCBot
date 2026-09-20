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
    "preentry": "tachys_preentry_value_memory_v9_4i.csv",
    "failed_regen": "tachys_failed_regen_shadow_v9_4i.csv",
    "crest": "tachys_crest_fakeout_v9_4i.csv",
    "borders": "tachys_master_of_borders_v9_4i.csv",
    "hand": "tachys_regime_handshake_v9_4i.csv",
    "war": "tachys_rollover_war_council_v9_4i.csv",
}

OUT_FIELDS = [
    "run_label", "paper_entry_ts", "ticker", "trade_id", "side", "entry_ask",
    "trade_intent", "strategy", "actual_pnl", "actual_exit_reason",
    "settlement_result", "settlement_correct",
    "timing_shadow", "price_arc_phase", "battlefield_class",
    "prevalidation_delay_sec", "ask_inflation_from_first_cents",
    "stale9", "initial_state",
    "coverage_failed_regen", "coverage_crest", "coverage_borders",
    "coverage_hand", "coverage_war", "coverage_source_count",
    "same_hard_release_source", "same_hard_release_ts", "same_hard_release_delay_sec",
    "same_hard_release_detail",
    "opposite_hard_release_source", "opposite_hard_release_ts", "opposite_hard_release_delay_sec",
    "opposite_hard_release_detail",
    "hard_release_order",
    "same_hard_release_within_9s", "same_hard_release_within_30s",
    "opposite_hard_release_within_9s", "opposite_hard_release_within_30s",
]

SUMMARY_FIELDS = [
    "run_label", "group_type", "group_value", "n", "actual_pnl",
    "wins", "losses", "settlement_known", "settlement_correct",
    "settlement_accuracy", "avg_prevalidation_delay_sec",
    "avg_reprice_from_first_cents",
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
) -> Optional[dict]:
    ets = parse_ts(entry.get("timestamp", ""), paper_local=True)
    if ets is None:
        return None
    best = None
    best_dt = None
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
            best = row
            best_dt = dt
    return best


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
        if dt <= 20 * 60 and (best_dt is None or dt < best_dt):
            best = row
            best_dt = dt
    return best


def settlement_for(entry: dict, results: Iterable[dict]) -> str:
    rows = [r for r in results if r.get("ticker") == entry.get("ticker")]
    return str(rows[-1].get("result") or "") if rows else ""


def initial_state(timing: dict) -> str:
    phase = str(timing.get("price_arc_phase") or "")
    shadow = str(timing.get("timing_shadow") or "")
    battlefield = str(timing.get("battlefield_class") or "")
    rem = fnum(timing.get("remaining_capacity"))

    if phase == "CROSS_RESET" or shadow == "WAIT_NEW_ARC_SHADOW":
        return "HINGE_WAIT"
    if phase == "RETURN_TO_EMA9" or shadow == "WAIT_EMA9_REACTION_SHADOW":
        return "PULLBACK_WAIT"
    if shadow == "LOW_REMAINING_CAPACITY_SHADOW" or (
        rem is not None and rem <= 0.22 and phase in ("PEAK_TROUGH_BUILD", "EXTENSION_SLOW")
    ):
        return "MID_PLAY_CLOSED"
    if shadow in ("EARLY_COUNTERARC_SHADOW", "ELITE_RAID_ONLY_SHADOW"):
        return "TACTICAL_COUNTERWAVE_ONLY"
    if "STORM" in battlefield:
        return "UNRESOLVED_STORM"
    return "UNCLASSIFIED_ENTRY"


def regime_side(regime: str) -> str:
    r = str(regime or "").upper()
    if r.startswith("UP_"):
        return "YES"
    if r.startswith("DOWN_"):
        return "NO"
    return ""


def map_release_side(v: str) -> str:
    s = str(v or "").upper()
    if s in ("YES", "UP"):
        return "YES"
    if s in ("NO", "DOWN"):
        return "NO"
    return ""


def build_hard_events(data: Dict[str, List[dict]]) -> List[dict]:
    events: List[dict] = []

    # Failed regeneration: strongest event is CONFIRMED_RELEASE.
    for r in data["failed_regen"]:
        if str(r.get("state") or "") != "CONFIRMED_RELEASE":
            continue
        side = map_release_side(r.get("shadow_side"))
        ts = parse_ts(r.get("timestamp", ""))
        if not side or ts is None:
            continue
        events.append({
            "ts": ts, "timestamp": r.get("timestamp", ""), "ticker": r.get("ticker", ""),
            "side": side, "source": "FAILED_REGEN_CONFIRMED",
            "detail": str(r.get("release_reasons") or r.get("event") or ""),
        })

    # Crest fakeout release.
    for r in data["crest"]:
        if str(r.get("event") or "") != "RELEASE_CONFIRMED":
            continue
        side = map_release_side(r.get("release_side"))
        ts = parse_ts(r.get("timestamp", ""))
        if not side or ts is None:
            continue
        events.append({
            "ts": ts, "timestamp": r.get("timestamp", ""), "ticker": r.get("ticker", ""),
            "side": side, "source": "CREST_RELEASE_CONFIRMED",
            "detail": str(r.get("reason") or ""),
        })

    # Borders: only explicit directional releases count.
    for r in data["borders"]:
        if str(r.get("territory_state") or "") != "BOUNDARY_RELEASE":
            continue
        side = map_release_side(r.get("release_side"))
        ts = parse_ts(r.get("timestamp", ""))
        if not side or ts is None:
            continue
        events.append({
            "ts": ts, "timestamp": r.get("timestamp", ""), "ticker": r.get("ticker", ""),
            "side": side, "source": "BOUNDARY_RELEASE",
            "detail": ";".join(filter(None, [
                str(r.get("transition_reason") or ""),
                str(r.get("churn_type") or ""),
            ])),
        })

    # Hand: count only true transfer from non-side to side.
    for r in data["hand"]:
        trans = str(r.get("transition_event") or "")
        if "->" not in trans:
            continue
        before, after = trans.split("->", 1)
        side = map_release_side(r.get("authority_side"))
        if not side:
            continue
        before_side = regime_side(before)
        after_side = regime_side(after)
        if after_side != side:
            continue
        if before_side == side:
            continue
        ts = parse_ts(r.get("timestamp", ""))
        if ts is None:
            continue
        events.append({
            "ts": ts, "timestamp": r.get("timestamp", ""), "ticker": r.get("ticker", ""),
            "side": side, "source": "HAND_AUTHORITY_TRANSFER",
            "detail": trans,
        })

    # War: use actual meetings/rollover remap, not later outcome rows.
    for r in data["war"]:
        if str(r.get("event") or "") not in ("MEETING", "ROLLOVER_REMAP", "FIRST_VALID_PRICE"):
            continue
        directive = str(r.get("directive") or "")
        if directive not in ("ACT_IMMEDIATELY", "ACT_FIRST_VALID"):
            continue
        side = map_release_side(r.get("directive_side"))
        if not side:
            continue
        ts = parse_ts(r.get("timestamp", ""))
        if ts is None:
            continue
        ticker = str(r.get("from_ticker") or "")
        events.append({
            "ts": ts, "timestamp": r.get("timestamp", ""), "ticker": ticker,
            "side": side, "source": "WAR_COUNCIL_RELEASE",
            "detail": ";".join(filter(None, [
                directive,
                str(r.get("structural_event") or ""),
                str(r.get("reason") or ""),
            ])),
        })

    events.sort(key=lambda x: x["ts"])
    return events


def first_hard_event(
    events: List[dict], ticker: str, side: str, start_ts: float, end_ts: float
) -> Optional[dict]:
    for ev in events:
        if ev["ts"] <= start_ts:
            continue
        if ev["ts"] > end_ts:
            break
        if ev.get("ticker") == ticker and ev.get("side") == side:
            return ev
    return None


def build_run(run_dir: Path, run_label: str) -> List[dict]:
    data = {k: read_csv(run_dir / fn) for k, fn in FILES.items()}
    entries = [r for r in data["paper"] if r.get("event") == "ENTRY"]
    exits = [r for r in data["paper"] if r.get("event") == "EXIT"]
    hard = build_hard_events(data)

    coverage = {
        "failed_regen": int(bool(data["failed_regen"])),
        "crest": int(bool(data["crest"])),
        "borders": int(bool(data["borders"])),
        "hand": int(bool(data["hand"])),
        "war": int(bool(data["war"])),
    }

    out = []
    for e in entries:
        ets = parse_ts(e.get("timestamp", ""), paper_local=True)
        if ets is None:
            continue

        timing = nearest_entry_row(e, data["timing"], event="ENTERED", ask_field="ask") or {}
        pre = nearest_entry_row(e, data["preentry"], event="PAPER_ENTRY", ask_field="ask") or {}
        x = nearest_exit(e, exits) or {}
        settlement = settlement_for(e, data["results"])

        epoch_age = fnum(pre.get("epoch_age_sec"))
        post_valid_wait = fnum(pre.get("candidate_age_sec"))
        prevalidation_delay = None
        if epoch_age is not None and post_valid_wait is not None:
            prevalidation_delay = max(0.0, epoch_age - post_valid_wait)

        seconds_left = fnum(e.get("seconds_to_close"))
        end_ts = ets + (seconds_left if seconds_left is not None else 15 * 60)

        side = str(e.get("side") or "")
        opp = "NO" if side == "YES" else "YES"

        same = first_hard_event(hard, e.get("ticker", ""), side, ets, end_ts)
        opposite = first_hard_event(hard, e.get("ticker", ""), opp, ets, end_ts)

        same_ts = same["ts"] if same else None
        opp_ts = opposite["ts"] if opposite else None

        if same_ts is None and opp_ts is None:
            order = "NO_HARD_RELEASE_SEEN"
        elif same_ts is not None and (opp_ts is None or same_ts < opp_ts):
            order = "SAME_HARD_RELEASE_FIRST"
        elif opp_ts is not None and (same_ts is None or opp_ts < same_ts):
            order = "OPPOSITE_HARD_RELEASE_FIRST"
        else:
            order = "SIMULTANEOUS_HARD_RELEASE"

        same_delay = (same_ts - ets) if same_ts is not None else None
        opp_delay = (opp_ts - ets) if opp_ts is not None else None

        row = {
            "run_label": run_label,
            "paper_entry_ts": e.get("timestamp", ""),
            "ticker": e.get("ticker", ""),
            "trade_id": e.get("trade_id", ""),
            "side": side,
            "entry_ask": e.get("entry_ask", ""),
            "trade_intent": e.get("trade_intent", ""),
            "strategy": e.get("strategy", ""),
            "actual_pnl": x.get("pnl", ""),
            "actual_exit_reason": x.get("reason", ""),
            "settlement_result": settlement,
            "settlement_correct": int(bool(settlement) and settlement == side) if settlement else "",
            "timing_shadow": timing.get("timing_shadow", ""),
            "price_arc_phase": timing.get("price_arc_phase", ""),
            "battlefield_class": timing.get("battlefield_class", ""),
            "prevalidation_delay_sec": prevalidation_delay if prevalidation_delay is not None else "",
            "ask_inflation_from_first_cents": pre.get("ask_inflation_from_first_cents", ""),
            "stale9": int(prevalidation_delay is not None and prevalidation_delay >= 9.0),
            "initial_state": initial_state(timing),
            "coverage_failed_regen": coverage["failed_regen"],
            "coverage_crest": coverage["crest"],
            "coverage_borders": coverage["borders"],
            "coverage_hand": coverage["hand"],
            "coverage_war": coverage["war"],
            "coverage_source_count": sum(coverage.values()),
            "same_hard_release_source": same.get("source", "") if same else "",
            "same_hard_release_ts": same.get("timestamp", "") if same else "",
            "same_hard_release_delay_sec": round(same_delay, 3) if same_delay is not None else "",
            "same_hard_release_detail": same.get("detail", "") if same else "",
            "opposite_hard_release_source": opposite.get("source", "") if opposite else "",
            "opposite_hard_release_ts": opposite.get("timestamp", "") if opposite else "",
            "opposite_hard_release_delay_sec": round(opp_delay, 3) if opp_delay is not None else "",
            "opposite_hard_release_detail": opposite.get("detail", "") if opposite else "",
            "hard_release_order": order,
            "same_hard_release_within_9s": int(same_delay is not None and same_delay <= 9.0),
            "same_hard_release_within_30s": int(same_delay is not None and same_delay <= 30.0),
            "opposite_hard_release_within_9s": int(opp_delay is not None and opp_delay <= 9.0),
            "opposite_hard_release_within_30s": int(opp_delay is not None and opp_delay <= 30.0),
        }
        out.append(row)

    return out


def summarize(rows: List[dict], run_label: str, group_type: str, key: str) -> List[dict]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        groups[str(r.get(key) if r.get(key) not in ("", None) else "(blank)")].append(r)

    out = []
    for value, items in sorted(groups.items()):
        pnls = [fnum(x.get("actual_pnl")) for x in items]
        pnls = [x for x in pnls if x is not None]
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
            "avg_prevalidation_delay_sec": round(mean(delays), 3) if delays else "",
            "avg_reprice_from_first_cents": round(mean(reprices), 3) if reprices else "",
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


def make_report(rows: List[dict], dupes: List[str], path: Path) -> None:
    stale = [r for r in rows if str(r.get("stale9")) == "1" or r.get("stale9") == 1]
    stale_pull = [r for r in stale if r.get("initial_state") == "PULLBACK_WAIT"]

    lines = [
        "# Entry Authority Router V3 — Hard Release Replay",
        "",
        "Hard release is intentionally stricter than local arc continuation.",
        "",
        "Counted evidence:",
        "- Failed-Regen CONFIRMED_RELEASE",
        "- Crest RELEASE_CONFIRMED",
        "- directional BOUNDARY_RELEASE",
        "- true Hand authority transfer",
        "- War Council ACT_IMMEDIATELY / ACT_FIRST_VALID",
        "",
        "Missing telemetry is UNKNOWN, not negative evidence.",
        "",
        f"All entries: {len(rows)}",
        f"Stale >=9s entries: {len(stale)}",
        f"Stale >=9s PULLBACK_WAIT entries: {len(stale_pull)}",
        "",
    ]

    if dupes:
        lines += ["## Duplicate archives skipped", ""]
        lines += [f"- {d}" for d in dupes]
        lines.append("")

    def emit(title: str, sample: List[dict], key: str):
        groups = defaultdict(list)
        for r in sample:
            groups[str(r.get(key) if r.get(key) not in ("", None) else "(blank)")].append(r)
        lines.extend([f"## {title}", ""])
        for val, items in sorted(groups.items()):
            pnl = sum(fnum(x.get("actual_pnl")) or 0.0 for x in items)
            known = [x for x in items if x.get("settlement_correct") not in ("", None)]
            correct = sum(int(x.get("settlement_correct") or 0) for x in known)
            lines.append(
                f"- {val}: N={len(items)} P&L={money(pnl)} settlement={correct}/{len(known)}"
            )
        lines.append("")

    emit("Stale >=9s: hard release order", stale, "hard_release_order")
    emit("Stale >=9s PULLBACK_WAIT: hard release order", stale_pull, "hard_release_order")
    emit("Stale >=9s PULLBACK_WAIT: first same hard release source", stale_pull, "same_hard_release_source")
    emit("Stale >=9s PULLBACK_WAIT: same hard release within 30s", stale_pull, "same_hard_release_within_30s")
    emit("Coverage source count", rows, "coverage_source_count")

    lines += [
        "## Interpretation discipline",
        "",
        "- A local EMA arc resuming in the same direction is not counted as authority transfer.",
        "- A hard release after the historical entry is counterfactual evidence that waiting may have had a structural endpoint.",
        "- This still does not simulate fill price or management after waiting.",
        "- Runs with partial telemetry must not be treated as if absent events were disproven.",
        "- No V3 result changes V9.5A authority.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dirs", nargs="*", default=DEFAULT_RUNS)
    ap.add_argument("--out-dir", default="analysis/router_v3_hard_release_replay")
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

        cov = {}
        for name in ("failed_regen", "crest", "borders", "hand", "war"):
            cov[name] = int(bool(read_csv(run_dir / FILES[name])))
        print(f"{run_dir.name}: {len(rows)} entries | coverage={cov}")

    write_csv(out_dir / "router_v3_hard_release_features.csv", all_rows, OUT_FIELDS)

    groupings = [
        ("hard_release_order", "hard_release_order"),
        ("initial_state", "initial_state"),
        ("same_hard_source", "same_hard_release_source"),
        ("same_hard_30s", "same_hard_release_within_30s"),
        ("coverage_count", "coverage_source_count"),
    ]
    summaries: List[dict] = []
    for label in sorted(set(r["run_label"] for r in all_rows)):
        rr = [r for r in all_rows if r["run_label"] == label]
        stale = [r for r in rr if r.get("stale9") == 1]
        stale_pull = [r for r in stale if r.get("initial_state") == "PULLBACK_WAIT"]
        for group_type, key in groupings:
            summaries += summarize(stale, label + ":STALE9", group_type, key)
            summaries += summarize(stale_pull, label + ":STALE9_PULLBACK", group_type, key)

    stale_all = [r for r in all_rows if r.get("stale9") == 1]
    stale_pull_all = [r for r in stale_all if r.get("initial_state") == "PULLBACK_WAIT"]
    for group_type, key in groupings:
        summaries += summarize(stale_all, "ALL_RUNS:STALE9", group_type, key)
        summaries += summarize(stale_pull_all, "ALL_RUNS:STALE9_PULLBACK", group_type, key)

    write_csv(out_dir / "router_v3_hard_release_summary.csv", summaries, SUMMARY_FIELDS)
    make_report(all_rows, dupes, out_dir / "router_v3_hard_release_report.md")

    print()
    print(f"WROTE {out_dir / 'router_v3_hard_release_features.csv'}")
    print(f"WROTE {out_dir / 'router_v3_hard_release_summary.csv'}")
    print(f"WROTE {out_dir / 'router_v3_hard_release_report.md'}")


if __name__ == "__main__":
    main()
