# Cross-validation Prompt A: count rows where txn_type equals exactly 'Buy'.
# Generated with Claude Cowork, 2026-09-23. Run from the repository root.
import pandas as pd

df = pd.read_csv("data/raw/fact_transactions.csv")
buy_count = (df["txn_type"] == "Buy").sum()
print(f"Prompt A — direct filter: Buy transactions = {buy_count:,}")
