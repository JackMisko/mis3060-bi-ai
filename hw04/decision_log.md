# HW4 Decision Log: Wildcat Capital Data Cleaning

Written **before** `02_clean.py`. Each entry is an instruction for the cleaning code. Evidence numbers come from `reports/dq_summary_raw.csv` (check IDs `Axxx`) or from follow-up queries on the raw files in `data/raw/`.

Decisions used: **convert** (same value, correct type/format) · **standardize** (same meaning, one spelling) · **fill** · **flag** (add a 0/1 column, keep the value) · **quarantine** (move the row to `data/audit/quarantine_*.csv`) · **leave as is**.

No values are filled by inference anywhere in this log. Where a value is wrong but the right value cannot be proven from other columns or tables, the row is flagged, not repaired.

---

## Part 1: Defects to fix

### D01: `fact_transactions.security_id` stored as decimal text

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.security_id` |
| **Evidence** | 197,175 of 197,175 non-blank values are written like `'45.0'` (A003, A004). As text, **0%** join to `dim_security.security_id` (`'45'`) (A008). After numeric normalisation, 100% join and 0 are true orphans (A026). 0 values have a non-zero decimal part. |
| **Dimension violated** | Validity, Referential Integrity |
| **Decision** | **Convert**: `'45.0'` → `'45'` (integer text). Blank stays blank (see L01). |
| **Justification** | The key is an integer ID that was exported through a float column. Nothing about the security changes. Without this, every Buy/Sell/Dividend row loses its security, asset class and benchmark in any text join. |
| **Risk** | Low. If any key had a real fractional part, it would be silently truncated. The code asserts `v == round(v)` before converting, and asserts a 100% match to `dim_security` afterwards. |

### D02: `return_ytd` stored as percent strings

| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` |
| **Evidence** | 300 values look like `'9.28%'` and fail a numeric parse (A002). Divided by 100, **300 of 300** reconcile to `benchmark_return_ytd + active_alpha_ytd` within 0.00005 (A022). The largest gap is 0.00005, which is the rounding from two-decimal percents. |
| **Dimension violated** | Validity, Consistency |
| **Decision** | **Convert**: strip `%`, divide by 100. |
| **Justification** | The other 129,247 rows store returns as decimals. A `%` string makes the whole column text in Power BI, and a naive strip would make `9.28` mean 928%. The reconciliation shows that /100 is the right fix, so this is verified against other columns, not assumed. |
| **Risk** | If the figure were already a decimal with a stray `%`, dividing would understate it 100×. Ruled out because 0 of 300 reconcile *without* the /100. After the fix, assert that all 300 reconcile within 0.0001. |

### D03: Scientific notation in return columns

| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` (135 values), `active_alpha_ytd` (756 values) |
| **Evidence** | Values like `'9.9e-05'` and `'-1.9e-05'` (profile `sci_notation` column). They parse fine in Python but make the column's format mixed (`mixed_format = yes`). All values have at most 6 decimal places. |
| **Dimension violated** | Consistency |
| **Decision** | **Standardize** formatting: write every value as a plain decimal with up to 6 places (`0.000099`). The numeric value is unchanged. |
| **Justification** | Some BI tools and Excel locales read `e-05` as text or as a different number. One format per column is the minimum for Assignment 5. |
| **Risk** | Very low. Rounding loss is impossible at 6 places because no source value has more. Assert that the parsed value before equals the parsed value after for every row. |

### D04: `dim_client.state` full names

| Field | Entry |
|---|---|
| **Table / column** | `dim_client.state` |
| **Evidence** | 78 values fail the USPS-code list (A001): Pennsylvania 25, Florida 15, New York 14, New Jersey 13, California 5, Illinois 4, Texas 2. The other 2,447 rows use 2-letter codes, and all 7 target codes (PA, FL, NY, NJ, CA, IL, TX) already exist in the column. 1 of the 78 is on a duplicate client row (D06). |
| **Dimension violated** | Consistency, Validity |
| **Decision** | **Standardize** with an explicit 7-entry name → code map. Runs after D06, so **77** rows change. |
| **Justification** | Same state, two spellings. Left as is, a state slicer shows "PA" and "Pennsylvania" as different regions and splits client counts and AUM. |
| **Risk** | Minimal; the map is explicit, not fuzzy. Assert that every value afterwards is in the USPS list and that no other value changed. |

### D05: Negative shares on Buy rows

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.shares` |
| **Evidence** | 836 rows have `shares < 0` (A005), **all** with `txn_type = Buy`. Every one has a positive `amount` and `price`, and `amount = |shares| × price` within $0.01 for all 836 (A024). Every other Buy/Sell/Dividend row has positive shares, with direction carried by `txn_type`. |
| **Dimension violated** | Validity (sign rule), Consistency |
| **Decision** | **Convert**: `shares = abs(shares)` on those 836 rows. |
| **Justification** | The table's sign convention is quantity > 0, with direction from `txn_type`. A negative Buy quantity would reduce share totals and position calculations. The amount reconciliation shows that only the sign is wrong, not the size. |
| **Risk** | If these were really sells mislabelled as Buy, `txn_type` would be the wrong field and we'd be fixing the wrong one. That can't be proven from this data, so `txn_type` is left unchanged. Assert that afterwards 0 shares are ≤ 0 and that `amount = shares × price` within $0.01 on all security rows. |

### D06: Duplicate clients with mistyped last names

| Field | Entry |
|---|---|
| **Table / column** | `dim_client`, all columns |
| **Evidence** | 50 rows (25 pairs) are identical on every column except `client_id` and `last_name` (A010). The copies are `client_id` 2501–2525. Each copy's last name is a one-letter edit of the original: 23 are missing the final letter (`Lopez` → `Lope`) and 2 have an extra letter (`Lee` → `Leen`, `Pace` → `Pacen`). **0** rows in any fact table reference IDs 2501–2525. The originals (IDs ≤ 2500) have full fact history. |
| **Dimension violated** | Uniqueness, Accuracy |
| **Decision** | **Quarantine** the 25 copies → `data/audit/quarantine_dim_client_duplicates.csv`, with the original's `client_id` and last name added as trace columns. |
| **Justification** | They would inflate client counts by 1% and add 25 clients with no AUM, fees or snapshots, which skews averages such as "AUM per client". The IDs, the missing fact history and the one-character name edits all point to re-keyed copies. |
| **Risk** | If any were real clients, they'd be dropped from client counts. That's low risk because they have no activity to lose, and the quarantine file keeps them recoverable. Assert 2,525 = 2,500 clean + 25 quarantined, and that client_id stays unique. |

### D07: Orphan transactions (copies with a fake client_id)

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.client_id` |
| **Evidence** | 200 rows reference `client_id`s not in `dim_client` (A006, A007), with IDs from 2702 to 3192. All 200 are the last rows of the file (`txn_id` 298573–298772). **200 of 200** are identical to a real transaction on all other 8 columns (same advisor, security, date, type, shares, price, amount), which is why 400 rows show as near-duplicates (A015). |
| **Dimension violated** | Referential Integrity, Uniqueness |
| **Decision** | **Quarantine** → `data/audit/quarantine_fact_transactions_orphans.csv`, with the `txn_id` of the matching real row added. |
| **Justification** | They can't be attributed to any client. Because each duplicates a real transaction, keeping them double-counts flows, and re-pointing them to the real client would double-count exactly. Either way trade and flow totals would be overstated. |
| **Risk** | If dim_client were missing 200 real clients, we would drop real activity. That's unlikely: the matched-copy evidence covers every row, and the rows stay in quarantine. Assert 298,772 = 298,572 clean + 200 quarantined, and 100% client match afterwards. |

### D08: Blank `risk_profile`

| Field | Entry |
|---|---|
| **Table / column** | `dim_client.risk_profile` |
| **Evidence** | 76 blanks (A009); 1 is on a duplicate row (D06), so **75** remain. All 75 clients are on benchmark 3 (60/40 Blend) in every snapshot, and benchmark 3 maps only to *Balanced* among known profiles (A027). Tiers: Retail 49, HNW 18, UHNW 9. |
| **Dimension violated** | Completeness |
| **Decision** | **Standardize** blank → `'Unknown'`. **Do not fill** with `'Balanced'`. |
| **Justification** | Risk profile is a suitability attribute: it records what the client agreed to. The benchmark evidence is circular. A 60/40 blend is the natural default a system assigns when no profile exists, so "on benchmark 3" may be a *result* of the missing profile, not proof of it. `'Unknown'` keeps the gap visible on a slicer instead of hiding it in a blank. |
| **Risk** | Reports that group by risk profile get a small "Unknown" bucket (3% of clients). The opposite risk (filling it in) is worse: compliance could read an unverified "Balanced" as the client's consent. Assert 0 blanks and exactly 75 `'Unknown'` afterwards. |

### D09: Transactions after a client left

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.txn_date` vs `dim_client.is_active` and `fact_portfolio_snapshot` |
| **Evidence** | 175 clients are inactive. Their snapshots stop between 2022-12 and 2023-11, while all 2,325 active clients run to 2024-12. 2,410 transactions for 131 of those 175 clients are dated after the end of their last snapshot month (A018), totalling about $127.5M across all types (Buy 689, Sell 482, Dividend 439, Advisory Fee 284, Deposit 278, Withdrawal 238). **0** fees are charged after departure. |
| **Dimension violated** | Consistency, Accuracy/Plausibility |
| **Decision** | **Flag**: add `is_post_departure_txn` (0/1). Keep the rows and values. |
| **Justification** | Either the departure (snapshot end) is wrong or the transactions are. The data can't tell which. The fee table stops cleanly, which suggests the transactions are the anomaly, but deleting $127M of money movement would hide exactly what a compliance review needs to see. A flag lets the committee include or exclude these rows. |
| **Risk** | Reports that don't filter on the flag will include activity on closed accounts. This is documented in `README_clean.md`. Assert that the flag count is 2,410. |

### D10: Extreme YTD returns

| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` (and `active_alpha_ytd`, which is derived from it) |
| **Evidence** | 977 rows have \|return_ytd\| > 100% (A013), across 144 clients, with a maximum of +9,467%. 498 rows are below −90%. On **all 104,823** testable rows, `return_ytd = aum / prior-December aum − 1` within 0.001 (A023). |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | **Flag**: add `is_return_suspect` = 1 where \|return_ytd\| > 1. **Do not change** the values. |
| **Justification** | The values aren't typos. They're computed exactly as the column defines them, but that definition is AUM change *including deposits and withdrawals*, not investment performance. A client who deposits $50k into a $10k account shows a "+400% return". The real return can't be rebuilt without daily flows and a time-weighted method, so overwriting would invent data. The flag marks the rows where the definition makes the number misleading. |
| **Risk** | Rows under 100% are also contaminated by flows, just less visibly. The flag is a floor, not a full fix, and this is stated as a known limitation. Any "average return" or "alpha" measure in Assignment 5 must exclude flagged rows or carry a caveat. Assert that the flag count is 977. |

### D11: AUM stuck at exactly $1,000

| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.aum` (420 rows, 92 clients); `fact_fees.aum_basis` (386 rows) |
| **Evidence** | Exactly 1,000.00 is the column minimum in both tables (A012, A014), and no value is below it. A typical client goes $16,705 → $1,000 → $1,000 → $1,013, which reads as a balance clipped at a floor rather than a real balance. 249 of the 420 rows also have \|return\| > 90%. Fee `aum_basis` equals the snapshot `aum` for the same client-month on every fee row, so the fee table inherits the floor. |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | **Flag**: add `is_aum_floor` (0/1) to both tables. Keep the values. |
| **Justification** | The real balance isn't recoverable from any table. The fee amounts reconcile to the $1,000 basis, so $1,000 is what the firm actually billed on. Changing it would break that reconciliation. |
| **Risk** | AUM totals may slightly overstate tiny accounts (or understate them, if the true value was higher). The effect on firm AUM is immaterial: 420 × $1,000 = $0.42M. Assert flag counts of 420 and 386. |

### D12: Trades dated on weekends

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.txn_date` vs `dim_date.is_trading_day` |
| **Evidence** | 40,649 of 143,311 Buy/Sell rows (28.4%) fall on a non-trading day (A019). Trades are spread evenly over all seven days (about 20,200–20,700 each, Saturday and Sunday included). 28.4% is almost exactly 2/7. |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | **Leave as is**, and document as a known limitation. |
| **Justification** | An even 2/7 split means the dates were generated without a calendar. It's a property of the whole column, not of individual bad rows, so a row-level flag on 28% of trades carries no signal. Moving trades to the next business day would invent dates, and the monthly reporting grain (snapshots, fees) is unaffected. |
| **Risk** | Daily or weekday trade analysis is unreliable, and Assignment 5 should report trades by month, not day. If the committee wants daily analysis, this decision should be revisited. |

---

## Part 2: Looks odd, but is legitimate structure (leave as is)

| # | Table / column | Evidence | Dimension questioned | Decision | Justification | Risk |
|---|---|---|---|---|---|---|
| L01 | `fact_transactions.security_id`, `shares`, `price` | 101,597 blanks in each (A025). The count equals Deposit 35,981 + Withdrawal 29,850 + Advisory Fee 35,766 exactly, and the row rule "security fields present ⇔ security txn type" passes on all 298,772 rows. | Completeness, RI | **Leave as is** (keep blank) | Cash movements have no security. Filling 0 or a dummy security would create fake positions. Power BI keeps `security_id` as Whole Number with blanks. | A careless inner join to `dim_security` drops all cash rows. Documented in `README_clean.md`. |
| L02 | `dim_security.sector`, `expense_ratio_bps` | 219 blank sectors = the 219 ETFs; 281 blank expense ratios = the 281 non-ETFs (A020, A021, both 0 exceptions). | Completeness | **Leave as is** | ETFs span sectors; single stocks/bonds have no expense ratio. The blanks mean "not applicable", not "missing". | Low. A sector chart shows ETFs as "(Blank)"; README suggests labelling it "ETF / multi-sector" in the BI layer, not the data. |
| L03 | `dim_advisor.certifications` | 6 advisors have the literal value `'None'` (A040: allowed-tokens check passes). | Completeness | **Leave as is** | `'None'` is a real answer ("no certification"). Default `pd.read_csv` would turn it into NaN, which is why the brief requires `keep_default_na=False`. | Low. A tool that reads `'None'` as null would count these advisors as unknown. README lists it. |
| L04 | `fact_transactions` near-duplicates on `amount` | 1,050 rows match another row on everything except `txn_id` and `amount` (A017): Deposit 411, Advisory Fee 377, Withdrawal 262. All are cash rows. | Uniqueness | **Leave as is** | Two deposits from the same client on the same day with different amounts are normal. Different amounts make them distinct events, not copies. | If some really were double entries with a typo'd amount, flows would be overstated. There's no evidence for that: no amount-to-amount pattern. |
| L05 | Near-duplicates on dates | 14 `fact_transactions` rows (A016) and 2 `fact_fees` rows (A011) match except for the date. Examples: client 1060 Advisory Fee $306.32 on 2020-03-02 and 2022-11-10; client 1169's fee on the $1,000 floor basis in 2020-06 and 2024-04. | Uniqueness | **Leave as is** | Recurring fees of the same amount in different months, years apart, are expected, especially on a floored basis. | Very low. |
| L06 | `dim_client.zip_code` | All 2,525 values are 5-digit text, including leading zeros (e.g. `'03897'`). | Validity | **Leave as is**; README says load as **Text** | Correct as text. Numeric parsing would drop the zero (`3897`). | Breaks only if loaded as a number. Called out in README for Power BI. |
| L07 | `dim_security.name` | 3 names appear twice (e.g. *Jones Inc Fund*: OLAB / Alternative and YXPS / Fixed Income). Tickers and IDs are unique. | Uniqueness | **Leave as is** | Fund families reuse names across share classes and asset classes. The key is `security_id` / `ticker`, and both are unique. | Low. A visual grouped by name would merge two securities, so use ticker. |
| L08 | `fact_transactions` Dividend rows | Dividend `amount = shares × price` at market price (median dividend $48.8k vs median Buy $47.9k), so each "dividend" equals the full position value. | Accuracy/Plausibility | **Leave as is**; known limitation | Implausible (real yields are about 1–5%), but the right figure can't be derived from any table. It reconciles internally, so it isn't a row-level typo. | Income totals are overstated by orders of magnitude, so they shouldn't be used in reporting until the source is confirmed. Listed in README and the report. |
| L09 | `dim_benchmark` usage | Snapshots use only benchmarks 1, 3 and 8; securities use 1, 2, 3, 4, 5 and 7; benchmark 6 is unused by any table. | Referential Integrity | **Leave as is** | A dimension may hold members no fact uses. Every foreign key resolves (all RI checks pass). | None. |
| L10 | `dim_client.zip_code` vs `state` | Zip prefixes don't match states (e.g. a PA client with `75726`, a Texas range). | Accuracy | **Leave as is**; known limitation | There's no reference table to check against, and either column could be the wrong one. Region analysis uses `state`. | Geographic analysis by zip is unreliable. |

---

## Part 3: Cleaning order (for `02_clean.py`)

The order matters because later steps rely on earlier ones:

1. **D06: quarantine duplicate clients.** First, so D04 and D08 count only real clients (77 state fixes, 75 Unknowns) and RI checks run against the final `dim_client`.
2. **D07: quarantine orphan transactions.** Before any transaction-level fix, so 200 copies aren't "repaired" and then dropped.
3. **D01: convert `security_id`.** Before D05 and the reconciliations, which join to `dim_security`.
4. **D05: absolute value of negative shares.** Assert `amount = shares × price` on all security rows.
5. **D02 then D03: returns to numeric, then standardize the format.** D02 must run before D10, because the return flag needs parsed returns.
6. **D04: state codes.** **D08: `'Unknown'` risk profile.**
7. **Flags, after all value fixes:** D09 `is_post_departure_txn`, D10 `is_return_suspect`, D11 `is_aum_floor`.
8. **Final asserts:** for every table, raw rows = clean rows + quarantined rows; every foreign key matches 100% (blank `security_id` on cash rows excepted); column names are unchanged except for the added flag columns.

**Expected row counts after cleaning**

| Table | Raw | Clean | Quarantined |
|---|---:|---:|---:|
| dim_client | 2,525 | 2,500 | 25 |
| fact_transactions | 298,772 | 298,572 | 200 |
| all other 6 tables | unchanged | unchanged | 0 |

**Flag columns to add**
- `fact_transactions.is_post_departure_txn`: expect 2,410
- `fact_portfolio_snapshot.is_return_suspect`: expect 977
- `fact_portfolio_snapshot.is_aum_floor`: expect 420
- `fact_fees.is_aum_floor`: expect 386
