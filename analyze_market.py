import pandas as pd
import json

FILE = "kalshi_btc_data.csv"

df = pd.read_csv(FILE)

print("=" * 70)
print("KALSHI BTC 15-MINUTE MARKET ANALYSIS")
print("=" * 70)

print()
print("Total events:", len(df))

print()
print("Event types:")
print(df["message_type"].value_counts())

# ---------------------------------------------------------
# Parse ticker messages
# ---------------------------------------------------------

ticker_rows = []

for _, row in df.iterrows():

    if row["message_type"] != "ticker":
        continue

    try:
        data = json.loads(row["raw_message"])
        msg = data["msg"]

        ticker_rows.append({
            "received_at": row["received_at"],
            "ticker": msg.get("market_ticker"),
            "ts_ms": msg.get("ts_ms"),
            "price": float(msg.get("price_dollars", 0)),
            "yes_bid": float(msg.get("yes_bid_dollars", 0)),
            "yes_ask": float(msg.get("yes_ask_dollars", 0)),
            "volume": float(msg.get("volume_fp", 0)),
            "open_interest": float(
                msg.get("open_interest_fp", 0)
            ),
            "last_trade_size": float(
                msg.get("last_trade_size_fp", 0)
            )
        })

    except Exception:
        pass


ticker_df = pd.DataFrame(ticker_rows)

print()
print("=" * 70)
print("TICKER DATA")
print("=" * 70)

print("Ticker observations:", len(ticker_df))

if len(ticker_df) > 0:

    print()
    print(
        ticker_df[
            [
                "received_at",
                "price",
                "yes_bid",
                "yes_ask",
                "last_trade_size"
            ]
        ].head(10).to_string(index=False)
    )

    print()
    print("LAST 10 TICKER OBSERVATIONS")

    print(
        ticker_df[
            [
                "received_at",
                "price",
                "yes_bid",
                "yes_ask",
                "last_trade_size"
            ]
        ].tail(10).to_string(index=False)
    )

    ticker_df.to_csv(
        "kalshi_ticker_data.csv",
        index=False
    )

# ---------------------------------------------------------
# Parse trades
# ---------------------------------------------------------

trade_rows = []

for _, row in df.iterrows():

    if row["message_type"] != "trade":
        continue

    try:

        data = json.loads(
            row["raw_message"]
        )

        msg = data["msg"]

        trade_rows.append({

            "received_at":
                row["received_at"],

            "ts_ms":
                msg.get("ts_ms"),

            "price":
                float(
                    msg.get(
                        "yes_price_dollars",
                        0
                    )
                ),

            "count":
                float(
                    msg.get(
                        "count_fp",
                        0
                    )
                ),

            "taker_side":
                msg.get(
                    "taker_side"
                )
        })

    except Exception:
        pass


trade_df = pd.DataFrame(
    trade_rows
)

print()
print("=" * 70)
print("TRADE DATA")
print("=" * 70)

print(
    "Trades:",
    len(trade_df)
)

if len(trade_df) > 0:

    print()

    print(
        trade_df.head(10)
        .to_string(index=False)
    )

    print()
    print("LAST 10 TRADES")

    print(
        trade_df.tail(10)
        .to_string(index=False)
    )

    trade_df.to_csv(
        "kalshi_trade_data.csv",
        index=False
    )

print()
print("=" * 70)
print("FILES CREATED")
print("=" * 70)

print("kalshi_ticker_data.csv")
print("kalshi_trade_data.csv")

print()
print("Analysis complete.")