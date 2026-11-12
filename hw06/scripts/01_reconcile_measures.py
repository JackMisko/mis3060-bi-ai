"""
HW6 Part B - Reconcile the DAX measure library to pandas
MIS3060 Business Intelligence with AI

What it does
  1. Recomputes every measure independently in pandas from the cleaned CSVs
     (it never reads anything from Power BI to do this).
  2. Writes the pandas results to reports/pandas_values.csv.
  3. If reports/powerbi_export.tsv exists (the wide grid copied from DAX query
     view, see powerbi/dax_build_sheet.md section 3), reshapes it into
     reports/powerbi_values.csv (columns: measure, slice, value).
  4. If reports/powerbi_values.csv exists, compares the two and writes
     reports/measure_reconciliation.csv with columns
     measure, slice, powerbi_value, pandas_value, abs_diff, match.

Usage (from the hw06 folder, Git Bash):
    python scripts/01_reconcile_measures.py
    python scripts/01_reconcile_measures.py path/to/data   # if the CSVs live elsewhere

Each pandas function copies the filter-context behaviour of its DAX measure:
  * A "context" is a date range (from dim_date) plus an optional client tier.
  * Ending AUM uses the LAST snapshot date that has rows inside the context
    (DAX: LASTNONBLANK over dim_date[date]). Snapshots fall on the 1st of the month.
  * SAMEPERIODLASTYEAR / DATEADD shift the context's whole date range and keep
    only dates that exist in dim_date (2020-01-01 to 2024-12-31).

Slice keys (must match the keys used when reshaping the Power BI export):
    total              no filters
    year=2024          dim_date[year] = 2024
    year=2024|tier=HNW dim_date[year] = 2024 and dim_client[client_tier] = HNW
    month=2024-12      December 2024
"""

import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HW_DIR = os.path.dirname(HERE)
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW_DIR, "data")
REPORTS = os.path.join(HW_DIR, "reports")

# Tolerances from the assignment: 0.01 for currency, 0.0001 for ratios
TOL_CURRENCY = 0.01
TOL_RATIO = 0.0001

# measure name -> kind ("currency", "count", "ratio", "bps", "text")
MEASURE_KIND = {
    "AUM (naive SUM)": "currency",
    "Ending AUM": "currency",
    "Ending Clients": "count",
    "Avg AUM per Client": "currency",
    "Ending AUM LY": "currency",
    "AUM YoY %": "ratio",
    "Ending AUM PM": "currency",
    "AUM MoM %": "ratio",
    "Avg Monthly AUM": "currency",
    "Fee Yield (bps)": "bps",
    "Organic Growth Rate": "ratio",
    "AUM-Weighted Alpha": "ratio",
    "Alpha Signal": "text",
    "Top 10 Client Share": "ratio",
}


# ----------------------------------------------------------------------------- data
def find_csv(name):
    """Return the CSV for a table: 'name.csv', or a browser-download copy such as
    'name (2).csv' (the highest copy number wins, as in hw05)."""
    exact = os.path.join(DATA_DIR, f"{name}.csv")
    if os.path.exists(exact):
        return exact
    copies = []
    for f in os.listdir(DATA_DIR) if os.path.isdir(DATA_DIR) else []:
        m = re.fullmatch(re.escape(name) + r" \((\d+)\)\.csv", f)
        if m:
            copies.append((int(m.group(1)), os.path.join(DATA_DIR, f)))
    if copies:
        return max(copies)[1]
    sys.exit(f"Missing {exact}. Put the 8 cleaned CSVs in hw06/data/ "
             f"or pass a folder, e.g.  python scripts/01_reconcile_measures.py ../hw05")


def load(name):
    path = find_csv(name)
    print(f"  loaded {os.path.relpath(path)}")
    return pd.read_csv(path, dtype={"zip_code": str})


snap = load("fact_portfolio_snapshot")
fees = load("fact_fees")
txn = load("fact_transactions")
client = load("dim_client")
cal = load("dim_date")

for df, col in [(snap, "snapshot_date"), (fees, "fee_date"), (txn, "txn_date"), (cal, "date")]:
    df[col] = pd.to_datetime(df[col])

# client_tier comes from dim_client, exactly as the relationship would deliver it
tier_of = client.set_index("client_id")["client_tier"]
for df in (snap, fees, txn):
    df["client_tier"] = df["client_id"].map(tier_of)

CAL_MIN, CAL_MAX = cal["date"].min(), cal["date"].max()


# ----------------------------------------------------------------------------- contexts
class Ctx:
    """A filter context: an inclusive date range plus an optional client tier."""

    def __init__(self, start, end, tier=None):
        self.start, self.end, self.tier = pd.Timestamp(start), pd.Timestamp(end), tier

    def clip(self):
        """Keep only dates that exist in dim_date; None if nothing is left."""
        s, e = max(self.start, CAL_MIN), min(self.end, CAL_MAX)
        return Ctx(s, e, self.tier) if s <= e else None

    def rows(self, df, date_col):
        m = df[date_col].between(self.start, self.end)
        if self.tier is not None:
            m &= df["client_tier"] == self.tier
        return df[m]

    def same_period_last_year(self):
        return Ctx(self.start - pd.DateOffset(years=1), self.end - pd.DateOffset(years=1), self.tier).clip()

    def prev_month(self):
        # DATEADD(-1, MONTH) on a range of whole months: shift the first day back a
        # month and move the end to the last day of the previous month
        start = self.start - pd.DateOffset(months=1)
        end = (self.end.replace(day=1) - pd.Timedelta(days=1)) if self.end.is_month_end \
            else self.end - pd.DateOffset(months=1)
        return Ctx(start, end, self.tier).clip()


def blank():
    return np.nan


def div(n, d):
    """DAX DIVIDE with no alternate: blank when the denominator is 0 or blank
    (a blank numerator also gives blank, as DIVIDE(BLANK(), x) does)."""
    if d is None or pd.isna(d) or d == 0 or n is None or pd.isna(n):
        return blank()
    return n / d


def growth(cur, prior):
    """DIVIDE ( [cur] - [prior], [prior] ) with DAX blank arithmetic: a blank
    current value acts as 0 in the subtraction (a client who left shows -100%),
    and a blank or zero prior value gives blank."""
    if prior is None or pd.isna(prior) or prior == 0:
        return blank()
    cur = 0.0 if cur is None or pd.isna(cur) else cur
    return (cur - prior) / prior


# ----------------------------------------------------------------------------- measures
def last_snapshot_rows(ctx):
    """Snapshot rows on the last date that has data in the context (LASTNONBLANK)."""
    if ctx is None:
        return snap.iloc[0:0]
    s = ctx.rows(snap, "snapshot_date")
    if s.empty:
        return s
    return s[s["snapshot_date"] == s["snapshot_date"].max()]


def aum_naive(ctx):
    s = ctx.rows(snap, "snapshot_date")
    return s["aum"].sum() if len(s) else blank()


def ending_aum(ctx):
    s = last_snapshot_rows(ctx)
    return s["aum"].sum() if len(s) else blank()


def ending_clients(ctx):
    s = last_snapshot_rows(ctx)
    return float(s["client_id"].nunique()) if len(s) else blank()


def avg_aum_per_client(ctx):
    return div(ending_aum(ctx), ending_clients(ctx))


def ending_aum_ly(ctx):
    return ending_aum(ctx.same_period_last_year())


def aum_yoy(ctx):
    return growth(ending_aum(ctx), ending_aum_ly(ctx))


def ending_aum_pm(ctx):
    return ending_aum(ctx.prev_month())


def aum_mom(ctx):
    return growth(ending_aum(ctx), ending_aum_pm(ctx))


def avg_monthly_aum(ctx):
    s = ctx.rows(snap, "snapshot_date")
    return div(s["aum"].sum(), s["snapshot_date"].nunique()) if len(s) else blank()


def total_fees(ctx):
    f = ctx.rows(fees, "fee_date")
    return f["amount"].sum() if len(f) else blank()


def fee_yield_bps(ctx):
    s = ctx.rows(snap, "snapshot_date")
    tf = total_fees(ctx)
    return div(tf * 12 * 10000, s["aum"].sum()) if len(s) and not pd.isna(tf) else blank()


def net_flows(ctx):
    t = ctx.rows(txn, "txn_date")
    if t.empty:
        return blank()
    return t.loc[t["txn_type"] == "Deposit", "amount"].sum() - t.loc[t["txn_type"] == "Withdrawal", "amount"].sum()


def organic_growth(ctx):
    return div(net_flows(ctx), ending_aum_ly(ctx))


def aum_weighted_alpha(ctx):
    s = last_snapshot_rows(ctx)
    s = s[s["is_return_suspect"] == 0]
    return div((s["aum"] * s["active_alpha_ytd"]).sum(), s["aum"].sum()) if len(s) else blank()


def alpha_signal(ctx):
    a = aum_weighted_alpha(ctx)
    if pd.isna(a):
        return None
    if a >= 0.02:
        return "Outperforming"
    if a <= -0.02:
        return "Lagging"
    return "In line"


def top10_share(ctx):
    """Share of Ending AUM held by the 10 largest clients at the last snapshot in the context."""
    s = last_snapshot_rows(ctx)
    if s.empty:
        return blank()
    by_client = s.groupby("client_id")["aum"].sum()
    # TOPN keeps ties at the cut-off, so keep every client >= the 10th largest value
    cutoff = by_client.nlargest(10).min()
    return div(by_client[by_client >= cutoff].sum(), by_client.sum())


MEASURES = {
    "AUM (naive SUM)": aum_naive,
    "Ending AUM": ending_aum,
    "Ending Clients": ending_clients,
    "Avg AUM per Client": avg_aum_per_client,
    "Ending AUM LY": ending_aum_ly,
    "AUM YoY %": aum_yoy,
    "Ending AUM PM": ending_aum_pm,
    "AUM MoM %": aum_mom,
    "Avg Monthly AUM": avg_monthly_aum,
    "Fee Yield (bps)": fee_yield_bps,
    "Organic Growth Rate": organic_growth,
    "AUM-Weighted Alpha": aum_weighted_alpha,
    "Alpha Signal": alpha_signal,
    "Top 10 Client Share": top10_share,
}

# ----------------------------------------------------------------------------- slices
YEARS = sorted(cal["date"].dt.year.unique())
TIERS = sorted(client["client_tier"].unique())

SLICES = {"total": Ctx(CAL_MIN, CAL_MAX)}
for y in YEARS:
    SLICES[f"year={y}"] = Ctx(f"{y}-01-01", f"{y}-12-31")
for t in TIERS:
    SLICES[f"year=2024|tier={t}"] = Ctx("2024-01-01", "2024-12-31", t)
SLICES["month=2024-12"] = Ctx("2024-12-01", "2024-12-31")

# Which measures each slice must cover (assignment Part B, plus extras the report uses)
ALL = list(MEASURES)
BY_YEAR = ["AUM (naive SUM)", "Ending AUM", "Ending Clients", "Ending AUM LY", "AUM YoY %",
           "Avg Monthly AUM", "Fee Yield (bps)", "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal",
           "Top 10 Client Share"]  # Top 10 by year: Part D edge cases (verification.md)
BY_TIER = ["AUM (naive SUM)", "Ending AUM", "Ending Clients", "Avg AUM per Client", "Ending AUM LY",
           "AUM YoY %", "Fee Yield (bps)", "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal",
           "Top 10 Client Share"]
BY_MONTH = ["Ending AUM", "Ending AUM PM", "AUM MoM %"]


def measures_for(slice_key):
    if slice_key == "total":
        return ALL
    if slice_key.startswith("year=") and "|" not in slice_key:
        return BY_YEAR
    if "|tier=" in slice_key:
        return BY_TIER
    if slice_key.startswith("month="):
        return BY_MONTH
    raise ValueError(f"Unknown slice key {slice_key!r}: expected total, year=, year=...|tier= or month=")


# ----------------------------------------------------------------------------- run
def compute_pandas():
    rows = []
    for key, ctx in SLICES.items():
        for m in measures_for(key):
            rows.append({"measure": m, "slice": key, "pandas_value": MEASURES[m](ctx)})
    return pd.DataFrame(rows)


def tolerance(measure):
    return TOL_CURRENCY if MEASURE_KIND[measure] in ("currency", "count") else TOL_RATIO


def compare(pandas_df, pbi_path):
    pbi = pd.read_csv(pbi_path, dtype={"value": str})
    pbi.columns = [c.strip().lower() for c in pbi.columns]
    pbi["measure"] = pbi["measure"].str.strip()
    pbi["slice"] = pbi["slice"].str.strip()
    out = pandas_df.merge(pbi.rename(columns={"value": "powerbi_value"}),
                          on=["measure", "slice"], how="outer", indicator=True)

    def judge(r):
        if r["_merge"] == "left_only":
            return pd.Series({"abs_diff": np.nan, "match": "MISSING_IN_POWERBI"})
        if r["_merge"] == "right_only":
            return pd.Series({"abs_diff": np.nan, "match": "MISSING_IN_PANDAS"})
        pv, pdv = r["powerbi_value"], r["pandas_value"]
        pv_blank = pd.isna(pv) or str(pv).strip() == ""
        pd_blank = pdv is None or (isinstance(pdv, float) and np.isnan(pdv))
        if pv_blank or pd_blank:
            return pd.Series({"abs_diff": np.nan, "match": bool(pv_blank and pd_blank)})
        if MEASURE_KIND.get(r["measure"]) == "text":
            return pd.Series({"abs_diff": np.nan, "match": str(pv).strip() == str(pdv)})
        diff = abs(float(pv) - float(pdv))
        return pd.Series({"abs_diff": diff, "match": diff <= tolerance(r["measure"])})

    out[["abs_diff", "match"]] = out.apply(judge, axis=1)
    return out[["measure", "slice", "powerbi_value", "pandas_value", "abs_diff", "match"]]


def reshape_export(tsv_path, out_path):
    """Turn the wide DAX query view export (one row per slice, one column per
    measure) into the long powerbi_values.csv the assignment asks for."""
    wide = pd.read_csv(tsv_path, sep="\t", dtype=str)
    # DAX query view may wrap column names in brackets, e.g. [Ending AUM]
    wide.columns = [c.strip().strip("[]") for c in wide.columns]
    if "slice" not in wide.columns:
        sys.exit(f"{tsv_path} has no 'slice' column; columns are {list(wide.columns)}")
    unknown = sorted(set(wide.columns) - set(MEASURES) - {"slice"})
    if unknown:
        print(f"  warning: export columns that are not known measures (ignored): {unknown}")
    long = wide.melt(id_vars="slice", var_name="measure", value_name="value")
    long["slice"] = long["slice"].str.strip()
    keep = long.apply(lambda r: r["measure"] in measures_for(r["slice"]), axis=1)
    dropped = int((~keep).sum())
    long = long[keep]
    long[["measure", "slice", "value"]].to_csv(out_path, index=False)
    print(f"Reshaped {tsv_path} -> {out_path} ({len(long)} rows; "
          f"{dropped} exported cells not required for their slice were left out)")
    print("  note: powerbi_values.csv is regenerated from the TSV on every run; edit the TSV, not the CSV.")


def main():
    os.makedirs(REPORTS, exist_ok=True)
    tsv_path = os.path.join(REPORTS, "powerbi_export.tsv")
    if os.path.exists(tsv_path):
        reshape_export(tsv_path, os.path.join(REPORTS, "powerbi_values.csv"))
    pandas_df = compute_pandas()
    pandas_path = os.path.join(REPORTS, "pandas_values.csv")
    pandas_df.to_csv(pandas_path, index=False)
    print(f"pandas: {len(pandas_df)} measure/slice values -> {pandas_path}\n")

    # readable preview of the headline numbers
    show = pandas_df.pivot(index="slice", columns="measure", values="pandas_value")
    with pd.option_context("display.width", 200, "display.max_columns", 20, "display.float_format", "{:,.4f}".format):
        print(show[["Ending AUM", "AUM YoY %", "Fee Yield (bps)", "Organic Growth Rate",
                    "AUM-Weighted Alpha", "Alpha Signal"]].to_string())

    pbi_path = os.path.join(REPORTS, "powerbi_values.csv")
    if not os.path.exists(pbi_path):
        print(f"\nNo {pbi_path} yet: export the Power BI values (guide section 3), then re-run.")
        return 2  # nothing was reconciled, so do not report success

    rec = compare(pandas_df, pbi_path)
    rec_path = os.path.join(REPORTS, "measure_reconciliation.csv")
    rec.to_csv(rec_path, index=False)
    n_ok = (rec["match"] == True).sum()  # noqa: E712 (match also holds text labels)
    print(f"\nReconciliation: {n_ok} of {len(rec)} rows match -> {rec_path}")
    bad = rec[rec["match"] != True]  # noqa: E712
    if len(bad):
        print(bad.to_string(index=False))
    return 0 if bad.empty else 1


if __name__ == "__main__":
    sys.exit(main())
