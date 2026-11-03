"""
HW05 - Wildcat Capital star schema checks
MIS3060 Business Intelligence with AI

Proves the claims in star_design.md with code:
  Part A - every primary key is unique and non-null; every foreign key
           matches its target column (no orphans); blank keys are counted
  Part B - each fact table's stated grain is unique
  Part C - supporting checks for the measure classifications
  Part E - evidence for design questions (a)-(d)

Usage (from the hw05 folder, Git Bash):
    python hw05_star_checks.py                 # CSVs in this folder
    python hw05_star_checks.py "Wildcat Capital Clean"   # or a data folder

The script reads the CSVs only; it never modifies them.
"""

import glob
import os
import re
import sys

import pandas as pd

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))

EXPECTED_ROWS = {
    "dim_advisor": 25,
    "dim_benchmark": 8,
    "dim_client": 2500,
    "dim_date": 1827,
    "dim_security": 500,
    "fact_fees": 122197,
    "fact_portfolio_snapshot": 129547,
    "fact_transactions": 298572,
}

results = []  # (check, passed)


def check(label, passed, detail=""):
    results.append((label, bool(passed)))
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label}" + (f"  ({detail})" if detail else ""))


def load(name):
    """Find name.csv, also accepting browser-download names like 'name (2).csv'.

    If several downloaded copies exist, the highest copy number wins (the most
    recent download), and a warning is printed so the choice is never silent.
    """
    exact = os.path.join(DATA_DIR, f"{name}.csv")
    if os.path.exists(exact):
        path = exact
    else:
        copies = glob.glob(os.path.join(DATA_DIR, f"{name} (*).csv"))
        if not copies:
            sys.exit(f"Could not find {name}.csv in {DATA_DIR}")
        # sort by the number in brackets, not as text ("(10)" must come after "(2)")
        copies.sort(key=lambda p: int(re.search(r"\((\d+)\)\.csv$", p).group(1)))
        path = copies[-1]
        if len(copies) > 1:
            print(f"  [WARN] {len(copies)} copies of {name} found; using the latest")
    print(f"  loaded {name:<24} from {os.path.basename(path)}")
    # zip_code must stay text or leading zeros are lost
    return pd.read_csv(path, dtype={"zip_code": str})


print("Loading tables")
t = {name: load(name) for name in EXPECTED_ROWS}

# ---------------------------------------------------------------- row counts
print("\nRow counts vs handout")
for name, expected in EXPECTED_ROWS.items():
    check(f"{name} has {expected:,} rows", len(t[name]) == expected, f"found {len(t[name]):,}")

# ---------------------------------------------------------------- Part A: keys
print("\nPart A - primary keys (unique, no blanks)")
PRIMARY_KEYS = {
    "dim_advisor": "advisor_id",
    "dim_benchmark": "benchmark_id",
    "dim_client": "client_id",
    "dim_date": "date_id",
    "dim_security": "security_id",
    "fact_fees": "fee_id",
    "fact_portfolio_snapshot": "snapshot_id",
    "fact_transactions": "txn_id",
}
for table, col in PRIMARY_KEYS.items():
    s = t[table][col]
    check(f"{table}[{col}] unique and non-null", s.is_unique and s.notna().all())

# dim_date[date] is the column the facts actually join to, so it must also be unique
check("dim_date[date] unique and non-null (alternate key used for joins)",
      t["dim_date"]["date"].is_unique and t["dim_date"]["date"].notna().all())

print("\nPart A - foreign keys (every non-blank value exists in the target column)")
FOREIGN_KEYS = [
    # (table, column, target table, target column, blanks allowed?)
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id", False),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("fact_fees", "client_id", "dim_client", "client_id", False),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_fees", "fee_date", "dim_date", "date", False),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id", False),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date", False),
    ("fact_transactions", "client_id", "dim_client", "client_id", False),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_transactions", "security_id", "dim_security", "security_id", True),
    ("fact_transactions", "txn_date", "dim_date", "date", False),
]
for table, col, target, target_col, blanks_ok in FOREIGN_KEYS:
    s = t[table][col]
    blanks = int(s.isna().sum())
    orphans = int((~s.dropna().isin(t[target][target_col])).sum())
    ok = orphans == 0 and (blanks_ok or blanks == 0)
    check(f"{table}[{col}] -> {target}[{target_col}]", ok, f"orphans={orphans}, blanks={blanks}")

# The fact dates are stored as calendar dates (text like 2023-12-16), not as date_id
# integers. Together with the zero-orphan checks above against dim_date[date], this
# shows the join column is dim_date[date]. The ISO format also makes the string
# comparisons further down (min/max, <) sort correctly.
print("\nPart A - fact dates are stored as YYYY-MM-DD calendar dates (so they join to dim_date[date])")
for table, col in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date"),
                   ("fact_transactions", "txn_date")]:
    looks_like_date = t[table][col].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$").all()
    check(f"{table}[{col}] values are YYYY-MM-DD dates", looks_like_date)

# client_since is a date attribute, not a foreign key: most values fall before the calendar
cs = t["dim_client"]["client_since"]
before = int((cs < t["dim_date"]["date"].min()).sum())
print(f"  [INFO] dim_client[client_since]: {before:,} of {len(cs):,} values are before "
      f"{t['dim_date']['date'].min()}, so it is not joined to dim_date "
      f"(range {cs.min()} to {cs.max()})")

# ---------------------------------------------------------------- Part B: grain
print("\nPart B - grain checks")
fees, snap, txn = t["fact_fees"], t["fact_portfolio_snapshot"], t["fact_transactions"]

check("fact_fees: one row per client per fee month (client_id + fee_date unique)",
      not fees.duplicated(["client_id", "fee_date"]).any())
check("fact_fees: every fee_date is the 1st of a month",
      (pd.to_datetime(fees["fee_date"]).dt.day == 1).all())

check("fact_portfolio_snapshot: one row per client per month (client_id + snapshot_date unique)",
      not snap.duplicated(["client_id", "snapshot_date"]).any())
check("fact_portfolio_snapshot: every snapshot_date is the 1st of a month",
      (pd.to_datetime(snap["snapshot_date"]).dt.day == 1).all())
check("fact_portfolio_snapshot: each client has exactly one account_type",
      (snap.groupby("client_id")["account_type"].nunique() == 1).all())

natural_key = ["client_id", "txn_date", "txn_type", "security_id"]
repeats = txn[txn.duplicated(natural_key)]
# txn_id uniqueness is already proven in Part A; it is restated here because it IS the grain
check("fact_transactions: txn_id unique (one row per transaction)", txn["txn_id"].is_unique)
check("fact_transactions: no fully duplicated rows apart from txn_id",
      not txn.duplicated(list(txn.columns.drop("txn_id"))).any())
print(f"  [INFO] client + date + type + security repeats {len(repeats):,} times, "
      f"so there is no natural composite key; txn_id defines the grain")
print(f"  [INFO] repeats by type: {repeats['txn_type'].value_counts().to_dict()}")
example = txn[(txn["client_id"] == 1) & (txn["txn_date"] == "2024-09-25")]
print(f"  [INFO] example: client 1 on 2024-09-25 has {len(example)} rows of type "
      f"{sorted(example['txn_type'].unique())}")

# ---------------------------------------------------------------- Part C: measures
# Tolerance: amounts are stored to the cent, so a correct row is off by at most
# half a cent (0.005) from rounding. 0.01 allows that and nothing more.
CENT = 0.01
print("\nPart C - supporting checks for measure classification")
check("fact_fees: amount = aum_basis x bps_charged / 10,000 / 12 (bps is an annual rate)",
      ((fees["aum_basis"] * fees["bps_charged"] / 10000 / 12 - fees["amount"]).abs() < CENT).all())
merged = fees.merge(snap, left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"])
# an inner merge drops unmatched fee rows, so first prove that none were dropped
check("fact_fees: every fee row has a snapshot for the same client and month",
      len(merged) == len(fees), f"{len(merged):,} of {len(fees):,} matched")
check("fact_fees: aum_basis equals that month's snapshot aum (a balance, so semi-additive)",
      len(merged) > 0 and ((merged["aum_basis"] - merged["aum"]).abs() < CENT).all())
check("fact_portfolio_snapshot: active_alpha_ytd = return_ytd - benchmark_return_ytd",
      ((snap["return_ytd"] - snap["benchmark_return_ytd"] - snap["active_alpha_ytd"]).abs() < 1e-5).all())
check("fact_transactions: every amount is positive (direction comes from txn_type)",
      (txn["amount"] > 0).all())
trades = txn[txn["txn_type"].isin(["Buy", "Sell", "Dividend"])]
check("fact_transactions: amount = shares x price on Buy/Sell/Dividend rows",
      len(trades) > 0 and ((trades["shares"] * trades["price"] - trades["amount"]).abs() < CENT).all(),
      f"{len(trades):,} rows")
sec = t["dim_security"]
check("dim_security: expense_ratio_bps is blank exactly on non-ETF rows",
      (sec["expense_ratio_bps"].isna() == (sec["is_etf"].astype(str) == "False")).all())
print(f"  [INFO] flag rows: is_return_suspect={int(snap['is_return_suspect'].sum()):,}, "
      f"is_post_departure_txn={int(txn['is_post_departure_txn'].sum()):,}")

# ---------------------------------------------------------------- Part E: design evidence
print("\nPart E - evidence for the design questions")
cash_types = {"Deposit", "Withdrawal", "Advisory Fee"}
blank_sec = txn[txn["security_id"].isna()]
cash_rows = txn[txn["txn_type"].isin(cash_types)]
check("(a) every blank security_id is a Deposit, Withdrawal or Advisory Fee row",
      len(blank_sec) > 0 and set(blank_sec["txn_type"]) <= cash_types, f"{len(blank_sec):,} blank rows")
check("(a) every Deposit, Withdrawal and Advisory Fee row has a blank security_id",
      len(cash_rows) > 0 and cash_rows["security_id"].isna().all())
check("(a) shares and price are also blank on every cash row",
      cash_rows["shares"].isna().all() and cash_rows["price"].isna().all())

client_adv = t["dim_client"][["client_id", "advisor_id"]]
for table in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
    m = t[table].merge(client_adv, on="client_id", suffixes=("", "_client"))
    check(f"(b) {table}[advisor_id] always equals dim_client[advisor_id]",
          len(m) == len(t[table]) and (m["advisor_id"] == m["advisor_id_client"]).all())

# Coverage of fact dates is already proven by the zero-orphan date checks in Part A.
# What Mark as date table also needs is one row for every day with no gaps.
cal = pd.to_datetime(t["dim_date"]["date"])
check("(c) dim_date is a continuous daily calendar (no missing days)",
      cal.is_monotonic_increasing and (cal.diff().dropna() == pd.Timedelta(days=1)).all(),
      f"{cal.min().date()} to {cal.max().date()}")

# Snapshot benchmark_id belongs to the client's portfolio, not to a security,
# which is why dim_benchmark reaches snapshots directly and transactions via dim_security.
check("(d) snapshot benchmark_id is a client-level attribute (one benchmark per client)",
      (snap.groupby("client_id")["benchmark_id"].nunique() == 1).all())
print(f"  [INFO] benchmarks used: snapshots {sorted(snap['benchmark_id'].unique().tolist())}, "
      f"securities {sorted(sec['benchmark_id'].unique().tolist())}")

# ---------------------------------------------------------------- summary
passed = sum(ok for _, ok in results)
print(f"\n{passed} of {len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
