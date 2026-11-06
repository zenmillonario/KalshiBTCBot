"""Stream exact PID19996 original decisions without retaining the large tape.

Only the runtime's new receipt bridge is added to a reconstructed snapshot.
The source time, decision time, quote, geometry, and original record remain
unchanged.  Capture time is the identity source_time + recorded source_age.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import lzma
from pathlib import Path
import re

from strategy_core.paper_execution import PaperBook, PriceLevel
from strategy_core.paper_runtime import snapshot_from_book
from strategy_core.source_freshness import RECEIPT_KEY, capture_source_receipt
from strategy_core.commander import OneCommander
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, Lane, Side, ToolIntent


DIRECTORY = Path(__file__).with_name("fixtures")
PATH = DIRECTORY / "pid19996_rail_fishing_cases.jsonl.xz"
MANIFEST = DIRECTORY / "pid19996_rail_fishing_manifest.json"


@lru_cache(maxsize=1)
def manifest():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data["schema"] != "TACHYOS_PID19996_EXACT_RAIL_FISHING_CASES_V1":
        raise ValueError("Unexpected PID19996 Rail fixture schema")
    if hashlib.sha256(PATH.read_bytes()).hexdigest() != data["compressed_sha256"]:
        raise ValueError("PID19996 Rail fixture archive changed")
    return data


def iter_records(group=None, *, sequences=None):
    corpus = manifest()
    wanted = (set(corpus["groups"][group]) if group is not None else
              set(sequences) if sequences is not None else None)
    with lzma.open(PATH, "rb") as source:
        for line in source:
            match = re.match(rb'\{"sequence":\s*(\d+)', line)
            if match is None:
                raise ValueError("Unexpected original decision JSONL prefix")
            sequence = int(match.group(1))
            if wanted is not None and sequence not in wanted:
                continue
            evidence = corpus["records"][str(sequence)]
            if hashlib.sha256(line).hexdigest() != evidence["original_line_sha256"]:
                raise ValueError("Original PID19996 line changed: " + str(sequence))
            record = json.loads(line)
            payload = {key: value for key, value in record.items() if key != "sha256"}
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            if digest != record["sha256"] or digest != evidence["original_decision_sha256"]:
                raise ValueError("Original PID19996 decision hash changed: " + str(sequence))
            yield record


@lru_cache(maxsize=16)
def _record(sequence):
    return next(iter_records(sequences=(sequence,)))


def record(sequence):
    return deepcopy(_record(sequence))


def book_from_record(data):
    native = deepcopy(data["native_book"])
    for key in ("yes_bids", "no_bids"):
        native[key] = tuple(PriceLevel(**row) for row in native[key])
    return PaperBook(**native)


def snapshot_from_record(data, *, bridge_receipt=True):
    metadata = deepcopy(data["physical_metadata"])
    if bridge_receipt:
        source_ms = metadata["current_geometry"]["epoch_ms"]
        source_age = data["source_status"]["btc_geometry_age_seconds"]
        metadata[RECEIPT_KEY] = capture_source_receipt(metadata, data["source_status"],
            captured_at=source_ms / 1000.0 + source_age,
            source_generation=data["source_generation"])
    return snapshot_from_book(book_from_record(data), now_ts=data["now_ts"],
        metadata=metadata, ticker=data["market"]["ticker"], close_ts=data["market"]["close_ts"])


def snapshot(sequence, **kwargs):
    return snapshot_from_record(record(sequence), **kwargs)


def intent_from_dict(raw):
    data = deepcopy(raw)
    data["action"], data["lane"] = Action(data["action"]), Lane(data["lane"])
    data["side"] = Side(data["side"]) if data.get("side") else None
    return ToolIntent(**data)


def original_intents(data):
    return tuple(intent_from_dict(raw) for raw in data["rack"].get("commander_intents") or [])


def original_entry_intent(sequence):
    rows = record(sequence)["decisions"]
    raw = next(row["decision"].get("intent") for row in rows if row["scope"] == "ENTRY")
    if raw is None:
        raise ValueError("Original entry has no intent: " + str(sequence))
    return intent_from_dict(raw)


@lru_cache(maxsize=1)
def opening_trajectory_probe():
    """Offer each original opening frame causally; never invent a booked fill.

    The engine's separately recorded session entry deadline is reported apart
    from candidate eligibility.  Kept-flat admission probes intentionally do
    not claim fill, fee, exit, settlement, or counterfactual profit results.
    """
    group_names = ("winner_one_opening", "winner_two_opening", "third_first_300s")
    group_sets = {name: set(manifest()["groups"][name]) for name in group_names}
    commanders = {name: OneCommander() for name in group_names}
    racks = {name: ToolRackController() for name in group_names}
    report = {name: {"callbacks": [], "watch_changes": []} for name in group_names}
    previous_watch = dict.fromkeys(group_names)
    for data in iter_records():
        sequence = data["sequence"]
        group = next((name for name in group_names if sequence in group_sets[name]), None)
        if group is None:
            continue
        commander = commanders[group]
        snap = snapshot_from_record(data)
        candidates = commander.physical_entry_candidates(snap)
        advisers = tuple(intent for intent in original_intents(data)
                         if intent.metadata.get("commander_primary_candidate") is not True)
        rack = racks[group]
        # Match paper_runtime's actual new-entry qualification chain.  The
        # ordinary first-300s independent-MAIN observation rule must not erase
        # an earned Commander opening carried forward to its value rejoin.
        proposed = tuple(rack.qualify_independent_role_mission(
            rack.qualify_independent_recovery_mission(intent, snap, {}), snap, {})
            for intent in candidates + advisers)
        proposed = rack.filter_independent_lane_candidates(proposed, snap)
        decision = commander.decide_entry(proposed, snap, {})
        watch = commander._opening_rail_value_watch.state
        watch_key = watch["deferred_source_ms"] if watch is not None else None
        if previous_watch[group] != watch_key:
            report[group]["watch_changes"].append({"sequence": sequence, "deferred_source_ms": watch_key})
            previous_watch[group] = watch_key
        entry = next(row["decision"] for row in data["decisions"] if row["scope"] == "ENTRY")
        geometry = snap.metadata["current_geometry"]
        row = {"sequence": sequence, "original_decision_sha256": data["sha256"],
               "now_ts": snap.now_ts, "contract_age_s": snap.contract_age_s,
               "yes_ask": snap.yes_ask, "action": decision.action.value,
               "reason": decision.reason, "candidate_reason": decision.intent.reason if decision.intent else None,
               "candidate_side": decision.intent.side.value if decision.intent and decision.intent.side else None,
               "parent_id": snap.metadata["mission_context"]["parent"]["id"],
               "native_direction": geometry.get("current_native_direction"),
               "motion": {key: geometry.get(key) for key in ("btc_change6", "btc_change9", "ema9_change6")},
               "watch_retained": watch is not None,
               "recorded_engine_entry_window_open": entry["reason"] != "PAPER_ENTRY_WINDOW_CLOSED_DRAINING"}
        if decision.intent is not None:
            row["physical_evidence"] = deepcopy(decision.intent.metadata.get("commander_physical_evidence"))
            row["max_price"] = decision.intent.max_price
        report[group]["callbacks"].append(row)
    return report
