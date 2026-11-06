"""Actual display OHLC stays separate from causal trading geometry."""
import asyncio
from datetime import datetime, timezone
import tempfile
import unittest
from unittest.mock import patch

from strategy_core.marketdata.btc_observation import ema, validate_candles
from strategy_core.marketdata.btc_transport import PublicFeed, seed_chart_candles
from strategy_core.paper_feed import CHART_HISTORY_LIMIT, DirectPaperFeed


MINUTE = 1_800_000_000


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat()


def seed_rows(end=MINUTE, count=60):
    return [[end - (count - i) * 60, 80000 + i - 2, 80000 + i + 3,
             80000 + i - 1, 80000 + i, 1.0] for i in range(count)]


def status_event(end=MINUTE, epoch=1):
    raw = seed_rows(end)
    accepted, meta = validate_candles(raw, end + 2)
    return {"kind": "btc_status", "observed_at": end + 2,
            "row": {"state": "PUBLIC_SEED_READY", "epoch": epoch, "seed": meta,
                    "chart_candles": seed_chart_candles(accepted, raw, epoch=epoch, received=end + 2)}}


def trade_event(stamp, price, trade_id, epoch=1, mono=100):
    return {"kind": "btc_trade", "observed_at": stamp + .01,
            "row": {"timestamp_epoch": stamp, "price": price, "trade_id": str(trade_id),
                    "connection_epoch": epoch, "received_monotonic": mono,
                    "received_utc": iso(stamp + .01)}}


def enqueue(feed, *events):
    for event in events:
        feed._btc.queue.put_nowait(event)
    feed._drain_btc()


class NautilusChartSourceTests(unittest.TestCase):
    def test_seed_uses_exact_returned_ohlc_and_never_populates_trading_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = DirectPaperFeed(directory)
            enqueue(feed, status_event())
            chart = feed.chart_snapshot()
            self.assertEqual(len(chart["candles"]), 60)
            self.assertEqual(len(feed._rows), 0)
            self.assertFalse(feed._btc_usable)
            self.assertEqual(chart["candles"][0]["open"], 79999)
            self.assertEqual(chart["candles"][0]["high"], 80003)
            self.assertEqual(chart["candles"][0]["low"], 79998)
            self.assertEqual(chart["candles"][0]["close"], 80000)
            self.assertIsNone(chart["candles"][7]["e9"])
            self.assertEqual(chart["candles"][8]["e9"], ema(list(range(80000, 80009)), 9))
            self.assertIsNone(chart["candles"][28]["e30"])
            self.assertIsNotNone(chart["candles"][29]["e30"])
            chart["candles"][0]["close"] = 0
            self.assertEqual(feed.chart_snapshot()["candles"][0]["close"], 80000)

    def test_all_accepted_trades_preserve_extremes_between_geometry_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = DirectPaperFeed(directory)
            enqueue(feed, status_event(),
                    trade_event(MINUTE + .1, 80100, 1),
                    trade_event(MINUTE + .2, 80107, 2),
                    trade_event(MINUTE + .3, 80095, 3),
                    trade_event(MINUTE + .9, 80101, 4),
                    {"kind": "btc_geometry", "observed_at": MINUTE + 1,
                     "row": {"connection_epoch": 1, "sample_serial": 1,
                             "timestamp": iso(MINUTE + .9), "btc_price": 80101,
                             "ema9": 80090, "ema30": 80050, "received_monotonic": 100}})
            bar = feed.chart_snapshot()["candles"][-1]
            self.assertEqual((bar["open"], bar["high"], bar["low"], bar["close"]),
                             (80100, 80107, 80095, 80101))
            self.assertEqual((bar["e9"], bar["e30"]), (80090, 80050))
            self.assertEqual(bar["ema_observed_at"], MINUTE + .9)
            self.assertEqual(bar["quality"], "sampled")
            self.assertFalse(bar["full_minute"])
            self.assertEqual(len(feed._rows), 1)
            self.assertEqual(feed._rows[-1]["btc_price"], 80101)

    def test_first_partial_minute_is_disclosed_and_continuous_next_minute_is_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = DirectPaperFeed(directory)
            events = [trade_event(MINUTE + offset, 80000 + i, i + 1)
                      for i, offset in enumerate((12, 35, 59, 60.1, 85, 110, 119, 120.1))]
            enqueue(feed, status_event(), *events)
            candles = {bar["time"]: bar for bar in feed.chart_snapshot()["candles"]}
            self.assertTrue(candles[MINUTE]["complete"])
            self.assertFalse(candles[MINUTE]["full_minute"])
            self.assertEqual(candles[MINUTE]["quality"], "sampled")
            self.assertTrue(candles[MINUTE + 60]["complete"])
            self.assertTrue(candles[MINUTE + 60]["full_minute"])
            self.assertEqual(candles[MINUTE + 60]["quality"], "coinbase-completed")
            self.assertFalse(candles[MINUTE + 120]["complete"])
            self.assertEqual(candles[MINUTE + 120]["quality"], "coinbase-developing")

    def test_gap_does_not_fabricate_bars_or_merge_connection_epochs(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = DirectPaperFeed(directory)
            enqueue(feed, status_event(), trade_event(MINUTE + 5, 80020, 1),
                    {"kind": "btc_gap", "row": {"reason": "TEST_GAP"}},
                    trade_event(MINUTE + 245, 80100, 2, epoch=2))
            chart = feed.chart_snapshot()
            candles = {bar["time"]: bar for bar in chart["candles"]}
            self.assertEqual(chart["history"]["source_gap_count"], 1)
            self.assertTrue(candles[MINUTE]["interrupted"])
            self.assertFalse(candles[MINUTE]["complete"])
            for stamp in (MINUTE + 60, MINUTE + 120, MINUTE + 180):
                self.assertNotIn(stamp, candles)
            self.assertEqual(candles[MINUTE + 240]["open"], 80100)
            self.assertEqual(candles[MINUTE + 240]["connection_epoch"], 2)
            self.assertFalse(candles[MINUTE + 240]["full_minute"])
            self.assertEqual(len(feed._rows), 0)

    def test_real_new_seed_can_replace_partial_history_without_forward_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = DirectPaperFeed(directory)
            enqueue(feed, status_event(), trade_event(MINUTE + 5, 80200, 1),
                    {"kind": "btc_gap", "row": {"reason": "TEST_GAP"}},
                    status_event(end=MINUTE + 60, epoch=2))
            bar = feed.chart_snapshot()["candles"][-1]
            self.assertEqual(bar["time"], MINUTE)
            self.assertEqual(bar["close"], 80059)
            self.assertTrue(bar["complete"] and bar["full_minute"])
            self.assertEqual(bar["source"], "COINBASE_EXCHANGE_PUBLIC_CANDLES_60S")
            self.assertEqual(len(feed._rows), 0)
            self.assertFalse(feed._btc_usable)

    def test_seed_excludes_open_unused_and_ambiguous_ohlc_buckets(self):
        raw = seed_rows()
        conflict = raw[10].copy()
        conflict[1] -= 1
        raw.extend([conflict, [MINUTE, 79900, 80100, 80000, 80050, 1]])
        accepted, _ = validate_candles(raw, MINUTE + 2)
        candles = seed_chart_candles(accepted, raw, epoch=1, received=MINUTE + 2)
        stamps = {bar["time"] for bar in candles}
        self.assertNotIn(MINUTE, stamps)
        self.assertNotIn(conflict[0], stamps)
        self.assertEqual(len(candles), 59)

    def test_chart_is_bounded_and_old_receive_time_is_not_refreshed_by_polling(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = DirectPaperFeed(directory)
            for i in range(CHART_HISTORY_LIMIT + 10):
                enqueue(feed, trade_event(MINUTE + i * 60 + 1, 80000, i + 1, mono=100))
            with patch("strategy_core.paper_feed.time.time", return_value=MINUTE + 730 * 60), \
                 patch("strategy_core.paper_feed.time.monotonic", return_value=104):
                chart = feed.chart_snapshot()
                self.assertEqual(len(chart["candles"]), CHART_HISTORY_LIMIT)
                self.assertEqual(chart["history"]["developing_status"], "STALE")
                self.assertEqual(chart["history"]["last_trade_ts"], MINUTE + 729 * 60 + 1)
            self.assertEqual(len(feed._rows), 0)

    def test_chart_failure_does_not_change_source_currentness_or_causal_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, affected = DirectPaperFeed(directory), DirectPaperFeed(directory)
            geometry = {"kind": "btc_geometry", "observed_at": MINUTE + 1,
                        "row": {"connection_epoch": 1, "sample_serial": 1,
                                "timestamp": iso(MINUTE + .9), "btc_price": 80101,
                                "ema9": 80090, "ema30": 80050, "received_monotonic": 100}}
            with patch("strategy_core.paper_feed.time.time", return_value=MINUTE + 1), \
                 patch("strategy_core.paper_feed.time.monotonic", return_value=100):
                enqueue(baseline, status_event(), trade_event(MINUTE + .9, 80101, 1), geometry)
                normal = baseline._capture()
                with patch.object(affected._chart, "seed", side_effect=RuntimeError("display only")), \
                     patch.object(affected._chart, "trade", side_effect=ValueError("display only")), \
                     patch.object(affected._chart, "geometry", side_effect=KeyError("display only")):
                    enqueue(affected, status_event(), trade_event(MINUTE + .9, 80101, 1), geometry)
                    actual = affected._capture()
                self.assertEqual(actual.geometry_rows, normal.geometry_rows)
                self.assertEqual(actual.generation, normal.generation)
                self.assertTrue(actual.source_status["btc_current"])
                self.assertIsNone(actual.source_status["source_error"])
                self.assertEqual(actual.source_status["btc_geometry_age_seconds"],
                                 normal.source_status["btc_geometry_age_seconds"])
                with patch.object(affected._chart, "snapshot", side_effect=RuntimeError("display only")):
                    failed_display = affected.chart_snapshot()
                self.assertEqual(failed_display["history"]["status"], "DEGRADED")
                self.assertEqual(failed_display["candles"], [])
                self.assertEqual(affected._capture().geometry_rows, normal.geometry_rows)

    def test_seed_display_exception_still_connects_public_transport_with_validated_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = seed_rows()
            seed, meta = validate_candles(raw, MINUTE + 2)
            sent = []
            worker = PublicFeed(directory, seed_fetch=lambda: (seed, meta, raw))

            class Connection:
                async def __aenter__(self):
                    worker.stop_event.set()
                    return self

                async def __aexit__(self, *args):
                    return False

                async def send(self, message):
                    sent.append(message)

            worker.connect = lambda *args, **kwargs: Connection()

            async def direct_async_call(function, *args):
                return function(*args)

            with patch.object(worker, "_record"), \
                 patch("strategy_core.marketdata.btc_transport.asyncio.to_thread", direct_async_call), \
                 patch("strategy_core.marketdata.btc_transport.seed_chart_candles",
                       side_effect=RuntimeError("display only")):
                asyncio.run(worker._run())
            status = worker.queue.get_nowait()
            self.assertEqual(status["kind"], "btc_status")
            self.assertEqual(status["row"]["state"], "PUBLIC_SEED_READY")
            self.assertEqual(status["row"]["seed"], meta)
            self.assertEqual(status["row"]["chart_candles"], [])
            self.assertEqual(status["row"]["chart_history_error"], "RuntimeError")
            self.assertEqual(len(sent), 1)
            self.assertIn('"channel": "market_trades"', sent[0])
            self.assertTrue(worker.queue.empty())


if __name__ == "__main__":
    unittest.main()
