"""Offline readiness gate for the optional 45-minute PAPER capture candidate.

Run with the same Python interpreter that will run the candidate:
    python prepare_next_run.py --out <new-offline-readiness-directory>

Without --out, results go beneath OFFLINE_READINESS in the launcher's output
root. This command never changes LAST_RUN, starts a feed, reads credentials,
or opens an account connection. It runs one fresh three-way engine proof and
then a finite 60-second recorder-only load. Exit zero means the measured short
candidate gates passed on this machine; it is not a hard latency guarantee,
strategy acceptance, or authorization for a six-hour run.
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid

from engine_replay import ROOT, source_hashes, verify_bundled_source
from bounded_tape import TapeWriter, iter_tape
from input_codec import pin, pin_call
from run_validation import network_forbidden
from TOOL_RACK_PAPER import default_output_root
from strategy_core.marketdata.kalshi_public import MarketInfo
from strategy_core.paper_execution import PaperBook, PriceLevel
from strategy_core.paper_feed import FeedSnapshot, freeze_data


HZ = 4
LOAD_SECONDS = 60
WARMUP_SECONDS = 10
GEOMETRY_ROWS = 3600
COMPLETED_CANDLES = 360
CAPTURE_MAX_BYTES = 512_000_000
QUEUE_CAPACITY = 64
DISPATCH_BUDGET_US = 250_000
REQUIRED_INTEGRITY_TESTS = 18
SHORT_ENTRY_SECONDS = 45 * 60
DRAIN_ALLOWANCE_SECONDS = 17 * 60
SHORT_TOTAL_SECONDS = SHORT_ENTRY_SECONDS + DRAIN_ALLOWANCE_SECONDS
LONG_ENTRY_SECONDS = 6 * 60 * 60
STORAGE_HEADROOM = 1.5
FREE_SPACE_RESERVE_BYTES = 1 << 30
SYNTHETIC_START = 1_800_000_030.0
REPORT_NAME = "OFFLINE_READINESS_REPORT.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def _utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def statistics(values):
    ordered = sorted(values)
    if not ordered:
        return {"count": 0}
    return {
        "count": len(ordered),
        "median_us": round(ordered[int((len(ordered) - 1) * .5)], 3),
        "p99_us": round(ordered[math.ceil(len(ordered) * .99) - 1], 3),
        "max_us": round(ordered[-1], 3),
    }


class LoadInputs:
    """Source-shaped synthetic inputs; no strategy scenarios or engine calls.

    Geometry rows use the actual source schema and retain private immutable
    row objects, as DirectPaperFeed does. Every frame contains the whole rolling
    window. Historical candles remain mutable until input_codec.pin copies them.
    The 360 completed bars exceed the usual 240-bar seed plus the 62-minute
    short-run planning window. The load crosses a minute boundary and revises
    two completed bars, so delta capture cannot assume append-only history.
    """

    def __init__(self):
        self.last_second = int(SYNTHETIC_START)
        self.rows = deque((self._row(second) for second in range(
            self.last_second - GEOMETRY_ROWS + 1, self.last_second + 1)),
            maxlen=GEOMETRY_ROWS)
        self.minute = int(SYNTHETIC_START // 60) * 60
        self.candles = [self._bar(opened, complete=True) for opened in range(
            self.minute - COMPLETED_CANDLES * 60, self.minute, 60)]
        self.candles.append(self._bar(self.minute, complete=False))
        self.geometry_appends = self.geometry_evictions = 0
        self.candle_appends = self.candle_evictions = self.candle_revisions = 0
        self.market = MarketInfo(
            "SYNTHETIC-RECORDER-LOAD", self.minute, self.minute + 900, "active",
            target=80000.0, target_source="KALSHI_MARKET_FLOOR_STRIKE")

    @staticmethod
    def _row(second):
        offset = second - SYNTHETIC_START
        stamp = _utc(second)
        return freeze_data({
            "timestamp": stamp, "epoch_ms": second * 1000.0,
            "btc_price": 80000.0 + offset * .01,
            "ema9": 79999.0 + offset * .01,
            "ema30": 79996.0 + offset * .01,
            "product_id": "BTC-USD", "geometry_source": "COINBASE_PUBLIC_TRADES_INDEPENDENT",
            "price_kind": "BTC_TRADE_NOT_CONTRACT_BID", "exchange_trade_utc": stamp,
            "received_utc": _utc(second + .02), "received_monotonic": 100000.0 + offset,
            "exchange_to_receive_seconds": .02, "connection_epoch": 1,
            "sequence_num": second, "last_trade_id": str(second),
            "sample_serial": second, "sample_policy": "LAST_TRADE_IN_RECEIVED_UPDATE_AT_MOST_1HZ",
            "completed_seed_bars": 240, "completed_live_minutes": 60,
            "current_minute": int(second // 60) * 60,
            "ema_method": "SMA_SEED_9_30_ROLLING_240_COMPLETED_MINUTE_CLOSES_PLUS_PROVISIONAL",
            "ema_clock": "EXCHANGE_TRADE_TIME", "engine_ema_equality_claim": False,
            "seed_metadata": {"completed_bars": 240, "synthetic": True,
                              "source": "SYNTHETIC_SCHEMA_ONLY"},
            "batch_trade_count": 5, "source_observed_ts": second + .02,
            "source_row_id": f"COINBASE:1:{second}",
            "historical_seed_is_not_forward_observation": True,
            "synthetic": True, "not_venue_evidence": True,
        })

    @staticmethod
    def _bar(opened, *, complete):
        price = 80000.0 + (opened - SYNTHETIC_START) * .01
        return {
            "time": float(opened), "open": price, "high": price + 1,
            "low": price - 1, "close": price + .25,
            "e9": price - 1, "e30": price - 4,
            "known_at": float(opened + 60 if complete else opened),
            "complete": complete, "full_minute": complete,
            "connection_epoch": 1, "source": "COINBASE_VALIDATED_HISTORY",
            "historical_seed_is_not_forward_observation": True,
            "synthetic": True, "not_venue_evidence": True,
        }

    def frame(self, index):
        timestamp = SYNTHETIC_START + index / HZ
        while self.last_second < int(timestamp):
            self.last_second += 1
            self.rows.append(self._row(self.last_second))
            self.geometry_appends += 1
            self.geometry_evictions += 1
        minute = int(timestamp // 60) * 60
        if minute != self.minute:
            self.candles[-1].update(complete=True, full_minute=True,
                                    known_at=float(self.minute + 60))
            self.candles.append(self._bar(minute, complete=False))
            self.candles.pop(0)
            self.minute = minute
            self.candle_appends += 1
            self.candle_evictions += 1
        current = self.candles[-1]
        close = 80000.0 + index * .001
        current.update(close=close, high=max(current["high"], close),
                       low=min(current["low"], close), known_at=timestamp,
                       e9=close - 1, e30=close - 4)
        if index in (15 * HZ, 45 * HZ):
            revised = self.candles[-10]
            revised["close"] += .125
            revised["high"] = max(revised["high"], revised["close"])
            revised["known_at"] = timestamp
            self.candle_revisions += 1
        adjustment = (index % 3) * .0001
        book = PaperBook(
            self.market.ticker, f"SYNTHETIC-NATIVE:{index}", timestamp, timestamp,
            tuple(PriceLevel(.78 - level * .005 + adjustment, 1000) for level in range(8)),
            tuple(PriceLevel(.18 - level * .005, 1000) for level in range(8)),
            self.market.close_ts,
            provenance=freeze_data({
                "sequence_checked": True, "snapshot_verified": True,
                "monotonic_receive_fresh": True, "received_monotonic": 100000.0 + index / HZ,
                "receive_age_seconds": 0.0, "receiver_generation": 1,
                "source_generation": index + 1, "seq": index + 1,
                "raw_depth_is_not_a_venue_fill": True,
                "synthetic": True, "not_venue_evidence": True,
            }))
        feed = FeedSnapshot(
            index + 1, timestamp, self.market, book, tuple(self.rows),
            freeze_data({
                "btc_current": True, "book_current": True,
                "geometry_rows": GEOMETRY_ROWS, "btc_connection_epoch": 1,
                "btc_geometry_age_seconds": timestamp - self.last_second,
                "btc_geometry_receive_age_seconds": timestamp - self.last_second,
                "entry_quote_available": True, "source_error": None,
                "btc": {"state": "SYNTHETIC_CURRENT", "epoch": 1},
                "native": {"state": "SYNTHETIC_CURRENT", "sequence_checked": True},
                "captured_together_without_producer_reread": True,
                "different_exchanges_are_not_claimed_simultaneous": True,
                "synthetic": True, "not_venue_evidence": True,
            }))
        return {"feed": feed, "historical_candles": self.candles,
                "entry_window_closed": False}, timestamp


def _envelope(method, arguments, clocks):
    # These scalar heads are recorder-load placeholders. No engine outcome is
    # claimed for this workload; the separate three-way proof executes it.
    return pin({"call": pin_call(method, arguments), "clocks": tuple(clocks),
                "expected": {"decision_seq": 0, "decision_sha256": "0" * 64,
                             "journal_seq": 0, "journal_sha256": "0" * 64}})


def _require_health(writer):
    health = writer.health()
    required = ("accepted", "written", "dropped", "backlog", "queue_highwater",
                "queue_capacity", "bytes", "max_bytes", "reason", "delta")
    if not isinstance(health, dict) or any(key not in health for key in required):
        raise RuntimeError("WRITER_HEALTH_FIELDS_REQUIRED")
    delta = health["delta"]
    if not isinstance(delta, dict) or not delta.get("enabled"):
        raise RuntimeError("BOUNDED_DELTA_CAPTURE_REQUIRED")
    if any(key not in delta for key in ("max_snapshot_rows", "max_snapshot_bytes",
                                        "geometry_rows", "historical_candles")):
        raise RuntimeError("DELTA_CACHE_ACCOUNTING_FIELDS_REQUIRED")
    for component in ("geometry_rows", "historical_candles"):
        if any(key not in delta[component] for key in ("rows", "bytes")):
            raise RuntimeError("DELTA_COMPONENT_ACCOUNTING_FIELDS_REQUIRED")
    return health


def recorder_load(out, hashes):
    inputs = LoadInputs()
    path = out / "recorder_load.jsonl"
    writer = TapeWriter(path, header={
        "input_kind": "SYNTHETIC_RECORDER_LOAD_NOT_ENGINE_REPLAY",
        "source_hashes": hashes, "run_id": "SYNTHETIC_RECORDER_4HZ",
        "initial_state": "NO_ENGINE_IN_RECORDER_LOAD",
        "boundary": "PINNED_INPUT_ENVELOPE_ONLY", "synthetic": True,
        "geometry_rows": GEOMETRY_ROWS, "completed_candles": COMPLETED_CANDLES,
    }, queue_capacity=QUEUE_CAPACITY, max_bytes=CAPTURE_MAX_BYTES)
    pin_times, submit_times, producer_times, preparation_times, lags = [], [], [], [], []
    health_samples = []
    before_close = baseline = None
    producer_error = None
    started = time.perf_counter()
    try:
        _require_health(writer)
        writer.submit(_envelope("init", {}, (SYNTHETIC_START - .25,)))
        for index in range(LOAD_SECONDS * HZ):
            remaining = started + index / HZ - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
            lag = max(0.0, time.perf_counter() - (started + index / HZ))
            lags.append(lag * 1_000_000)
            health = _require_health(writer)
            health_samples.append({"index": index, "elapsed_s": time.perf_counter() - started,
                                   "health": health})
            if index == WARMUP_SECONDS * HZ:
                baseline = health_samples[-1]
            if health["reason"] is not None or health["dropped"]:
                break
            before = time.perf_counter_ns()
            arguments, timestamp = inputs.frame(index)
            preparation_times.append((time.perf_counter_ns() - before) / 1000)
            before = time.perf_counter_ns()
            event = _envelope("process", arguments, (timestamp, timestamp + .00001))
            pinned = time.perf_counter_ns()
            accepted = writer.submit(event)
            submitted = time.perf_counter_ns()
            pin_times.append((pinned - before) / 1000)
            submit_times.append((submitted - pinned) / 1000)
            producer_times.append((submitted - before) / 1000)
            if not accepted:
                break
            if index and index % (15 * HZ) == 0:
                print(f"Recorder load: {index // HZ}/{LOAD_SECONDS}s; "
                      f"backlog={health['backlog']}; dropped={health['dropped']}", flush=True)
        if len(producer_times) == LOAD_SECONDS * HZ:
            remaining = started + LOAD_SECONDS - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
        before_close = _require_health(writer)
        writer.submit(_envelope("close", {"reason": "SYNTHETIC_RECORDER_LOAD_COMPLETE"},
                                (SYNTHETIC_START + LOAD_SECONDS,)))
    except BaseException as exc:
        writer.fail("READINESS_LOAD:" + type(exc).__name__)
        producer_error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        manifest = writer.close(timeout_s=10)
    elapsed = time.perf_counter() - started
    final_health = _require_health(writer)
    verified, verification_error = False, None
    if manifest.get("complete"):
        try:
            _, stream = iter_tape(path, expected_source_hashes=hashes)
            stream.close()
            verified = True
        except Exception as exc:
            verification_error = {"type": type(exc).__name__, "message": str(exc)}
    all_health = [sample["health"] for sample in health_samples] + [final_health]
    observed_cache = {}
    for component in ("geometry_rows", "historical_candles"):
        observed_cache[component] = {
            "max_rows": max(item["delta"][component]["rows"] for item in all_health),
            "max_canonical_bytes": max(item["delta"][component]["bytes"] for item in all_health),
        }
    baseline_bytes = baseline["health"]["bytes"] if baseline else manifest.get("bytes", 0)
    steady_seconds = max(0.0, LOAD_SECONDS - baseline["elapsed_s"]) if baseline else 0
    steady_bytes = max(0, manifest.get("bytes", 0) - baseline_bytes)
    steady_rate = steady_bytes / steady_seconds if steady_seconds else None
    return {
        "kind": "RECORDER_LOAD_ONLY_NOT_ENGINE_REPLAY", "requested_hz": HZ,
        "requested_seconds": LOAD_SECONDS, "process_calls": len(producer_times),
        "elapsed_seconds_including_writer_close": round(elapsed, 6),
        "geometry_rows_each_frame": GEOMETRY_ROWS,
        "historical_candles_each_frame": COMPLETED_CANDLES + 1,
        "mutations": {"geometry_appends": inputs.geometry_appends,
                      "geometry_evictions": inputs.geometry_evictions,
                      "candle_appends": inputs.candle_appends,
                      "candle_evictions": inputs.candle_evictions,
                      "completed_candle_revisions": inputs.candle_revisions},
        "pin": statistics(pin_times), "submit": statistics(submit_times),
        "producer_capture": statistics(producer_times),
        "fixture_preparation_excluded_from_capture": statistics(preparation_times),
        "scheduling_lag": statistics(lags),
        "steady_scheduling_lag": statistics(lags[WARMUP_SECONDS * HZ:]),
        "queue_highwater": max(item["queue_highwater"] for item in all_health),
        "max_backlog_including_inflight": max(item["backlog"] for item in all_health),
        "backlog_before_close": before_close["backlog"] if before_close else None,
        "initial_observed_bytes_at_warmup_end": baseline_bytes,
        "steady_measurement_seconds": steady_seconds,
        "steady_write_bytes_per_second": steady_rate,
        "whole_load_write_bytes_per_second": manifest.get("bytes", 0) / max(elapsed, .001),
        "manifest": manifest, "final_health": final_health,
        "cache_observed": observed_cache, "tape_integrity_verified": verified,
        "producer_error": producer_error, "verification_error": verification_error,
        "memory_scope": "Canonical row bytes retained by bounded delta caches, not Python process RSS or total allocator memory.",
        "measurement_scope": "Empirical capture-only work at 4Hz. Strategy, feed transport and future system load are outside this timing measurement.",
    }


def storage_projection(load, engine_bytes_per_process, seconds):
    steady_rate = load["steady_write_bytes_per_second"]
    if steady_rate is None:
        return None
    input_bytes = math.ceil(load["initial_observed_bytes_at_warmup_end"] + steady_rate * seconds)
    engine_bytes = math.ceil(engine_bytes_per_process * HZ * seconds)
    input_with_headroom = math.ceil(input_bytes * STORAGE_HEADROOM)
    engine_with_headroom = math.ceil(engine_bytes * STORAGE_HEADROOM)
    # Current input + replay's verified compact spool + an uncompressed ZIP
    # allowance. ZIP allowance also includes both engine-output copies.
    live_and_replay = 2 * engine_with_headroom
    temporary_zip = live_and_replay + input_with_headroom
    required = live_and_replay + 2 * input_with_headroom + temporary_zip + FREE_SPACE_RESERVE_BYTES
    return {
        "seconds": seconds, "estimated_process_calls": HZ * seconds,
        "input_tape_bytes_estimate": input_bytes,
        "input_tape_bytes_with_headroom": input_with_headroom,
        "engine_output_bytes_estimate_per_copy": engine_bytes,
        "engine_output_bytes_with_headroom_per_copy": engine_with_headroom,
        "headroom_factor": STORAGE_HEADROOM,
        "original_and_replay_output_bytes": live_and_replay,
        "verified_compact_spool_bytes": input_with_headroom,
        "temporary_zip_bytes_uncompressed_allowance": temporary_zip,
        "additional_free_space_reserve_bytes": FREE_SPACE_RESERVE_BYTES,
        "required_free_bytes_estimate": required,
        "fits_input_capture_cap_with_headroom": input_with_headroom < CAPTURE_MAX_BYTES,
        "scope": "Linear empirical projection, not a guaranteed upper bound; future engine log size and market activity can differ.",
    }


def acceptance_failures(proof, load, short_projection, free_bytes):
    failures = []
    for key in ("original_vs_recorded", "recorded_vs_replay", "replay",
                "altered_input_control", "integrity_tests"):
        if not proof.get(key, {}).get("pass"):
            failures.append("THREE_WAY_PROOF_" + key.upper())
    if not proof.get("pass") or proof.get("integrity_tests", {}).get("run", 0) < REQUIRED_INTEGRITY_TESTS:
        failures.append("THREE_WAY_PROOF_INCOMPLETE")
    if proof.get("replay", {}).get("validation_scope") != "ALL_PERSISTENT_ENGINE_OUTPUT_FILES":
        failures.append("FULL_OUTPUT_COMPARISON_REQUIRED")
    if load.get("process_calls") != LOAD_SECONDS * HZ:
        failures.append("SUSTAINED_LOAD_INCOMPLETE")
    if not load.get("manifest", {}).get("complete") or not load.get("tape_integrity_verified"):
        failures.append("RECORDER_EVIDENCE_INCOMPLETE")
    if load.get("manifest", {}).get("dropped", 1) or load.get("final_health", {}).get("reason"):
        failures.append("RECORDER_DROPS_OR_FAILURE")
    if load.get("backlog_before_close") != 0:
        failures.append("RECORDER_BACKLOG_AT_END_OF_PACED_LOAD")
    if load.get("queue_highwater", QUEUE_CAPACITY) >= QUEUE_CAPACITY:
        failures.append("RECORDER_QUEUE_REACHED_CAPACITY")
    for label, observed in (
        ("LOAD_CAPTURE", load.get("producer_capture", {}).get("max_us")),
        ("ENGINE_CAPTURE", proof.get("capture_timing", {}).get("measured_capture_work", {}).get("max_us")),
        ("STEADY_SCHEDULING_LAG", load.get("steady_scheduling_lag", {}).get("max_us")),
    ):
        if observed is None or observed >= DISPATCH_BUDGET_US:
            failures.append(label + "_EXCEEDS_250MS_OBSERVED_BUDGET")
    delta = load.get("final_health", {}).get("delta", {})
    if (not delta.get("enabled")
            or any(key not in delta for key in ("max_snapshot_rows", "max_snapshot_bytes"))
            or set(load.get("cache_observed", {})) != {"geometry_rows", "historical_candles"}):
        failures.append("BOUNDED_DELTA_ACCOUNTING_REQUIRED")
    else:
        for name, observed in load.get("cache_observed", {}).items():
            if (observed["max_rows"] > delta["max_snapshot_rows"]
                    or observed["max_canonical_bytes"] > delta["max_snapshot_bytes"]):
                failures.append("DELTA_CACHE_BOUND_EXCEEDED_" + name.upper())
    if short_projection is None or not short_projection["fits_input_capture_cap_with_headroom"]:
        failures.append("62MIN_INPUT_PROJECTION_EXCEEDS_CAPTURE_CAP_WITH_HEADROOM")
    if short_projection is None or free_bytes < short_projection["required_free_bytes_estimate"]:
        failures.append("INSUFFICIENT_PROJECTED_FREE_DISK_FOR_INPUT_ENGINE_REPLAY_AND_ZIP")
    return failures


def _existing_parent(path):
    path = Path(path).expanduser().resolve()
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _run_proof(out):
    command = [sys.executable, str(ROOT / "run_validation.py"), "--out", str(out)]
    with (out.parent / "three_way_console.txt").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
        return_code = process.wait()
    report_path = out / "validation_report.json"
    if not report_path.exists():
        raise RuntimeError("THREE_WAY_PROOF_DID_NOT_PRODUCE_REPORT")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if return_code or not report.get("pass"):
        raise RuntimeError("THREE_WAY_PROOF_FAILED:" + str(report.get("failure") or return_code))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="New offline readiness directory; never an existing run.")
    parser.add_argument("--output-root", type=Path,
                        help="Planned PAPER output root for default readiness location and free-disk checks.")
    args = parser.parse_args(argv)
    output_root = (args.output_root or default_output_root()).expanduser().resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = (args.out or output_root / "OFFLINE_READINESS" / (stamp + "_" + uuid.uuid4().hex[:8])).expanduser().resolve()
    if out.exists():
        parser.error("--out must name a new directory; existing evidence is never overwritten")
    out.mkdir(parents=True)
    report = {
        "schema": "TACHYOS_OFFLINE_NEXT_RUN_READINESS_V1", "started_utc": utc_now(),
        "pass": False, "offline_only": True, "strategy_modified": False,
        "feed_started": False, "credentials_accessed": False, "last_run_pointer_modified": False,
        "environment": {"python": platform.python_version(),
                        "implementation": platform.python_implementation(),
                        "executable": sys.executable, "platform": platform.platform(),
                        "machine": platform.machine()},
        "candidate_output_root": str(output_root), "offline_directory": str(out),
        "scope": "Same-interpreter local synthetic engine equivalence and finite recorder load; short 45-minute candidate with 17-minute planning allowance for drain only.",
        "six_hour_run_accepted": False,
    }
    try:
        hashes = verify_bundled_source()
        report["source_files_verified"] = len(hashes)
        print("OFFLINE READINESS 1/2: unchanged engine, recorded engine and input-driven replay.", flush=True)
        proof_dir = out / "three_way_proof"
        report["three_way_proof"] = proof = _run_proof(proof_dir)
        print("OFFLINE READINESS 2/2: 60-second recorder load, 4Hz, full 3,600-row snapshots.", flush=True)
        with network_forbidden():
            report["recorder_load"] = load = recorder_load(out, hashes)
        recorded_dir = proof_dir / "recorded" / proof["fixture"]["run_id"]
        sizes = {p.relative_to(recorded_dir).as_posix(): p.stat().st_size
                 for p in recorded_dir.rglob("*") if p.is_file() and p.name != "paper_writer.lock"}
        process_count = proof["observed_lifecycle"]["process_calls"]
        if not sizes or process_count <= 0:
            raise RuntimeError("ENGINE_OUTPUT_SIZE_EVIDENCE_MISSING")
        per_process = sum(sizes.values()) / process_count
        report["engine_output_measurement"] = {
            "files": sizes, "total_bytes": sum(sizes.values()), "process_calls": process_count,
            "bytes_per_process_for_linear_projection": per_process,
            "includes": "All persistent original-engine files, separately from input capture; fixed and overwritten outputs are conservatively included.",
        }
        short = storage_projection(load, per_process, SHORT_TOTAL_SECONDS)
        report["storage_projection"] = {
            "45m_entry_plus_17m_drain": short,
            "6h_entry_only_projection": storage_projection(load, per_process, LONG_ENTRY_SECONDS),
            "6h_plus_17m_drain_projection_only": storage_projection(
                load, per_process, LONG_ENTRY_SECONDS + DRAIN_ALLOWANCE_SECONDS),
            "input_cap_bytes": CAPTURE_MAX_BYTES,
            "input_cap_excludes_engine_outputs": True,
        }
        disk_path = _existing_parent(output_root)
        free_bytes = shutil.disk_usage(disk_path).free
        report["disk"] = {"checked_path": str(disk_path), "free_bytes_after_preflight": free_bytes}
        failures = acceptance_failures(proof, load, short, free_bytes)
        report["acceptance"] = {
            "pass": not failures, "failures": failures,
            "observed_capture_budget_us": DISPATCH_BUDGET_US,
            "hard_latency_bound_claimed": False,
            "sustained_load_seconds": LOAD_SECONDS, "cadence_hz": HZ,
            "backlog_rule": "Zero accepted-but-unwritten events after the final full 250ms dispatch slot, before close drains the writer.",
            "projection_headroom_factor": STORAGE_HEADROOM,
        }
        report["pass"] = not failures
    except BaseException as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        report["finished_utc"] = utc_now()
        (out / REPORT_NAME).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "report": str(out / REPORT_NAME),
                      "scope": "45m candidate plus bounded drain; six-hour projection is not acceptance",
                      "failures": report.get("acceptance", {}).get("failures", report.get("failure"))}, indent=2), flush=True)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
