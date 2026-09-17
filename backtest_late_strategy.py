import pandas as pd

df = pd.read_csv("late_strategy_summary.csv")

# Convert YES market prices into the implied winning side.
# If final result is YES:
#   YES price = entry cost
# If final result is NO:
#   NO price = 1 - YES price

time_points = {
    "5_min": 300,
    "4_min": 240,
    "3_min": 180,
    "2_min": 120,
    "1_min": 60,
    "30_sec": 30,
}

thresholds = [0.50, 0.60, 0.70, 0.80, 0.90, 0.95]

print("=" * 75)
print("KALSHI BTC 15-MINUTE LATE STRATEGY BACKTEST")
print("=" * 75)

all_results = []

for time_name, seconds in time_points.items():

    price_col = f"yes_{seconds}s"

    if price_col not in df.columns:
        continue

    print(f"\n{'=' * 75}")
    print(f"ENTRY TIME: {time_name.replace('_', ' ').upper()}")
    print(f"{'=' * 75}")

    rows = []

    for _, row in df.iterrows():

        yes_price = row[price_col]

        if pd.isna(yes_price):
            continue

        result = row["estimated_result"]

        # The side with the higher market probability
        if yes_price >= 0.50:
            chosen_side = "YES"
            entry_price = yes_price
        else:
            chosen_side = "NO"
            entry_price = 1 - yes_price

        won = chosen_side == result

        # $1 payout contract.
        # Profit per contract = $1 - entry price if win
        # Loss = entry price if lose
        profit = (1 - entry_price) if won else -entry_price

        rows.append({
            "chosen_side": chosen_side,
            "entry_price": entry_price,
            "won": won,
            "profit": profit,
        })

    test = pd.DataFrame(rows)

    for threshold in thresholds:

        trades = test[test["entry_price"] >= threshold].copy()

        if len(trades) == 0:
            continue

        wins = trades["won"].sum()
        losses = len(trades) - wins
        win_rate = wins / len(trades) * 100

        total_profit = trades["profit"].sum()
        avg_profit = trades["profit"].mean()

        print(
            f"Threshold {threshold:.0%} | "
            f"Trades: {len(trades):2d} | "
            f"Wins: {wins:2d} | "
            f"Losses: {losses:2d} | "
            f"Win Rate: {win_rate:5.1f}% | "
            f"Total P/L: ${total_profit:7.2f} | "
            f"Avg/trade: ${avg_profit:6.3f}"
        )

        all_results.append({
            "entry_time": time_name,
            "threshold": threshold,
            "trades": len(trades),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_profit_per_contract": total_profit,
            "avg_profit_per_contract": avg_profit,
        })

results_df = pd.DataFrame(all_results)

results_df.to_csv("backtest_results.csv", index=False)

print("\n" + "=" * 75)
print("BEST STRATEGIES BY AVERAGE PROFIT PER $1 CONTRACT")
print("=" * 75)

print(
    results_df
    .sort_values("avg_profit_per_contract", ascending=False)
    .head(15)
    .to_string(index=False)
)

print("\nFiles created:")
print("backtest_results.csv")
print("\nBacktest complete.")