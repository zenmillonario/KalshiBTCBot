from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from strategy_core.marketdata.kalshi_public import MarketInfo
from strategy_core.paper_execution import OfficialResult, PaperBook, PaperExecutioner, PriceLevel
from strategy_core.paper_feed import FeedSnapshot, freeze_data
from strategy_core.paper_runtime import GlobalPaperLease, ToolRackPaperEngine
from strategy_core.physical_source import CausalGeometry
from strategy_core.types import Side, Territory


BASE = 1_800_000_000.0


def raw_rows(stop=1200, start=0, epoch=1):
    return tuple({"epoch_ms": (BASE + i) * 1000, "btc_price": 79995 - i * .10,
                  "ema9": 80000 - i * .10, "ema30": 80015 - i * .10,
                  "connection_epoch": epoch, "sequence_num": i}
                 for i in range(start, stop + 1))


def capture(offset=1200, *, ticker="KXBTC15M-FIXTURE-A", close=2080,
            no_bid=.28, no_ask=.30, quote_id=None, rows=None):
    ts = BASE + offset
    book = PaperBook(ticker, quote_id or f"NATIVE:{offset}", ts, ts,
        (PriceLevel(round(1 - no_ask, 8), 1000),), (PriceLevel(no_bid, 1000),), BASE + close,
        provenance=freeze_data({"sequence_checked": True, "snapshot_verified": True,
                                "monotonic_receive_fresh": True, "fixture": True}))
    return FeedSnapshot(offset, ts, MarketInfo(ticker, BASE + close - 900, BASE + close, "active"),
                        book, freeze_data(raw_rows(offset) if rows is None else rows),
                        freeze_data({"btc_current": True, "book_current": True}))


class DirectPaperRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name) / "TOOL_RACK_PAPER_FIXTURE"
        self.engine = ToolRackPaperEngine(self.run)

    def tearDown(self):
        self.engine.close(reason="OFFLINE_FIXTURE_COMPLETE")
        self.temp.cleanup()

    def process(self, frame, **kwargs):
        return self.engine.process(frame, now_ts=frame.observed_ts, **kwargs)

    def test_raw_causal_down_rail_30c_to_real_committed_paper_fill(self):
        result = self.process(capture())
        self.assertEqual(result["status"]["rack"]["owned_territory"], Territory.DOWN_RAIL.value)
        receipt = result["receipts"][0]
        self.assertEqual(receipt.status, "BOOKED")
        self.assertEqual(receipt.event["side"], "NO")
        self.assertEqual(float(receipt.event["price"]), .30)
        self.assertGreater(receipt.event["qty"], 0)
        self.assertLessEqual(float(receipt.event["cost"]) + float(receipt.event["fees"]), 25)
        checked = PaperExecutioner.inspect_journal(self.run)
        self.assertEqual(checked["state"]["events"][0]["quote_id"], "NATIVE:1200")
        self.assertTrue(checked["committed_boundary"])
        self.assertFalse(receipt.event["venue_fill_claim"])

    def test_repeat_observation_does_not_stack_or_consume_another_rail_slice(self):
        self.process(capture())
        second = self.process(capture(1201))
        self.assertFalse(second["receipts"])
        self.assertEqual(len(self.engine.executor.positions), 1)
        self.assertEqual(len(self.engine.executor.events), 1)

    def test_expensive_observation_does_not_consume_later_30c_rail(self):
        self.process(capture(no_bid=.54, no_ask=.56))
        self.assertFalse(self.engine.executor.positions)
        result = self.process(capture(1201))
        self.assertEqual(result["receipts"][0].status, "BOOKED")

    def test_armed_rail_floor_exits_then_reenters_on_next_native_quote(self):
        self.process(capture())
        self.process(capture(1201, no_bid=.66, no_ask=.68))
        position = next(iter(self.engine.executor.positions.values()))
        self.assertAlmostEqual(position.floor_bid, .594)
        # Under30 seconds is protected at an explicitly earned +100% ROI.
        result = self.process(capture(1202, no_bid=.58, no_ask=.60))
        self.assertEqual(result["receipts"][0].status, "EXITED")
        self.assertFalse(self.engine.executor.positions)
        self.assertEqual(result["decisions"][-1]["decision"]["reason"], "EXIT_COMMITTED_WAIT_FOR_NEXT_NATIVE_QUOTE")
        next_quote = self.process(capture(1203))
        self.assertEqual(next_quote["receipts"][0].status, "BOOKED")
        self.assertIn("REARM1", next_quote["receipts"][0].event["opportunity_id"])

    def test_rollover_new_slice_and_late_old_finality_cannot_clear_it(self):
        self.process(capture())
        result = self.process(capture(2081, ticker="KXBTC15M-FIXTURE-B", close=2980))
        self.assertEqual(result["receipts"][0].status, "BOOKED")
        self.assertEqual(len(self.engine.executor.positions), 2)
        self.engine.settle(OfficialResult("KXBTC15M-FIXTURE-A", "OFFICIAL:A", Side.NO,
            BASE + 2080, BASE + 2082, "KALSHI_PUBLIC_TLS_GET"))
        self.assertEqual(len(self.engine.executor.positions), 1)
        held = next(iter(self.engine.executor.positions.values()))
        self.assertEqual(held.ticker, "KXBTC15M-FIXTURE-B")
        self.process(capture(2083, ticker=held.ticker, close=2980))
        entries = [event for event in self.engine.executor.events if event["event"] == "ENTRY"]
        self.assertEqual(len(entries), 2)

    def test_stale_native_quote_does_not_book_despite_qualified_rail(self):
        frame = capture()
        frame = replace(frame, book=replace(frame.book, observed_ts=BASE + 1195))
        result = self.process(frame)
        self.assertFalse(result["receipts"])
        self.assertFalse(self.engine.executor.positions)
        self.assertEqual(result["decisions"][-1]["decision"]["reason"], "OBJECTIVE_QUOTE_STALE")

    def test_live_imports_do_not_load_legacy_authority_or_shadow_source(self):
        import sys
        forbidden = ("r3_single_commander", "r17_guarded", "tachys_v9_", "strategy_core.r22_run_source")
        # Other suites intentionally test migration adapters, so inspect live
        # module source dependencies rather than unrelated global test imports.
        for module_name in ("strategy_core.paper_runtime", "strategy_core.paper_feed", "strategy_core.physical_source"):
            module = sys.modules[module_name]
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertFalse(any(f"import {name}" in source or f"from {name}" in source for name in forbidden))


class CausalGeometryTests(unittest.TestCase):
    def test_full_live_horizon_has_no_minute_endpoint_lag(self):
        geometry = CausalGeometry()
        for row in raw_rows(599):
            last = geometry.append(row)
        self.assertAlmostEqual(last["struct_slope3m"], -18.0)
        self.assertAlmostEqual(last["struct_slope6m"], -36.0)
        self.assertAlmostEqual(last["struct_slope9m"], -54.0)

    def test_short_observation_history_cannot_claim_three_minutes(self):
        geometry = CausalGeometry()
        for row in raw_rows(100):
            last = geometry.append(row)
        self.assertIsNone(last["struct_slope3m"])
        self.assertIsNone(last["struct_slope9m"])

    def test_repeated_capture_does_not_append_or_relabel_old_arcs(self):
        geometry = CausalGeometry()
        for row in raw_rows(600):
            geometry.append(row)
        before = json.dumps(list(geometry.rows), sort_keys=True)
        for row in raw_rows(600):
            self.assertIsNone(geometry.append(row))
        self.assertEqual(before, json.dumps(list(geometry.rows), sort_keys=True))

    def test_gap_clears_old_shape_and_does_not_invent_history(self):
        geometry = CausalGeometry()
        for row in raw_rows(600):
            geometry.append(row)
        last = geometry.append(raw_rows(700, start=700, epoch=2)[0])
        self.assertEqual(len(geometry.rows), 1)
        self.assertIsNone(last["struct_slope3m"])
        self.assertEqual(last["geometry_reset"], "BTC_CONNECTION_EPOCH_CHANGED")

    def test_global_lease_rejects_second_engine_even_in_another_run(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "engine.lock"
            with GlobalPaperLease(path):
                with self.assertRaisesRegex(RuntimeError, "ANOTHER_TOOL_RACK"):
                    with GlobalPaperLease(path):
                        self.fail("Second PAPER engine acquired the global lease")
            with GlobalPaperLease(path):
                pass


if __name__ == "__main__":
    unittest.main()
