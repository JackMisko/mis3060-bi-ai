# HW6 — DAX Measure Library: AUM & Performance

Model: `powerbi/hw06.pbix` (the posted `Wildcat_Star_Model.pbix` plus a `_Measures` table and a **Measures** report page).
Every value below is reconciled to pandas in `reports/measure_reconciliation.csv`: **105 of 105 rows match**.

**Additivity drives the pattern.**

| Class | Pattern | Why |
|---|---|---|
| Additive (flows: fees, deposits, withdrawals) | `SUM` | Adding months or clients gives a meaningful total |
| Semi-additive (`aum` is a **balance**) | **Last balance** | Additive across clients, never across time. Take the latest snapshot in the filter with `LASTNONBLANK(dim_date[date], CALCULATE(COUNTROWS(fact_portfolio_snapshot)))`, because snapshots fall on the 1st of the month, not the last calendar day |
| Non-additive (ratios, rates, alpha, shares) | **Recompute and weight** | Never sum or average the stored ratio. Rebuild it from its parts (DIVIDE / SUMX) in every filter context |

## Base measures (from the ICEs)
```DAX
Total Fees = SUM ( fact_fees[amount] )
Net Flows  = CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" )
           - CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" )
```
**Pattern:** SUM (additive flows).

---

## Part A — The measure library

### 0. `AUM (naive SUM)` — ⚠️ WRONG ON PURPOSE (never put it on a report)
```DAX
AUM (naive SUM) = SUM ( fact_portfolio_snapshot[aum] )
```
**Pattern:** SUM applied to a balance, which is the trap.
**Meaning:** with no filter it reports **$566.7B**, about 44× what Wildcat actually manages, because it adds 60 monthly balances together. Pandas reproduces the same wrong number, which shows both tools make the same mistake. It is kept only as a teaching contrast.
**Format:** Currency, 2 dp.

### 1. `Ending AUM`
```DAX
Ending AUM =
CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) )
```
**Pattern:** last balance (semi-additive).
**Meaning:** the assets Wildcat manages at the end of whatever period is selected. Today that is **$12.73B**.
**Format:** Currency, 2 dp.

### 2. `Ending Clients`
```DAX
Ending Clients =
CALCULATE ( DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) )
```
**Pattern:** last balance (a headcount on the last snapshot date).
**Meaning:** how many clients hold assets at period end: **2,325** today, down from a peak of 2,500 in 2022.
**Format:** Whole number with a thousands separator.

### 3. `Avg AUM per Client`
```DAX
Avg AUM per Client = DIVIDE ( [Ending AUM], [Ending Clients] )
```
**Pattern:** recompute (a ratio of two last-balance measures).
**Meaning:** the typical relationship size. It is **$5.48M** overall, ranging from $383K for Retail to $39.5M for UHNW.
**Format:** Currency, 2 dp.

### 4. `Ending AUM LY` and `AUM YoY %`
```DAX
Ending AUM LY = CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )
AUM YoY %     = DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] )
```
**Pattern:** last balance, shifted one year, then recompute.
**Meaning:** year-over-year growth in managed assets. 2024 grew **+19.58%**; 2022 fell **−7.01%**. 2020 is blank because there is no 2019 to compare with, and DIVIDE returns blank rather than an error.
**Format:** $ / Percentage, 2 dp.

### 5. `Ending AUM PM` and `AUM MoM %`
```DAX
Ending AUM PM = CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) )
AUM MoM %     = DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] )
```
**Pattern:** last balance, shifted one month, then recompute.
**Meaning:** month-to-month momentum. December 2024 grew **+4.25%** over November ($12.21B → $12.73B).
**Format:** $ / Percentage, 2 dp.

### 6. `Avg Monthly AUM`
```DAX
Avg Monthly AUM = DIVIDE ( SUM ( fact_portfolio_snapshot[aum] ),
                           DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] ) )
```
**Pattern:** recompute (the average balance across the months in the filter).
**Meaning:** the average balance that actually generated revenue during the period. It is the right denominator for revenue ratios: **$11.29B** for 2024, against a year-end $12.73B.
**Format:** Currency, 2 dp.

### 7. `Fee Yield (bps)`
```DAX
Fee Yield (bps) = DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) )
```
**Pattern:** recompute and weight across **two fact tables**: monthly fees over monthly AUM, annualized ×12 and expressed in bps ×10,000. Both sides are summed over the same months, so the ratio is dollar-weighted.
**Meaning:** what Wildcat earns per dollar managed: **43.34 bps** overall, and 82.8 bps on Retail versus 36.1 bps on UHNW in 2024.
**Format:** Decimal, 2 dp.

### 8. `Organic Growth Rate`
```DAX
Organic Growth Rate = DIVIDE ( [Net Flows], [Ending AUM LY] )
```
**Pattern:** recompute (an additive flow divided by a semi-additive balance).
**Meaning:** net new client money as a share of where the firm started the year: **0.73%** in 2024, separate from market gains.
**Format:** Percentage, 2 dp.

### 9. `AUM-Weighted Alpha`
```DAX
AUM-Weighted Alpha =
VAR LastSnapshot = LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
RETURN
CALCULATE (
    DIVIDE ( SUMX ( fact_portfolio_snapshot,
                    fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ),
             SUM ( fact_portfolio_snapshot[aum] ) ),
    LastSnapshot,
    fact_portfolio_snapshot[is_return_suspect] = 0 )
```
**Pattern:** recompute and weight (SUMX of aum × alpha ÷ Σ aum), read at the last snapshot only, with suspect returns excluded.
**Meaning:** how far the average client dollar beat or lagged its benchmark year to date: **+1.45%** for 2024.
**Format:** Percentage, 2 dp.

### 10. `Alpha Signal`
```DAX
Alpha Signal =
VAR a = [AUM-Weighted Alpha]
RETURN SWITCH ( TRUE (),
    ISBLANK ( a ), BLANK (),
    a >= 0.02,  "Outperforming",
    a <= -0.02, "Lagging",
    "In line" )
```
**Pattern:** recompute (a text label derived from measure 9 in the same filter context).
**Meaning:** a traffic-light reading for managers. 2024 overall is "In line". 2022 and 2024 Retail are "Outperforming".
**Format:** Text.

### 11. `Top 10 Client Share` (drafted with Claude; see `claude/`)
```DAX
Top 10 Client Share =
VAR LastSnapshot =
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
VAR ClientAUM =
    CALCULATETABLE (
        ADDCOLUMNS ( VALUES ( dim_client[client_id] ),
                     "@aum", CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) ),
        LastSnapshot )
VAR ActiveClients = FILTER ( ClientAUM, NOT ISBLANK ( [@aum] ) )
VAR Top10 = TOPN ( 10, ActiveClients, [@aum], DESC )
VAR Top10AUM = SUMX ( Top10, [@aum] )
VAR TotalAUM = SUMX ( ActiveClients, [@aum] )
RETURN DIVIDE ( Top10AUM, TotalAUM )
```
**Pattern:** recompute (a ranking within the current filter, at one shared last-snapshot date).
**Meaning:** concentration risk, i.e. how much of the book walks out the door if the 10 biggest clients leave. It is **6.16%** firm-wide and **8.13%** within UHNW.
**Format:** Percentage, 2 dp.

### Measures report page
- **Card:** Ending AUM, Ending Clients, Avg AUM per Client, Top 10 Client Share. The Card visual does not render on the Apporto virtual desktop, so a one-row table with the same four measures sits beside it.
- **Table by `dim_date[year]`:** Ending AUM, AUM YoY %, Avg Monthly AUM, Fee Yield (bps), Organic Growth Rate, AUM-Weighted Alpha, Alpha Signal.
- **Table by `dim_client[client_tier]`**, with a visual-level filter `dim_date[year] = 2024`: Ending AUM, Avg AUM per Client, AUM YoY %, Fee Yield (bps), Organic Growth Rate, AUM-Weighted Alpha, Alpha Signal, Top 10 Client Share.

---

## Part C — Design questions

### (a) `Ending AUM` vs `SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )`
| | Value (no filters) |
|---|---|
| `Ending AUM` | **$12,729,572,078.86** |
| `SUMX` over clients | **$13,149,297,713.80** |
| Difference | **$419,725,634.94** |

`SUMX` iterates the clients. Context transition then evaluates `[Ending AUM]` once **per client**, so LASTNONBLANK finds **each client's own** last snapshot. For the 2,325 active clients that is 2024-12-01. For the **175 clients who left**, it is their final month before departure. The $419.7M difference equals exactly the sum of those 175 clients' last balances. Pandas confirms it to the cent.

**`Ending AUM` answers "How much do we manage today?"** It evaluates one shared date for everyone, and departed clients have no row on that date. The SUMX version counts money that has already left the firm.

### (b) 2024 `Fee Yield (bps)` (43.15) < ICE 9 `Effective Fee Rate (bps)` (45.53)
Both measures are annualized fees per dollar, but their denominators differ:
- **Effective Fee Rate** divides by `fact_fees[aum_basis]`, the AUM **on the fee rows only**.
- **Fee Yield** divides by `fact_portfolio_snapshot[aum]`, **all** AUM that exists.

Pandas evidence (2024):

| Item | Value |
|---|---|
| Snapshot client-months | 27,900 |
| Fee rows | 26,216 |
| Client-months with a snapshot but **no fee row** | **1,684** (1,082 clients, scattered across all 12 months and all tiers) |
| AUM in those months | $7.07B, 5.2% of 2024 Σ aum |

Fee Yield's denominator includes that $7.07B, but its numerator has no fees for it. Every fee row's `aum_basis` equals its snapshot's AUM, so Σ aum_basis = Σ aum − $7,074,540,256.63 exactly. That gives **45.53 × (1 − 0.05223) = 43.15**, so the gap reconciles exactly, not just approximately.

**Data limitation:** fee coverage is incomplete. Some client-months were managed but never billed, or the fee records are missing. Effective Fee Rate hides the gap because it only looks at billed rows. Fee Yield exposes it as revenue leakage, so it is the more honest firm-level metric. The gaps should be investigated with billing.

### (c) Why read `AUM-Weighted Alpha` at the last snapshot, and why exclude suspects?
- **Last snapshot only:** `active_alpha_ytd` is **year-to-date**, so each month's value already includes all earlier months. Averaging or summing it across months double-counts January's performance 12 times and mixes partial-year with full-year results. Only the latest snapshot gives the full-period figure, which is the same last-balance logic used for AUM.
- **Weighting by `aum`:** the question is how the firm's money performed, not the average account. A $40M UHNW account should count more than a $40K Retail account.
- **Excluding `is_return_suspect = 1`:** those returns are flagged as data errors with extreme values. Including them distorts the result, especially in an unweighted mean.

December 2024 (2,325 rows, 148 flagged suspect):

| Calculation | Value |
|---|---|
| **AUM-weighted, suspects excluded** (the measure) | **1.45%** |
| Simple mean, suspects excluded | 0.88% |
| AUM-weighted, **suspects included** | 1.67% |
| Simple mean, suspects included (for reference) | 15.56% |

The weighted figure is higher than the simple mean (1.45% vs 0.88%), which says larger accounts outperformed smaller ones. Leaving the suspects in inflates the weighted figure by 0.22 points. In an unweighted mean they would explode it to 15.6%.

### (d) Organic Growth Rate by client tier, 2024
| Tier | Net Flows | Organic Growth | AUM YoY % | Growth not explained by flows (≈ market) |
|---|---|---|---|---|
| Retail | $44.2M | **9.87%** | 19.13% | ≈ 9.3% |
| HNW | $25.2M | 1.18% | 19.64% | ≈ 18.5% |
| UHNW | $8.1M | **0.10%** | 19.59% | ≈ 19.5% |

**What it says:** all three tiers grew AUM by about 19–20%, but for very different reasons.
- **Retail** is the only tier bringing in meaningful new money: about half its growth is net deposits.
- **UHNW**, 76% of AUM, grew almost entirely from markets; clients added essentially nothing.
- Wildcat's *client-driven* growth comes from Retail, while its *dollar* growth rides on UHNW market returns.

**What it does not tell you:**
- **Why** money moved: new clients versus existing clients adding, or retirement withdrawals.
- Whether market returns came from Wildcat's skill or simply the benchmark (that is alpha's job).
- **Client retention**, since departures mostly appear in balances, not flows.
- **Dollar scale:** Retail's 9.87% sounds large, but it is $44.2M, 57% of the firm's $77.5M in net flows and only about 0.35% of firm AUM. Retail's high rate pays the most bps, but it moves the firm total little.
- Organic growth is measured against last year's balance, so a small base, like Retail's $448M, inflates the rate.
