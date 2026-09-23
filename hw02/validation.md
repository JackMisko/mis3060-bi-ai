# HW2 Validation — Wildcat Capital `fact_transactions.csv` EDA

**Student:** Jack Miskiewicz
**Course:** MIS3060 Business Intelligence with AI
**Script validated:** `hw02/hw02_eda.py`
**Run command:** `python hw02/hw02_eda.py` (from repository root)
**Full terminal output:** saved in `hw02/terminal_output.txt`

---

## How the Five Week 4 Validation Methods Are Covered

| # | Validation method (Week 4) | Where it is documented |
|---|---|---|
| 1 | Known-answer benchmarks | Section 2A |
| 2 | Ask Claude Cowork to explain the code | Section 2B, Prompt 1 |
| 3 | Ask Claude Cowork to explain the output | Section 2B, Prompt 2 |
| 4 | Business-reasonableness check | Section 2C, Questions 1–5 |
| 5 | Cross-validation (two prompts, same question) | Section 2C, Questions 6–8 |

---

## Run Log (Part 1C)

- The script ran start to finish with **no errors** in about 15 seconds.
- `hw02/hw02_profile.txt` and all three charts in `hw02/charts/` were created.
- **Manual change made:** I edited the data path in the script (the `DATA_PATH` setting, the header comment, and the file-not-found message) from `data/raw/fact_transactions.csv` to `02_Data/Raw/fact_transactions.csv`, because that is where the file is stored in my repository. This changes only where the file is read from, not any calculation.

---

## 2A — Known-Answer Benchmarks

| Check | Expected | Your Script Produced | Match? | Notes |
|---|---|---|---|---|
| Dataset shape | (298772, 9) | 298,772 rows × 9 columns | Yes | Section 14 also printed "Shape confirmed" |
| Null count — `security_id` | 101,597 | 101,597 | Yes | 34.00% of rows; `shares` and `price` have the same count |
| Null count — `amount` | 0 | 0 | Yes | |
| Unique `txn_type` values | 6 | 6 | Yes | Advisory Fee, Buy, Deposit, Dividend, Sell, Withdrawal |
| Count of `Buy` transactions | 83,556 | 83,556 | Yes | 27.97% of rows, most frequent type |
| `txn_date` data type | object | object | Yes | Stored as text; not converted in the main DataFrame |
| Earliest `txn_date` | 2020-01-01 | 2020-01-01 | Yes | |
| Latest `txn_date` | 2024-12-30 | 2024-12-30 | Yes | |
| Duplicate `txn_id` count | 0 | 0 | Yes | |
| Mean `amount` | $54,075.17 | $54,075.17 | Yes | |
| Median `amount` | $41,220.48 | $41,220.49 | **No** | Rounding difference of $0.01 — see note below |
| Skewness of `amount` | 1.15 | 1.15 | Yes | Script labeled it right-skewed |
| Correlation `shares`–`amount` | 0.65 | 0.65 | Yes | Ranked #1 strongest |
| Correlation `price`–`amount` | 0.64 | 0.64 | Yes | Ranked #2 |
| Correlation `shares`–`price` | 0.00 | 0.00 | Yes | Ranked #3 (no linear relationship) |
| Negative `shares` count (Buy only) | 836 | 836 (all Buy) | Yes | Min Buy shares = −499.6323; all other types have 0 negatives |
| Profile file created | Yes | Yes | Yes | `hw02/hw02_profile.txt` |
| Chart files created (3) | Yes | Yes (3) | Yes | `hist_amount.png`, `box_amount_by_type.png`, `scatter_shares_amount.png` |

**Group-by benchmark (Section 11):** all six rows matched exactly — counts, mean `amount`, and median `amount` for Dividend, Buy, Sell, Deposit, Withdrawal, and Advisory Fee, in the same descending order by mean.

### Mismatch investigation — Median `amount`

**Discrepancy:** Expected $41,220.48; script printed $41,220.49.

**Investigation (Claude Cowork conversation, summarized):**
- While validating the output, Claude Cowork flagged the one-cent difference and checked the underlying value: the dataset has an even number of rows (298,772), so the median is the average of the two middle values after sorting — **$41,219.90** and **$41,221.07**.
- Their average is exactly **$41,220.485**, which falls precisely halfway between two cents.
- Python rounded the half-cent up to $41,220.49; the benchmark rounded it down (or truncated) to $41,220.48.

**Conclusion:** This is a rounding convention difference, not a bug. The script computed the median correctly, and no fix is needed.

---

## 2B — Explain the Code and Output

> **How this was run:** Both prompts went to a **separate, fresh Claude reviewer agent**. It had no access to the conversation that generated the script and was not told what the results should be. For Prompt 1 it could read **only** `hw02_eda.py`. It was told not to run the script, load the CSV, or open the output, so its predictions came from the code alone. For Prompt 2 it was then given `hw02/terminal_output.txt`.

**Prompt 1 (the code):** pasted the full `hw02_eda.py` and asked:
> *"Walk me through each section of this script, including the grouping, correlation, and charting steps. What should I see in the terminal when I run it? List each expected output value explicitly."*

**Prompt 2 (the output):** pasted the full contents of `hw02/terminal_output.txt` and asked:
> *"Here is the terminal output from running an EDA script on a wealth management transaction dataset. What does each value mean? Flag anything that looks unexpected or that I should investigate before using this data in an analysis."*

**1. Did Claude's predicted outputs (Prompt 1) match what I actually saw in the terminal? Discrepancies:**

Mostly yes. Claude correctly predicted:
- The section structure and headers.
- The shape of 298,772 × 9 and the "Shape confirmed" line.
- ID columns showing up in the descriptive statistics.
- A right skew with the mean above the median.
- `shares`–`amount` / `price`–`amount` as the strongest correlations.
- The descending sort in Section 11.
- The three "Saved:" chart lines and the profile file line.

It could not predict exact values from code alone, which is expected. The discrepancies:

| Claude predicted | What actually happened |
|---|---|
| Section 13 had a **bug**: types with no shares would print `nan` instead of `(none)` | Output shows `(none)`. There is no bug. Claude withdrew this claim after seeing the output. |
| Only trade rows (Buy/Sell) would have `shares`/`price`; all non-trade types would be blank | **Dividend** rows also have shares and price. Only Deposit, Withdrawal, and Advisory Fee are blank. |
| ID columns would be `int64` or text | `security_id` is `float64`, because its blank values force pandas to store it as a float. |
| A possible date warning or crash in Section 8 | No date problems. Every `txn_date` parsed. |
| No warnings mentioned | Two harmless matplotlib `UserWarning`s ("Creating legend with loc='best' can be slow") printed at the top, caused by the ~197,000-point scatter plot legend. |

**2. What did Claude flag as unexpected or worth investigating (Prompt 2)?**

1. **836 negative-share Buy transactions.** That is almost exactly 1.0% of Buys, and no Sell or Dividend has negative shares. Claude called this the top issue to resolve before analysis.
2. **Dividend amounts are trade-sized.** The mean is $64,077, almost identical to Buy and Sell. Real dividends are usually a small percentage of a position, so Claude recommended confirming what `shares`/`price` mean on Dividend rows.
3. **Advisory Fee is heavily skewed.** The mean is $7,375 against a median of $859. Claude recommended reviewing the largest fees for misclassification or decimal errors.
4. **`client_id` gaps.** The maximum ID is 3,192, but only 2,700 distinct clients appear, so 492 IDs are never used. Claude suggested checking against a client table.
5. **`amount` is always positive.** Money-in vs. money-out direction comes only from `txn_type`, so a sign convention is needed before any net cash-flow or AUM calculation.
6. **Data-type fixes.** Convert `txn_date` to a date type, and treat `security_id` (stored as float) as a key rather than a measure.
7. **Signs of synthetic data.** Type percentages are near-round (28/20/18/12/12/10%), prices are exactly 10–500, and the `shares`–`price` correlation is 0.00. Claude said this is fine for coursework but worth noting.

**3. Did Claude mention the 101,597 null values in `security_id`? What explanation did it give?**

Yes. Claude noted that `security_id`, `shares`, and `price` are each missing in exactly 101,597 rows (34.00%). It showed that this equals Deposit (35,981) + Advisory Fee (35,766) + Withdrawal (29,850). It explained the nulls as **structural, not a data-quality problem**: cash movements and fees don't involve a security, so there is no security, share count, or price to record. It advised not to fill or drop them.

**4. Did Claude flag `txn_date` as a concern? Why would that matter for a time-series analysis?**

Yes. Claude flagged that `txn_date` is stored as `object` (text) and "needs converting before any time-based analysis," and put it on its investigation checklist. It also suggested confirming that the raw date format is not ambiguous (month-first vs. day-first).

This matters for time-series work because pandas treats a text date as plain characters, not a point in time:
- You cannot subtract two dates to get days between transactions.
- You cannot group or resample by month, quarter, or year.
- You cannot filter by a date range.
- Charts would treat each date as a separate category label instead of plotting on a real timeline.

The format here (YYYY-MM-DD) happens to sort correctly as text, which hides the problem until a date calculation fails.

**5. Do the three chart files match Claude's explanation of each section? Differences:**

- **`hist_amount.png`** — **Matches.** The histogram shows a long right tail. The red dashed mean line ($54,075.17) sits to the right of the green solid median line ($41,220.49), with both values in the legend, as Claude described. The tallest bar is at the far left (small amounts), which fits Claude's comment that the many small Advisory Fees help create the skew.
- **`box_amount_by_type.png`** — **Matches.** Boxes are horizontal and ordered by mean, highest at the top (Dividend, Buy, Sell, Deposit, Withdrawal, Advisory Fee), as predicted.
  - Deposit and Withdrawal are symmetric and capped at about $100,000, with no outliers. This matches Claude's "evenly spread up to about $100k" comment.
  - Advisory Fee has a tiny box near $0 and a long trail of outliers out to about $140,000. This visually confirms Claude's skewed-fee flag.
- **`scatter_shares_amount.png`** — **Matches.** Only Buy, Dividend, and Sell appear in the legend, because types with no shares are skipped, as Claude predicted.
  - The fan/triangle shape rising to about $250,000 at 500 shares is consistent with amount ≈ shares × price.
  - A separate cloud of orange (Buy) points sits at **negative shares with positive amounts**. This visually confirms the 836-row anomaly and the follow-up answer below.
  - **Difference:** Claude's code walkthrough did not mention that the legend would trigger a "slow legend" warning at this data size. Otherwise the chart matches.

**6. One follow-up question I asked Claude, and Claude's answer:**

- **My question:** *"The 836 negative-share Buy transactions still have positive dollar amounts — what does that suggest about whether they are sign errors versus reversals?"*
- **Claude's answer (summarized):** Claude said the positive amounts point more toward **sign errors than reversals**, for three reasons:
  - A real reversal or cancellation would normally show a negative amount, its own transaction type, or a link to the original trade. Here the shares say "reversed" but the dollars say "normal purchase," which is the signature of a one-field sign error.
  - If `amount` were calculated as signed shares × price, these rows would be negative. Yet the dataset's minimum amount is +$13.33, and the Buy mean ($63,738) isn't pulled down relative to Sell or Dividend.
  - The negatives mirror the positive range (down to −499.63), hit almost exactly 1% of Buys, and never affect Sells. That looks like randomly flipped signs, not a business process.

  Claude said it would change its mind if each negative Buy matched an earlier positive Buy for the same client, security, and share count, or if the rows clustered at month-end or under one advisor. It recommended three checks:
  - Compare `amount` with |shares| × price on those rows.
  - Search for matching offsetting transactions.
  - Look at how the rows are spread across dates and advisors.

  It also recommended documenting whichever fix is applied: flipping the sign with a flag column, or netting out reversal pairs.

---

## 2C — Business Check & Cross-Validation

### Business-Reasonableness Questions

> Answered in my own words.

**1. Which three transaction types would have no security, why, and do the counts add up to 101,597?**

_[Your answer]_

**2. What does it mean to have 83,556 Buys vs. 59,755 Sells over five years?**

_[Your answer]_

**3. What would go wrong computing average days between transactions if `txn_date` stays a string?**

_[Your answer]_

**4. Is ~108 clients per advisor (2,700 clients / 25 advisors) plausible for an RIA?**

_[Your answer]_

**5. Two plausible explanations for 836 negative-share Buy transactions, and what I would do next:**

_[Your answer]_

### Cross-Validation — Count of `Buy` Transactions

Both scripts were generated from the two prompts below and run from the repository root.

- **Prompt A:** *"Write Python to count rows in fact_transactions.csv where txn_type equals exactly 'Buy'."* → `hw02/crossval_a.py`
- **Prompt B:** *"Write Python to count the total rows in fact_transactions.csv, then subtract the count of rows where txn_type is Sell, Deposit, Withdrawal, Dividend, or Advisory Fee."* → `hw02/crossval_b.py`

**6. What did each script return?**

| Approach | Method | Result |
|---|---|---|
| Prompt A | Direct filter: `txn_type` equals "Buy" | **83,556** |
| Prompt B | 298,772 total rows − 215,216 rows of the other five types | **83,556** |

**7. Do the results agree? If not, which is wrong and why?**

Yes. Both approaches returned 83,556, which also matches the known-answer benchmark and the Section 6 value count from `hw02_eda.py`. The agreement also confirms there are no stray or misspelled `txn_type` values (for example "buy" or "Buy "): if there were, the subtraction method would have produced a larger number than the direct filter.

**8. Why verify a count by subtraction rather than direct filtering?**

_[Your answer]_
