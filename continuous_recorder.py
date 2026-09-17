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
# CONFIGURATION
# ============================================================

load_dotenv()

API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")
PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH")

REST_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"

CSV_FILE = "kalshi_btc_continuous.csv"


# ============================================================
# PRIVATE KEY
# ============================================================

def load_private_key():

    with open(PRIVATE_KEY_PATH, "rb") as f:

        return serialization.load_pem_private_key(
            f.read(),
            password=None
        )


# ============================================================
# FIND CURRENT BTC 15-MINUTE MARKET
# ============================================================

def get_current_market():

    params = {
        "series_ticker": "KXBTC15M",
        "status": "open",
        "limit": 10
    }

    response = requests.get(
        REST_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    markets = response.json().get(
        "markets",
        []
    )

    if not markets:
        return None

    # Find the market that is currently open
    # and closest to the present time.

    now = time.time()

    valid = []

    for market in markets:

        try:

            open_time = (
                market["open_time"]
            )

            close_time = (
                market["close_time"]
            )

            from datetime import datetime

            open_dt = datetime.fromisoformat(
                open_time.replace("Z", "+00:00")
            )

            close_dt = datetime.fromisoformat(
                close_time.replace("Z", "+00:00")
            )

            current = datetime.now(
                open_dt.tzinfo
            )

            if open_dt <= current <= close_dt:

                valid.append(market)

        except Exception:

            pass

    if valid:

        return valid[0]

    # If nothing is currently open,
    # return the first market so we can retry.

    return markets[0]


# ============================================================
# CREATE KALSHI WEBSOCKET SIGNATURE
# ============================================================

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
            mgf=padding.MGF1(
                hashes.SHA256()
            ),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),

        hashes.SHA256()
    )

    return (
        timestamp,
        base64.b64encode(
            signature
        ).decode()
    )


# ============================================================
# SAVE RAW EVENT
# ============================================================

def save_event(

    market,
    received_at,
    message_type,
    data

):

    file_exists = os.path.exists(
        CSV_FILE
    )

    record = {

        "received_at":
            received_at,

        "ticker":
            market.get("ticker"),

        "event_ticker":
            market.get("event_ticker"),

        "target":
            market.get("floor_strike"),

        "open_time":
            market.get("open_time"),

        "close_time":
            market.get("close_time"),

        "message_type":
            message_type,

        "raw_message":
            json.dumps(data)

    }

    with open(

        CSV_FILE,
        "a",
        newline="",
        encoding="utf-8"

    ) as f:

        writer = csv.DictWriter(

            f,

            fieldnames=[
                "received_at",
                "ticker",
                "event_ticker",
                "target",
                "open_time",
                "close_time",
                "message_type",
                "raw_message"
            ]

        )

        if not file_exists:

            writer.writeheader()

        writer.writerow(record)


# ============================================================
# RECORD ONE MARKET
# ============================================================

async def record_market(market):

    ticker = market["ticker"]

    print()
    print("=" * 70)
    print("NEW BTC 15-MINUTE CONTRACT")
    print("=" * 70)

    print("Ticker:")
    print(ticker)

    print()

    print("Target:")
    print(
        market.get(
            "yes_sub_title"
        )
    )

    print()

    print("Opens:")
    print(
        market.get(
            "open_time"
        )
    )

    print("Closes:")
    print(
        market.get(
            "close_time"
        )
    )

    print()

    print("YES:")
    print(
        market.get(
            "yes_bid_dollars"
        ),
        "/",
        market.get(
            "yes_ask_dollars"
        )
    )

    print("NO:")
    print(
        market.get(
            "no_bid_dollars"
        ),
        "/",
        market.get(
            "no_ask_dollars"
        )
    )

    print("=" * 70)

    private_key = load_private_key()

    timestamp, signature = (
        create_signature(
            private_key
        )
    )

    headers = {

        "KALSHI-ACCESS-KEY":
            API_KEY_ID,

        "KALSHI-ACCESS-SIGNATURE":
            signature,

        "KALSHI-ACCESS-TIMESTAMP":
            timestamp

    }

    try:

        async with websockets.connect(

            WS_URL,

            additional_headers=headers,

            ping_interval=20,

            ping_timeout=20

        ) as ws:

            print()
            print("CONNECTED")

            subscribe = {

                "id": 1,

                "cmd": "subscribe",

                "params": {

                    "channels": [

                        "ticker",

                        "orderbook_delta",

                        "trade"

                    ],

                    "market_tickers": [

                        ticker

                    ]

                }

            }

            await ws.send(
                json.dumps(
                    subscribe
                )
            )

            print(
                "Subscribed to:",
                ticker
            )

            print(
                "Recording..."
            )

            print()

            # Continue until the market closes.

            while True:

                try:

                    message = await asyncio.wait_for(

                        ws.recv(),

                        timeout=30

                    )

                except asyncio.TimeoutError:

                    # Keep connection alive.

                    continue

                received_at = (
                    time.strftime(
                        "%Y-%m-%dT%H:%M:%S",
                        time.gmtime()
                    )
                )

                try:

                    data = json.loads(
                        message
                    )

                except Exception:

                    continue

                message_type = (
                    data.get(
                        "type",
                        "unknown"
                    )
                )

                save_event(

                    market,

                    received_at,

                    message_type,

                    data

                )

                # Print only useful heartbeat information.

                if message_type == "ticker":

                    try:

                        msg = data["msg"]

                        price = msg.get(
                            "price_dollars"
                        )

                        yes_bid = msg.get(
                            "yes_bid_dollars"
                        )

                        yes_ask = msg.get(
                            "yes_ask_dollars"
                        )

                        print(

                            received_at,

                            "| YES",
                            yes_bid,
                            "/",
                            yes_ask,
                            "| price",
                            price

                        )

                    except Exception:

                        pass

                # Once the exchange sends the
                # post-expiration snapshot,
                # we'll leave this contract.

                if (

                    message_type
                    == "orderbook_snapshot"

                    and data.get("msg", {})
                    .get("market_ticker")
                    == ticker

                ):

                    msg = data.get(
                        "msg",
                        {}
                    )

                    if (
                        not msg.get(
                            "yes_dollars_fp"
                        )
                        and not msg.get(
                            "no_dollars_fp"
                        )
                    ):

                        print()
                        print(
                            "Market appears settled."
                        )

                        break

    except Exception as e:

        print()
        print(
            "WebSocket error:"
        )

        print(e)

        print(
            "Retrying..."
        )

        await asyncio.sleep(3)


# ============================================================
# MAIN LOOP
# ============================================================

async def main():

    print()
    print("=" * 70)
    print("KALSHI BTC CONTINUOUS RECORDER")
    print("=" * 70)
    print()
    print(
        "No trading is enabled."
    )
    print(
        "Recording only."
    )
    print()

    last_ticker = None

    while True:

        try:

            market = (
                get_current_market()
            )

            if market is None:

                print(
                    "No active market."
                )

                await asyncio.sleep(5)

                continue

            ticker = market[
                "ticker"
            ]

            if ticker == last_ticker:

                await asyncio.sleep(5)

                continue

            last_ticker = ticker

            await record_market(
                market
            )

            print()
            print(
                "Waiting for next "
                "BTC 15-minute contract..."
            )

            await asyncio.sleep(3)

        except KeyboardInterrupt:

            print()
            print(
                "Recorder stopped."
            )

            break

        except Exception as e:

            print()
            print(
                "Main loop error:"
            )

            print(e)

            await asyncio.sleep(5)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )