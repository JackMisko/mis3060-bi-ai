# Wildcat Capital Data Cleaning Report

**To:** Portfolio Committee · **Re:** Readiness of the warehouse extract for reporting · **Scope:** 8 tables, 555,401 raw rows

## Executive summary

The warehouse extract can now be used for monthly AUM, fee, client and advisor reporting. **Investment-performance and dividend-income figures cannot be used as they are.**

The extract had defects that would have broken or distorted reports:
- 197,175 transaction security IDs (66% of all transactions) didn't join to the security table
- 25 duplicate clients
- 200 copied transactions pointing at clients that don't exist
- 836 Buys with negative share counts
- 300 returns stored as text percentages

After cleaning, all 13 table relationships join 100%, all 48 business rules pass, and all 9 reconciliations agree. Every change is logged, and no row was deleted: 225 rows were set aside in quarantine files, and each one can be traced.

Three things still need a business decision:
- **Reported "returns" include deposits and withdrawals.** They measure AUM change, not performance.
- **2,410 transactions ($127.5M) took place after the client left.**
- **Dividend amounts are implausibly large.**

These rows are flagged rather than changed, so the committee can choose how to treat them.

## What was cleaned

| Issue | Table | Rows | Action | How the fix was verified |
|---|---|---:|---|---|
| Duplicate clients: copies with a one-letter last-name typo (IDs 2501–2525) | `dim_client` | 25 | Quarantined | No fact rows reference them; each pairs with an original |
| Orphan transactions: exact copies of real transactions with a fake client ID | `fact_transactions` | 200 | Quarantined | Each one matched to the real transaction it copies |
| Security ID stored as `45.0` | `fact_transactions` | 197,044 | Converted to `45` | Join to securities: 0% → 100% |
| Negative shares on Buy rows | `fact_transactions` | 835 | Sign removed | amount = shares × price on every trade |
| Returns stored as `9.28%` | `fact_portfolio_snapshot` | 300 | Converted to 0.0928 | All 300 = benchmark + alpha (max gap 0.00005) |
| Scientific notation (`9.9e-05`) | `fact_portfolio_snapshot` | 891 | Plain decimals | Exact values unchanged |
| State names (`Pennsylvania`) | `dim_client` | 77 | USPS codes | 20 valid codes remain, 0 invalid |
| Blank risk profile | `dim_client` | 75 | Marked `Unknown` | Not filled in (see judgment call 1) |
| Activity after client departure | `fact_transactions` | 2,410 | Flagged | Fees stop cleanly at departure (0 after) |
| YTD return beyond ±100% | `fact_portfolio_snapshot` | 977 | Flagged | Values unchanged |
| AUM stuck at exactly $1,000 | snapshots / fees | 420 / 386 | Flagged | Fee and snapshot flags agree on every client-month |

**Totals:**
- **Rows:** 555,401 raw = 555,176 clean + 225 quarantined.
- **Cells changed:** 199,222, each logged with its old and new value. Every other cell is identical to the source.
- **Left as they are:** 10 issues that only *look* wrong were investigated and kept. For example, blank security IDs appear only on the 101,528 cash transactions, and blank sectors appear only on ETFs.

**Data quality scorecard (raw → clean).** These are the three tables that changed; the other five score 100% on every measure in both stages.

| Table | Completeness | Key uniqueness | Type validity | Rule pass | Referential match |
|---|---|---|---|---|---|
| `fact_transactions` | 100 → 100 | 99.866 → 100 | 91.730 → 100 | 99.947 → 100 | 81.95 → 100 |
| `dim_client` | 99.785 → 99.786 | 98.020 → 100 | 100 → 100 | 99.612 → 100 | 100 → 100 |
| `fact_portfolio_snapshot` | 100 → 100 | 100 → 100 | 99.982 → 100 | 100 → 100 | 100 → 100 |

`dim_client` completeness stays below 100% on purpose: `Unknown` is scored as still missing.

## Key judgment calls

**1. The 75 missing risk profiles are marked `Unknown`, not filled with "Balanced".**
- **Evidence:** all 75 clients sit on the 60/40 benchmark, which only *Balanced* clients use.
- **Why we didn't fill it:** that evidence is circular. A 60/40 blend is the default a system assigns when no profile exists. Risk profile is a suitability record of what the client agreed to, and an inferred "Balanced" could be read as the client's consent.
- **Risk:** risk-profile reports show a small "Unknown" group, 3% of clients. That's less harmful than an unverified suitability record.

**2. Extreme returns are flagged, not corrected.**
- **Evidence:** on all 104,823 testable rows, `return_ytd` equals AUM ÷ prior-December AUM − 1. Deposits and withdrawals therefore count as "return": one client shows +9,467%.
- **Why we didn't correct it:** a true time-weighted return needs daily cash flows that the extract doesn't contain, so any correction would invent data.
- **Risk:** the 977 flagged rows are only the obvious cases. Smaller returns and `active_alpha_ytd` are affected too, so performance and alpha should not be reported from this column without a caveat.

**3. Post-departure activity is kept and flagged, not deleted.**
- **Evidence:** 131 of 175 inactive clients have 2,410 transactions ($127.5M) dated after their last snapshot month. The fee table stops cleanly at departure.
- **Why we kept it:** the data can't show whether the departure dates or the transactions are wrong. Deleting $127.5M of money movement would hide exactly what a compliance review needs.
- **Risk:** totals include closed-account activity unless reports filter on `is_post_departure_txn`.

**4. The orphan transactions are quarantined, not re-assigned to the real client.**
- **Evidence:** all 200 duplicate a real transaction on every field except the client ID.
- **Why:** re-assigning them would double-count exactly those trades and cash flows.

## Limitations

1. **Returns and alpha** reflect cash flows, not performance (judgment call 2).
2. **Dividend amounts equal the full position value.** The median dividend is $48.8k, against a median Buy of $47.9k, far above any real yield. The correct figure can't be derived, so dividend income should not be reported until the source is confirmed.
3. **Trade dates ignore the calendar.** 40,649 of 143,311 Buys and Sells (28.4%) fall on non-trading days, spread evenly across all seven days of the week. Report trades by month, not by day.
4. **$1,000 AUM floor.** Those 420 snapshot balances are kept: fees were billed on that $1,000 basis (386 fee rows), and the true balance is unknown.
5. **Zip codes don't match states,** and there's no reference table to say which is wrong. Use `state` for geography.
6. **Negative shares were treated as a sign error, not a mislabelled sell.** The amounts support the sign fix but can't prove the transaction type.
7. **IQR outliers are not errors.** All 251 `initial_aum` outliers are UHNW clients. Large transactions by Retail clients (4,366 above $186k) deserve a review but were not changed.

Sources: `decision_log.md`, `data/audit/cleaning_log.csv`, `reports/data_quality_scorecard.csv`, `reports/reconciliations.csv`, `reports/outliers_iqr.csv`, `reports/dq_summary_raw.csv`.

---

AI-assisted report — reviewed for factual accuracy on [date] by [your name]
