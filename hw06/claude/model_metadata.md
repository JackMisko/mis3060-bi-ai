# Model metadata: hw06.pbix

> **Timing note:** this metadata was exported on 11/11/2026, before format strings were set and before measure 11 (`Top 10 Client Share`) was added. So the measures table shows no FormatString and lists 15 measures, not 16. The formats as built are listed in `powerbi/measures.md`.


Exported from Power BI Desktop **DAX query view** on the Apporto virtual desktop (11/11/2026) with the three `INFO.VIEW` queries from `powerbi_dax_guide.md` §2. The raw tab-separated output is in `hw06_metadata.txt`; this file presents it as tables.

Power BI's *Auto date/time* option adds hidden `DateTableTemplate_…` / `LocalDateTable_…` tables. They are listed separately at the end of each section and are not part of the star schema.

## 1. Columns (`INFO.VIEW.COLUMNS`)

78 model columns + 21 hidden auto-date columns.

| Table | Column | Data type | DAX formula | Hidden |
|---|---|---|---|---|
| _Measures | Column1 | Text |  | false |
| dim_advisor | advisor_id | Integer |  | false |
| dim_advisor | aum_target_mm | Integer |  | false |
| dim_advisor | certifications | Text |  | false |
| dim_advisor | first_name | Text |  | false |
| dim_advisor | last_name | Text |  | false |
| dim_advisor | region | Text |  | false |
| dim_advisor | years_experience | Integer |  | false |
| dim_benchmark | asset_class | Text |  | false |
| dim_benchmark | benchmark_id | Integer |  | false |
| dim_benchmark | name | Text |  | false |
| dim_benchmark | ticker_proxy | Text |  | false |
| dim_client | advisor_id | Integer |  | false |
| dim_client | age | Integer |  | false |
| dim_client | city | Text |  | false |
| dim_client | client_id | Integer |  | false |
| dim_client | client_since | Date |  | false |
| dim_client | client_tier | Text |  | false |
| dim_client | first_name | Text |  | false |
| dim_client | initial_aum | Number |  | false |
| dim_client | is_active | True/False |  | false |
| dim_client | last_name | Text |  | false |
| dim_client | primary_account_type | Text |  | false |
| dim_client | risk_profile | Text |  | false |
| dim_client | state | Text |  | false |
| dim_client | zip_code | Text |  | false |
| dim_date | Date | Date |  | false |
| dim_date | date_id | Integer |  | false |
| dim_date | day_of_week | Text |  | false |
| dim_date | is_month_end | Integer |  | false |
| dim_date | is_quarter_end | Integer |  | false |
| dim_date | is_trading_day | Integer |  | false |
| dim_date | is_year_end | Integer |  | false |
| dim_date | Month | Integer |  | false |
| dim_date | month_name | Text |  | false |
| dim_date | Quarter | Integer |  | false |
| dim_date | week_of_year | Integer |  | false |
| dim_date | Year | Integer |  | false |
| dim_security | asset_class | Text |  | false |
| dim_security | benchmark_id | Integer |  | false |
| dim_security | expense_ratio_bps | Integer |  | false |
| dim_security | is_etf | True/False |  | false |
| dim_security | name | Text |  | false |
| dim_security | sector | Text |  | false |
| dim_security | security_id | Integer |  | false |
| dim_security | ticker | Text |  | false |
| fact_fees | advisor_id | Integer |  | false |
| fact_fees | amount | Number |  | false |
| fact_fees | aum_basis | Number |  | false |
| fact_fees | bps_charged | Number |  | false |
| fact_fees | client_id | Integer |  | false |
| fact_fees | fee_date | Date |  | false |
| fact_fees | fee_id | Integer |  | false |
| fact_fees | fee_type | Text |  | false |
| fact_portfolio_snapshot | account_type | Text |  | false |
| fact_portfolio_snapshot | active_alpha_ytd | Number |  | false |
| fact_portfolio_snapshot | advisor_id | Integer |  | false |
| fact_portfolio_snapshot | aum | Number |  | false |
| fact_portfolio_snapshot | benchmark_id | Integer |  | false |
| fact_portfolio_snapshot | benchmark_return_ytd | Number |  | false |
| fact_portfolio_snapshot | cash_pct | Number |  | false |
| fact_portfolio_snapshot | client_id | Integer |  | false |
| fact_portfolio_snapshot | is_return_suspect | Integer |  | false |
| fact_portfolio_snapshot | Month | Integer |  | false |
| fact_portfolio_snapshot | return_ytd | Number |  | false |
| fact_portfolio_snapshot | snapshot_date | Date |  | false |
| fact_portfolio_snapshot | snapshot_id | Integer |  | false |
| fact_portfolio_snapshot | Year | Integer |  | false |
| fact_transactions | advisor_id | Integer |  | false |
| fact_transactions | amount | Number |  | false |
| fact_transactions | client_id | Integer |  | false |
| fact_transactions | is_post_departure_txn | Integer |  | false |
| fact_transactions | price | Number |  | false |
| fact_transactions | security_id | Integer |  | false |
| fact_transactions | shares | Number |  | false |
| fact_transactions | txn_date | Date |  | false |
| fact_transactions | txn_id | Integer |  | false |
| fact_transactions | txn_type | Text |  | false |

<details><summary>Hidden auto-date columns (21)</summary>

| Table | Column | Data type | DAX formula |
|---|---|---|---|
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | Date | Date |  |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | Day | Integer | DAY([Date]) |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | Quarter | Text | "Qtr " & [QuarterNo] |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | QuarterNo | Integer | INT(([MonthNo] + 2) / 3) |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | Month | Text | FORMAT([Date], "MMMM") |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | MonthNo | Integer | MONTH([Date]) |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | Year | Integer | YEAR([Date]) |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | QuarterNo | Integer | INT(([MonthNo] + 2) / 3) |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | Date | Date |  |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | Year | Integer | YEAR([Date]) |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | MonthNo | Integer | MONTH([Date]) |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | Month | Text | FORMAT([Date], "MMMM") |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | Day | Integer | DAY([Date]) |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | Quarter | Text | "Qtr " & [QuarterNo] |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | Year | Integer | YEAR([Date]) |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | MonthNo | Integer | MONTH([Date]) |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | Month | Text | FORMAT([Date], "MMMM") |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | QuarterNo | Integer | INT(([MonthNo] + 2) / 3) |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | Quarter | Text | "Qtr " & [QuarterNo] |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | Day | Integer | DAY([Date]) |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | Date | Date |  |

</details>

## 2. Relationships (`INFO.VIEW.RELATIONSHIPS`)

12 model relationships, all active, many-to-one, single cross-filter direction (+ 2 to hidden auto-date tables). Note: the posted model has **no** `dim_client[advisor_id] → dim_advisor` relationship.

| From (many) | To (one) | Cardinality | Cross-filter | Active |
|---|---|---|---|---|
| fact_transactions[advisor_id] | dim_advisor[advisor_id] | Many : One | OneDirection | true |
| fact_transactions[client_id] | dim_client[client_id] | Many : One | OneDirection | true |
| fact_transactions[security_id] | dim_security[security_id] | Many : One | OneDirection | true |
| fact_transactions[txn_date] | dim_date[date] | Many : One | OneDirection | true |
| fact_portfolio_snapshot[advisor_id] | dim_advisor[advisor_id] | Many : One | OneDirection | true |
| fact_portfolio_snapshot[benchmark_id] | dim_benchmark[benchmark_id] | Many : One | OneDirection | true |
| fact_portfolio_snapshot[client_id] | dim_client[client_id] | Many : One | OneDirection | true |
| fact_portfolio_snapshot[snapshot_date] | dim_date[date] | Many : One | OneDirection | true |
| fact_fees[advisor_id] | dim_advisor[advisor_id] | Many : One | OneDirection | true |
| fact_fees[client_id] | dim_client[client_id] | Many : One | OneDirection | true |
| fact_fees[fee_date] | dim_date[date] | Many : One | OneDirection | true |
| dim_security[benchmark_id] | dim_benchmark[benchmark_id] | Many : One | OneDirection | true |

Hidden auto-date relationships: dim_client[client_since] → LocalDateTable_9…; dim_date[date] → LocalDateTable_3…

## 3. Measures (`INFO.VIEW.MEASURES`)

15 measures, all in `_Measures`, all State = Valid. Format strings were not yet set at export time.

| Measure | DAX formula | Format | State |
|---|---|---|---|
| Total Fees | `SUM ( fact_fees[amount] )` |  | Valid |
| Net Flows | `CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" ) - CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" )` |  | Valid |
| AUM (naive SUM) | `SUM ( fact_portfolio_snapshot[aum] )` |  | Valid |
| Ending AUM | `CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) )` |  | Valid |
| Ending Clients | `CALCULATE ( DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) )` |  | Valid |
| Avg AUM per Client | `DIVIDE ( [Ending AUM], [Ending Clients] )` |  | Valid |
| Ending AUM LY | `CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )` |  | Valid |
| AUM YoY % | `DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] )` |  | Valid |
| Ending AUM PM | `CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) )` |  | Valid |
| AUM MoM % | `DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] )` |  | Valid |
| Avg Monthly AUM | `DIVIDE ( SUM ( fact_portfolio_snapshot[aum] ), DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] ) )` |  | Valid |
| Fee Yield (bps) | `DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) )` |  | Valid |
| Organic Growth Rate | `DIVIDE ( [Net Flows], [Ending AUM LY] )` |  | Valid |
| AUM-Weighted Alpha | `VAR LastSnapshot = LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) RETURN CALCULATE ( DIVIDE ( SUMX ( fact_portfolio_snapshot, fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ), SUM ( fact_portfolio_snapshot[aum] ) ), LastSnapshot, fact_portfolio_snapshot[is_return_suspect] = 0 )` |  | Valid |
| Alpha Signal | `VAR a = [AUM-Weighted Alpha] RETURN SWITCH ( TRUE (), ISBLANK ( a ), BLANK (), a >= 0.02, "Outperforming", a <= -0.02, "Lagging", "In line" )` |  | Valid |

## 4. What the metadata cannot tell Claude (added by hand)

| Table | Grain (one row per …) | Notes |
|---|---|---|
| fact_portfolio_snapshot | client per month; `snapshot_date` is always the **1st** of the month (60 dates, 2020-01-01 … 2024-12-01) | `aum` is a **balance** (semi-additive: sum across clients, last value across time). `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd` are **year-to-date rates** (non-additive). `cash_pct` is a rate. `is_return_suspect` = 1 flags 3,875 rows with unreliable returns. Clients who leave stop having rows (175 departed clients). |
| fact_fees | client per month; `fee_date` is the 1st of the month | `amount` additive; `aum_basis` is a balance (= that month's snapshot `aum`); `bps_charged` is an annual rate. |
| fact_transactions | one transaction | `amount` is always positive; direction comes from `txn_type` (Deposit, Withdrawal, Buy, Sell, Dividend, Advisory Fee). Cash rows have blank `security_id`. |
| dim_date | one calendar day, 2020-01-01 … 2024-12-31 | Marked as the date table; facts join on `dim_date[date]`. |

Last-snapshot rule used throughout: `LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )`. `LASTDATE`/`ENDOFMONTH` return a date with no snapshot.
