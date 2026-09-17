# Tachys V6.3 - 2-minute observe + strong-only 2-4m + 50% TP through minute 10
import os
import time
import base64
import asyncio
import json
import csv
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
import websockets
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")
PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH")

API_BASE = "https://external-api.kalshi.com/trade-api/v2"
REST_URL = f"{API_BASE}/markets"
WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"

SERIES = "KXBTC15M"

# Two paper-entry grades. CONFIRMED preserves the V3 rules exactly.
EARLY_ENTRY_ASK = 0.40
CONFIRMED_ENTRY_ASK = 0.50
MAX_ENTRY_ASK = 0.80

EARLY_MOM_90_75 = 0.01
EARLY_MOM_90_60 = 0.03
CONFIRMED_MOM_90_75 = 0.02
CONFIRMED_MOM_90_60 = 0.05

HISTORY_SECONDS = 300
RECONNECT_DELAY = 1
REST_POLL_SECONDS = 1.0
WS_RECV_TIMEOUT = 0.50
STATUS_SECONDS = 15

# New schema because signals now include YES/NO side.
LOG_FILE = "tachys_signals_v7.csv"
RESULT_LOG_FILE = "tachys_contract_results.csv"
REVERSAL_LOG_FILE = "tachys_reversal_watch.csv"
PAPER_LOG_FILE = "tachys_paper_trades_v7.csv"

# Paper money-management experiment. Fixed maximum stake per entry.
PAPER_STAKE = 5.00
A_PLUS_PAPER_STAKE = 10.00

# V7 contract phases. A 15-minute contract starts with a HARD 2-minute
# observation window. From minute 2 to minute 4, only stronger A/A+ signals
# may enter; weaker EARLY/CONFIRMED grades are logged but blocked. Trades
# entered from minute 2 through minute 10 bank +50% immediately so profit can
# be recycled into a fresh setup later in the same contract.
OBSERVATION_SECONDS = 120          # first 2:00: data gathering only
STRONG_ONLY_WINDOW_SECONDS = 240   # 2:00-4:00: A/A+ entries only
EARLY_PROFIT_WINDOW_SECONDS = 600  # entries from 2:00-10:00 use +50% take-profit
EXPIRY_MODE_SECONDS = 60           # final 1:00
EARLY_TAKE_PROFIT_ROI = 0.50       # bank +50% on early trades
EARLY_MIN_BTC_NET_MOVE_60S = 30.0
EARLY_MIN_TREND_EFFICIENCY = 0.55
EARLY_MIN_MOM_90_75 = 0.03
EARLY_MIN_MOM_90_60 = 0.06
# V5: the old fixed -20% stop is no longer the primary exit.
# Early in the contract, give the thesis room. Late in the contract,
# time + target relationship matter more. A deep emergency stop remains
# only as a paper-risk guardrail while we collect data.
EMERGENCY_STOP_LOSS = 0.60
LATE_RISK_WINDOW_SECONDS = 300
LATE_TARGET_STOP_ROI = -0.20
TRAIL_ACTIVATE_ROI = 0.40       # start trailing after +40%
TRAIL_GIVEBACK_ROI = 0.20       # exit after 20 percentage-point giveback from peak
PAPER_REENTRY_COOLDOWN = 20
PROFIT_MILESTONES = (0.20, 0.30, 0.40, 0.50, 0.60, 0.75, 0.90, 1.00)
ET = ZoneInfo("America/New_York")

BTC_WS_URL = "wss://advanced-trade-ws.coinbase.com"
BTC_PRODUCT = "BTC-USD"
BTC_CANDLES_URL = f"https://api.exchange.coinbase.com/products/{BTC_PRODUCT}/candles"
REVERSAL_THRESHOLDS = (200, 250, 300)

# EMA is still informational only. It is NOT an entry filter.
EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 30

SIDES = ("YES", "NO")

active_target = ""
paper_positions = {"YES": None, "NO": None}
last_paper_exit_time = {"YES": 0.0, "NO": 0.0}
paper_trade_counter = 0
paper_realized_pnl = 0.0
contract_trade_ids = {}
contract_trade_records = {}
btc_tick_history = []
btc_trade_volume_history = []
btc_current_minute_ohlc = None
btc_current_minute_volume = 0.0
btc_completed_candles = []


# ============================================================
# AUTH
# ============================================================

def load_private_key():
    with open(PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(
            f.read(),
            password=None,
        )


def create_signature(private_key):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + "GET" + "/trade-api/ws/v2"

    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )

    return timestamp, base64.b64encode(signature).decode()


# ============================================================
# MARKET HELPERS
# ============================================================

def iso_to_timestamp(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).timestamp()
    except (ValueError, TypeError):
        return None


def get_current_market():
    """
    Choose the KXBTC15M market whose close time is the nearest one
    still in the future. This prevents getting stuck on an old/open
    listing when several 15-minute markets are returned.
    """
    params = {
        "series_ticker": SERIES,
        "status": "open",
        "limit": 100,
    }

    response = requests.get(
        REST_URL,
        params=params,
        timeout=10,
    )
    response.raise_for_status()

    markets = response.json().get("markets", [])
    if not markets:
        return None

    now = time.time()
    future_markets = []

    for market in markets:
        close_ts = iso_to_timestamp(market.get("close_time"))
        if close_ts is not None and close_ts > now:
            future_markets.append((close_ts, market))

    if not future_markets:
        return None

    future_markets.sort(key=lambda item: item[0])
    return future_markets[0][1]


def get_market_snapshot(ticker):
    response = requests.get(
        f"{REST_URL}/{ticker}",
        timeout=5,
    )
    response.raise_for_status()
    return response.json().get("market", {})


def to_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def extract_top_of_book(source):
    """
    Return (yes_ask, no_ask).

    Prefer explicit ask fields. If an ask is absent, reconstruct it
    from the opposite-side bid, which is valid for a binary market:
      YES ask = 1 - NO bid
      NO ask  = 1 - YES bid
    """
    if not isinstance(source, dict):
        return None, None

    yes_ask = to_float(source.get("yes_ask_dollars"))
    no_ask = to_float(source.get("no_ask_dollars"))
    yes_bid = to_float(source.get("yes_bid_dollars"))
    no_bid = to_float(source.get("no_bid_dollars"))

    if yes_ask is None and no_bid is not None:
        yes_ask = max(0.0, min(1.0, 1.0 - no_bid))

    if no_ask is None and yes_bid is not None:
        no_ask = max(0.0, min(1.0, 1.0 - yes_bid))

    return yes_ask, no_ask


# ============================================================
# BTC/USD FEED + 1-MINUTE EMA ENGINE
# ============================================================

btc_last_price = None
btc_connected = False
btc_updates = 0

btc_minute_closes = []
btc_current_minute = None
btc_current_minute_price = None
btc_ema_9 = None
btc_ema_30 = None

pending_settlements = set()
logged_settlements = set()


def _ema_from_values(values, period):
    """Standard EMA seeded by the SMA of the first `period` closes."""
    if len(values) < period:
        return None
    ema = sum(values[:period]) / period
    k = 2 / (period + 1)
    for value in values[period:]:
        ema = (value - ema) * k + ema
    return ema


def update_btc_ema(include_live_candle=True):
    """
    Recompute BTC EMA from the historical 1-minute close series.

    When include_live_candle=True, append the current forming candle's latest
    price as its provisional close. This mirrors how charting platforms show
    a live EMA that moves during the current 1-minute candle.
    """
    global btc_ema_9
    global btc_ema_30

    values = [p for _, p in btc_minute_closes]
    if include_live_candle and btc_current_minute_price is not None:
        values = values + [btc_current_minute_price]

    btc_ema_9 = _ema_from_values(values, EMA_FAST_PERIOD)
    btc_ema_30 = _ema_from_values(values, EMA_SLOW_PERIOD)


def bootstrap_btc_history():
    """Load historical Coinbase 1-minute candles before the live feed starts."""
    global btc_minute_closes
    global btc_completed_candles

    try:
        response = requests.get(
            BTC_CANDLES_URL,
            params={"granularity": 60},
            headers={"User-Agent": "Tachys/6.3"},
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("Unexpected Coinbase candle response")

        current_minute = int(time.time() // 60) * 60
        parsed = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                continue
            ts = int(row[0])
            if ts >= current_minute:
                continue  # never seed from the still-forming candle
            parsed.append({
                "minute": ts,
                "low": float(row[1]),
                "high": float(row[2]),
                "open": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })

        parsed.sort(key=lambda c: c["minute"])
        parsed = parsed[-120:]
        if len(parsed) < EMA_SLOW_PERIOD:
            raise ValueError(f"Only {len(parsed)} completed candles returned")

        btc_minute_closes = [(c["minute"], c["close"]) for c in parsed]
        btc_completed_candles = list(parsed)
        update_btc_ema(include_live_candle=False)
        print(
            f"BTC EMA bootstrap: {len(parsed)} completed 1m candles loaded "
            f"| EMA9=${btc_ema_9:,.2f} | EMA30=${btc_ema_30:,.2f}"
        )
        return True
    except Exception as exc:
        print(f"⚠️ BTC EMA bootstrap failed: {exc}")
        print("EMA will warm from live candles; EMA-based grades are less reliable until then.")
        return False


def process_btc_price(price, now=None):
    global btc_last_price
    global btc_updates
    global btc_current_minute
    global btc_current_minute_price
    global btc_current_minute_ohlc
    global btc_current_minute_volume

    if price is None:
        return
    if now is None:
        now = time.time()

    btc_last_price = price
    btc_updates += 1
    btc_tick_history.append((now, price))
    cutoff = now - 600
    while btc_tick_history and btc_tick_history[0][0] < cutoff:
        btc_tick_history.pop(0)

    minute_ts = int(now // 60) * 60

    if btc_current_minute is None:
        btc_current_minute = minute_ts
        btc_current_minute_price = price
        btc_current_minute_ohlc = {"open": price, "high": price, "low": price, "close": price}
        update_btc_ema(include_live_candle=True)
        return

    if minute_ts == btc_current_minute:
        btc_current_minute_price = price
        if btc_current_minute_ohlc is None:
            btc_current_minute_ohlc = {"open": price, "high": price, "low": price, "close": price}
        else:
            btc_current_minute_ohlc["high"] = max(btc_current_minute_ohlc["high"], price)
            btc_current_minute_ohlc["low"] = min(btc_current_minute_ohlc["low"], price)
            btc_current_minute_ohlc["close"] = price
        update_btc_ema(include_live_candle=True)
        return

    btc_minute_closes.append((btc_current_minute, btc_current_minute_price))
    if len(btc_minute_closes) > 120:
        btc_minute_closes.pop(0)

    if btc_current_minute_ohlc is not None:
        candle = dict(btc_current_minute_ohlc)
        candle["minute"] = btc_current_minute
        candle["volume"] = btc_current_minute_volume
        btc_completed_candles.append(candle)
        if len(btc_completed_candles) > 120:
            btc_completed_candles.pop(0)

    btc_current_minute = minute_ts
    btc_current_minute_price = price
    btc_current_minute_ohlc = {"open": price, "high": price, "low": price, "close": price}
    btc_current_minute_volume = 0.0
    update_btc_ema(include_live_candle=True)


def process_btc_trade_volume(size, now=None):
    global btc_current_minute_volume
    if size is None:
        return
    if now is None:
        now = time.time()
    btc_current_minute_volume += max(0.0, float(size))
    btc_trade_volume_history.append((now, float(size)))
    cutoff = now - 600
    while btc_trade_volume_history and btc_trade_volume_history[0][0] < cutoff:
        btc_trade_volume_history.pop(0)


def extract_coinbase_trades(data):
    trades = []
    if not isinstance(data, dict):
        return trades
    for event in data.get("events", []) or []:
        if not isinstance(event, dict):
            continue
        for trade in event.get("trades", []) or []:
            if not isinstance(trade, dict) or trade.get("product_id") != BTC_PRODUCT:
                continue
            price = to_float(trade.get("price"))
            size = to_float(trade.get("size"))
            if price is not None:
                trades.append((price, size))
    return trades


def btc_range(seconds, now=None):
    if now is None:
        now = time.time()
    vals = [p for ts, p in btc_tick_history if ts >= now - seconds]
    return (max(vals) - min(vals)) if len(vals) >= 2 else None


def btc_change(seconds, now=None):
    """Net BTC move over the requested lookback."""
    if now is None:
        now = time.time()
    vals = [(ts, p) for ts, p in btc_tick_history if ts >= now - seconds]
    if len(vals) < 2:
        return None
    return vals[-1][1] - vals[0][1]


def btc_trend_efficiency(seconds=60, bucket_seconds=5, now=None):
    """
    Directional efficiency of BTC over a recent window.
    1.0 is nearly straight-line movement; values near 0 are choppy.
    Uses 5-second buckets so individual exchange ticks do not dominate.
    """
    if now is None:
        now = time.time()
    pts = [(ts, p) for ts, p in btc_tick_history if ts >= now - seconds]
    if len(pts) < 3:
        return None

    buckets = {}
    for ts, price in pts:
        key = int(ts // bucket_seconds)
        buckets[key] = price
    sampled = [buckets[k] for k in sorted(buckets)]
    if len(sampled) < 3:
        return None

    path = sum(abs(sampled[i] - sampled[i-1]) for i in range(1, len(sampled)))
    if path <= 0:
        return 0.0
    return abs(sampled[-1] - sampled[0]) / path


def contract_phase(close_ts, now=None):
    if now is None:
        now = time.time()
    if close_ts is None:
        return "CORE", None, None
    seconds_left = max(0.0, close_ts - now)
    elapsed = max(0.0, 900.0 - seconds_left)
    if elapsed < OBSERVATION_SECONDS:
        return "OBSERVE", seconds_left, elapsed
    if seconds_left <= EXPIRY_MODE_SECONDS:
        return "EXPIRY", seconds_left, elapsed
    return "CORE", seconds_left, elapsed


def current_candle_range():
    if not btc_current_minute_ohlc:
        return None
    return btc_current_minute_ohlc["high"] - btc_current_minute_ohlc["low"]


def recent_avg_candle_range(n=5):
    vals = [c["high"] - c["low"] for c in btc_completed_candles[-n:]]
    return (sum(vals) / len(vals)) if vals else None


def recent_volume_ratio(n=5):
    vols = [c.get("volume", 0.0) for c in btc_completed_candles[-n:] if c.get("volume", 0.0) > 0]
    if not vols or btc_current_minute_volume <= 0:
        return None
    avg = sum(vols) / len(vols)
    return (btc_current_minute_volume / avg) if avg > 0 else None


def parse_target_price(text):
    if not text:
        return None
    m = re.search(r"\$?([0-9]{2,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]{4,}(?:\.[0-9]+)?)", str(text))
    if not m:
        return None
    return to_float(m.group(1).replace(",", ""))


def session_context(now=None):
    if now is None:
        now = time.time()
    dt = datetime.fromtimestamp(now, ET)
    hour = dt.hour
    session = "OVERNIGHT" if hour < 7 else "DAYTIME"
    daypart = "OVERNIGHT" if hour < 6 else "MORNING" if hour < 12 else "AFTERNOON" if hour < 18 else "EVENING"
    return session, daypart, hour


def extract_coinbase_price(data):
    if not isinstance(data, dict):
        return None

    for event in data.get("events", []) or []:
        if not isinstance(event, dict):
            continue
        for ticker in event.get("tickers", []) or []:
            if not isinstance(ticker, dict):
                continue
            if ticker.get("product_id") == BTC_PRODUCT:
                price = to_float(ticker.get("price"))
                if price is not None:
                    return price
    return None


async def btc_price_feed():
    global btc_connected

    while True:
        try:
            async with websockets.connect(
                BTC_WS_URL,
                ping_interval=20,
                ping_timeout=None,
                close_timeout=10,
            ) as ws:
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "product_ids": [BTC_PRODUCT],
                    "channel": "ticker",
                }))
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "product_ids": [BTC_PRODUCT],
                    "channel": "market_trades",
                }))
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "channel": "heartbeats",
                }))

                btc_connected = True
                print("BTC/USD feed connected.")

                while True:
                    message = await ws.recv()
                    data = json.loads(message)
                    price = extract_coinbase_price(data)
                    if price is not None:
                        process_btc_price(price)
                    for trade_price, trade_size in extract_coinbase_trades(data):
                        process_btc_price(trade_price)
                        if trade_size is not None:
                            process_btc_trade_volume(trade_size)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            btc_connected = False
            print()
            print("⚠️ BTC feed error:", e)
            await asyncio.sleep(2)


# ============================================================
# SIDE PRICE HISTORY
# ============================================================

price_history = {
    "YES": [],
    "NO": [],
}


def reset_contract_history():
    for side in SIDES:
        price_history[side] = []


def record_price(side, price, now=None):
    if price is None:
        return

    if now is None:
        now = time.time()

    history = price_history[side]
    history.append((now, price))

    cutoff = now - HISTORY_SECONDS
    while history and history[0][0] < cutoff:
        history.pop(0)


def get_price_at(side, seconds_ago, now=None):
    history = price_history[side]
    if not history:
        return None

    if now is None:
        now = time.time()

    target = now - seconds_ago
    closest = min(
        history,
        key=lambda item: abs(item[0] - target),
    )

    distance = abs(closest[0] - target)
    if distance > 3:
        return None

    return closest[1]


# ============================================================
# 1-MINUTE EMA ENGINE — INFORMATIONAL ONLY
# ============================================================

# Kept continuous across contract handoffs as requested.
minute_closes = {
    "YES": [],
    "NO": [],
}
current_minute = {
    "YES": None,
    "NO": None,
}
current_minute_price = {
    "YES": None,
    "NO": None,
}
ema_9 = {
    "YES": None,
    "NO": None,
}
ema_30 = {
    "YES": None,
    "NO": None,
}


def calculate_sma(values):
    if not values:
        return None
    return sum(values) / len(values)


def update_ema(side):
    closes = minute_closes[side]

    if len(closes) >= EMA_FAST_PERIOD:
        fast_values = [
            price
            for _, price in closes[-EMA_FAST_PERIOD:]
        ]

        if ema_9[side] is None:
            ema_9[side] = calculate_sma(fast_values)
        else:
            multiplier = 2 / (EMA_FAST_PERIOD + 1)
            ema_9[side] = (
                (fast_values[-1] - ema_9[side]) * multiplier
                + ema_9[side]
            )

    if len(closes) >= EMA_SLOW_PERIOD:
        slow_values = [
            price
            for _, price in closes[-EMA_SLOW_PERIOD:]
        ]

        if ema_30[side] is None:
            ema_30[side] = calculate_sma(slow_values)
        else:
            multiplier = 2 / (EMA_SLOW_PERIOD + 1)
            ema_30[side] = (
                (slow_values[-1] - ema_30[side]) * multiplier
                + ema_30[side]
            )


def process_minute_price(side, price, now=None):
    if price is None:
        return

    if now is None:
        now = time.time()

    minute_timestamp = int(now // 60) * 60

    if current_minute[side] is None:
        current_minute[side] = minute_timestamp
        current_minute_price[side] = price
        return

    if minute_timestamp == current_minute[side]:
        current_minute_price[side] = price
        return

    minute_closes[side].append(
        (
            current_minute[side],
            current_minute_price[side],
        )
    )

    if len(minute_closes[side]) > 60:
        minute_closes[side].pop(0)

    current_minute[side] = minute_timestamp
    current_minute_price[side] = price
    update_ema(side)


def get_ema_values(side):
    return ema_9[side], ema_30[side]


# ============================================================
# CSV LOGGING
# ============================================================

def initialize_log():
    files_and_headers = {
        LOG_FILE: [
            "timestamp", "ticker", "side", "current_ask",
            "ask_90s", "ask_75s", "ask_60s",
            "m90_75", "m90_60",
            "kalshi_ema_9_1m", "kalshi_ema_30_1m",
            "btc_price", "btc_ema_9_1m", "btc_ema_30_1m",
            "btc_ema9_above_ema30", "btc_price_above_ema9",
            "btc_move_from_contract_start", "seconds_to_close", "setup_grade",
            "signal_grade", "a_plus_score", "a_plus_reasons", "session", "daypart", "et_hour",
            "target_price", "target_distance", "favorable_cushion",
            "btc_range_30s", "btc_range_60s", "btc_range_180s",
            "btc_current_1m_range", "btc_avg_5m_candle_range", "btc_volume_ratio",
            "contract_phase", "contract_elapsed_seconds", "btc_change_60s",
            "btc_trend_efficiency_60s", "early_exception", "early_exception_reasons",
        ],
        RESULT_LOG_FILE: [
            "timestamp", "ticker", "result", "settlement_time"
        ],
        REVERSAL_LOG_FILE: [
            "timestamp", "ticker", "btc_start", "btc_now",
            "btc_move", "threshold", "seconds_to_close",
            "suggested_next_side"
        ],
        PAPER_LOG_FILE: [
            "timestamp", "event", "trade_id", "ticker", "side",
            "qty", "entry_ask", "exit_bid", "cost", "value",
            "pnl", "roi_pct", "reason", "mfe_pct", "mae_pct",
            "seconds_to_close", "target", "btc_price",
            "btc_ema_9_1m", "btc_ema_30_1m", "setup_grade", "signal_grade",
            "stake_cap", "session", "daypart", "et_hour", "target_price", "target_distance",
            "favorable_cushion", "btc_range_30s", "btc_range_60s", "btc_range_180s",
            "btc_current_1m_range", "btc_avg_5m_candle_range", "btc_volume_ratio",
            "contract_phase", "contract_elapsed_seconds", "btc_change_60s",
            "btc_trend_efficiency_60s", "early_exception", "early_exception_reasons",
            "cumulative_pnl"
        ],
    }

    for path, header in files_and_headers.items():
        if os.path.exists(path):
            continue
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)


def log_signal(ticker, side, signal):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            ticker, side,
            signal["price"], signal["price_90"],
            signal["price_75"], signal["price_60"],
            signal["m90_75"], signal["m90_60"],
            signal.get("ema_9"), signal.get("ema_30"),
            signal.get("btc_price"), signal.get("btc_ema_9"),
            signal.get("btc_ema_30"),
            signal.get("btc_ema9_above_ema30", ""),
            signal.get("btc_price_above_ema9", ""),
            signal.get("btc_move_from_contract_start"),
            signal.get("seconds_to_close"), signal.get("setup_grade", ""),
            signal.get("signal_grade", ""), signal.get("a_plus_score", ""),
            signal.get("a_plus_reasons", ""), signal.get("session", ""),
            signal.get("daypart", ""), signal.get("et_hour", ""),
            signal.get("target_price"), signal.get("target_distance"),
            signal.get("favorable_cushion"), signal.get("btc_range_30s"),
            signal.get("btc_range_60s"), signal.get("btc_range_180s"),
            signal.get("btc_current_1m_range"), signal.get("btc_avg_5m_candle_range"),
            signal.get("btc_volume_ratio"), signal.get("contract_phase", ""),
            signal.get("contract_elapsed_seconds"), signal.get("btc_change_60s"),
            signal.get("btc_trend_efficiency_60s"), signal.get("early_exception", ""),
            signal.get("early_exception_reasons", ""),
        ])


def log_reversal_watch(ticker, btc_start, btc_now, move, threshold, seconds_to_close):
    next_side = "NO" if move > 0 else "YES"
    with open(REVERSAL_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            ticker, btc_start, btc_now, move, threshold,
            round(seconds_to_close, 1), next_side,
        ])


def log_settlement(ticker, result, settlement_time):
    if ticker in logged_settlements:
        return
    with open(RESULT_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            ticker, result, settlement_time or "",
        ])
    logged_settlements.add(ticker)


def log_paper_event(event, position, exit_bid=None, reason=""):
    global paper_realized_pnl

    value = ""
    pnl = ""
    roi_pct = ""
    if exit_bid is not None:
        value = position["qty"] * exit_bid
        pnl = value - position["cost"]
        roi_pct = (pnl / position["cost"] * 100) if position["cost"] else 0.0

    with open(PAPER_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"), event, position["trade_id"],
            position["ticker"], position["side"], position["qty"],
            position["entry_ask"], exit_bid if exit_bid is not None else "",
            position["cost"], value, pnl, roi_pct, reason,
            position.get("mfe_pct", 0.0), position.get("mae_pct", 0.0),
            position.get("seconds_to_close"), position.get("target", ""),
            position.get("btc_price"), position.get("btc_ema_9"),
            position.get("btc_ema_30"), position.get("setup_grade", ""),
            position.get("signal_grade", ""), position.get("stake_cap"),
            position.get("session", ""), position.get("daypart", ""), position.get("et_hour", ""),
            position.get("target_price"), position.get("target_distance"),
            position.get("favorable_cushion"), position.get("btc_range_30s"),
            position.get("btc_range_60s"), position.get("btc_range_180s"),
            position.get("btc_current_1m_range"), position.get("btc_avg_5m_candle_range"),
            position.get("btc_volume_ratio"), position.get("contract_phase", ""),
            position.get("contract_elapsed_seconds"), position.get("btc_change_60s"),
            position.get("btc_trend_efficiency_60s"), position.get("early_exception", ""),
            position.get("early_exception_reasons", ""), paper_realized_pnl,
        ])


def paper_enter(ticker, side, ask, signal):
    global paper_trade_counter

    if paper_positions[side] is not None:
        return
    if time.time() - last_paper_exit_time[side] < PAPER_REENTRY_COOLDOWN:
        return
    if ask <= 0:
        return

    elapsed = signal.get("contract_elapsed_seconds")
    is_early_trade = (
        elapsed is not None
        and OBSERVATION_SECONDS <= float(elapsed) < EARLY_PROFIT_WINDOW_SECONDS
    )
    stake_cap = (
        A_PLUS_PAPER_STAKE
        if signal.get("signal_grade") == "A+"
        else PAPER_STAKE
    )
    qty = int(stake_cap // ask)
    if qty < 1:
        return

    paper_trade_counter += 1
    cost = qty * ask
    position = {
        "trade_id": paper_trade_counter, "ticker": ticker, "side": side,
        "qty": qty, "entry_ask": ask, "cost": cost, "entry_time": time.time(),
        "mfe_pct": 0.0, "mae_pct": 0.0,
        "seconds_to_close": signal.get("seconds_to_close"),
        "target": active_target, "btc_price": signal.get("btc_price"),
        "btc_ema_9": signal.get("btc_ema_9"), "btc_ema_30": signal.get("btc_ema_30"),
        "setup_grade": signal.get("setup_grade", ""), "signal_grade": signal.get("signal_grade", ""),
        "stake_cap": stake_cap, "session": signal.get("session", ""),
        "daypart": signal.get("daypart", ""), "et_hour": signal.get("et_hour", ""),
        "target_price": signal.get("target_price"), "target_distance": signal.get("target_distance"),
        "favorable_cushion": signal.get("favorable_cushion"),
        "btc_range_30s": signal.get("btc_range_30s"), "btc_range_60s": signal.get("btc_range_60s"),
        "btc_range_180s": signal.get("btc_range_180s"),
        "btc_current_1m_range": signal.get("btc_current_1m_range"),
        "btc_avg_5m_candle_range": signal.get("btc_avg_5m_candle_range"),
        "btc_volume_ratio": signal.get("btc_volume_ratio"),
        "contract_phase": signal.get("contract_phase", ""),
        "contract_elapsed_seconds": signal.get("contract_elapsed_seconds"),
        "btc_change_60s": signal.get("btc_change_60s"),
        "btc_trend_efficiency_60s": signal.get("btc_trend_efficiency_60s"),
        "early_exception": False,
        "early_exception_reasons": "",
        "early_trade": is_early_trade,
        "milestones_hit": set(),
    }
    paper_positions[side] = position
    contract_trade_ids.setdefault(ticker, []).append(position["trade_id"])
    log_paper_event("ENTRY", position)
    grade = position.get("signal_grade") or position.get("setup_grade")
    print(f"💵 PAPER ${stake_cap:.0f} ENTRY | #{paper_trade_counter} {side} {grade} | {qty} contracts @ {ask:.3f} | cost=${cost:.2f}")


def record_contract_trade(position, exit_bid, pnl, reason):
    contract_trade_records.setdefault(position["ticker"], []).append({
        "trade_id": position["trade_id"],
        "side": position["side"],
        "grade": position.get("signal_grade") or position.get("setup_grade", ""),
        "entry": position["entry_ask"],
        "exit": exit_bid,
        "pnl": pnl,
        "reason": reason,
        "mfe_pct": position.get("mfe_pct", 0.0),
        "mae_pct": position.get("mae_pct", 0.0),
        "stake_cap": position.get("stake_cap", PAPER_STAKE),
    })


def print_contract_summary(ticker):
    trades = contract_trade_records.get(ticker, [])
    print()
    print("=" * 68)
    print("📊 CONTRACT SUMMARY")
    print("=" * 68)
    print("Ticker:", ticker)
    if not trades:
        print("Trades: 0 | Contract P&L: $+0.00")
        print(f"Running P&L: ${paper_realized_pnl:+.2f}")
        print("=" * 68)
        return

    for t in trades:
        print(
            f"#{t['trade_id']:>3} | {t['side']:<3} | {t['grade']:<9} "
            f"| {t['entry']:.3f} -> {t['exit']:.3f} "
            f"| P&L=${t['pnl']:+.2f} | peak={t['mfe_pct']:+.1f}% "
            f"| {t['reason']}"
        )
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    subtotal = sum(t["pnl"] for t in trades)
    print("-" * 68)
    print(f"Trades: {len(trades)} | Wins: {wins} | Losses: {losses}")
    print(f"Contract P&L: ${subtotal:+.2f}")
    print(f"Running P&L:  ${paper_realized_pnl:+.2f}")
    print("=" * 68)


def copilot_snapshot(close_ts, yes_ask, no_ask):
    """Compact live decision-support view. Observational only; paper trading remains rule-driven."""
    now = time.time()
    phase, seconds_left, elapsed = contract_phase(close_ts, now)
    target = parse_target_price(active_target)
    dist = (btc_last_price - target) if btc_last_price is not None and target is not None else None
    ch60 = btc_change(60, now)
    eff60 = btc_trend_efficiency(60, 5, now)
    r60 = btc_range(60, now)
    vr = recent_volume_ratio(5)

    if btc_ema_9 is None or btc_ema_30 is None:
        ema_state = "WARMING"
    elif btc_ema_9 > btc_ema_30:
        ema_state = "YES"
    elif btc_ema_9 < btc_ema_30:
        ema_state = "NO"
    else:
        ema_state = "FLAT"

    # Simple market-state label: efficiency says whether recent BTC movement is
    # directional or back-and-forth; range prevents tiny drift from looking strong.
    if eff60 is None or r60 is None:
        state = "WARMING"
    elif eff60 < 0.35:
        state = "CHOP"
    elif eff60 >= 0.60 and r60 >= 30:
        state = "TREND"
    else:
        state = "MIXED"

    # Final minute is not a normal momentum-entry phase. Surface an expiry edge
    # only when BTC has a meaningful target cushion, recent movement is not aimed
    # hard back through the target, and the Kalshi side is still priced below 90c.
    edge = "NONE"
    if seconds_left is not None and seconds_left <= EXPIRY_MODE_SECONDS and dist is not None:
        velocity = ch60 or 0.0
        cushion_floor = max(25.0, (r60 or 0.0) * 0.50)
        if dist >= cushion_floor and velocity > -max(20.0, abs(dist) * 0.50) and yes_ask is not None and yes_ask < 0.90:
            edge = "YES"
        elif dist <= -cushion_floor and velocity < max(20.0, abs(dist) * 0.50) and no_ask is not None and no_ask < 0.90:
            edge = "NO"

    if phase == "OBSERVE":
        action = "WATCH"
    elif seconds_left is not None and seconds_left <= EXPIRY_MODE_SECONDS:
        action = f"EXPIRY EDGE {edge}" if edge != "NONE" else "NO NEW TRADE"
    elif state == "CHOP":
        action = "CAUTION / CHOP"
    elif state == "TREND":
        action = f"TREND {ema_state}" if ema_state in ("YES", "NO") else "TREND"
    else:
        action = "SELECTIVE"

    def fmt(v, spec):
        return format(v, spec) if v is not None else "---"

    left = f"{seconds_left:4.0f}s" if seconds_left is not None else "---"
    return (
        f"COPILOT | {action} | {state} | left={left} | "
        f"targetΔ={fmt(dist, '+.0f')} | BTC60={fmt(ch60, '+.0f')} "
        f"range60={fmt(r60, '.0f')} eff={fmt(eff60, '.2f')} "
        f"EMA={ema_state} vol={fmt(vr, '.2f')}x"
    )


def paper_manage(ticker, yes_ask, no_ask):
    global paper_realized_pnl

    bids = {
        "YES": (1.0 - no_ask) if no_ask is not None else None,
        "NO": (1.0 - yes_ask) if yes_ask is not None else None,
    }

    for side in SIDES:
        position = paper_positions[side]
        bid = bids[side]
        if position is None or bid is None or position["ticker"] != ticker:
            continue

        value = position["qty"] * bid
        pnl = value - position["cost"]
        roi = pnl / position["cost"] if position["cost"] else 0.0
        position["mfe_pct"] = max(position["mfe_pct"], roi * 100)
        position["mae_pct"] = min(position["mae_pct"], roi * 100)

        # Record profit milestones without forcing an exit.
        for milestone in PROFIT_MILESTONES:
            if roi >= milestone and milestone not in position["milestones_hit"]:
                position["milestones_hit"].add(milestone)
                label = f"HIT_{int(milestone * 100)}PCT"
                log_paper_event("MILESTONE", position, bid, label)
                print(f"📈 PAPER MILESTONE | #{position['trade_id']} {side} | +{int(milestone * 100)}% reached | current P&L=${pnl:+.2f}")

        reason = None
        peak_roi = position["mfe_pct"] / 100.0
        seconds_left = None
        # current_close_ts is injected by process_top_of_book as a timestamp directly.
        if isinstance(getattr(paper_manage, "current_close_ts", None), (int, float)):
            seconds_left = max(0.0, paper_manage.current_close_ts - time.time())
        position["seconds_to_close"] = seconds_left if seconds_left is not None else position.get("seconds_to_close")

        target_price = parse_target_price(active_target)
        if btc_last_price is not None and target_price is not None:
            target_distance = btc_last_price - target_price
            favorable_cushion = target_distance if side == "YES" else -target_distance
            position["target_price"] = target_price
            position["target_distance"] = target_distance
            position["favorable_cushion"] = favorable_cushion
        else:
            favorable_cushion = None

        # V7 contextual risk logic:
        # - no automatic -20% exit early in the contract;
        # - trailing winners still protects gains;
        # - in the last 5 minutes, a losing trade may exit when BTC is already
        #   on the wrong side of target;
        # - -60% is only an emergency paper guardrail while we collect data.
        if position.get("early_trade") and roi >= EARLY_TAKE_PROFIT_ROI:
            reason = "EARLY_TAKE_PROFIT_50"
        elif peak_roi >= TRAIL_ACTIVATE_ROI and roi <= peak_roi - TRAIL_GIVEBACK_ROI:
            reason = "TRAIL_20PTS_AFTER_40"
        elif (
            peak_roi >= 0.20
            and roi <= -0.05
        ):
            # V7 earned-protection: a trade that proved itself (+20% MFE) is
            # no longer treated like a thesis that was wrong immediately.
            reason = "PROTECT_PROVEN_TRADE"
        elif (
            seconds_left is not None
            and seconds_left <= LATE_RISK_WINDOW_SECONDS
            and roi <= LATE_TARGET_STOP_ROI
            and favorable_cushion is not None
            and favorable_cushion < 0
            and peak_roi < 0.20
        ):
            reason = "LATE_TARGET_INVALIDATION"
        elif roi <= -EMERGENCY_STOP_LOSS:
            reason = "EMERGENCY_STOP_60"

        if reason:
            paper_realized_pnl += pnl
            log_paper_event("EXIT", position, bid, reason)
            record_contract_trade(position, bid, pnl, reason)
            print(f"💰 PAPER EXIT | #{position['trade_id']} {side} @ {bid:.3f} | {reason} | peak={peak_roi*100:.1f}% | P&L=${pnl:+.2f} | total=${paper_realized_pnl:+.2f}")
            paper_positions[side] = None
            last_paper_exit_time[side] = time.time()


def paper_close_contract(ticker, yes_ask, no_ask):
    global paper_realized_pnl
    bids = {
        "YES": (1.0 - no_ask) if no_ask is not None else None,
        "NO": (1.0 - yes_ask) if yes_ask is not None else None,
    }
    for side in SIDES:
        position = paper_positions[side]
        if position is None or position["ticker"] != ticker:
            continue
        bid = bids[side]
        if bid is None:
            continue
        value = position["qty"] * bid
        pnl = value - position["cost"]
        paper_realized_pnl += pnl
        log_paper_event("EXIT", position, bid, "CONTRACT_CLOSE")
        record_contract_trade(position, bid, pnl, "CONTRACT_CLOSE")
        print(f"💰 PAPER CLOSE | #{position['trade_id']} {side} @ {bid:.3f} | P&L=${pnl:+.2f} | total=${paper_realized_pnl:+.2f}")
        paper_positions[side] = None
        last_paper_exit_time[side] = time.time()


async def settlement_watcher():
    while True:
        try:
            for ticker in list(pending_settlements):
                try:
                    market = await asyncio.to_thread(get_market_snapshot, ticker)
                    result = str(market.get("result", "")).lower()
                    if result in ("yes", "no"):
                        log_settlement(
                            ticker,
                            result.upper(),
                            market.get("settlement_ts") or market.get("settled_time"),
                        )
                        pending_settlements.discard(ticker)
                except Exception:
                    pass
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise


# ============================================================
# STRATEGY — SAME RULES, NOW APPLIED TO YES AND NO
# ============================================================

def evaluate_strategy(side, current_price, now=None):
    p90 = get_price_at(side, 90, now)
    p75 = get_price_at(side, 75, now)
    p60 = get_price_at(side, 60, now)

    if p90 is None or p75 is None or p60 is None:
        return None

    m90_75 = p75 - p90
    m90_60 = p60 - p90
    ema9, ema30 = get_ema_values(side)

    if current_price < EARLY_ENTRY_ASK or current_price > MAX_ENTRY_ASK:
        return None

    # Continuation is required for both grades.
    if current_price <= p75 or current_price <= p60:
        return None

    confirmed = (
        current_price >= CONFIRMED_ENTRY_ASK
        and m90_75 >= CONFIRMED_MOM_90_75
        and m90_60 >= CONFIRMED_MOM_90_60
    )
    early = (
        m90_75 >= EARLY_MOM_90_75
        and m90_60 >= EARLY_MOM_90_60
    )

    if not confirmed and not early:
        return None

    return {
        "price": current_price,
        "price_90": p90,
        "price_75": p75,
        "price_60": p60,
        "m90_75": m90_75,
        "m90_60": m90_60,
        "ema_9": ema9,
        "ema_30": ema30,
        "setup_grade": "CONFIRMED" if confirmed else "EARLY",
    }


def early_exception_check(side, signal):
    """Strict escape hatch during the first four minutes."""
    reasons = []
    if signal.get("setup_grade") != "CONFIRMED":
        return False, reasons

    ema9v = signal.get("btc_ema_9")
    ema30v = signal.get("btc_ema_30")
    price = signal.get("btc_price")
    if ema9v is None or ema30v is None or price is None:
        return False, reasons

    ema_aligned = (ema9v > ema30v) if side == "YES" else (ema9v < ema30v)
    price_aligned = (price > ema9v) if side == "YES" else (price < ema9v)
    if not ema_aligned or not price_aligned:
        return False, reasons
    reasons.extend(["ema9_30_aligned", "btc_vs_ema9_aligned"])

    ch60 = signal.get("btc_change_60s")
    eff = signal.get("btc_trend_efficiency_60s")
    if ch60 is None or eff is None:
        return False, reasons
    directional_move = ch60 if side == "YES" else -ch60
    if directional_move < EARLY_MIN_BTC_NET_MOVE_60S:
        return False, reasons
    reasons.append(f"btc60_dir_{directional_move:.0f}")
    if eff < EARLY_MIN_TREND_EFFICIENCY:
        return False, reasons
    reasons.append(f"trend_eff_{eff:.2f}")

    if signal.get("m90_75", 0) < EARLY_MIN_MOM_90_75:
        return False, reasons
    if signal.get("m90_60", 0) < EARLY_MIN_MOM_90_60:
        return False, reasons
    reasons.append("strong_kalshi_momentum")
    return True, reasons


def enrich_signal_context(side, signal, close_ts=None):
    now = time.time()
    session, daypart, et_hour = session_context(now)
    target_price = parse_target_price(active_target)
    target_distance = None
    favorable_cushion = None
    if btc_last_price is not None and target_price is not None:
        target_distance = btc_last_price - target_price
        favorable_cushion = target_distance if side == "YES" else -target_distance

    r30 = btc_range(30, now)
    r60 = btc_range(60, now)
    r180 = btc_range(180, now)
    c1 = current_candle_range()
    avg5 = recent_avg_candle_range(5)
    vr = recent_volume_ratio(5)
    phase, seconds_left, elapsed = contract_phase(close_ts, now)
    ch60 = btc_change(60, now)
    eff60 = btc_trend_efficiency(60, 5, now)

    ema_aligned = None
    price_ema_aligned = None
    if btc_ema_9 is not None and btc_ema_30 is not None:
        ema_aligned = (btc_ema_9 > btc_ema_30) if side == "YES" else (btc_ema_9 < btc_ema_30)
    if btc_last_price is not None and btc_ema_9 is not None:
        price_ema_aligned = (btc_last_price > btc_ema_9) if side == "YES" else (btc_last_price < btc_ema_9)

    score = 0
    reasons = []
    if signal.get("setup_grade") == "CONFIRMED":
        score += 2
        reasons.append("confirmed")
    if ema_aligned:
        score += 2
        reasons.append("ema9_30_aligned")
    if price_ema_aligned:
        score += 1
        reasons.append("btc_vs_ema9_aligned")
    if signal.get("m90_75", 0) >= 0.04:
        score += 1
        reasons.append("strong_90_75")
    if signal.get("m90_60", 0) >= 0.08:
        score += 1
        reasons.append("strong_90_60")
    if favorable_cushion is not None and favorable_cushion > 0:
        score += 1
        reasons.append("target_side_favorable")

    signal_grade = "A+" if score >= 6 else ("A" if score >= 4 else signal.get("setup_grade", ""))
    # A+ sizing is never granted during the observation phase.
    if phase == "OBSERVE" and signal_grade == "A+":
        signal_grade = "A"

    signal.update({
        "signal_grade": signal_grade,
        "a_plus_score": score,
        "a_plus_reasons": ";".join(reasons),
        "session": session,
        "daypart": daypart,
        "et_hour": et_hour,
        "target_price": target_price,
        "target_distance": target_distance,
        "favorable_cushion": favorable_cushion,
        "btc_range_30s": r30,
        "btc_range_60s": r60,
        "btc_range_180s": r180,
        "btc_current_1m_range": c1,
        "btc_avg_5m_candle_range": avg5,
        "btc_volume_ratio": vr,
        "contract_phase": phase,
        "contract_elapsed_seconds": elapsed,
        "btc_change_60s": ch60,
        "btc_trend_efficiency_60s": eff60,
        "early_exception": False,
        "early_exception_reasons": "",
    })
    return signal

# ============================================================
# SIGNAL DISPLAY
# ============================================================

last_signal_time = {
    "YES": 0,
    "NO": 0,
}
last_signal_signature = {
    "YES": None,
    "NO": None,
}


def print_signal(ticker, side, signal, btc_start=None, close_ts=None):
    now = time.time()

    signature = (
        round(signal["price"], 2),
        round(signal["m90_75"], 2),
        round(signal["m90_60"], 2),
    )

    if signature == last_signal_signature[side]:
        return

    if now - last_signal_time[side] < 5:
        return

    last_signal_time[side] = now
    last_signal_signature[side] = signature

    now_wall = time.time()
    signal["btc_price"] = btc_last_price
    signal["btc_ema_9"] = btc_ema_9
    signal["btc_ema_30"] = btc_ema_30
    signal["btc_ema9_above_ema30"] = (
        "YES" if btc_ema_9 is not None and btc_ema_30 is not None and btc_ema_9 > btc_ema_30
        else "NO" if btc_ema_9 is not None and btc_ema_30 is not None
        else ""
    )
    signal["btc_price_above_ema9"] = (
        "YES" if btc_last_price is not None and btc_ema_9 is not None and btc_last_price > btc_ema_9
        else "NO" if btc_last_price is not None and btc_ema_9 is not None
        else ""
    )
    signal["btc_move_from_contract_start"] = (
        btc_last_price - btc_start
        if btc_last_price is not None and btc_start is not None
        else None
    )
    signal["seconds_to_close"] = (
        max(0.0, close_ts - now_wall) if close_ts is not None else None
    )
    enrich_signal_context(side, signal, close_ts)

    phase = signal.get("contract_phase", "CORE")
    if phase == "OBSERVE":
        # V7: hard 2-minute observation window. We still log qualifying
        # signals for later analysis, but never open a paper position here.
        signal["early_exception"] = False
        signal["early_exception_reasons"] = "HARD_2MIN_OBSERVE"
        signal["signal_grade"] = "OBSERVE_ONLY"
        log_signal(ticker, side, signal)
        return

    elapsed = signal.get("contract_elapsed_seconds")
    seconds_left_sig = signal.get("seconds_to_close")
    if seconds_left_sig is not None and float(seconds_left_sig) <= EXPIRY_MODE_SECONDS:
        # V7: final minute is edge-only, never ordinary momentum trading.
        target = signal.get("target_price")
        dist = signal.get("target_distance")
        r60 = signal.get("btc_range_60s")
        ch60 = signal.get("btc_change_60s") or 0.0
        cushion_floor = max(25.0, (r60 or 0.0) * 0.50)
        expiry_edge = False
        if dist is not None:
            if side == "YES":
                expiry_edge = dist >= cushion_floor and ch60 > -max(20.0, abs(dist) * 0.50) and signal["price"] < 0.90
            else:
                expiry_edge = dist <= -cushion_floor and ch60 < max(20.0, abs(dist) * 0.50) and signal["price"] < 0.90
        if not expiry_edge:
            signal["early_exception_reasons"] = "BLOCK_FINAL_MINUTE_NO_EDGE"
            log_signal(ticker, side, signal)
            return
        signal["early_exception_reasons"] = "FINAL_MINUTE_EXPIRY_EDGE"

    if (
        elapsed is not None
        and OBSERVATION_SECONDS <= float(elapsed) < STRONG_ONLY_WINDOW_SECONDS
        and signal.get("signal_grade") not in ("A", "A+")
    ):
        # V7: minute 2-4 is tradable only for stronger A/A+ setups.
        # We keep weaker signals in the CSV so this filter can be audited.
        signal["early_exception_reasons"] = "BLOCK_2_4_WEAK_GRADE"
        log_signal(ticker, side, signal)
        return

    log_signal(ticker, side, signal)
    paper_enter(ticker, side, signal["price"], signal)

    print()
    print()
    print("=" * 60)
    print(f"🔥 {side} MOMENTUM SIGNAL — {signal.get('signal_grade') or signal.get('setup_grade', '')}")
    print("=" * 60)
    print("TICKER      :", ticker)
    print("SIDE        :", side)
    print(f"CURRENT ASK : {signal['price']:.3f}")
    print(f"90s ASK     : {signal['price_90']:.3f}")
    print(f"75s ASK     : {signal['price_75']:.3f}")
    print(f"60s ASK     : {signal['price_60']:.3f}")
    print()
    print(f"90→75 MOM   : {signal['m90_75']:+.3f}")
    print(f"90→60 MOM   : {signal['m90_60']:+.3f}")
    print()

    if signal["ema_9"] is not None:
        print(f"1M EMA 9    : {signal['ema_9']:.3f}")
    else:
        print("1M EMA 9    : warming up")

    if signal["ema_30"] is not None:
        print(f"1M EMA 30   : {signal['ema_30']:.3f}")
    else:
        print("1M EMA 30   : warming up")

    if signal["ema_9"] is not None and signal["ema_30"] is not None:
        trend = (
            "9 EMA ABOVE 30 EMA"
            if signal["ema_9"] > signal["ema_30"]
            else "9 EMA BELOW 30 EMA"
        )
        print("EMA TREND   :", trend)

    if btc_last_price is not None:
        print(f"BTC/USD     : ${btc_last_price:,.2f}")
    if btc_ema_9 is not None:
        print(f"BTC EMA 9   : ${btc_ema_9:,.2f}")
    if btc_ema_30 is not None:
        print(f"BTC EMA 30  : ${btc_ema_30:,.2f}")

    print(f"SESSION     : {signal.get('session', '')} / {signal.get('daypart', '')} ET hour {signal.get('et_hour', '')}")
    print(f"PHASE       : {signal.get('contract_phase', '')} | elapsed={signal.get('contract_elapsed_seconds') or 0:.0f}s")
    if signal.get("early_exception"):
        print(f"EARLY WHY   : {signal.get('early_exception_reasons', '')}")
    print(f"GRADE       : {signal.get('signal_grade', '')} | score={signal.get('a_plus_score', '')}")
    if signal.get("a_plus_reasons"):
        print(f"GRADE WHY   : {signal.get('a_plus_reasons')}")
    if signal.get("target_price") is not None:
        print(f"TARGET      : ${signal['target_price']:,.2f}")
        print(f"BTC-TARGET  : ${signal['target_distance']:+,.2f} | favorable cushion={signal['favorable_cushion']:+,.2f}")
    if signal.get("btc_range_60s") is not None:
        print(f"BTC RANGE   : 30s=${signal.get('btc_range_30s') or 0:.0f} | 60s=${signal.get('btc_range_60s') or 0:.0f} | 3m=${signal.get('btc_range_180s') or 0:.0f}")
    if signal.get("btc_change_60s") is not None:
        print(f"BTC TREND   : 60s net=${signal.get('btc_change_60s'):+.0f} | efficiency={signal.get('btc_trend_efficiency_60s') or 0:.2f}")
    if signal.get("btc_current_1m_range") is not None:
        print(f"1M CANDLE   : ${signal['btc_current_1m_range']:.0f} | avg5=${signal.get('btc_avg_5m_candle_range') or 0:.0f}")
    if signal.get("btc_volume_ratio") is not None:
        print(f"VOLUME      : {signal['btc_volume_ratio']:.2f}x current minute vs recent")

    print()
    print(">>> PAPER CANDIDATE — NO ORDER <<<")
    print("=" * 60)
    print()


# ============================================================
# PRICE PROCESSING
# ============================================================

def process_top_of_book(ticker, yes_ask, no_ask, source, btc_start=None, close_ts=None):
    now = time.time()
    paper_manage.current_close_ts = close_ts
    paper_manage(ticker, yes_ask, no_ask)

    for side, price in (("YES", yes_ask), ("NO", no_ask)):
        if price is None:
            continue

        record_price(side, price, now)
        process_minute_price(side, price, now)

        signal = evaluate_strategy(side, price, now)
        if signal is not None:
            print_signal(ticker, side, signal, btc_start, close_ts)


# ============================================================
# WEBSOCKET + REST FALLBACK
# ============================================================

async def listen_to_market(market):
    global active_target
    ticker = market["ticker"]
    close_ts = iso_to_timestamp(market.get("close_time"))
    active_target = market.get("yes_sub_title", "") or ""
    last_yes_ask, last_no_ask = extract_top_of_book(market)

    # 90/75/60-second history must start fresh for each new contract.
    reset_contract_history()
    btc_start_price = btc_last_price
    reversal_flags = set()

    private_key = load_private_key()
    timestamp, signature = create_signature(private_key)

    headers = {
        "KALSHI-ACCESS-KEY": API_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }

    print()
    print("=" * 60)
    print("CURRENT BTC 15-MINUTE CONTRACT")
    print("=" * 60)
    print("Ticker:", ticker)
    print("Title:", market.get("title", ""))
    print("Target:", active_target)
    print(
        "YES:",
        market.get("yes_bid_dollars"),
        "/",
        market.get("yes_ask_dollars"),
    )
    print(
        "NO:",
        market.get("no_bid_dollars"),
        "/",
        market.get("no_ask_dollars"),
    )
    print("Closes:", market.get("close_time", ""))
    if btc_start_price is not None:
        print(f"BTC start: ${btc_start_price:,.2f}")
    else:
        print("BTC start: waiting for BTC/USD feed")
    print("=" * 60)
    print()

    ws_messages = 0
    ticker_messages = 0
    orderbook_messages = 0
    rest_polls = 0
    usable_updates = 0

    last_rest_poll = 0.0
    last_status = time.monotonic()

    async with websockets.connect(
        WS_URL,
        additional_headers=headers,
        ping_interval=10,
        ping_timeout=None,
        close_timeout=10,
    ) as ws:
        print("CONNECTED TO KALSHI")
        print()

        subscribe = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": [
                    "ticker",
                    "orderbook_delta",
                ],
                "market_tickers": [ticker],
            },
        }

        await ws.send(json.dumps(subscribe))

        print("Subscribed to ticker + orderbook.")
        print("Tracking BOTH YES and NO sides.")
        print("REST top-of-book fallback: 1 update/second.")
        print("90-second strategy history starts fresh on this contract.")
        print("EMA history remains continuous and informational only.")
        print("V7 PHASES: first 2m HARD OBSERVE | 2-4m A/A+ only | +50% TP through 10m | final 1m expiry.")
        print("No entries are allowed during the first 2 minutes.")
        print("Trades entered from 2:00-10:00 bank +50% immediately; A+ can use the $10 paper cap after observation.")
        print()

        while True:
            # Fast handoff at the actual 15-minute contract close.
            if close_ts is not None and time.time() >= close_ts:
                print()
                print("⏱️ Contract closed — switching immediately.")
                paper_close_contract(ticker, last_yes_ask, last_no_ask)
                print_contract_summary(ticker)
                pending_settlements.add(ticker)
                return

            data = None

            try:
                message = await asyncio.wait_for(
                    ws.recv(),
                    timeout=WS_RECV_TIMEOUT,
                )
                data = json.loads(message)
                ws_messages += 1

                msg_type = data.get("type", "")
                if msg_type == "ticker":
                    ticker_messages += 1
                elif msg_type == "orderbook_delta":
                    orderbook_messages += 1

                msg = data.get("msg", {})
                if isinstance(msg, dict):
                    yes_ask, no_ask = extract_top_of_book(msg)

                    if yes_ask is not None or no_ask is not None:
                        if yes_ask is not None:
                            last_yes_ask = yes_ask
                        if no_ask is not None:
                            last_no_ask = no_ask
                        usable_updates += 1
                        process_top_of_book(
                            ticker,
                            yes_ask,
                            no_ask,
                            "WS",
                            btc_start_price,
                            close_ts,
                        )

            except asyncio.TimeoutError:
                pass

            except websockets.exceptions.ConnectionClosed as e:
                print()
                print()
                print("⚠️ WebSocket disconnected.")
                print("Code:", e.code)
                return

            except Exception as e:
                print()
                print("⚠️ WebSocket error:", e)

            # Reliable 1-second top-of-book sampling. This prevents the
            # strategy from freezing when the websocket has no usable ASK.
            now_mono = time.monotonic()
            if now_mono - last_rest_poll >= REST_POLL_SECONDS:
                last_rest_poll = now_mono

                try:
                    snapshot = await asyncio.to_thread(
                        get_market_snapshot,
                        ticker,
                    )
                    rest_polls += 1

                    yes_ask, no_ask = extract_top_of_book(snapshot)

                    refreshed_target = snapshot.get("yes_sub_title", "") or ""
                    if refreshed_target and refreshed_target != active_target:
                        old_target = active_target or "TBD"
                        active_target = refreshed_target
                        print()
                        print(f"🎯 TARGET UPDATED | {old_target} -> {active_target}")

                    if yes_ask is not None or no_ask is not None:
                        if yes_ask is not None:
                            last_yes_ask = yes_ask
                        if no_ask is not None:
                            last_no_ask = no_ask
                        usable_updates += 1
                        process_top_of_book(
                            ticker,
                            yes_ask,
                            no_ask,
                            "REST",
                            btc_start_price,
                            close_ts,
                        )

                except Exception as e:
                    print()
                    print("⚠️ REST snapshot error:", e)

            # Late-contract BTC displacement experiment.
            if (
                close_ts is not None
                and btc_start_price is not None
                and btc_last_price is not None
            ):
                seconds_left = max(0.0, close_ts - time.time())
                btc_move = btc_last_price - btc_start_price
                if seconds_left <= 300:
                    for threshold in REVERSAL_THRESHOLDS:
                        key = threshold
                        if abs(btc_move) >= threshold and key not in reversal_flags:
                            reversal_flags.add(key)
                            log_reversal_watch(
                                ticker, btc_start_price, btc_last_price,
                                btc_move, threshold, seconds_left,
                            )
                            next_side = "NO" if btc_move > 0 else "YES"
                            print()
                            print(
                                f"⚡ REVERSAL WATCH | BTC move={btc_move:+.2f} "
                                f"| {seconds_left:.0f}s left | next side={next_side}"
                            )

            # Heartbeat so silence never looks like a frozen bot again.
            if now_mono - last_status >= STATUS_SECONDS:
                last_status = now_mono

                yes_now = (
                    price_history["YES"][-1][1]
                    if price_history["YES"]
                    else None
                )
                no_now = (
                    price_history["NO"][-1][1]
                    if price_history["NO"]
                    else None
                )

                yes_text = f"{yes_now:.3f}" if yes_now is not None else "---"
                no_text = f"{no_now:.3f}" if no_now is not None else "---"

                btc_text = f"${btc_last_price:,.2f}" if btc_last_price is not None else "---"
                btc_ema_text = (
                    f"{btc_ema_9:,.0f}/{btc_ema_30:,.0f}"
                    if btc_ema_9 is not None and btc_ema_30 is not None
                    else "warming"
                )

                phase_now, sec_left_now, elapsed_now = contract_phase(close_ts)
                live_line = (
                    f"LIVE | {phase_now} | YES={yes_text} | NO={no_text} "
                    f"| BTC={btc_text} | BTC EMA9/30={btc_ema_text} "
                    f"| WS={ws_messages} | REST={rest_polls} "
                    f"| usable={usable_updates} | BTCticks={btc_updates} "
                    f"| PaperPnL=${paper_realized_pnl:+.2f}"
                )
                copilot_line = copilot_snapshot(close_ts, yes_now, no_now)
                print("\r" + live_line + " " * 8)
                print(copilot_line + " " * 8, end="\033[F", flush=True)


# ============================================================
# MAIN LOOP WITH FAST CONTRACT HANDOFF
# ============================================================

async def main():
    initialize_log()

    print("Bootstrapping BTC 1-minute EMA history from Coinbase...")
    await asyncio.to_thread(bootstrap_btc_history)

    btc_task = asyncio.create_task(btc_price_feed())
    settlement_task = asyncio.create_task(settlement_watcher())

    try:
        while True:
            try:
                print()
                print("Searching for current KXBTC15M market...")

                market = await asyncio.to_thread(get_current_market)

                if market is None:
                    print("No active future KXBTC15M market found.")
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue

                await listen_to_market(market)
                await asyncio.sleep(0.25)

            except Exception as e:
                print()
                print()
                print("⚠️ MAIN LOOP ERROR:", e)
                print(f"Reconnecting in {RECONNECT_DELAY} second(s)...")
                await asyncio.sleep(RECONNECT_DELAY)

    finally:
        btc_task.cancel()
        settlement_task.cancel()
        await asyncio.gather(
            btc_task, settlement_task, return_exceptions=True
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
