"""Integration controls for real Commander -> passive PAPER ledger behavior."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from strategy_core.marketdata.kalshi_public import MarketInfo
from strategy_core.paper_execution import OfficialResult, PaperBook, PriceLevel
from strategy_core.paper_feed import FeedSnapshot, freeze_data
from strategy_core.paper_runtime import ToolRackPaperEngine
from strategy_core.physical_source import DirectPhysicalFrame
from strategy_core.router import PhysicalEvidence
from strategy_core.types import Side


def captured(ts=1000., *, close=1900., bid=.16, quote_id=None):
    native = PaperBook("KX1", quote_id or f"Q{ts}", ts, ts,
                       (PriceLevel(bid, 1000),), (PriceLevel(round(.99-bid, 9), 1000),), close,
                       provenance=freeze_data({"fixture": {"coherent_capture": True}}))
    return FeedSnapshot(1, ts, MarketInfo("KX1", close-900, close, "active"), native,
                        (freeze_data({"epoch_ms": ts*1000}),), freeze_data({"btc_current": True}))


def rail_frame():
    return DirectPhysicalFrame(
        PhysicalEvidence(ema9_direction=Side.YES, ema30_direction=Side.YES,
                         ema_pair_parallel=True, directional_residence=True,
                         contracts_persistent=1.0),
        {"physical_current": True}, None, (), True)


class RuntimeAccountingAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name) / "run"
        self.engine = ToolRackPaperEngine(self.run)

    def tearDown(self):
        self.engine.close(reason="FIXTURE_END")
        self.temp.cleanup()

    def test_live_dispatch_rechecks_receive_age_after_measurement_work(self):
        clock = [1000.]
        def measurement(*args, **kwargs):
            clock[0] = 1005.
            return rail_frame()
        with patch.object(self.engine.physical, "observe", side_effect=measurement), patch(
                "strategy_core.paper_runtime.time.time", side_effect=lambda: clock[0]):
            result = self.engine.process(captured())
        self.assertFalse(self.engine.executor.positions)
        self.assertFalse(self.engine.executor.events)
        self.assertTrue(any(receipt.reason == "OBJECTIVE_NATIVE_RECEIVE_STALE"
                            for receipt in result["receipts"]))

    def test_live_dispatch_rechecks_expiry_after_measurement_work(self):
        clock = [1000.]
        def measurement(*args, **kwargs):
            clock[0] = 1001.1
            return rail_frame()
        with patch.object(self.engine.physical, "observe", side_effect=measurement), patch(
                "strategy_core.paper_runtime.time.time", side_effect=lambda: clock[0]):
            result = self.engine.process(captured(close=1001.))
        self.assertFalse(self.engine.executor.positions)
        self.assertTrue(any(receipt.reason == "OBJECTIVE_CONTRACT_CLOSED"
                            for receipt in result["receipts"]))

    def test_final_summary_includes_settlement_after_last_decision_snapshot(self):
        with patch.object(self.engine.physical, "observe", return_value=rail_frame()):
            result = self.engine.process(captured(), now_ts=1000.)
        self.assertEqual(result["receipts"][0].status, "BOOKED")
        self.assertEqual(self.engine.executor.positions["1"].qty, 138)
        self.engine.settle(OfficialResult("KX1", "OFFICIAL1", Side.YES, 1900., 1901.,
                                          "KALSHI_PUBLIC_TLS_GET"))
        final = self.engine.executor.snapshot()
        self.engine.close(reason="AFTER_FINALITY")
        summary = json.loads((self.run / "RUN_SUMMARY.json").read_text(encoding="utf-8"))
        for key in ("cash", "realized_net", "realized_gross", "fees_paid", "events"):
            self.assertEqual(summary[key], final[key])
        self.assertAlmostEqual(float(summary["realized_gross"]), 114.54)
        self.assertAlmostEqual(float(summary["realized_net"]), 113.17)
        self.assertEqual(summary["unresolved_inventory_count"], 0)
        self.assertEqual(summary["events"][-1]["event"], "SETTLEMENT")

    def test_optional_status_read_lock_does_not_undo_or_halt_committed_trade(self):
        actual_replace = os.replace
        def locked_projection(source, destination):
            if Path(destination).name == "STATUS.json":
                raise PermissionError("fixture monitor has STATUS open")
            return actual_replace(source, destination)
        with patch.object(self.engine.physical, "observe", return_value=rail_frame()), patch(
                "strategy_core.paper_runtime.os.replace", side_effect=locked_projection):
            result = self.engine.process(captured(), now_ts=1000.)
        self.assertEqual(result["receipts"][0].status, "BOOKED")
        self.assertEqual(self.engine.executor.positions["1"].qty, 138)
        self.assertEqual(len(self.engine.executor.events), 1)
        self.assertTrue((self.run / "paper_writer.lock").exists())

    def test_real_rail_floor_exit_then_fresh_value_reentry_uses_single_commander(self):
        with patch.object(self.engine.physical, "observe", return_value=rail_frame()):
            initial = self.engine.process(captured(), now_ts=1000.)
            first_id = initial["receipts"][0].position_id
            territory = self.engine.executor.positions[first_id].territory_id
            self.engine.process(captured(1040., bid=.34), now_ts=1040.)
            self.assertAlmostEqual(self.engine.executor.positions[first_id].floor_bid, .306)
            broken = self.engine.process(captured(1041., bid=.30), now_ts=1041.)
            self.assertEqual([r.status for r in broken["receipts"]], ["EXITED"])
            self.assertFalse(self.engine.executor.positions)
            repeated = self.engine.process(captured(1041., bid=.30), now_ts=1041.1)
            self.assertFalse(repeated["receipts"])
            value = self.engine.process(captured(1042., bid=.16), now_ts=1042.)
            self.assertEqual([r.status for r in value["receipts"]], ["BOOKED"])
            second = self.engine.executor.positions[value["receipts"][0].position_id]
            self.assertNotEqual(first_id, second.position_id)
            self.assertEqual(second.territory_id, territory)
            self.assertIn("REARM1", second.opportunity_id)
            self.assertEqual([event["event"] for event in self.engine.executor.events],
                             ["ENTRY", "EXIT", "ENTRY"])

    def test_close_releases_writer_even_if_projection_function_raises(self):
        with patch("strategy_core.paper_runtime.atomic_json", side_effect=PermissionError("fixture")):
            with self.assertRaises(PermissionError):
                self.engine.close(reason="FIXTURE_FAILURE")
        self.assertFalse((self.run / "paper_writer.lock").exists())
        self.assertTrue(self.engine.audit.closed)
        self.assertTrue(self.engine.geometry_log.closed)


if __name__ == "__main__":
    unittest.main()
