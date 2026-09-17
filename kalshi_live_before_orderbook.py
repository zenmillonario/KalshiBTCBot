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

# Paper-trading settings
ENTRY_ASK = 0.50

MOM_90_75 = 0.02
MOM_90_60 = 0.05

HISTORY_SECONDS = 300

LOG_FILE = "live_candidate_signals.csv"

RECONNECT_DELAY = 3


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


def reset_price_history():

    global price_history

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

    target_time = time.time() - seconds_ago

    closest = min(
        price_history,
        key=lambda item: abs(
            item[0] - target_time
        )
    )

    distance = abs(
        closest[0] - target_time
    )

    # Historical value must be reasonably close
    # to the requested timestamp.
    if distance > 3:

        return None

    return closest[1]


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
            "m90_60"
        ])


def log_signal(ticker, signal):

    with open(
        LOG_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

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
            signal["m90_60"]
        ])


# ============================================================
# STRATEGY
# ============================================================

def evaluate_strategy(current_price):

    p90 = get_price_at(90)
    p75 = get_price_at(75)
    p60 = get_price_at(60)

    # We need all three historical observations.
    if p90 is None:
        return None

    if p75 is None:
        return None

    if p60 is None:
        return None

    m90_75 = p75 - p90
    m90_60 = p60 - p90

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

    # Entry price filter
    if current_price < ENTRY_ASK:

        return None

    # Momentum filters
    if m90_75 < MOM_90_75:

        return None

    if m90_60 < MOM_90_60:

        return None

    return {
        "price": current_price,
        "price_90": p90,
        "price_75": p75,
        "price_60": p60,
        "m90_75": m90_75,
        "m90_60": m90_60
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

    # Don't repeat identical signals.
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

    print(">>> PAPER CANDIDATE — NO ORDER <<<")

    print("=" * 60)
    print()


# ============================================================
# WEBSOCKET
# ============================================================

async def listen_to_market(market):

    ticker = market["ticker"]

    reset_price_history()

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

        print()

        while True:

            try:

                message = await ws.recv()

                data = json.loads(message)

                print("\nRAW MESSAGE:", data)

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
            # EXTRACT ONLY YES ASK
            # ------------------------------------------------
            #
            # IMPORTANT:
            # We intentionally DO NOT use price_dollars.
            #
            # Only yes_ask_dollars is allowed into the
            # strategy's historical price series.
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

            # ------------------------------------------------
            # VALIDATE PRICE
            # ------------------------------------------------

            if price is None:

                continue

            # Kalshi YES prices should be between 0 and 1.
            if price < 0 or price > 1:

                continue

            # ------------------------------------------------
            # RECORD PRICE
            # ------------------------------------------------

            record_price(
                price
            )

            # ------------------------------------------------
            # STRATEGY
            # ------------------------------------------------

def evaluate_strategy(current_price):

    p90 = get_price_at(90)
    p75 = get_price_at(75)
    p60 = get_price_at(60)

    # Need clean history for all checkpoints.
    if p90 is None:
        return None

    if p75 is None:
        return None

    if p60 is None:
        return None

    # Historical momentum.
    m90_75 = p75 - p90
    m90_60 = p60 - p90

    # Current continuation momentum.
    m60_now = current_price - p60
    m75_now = current_price - p75

    print(
        f"\rASK={current_price:.3f} "
        f"90s={p90:.3f} "
        f"75s={p75:.3f} "
        f"60s={p60:.3f} "
        f"M90-75={m90_75:+.3f} "
        f"M90-60={m90_60:+.3f} "
        f"M60-NOW={m60_now:+.3f}",
        end="",
        flush=True
    )

    # Basic entry price requirement.
    if current_price < ENTRY_ASK:
        return None

    # Momentum must have moved upward from 90 seconds ago.
    if m90_75 < MOM_90_75:
        return None

    if m90_60 < MOM_90_60:
        return None

    # IMPORTANT:
    # The current price must still be above both the
    # 75-second and 60-second prices.
    #
    # This prevents entering after momentum has already reversed.
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
        "m60_now": m60_now,
        "m75_now": m75_now
    }


# ============================================================
# MAIN LOOP
# ============================================================

async def main():

    initialize_log()

    print()
    print("==============================================")
    print(" KALSHI BTC 15M PAPER MOMENTUM BOT")
    print("==============================================")
    print()
    print("LIVE ORDERS: DISABLED")
    print("YES ASK ONLY: ENABLED")
    print()

    while True:

        try:

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

            print()
            print(
                f"Reconnecting in {RECONNECT_DELAY} seconds..."
            )

            await asyncio.sleep(
                RECONNECT_DELAY
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