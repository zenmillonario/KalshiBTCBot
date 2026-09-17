import os
import time
import base64
import asyncio
import json
import csv
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

REST_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"

SERIES = "KXBTC15M"

ENTRY_ASK = 0.50
MAX_ENTRY_ASK = 0.80

MOM_90_75 = 0.02
MOM_90_60 = 0.05

HISTORY_SECONDS = 300

# New EMA test log.
# This keeps the previous CSV untouched.
LOG_FILE = "live_candidate_signals_ema.csv"

RECONNECT_DELAY = 3

# 1-minute EMA settings.
EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 30


# ============================================================
# AUTH
# ============================================================

def load_private_key():

    with open(PRIVATE_KEY_PATH, "rb") as f:

        return serialization.load_pem_private_key(
            f.read(),
            password=None
        )


def create_signature(private_key):

    timestamp = str(
        int(time.time() * 1000)
    )

    message = (
        timestamp
        + "GET"
        + "/trade-api/ws/v2"
    )

    signature = private_key.sign(

        message.encode("utf-8"),

        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),

        hashes.SHA256()
    )

    return (
        timestamp,
        base64.b64encode(signature).decode()
    )


# ============================================================
# MARKET
# ============================================================

def get_current_market():

    params = {
        "series_ticker": SERIES,
        "status": "open",
        "limit": 1
    }

    response = requests.get(
        REST_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    markets = data.get("markets", [])

    if not markets:

        return None

    return markets[0]


# ============================================================
# PRICE HISTORY
# ============================================================

price_history = []


def record_price(price):

    now = time.time()

    price_history.append(
        (now, price)
    )

    cutoff = now - HISTORY_SECONDS

    while price_history:

        if price_history[0][0] >= cutoff:
            break

        price_history.pop(0)


def get_price_at(seconds_ago):

    if not price_history:

        return None

    target = time.time() - seconds_ago

    closest = min(
        price_history,
        key=lambda item: abs(item[0] - target)
    )

    distance = abs(
        closest[0] - target
    )

    # Require the historical observation
    # to be reasonably close to the requested time.
    if distance > 3:

        return None

    return closest[1]


# ============================================================
# 1-MINUTE EMA ENGINE
# ============================================================

minute_closes = []

current_minute = None
current_minute_price = None

ema_9 = None
ema_30 = None


def calculate_sma(values):

    if not values:

        return None

    return sum(values) / len(values)


def update_ema():

    global ema_9
    global ema_30

    if len(minute_closes) >= EMA_FAST_PERIOD:

        fast_values = [
            price
            for _, price in minute_closes[-EMA_FAST_PERIOD:]
        ]

        if ema_9 is None:

            ema_9 = calculate_sma(
                fast_values
            )

        else:

            multiplier = 2 / (
                EMA_FAST_PERIOD + 1
            )

            ema_9 = (
                (fast_values[-1] - ema_9)
                * multiplier
                + ema_9
            )

    if len(minute_closes) >= EMA_SLOW_PERIOD:

        slow_values = [
            price
            for _, price in minute_closes[-EMA_SLOW_PERIOD:]
        ]

        if ema_30 is None:

            ema_30 = calculate_sma(
                slow_values
            )

        else:

            multiplier = 2 / (
                EMA_SLOW_PERIOD + 1
            )

            ema_30 = (
                (slow_values[-1] - ema_30)
                * multiplier
                + ema_30
            )


def process_minute_price(price):

    global current_minute
    global current_minute_price

    now = time.time()

    minute_timestamp = int(
        now // 60
    ) * 60

    # First price received.
    if current_minute is None:

        current_minute = minute_timestamp
        current_minute_price = price

        return

    # Still inside the same minute.
    if minute_timestamp == current_minute:

        current_minute_price = price

        return

    # A new minute has started.
    # Save the final price from the previous minute
    # as that minute's close.
    minute_closes.append(
        (
            current_minute,
            current_minute_price
        )
    )

    # Keep enough history for EMA calculations.
    if len(minute_closes) > 60:

        minute_closes.pop(0)

    current_minute = minute_timestamp
    current_minute_price = price

    update_ema()


def get_ema_values():

    return (
        ema_9,
        ema_30
    )


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
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            "timestamp",
            "ticker",
            "current_ask",
            "ask_90s",
            "ask_75s",
            "ask_60s",
            "m90_75",
            "m90_60",
            "ema_9_1m",
            "ema_30_1m",
            "ema9_above_ema30",
            "ask_above_ema9"
        ])


def log_signal(ticker, signal):

    with open(
        LOG_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

        ema9 = signal.get(
            "ema_9"
        )

        ema30 = signal.get(
            "ema_30"
        )

        ema9_above_ema30 = ""

        ask_above_ema9 = ""

        if ema9 is not None and ema30 is not None:

            ema9_above_ema30 = (
                "YES"
                if ema9 > ema30
                else "NO"
            )

        if ema9 is not None:

            ask_above_ema9 = (
                "YES"
                if signal["price"] > ema9
                else "NO"
            )

        writer.writerow([
            time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            ticker,
            signal["price"],
            signal["price_90"],
            signal["price_75"],
            signal["price_60"],
            signal["m90_75"],
            signal["m90_60"],
            ema9,
            ema30,
            ema9_above_ema30,
            ask_above_ema9
        ])


# ============================================================
# STRATEGY
# ============================================================

def evaluate_strategy(current_price):

    p90 = get_price_at(90)
    p75 = get_price_at(75)
    p60 = get_price_at(60)

    if p90 is None:
        return None

    if p75 is None:
        return None

    if p60 is None:
        return None

    m90_75 = p75 - p90
    m90_60 = p60 - p90

    ema9, ema30 = get_ema_values()

    print(
        f"\rASK={current_price:.3f} "
        f"90s={p90:.3f} "
        f"75s={p75:.3f} "
        f"60s={p60:.3f} "
        f"M90-75={m90_75:+.3f} "
        f"M90-60={m90_60:+.3f}",
        end="",
        flush=True
    )

    # --------------------------------------------------------
    # EMA DISPLAY
    #
    # EMA values are informational only at this stage.
    # They DO NOT affect the entry decision.
    # --------------------------------------------------------

    if ema9 is not None and ema30 is not None:

        print(
            f" "
            f"EMA9={ema9:.3f} "
            f"EMA30={ema30:.3f}",
            end="",
            flush=True
        )

    # Minimum entry price
    if current_price < ENTRY_ASK:
        return None

    # Maximum entry price
    if current_price > MAX_ENTRY_ASK:
        return None

    # Momentum requirements
    if m90_75 < MOM_90_75:
        return None

    if m90_60 < MOM_90_60:
        return None

    # --------------------------------------------------------
    # CONTINUATION FILTER
    #
    # The current ASK must still be above both recent
    # reference prices. This prevents buying after a reversal
    # or sharp pullback.
    # --------------------------------------------------------

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
        "ema_30": ema30
    }


# ============================================================
# SIGNAL DISPLAY
# ============================================================

last_signal_time = 0
last_signal_signature = None


def print_signal(ticker, signal):

    global last_signal_time
    global last_signal_signature

    now = time.time()

    signature = (
        round(signal["price"], 2),
        round(signal["m90_75"], 2),
        round(signal["m90_60"], 2)
    )

    # Avoid printing identical signals repeatedly.
    if signature == last_signal_signature:

        return

    # Minimum spacing between signals.
    if now - last_signal_time < 5:

        return

    last_signal_time = now
    last_signal_signature = signature

    log_signal(
        ticker,
        signal
    )

    print()
    print()
    print("=" * 60)
    print("🔥 MOMENTUM SIGNAL")
    print("=" * 60)

    print(
        "TICKER      :",
        ticker
    )

    print(
        f"CURRENT ASK : {signal['price']:.3f}"
    )

    print(
        f"90s ASK     : {signal['price_90']:.3f}"
    )

    print(
        f"75s ASK     : {signal['price_75']:.3f}"
    )

    print(
        f"60s ASK     : {signal['price_60']:.3f}"
    )

    print()

    print(
        f"90→75 MOM   : {signal['m90_75']:+.3f}"
    )

    print(
        f"90→60 MOM   : {signal['m90_60']:+.3f}"
    )

    print()

    if signal["ema_9"] is not None:

        print(
            f"1M EMA 9    : {signal['ema_9']:.3f}"
        )

    else:

        print(
            "1M EMA 9    : warming up"
        )

    if signal["ema_30"] is not None:

        print(
            f"1M EMA 30   : {signal['ema_30']:.3f}"
        )

    else:

        print(
            "1M EMA 30   : warming up"
        )

    if (
        signal["ema_9"] is not None
        and signal["ema_30"] is not None
    ):

        if signal["ema_9"] > signal["ema_30"]:

            print(
                "EMA TREND   : 9 EMA ABOVE 30 EMA"
            )

        else:

            print(
                "EMA TREND   : 9 EMA BELOW 30 EMA"
            )

    print()

    print(">>> PAPER CANDIDATE — NO ORDER <<<")

    print("=" * 60)
    print()


# ============================================================
# WEBSOCKET
# ============================================================

async def listen_to_market(market):

    global price_history

    ticker = market["ticker"]

    price_history = []

    private_key = load_private_key()

    timestamp, signature = create_signature(
        private_key
    )

    headers = {
        "KALSHI-ACCESS-KEY": API_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }

    print()
    print("=" * 60)
    print("CURRENT BTC 15-MINUTE CONTRACT")
    print("=" * 60)

    print(
        "Ticker:",
        ticker
    )

    print(
        "Title:",
        market["title"]
    )

    print(
        "Target:",
        market["yes_sub_title"]
    )

    print(
        "YES:",
        market["yes_bid_dollars"],
        "/",
        market["yes_ask_dollars"]
    )

    print(
        "NO:",
        market["no_bid_dollars"],
        "/",
        market["no_ask_dollars"]
    )

    print(
        "Closes:",
        market["close_time"]
    )

    print("=" * 60)
    print()

    async with websockets.connect(

        WS_URL,

        additional_headers=headers,

        ping_interval=10,

        ping_timeout=None,

        close_timeout=10

    ) as ws:

        print("CONNECTED TO KALSHI")
        print()

        subscribe = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": [
                    "ticker",
                    "orderbook_delta"
                ],
                "market_tickers": [
                    ticker
                ]
            }
        }

        await ws.send(
            json.dumps(subscribe)
        )

        print(
            "Subscribed to ticker + orderbook."
        )

        print(
            "Waiting for 90 seconds of clean history..."
        )

        print(
            "1-minute EMA data will warm up separately."
        )

        print()

        while True:

            try:

                message = await ws.recv()

                data = json.loads(message)

            except websockets.exceptions.ConnectionClosed as e:

                print()
                print()
                print("⚠️ WebSocket disconnected.")
                print(
                    "Code:",
                    e.code
                )

                return

            except Exception as e:

                print()
                print(
                    "⚠️ WebSocket error:",
                    e
                )

                continue

            # ------------------------------------------------
            # EXTRACT YES ASK
            # ------------------------------------------------

            price = None

            msg = data.get(
                "msg",
                {}
            )

            if isinstance(msg, dict):

                value = msg.get(
                    "yes_ask_dollars"
                )

                if value is not None:

                    try:

                        price = float(value)

                    except (
                        ValueError,
                        TypeError
                    ):

                        price = None

                if price is None:

                    value = msg.get(
                        "price_dollars"
                    )

                    if value is not None:

                        try:

                            price = float(value)

                        except (
                            ValueError,
                            TypeError
                        ):

                            price = None

            # ------------------------------------------------
            # PROCESS PRICE
            # ------------------------------------------------

            if price is None:

                continue

            record_price(
                price
            )

            process_minute_price(
                price
            )

            signal = evaluate_strategy(
                price
            )

            if signal is not None:

                print_signal(
                    ticker,
                    signal
                )


# ============================================================
# MAIN LOOP WITH RECONNECT
# ============================================================

async def main():

    initialize_log()

    while True:

        try:

            print()
            print(
                "Searching for current KXBTC15M market..."
            )

            market = get_current_market()

            if market is None:

                print(
                    "No active KXBTC15M market found."
                )

                await asyncio.sleep(
                    RECONNECT_DELAY
                )

                continue

            await listen_to_market(
                market
            )

        except KeyboardInterrupt:

            print()
            print(
                "Bot stopped."
            )

            break

        except Exception as e:

            print()
            print()
            print(
                "⚠️ MAIN LOOP ERROR:",
                e
            )

            print(
                f"Reconnecting in {RECONNECT_DELAY} seconds..."
            )

            await asyncio.sleep(
                RECONNECT_DELAY
            )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())