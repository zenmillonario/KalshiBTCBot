from __future__ import annotations

import csv
import math
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import List, Optional

RUN_DIR = Path("runs/2026-09-20_v9_5a_rs1_entry_authority_router_shadow_01")
TRADE_JOIN = Path("analysis/rs1_prospective_01/rs1_trade_join.csv")
PAPER = RUN_DIR / "tachys_paper_trades_v9_2_6.csv"
ARCS = RUN_DIR / "tachys_ema_arcs_v9_4i.csv"
ORBIT = RUN_DIR / "tachys_ema_orbital_clock_v9_4i.csv"

OUT_DIR = Path("analysis/rs1_chess_manager_01")
OUT_CSV = OUT_DIR / "rs1_chess_trade_features.csv"
OUT_REPORT = OUT_DIR / "rs1_chess_manager_report.md"

WATCHED = "KXBTC15M-26SEP200315-15"


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


def ts(v: str, local_et: bool = False) -> Optional[float]:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if d.tzinfo is None:
            from zoneinfo import ZoneInfo
            d = d.replace(tzinfo=ZoneInfo("America/New_York") if local_et else timezone.utc)
        return d.timestamp()
    except Exception:
        return None


def side_dir(side: str) -> str:
    return "UP" if str(side).upper() == "YES" else "DOWN"


def categorical_support(side: str, value) -> str:
    if value in (None, ""):
        return ""
    v = str(value).upper()
    yes_tokens = ("UP", "YES", "BULL", "LONG", "ABOVE")
    no_tokens = ("DOWN", "NO", "BEAR", "SHORT", "BELOW")
    if any(t in v for t in yes_tokens):
        return "1" if side_dir(side) == "UP" else "0"
    if any(t in v for t in no_tokens):
        return "1" if side_dir(side) == "DOWN" else "0"
    return ""


def signed_support(side: str, value) -> str:
    x = fnum(value)
    if x is None or x == 0:
        return ""
    return "1" if ((x > 0) == (side_dir(side) == "UP")) else "0"


def pair_exit_times(paper: List[dict], trades: List[dict]) -> dict:
    exits = defaultdict(list)
    for r in paper:
        if r.get("event") != "EXIT":
            continue
        key = (str(r.get("trade_id") or ""), str(r.get("ticker") or ""), str(r.get("side") or ""))
        x = ts(r.get("timestamp", ""), local_et=True)
        if x is not None:
            exits[key].append((x, r))
    for vals in exits.values():
        vals.sort(key=lambda z: z[0])

    out = {}
    for tr in trades:
        key = (str(tr.get("trade_id") or ""), str(tr.get("ticker") or ""), str(tr.get("side") or ""))
        et = ts(tr.get("entry_ts", ""), local_et=True)
        if et is None:
            continue
        for xt, xr in exits.get(key, []):
            if xt >= et:
                out[key] = (xt, xr)
                break
    return out


def orbit_index(rows: List[dict]):
    items = []
    for r in rows:
        x = ts(r.get("timestamp", ""), local_et=False)
        if x is not None:
            items.append((x, r))
    items.sort(key=lambda z: z[0])
    return [x[0] for x in items], [x[1] for x in items]


def nearest_orbit(times, rows, target: Optional[float], max_delta: float = 3.0) -> Optional[dict]:
    if target is None or not times:
        return None
    i = bisect_left(times, target)
    candidates = []
    if i < len(times):
        candidates.append((abs(times[i] - target), rows[i]))
    if i > 0:
        candidates.append((abs(times[i-1] - target), rows[i-1]))
    if not candidates:
        return None
    d, r = min(candidates, key=lambda z: z[0])
    return r if d <= max_delta else None


def quadrant(r: dict) -> str:
    correct = str(r.get("settlement_correct") or "")
    pnl = fnum(r.get("actual_pnl")) or 0.0
    if correct == "1" and pnl > 0:
        return "RIGHT_SIDE_WIN"
    if correct == "1" and pnl < 0:
        return "RIGHT_SIDE_LOSS"
    if correct == "0" and pnl > 0:
        return "WRONG_SIDE_WIN"
    if correct == "0" and pnl < 0:
        return "WRONG_SIDE_LOSS"
    return "FLAT_OR_UNKNOWN"


def median_text(rows: List[dict], key: str, digits: int = 3) -> str:
    vals = [fnum(r.get(key)) for r in rows]
    vals = [x for x in vals if x is not None]
    return "n/a" if not vals else f"{median(vals):.{digits}f}"


def pct_count(rows: List[dict], key: str, wanted: str = "1") -> str:
    known = [r for r in rows if str(r.get(key) or "") in ("0", "1")]
    yes = sum(1 for r in known if str(r.get(key)) == wanted)
    return f"{yes}/{len(known)}"


def write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in rows for k in r}) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def summarize(rows: List[dict], label: str) -> str:
    pnl = sum(fnum(r.get("actual_pnl")) or 0.0 for r in rows)
    return (
        f"- {label}: N={len(rows)} PnL=${pnl:+.2f} "
        f"arcAligned={pct_count(rows,'arc_aligned')} "
        f"gapSupportExit={pct_count(rows,'gap_support_exit')} "
        f"velSupportExit={pct_count(rows,'gap_velocity_support_exit')} "
        f"microSupportExit={pct_count(rows,'micro_support_exit')} "
        f"macroSupportExit={pct_count(rows,'macro_support_exit')} "
        f"medianArcProgress={median_text(rows,'arc_progress_at_entry')}"
    )


def main() -> None:
    trades = read_csv(TRADE_JOIN)
    paper = read_csv(PAPER)
    arcs = read_csv(ARCS)
    orbit = read_csv(ORBIT)

    arc_by_id = {str(r.get("arc_id") or ""): r for r in arcs if r.get("arc_id")}
    exit_map = pair_exit_times(paper, trades)
    otimes, orows = orbit_index(orbit)

    out = []
    for tr in trades:
        side = str(tr.get("side") or "")
        key = (str(tr.get("trade_id") or ""), str(tr.get("ticker") or ""), side)
        entry_t = ts(tr.get("entry_ts", ""), local_et=True)
        exit_pair = exit_map.get(key)
        exit_t = exit_pair[0] if exit_pair else None
        exit_row = exit_pair[1] if exit_pair else {}

        arc = arc_by_id.get(str(tr.get("proposal_arc_id") or ""), {})
        arc_duration = fnum(arc.get("duration_sec"))
        arc_age = fnum(tr.get("proposal_arc_age_sec"))
        progress = (arc_age / arc_duration) if arc_age is not None and arc_duration and arc_duration > 0 else None

        arc_end = ts(arc.get("end_time", ""), local_et=False)
        arc_remaining_exit = (arc_end - exit_t) if arc_end is not None and exit_t is not None else None
        exit_before_arc_end = ""
        if arc_end is not None and exit_t is not None:
            exit_before_arc_end = "1" if exit_t < arc_end else "0"

        oe = nearest_orbit(otimes, orows, entry_t)
        ox = nearest_orbit(otimes, orows, exit_t)
        o6 = nearest_orbit(otimes, orows, exit_t + 6.0 if exit_t is not None else None)
        o9 = nearest_orbit(otimes, orows, exit_t + 9.0 if exit_t is not None else None)

        row = dict(tr)
        row.update({
            "quadrant": quadrant(tr),
            "exit_ts": exit_row.get("timestamp", ""),
            "arc_completed_direction": arc.get("direction", ""),
            "arc_duration_sec": arc_duration,
            "arc_progress_at_entry": progress,
            "arc_remaining_sec_at_exit": arc_remaining_exit,
            "exit_before_arc_end": exit_before_arc_end,
            "arc_sequence_id": arc.get("sequence_id", ""),
            "arc_sequence_count": arc.get("sequence_count", ""),
            "arc_amplitude": arc.get("amplitude", ""),
            "arc_amplitude_ratio": arc.get("amplitude_ratio", ""),
            "arc_crest_progression": arc.get("crest_progression", ""),
            "arc_parent_direction": arc.get("parent_direction", ""),
            "arc_parent_maturity": arc.get("parent_maturity", ""),
            "arc_local_regime": arc.get("local_regime", ""),
            "arc_target_relation_extreme": arc.get("target_relation_at_extreme", ""),
            "arc_target_distance_extreme": arc.get("target_distance_at_extreme", ""),
            "arc_aligned": categorical_support(side, arc.get("direction")),
        })

        for prefix, sample in (("entry", oe), ("exit", ox), ("exit6", o6), ("exit9", o9)):
            sample = sample or {}
            row[f"orbit_gap_{prefix}"] = sample.get("gap", "")
            row[f"orbit_gap_velocity_{prefix}"] = sample.get("gap_velocity", "")
            row[f"orbit_phase_deg_{prefix}"] = sample.get("phase_deg", "")
            row[f"orbit_micro_side_{prefix}"] = sample.get("micro_side", "")
            row[f"orbit_macro_side_{prefix}"] = sample.get("macro_side", "")
            row[f"orbit_tactical_state_{prefix}"] = sample.get("tactical_cycle_state", "")
            row[f"orbit_campaign_state_{prefix}"] = sample.get("campaign_cycle_state", "")
            row[f"orbit_churn_{prefix}"] = sample.get("churn_type", "")
            row[f"orbit_hand_{prefix}"] = sample.get("hand_authority", "")
            row[f"gap_support_{prefix}"] = signed_support(side, sample.get("gap"))
            row[f"gap_velocity_support_{prefix}"] = signed_support(side, sample.get("gap_velocity"))
            row[f"micro_support_{prefix}"] = categorical_support(side, sample.get("micro_side"))
            row[f"macro_support_{prefix}"] = categorical_support(side, sample.get("macro_side"))

        out.append(row)

    groups = defaultdict(list)
    for r in out:
        groups[r["quadrant"]].append(r)

    right_loss = groups["RIGHT_SIDE_LOSS"]
    wrong_loss = groups["WRONG_SIDE_LOSS"]

    lines = [
        "# RS1 Chess / Arc Manager Forensics",
        "",
        "This pass uses existing completed-arc and Orbital Clock telemetry. It adds no detector and changes no authority.",
        "",
        "## Four-way outcome split",
        "",
    ]
    for label in ("RIGHT_SIDE_WIN","RIGHT_SIDE_LOSS","WRONG_SIDE_WIN","WRONG_SIDE_LOSS","FLAT_OR_UNKNOWN"):
        if groups[label]:
            lines.append(summarize(groups[label], label))

    lines += [
        "",
        "## Manager question: correct side, losing exit",
        "",
        f"- Correct-side losing trades: {len(right_loss)}",
        f"- EMA gap still supported trade side at exit: {pct_count(right_loss,'gap_support_exit')}",
        f"- EMA gap velocity still supported trade side at exit: {pct_count(right_loss,'gap_velocity_support_exit')}",
        f"- Micro side still supported trade at exit: {pct_count(right_loss,'micro_support_exit')}",
        f"- Macro side still supported trade at exit: {pct_count(right_loss,'macro_support_exit')}",
        f"- Gap supported trade again 6s after exit: {pct_count(right_loss,'gap_support_exit6')}",
        f"- Gap supported trade again 9s after exit: {pct_count(right_loss,'gap_support_exit9')}",
        f"- Exit occurred before proposal arc completed: {pct_count(right_loss,'exit_before_arc_end')}",
        "",
        "### Correct-side losers by exit reason",
        "",
    ]
    by_reason = defaultdict(list)
    for r in right_loss:
        by_reason[str(r.get("exit_reason") or "(blank)")].append(r)
    for reason, rows in sorted(by_reason.items(), key=lambda z: (-len(z[1]), z[0])):
        lines.append(summarize(rows, reason))

    lines += [
        "",
        "## Comparison: genuinely wrong-side losing trades",
        "",
        f"- Wrong-side losing trades: {len(wrong_loss)}",
        f"- EMA gap still supported chosen trade side at exit: {pct_count(wrong_loss,'gap_support_exit')}",
        f"- EMA gap velocity still supported chosen trade side at exit: {pct_count(wrong_loss,'gap_velocity_support_exit')}",
        f"- Micro side still supported chosen trade at exit: {pct_count(wrong_loss,'micro_support_exit')}",
        f"- Macro side still supported chosen trade at exit: {pct_count(wrong_loss,'macro_support_exit')}",
        f"- Gap supported chosen side again 6s after exit: {pct_count(wrong_loss,'gap_support_exit6')}",
        f"- Gap supported chosen side again 9s after exit: {pct_count(wrong_loss,'gap_support_exit9')}",
        f"- Exit occurred before proposal arc completed: {pct_count(wrong_loss,'exit_before_arc_end')}",
        "",
        "## Existing little-mountain proxy at entry",
        "",
    ]

    for label, rows in (("RIGHT_SIDE_WIN", groups["RIGHT_SIDE_WIN"]),
                        ("RIGHT_SIDE_LOSS", right_loss),
                        ("WRONG_SIDE_WIN", groups["WRONG_SIDE_WIN"]),
                        ("WRONG_SIDE_LOSS", wrong_loss)):
        if not rows:
            continue
        seq = Counter()
        crest = Counter()
        for r in rows:
            c = fnum(r.get("arc_sequence_count"))
            if c is None:
                seq["UNKNOWN"] += 1
            elif c >= 4:
                seq["4+"] += 1
            else:
                seq[str(int(c))] += 1
            crest[str(r.get("arc_crest_progression") or "NONE")] += 1
        lines.append(f"- {label}: seq=" + ", ".join(f"{k}:{v}" for k,v in sorted(seq.items())) +
                     " | crest=" + ", ".join(f"{k}:{v}" for k,v in crest.most_common()))

    lines += [
        "",
        "## Twelve correct-side losers",
        "",
    ]
    for r in right_loss:
        lines.append(
            f"- #{r.get('trade_id')} {r.get('ticker')} {r.get('side')} @{r.get('entry_ask')} "
            f"exit={r.get('exit_reason')} pnl=${(fnum(r.get('actual_pnl')) or 0):+.2f} "
            f"arc={r.get('proposal_arc_id')} dir={r.get('arc_completed_direction')} "
            f"seq={r.get('arc_sequence_count')} crest={r.get('arc_crest_progression')} "
            f"progress={r.get('arc_progress_at_entry')} "
            f"gapExit={r.get('gap_support_exit')} velExit={r.get('gap_velocity_support_exit')} "
            f"microExit={r.get('micro_support_exit')} macroExit={r.get('macro_support_exit')} "
            f"gap6={r.get('gap_support_exit6')} gap9={r.get('gap_support_exit9')} "
            f"beforeArcEnd={r.get('exit_before_arc_end')}"
        )

    watched = [r for r in out if r.get("ticker") == WATCHED]
    lines += [
        "",
        f"## Watched compression contract {WATCHED}",
        "",
    ]
    for r in watched:
        lines.append(
            f"- #{r.get('trade_id')} {r.get('side')} outcome={r.get('quadrant')} "
            f"arc={r.get('proposal_arc_id')} arcDir={r.get('arc_completed_direction')} "
            f"seq={r.get('arc_sequence_count')} crest={r.get('arc_crest_progression')} "
            f"arcProgress={r.get('arc_progress_at_entry')} exit={r.get('exit_reason')} "
            f"gapExit={r.get('gap_support_exit')} velExit={r.get('gap_velocity_support_exit')} "
            f"microExit={r.get('micro_support_exit')} macroExit={r.get('macro_support_exit')}"
        )

    lines += [
        "",
        "## Discipline",
        "",
        "- Sequence count and crest progression are existing telemetry, used as the machine proxy for the little mountains.",
        "- Gap/velocity/micro/macro support are descriptive joins from the existing Orbital Clock; no new threshold is introduced.",
        "- The +6s and +9s samples are post-exit diagnostics only, not proposed hold rules.",
        "- Settlement correctness is not the same thing as trade quality; profitable wrong-side exits are preserved as their own class.",
        "- The target question is whether current managers can distinguish ordinary snake counter-motion from a genuine structural escape.",
        "",
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUT_CSV, out)
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"trades={len(out)}")
    print(
        "quadrants "
        + " ".join(f"{k}={len(groups[k])}" for k in
                   ("RIGHT_SIDE_WIN","RIGHT_SIDE_LOSS","WRONG_SIDE_WIN","WRONG_SIDE_LOSS","FLAT_OR_UNKNOWN"))
    )
    print(f"WROTE {OUT_CSV}")
    print(f"WROTE {OUT_REPORT}")


if __name__ == "__main__":
    main()
