# Part D prompt: measure 11 (Top 10 Client Share)

**How to use:** open **Claude Desktop**, start a new chat, **attach `claude/model_metadata.md`**, paste everything in the box below, and send. Copy the whole conversation (prompt and full reply, plus any follow-ups) into `claude/dax_session.md`.

---

```
I'm building a DAX measure library in Power BI Desktop for a wealth-management star schema (Wildcat Capital). The attached model_metadata.md is the output of the INFO.VIEW.COLUMNS, INFO.VIEW.RELATIONSHIPS and INFO.VIEW.MEASURES queries from my model. Use only the table, column and measure names in it.

What the metadata does not show:
- fact_portfolio_snapshot has one row per client per month. snapshot_date is always the 1st of the month (60 dates, 2020-01-01 to 2024-12-01). Clients who leave the firm stop having rows, so a departed client's last row can be years before the latest snapshot.
- aum is a balance (semi-additive): it can be summed across clients for one date, but never summed across months. active_alpha_ytd and return_ytd are year-to-date rates.
- dim_date is marked as the date table and the facts join to dim_date[date]. Because snapshots fall on the 1st, my existing [Ending AUM] measure uses LASTNONBLANK over dim_date[date] rather than LASTDATE.
- All measures live in the _Measures table. Reuse existing measures such as [Ending AUM] where that is correct.

The measure I need: "Top 10 Client Share" = the share of Ending AUM held by the 10 largest clients within the current filter context. It must work in a card (no filters), in a table by dim_date[year], and in a table by dim_client[client_tier] filtered to 2024. A suggested starting point is TOPN over VALUES ( dim_client[client_id] ).

Please give me:
1. The DAX for the measure.
2. A step-by-step explanation of its filter context: which rows the numerator and denominator see, how the 10 clients are chosen, and what happens at the grand total, in a year row, and in a client_tier row.
3. A DAX query I can run in DAX query view to test it at the grand total, by dim_date[year], and by dim_client[client_tier] for 2024.
4. Any edge cases or ways this measure could mislead a manager.
```

---

## Expected values to verify against (pandas, `reports/pandas_values.csv`)
Do **not** paste these into the prompt; they are for checking Claude's answer.

| Slice | Top 10 Client Share |
|---|---:|
| Grand total | 6.16% |
| 2024 HNW | 3.14% |
| 2024 Retail | 1.83% |
| 2024 UHNW | 8.13% |
