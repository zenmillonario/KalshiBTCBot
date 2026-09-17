import pandas as pd
import json
import os
from collections import defaultdict

FILE = "kalshi_btc_continuous.csv"

print("=" * 75)
print("KALSHI BTC 15-MINUTE STREAMING EXECUTION BACKTEST")
print("=" * 75)

if not os.path.exists(FILE):
    print("ERROR: kalshi_btc_continuous.csv not found.")
    input("Press ENTER to exit...")
    raise SystemExit

print("\nStreaming large dataset...")
print("This may take several minutes.")
print("The 14.6 GB file will NOT be loaded into RAM.")

# ------------------------------------------------------------
# We only need these message types
# ------------------------------------------------------------

USE_TYPES = {
    "subscribed",
    "orderbook_snapshot",
    "orderbook_delta",
    "ticker",
}

# ------------------------------------------------------------
# We will maintain a small amount of data per contract.
#
# snapshots establish the book
# deltas modify it
# ticker messages give us high-frequency market prices
# ------------------------------------------------------------

books = {}

# Contract metadata
contracts = {}

# Important observations near the end
observations = defaultdict(list)

# Last ticker per contract
last_ticker = {}

# ------------------------------------------------------------
# Parse one JSON message
# ------------------------------------------------------------

def parse_message(raw):

    try:
        return json.loads(raw)
    except Exception:
        return None


# ------------------------------------------------------------
# Find YES ask from reconstructed book
# ------------------------------------------------------------

def yes_ask_from_book(book):

    yes = book.get("yes", {})

    if not yes:
        return None

    positive = [
        price for price, size in yes.items()
        if size > 0
    ]

    if not positive:
        return None

    return min(positive)


# ------------------------------------------------------------
# Process chunks
# ------------------------------------------------------------

total_rows = 0
ticker_rows = 0
snapshot_rows = 0
delta_rows = 0

reader = pd.read_csv(
    FILE,
    chunksize=100000,
    usecols=[
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

for chunk_number, df in enumerate(reader, 1):

    total_rows += len(df)

    for row in df.itertuples(index=False):

        msg_type = row.message_type

        if msg_type not in USE_TYPES:
            continue

        ticker = row.ticker

        if not ticker or pd.isna(ticker):
            continue

        msg = parse_message(row.raw_message)

        if not msg:
            continue

        # ----------------------------------------------------
        # Establish contract metadata
        # ----------------------------------------------------

        if ticker not in contracts:

            contracts[ticker] = {
                "event_ticker": row.event_ticker,
                "target": row.target,
                "open_time": row.open_time,
                "close_time": row.close_time
            }

        # ----------------------------------------------------
        # SUBSCRIBED
        # ----------------------------------------------------

        if msg_type == "subscribed":
            continue

        # ----------------------------------------------------
        # ORDERBOOK SNAPSHOT
        # ----------------------------------------------------

        if msg_type == "orderbook_snapshot":

            snapshot_rows += 1

            m = msg.get("msg", {})

            yes_levels = m.get("yes_dollars_fp", [])
            no_levels = m.get("no_dollars_fp", [])

            book = {
                "yes": {},
                "no": {}
            }

            for level in yes_levels:

                try:
                    price = float(level[0])
                    size = float(level[1])

                    book["yes"][price] = size

                except Exception:
                    pass

            for level in no_levels:

                try:
                    price = float(level[0])
                    size = float(level[1])

                    book["no"][price] = size

                except Exception:
                    pass

            books[ticker] = book

            continue

        # ----------------------------------------------------
        # ORDERBOOK DELTA
        # ----------------------------------------------------

        if msg_type == "orderbook_delta":

            delta_rows += 1

            m = msg.get("msg", {})

            side = m.get("side")

            try:
                price = float(m.get("price_dollars"))
                delta = float(m.get("delta_fp"))

            except Exception:
                continue

            if ticker not in books:

                books[ticker] = {
                    "yes": {},
                    "no": {}
                }

            if side not in books[ticker]:
                continue

            old = books[ticker][side].get(price, 0)

            new = old + delta

            if new <= 0:
                books[ticker][side].pop(price, None)
            else:
                books[ticker][side][price] = new

            continue

        # ----------------------------------------------------
        # TICKER
        # ----------------------------------------------------

        if msg_type == "ticker":

            ticker_rows += 1

            m = msg.get("msg", {})

            try:

                timestamp = pd.to_datetime(
                    m.get("time"),
                    utc=True
                )

            except Exception:
                continue

            try:
                market_price = float(
                    m.get("price_dollars")
                )
            except Exception:
                market_price = None

            try:
                yes_bid = float(
                    m.get("yes_bid_dollars")
                )
            except Exception:
                yes_bid = None

            try:
                yes_ask = float(
                    m.get("yes_ask_dollars")
                )
            except Exception:
                yes_ask = None

            # Prefer ticker ask because it is directly reported
            # by Kalshi. Reconstructed book is retained as
            # additional information.

            book_ask = None

            if ticker in books:
                book_ask = yes_ask_from_book(
                    books[ticker]
                )

            last_ticker[ticker] = {
                "time": timestamp,
                "price": market_price,
                "bid": yes_bid,
                "ask": yes_ask,
                "book_ask": book_ask
            }

            # Keep ticker history only for observations
            # close to the end.
            #
            # We use the contract close_time to determine
            # how much time remains.

            try:

                close = pd.to_datetime(
                    row.close_time,
                    utc=True
                )

                remaining = (
                    close - timestamp
                ).total_seconds()

            except Exception:
                continue

            # Capture last 5 minutes
            if 0 <= remaining <= 300:

                observations[ticker].append({
                    "time": timestamp,
                    "remaining": remaining,
                    "price": market_price,
                    "bid": yes_bid,
                    "ask": yes_ask,
                    "book_ask": book_ask
                })

    if chunk_number % 10 == 0:

        print(
            f"Processed {total_rows:,} rows | "
            f"Contracts: {len(contracts)} | "
            f"Tickers: {ticker_rows:,}"
        )

print("\n" + "=" * 75)
print("STREAMING COMPLETE")
print("=" * 75)

print(f"Rows processed:       {total_rows:,}")
print(f"Contracts found:      {len(contracts)}")
print(f"Ticker observations:  {ticker_rows:,}")
print(f"Snapshots:            {snapshot_rows:,}")
print(f"Deltas:               {delta_rows:,}")

# ------------------------------------------------------------
# BUILD CONTRACT DATA
# ------------------------------------------------------------

print("\nBuilding contract observations...")

results = []

for ticker, meta in contracts.items():

    obs = observations.get(ticker, [])

    if len(obs) < 5:
        continue

    obs = sorted(
        obs,
        key=lambda x: x["time"]
    )

    # --------------------------------------------------------
    # Determine final outcome using last recorded ticker
    # --------------------------------------------------------

    final = obs[-1]

    final_price = final["price"]

    if final_price is None:
        continue

    if final_price >= 0.90:
        result = "YES"

    elif final_price <= 0.10:
        result = "NO"

    else:
        continue

    row = {
        "ticker": ticker,
        "target": meta["target"],
        "result": result,
        "final_price": final_price
    }

    # --------------------------------------------------------
    # Sample nearest observation to requested remaining times
    # --------------------------------------------------------

    for seconds in [
        300,
        240,
        180,
        120,
        90,
        75,
        60,
        45,
        30,
        20,
        10
    ]:

        candidates = [
            x for x in obs
            if x["remaining"] >= seconds
        ]

        if not candidates:

            row[f"ask_{seconds}s"] = None
            row[f"bid_{seconds}s"] = None
            row[f"price_{seconds}s"] = None

            continue

        # Closest observation to target
        chosen = min(
            candidates,
            key=lambda x:
            abs(x["remaining"] - seconds)
        )

        row[f"ask_{seconds}s"] = chosen["ask"]
        row[f"bid_{seconds}s"] = chosen["bid"]
        row[f"price_{seconds}s"] = chosen["price"]

    results.append(row)

results_df = pd.DataFrame(results)

print(f"\nCompleted contracts: {len(results_df)}")

# ------------------------------------------------------------
# BACKTEST
# ------------------------------------------------------------

print("\n" + "=" * 75)
print("REALISTIC EXECUTION BACKTEST")
print("=" * 75)

entry_times = [
    300,
    240,
    180,
    120,
    90,
    75,
    60,
    45,
    30,
    20,
    10
]

thresholds = [
    0.50,
    0.60,
    0.70,
    0.80,
    0.90,
    0.95
]

backtest = []

for seconds in entry_times:

    print(
        f"\nENTRY: {seconds} SECONDS REMAINING"
    )

    for threshold in thresholds:

        trades_count = 0
        wins = 0
        losses = 0
        profit = 0

        ask_col = f"ask_{seconds}s"

        for _, r in results_df.iterrows():

            ask = r[ask_col]

            if pd.isna(ask):
                continue

            ask = float(ask)

            # Only enter when the actual YES ask is
            # at or above the threshold.

            if ask < threshold:
                continue

            trades_count += 1

            if r["result"] == "YES":

                wins += 1

                profit += (
                    1.0 - ask
                )

            else:

                losses += 1

                profit -= ask

        if trades_count:

            win_rate = (
                wins / trades_count
            ) * 100

            avg_profit = (
                profit / trades_count
            )

            print(
                f"Ask >= {threshold:.0%} | "
                f"Trades {trades_count:3d} | "
                f"W {wins:3d} | "
                f"L {losses:3d} | "
                f"Win {win_rate:6.1f}% | "
                f"P/L ${profit:8.3f} | "
                f"Avg ${avg_profit:8.4f}"
            )

            backtest.append({
                "entry_seconds": seconds,
                "threshold": threshold,
                "trades": trades_count,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "profit": profit,
                "avg_profit": avg_profit
            })

# ------------------------------------------------------------
# SAVE RESULTS
# ------------------------------------------------------------

results_df.to_csv(
    "realistic_stream_contracts.csv",
    index=False
)

backtest_df = pd.DataFrame(backtest)

backtest_df.to_csv(
    "realistic_stream_backtest.csv",
    index=False
)

print("\n" + "=" * 75)
print("FILES CREATED")
print("=" * 75)

print("realistic_stream_contracts.csv")
print("realistic_stream_backtest.csv")

print("\nDONE.")

input("\nPress ENTER to exit...")