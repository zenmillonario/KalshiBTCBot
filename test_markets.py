import requests
from datetime import datetime


URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

PARAMS = {
    "series_ticker": "KXBTC15M",
    "status": "open",
    "limit": 1
}


def get_market():
    response = requests.get(
        URL,
        params=PARAMS,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    markets = data.get("markets", [])

    if not markets:
        print("No open BTC 15-minute market found.")
        return None

    return markets[0]


def dollars(value):
    if value is None:
        return "N/A"

    return f"${float(value):,.4f}"


market = get_market()

if market:

    print()
    print("=" * 50)
    print("BTC 15-MINUTE MARKET")
    print("=" * 50)

    print(f"Ticker:        {market['ticker']}")

    print()
    print("TARGET")
    print(f"Target price:  {market['yes_sub_title']}")

    print()
    print("YES")
    print(f"Bid:           {dollars(market['yes_bid_dollars'])}")
    print(f"Ask:           {dollars(market['yes_ask_dollars'])}")
    print(f"Bid size:      {market['yes_bid_size_fp']}")
    print(f"Ask size:      {market['yes_ask_size_fp']}")

    print()
    print("NO")
    print(f"Bid:           {dollars(market['no_bid_dollars'])}")
    print(f"Ask:           {dollars(market['no_ask_dollars'])}")

    print()
    print("MARKET ACTIVITY")
    print(f"Open interest: {market['open_interest_fp']}")
    print(f"24h volume:    {market['volume_24h_fp']}")
    print(f"Total volume:  {market['volume_fp']}")

    print()
    print("TIMING")
    print(f"Opens:         {market['open_time']}")
    print(f"Closes:        {market['close_time']}")
    print(f"Expected exp:  {market['expected_expiration_time']}")

    print()
    print("SETTLEMENT")
    print("60 one-second CF Benchmarks BRTI observations")
    print("during the final minute are averaged.")

    print()
    print("RULE")
    print("YES if final-minute BRTI average >= previous")
    print("15-minute settlement BRTI average.")

    print("=" * 50)

import websocket
import json


URL = "wss://www.cfbenchmarks.com/ws/v4"


def on_open(ws):
    print("Connected to CF Benchmarks.")
    print("Requesting available streams...")

    message = {
        "type": "info"
    }

    ws.send(json.dumps(message))


def on_message(ws, message):
    print("\nMESSAGE RECEIVED:")
    print(message)

    ws.close()


def on_error(ws, error):
    print("\nERROR:")
    print(error)


def on_close(ws, close_status_code, close_msg):
    print("\nConnection closed.")
    print("Status:", close_status_code)
    print("Message:", close_msg)


print("Connecting to CF Benchmarks...")

ws = websocket.WebSocketApp(
    URL,
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)

ws.run_forever()