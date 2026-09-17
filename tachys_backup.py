import os
import time
import base64
import asyncio
import json
import csv
from datetime import datetime, timezone

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

ENTRY_ASK = 0.50
MAX_ENTRY_ASK = 0.80

MOM_90_75 = 0.02
MOM_90_60 = 0.05

HISTORY_SECONDS = 300
RECONNECT_DELAY = 1
REST_POLL_SECONDS = 1.0
WS_RECV_TIMEOUT = 0.50
STATUS_SECONDS = 15

# New schema because signals now include YES/NO side.
LOG_FILE = "live_candidate_signals_dual.csv"

# EMA is still informational only. It is NOT an entry filter.
EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 30

SIDES = ("YES", "NO")


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
    if os.path.exists(LOG_FILE):
        return

    with open(
        LOG_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "ticker",
            "side",
            "current_ask",
            "ask_90s",
            "ask_75s",
            "ask_60s",
            "m90_75",
            "m90_60",
            "ema_9_1m",
            "ema_30_1m",
            "ema9_above_ema30",
            "ask_above_ema9",
        ])


def log_signal(ticker, side, signal):
    ema9 = signal.get("ema_9")
    ema30 = signal.get("ema_30")

    ema9_above_ema30 = ""
    ask_above_ema9 = ""

    if ema9 is not None and ema30 is not None:
        ema9_above_ema30 = "YES" if ema9 > ema30 else "NO"

    if ema9 is not None:
        ask_above_ema9 = "YES" if signal["price"] > ema9 else "NO"

    with open(
        LOG_FILE,
        "a",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.writer(f)
        writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            ticker,
            side,
            signal["price"],
            signal["price_90"],
            signal["price_75"],
            signal["price_60"],
            signal["m90_75"],
            signal["m90_60"],
            ema9,
            ema30,
            ema9_above_ema30,
            ask_above_ema9,
        ])


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

    # Same entry band as before.
    if current_price < ENTRY_ASK:
        return None

    if current_price > MAX_ENTRY_ASK:
        return None

    # Same momentum requirements as before.
    if m90_75 < MOM_90_75:
        return None

    if m90_60 < MOM_90_60:
        return None

    # Same continuation filter as before.
    if current_price <= p75:
        return None

    if current_price <= p60:
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
    }


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


def print_signal(ticker, side, signal):
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

    log_signal(ticker, side, signal)

    print()
    print()
    print("=" * 60)
    print(f"🔥 {side} MOMENTUM SIGNAL")
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

    print()
    print(">>> PAPER CANDIDATE — NO ORDER <<<")
    print("=" * 60)
    print()


# ============================================================
# PRICE PROCESSING
# ============================================================

def process_top_of_book(ticker, yes_ask, no_ask, source):
    now = time.time()

    for side, price in (("YES", yes_ask), ("NO", no_ask)):
        if price is None:
            continue

        record_price(side, price, now)
        process_minute_price(side, price, now)

        signal = evaluate_strategy(side, price, now)
        if signal is not None:
            print_signal(ticker, side, signal)


# ============================================================
# WEBSOCKET + REST FALLBACK
# ============================================================

async def listen_to_market(market):
    ticker = market["ticker"]
    close_ts = iso_to_timestamp(market.get("close_time"))

    # 90/75/60-second history must start fresh for each new contract.
    reset_contract_history()

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
    print("Target:", market.get("yes_sub_title", ""))
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
        print()

        while True:
            # Fast handoff at the actual 15-minute contract close.
            if close_ts is not None and time.time() >= close_ts:
                print()
                print("⏱️ Contract closed — switching immediately.")
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
                        usable_updates += 1
                        process_top_of_book(
                            ticker,
                            yes_ask,
                            no_ask,
                            "WS",
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

                    if yes_ask is not None or no_ask is not None:
                        usable_updates += 1
                        process_top_of_book(
                            ticker,
                            yes_ask,
                            no_ask,
                            "REST",
                        )

                except Exception as e:
                    print()
                    print("⚠️ REST snapshot error:", e)

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

                print(
                    f"\rLIVE | YES ask={yes_text} | NO ask={no_text} "
                    f"| WS={ws_messages} "
                    f"| ticker={ticker_messages} "
                    f"| book={orderbook_messages} "
                    f"| REST={rest_polls} "
                    f"| usable={usable_updates}",
                    end="",
                    flush=True,
                )


# ============================================================
# MAIN LOOP WITH FAST CONTRACT HANDOFF
# ============================================================

async def main():
    initialize_log()

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

            # Short pause only to avoid hammering the endpoint during handoff.
            await asyncio.sleep(0.25)

        except KeyboardInterrupt:
            print()
            print("Bot stopped.")
            break

        except Exception as e:
            print()
            print()
            print("⚠️ MAIN LOOP ERROR:", e)
            print(f"Reconnecting in {RECONNECT_DELAY} second(s)...")
            await asyncio.sleep(RECONNECT_DELAY)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
