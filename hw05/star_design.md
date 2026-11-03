# HW5 Star Schema Design: Wildcat Capital

Every key, grain and integrity claim below is a PASS/FAIL check in `hw05_star_checks.py` (55 checks, all pass; run it with `python hw05_star_checks.py`). The supporting counts quoted in the text (flag counts, benchmarks used, the `client_since` range, the make-up of repeated transactions) are printed by the same script as `[INFO]` lines. The checks are grouped by part (A, B, C, E) to match this document.

---

## Part A: Keys

| Table | Type | Primary key | Foreign keys (column → table[column]) |
|---|---|---|---|
| dim_advisor | Dimension | `advisor_id` | — |
| dim_benchmark | Dimension | `benchmark_id` | — |
| dim_client | Dimension | `client_id` | `advisor_id` → dim_advisor[advisor_id] |
| dim_date | Dimension | `date_id` (the facts join on the alternate key `date`, also unique) | — |
| dim_security | Dimension | `security_id` | `benchmark_id` → dim_benchmark[benchmark_id] |
| fact_fees | Fact | `fee_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`fee_date` → dim_date[date] |
| fact_portfolio_snapshot | Fact | `snapshot_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`benchmark_id` → dim_benchmark[benchmark_id]<br>`snapshot_date` → dim_date[date] |
| fact_transactions | Fact | `txn_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`security_id` → dim_security[security_id] *(can be blank)*<br>`txn_date` → dim_date[date] |

**Integrity (proven in code):** all eight primary keys are unique and never blank, and so is `dim_date[date]`. All 13 foreign keys have **zero orphans**. Row counts match the handout exactly.

**Keys that can legitimately be blank:** `fact_transactions[security_id]` is blank on 101,528 rows, and every one of them is a Deposit, Withdrawal or Advisory Fee. These are cash movements, so there is no security for them to point to (see E(a)). No other foreign key has a blank.

**Not a foreign key:** `dim_client[client_since]` is a date, but 1,532 of the 2,500 values fall before 2020-01-01, where `dim_date` starts. It is a descriptive attribute of the client, not a key into the calendar.

---

## Part B: Grain

- **fact_fees:** One row represents the single fee charged to one client for one month (fee_date is always the 1st). *Check: client_id + fee_date is unique.*
- **fact_portfolio_snapshot:** One row represents the state of one client's account (each client has exactly one) at the start of one month. *Check: client_id + snapshot_date is unique.*
- **fact_transactions:** One row represents one individual transaction: a buy, sell, dividend, deposit, withdrawal or advisory-fee debit, by one client on one date. *Check: txn_id is unique and no rows are duplicated apart from txn_id. There is no natural composite key: client + date + type + security repeats 622 times (mostly two separate deposits, fee debits or withdrawals by one client on the same day, e.g. client 1 made two deposits on 2024-09-25), so txn_id itself defines the grain.*

---

## Part C: Measures

### Fact measures

| Table | Column | Classification | What it means for summing / averaging |
|---|---|---|---|
| fact_fees | `amount` | **Additive** | Fee dollars can be summed across clients, advisors, fee types and months; the total is revenue for that slice. |
| fact_fees | `aum_basis` | **Semi-additive** | It is a balance (equal to that month's snapshot `aum`). Sum it across clients for one month, but never across months; over time take the last month or the average. |
| fact_fees | `bps_charged` | **Non-additive** | An annual rate; summing rates is meaningless. The correct average rate is weighted: SUM(amount) × 12 × 10,000 / SUM(aum_basis). |
| fact_portfolio_snapshot | `aum` | **Semi-additive** | Summing across clients for one month gives firm AUM; summing across months double-counts the same money. Over time, use the period's last snapshot (or the average). |
| fact_portfolio_snapshot | `return_ytd` | **Non-additive** | A cumulative percentage. Never sum it. Across clients, take an AUM-weighted average; across months, take the value at the last month of the year (it already contains the earlier months). |
| fact_portfolio_snapshot | `benchmark_return_ytd` | **Non-additive** | Same as `return_ytd`: a cumulative percentage to compare against, never summed. |
| fact_portfolio_snapshot | `active_alpha_ytd` | **Non-additive** | Defined as return_ytd − benchmark_return_ytd (checked), so it is a difference of percentages. Take a weighted average or recompute it from the two returns; never sum it. |
| fact_portfolio_snapshot | `cash_pct` | **Non-additive** | A share of the account. Averaging across clients needs AUM weights (cash $ / AUM $); summing produces numbers above 100%. |
| fact_transactions | `amount` | **Additive** (only within one `txn_type`) | Every amount is positive, and direction comes from `txn_type`. SUM is valid for one type (total deposits, total buys) across clients, securities and dates. Summing across types (buys + sells + withdrawals) adds money moving in opposite directions and means nothing. |
| fact_transactions | `shares` | **Additive** (only within one security and `txn_type`) | Shares bought of one security can be summed across clients and dates. Summing across securities mixes units (100 shares of a stock + 100 shares of a bond ETF), and Dividend rows also carry shares, so mixing types would count shares that were never traded. |
| fact_transactions | `price` | **Non-additive** | A per-share price; summing is meaningless. The average price is share-weighted: SUM(amount) / SUM(shares) for Buy/Sell rows. |

### Numeric columns in fact tables that are not measures
- **Keys:** `fee_id`, `snapshot_id`, `txn_id`, `client_id`, `advisor_id`, `benchmark_id`, `security_id` (summing an ID is meaningless; COUNT or DISTINCTCOUNT them instead).
- **Date parts:** `fact_portfolio_snapshot[year]`, `[month]` (duplicates of `dim_date` attributes; slice with dim_date instead).
- **Flags:** `is_return_suspect` (3,875 rows), `is_post_departure_txn` (2,410 rows) are 0/1 filters. Their SUM happens to equal a count of flagged rows, but they are used to filter or exclude rows, not as quantities.

### Numeric attributes in dimension tables that must never be summed
- **dim_advisor:** `years_experience` (average it, don't add it), `aum_target_mm` (a per-advisor goal; compare it against that advisor's AUM rather than adding it up across fact rows)
- **dim_client:** `age`; `initial_aum` (each value is a balance taken at a different onboarding date between 2015 and 2022, so the total is not the AUM at any point in time); `zip_code` (an identifier, loaded as Text)
- **dim_security:** `expense_ratio_bps` (a rate, and blank for non-ETFs)
- **dim_date:** `date_id`, `year`, `quarter`, `month`, `week_of_year`, and the `is_*` flags (calendar labels and filters)
- **All dimensions:** the `*_id` keys

---

## Part D: Power BI model (summary)

Model saved as `powerbi/hw05.pbix` (21.8 MB), screenshot `powerbi/model_view.png`, row-count check `powerbi/row_counts.png`.

**Load and types.** All eight CSVs were loaded through Power Query (Transform Data) and the queries renamed to the handout table names. Every column type was checked in the Advanced Editor: keys are Whole Number (`fact_transactions[security_id]` stays Whole Number with blanks on cash rows); `date`, `fee_date`, `snapshot_date`, `txn_date` and `client_since` are Date; amounts, AUM, prices, rates and returns are Decimal Number; `is_active` and `is_etf` are True/False; the `is_*` flags are Whole Number. The one type Power BI guessed wrong was `dim_client[zip_code]` (Whole Number, which turned `03897` into `3897`). It was changed to Text by replacing the original type step, so leading zeros come straight from the CSV.

**Relationships.** Power BI auto-detected 11 relationships but made the wrong advisor choice: it kept `dim_client → dim_advisor` active and set all three `fact → dim_client` relationships inactive. I reversed this (see E(b)) and added the three date relationships, which auto-detect missed. All relationships are many-to-one with single cross-filter direction.

| From (many) | To (one) | Active? |
|---|---|---|
| fact_fees[client_id] | dim_client[client_id] | Yes |
| fact_fees[advisor_id] | dim_advisor[advisor_id] | Yes |
| fact_fees[fee_date] | dim_date[date] | Yes |
| fact_portfolio_snapshot[client_id] | dim_client[client_id] | Yes |
| fact_portfolio_snapshot[advisor_id] | dim_advisor[advisor_id] | Yes |
| fact_portfolio_snapshot[benchmark_id] | dim_benchmark[benchmark_id] | Yes |
| fact_portfolio_snapshot[snapshot_date] | dim_date[date] | Yes |
| fact_transactions[client_id] | dim_client[client_id] | Yes |
| fact_transactions[advisor_id] | dim_advisor[advisor_id] | Yes |
| fact_transactions[security_id] | dim_security[security_id] | Yes |
| fact_transactions[txn_date] | dim_date[date] | Yes |
| dim_security[benchmark_id] | dim_benchmark[benchmark_id] | Yes |
| dim_client[advisor_id] | dim_advisor[advisor_id] | **No** (inactive, see E(b)) |

`dim_date` is marked as the date table on `date` (Power BI validated it: unique, continuous dates).

**Row counts reconcile.** A card for each table showing the count of its primary key matches the handout exactly: dim_date 1,827 · fact_fees 122,197 · fact_transactions 298,572 · dim_security 500 · dim_client 2,500 · dim_advisor 25 · dim_benchmark 8 · fact_portfolio_snapshot 129,547 (`row_counts.png`; Power BI displays these as 1.827K, 122.197K and so on).

Conformed dimensions are named at the start of Part E.

---

## Part E: Relationships and design questions

**Conformed dimensions.** `dim_client`, `dim_advisor` and `dim_date` are conformed: all three facts use them with the same meaning, so one slicer on any of them filters fees, snapshots and transactions consistently. `dim_benchmark` is **shared but not conformed**: it reaches snapshots directly (the *client portfolio's* benchmark) and transactions through `dim_security` (the *security's* benchmark), so the same benchmark means different things for the two facts (see d). `dim_security` is used only by transactions. No foreign key was left out of the model; the only date-like column not joined is `dim_client[client_since]`, which is an attribute, not a key (Part A).

**(a) Blank `security_id`.** The 101,528 transactions with no `security_id` are exactly the Deposit, Withdrawal and Advisory Fee rows: every blank is one of those types, and every row of those types is blank. These rows move cash into, out of, or out of the account to pay the firm, so no security is involved. Their `shares` and `price` are blank for the same reason. It is not a defect: it is the honest structure of the data, and filling it with a fake "cash" security would put made-up rows into the dimension. In Power BI these rows appear as a `(Blank)` member when transactions are sliced by `dim_security`, which is expected. Because there are zero orphans, `(Blank)` never means a broken key here.

**(b) `advisor_id` in four places.** I kept the three **fact → dim_advisor** relationships active and made **dim_client → dim_advisor inactive**. Power BI allows only one active path between two tables, and keeping both would give dim_advisor two routes to each fact (directly, and through dim_client). This is a design choice, not something the data proves: today the fact `advisor_id` equals `dim_client[advisor_id]` on every row of all three facts (checked), so both paths give identical results now. The choice rests on what each column is for. A fact row carries its own `advisor_id`, so if the source system stamps the advisor at the time of the event, that path keeps past fees and AUM credited to the advisor who earned them, while the client path would move all history to whoever holds the client today. The data shows the source does not yet do this consistently: the 2,410 transactions flagged `is_post_departure_txn` happened after their advisor left, yet still carry the departed advisor's ID. The fact path credits those rows to the departed advisor, and the client path would too, so neither path fixes them; they are kept visible by the flag rather than hidden. The fact path also keeps the model a pure star, and it is the one that will stay correct if the source starts recording reassignments. One side effect: because `dim_client → dim_advisor` is inactive, advisor fields do not filter a visual built only from `dim_client` columns (for example a client list by advisor region); that needs a fact in the visual or USERELATIONSHIP. The inactive relationship can still be switched on in a measure with USERELATIONSHIP for "current book of business" questions.

**(c) Joining on `date`, not `date_id`.** I joined all three facts on `dim_date[date]`. The facts store calendar dates (`2023-12-16`), not the integer `date_id`, so there is nothing in the facts for `date_id` to match: a Date column cannot join to a Whole Number key, and Power BI would either refuse the relationship or leave every fact row unmatched. `date` is unique in dim_date (an alternate key), and dim_date is a continuous daily calendar from 2020-01-01 to 2024-12-31. Every fact date falls inside it (fees and snapshots run to 2024-12-01, transactions to 2024-12-30), and all three date relationships have zero orphans, so every fact row finds its day. Both sides are set to the Date type (not Date/Time) so the values match exactly. `dim_date` is then marked as the date table on `date` for time intelligence.

**(d) Star or snowflake.** Two links run from one dimension to another: `dim_client → dim_advisor` and `dim_security → dim_benchmark`.
- **dim_client → dim_advisor:** kept but **inactive**, because the facts already reach advisors directly (see b). The core facts therefore stay a star.
- **dim_security → dim_benchmark:** kept **active**, which makes a small snowflake branch. Transactions have no benchmark column of their own, so this is the only way to group trades by benchmark (e.g. buys of securities tracked against the S&P 500). It creates no ambiguity: dim_benchmark reaches snapshots directly and transactions only through securities, so each fact has one path. The caveat, and the reason dim_benchmark is shared but not conformed, is that a benchmark slicer means different things for the two facts: the *client's portfolio* benchmark for snapshots, and the *security's* benchmark for transactions. Report titles must make that clear. Snapshots use only 3 benchmarks (1, 3, 8) and securities use 6.

---

## Part F: Reflection

1. **Fees:** *"How much fee revenue did each region earn by quarter in 2024, split by fee type?"*
   **One visual, no DAX.** `amount` is fully additive, so a matrix with dim_advisor[region] on rows, dim_date[quarter] on columns, fee_type as a legend and SUM(amount) answers it directly.

2. **Portfolio snapshot:** *"What was each advisor's total AUM at the end of each quarter, and how did it grow over 2024?"*
   **Not without DAX.** `aum` is semi-additive. A monthly line chart works because each month has one snapshot per client, but at the quarter or year level Power BI sums three or twelve monthly balances and overstates AUM 3–12×. A closing-balance measure (LASTDATE / CLOSINGBALANCEQUARTER) is needed. Two schema issues make this worse: snapshots are taken on the **1st** of the month, so dim_date's `is_month_end` / `is_quarter_end` flags never match a snapshot row, and the "end of Q4" balance actually lives on the next year's Jan 1 row (which does not exist for 2024). **Fix:** record snapshots as of month-end (or add an `as_of_period` column), and add an `is_period_end_snapshot` flag so a plain filter returns one balance per period.

3. **Transactions:** *"What was each advisor's net new money (deposits minus withdrawals) per month?"*
   **Not without DAX.** Every `amount` is positive, so SUM(amount) adds deposits and withdrawals together. You need a measure that subtracts withdrawals (CALCULATE with a txn_type filter), or two visuals compared by eye. **Fix:** add a small `dim_txn_type` dimension with a `cash_sign` for each type's effect on the account's cash (+1 Deposit/Sell/Dividend, −1 Withdrawal/Buy/Advisory Fee) and a category (trade / income / external flow / fee), or store a signed `net_amount` in the fact. Net flows then become a plain sum filtered to external flows.

**Honest assessment:** the model answers "how much" questions on additive amounts (fees, gross deposits, trade volume) cleanly. Anything about balances over time, average returns, or net cash flow needs DAX in Assignment 6, because of semi-additive AUM, non-additive percentages and unsigned transaction amounts. It also cannot answer "what does a client hold today": there is no holdings fact, and reconstructing positions from transactions would need a running total of signed shares.
