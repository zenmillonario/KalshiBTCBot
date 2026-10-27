"""One-process Tool Rack PAPER launcher. No exchange-order capability."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import importlib.util
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
                               f"({len(positions)} positions). Review/export that run before a fresh $1,000 session.")


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

    engine = ToolRackPaperEngine(run_dir)
    feed = None
    dashboard = None
    stop_reason = None
    stop_started = None
    force_stop = False
    finality_tasks: dict[str, asyncio.Task] = {}
    next_finality: dict[str, float] = {}
    next_dashboard = 0.0
    previous_handlers = {}
    exit_code = 0

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
        feed = DirectPaperFeed(run_dir, credential_dir=args.credential_dir)
        print("TACHYOS TOOL RACK PAPER | one Commander | direct market data | fresh $1,000 ledger", flush=True)
        print(f"Run: {run_dir}", flush=True)
        print(f"Observation/trading window: {args.minutes:g} minutes; Ctrl+C requests an orderly PAPER stop.", flush=True)
        print("EMAs use validated minute closes; physical territories form from actual forward observations.", flush=True)
        try:
            dashboard = Dashboard(run_dir, port=args.dashboard_port)
            url = dashboard.start()
            print(f"Read-only bridge: {url}", flush=True)
            if not args.no_browser:
                webbrowser.open(url, new=2)
        except OSError as exc:
            print(f"Read-only bridge unavailable ({type(exc).__name__}); console and journal remain available.", flush=True)
        await feed.start()
        trading_started = time.monotonic()
        while True:
            if force_stop:
                stop_reason = "OPERATOR_IMMEDIATE_STOP"
                break
            if stop_reason is None and time.monotonic() - trading_started >= args.minutes * 60:
                stop_reason, stop_started = "PAPER_WINDOW_COMPLETE", time.monotonic()
                print("PAPER window complete. New entries stopped; Commander is closing remaining inventory.", flush=True)
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
                    engine.settle(result)
            now = time.time()
            for position in engine.executor.positions.values():
                if (now >= position.close_ts and position.ticker not in finality_tasks
                        and time.monotonic() >= next_finality.get(position.ticker, 0.0)):
                    finality_tasks[position.ticker] = asyncio.create_task(
                        feed.official_result(position.ticker, position.close_ts))
            frame = await feed.next_snapshot(timeout=1.0)
            # Do not pass the capture wall as the execution wall. Each live
            # dispatch rechecks real time after detector / journal work.
            outcome = engine.process(frame, stop_requested=stop_reason is not None)
            if dashboard is not None and time.monotonic() >= next_dashboard:
                next_dashboard = time.monotonic() + 1.0
                try:
                    dashboard.publish(outcome["status"], tuple(engine.physical.geometry.rows))
                except Exception as exc:
                    print(f"READ_ONLY_BRIDGE_UPDATE_WAIT {type(exc).__name__}", flush=True)
            if stop_reason is not None:
                if not engine.executor.positions:
                    break
                if time.monotonic() - stop_started >= args.stop_grace_seconds:
                    print("Stop grace ended; unresolved PAPER positions will remain explicit in the final ledger.", flush=True)
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
                engine.close(reason=stop_reason or "SESSION_ENDED")
            finally:
                if dashboard is not None:
                    dashboard.close()
                for sig, handler in previous_handlers.items():
                    signal.signal(sig, handler)
        print(f"PAPER session ended: {stop_reason or 'SESSION_ENDED'}", flush=True)
        print(f"Cash ${engine.executor.cash:.2f}; unresolved positions {len(engine.executor.positions)}.", flush=True)
        print(f"Review: {run_dir / 'RUN_SUMMARY.json'}", flush=True)
    return exit_code


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--minutes", type=float, default=90.0)
    result.add_argument("--output-root", type=Path, default=default_output_root())
    result.add_argument("--credential-dir", type=Path, default=Path(r"C:\KalshiBTCBot"))
    result.add_argument("--dashboard-port", type=int, default=0)
    result.add_argument("--no-browser", action="store_true")
    result.add_argument("--stop-grace-seconds", type=float, default=120.0)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not 0 < args.minutes <= 1440 or not 0 <= args.stop_grace_seconds <= 300:
        raise SystemExit("Use --minutes within (0, 1440] and stop grace within [0, 300].")
    if not 0 <= args.dashboard_port <= 65535:
        raise SystemExit("Dashboard port must be 0 (automatic) or a valid local port.")
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required. Use the existing KalshiBTCBot Python or install dependencies.")
    missing = [name for name in ("websockets", "cryptography") if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit("Missing dependencies: " + ", ".join(missing) +
                         ". Run 03_INSTALL_TOOL_RACK_DEPENDENCIES.cmd, then start again.")
    args.output_root = args.output_root.expanduser().resolve()
    args.output_root.mkdir(parents=True, exist_ok=True)
    run_name = "TOOL_RACK_PAPER_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"_PID{os.getpid()}"
    run_dir = args.output_root / run_name
    lease_path = global_lease_path()
    global_last_run = lease_path.with_name("paper_last_run.json")
    with GlobalPaperLease(lease_path):
        assert_previous_runs_flat(global_last_run, args.output_root / "LAST_RUN.json")
        run_dir.mkdir(exist_ok=False)
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
