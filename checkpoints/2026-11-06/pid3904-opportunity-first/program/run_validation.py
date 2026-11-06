"""Run the original, recorded original, and input-driven replay fully offline.

Usage: python run_validation.py --out validation_run
The output directory must be new. This command never starts a PAPER feed,
opens credentials, or invokes a live launcher.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager, redirect_stdout
from dataclasses import replace
import json
from pathlib import Path
import platform
import socket
import sys
import time
from types import SimpleNamespace
import unittest

from engine_replay import (ROOT, SOURCE_ROOT, ClockProxy, RecordedEngine, ReplayMismatch,
                           ScriptClock, compare_directories, replay, runtime,
                           runtime_clock, source_hashes, verify_bundled_source)
from bounded_tape import TapeWriter, iter_tape
from input_codec import pin
from synthetic_session import BASE, RUN_ID, calls, fixture_metadata


@contextmanager
def network_forbidden():
    def denied(*args, **kwargs):
        raise RuntimeError("OFFLINE_VALIDATION_NETWORK_FORBIDDEN")
    original_connect = socket.socket.connect
    original_create = socket.create_connection
    original_resolve = socket.getaddrinfo
    socket.socket.connect = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.create_connection = original_create
        socket.getaddrinfo = original_resolve


def stats(values):
    values = sorted(values)
    if not values:
        return {"count": 0}
    def quantile(q):
        return round(values[int((len(values) - 1) * q)], 4)
    return {"count": len(values), "median_us": quantile(.5), "p95_us": quantile(.95),
            "p99_us": quantile(.99), "max_us": round(values[-1], 4)}


def summarize(run_dir):
    ledger = json.loads((run_dir / "PAPER_LEDGER.json").read_text(encoding="utf-8"))
    journal = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((run_dir / "paper_journal").glob("*.json"))]
    decisions = Counter()
    floors = 0
    process_count = 0
    with (run_dir / "decisions.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            process_count += 1
            for decision in row["decisions"]:
                decisions[decision["decision"]["reason"]] += 1
                floors += len(decision.get("floors", []))
    events = [{key: event.get(key) for key in
               ("event", "ticker", "position_id", "side", "qty", "price", "reason", "timestamp")}
              for event in ledger["events"]]
    custody = [row["event"] for row in journal if row["kind"] == "CUSTODY_TRANSITION"]
    return {"process_calls": process_count, "journal_records": len(journal),
            "journal_kinds": dict(Counter(row["kind"] for row in journal)),
            "financial_events": events, "floor_observations_in_decisions": floors,
            "decision_reasons": dict(decisions), "final_open_positions": len(ledger["positions"]),
            "final_cash_synthetic_only": ledger["cash"], "fees_synthetic_only": ledger["fees_paid"],
            "custody_transitions": [{key: event.get(key) for key in
                                      ("position_id", "previous_state", "state", "reason")}
                                     for event in custody],
            "promotion_events": sum(event.get("state") == "PROMOTED_MAIN" for event in custody),
            "profitability_evidence": False}


def run_original(parent):
    run_dir = parent / RUN_ID
    run_dir.mkdir(parents=True)
    engine = None
    before = time.perf_counter()
    with (parent / "console.txt").open("w", encoding="utf-8") as output, redirect_stdout(output):
        try:
            with runtime_clock(SimpleNamespace(time=ScriptClock(BASE + 1199.75), sleep=time.sleep)):
                engine = runtime.ToolRackPaperEngine(run_dir, source_root=SOURCE_ROOT)
            for method, arguments, base in calls():
                with runtime_clock(SimpleNamespace(time=ScriptClock(base), sleep=time.sleep)):
                    getattr(engine, method)(**arguments)
            with runtime_clock(SimpleNamespace(time=ScriptClock(BASE + 2702.25), sleep=time.sleep)):
                engine.close(reason="SYNTHETIC_OFFLINE_COMPLETE")
        finally:
            if engine is not None and not engine.executor._closed:
                engine.close(reason="VALIDATION_ABORTED")
    return run_dir, time.perf_counter() - before


def run_recorded(parent, tape_path):
    parent.mkdir(parents=True)
    before = time.perf_counter()
    with (parent / "console.txt").open("w", encoding="utf-8") as output, redirect_stdout(output):
        recorded = RecordedEngine(parent / RUN_ID, tape_path,
            input_kind="SYNTHETIC_ENGINE_BOUNDARY_SESSION", clock_supplier=ScriptClock(BASE + 1199.75))
        try:
            for method, arguments, base in calls():
                recorded.invoke(method, arguments, clock_supplier=ScriptClock(base))
            manifest = recorded.close(reason="SYNTHETIC_OFFLINE_COMPLETE",
                                      clock_supplier=ScriptClock(BASE + 2702.25))
        except BaseException:
            recorded.writer.fail("VALIDATION_ABORTED")
            if not recorded.engine.executor._closed:
                recorded.engine.close(reason="VALIDATION_ABORTED")
            recorded.writer.close()
            raise
    metrics = recorded.metrics
    total = [a + b + c for a, b, c in zip(metrics["pin_us"], metrics["finish_enqueue_us"],
                                         metrics["clock_read_us"])]
    return recorded.run_dir, manifest, {
        "pin_call": stats(metrics["pin_us"]),
        "finish_and_enqueue": stats(metrics["finish_enqueue_us"]),
        "clock_recording_including_supplier": stats(metrics["clock_read_us"]),
        "measured_capture_work": stats(total),
        "clock_read_count": metrics["clock_read_count"],
        "elapsed_seconds": round(time.perf_counter() - before, 6),
        "notes": ["Includes synchronous history/auxiliary-input detachment.",
                  "No tracemalloc during latency measurement.",
                  "Clock read measurement includes the synthetic clock supplier.",
                  "No Commander/ToolRack collection traversals or state-witness hashing.",
                  "Observed local timings, not hard latency bounds or acceptance on another machine."]}


def altered_input_control(tape_path, out, reference_dir):
    """Re-author a three-call negative fixture with one different entry book.

    This intentionally gets a valid new capture hash chain, so rejection must
    come from original-engine output comparison rather than damaged tape bytes.
    It uses the recorded init, first process, and close calls; it is explicitly
    a short authored negative fixture, not a modified full historical session.
    """
    header, stream = iter_tape(tape_path, expected_source_hashes=source_hashes())
    initial = first = last = None
    for envelope in stream:
        method = envelope["call"]["method"]
        if method == "init":
            initial = envelope
        elif method == "process" and first is None:
            first = envelope
        elif method == "close":
            last = envelope
    first = dict(first)
    call = dict(first["call"])
    arguments = dict(call["arguments"])
    feed = arguments["feed"]
    # Ask increases from 10c to 11c; all other authored source inputs remain.
    levels = (replace(feed.book.yes_bids[0], price=.89),) + feed.book.yes_bids[1:]
    arguments["feed"] = replace(feed, book=replace(feed.book, yes_bids=levels))
    call["arguments"] = arguments
    first["call"] = call
    negative_path = out / "altered_input.jsonl"
    header = {**header, "input_kind": "AUTHORED_THREE_CALL_NEGATIVE_CONTROL"}
    writer = TapeWriter(negative_path, header=header, queue_capacity=8)
    for envelope in (initial, first, last):
        writer.submit(pin(envelope))
    manifest = writer.close()
    if not manifest.get("complete"):
        raise RuntimeError("NEGATIVE_CONTROL_CAPTURE_FAILED")
    with (out / "altered_console.txt").open("w", encoding="utf-8") as output, redirect_stdout(output):
        try:
            replay(negative_path, out / "altered_replay", reference_dir=reference_dir)
        except ReplayMismatch as exc:
            if exc.report["call_index"] != 2 or exc.report.get("reason") != "FIRST_ENGINE_OUTPUT_DIVERGENCE":
                raise
            return {"pass": True, "change": "First NO ask 0.10 -> 0.11", "report": exc.report,
                    "scope": "Three-call authored negative fixture with valid integrity chain"}
    raise AssertionError("ALTERED_INPUT_WAS_NOT_DETECTED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must name a new directory; existing evidence is never overwritten")
    args.out.mkdir(parents=True)
    verify_bundled_source()
    report = {"date": "2026-11-04", "fixture": fixture_metadata(),
              "environment": {"python": platform.python_version(), "platform": platform.platform()},
              "source_files_verified": len(source_hashes()), "strategy_modified": False,
              "trading_release": False, "real_market_replay": False,
              "native_transport_replay": False, "pass": False}
    try:
        with network_forbidden():
            print("1/4: unchanged original engine", flush=True)
            original, elapsed = run_original(args.out / "original")
            report["original_elapsed_seconds"] = round(elapsed, 6)
            print("2/4: unchanged engine with ordered input capture", flush=True)
            tape_path = args.out / "engine_inputs.jsonl"
            recorded, manifest, timing = run_recorded(args.out / "recorded", tape_path)
            report["capture_manifest"] = manifest
            report["capture_timing"] = timing
            report["original_vs_recorded"] = compare_directories(original, recorded)
            if not report["original_vs_recorded"]["pass"]:
                raise AssertionError("ORIGINAL_VS_RECORDED_DIVERGED")
            print("3/4: fresh unchanged engine from verified captured inputs", flush=True)
            with (args.out / "replay_console.txt").open("w", encoding="utf-8") as output, redirect_stdout(output):
                report["replay"] = replay(tape_path, args.out / "replayed", reference_dir=recorded)
            report["recorded_vs_replay"] = compare_directories(recorded, Path(report["replay"]["run_dir"]))
            if not report["recorded_vs_replay"]["pass"]:
                raise AssertionError("RECORDED_VS_REPLAY_FILE_DIVERGENCE")
            report["observed_lifecycle"] = summarize(recorded)
            print("4/4: first-divergence and evidence-integrity controls", flush=True)
            report["altered_input_control"] = altered_input_control(tape_path, args.out, recorded)
            integrity_suites = ("test_capture_integrity.py", "test_snapshot_delta.py", "test_capture_session.py")
            suite = unittest.TestSuite(unittest.defaultTestLoader.discover(str(ROOT), pattern=pattern)
                                       for pattern in integrity_suites)
            with (args.out / "integrity_tests.txt").open("w", encoding="utf-8") as handle:
                result = unittest.TextTestRunner(stream=handle, verbosity=2).run(suite)
            report["integrity_tests"] = {"pass": result.wasSuccessful(), "run": result.testsRun,
                                         "failures": len(result.failures), "errors": len(result.errors),
                                         "suites": list(integrity_suites)}
            report["pass"] = bool(result.wasSuccessful() and result.testsRun > 0
                                  and manifest.get("complete") and report["replay"]["pass"])
    except BaseException as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        if isinstance(exc, ReplayMismatch):
            report["failure"]["first_divergence"] = exc.report
        raise
    finally:
        (args.out / "validation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "report": str(args.out / "validation_report.json"),
                      "process_calls": report["observed_lifecycle"]["process_calls"],
                      "journal_records": report["observed_lifecycle"]["journal_records"]}, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
