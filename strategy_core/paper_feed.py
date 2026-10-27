"""Direct, read-only venue sources for the Tool Rack PAPER runtime.

The Tool Rack consumes one immutable capture of current native Kalshi depth and
forward Coinbase geometry. No R22 process, run file, policy, startup receipt, or
legacy decision authority is read or imported. Transport reuse is confined to
the isolated marketdata package; it contains no account/order client.

The HTTP book is diagnostic. Only an authenticated, sequence-checked native
WebSocket book supplies PAPER execution depth. A local receipt never becomes an
invented exchange timestamp, and an unchanged observation keeps its old time.
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
import queue
import time
from types import MappingProxyType
from typing import Any, Mapping

from strategy_core.marketdata.btc_observation import FeedFault
from strategy_core.marketdata.btc_transport import PublicFeed
from strategy_core.marketdata.common import parse_time
from strategy_core.marketdata.kalshi_public import (
    MarketDataCredentials, MarketDataError, MarketInfo, PublicMarketClient,
    PublicReceipt, WS_URL, checked_ticker, select_current_market, source_timestamp,
)
from strategy_core.marketdata.native_book import (
    BOOK_MAX_AGE, FUTURE_TOLERANCE, Quote, QuoteHub,
)
from strategy_core.marketdata.native_receiver import NativeWsReceiver
from strategy_core.paper_execution import OfficialResult, PaperBook, PriceLevel
from strategy_core.types import Side


FEED_REVISION = "TOOL_RACK_DIRECT_MARKET_DATA_V1"
GEOMETRY_HISTORY_LIMIT = 3600
BTC_GEOMETRY_MAX_AGE = 3.0


def freeze_data(value: Any) -> Any:
    """Recursively detach and freeze data at the source capture boundary."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): freeze_data(item) for key, item in value.items()})
    if isinstance(value, (list, tuple, deque)):
        return tuple(freeze_data(item) for item in value)
    return value


def plain_data(value: Any) -> Any:
    """JSON-safe copy; unlike asdict, supports immutable mapping proxies."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return {item.name: plain_data(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, deque)):
        return [plain_data(item) for item in value]
    return value


@dataclass(frozen=True)
class FeedSnapshot:
    generation: int
    observed_ts: float
    market: MarketInfo | None
    book: PaperBook | None
    geometry_rows: tuple[Mapping[str, Any], ...]
    source_status: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return plain_data(self)


def paper_book_from_quote(quote: Quote, *, now_ts: float, now_mono: float,
                          sequence_verified: bool, receiver_generation: int,
                          source_generation: int, market_active: bool = True) -> PaperBook:
    """Convert a pinned native observation; never restamp it with poll time."""
    receive_fresh = 0 <= now_mono - quote.observed_mono <= BOOK_MAX_AGE
    source_not_future = quote.exchange_ts is None or quote.exchange_ts <= now_ts + FUTURE_TOLERANCE
    fresh = quote.fresh_at(now_ts, now_mono) and source_not_future
    known_healthy = quote.valid or quote.can_mark("YES") or quote.can_mark("NO")
    current = bool(sequence_verified and fresh and known_healthy and market_active)
    reason = quote.reason if source_not_future else "BOOK_EXCHANGE_TIME_IN_FUTURE"
    return PaperBook(
        ticker=quote.ticker, quote_id=quote.quote_id,
        observed_ts=quote.observed_wall, exchange_ts=quote.exchange_ts,
        yes_bids=tuple(PriceLevel(price, quantity) for price, quantity in quote.yes_levels),
        no_bids=tuple(PriceLevel(price, quantity) for price, quantity in quote.no_levels),
        close_ts=float(quote.close_ts or 0.0), current=current,
        entry_allowed=bool(current and quote.can_buy("YES") and quote.can_buy("NO")),
        yes_sell_allowed=bool(current and quote.can_sell("YES")),
        no_sell_allowed=bool(current and quote.can_sell("NO")),
        source="WS_SEQUENCE_CHECKED_BOOK",
        provenance=freeze_data({
            "feed_revision": FEED_REVISION, "source_generation": source_generation,
            "receiver_generation": receiver_generation,
            "native_quote_generation": quote.generation,
            "sid": quote.sid, "seq": quote.seq,
            "sequence_checked": bool(sequence_verified),
            "snapshot_verified": bool(sequence_verified),
            "monotonic_receive_fresh": receive_fresh,
            "received_monotonic": quote.observed_mono,
            "receive_age_seconds": now_mono - quote.observed_mono,
            "exchange_timestamp_known": quote.exchange_ts is not None,
            "exchange_time_basis": quote.exchange_time_basis,
            "quote_reason": reason, "raw_depth_is_not_a_venue_fill": True,
        }),
    )


def official_result_from_receipt(ticker: str, close_ts: float,
                                 receipt: PublicReceipt) -> OfficialResult | None:
    """Only a final, exact-ticker venue result can settle the PAPER ledger."""
    checked_ticker(ticker)
    body = receipt.body
    market = body.get("market") if isinstance(body, Mapping) else None
    if not isinstance(market, Mapping):
        raise MarketDataError("OFFICIAL_RESULT_MARKET_OBJECT_MISSING")
    if market.get("ticker") != ticker or market.get("market_type") != "binary":
        raise MarketDataError("OFFICIAL_RESULT_WRONG_TICKER_OR_MARKET_TYPE")
    venue_close = source_timestamp(market.get("close_time"))
    if not math.isfinite(close_ts) or abs(venue_close - close_ts) > 0.001:
        raise MarketDataError("OFFICIAL_RESULT_PINNED_CLOSE_MISMATCH")
    if market.get("status") != "finalized" or market.get("is_provisional") is True:
        return None
    result = market.get("result")
    if result not in ("yes", "no"):
        raise MarketDataError("OFFICIAL_RESULT_NOT_BINARY")
    settled = source_timestamp(market.get("settlement_ts"))
    if not close_ts <= settled <= receipt.observed_ts or receipt.observed_ts < close_ts:
        raise MarketDataError("OFFICIAL_RESULT_CHRONOLOGY_INVALID")
    payout = market.get("settlement_value_dollars")
    if payout is not None:
        try:
            value = Decimal(str(payout))
            if not value.is_finite() or value not in (Decimal(0), Decimal(1)):
                raise ValueError
            if (value == 1) != (result == "yes"):
                raise ValueError
        except (ArithmeticError, TypeError, ValueError):
            raise MarketDataError("OFFICIAL_RESULT_PAYOUT_CONFLICT_OR_NONBINARY") from None
    result_id = "KALSHI_FINAL_" + sha256(
        f"{ticker}|{venue_close:.6f}|{settled:.6f}|{result}".encode()).hexdigest()[:32]
    return OfficialResult(
        ticker=ticker, result_id=result_id, result=Side(result.upper()),
        close_ts=close_ts, observed_ts=receipt.observed_ts,
        source="KALSHI_PUBLIC_TLS_GET", final=True,
        provenance=freeze_data({
            "route": receipt.route, "body_sha256": receipt.body_sha256,
            "venue_status": "finalized", "settlement_ts": settled,
            "venue_result": result, "settlement_value_dollars": payout,
            "market": market, "request_duration": receipt.request_duration,
            "btc_price_or_local_clock_did_not_determine_result": True,
        }),
    )


class DirectPaperFeed:
    """Async facade over independent bounded read-only source workers.

    All snapshot assembly runs in the caller's event-loop thread. Kalshi folds
    native deltas under its receiver lock; BTC emits detached parser rows. This
    captures known source states, without claiming exchange simultaneity or
    comparing a captured frame to a later mutable producer.
    """

    def __init__(self, out_dir: str | Path, *,
                 credential_dir: str | Path = Path(r"C:\KalshiBTCBot"),
                 credentials: MarketDataCredentials | None = None,
                 history_limit: int = GEOMETRY_HISTORY_LIMIT):
        if not 1800 <= history_limit <= 10000:
            raise ValueError("BOUNDED_GEOMETRY_HISTORY_1800_TO_10000_REQUIRED")
        self.out_dir = Path(out_dir)
        self.credential_dir = Path(credential_dir)
        self._credentials = credentials
        self._http = PublicMarketClient()
        self._btc = PublicFeed(self.out_dir)
        self._native: NativeWsReceiver | None = None
        self._hub = QuoteHub()
        self._market: MarketInfo | None = None
        self._rows: deque[Mapping[str, Any]] = deque(maxlen=history_limit)
        self._btc_epoch: int | None = None
        self._btc_usable = False
        self._generation = 0
        self._receiver_generation = 0
        self._last_quote_id: str | None = None
        self._last_geometry_serial: tuple[int, int] | None = None
        self._last_source_error: str | None = None
        self._last_discovery_error: str | None = None
        self._last_rest_error: str | None = None
        self._latest_rest: Mapping[str, Any] | None = None
        self._next_market_check = 0.0
        self._refresh_task: asyncio.Task | None = None
        self._last_emit_mono = 0.0
        self._started = False
        self._closed = False
        self._tape = None
        self._tape_last_flush = 0.0
        self._source_bytes = 0
        self._final_results: dict[str, OfficialResult] = {}

    def _record(self, kind: str, data: Any) -> None:
        if self._tape is None:
            return
        row = {"kind": kind, "recorded_ts": time.time(), "data": plain_data(data)}
        payload = json.dumps(row, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n"
        self._source_bytes += len(payload.encode("utf-8"))
        if self._source_bytes > 1_000_000_000:
            raise MarketDataError("SOURCE_CAPTURE_BYTE_LIMIT")
        try:
            self._tape.write(payload)
            if time.monotonic() - self._tape_last_flush >= 1.0:
                self._tape.flush()
                self._tape_last_flush = time.monotonic()
        except OSError:
            raise MarketDataError("SOURCE_CAPTURE_WRITE_FAILED") from None

    async def start(self) -> None:
        if self._started or self._closed:
            raise MarketDataError("DIRECT_FEED_ALREADY_STARTED_OR_CLOSED")
        if self._credentials is None:
            self._credentials = MarketDataCredentials.resolve(self.credential_dir)
        # Fail dependency checks before creating source workers or partial files.
        try:
            from websockets.sync.client import connect  # noqa: F401
            import websockets  # noqa: F401
        except ImportError:
            raise MarketDataError("EXISTING_WEBSOCKETS_DEPENDENCY_UNAVAILABLE") from None
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._tape = (self.out_dir / "market_data_source.jsonl").open("x", encoding="utf-8")
        self._started = True
        self._record("SOURCE_START", {"revision": FEED_REVISION, "account_access": False,
                                      "order_access": False, "legacy_strategy_imported": False})
        self._btc.start()
        await self._refresh_market()

    async def _refresh_market(self) -> None:
        self._next_market_check = time.monotonic() + 10.0
        try:
            receipt = await asyncio.to_thread(self._http.discovery)
            market = select_current_market(receipt.body, time.time())
            self._last_discovery_error = None
            self._record("MARKET_DISCOVERY", receipt)
        except MarketDataError as exc:
            self._last_discovery_error = str(exc)
            self._next_market_check = time.monotonic() + 3.0
            self._record("MARKET_DISCOVERY_WAIT", {"reason": str(exc)})
            return
        if self._market is not None and self._market.ticker == market.ticker:
            if self._market.close_ts != market.close_ts:
                raise MarketDataError("CURRENT_MARKET_CLOSE_CHANGED")
            self._market = market
            self._next_market_check = time.monotonic() + min(10.0, max(0.25, market.close_ts - time.time()))
            return
        if self._native is not None:
            await asyncio.to_thread(self._native.stop, 3.0)
        self._market = market
        self._next_market_check = time.monotonic() + min(10.0, max(0.25, market.close_ts - time.time()))
        self._receiver_generation = 0
        self._last_quote_id = None
        self._latest_rest = None
        self._generation += 1
        self._hub.begin(market.ticker, market.close_ts, time.time(), time.monotonic())
        subscription = {"id": 1, "cmd": "subscribe", "params": {
            "channels": ["orderbook_delta", "ticker"], "market_tickers": [market.ticker]}}
        self._native = NativeWsReceiver(
            WS_URL, {}, subscription, ticker=market.ticker,
            headers_factory=self._credentials.websocket_headers,
            reconnect_delay=1.0,
        )
        self._native.start()
        self._record("MARKET_ROLLOVER", market)
        # A REST snapshot is useful for diagnostics but cannot anchor WS seq.
        try:
            rest = await asyncio.to_thread(self._http.orderbook, market.ticker)
            self._latest_rest = freeze_data({"ticker": market.ticker, "observed_ts": rest.observed_ts,
                                            "body_sha256": rest.body_sha256, "diagnostic_only": True})
            self._last_rest_error = None
            self._record("REST_BOOK_DIAGNOSTIC", rest)
        except MarketDataError as exc:
            self._last_rest_error = str(exc)
            self._record("REST_BOOK_WAIT", {"reason": str(exc), "ticker": market.ticker})

    def _drain_btc(self) -> None:
        for _ in range(10000):
            try:
                item = self._btc.queue.get_nowait()
            except queue.Empty:
                break
            kind, row = item.get("kind"), item.get("row") or {}
            if kind == "btc_gap":
                self._btc_usable = False
                self._rows.clear()
                self._last_geometry_serial = None
                self._last_source_error = str(row.get("reason") or "BTC_SOURCE_GAP")
                self._generation += 1
                self._record("BTC_GEOMETRY_RESET", row)
            elif kind == "btc_status":
                epoch = row.get("epoch")
                if epoch != self._btc_epoch:
                    self._rows.clear()
                    self._btc_usable = False
                    self._last_geometry_serial = None
                    self._btc_epoch = epoch
                    self._generation += 1
                self._record("BTC_STATUS", row)
            elif kind == "btc_geometry":
                epoch = int(row.get("connection_epoch"))
                serial = int(row.get("sample_serial"))
                if epoch != self._btc_epoch:
                    self._rows.clear()
                    self._btc_epoch = epoch
                    self._last_geometry_serial = None
                if self._last_geometry_serial == (epoch, serial):
                    continue
                timestamp = parse_time(row.get("timestamp"))
                copied = dict(row)
                copied["epoch_ms"] = timestamp * 1000.0
                copied["source_observed_ts"] = float(item["observed_at"])
                copied["source_row_id"] = f"COINBASE:{epoch}:{serial}"
                copied["historical_seed_is_not_forward_observation"] = True
                frozen = freeze_data(copied)
                self._rows.append(frozen)
                self._last_geometry_serial = (epoch, serial)
                self._btc_usable = True
                self._last_source_error = None
                self._generation += 1
                self._record("BTC_GEOMETRY", frozen)
        if self._btc.error:
            self._btc_usable = False
            self._last_source_error = "BTC_WORKER_" + str(self._btc.error)

    def _drain_native(self) -> None:
        if self._native is None:
            return
        for item in self._native.drain_nowait():
            generation = int(item.get("generation") or 0)
            if generation != self._receiver_generation:
                self._receiver_generation = generation
                self._hub.reconnect(float(item["received_wall"]), float(item["received_mono"]), generation)
                self._generation += 1
            if item.get("kind") == "receiver":
                self._record("NATIVE_RECEIVER_EVENT", item)
                if item.get("event") in ("DISCONNECTED", "BOOK_FOLD_INVALID", "FORCED_RECONNECT", "STOPPED"):
                    self._hub.reconnect(float(item["received_wall"]), float(item["received_mono"]), generation)
                    self._generation += 1
            elif item.get("kind") == "message":
                data = item.get("data")
                self._hub.on_ws(data, float(item["received_wall"]), float(item["received_mono"]))
                if item.get("folded_current_book"):
                    self._generation += 1
                    self._record("NATIVE_SEQUENCE_CHECKED_BOOK", item)
        for event in self._hub.drain():
            self._record("NATIVE_BOOK_PROVENANCE", event)
        request = self._hub.resnapshot_request(time.time(), time.monotonic())
        if request is not None:
            self._native.send_json(request)

    def _capture(self) -> FeedSnapshot:
        self._drain_btc()
        self._drain_native()
        wall, mono = time.time(), time.monotonic()
        book = None
        if self._market is not None:
            quote = self._hub.view(wall, mono)
            book = paper_book_from_quote(
                quote, now_ts=wall, now_mono=mono,
                sequence_verified=bool(self._hub.book_ok and quote.sid is not None and quote.seq is not None),
                receiver_generation=self._receiver_generation, source_generation=self._generation,
                market_active=bool(self._market.open_ts <= wall < self._market.close_ts),
            )
        age = None
        receive_age = None
        if self._rows:
            age = wall - float(self._rows[-1]["epoch_ms"]) / 1000.0
            receive_age = mono - float(self._rows[-1]["received_monotonic"])
        btc_current = bool(self._btc_usable and age is not None and receive_age is not None
                           and -FUTURE_TOLERANCE <= age <= BTC_GEOMETRY_MAX_AGE
                           and 0 <= receive_age <= BTC_GEOMETRY_MAX_AGE)
        status = freeze_data({
            "revision": FEED_REVISION, "started": self._started, "closed": self._closed,
            "btc_current": btc_current, "btc_geometry_age_seconds": age,
            "btc_geometry_receive_age_seconds": receive_age, "btc_connection_epoch": self._btc_epoch,
            "geometry_rows": len(self._rows), "geometry_source": "DIRECT_COINBASE_PUBLIC_TRADES",
            "btc": self._btc.status(),
            "native": self._native.snapshot() if self._native is not None else None,
            "book_current": bool(book and book.current),
            "entry_quote_available": bool(book and book.entry_allowed),
            "source_error": self._last_source_error,
            "discovery_error": self._last_discovery_error, "rest_diagnostic_error": self._last_rest_error,
            "rest_book": self._latest_rest,
            "captured_together_without_producer_reread": True,
            "different_exchanges_are_not_claimed_simultaneous": True,
            "legacy_strategy_authority": False,
        })
        return FeedSnapshot(self._generation, wall, self._market, book, tuple(self._rows), status)

    async def next_snapshot(self, timeout: float = 1.0) -> FeedSnapshot:
        if not self._started or self._closed:
            raise MarketDataError("DIRECT_FEED_NOT_RUNNING")
        if not 0 <= timeout <= 30:
            raise ValueError("SNAPSHOT_TIMEOUT_OUT_OF_RANGE")
        # Do not busy-spin unchanged state. Network threads keep draining while
        # the consumer writes its own durable decision/execution records.
        wait = min(timeout, max(0.0, 0.25 - (time.monotonic() - self._last_emit_mono)))
        if wait:
            await asyncio.sleep(wait)
        # Periodic HTTP work must not block held-position management. The
        # network task publishes a complete market/hub/receiver transition only
        # between awaits; snapshots keep the last available immutable evidence.
        if self._refresh_task is not None and self._refresh_task.done():
            completed, self._refresh_task = self._refresh_task, None
            completed.result()  # Surface integrity/write failures to the owner.
        if self._refresh_task is None and time.monotonic() >= self._next_market_check:
            self._refresh_task = asyncio.create_task(self._refresh_market(), name="ToolRackMarketDiscovery")
        snapshot = self._capture()
        self._last_emit_mono = time.monotonic()
        return snapshot

    async def book_for(self, ticker: str) -> PaperBook | None:
        """Exact-ticker current book only; never substitute the new contract."""
        checked_ticker(ticker)
        if not self._started or self._closed or self._market is None or ticker != self._market.ticker:
            return None
        return self._capture().book

    async def official_result(self, ticker: str, close_ts: float) -> OfficialResult | None:
        checked_ticker(ticker)
        cached = self._final_results.get(ticker)
        if cached is not None:
            if cached.close_ts != close_ts:
                raise MarketDataError("FINAL_RESULT_REQUEST_CLOSE_CHANGED")
            return cached
        receipt = await asyncio.to_thread(self._http.market, ticker)
        result = official_result_from_receipt(ticker, close_ts, receipt)
        self._record("OFFICIAL_MARKET_RESULT_READ", receipt)
        if result is not None:
            self._final_results[ticker] = result
            self._record("OFFICIAL_FINAL_RESULT", result)
        return result

    def status(self) -> dict[str, Any]:
        return {"revision": FEED_REVISION, "started": self._started, "closed": self._closed,
                "market": plain_data(self._market), "source_generation": self._generation,
                "btc": self._btc.status(), "geometry_rows": len(self._rows),
                "native": self._native.snapshot() if self._native else None,
                "source_error": self._last_source_error, "discovery_error": self._last_discovery_error}

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        errors = []
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                errors.append("DISCOVERY_STOP_" + type(exc).__name__)
            self._refresh_task = None
        if self._native is not None:
            try:
                await asyncio.to_thread(self._native.stop, 5.0)
            except Exception as exc:
                errors.append("NATIVE_STOP_" + type(exc).__name__)
        if self._started:
            try:
                await asyncio.to_thread(self._btc.stop, 15.0)
            except Exception as exc:
                errors.append("BTC_STOP_" + (str(exc) if isinstance(exc, FeedFault) else type(exc).__name__))
        if self._tape is not None:
            try:
                self._record("SOURCE_STOP", {"errors": errors})
                self._tape.flush()
            finally:
                self._tape.close()
                self._tape = None
        if errors:
            raise MarketDataError(";".join(errors))
