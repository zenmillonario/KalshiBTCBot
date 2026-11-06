"""Bounded recorded-case acceptance for the approved PID17224 A/B/C changes.

This runs the regression suites against hash-checked selected records and
explicitly labelled source-clock and measured-premise variants. Unmodified
records with future source clocks or insufficient wall proof must WAIT. The
derived Release and Heist controls exercise the real PAPER executioner in
temporary ledgers. This is not a full session replay or a profit claim.

Run with no arguments, or supply --output DIRECTORY. The parent process gives
the complete worker 50 seconds and writes report.json on success or failure.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parent
WORKER_TIMEOUT_SECONDS = 50
PASS_MARKER = "PID17224 APPROVED CORRECTIONS CONSTRUCT PASS"
FAIL_MARKER = "PID17224 APPROVED CORRECTIONS CONSTRUCT FAILED"
SUITES = (
    ("RECORDED_SOURCE_PROOF", "tests.tool_rack.test_pid17224_release_heist.PID17224RawSourceProofTests"),
    ("A_RELEASE_CUSTODY", "tests.tool_rack.test_pid17224_release_heist.PID17224ReleaseCustodyTests"),
    ("B_MAIN_PARENT_QUALITY", "tests.tool_rack.test_pid17224_main_returns.PID17224MainReturnTests"),
    ("C_LATER_HEIST", "tests.tool_rack.test_pid17224_release_heist.PID17224LaterHeistTests"),
)
REQUIRED_METHODS = {
    "test_4561_release_resolves_role_and_mission_before_committed_fill",
    "test_4562_next_callback_holds_the_corrected_release",
    "test_4601_derived_release_mechanics_when_inventory_is_clear",
    "test_corrected_4561_custody_prevents_duplicate_4601_entry",
    "test_original_recorded_main_intent_cannot_bypass_the_commander_boundary",
    "test_recorded_bounce_does_not_erase_the_established_no_parent",
    "test_mirrored_up_parent_rejects_the_same_short_no_bounce",
    "test_derived_repeated_box_5377_and_5600_preserve_execution_and_tactical_role",
    "test_original_future_source_and_partial_boxes_do_not_admit",
    "test_clock_alignment_alone_does_not_invent_repeated_walls",
    "test_first_and_repeat_callbacks_stay_observation_later_swing_can_qualify",
    "test_strong_opposing_release_check_still_runs_after_pause_exception",
}


class CaseResults(unittest.TestResult):
    """Keep one JSON outcome per test method, retaining subtest failures."""

    def __init__(self, groups):
        super().__init__()
        self.groups = groups
        self.cases = []
        self.current = None
        self.started = 0.0

    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()
        self.current = {"id": test.id(), "group": self.groups[test.id()],
                        "status": "RUNNING", "subtests": []}
        self.cases.append(self.current)

    def stopTest(self, test):
        self.current["elapsed_seconds"] = round(time.monotonic() - self.started, 6)
        super().stopTest(test)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.current["status"] = "PASS"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.current.update(status="FAIL", detail=self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        if self.current is None or self.current["id"] != test.id():
            # Import/setUpClass errors are not ordinary test callbacks.
            self.cases.append({"id": test.id(), "group": "SUITE_SETUP", "status": "ERROR",
                               "detail": self._exc_info_to_string(err, test)})
        else:
            self.current.update(status="ERROR", detail=self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.current is None:
            self.cases.append({"id": test.id(), "group": "SUITE_SETUP",
                               "status": "SKIP", "detail": reason})
        else:
            self.current.update(status="SKIP", detail=reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.current.update(status="EXPECTED_FAILURE", detail=self._exc_info_to_string(err, test))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.current["status"] = "UNEXPECTED_SUCCESS"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        entry = {"id": subtest.id(), "status": "PASS" if err is None else "FAIL"}
        if err is not None:
            self.current["status"] = "FAIL"
            entry["detail"] = self._exc_info_to_string(err, subtest)
        self.current["subtests"].append(entry)


def _tests(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from _tests(test)
        else:
            yield test


def run_controls():
    suite = unittest.TestSuite()
    groups = {}
    for label, name in SUITES:
        selected = unittest.defaultTestLoader.loadTestsFromName(name)
        groups.update({test.id(): label for test in _tests(selected)})
        suite.addTests(selected)
    expected = suite.countTestCases()
    methods = {name.rsplit(".", 1)[-1] for name in groups}
    missing = sorted(REQUIRED_METHODS - methods)
    if missing:
        raise RuntimeError("Required recorded acceptance controls missing: " + ", ".join(missing))

    result = CaseResults(groups)
    started = time.monotonic()
    suite.run(result)
    success = (expected > 0 and result.testsRun == expected and result.wasSuccessful()
               and not result.skipped and not result.expectedFailures
               and len(result.cases) == expected
               and all(case["status"] == "PASS" for case in result.cases))
    group_results = {}
    for label, _ in SUITES:
        cases = [case for case in result.cases if case["group"] == label]
        group_results[label] = {"tests_run": len(cases),
                                "passed": sum(case["status"] == "PASS" for case in cases)}

    from tests.tool_rack.pid17224_recorded_fixtures import PATH, provenance, record
    recorded_sequences = (4561, 4562, 4601, 5377, 5600, 6087)
    source_files = (
        "CONSTRUCT_PID17224_APPROVED_CORRECTIONS.py",
        "strategy_core/commander.py", "strategy_core/commander_candidates.py",
        "strategy_core/directional_parent.py", "strategy_core/paper_execution.py",
        "strategy_core/paper_runtime.py", "strategy_core/tool_rack.py", "strategy_core/types.py",
        "tests/tool_rack/pid17224_recorded_fixtures.py",
        "tests/tool_rack/test_pid17224_main_returns.py",
        "tests/tool_rack/test_pid17224_release_heist.py",
    )
    return {
        "schema": "TACHYOS_PID17224_APPROVED_CORRECTIONS_CONSTRUCT_V1",
        "status": "PASS" if success else "FAIL",
        "scope": "Recorded provenance denials and explicitly derived source-clock/measured-premise admission, custody and PAPER execution controls",
        "full_session_replay": False,
        "counterfactual_profit_claimed": False,
        "paper_only": True,
        "expected_tests": expected,
        "tests_run": result.testsRun,
        "passed": sum(case["status"] == "PASS" for case in result.cases),
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "groups": group_results,
        "fixture_sha256": hashlib.sha256(PATH.read_bytes()).hexdigest(),
        "recorded_controls": [{"sequence": sequence, "record_sha256": record(sequence)["sha256"],
                               **provenance(sequence)} for sequence in recorded_sequences],
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in source_files},
        "evidence_notes": [
            "The explicitly derived source-clock-aligned Release 4561 is booked through PaperExecutioner; derived 4562 must HOLD that same whole lot.",
            "The derived Release 4601 has a current source clock, sufficient runway and target below both EMA rails; clear inventory admits it and holding derived 4561 prevents duplication.",
            "6087 boundary tests use the original entry intent and original physical snapshot.",
            "6087 generator tests restore only the exact same-decision recent_level_match cache "
            "copied into the recorded intent; the unchecked original route is also asserted.",
            "Mirror and completed-transfer controls are labelled derived contemporaneous inputs.",
            "Derived 5377 and 5600 add six distinct numerical wall/center visits and current source clocks before testing admission and native-book PAPER fills; no later profit is assumed.",
            "Raw original future-source records remain WAIT; aligning time alone does not invent repeated-wall proof.",
            "First/repeated fade memory, current qualified visit, Release, floor, stop, inventory, "
            "source, quote, depth, permission, price and stale-command controls remain required.",
        ],
        "cases": result.cases,
    }


def worker():
    captured = io.StringIO()
    try:
        with redirect_stdout(captured), redirect_stderr(captured):
            report = run_controls()
    except Exception as exc:
        report = {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}
    report["captured_test_output"] = captured.getvalue()
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("PID17224_APPROVED_CORRECTIONS_CONSTRUCT_RESULTS"))
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker()

    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--worker"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            timeout=WORKER_TIMEOUT_SECONDS, check=False,
        )
        try:
            report = json.loads(completed.stdout)
        except (ValueError, TypeError):
            report = {"status": "ERROR", "error": "Worker did not return a JSON report",
                      "worker_stdout": completed.stdout}
        report["worker_returncode"] = completed.returncode
        report["worker_stderr"] = completed.stderr
        if completed.returncode != 0 and report.get("status") == "PASS":
            report.update(status="ERROR", error="Worker failed despite a PASS report")
    except subprocess.TimeoutExpired:
        report = {"status": "TIMEOUT", "error": "Recorded-case worker exceeded its 50-second limit"}
    except OSError as exc:
        report = {"status": "ERROR", "error": f"Worker could not start: {exc}"}

    report["worker_timeout_seconds"] = WORKER_TIMEOUT_SECONDS
    report["total_elapsed_seconds"] = round(time.monotonic() - started, 6)
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / "report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    success = report.get("status") == "PASS"
    print(json.dumps({"status": report["status"], "tests_run": report.get("tests_run", 0),
                      "passed": report.get("passed", 0), "groups": report.get("groups", {}),
                      "elapsed_seconds": report["total_elapsed_seconds"],
                      "report": str(path)}, sort_keys=True))
    print(PASS_MARKER if success else FAIL_MARKER)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
