"""Offline raw-price arc acceptance through the actual Tool Rack PAPER engine.

Expected zones are authored before observing engine output. No detector,
mission, proposal, Commander or ledger replacement is used. Inputs are
explicitly synthetic, not a replay or a claim about venue fills/profitability.
A behavioral miss returns exit code 2 and remains a failed acceptance case.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
from unittest.mock import patch

from strategy_core.paper_execution import PaperExecutioner
from strategy_core.paper_runtime import ToolRackPaperEngine
from tests.tool_rack.construct_arc_fixtures import ArcScenario, BASE, build_tape


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AccelerationScenario(ArcScenario):
    def price(self, offset):
        if offset < self.current_start:
            return super().price(offset)
        progress = (offset - self.current_start) / self.leg_seconds
        return (80000. + self.drift_per_second * offset
                + self.direction * self.amplitude * (-1. + 2. * progress + progress ** 2))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def source_hashes():
    paths = [ROOT / "CONSTRUCT_TOOL_RACK_ARCS.py", ROOT / "tests/tool_rack/construct_arc_fixtures.py"]
    paths += sorted(p for p in (ROOT / "strategy_core").rglob("*")
                    if p.is_file() and p.suffix in (".py", ".json"))
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def optional_source_git(root=ROOT):
    """Optional checkout metadata; per-file hashes identify packaged sources.

    An extracted bundle has no Git metadata and must not inherit the identity
    of an unrelated enclosing repository. Missing Git or an unavailable HEAD
    leaves this descriptive field null without affecting a finished gate.
    """
    try:
        root = Path(root).resolve()
        if not (root / ".git").exists():
            return None
        result = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root,
            capture_output=True, text=True, encoding="utf-8", timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    if (result.returncode != 0 or len(value) not in (40, 64)
            or any(character not in "0123456789abcdefABCDEF" for character in value)):
        return None
    return value


def blocked_network(*args, **kwargs):
    raise RuntimeError("CONSTRUCT_EXTERNAL_NETWORK_FORBIDDEN")


def compact(status, offset, receipts):
    physical, geometry = status["physical"], status["latest_geometry"]
    mountain, context, rack = physical.get("mountain", {}), status.get("mission_context", {}), status.get("rack", {})
    parent = context.get("parent", {})
    reference = mountain.get("reference_history", {})
    entry = next((r["decision"] for r in status["decisions"] if r["scope"] == "ENTRY"), {})
    actions = [{"tool": r.get("tool"), "side": r.get("side"), "action": r.get("action"),
                "reason": r.get("reason"), "purpose": (r.get("metadata", {}).get("mission") or {}).get("purpose")}
               for r in rack.get("intents", ())]
    reviews = []
    for raw in status.get("candidate_review", ()):
        row = {k: raw.get(k) for k in ("tool", "stage", "side", "purpose", "classification", "decision", "reason",
                                      "observed_ask", "max_price")}
        economics = raw.get("economics") or {}
        row["economics"] = {k: economics.get(k) for k in ("status", "reason", "quantity", "entry_ask",
            "required_exit_bid", "estimated_exit_bid", "gross_roi", "physical_distance", "collection_boundary_btc",
            "response_pair_count")}
        reviews.append(row)
    return {"offset": offset, "btc": geometry.get("btc_price"), "ema9": geometry.get("ema9"),
        "ema30": geometry.get("ema30"), "native_side": geometry.get("arc_direction"),
        "native_arc_id": geometry.get("arc_id"), "parent_side": parent.get("side"),
        "parent_entry_edge": parent.get("entry_edge"), "parent_terminal": parent.get("terminal"),
        "contract_thesis": context.get("contract", {}).get("thesis_side"),
        "history_status": context.get("contract", {}).get("history_status"),
        "territory": rack.get("owned_territory"), "owner": rack.get("owned_side"),
        "mountain": {k: mountain.get(k) for k in ("owner_side", "mature_edge", "stall", "hesitation",
            "terminal_evidence_qualified", "spent_edge", "strong_active_release", "entry_routes",
            "current_arc_id", "retreat_dollars", "owner_price_gap", "contact_width")},
        "references": reference, "candidate_reviews": reviews, "intents": actions,
        "entry_action": entry.get("action"), "entry_reason": entry.get("reason"),
        "entry_side": (entry.get("intent") or {}).get("side"),
        "booked": [{"status": r.status, "position_id": r.position_id,
                    "event": r.event} for r in receipts if r.event]}


def run_case(scenario, destination, control=None, step=6):
    started = time.monotonic()
    destination.mkdir(parents=True, exist_ok=False)
    expectation = scenario.expectations()
    expectation.update(control=control, decisions_every_seconds=step,
        warmup_entries_disabled=True, physical_history_is_observed_prefix=True,
        expected_no_counterfade_through_current_leg=control == "ACCELERATION",
        expected_no_entries=control == "QUIET")
    write_json(destination / "expectations.json", expectation)
    tape = build_tape(scenario)
    input_digest = hashlib.sha256(canonical({"rows": tape.rows, "history": tape.completed_bars,
                                             "scenario": asdict(scenario)})).hexdigest()
    write_json(destination / "input_identity.json", {"sha256": input_digest,
        "raw_price_count": len(tape.rows), "raw_step_seconds": 1, "scenario": asdict(scenario)})
    frames, events, reviews = [], [], Counter()
    warmup = scenario.current_start - 180
    end = (scenario.first_edge_zone[1] + 60 if control == "ACCELERATION" else scenario.end_offset)
    previous = None
    with (destination / "console.log").open("w", encoding="utf-8") as console, redirect_stdout(console):
        engine = ToolRackPaperEngine(destination / "paper_run")
        try:
            for offset in range(warmup, end + 1, step):
                feed = tape.capture(offset, previous_offset=previous, include_prefix=previous is None)
                result = engine.process(feed, now_ts=feed.observed_ts,
                    historical_candles=tape.history_at(offset), entry_window_closed=offset < scenario.current_start)
                frame = compact(result["status"], offset, result["receipts"])
                frames.append(frame)
                if offset >= scenario.current_start:
                    reviews.update([frame["entry_reason"]])
                for receipt in result["receipts"]:
                    if receipt.event:
                        event = dict(receipt.event)
                        held = engine.executor.positions.get(receipt.position_id)
                        mission = (held.entry_metadata.get("mission") or {}) if held else {}
                        events.append({"offset": offset, "event": event,
                            "purpose": mission.get("purpose"), "parent_leg_id": mission.get("parent_leg_id"),
                            "btc": frame["btc"], "ema9": frame["ema9"], "ema30": frame["ema30"],
                            "contract_thesis": frame["contract_thesis"], "parent_side": frame["parent_side"]})
                previous = offset
        finally:
            engine.close(reason="OFFLINE_SYNTHETIC_CONSTRUCT_COMPLETE")
    journal = PaperExecutioner.inspect_journal(destination / "paper_run")
    entries = [r for r in events if r["event"]["event"] == "ENTRY"]
    zones = []
    for name, side, bounds in (("PEAK", "NO", scenario.peak_zone), ("VALLEY", "YES", scenario.valley_zone)):
        window = [f for f in frames if bounds[0] <= f["offset"] <= bounds[1]]
        eligible = [e for e in entries if e["event"]["side"] == side and bounds[0] <= e["offset"] <= bounds[1]]
        opposed = [e for e in entries if e["event"]["side"] != side and bounds[0] <= e["offset"] <= bounds[1]]
        outward = "YES" if side == "NO" else "NO"
        edges = [f for f in window if f["mountain"]["mature_edge"] is True
                 and f["mountain"]["owner_side"] == outward]
        intents = [f for f in window if any(i["action"] in ("ENTER", "RELAY") and i["side"] == side for i in f["intents"])]
        accepted = [f for f in window if f["entry_action"] in ("ENTER", "RELAY") and f["entry_side"] == side]
        stop_reasons = Counter(f["entry_reason"] for f in window)
        zones.append({"name": name, "expected_side": side, "bounds": bounds,
            "applicable": control is None, "pass": bool(eligible) and not opposed if control is None else None,
            "first_detected_edge": edges[0]["offset"] if edges else None,
            "first_actionable_intent": intents[0]["offset"] if intents else None,
            "first_commander_acceptance": accepted[0]["offset"] if accepted else None,
            "correct_entries": eligible, "opposite_entries": opposed,
            "dominant_wait_reasons": stop_reasons.most_common(5)})
    middle_counter = []
    first_middle = (scenario.current_start + 120, scenario.first_edge_zone[0])
    second_middle = (scenario.first_edge_zone[1] + 120, scenario.second_edge_zone[0])
    for event in entries:
        t, side = event["offset"], event["event"]["side"]
        if ((first_middle[0] <= t < first_middle[1] and side != ("YES" if scenario.direction == 1 else "NO"))
                or (control is None and second_middle[0] <= t < second_middle[1]
                    and side != ("NO" if scenario.direction == 1 else "YES"))):
            middle_counter.append(event)
    if control == "QUIET":
        passed = not entries
    elif control == "ACCELERATION":
        passed = not any(e["event"]["side"] != ("YES" if scenario.direction == 1 else "NO") for e in entries)
    else:
        passed = all(z["pass"] for z in zones) and not middle_counter
    summary = {"name": scenario.name, "synthetic": True, "control": control,
        "acceptance": "PASS" if passed else "FAIL", "expectations": expectation,
        "input_sha256": input_digest, "decision_count": len(frames), "zones": zones,
        "entries": entries, "other_events": [e for e in events if e["event"]["event"] != "ENTRY"],
        "midleg_counter_entries": middle_counter, "dominant_entry_reasons": reviews.most_common(10),
        "unresolved_positions_at_end": len(journal["state"]["positions"]),
        "journal_seq": journal["seq"], "journal_sha256": journal["sha256"],
        "journal_verified": journal["committed_boundary"], "wall_seconds": round(time.monotonic() - started, 3),
        "settlement_or_profitability_claim": False}
    write_json(destination / "frames.json", frames)
    write_json(destination / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", default="level,rising,mirrored,acceleration,quiet,quote400,quote350_floor005")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    scenarios = {"level": (ArcScenario(name="level"), None),
        "rising": (ArcScenario(name="rising", drift_per_second=.01), None),
        "mirrored": (ArcScenario(name="mirrored", direction=-1), None),
        "acceleration": (AccelerationScenario(name="acceleration"), "ACCELERATION"),
        "quiet": (ArcScenario(name="quiet", amplitude=.5, target_offset=0.), "QUIET"),
        "quote400": (ArcScenario(name="quote400", quote_scale=400.), None),
        "quote350_floor005": (ArcScenario(name="quote350_floor005", quote_scale=350.,
            midpoint_floor=.004, quote_half_spread=.001), None)}
    selected = args.cases.split(",")
    if any(name not in scenarios for name in selected):
        parser.error("Unknown case")
    before = source_hashes()
    results = []
    with patch.object(socket.socket, "connect", blocked_network), patch.object(socket, "getaddrinfo", blocked_network):
        for name in selected:
            print("RUN " + name, flush=True)
            summary = run_case(*scenarios[name][:1], args.output / name, control=scenarios[name][1])
            results.append(summary)
            print(json.dumps({"case": name, "acceptance": summary["acceptance"],
                "entries": [(e["offset"], e["event"]["side"], e["event"]["price"]) for e in summary["entries"]],
                "zones": [{k: z[k] for k in ("name", "pass", "first_detected_edge", "first_actionable_intent",
                                            "first_commander_acceptance")} for z in summary["zones"]],
                "wall_seconds": summary["wall_seconds"]}), flush=True)
    if before != source_hashes():
        raise RuntimeError("CONSTRUCT_SOURCE_CHANGED_DURING_RUN")
    report = {"kind": "CURRENT_TOOL_RACK_RAW_PRICE_ARC_CONSTRUCT", "synthetic": True,
        "production_modified": False, "preset_detector_or_mission_labels": False,
        "actual_pid12448_replay": False, "network_connections_allowed": False,
        "source_git": optional_source_git(ROOT),
        "source_files": before, "cases": results,
        "acceptance": "PASS" if all(r["acceptance"] == "PASS" for r in results) else "FAIL"}
    write_json(args.output / "construct_results.json", report)
    print("CONSTRUCT " + report["acceptance"] + ": " + str(args.output / "construct_results.json"), flush=True)
    return 0 if report["acceptance"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
