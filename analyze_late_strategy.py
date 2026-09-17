import pandas as pd

FILE = "kalshi_btc_continuous.csv"

print("Loading ticker data only...")

chunks = []

for chunk in pd.read_csv(
    FILE,
    usecols=["received_at", "ticker", "target", "message_type", "raw_message"],
    chunksize=500_000
):
    ticker_rows = chunk[chunk["message_type"] == "ticker"].copy()
    if len(ticker_rows):
        chunks.append(ticker_rows)

df = pd.concat(chunks, ignore_index=True)

print(f"Ticker observations loaded: {len(df):,}")

# Extract fields from the JSON message
data = df["raw_message"].str.extract(
    r'"price_dollars":\s*"([^"]+)".*?'
    r'"yes_bid_dollars":\s*"([^"]+)".*?'
    r'"yes_ask_dollars":\s*"([^"]+)"'
)

df["price"] = pd.to_numeric(data[0], errors="coerce")
df["yes_bid"] = pd.to_numeric(data[1], errors="coerce")
df["yes_ask"] = pd.to_numeric(data[2], errors="coerce")

df["time"] = pd.to_datetime(df["received_at"], utc=True)

print("\nBuilding contract summaries...")

results = []

for ticker, g in df.groupby("ticker"):

    g = g.sort_values("time").copy()

    if len(g) < 100:
        continue

    start = g["time"].min()
    end = g["time"].max()
    duration = (end - start).total_seconds()

    # Skip obvious incomplete contracts
    if duration < 600:
        continue

    final_price = g["price"].dropna().iloc[-1]

    result = "YES" if final_price >= 0.90 else (
        "NO" if final_price <= 0.10 else "UNCLEAR"
    )

    row = {
        "ticker": ticker,
        "start": start,
        "end": end,
        "duration_seconds": round(duration, 1),
        "final_market_price": final_price,
        "estimated_result": result,
        "observations": len(g),
    }

    # Get market state approximately 5, 4, 3, 2, 1 minutes
    # before the end of the recorded contract
    for seconds in [300, 240, 180, 120, 60, 30, 10]:

        target_time = end - pd.Timedelta(seconds=seconds)

        subset = g[g["time"] <= target_time]

        if len(subset):
            obs = subset.iloc[-1]

            row[f"yes_{seconds}s"] = obs["price"]
            row[f"bid_{seconds}s"] = obs["yes_bid"]
            row[f"ask_{seconds}s"] = obs["yes_ask"]

    results.append(row)

summary = pd.DataFrame(results)

summary.to_csv("late_strategy_summary.csv", index=False)

print(f"\nComplete contracts analyzed: {len(summary)}")

print("\nRESULT DISTRIBUTION")
print(summary["estimated_result"].value_counts())

print("\nFIRST 10 CONTRACTS")
cols = [
    "ticker",
    "estimated_result",
    "yes_300s",
    "yes_180s",
    "yes_60s",
    "yes_30s",
    "yes_10s",
    "final_market_price"
]

available = [c for c in cols if c in summary.columns]

print(summary[available].head(10).to_string(index=False))

print("\nFiles created:")
print("late_strategy_summary.csv")
print("\nAnalysis complete.")