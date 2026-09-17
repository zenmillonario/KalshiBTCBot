import pandas as pd
import json
import os
from datetime import datetime, timezone

print("=" * 75)
print("KALSHI BTC 15-MINUTE REALISTIC EXECUTION BACKTEST")
print("=" * 75)

# ------------------------------------------------------------
# FILES
# ------------------------------------------------------------

TICKER_FILE = "kalshi_ticker_data.csv"
TRADE_FILE = "kalshi_trade_data.csv"

print("\nLoading recorded data...")

if not os.path.exists(TICKER_FILE):
    print(f"ERROR: {TICKER_FILE} not found.")
    input("\nPress ENTER to exit...")
    raise SystemExit

if not os.path.exists(TRADE_FILE):
    print(f"ERROR: {TRADE_FILE} not found.")
    input("\nPress ENTER to exit...")
    raise SystemExit

ticker = pd.read_csv(TICKER_FILE)
trades = pd.read_csv(TRADE_FILE)

ticker["received_at"] = pd.to_datetime(ticker["received_at"], utc=True)
trades["received_at"] = pd.to_datetime(trades["received_at"], utc=True)

print(f"Ticker rows: {len(ticker):,}")
print(f"Trade rows:  {len(trades):,}")

# ------------------------------------------------------------
# DETERMINE CONTRACTS
# ------------------------------------------------------------

contracts = sorted(ticker["ticker"].dropna().unique())

print(f"Contracts found: {len(contracts)}")

# ------------------------------------------------------------
# HELPER
# ------------------------------------------------------------

def get_value_at_time(df, seconds_remaining):
    """
    Get the observation closest to the desired time before
    contract close.

    We use the last observation at or before the target time.
    """

    if len(df) == 0:
        return None

    end_time = df["received_at"].max()

    target_time = end_time - pd.Timedelta(seconds=seconds_remaining)

    before = df[df["received_at"] <= target_time]

    if len(before) == 0:
        return None

    return before.iloc[-1]


# ------------------------------------------------------------
# ANALYZE EACH CONTRACT
# ------------------------------------------------------------

results = []

print("\nAnalyzing contracts...")

for i, contract in enumerate(contracts, 1):

    df = ticker[ticker["ticker"] == contract].copy()

    if len(df) < 20:
        continue

    df = df.sort_values("received_at")

    start = df["received_at"].min()
    end = df["received_at"].max()

    # Need approximately a complete contract
    duration = (end - start).total_seconds()

    if duration < 600:
        continue

    # Final market price
    final_row = df.iloc[-1]

    final_price = float(final_row["price"])

    # Determine result.
    # Near settlement, YES ~= 1 means YES won.
    # YES ~= 0 means NO won.
    if final_price >= 0.90:
        result = "YES"
    elif final_price <= 0.10:
        result = "NO"
    else:
        continue

    row = {
        "ticker": contract,
        "start": start,
        "end": end,
        "result": result,
        "final_price": final_price
    }

    # --------------------------------------------------------
    # Capture prices at different remaining times
    # --------------------------------------------------------

    for seconds in [300, 240, 180, 120, 90, 75, 60, 45, 30, 20, 10]:

        obs = get_value_at_time(df, seconds)

        if obs is None:
            row[f"yes_{seconds}s"] = None
            row[f"bid_{seconds}s"] = None
            row[f"ask_{seconds}s"] = None
        else:
            row[f"yes_{seconds}s"] = float(obs["price"])
            row[f"bid_{seconds}s"] = float(obs["yes_bid"])
            row[f"ask_{seconds}s"] = float(obs["yes_ask"])

    results.append(row)

    if i % 10 == 0:
        print(f"Processed {i}/{len(contracts)} contracts...")

results_df = pd.DataFrame(results)

print("\n" + "=" * 75)
print("CONTRACTS ANALYZED")
print("=" * 75)

print(f"Completed contracts: {len(results_df)}")

if len(results_df) == 0:
    print("No complete contracts found.")
    input("\nPress ENTER to exit...")
    raise SystemExit

print("\nRESULT DISTRIBUTION")
print(results_df["result"].value_counts())

# ------------------------------------------------------------
# STRATEGY TEST
# ------------------------------------------------------------

print("\n" + "=" * 75)
print("REALISTIC ENTRY TEST")
print("=" * 75)

entry_times = [300, 240, 180, 120, 90, 75, 60, 45, 30, 20, 10]
thresholds = [0.50, 0.60, 0.70, 0.80, 0.90, 0.95]

all_results = []

for seconds in entry_times:

    print("\n" + "-" * 75)
    print(f"ENTRY WITH {seconds} SECONDS REMAINING")
    print("-" * 75)

    for threshold in thresholds:

        trades_count = 0
        wins = 0
        losses = 0
        total_profit = 0.0

        price_col = f"yes_{seconds}s"
        ask_col = f"ask_{seconds}s"

        for _, r in results_df.iterrows():

            yes_price = r[price_col]
            yes_ask = r[ask_col]

            if pd.isna(yes_price):
                continue

            # ------------------------------------------------
            # We require the YES ask to actually be available.
            # If ask is missing, don't assume execution.
            # ------------------------------------------------

            if pd.isna(yes_ask):
                continue

            yes_ask = float(yes_ask)

            # Strategy:
            # Buy YES only when executable ask >= threshold.
            #
            # This is intentionally conservative:
            # we're testing whether a very strong late signal
            # is still profitable.
            # ------------------------------------------------

            if yes_ask < threshold:
                continue

            trades_count += 1

            if r["result"] == "YES":

                wins += 1

                # Contract pays $1.
                # Cost = ask.
                profit = 1.00 - yes_ask

            else:

                losses += 1

                # Losing YES contract goes to $0.
                profit = -yes_ask

            total_profit += profit

        if trades_count > 0:

            win_rate = wins / trades_count * 100
            avg_profit = total_profit / trades_count

            print(
                f"Ask >= {threshold:.0%} | "
                f"Trades: {trades_count:3d} | "
                f"Wins: {wins:3d} | "
                f"Losses: {losses:3d} | "
                f"Win Rate: {win_rate:6.1f}% | "
                f"P/L: ${total_profit:7.3f} | "
                f"Avg: ${avg_profit:7.4f}"
            )

            all_results.append({
                "entry_seconds": seconds,
                "threshold": threshold,
                "trades": trades_count,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "total_profit": total_profit,
                "avg_profit": avg_profit
            })

# ------------------------------------------------------------
# BEST STRATEGIES
# ------------------------------------------------------------

summary = pd.DataFrame(all_results)

print("\n" + "=" * 75)
print("BEST REALISTIC STRATEGIES")
print("=" * 75)

if len(summary):

    best = summary.sort_values(
        "avg_profit",
        ascending=False
    ).head(20)

    print(
        best[
            [
                "entry_seconds",
                "threshold",
                "trades",
                "wins",
                "losses",
                "win_rate",
                "total_profit",
                "avg_profit"
            ]
        ].to_string(index=False)
    )

# ------------------------------------------------------------
# SAVE
# ------------------------------------------------------------

results_df.to_csv(
    "realistic_contract_analysis.csv",
    index=False
)

summary.to_csv(
    "realistic_backtest_results.csv",
    index=False
)

print("\n" + "=" * 75)
print("FILES CREATED")
print("=" * 75)

print("realistic_contract_analysis.csv")
print("realistic_backtest_results.csv")

print("\nBacktest complete.")

input("\nPress ENTER to exit...")