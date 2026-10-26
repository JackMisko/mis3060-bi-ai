# HW4: Cleaning the Wildcat Capital Data

MIS3060 Business Intelligence with AI. Brief: [HW04_Data_Cleaning.md](HW04_Data_Cleaning.md)

## Folder structure

```
hw04/
├── HW04_Data_Cleaning.md       assignment brief
├── README.md                   this file
├── scripts/
│   └── 01_profile.py           Part A: generic profiler + four groups of checks
├── data/
│   └── raw/                    the eight source CSVs (not committed; copy them in)
└── reports/
    ├── profile_raw.csv         one row per table x column (75 rows)
    └── dq_summary_raw.csv      one row per check, tagged ERROR / WARN / INFO / PASS
```

Parts B-E (`decision_log.md`, `02_clean.py`, `03_validate.py`, `data/clean/`, `data/audit/`,
the scorecard and the business report) will be added in later commits.

## How to run

From inside `hw04/`, with the eight raw files in `data/raw/`:

```
python scripts/01_profile.py                              # full audit of all eight tables (~100 s)
python scripts/01_profile.py data/raw/dim_benchmark.csv   # generic profile of any single CSV
```

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

## Claude Code review findings

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
