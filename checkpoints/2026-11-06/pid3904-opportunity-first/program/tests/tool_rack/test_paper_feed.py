from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from strategy_core.marketdata.btc_observation import TradeStream, FeedFault, validate_candles
from strategy_core.marketdata.kalshi_public import (
    MarketDataCredentials, MarketDataError, MarketInfo, PublicMarketClient,
    PublicReceipt, _local_env_values, select_current_market,
)
from strategy_core.marketdata.native_book import QuoteHub
from strategy_core.marketdata.native_receiver import NativeWsReceiver, _ReconnectNow
from strategy_core.paper_feed import (
    DirectPaperFeed, FeedSnapshot, freeze_data, official_result_from_receipt,
    paper_book_from_quote,
)
from strategy_core.types import Side


NOW = 1_800_000_002.0
TICKER = "KXBTC15M-2701150800-00"


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def market_row(ticker=TICKER, close=NOW + 300, **updates):
    return {"ticker": ticker, "market_type": "binary", "status": "active",
            "open_time": iso(close - 3600), "close_time": iso(close), **updates}


def snapshot_message(ticker=TICKER, seq=1, yes=None, no=None, timestamp=NOW):
    message = {"type": "orderbook_snapshot", "sid": 2, "seq": seq, "msg": {
        "market_ticker": ticker, "yes_dollars_fp": [["0.45", "20.5"]] if yes is None else yes,
        "no_dollars_fp": [["0.50", "31.8"]] if no is None else no}}
    if timestamp is not None:
        message["sending_ts_ms"] = int(timestamp * 1000)
    return message


def delta_message(seq=2, delta="2.00", ticker=TICKER):
    return {"type": "orderbook_delta", "sid": 2, "seq": seq,
            "msg": {"market_ticker": ticker, "side": "yes", "price_dollars": "0.45",
                    "delta_fp": delta, "ts_ms": int(NOW * 1000)}}


def hub_with_book(**snapshot_options):
    hub = QuoteHub()
    hub.begin(TICKER, NOW + 300, NOW, 100.0)
    hub.on_ws(snapshot_message(**snapshot_options), NOW, 100.0)
    return hub


def convert(hub, now=NOW, mono=100.0):
    return paper_book_from_quote(hub.view(now, mono), now_ts=now, now_mono=mono,
                                 sequence_verified=hub.book_ok, receiver_generation=1,
                                 source_generation=7)


class DirectPaperBookTests(unittest.TestCase):
    def test_depth_complements_and_unchanged_observation_keeps_identity_and_time(self):
        hub = hub_with_book()
        first = convert(hub)
        later = convert(hub, NOW + 1, 101)
        self.assertEqual(first.quote_id, later.quote_id)
        self.assertEqual(first.observed_ts, later.observed_ts)
        self.assertEqual(first.observed_ts, NOW)
        self.assertEqual(first.asks(Side.YES)[0].price, 0.5)
        self.assertEqual(first.asks(Side.NO)[0].price, 0.55)
        self.assertEqual(first.yes_bids[0].quantity, 20.5)
        self.assertTrue(first.current and first.entry_allowed)
        self.assertFalse(convert(hub, NOW + 4, 104).current)

    def test_untimed_snapshot_is_unknown_and_sequence_proven(self):
        book = convert(hub_with_book(timestamp=None))
        self.assertIsNone(book.exchange_ts)
        self.assertTrue(book.current)
        for name in ("sequence_checked", "snapshot_verified", "monotonic_receive_fresh"):
            self.assertIs(book.provenance[name], True)
        self.assertFalse(book.provenance["exchange_timestamp_known"])

    def test_one_sided_book_only_allows_real_held_side_sell(self):
        book = convert(hub_with_book(no=[]))
        self.assertTrue(book.current)
        self.assertFalse(book.entry_allowed)
        self.assertTrue(book.yes_sell_allowed)
        self.assertFalse(book.no_sell_allowed)
        self.assertEqual(book.no_bids, ())

    def test_gap_future_or_expired_book_has_no_permission(self):
        hub = hub_with_book()
        hub.on_ws(delta_message(seq=3), NOW, 100.1)
        self.assertFalse(convert(hub, NOW + .1, 100.1).current)
        self.assertFalse(convert(hub_with_book(timestamp=NOW + 5)).current)
        old = hub_with_book()
        self.assertFalse(convert(old, NOW + 300, 100).current)

    def test_wrong_ticker_and_duplicate_do_not_refresh_quote(self):
        hub = hub_with_book()
        before = convert(hub)
        hub.on_ws(snapshot_message(ticker="KXBTC15M-OTHER"), NOW + 1, 101)
        hub.on_ws(snapshot_message(), NOW + 1, 101)
        after = convert(hub, NOW + 1, 101)
        self.assertEqual(before.quote_id, after.quote_id)
        self.assertEqual(before.observed_ts, after.observed_ts)

    def test_native_receiver_folds_contiguous_depth_and_invalidates_gap(self):
        receiver = NativeWsReceiver("unused", {}, {}, ticker=TICKER, connect_factory=lambda: None)
        receiver._generation = 1
        receiver._enqueue_message(snapshot_message(), NOW, 100)
        receiver._enqueue_message(delta_message(), NOW + .1, 100.1)
        folded = receiver.drain_nowait()
        self.assertEqual(len(folded), 1)
        self.assertTrue(folded[0]["folded_current_book"])
        self.assertEqual(folded[0]["data"]["seq"], 2)
        self.assertEqual(folded[0]["data"]["msg"]["yes_dollars_fp"][0][1], "22.50")
        with self.assertRaises(_ReconnectNow):
            receiver._enqueue_message(delta_message(seq=4), NOW + .2, 100.2)
        self.assertFalse(receiver.snapshot()["current_book_valid"])
        self.assertFalse(any(row.get("folded_current_book") for row in receiver.drain_nowait()))


class DirectMarketAndFinalityTests(unittest.TestCase):
    def test_display_target_is_exact_market_strike_and_never_inferred(self):
        selected = select_current_market({"markets": [market_row(
            strike_type="greater", floor_strike="80321.75")]}, NOW)
        self.assertEqual(selected.target, 80321.75)
        self.assertEqual(selected.target_source, "KALSHI_MARKET_FLOOR_STRIKE")
        for values in ({"title": "Bitcoin above $80000"},
                       {"strike_type": "between", "floor_strike": 80000},
                       {"strike_type": "greater", "floor_strike": "NaN"},
                       {"strike_type": "greater", "floor_strike": True},
                       {"strike_type": "greater", "floor_strike": 0}):
            with self.subTest(values=values):
                market = select_current_market({"markets": [market_row(**values)]}, NOW)
                self.assertIsNone(market.target)
                self.assertIsNone(market.target_source)

    def test_discovery_selects_current_exact_series_not_upcoming_or_expired(self):
        rows = [market_row("KXBTC15M-FUTURE", close=NOW + 1800),
                market_row("KXBTC15M-EXPIRED", close=NOW),
                market_row("KXOTHER-OPEN", close=NOW + 60), market_row()]
        selected = select_current_market({"markets": rows}, NOW)
        self.assertEqual(selected.ticker, TICKER)
        self.assertEqual(selected.interval_start_ts, selected.close_ts - 900)
        with self.assertRaises(MarketDataError):
            select_current_market({"markets": rows[:-1]}, NOW)

    def receipt(self, **updates):
        market = market_row(close=NOW - 60, status="finalized", result="yes",
                            settlement_ts=iso(NOW - 10), settlement_value_dollars="1.0000")
        market.update(updates)
        return PublicReceipt({"market": market}, NOW, .1, "a" * 64, "/markets/" + TICKER)

    def test_only_official_final_binary_exact_ticker_result_settles(self):
        final = official_result_from_receipt(TICKER, NOW - 60, self.receipt())
        self.assertEqual(final.result, Side.YES)
        self.assertEqual(final.source, "KALSHI_PUBLIC_TLS_GET")
        self.assertIsNone(official_result_from_receipt(TICKER, NOW - 60, self.receipt(status="determined")))
        self.assertIsNone(official_result_from_receipt(TICKER, NOW - 60, self.receipt(is_provisional=True)))
        for updates in ({"ticker": "KXBTC15M-OTHER"}, {"result": "scalar"},
                        {"settlement_value_dollars": "0.50"}, {"settlement_value_dollars": "0"},
                        {"settlement_ts": iso(NOW + 1)}, {"settlement_ts": None}):
            with self.subTest(updates=updates), self.assertRaises(MarketDataError):
                official_result_from_receipt(TICKER, NOW - 60, self.receipt(**updates))
        with self.assertRaises(MarketDataError):
            official_result_from_receipt(TICKER, NOW - 59, self.receipt())

    def test_public_http_allowlist_has_no_account_route(self):
        client = PublicMarketClient()
        for route in ("/portfolio/balance", "/portfolio/orders", "/markets/OTHER", "https://example.com"):
            with self.subTest(route=route), self.assertRaises(MarketDataError):
                client._get(route)
        self.assertFalse(hasattr(client, "post"))
        self.assertFalse(hasattr(client, "orders"))

    def test_credential_parser_preserves_windows_paths_and_only_reads_two_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = ('KALSHI_API_KEY_ID="local-test-id" # configured\n'
                       "KALSHI_PRIVATE_KEY_PATH='C:\\Existing Folder\\existing.pem'\n"
                       'UNRELATED_SECRET=do-not-load\n')
            path = directory / ".env"
            path.write_text(content, encoding="utf-8")
            before = path.read_bytes()
            values = _local_env_values(directory)
            self.assertEqual(values["KALSHI_PRIVATE_KEY_PATH"], r"C:\Existing Folder\existing.pem")
            self.assertEqual(set(values), {"KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY_PATH"})
            self.assertEqual(path.read_bytes(), before)

    def test_credentials_sign_only_fixed_ws_get_path_and_never_repr_secrets(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            self.skipTest("existing cryptography dependency unavailable in test interpreter")
        key = Ed25519PrivateKey.generate()
        credential = MarketDataCredentials("fixture-key-id", key)
        headers = credential.websocket_headers()
        message = (headers["KALSHI-ACCESS-TIMESTAMP"] + "GET/trade-api/ws/v2").encode()
        key.public_key().verify(base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"]), message)
        self.assertNotIn("fixture-key-id", repr(credential))
        self.assertFalse(hasattr(credential, "sign_request"))


class DirectBtcAndCaptureTests(unittest.TestCase):
    def stream(self):
        current = int(NOW // 60) * 60
        rows = [[current - offset * 60, 100, 110, 105, 105, 1] for offset in range(1, 241)]
        seed, metadata = validate_candles(rows, NOW)
        return TradeStream(seed, metadata, 1)

    def envelope(self, sequence, kind, trades):
        return {"channel": "market_trades", "sequence_num": sequence, "timestamp": iso(NOW),
                "events": [{"type": kind, "trades": trades}]}

    def trade(self, trade_id, timestamp=NOW):
        return {"product_id": "BTC-USD", "trade_id": str(trade_id), "time": iso(timestamp),
                "price": "106", "size": "0.01", "side": "BUY"}

    def test_snapshot_never_becomes_fresh_trade_and_ack_sequence_is_counted(self):
        stream = self.stream()
        self.assertEqual(stream.consume(self.envelope(0, "snapshot", [self.trade(1)]), NOW, 100), [])
        stream.consume({"channel": "subscriptions", "sequence_num": 1}, NOW, 100)
        rows = stream.consume(self.envelope(2, "update", [self.trade(2)]), NOW, 100)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["connection_epoch"], 1)
        self.assertEqual(rows[0]["btc_price"], 106)
        self.assertEqual(stream.bars.completed_live, 0)
        with self.assertRaises(FeedFault):
            stream.consume(self.envelope(4, "update", [self.trade(3)]), NOW, 100)

    def test_seed_holes_never_generate_history(self):
        current = int(NOW // 60) * 60
        rows = [[current - offset * 60, 100, 110, 105, 105, 1] for offset in range(2, 242)]
        with self.assertRaises(FeedFault):
            validate_candles(rows, NOW)

    def test_capture_freezes_data_and_gap_clears_forward_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            feed = DirectPaperFeed(temporary)
            row = {"timestamp": iso(NOW), "btc_price": 106, "ema9": 105.2, "ema30": 105.1,
                   "connection_epoch": 1, "sample_serial": 1, "received_monotonic": 100,
                   "seed_metadata": {"completed_bars": 240}}
            feed._btc.queue.put({"kind": "btc_geometry", "row": row, "observed_at": NOW})
            with patch("strategy_core.paper_feed.time.time", return_value=NOW), patch(
                    "strategy_core.paper_feed.time.monotonic", return_value=100):
                capture = feed._capture()
            row["seed_metadata"]["completed_bars"] = 0
            self.assertEqual(capture.geometry_rows[0]["seed_metadata"]["completed_bars"], 240)
            with self.assertRaises(TypeError):
                capture.geometry_rows[0]["btc_price"] = 0
            json.dumps(capture.to_dict())
            self.assertTrue(capture.source_status["btc_current"])
            feed._btc.queue.put({"kind": "btc_gap", "row": {"reason": "PUBLIC_SEQUENCE_GAP"}})
            after = feed._capture()
            self.assertEqual(after.geometry_rows, ())
            self.assertFalse(after.source_status["btc_current"])
            self.assertEqual(capture.geometry_rows[0]["btc_price"], 106)

    def test_market_rollover_keeps_btc_history_and_never_returns_other_ticker_book(self):
        class Credentials:
            def websocket_headers(self):
                return {}

        class Receiver:
            def __init__(self, *args, **kwargs):
                self.stopped = False
            def start(self):
                pass
            def stop(self, timeout):
                self.stopped = True

        class HTTP:
            def discovery(self):
                return PublicReceipt({"markets": [market_row("KXBTC15M-NEW")]}, NOW, .1, "a", "/markets")
            def orderbook(self, ticker):
                return PublicReceipt({"orderbook_fp": {}}, NOW, .1, "b", "/markets/" + ticker + "/orderbook")

        async def fixture_thread_call(function, *args):
            # Pure fake responses need no OS worker. Real Windows transport
            # threading is exercised by deployment, not this fixture test.
            return function(*args)

        with tempfile.TemporaryDirectory() as temporary:
            feed = DirectPaperFeed(temporary, credentials=Credentials())
            feed._http = HTTP()
            feed._market = MarketInfo(TICKER, NOW - 900, NOW, "active")
            feed._rows.append(freeze_data({"epoch_ms": NOW * 1000, "connection_epoch": 1}))
            with patch("strategy_core.paper_feed.NativeWsReceiver", Receiver), patch(
                    "strategy_core.paper_feed.time.time", return_value=NOW), patch(
                    "strategy_core.paper_feed.asyncio.to_thread", fixture_thread_call):
                asyncio.run(feed._refresh_market())
            self.assertEqual(len(feed._rows), 1)
            self.assertEqual(feed._market.ticker, "KXBTC15M-NEW")
            self.assertIsNone(asyncio.run(feed.book_for(TICKER)))

    def test_pending_http_discovery_does_not_block_snapshot_or_shutdown(self):
        async def scenario(directory):
            feed = DirectPaperFeed(directory)
            feed._started = True
            entered = asyncio.Event()
            release = asyncio.Event()
            async def slow_refresh():
                entered.set()
                await release.wait()
            async def fixture_thread_call(function, *args):
                return function(*args)
            feed._refresh_market = slow_refresh
            capture = await feed.next_snapshot(timeout=0)
            await asyncio.sleep(0)
            self.assertTrue(entered.is_set())
            self.assertIsNone(capture.market)
            self.assertFalse(feed._refresh_task.done())
            next_capture = await feed.next_snapshot(timeout=0)
            self.assertGreaterEqual(next_capture.observed_ts, capture.observed_ts)
            with patch("strategy_core.paper_feed.asyncio.to_thread", fixture_thread_call):
                await feed.close()
            self.assertIsNone(feed._refresh_task)
            self.assertTrue(feed._closed)
        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(temporary))


if __name__ == "__main__":
    unittest.main()
