# HW4: Cleaning the Wildcat Capital Data

MIS3060 Business Intelligence with AI. Brief: [HW04_Data_Cleaning.md](HW04_Data_Cleaning.md)

## Folder structure

```
hw04/
├── HW04_Data_Cleaning.md       assignment brief
├── README.md                   this file
├── decision_log.md             Part B: 12 defects, 10 legitimate-structure decisions, cleaning order
├── scripts/
│   ├── 01_profile.py           Part A: generic profiler + four groups of checks
│   ├── 02_clean.py             Part C: applies the decision log; writes clean tables + audit trail
│   └── 03_validate.py          Part D: RI, rules, reconciliations, IQR and scorecard on raw AND clean
├── data/
│   ├── raw/                    the eight source CSVs (not committed; copy them in)
│   ├── clean/                  the eight cleaned tables (raw columns + 4 flag columns)
│   │   └── README_clean.md     row counts, relationships, BI column types, flags, known limitations
│   └── audit/
│       ├── cleaning_log.csv                          one row per decision (24 rows)
│       ├── value_changes.csv                         one row per changed cell (199,222 rows), old -> new
│       ├── quarantine_dim_client_duplicates.csv      25 duplicate clients removed from dim_client
│       └── quarantine_fact_transactions_orphans.csv  200 orphan copies, with the real txn_id each copies
└── reports/
    ├── profile_raw.csv             one row per table x column (75 rows)
    ├── dq_summary_raw.csv          one row per check, tagged ERROR / WARN / INFO / PASS
    ├── ri_results.csv              13 relationships x 2 stages: match rate, orphans, null-key rate (26 rows)
    ├── rule_checks.csv             48 rules x 2 stages: rows evaluated / failed, failing examples (96 rows)
    ├── reconciliations.csv         9 recomputed-vs-stored checks x 2 stages (18 rows)
    ├── outliers_iqr.csv            IQR fences on 4 columns x 2 stages, flagged rows by client tier (8 rows)
    └── data_quality_scorecard.csv  8 tables x 2 stages, five quality percentages (16 rows)
```

Part E (the business report) will be added in a later commit.

## How to run

From inside `hw04/`, with the eight raw files in `data/raw/`:

```
python scripts/01_profile.py                              # full audit of all eight tables (~100 s)
python scripts/01_profile.py data/raw/dim_benchmark.csv   # generic profile of any single CSV
python scripts/02_clean.py                                # clean all eight tables into data/clean/ + data/audit/ (~1 min)
python scripts/03_validate.py                             # validate raw and clean, write the 5 Part D reports (~45 s)
```

`02_clean.py` never writes to `data/raw/`. It stops with an `AssertionError` if any count differs from the
decision log, so a successful run ends with `all final asserts passed`.

`03_validate.py` reads both `data/raw/` and `data/clean/` and writes only to `reports/`. After writing the reports it
asserts that the clean stage has no orphan keys, unique dimension keys, no rule failures and no reconciliation failures.

Requires Python 3.12 with pandas and numpy.

## Part A results

251 checks: **8 ERROR / 11 WARN / 8 INFO / 224 PASS**. Headline findings:

| Finding | Rows | Severity |
|---|---:|---|
| `fact_transactions.security_id` stored as `'45.0'` (breaks text joins) | 197,175 | ERROR |
| `return_ytd` stored as `'%'` strings | 300 | ERROR |
| `dim_client.state` full names instead of codes | 78 | ERROR |
| Negative `shares` (amount reconciles only if sign ignored) | 836 | ERROR |
| Orphan `client_id` in `fact_transactions` (all 200 are copies of real rows, see near-duplicates) | 200 | ERROR |
| Near-duplicate clients (25 pairs differing only in `last_name`) | 50 | WARN |
| Blank `risk_profile` | 76 | WARN |
| Transactions after an inactive client's last snapshot month | 2,410 | WARN |
| \|return_ytd\| > 100% | 977 | WARN |

## Claude Code review findings: Part A

Claude Code reviewed the Claude Desktop draft of `01_profile.py` before the first commit.

| # | Finding | Type | Action |
|---|---|---|---|
| 1 | `_benchmark_vs_risk` treated blank `risk_profile` as its own group, so 3,942 snapshot rows were compared against their own "dominant" benchmark and always passed | bug | **Fixed.** Blank profiles are excluded (125,605 rows now evaluated). Added an INFO check showing every blank-profile client is on benchmark 3, which only *Balanced* maps to (evidence for Part B) |
| 2 | `mixed_format` treated a minus sign as a different format, so `benchmark_return_ytd` and `shares` were flagged as mixed | bug | **Fixed.** The sign is ignored for this flag; only `return_ytd` (`%`) and `active_alpha_ytd` (scientific notation) remain mixed |
| 3 | RI checks tested only non-blank keys; a blank FK would pass silently, with its count buried in the `example_keys` text | risk | **Fixed.** FK and fact-date columns are marked `required` (blank = WARN). The null-key rate is its own INFO finding: 101,597 blank `security_id`, all legitimate cash rows (Deposit / Withdrawal / Advisory Fee) |
| 4 | Some rules could count an unparseable value as a pass or a failure (blank `client_since` compared as text, missing `aum`, unparseable `month` / `fee_date`) | risk | **Fixed.** These rules only evaluate rows whose inputs parse. No counts changed (the current data has no such values) |
| 5 | RI normalisation `astype("Int64")` crashed on a non-integer key such as `'45.5'` | risk | **Fixed.** Non-integers become NA and are reported as true orphans (tested with synthetic keys) |
| 6 | One issue counted by several ERRORs: the same 197,175 cells in A003 / A004 / A008, the same 200 rows in A006 / A007, the same 836 in A005 / A024. "8 ERROR" is about 5 separate issues | style | **Not fixed (documented).** Each check answers a different question (does it parse, is it a `.0` float, does it join). Kept separate so Part D can show each one clearing |
| 7 | `dim_date` row rules didn't check `is_quarter_end` or `is_year_end` against the date | gap | **Fixed.** Two rules added; both pass |
| 8 | A byte-order mark in a CSV would rename the first column | risk | **Not fixed.** None of the eight files has one |
| 9 | Runtime: `shape_of` ran twice per column, and the near-duplicate loop recomputed the exact-duplicate mask on every pass | style | **Fixed.** 112 s to 99 s |

Severity notes from the review (no code change):

- **Buy/Sell on non-trading days (40,649 of 143,311 = 28.4%):** close to 2/7, so trade dates look evenly spread over all seven days. That's a property of the whole column, not of individual bad rows. Kept as WARN; handled in the decision log.
- **|return_ytd| > 100% (977):** `return_ytd` equals AUM change since the prior December, including deposits, on all 104,823 rows that can be tested. So large values follow from how the column is defined and are not entry errors.
- **Near-duplicates differing only in `client_id` (400):** these are exactly the 200 orphan transactions plus the 200 real rows they copy.

## Claude Code review findings: Part C

Claude Code reviewed `02_clean.py` against `decision_log.md` and the raw file formats (grep/awk only, no Python) before the
first run was committed. None of the fixes changed a count. The rerun gave the same 225 quarantined rows,
199,222 changed cells and flag counts, and all new asserts passed.

| # | Finding | Type | Action |
|---|---|---|---|
| 1 | The decision log's expected counts (D06 25, D07 200, D02 300, D04 77, D08 75, flags 2,410 / 977 / 420 / 386) were never asserted, and the existing asserts couldn't fail (`len(kept) + mask.sum() == n_before` always holds after a mask split) | gap | **Fixed.** An `EXPECTED` dict + `check_count()` asserts every step's rows affected; D06 also asserts the copy IDs are exactly 2501-2525 |
| 2 | Nothing proved that *only* the decided cells changed. A cell changed outside `record_changes` would go unnoticed | gap | **Fixed.** `final_checks` compares every original column of every kept row against raw. Per table/column, the changed cells must equal the `value_changes.csv` entries exactly (199,222), and none is logged twice |
| 3 | D01 "no fractional part" assert was vacuous: the `^\d+\.0+$` selector already guaranteed an integer, so `45.5` would slip past | bug | **Fixed.** Selects `N.d`, asserts every non-blank `security_id` has that shape, then asserts it is integral |
| 4 | D02 never ran the log's key check ("0 of 300 reconcile *without* /100"), and the "before" failure count skipped the 300 `%` rows (NaN > tol is False) | gap | **Fixed.** Asserts 0 of 300 reconcile with the `%` merely stripped; unparsable rows now count as failures before (300 -> 0) |
| 5 | `README_clean.md` hard-coded "836 Buy rows"; the clean table changed 835 (1 left with the D07 orphans) | bug (doc) | **Fixed.** Uses the computed D05 count |
| 6 | `README_clean.md` lacked L02 (blank ETF sector), L07 (group by ticker, not name) and a Text type for `account_type` / `primary_account_type` (`529` auto-types as a number) | gap | **Fixed.** Limitations 8-9 and the type row added |
| 7 | D09 compares dates as text, which is only correct for zero-padded ISO dates. Not asserted | risk | **Fixed.** Asserts `txn_date`, `snapshot_date`, `fee_date` all match `YYYY-MM-DD` first |
| 8 | `to_csv` defaults to CRLF line endings on Windows; raw files are LF | risk | **Fixed.** `lineterminator="\n"` on every `to_csv` |
| 9 | Quarantine files are written during D06/D07, before the final asserts; a failed rerun would leave new quarantine files next to stale clean files | risk | **Not fixed.** A refactor that only matters for a partial failed rerun; it adds no proof. The run log shows the asserts passed |
| 10 | `drop_duplicates(keep="first")` would silently pick one twin if an orphan matched several real rows, so the trace `txn_id` could be wrong | risk | **Fixed.** Asserts each orphan matches exactly one real transaction (0 multi-matches) |
| 11 | `decision_log.md` D07 says "all other 8 columns" but lists 7 (the code correctly uses 7) | nit | **Not fixed.** The log was committed as Part B; editing it after the code exists would muddy the history |

Count differences that are **not** defects: D01 converts 197,044 values (audit: 197,175) and D05 converts 835 (audit: 836).
The audit counted raw rows. The cleaner counts after D07, which quarantines 131 `'N.0'` IDs and 1 negative share on orphan rows.
Both overlaps are printed and logged.

## Part D results

`03_validate.py` runs the same checks on raw and clean: one reusable `check_referential_integrity()` on 13 relationships,
48 rules, 9 reconciliations and IQR fences on 4 columns.

| Check | Raw | Clean |
|---|---|---|
| Referential integrity | `client_id` 99.933% (200 orphans); `security_id` **0.000%** (197,175 orphans, `'45.0'` vs `45`); other 11 at 100% | all 13 at 100% |
| Null-key rate, `fact_transactions.security_id` | 34.00% | 34.00% (cash rows, legitimate) |
| Rules (48) | 2 failing: `state` 78, `shares` 836 | 0 failing |
| Reconciliations (9) | R3 amount = shares x price fails 836; the other 8 pass | all 9 pass |

Scorecard, raw -> clean, for the three tables that changed (the other five are 100% on every measure in both stages):

| Table | Completeness | Key uniqueness | Type validity | Rule pass | Referential match |
|---|---|---|---|---|---|
| `fact_transactions` | 100 -> 100 | 99.866 -> **100** | 91.730 -> **100** | 99.947 -> **100** | 81.95 -> **100** |
| `dim_client` | 99.785 -> 99.786 | 98.020 -> **100** | 100 -> 100 | 99.612 -> **100** | 100 -> 100 |
| `fact_portfolio_snapshot` | 100 -> 100 | 100 -> 100 | 99.982 -> **100** | 100 -> 100 | 100 -> 100 |

% rule pass is row-weighted: failed evaluations / all evaluations across the table's rules. For example,
`dim_client` raw = 1 - 78 / 20,124 = 99.612%.

**`dim_client` completeness stays at ~99.79% on purpose.** The 76 blank `risk_profile` values were standardized to the
explicit marker `'Unknown'` (D08), not filled in. The scorecard counts `'Unknown'` as still missing, so standardizing
a blank doesn't count as filling it.

**IQR outliers (clean):** `fact_transactions.amount` 7,221 flagged, `fact_portfolio_snapshot.aum` 13,261,
`active_alpha_ytd` 37,469, `dim_client.initial_aum` 251. Flagged does not mean wrong: money columns are right-skewed,
so the IQR fence flags the firm's biggest accounts (every `initial_aum` outlier and ~99% of AUM outliers are UHNW
clients, large by definition) and 29% of alpha values because returns are fat-tailed. An IQR flag is a prompt to look
(e.g. the many Retail clients with $186k+ trades). Only rules or reconciliations prove a value wrong.

## Claude Code review findings: Part D

Claude Code reviewed `03_validate.py` (grep/read only, no Python) before the run was committed. This table was
reconstructed from the code afterwards, so the wording is approximate. The fixes changed the rule set from 45 raw / 49 clean
to the same 48 rules in both stages, so `dim_client` raw rule pass is 99.612%.

| # | Finding | Type | Action |
|---|---|---|---|
| 1 | Raw and clean ran different rule sets (45 vs 49) because some rules (e.g. on the flag columns added in Part C) only applied in one stage, so the rule-pass percentages weren't comparable | bug | **Fixed.** Both stages run the same 48 rules |
| 2 | True/False and 0/1 columns had code-list rules *and* a `bool`/`flag` type, so the same defect was scored twice | style | **Fixed.** Those rules were removed; the columns are scored under type validity only |
| 3 | No rules for `dim_benchmark`, `dim_date`, the ETF-only fields or snapshot `year`/`month` | gap | **Fixed.** Added `asset_class` and `ticker_proxy` (benchmark); 7 range/code-list rules (date); `sector` present exactly on non-ETFs and `expense_ratio_bps` exactly on ETFs; `year`/`month` agree with `snapshot_date` |
| 4 | Completeness counted `'Unknown'` `risk_profile` as filled, so D08 would look like it raised completeness | bug | **Fixed.** `NO_INFO` marks `'Unknown'` as missing (raw 99.785, clean 99.786) |
| 5 | R4b merged on the prior-December AUM without deduplicating it; a repeated client-year would add rows and misalign `base` with the snapshot index | risk | **Fixed.** One base per client-year (`drop_duplicates`) before the merge |
| 6 | R1 only compared fees that matched a snapshot; a fee with no snapshot for its client-month was silently excluded | gap | **Fixed.** `rows_unmatched` is reported and asserted to be 0 on clean |
| 7 | The clean-stage asserts ran before the reports were written, so a failure left nothing to diagnose | risk | **Fixed.** Asserts run after all 5 reports are written; added a dimension-key uniqueness assert |
| 8 | `orphan_rows` used a boolean Series to index `fact_df`; a non-unique index could return extra rows | risk | **Fixed.** Positional mask (`.to_numpy()`) |
| 9 | `certifications` accepted `'None'` inside a list (e.g. `'CFA, None'`) | bug | **Fixed.** `'None'` is valid only on its own (L03) |
| 10 | The `fact_transactions` business key leaves out `client_id`, so two clients of one advisor with an identical same-day cash flow would count as duplicates | risk | **Not fixed (documented).** Leaving out `client_id` is what catches the 200 orphan copies, which differ from the real rows only there. The clean stage has 0 such pairs |
