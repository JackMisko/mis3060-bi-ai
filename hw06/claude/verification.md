# Verification — Measure 11: Top 10 Client Share

**Measure tested:** Claude Desktop's `Top 10 Client Share` (full prompt and response are in `dax_session.md`).
**Where:** `powerbi/hw06.pbix`, `_Measures` table, format Percentage (2 dp). Verified 11/11/2026.
**Who did what:** Claude Desktop drafted the measure (`dax_session.md`). The steps below were carried out in a Claude session at my direction:
- entering the measure in Power BI on Apporto, through the browser
- running the test query
- the pandas checks

I reviewed every result. "I" below means that session, working on my behalf.

## 1. Did it run as written?
Yes. The measure was entered in `_Measures` **exactly as Claude wrote it**, collapsed onto one line, so the only change was whitespace. It validated with no errors on the first try. **No DAX was changed.** This is the text in the pbix, with Claude's line breaks restored:

```DAX
Top 10 Client Share =
VAR LastSnapshot =
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
VAR ClientAUM =
    CALCULATETABLE (
        ADDCOLUMNS (
            VALUES ( dim_client[client_id] ),
            "@aum", CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) )
        ),
        LastSnapshot
    )
VAR ActiveClients =
    FILTER ( ClientAUM, NOT ISBLANK ( [@aum] ) )
VAR Top10 =
    TOPN ( 10, ActiveClients, [@aum], DESC )
VAR Top10AUM = SUMX ( Top10, [@aum] )
VAR TotalAUM = SUMX ( ActiveClients, [@aum] )
RETURN
    DIVIDE ( Top10AUM, TotalAUM )
```

*(An earlier draft of this file showed the last two VARs folded into the RETURN line. That was a documentation shortcut only. The measure in the pbix keeps Claude's `Top10AUM` and `TotalAUM` variables.)*

## 2. Test query results vs pandas
In DAX query view I ran **an adapted version of Claude's suggested test query** (not word for word): a UNION of the grand total, one row per year, and the 2024 tiers. The measure was wrapped in `FORMAT(...,"0.000000")` because the grid rounds to 2 decimals. Ending AUM and Ending Clients were added as cross-checks. The pandas column comes from `scripts/01_reconcile_measures.py` (`reports/pandas_values.csv`). The script reconciles Top 10 Client Share at the total, for every year and for the three 2024 tiers.

| Slice | Power BI | pandas | Ending AUM (PBI) | Ending Clients | Match |
|---|---|---|---|---|---|
| Grand total | 0.061589 | 0.061589 | 12,729,572,078.86 | 2,325 | ✅ |
| Year 2020 | 0.070411 | 0.070411 | 8,130,190,789.37 | 1,847 | ✅ |
| Year 2021 | 0.063754 | 0.063754 | 10,010,301,949.11 | 2,157 | ✅ |
| Year 2022 | 0.055309 | 0.055309 | 9,308,159,286.53 | 2,500 | ✅ |
| Year 2023 | 0.060379 | 0.060379 | 10,644,971,737.00 | 2,325 | ✅ |
| Year 2024 | 0.061589 | 0.061589 | 12,729,572,078.86 | 2,325 | ✅ |
| 2024 HNW | 0.031397 | 0.031397 | 2,548,521,154.33 | 687 | ✅ |
| 2024 Retail | 0.018348 | 0.018348 | 533,452,497.89 | 1,394 | ✅ |
| 2024 UHNW | 0.081264 | 0.081264 | 9,647,598,426.64 | 244 | ✅ |

The 9 `Top 10 Client Share` rows in `reports/measure_reconciliation.csv` are the formal proof. They cover slices `total`, `year=2020` … `year=2024` and `year=2024|tier=HNW/Retail/UHNW`; all match, with abs_diff < 1e-12. That file is produced by the reconciliation script from the Power BI export.

## 3. Edge cases checked
1. **Grand total, no filter.** It returns 6.16%, identical to the Year 2024 row. This is correct: with no date filter, LASTNONBLANK lands on 2024-12-01, the latest snapshot. The grand total is **not** a sum or average of the yearly shares (2020's share is 7.04%, yet the total is 6.16%).
2. **Year 2022, the peak client count (2,500).** The result is 5.53%. It is the lowest concentration of any year, because the base is widest just before the 175 departures.
3. **2024 tiers.** Each tier ranks only its own clients, so the tier values are not parts of the total. UHNW (8.13%) is more concentrated than the firm overall, and Retail (1.83%) is the least concentrated.
4. **Denominator check.** Claude's `TotalAUM` variable sums every active client's balance at the shared `LastSnapshot`, which is the same definition as `[Ending AUM]`. The pandas top-10 calculation uses that same denominator. Since every share matches pandas and the Ending AUM column matches pandas, the denominators agree.

## 4. Claims from Claude's answer
- **Confirmed: the departed-client trap.** Claude warned that ranking clients by `[Ending AUM]` evaluated per client would give each client *their own* last snapshot. Departed clients would then keep stale balances in the pool. I tested a naive version in pandas that uses each client's own last balance:

  | Slice | Correct (shared last date) | Naive (own last date) | Naive denominator |
  |---|---|---|---|
  | Grand total | 6.16% | **5.96%** | 13,149,297,713.80 (2,500 clients) |
  | Year 2023 | 6.04% | **5.84%** | 11,003,691,413.65 (2,487 clients) |
  | 2020–2022, 2024 | identical | identical | (no clients left during these years) |

  The naive grand-total denominator is $419.7M too high. That is exactly the last balances of the 175 departed clients, so the naive version would be wrong at the grand total and in 2023. Claude's version pins every client to one shared `LastSnapshot`, which avoids the problem.
- **Refuted: "UHNW may be a small group (about 10–15 clients), so the top 10 could be nearly 100%."** Ending Clients for 2024 UHNW is **244**, and the top 10 hold only 8.13% of UHNW AUM. The concern would matter for a tiny segment, but it does not apply to this data.
- **Confirmed: there is no `dim_client → dim_advisor` relationship in the model** (see `model_metadata.md`, which lists 12 relationships). Claude correctly avoided relying on one.

In total: **two claims confirmed** (the departed-client trap, and no client → advisor relationship) and **one refuted** (the UHNW small-group concern).

## 5. What changed
Nothing in the DAX: Claude's measure is in the pbix as written, variables included. The only additions were the Percentage format string and the `FORMAT` wrapper, which was used in the test query only to show 6 decimals.
