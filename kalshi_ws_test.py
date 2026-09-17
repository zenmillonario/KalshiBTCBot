import os
import time
import base64
import asyncio
import json

import websockets
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


load_dotenv()

API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")
PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH")

WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"

# This may be expired by now.
# We are using it only to test authentication.
MARKET_TICKER = "KXBTC15M-26AUG250345-45"


def load_private_key():
    with open(PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(
            f.read(),
            password=None
        )


def create_signature(private_key):
    timestamp = str(int(time.time() * 1000))

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

    return timestamp, base64.b64encode(signature).decode("utf-8")


async def main():

    private_key = load_private_key()

    timestamp, signature = create_signature(private_key)

    headers = {
        "KALSHI-ACCESS-KEY": API_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }

    print("Connecting to Kalshi...")
    print()

    async with websockets.connect(
        WS_URL,
        additional_headers=headers
    ) as ws:

        print("========================================")
        print("CONNECTED TO KALSHI")
        print("========================================")
        print()

        subscribe_message = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["ticker"],
                "market_tickers": [MARKET_TICKER]
            }
        }

        await ws.send(json.dumps(subscribe_message))

        print("Subscription sent.")
        print("Waiting for response...")
        print()

        try:
            while True:
                message = await asyncio.wait_for(
                    ws.recv(),
                    timeout=10
                )

                print("MESSAGE:")
                print(message)
                print()

        except asyncio.TimeoutError:
            print("No message received for 10 seconds.")


if __name__ == "__main__":
    asyncio.run(main())