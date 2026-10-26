"""
HW4 Part C - Clean the Wildcat Capital tables.

Implements decision_log.md, one decision at a time, in the order defended
in Part 3 of the log:

    D06 quarantine duplicate clients        D07 quarantine orphan transactions
    D01 security_id '45.0' -> '45'          D05 abs() on negative Buy shares
    D02 '%' returns -> decimals             D03 scientific notation -> plain decimal
    D04 state names -> USPS codes           D08 blank risk_profile -> 'Unknown'
    D09/D10/D11 flag columns                final reconciliation asserts

Rules this script follows:
  * Raw files in data/raw/ are only read, never written.
  * Every cell stays TEXT. Only the cells a decision targets are rewritten,
    using exact Decimal arithmetic, so untouched values are byte-identical.
  * After every step: print rows affected + a before/after check, then
    assert the after-state. A failed assert stops the script.
  * No row is deleted silently: removed rows go to data/audit/quarantine_*.csv
    and raw rows = clean rows + quarantined rows is asserted per table.

Usage (from the hw04 folder):
    python scripts/02_clean.py

Outputs:
    data/clean/<same 8 file names>.csv, data/clean/README_clean.md
    data/audit/cleaning_log.csv, data/audit/value_changes.csv,
    data/audit/quarantine_dim_client_duplicates.csv,
    data/audit/quarantine_fact_transactions_orphans.csv
"""

from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "clean"
AUDIT_DIR = ROOT / "data" / "audit"

TABLES = [
    "dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]
PK = {
    "dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
    "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
    "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id",
}
CASH_TYPES = {"Deposit", "Withdrawal", "Advisory Fee"}
STATE_MAP = {
    "Pennsylvania": "PA", "Florida": "FL", "New York": "NY", "New Jersey": "NJ",
    "California": "CA", "Illinois": "IL", "Texas": "TX",
}
US_STATES = set("""AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ
NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY""".split())

# Relationships (same 13 as 01_profile.py). Used for the final RI assert.
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

# Rows each step must change, from decision_log.md. These are clean-table counts:
# D01 / D05 are lower than the raw audit (197,175 / 836) because D07 removes 131 / 1 first.
EXPECTED = {
    "D06": 25, "D07": 200, "D01": 197_044, "D05": 835, "D02": 300,
    "D03 return_ytd": 135, "D03 active_alpha_ytd": 756, "D04": 77, "D08": 75,
    "D09": 2_410, "D10": 977, "D11 snapshot": 420, "D11 fees": 386,
}
ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"

CLEANING_LOG = []   # table, issue, action, rows_affected, note
VALUE_CHANGES = []  # DataFrames: table, key_column, key, column, old_value, new_value
QUARANTINE = {}     # table -> rows quarantined


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def read_text(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def dec(s):
    """Exact decimal parse of a text value; None if it does not parse."""
    try:
        return Decimal(s)
    except (InvalidOperation, TypeError, ValueError):
        return None


def num(s):
    return pd.to_numeric(s.where(s.str.strip() != ""), errors="coerce")


def plain(d):
    """Decimal -> plain decimal text, never scientific ('9.9E-5' -> '0.000099')."""
    text = format(d, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def header(step_id, title):
    print(f"\n{'=' * 78}\n{step_id}: {title}\n{'-' * 78}")


def check_count(step, actual):
    """Assert a step changed exactly the number of rows the decision log predicts."""
    assert int(actual) == EXPECTED[step], f"{step}: expected {EXPECTED[step]:,} rows, got {int(actual):,}"


def log_step(table, issue, action, rows, note):
    CLEANING_LOG.append({"table": table, "issue": issue, "action": action,
                         "rows_affected": int(rows), "note": note})
    print(f"  -> logged: {table} | {action} | rows affected = {rows:,}")


def record_changes(table, df, column, mask, old_values):
    """Store one row per changed cell in value_changes.csv."""
    if not mask.any():
        return
    VALUE_CHANGES.append(pd.DataFrame({
        "table": table,
        "key_column": PK[table],
        "key": df.loc[mask, PK[table]].values,
        "column": column,
        "old_value": old_values[mask].values,
        "new_value": df.loc[mask, column].values,
    }))


def quarantine(name, table, df, mask, extra_cols=None):
    """Move rows out of `df` into data/audit/quarantine_<name>.csv; return the kept rows."""
    q = df[mask].copy()
    if extra_cols is not None:
        q = q.join(extra_cols)
    q.insert(0, "quarantine_reason", name)
    q.insert(0, "source_table", table)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    q.to_csv(AUDIT_DIR / f"quarantine_{name}.csv", index=False, lineterminator="\n")
    QUARANTINE[table] = QUARANTINE.get(table, 0) + len(q)
    return df[~mask].copy()


def show(label, before, after):
    print(f"  {label:58} before = {before!s:>10}   after = {after!s:>10}")


# --------------------------------------------------------------------------
# Load
# --------------------------------------------------------------------------

def load():
    t = {}
    for name in TABLES:
        t[name] = read_text(RAW_DIR / f"{name}.csv")
        print(f"loaded raw {name:26} {len(t[name]):>8,} rows x {t[name].shape[1]} cols")
    return t


# --------------------------------------------------------------------------
# Steps (order = decision_log.md Part 3)
# --------------------------------------------------------------------------

def d06_duplicate_clients(t):
    header("D06", "quarantine duplicate clients (mistyped last name)")
    cl = t["dim_client"]
    others = [c for c in cl.columns if c not in ("client_id", "last_name")]
    n_before = len(cl)

    # a copy = identical to another client on every column except id and last_name
    cl = cl.assign(_cid=cl["client_id"].astype(int))
    grp = cl.groupby(others, sort=False)["_cid"]
    cl = cl.assign(_n=grp.transform("size"), _first_id=grp.transform("min").astype(str))
    cl = cl.drop(columns="_cid")
    is_pair = cl["_n"] == 2
    is_copy = is_pair & (cl["client_id"] != cl["_first_id"])

    # trace: who is the original, and is the name a one-letter edit of it?
    orig = cl.loc[is_pair & ~is_copy, ["client_id", "last_name"]].set_index("client_id")["last_name"]
    trace = pd.DataFrame({
        "original_client_id": cl.loc[is_copy, "_first_id"],
        "original_last_name": cl.loc[is_copy, "_first_id"].map(orig),
    })
    copy_names = cl.loc[is_copy, "last_name"]
    one_letter = [
        abs(len(a) - len(b)) == 1 and (a.startswith(b) or b.startswith(a))
        for a, b in zip(copy_names, trace["original_last_name"])
    ]
    assert (cl["_n"] <= 2).all(), "a group of more than two near-identical clients needs review"
    assert all(one_letter), "a duplicate's last name is not a one-letter edit of the original"
    assert (cl.loc[is_copy, "client_id"].astype(int) > cl.loc[is_copy, "_first_id"].astype(int)).all()

    # the copies must have no fact history (otherwise quarantine would orphan facts)
    copy_ids = set(cl.loc[is_copy, "client_id"])
    fact_refs = sum(t[f]["client_id"].isin(copy_ids).sum()
                    for f in ("fact_fees", "fact_portfolio_snapshot", "fact_transactions"))
    show("fact rows referencing the copies", fact_refs, "n/a")
    assert fact_refs == 0, "duplicate clients are referenced by facts; decision D06 does not apply"
    check_count("D06", is_copy.sum())
    assert sorted(copy_ids, key=int) == [str(i) for i in range(2501, 2526)], "copy IDs are not 2501-2525"

    cl = cl.drop(columns=["_n", "_first_id"])
    kept = quarantine("dim_client_duplicates", "dim_client", cl, is_copy, trace)
    show("dim_client rows", n_before, len(kept))
    show("near-duplicate pairs remaining", int(is_copy.sum()),
         int(kept.duplicated(others, keep=False).sum()))
    assert len(kept) + is_copy.sum() == n_before
    assert not kept.duplicated(others, keep=False).any()
    assert kept["client_id"].is_unique
    t["dim_client"] = kept
    log_step("dim_client", "D06 duplicate clients (IDs 2501-2525, one-letter last-name edits)",
             "quarantine", is_copy.sum(),
             f"copy IDs {min(copy_ids, key=int)}-{max(copy_ids, key=int)}; 0 fact rows reference them")


def d07_orphan_transactions(t):
    header("D07", "quarantine orphan transactions (copies with unknown client_id)")
    tx = t["fact_transactions"]
    n_before = len(tx)
    orphan = ~tx["client_id"].isin(set(t["dim_client"]["client_id"]))

    # reconcile: each orphan must duplicate a real transaction on every other column
    match_cols = [c for c in tx.columns if c not in ("txn_id", "client_id")]
    real = tx[~orphan][match_cols + ["txn_id", "client_id"]].rename(
        columns={"txn_id": "matched_real_txn_id", "client_id": "matched_real_client_id"})
    real = real.drop_duplicates(match_cols, keep="first")
    m = tx[orphan].reset_index().merge(real, on=match_cols, how="left").set_index("index")
    show("orphan rows", int(orphan.sum()), "n/a")
    show("orphans that copy a real transaction", int(m["matched_real_txn_id"].notna().sum()), "n/a")
    assert m["matched_real_txn_id"].notna().all(), "an orphan has no real twin; decision D07 does not apply"
    # the twin must be unambiguous, or the trace column could name the wrong txn_id
    real_all = tx.loc[~orphan, match_cols + ["txn_id"]]
    multi = set(real_all.loc[real_all.duplicated(match_cols, keep=False), "txn_id"])
    ambiguous = int(m["matched_real_txn_id"].isin(multi).sum())
    show("orphans matching more than one real transaction", ambiguous, "n/a")
    assert ambiguous == 0, "an orphan matches several real transactions; trace is ambiguous"
    check_count("D07", orphan.sum())

    # overlap with later steps: these defects leave with the quarantined rows,
    # so D01 / D05 counts on the clean table are lower than the raw audit counts
    overlap_sid = int((orphan & tx["security_id"].str.match(r"^\d+\.0+$")).sum())
    overlap_neg = int((orphan & tx["shares"].str.startswith("-")).sum())
    show("orphans also holding a 'N.0' security_id (D01)", overlap_sid, "n/a")
    show("orphans also holding negative shares (D05)", overlap_neg, "n/a")

    kept = quarantine("fact_transactions_orphans", "fact_transactions", tx, orphan,
                      m[["matched_real_txn_id", "matched_real_client_id"]])
    orphans_after = (~kept["client_id"].isin(set(t["dim_client"]["client_id"]))).sum()
    show("fact_transactions rows", n_before, len(kept))
    show("client_id orphans", int(orphan.sum()), int(orphans_after))
    assert orphans_after == 0 and len(kept) + orphan.sum() == n_before
    t["fact_transactions"] = kept
    log_step("fact_transactions", "D07 orphan client_id (each is a copy of a real transaction)",
             "quarantine", orphan.sum(),
             f"txn_id {tx.loc[orphan, 'txn_id'].astype(int).min()}-{tx.loc[orphan, 'txn_id'].astype(int).max()}; "
             f"matched real txn_id kept in quarantine file; removes {overlap_sid} 'N.0' security_ids "
             f"and {overlap_neg} negative-share rows before D01/D05")


def d01_security_id(t):
    header("D01", "convert fact_transactions.security_id '45.0' -> '45'")
    tx = t["fact_transactions"]
    sid = tx["security_id"]
    decimal_text = sid.str.match(r"^\d+\.\d+$")
    assert (decimal_text == (sid != "")).all(), "a non-blank security_id is not in decimal-text form"
    values = sid[decimal_text].map(dec)
    assert all(v == v.to_integral_value() for v in values), "a security_id has a real fractional part"
    check_count("D01", decimal_text.sum())

    dim_ids = set(t["dim_security"]["security_id"])
    nonblank = sid != ""
    match_before = sid[nonblank].isin(dim_ids).mean()
    old = sid.copy()
    tx.loc[decimal_text, "security_id"] = values.map(lambda v: str(int(v)))
    match_after = tx.loc[nonblank, "security_id"].isin(dim_ids).mean()

    show("values in 'N.0' form", int(decimal_text.sum()), int(tx["security_id"].str.contains(r"\.").sum()))
    show("non-blank security_id matching dim_security", f"{match_before:.1%}", f"{match_after:.1%}")
    show("blank security_id (cash rows, unchanged)", int((old == "").sum()), int((tx["security_id"] == "").sum()))
    assert match_after == 1.0
    assert (num(old[decimal_text]) == num(tx.loc[decimal_text, "security_id"])).all(), "a value changed number"
    assert ((old == "") == (tx["security_id"] == "")).all()
    record_changes("fact_transactions", tx, "security_id", decimal_text, old)
    log_step("fact_transactions", "D01 security_id stored as decimal text", "convert",
             decimal_text.sum(), "numeric value unchanged; join to dim_security 0% -> 100%")


def d05_negative_shares(t):
    header("D05", "convert negative Buy shares to their absolute value")
    tx = t["fact_transactions"]
    neg = tx["shares"].str.startswith("-")
    types = tx.loc[neg, "txn_type"].unique().tolist()
    assert types == ["Buy"], f"negative shares outside Buy rows: {types}"
    check_count("D05", neg.sum())

    # reconcile BEFORE: |shares| x price must already equal amount (only the sign is wrong)
    def recon_fail(df):
        sec = df["security_id"] != ""
        diff = (num(df.loc[sec, "shares"]) * num(df.loc[sec, "price"]) - num(df.loc[sec, "amount"])).abs()
        return int((diff > 0.011).sum())

    absdiff = (num(tx.loc[neg, "shares"]).abs() * num(tx.loc[neg, "price"]) - num(tx.loc[neg, "amount"])).abs()
    assert (absdiff <= 0.011).all(), "a negative-share row does not reconcile even ignoring sign"

    fails_before = recon_fail(tx)
    old = tx["shares"].copy()
    tx.loc[neg, "shares"] = tx.loc[neg, "shares"].str[1:]
    fails_after = recon_fail(tx)

    show("shares < 0", int(neg.sum()), int((num(tx["shares"]) < 0).sum()))
    show("security rows failing amount = shares x price", fails_before, fails_after)
    assert (num(tx["shares"]) > 0).sum() == (tx["shares"] != "").sum()
    assert fails_after == 0
    record_changes("fact_transactions", tx, "shares", neg, old)
    log_step("fact_transactions", "D05 negative shares on Buy rows", "convert", neg.sum(),
             "abs(shares); amount = shares x price reconciles on all security rows after")


def d02_d03_returns(t):
    s = t["fact_portfolio_snapshot"]

    def alpha_recon_fail(df):
        r = num(df["return_ytd"])
        diff = (r - num(df["benchmark_return_ytd"]) - num(df["active_alpha_ytd"])).abs()
        return int((diff > 1e-4).sum()), int(r.isna().sum())

    header("D02", "convert '%' return_ytd strings to decimals")
    pct = s["return_ytd"].str.endswith("%")
    check_count("D02", pct.sum())
    # reconcile: a naive strip (no /100) must NOT reconcile, or /100 would be a guess
    naive = num(s.loc[pct, "return_ytd"].str[:-1])
    naive_ok = int(((naive - num(s.loc[pct, "benchmark_return_ytd"])
                     - num(s.loc[pct, "active_alpha_ytd"])).abs() <= 1e-4).sum())
    show("'%' rows reconciling WITHOUT /100 (expect 0)", naive_ok, "n/a")
    assert naive_ok == 0, "some '%' values reconcile without /100; D02 would understate them"
    fails_before, unparsable_before = alpha_recon_fail(s)
    old = s["return_ytd"].copy()
    s.loc[pct, "return_ytd"] = s.loc[pct, "return_ytd"].str[:-1].map(lambda v: plain(dec(v) / 100))
    fails_after, unparsable_after = alpha_recon_fail(s)
    show("'%' strings", int(pct.sum()), int(s["return_ytd"].str.contains("%").sum()))
    show("return_ytd values that fail a numeric parse", unparsable_before, unparsable_after)
    show("rows failing or unparsable: return = benchmark + alpha", fails_before + unparsable_before,
         fails_after + unparsable_after)
    pct_diff = (num(s.loc[pct, "return_ytd"]) - num(s.loc[pct, "benchmark_return_ytd"])
                - num(s.loc[pct, "active_alpha_ytd"])).abs()
    show("max reconciliation gap on the 300 converted rows", "n/a", f"{pct_diff.max():.6f}")
    assert unparsable_after == 0 and fails_after == 0 and pct_diff.max() <= 1e-4
    record_changes("fact_portfolio_snapshot", s, "return_ytd", pct, old)
    log_step("fact_portfolio_snapshot", "D02 return_ytd stored as '%' strings", "convert", pct.sum(),
             f"/100; all {pct.sum()} reconcile to benchmark + alpha (max gap {pct_diff.max():.6f})")

    header("D03", "standardize scientific notation to plain decimals (value unchanged)")
    for col in ("return_ytd", "active_alpha_ytd"):
        sci = s[col].str.contains(r"[eE]")
        old = s[col].copy()
        s.loc[sci, col] = s.loc[sci, col].map(lambda v: plain(dec(v)))
        same_value = all(dec(a) == dec(b) for a, b in zip(old[sci], s.loc[sci, col]))
        show(f"{col}: values in scientific notation", int(sci.sum()), int(s[col].str.contains(r"[eE]").sum()))
        assert same_value, f"{col}: a value changed while reformatting"
        assert not s[col].str.contains(r"[eE]").any()
        check_count(f"D03 {col}", sci.sum())
        record_changes("fact_portfolio_snapshot", s, col, sci, old)
        log_step("fact_portfolio_snapshot", f"D03 {col} in scientific notation", "standardize", sci.sum(),
                 "plain decimal text; exact Decimal value unchanged")
    fails, _ = alpha_recon_fail(s)
    show("rows failing return = benchmark + alpha after D03", "n/a", fails)
    assert fails == 0


def d04_state(t):
    header("D04", "standardize dim_client.state full names to USPS codes")
    cl = t["dim_client"]
    full = cl["state"].isin(STATE_MAP)
    assert set(STATE_MAP.values()) <= set(cl.loc[~full, "state"]), "a target code is not already in use"
    old = cl["state"].copy()
    cl.loc[full, "state"] = cl.loc[full, "state"].map(STATE_MAP)
    invalid_after = (~cl["state"].isin(US_STATES)).sum()
    show("state values not a USPS code", int((~old.isin(US_STATES)).sum()), int(invalid_after))
    show("distinct state values", old.nunique(), cl["state"].nunique())
    assert invalid_after == 0
    assert (old[~full] == cl.loc[~full, "state"]).all(), "a value outside the map changed"
    check_count("D04", full.sum())
    record_changes("dim_client", cl, "state", full, old)
    log_step("dim_client", "D04 state stored as full name", "standardize", full.sum(),
             "explicit 7-name map; 1 of the 78 raw full names was on a quarantined duplicate")


def d08_risk_profile(t):
    header("D08", "standardize blank dim_client.risk_profile to 'Unknown' (not filled)")
    cl = t["dim_client"]
    blank = cl["risk_profile"].str.strip() == ""
    old = cl["risk_profile"].copy()
    cl.loc[blank, "risk_profile"] = "Unknown"
    show("blank risk_profile", int(blank.sum()), int((cl["risk_profile"].str.strip() == "").sum()))
    show("'Unknown' risk_profile", int((old == "Unknown").sum()), int((cl["risk_profile"] == "Unknown").sum()))
    assert (cl["risk_profile"] == "").sum() == 0
    assert (cl["risk_profile"] == "Unknown").sum() == blank.sum()
    check_count("D08", blank.sum())
    record_changes("dim_client", cl, "risk_profile", blank, old)
    log_step("dim_client", "D08 blank risk_profile", "standardize", blank.sum(),
             "set to 'Unknown'; NOT filled from benchmark (suitability attribute, evidence circular)")


def flags(t):
    tx, s, fee, cl = t["fact_transactions"], t["fact_portfolio_snapshot"], t["fact_fees"], t["dim_client"]

    header("D09", "flag transactions after an inactive client's last snapshot month")
    # dates are compared as text below, which is only correct for zero-padded ISO dates
    for df, col in ((tx, "txn_date"), (s, "snapshot_date"), (fee, "fee_date")):
        assert df[col].str.match(ISO_DATE).all(), f"{col}: not all YYYY-MM-DD; text comparison unsafe"
    last =s.groupby("client_id")["snapshot_date"].max()
    month_end = (pd.to_datetime(last) + pd.offsets.MonthEnd(0)).dt.strftime("%Y-%m-%d")
    inactive = set(cl.loc[cl["is_active"] == "False", "client_id"])
    end = tx["client_id"].map(month_end)
    post = tx["client_id"].isin(inactive) & end.notna() & (tx["txn_date"] > end)
    tx["is_post_departure_txn"] = post.astype(int).astype(str)
    fee_post = fee["client_id"].isin(inactive) & (fee["fee_date"] > fee["client_id"].map(month_end))
    show("flagged transactions", "n/a", int(post.sum()))
    show("clients affected / inactive clients", "n/a", f"{tx.loc[post, 'client_id'].nunique()}/{len(inactive)}")
    show("fees after departure (cross-check, expect 0)", "n/a", int(fee_post.sum()))
    assert fee_post.sum() == 0
    assert set(tx["is_post_departure_txn"]) <= {"0", "1"}
    check_count("D09", post.sum())
    log_step("fact_transactions", "D09 activity after client's last snapshot month (inactive clients)",
             "flag", post.sum(), f"is_post_departure_txn; {tx.loc[post, 'client_id'].nunique()} clients; "
             f"${num(tx.loc[post, 'amount']).sum():,.0f} total amount; rows kept")

    header("D10", "flag implausible YTD returns (|return_ytd| > 100%)")
    r = num(s["return_ytd"])
    assert r.notna().all(), "return_ytd must be numeric before flagging (run D02 first)"
    suspect = r.abs() > 1
    s["is_return_suspect"] = suspect.astype(int).astype(str)
    show("flagged snapshots", "n/a", int(suspect.sum()))
    show("clients affected", "n/a", s.loc[suspect, "client_id"].nunique())
    check_count("D10", suspect.sum())
    log_step("fact_portfolio_snapshot", "D10 |return_ytd| > 100% (return = AUM change incl. cash flows)",
             "flag", suspect.sum(), "is_return_suspect; values unchanged")

    header("D11", "flag AUM stuck at exactly 1,000.00")
    s_floor = num(s["aum"]) == 1000
    f_floor = num(fee["aum_basis"]) == 1000
    s["is_aum_floor"] = s_floor.astype(int).astype(str)
    fee["is_aum_floor"] = f_floor.astype(int).astype(str)
    # reconcile: fee aum_basis equals snapshot aum for the same client-month, so flags must agree
    m = fee[["client_id", "fee_date", "is_aum_floor"]].merge(
        s[["client_id", "snapshot_date", "is_aum_floor"]],
        left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"], how="left")
    disagree = (m["is_aum_floor_x"] != m["is_aum_floor_y"]).sum()
    show("flagged snapshots", "n/a", int(s_floor.sum()))
    show("flagged fees", "n/a", int(f_floor.sum()))
    show("fee rows whose flag disagrees with its snapshot", "n/a", int(disagree))
    assert disagree == 0
    check_count("D11 snapshot", s_floor.sum())
    check_count("D11 fees", f_floor.sum())
    log_step("fact_portfolio_snapshot", "D11 aum exactly 1,000.00 (floor value)", "flag", s_floor.sum(),
             "is_aum_floor; real balance not recoverable; values unchanged")
    log_step("fact_fees", "D11 aum_basis exactly 1,000.00 (floor value)", "flag", f_floor.sum(),
             "is_aum_floor; fee amount reconciles to the 1,000 basis; values unchanged")


def leave_as_is_entries():
    """Decisions with no code change still belong in the cleaning log."""
    for table, issue, note in [
        ("fact_transactions", "D12 Buy/Sell on non-trading days", "even 2/7 spread = column-level artifact; documented limitation"),
        ("fact_transactions", "L01 blank security_id/shares/price on cash rows", "legitimate structure (Deposit/Withdrawal/Advisory Fee)"),
        ("dim_security", "L02 blank sector (ETFs) / expense_ratio_bps (non-ETFs)", "legitimate structure: not applicable"),
        ("dim_advisor", "L03 certifications = 'None'", "real value, kept as text"),
        ("fact_transactions", "L04 same-day cash flows differing only in amount", "distinct events, not duplicates"),
        ("fact_transactions", "L05 recurring same-amount fees on different dates", "expected; also 2 fee rows"),
        ("dim_client", "L06 zip_code leading zeros", "kept as text"),
        ("dim_security", "L07 duplicate security names, distinct tickers", "different securities"),
        ("fact_transactions", "L08 dividend amount = full position value", "implausible but not derivable; documented limitation"),
        ("dim_benchmark", "L09 benchmark 6 unused", "dimension members need not appear in facts"),
        ("dim_client", "L10 zip prefix vs state mismatch", "no reference table; documented limitation"),
    ]:
        CLEANING_LOG.append({"table": table, "issue": issue, "action": "leave as is", "rows_affected": 0, "note": note})


# --------------------------------------------------------------------------
# Final checks
# --------------------------------------------------------------------------

def final_checks(t, raw, raw_shapes, raw_columns):
    header("FINAL", "reconciliation and integrity asserts on the clean tables")
    added = {"fact_transactions": ["is_post_departure_txn"],
             "fact_portfolio_snapshot": ["is_return_suspect", "is_aum_floor"],
             "fact_fees": ["is_aum_floor"]}
    for name in TABLES:
        df = t[name]
        q = QUARANTINE.get(name, 0)
        print(f"  {name:26} raw {raw_shapes[name]:>8,} = clean {len(df):>8,} + quarantined {q:>4}")
        assert raw_shapes[name] == len(df) + q, f"{name}: rows lost or created"
        assert list(df.columns) == raw_columns[name] + added.get(name, []), f"{name}: columns changed"
        assert df[PK[name]].is_unique, f"{name}: primary key not unique"

    print()
    for fact, fcol, dim, dcol in RELATIONSHIPS:
        key = t[fact][fcol]
        nonblank = key != ""
        rate = key[nonblank].isin(set(t[dim][dcol])).mean()
        print(f"  RI {fact}.{fcol:14} -> {dim}.{dcol:13} match {rate:7.2%}   blank keys {int((~nonblank).sum()):,}")
        assert rate == 1.0, f"{fact}.{fcol}: orphans remain"
        if fcol == "security_id":
            assert (~nonblank == t[fact]["txn_type"].isin(CASH_TYPES)).all(), "blank security_id on a non-cash row"
        else:
            assert nonblank.all(), f"{fact}.{fcol}: blank keys"

    tx, s, fee = t["fact_transactions"], t["fact_portfolio_snapshot"], t["fact_fees"]
    sec = tx["security_id"] != ""
    recon = {
        "fact_transactions amount = shares x price":
            ((num(tx.loc[sec, "shares"]) * num(tx.loc[sec, "price"]) - num(tx.loc[sec, "amount"])).abs() > 0.011).sum(),
        "fact_fees amount = aum_basis x bps / 120,000":
            ((num(fee["amount"]) - num(fee["aum_basis"]) * num(fee["bps_charged"]) / 120000).abs() > 0.011).sum(),
        "fact_portfolio_snapshot return = benchmark + alpha":
            ((num(s["return_ytd"]) - num(s["benchmark_return_ytd"]) - num(s["active_alpha_ytd"])).abs() > 1e-4).sum(),
    }
    print()
    for label, fails in recon.items():
        print(f"  reconcile {label:52} failures = {fails}")
        assert fails == 0
    for name, cols in {"fact_portfolio_snapshot": ["aum", "return_ytd", "benchmark_return_ytd",
                                                   "active_alpha_ytd", "cash_pct"],
                       "fact_fees": ["aum_basis", "bps_charged", "amount"],
                       "fact_transactions": ["amount"]}.items():
        for c in cols:
            assert num(t[name][c]).notna().all(), f"{name}.{c}: non-numeric value remains"
    assert not t["dim_client"]["state"].isin(STATE_MAP).any()

    # every cell that differs from raw must be in value_changes.csv, and nothing else may differ
    vc = pd.concat(VALUE_CHANGES, ignore_index=True)
    assert not vc.duplicated(["table", "column", "key"]).any(), "a cell was changed by two steps"
    print()
    for name in TABLES:
        cols, clean = raw_columns[name], t[name]
        changed = raw[name].loc[clean.index, cols].ne(clean[cols])
        for c in cols:
            keys = set(clean.loc[changed[c], PK[name]])
            logged = set(vc.loc[(vc["table"] == name) & (vc["column"] == c), "key"])
            if keys or logged:
                print(f"  cells changed {name}.{c:22} {len(keys):>8,}   in value_changes {len(logged):>8,}")
            assert keys == logged, f"{name}.{c}: changed cells do not match value_changes.csv"
    print(f"  every other cell is byte-identical to raw ({len(vc):,} logged changes)")
    print("\n  all final asserts passed")


# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------

def write_outputs(t):
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        t[name].to_csv(CLEAN_DIR / f"{name}.csv", index=False, lineterminator="\n")
    pd.DataFrame(CLEANING_LOG).to_csv(AUDIT_DIR / "cleaning_log.csv", index=False, lineterminator="\n")
    vc = pd.concat(VALUE_CHANGES, ignore_index=True)
    vc.to_csv(AUDIT_DIR / "value_changes.csv", index=False, lineterminator="\n")
    write_readme(t, vc)
    print(f"\nwrote {len(TABLES)} clean tables to {CLEAN_DIR}")
    print(f"wrote cleaning_log.csv ({len(CLEANING_LOG)} rows), value_changes.csv ({len(vc):,} rows), "
          f"{len(QUARANTINE)} quarantine files to {AUDIT_DIR}")
    print("\nvalue changes by table/column:")
    print(vc.groupby(["table", "column"]).size().to_string())


def write_readme(t, vc):
    s, tx, fee = t["fact_portfolio_snapshot"], t["fact_transactions"], t["fact_fees"]
    flags = {
        "fact_transactions.is_post_departure_txn": int((tx["is_post_departure_txn"] == "1").sum()),
        "fact_portfolio_snapshot.is_return_suspect": int((s["is_return_suspect"] == "1").sum()),
        "fact_portfolio_snapshot.is_aum_floor": int((s["is_aum_floor"] == "1").sum()),
        "fact_fees.is_aum_floor": int((fee["is_aum_floor"] == "1").sum()),
    }
    n_shares = int(((vc["table"] == "fact_transactions") & (vc["column"] == "shares")).sum())
    rows = "\n".join(f"| `{n}` | {len(t[n]):,} | {t[n].shape[1]} | `{PK[n]}` |" for n in TABLES)
    rels = "\n".join(f"| `{f}.{fc}` | `{d}.{dc}` | many-to-one |" for f, fc, d, dc in RELATIONSHIPS)
    text = f"""# Clean Wildcat Capital tables

Produced by `scripts/02_clean.py` from `data/raw/`, following `decision_log.md`.
Audit trail: `data/audit/` (`cleaning_log.csv`, `value_changes.csv` with {len(vc):,} changed cells, quarantine files).

## Tables

| Table | Rows | Cols | Primary key |
|---|---:|---:|---|
{rows}

Removed rows (quarantined, not deleted): `dim_client` {QUARANTINE.get('dim_client', 0)} duplicate clients,
`fact_transactions` {QUARANTINE.get('fact_transactions', 0)} orphan copies. For every table, raw rows = clean rows + quarantined rows.

## Relationships

Star schema: five dimensions, three facts. Every key below matches 100% after cleaning.

| From (many) | To (one) | Cardinality |
|---|---|---|
{rels}

`fact_transactions.security_id` is **blank on every cash row** (Deposit, Withdrawal, Advisory Fee) and only there. Use a
left/outer relationship; an inner join drops all cash flows.

## Column types a BI tool needs

| Column(s) | Type | Why |
|---|---|---|
| all `*_id` keys | Whole Number | keys; `security_id` blank on cash rows is expected |
| `date`, `client_since`, `fee_date`, `snapshot_date`, `txn_date` | Date (not Date/Time) | ISO `YYYY-MM-DD` text |
| `aum`, `aum_basis`, `initial_aum`, `amount`, `price`, `shares` | Decimal / Fixed decimal | money and quantities |
| `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd`, `cash_pct` | Decimal Number | stored as decimals (0.0928 = 9.28%); format as % in the BI layer |
| `bps_charged`, `expense_ratio_bps` | Decimal Number | basis points |
| `dim_client.zip_code` | **Text** | leading zeros (e.g. `03897`) |
| `dim_client.primary_account_type`, `fact_portfolio_snapshot.account_type` | **Text** | values include `529`, which auto-detects as a number |
| `dim_client.is_active`, `dim_security.is_etf` | True/False | text `True`/`False` |
| `is_*` flag columns, `dim_date` `is_*` columns | Whole Number (0/1) | |
| `dim_advisor.certifications` | Text | `None` is a real value ("no certification"), not null |

## Flag columns added (0/1, values never changed)

| Column | Rows = 1 | Meaning |
|---|---:|---|
| `fact_transactions.is_post_departure_txn` | {flags['fact_transactions.is_post_departure_txn']:,} | inactive client, dated after the end of their last snapshot month (D09) |
| `fact_portfolio_snapshot.is_return_suspect` | {flags['fact_portfolio_snapshot.is_return_suspect']:,} | \\|return_ytd\\| > 100%: return is AUM change incl. cash flows (D10) |
| `fact_portfolio_snapshot.is_aum_floor` | {flags['fact_portfolio_snapshot.is_aum_floor']:,} | AUM exactly 1,000.00, looks like a floor value (D11) |
| `fact_fees.is_aum_floor` | {flags['fact_fees.is_aum_floor']:,} | fee basis exactly 1,000.00, same client-months as above (D11) |

Other standardizations: `risk_profile = 'Unknown'` marks clients with no recorded profile (D08), deliberately not filled.

## Known limitations (not fixed, with reason)

1. **`return_ytd` is not investment performance.** It equals AUM / prior-December AUM - 1 on every testable row, so
   deposits and withdrawals count as "return". `active_alpha_ytd` inherits this. Flagged only where > 100%; smaller
   values are also affected. A true time-weighted return needs daily flows that are not in this data.
2. **Post-departure activity is kept** (flagged). The data cannot show whether the departure or the transactions are wrong.
3. **Trade dates ignore the calendar.** About 28% of Buy/Sell rows fall on weekends, evenly across all seven days.
   Report trades by month, not by day.
4. **Dividend amounts equal full position value** (shares x market price), far above any real yield. Not derivable
   from other data; do not report dividend income until the source is confirmed.
5. **AUM floor rows** keep the 1,000.00 value because the true balance is unknown and fees were billed on it.
6. **Zip codes do not match states**; no reference table to say which is wrong. Use `state` for geography.
7. **Negative shares were treated as a sign error, not a mislabelled `txn_type`** ({n_shares:,} Buy rows); amounts
   support the sign fix but cannot prove the type.
8. **Blank `dim_security.sector` on ETFs and blank `expense_ratio_bps` on non-ETFs mean "not applicable".** Label the
   blank sector "ETF / multi-sector" in the BI layer, not in the data.
9. **Three security names appear twice** (different tickers and asset classes). Group by `ticker`, not `name`.
"""
    (CLEAN_DIR / "README_clean.md").write_text(text, encoding="utf-8")


def main():
    t = load()
    raw = {n: df.copy() for n, df in t.items()}  # untouched copy for the final cell-level diff
    raw_shapes = {n: len(df) for n, df in t.items()}
    raw_columns = {n: list(df.columns) for n, df in t.items()}

    d06_duplicate_clients(t)
    d07_orphan_transactions(t)
    d01_security_id(t)
    d05_negative_shares(t)
    d02_d03_returns(t)
    d04_state(t)
    d08_risk_profile(t)
    flags(t)
    leave_as_is_entries()
    final_checks(t, raw, raw_shapes, raw_columns)
    write_outputs(t)


if __name__ == "__main__":
    main()
