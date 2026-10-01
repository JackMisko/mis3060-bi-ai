# HW3 Validation

Company and quarter used for 5A and 5C: **Walmart (WMT), Q2 fiscal 2027** (three months ended July 31, 2026; earnings 8-K filed 2026-08-20). It is Walmart's most recent quarter, so the same quarter can be checked against yfinance's "most recent quarter" in 5C.

## 5A — Known-Answer Check: Earnings

Official source: Walmart's Q2 FY27 earnings release on its investor relations site ([stock.walmart.com](https://stock.walmart.com/_assets/_921ff28c537145729fbc2553b7f43fac/walmart/db/938/9996/earnings_release/Earnings+Release+(FY27+Q2).pdf)): "Total revenues $187,937" million (headline "$187.9 billion"), GAAP diluted EPS $0.80.

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| Walmart Q2 FY27 Revenue | $187,937M ("$187.9 billion" in the headline) | 187900.0 ($M) | Yes, within rounding |
| Walmart Q2 FY27 EPS Diluted | $0.80 (GAAP) | 0.80 | Yes, exact |

Notes:
- **Revenue:** the pipeline reads the narrative headline first ("Revenue of $187.9 billion"), so the CSV value is rounded to $0.1 billion. The $37M gap from the table value of 187,937 is rounding (0.02%), not an extraction error.
- **EPS:** the CSV holds the GAAP figure ($0.80), not adjusted EPS ($0.81). The release prints both on the same line ("GAAP EPS of $0.80; Adjusted EPS of $0.81"), so this confirms the pipeline skipped the adjusted number correctly.
- **No regex fix needed:** neither value mismatched or showed `NOT_FOUND`, so there is no before/after pattern to document.

## 5B — Known-Answer Check: Executive Events

CSV row checked: `Walmart Inc., WMT, 0000104169, 2025-11-14, departure, C. Douglas McMillon, President and Chief Executive Officer, 2026-01-31`

Sources:
- Walmart's own announcement, 2025-11-14 ([corporate.walmart.com](https://corporate.walmart.com/content/corporate/en_us/news/2025/11/14/walmart-announces-john-furner-as-president-and-chief-executive-o0.html))
- Yahoo Finance news ([finance.yahoo.com](https://finance.yahoo.com/news/walmart-ceo-doug-mcmillon-to-retire-jan-31-longtime-exec-john-furner-named-next-ceo-142125331.html))

| Check | News Source Confirms? | Notes |
|---|---|---|
| Person name and title | Yes | Walmart names him "Doug McMillon," President and Chief Executive Officer of Walmart Inc. The 8-K uses his legal name, C. Douglas McMillon, which is what the CSV holds. |
| Event type (departure/appointment) | Yes | Retirement, which is a departure. His successor, John Furner, appears as a separate `appointment` row in the same filing, as Specification B requires. |
| Effective date | Yes | McMillon "will retire on January 31, 2026" (CSV: 2026-01-31). Furner becomes President and CEO effective February 1, 2026. |

Discrepancy found while checking this filing: the same filing also produced a spurious `departure` row for John R. Furner (title `NOT_FOUND`). The cause is the description of his non-compete agreement ("for a period of two years following his termination of employment…", "if Mr. Furner is terminated from the Company for any reason…"). Those sentences describe hypothetical future terms, not an event, but they contain the departure keywords "terminated" and "termination of employment". Furner was appointed, not departing. This is a known weakness of keyword-plus-nearest-name matching, and it inflates event row counts.

## 5C — Cross-Validation: Earnings via Yahoo Finance

Prompt used: *"Write Python using yfinance to get the most recent quarterly revenue and net income for WMT."* The resulting script is `hw03/hw03_yfinance_check.py`.

yfinance output (run 2026-09-30):

```
WMT most recent quarter ended: 2026-07-31
  Revenue (Total Revenue): $187,937.0M
  Net Income (Net Income): $6,366.0M
  Diluted EPS (Diluted EPS): $0.80
```

| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | $187,900.0M | $187,937.0M | Yes, within rounding (0.02%) |
| Net Income | $6,366.0M (net income attributable to Walmart) | $6,366.0M | Yes, exact |

Explanation: the two sources agree.
- **Period:** yfinance's most recent quarter ended 2026-07-31, the same quarter as the Q2 FY27 earnings 8-K filed 2026-08-20, so there is no period mismatch.
- **Revenue:** the $37M gap is a precision difference, not an error. The pipeline takes the narrative headline ("Revenue of $187.9 billion"), which is rounded to $0.1 billion, while yfinance reports the exact income-statement figure (Total revenues $187,937M). Both match the "Total revenues" line in Walmart's official release.
- **Net income:** this matches exactly. It also confirms that yfinance's "Net Income" uses the same definition the pipeline was built to prefer: consolidated net income attributable to Walmart, which excludes the noncontrolling-interest share.
- **EPS:** yfinance's diluted EPS of $0.80 also matches the CSV and the 5A official figure.
- **Possible improvement:** to remove the rounding gap, the revenue pattern could take the income-statement "Total revenues" row ahead of the narrative headline.

## 5D — Pipeline Integrity Checks

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies × 4 quarters) | 20 | Pass |
| `executive_events.csv` row count | At least 0 (document actual) | 38 rows from 19 Item 5.02 filings | Pass |
| `corporate_events_timeline.csv` created | Yes | Yes, 38 rows | Pass |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | 0 (no `NOT_FOUND` values anywhere in the earnings CSV) | Pass |

Additional observation: `executive_events.csv` has 2 rows with `event_type = NOT_FOUND` (MSFT 2025-12-08 and NVDA 2026-03-06). These are Item 5.02 filings with no departure or appointment wording, most likely compensation-only filings under Item 5.02(e). The pipeline keeps them on purpose so they stay visible in the data.
