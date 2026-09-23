# Cross-validation Prompt B: total rows minus rows whose txn_type is Sell,
# Deposit, Withdrawal, Dividend, or Advisory Fee.
# Generated with Claude Cowork, 2026-09-23. Run from the repository root.
import pandas as pd

df = pd.read_csv("data/raw/fact_transactions.csv")
total_rows = len(df)
other_types = ["Sell", "Deposit", "Withdrawal", "Dividend", "Advisory Fee"]
other_count = df["txn_type"].isin(other_types).sum()
buy_by_subtraction = total_rows - other_count
print(f"Total rows                 : {total_rows:,}")
print(f"Non-Buy rows (5 types)     : {other_count:,}")
print(f"Prompt B — by subtraction  : Buy transactions = {buy_by_subtraction:,}")
