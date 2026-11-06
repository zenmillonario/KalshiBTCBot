"""Exact PID3904 held-position controls for collection at the held leg's scale.

These are source-bound decisions, not a hypothetical replay or P&L claim.
Synthetic perturbations are labelled and change only the evidence under test.
"""
import copy
import gzip
import json
from dataclasses import replace
from pathlib import Path
import unittest

from strategy_core.commander import OneCommander
from strategy_core.custody_evidence import build_custody_evidence
from strategy_core.types import Action, MarketSnapshot


def source_case(position_id="6"):
    path = Path(__file__).parent / "fixtures" / "pid3904_parent_custody.json.gz"
    case = json.loads(gzip.decompress(path.read_bytes()))["cases"][position_id]
    frame = case["frame"]
    snap = MarketSnapshot(
        now_ts=frame["now_ts"], ticker=frame["ticker"],
        contract_age_s=frame["contract_age_s"], **frame["book_top"],
        metadata=frame["physical_metadata"], quote_current=True,
        depth_available=True, yes_sell_allowed=True, no_sell_allowed=True,
    )
    return snap, case["preexit_position"]


class PID3904ParentCollection(unittest.TestCase):
    def test_source_rail_six_does_not_collect_live_parent_at_child_terminal(self):
        snapshot, position = source_case()
        self.assertFalse(position["exit_required"])
        self.assertIsNone(position["floor_bid"])
        self.assertTrue(snapshot.metadata["mountain"]["primary_collection_terminal_qualified"])
        evidence = build_custody_evidence(position, snapshot)
        self.assertTrue(evidence["collection_parent_geometry_current"])
        self.assertEqual(evidence["collection_scope"], "CURRENT_MAIN_PARENT")
        self.assertFalse(evidence["held_leg_terminal"])
        self.assertEqual(evidence["recommendation"], "HOLD")
        decision = OneCommander().decide_position((), snapshot, position)
        self.assertIs(decision.action, Action.HOLD)

    def test_source_rail_four_opposite_child_is_not_held_parent_terminal(self):
        snapshot, position = source_case("4")
        self.assertEqual(snapshot.metadata["mountain"]["owner_side"], "NO")
        evidence = build_custody_evidence(position, snapshot)
        self.assertTrue(evidence["collection_parent_geometry_current"])
        self.assertFalse(evidence["held_leg_terminal"])
        self.assertNotEqual(evidence["reason"], "COMMANDER_MOUNTAIN_ONLY_HELD_LEG_TERMINAL_EDGE")
        # This does not assert the turning parent is healthy or promise a gain.

    def test_synthetic_true_new_parent_terminal_still_collects(self):
        snapshot, position = source_case()
        metadata = copy.deepcopy(snapshot.metadata)
        geometry = metadata["mission_context"]["parent"]["geometry"]
        extreme_ms = (position["entry_time"] + 5.0) * 1000.0
        geometry.update(primary_collection_terminal_qualified=True,
                        terminal_evidence_qualified=True, mature_edge=True,
                        edge_window_active=True,
                        edge_id=geometry["current_arc_id"] + ":" + str(int(extreme_ms)),
                        edge_extreme_ms=extreme_ms)
        altered = replace(snapshot, metadata=metadata)
        evidence = build_custody_evidence(position, altered)
        self.assertTrue(evidence["held_leg_terminal"])
        self.assertEqual(evidence["recommendation"], "COLLECT")
        decision = OneCommander().decide_position((), altered, position)
        self.assertIs(decision.action, Action.EXIT)
        self.assertEqual(decision.intent.reason, "COMMANDER_MOUNTAIN_ONLY_HELD_LEG_TERMINAL_EDGE")

    def test_synthetic_parent_geometry_identity_is_mandatory(self):
        snapshot, position = source_case()
        changes = ({"current": False}, {"source_ms": 0.0},
                   {"continuity_generation": 999}, {"current_arc_id": "OTHER_PARENT"},
                   {"owner_side": "NO"}, {"current_btc": 1.0},
                   {"current_ema9": 1.0}, {"current_ema30": 1.0})
        for change in changes:
            with self.subTest(change=change):
                metadata = copy.deepcopy(snapshot.metadata)
                geometry = metadata["mission_context"]["parent"]["geometry"]
                geometry.update(primary_collection_terminal_qualified=True,
                                mature_edge=True, edge_window_active=True)
                geometry.update(change)
                evidence = build_custody_evidence(position, replace(snapshot, metadata=metadata))
                self.assertFalse(evidence["collection_parent_geometry_current"])
                self.assertFalse(evidence["held_leg_terminal"])

    def test_missing_parent_or_mismatched_mission_cannot_fall_back_to_child_exit(self):
        snapshot, position = source_case()
        for key, value in (("parent", {}), ("continuity_generation", 999), ("current", False)):
            with self.subTest(key=key):
                metadata = copy.deepcopy(snapshot.metadata)
                metadata["mission_context"][key] = value
                evidence = build_custody_evidence(position, replace(snapshot, metadata=metadata))
                self.assertEqual(evidence["collection_scope"], "MAIN_PARENT_UNVERIFIED")
                self.assertFalse(evidence["collection_parent_geometry_current"])
                self.assertFalse(evidence["held_leg_terminal"])

    def test_missing_unparseable_or_future_parent_edge_cannot_collect(self):
        snapshot, position = source_case()
        current = snapshot.metadata["mission_context"]["parent"]["geometry"]
        for edge_id in ("", "UNKNOWN", "OTHER_PARENT:" + current["edge_id"].rsplit(":", 1)[1],
                        current["current_arc_id"] + ":" + str((snapshot.now_ts + 10) * 1000)):
            with self.subTest(edge_id=edge_id):
                metadata = copy.deepcopy(snapshot.metadata)
                metadata["mission_context"]["parent"]["geometry"].update(
                    primary_collection_terminal_qualified=True, mature_edge=True,
                    edge_window_active=True, edge_id=edge_id)
                self.assertFalse(build_custody_evidence(position, replace(snapshot, metadata=metadata))["held_leg_terminal"])

    def test_synthetic_preentry_parent_edge_does_not_close_new_position(self):
        snapshot, position = source_case()
        metadata = copy.deepcopy(snapshot.metadata)
        metadata["mission_context"]["parent"]["geometry"].update(
            primary_collection_terminal_qualified=True, mature_edge=True,
            edge_window_active=True,
            edge_id="PARENT_EDGE:" + str((position["entry_time"] - 1.0) * 1000.0))
        self.assertFalse(build_custody_evidence(position, replace(snapshot, metadata=metadata))["held_leg_terminal"])

    def test_objective_floor_and_latched_exit_keep_priority(self):
        snapshot, position = source_case()
        for flag in ("floor_breached", "exit_required"):
            with self.subTest(flag=flag):
                held = dict(position, exit_required=flag == "exit_required")
                decision = OneCommander().decide_position((), snapshot, held,
                                                         floor_breached=flag == "floor_breached")
                self.assertIs(decision.action, Action.EXIT)
                self.assertNotEqual(decision.intent.reason, "COMMANDER_MOUNTAIN_ONLY_HELD_LEG_TERMINAL_EDGE")


if __name__ == "__main__":
    unittest.main()
