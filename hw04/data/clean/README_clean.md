# Clean Wildcat Capital tables

Produced by `scripts/02_clean.py` from `data/raw/`, following `decision_log.md`.
Audit trail: `data/audit/` (`cleaning_log.csv`, `value_changes.csv` with 199,222 changed cells, quarantine files).

## Tables

| Table | Rows | Cols | Primary key |
|---|---:|---:|---|
| `dim_advisor` | 25 | 7 | `advisor_id` |
| `dim_benchmark` | 8 | 4 | `benchmark_id` |
| `dim_client` | 2,500 | 14 | `client_id` |
| `dim_date` | 1,827 | 12 | `date_id` |
| `dim_security` | 500 | 8 | `security_id` |
| `fact_fees` | 122,197 | 9 | `fee_id` |
| `fact_portfolio_snapshot` | 129,547 | 15 | `snapshot_id` |
| `fact_transactions` | 298,572 | 10 | `txn_id` |

Removed rows (quarantined, not deleted): `dim_client` 25 duplicate clients,
`fact_transactions` 200 orphan copies. For every table, raw rows = clean rows + quarantined rows.

## Relationships

Star schema: five dimensions, three facts. Every key below matches 100% after cleaning.

| From (many) | To (one) | Cardinality |
|---|---|---|
| `dim_client.advisor_id` | `dim_advisor.advisor_id` | many-to-one |
| `dim_security.benchmark_id` | `dim_benchmark.benchmark_id` | many-to-one |
| `fact_fees.client_id` | `dim_client.client_id` | many-to-one |
| `fact_fees.advisor_id` | `dim_advisor.advisor_id` | many-to-one |
| `fact_portfolio_snapshot.client_id` | `dim_client.client_id` | many-to-one |
| `fact_portfolio_snapshot.advisor_id` | `dim_advisor.advisor_id` | many-to-one |
| `fact_portfolio_snapshot.benchmark_id` | `dim_benchmark.benchmark_id` | many-to-one |
| `fact_transactions.client_id` | `dim_client.client_id` | many-to-one |
| `fact_transactions.advisor_id` | `dim_advisor.advisor_id` | many-to-one |
| `fact_transactions.security_id` | `dim_security.security_id` | many-to-one |
| `fact_fees.fee_date` | `dim_date.date` | many-to-one |
| `fact_portfolio_snapshot.snapshot_date` | `dim_date.date` | many-to-one |
| `fact_transactions.txn_date` | `dim_date.date` | many-to-one |

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
| `fact_transactions.is_post_departure_txn` | 2,410 | inactive client, dated after the end of their last snapshot month (D09) |
| `fact_portfolio_snapshot.is_return_suspect` | 977 | \|return_ytd\| > 100%: return is AUM change incl. cash flows (D10) |
| `fact_portfolio_snapshot.is_aum_floor` | 420 | AUM exactly 1,000.00, looks like a floor value (D11) |
| `fact_fees.is_aum_floor` | 386 | fee basis exactly 1,000.00, same client-months as above (D11) |

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
7. **Negative shares were treated as a sign error, not a mislabelled `txn_type`** (835 Buy rows); amounts
   support the sign fix but cannot prove the type.
8. **Blank `dim_security.sector` on ETFs and blank `expense_ratio_bps` on non-ETFs mean "not applicable".** Label the
   blank sector "ETF / multi-sector" in the BI layer, not in the data.
9. **Three security names appear twice** (different tickers and asset classes). Group by `ticker`, not `name`.
