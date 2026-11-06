"""Raw-price parent holding Construct through the actual PAPER ledger.

Predeclared paths exercise two early pullbacks then a spent third weakness,
repeated observations of one weak patch, a continuous slow drift into one
pause, and three pauses in a living leg.
No detector or management labels, fixed holdings, or desired orders are
injected. This is synthetic behavioral acceptance, not a market replay.
Positive acceptance follows the same incoming return lot through the natural
return and EMA9 contact; a correct outgoing sale alone cannot pass.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import socket
import time
from unittest.mock import patch

from CONSTRUCT_TOOL_RACK_ARCS import (
    blocked_network, canonical, optional_source_git, source_hashes as arc_source_hashes, write_json,
)
from strategy_core.paper_execution import PaperExecutioner
from strategy_core.paper_runtime import ToolRackPaperEngine, plain
from tests.tool_rack.construct_arc_fixtures import BASE, build_tape
from tests.tool_rack.construct_holding_fixtures import HoldingScenario


ROOT = Path(__file__).resolve().parent


def source_hashes():
    hashes = arc_source_hashes()
    for name in ("CONSTRUCT_TOOL_RACK_HOLDING.py", "tests/tool_rack/construct_holding_fixtures.py"):
        hashes[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    return hashes


def position_quantities(engine):
    return {str(key): value.qty for key, value in engine.executor.positions.items()}


def scoped_inventory(engine):
    return {str(key): {
        "quantity": value.qty, "side": plain(value.side), "ticker": value.ticker,
        "opportunity_id": value.opportunity_id, "custody_state": value.custody_state,
        "mission": plain(value.entry_metadata.get("mission") or {}),
    } for key, value in engine.executor.positions.items()}


def frame_evidence(status, *, offset, start, anchor_id, anchor_scope, engine, receipts, repeated=False):
    context = plain(status.get("mission_context") or {})
    parent = context.get("parent") or {}
    scopes = context.get("parents_by_id") or {}
    held_scope = scopes.get(anchor_scope) or (parent if parent.get("id") == anchor_scope else {})
    geometry = status.get("latest_geometry") or {}
    position = engine.executor.positions.get(anchor_id) if anchor_id is not None else None
    return {
        "offset": offset, "relative_seconds": offset - start,
        "repeated_same_source": repeated,
        "btc": geometry.get("btc_price"), "ema9": geometry.get("ema9"), "ema30": geometry.get("ema30"),
        "native_side": geometry.get("arc_direction"),
        "current_parent_id": parent.get("id"), "current_parent_side": parent.get("side"),
        "held_position_id": anchor_id, "held_parent_id": anchor_scope,
        "held_quantity": position.qty if position is not None else 0,
        "held_scope_status": held_scope.get("status"),
        "held_scope_terminal": held_scope.get("terminal") or {},
        "held_scope_weakness": held_scope.get("weakness") or {},
        "position_inventory_after_processing": scoped_inventory(engine),
        "parent_scopes": {key: {field: value.get(field) for field in (
            "id", "side", "status", "source_ms", "continuity_generation", "supported",
            "invalidated", "invalidation_reason", "invalidated_known_ms", "predecessor_id",
        )} for key, value in scopes.items()},
        "source_ms": context.get("source_ms"),
        "position_decisions": plain([row for row in status.get("decisions", ()) if row.get("scope") != "ENTRY"]),
        "entry_decision": plain(next((row.get("decision") for row in status.get("decisions", ())
                                      if row.get("scope") == "ENTRY"), {})),
        "booked_events": [plain(receipt.event) for receipt in receipts if receipt.event],
    }


def incoming_lifecycle_evidence(incoming, frames, events, tape, expectation):
    """Score the actual bought return lot, without supplying engine evidence.

    The authored path has no subsequent terminal or rollover before its end.
    A tiny continued extension around the broad edge must not sell the newly
    acquired lot or mint a replacement holding for the same natural return.
    """
    if not expectation["expected_terminal_collection"]:
        return {"required": False, "qualified": True}
    if incoming is None:
        return {"required": True, "qualified": False,
                "failure_reasons": ["NO_SAME_QUOTE_INCOMING_ARC_ENTRY"]}
    key = str(incoming["event"]["position_id"])
    qty = incoming["event"]["qty"]
    scope_id = incoming["mission"].get("parent_leg_id")
    generation = incoming["mission"].get("continuity_generation")
    side = incoming["event"]["side"]
    signed = 1.0 if side == "YES" else -1.0
    end = expectation["end_relative_seconds"]
    tracked = [f for f in frames if incoming["relative_seconds"] <= f["relative_seconds"] <= end]
    reductions = [e for e in events if str(e["event"].get("position_id")) == key
        and e["event"].get("event") in ("EXIT", "PARTIAL_EXIT", "SETTLEMENT")]
    later_entries = [e for e in events if e["event"].get("event") == "ENTRY"
        and e["relative_seconds"] >= incoming["relative_seconds"]
        and str(e["event"].get("position_id")) != key]
    inventory_failures, scope_failures = [], []
    for frame in tracked:
        position = frame["position_inventory_after_processing"].get(key) or {}
        mission = position.get("mission") or {}
        if (position.get("quantity") != qty or position.get("side") != side
                or mission.get("purpose") != "ARC_RETURN"
                or mission.get("parent_leg_id") != scope_id
                or mission.get("continuity_generation") != generation):
            inventory_failures.append({"relative_seconds": frame["relative_seconds"],
                "position": position})
        scope = frame["parent_scopes"].get(scope_id) or {}
        if (not scope_id or scope.get("id") != scope_id or scope.get("side") != side
                or scope.get("continuity_generation") != generation
                or scope.get("invalidated") is True
                or scope.get("status") not in ("ANTICIPATED", "ACTIVE")):
            scope_failures.append({"relative_seconds": frame["relative_seconds"], "scope": scope})
    # The scorer examines the actual raw production-EMA samples only after all
    # processing has finished. It does not tell the engine where contact is.
    contact_row = next((row for row in tape.rows[incoming["offset"] + 1:]
        if signed * (row["btc_price"] - row["ema9"]) >= 0), None)
    contact = ({"relative_seconds": contact_row["epoch_ms"] / 1000 - BASE - tape.scenario.current_start,
                "source_ms": contact_row["epoch_ms"], "btc": contact_row["btc_price"],
                "ema9": contact_row["ema9"]} if contact_row else None)
    post_contact = [f for f in tracked if contact and f["relative_seconds"] > contact["relative_seconds"]]
    held_past_contact = bool(post_contact and all(
        (f["position_inventory_after_processing"].get(key) or {}).get("quantity") == qty
        for f in post_contact))
    reached_end = bool(tracked and tracked[-1]["relative_seconds"] == end)
    final = tracked[-1] if tracked else {}
    final_scope = (final.get("parent_scopes") or {}).get(scope_id) or {}
    active_at_end = bool(reached_end and final.get("current_parent_id") == scope_id
        and final_scope.get("status") == "ACTIVE" and final_scope.get("side") == side)
    failure_reasons = []
    if not reached_end or inventory_failures:
        failure_reasons.append("INCOMING_POSITION_OR_FULL_QUANTITY_NOT_RETAINED")
    if scope_failures:
        failure_reasons.append("INCOMING_PARENT_SCOPE_CHANGED_OR_INVALIDATED")
    if reductions:
        failure_reasons.append("INCOMING_POSITION_REDUCED_BEFORE_NATURAL_RETURN_END")
    if later_entries:
        failure_reasons.append("NEW_ENTRY_AFTER_INITIAL_RETURN_HANDOFF")
    if not held_past_contact:
        failure_reasons.append("SAME_INCOMING_LOT_NOT_HELD_PAST_OBSERVED_EMA9_CONTACT")
    if not active_at_end:
        failure_reasons.append("ORIGINAL_INCOMING_PARENT_NOT_ACTIVE_AT_END")
    return {"required": True, "qualified": not failure_reasons,
        "position_id": key, "parent_leg_id": scope_id, "side": side,
        "original_quantity": qty, "tracked_frame_count": len(tracked),
        "held_full_quantity_through_end": reached_end and not inventory_failures,
        "scope_owned_without_invalidation": bool(scope_id and not scope_failures),
        "original_parent_active_at_end": active_at_end,
        "ema9_return_contact": contact, "held_past_ema9_contact": held_past_contact,
        "incoming_reductions": reductions, "entries_after_handoff": later_entries,
        "inventory_failures": inventory_failures, "scope_failures": scope_failures,
        "failure_reasons": failure_reasons}


def run_case(scenario, destination, *, step=6):
    started = time.monotonic()
    destination.mkdir(parents=True, exist_ok=False)
    expectation = scenario.expectations()
    expectation.update(decisions_every_seconds=step, raw_price_step_seconds=1,
        warmup_entries_disabled=True, injected_holdings=False, injected_weakness_or_terminal_flags=False)
    write_json(destination / "expectations.json", expectation)
    tape = build_tape(scenario)
    input_sha = hashlib.sha256(canonical({"rows": tape.rows, "history": tape.completed_bars,
                                         "scenario": asdict(scenario)})).hexdigest()
    write_json(destination / "input_identity.json", {"sha256": input_sha,
        "scenario": asdict(scenario), "raw_price_count": len(tape.rows)})
    frames, events, repetitions = [], [], []
    anchor_id = anchor_scope = None
    anchor_qty = None
    previous = None
    missions = {}
    start = scenario.current_start
    with (destination / "console.log").open("w", encoding="utf-8") as console, redirect_stdout(console):
        engine = ToolRackPaperEngine(destination / "paper_run")
        try:
            for offset in range(start - 180, scenario.end_offset + 1, step):
                feed = tape.capture(offset, previous_offset=previous, include_prefix=previous is None)
                result = engine.process(feed, now_ts=feed.observed_ts,
                    historical_candles=tape.history_at(offset), entry_window_closed=offset < start)
                for receipt in result["receipts"]:
                    if not receipt.event:
                        continue
                    event = plain(receipt.event)
                    position_id = str(receipt.position_id)
                    if event.get("event") == "ENTRY":
                        held = engine.executor.positions.get(receipt.position_id)
                        mission = plain((held.entry_metadata.get("mission") or {}) if held else {})
                        missions[position_id] = mission
                        if (anchor_id is None and 0 <= offset - start <= 60
                                and event.get("side") == expectation["opening_side"]):
                            anchor_id, anchor_scope = receipt.position_id, mission.get("parent_leg_id")
                            anchor_qty = event["qty"]
                    events.append({"offset": offset, "relative_seconds": offset - start,
                        "mission": missions.get(position_id, {}), "event": event})
                frame = frame_evidence(result["status"], offset=offset, start=start,
                    anchor_id=anchor_id, anchor_scope=anchor_scope, engine=engine, receipts=result["receipts"])
                frames.append(frame)
                if offset - start == expectation["same_source_repeat_relative"]:
                    before_weakness = canonical(frame["held_scope_weakness"])
                    before_inventory = position_quantities(engine)
                    for number in range(expectation["same_source_repeat_count"]):
                        duplicate = engine.process(feed, now_ts=feed.observed_ts,
                            historical_candles=tape.history_at(offset))
                        repeated = frame_evidence(duplicate["status"], offset=offset, start=start,
                            anchor_id=anchor_id, anchor_scope=anchor_scope, engine=engine,
                            receipts=duplicate["receipts"], repeated=True)
                        frames.append(repeated)
                        repetitions.append({"relative_seconds": offset-start, "repeat": number+1,
                            "anchor_present": anchor_id is not None,
                            "weakness_unchanged": canonical(repeated["held_scope_weakness"]) == before_weakness,
                            "inventory_unchanged": position_quantities(engine) == before_inventory,
                            "events": repeated["booked_events"]})
                        for event in repeated["booked_events"]:
                            events.append({"offset": offset, "relative_seconds": offset-start,
                                "repeated_same_source": True,
                                "mission": missions.get(str(event.get("position_id")), {}), "event": event})
                previous = offset
        finally:
            engine.close(reason="OFFLINE_SYNTHETIC_HOLDING_CONSTRUCT_COMPLETE")
    journal = PaperExecutioner.inspect_journal(destination / "paper_run")
    regular = [f for f in frames if not f["repeated_same_source"]]
    anchor_key = str(anchor_id) if anchor_id is not None else None
    anchor_events = [e for e in events if str(e["event"].get("position_id")) == anchor_key]
    entry = next((e for e in anchor_events if e["event"].get("event") == "ENTRY"), None)
    reductions = [e for e in anchor_events if e["event"].get("event") in ("EXIT", "PARTIAL_EXIT", "SETTLEMENT")]
    exit_window = expectation["terminal_exit_window_relative"]
    hold_until = exit_window[0] if exit_window else expectation["end_relative_seconds"] + 1
    held_frames = [f for f in regular if entry and entry["relative_seconds"] <= f["relative_seconds"] < hold_until]
    held_unchanged = bool(entry and held_frames and all(f["held_quantity"] == anchor_qty for f in held_frames))
    checkpoint = next((f for f in regular if f["relative_seconds"] == expectation["counter_checkpoint_relative"]), {})
    count_at_checkpoint = (checkpoint.get("held_scope_weakness") or {}).get("count")
    counter_correct = count_at_checkpoint == expectation["expected_counter_at_checkpoint"]
    sale = None
    sale_frame = None
    incoming = None
    if exit_window:
        sale = next((e for e in reductions if e["event"].get("event") == "EXIT"
                     and exit_window[0] <= e["relative_seconds"] <= exit_window[1]), None)
        sale_frame = next((f for f in regular if sale and f["offset"] == sale["offset"]), None)
        incoming = next((e for e in events if sale and e["event"].get("event") == "ENTRY"
            and e["event"].get("side") == expectation["incoming_return_side"]
            and e["offset"] == sale["offset"]
            and e["event"].get("quote_id") == sale["event"].get("quote_id")
            and e["mission"].get("purpose") == "ARC_RETURN"), None)
    third = (sale_frame or {}).get("held_scope_weakness") or {}
    ordinary_exit = bool(sale and sale["event"].get("reason") == "MOUNTAIN_NEXT_MATURE_PHYSICAL_EDGE"
        and third.get("count", 0) >= 3 and third.get("third_observed") is True
        and (sale_frame.get("held_scope_terminal") or {}).get("qualified") is True)
    duplicate_pass = (len(repetitions) == expectation["same_source_repeat_count"]
        and all(r["anchor_present"] and r["weakness_unchanged"] and r["inventory_unchanged"]
                and not any(e.get("event") in ("ENTRY", "EXIT", "PARTIAL_EXIT", "SETTLEMENT")
                            for e in r["events"]) for r in repetitions))
    no_early_sale = not any(e["relative_seconds"] < hold_until for e in reductions)
    lifecycle = incoming_lifecycle_evidence(incoming, regular, events, tape, expectation)
    outgoing_pass = bool(ordinary_exit and incoming) if exit_window else not reductions
    positive_pass = outgoing_pass and lifecycle["qualified"]
    passed = bool(entry and held_unchanged and counter_correct and duplicate_pass
                  and no_early_sale and positive_pass and journal["committed_boundary"])
    summary = {
        "name": scenario.name, "synthetic": True, "acceptance": "PASS" if passed else "FAIL",
        "expectations": expectation, "input_sha256": input_sha,
        "anchor_position_id": anchor_id, "anchor_parent_id": anchor_scope, "anchor_quantity": anchor_qty,
        "actual_opening_entry": entry, "held_unchanged_through_required_window": held_unchanged,
        "no_early_sale": no_early_sale, "counter_at_checkpoint": count_at_checkpoint,
        "counter_checkpoint_pass": counter_correct,
        "same_source_repeats_pass": duplicate_pass, "same_source_repeats": repetitions,
        "actual_terminal_sale": sale, "terminal_sale_uses_third_weakness": ordinary_exit,
        "same_quote_opposite_arc_handoff": incoming,
        "outgoing_holding_and_handoff_pass": outgoing_pass,
        "incoming_lifecycle": lifecycle,
        "all_position_reductions": [e for e in events
            if e["event"].get("event") in ("EXIT", "PARTIAL_EXIT", "SETTLEMENT")],
        "held_through_end": bool(not reductions and regular and regular[-1]["held_quantity"] == anchor_qty),
        "events": events, "unresolved_positions_at_end": len(journal["state"]["positions"]),
        "journal_seq": journal["seq"], "journal_sha256": journal["sha256"],
        "journal_verified": journal["committed_boundary"],
        "decision_count": len(frames), "wall_seconds": round(time.monotonic()-started, 3),
        "actual_market_replay": False, "settlement_or_profitability_claim": False,
    }
    write_json(destination / "frames.json", frames)
    selected = {0, 6, 150, 174, 192, 210, 300, 330, 354, 396, 420, 570, 630, 636, 654, 672, 690, 708, 732, 840}
    write_json(destination / "selected_frames.json", [f for f in frames if f["relative_seconds"] in selected
        or f["booked_events"]])
    write_json(destination / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", default="holding_up,holding_down,repeated_patch,three_pauses,drifting_pause_up,drifting_pause_down")
    args = parser.parse_args(argv)
    scenarios = {
        "holding_up": HoldingScenario(name="holding_up"),
        "holding_down": HoldingScenario(name="holding_down", direction=-1),
        "repeated_patch": HoldingScenario(name="repeated_patch", path_kind="ONE_REPEATED_PATCH"),
        "three_pauses": HoldingScenario(name="three_pauses", path_kind="THREE_PAUSES_CONTINUATION"),
        "drifting_pause_up": HoldingScenario(name="drifting_pause_up", path_kind="DRIFTING_SINGLE_PAUSE"),
        "drifting_pause_down": HoldingScenario(name="drifting_pause_down", direction=-1,
                                                path_kind="DRIFTING_SINGLE_PAUSE"),
    }
    selected = args.cases.split(",")
    if any(name not in scenarios for name in selected):
        parser.error("Unknown holding Construct case")
    args.output.mkdir(parents=True, exist_ok=True)
    before = source_hashes()
    results = []
    with patch.object(socket.socket, "connect", blocked_network), patch.object(socket, "getaddrinfo", blocked_network):
        for name in selected:
            print("RUN " + name, flush=True)
            result = run_case(scenarios[name], args.output / name)
            results.append(result)
            print(json.dumps({"case": name, "acceptance": result["acceptance"],
                "held_unchanged": result["held_unchanged_through_required_window"],
                "counter_at_checkpoint": result["counter_at_checkpoint"],
                "same_source_repeats_pass": result["same_source_repeats_pass"],
                "exit_relative": (result["actual_terminal_sale"] or {}).get("relative_seconds"),
                "handoff": bool(result["same_quote_opposite_arc_handoff"]),
                "incoming_lifecycle_pass": result["incoming_lifecycle"]["qualified"],
                "incoming_failure_reasons": result["incoming_lifecycle"].get("failure_reasons", []),
                "wall_seconds": result["wall_seconds"]}), flush=True)
    if source_hashes() != before:
        raise RuntimeError("HOLDING_CONSTRUCT_SOURCE_CHANGED_DURING_RUN")
    report = {"kind": "CURRENT_TOOL_RACK_RAW_PRICE_HOLDING_CONSTRUCT", "synthetic": True,
        "source_git": optional_source_git(ROOT),
        "source_files": before, "production_modified_during_run": False,
        "preset_detector_or_weakness_labels": False, "injected_positions": False,
        "network_connections_allowed": False, "cases": results,
        "acceptance": "PASS" if all(r["acceptance"] == "PASS" for r in results) else "FAIL"}
    write_json(args.output / "construct_results.json", report)
    print("HOLDING CONSTRUCT " + report["acceptance"] + ": " + str(args.output / "construct_results.json"), flush=True)
    return 0 if report["acceptance"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
