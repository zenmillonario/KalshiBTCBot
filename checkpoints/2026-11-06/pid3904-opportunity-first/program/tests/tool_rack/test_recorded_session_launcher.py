"""Opt-in recording preserves the original launcher's bounded lifecycle."""
import asyncio
from argparse import Namespace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import TOOL_RACK_PAPER
from tests.tool_rack import test_session_draining_launcher as draining_fixture


class RecordedSessionDrainingLauncherTests(draining_fixture.SessionDrainingLauncherTests):
    """Run the existing cutoff/finality/manual-stop controls through recording.

    The original fixture still owns its engine, feed, clock and signal models.
    This facade records the launcher boundary and checks that no extra engine
    construction, close, timestamp substitution or finality dispatch is added.
    """

    def scenario(self, **kwargs):
        original_run_session = TOOL_RACK_PAPER.run_session
        recorders = []
        capture_failed = getattr(self, "capture_failed", False)

        class Recorder:
            def __init__(self, run_dir):
                self.engine = TOOL_RACK_PAPER.ToolRackPaperEngine(run_dir)
                self.calls = [("init", {})]
                self.close_count = 0
                recorders.append(self)

            def invoke(self, method, arguments):
                self.calls.append((method, dict(arguments)))
                if method == "process":
                    frame = arguments["feed"]
                    return self.engine.process(frame, **{
                        key: value for key, value in arguments.items() if key != "feed"
                    })
                if method == "settle":
                    return self.engine.settle(**arguments)
                raise AssertionError("Unexpected recorded launcher call: " + method)

            def close(self, *, reason):
                self.calls.append(("close", {"reason": reason}))
                self.close_count += 1
                self.engine.close(reason=reason)

        async def recorded_session(args, run_dir):
            args.record_for_replay = True
            return await original_run_session(args, run_dir)

        def open_recorder(run_dir, args):
            self.assertTrue(args.record_for_replay)
            return Recorder(run_dir)

        def health(recorder):
            return {"status": "failed" if capture_failed else "running",
                    "reason": "TEST_CAPTURE_FAILURE" if capture_failed else None,
                    "dropped": 1 if capture_failed else 0}

        def finish(recorder, *, reason):
            recorder.close(reason=reason)
            return {**health(recorder), "status": "failed" if capture_failed else "complete",
                    "complete": not capture_failed}

        with patch("TOOL_RACK_PAPER.run_session", side_effect=recorded_session), \
             patch("capture_session.open_capture", side_effect=open_recorder), \
             patch("capture_session.capture_health", side_effect=health), \
             patch("capture_session.finish_capture", side_effect=finish):
            result = super().scenario(**kwargs)

        self.assertEqual(len(recorders), 1)
        recorder = recorders[0]
        self.assertIs(result[3], recorder.engine)
        self.assertEqual(recorder.close_count, 1)
        self.assertEqual(recorder.calls[0], ("init", {}))
        self.assertEqual(recorder.calls[-1], ("close", {"reason": result[1]["stop_reason"]}))
        processes = [args for method, args in recorder.calls if method == "process"]
        self.assertEqual(
            [(args["feed"].elapsed, args["stop_requested"], args["entry_window_closed"])
             for args in processes], result[2])
        for args in processes:
            self.assertEqual(set(args), {
                "feed", "stop_requested", "entry_window_closed", "historical_candles",
            })
            self.assertNotIn("now_ts", args)
            self.assertEqual(args["historical_candles"], [])
        settlements = [args for method, args in recorder.calls if method == "settle"]
        self.assertEqual([args["result"] for args in settlements], result[3].settlements)
        self.assertTrue(all(set(args) == {"result"} for args in settlements))
        return result

    def test_capture_failure_is_reported_without_becoming_a_strategy_veto(self):
        self.capture_failed = True
        with patch("builtins.print") as printed:
            code, summary, calls, _, _, _ = self.scenario(steps=[30, 60, 90], flatten_at=90)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [(30, False, False), (60, False, True), (90, False, True)])
        self.assertEqual(summary["stop_reason"], "PAPER_ENTRY_WINDOW_COMPLETE_FLAT")
        text = "\n".join(str(call.args[0]) for call in printed.call_args_list if call.args)
        self.assertIn("TEST_CAPTURE_FAILURE", text)


class RecordedLauncherStartupTests(unittest.TestCase):
    def test_recording_is_opt_in_and_receipt_is_optional(self):
        args = TOOL_RACK_PAPER.parser().parse_args([])
        self.assertFalse(args.record_for_replay)
        self.assertIsNone(args.run_receipt)
        self.assertEqual(args.minutes, 90.0)

    def test_capture_startup_failure_does_not_start_a_feed_or_second_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            args = Namespace(record_for_replay=True)
            with patch("capture_session.open_capture", side_effect=OSError("TEST_CAPTURE_UNAVAILABLE")), \
                 patch("TOOL_RACK_PAPER.DirectPaperFeed") as feed, \
                 patch("TOOL_RACK_PAPER.ToolRackPaperEngine") as engine:
                with self.assertRaisesRegex(OSError, "TEST_CAPTURE_UNAVAILABLE"):
                    asyncio.run(TOOL_RACK_PAPER.run_session(args, Path(directory) / "NEW_RUN"))
            feed.assert_not_called()
            engine.assert_not_called()

    def test_run_receipt_identifies_this_run_and_preserves_session_return_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = root / "receipt" / "new_run.json"

            async def session(args, run_dir):
                saved = json.loads(receipt.read_text(encoding="utf-8"))
                self.assertEqual(saved, {"run_dir": str(run_dir), "mode": "PAPER"})
                self.assertEqual(args.run_receipt, receipt)
                self.assertTrue((run_dir / "console.log").is_file())
                return 2

            with patch("TOOL_RACK_PAPER.global_lease_path", return_value=root / "paper_engine.lock"), \
                 patch("TOOL_RACK_PAPER.importlib.util.find_spec", return_value=object()), \
                 patch("TOOL_RACK_PAPER.run_session", side_effect=session) as launched:
                code = TOOL_RACK_PAPER.main([
                    "--output-root", str(root / "runs"), "--run-receipt", str(receipt),
                ])
            self.assertEqual(code, 2)
            launched.assert_called_once()
            self.assertTrue(receipt.is_file())

    def test_blocked_prior_inventory_creates_no_receipt_or_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = root / "new_run.json"
            with patch("TOOL_RACK_PAPER.global_lease_path", return_value=root / "paper_engine.lock"), \
                 patch("TOOL_RACK_PAPER.importlib.util.find_spec", return_value=object()), \
                 patch("TOOL_RACK_PAPER.assert_previous_runs_flat",
                       side_effect=RuntimeError("PREVIOUS_TOOL_RACK_INVENTORY_UNRESOLVED")), \
                 patch("TOOL_RACK_PAPER.run_session") as launched:
                code = TOOL_RACK_PAPER.main([
                    "--output-root", str(root / "runs"), "--run-receipt", str(receipt),
                ])
            self.assertEqual(code, 2)
            launched.assert_not_called()
            self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main()
