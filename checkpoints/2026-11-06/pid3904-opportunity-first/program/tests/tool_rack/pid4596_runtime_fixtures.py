"""PID4596 retained observations and explicitly bounded failure controls.

The failing atomic FeedSnapshot and full clock envelope were not recorded.
The fixture therefore preserves its independent components, the preceding
exact quote observations, and the missing/reconstructed fields separately.
No helper accepts the incomplete session as an exact replay or creates orders.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import sys
import traceback
import types

from strategy_core.mission_policy import MissionPolicy
from strategy_core.paper_execution import PaperBook, PriceLevel
from strategy_core.paper_runtime import plain, snapshot_from_book
from strategy_core.physical_source import DirectPhysicalSource
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


DIRECTORY = Path(__file__).with_name("fixtures")
PATH = DIRECTORY / "pid4596_optional_economics_cases.json.gz"
MANIFEST = DIRECTORY / "pid4596_optional_economics_manifest.json"


def _digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()


@lru_cache(maxsize=1)
def manifest():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data["schema"] != "TACHYOS_PID4596_OPTIONAL_ECONOMICS_MANIFEST_V1":
        raise ValueError("Unexpected PID4596 fixture manifest")
    return data


@lru_cache(maxsize=1)
def corpus():
    sealed = manifest()
    packed = PATH.read_bytes()
    if hashlib.sha256(packed).hexdigest() != sealed["compressed_sha256"]:
        raise ValueError("PID4596 compressed fixture changed")
    raw = gzip.decompress(packed)
    if hashlib.sha256(raw).hexdigest() != sealed["uncompressed_sha256"]:
        raise ValueError("PID4596 uncompressed fixture changed")
    data = json.loads(raw)
    if data["schema"] != "TACHYOS_PID4596_OPTIONAL_ECONOMICS_CASES_V1":
        raise ValueError("Unexpected PID4596 fixture schema")
    retained = data["retained_last_decision"]["record"]
    if (_digest({k: v for k, v in retained.items() if k != "sha256"}) != retained["sha256"]
            or retained["sha256"] != sealed["original_last_decision_sha256"]):
        raise ValueError("Original complete PID4596 decision changed")
    observations = data["quote_observations"]
    if [item["sequence"] for item in observations] != list(range(3690, 4260)):
        raise ValueError("PID4596 original quote observation sequence changed")
    for item in observations:
        if sealed["quote_observations"][str(item["sequence"])] != {
                name: item[name] for name in ("original_line_sha256", "original_decision_sha256")}:
            raise ValueError("PID4596 observation provenance changed")
    source = data["captured_original_policy"]
    if (hashlib.sha256(source["utf8_source"].encode()).hexdigest() != source["sha256"]
            or source["sha256"] != sealed["original_policy_sha256"]):
        raise ValueError("Captured PID4596 original policy source changed")
    return data


def snapshot_from_dict(raw):
    return MarketSnapshot(**deepcopy(raw))


def intent_from_dict(raw):
    data = deepcopy(raw)
    for key, cls in (("action", Action), ("lane", Lane), ("side", Side)):
        data[key] = cls(data[key]) if data.get(key) is not None else None
    return ToolIntent(**data)


@lru_cache(maxsize=1)
def captured_policy_class():
    """Load the hash-verified captured adviser for a test-only old/new control."""
    source = corpus()["captured_original_policy"]
    name = "strategy_core._pid4596_captured_original_mission_policy"
    module = types.ModuleType(name)
    module.__file__ = str(Path(__file__).resolve().parents[2] / "strategy_core/mission_policy.py")
    module.__package__ = "strategy_core"
    sys.modules[name] = module
    # Config loads from the current package's unchanged mission.json. The
    # captured Python source itself remains exact and is never written over.
    exec(compile(source["utf8_source"], "captured_original/strategy_core/mission_policy.py", "exec"), module.__dict__)
    return module.MissionPolicy


@lru_cache(maxsize=2)
def _observed_policy(original=False):
    policy = captured_policy_class()() if original else MissionPolicy()
    for item in corpus()["quote_observations"]:
        if item["runtime_called_observe"]:
            policy.observe(snapshot_from_dict(item["snapshot"]))
    return policy


def observed_policy(*, original=False):
    return deepcopy(_observed_policy(original))


def retained_last_snapshot():
    record = corpus()["retained_last_decision"]["record"]
    raw = deepcopy(record["native_book"])
    for key in ("yes_bids", "no_bids"):
        raw[key] = tuple(PriceLevel(**level) for level in raw[key])
    return snapshot_from_book(PaperBook(**raw), now_ts=record["now_ts"],
        metadata=deepcopy(record["physical_metadata"]), ticker=record["market"]["ticker"],
        close_ts=record["market"]["close_ts"])


def retained_last_intent():
    return intent_from_dict(corpus()["retained_last_decision"]["record"]["rack"]["commander_intents"][0])


@lru_cache(maxsize=2)
def _boundary_case(original=False):
    data = corpus()["boundary"]
    snapshot = snapshot_from_dict(data["snapshot"])
    intent = intent_from_dict(data["intent"])
    policy = observed_policy(original=original)
    policy.observe(snapshot)
    if plain(policy._quotes) != data["policy_quotes_before_review"]:
        raise ValueError("PID4596 causal quote history differs from the sealed observation projection")
    return policy, intent, snapshot


def boundary_case(*, original=False):
    """Return a fresh bounded adviser scene, not the missing atomic frame."""
    return deepcopy(_boundary_case(original))


@lru_cache(maxsize=1)
def physical_component_conformance():
    data = corpus()
    last = data["retained_last_decision"]["record"]
    raw = data["raw_geometry"]
    source = DirectPhysicalSource()
    before = source.observe(raw[:-1], now_ts=last["now_ts"])
    mismatches = [key for key, value in before.metadata.items()
                  if plain(value) != last["physical_metadata"].get(key)]
    after = source.observe(raw[-1:], now_ts=data["boundary"]["snapshot"]["now_ts"])
    expected = data["original_components"]["physical_geometry_tail"][-1]["record"]
    return {"raw_observations": len(raw), "preceding_metadata_mismatches": mismatches,
        "final_geometry_matches_retained_record": plain(after.new_rows[-1]) == expected,
        "before_lean": before.metadata["heist"]["lean_evidence"]["status"],
        "after_lean": after.metadata["heist"]["lean_evidence"]["status"],
        "current_source_ms": after.metadata["current_geometry"]["epoch_ms"]}


def original_crash_control():
    policy, intent, snapshot = boundary_case(original=True)
    try:
        policy.review(intent, snapshot)
    except TypeError as exc:
        frames = traceback.extract_tb(exc.__traceback__)
        return {"error_type": type(exc).__name__, "message": str(exc),
            "source_file": frames[-1].filename, "source_line": frames[-1].lineno,
            "advice_before_error": deepcopy(policy.reviews[-1])}
    raise AssertionError("Captured original optional-price crash no longer reproduces")


def synthetic_response_case(bids=(.05, .08, .11, .14), *, original=False):
    """Labelled synthetic calibration controls; never a historical outcome."""
    policy, intent, snapshot = boundary_case(original=original)
    now, btc = snapshot.now_ts, snapshot.metadata["current_geometry"]["btc_price"]
    points = []
    for index, bid in enumerate(bids):
        remaining = len(bids) - index - 1
        points.append({"time": now - 10. * remaining, "quote_time": now - 10. * remaining,
            "source_ms": snapshot.metadata["current_geometry"]["epoch_ms"] - 10000. * remaining,
            "quote_id": snapshot.metadata["quote_id"] if not remaining else f"SYNTHETIC_RESPONSE:{index}",
            "btc": btc + 5. * remaining, "YES": (PriceLevel(.85, 1000.),),
            "NO": (PriceLevel(bid, 1000.),)})
    policy._quotes = deque(points, maxlen=2048)
    return policy, intent, snapshot
