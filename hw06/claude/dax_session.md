# Part D: Claude DAX session (measure 11, Top 10 Client Share)

- **Tool:** Claude Desktop, new chat, 11/11/2026
- **Workflow step:** Draft (Week 10, Draft → Test → Debug → Review)
- **Context supplied:** the model metadata from the three INFO.VIEW queries (full export in `model_metadata.md`, condensed inline below), plus the grain, additivity and business definition the metadata cannot show.
- **Note:** a first attempt that attached `model_metadata.md` instead of pasting the metadata confused the chat, so the prompt was rewritten to be self-contained. The prompt below is the one that produced the answer.

---

## Prompt

```
I'm building a DAX measure library in Power BI Desktop for a wealth-management star schema (Wildcat Capital). Below is my model metadata, exported from DAX query view with INFO.VIEW.COLUMNS, INFO.VIEW.RELATIONSHIPS and INFO.VIEW.MEASURES. Use ONLY these table, column and measure names.

=== COLUMNS (table: columns) ===
fact_portfolio_snapshot: snapshot_id, client_id, advisor_id, benchmark_id, snapshot_date (Date), Year, Month, aum (Number), return_ytd, benchmark_return_ytd, active_alpha_ytd, cash_pct, account_type, is_return_suspect (Integer 0/1)
fact_fees: fee_id, client_id, advisor_id, fee_date (Date), fee_type, aum_basis, bps_charged, amount
fact_transactions: txn_id, client_id, advisor_id, security_id, txn_date (Date), txn_type, shares, price, amount, is_post_departure_txn
dim_client: client_id, first_name, last_name, age, city, state, zip_code, risk_profile, client_tier (Retail / HNW / UHNW), primary_account_type, initial_aum, client_since, advisor_id, is_active
dim_advisor: advisor_id, first_name, last_name, region, years_experience, aum_target_mm, certifications
dim_date: date_id, date (Date), year, quarter, month, month_name, week_of_year, day_of_week, is_month_end, is_quarter_end, is_year_end, is_trading_day
dim_security: security_id, ticker, name, asset_class, sector, benchmark_id, is_etf, expense_ratio_bps
dim_benchmark: benchmark_id, name, asset_class, ticker_proxy
_Measures: (measures only)

=== RELATIONSHIPS (all active, many-to-one, single direction) ===
fact_portfolio_snapshot[client_id] -> dim_client[client_id]
fact_portfolio_snapshot[advisor_id] -> dim_advisor[advisor_id]
fact_portfolio_snapshot[benchmark_id] -> dim_benchmark[benchmark_id]
fact_portfolio_snapshot[snapshot_date] -> dim_date[date]
fact_fees[client_id] -> dim_client[client_id]
fact_fees[advisor_id] -> dim_advisor[advisor_id]
fact_fees[fee_date] -> dim_date[date]
fact_transactions[client_id] -> dim_client[client_id]
fact_transactions[advisor_id] -> dim_advisor[advisor_id]
fact_transactions[security_id] -> dim_security[security_id]
fact_transactions[txn_date] -> dim_date[date]
dim_security[benchmark_id] -> dim_benchmark[benchmark_id]

=== EXISTING MEASURES (in _Measures) ===
Total Fees = SUM ( fact_fees[amount] )
Ending AUM = CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) )
Ending Clients = CALCULATE ( DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) )
Ending AUM LY = CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )
AUM-Weighted Alpha = VAR LastSnapshot = LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) RETURN CALCULATE ( DIVIDE ( SUMX ( fact_portfolio_snapshot, fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ), SUM ( fact_portfolio_snapshot[aum] ) ), LastSnapshot, fact_portfolio_snapshot[is_return_suspect] = 0 )
(plus Net Flows, Avg AUM per Client, AUM YoY %, Ending AUM PM, AUM MoM %, Avg Monthly AUM, Fee Yield (bps), Organic Growth Rate, Alpha Signal)

=== WHAT THE METADATA DOESN'T SHOW ===
- fact_portfolio_snapshot has ONE ROW PER CLIENT PER MONTH. snapshot_date is always the 1st of the month (60 dates, 2020-01-01 to 2024-12-01). Clients who leave the firm stop having rows, so a departed client's last row can be years before the latest snapshot.
- aum is a BALANCE (semi-additive): sum it across clients for one date, never across months. active_alpha_ytd and return_ytd are year-to-date rates.
- dim_date is marked as the date table and the facts join on dim_date[date]. Because snapshots fall on the 1st, Ending AUM uses LASTNONBLANK, not LASTDATE.

=== WHAT I NEED ===
Measure name: Top 10 Client Share
Definition: the share of Ending AUM held by the 10 largest clients within the current filter context.
It must work in a card (no filters), in a table by dim_date[year], and in a table by dim_client[client_tier] filtered to 2024. A suggested starting point is TOPN over VALUES ( dim_client[client_id] ).

Please give me:
1. The DAX for the measure.
2. A step-by-step explanation of its filter context: which rows the numerator and denominator see, how the 10 clients are chosen, and what happens at the grand total, in a year row, and in a client_tier row.
3. A DAX query I can run in DAX query view to test it at the grand total, by dim_date[year], and by dim_client[client_tier] for 2024.
4. Any edge cases or ways this measure could mislead a manager.
```

---

## Claude's full response

## 1. The DAX

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

Format: Percentage, 2 decimals.

This starts from your suggested `TOPN` over `VALUES ( dim_client[client_id] )`, with one change: it **fixes the snapshot date before ranking**. Don't rank clients by `[Ending AUM]`. Inside a loop over clients, `[Ending AUM]` runs `LASTNONBLANK` again for each client, so each client gets their *own* last snapshot. A client who left in 2021 would then compete on their 2021 balance. Fixing the date first means everyone is compared on the same day.

## 2. How the filter context works

**Step 1: `LastSnapshot`.** In whatever filters the visual applies, find the latest `dim_date[date]` that has at least one snapshot row. This is the same rule Ending AUM uses, which is what keeps the denominator in step with Ending AUM.

**Step 2: `ClientAUM`.** `VALUES ( dim_client[client_id] )` lists every client allowed by the current `dim_client` filters. A tier filter limits the list, but date filters don't: the relationship only filters from `dim_client` to the fact, not back. So departed clients are still in the list. For each client, `CALCULATE` turns that row into a client filter. `CALCULATETABLE` adds the `LastSnapshot` date filter, so `@aum` is that client's balance on that one date.

**Step 3: `ActiveClients`.** Clients with no row on that date get a blank `@aum`. These are departed clients and clients who hadn't joined yet. They're removed here, so they can't take a top-10 slot or count in the total.

**Step 4: `Top10`.** `TOPN` keeps the 10 rows with the largest `@aum`. If the 10th place is tied, it keeps all the tied clients, so you can get more than 10.

**Step 5: Numerator and denominator.**
- The **numerator** is the summed balance of those top clients on `LastSnapshot`.
- The **denominator** is the summed balance of all active clients on `LastSnapshot`. That's the same number as `[Ending AUM]` in the same context.

**How it behaves in each visual:**

| Context | `LastSnapshot` | Clients ranked | Denominator |
|---|---|---|---|
| Card, no filters | 2024-12-01 | Every client with a row on 2024-12-01 | Firm Ending AUM |
| Table row `year = 2022` | 2022-12-01 (last snapshot that year) | Clients with a row on 2022-12-01 | Ending AUM for 2022 |
| Table row `client_tier = HNW`, filtered to 2024 | Last 2024 date with an HNW row (normally 2024-12-01) | HNW clients only | HNW Ending AUM for 2024 |
| Total row of either table | Same as the card for that table's filters | All clients, re-ranked | Firm (or 2024) Ending AUM |

If a context has no snapshot rows at all, `LastSnapshot` comes back empty and the measure returns blank instead of 0.

## 3. Test query

Paste this into DAX query view:

```DAX
EVALUATE
UNION (
    ROW (
        "Slice", "Grand total",
        "Top 10 Client Share", [Top 10 Client Share],
        "Ending AUM", [Ending AUM],
        "Ending Clients", [Ending Clients]
    ),
    SELECTCOLUMNS (
        VALUES ( dim_date[year] ),
        "Slice", "Year " & dim_date[year],
        "Top 10 Client Share", [Top 10 Client Share],
        "Ending AUM", [Ending AUM],
        "Ending Clients", [Ending Clients]
    ),
    CALCULATETABLE (
        SELECTCOLUMNS (
            VALUES ( dim_client[client_tier] ),
            "Slice", "2024 " & dim_client[client_tier],
            "Top 10 Client Share", [Top 10 Client Share],
            "Ending AUM", [Ending AUM],
            "Ending Clients", [Ending Clients]
        ),
        dim_date[year] = 2024
    )
)
ORDER BY [Slice]
```

Then run this second query to see which clients are counted at the grand total. Add up their `aum` and divide by the grand-total Ending AUM; you should get the measure's value.

```DAX
EVALUATE
VAR d = CALCULATE ( MAX ( fact_portfolio_snapshot[snapshot_date] ) )
RETURN
    TOPN (
        10,
        ADDCOLUMNS (
            VALUES ( dim_client[client_id] ),
            "aum", CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), dim_date[date] = d )
        ),
        [aum], DESC
    )
ORDER BY [aum] DESC
```

**What a correct result looks like:**
- The grand total equals the `Year 2024` row, because both use 2024-12-01.
- Every value is between 0 and 1.
- If a share is above 100%, or the measure's denominator doesn't match Ending AUM, departed clients are being counted somewhere.

## 4. Edge cases and ways it could mislead a manager

1. **Shares don't add up.** Tier shares don't sum to anything meaningful, and a table's total row is not the sum or average of its rows; it re-ranks all clients. Say this next to the table.
2. **Small groups always look concentrated.** A tier with 10 or fewer clients shows 100%, and a tier with 15 clients will look very concentrated whatever the reality. UHNW is the likely case. Put `Ending Clients` beside the share so the size of each group is visible.
3. **It's the top 10 at each date, not the same 10 clients.** A trend by year shows how concentration changed. It doesn't follow particular clients, so a falling line could just mean a big client left.
4. **It's a point-in-time number.** A year row reflects the balance on the 1st of that year's last snapshot month (for example 2022-12-01, not 12/31). A large client who joined and left inside the year never shows up.
5. **Ties can make it more than 10 clients.** With identical balances, `TOPN` includes all tied clients. This is rare with continuous AUM values, but worth one line in the documentation.
6. **The dangerous version looks fine on the card.** If someone rewrites it with `RANKX` or `TOPN` over `[Ending AUM]` per client, departed clients come back with old balances. The result can look reasonable on the card and still be wrong in year and tier rows. Keep the fixed-date step and explain why in the measure description.
7. **A client is not a household.** A family split across several `client_id`s is counted as separate clients, so the measure can understate real relationship concentration.
8. **Slicing by advisor works, but only through the fact table.** `dim_client[advisor_id]` has no relationship, so advisor filters reach the measure via `fact_portfolio_snapshot[advisor_id]`. That's fine here, because the fact rows carry the advisor for that month. Just don't build an advisor slicer from `dim_client`.
