"""
HW4 Part A - Audit / profile the Wildcat Capital raw tables.

Two layers:
  1. profile_table(df)  - GENERIC. Works on any table with no configuration:
     blanks, null-like tokens, distinct count, value shapes, inferred type,
     parse-failure share, whitespace, mixed formats, numeric min/max.
  2. Rule checks in four groups (column, single-table, referential integrity,
     cross-table). The rule ENGINE is generic; the rules themselves are data
     (SCHEMA, RELATIONSHIPS, ROW_RULES, CROSS_RULES) describing this warehouse.

Every file is read as text (dtype=str, keep_default_na=False) and converted
on purpose inside each check.

Usage (from the hw04 folder):
    python scripts/01_profile.py                 # all eight tables
    python scripts/01_profile.py some_file.csv   # generic profile of any CSV

Outputs:
    reports/profile_raw.csv     one row per table x column
    reports/dq_summary_raw.csv  one row per check (ERROR / WARN / INFO)
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "reports"

TABLES = [
    "dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]

NULL_TOKENS = {"none", "null", "nan", "na", "n/a", "#n/a", "-", "?"}

# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def read_text(path):
    """Read a CSV with every cell as a string, nothing auto-converted."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def num(s):
    """Strict numeric parse: anything that is not a plain number -> NaN."""
    return pd.to_numeric(s.where(s.str.strip() != ""), errors="coerce")


def is_blank(s):
    return s.str.strip() == ""


def shape_of(s):
    """Reduce a value to its pattern: 'Abc 12.5%' -> 'A 9.9%'."""
    out = s.str.replace(r"[A-Za-z]+", "A", regex=True)
    out = out.str.replace(r"\d+", "9", regex=True)
    return out.where(s != "", "<blank>")


INT_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BOOL_SET = {"true", "false", "0", "1"}


def parses_as(values, kind):
    """Boolean Series: does each non-blank value parse as `kind`?"""
    v = values.str.strip()
    if kind == "int":
        return v.str.match(INT_RE)
    if kind == "float":
        return v.str.match(FLOAT_RE)
    if kind == "date":
        ok = v.str.match(DATE_RE)
        real = pd.to_datetime(v.where(ok), format="%Y-%m-%d", errors="coerce").notna()
        return ok & real
    if kind == "bool":
        return v.str.lower().isin(BOOL_SET)
    return pd.Series(True, index=values.index)


def infer_type(values):
    """Pick the narrowest type that at least 90% of non-blank values fit."""
    v = values[~is_blank(values)]
    if v.empty:
        return "empty"
    if v.str.lower().isin(BOOL_SET).all() and v.nunique() <= 2:
        return "bool"
    for kind in ("int", "float", "date"):
        if parses_as(v, kind).mean() >= 0.90:
            return kind
    return "text"


# --------------------------------------------------------------------------
# Layer 1: generic column profile
# --------------------------------------------------------------------------

def profile_table(df, table_name="table", expected_types=None):
    """Profile every column of ANY dataframe of strings."""
    expected_types = expected_types or {}
    rows = []
    n = len(df)
    for col in df.columns:
        s = df[col].astype(str)
        blank = is_blank(s)
        nonblank = s[~blank]
        inferred = infer_type(s)
        expected = expected_types.get(col, inferred)
        fails = (~parses_as(nonblank, expected)).sum() if expected not in ("text", "empty") else 0
        all_shapes = shape_of(s)
        shapes = all_shapes.value_counts()
        nb_shapes = all_shapes[~blank].value_counts()
        # a leading sign is not a different format ('-9.9' vs '9.9')
        unsigned_shapes = all_shapes[~blank].str.replace(r"^[-+]", "", regex=True).nunique()
        numeric = num(nonblank) if expected in ("int", "float") else pd.Series(dtype=float)
        rows.append({
            "table": table_name,
            "column": col,
            "rows": n,
            "blank_count": int(blank.sum()),
            "blank_pct": round(100 * blank.mean(), 3) if n else 0,
            "null_token_count": int(s.str.strip().str.lower().isin(NULL_TOKENS).sum()),
            "distinct_count": int(s.nunique()),
            "inferred_type": inferred,
            "expected_type": expected,
            "parse_fail_count": int(fails),
            "parse_fail_pct": round(100 * fails / len(nonblank), 3) if len(nonblank) else 0,
            "leading_trailing_ws": int((s != s.str.strip()).sum()),
            "double_internal_space": int(s.str.contains(r"\S\s{2,}\S", regex=True).sum()),
            "shape_count_nonblank": int(len(nb_shapes)),
            "mixed_format": "yes" if unsigned_shapes > 1 and expected in ("int", "float", "date", "bool") else "no",
            "top_shapes": "; ".join(f"{k} ({v})" for k, v in shapes.head(4).items()),
            "pct_strings": int(s.str.contains("%", regex=False).sum()),
            "currency_strings": int(s.str.contains(r"\$", regex=True).sum()),
            "sci_notation": int(s.str.contains(r"\d[eE][-+]?\d", regex=True).sum()),
            "numeric_min": numeric.min() if len(numeric) else "",
            "numeric_max": numeric.max() if len(numeric) else "",
            "top_values": "; ".join(f"{k} ({v})" for k, v in s.value_counts().head(5).items()),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Rules as data
# --------------------------------------------------------------------------

US_STATES = set("""AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ
NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY""".split())

# Per-table column rules. type = expected type; allowed = code list;
# min/max = natural business bounds; pk = primary key.
SCHEMA = {
    "dim_advisor": {
        "pk": "advisor_id",
        "cols": {
            "advisor_id": {"type": "int"},
            "first_name": {"type": "text", "required": True},
            "last_name": {"type": "text", "required": True},
            "region": {"type": "text", "allowed": {"Northeast", "Southeast", "Mid-Atlantic", "West", "Midwest"}},
            "years_experience": {"type": "int", "min": 0, "max": 50},
            "aum_target_mm": {"type": "int", "min": 1, "max": 10000},
            # "None" here is a real answer (no certification), not a missing value
            "certifications": {"type": "text", "tokens": {"CFA", "CFP", "CIMA", "None"}},
        },
    },
    "dim_benchmark": {
        "pk": "benchmark_id",
        "cols": {
            "benchmark_id": {"type": "int"},
            "name": {"type": "text", "required": True},
            "asset_class": {"type": "text", "required": True},
            "ticker_proxy": {"type": "text", "required": True},
        },
    },
    "dim_client": {
        "pk": "client_id",
        "cols": {
            "client_id": {"type": "int"},
            "first_name": {"type": "text", "required": True},
            "last_name": {"type": "text", "required": True},
            "age": {"type": "int", "min": 18, "max": 110},
            "city": {"type": "text", "required": True},
            "state": {"type": "text", "allowed": US_STATES},
            "zip_code": {"type": "text", "pattern": r"^\d{5}$"},
            "risk_profile": {"type": "text", "required": True, "allowed": {
                "Conservative", "Moderately Conservative", "Balanced", "Moderately Aggressive", "Aggressive"}},
            "client_tier": {"type": "text", "allowed": {"Retail", "HNW", "UHNW"}},
            "primary_account_type": {"type": "text", "allowed": {"Taxable", "IRA", "Roth IRA", "Trust", "529"}},
            "initial_aum": {"type": "float", "min": 0.01},
            "client_since": {"type": "date", "min": "1950-01-01", "max": "2024-12-31"},
            "advisor_id": {"required": True, "type": "int"},
            "is_active": {"type": "bool", "allowed": {"True", "False"}},
        },
    },
    "dim_date": {
        "pk": "date_id",
        "unique": ["date"],
        "cols": {
            "date_id": {"type": "int"},
            "date": {"type": "date", "min": "2020-01-01", "max": "2024-12-31"},
            "year": {"type": "int", "min": 2020, "max": 2024},
            "quarter": {"type": "int", "min": 1, "max": 4},
            "month": {"type": "int", "min": 1, "max": 12},
            "week_of_year": {"type": "int", "min": 1, "max": 53},
            "is_month_end": {"type": "int", "allowed": {"0", "1"}},
            "is_quarter_end": {"type": "int", "allowed": {"0", "1"}},
            "is_year_end": {"type": "int", "allowed": {"0", "1"}},
            "is_trading_day": {"type": "int", "allowed": {"0", "1"}},
        },
    },
    "dim_security": {
        "pk": "security_id",
        "unique": ["ticker"],
        "cols": {
            "security_id": {"type": "int"},
            "ticker": {"type": "text", "pattern": r"^[A-Z]{1,5}$"},
            "name": {"type": "text", "required": True},
            "asset_class": {"type": "text", "allowed": {"Equity", "Fixed Income", "Alternative", "Cash Equivalent"}},
            "benchmark_id": {"required": True, "type": "int"},
            "is_etf": {"type": "bool", "allowed": {"True", "False"}},
            "expense_ratio_bps": {"type": "float", "min": 0, "max": 300},
        },
    },
    "fact_fees": {
        "pk": "fee_id",
        "cols": {
            "fee_id": {"type": "int"},
            "client_id": {"required": True, "type": "int"},
            "advisor_id": {"required": True, "type": "int"},
            "fee_date": {"required": True, "type": "date", "min": "2020-01-01", "max": "2024-12-31"},
            "fee_type": {"type": "text", "allowed": {"Management", "Advisory", "Custodial", "Performance"}},
            "aum_basis": {"type": "float", "min": 0.01},
            "bps_charged": {"type": "float", "min": 0, "max": 300},
            "amount": {"type": "float", "min": 0.01},
        },
    },
    "fact_portfolio_snapshot": {
        "pk": "snapshot_id",
        "cols": {
            "snapshot_id": {"type": "int"},
            "client_id": {"required": True, "type": "int"},
            "advisor_id": {"required": True, "type": "int"},
            "benchmark_id": {"required": True, "type": "int"},
            "snapshot_date": {"required": True, "type": "date", "min": "2020-01-01", "max": "2024-12-31"},
            "year": {"type": "int", "min": 2020, "max": 2024},
            "month": {"type": "int", "min": 1, "max": 12},
            "aum": {"type": "float", "min": 0.01},
            # a portfolio cannot lose more than 100%; no natural upper bound
            "return_ytd": {"type": "float", "min": -1},
            "benchmark_return_ytd": {"type": "float", "min": -1, "max": 1},
            "active_alpha_ytd": {"type": "float"},
            "cash_pct": {"type": "float", "min": 0, "max": 1},
            "account_type": {"type": "text", "allowed": {"Taxable", "IRA", "Roth IRA", "Trust", "529"}},
        },
    },
    "fact_transactions": {
        "pk": "txn_id",
        "cols": {
            "txn_id": {"type": "int"},
            "client_id": {"required": True, "type": "int"},
            "advisor_id": {"required": True, "type": "int"},
            # blank on cash rows is legitimate structure (checked by a row rule)
            "security_id": {"type": "int"},
            "txn_date": {"required": True, "type": "date", "min": "2020-01-01", "max": "2024-12-31"},
            "txn_type": {"type": "text", "allowed": {"Buy", "Sell", "Dividend", "Deposit", "Withdrawal", "Advisory Fee"}},
            # sign rule: shares are a quantity; direction comes from txn_type
            "shares": {"type": "float", "min": 0.0001},
            "price": {"type": "float", "min": 0.01},
            "amount": {"type": "float", "min": 0.01},
        },
    },
}

# (fact table, fact column, dim table, dim column)  - 10 ID-based + 3 date
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


def tri(fail, evaluable):
    """Rule result: True = fails, False = passes, NA = could not evaluate."""
    out = pd.Series(fail, dtype="boolean")
    out[~evaluable.fillna(False).astype(bool)] = pd.NA
    return out


def parse_return(s):
    """Lenient parse used ONLY to test reconciliation ('5.2%' -> 0.052)."""
    pct = s.str.endswith("%")
    v = pd.to_numeric(s.str.rstrip("%"), errors="coerce")
    return v.where(~pct, v / 100)


def _return_is_aum_change(t):
    """Test whether return_ytd is simply AUM growth since the prior December.
    Fails = row does NOT follow that definition. A full pass means the stored
    'return' is money-weighted AUM change (deposits/withdrawals included),
    not investment performance."""
    aum = num(t["aum"])
    year = pd.to_numeric(t["year"], errors="coerce")
    dec = pd.DataFrame({"client_id": t["client_id"], "year": year + 1, "base": aum})[t["month"] == "12"]
    base = pd.DataFrame({"client_id": t["client_id"], "year": year}).merge(
        dec, on=["client_id", "year"], how="left")["base"]
    base.index = t.index
    implied = aum / base - 1
    return tri((implied - parse_return(t["return_ytd"])).abs() > 1e-3,
               base.notna() & aum.notna() & parse_return(t["return_ytd"]).notna())


# Single-table rules: values that contradict other columns of the same row.
def _date_rules(t):
    d = pd.to_datetime(t["date"], errors="coerce")
    ok = d.notna()
    iso = d.dt.isocalendar()
    return {
        "year matches date": tri(t["year"] != d.dt.year.astype("Int64").astype(str), ok),
        "quarter matches date": tri(t["quarter"] != d.dt.quarter.astype("Int64").astype(str), ok),
        "month matches date": tri(t["month"] != d.dt.month.astype("Int64").astype(str), ok),
        "month_name matches date": tri(t["month_name"] != d.dt.month_name(), ok),
        "day_of_week matches date": tri(t["day_of_week"] != d.dt.day_name(), ok),
        "week_of_year = ISO week": tri(t["week_of_year"] != iso["week"].astype(str), ok),
        "is_month_end matches date": tri(t["is_month_end"] != d.dt.is_month_end.astype(int).astype(str), ok),
        "is_quarter_end matches date": tri(t["is_quarter_end"] != d.dt.is_quarter_end.astype(int).astype(str), ok),
        "is_year_end matches date": tri(t["is_year_end"] != d.dt.is_year_end.astype(int).astype(str), ok),
        "is_trading_day = weekday": tri(t["is_trading_day"] != (d.dt.weekday < 5).astype(int).astype(str), ok),
    }


ROW_RULES = {
    "dim_date": [("ERROR", _date_rules)],
    "dim_security": [
        ("INFO", lambda t: {
            "ETF <=> sector blank (structure check)":
                tri((t["is_etf"] == "True") != is_blank(t["sector"]), pd.Series(True, index=t.index)),
            "ETF <=> expense ratio present (structure check)":
                tri((t["is_etf"] == "True") == is_blank(t["expense_ratio_bps"]), pd.Series(True, index=t.index)),
        }),
    ],
    "fact_fees": [
        ("WARN", lambda t: {
            "aum_basis exactly 1,000.00 (looks like a floor / placeholder value)":
                tri(num(t["aum_basis"]) == 1000, num(t["aum_basis"]).notna()),
        }),
        ("ERROR", lambda t: {
            "amount = aum_basis x bps / 10000 / 12 (+/- 0.01)":
                tri((num(t["amount"]) - num(t["aum_basis"]) * num(t["bps_charged"]) / 120000).abs() > 0.011,
                    num(t["amount"]).notna() & num(t["aum_basis"]).notna() & num(t["bps_charged"]).notna()),
            "fee_date is first of month":
                tri(t["fee_date"].str[8:10] != "01", parses_as(t["fee_date"], "date")),
        }),
    ],
    "fact_portfolio_snapshot": [
        ("ERROR", lambda t: {
            "year/month match snapshot_date":
                tri((t["snapshot_date"].str[:4] != t["year"]) |
                    (pd.to_numeric(t["snapshot_date"].str[5:7], errors="coerce") != num(t["month"])),
                    parses_as(t["snapshot_date"], "date") & parses_as(t["year"], "int") & parses_as(t["month"], "int")),
            "return_ytd = benchmark_return_ytd + active_alpha_ytd (+/- 0.0001), strict parse":
                tri((num(t["return_ytd"]) - num(t["benchmark_return_ytd"]) - num(t["active_alpha_ytd"])).abs() > 1e-4,
                    num(t["return_ytd"]).notna() & num(t["benchmark_return_ytd"]).notna() & num(t["active_alpha_ytd"]).notna()),
        }),
        ("INFO", lambda t: {
            "'%' return_ytd values reconcile after /100 (+/- 0.0001)":
                tri((parse_return(t["return_ytd"]) - num(t["benchmark_return_ytd"]) - num(t["active_alpha_ytd"])).abs() > 1e-4,
                    t["return_ytd"].str.endswith("%")),
        }),
        ("WARN", lambda t: {
            "|return_ytd| > 100% (implausible YTD for a managed account)":
                tri(parse_return(t["return_ytd"]).abs() > 1, parse_return(t["return_ytd"]).notna()),
            "aum exactly 1,000.00 (looks like a floor / placeholder value)":
                tri(num(t["aum"]) == 1000, num(t["aum"]).notna()),
        }),
        ("INFO", lambda t: {
            "return_ytd = aum / prior-December aum - 1 (+/- 0.001): return includes cash flows":
                _return_is_aum_change(t),
        }),
    ],
    "fact_transactions": [
        ("ERROR", lambda t: {
            "security/shares/price present <=> security txn type":
                tri(t["txn_type"].isin(CASH_TYPES) != (is_blank(t["security_id"]) & is_blank(t["shares"]) & is_blank(t["price"])),
                    t["txn_type"] != ""),
            "amount = |shares| x price (+/- 0.01)":
                tri((num(t["shares"]).abs() * num(t["price"]) - num(t["amount"])).abs() > 0.011,
                    num(t["shares"]).notna() & num(t["price"]).notna() & num(t["amount"]).notna()),
        }),
        ("INFO", lambda t: {
            "amount = shares x price only if sign ignored (sign error on shares)":
                tri(num(t["shares"]) < 0, num(t["shares"]).notna()),
        }),
    ],
}


def _client(tables):
    return tables["dim_client"].drop_duplicates("client_id")


def _fact_vs_client_advisor(fact):
    def rule(tables):
        f = tables[fact]
        m = f.merge(_client(tables)[["client_id", "advisor_id"]], on="client_id", how="left", suffixes=("", "_dim"))
        m.index = f.index
        return tri(m["advisor_id"] != m["advisor_id_dim"], m["advisor_id_dim"].notna())
    return rule


def _fact_before_client_since(fact, date_col):
    def rule(tables):
        f = tables[fact]
        m = f.merge(_client(tables)[["client_id", "client_since"]], on="client_id", how="left")
        m.index = f.index
        # snapshots/fees are monthly: compare against the first of the client_since month
        start = m["client_since"].str[:7] + "-01" if date_col != "txn_date" else m["client_since"]
        # ISO text compares correctly only when both sides are valid dates ('' or NaN is not evaluable)
        ev = parses_as(m["client_since"].fillna(""), "date") & parses_as(m[date_col], "date")
        return tri(m[date_col] < start, ev)
    return rule


def _last_snapshot(tables):
    s = tables["fact_portfolio_snapshot"]
    last = s.groupby("client_id")["snapshot_date"].max()
    month_end = (pd.to_datetime(last) + pd.offsets.MonthEnd(0)).dt.strftime("%Y-%m-%d")
    return month_end.rename("last_snapshot_month_end")


def _after_departure(fact, date_col):
    def rule(tables):
        f = tables[fact]
        c = _client(tables)[["client_id", "is_active"]].merge(
            _last_snapshot(tables), left_on="client_id", right_index=True, how="left")
        m = f.merge(c, on="client_id", how="left")
        m.index = f.index
        ev = (m["is_active"] == "False") & m["last_snapshot_month_end"].notna()
        return tri(m[date_col] > m["last_snapshot_month_end"], ev)
    return rule


def _fee_vs_snapshot_aum(tables):
    f = tables["fact_fees"]
    s = tables["fact_portfolio_snapshot"][["client_id", "snapshot_date", "aum"]].drop_duplicates(["client_id", "snapshot_date"])
    m = f.merge(s, left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"], how="left")
    m.index = f.index
    return tri((num(m["aum_basis"]) - num(m["aum"])).abs() > 0.01, m["aum"].notna())


def _fee_without_snapshot(tables):
    f = tables["fact_fees"]
    keys = set(zip(tables["fact_portfolio_snapshot"]["client_id"], tables["fact_portfolio_snapshot"]["snapshot_date"]))
    has = pd.Series([k in keys for k in zip(f["client_id"], f["fee_date"])], index=f.index)
    return tri(~has, pd.Series(True, index=f.index))


def _snapshot_account_type(tables):
    s = tables["fact_portfolio_snapshot"]
    m = s.merge(_client(tables)[["client_id", "primary_account_type"]], on="client_id", how="left")
    m.index = s.index
    return tri(m["account_type"] != m["primary_account_type"], m["primary_account_type"].notna())


def _benchmark_vs_risk(tables):
    """Each risk profile should map to one benchmark; flag rows off the dominant mapping."""
    s = tables["fact_portfolio_snapshot"]
    m = s.merge(_client(tables)[["client_id", "risk_profile"]], on="client_id", how="left")
    m.index = s.index
    # a blank profile is not a group: it would only be compared with itself
    known = m["risk_profile"].notna() & (m["risk_profile"] != "")
    dominant = m[known].groupby("risk_profile")["benchmark_id"].agg(lambda x: x.value_counts().idxmax())
    return tri(m["benchmark_id"] != m["risk_profile"].map(dominant), known)


def _blank_risk_inferable(tables):
    """Blank risk_profile: fails = the snapshot's benchmark maps to more than one known profile,
    so the blank cannot be inferred from it."""
    s = tables["fact_portfolio_snapshot"]
    m = s.merge(_client(tables)[["client_id", "risk_profile"]], on="client_id", how="left")
    m.index = s.index
    known = m["risk_profile"].notna() & (m["risk_profile"] != "")
    profiles_per_benchmark = m[known].groupby("benchmark_id")["risk_profile"].nunique()
    return tri(m["benchmark_id"].map(profiles_per_benchmark) != 1, m["risk_profile"] == "")


def _trade_on_non_trading_day(tables):
    t = tables["fact_transactions"]
    d = tables["dim_date"]
    trading = set(d.loc[d["is_trading_day"] == "1", "date"])
    is_trade = t["txn_type"].isin({"Buy", "Sell"})
    return tri(~t["txn_date"].isin(trading), is_trade & t["txn_date"].isin(set(d["date"])))


def _security_benchmark_vs_class(tables):
    sec = tables["dim_security"]
    dominant = sec.groupby("benchmark_id")["asset_class"].agg(lambda x: x.value_counts().idxmax())
    return tri(sec["asset_class"] != sec["benchmark_id"].map(dominant), sec["benchmark_id"] != "")


# Cross-table business rules: (severity, table checked, column, description, fn)
CROSS_RULES = [
    ("ERROR", "fact_fees", "advisor_id", "fee advisor = client's advisor in dim_client", _fact_vs_client_advisor("fact_fees")),
    ("ERROR", "fact_portfolio_snapshot", "advisor_id", "snapshot advisor = client's advisor in dim_client", _fact_vs_client_advisor("fact_portfolio_snapshot")),
    ("ERROR", "fact_transactions", "advisor_id", "transaction advisor = client's advisor in dim_client", _fact_vs_client_advisor("fact_transactions")),
    ("ERROR", "fact_fees", "aum_basis", "fee aum_basis = snapshot aum for same client-month", _fee_vs_snapshot_aum),
    ("WARN", "fact_fees", "fee_date", "fee has a matching client-month snapshot", _fee_without_snapshot),
    ("WARN", "fact_portfolio_snapshot", "account_type", "snapshot account_type = client primary_account_type", _snapshot_account_type),
    ("WARN", "fact_portfolio_snapshot", "benchmark_id", "benchmark follows client risk profile (dominant mapping)", _benchmark_vs_risk),
    ("INFO", "fact_portfolio_snapshot", "benchmark_id", "blank risk_profile: benchmark maps to exactly one known profile (fill candidate)", _blank_risk_inferable),
    ("WARN", "fact_fees", "fee_date", "fee not before client_since month", _fact_before_client_since("fact_fees", "fee_date")),
    ("WARN", "fact_portfolio_snapshot", "snapshot_date", "snapshot not before client_since month", _fact_before_client_since("fact_portfolio_snapshot", "snapshot_date")),
    ("WARN", "fact_transactions", "txn_date", "transaction not before client_since", _fact_before_client_since("fact_transactions", "txn_date")),
    ("WARN", "fact_transactions", "txn_date", "inactive client: transaction after last snapshot month (post-departure)", _after_departure("fact_transactions", "txn_date")),
    ("WARN", "fact_fees", "fee_date", "inactive client: fee after last snapshot month (post-departure)", _after_departure("fact_fees", "fee_date")),
    ("WARN", "fact_transactions", "txn_date", "Buy/Sell on a non-trading day per dim_date", _trade_on_non_trading_day),
    ("WARN", "dim_security", "benchmark_id", "security benchmark consistent with asset_class", _security_benchmark_vs_class),
]


# --------------------------------------------------------------------------
# Rule engine
# --------------------------------------------------------------------------

FINDINGS = []


def add_finding(group, severity, table, column, check, failed, evaluated, examples="", key_examples=""):
    FINDINGS.append({
        "group": group,
        # INFO checks are worth knowing whether they pass or fail
        "severity": severity if (failed or severity == "INFO") else "PASS",
        "rule_severity": severity,
        "table": table,
        "column": column,
        "check": check,
        "rows_evaluated": int(evaluated),
        "rows_failed": int(failed),
        "pct_failed": round(100 * failed / evaluated, 3) if evaluated else 0,
        "examples": examples,
        "example_keys": key_examples,
    })


def examples_of(values, k=5):
    vc = values.value_counts().head(k)
    return "; ".join(f"{v!r} ({c})" for v, c in vc.items())


def record_tri(group, severity, table, column, check, result, df, pk):
    fail = result.fillna(False).astype(bool)
    add_finding(group, severity, table, column, check, fail.sum(), result.notna().sum(),
                key_examples=", ".join(df.loc[fail, pk].head(5)) if pk else "")


def column_checks(name, df, spec):
    pk = spec["pk"]
    n = len(df)
    for col, rule in spec["cols"].items():
        if col not in df.columns:
            add_finding("1 column", "ERROR", name, col, "column exists", 1, 1)
            continue
        s = df[col]
        blank = is_blank(s)
        nb = s[~blank]
        kind = rule.get("type", "text")
        if kind != "text":
            bad = ~parses_as(nb, kind)
            sev = "ERROR"
            add_finding("1 column", sev, name, col, f"type: parses as {kind}", bad.sum(), len(nb), examples_of(nb[bad]))
            if kind == "int":
                floaty = nb.str.match(r"^-?\d+\.0+$")
                add_finding("1 column", "ERROR", name, col, "integer stored with decimal (e.g. '45.0' breaks text joins)",
                            floaty.sum(), len(nb), examples_of(nb[floaty]))
        if rule.get("required") or col == pk:
            add_finding("1 column", "WARN" if col != pk else "ERROR", name, col, "completeness: not blank",
                        blank.sum(), n, key_examples=", ".join(df.loc[blank, pk].head(5)))
        if "allowed" in rule:
            bad = ~nb.isin(rule["allowed"])
            add_finding("1 column", "ERROR", name, col, "allowed values", bad.sum(), len(nb), examples_of(nb[bad]))
        if "tokens" in rule:
            toks = nb.str.split(",").apply(lambda xs: all(x.strip() in rule["tokens"] for x in xs))
            add_finding("1 column", "ERROR", name, col, "allowed tokens in list", (~toks).sum(), len(nb), examples_of(nb[~toks]))
        if "pattern" in rule:
            bad = ~nb.str.match(rule["pattern"])
            add_finding("1 column", "ERROR", name, col, f"pattern {rule['pattern']}", bad.sum(), len(nb), examples_of(nb[bad]))
        if "min" in rule or "max" in rule:
            if kind == "date":
                v = pd.to_datetime(nb, format="%Y-%m-%d", errors="coerce")
                lo, hi = pd.Timestamp(rule.get("min", "1900-01-01")), pd.Timestamp(rule.get("max", "2100-12-31"))
            else:
                v = num(nb)
                lo, hi = rule.get("min", -np.inf), rule.get("max", np.inf)
            bad = v.notna() & ((v < lo) | (v > hi))
            add_finding("1 column", "ERROR", name, col, f"range [{rule.get('min', '-inf')}, {rule.get('max', 'inf')}]",
                        bad.sum(), v.notna().sum(), examples_of(nb[bad]))
        ws = s != s.str.strip()
        if ws.any():
            add_finding("1 column", "WARN", name, col, "leading/trailing whitespace", ws.sum(), n, examples_of(s[ws]))
    # key uniqueness
    for key in [pk] + spec.get("unique", []):
        dup = df[key].duplicated(keep=False) & ~is_blank(df[key])
        add_finding("1 column", "ERROR", name, key, "key uniqueness", dup.sum(), n, examples_of(df.loc[dup, key]))


def single_table_checks(name, df, spec):
    pk = spec["pk"]
    others = [c for c in df.columns if c != pk]
    # exact duplicate rows ignoring the surrogate key
    dup = df.duplicated(others, keep="first")
    add_finding("2 single-table", "ERROR", name, "(all but pk)", "exact duplicate rows ignoring primary key",
                dup.sum(), len(df), key_examples=", ".join(df.loc[dup, pk].head(5)))
    # near-duplicates: identical on every column except the PK and ONE other column
    if len(others) >= 3:
        hits = {}
        exact_dup = df.duplicated(others, keep=False)
        for drop in others:
            cols = [c for c in others if c != drop]
            m = df.duplicated(cols, keep=False) & ~exact_dup
            if m.any():
                hits[drop] = m
        for drop, m in hits.items():
            add_finding("2 single-table", "WARN", name, drop,
                        f"near-duplicate: rows identical except pk and '{drop}'",
                        m.sum(), len(df), examples_of(df.loc[m, drop]), ", ".join(df.loc[m, pk].head(6)))
        if not hits:
            add_finding("2 single-table", "WARN", name, "(all but pk)", "near-duplicate (all-but-one column)", 0, len(df))
    for severity, fn in ROW_RULES.get(name, []):
        for check, result in fn(df).items():
            record_tri("2 single-table", severity, name, "(row rule)", check, result, df, pk)


def ri_checks(tables):
    for fact, fcol, dim, dcol in RELATIONSHIPS:
        f, d = tables[fact], tables[dim]
        key = f[fcol]
        blank = is_blank(key)
        nonblank = key[~blank]
        exact = nonblank.isin(set(d[dcol]))
        # same test after normalising numeric format ('45.0' -> '45'), to separate
        # format breaks from true orphans
        # non-integer numbers ('45.5') become NA instead of crashing the Int64 cast
        v = num(nonblank)
        norm = v.where(v == v.round()).astype("Int64").astype(str)
        norm_ok = norm.isin(set(d[dcol])) if fcol.endswith("_id") else exact
        true_orphans = ~norm_ok
        fmt_only = ~exact & norm_ok
        pk = SCHEMA[fact]["pk"]
        if blank.any():
            # blank keys cannot join; whether that is legitimate is decided by a row rule
            add_finding("3 referential", "INFO", fact, fcol, f"FK -> {dim}.{dcol}: null-key rate (blank keys)",
                        blank.sum(), len(key), key_examples=", ".join(f.loc[blank, pk].head(5)))
        add_finding("3 referential", "ERROR", fact, fcol, f"FK -> {dim}.{dcol}: exact text match",
                    (~exact).sum(), len(nonblank),
                    examples_of(nonblank[~exact]),
                    ", ".join(f.loc[nonblank[~exact].index, pk].head(5)))
        if fmt_only.any():
            add_finding("3 referential", "INFO", fact, fcol, f"FK -> {dim}.{dcol}: misses fixed by numeric normalisation",
                        fmt_only.sum(), len(nonblank), examples_of(nonblank[fmt_only]))
        add_finding("3 referential", "ERROR", fact, fcol, f"FK -> {dim}.{dcol}: true orphans after normalisation",
                    true_orphans.sum(), len(nonblank), examples_of(nonblank[true_orphans]),
                    ", ".join(f.loc[nonblank[true_orphans].index, pk].head(5)))


def cross_table_checks(tables):
    for severity, table, column, check, fn in CROSS_RULES:
        result = fn(tables)
        record_tri("4 cross-table", severity, table, column, check, result, tables[table], SCHEMA[table]["pk"])


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def run_all():
    tables = {}
    for name in TABLES:
        path = RAW_DIR / f"{name}.csv"
        if not path.exists():
            sys.exit(f"Missing raw file: {path}")
        tables[name] = read_text(path)
        print(f"loaded {name:26} {tables[name].shape[0]:>8,} rows x {tables[name].shape[1]} cols")

    profiles = []
    for name, df in tables.items():
        types = {c: r["type"] for c, r in SCHEMA[name]["cols"].items()}
        profiles.append(profile_table(df, name, types))
        column_checks(name, df, SCHEMA[name])
        single_table_checks(name, df, SCHEMA[name])
    ri_checks(tables)
    cross_table_checks(tables)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    profile = pd.concat(profiles, ignore_index=True)
    profile.to_csv(REPORT_DIR / "profile_raw.csv", index=False)

    summary = pd.DataFrame(FINDINGS)
    order = {"ERROR": 0, "WARN": 1, "INFO": 2, "PASS": 3}
    summary = summary.sort_values(["severity", "group", "table"], key=lambda c: c.map(order) if c.name == "severity" else c)
    summary.insert(0, "check_id", [f"A{i:03d}" for i in range(1, len(summary) + 1)])
    summary.to_csv(REPORT_DIR / "dq_summary_raw.csv", index=False)

    print(f"\nwrote {REPORT_DIR / 'profile_raw.csv'} ({len(profile)} column profiles)")
    print(f"wrote {REPORT_DIR / 'dq_summary_raw.csv'} ({len(summary)} checks)")
    print("\nchecks by severity:", summary["severity"].value_counts().to_dict())
    print("\nFINDINGS (ERROR / WARN / INFO):")
    with pd.option_context("display.width", 200, "display.max_colwidth", 70):
        flagged = summary[summary["severity"] != "PASS"]
        print(flagged[["check_id", "severity", "group", "table", "column", "check", "rows_failed"]].to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # generic mode: profile any CSV with no configuration
        p = Path(sys.argv[1])
        out = profile_table(read_text(p), p.stem)
        with pd.option_context("display.width", 200, "display.max_columns", 30):
            print(out.drop(columns=["top_values"]).to_string(index=False))
    else:
        run_all()
