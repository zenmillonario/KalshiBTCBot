"""Launcher orchestration: timed entry cutoff differs from manual flatten."""
import asyncio
from argparse import Namespace
import json
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import TOOL_RACK_PAPER


class SessionDrainingLauncherTests(unittest.TestCase):
    def scenario(self, *, steps, held_close=180, finality_buffer=120,
                 flatten_at=None, official_finality=False, manual_at=(), stop_grace=120):
        """Use deterministic source beats to inspect the actual launcher loop.

        Engine semantics and journal entries are covered by runtime tests. This
        fixture isolates flag routing, source waits, finality scheduling, and
        the single Nautilus lifecycle without connecting any market source.
        """
        clock = {"elapsed": 0.0}
        base = 1_800_000_000.0
        handlers = {}
        calls, instances, dashboards, finality_reads, opened = [], [], [], [], []

        class Engine:
            def __init__(self, run_dir):
                self.run_dir = Path(run_dir)
                self.run_dir.mkdir(parents=True, exist_ok=True)
                self.executor = SimpleNamespace(positions={"1": SimpleNamespace(
                    ticker="KXBTC15M-HELD", close_ts=base + held_close)}, cash=990.0)
                self.physical = SimpleNamespace(geometry=SimpleNamespace(rows=[]))
                self.latest_status = {}
                self.settlements = []
                instances.append(self)

            def process(self, frame, *, stop_requested=False, entry_window_closed=False, historical_candles=()):
                calls.append((frame.elapsed, stop_requested, entry_window_closed))
                if flatten_at is not None and frame.elapsed >= flatten_at:
                    self.executor.positions.clear()
                self.latest_status = {
                    "run_id": self.run_dir.name, "updated_at": base + frame.elapsed,
                    "state": "STOPPING" if stop_requested else "DRAINING" if entry_window_closed else "RUNNING",
                    "entry_window_closed": entry_window_closed, "positions": dict(self.executor.positions),
                }
                return {"status": self.latest_status}

            def settle(self, result):
                self.settlements.append(result)
                self.executor.positions.clear()

            def close(self, *, reason):
                self.latest_status = {**self.latest_status, "state": "STOPPED", "stop_reason": reason,
                                      "unresolved_inventory_count": len(self.executor.positions)}
                (self.run_dir / "RUN_SUMMARY.json").write_text(json.dumps({
                    "state": "STOPPED", "stop_reason": reason,
                    "unresolved_inventory_count": len(self.executor.positions)}), encoding="utf-8")

        class Feed:
            def __init__(self, *args, **kwargs):
                self.steps = iter(steps)
                self.closed = False

            async def start(self):
                pass

            async def next_snapshot(self, **kwargs):
                try:
                    clock["elapsed"] = float(next(self.steps))
                except StopIteration:
                    raise RuntimeError("Launcher failed to stop within the bounded fixture") from None
                for at in manual_at:
                    if clock["elapsed"] == at:
                        handlers[signal.SIGINT](signal.SIGINT, None)
                await asyncio.sleep(0)
                return SimpleNamespace(elapsed=clock["elapsed"])

            async def official_result(self, ticker, close):
                finality_reads.append((ticker, close))
                return {"ticker": ticker, "official": True} if official_finality else None

            def request_official_result(self, ticker, close):
                return asyncio.create_task(self.official_result(ticker, close))

            def chart_snapshot(self):
                return {"candles": [], "history": {"status": "FIXTURE"}}

            async def close(self):
                self.closed = True

        class Dashboard:
            def __init__(self, *args, **kwargs):
                self.observed, self.published = [], []
                self.started = False
                self.closed = False
                dashboards.append(self)

            def start(self):
                self.started = True
                return "http://127.0.0.1:8580/"

            def observe(self, status):
                self.observed.append(dict(status))

            def publish(self, status, geometry_rows, chart_data=None):
                self.published.append((dict(status), chart_data))

            def close(self):
                self.closed = True

        def register_signal(which, handler):
            previous = handlers.get(which, signal.SIG_DFL)
            handlers[which] = handler
            return previous

        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "DRAINING_LAUNCHER_FIXTURE"
            args = Namespace(credential_dir=Path(directory), dashboard_port=8580, no_browser=False,
                             minutes=1, stop_grace_seconds=stop_grace,
                             finality_buffer_seconds=finality_buffer)
            with patch("TOOL_RACK_PAPER.ToolRackPaperEngine", Engine), \
                 patch("TOOL_RACK_PAPER.DirectPaperFeed", Feed), \
                 patch("strategy_core.paper_dashboard.Dashboard", Dashboard), \
                 patch("TOOL_RACK_PAPER.webbrowser.open", side_effect=lambda url, **kwargs: opened.append(url)), \
                 patch("TOOL_RACK_PAPER.time.time", side_effect=lambda: base + clock["elapsed"]), \
                 patch("TOOL_RACK_PAPER.time.monotonic", side_effect=lambda: 1000 + clock["elapsed"]), \
                 patch("TOOL_RACK_PAPER.signal.signal", side_effect=register_signal):
                code = asyncio.run(TOOL_RACK_PAPER.run_session(args, run))
            summary = json.loads((run / "RUN_SUMMARY.json").read_text(encoding="utf-8"))
        self.assertEqual(len(instances), 1)
        self.assertEqual(len(dashboards), 1)
        self.assertEqual(opened, ["http://127.0.0.1:8580/"])
        self.assertTrue(dashboards[0].started and dashboards[0].closed)
        return code, summary, calls, instances[0], dashboards[0], finality_reads

    def test_entry_cutoff_crossed_during_source_await_keeps_normal_held_strategy(self):
        code, summary, calls, engine, dashboard, _ = self.scenario(steps=[30, 60, 90], flatten_at=90)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [(30, False, False), (60, False, True), (90, False, True)])
        self.assertEqual(summary["stop_reason"], "PAPER_ENTRY_WINDOW_COMPLETE_FLAT")
        self.assertEqual(summary["unresolved_inventory_count"], 0)
        self.assertEqual([s["state"] for s in dashboard.observed[:3]], ["RUNNING", "DRAINING", "DRAINING"])
        self.assertEqual(dashboard.observed[-1]["state"], "STOPPED")
        self.assertEqual(dashboard.published[-1][0]["stop_reason"], "PAPER_ENTRY_WINDOW_COMPLETE_FLAT")
        self.assertTrue(all(chart is not None for _, chart in dashboard.published))

    def test_automatic_drain_accepts_only_official_finality_before_finishing_flat(self):
        code, summary, calls, engine, _, reads = self.scenario(
            steps=[60, 70, 71, 72], held_close=70, finality_buffer=20, official_finality=True)
        self.assertEqual(code, 0)
        self.assertEqual(summary["stop_reason"], "PAPER_ENTRY_WINDOW_COMPLETE_FLAT")
        self.assertEqual(reads, [("KXBTC15M-HELD", 1_800_000_070.0)])
        self.assertEqual(engine.settlements, [{"ticker": "KXBTC15M-HELD", "official": True}])
        self.assertTrue(all(not manual and closed for _, manual, closed in calls))

    def test_automatic_finality_timeout_returns_unresolved_without_forced_sell(self):
        code, summary, calls, engine, _, reads = self.scenario(
            steps=[60, 70, 90], held_close=70, finality_buffer=20)
        self.assertEqual(code, 2)
        self.assertEqual(summary["stop_reason"], "PAPER_ENTRY_WINDOW_FINALITY_TIMEOUT_UNRESOLVED")
        self.assertEqual(summary["unresolved_inventory_count"], 1)
        self.assertTrue(engine.executor.positions)
        self.assertEqual(engine.settlements, [])
        self.assertTrue(reads)
        self.assertTrue(all(not manual and closed for _, manual, closed in calls))

    def test_first_manual_ctrl_c_during_automatic_drain_requests_orderly_flatten(self):
        code, summary, calls, _, _, _ = self.scenario(
            steps=[60, 70], manual_at=(70,), flatten_at=70)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [(60, False, True), (70, True, True)])
        self.assertEqual(summary["stop_reason"], "OPERATOR_STOP")

    def test_manual_grace_timeout_is_explicit_unresolved(self):
        code, summary, calls, _, _, _ = self.scenario(
            steps=[20, 25], manual_at=(20,), stop_grace=5)
        self.assertEqual(code, 2)
        self.assertEqual(summary["stop_reason"], "OPERATOR_STOP_GRACE_EXPIRED_UNRESOLVED")
        self.assertEqual(summary["unresolved_inventory_count"], 1)
        self.assertEqual(calls, [(20, True, False), (25, True, False)])

    def test_second_ctrl_c_during_source_await_stops_before_another_engine_dispatch(self):
        code, summary, calls, _, _, _ = self.scenario(steps=[20, 21], manual_at=(20, 21))
        self.assertEqual(code, 2)
        self.assertEqual(summary["stop_reason"], "OPERATOR_IMMEDIATE_STOP")
        self.assertEqual(calls, [(20, True, False)])


if __name__ == "__main__":
    unittest.main()
