from __future__ import annotations

import csv
import math
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import List, Optional
from zoneinfo import ZoneInfo

RUN_DIR = Path("runs/2026-09-20_v9_5a_rs1_entry_authority_router_shadow_01")
PERSIST = Path("analysis/rs1_battlefield_persistence_01/rs1_battlefield_persistence.csv")
ROUTER = RUN_DIR / "tachys_entry_authority_router_shadow_v9_5a_rs1.csv"
ARCS = RUN_DIR / "tachys_ema_arcs_v9_4i.csv"
ORBIT = RUN_DIR / "tachys_ema_orbital_clock_v9_4i.csv"

OUT_DIR = Path("analysis/rs1_reacquisition_signature_01")
OUT_CSV = OUT_DIR / "rs1_reacquisition_signature.csv"
OUT_REPORT = OUT_DIR / "rs1_reacquisition_signature_report.md"

ET = ZoneInfo("America/New_York")


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


def to_ts(v: str, local_et: bool = False) -> Optional[float]:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=ET if local_et else timezone.utc)
        return d.timestamp()
    except Exception:
        return None


def aligned_side(side: str, value) -> str:
    if value in (None, ""):
        return ""
    s = str(side or "").upper()
    v = str(value or "").upper()
    if v in ("YES", "UP", "BULL", "LONG", "ABOVE"):
        return "1" if s == "YES" else "0"
    if v in ("NO", "DOWN", "BEAR", "SHORT", "BELOW"):
        return "1" if s == "NO" else "0"
    if v.startswith("UP_"):
        return "1" if s == "YES" else "0"
    if v.startswith("DOWN_"):
        return "1" if s == "NO" else "0"
    return ""


def signed_support(side: str, value) -> str:
    x = fnum(value)
    if x is None or x == 0:
        return ""
    return "1" if ((x > 0 and str(side).upper() == "YES") or (x < 0 and str(side).upper() == "NO")) else "0"


def target_support(side: str, target_distance) -> str:
    x = fnum(target_distance)
    if x is None or x == 0:
        return ""
    return "1" if ((x > 0 and str(side).upper() == "YES") or (x < 0 and str(side).upper() == "NO")) else "0"


def build_time_index(rows: List[dict], field: str, local_et: bool = False):
    items = []
    for r in rows:
        x = to_ts(r.get(field, ""), local_et=local_et)
        if x is not None:
            rr = dict(r)
            rr["_ts"] = x
            items.append(rr)
    items.sort(key=lambda r: r["_ts"])
    return [r["_ts"] for r in items], items


def nearest(times, rows, target: Optional[float], max_delta: float = 3.0) -> Optional[dict]:
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


def find_matching_proposal(router_rows: List[dict], ticker: str, side: str, target_ts: float, arc_id: str) -> Optional[dict]:
    candidates = []
    for r in router_rows:
        if str(r.get("event") or "") != "LEGACY_PROPOSAL_SHADOW":
            continue
        if str(r.get("ticker") or "") != ticker or str(r.get("side") or "") != side:
            continue
        rt = to_ts(r.get("timestamp", ""), local_et=False)
        if rt is None:
            continue
        score = abs(rt - target_ts)
        if arc_id and str(r.get("arc_id") or "") == arc_id:
            score -= 0.25
        candidates.append((score, abs(rt - target_ts), r))
    if not candidates:
        return None
    candidates.sort(key=lambda z: z[0])
    _, delta, row = candidates[0]
    return row if delta <= 2.5 else None


def median_field(rows: List[dict], field: str, digits: int = 2) -> str:
    vals = [fnum(r.get(field)) for r in rows]
    vals = [x for x in vals if x is not None]
    return "n/a" if not vals else f"{median(vals):.{digits}f}"


def bool_count(rows: List[dict], field: str) -> str:
    known = [r for r in rows if str(r.get(field) or "") in ("0", "1")]
    yes = sum(1 for r in known if str(r.get(field)) == "1")
    return f"{yes}/{len(known)}"


def categorical(rows: List[dict], field: str) -> str:
    c = Counter(str(r.get(field) or "UNKNOWN") for r in rows)
    return ", ".join(f"{k}={v}" for k, v in c.most_common())


def write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in rows for k in r}) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    persist = read_csv(PERSIST)
    router = read_csv(ROUTER)
    arcs = read_csv(ARCS)
    orbit = read_csv(ORBIT)

    arc_by_id = {str(r.get("arc_id") or ""): r for r in arcs if r.get("arc_id")}
    otimes, orows = build_time_index(orbit, "timestamp", local_et=False)

    out = []
    for p in persist:
        if str(p.get("same_side_proposal_after_exit") or "") != "1":
            continue

        ticker = str(p.get("ticker") or "")
        side = str(p.get("side") or "")
        exit_t = to_ts(p.get("exit_ts", ""), local_et=True)
        delay = fnum(p.get("same_side_proposal_delay_sec"))
        if exit_t is None or delay is None:
            continue
        target_t = exit_t + delay
        arc_id = str(p.get("same_side_proposal_arc_id") or "")

        proposal = find_matching_proposal(router, ticker, side, target_t, arc_id)
        if not proposal:
            continue

        prop_t = to_ts(proposal.get("timestamp", ""), local_et=False)
        orbit_row = nearest(otimes, orows, prop_t)
        arc = arc_by_id.get(str(proposal.get("arc_id") or ""), {})

        row = {
            "trade_id": p.get("trade_id", ""),
            "ticker": ticker,
            "side": side,
            "label_parent_settlement_correct": p.get("settlement_correct", ""),
            "label_parent_outcome_class": p.get("outcome_class", ""),
            "new_arc": p.get("same_side_proposal_new_arc", ""),
            "proposal_ts": proposal.get("timestamp", ""),
            "proposal_ask": proposal.get("proposal_ask", ""),
            "proposal_delay_sec": p.get("same_side_proposal_delay_sec", ""),
            "recognition_age_sec": proposal.get("recognition_age_sec", ""),
            "expired9": proposal.get("expired9", ""),
            "prior_state": proposal.get("prior_state", ""),
            "proposal_strategy": proposal.get("proposal_strategy", ""),
            "proposal_trade_intent": proposal.get("proposal_trade_intent", ""),
            "proposal_signal_grade": proposal.get("proposal_signal_grade", ""),
            "proposal_setup_grade": proposal.get("proposal_setup_grade", ""),
            "price_arc_phase": proposal.get("price_arc_phase", ""),
            "arc_id": proposal.get("arc_id", ""),
            "arc_direction": proposal.get("arc_direction", ""),
            "arc_direction_aligned": aligned_side(side, proposal.get("arc_direction")),
            "arc_age_sec": proposal.get("arc_age_sec", ""),
            "remaining_capacity": proposal.get("remaining_capacity", ""),
            "battlefield_class": proposal.get("battlefield_class", ""),
            "zoom_mode": proposal.get("zoom_mode", ""),
            "boss_side": proposal.get("boss_side", ""),
            "boss_aligned": aligned_side(side, proposal.get("boss_side")),
            "hand_side": proposal.get("hand_side", ""),
            "hand_aligned": aligned_side(side, proposal.get("hand_side")),
            "territory_state": proposal.get("territory_state", ""),
            "churn_type": proposal.get("churn_type", ""),
            "cage_state": proposal.get("cage_state", ""),
            "dragon_state": proposal.get("dragon_state", ""),
            "seconds_left": proposal.get("seconds_left", ""),
            "target_distance": proposal.get("target_distance", ""),
            "target_support": target_support(side, proposal.get("target_distance")),
            "active_same_side_position": proposal.get("active_same_side_position", ""),
            "active_opposite_position": proposal.get("active_opposite_position", ""),
            "arc_sequence_id": arc.get("sequence_id", ""),
            "arc_sequence_count": arc.get("sequence_count", ""),
            "arc_crest_progression": arc.get("crest_progression", ""),
            "arc_amplitude_ratio": arc.get("amplitude_ratio", ""),
            "arc_parent_direction": arc.get("parent_direction", ""),
            "arc_parent_maturity": arc.get("parent_maturity", ""),
            "arc_local_regime": arc.get("local_regime", ""),
            "orbit_gap": (orbit_row or {}).get("gap", ""),
            "orbit_gap_support": signed_support(side, (orbit_row or {}).get("gap")),
            "orbit_gap_velocity": (orbit_row or {}).get("gap_velocity", ""),
            "orbit_velocity_support": signed_support(side, (orbit_row or {}).get("gap_velocity")),
            "orbit_phase_deg": (orbit_row or {}).get("phase_deg", ""),
            "orbit_micro_side": (orbit_row or {}).get("micro_side", ""),
            "orbit_micro_aligned": aligned_side(side, (orbit_row or {}).get("micro_side")),
            "orbit_macro_side": (orbit_row or {}).get("macro_side", ""),
            "orbit_macro_aligned": aligned_side(side, (orbit_row or {}).get("macro_side")),
            "orbit_tactical_state": (orbit_row or {}).get("tactical_cycle_state", ""),
            "orbit_campaign_state": (orbit_row or {}).get("campaign_cycle_state", ""),
            "first_post_exit_proposal_relation": p.get("first_post_exit_proposal_relation", ""),
            "proposal_cheaper_than_original": p.get("same_side_proposal_cheaper_than_original", ""),
            "proposal_improvement_cents": p.get("same_side_proposal_improvement_cents", ""),
            "actual_same_side_reentry": p.get("same_side_reentry", ""),
            "actual_reentry_trade_id": p.get("same_side_reentry_trade_id", ""),
            "actual_reentry_settlement_correct": p.get("same_side_reentry_outcome_correct", ""),
        }
        out.append(row)

    new_arc = [r for r in out if str(r.get("new_arc") or "") == "1"]
    correct = [r for r in new_arc if str(r.get("label_parent_settlement_correct") or "") == "1"]
    wrong = [r for r in new_arc if str(r.get("label_parent_settlement_correct") or "") == "0"]

    lines = [
        "# RS1 Reacquisition Signature Forensics",
        "",
        "This pass compares contemporaneous features at the moment a same-side proposal reappeared after a losing exit. Settlement correctness is used only as an outcome label and is not available prospectively.",
        "",
        f"- Same-side post-exit proposals matched: {len(out)}",
        f"- New-arc proposals: {len(new_arc)}",
        f"- New-arc outcome labels: eventually-correct thesis={len(correct)} eventually-wrong thesis={len(wrong)}",
        "",
        "## New-arc contemporaneous comparison",
        "",
        f"- Eventually-correct thesis: N={len(correct)} askMedian={median_field(correct,'proposal_ask')} arcAgeMedian={median_field(correct,'arc_age_sec',1)}s secondsLeftMedian={median_field(correct,'seconds_left',1)}s",
        f"- Eventually-wrong thesis: N={len(wrong)} askMedian={median_field(wrong,'proposal_ask')} arcAgeMedian={median_field(wrong,'arc_age_sec',1)}s secondsLeftMedian={median_field(wrong,'seconds_left',1)}s",
        f"- Arc direction aligned: correct {bool_count(correct,'arc_direction_aligned')} | wrong {bool_count(wrong,'arc_direction_aligned')}",
        f"- Target already supports side: correct {bool_count(correct,'target_support')} | wrong {bool_count(wrong,'target_support')}",
        f"- Hand aligned: correct {bool_count(correct,'hand_aligned')} | wrong {bool_count(wrong,'hand_aligned')}",
        f"- Boss aligned: correct {bool_count(correct,'boss_aligned')} | wrong {bool_count(wrong,'boss_aligned')}",
        f"- EMA gap supports side: correct {bool_count(correct,'orbit_gap_support')} | wrong {bool_count(wrong,'orbit_gap_support')}",
        f"- EMA gap velocity supports side: correct {bool_count(correct,'orbit_velocity_support')} | wrong {bool_count(wrong,'orbit_velocity_support')}",
        f"- Orbital micro side aligned: correct {bool_count(correct,'orbit_micro_aligned')} | wrong {bool_count(wrong,'orbit_micro_aligned')}",
        f"- Orbital macro side aligned: correct {bool_count(correct,'orbit_macro_aligned')} | wrong {bool_count(wrong,'orbit_macro_aligned')}",
        "",
        "### Existing categorical telemetry",
        "",
        f"- Crest progression, correct: {categorical(correct,'arc_crest_progression')}",
        f"- Crest progression, wrong: {categorical(wrong,'arc_crest_progression')}",
        f"- Sequence count, correct: {categorical(correct,'arc_sequence_count')}",
        f"- Sequence count, wrong: {categorical(wrong,'arc_sequence_count')}",
        f"- Battlefield, correct: {categorical(correct,'battlefield_class')}",
        f"- Battlefield, wrong: {categorical(wrong,'battlefield_class')}",
        f"- Churn, correct: {categorical(correct,'churn_type')}",
        f"- Churn, wrong: {categorical(wrong,'churn_type')}",
        f"- Dragon, correct: {categorical(correct,'dragon_state')}",
        f"- Dragon, wrong: {categorical(wrong,'dragon_state')}",
        f"- Price arc phase, correct: {categorical(correct,'price_arc_phase')}",
        f"- Price arc phase, wrong: {categorical(wrong,'price_arc_phase')}",
        "",
        "## New-arc proposal detail",
        "",
    ]

    for r in new_arc:
        lines.append(
            f"- parent #{r['trade_id']} {r['side']} labelCorrect={r['label_parent_settlement_correct']} "
            f"ask={r['proposal_ask']} arc={r['arc_id']} dir={r['arc_direction']} "
            f"seq={r['arc_sequence_count']} crest={r['arc_crest_progression']} "
            f"phase={r['price_arc_phase']} battle={r['battlefield_class']} churn={r['churn_type']} "
            f"dragon={r['dragon_state']} targetSupport={r['target_support']} "
            f"handAligned={r['hand_aligned']} bossAligned={r['boss_aligned']} "
            f"gapSupport={r['orbit_gap_support']} velSupport={r['orbit_velocity_support']} "
            f"microAligned={r['orbit_micro_aligned']} macroAligned={r['orbit_macro_aligned']} "
            f"arcAge={r['arc_age_sec']}s left={r['seconds_left']}s"
        )

    lines += [
        "",
        "## Discipline",
        "",
        "- The outcome label is hindsight and must never become a prospective input.",
        "- No score, threshold, or entry rule is fitted from this tiny RS1 sample.",
        "- The goal is to identify which already-existing battlefield fields deserve prospective logging around a dead-position / live-thesis reacquisition state.",
        "- A new arc alone is explicitly insufficient because wrong theses also regenerated onto new arcs.",
        "- V9.5A remains the frozen paper authority baseline.",
        "",
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUT_CSV, out)
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"same-side proposals={len(out)} new-arc={len(new_arc)} correct-label={len(correct)} wrong-label={len(wrong)}")
    print(f"WROTE {OUT_CSV}")
    print(f"WROTE {OUT_REPORT}")


if __name__ == "__main__":
    main()
