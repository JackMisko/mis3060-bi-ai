# =============================================================================
# Script name : hw02_eda.py
# Purpose     : Exploratory data analysis of Wildcat Capital transaction data
#               (MIS3060 HW2)
# Dataset     : data/raw/fact_transactions.csv
# Author      : Jack Miskiewicz (generated with Claude Cowork)
# Generated   : 2026-09-22
# How to run  : python hw02/hw02_eda.py   (from the repository root)
# Outputs     : hw02/hw02_profile.txt
#               hw02/charts/hist_amount.png
#               hw02/charts/box_amount_by_type.png
#               hw02/charts/scatter_shares_amount.png
# =============================================================================

import os
import sys

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # save charts to files without opening a window
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# -----------------------------------------------------------------------------
# Settings
# -----------------------------------------------------------------------------
DATA_PATH = os.path.join("data", "raw", "fact_transactions.csv")
OUT_DIR = "hw02"
CHART_DIR = os.path.join(OUT_DIR, "charts")
PROFILE_PATH = os.path.join(OUT_DIR, "hw02_profile.txt")
EXPECTED_SHAPE = (298772, 9)

# Show every row and column; never truncate with "..."
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")

# Everything printed for items 2-13 is also collected here for the profile file
profile_lines = []


def report(text=""):
    """Print to the terminal and record the same text for the profile file."""
    text = str(text)
    print(text)
    profile_lines.append(text)


def header(title):
    report("")
    report(f"=== {title} ===")


dollar_fmt = FuncFormatter(lambda v, _: f"${v:,.0f}")

# -----------------------------------------------------------------------------
# 1. Load the data
# -----------------------------------------------------------------------------
print("=== 1. LOAD DATA ===")
if not os.path.exists(DATA_PATH):
    print(f"ERROR: Data file not found at '{DATA_PATH}'.")
    print("Place fact_transactions.csv in data/raw/ and run this script "
          "from the repository root.")
    sys.exit(1)

df = pd.read_csv(DATA_PATH)  # txn_date intentionally left as loaded (string)
print(f"Loaded {DATA_PATH}")

# -----------------------------------------------------------------------------
# 2. Shape
# -----------------------------------------------------------------------------
header("2. SHAPE")
n_rows, n_cols = df.shape
report(f"{n_rows:,} rows × {n_cols} columns")

# -----------------------------------------------------------------------------
# 3. Columns and data types
# -----------------------------------------------------------------------------
header("3. COLUMNS AND DATA TYPES")
dtypes = df.dtypes.astype(str).rename("dtype").to_frame()
dtypes.index.name = "column"
report(dtypes.to_string())

# -----------------------------------------------------------------------------
# 4. Missing values
# -----------------------------------------------------------------------------
header("4. MISSING VALUES")
missing = df.isna().sum().rename("missing_count").to_frame()
missing["missing_pct"] = (missing["missing_count"] / n_rows * 100).round(2)
missing.index.name = "column"
report(missing.to_string(formatters={"missing_count": "{:,}".format,
                                     "missing_pct": "{:.2f}%".format}))

# -----------------------------------------------------------------------------
# 5. Descriptive statistics (numeric columns)
# -----------------------------------------------------------------------------
header("5. DESCRIPTIVE STATISTICS (NUMERIC COLUMNS)")
desc = df.describe()  # count, mean, std, min, 25%, 50%, 75%, max
desc = desc.rename(index={"50%": "50% (median)"})
report(desc.to_string())

# -----------------------------------------------------------------------------
# 6. Transaction type breakdown
# -----------------------------------------------------------------------------
header("6. TRANSACTION TYPE BREAKDOWN")
type_counts = df["txn_type"].value_counts()  # sorted most to least frequent
type_table = pd.DataFrame({
    "count": type_counts,
    "percent": (type_counts / type_counts.sum() * 100).round(2),
})
report(type_table.to_string(formatters={"count": "{:,}".format,
                                        "percent": "{:.2f}%".format}))
report(f"Distinct transaction types: {df['txn_type'].nunique()}")

# -----------------------------------------------------------------------------
# 7. Unique entities
# -----------------------------------------------------------------------------
header("7. UNIQUE ENTITIES")
report(f"Unique clients    (client_id)  : {df['client_id'].nunique():,}")
report(f"Unique advisors   (advisor_id) : {df['advisor_id'].nunique():,}")
report(f"Unique securities (security_id): {df['security_id'].nunique():,} "
       "(blanks ignored)")

# -----------------------------------------------------------------------------
# 8. Date range (conversion done on a separate copy only)
# -----------------------------------------------------------------------------
header("8. DATE RANGE")
dates_copy = pd.to_datetime(df["txn_date"].copy(), errors="coerce")
report(f"txn_date stored as : {df['txn_date'].dtype}")
report(f"Earliest txn_date  : {dates_copy.min():%Y-%m-%d}")
report(f"Latest txn_date    : {dates_copy.max():%Y-%m-%d}")
unparsed = dates_copy.isna().sum() - df["txn_date"].isna().sum()
if unparsed > 0:
    report(f"Note: {unparsed:,} txn_date values could not be read as dates.")

# -----------------------------------------------------------------------------
# 9. Duplicate check by txn_id
# -----------------------------------------------------------------------------
header("9. DUPLICATE CHECK (txn_id)")
dup_rows = int(df["txn_id"].duplicated(keep=False).sum())
report(f"Rows with a txn_id that appears more than once: {dup_rows:,}")

# -----------------------------------------------------------------------------
# 10. Amount distribution
# -----------------------------------------------------------------------------
header("10. AMOUNT DISTRIBUTION")
amt_mean = df["amount"].mean()
amt_median = df["amount"].median()
amt_skew = df["amount"].skew()
report(f"Mean amount    : ${amt_mean:,.2f}")
report(f"Median amount  : ${amt_median:,.2f}")
report(f"Skewness       : {amt_skew:.2f}")
if amt_skew > 0.5:
    shape_note = ("Right-skewed: a tail of large transactions pulls the mean "
                  "above the median.")
elif amt_skew < -0.5:
    shape_note = ("Left-skewed: a tail of small transactions pulls the mean "
                  "below the median.")
else:
    shape_note = "Roughly symmetric: mean and median are close together."
report(f"Interpretation : {shape_note}")

# -----------------------------------------------------------------------------
# 11. Group by transaction type
# -----------------------------------------------------------------------------
header("11. AMOUNT BY TRANSACTION TYPE (sorted by mean, descending)")
grouped = (
    df.groupby("txn_type")["amount"]
    .agg(count="count", mean_amount="mean", median_amount="median")
    .round(2)
    .sort_values("mean_amount", ascending=False)
)
report(grouped.to_string(formatters={
    "count": "{:,}".format,
    "mean_amount": "${:,.2f}".format,
    "median_amount": "${:,.2f}".format,
}))

# -----------------------------------------------------------------------------
# 12. Correlation matrix and strongest correlations
# -----------------------------------------------------------------------------
header("12. CORRELATION (shares, price, amount)")
corr_cols = ["shares", "price", "amount"]
corr = df[corr_cols].corr().round(2)
report(corr.to_string())

pairs = []
for i in range(len(corr_cols)):
    for j in range(i + 1, len(corr_cols)):  # each pair once, never self
        pairs.append((corr_cols[i], corr_cols[j], corr.iloc[i, j]))
pairs.sort(key=lambda p: abs(p[2]), reverse=True)

report("")
report("Three strongest correlations (ranked by absolute value):")
for rank, (a, b, r) in enumerate(pairs[:3], start=1):
    report(f"  {rank}. {a} – {b}: {r:.2f}")

# -----------------------------------------------------------------------------
# 13. Negative shares check by transaction type
# -----------------------------------------------------------------------------
header("13. NEGATIVE SHARES CHECK (by txn_type)")
shares_by_type = df.groupby("txn_type")["shares"].agg(
    min_shares="min",
    max_shares="max",
    negative_count=lambda s: int((s < 0).sum()),
)
report(shares_by_type.to_string(na_rep="(none)", formatters={
    "min_shares": "{:,.4f}".format,
    "max_shares": "{:,.4f}".format,
    "negative_count": "{:,}".format,
}))
report(f"Total rows with negative shares: {int((df['shares'] < 0).sum()):,}")

# -----------------------------------------------------------------------------
# 14. Shape validation
# -----------------------------------------------------------------------------
print("\n=== 14. SHAPE VALIDATION ===")
if df.shape != EXPECTED_SHAPE:
    print("*" * 70)
    print(f"WARNING: Shape mismatch! Expected {EXPECTED_SHAPE}, "
          f"got {df.shape}.")
    print("*" * 70)
else:
    print(f"Shape confirmed: {df.shape} matches the expected {EXPECTED_SHAPE}.")

# -----------------------------------------------------------------------------
# 15. Charts
# -----------------------------------------------------------------------------
print("\n=== 15. CHARTS ===")
os.makedirs(CHART_DIR, exist_ok=True)

# 15a. Histogram of amount with mean and median lines
hist_path = os.path.join(CHART_DIR, "hist_amount.png")
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(df["amount"].dropna(), bins=60, color="#4C72B0",
        edgecolor="white", linewidth=0.5)
ax.axvline(amt_mean, color="#C44E52", linestyle="--", linewidth=2,
           label=f"Mean: ${amt_mean:,.2f}")
ax.axvline(amt_median, color="#2CA02C", linestyle="-", linewidth=2,
           label=f"Median: ${amt_median:,.2f}")
ax.set_title("Distribution of Transaction Amount")
ax.set_xlabel("Transaction amount (USD)")
ax.set_ylabel("Number of transactions")
ax.xaxis.set_major_formatter(dollar_fmt)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
ax.legend()
fig.tight_layout()
fig.savefig(hist_path, dpi=150)
plt.close(fig)
print(f"Saved: {hist_path}")

# 15b. Horizontal box plot of amount by txn_type
box_path = os.path.join(CHART_DIR, "box_amount_by_type.png")
type_order = grouped.index.tolist()  # same order as the item 11 table
box_data = [df.loc[df["txn_type"] == t, "amount"].dropna() for t in type_order]
fig, ax = plt.subplots(figsize=(10, 6))
try:
    ax.boxplot(box_data, orientation="horizontal", patch_artist=True,
               flierprops={"markersize": 2, "alpha": 0.3})
except TypeError:  # older matplotlib versions
    ax.boxplot(box_data, vert=False, patch_artist=True,
               flierprops={"markersize": 2, "alpha": 0.3})
ax.set_yticks(range(1, len(type_order) + 1))
ax.set_yticklabels(type_order)
ax.invert_yaxis()  # highest mean at the top
ax.set_title("Transaction Amount by Transaction Type")
ax.set_xlabel("Transaction amount (USD)")
ax.set_ylabel("Transaction type")
ax.xaxis.set_major_formatter(dollar_fmt)
fig.tight_layout()
fig.savefig(box_path, dpi=150)
plt.close(fig)
print(f"Saved: {box_path}")

# 15c. Scatter of shares vs amount, colored by txn_type
scatter_path = os.path.join(CHART_DIR, "scatter_shares_amount.png")
fig, ax = plt.subplots(figsize=(10, 7))
colors = plt.get_cmap("tab10").colors
plotted = df.dropna(subset=["shares", "amount"])
for idx, t in enumerate(sorted(df["txn_type"].dropna().unique())):
    subset = plotted[plotted["txn_type"] == t]
    if subset.empty:
        continue  # types with no share values have nothing to plot
    ax.scatter(subset["shares"], subset["amount"], s=3, alpha=0.25,
               color=colors[idx % len(colors)], label=t, edgecolors="none")
ax.set_title("Shares vs. Transaction Amount by Transaction Type")
ax.set_xlabel("Shares")
ax.set_ylabel("Transaction amount (USD)")
ax.yaxis.set_major_formatter(dollar_fmt)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
leg = ax.legend(title="Transaction type", markerscale=4)
for handle in leg.legend_handles if hasattr(leg, "legend_handles") \
        else leg.legendHandles:
    handle.set_alpha(1)
fig.tight_layout()
fig.savefig(scatter_path, dpi=150)
plt.close(fig)
print(f"Saved: {scatter_path}")

# -----------------------------------------------------------------------------
# 16. Save profile of items 2-13
# -----------------------------------------------------------------------------
print("\n=== 16. PROFILE FILE ===")
with open(PROFILE_PATH, "w", encoding="utf-8") as f:
    f.write("Wildcat Capital — fact_transactions.csv EDA Profile (items 2–13)\n")
    f.write(f"Source: {DATA_PATH}\n")
    f.write("\n".join(profile_lines).lstrip("\n") + "\n")
print(f"Saved: {PROFILE_PATH}")

print("\nEDA script finished successfully.")
