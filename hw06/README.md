# HW6: DAX Measure Library — AUM & Performance

MIS3060 Business Intelligence with AI · Villanova University

This folder builds a library of 12 DAX measures on Wildcat Capital's portfolio snapshot. Each measure uses the DAX pattern that matches its additivity class:
- SUM for flows
- last balance for AUM
- recompute-and-weight for ratios

Every number is reconciled to an independent pandas calculation. **Result: 105 of 105 reconciliation rows match.**

## Folder structure

```
hw06/
├── README.md                      this file
├── powerbi/
│   ├── hw06.pbix                  posted model + _Measures table + "Measures" report page (21.9 MB)
│   ├── measures.md                Part A documentation (DAX, pattern, meaning) and Part C answers
│   └── dax_build_sheet.md         working sheet: every measure, its format, expected values, export query
├── scripts/
│   └── 01_reconcile_measures.py   Part B: pandas recomputation + reconciliation
├── reports/
│   ├── pandas_values.csv          105 measure/slice values computed in pandas
│   ├── powerbi_export.tsv         raw grid copied from DAX query view (Query 3 in the pbix)
│   ├── powerbi_values.csv         the export reshaped to measure, slice, value (generated each run from the TSV)
│   └── measure_reconciliation.csv measure, slice, powerbi_value, pandas_value, abs_diff, match
├── claude/
│   ├── hw06_metadata.txt          raw output of the three INFO.VIEW queries
│   ├── model_metadata.md          Part D step 1: the metadata as tables + what it cannot say
│   ├── part_d_prompt.md           first-draft prompt (it attached the metadata; replaced, see dax_session.md)
│   ├── dax_session.md             Part D step 2: final prompt and Claude's full response
│   └── verification.md            Part D step 3: how measure 11 was tested and judged
├── data/                          the 8 cleaned CSVs (not committed, see below)
├── HW06_DAX_Measure_Library.md    assignment handout
└── powerbi_dax_guide.md           course DAX guide
```

The posted starting model, `Wildcat_Star_Model.pbix`, is on Brightspace. Its local copy is listed in `.gitignore` and not committed, because `hw06.pbix` already contains it.


## How to run the reconciliation

You need Python 3 with pandas (`pip install pandas`). On Windows, use `py` if `python` is not found. From Git Bash in `hw06/`:

```bash
python scripts/01_reconcile_measures.py            # CSVs in hw06/data/
python scripts/01_reconcile_measures.py ../hw05    # or reuse the CSVs committed in hw05/
```

**Where the data comes from.** The inputs are the same eight `Wildcat Capital Clean` CSVs used in HW5. They are already committed in `hw05/`, so `hw06/data/` is ignored by `.gitignore` to avoid storing 34 MB twice. The script accepts either plain names (`dim_client.csv`) or browser-download names (`dim_client (2).csv`, highest copy wins). Both locations give an identical result.

**What the script does:**
1. It recomputes every measure in pandas from the CSVs only. It never reads Power BI values to do this. Each function copies the DAX filter context:
   - LASTNONBLANK becomes "the last snapshot date with rows in the context".
   - SAMEPERIODLASTYEAR and DATEADD shift the whole date range.
   - DIVIDE returns blank instead of an error.
2. It reshapes `reports/powerbi_export.tsv` (the wide grid from DAX query view) into `reports/powerbi_values.csv`.
3. It compares the two and writes `reports/measure_reconciliation.csv`. The tolerance is **0.01 for currency and counts** and **0.0001 for ratios and bps**. Text is compared exactly, and blank = blank counts as a match.
4. It prints a summary. Exit code 0 means every row matched, 1 means at least one mismatch, and 2 means nothing was compared (no Power BI values yet).

`reports/powerbi_values.csv` is **regenerated from `powerbi_export.tsv` on every run**, so edit the TSV, not the CSV. Unknown slice keys raise an error, and any exported cells not needed for a slice are counted in the output.

**How the Power BI numbers were exported.** One query in DAX query view (saved in the pbix as *Query 3*; the text is in `powerbi/dax_build_sheet.md`) returns 10 slices × 14 measures. Every numeric measure is wrapped in `FORMAT(…, "0.000000000000")`, because the results grid rounds to 2 decimals. The grid was copied with **Copy → Entire table**, pasted into Notepad on Apporto and downloaded.

### Coverage (105 rows)

| Requirement | Slices covered |
|---|---|
| Every measure at the grand total | `total`: all 14, including `AUM (naive SUM)` |
| Measures 1, 4, 6–10 by year | `year=2020` … `year=2024` |
| Measures 1, 3, 4, 7–11 by tier, 2024 | `year=2024\|tier=HNW / Retail / UHNW` |
| Measure 5 for December 2024 | `month=2024-12` (Ending AUM, Ending AUM PM, AUM MoM %) |
| Extra: measure 11 by year | `year=2020` … `year=2024`, the Part D edge cases from `claude/verification.md` |
| Naive SUM in both tools | 9 rows. Both tools report the same wrong $566.7B, about 44× real AUM |

The largest absolute difference is $0.0001 on a $27B naive SUM, which is floating-point noise.

### Mismatches and fixes
**None in the final run: 105 of 105 match.** Problems found along the way:
- **Display rounding.** DAX query view rounds the grid to 2 decimals, which would have failed the 0.0001 ratio tolerance. Fixed on the Power BI side by exporting through `FORMAT` with 12 decimals.
- **One wrong field on the report page.** The year table first showed `Ending AUM PM` instead of `Ending AUM`; the 2024 row read $12.21B instead of $12.73B. Spotted by comparing with pandas and fixed in the visual. The measures were never wrong.

## Power BI notes
- **Relationships:** the posted model has **12 relationships, not the 11 the handout states**. It has no `dim_client → dim_advisor` relationship but does have `dim_security → dim_benchmark`. Auto date/time is on, which adds hidden date tables (see `claude/model_metadata.md`). No measure depends on these differences.
- **`_Measures` table:** holds all 16 measures (12 library measures plus LY and PM helpers plus 2 base measures), each with a format string.
- **Measures page:**
  - The **Card** visual (holding all four headline measures) does not render on the Apporto virtual desktop. It stays blank even though the fields are bound.
  - A one-row table with the same four measures sits next to it, so the numbers are visible anywhere: $12,729,572,078.86 · 2,325 · $5,475,084.77 · 6.16%.
  - The tier table uses a visual-level filter, `dim_date[year] = 2024`.
- **Saving on Apporto:** saving over `hw06.pbix` failed after a session disconnect left a file lock. The work was saved as a new copy on Apporto and renamed `hw06.pbix` in this repo.

## Who did what (Claude usage)
| Step | Done by |
|---|---|
| Drafting `01_reconcile_measures.py`, `dax_build_sheet.md`, `measures.md`, `verification.md` and this README | **Claude, in a claude.ai agent session**, not Claude Desktop. This **deviates from the handout**, which names Claude Desktop as the script-drafting tool. |
| Entering the DAX measures and formats in Power BI, running the DAX test and export queries | The same Claude session, operating Power BI on Apporto through my browser, at my direction |
| Building the **Measures** report page (cards and both tables) | **Me** (Jack), by hand. Claude fixed the card's field binding and added the backup table |
| Measure 11 (`Top 10 Client Share`) | **Claude Desktop**, through the Part D Draft → Test → Debug → Review workflow (`claude/dax_session.md`) |
| Running the script and checking the output | Me, in VS Code / Git Bash: `python scripts/01_reconcile_measures.py` gives 105 of 105 |
| Review before commit | **Claude Code** (findings below) |

Part D result: Claude Desktop's measure ran as written, with no DAX changes. An adapted version of its test query matched pandas on all 9 slices. **Two claims were confirmed** (the departed-client trap, and no `dim_client → dim_advisor` relationship) and **one was refuted** (UHNW being a "small group": it has 244 clients).

## Claude Code review findings
Claude Code reviewed the script, reports, docs and `.gitignore` before commit, without editing anything. It re-ran the script in a scratch folder and got byte-for-byte identical CSVs. It recomputed every Part C number from `../hw05` and all matched. It found **no High-severity issues**.

| # | Finding | File | Severity | Action taken |
|---|---|---|---|---|
| 1 | verification.md says "no DAX was changed", but its code block shows `Top10AUM`/`TotalAUM` folded into RETURN, unlike Claude's draft | claude/verification.md | Med | Checked the pbix: it holds Claude's exact DAX, VARs included. The code block was a documentation shortcut. Replaced it with the exact text and added a note; same fix in measures.md |
| 2 | Edge case 4 refers to `TotalAUM`, which the documented measure lacked | claude/verification.md | Low | Resolved by #1; wording now says "Claude's `TotalAUM` variable" |
| 3 | `[Ending AUM] - [LY]`: DAX treats a blank current value as 0 (giving −100%), but the script returned blank | scripts/01_reconcile_measures.py | Med | Added `growth()` with DAX blank arithmetic for YoY and MoM. No current slice was affected; tested that `growth(blank, 100) = −100%` |
| 4 | Unknown slice keys fell back to month measures silently; reshape dropped cells silently | scripts/01_reconcile_measures.py | Low | Unknown keys now raise `ValueError`; reshape reports dropped cells and warns about unknown columns |
| 5 | Exit code 0 when there is nothing to compare; powerbi_values.csv is overwritten on every run | scripts/01_reconcile_measures.py, README.md | Low | Exit code 2 when nothing is compared; README and script output say the CSV is regenerated from the TSV |
| 6 | Unclear who did what; the script was not drafted in Claude Desktop as the handout asks | README.md, claude/verification.md | Med | Added the "Who did what" table, stated the deviation, and defined "I" at the top of verification.md |
| 7 | "Matched on all 9 slices" overstated (test query was adapted; per-year Top 10 values were not in a committed file); "one confirmed" miscounted | README.md | Low | Said "adapted version"; added Top 10 by year to the reconciliation (now 105 rows); corrected to two confirmed, one refuted |
| 8 | C(d) compared Retail's $44M flow with UHNW's $9.6B balance | powerbi/measures.md | Low | Now compares like with like: Retail is 57% of the firm's $77.5M net flows, about 0.35% of AUM |
| 9 | C(b) said "≈ 43.15", but it reconciles exactly | powerbi/measures.md | Low | Shown as exact: Σ aum_basis = Σ aum − $7,074,540,256.63, so 45.53 × (1 − 0.05223) = 43.15 |
| 10 | Format strings differ between measures.md and dax_build_sheet.md; the metadata predates formats | powerbi/*.md, claude/model_metadata.md | Low | Checked the pbix (Currency 2 dp, % 2 dp, Decimal 2 dp, Whole number) and aligned both docs; added a timing note to model_metadata.md |
| 11 | README review table was a placeholder | README.md | Low | Filled in (this table) |
| 12 | `Wildcat_Star_Model (1).pbix` (21.9 MB) would be committed and duplicates the Brightspace starter | hw06/ | Low | Added to `.gitignore`; README points to Brightspace |
| 13 | `.gitignore` change not yet committed | ../.gitignore | Low | Committed together with hw06 |
