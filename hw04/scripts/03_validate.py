"""
HW4 Part D - Referential integrity and validation, raw vs clean.

Runs the SAME checks on data/raw/ and data/clean/ and compares them:

  1. check_referential_integrity()  one reusable function, applied to all 13
     relationships (10 ID-based + 3 to dim_date).  Reused in Assignment 5.
  2. Rule checks for every column with a natural business bound
     (ranges, allowed code lists, sign rules, conditional presence).
  3. Cross-table reconciliations: a recomputed value vs the stored value.
  4. IQR outlier flags on numeric columns with no natural bound.
  5. Scorecard: one row per table per stage with % completeness,
     % key uniqueness, % type validity, % rule pass, % referential match.

All files are read as text (dtype=str, keep_default_na=False); every check
converts on purpose. Nothing is written to data/.

Usage (from the hw04 folder):
    python scripts/03_validate.py

Outputs (reports/):
    ri_results.csv, rule_checks.csv, reconciliations.csv,
    outliers_iqr.csv, data_quality_scorecard.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STAGES = {"raw": ROOT / "data" / "raw", "clean": ROOT / "data" / "clean"}
REPORT_DIR = ROOT / "reports"

TABLES = [
    "dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]
PK = {
    "dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
    "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
    "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id",
}

# (fact table, fact key, dim table, dim key): 10 ID-based + 3 date relationships
RELATIONSHIPS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]

CASH_TYPES = {"Deposit", "Withdrawal", "Advisory Fee"}
SECURITY_TYPES = {"Buy", "Sell", "Dividend"}
US_STATES = set("""AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ
NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY""".split())
RISK_PROFILES = {"Conservative", "Moderately Conservative", "Balanced", "Moderately Aggressive", "Aggressive"}
ACCOUNT_TYPES = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}


# ==========================================================================
# 1. Reusable referential-integrity function  (KEEP for Assignment 5)
# ==========================================================================

def check_referential_integrity(fact_df, fact_key, dim_df, dim_key):
    """Check that every value of fact_df[fact_key] exists in dim_df[dim_key].

    Keys are compared exactly as text after trimming whitespace, which is what
    a join on text columns does; '45.0' TEXT does NOT match '45'. A float
    column whose values are all whole numbers (e.g. an ID column that pandas
    read as float because of blanks) is compared as integers first. Blank /
    NaN keys are counted as null keys and excluded from the match rate.

    Returns a dict:
        fact_rows              rows in fact_df
        null_key_rows          rows whose key is blank / NaN
        null_key_rate          null_key_rows / fact_rows
        evaluated_rows         rows with a non-null key
        matched_rows           non-null keys found in dim_df[dim_key]
        match_rate             matched_rows / evaluated_rows (NaN if none evaluated)
        orphan_row_count       non-null keys NOT found in the dimension
        distinct_orphan_keys   sorted list of the distinct orphan key values
        orphan_rows            DataFrame of the orphan fact rows
        dim_key_unique         True if dim_key is unique in dim_df (required for a 1-to-many join)
    """
    def as_key(s):
        if pd.api.types.is_float_dtype(s) and (s.dropna() % 1 == 0).all():
            s = s.astype("Int64")
        s = s.astype("string").str.strip()
        return s.mask(s.isna() | s.isin(["", "nan", "NaN", "None", "<NA>"]))

    fkey = as_key(fact_df[fact_key])
    dkey = as_key(dim_df[dim_key])
    null = fkey.isna()
    orphan = ~null & ~fkey.isin(set(dkey.dropna()))
    n, evaluated = len(fkey), int((~null).sum())
    return {
        "fact_rows": n,
        "null_key_rows": int(null.sum()),
        "null_key_rate": float(null.mean()) if n else 0.0,
        "evaluated_rows": evaluated,
        "matched_rows": evaluated - int(orphan.sum()),
        "match_rate": 1 - float(orphan.sum()) / evaluated if evaluated else np.nan,
        "orphan_row_count": int(orphan.sum()),
        "distinct_orphan_keys": sorted(fkey[orphan].unique().tolist()),
        # positional mask, so a non-unique index cannot return extra rows
        "orphan_rows": fact_df[orphan.to_numpy()],
        "dim_key_unique": bool(dkey.dropna().is_unique),
    }


# ==========================================================================
# Helpers
# ==========================================================================

def read_text(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def num(s):
    """Strict numeric parse: '9.28%' or '' -> NaN."""
    return pd.to_numeric(s.where(s.str.strip() != ""), errors="coerce")


def blank(s):
    return s.str.strip() == ""


def parses(s, kind):
    v = s.str.strip()
    if kind == "int":
        return v.str.match(r"^-?\d+$")
    if kind == "float":
        return num(v).notna()
    if kind == "date":
        return pd.to_datetime(v.where(v.str.match(r"^\d{4}-\d{2}-\d{2}$")),
                              format="%Y-%m-%d", errors="coerce").notna()
    if kind == "bool":
        return v.isin(["True", "False"])
    if kind == "flag":
        return v.isin(["0", "1"])
    return pd.Series(True, index=s.index)


def everywhere(df):
    return pd.Series(True, index=df.index)


# ==========================================================================
# Column specs: expected type, and where a value is EXPECTED to be present
# ==========================================================================

# "present_when" returns the rows on which a blank would be a defect.
# Columns that are legitimately blank on some rows (decision log L01, L02)
# are only required where the business says they apply.
TYPES = {
    "dim_advisor": {"advisor_id": "int", "first_name": "text", "last_name": "text", "region": "text",
                    "years_experience": "int", "aum_target_mm": "int", "certifications": "text"},
    "dim_benchmark": {"benchmark_id": "int", "name": "text", "asset_class": "text", "ticker_proxy": "text"},
    "dim_client": {"client_id": "int", "first_name": "text", "last_name": "text", "age": "int", "city": "text",
                   "state": "text", "zip_code": "text", "risk_profile": "text", "client_tier": "text",
                   "primary_account_type": "text", "initial_aum": "float", "client_since": "date",
                   "advisor_id": "int", "is_active": "bool"},
    "dim_date": {"date_id": "int", "date": "date", "year": "int", "quarter": "int", "month": "int",
                 "month_name": "text", "week_of_year": "int", "day_of_week": "text", "is_month_end": "flag",
                 "is_quarter_end": "flag", "is_year_end": "flag", "is_trading_day": "flag"},
    "dim_security": {"security_id": "int", "ticker": "text", "name": "text", "asset_class": "text",
                     "sector": "text", "benchmark_id": "int", "is_etf": "bool", "expense_ratio_bps": "float"},
    "fact_fees": {"fee_id": "int", "client_id": "int", "advisor_id": "int", "fee_date": "date",
                  "fee_type": "text", "aum_basis": "float", "bps_charged": "float", "amount": "float",
                  "is_aum_floor": "flag"},
    "fact_portfolio_snapshot": {"snapshot_id": "int", "client_id": "int", "advisor_id": "int",
                                "benchmark_id": "int", "snapshot_date": "date", "year": "int", "month": "int",
                                "aum": "float", "return_ytd": "float", "benchmark_return_ytd": "float",
                                "active_alpha_ytd": "float", "cash_pct": "float", "account_type": "text",
                                "is_return_suspect": "flag", "is_aum_floor": "flag"},
    "fact_transactions": {"txn_id": "int", "client_id": "int", "advisor_id": "int", "security_id": "int",
                          "txn_date": "date", "txn_type": "text", "shares": "float", "price": "float",
                          "amount": "float", "is_post_departure_txn": "flag"},
}

PRESENT_WHEN = {
    ("dim_security", "sector"): lambda t: t["is_etf"] == "False",
    ("dim_security", "expense_ratio_bps"): lambda t: t["is_etf"] == "True",
    ("fact_transactions", "security_id"): lambda t: t["txn_type"].isin(SECURITY_TYPES),
    ("fact_transactions", "shares"): lambda t: t["txn_type"].isin(SECURITY_TYPES),
    ("fact_transactions", "price"): lambda t: t["txn_type"].isin(SECURITY_TYPES),
}

# Values that are present as text but carry no information (count as missing
# for completeness). 'Unknown' is the explicit marker from D08: standardizing a
# blank to 'Unknown' must NOT be scored as filling it in.
NO_INFO = {("dim_client", "risk_profile"): {"Unknown"}}

# Natural / business keys that must be unique, in addition to the primary key.
BUSINESS_KEYS = {
    "dim_client": ["first_name", "age", "city", "state", "zip_code", "client_since", "initial_aum"],
    "dim_date": ["date"],
    "dim_security": ["ticker"],
    "fact_fees": ["client_id", "fee_date", "fee_type"],
    "fact_portfolio_snapshot": ["client_id", "snapshot_date"],
    # a transaction is the same event if everything but the surrogate IDs matches.
    # client_id is left out on purpose: the 200 orphan copies (D07) differ from
    # the real row ONLY in client_id. Trade-off: two clients of one advisor with
    # an identical same-day cash flow would also count as duplicates (0 in clean).
    "fact_transactions": ["advisor_id", "security_id", "txn_date", "txn_type", "shares", "price", "amount"],
}


# ==========================================================================
# 2. Rule checks: natural bounds, code lists, sign rules
# ==========================================================================

def r_range(col, lo=None, hi=None):
    def f(t):
        v = num(t[col])
        ok = pd.Series(True, index=t.index)
        if lo is not None:
            ok &= v >= lo
        if hi is not None:
            ok &= v <= hi
        return ok, v.notna()
    return f


def r_date_range(col, lo, hi):
    def f(t):
        d = pd.to_datetime(t[col], format="%Y-%m-%d", errors="coerce")
        return (d >= pd.Timestamp(lo)) & (d <= pd.Timestamp(hi)), d.notna()
    return f


def r_codes(col, allowed):
    def f(t):
        return t[col].isin(allowed), ~blank(t[col])
    return f


def r_pattern(col, pattern):
    def f(t):
        return t[col].str.match(pattern), ~blank(t[col])
    return f


def r_cert_tokens(t):
    # 'None' is only valid on its own ("no certification", L03), never in a list
    toks = t["certifications"].str.split(",").apply(
        lambda xs: [x.strip() for x in xs] == ["None"] or all(x.strip() in {"CFA", "CFP", "CIMA"} for x in xs))
    return toks, ~blank(t["certifications"])


def r_etf_fields(col, required_when):
    # L02: sector exists only on non-ETFs, expense ratio only on ETFs. Completeness
    # checks presence where expected; this also catches a value where none applies.
    def f(t):
        return ~blank(t[col]) == (t["is_etf"] == required_when), t["is_etf"].isin(["True", "False"])
    return f


def r_snapshot_year_month_match_date(t):
    d = t["snapshot_date"]
    return (t["year"] == d.str[0:4]) & (t["month"].str.zfill(2) == d.str[5:7]), parses(d, "date")


def r_cash_rows_have_no_security(t):
    is_cash = t["txn_type"].isin(CASH_TYPES)
    no_sec = blank(t["security_id"]) & blank(t["shares"]) & blank(t["price"])
    return is_cash == no_sec, ~blank(t["txn_type"])


def r_fee_first_of_month(t):
    return t["fee_date"].str[8:10] == "01", parses(t["fee_date"], "date")


def r_snapshot_first_of_month(t):
    return t["snapshot_date"].str[8:10] == "01", parses(t["snapshot_date"], "date")


RULES = {
    "dim_advisor": [
        ("years_experience", "range 0-50", r_range("years_experience", 0, 50)),
        ("aum_target_mm", "range > 0", r_range("aum_target_mm", 0.000001)),
        ("region", "code list", r_codes("region", {"Northeast", "Southeast", "Mid-Atlantic", "West", "Midwest"})),
        ("certifications", "code list (comma tokens)", r_cert_tokens),
    ],
    "dim_client": [
        ("age", "range 18-110", r_range("age", 18, 110)),
        ("state", "USPS code list", r_codes("state", US_STATES)),
        ("zip_code", "5-digit text", r_pattern("zip_code", r"^\d{5}$")),
        ("risk_profile", "code list (+ 'Unknown' marker)", r_codes("risk_profile", RISK_PROFILES | {"Unknown"})),
        ("client_tier", "code list", r_codes("client_tier", {"Retail", "HNW", "UHNW"})),
        ("primary_account_type", "code list", r_codes("primary_account_type", ACCOUNT_TYPES)),
        ("initial_aum", "sign: > 0", r_range("initial_aum", 0.01)),
        ("client_since", "date <= 2024-12-31", r_date_range("client_since", "1950-01-01", "2024-12-31")),
    ],
    # True/False and 0/1 columns are not repeated here: their allowed values ARE
    # their type ("bool" / "flag" in TYPES), so they are scored under type validity.
    "dim_benchmark": [
        ("asset_class", "code list", r_codes("asset_class", {"Equity", "Fixed Income", "Multi-Asset", "International",
                                                             "Small Cap", "Emerging", "Cash"})),
        ("ticker_proxy", "capital letters / digits / _", r_pattern("ticker_proxy", r"^[A-Z][A-Z0-9_]{1,11}$")),
    ],
    "dim_date": [
        ("date", "range 2020-2024", r_date_range("date", "2020-01-01", "2024-12-31")),
        ("year", "range 2020-2024", r_range("year", 2020, 2024)),
        ("quarter", "range 1-4", r_range("quarter", 1, 4)),
        ("month", "range 1-12", r_range("month", 1, 12)),
        ("month_name", "code list", r_codes("month_name", {
            "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
            "November", "December"})),
        ("week_of_year", "range 1-53", r_range("week_of_year", 1, 53)),
        ("day_of_week", "code list", r_codes("day_of_week", {
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"})),
    ],
    "dim_security": [
        ("ticker", "1-5 capital letters", r_pattern("ticker", r"^[A-Z]{1,5}$")),
        ("asset_class", "code list", r_codes("asset_class", {"Equity", "Fixed Income", "Alternative", "Cash Equivalent"})),
        ("expense_ratio_bps", "range 0-300", r_range("expense_ratio_bps", 0, 300)),
        ("sector", "present exactly on non-ETFs", r_etf_fields("sector", "False")),
        ("expense_ratio_bps", "present exactly on ETFs", r_etf_fields("expense_ratio_bps", "True")),
    ],
    "fact_fees": [
        ("fee_date", "range 2020-2024", r_date_range("fee_date", "2020-01-01", "2024-12-31")),
        ("fee_date", "first of month", r_fee_first_of_month),
        ("fee_type", "code list", r_codes("fee_type", {"Management", "Advisory", "Custodial", "Performance"})),
        ("aum_basis", "sign: > 0", r_range("aum_basis", 0.01)),
        ("bps_charged", "range 0-300", r_range("bps_charged", 0, 300)),
        ("amount", "sign: > 0", r_range("amount", 0.01)),
    ],
    "fact_portfolio_snapshot": [
        ("snapshot_date", "range 2020-2024", r_date_range("snapshot_date", "2020-01-01", "2024-12-31")),
        ("snapshot_date", "first of month", r_snapshot_first_of_month),
        ("year", "range 2020-2024", r_range("year", 2020, 2024)),
        ("month", "range 1-12", r_range("month", 1, 12)),
        ("year", "year/month agree with snapshot_date", r_snapshot_year_month_match_date),
        ("aum", "sign: > 0", r_range("aum", 0.01)),
        ("return_ytd", "range >= -100%", r_range("return_ytd", -1)),
        ("benchmark_return_ytd", "range -100% to +100%", r_range("benchmark_return_ytd", -1, 1)),
        ("cash_pct", "range 0-1", r_range("cash_pct", 0, 1)),
        ("account_type", "code list", r_codes("account_type", ACCOUNT_TYPES)),
    ],
    "fact_transactions": [
        ("txn_date", "range 2020-2024", r_date_range("txn_date", "2020-01-01", "2024-12-31")),
        ("txn_type", "code list", r_codes("txn_type", CASH_TYPES | SECURITY_TYPES)),
        ("shares", "sign: > 0 (direction from txn_type)", r_range("shares", 0.000001)),
        ("price", "sign: > 0", r_range("price", 0.01)),
        ("amount", "sign: > 0", r_range("amount", 0.01)),
        ("security_id", "blank exactly on cash rows", r_cash_rows_have_no_security),
    ],
}


def run_rules(stage, t):
    rows = []
    for table, rules in RULES.items():
        df = t[table]
        for col, name, fn in rules:
            ok, ev = fn(df)
            ok, ev = ok.fillna(False).astype(bool), ev.fillna(False).astype(bool)
            failed = int((ev & ~ok).sum())
            rows.append({"stage": stage, "table": table, "column": col, "rule": name,
                         "rows_evaluated": int(ev.sum()), "rows_failed": failed,
                         "pct_pass": round(100 * (1 - failed / ev.sum()), 3) if ev.sum() else 100.0,
                         "examples": "; ".join(df.loc[ev & ~ok, col].astype(str).head(3))})
    return pd.DataFrame(rows)


# ==========================================================================
# 3. Cross-table reconciliations (recomputed vs stored)
# ==========================================================================

def reconciliations(stage, t):
    fee, snap, tx = t["fact_fees"], t["fact_portfolio_snapshot"], t["fact_transactions"]
    client = t["dim_client"].drop_duplicates("client_id")
    out = []

    def add(name, tables, stored, recomputed, ev, tol):
        ev = ev.fillna(False).astype(bool)
        diff = (stored - recomputed).abs()
        fail = ev & (diff > tol)
        out.append({"stage": stage, "reconciliation": name, "tables": tables,
                    "rows_evaluated": int(ev.sum()), "rows_failed": int(fail.sum()),
                    "pct_pass": round(100 * (1 - fail.sum() / ev.sum()), 3) if ev.sum() else 100.0,
                    "max_abs_diff": float(diff[ev].max()) if ev.any() else 0.0, "tolerance": tol})

    # R1 fee basis = snapshot AUM for the same client-month  (fees vs snapshots)
    m = fee.merge(snap[["client_id", "snapshot_date", "aum"]].drop_duplicates(["client_id", "snapshot_date"]),
                  left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"], how="left")
    add("R1 fee aum_basis = snapshot aum (same client-month)", "fact_fees x fact_portfolio_snapshot",
        num(m["aum_basis"]), num(m["aum"]), num(m["aum"]).notna() & num(m["aum_basis"]).notna(), 0.01)
    # a fee with no snapshot for its client-month cannot be compared above; report it, don't hide it
    out[-1]["rows_unmatched"] = int(m["snapshot_date"].isna().sum())

    # R2 fee amount recomputed from basis and bps (stored vs recomputed)
    add("R2 fee amount = aum_basis x bps / 10,000 / 12", "fact_fees",
        num(fee["amount"]), num(fee["aum_basis"]) * num(fee["bps_charged"]) / 120000,
        num(fee["amount"]).notna() & num(fee["aum_basis"]).notna() & num(fee["bps_charged"]).notna(), 0.011)

    # R3 trade amount recomputed from shares x price (sign rule included: no abs())
    sec = ~blank(tx["security_id"])
    add("R3 transaction amount = shares x price (signed)", "fact_transactions",
        num(tx["amount"]), num(tx["shares"]) * num(tx["price"]),
        sec & num(tx["shares"]).notna() & num(tx["price"]).notna() & num(tx["amount"]).notna(), 0.011)

    # R4 return recomputed two ways: benchmark + alpha, and AUM vs prior December
    add("R4a return_ytd = benchmark_return_ytd + active_alpha_ytd", "fact_portfolio_snapshot",
        num(snap["return_ytd"]), num(snap["benchmark_return_ytd"]) + num(snap["active_alpha_ytd"]),
        num(snap["return_ytd"]).notna() & num(snap["benchmark_return_ytd"]).notna()
        & num(snap["active_alpha_ytd"]).notna(), 1e-4)
    year = pd.to_numeric(snap["year"], errors="coerce")
    dec = pd.DataFrame({"client_id": snap["client_id"], "year": year + 1, "base": num(snap["aum"])})[snap["month"] == "12"]
    dec = dec.drop_duplicates(["client_id", "year"])  # one base per client-year, so the merge keeps snap's length
    base = pd.DataFrame({"client_id": snap["client_id"], "year": year}).merge(dec, on=["client_id", "year"], how="left")["base"]
    base.index = snap.index
    add("R4b return_ytd = aum / prior-December aum - 1", "fact_portfolio_snapshot (across months)",
        num(snap["return_ytd"]), num(snap["aum"]) / base - 1,
        base.notna() & num(snap["return_ytd"]).notna(), 1e-3)

    # R5 advisor on every fact row = the client's advisor in dim_client
    for fact in ("fact_fees", "fact_portfolio_snapshot", "fact_transactions"):
        f = t[fact]
        mm = f[["client_id", "advisor_id"]].merge(client[["client_id", "advisor_id"]], on="client_id",
                                                  how="left", suffixes=("", "_dim"))
        ev = mm["advisor_id_dim"].notna()
        same = (mm["advisor_id"] == mm["advisor_id_dim"]).astype(float)
        add(f"R5 {fact}.advisor_id = dim_client.advisor_id", f"{fact} x dim_client",
            same, pd.Series(1.0, index=same.index), ev, 0)

    # R6 snapshot account type = client's primary account type
    mm = snap[["client_id", "account_type"]].merge(client[["client_id", "primary_account_type"]],
                                                    on="client_id", how="left")
    same = (mm["account_type"] == mm["primary_account_type"]).astype(float)
    add("R6 snapshot account_type = dim_client.primary_account_type", "fact_portfolio_snapshot x dim_client",
        same, pd.Series(1.0, index=same.index), mm["primary_account_type"].notna(), 0)
    return pd.DataFrame(out)


# ==========================================================================
# 4. IQR outliers on columns with no natural upper bound
# ==========================================================================

IQR_COLUMNS = [
    ("fact_transactions", "amount"),
    ("fact_portfolio_snapshot", "aum"),
    ("fact_portfolio_snapshot", "active_alpha_ytd"),
    ("dim_client", "initial_aum"),
]

IQR_NOTE = ("Flagged does not mean wrong: money columns are right-skewed, so the IQR fence flags the firm's "
            "biggest accounts (every initial_aum outlier and ~99% of AUM outliers are UHNW clients, large by "
            "definition) and 29% of alpha values because returns are fat-tailed; an IQR flag is a prompt to look "
            "(e.g. the many Retail clients with $186k+ trades), and only rules or reconciliations prove a value wrong.")


def iqr_outliers(stage, t):
    rows = []
    for table, col in IQR_COLUMNS:
        v = num(t[table][col]).dropna()
        q1, q3 = v.quantile(0.25), v.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        flagged = (v < lo) | (v > hi)
        extra = {}
        # who is flagged? tier of the client behind each flagged row
        ids = t[table].loc[flagged[flagged].index, "client_id"]
        tier_map = t["dim_client"].drop_duplicates("client_id").set_index("client_id")["client_tier"]
        tiers = ids.map(tier_map).fillna("(orphan)").value_counts()
        extra["flagged_by_tier"] = "; ".join(f"{k} {n}" for k, n in tiers.items())
        if table == "fact_portfolio_snapshot" and "is_return_suspect" in t[table].columns:
            sus = t[table].loc[flagged[flagged].index, "is_return_suspect"] == "1"
            extra["flagged_also_return_suspect"] = int(sus.sum())
        rows.append({"stage": stage, "table": table, "column": col, "values": len(v),
                     "q1": q1, "q3": q3, "iqr": iqr, "lower_fence": lo, "upper_fence": hi,
                     "below_fence": int((v < lo).sum()), "above_fence": int((v > hi).sum()),
                     "pct_flagged": round(100 * flagged.mean(), 3), **extra})
    return pd.DataFrame(rows)


# ==========================================================================
# 5. Scorecard
# ==========================================================================

def scorecard(stage, t, ri, rules):
    rows = []
    for table in TABLES:
        df = t[table]
        types = {c: k for c, k in TYPES[table].items() if c in df.columns}

        # % completeness: non-blank cells among cells that are expected to be present
        expected = present = 0
        for col in df.columns:
            need = PRESENT_WHEN.get((table, col), everywhere)(df).astype(bool)
            filled = ~blank(df[col]) & ~df[col].isin(NO_INFO.get((table, col), set()))
            expected += int(need.sum())
            present += int((need & filled).sum())

        # % key uniqueness: rows whose primary key AND business key are both unique
        unique = ~df[PK[table]].duplicated(keep=False)
        if table in BUSINESS_KEYS:
            unique &= ~df.duplicated(BUSINESS_KEYS[table], keep=False)

        # % type validity: non-blank cells that parse as the expected type
        valid = total = 0
        for col, kind in types.items():
            nb = df[col][~blank(df[col])]
            total += len(nb)
            valid += int(parses(nb, kind).sum())

        r = rules[rules["table"] == table]
        rr = ri[ri["fact_table"] == table]
        rows.append({
            "table": table, "stage": stage, "rows": len(df),
            "pct_completeness": round(100 * present / expected, 3) if expected else 100.0,
            "pct_key_uniqueness": round(100 * unique.mean(), 3),
            "pct_type_validity": round(100 * valid / total, 3) if total else 100.0,
            "pct_rule_pass": round(100 * (1 - r["rows_failed"].sum() / r["rows_evaluated"].sum()), 3)
                             if len(r) and r["rows_evaluated"].sum() else np.nan,
            "pct_referential_match": round(100 * rr["matched_rows"].sum() / rr["evaluated_rows"].sum(), 3)
                                     if len(rr) else np.nan,
            "fk_relationships": len(rr),
        })
    return pd.DataFrame(rows)


# ==========================================================================
# Main
# ==========================================================================

def run_stage(stage, folder):
    t = {name: read_text(folder / f"{name}.csv") for name in TABLES}
    print(f"\n{'=' * 78}\nSTAGE: {stage}  ({folder})\n{'=' * 78}")
    for name, df in t.items():
        print(f"  {name:26} {len(df):>8,} rows x {df.shape[1]} cols")

    ri_rows = []
    print("\n  Referential integrity (exact text join):")
    for fact, fkey, dim, dkey in RELATIONSHIPS:
        res = check_referential_integrity(t[fact], fkey, t[dim], dkey)
        ri_rows.append({"stage": stage, "fact_table": fact, "fact_key": fkey, "dim_table": dim, "dim_key": dkey,
                        **{k: v for k, v in res.items() if k not in ("orphan_rows", "distinct_orphan_keys")},
                        "distinct_orphan_key_count": len(res["distinct_orphan_keys"]),
                        "orphan_key_examples": ", ".join(map(str, res["distinct_orphan_keys"][:5]))})
        print(f"    {fact + '.' + fkey:40} -> {dim + '.' + dkey:28} match {res['match_rate']:8.3%}"
              f"  orphans {res['orphan_row_count']:>7,}  null keys {res['null_key_rate']:7.2%}")
    ri = pd.DataFrame(ri_rows)

    rules = run_rules(stage, t)
    print(f"\n  Rule checks: {len(rules)} rules, {int((rules['rows_failed'] > 0).sum())} with failures")
    for r in rules[rules["rows_failed"] > 0].itertuples():
        print(f"    FAIL {r.table}.{r.column:22} {r.rule:38} {r.rows_failed:>7,} of {r.rows_evaluated:,}")

    rec = reconciliations(stage, t)
    print("\n  Reconciliations (recomputed vs stored):")
    for r in rec.itertuples():
        print(f"    {r.reconciliation:62} pass {r.pct_pass:8.3f}%  failed {r.rows_failed:>6,}")

    out = iqr_outliers(stage, t)
    print("\n  IQR outliers (1.5 x IQR):")
    for r in out.itertuples():
        print(f"    {r.table}.{r.column:20} fences [{r.lower_fence:,.4f}, {r.upper_fence:,.4f}]"
              f"  flagged {r.below_fence + r.above_fence:>6,} ({r.pct_flagged}%)")

    sc = scorecard(stage, t, ri, rules)
    return t, ri, rules, rec, out, sc


def main():
    results = {stage: run_stage(stage, folder) for stage, folder in STAGES.items()}

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    names = ["ri_results", "rule_checks", "reconciliations", "outliers_iqr", "data_quality_scorecard"]
    for i, name in enumerate(names, start=1):
        df = pd.concat([results[s][i] for s in STAGES], ignore_index=True)
        if name == "outliers_iqr":
            df["note"] = IQR_NOTE
        if name == "data_quality_scorecard":
            df = df.sort_values(["table", "stage"], key=lambda c: c.map({"raw": 0, "clean": 1}) if c.name == "stage" else c)
        df.to_csv(REPORT_DIR / f"{name}.csv", index=False)
        print(f"wrote reports/{name}.csv ({len(df)} rows)")

    sc = pd.read_csv(REPORT_DIR / "data_quality_scorecard.csv")
    print("\nDATA QUALITY SCORECARD (raw vs clean)")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(sc.to_string(index=False))
    print(f"\nIQR note: {IQR_NOTE}")

    # sanity, AFTER the reports are written so a failure can be diagnosed from them:
    # the clean stage must be fully joinable, pass every rule and every reconciliation
    _, ri_c, rules_c, rec_c, _, _ = results["clean"]
    assert (ri_c["match_rate"] == 1.0).all(), "clean data has orphan keys"
    assert ri_c["dim_key_unique"].all(), "a dimension key is not unique in clean data"
    assert rules_c["rows_failed"].sum() == 0, "clean data fails a business rule"
    assert (rec_c["rows_failed"] == 0).all(), "clean data fails a reconciliation"
    assert rec_c["rows_unmatched"].fillna(0).sum() == 0, "clean fees with no matching snapshot"


if __name__ == "__main__":
    main()
