"""One-process Tool Rack PAPER launcher. No exchange-order capability."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback
import webbrowser

from strategy_core.paper_feed import DirectPaperFeed
from strategy_core.paper_execution import PaperExecutioner
from strategy_core.paper_runtime import GlobalPaperLease, ToolRackPaperEngine, atomic_json


def default_output_root() -> Path:
    configured = os.environ.get("TACHYOS_TOOL_RACK_PAPER_ROOT")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt" and Path("E:/").is_dir():
        return Path("E:/TachyosToolRackPaper")
    return Path.home() / "TachyosToolRackPaper"


def global_lease_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "TachyosToolRack" / "paper_engine.lock"


def assert_previous_runs_flat(*pointers: Path) -> None:
    """A fresh PAPER treasury never hides unresolved previous inventory."""
    checked_paths: set[Path] = set()
    for pointer in pointers:
        if not pointer.exists():
            continue
        try:
            import json
            prior = Path(json.loads(pointer.read_text(encoding="utf-8"))["run_dir"]).resolve()
            if prior in checked_paths:
                continue
            checked_paths.add(prior)
            journal = PaperExecutioner.inspect_journal(prior)
            if journal["state"] is None:
                raise ValueError("Previous committed baseline unavailable")
            positions = journal["state"]["positions"]
        except Exception as exc:
            raise RuntimeError(f"PREVIOUS_TOOL_RACK_LEDGER_REQUIRES_REVIEW: {pointer} ({type(exc).__name__})") from None
        if positions:
            raise RuntimeError(f"PREVIOUS_TOOL_RACK_INVENTORY_UNRESOLVED: {prior} "
                               f"({len(positions)} positions). Run 05_RECONCILE_PREVIOUS_TOOL_RACK_RUN.cmd "
                               "to finish expired PAPER positions from exact official results, then start again.")


class ConsoleLog:
    def __init__(self, stream, file):
        self.stream, self.file = stream, file

    def write(self, value):
        self.stream.write(value)
        self.file.write(value)
        return len(value)

    def flush(self):
        self.stream.flush()
        self.file.flush()

    def isatty(self):
        return self.stream.isatty()


async def run_session(args: argparse.Namespace, run_dir: Path) -> int:
    # Imported here so --help and offline checks do not start a server.
    from strategy_core.paper_dashboard import Dashboard

    recorder = None
    if getattr(args, "record_for_replay", False):
        # Recording is optional evidence around the same synchronous engine.
        # Import only when requested; the ordinary PAPER path stays unchanged.
        from capture_session import open_capture, capture_health, finish_capture

        recorder = open_capture(run_dir, args)
        engine = recorder.engine
    else:
        engine = ToolRackPaperEngine(run_dir)
    feed = None
    dashboard = None
    stop_reason = None
    stop_started = None
    entry_window_closed = False
    drain_deadline = None
    drain_close_ts = None
    finality_buffer_seconds = getattr(args, "finality_buffer_seconds", 120.0)
    force_stop = False
    finality_tasks: dict[str, asyncio.Task] = {}
    next_finality: dict[str, float] = {}
    next_dashboard = 0.0
    previous_handlers = {}
    exit_code = 0
    next_capture_report = 0.0
    last_capture_state = None

    def report_capture_health(*, health=None, force=False):
        """Expose evidence failures without changing engine decisions/status."""
        nonlocal next_capture_report, last_capture_state
        if recorder is None:
            return
        try:
            health = capture_health(recorder) if health is None else health
            state = (health.get("state"), health.get("status"), health.get("reason"),
                     health.get("complete"))
            current_mono = time.monotonic()
            if force or state != last_capture_state or current_mono >= next_capture_report:
                print("REPLAY_CAPTURE " + json.dumps(health, sort_keys=True), flush=True)
                last_capture_state = state
                next_capture_report = current_mono + 60.0
        except Exception as exc:
            # A diagnostic reporting error is not a new strategy veto. The
            # finalizer still inspects the recorder's manifest independently.
            state = ("REPORT_UNAVAILABLE", type(exc).__name__)
            if state != last_capture_state:
                print(f"REPLAY_CAPTURE_REPORT_UNAVAILABLE {type(exc).__name__}", flush=True)
                last_capture_state = state

    def request_stop(signum, frame):
        nonlocal stop_reason, stop_started, force_stop
        if stop_reason is None:
            stop_reason, stop_started = "OPERATOR_STOP", time.monotonic()
            print("PAPER stop requested. Commander will close at current held-side depth where available.", flush=True)
            print("Press Ctrl+C again to stop immediately and preserve unresolved PAPER inventory.", flush=True)
        else:
            force_stop = True

    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is not None:
            previous_handlers[sig] = signal.signal(sig, request_stop)
    try:
        if recorder is not None:
            report_capture_health(force=True)
        feed = DirectPaperFeed(run_dir, credential_dir=args.credential_dir)
        print("TACHYOS TOOL RACK PAPER | PID15740 INHERITED PARENT DUAL LANE | one Commander | PAPER only", flush=True)
        print(f"Run: {run_dir}", flush=True)
        print(f"New-entry window: {args.minutes:g} minutes; held positions then continue normal strategy management.", flush=True)
        print(f"Automatic drain is bounded at the latest held contract close plus {finality_buffer_seconds:g} seconds for official finality.", flush=True)
        print("Ctrl+C requests an orderly PAPER flatten; it is separate from the entry-window timer.", flush=True)
        print("EMAs use validated minute closes; physical territories form from actual forward observations.", flush=True)
        try:
            dashboard = Dashboard(run_dir, port=args.dashboard_port)
            url = dashboard.start()
            print(f"The Nautilus | Tool Rack PAPER | live engine feed: {url}", flush=True)
            if not args.no_browser:
                webbrowser.open(url, new=2)
        except OSError as exc:
            print(f"Read-only bridge unavailable ({type(exc).__name__}); console and journal remain available.", flush=True)
        await feed.start()
        trading_started = time.monotonic()

        def close_entry_window_if_due():
            nonlocal entry_window_closed, drain_deadline, drain_close_ts
            if entry_window_closed or stop_reason is not None:
                return
            current_mono = time.monotonic()
            if current_mono - trading_started < args.minutes * 60:
                return
            entry_window_closed = True
            held = tuple(engine.executor.positions.values())
            current_wall = time.time()
            drain_close_ts = max((position.close_ts for position in held), default=current_wall)
            # Freeze the bounded wait at cutoff. Repeated polling, missing
            # finality, or a changed wall clock cannot silently extend it.
            drain_deadline = current_mono + max(0.0,
                drain_close_ts + finality_buffer_seconds - current_wall)
            print("PAPER entry window closed. No new entries; held strategy and already-armed protection continue normally.", flush=True)
            if held:
                print("DRAINING: waiting for an ordinary strategy exit or exact-contract official finality; the timer does not sell positions.", flush=True)

        while True:
            if force_stop:
                stop_reason = "OPERATOR_IMMEDIATE_STOP"
                break
            close_entry_window_if_due()
            # HTTP finality runs in the background. It never holds the quote /
            # protection loop, and an unavailable result never becomes zero.
            for ticker, task in list(finality_tasks.items()):
                if not task.done():
                    continue
                del finality_tasks[ticker]
                next_finality[ticker] = time.monotonic() + 3.0
                try:
                    result = task.result()
                except Exception as exc:
                    print(f"OFFICIAL_FINALITY_WAIT {ticker} {type(exc).__name__}: {exc}", flush=True)
                    continue
                if result is not None:
                    # A ledger/finality conflict is fatal; it must not be
                    # mislabeled as a retryable market-data lookup failure.
                    if recorder is None:
                        engine.settle(result)
                    else:
                        recorder.invoke("settle", {"result": result})
                        report_capture_health()
            now = time.time()
            for position in engine.executor.positions.values():
                if (now >= position.close_ts and position.ticker not in finality_tasks
                        and time.monotonic() >= next_finality.get(position.ticker, 0.0)):
                    finality_tasks[position.ticker] = feed.request_official_result(
                        position.ticker, position.close_ts)
            frame = await feed.next_snapshot(timeout=1.0)
            if force_stop:
                stop_reason = "OPERATOR_IMMEDIATE_STOP"
                break
            # A source await may cross the boundary. Recheck before allowing
            # this frame to reach the Commander as a new-entry opportunity.
            close_entry_window_if_due()
            # Do not pass the capture wall as the execution wall. Each live
            # dispatch rechecks real time after detector / journal work.
            chart_data = feed.chart_snapshot() if hasattr(feed, "chart_snapshot") else None
            if recorder is None:
                outcome = engine.process(frame, stop_requested=stop_reason is not None,
                    entry_window_closed=entry_window_closed,
                    historical_candles=(chart_data or {}).get("candles", ()))
            else:
                outcome = recorder.invoke("process", {
                    "feed": frame, "stop_requested": stop_reason is not None,
                    "entry_window_closed": entry_window_closed,
                    "historical_candles": (chart_data or {}).get("candles", ()),
                })
                report_capture_health()
            if dashboard is not None:
                try:
                    # Retain every observed decision/ledger transition even
                    # though the browser projection publishes at most 1 Hz.
                    dashboard.observe(outcome["status"])
                    if time.monotonic() >= next_dashboard:
                        next_dashboard = time.monotonic() + 1.0
                        dashboard.publish(outcome["status"], tuple(engine.physical.geometry.rows),
                                          chart_data=chart_data)
                except Exception as exc:
                    print(f"READ_ONLY_BRIDGE_UPDATE_WAIT {type(exc).__name__}", flush=True)
            if stop_reason is not None:
                if not engine.executor.positions:
                    break
                if time.monotonic() - stop_started >= args.stop_grace_seconds:
                    print("Stop grace ended; unresolved PAPER positions will remain explicit in the final ledger.", flush=True)
                    stop_reason = "OPERATOR_STOP_GRACE_EXPIRED_UNRESOLVED"
                    exit_code = 2
                    break
            elif entry_window_closed:
                if not engine.executor.positions:
                    stop_reason = "PAPER_ENTRY_WINDOW_COMPLETE_FLAT"
                    break
                if drain_deadline is not None and time.monotonic() >= drain_deadline:
                    stop_reason = "PAPER_ENTRY_WINDOW_FINALITY_TIMEOUT_UNRESOLVED"
                    exit_code = 2
                    print("Automatic drain deadline reached with unresolved PAPER inventory. No exit or settlement is invented; review/export this run before a new ledger.", flush=True)
                    break
    except Exception as exc:
        exit_code = 1
        stop_reason = "RUNTIME_ERROR_" + type(exc).__name__
        print(f"PAPER runtime stopped: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        atomic_json(run_dir / "ERROR.json", {"timestamp": time.time(), "error_type": type(exc).__name__,
                    "message": str(exc)[:500], "mode": "PAPER"}, required=False)
    finally:
        for task in finality_tasks.values():
            task.cancel()
        if finality_tasks:
            await asyncio.gather(*finality_tasks.values(), return_exceptions=True)
        try:
            if feed is not None:
                await feed.close()
        finally:
            try:
                if recorder is None:
                    engine.close(reason=stop_reason or "SESSION_ENDED")
                else:
                    capture_final = finish_capture(recorder, reason=stop_reason or "SESSION_ENDED")
                    report_capture_health(health=capture_final, force=True)
            finally:
                if dashboard is not None:
                    try:
                        final_status = getattr(engine, "latest_status", {})
                        if final_status.get("state") == "STOPPED":
                            dashboard.observe(final_status)
                            chart_data = feed.chart_snapshot() if feed is not None and hasattr(feed, "chart_snapshot") else None
                            dashboard.publish(final_status, tuple(engine.physical.geometry.rows), chart_data=chart_data)
                    except Exception as exc:
                        print(f"NAUTILUS_FINAL_SNAPSHOT_UNAVAILABLE {type(exc).__name__}", flush=True)
                    finally:
                        dashboard.close()
                for sig, handler in previous_handlers.items():
                    signal.signal(sig, handler)
        print(f"PAPER session ended: {stop_reason or 'SESSION_ENDED'}", flush=True)
        print(f"Cash ${engine.executor.cash:.2f}; unresolved positions {len(engine.executor.positions)}.", flush=True)
        print(f"Review: {run_dir / 'RUN_SUMMARY.json'}", flush=True)
        if exit_code == 0 and engine.executor.positions:
            exit_code = 2
    return exit_code


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--minutes", type=float, default=90.0,
                        help="Minutes in which new entries are allowed; normal held-position management continues afterward.")
    result.add_argument("--output-root", type=Path, default=default_output_root())
    result.add_argument("--credential-dir", type=Path, default=Path(r"C:\KalshiBTCBot"))
    result.add_argument("--dashboard-port", type=int, default=8580)
    result.add_argument("--no-browser", action="store_true")
    result.add_argument("--record-for-replay", action="store_true",
                        help="Opt in to lossless synchronous-engine input recording for offline replay.")
    result.add_argument("--run-receipt", type=Path,
                        help="Write this newly created run's path for an exact post-run replay/export handoff.")
    result.add_argument("--stop-grace-seconds", type=float, default=120.0,
                        help="Maximum orderly flatten time after manual Ctrl+C (not the automatic entry cutoff).")
    result.add_argument("--finality-buffer-seconds", type=float, default=120.0,
                        help="Bounded automatic drain buffer after the latest held contract closes (0 to 300).")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if (not 0 < args.minutes <= 1440 or not 0 <= args.stop_grace_seconds <= 300
            or not 0 <= args.finality_buffer_seconds <= 300):
        raise SystemExit("Use --minutes within (0, 1440]; manual stop grace and finality buffer must be within [0, 300].")
    if not 0 <= args.dashboard_port <= 65535:
        raise SystemExit("Dashboard port must be 0 (automatic) or a valid local port.")
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required. Use the existing KalshiBTCBot Python or install dependencies.")
    missing = [name for name in ("websockets", "cryptography") if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit("Missing dependencies: " + ", ".join(missing) +
                         ". Run 03_INSTALL_TOOL_RACK_DEPENDENCIES.cmd, then start again.")
    args.output_root = args.output_root.expanduser().resolve()
    if args.run_receipt is not None:
        args.run_receipt = args.run_receipt.expanduser().resolve()
        if args.run_receipt.exists():
            raise SystemExit("Choose a new --run-receipt path; an existing receipt is never replaced.")
        args.run_receipt.parent.mkdir(parents=True, exist_ok=True)
    args.output_root.mkdir(parents=True, exist_ok=True)
    run_name = "TOOL_RACK_PAPER_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"_PID{os.getpid()}"
    run_dir = args.output_root / run_name
    lease_path = global_lease_path()
    global_last_run = lease_path.with_name("paper_last_run.json")
    with GlobalPaperLease(lease_path):
        try:
            assert_previous_runs_flat(global_last_run, args.output_root / "LAST_RUN.json")
        except RuntimeError as exc:
            print("PAPER start blocked: " + str(exc), flush=True)
            return 2 if "INVENTORY_UNRESOLVED" in str(exc) else 1
        run_dir.mkdir(exist_ok=False)
        if args.run_receipt is not None:
            atomic_json(args.run_receipt, {"run_dir": str(run_dir), "mode": "PAPER"})
        atomic_json(args.output_root / "LAST_RUN.json", {"run_dir": str(run_dir), "mode": "PAPER"})
        atomic_json(global_last_run, {"run_dir": str(run_dir), "mode": "PAPER"})
        original_out, original_err = sys.stdout, sys.stderr
        with (run_dir / "console.log").open("a", encoding="utf-8", buffering=1) as log:
            sys.stdout, sys.stderr = ConsoleLog(original_out, log), ConsoleLog(original_err, log)
            try:
                return asyncio.run(run_session(args, run_dir))
            finally:
                sys.stdout, sys.stderr = original_out, original_err


if __name__ == "__main__":
    raise SystemExit(main())
