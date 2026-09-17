import os
import time
import base64
import asyncio
import json
import requests
import csv
from datetime import datetime, timezone

import websockets
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


load_dotenv()

API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")
PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH")

REST_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"

CSV_FILE = "kalshi_btc_data.csv"


def load_private_key():

    with open(PRIVATE_KEY_PATH, "rb") as f:

        return serialization.load_pem_private_key(
            f.read(),
            password=None
        )


def get_current_market():

    params = {
        "series_ticker": "KXBTC15M",
        "status": "open",
        "limit": 1
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

    return markets[0]


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


def save_record(record):

    file_exists = os.path.exists(
        CSV_FILE
    )

    with open(
        CSV_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=record.keys()
        )

        if not file_exists:

            writer.writeheader()

        writer.writerow(record)


async def record_market(market):

    ticker = market["ticker"]

    private_key = load_private_key()

    timestamp, signature = create_signature(
        private_key
    )

    headers = {

        "KALSHI-ACCESS-KEY":
            API_KEY_ID,

        "KALSHI-ACCESS-SIGNATURE":
            signature,

        "KALSHI-ACCESS-TIMESTAMP":
            timestamp
    }

    print()
    print("=" * 60)
    print("RECORDING BTC 15-MINUTE MARKET")
    print("=" * 60)

    print("Ticker:", ticker)

    print(
        "Target:",
        market["yes_sub_title"]
    )

    print(
        "Closes:",
        market["close_time"]
    )

    print("=" * 60)
    print()

    async with websockets.connect(

        WS_URL,

        additional_headers=headers

    ) as ws:

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
            json.dumps(subscribe)
        )

        print(
            "Listening for market data..."
        )

        while True:

            message = await ws.recv()

            received_at = datetime.now(
                timezone.utc
            ).isoformat()

            try:

                data = json.loads(
                    message
                )

            except json.JSONDecodeError:

                continue

            record = {

                "received_at":
                    received_at,

                "ticker":
                    ticker,

                "target":
                    market.get(
                        "floor_strike"
                    ),

                "message_type":
                    data.get(
                        "type"
                    ),

                "raw_message":
                    json.dumps(
                        data
                    )
            }

            save_record(record)

            print(
                received_at,
                data.get("type")
            )


async def main():

    market = get_current_market()

    if market is None:

        print(
            "No active KXBTC15M market."
        )

        return

    await record_market(
        market
    )


if __name__ == "__main__":

    asyncio.run(main())