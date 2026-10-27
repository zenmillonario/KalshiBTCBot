"""Fixed Kalshi market-data reads and market-data-only WebSocket signing.

There is no account client, generic HTTP method, order endpoint, balance query,
or credential mutation. Only the fixed WS handshake path can be signed.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Mapping
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode


API_BASE = "https://external-api.kalshi.com/trade-api/v2"
WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"
SERIES = "KXBTC15M"
TICKER_PATTERN = re.compile(r"^KXBTC15M-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
MAX_RESPONSE_BYTES = 2_000_000


class MarketDataError(RuntimeError):
    """Locally constructed reason codes only; never secret/response text."""


def checked_ticker(ticker: str) -> str:
    if not isinstance(ticker, str) or len(ticker) > 100 or not TICKER_PATTERN.fullmatch(ticker):
        raise MarketDataError("MARKET_TICKER_OUTSIDE_KXBTC15M")
    return ticker


def source_timestamp(value: Any) -> float:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        timestamp = parsed.timestamp()
        if not math.isfinite(timestamp) or timestamp <= 0:
            raise ValueError
        return float(timestamp)
    except (TypeError, ValueError, OverflowError):
        raise MarketDataError("VENUE_TIMESTAMP_MISSING_OR_INVALID") from None


@dataclass(frozen=True)
class MarketInfo:
    ticker: str
    open_ts: float
    close_ts: float
    status: str
    title: str = ""
    # Display-only exact-market metadata. Neither field grants a permission or
    # determines settlement; missing/unsupported strikes stay unavailable.
    target: float | None = None
    target_source: str | None = None

    @property
    def interval_start_ts(self) -> float:
        # Venue listing/open time can precede the BTC fifteen-minute interval.
        return self.close_ts - 900.0


@dataclass(frozen=True)
class PublicReceipt:
    body: Mapping[str, Any]
    observed_ts: float
    request_duration: float
    body_sha256: str
    route: str


def select_current_market(body: Mapping[str, Any], now_ts: float) -> MarketInfo:
    rows = body.get("markets") if isinstance(body, Mapping) else None
    if not isinstance(rows, list):
        raise MarketDataError("MARKET_DISCOVERY_SCHEMA_INVALID")
    choices = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        try:
            ticker = checked_ticker(row.get("ticker"))
            opened = source_timestamp(row.get("open_time"))
            closed = source_timestamp(row.get("close_time"))
        except MarketDataError:
            continue
        if (row.get("market_type") != "binary"
                or row.get("status") not in ("open", "active")
                or row.get("is_provisional") is True
                or not opened <= now_ts < closed
                or not closed - 900.0 <= now_ts):
            continue
        target = None
        if row.get("strike_type") in ("greater", "greater_or_equal"):
            raw_target = row.get("floor_strike")
            try:
                candidate = float(raw_target) if not isinstance(raw_target, bool) else float("nan")
                if math.isfinite(candidate) and candidate > 0:
                    target = candidate
            except (TypeError, ValueError, OverflowError):
                pass
        choices.append(MarketInfo(
            ticker, opened, closed, str(row["status"]), str(row.get("title") or ""),
            target, "KALSHI_MARKET_FLOOR_STRIKE" if target is not None else None))
    if not choices:
        raise MarketDataError("NO_CURRENT_OPEN_KXBTC15M_MARKET")
    return min(choices, key=lambda market: (market.close_ts, market.ticker))


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise MarketDataError("PUBLIC_MARKET_REDIRECT_REFUSED")


class PublicMarketClient:
    """Only unauthenticated GET of discovery, exact market, and its book."""

    def __init__(self, *, timeout: float = 5.0):
        if not 0 < timeout <= 10:
            raise ValueError("BOUNDED_PUBLIC_TIMEOUT_REQUIRED")
        self.timeout = timeout
        self._opener = request.build_opener(_NoRedirect())

    def _get(self, route: str, query: Mapping[str, Any] | None = None) -> PublicReceipt:
        allowed = route == "/markets" or bool(re.fullmatch(
            r"/markets/KXBTC15M-[A-Z0-9]+(?:-[A-Z0-9]+)*(?:/orderbook)?", route))
        if not allowed:
            raise MarketDataError("PUBLIC_ROUTE_OUTSIDE_MARKET_DATA_ALLOWLIST")
        url = API_BASE + route
        if query:
            if route != "/markets" or set(query) - {"status", "series_ticker", "limit", "cursor"}:
                raise MarketDataError("PUBLIC_QUERY_OUTSIDE_DISCOVERY_ALLOWLIST")
            if query.get("status") != "open" or query.get("series_ticker") != SERIES:
                raise MarketDataError("PUBLIC_DISCOVERY_QUERY_INVALID")
            url += "?" + urlencode(query)
        req = request.Request(url, method="GET", headers={
            "Accept": "application/json", "Cache-Control": "no-cache",
            "User-Agent": "Tachyos-ToolRack-MarketData/1.0",
        })
        begun = time.monotonic()
        try:
            with self._opener.open(req, timeout=self.timeout) as response:
                if response.status != 200 or response.geturl() != url:
                    raise MarketDataError("PUBLIC_MARKET_ORIGIN_OR_STATUS_INVALID")
                content = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise MarketDataError("PUBLIC_MARKET_HTTP_" + str(exc.code)) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise MarketDataError("PUBLIC_MARKET_TRANSPORT_" + type(exc).__name__) from None
        duration = time.monotonic() - begun
        observed = time.time()
        if len(content) > MAX_RESPONSE_BYTES:
            raise MarketDataError("PUBLIC_MARKET_RESPONSE_OVERSIZED")
        try:
            body = json.loads(content)
        except (ValueError, UnicodeError):
            raise MarketDataError("PUBLIC_MARKET_JSON_INVALID") from None
        if not isinstance(body, dict):
            raise MarketDataError("PUBLIC_MARKET_OBJECT_REQUIRED")
        return PublicReceipt(body, observed, duration, sha256(content).hexdigest(), route)

    def discovery(self) -> PublicReceipt:
        rows = []
        cursor = None
        receipts = []
        for _ in range(5):
            query = {"status": "open", "series_ticker": SERIES, "limit": 200}
            if cursor:
                query["cursor"] = cursor
            receipt = self._get("/markets", query)
            found = receipt.body.get("markets")
            if not isinstance(found, list):
                raise MarketDataError("MARKET_DISCOVERY_SCHEMA_INVALID")
            rows.extend(found)
            receipts.append(receipt)
            cursor = receipt.body.get("cursor")
            if not cursor:
                return PublicReceipt({"markets": rows}, receipt.observed_ts,
                                     sum(item.request_duration for item in receipts),
                                     sha256("".join(item.body_sha256 for item in receipts).encode()).hexdigest(),
                                     "/markets")
            if not isinstance(cursor, str) or len(cursor) > 2048:
                raise MarketDataError("MARKET_DISCOVERY_CURSOR_INVALID")
        raise MarketDataError("MARKET_DISCOVERY_PAGE_LIMIT")

    def market(self, ticker: str) -> PublicReceipt:
        return self._get("/markets/" + checked_ticker(ticker))

    def orderbook(self, ticker: str) -> PublicReceipt:
        return self._get("/markets/" + checked_ticker(ticker) + "/orderbook")


def _local_env_values(directory: Path) -> dict[str, str]:
    """Read the two existing settings without executing/interpolating .env."""
    path = directory / ".env"
    try:
        if not path.is_file():
            return {}
        if path.stat().st_size > 100_000:
            raise MarketDataError("CREDENTIAL_CONFIG_OVERSIZED")
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise MarketDataError("CREDENTIAL_CONFIG_UNREADABLE") from None
    values = {}
    wanted = {"KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY_PATH"}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        name, separator, raw = stripped.partition("=")
        if not separator or name.strip() not in wanted:
            continue
        raw = raw.strip()
        if raw[:1] in ("'", '"'):
            quote = raw[0]
            end = raw.find(quote, 1)
            tail = raw[end + 1:].strip() if end >= 0 else ""
            if end < 0 or (tail and not tail.startswith("#")):
                raise MarketDataError("CREDENTIAL_CONFIG_FORMAT_INVALID")
            value = raw[1:end]
        else:
            value = raw.split(" #", 1)[0].rstrip()
        values[name.strip()] = value
    return values


@dataclass(frozen=True, repr=False)
class MarketDataCredentials:
    """Secret-bearing object: repr/str never print key ID, key, or key path."""
    _key_id: str = field(repr=False)
    _private_key: Any = field(repr=False)

    def __repr__(self) -> str:
        return "MarketDataCredentials(configured=True, scope='market-data-websocket')"

    @classmethod
    def resolve(cls, directory: str | Path = Path(r"C:\KalshiBTCBot"),
                environ: Mapping[str, str] | None = None) -> "MarketDataCredentials":
        directory = Path(directory)
        env = os.environ if environ is None else environ
        config = _local_env_values(directory)
        key_id = env.get("KALSHI_API_KEY_ID", config.get("KALSHI_API_KEY_ID"))
        raw_path = env.get("KALSHI_PRIVATE_KEY_PATH", config.get("KALSHI_PRIVATE_KEY_PATH"))
        if not isinstance(key_id, str) or not key_id.strip():
            raise MarketDataError("MARKET_DATA_KEY_ID_NOT_CONFIGURED")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise MarketDataError("MARKET_DATA_PRIVATE_KEY_PATH_NOT_CONFIGURED")
        key_path = Path(os.path.expandvars(raw_path)).expanduser()
        if not key_path.is_absolute():
            key_path = directory / key_path
        try:
            if key_path.stat().st_size > 100_000:
                raise MarketDataError("MARKET_DATA_PRIVATE_KEY_OVERSIZED")
            key_bytes = key_path.read_bytes()
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
            key = serialization.load_pem_private_key(key_bytes, password=None)
            if not isinstance(key, (RSAPrivateKey, Ed25519PrivateKey)):
                raise MarketDataError("MARKET_DATA_PRIVATE_KEY_TYPE_UNSUPPORTED")
        except MarketDataError:
            raise
        except ImportError:
            raise MarketDataError("EXISTING_CRYPTOGRAPHY_DEPENDENCY_UNAVAILABLE") from None
        except Exception:
            raise MarketDataError("MARKET_DATA_PRIVATE_KEY_UNAVAILABLE_OR_INVALID") from None
        return cls(key_id.strip(), key)

    def websocket_headers(self) -> dict[str, str]:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        timestamp = str(int(time.time() * 1000))
        message = (timestamp + "GET" + WS_PATH).encode("utf-8")
        if isinstance(self._private_key, Ed25519PrivateKey):
            signature = self._private_key.sign(message)
        else:
            signature = self._private_key.sign(message, padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256().digest_size), hashes.SHA256())
        return {"KALSHI-ACCESS-KEY": self._key_id,
                "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("ascii"),
                "KALSHI-ACCESS-TIMESTAMP": timestamp}
