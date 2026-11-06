"""Explicit mission premises for tests that already script physical detectors.

This is a test input, not a second production policy or an inference from the
fixture's prices. Raw-source/seed integration and recorded causal-model tests
use the real MissionContext instead. Accounting, partial-fill and lifecycle
tests can state a known physical purpose without also simulating 30 minutes
of source history in each unrelated execution test.
"""
from copy import deepcopy


class ExplicitMissionContext:
    def __init__(self, *, side="YES", parent_id="FIXTURE_PARENT", terminal=False):
        self.side, self.parent_id, self.terminal = side, parent_id, terminal
        self._last_context = {}

    def record_reacquisition(self, *, side, source_ms, continuity_generation, basis, held_missions):
        """This fixed execution premise does not model interrupted parents.

        A runtime callback cannot invent a bridge in these accounting/custody
        fixtures. Real source-reset and bridge behavior belongs to the actual
        MissionContext integration tests, which do not install this helper.
        """
        context = deepcopy(self._last_context)
        context["reacquisition_review"] = {
            "reason": "EXPLICIT_FIXTURE_HAS_NO_INTERRUPTED_SCOPE",
            "source_ms": source_ms, "continuity_generation": continuity_generation,
            "basis": basis, "links_created": []}
        return context

    def observe(self, metadata, *, ticker, open_ts, close_ts, target, now_ts, **unused):
        source = float((metadata.get("current_geometry") or {}).get("epoch_ms", now_ts*1000))
        generation = metadata.get("geometry_continuity_generation", 0)
        side = metadata.get("fixture_parent_side", self.side)
        opposite = "NO" if side == "YES" else "YES"
        parent_id = metadata.get("fixture_parent_id", self.parent_id)
        terminal = metadata.get("fixture_parent_terminal", self.terminal)
        known = min(source, float(metadata.get("fixture_parent_known_ms", source)))
        proof = {"qualified": terminal, "scope_id": parent_id, "side": side,
            "source_ms": source, "known_ms": source, "continuity_generation": generation,
            "reason": "EXPLICIT_TEST_PARENT_TERMINAL", "evidence": {"scripted_test_premise": True}}
        parent = {"id": parent_id, "side": side, "status": "ACTIVE", "known_ms": known,
            "supported": not terminal, "invalidated": False, "terminal": proof,
            "entry_edge": proof}
        parents = {parent_id: parent}
        successor = None
        if terminal:
            successor = {"id": parent_id+":NEXT", "side": opposite, "status": "ANTICIPATED",
                "known_ms": source, "predecessor_id": parent_id, "supported": True,
                "invalidated": False, "terminal": {"qualified": False}}
            parent["successor"] = successor
            parents[successor["id"]] = successor
        candidates = {}
        for value in ("YES", "NO"):
            incoming = bool(terminal and value == opposite)
            continuing = bool(not terminal and value == side)
            candidates[value] = {"side": value,
                "classification": "PARENT_EDGE_RETURN" if incoming else
                    "MAIN_CONTINUATION" if continuing else "UNRESOLVED",
                "qualified_edge": incoming, "entry_location_qualified": incoming or continuing,
                "continuation_supported": continuing, "current_progress_supported": continuing,
                "parent_leg_id": successor["id"] if incoming else parent_id,
                "swing_id": "FIXTURE_NATIVE", "source_ms": source,
                "destination": {"kind": "PARENT_TERMINAL"}, "continuity_generation": generation}
        context = {"version": "EXPLICIT_TEST_INPUT", "current": metadata.get("physical_current") is True,
            "source_ms": source, "continuity_generation": generation,
            "parent": parent, "parents_by_id": parents,
            "local": {"arc_id": "FIXTURE_NATIVE"}, "candidates": candidates,
            "contract": {"ticker": ticker, "open_ts": open_ts, "close_ts": close_ts,
                "target": target, "thesis_side": opposite if terminal else side,
                "reason": "SCRIPTED_MISSION_PREMISE_FOR_EXECUTION_TEST"},
            "prior_contracts": []}
        self._last_context = deepcopy(context)
        return context
