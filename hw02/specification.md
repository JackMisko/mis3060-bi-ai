# HW2 Specification — EDA Script for Wildcat Capital Transactions

**Student:** Jack Miskiewicz
**Course:** MIS3060 Business Intelligence with AI
**Date written:** September 22, 2026
**Script to be generated:** `hw02/hw02_eda.py`

---

## What I need

Write **one single Python script** that performs a complete exploratory data analysis (EDA) of Wildcat Capital's transaction history. All seventeen items below must live in the same file and run together, top to bottom, in one execution with the command `python hw02/hw02_eda.py`. Do not split the work into separate scripts, functions in other files, or notebooks.

## Context about the data

- **File:** `data/raw/fact_transactions.csv` (a path relative to the repository root, which is where the script will be run from).
- **What it is:** Every client transaction recorded by Wildcat Capital, a wealth management firm, from January 2020 through December 2024. Each row is one transaction event.
- **Columns (9):** `txn_id`, `client_id`, `advisor_id`, `security_id`, `txn_date`, `txn_type`, `shares`, `price`, `amount`.
- **Transaction types:** Buy, Sell, Deposit, Withdrawal, Dividend, and Advisory Fee.
- **Size:** Roughly 300,000 rows, so the script should be reasonably efficient and charts must stay readable at this scale.
- **Nulls are expected:** Non-trade transactions have no security, so `security_id`, `shares`, and `price` are blank on many rows. The script should report these nulls, not drop or fill them.
- **Leave the data as loaded:** Do not parse `txn_date` as a date when loading, and do not clean, filter, or change any column in the main DataFrame. I need to see the data types exactly as pandas reads them by default. If a date conversion is needed for any step, do it on a separate copy only.

## Libraries and environment

- Use only pandas, NumPy, and matplotlib (seaborn is acceptable for the charts). These are already installed from my `requirements.txt`.
- Charts must be saved to files without opening a pop-up window, so the script finishes on its own in the VS Code terminal.
- If the `hw02/charts/` folder does not exist, the script should create it.

## Required steps (in this order)

**1. Load the data.** Read `data/raw/fact_transactions.csv` into a pandas DataFrame. If the file cannot be found, print a clear message telling me the expected path and stop.

**2. Shape.** Print the number of rows and columns in the form "rows × columns".

**3. Columns and data types.** Print every column name alongside its data type.

**4. Missing values.** Print the count of missing values for every column, including columns with zero missing values.

**5. Descriptive statistics.** For all numeric columns, print count, mean, standard deviation, minimum, 25th percentile, median (50th percentile), 75th percentile, and maximum.

**6. Transaction type breakdown.** Print the count and percentage of total for each `txn_type` value, sorted from most to least frequent. Show percentages to two decimal places. Also print how many distinct transaction types there are.

**7. Unique entities.** Print the number of unique clients (`client_id`), unique advisors (`advisor_id`), and unique securities (`security_id`, ignoring blanks) referenced in the file.

**8. Date range.** Print the earliest and latest `txn_date` in the dataset.

**9. Duplicate check.** Count how many rows have a `txn_id` that appears more than once and print that duplicate count (print 0 if there are none).

**10. Amount distribution.** Print the mean, median, and skewness of the `amount` column. Round mean and median to 2 decimal places and skewness to 2 decimal places. Add a short plain-English note stating whether the distribution is right-skewed, left-skewed, or roughly symmetric.

**11. Group by transaction type.** Group the data by `txn_type` and print a table showing, for each type, the transaction count, the mean `amount`, and the median `amount`. Round mean and median to 2 decimal places. Sort the table by mean amount from highest to lowest.

**12. Correlation.** Compute the correlation matrix for `shares`, `price`, and `amount`, rounded to 2 decimal places, and print it. Then identify and print the three strongest correlations between *different* variables (never a variable with itself, and each pair listed only once), ranked by the strength of the relationship regardless of sign. Show each pair's names and its correlation value.

**13. Negative shares check.** For each `txn_type`, print the minimum `shares` value, the maximum `shares` value, and the count of rows where `shares` is negative. Also print the total number of negative-share rows across the whole file. Transaction types with no share values should still appear in the table (showing blanks or zero rather than being silently dropped).

**14. Shape validation.** If the shape of the DataFrame is not exactly 298,772 rows and 9 columns, print a clearly visible WARNING line that shows the expected shape and the actual shape. If the shape matches, print a short confirmation line instead.

**15. Charts.** Create and save three charts as PNG files in `hw02/charts/`. Each chart needs a descriptive title and labeled axes, and amounts should display in a readable dollar format.
   - **`hw02/charts/hist_amount.png`** — A histogram of `amount`, with one vertical line at the mean and a second, visually different vertical line (different color and line style) at the median. Include a legend that labels each line with its dollar value.
   - **`hw02/charts/box_amount_by_type.png`** — A horizontal box plot of `amount`, with one box per `txn_type` on the vertical axis.
   - **`hw02/charts/scatter_shares_amount.png`** — A scatter plot with `shares` on the x-axis and `amount` on the y-axis, with points colored by `txn_type` and a legend identifying each type. Because there are so many rows, use small, semi-transparent markers so overlapping points remain visible. Rows without share values will naturally not appear.

   After saving each chart, close it and print the file path that was saved.

**16. Profile file.** Save a plain-text summary of everything printed in items 2 through 13 to `hw02/hw02_profile.txt`. It should contain the same values that appear in the terminal, in the same order, with the same section headers, so I can compare the two. Overwrite the file if it already exists, and print a confirmation with the file path once it is written.

**17. Header comment block.** At the very top of the script, include a comment block that identifies:
   - Script name: `hw02_eda.py`
   - Purpose: Exploratory data analysis of Wildcat Capital transaction data (MIS3060 HW2)
   - Dataset: `data/raw/fact_transactions.csv`
   - Author: Jack Miskiewicz (generated with Claude Cowork)
   - Generation date
   - How to run it: `python hw02/hw02_eda.py` from the repository root

## Output formatting

- Separate each numbered section in the terminal with a clear header (for example, "=== 6. TRANSACTION TYPE BREAKDOWN ===") so I can match each output to this specification during validation.
- Show every row and column of each table; do not let pandas truncate output with "..." ellipses.
- Format large numbers with thousands separators where it helps readability.
- End the run with a single line stating the script finished successfully.

## What I will check

- The script runs from start to finish with no errors and no manual edits.
- All seventeen items above are present.
- `hw02/hw02_profile.txt` and all three chart files exist after the run.
- The printed values will be compared against independently calculated benchmarks, so do not hard-code or estimate any result — every number must be computed from the data.
