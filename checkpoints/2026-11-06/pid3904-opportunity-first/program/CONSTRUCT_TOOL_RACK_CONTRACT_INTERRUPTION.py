"""Bounded actual-pipeline Construct for profitable ARC contract interruption.

Prices, contract clocks and quotes are authored before execution. Production
derives every parent, entry mission, timing family, weakness and actual fill.
No holdings or strategy evidence are injected. Synthetic acceptance is not a
claim about the recorded market run or profitability outside these fixtures.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import socket
import time
from unittest.mock import patch

from CONSTRUCT_TOOL_RACK_ARCS import (
    blocked_network, canonical, optional_source_git, source_hashes as arc_source_hashes, write_json,
)
from strategy_core.paper_execution import PaperExecutioner, nominal_taker_fee
from strategy_core.paper_runtime import ToolRackPaperEngine, plain
from strategy_core.types import Side
from tests.tool_rack.construct_arc_fixtures import build_tape
from tests.tool_rack.construct_contract_interruption_fixtures import ContractInterruptionScenario


ROOT = Path(__file__).resolve().parent
EXIT_REASON = "ARC_PROFITABLE_CONTRACT_INTERRUPTION"


def source_hashes():
    result = arc_source_hashes()
    for name in ("CONSTRUCT_TOOL_RACK_CONTRACT_INTERRUPTION.py",
                 "tests/tool_rack/construct_contract_interruption_fixtures.py",
                 "tests/tool_rack/construct_holding_fixtures.py"):
        result[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    return result


def current_mark(position, book):
    """Scorer-only current synthetic depth observation, never an engine input."""
    if position is None or book is None or book.ticker != position.ticker:
        return None
    levels = book.bids(Side(position.side))
    remaining = position.qty
    amount = Decimal(0)
    for level in levels:
        quantity = min(remaining, level.quantity)
        amount += Decimal(str(level.price)) * quantity
        remaining -= quantity
        if remaining == 0:
            break
    if remaining:
        return {"full_lot": False}
    bid = amount / position.qty
    fee = nominal_taker_fee(position.qty, bid)
    net = amount - Decimal(str(position.cost)) - Decimal(str(position.entry_fee_remaining)) - fee
    peak = Decimal(str(position.peak_bid)) if position.peak_bid is not None else None
    return {"full_lot": True, "quantity": position.qty, "full_lot_bid": str(bid),
        "observed_peak_bid": str(peak) if peak is not None else None,
        "net_after_modeled_fees": str(net), "positive_net": net > 0,
        "observed_bid_giveback": peak is not None and peak > bid,
        "unrealized_scorer_observation_only": True}


def position_collection(decisions, position_id):
    for row in decisions:
        if str(row.get("position_id")) != str(position_id):
            continue
        decision = row.get("decision") or {}
        intent = decision.get("intent") or {}
        direct = (intent.get("metadata") or {}).get("mission_collection")
        if direct:
            return direct
        physical = (decision.get("custody_review") or {}).get("physical") or {}
        if physical.get("mission_collection"):
            return physical["mission_collection"]
    return {}


def run_case(scenario, destination, *, step=6):
    started = time.monotonic()
    destination.mkdir(parents=True, exist_ok=False)
    expected = scenario.expectations()
    expected.update(raw_price_step_seconds=1, decisions_every_seconds=step,
        warmup_entries_disabled=True, engine_classes_replaced=False)
    # Persist the authored expectation before deriving or observing outcomes.
    write_json(destination / "expectations.json", expected)
    tape = build_tape(scenario)
    identity = {"scenario": asdict(scenario), "rows": tape.rows, "history": tape.completed_bars}
    digest = hashlib.sha256(canonical(identity)).hexdigest()
    write_json(destination / "input_identity.json", {"sha256": digest,
        "scenario": asdict(scenario), "raw_price_count": len(tape.rows)})
    start = scenario.current_start
    frames, events, original_entries = [], [], {}
    anchor_id = anchor_scope = anchor_qty = None
    previous = None
    with (destination / "console.log").open("w", encoding="utf-8") as console, redirect_stdout(console):
        engine = ToolRackPaperEngine(destination / "paper_run")
        try:
            for offset in range(start - 180, scenario.end_offset + 1, step):
                feed = tape.capture(offset, previous_offset=previous, include_prefix=previous is None)
                processed = engine.process(feed, now_ts=feed.observed_ts,
                    historical_candles=tape.history_at(offset), entry_window_closed=offset < start)
                status = processed["status"]
                context = plain(status.get("mission_context") or {})
                for receipt in processed["receipts"]:
                    if not receipt.event:
                        continue
                    event = plain(receipt.event)
                    key = str(receipt.position_id)
                    if event.get("event") == "ENTRY":
                        position = engine.executor.positions.get(receipt.position_id)
                        entry_metadata = plain(position.entry_metadata if position is not None else {})
                        original_entries[key] = entry_metadata
                        if (anchor_id is None and 0 <= offset - start <= 60
                                and event.get("side") == expected["opening_side"]):
                            anchor_id, anchor_qty = receipt.position_id, event["qty"]
                            anchor_scope = (entry_metadata.get("mission") or {}).get("parent_leg_id")
                    events.append({"offset": offset, "relative_seconds": offset - start,
                        "event": event, "entry_metadata": original_entries.get(key, {})})
                position = engine.executor.positions.get(anchor_id) if anchor_id is not None else None
                scopes = context.get("parents_by_id") or {}
                scope = scopes.get(anchor_scope) or {}
                decisions = plain(status.get("decisions") or [])
                frame = {"offset": offset, "relative_seconds": offset - start,
                    "ticker": feed.market.ticker, "contract_open_ts": feed.market.open_ts,
                    "contract_close_ts": feed.market.close_ts,
                    "current_geometry": plain(status.get("latest_geometry") or {}),
                    "source_ms": context.get("source_ms"),
                    "continuity_generation": context.get("continuity_generation"),
                    "current_parent_id": (context.get("parent") or {}).get("id"),
                    "anchor_position_id": anchor_id, "anchor_parent_id": anchor_scope,
                    "held_quantity": position.qty if position is not None else 0,
                    "held_scope": {key: scope.get(key) for key in (
                        "id", "side", "status", "source_ms", "continuity_generation", "origin_ms",
                        "origin_observed", "invalidated", "terminal", "weakness", "return_timing_reference")},
                    "current_mark": current_mark(position, feed.book),
                    "collection": position_collection(decisions, anchor_id),
                    "decisions": decisions,
                    "booked_events": [plain(receipt.event) for receipt in processed["receipts"] if receipt.event],
                    "execution_receipts": [{"status": receipt.status, "reason": receipt.reason,
                        "position_id": receipt.position_id} for receipt in processed["receipts"]]}
                frames.append(frame)
                previous = offset
        finally:
            engine.close(reason="OFFLINE_SYNTHETIC_CONTRACT_INTERRUPTION_CONSTRUCT_COMPLETE")
    journal = PaperExecutioner.inspect_journal(destination / "paper_run")
    anchor_events = [row for row in events if str(row["event"].get("position_id")) == str(anchor_id)]
    entry = next((row for row in anchor_events if row["event"].get("event") == "ENTRY"), None)
    reductions = [row for row in anchor_events if row["event"].get("event") in ("EXIT", "PARTIAL_EXIT", "SETTLEMENT")]
    original = (entry or {}).get("entry_metadata") or {}
    mission, earned = original.get("mission") or {}, original.get("arc_entry_scale") or {}
    causal_entry = bool(entry and mission.get("purpose") == "ARC_RETURN"
        and earned.get("qualified") is True and earned.get("frozen_at_entry") is True
        and earned.get("incoming_parent_id") == mission.get("parent_leg_id")
        and earned.get("incoming_side") == mission.get("side")
        and earned.get("comparison_family") in ("received_parent", "completed_minute_parent"))
    tracked = [frame for frame in frames if entry and frame["offset"] >= entry["offset"]]
    window = [frame for frame in tracked if 150 <= frame["relative_seconds"] <= 210]
    givebacks = [frame for frame in window if (frame.get("current_mark") or {}).get("positive_net")
                 and (frame.get("current_mark") or {}).get("observed_bid_giveback")]
    sale = next((row for row in reductions if row["event"].get("reason") == EXIT_REASON), None)
    sale_frame = next((frame for frame in tracked if sale and frame["offset"] == sale["offset"]), {})
    sale_proof = (sale or {}).get("event", {}).get("arc_contract_interruption") or {}
    sale_scope = sale_frame.get("held_scope") or {}
    weakness = sale_scope.get("weakness") or {}
    full_positive_sale = bool(sale and len(reductions) == 1 and sale["event"].get("event") == "EXIT"
        and sale["event"].get("qty") == anchor_qty and Decimal(sale["event"]["net_pnl"]) > 0
        and 150 <= sale["relative_seconds"] <= 210 and sale_scope.get("status") == "ACTIVE"
        and (sale_scope.get("terminal") or {}).get("qualified") is not True
        and weakness.get("count") in (1, 2)
        and sale_proof.get("qualified") is True and sale_proof.get("parent_completed") is False
        and sale_proof.get("commit_full_remaining_lot_verified") is True
        and sale_proof.get("commit_quantity") == anchor_qty
        and sale_proof.get("reference_family") == earned.get("comparison_family")
        and sale_proof.get("close_ts", float("inf")) < sale_proof.get("earliest_reference_finish_ts", 0)
        and sale_proof.get("observed_peak_bid", 0) > sale_proof.get("current_full_lot_bid", 1))
    held = bool(entry and tracked and not reductions
        and all(frame["held_quantity"] == anchor_qty for frame in tracked))
    same_scope = bool(tracked and all(frame["held_scope"].get("id") == anchor_scope
        and frame["held_scope"].get("invalidated") is not True for frame in tracked))
    early_reductions = [row for row in reductions if row["relative_seconds"] < 150]
    later_reentries = [row for row in events if sale and row["event"].get("event") == "ENTRY"
        and row["offset"] >= sale["offset"] and str(row["event"].get("position_id")) != str(anchor_id)
        and (row["entry_metadata"].get("mission") or {}).get("parent_leg_id") == anchor_scope]
    counts = [(frame["held_scope"].get("weakness") or {}).get("count") for frame in window]
    control_evidence = {
        "positive_giveback_observations": len(givebacks),
        "weakness_counts_in_window": sorted(set(count for count in counts if count is not None)),
        "full_quantity_held_through_end": held,
        "same_parent_scope_without_invalidation": same_scope,
        "collection_reasons": sorted({(frame.get("collection") or {}).get("collection_hold_reason")
            or (frame.get("collection") or {}).get("reason") or "UNKNOWN" for frame in window}),
        "interruption_reasons": sorted({((frame.get("collection") or {}).get("contract_interruption") or {}).get("reason")
            or "NO_RECORDED_PROPOSAL" for frame in window})}
    if expected["expected_profitable_interruption"]:
        behavior_pass = full_positive_sale and not early_reductions and not later_reentries
    else:
        expected_counts = (any(count in (1, 2) for count in counts)
                           if expected["control"] == "SUFFICIENT_RUNWAY"
                           else bool(counts) and all(count == 0 for count in counts))
        behavior_pass = held and same_scope and bool(givebacks) and expected_counts
    passed = bool(causal_entry and behavior_pass and journal["committed_boundary"])
    summary = {"name": scenario.name, "acceptance": "PASS" if passed else "FAIL", "synthetic": True,
        "expectations": expected, "input_sha256": digest, "actual_opening_entry": entry,
        "causally_earned_arc_entry": causal_entry, "actual_exception_sale": sale,
        "exception_full_lot_positive_sale_while_active": full_positive_sale,
        "sale_weakness_count": weakness.get("count"), "control_evidence": control_evidence,
        "early_reductions": early_reductions, "same_scope_entries_after_sale": later_reentries,
        "all_anchor_reductions": reductions, "all_events": events,
        "journal_verified": journal["committed_boundary"], "journal_seq": journal["seq"],
        "journal_sha256": journal["sha256"], "decision_count": len(frames),
        "unresolved_positions_at_end": len(journal["state"]["positions"]),
        "wall_seconds": round(time.monotonic() - started, 3), "actual_market_replay": False,
        "injected_positions_or_strategy_evidence": False, "external_profitability_claim": False}
    write_json(destination / "frames.json", frames)
    write_json(destination / "selected_frames.json", [frame for frame in frames
        if frame["relative_seconds"] in (0, 6, 60, 120, 144, 150, 156, 162, 168, 174, 192, 210, 216)
        or frame["booked_events"]])
    write_json(destination / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cases", default="short_up,short_down,runway_up,runway_down,no_weakness_up,no_weakness_down")
    args = parser.parse_args(argv)
    scenarios = {}
    for suffix, direction in (("up", 1), ("down", -1)):
        for prefix, changes in (("short", {}), ("runway", {"close_relative_seconds": 900}),
            ("no_weakness", {"current_weakness_path": False, "quote_only_giveback": True})):
            name = prefix + "_" + suffix
            scenarios[name] = ContractInterruptionScenario(name=name, direction=direction, **changes)
    selected = args.cases.split(",")
    if any(name not in scenarios for name in selected):
        parser.error("Unknown contract interruption Construct case")
    args.output.mkdir(parents=True, exist_ok=True)
    before = source_hashes()
    results = []
    with patch.object(socket.socket, "connect", blocked_network), patch.object(socket, "getaddrinfo", blocked_network):
        for name in selected:
            print("RUN " + name, flush=True)
            result = run_case(scenarios[name], args.output / name)
            results.append(result)
            print(json.dumps({"case": name, "acceptance": result["acceptance"],
                "earned_arc_entry": result["causally_earned_arc_entry"],
                "sale_relative": (result["actual_exception_sale"] or {}).get("relative_seconds"),
                "sale_weakness_count": result["sale_weakness_count"],
                "full_positive_sale": result["exception_full_lot_positive_sale_while_active"],
                "control": result["control_evidence"], "wall_seconds": result["wall_seconds"]}), flush=True)
    if source_hashes() != before:
        raise RuntimeError("CONTRACT_INTERRUPTION_CONSTRUCT_SOURCE_CHANGED_DURING_RUN")
    report = {"kind": "CURRENT_TOOL_RACK_RAW_PRICE_CONTRACT_INTERRUPTION_CONSTRUCT",
        "synthetic": True, "source_files": before,
        "source_git": optional_source_git(ROOT),
        "production_modified_during_run": False, "network_connections_allowed": False,
        "injected_positions_or_strategy_evidence": False, "cases": results,
        "acceptance": "PASS" if all(result["acceptance"] == "PASS" for result in results) else "FAIL"}
    write_json(args.output / "construct_results.json", report)
    print("CONTRACT INTERRUPTION CONSTRUCT " + report["acceptance"] + ": " + str(args.output / "construct_results.json"), flush=True)
    return 0 if report["acceptance"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
