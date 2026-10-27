import asyncio
from argparse import Namespace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import TOOL_RACK_PAPER
from TOOL_RACK_EXPORT import export_run
from strategy_core.marketdata.kalshi_public import MarketDataError
from strategy_core.paper_runtime import ToolRackPaperEngine
from tests.tool_rack.test_direct_paper_runtime import capture


class PaperLauncherExportTests(unittest.TestCase):
    def test_fresh_ledger_cannot_hide_prior_unresolved_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "PRIOR_TOOL_RACK_PAPER_FIXTURE"
            engine = ToolRackPaperEngine(run)
            frame = capture()
            engine.process(frame, now_ts=frame.observed_ts)
            engine.close(reason="FIXTURE_UNRESOLVED_STOP")
            pointer = root / "LAST_RUN.json"
            pointer.write_text(json.dumps({"run_dir": str(run)}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "INVENTORY_UNRESOLVED"):
                TOOL_RACK_PAPER.assert_previous_runs_flat(pointer)

    def test_flat_previous_committed_ledger_allows_new_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "PRIOR_TOOL_RACK_FLAT_FIXTURE"
            engine = ToolRackPaperEngine(run)
            engine.close(reason="FIXTURE_FLAT_STOP")
            pointer = root / "LAST_RUN.json"
            pointer.write_text(json.dumps({"run_dir": str(run)}), encoding="utf-8")
            TOOL_RACK_PAPER.assert_previous_runs_flat(pointer)

    def test_manifest_failure_cleans_constructor_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "MANIFEST_FAILURE_FIXTURE"
            with patch("strategy_core.paper_runtime.atomic_json", side_effect=PermissionError("fixture")):
                with self.assertRaises(PermissionError):
                    ToolRackPaperEngine(run)
            self.assertFalse((run / "paper_writer.lock").exists())

    def test_missing_optional_dashboard_asset_does_not_leave_writer_or_block_paper(self):
        class Feed:
            def __init__(self, *args, **kwargs):
                pass
            async def start(self):
                pass
            async def next_snapshot(self, **kwargs):
                return capture()
            async def close(self):
                pass

        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "DASHBOARD_ASSET_FAILURE_FIXTURE"
            args = Namespace(credential_dir=Path(temporary), dashboard_port=0,
                             no_browser=True, minutes=0, stop_grace_seconds=0)
            with patch("TOOL_RACK_PAPER.DirectPaperFeed", Feed), \
                    patch("strategy_core.paper_dashboard.Dashboard", side_effect=FileNotFoundError("fixture asset")):
                result = asyncio.run(TOOL_RACK_PAPER.run_session(args, run))
            self.assertEqual(result, 0)
            self.assertFalse((run / "paper_writer.lock").exists())
            summary = json.loads((run / "RUN_SUMMARY.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["state"], "STOPPED")
            self.assertEqual(summary["stop_reason"], "PAPER_WINDOW_COMPLETE")

    def test_stopped_archive_has_actual_journal_and_matching_file_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "TOOL_RACK_OFFLINE_FIXTURE"
            engine = ToolRackPaperEngine(run)
            frame = capture()
            engine.process(frame, now_ts=frame.observed_ts)
            with self.assertRaisesRegex(ValueError, "Stop the PAPER"):
                export_run(run)
            engine.close(reason="OFFLINE_FIXTURE_COMPLETE")
            archive_path = export_run(run)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertIsNone(archive.testzip())
                manifest = json.loads(archive.read(run.name + "/EXPORT_MANIFEST.json"))
                self.assertTrue(manifest["journal_verified"])
                self.assertGreater(manifest["journal_seq"], 1)
                for name, expected in manifest["files"].items():
                    self.assertEqual(hashlib.sha256(archive.read(run.name + "/" + name)).hexdigest(), expected)
                self.assertFalse(any(".env" in name or "key.pem" in name for name in archive.namelist()))

    def test_failed_source_start_releases_engine_and_records_explicit_stop(self):
        class FailedFeed:
            instance = None
            def __init__(self, *args, **kwargs):
                FailedFeed.instance = self
                self.closed = False
            async def start(self):
                raise MarketDataError("MARKET_DATA_KEY_ID_NOT_CONFIGURED")
            async def close(self):
                self.closed = True

        class LocalDashboard:
            def __init__(self, *args, **kwargs):
                pass
            def start(self):
                return "http://127.0.0.1:1/"
            def close(self):
                pass

        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "TOOL_RACK_START_FAILURE_FIXTURE"
            args = Namespace(credential_dir=Path(temporary), dashboard_port=0,
                             no_browser=True, minutes=90, stop_grace_seconds=0)
            with patch("TOOL_RACK_PAPER.DirectPaperFeed", FailedFeed), \
                    patch("strategy_core.paper_dashboard.Dashboard", LocalDashboard):
                result = asyncio.run(TOOL_RACK_PAPER.run_session(args, run))
            self.assertEqual(result, 1)
            self.assertTrue(FailedFeed.instance.closed)
            self.assertFalse((run / "paper_writer.lock").exists())
            summary = json.loads((run / "RUN_SUMMARY.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["state"], "STOPPED")
            self.assertEqual(summary["unresolved_inventory_count"], 0)
            self.assertEqual(summary["cash"], "1000.0")


if __name__ == "__main__":
    unittest.main()
