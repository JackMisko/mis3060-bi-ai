# HW6 DAX build sheet: copy and paste into Power BI

> **As built:** every currency measure uses Currency, 2 decimals; percentages and alpha use Percentage, 2 decimals; Fee Yield uses Decimal, 2 decimals; Ending Clients uses Whole number with a thousands separator. An earlier plan used 0 decimals for currency. Expected values below may still be shown rounded to whole dollars.


Working file for building `hw06.pbix`. The graded write-up goes in `measures.md`; this sheet is just the paste source.

## 0. Setup (Apporto)
1. Open `Wildcat_Star_Model (1).pbix` → **File → Save as** → `hw06.pbix` (Documents, the persistent drive).
2. **Model view:** confirm there are **11 relationships**, all many-to-one with single direction, and that `dim_date` is marked as the date table. Note which 2 of our HW5 relationships are missing.
3. **Home → Enter data** → name it `_Measures` → **Load**.
4. For each measure below: right-click `_Measures` → **New measure** → paste → Enter. Then set the format in **Measure tools → Format**.
5. After the first measure, delete the empty `Column1` from `_Measures`.

> Measure names must match exactly (including spaces, `%` and brackets). The reconciliation script joins on them.

## 1. Base measures (from the ICEs)

```DAX
Total Fees = SUM ( fact_fees[amount] )
```
Format: Currency, 2 decimals

```DAX
Net Flows =
CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" )
    - CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" )
```
Format: Currency, 2 decimals

## 2. Measure library (Part A)

**0 · The trap (never on a report)**
```DAX
AUM (naive SUM) = SUM ( fact_portfolio_snapshot[aum] )
```
Format: Currency, 2 decimals. Description: *WRONG: adds monthly balances across months. Kept only for comparison.*

**1 · Ending AUM** (last balance)
```DAX
Ending AUM =
CALCULATE (
    SUM ( fact_portfolio_snapshot[aum] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
Format: Currency, 2 decimals. **Check now:** a card should show **$12,729,572,079**.

**2 · Ending Clients**
```DAX
Ending Clients =
CALCULATE (
    DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
Format: Whole number, thousands separator. Expected: **2,325**

**3 · Avg AUM per Client**
```DAX
Avg AUM per Client = DIVIDE ( [Ending AUM], [Ending Clients] )
```
Format: Currency, 2 decimals. Expected: **$5,475,085**

**4 · Ending AUM LY and AUM YoY %**
```DAX
Ending AUM LY = CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )
```
```DAX
AUM YoY % = DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] )
```
Formats: Currency 2 decimals; Percentage 2 decimals. Expected 2024: **19.58%**, 2020: **blank** (no prior year; do not add a 0 alternate).

**5 · Ending AUM PM and AUM MoM %**
```DAX
Ending AUM PM = CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) )
```
```DAX
AUM MoM % = DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] )
```
Formats: Currency 2 decimals; Percentage 2 decimals. Expected Dec 2024: PM **$12,211,162,448**, MoM **4.25%**

**6 · Avg Monthly AUM**
```DAX
Avg Monthly AUM =
DIVIDE (
    SUM ( fact_portfolio_snapshot[aum] ),
    DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] )
)
```
Format: Currency, 2 decimals. Expected total: **$9,444,684,742**

**7 · Fee Yield (bps)** (two fact tables)
```DAX
Fee Yield (bps) = DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) )
```
Format: Decimal, 2 decimals. Expected total: **43.34**, 2024: **43.15**

**8 · Organic Growth Rate**
```DAX
Organic Growth Rate = DIVIDE ( [Net Flows], [Ending AUM LY] )
```
Format: Percentage, 2 decimals. Expected 2024: **0.73%**, 2024 Retail: **9.87%**

**9 · AUM-Weighted Alpha** (last snapshot, suspects excluded)
```DAX
AUM-Weighted Alpha =
VAR LastSnapshot =
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
RETURN
    CALCULATE (
        DIVIDE (
            SUMX (
                fact_portfolio_snapshot,
                fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd]
            ),
            SUM ( fact_portfolio_snapshot[aum] )
        ),
        LastSnapshot,
        fact_portfolio_snapshot[is_return_suspect] = 0
    )
```
Format: Percentage, 2 decimals. Expected total / 2024: **1.45%**, 2022: **2.85%**

**10 · Alpha Signal** (text)
```DAX
Alpha Signal =
VAR a = [AUM-Weighted Alpha]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( a ), BLANK (),
        a >= 0.02, "Outperforming",
        a <= -0.02, "Lagging",
        "In line"
    )
```
Expected: 2022 **Outperforming**, 2024 Retail **Outperforming**, everything else **In line**

**11 · Top 10 Client Share**: built in **Part D** with the Claude Draft → Test → Debug → Review workflow (expected total: **6.16%**).

## 3. Export query (run after all 12 measures exist)

In **DAX query view**, paste and run the query below, click **Copy** on the result grid, paste it into Notepad, and save it as `hw06/reports/powerbi_export.tsv`. The reconciliation script reshapes it into `powerbi_values.csv`. `FORMAT ( …, "0.000000000000" )` sends every number as exact text with 12 decimals, because the results grid rounds to 2 decimals on screen. Blank measures come out as empty text.

```DAX
EVALUATE
UNION (
    ROW (
        "slice", "total",
        "AUM (naive SUM)", FORMAT ( [AUM (naive SUM)], "0.000000000000" ),
        "Ending AUM", FORMAT ( [Ending AUM], "0.000000000000" ),
        "Ending Clients", FORMAT ( [Ending Clients], "0.000000000000" ),
        "Avg AUM per Client", FORMAT ( [Avg AUM per Client], "0.000000000000" ),
        "Ending AUM LY", FORMAT ( [Ending AUM LY], "0.000000000000" ),
        "AUM YoY %", FORMAT ( [AUM YoY %], "0.000000000000" ),
        "Ending AUM PM", FORMAT ( [Ending AUM PM], "0.000000000000" ),
        "AUM MoM %", FORMAT ( [AUM MoM %], "0.000000000000" ),
        "Avg Monthly AUM", FORMAT ( [Avg Monthly AUM], "0.000000000000" ),
        "Fee Yield (bps)", FORMAT ( [Fee Yield (bps)], "0.000000000000" ),
        "Organic Growth Rate", FORMAT ( [Organic Growth Rate], "0.000000000000" ),
        "AUM-Weighted Alpha", FORMAT ( [AUM-Weighted Alpha], "0.000000000000" ),
        "Alpha Signal", [Alpha Signal],
        "Top 10 Client Share", FORMAT ( [Top 10 Client Share], "0.000000000000" )
    ),
    SELECTCOLUMNS (
        VALUES ( dim_date[year] ),
        "slice", "year=" & dim_date[year],
        "AUM (naive SUM)", FORMAT ( [AUM (naive SUM)], "0.000000000000" ),
        "Ending AUM", FORMAT ( [Ending AUM], "0.000000000000" ),
        "Ending Clients", FORMAT ( [Ending Clients], "0.000000000000" ),
        "Avg AUM per Client", FORMAT ( [Avg AUM per Client], "0.000000000000" ),
        "Ending AUM LY", FORMAT ( [Ending AUM LY], "0.000000000000" ),
        "AUM YoY %", FORMAT ( [AUM YoY %], "0.000000000000" ),
        "Ending AUM PM", FORMAT ( [Ending AUM PM], "0.000000000000" ),
        "AUM MoM %", FORMAT ( [AUM MoM %], "0.000000000000" ),
        "Avg Monthly AUM", FORMAT ( [Avg Monthly AUM], "0.000000000000" ),
        "Fee Yield (bps)", FORMAT ( [Fee Yield (bps)], "0.000000000000" ),
        "Organic Growth Rate", FORMAT ( [Organic Growth Rate], "0.000000000000" ),
        "AUM-Weighted Alpha", FORMAT ( [AUM-Weighted Alpha], "0.000000000000" ),
        "Alpha Signal", [Alpha Signal],
        "Top 10 Client Share", FORMAT ( [Top 10 Client Share], "0.000000000000" )
    ),
    CALCULATETABLE (
        SELECTCOLUMNS (
            VALUES ( dim_client[client_tier] ),
            "slice", "year=2024|tier=" & dim_client[client_tier],
            "AUM (naive SUM)", FORMAT ( [AUM (naive SUM)], "0.000000000000" ),
            "Ending AUM", FORMAT ( [Ending AUM], "0.000000000000" ),
            "Ending Clients", FORMAT ( [Ending Clients], "0.000000000000" ),
            "Avg AUM per Client", FORMAT ( [Avg AUM per Client], "0.000000000000" ),
            "Ending AUM LY", FORMAT ( [Ending AUM LY], "0.000000000000" ),
            "AUM YoY %", FORMAT ( [AUM YoY %], "0.000000000000" ),
            "Ending AUM PM", FORMAT ( [Ending AUM PM], "0.000000000000" ),
            "AUM MoM %", FORMAT ( [AUM MoM %], "0.000000000000" ),
            "Avg Monthly AUM", FORMAT ( [Avg Monthly AUM], "0.000000000000" ),
            "Fee Yield (bps)", FORMAT ( [Fee Yield (bps)], "0.000000000000" ),
            "Organic Growth Rate", FORMAT ( [Organic Growth Rate], "0.000000000000" ),
            "AUM-Weighted Alpha", FORMAT ( [AUM-Weighted Alpha], "0.000000000000" ),
            "Alpha Signal", [Alpha Signal],
            "Top 10 Client Share", FORMAT ( [Top 10 Client Share], "0.000000000000" )
        ),
        dim_date[year] = 2024
    ),
    CALCULATETABLE (
        ROW (
            "slice", "month=2024-12",
            "AUM (naive SUM)", FORMAT ( [AUM (naive SUM)], "0.000000000000" ),
            "Ending AUM", FORMAT ( [Ending AUM], "0.000000000000" ),
            "Ending Clients", FORMAT ( [Ending Clients], "0.000000000000" ),
            "Avg AUM per Client", FORMAT ( [Avg AUM per Client], "0.000000000000" ),
            "Ending AUM LY", FORMAT ( [Ending AUM LY], "0.000000000000" ),
            "AUM YoY %", FORMAT ( [AUM YoY %], "0.000000000000" ),
            "Ending AUM PM", FORMAT ( [Ending AUM PM], "0.000000000000" ),
            "AUM MoM %", FORMAT ( [AUM MoM %], "0.000000000000" ),
            "Avg Monthly AUM", FORMAT ( [Avg Monthly AUM], "0.000000000000" ),
            "Fee Yield (bps)", FORMAT ( [Fee Yield (bps)], "0.000000000000" ),
            "Organic Growth Rate", FORMAT ( [Organic Growth Rate], "0.000000000000" ),
            "AUM-Weighted Alpha", FORMAT ( [AUM-Weighted Alpha], "0.000000000000" ),
            "Alpha Signal", [Alpha Signal],
            "Top 10 Client Share", FORMAT ( [Top 10 Client Share], "0.000000000000" )
        ),
        dim_date[year] = 2024,
        dim_date[month] = 12
    )
)
```
