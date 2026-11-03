# HW5: Wildcat Capital Star Schema in Power BI

MIS3060 Business Intelligence with AI · Villanova University

This folder models the eight cleaned Wildcat Capital tables as a star schema. It does three things: identifies every key, grain and measure type, proves those claims in code, and builds the model in Power BI Desktop.

## Folder structure

```
hw05/
├── README.md                 this file
├── star_design.md            written answers: Parts A, B, C, E, F (and a Part D summary)
├── hw05_star_checks.py       script that proves the keys, grains and design claims (55 checks)
├── powerbi/
│   ├── hw05.pbix             Power BI model (Part D), 21.8 MB
│   ├── model_view.png        Model view: all 8 tables and 13 relationships
│   └── row_counts.png        card per table: row counts reconcile with the handout
├── HW05_Star_Schema_and_Power_BI.md   assignment handout
├── powerbi_guide (1).md               Power BI guide from the course
├── dim_advisor (2).csv                ┐
├── dim_benchmark (3).csv              │
├── dim_client (2).csv                 │  the course's "Wildcat Capital Clean" files,
├── dim_date (3).csv                   │  unchanged (names kept as downloaded);
├── dim_security (3).csv               │  committed so the checks run straight
├── fact_fees (2).csv                  │  from a fresh clone (~35 MB in total)
├── fact_portfolio_snapshot (2).csv    │
└── fact_transactions (3).csv          ┘
```

The eight CSVs are inputs, not deliverables. They are committed (as in HW4) so anyone can rerun the checks without downloading the data separately.

## How to run the checks

Requires Python 3 with pandas (`pip install pandas`). On Windows, if `python` opens the Microsoft Store or is not found, use `py` instead.

From Git Bash in the `hw05/` folder:

```bash
python hw05_star_checks.py                          # CSVs in this folder
python hw05_star_checks.py "Wildcat Capital Clean"  # or point it at the data folder
```

The script reads the CSVs only and never changes them. It accepts both the original file names (`dim_client.csv`) and browser-download names (`dim_client (2).csv`). It prints the file it loaded for each table (and warns if several downloaded copies exist, using the highest copy number). It then prints PASS/FAIL for each check and `[INFO]` lines for supporting counts, and exits with code 0 only if all checks pass.

**Result: 55 of 55 checks pass.**

The summary below groups the checks; the script output lists every one.

| Area | What is checked |
|---|---|
| Row counts | All 8 tables match the handout (25 · 8 · 2,500 · 1,827 · 500 · 122,197 · 129,547 · 298,572) |
| Part A, keys | 8 primary keys and `dim_date[date]` are unique and non-null; all 13 foreign keys have **0 orphans**; the only blanks are 101,528 `security_id` values on cash rows; fact dates are calendar dates that match `dim_date[date]`, not `date_id` |
| Part B, grain | `client_id + fee_date` and `client_id + snapshot_date` are unique; every fee and snapshot date is the 1st of a month; each client has one account type; `txn_id` is unique and no rows are duplicated apart from it (no natural composite key: 622 repeats) |
| Part C, measures | fee `amount = aum_basis × bps / 10,000 / 12` (to the cent); every fee row has a matching snapshot and its `aum_basis` equals that snapshot's AUM; `alpha = return − benchmark return`; all transaction amounts are positive; `amount = shares × price` on Buy/Sell/Dividend rows (to the cent); `expense_ratio_bps` is blank exactly on non-ETFs |
| Part E, design | (a) blank `security_id` ⇔ Deposit / Withdrawal / Advisory Fee, and those rows also have blank `shares` and `price`; (b) fact `advisor_id` always equals `dim_client[advisor_id]`; (c) `dim_date` is a continuous daily calendar; (d) snapshot `benchmark_id` is one per client |

## Power BI model (Part D)

Built in Power BI Desktop on the Apporto virtual desktop, following `powerbi_guide (1).md`:

- **Load:** 8 tables through Power Query, renamed to the handout names, every column type checked. `dim_client[zip_code]` was fixed to Text so leading zeros survive.
- **Relationships:** 12 active and 1 inactive, all many-to-one with single direction. The three date relationships join on `dim_date[date]`. `dim_client → dim_advisor` is **inactive**, so advisors filter the facts through each fact's own `advisor_id` (reasoning in `star_design.md` E(b)).
- **Date table:** `dim_date` is marked as the date table on `date` (validated by Power BI).
- **Row counts:** all 8 reconcile with the handout (`powerbi/row_counts.png`).

Auto-detect got the advisor and client relationships backwards and missed the date relationships entirely. Both were corrected by hand; details are in `star_design.md` Part D.

## Claude Code review findings

Claude Code reviewed `hw05_star_checks.py`, `star_design.md`, `README.md` and the Power BI screenshots before commit. No high-severity errors were found, and every number spot-checked against the CSVs matched. Items marked *judgment call* are design or wording choices, not errors.

| # | Finding | File | Severity | Action taken |
|---|---|---|---|---|
| 1 | Relationship lines in the Model view screenshot cross heavily and the facts are not in the middle; the guide asks for no overlapping lines | powerbi/model_view.png | Medium | **Pending (Power BI Desktop):** rearrange with the facts in the middle and retake the screenshot |
| 2 | `.gitignore` rule `!hw*/*.csv` means the 8 CSVs get committed, but the README did not list them | README.md | Medium | Kept them committed (as in HW4) and added them to the folder tree with their real names |
| 3 | "Every data claim is checked" overstated: several supporting counts were not in the script | star_design.md | Medium | Added 3 checks (cash rows have blank shares/price; expense ratio blank exactly on non-ETFs; every fee row has a snapshot) and `[INFO]` lines for the other counts; reworded the opening line |
| 4 | *Judgment call:* E(b) claimed the fact `advisor_id` records the advisor at event time, which the data cannot show (the 2,410 post-departure transactions still carry the departed advisor) | star_design.md | Medium | Reworded as a design choice; discussed the post-departure rows and the side effect of the inactive client → advisor relationship |
| 5 | Conformed dimensions were named in the Part D summary, but the rubric grades them under Part E | star_design.md | Low-Med | Moved into Part E |
| 6 | Tolerances were far looser than rounding needs (< $1 for shares × price, < 0.05 for fees; real maximum error 0.005) | hw05_star_checks.py | Low-Med | Both tightened to 0.01 (one cent) |
| 7 | The `aum_basis` check used an inner merge that would drop unmatched rows without a word, and compared floats with `==` | hw05_star_checks.py | Low | Added a check that all fee rows matched; compare within a cent |
| 8 | Some checks would pass on empty input | hw05_star_checks.py | Low | Added non-empty conditions |
| 9 | Some checks only partly tested their label or repeated another check | hw05_star_checks.py | Low | Replaced (c) with a continuous-calendar check (coverage is already proven by the zero-orphan FK checks); renamed (d) and the date-format section to say what they test; noted that `txn_id` uniqueness restates the PK check |
| 10 | `load()` picked the first match by text sort (`(10)` before `(2)`) without saying which file it used | hw05_star_checks.py | Low | Sorts by copy number, prints the file used and warns about multiple copies |
| 11 | INFO line hardcoded "of 2,500" | hw05_star_checks.py | Low | Uses the table length |
| 12 | *Judgment call:* keys, date parts, rates and percentages still default to Sum in the model | powerbi/hw05.pbix | Low | **Pending (Power BI Desktop):** set Summarize by to "Don't summarize" |
| 13 | E(c) said `dim_date` covers fact dates "to 2024-12-31"; fact dates actually end on 2024-12-01 and 2024-12-30 | star_design.md | Low | Reworded with the actual ranges |
| 14 | *Judgment call:* "Additive, within a txn_type" is not one of the three standard labels | star_design.md | Low | Changed to "Additive (only within one `txn_type`)" and the same for shares |
| 15 | *Judgment call:* `dim_benchmark` was called shared or conformed despite meaning different things for the two facts | star_design.md | Low | Now described as "shared but not conformed" |
| 16 | The README check table left out several checks | README.md | Low | Table now lists every check group |

## Tools

Claude drafted the script and write-up. The script was run on the course data, and every claim in `star_design.md` is backed by a check that passes. Claude Code reviewed the work before commit (findings above). Power BI Desktop (Apporto) was used for the model.
