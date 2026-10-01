"""
HW3 - Corporate Events Timeline

Joins hw03/executive_events.csv to hw03/earnings_history.csv: for every
executive event, finds the same company's nearest earnings filing, measures the
gap in days, and labels the event 'before earnings', 'after earnings' or
'same week'. Saves hw03/corporate_events_timeline.csv and prints a summary.

Run from the repository root:
    python hw03/hw03_timeline.py
"""

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EARNINGS_PATH = SCRIPT_DIR / "earnings_history.csv"
EVENTS_PATH = SCRIPT_DIR / "executive_events.csv"
OUTPUT_PATH = SCRIPT_DIR / "corporate_events_timeline.csv"

NOT_FOUND = "NOT_FOUND"
SAME_WEEK_DAYS = 7

# Company order used for printing (matches the two pipelines).
TICKER_ORDER = ["AAPL", "MSFT", "NVDA", "JPM", "WMT"]

EVENT_COLUMNS = ["company", "ticker", "cik", "filing_date", "event_type",
                 "person_name", "title", "effective_date"]
# Earnings columns carried over from the matched earnings filing. Its
# filing_date is renamed so it does not collide with the event's filing_date.
EARNINGS_COLUMNS = ["earnings_filing_date", "period", "revenue_reported",
                    "eps_diluted", "net_income"]
OUTPUT_COLUMNS = EVENT_COLUMNS + EARNINGS_COLUMNS + ["days_to_nearest_earnings", "event_timing"]


# Reads a CSV into a list of dicts (keeping every value as text, so CIKs keep
# their leading zeros).
def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# Parses YYYY-MM-DD, returning None for NOT_FOUND or anything unparseable.
def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


# Finds the earnings filing closest in time to event_date. On a tie (one
# filing the same distance before and after), the earlier filing wins.
def nearest_earnings(event_date, earnings_rows):
    dated = [(parse_date(r["filing_date"]), r) for r in earnings_rows]
    dated = [(d, r) for d, r in dated if d is not None]
    if not dated:
        return None, None
    d, row = min(dated, key=lambda dr: (abs((event_date - dr[0]).days), dr[0]))
    return d, row


# Labels an event by its signed gap to the nearest earnings filing
# (negative = event came first). Within 7 days either way is 'same week'.
def classify(signed_days):
    if abs(signed_days) <= SAME_WEEK_DAYS:
        return "same week"
    return "before earnings" if signed_days < 0 else "after earnings"


# Builds one timeline row per executive event.
def build_timeline(events, earnings):
    earnings_by_ticker = defaultdict(list)
    for row in earnings:
        earnings_by_ticker[row["ticker"]].append(row)

    timeline = []
    for ev in events:
        out = {col: ev.get(col, NOT_FOUND) or NOT_FOUND for col in EVENT_COLUMNS}
        for col in EARNINGS_COLUMNS + ["days_to_nearest_earnings", "event_timing"]:
            out[col] = NOT_FOUND

        event_date = parse_date(ev.get("filing_date"))
        e_date, e_row = (nearest_earnings(event_date, earnings_by_ticker[ev["ticker"]])
                         if event_date else (None, None))
        if e_row is not None:
            signed = (event_date - e_date).days
            out["earnings_filing_date"] = e_row["filing_date"]
            for col in ("period", "revenue_reported", "eps_diluted", "net_income"):
                out[col] = e_row.get(col, NOT_FOUND) or NOT_FOUND
            out["days_to_nearest_earnings"] = abs(signed)
            out["event_timing"] = classify(signed)
        timeline.append(out)
    return timeline


# Writes the combined table.
def write_csv(rows):
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


# Prints each company's events with their timing, then the overall counts.
def print_summary(timeline):
    by_ticker = defaultdict(list)
    for row in timeline:
        by_ticker[row["ticker"]].append(row)
    tickers = TICKER_ORDER + sorted(t for t in by_ticker if t not in TICKER_ORDER)

    print("=== Executive events vs. nearest earnings announcement ===")
    for ticker in tickers:
        rows = by_ticker.get(ticker, [])
        print(f"\n{ticker}")
        if not rows:
            print("  No executive events in past 12 months")
            continue
        for r in sorted(rows, key=lambda r: r["filing_date"]):
            if r["event_timing"] == NOT_FOUND:
                timing = "no earnings filing to compare against"
            else:
                timing = (f"{r['event_timing']} ({r['days_to_nearest_earnings']} days from "
                          f"{r['earnings_filing_date']} earnings, {r['period']})")
            print(f"  {r['filing_date']} | {r['event_type']} | {r['person_name']} | "
                  f"{r['title']} -> {timing}")

    counts = defaultdict(int)
    for r in timeline:
        counts[r["event_timing"]] += 1
    print("\n=== Totals across all five companies ===")
    print(f"  Before earnings: {counts['before earnings']}")
    print(f"  After earnings:  {counts['after earnings']}")
    print(f"  Same week:       {counts['same week']}")
    if counts[NOT_FOUND]:
        print(f"  No comparison:   {counts[NOT_FOUND]}")
    print(f"  Total events:    {len(timeline)}")


# Reads both tables, builds the timeline, saves it, and prints the summary.
def main():
    for path in (EARNINGS_PATH, EVENTS_PATH):
        if not path.exists():
            print(f"ERROR: {path.name} not found in {SCRIPT_DIR} — run the pipeline that creates it first.")
            return

    earnings = read_csv(EARNINGS_PATH)
    events = read_csv(EVENTS_PATH)
    if not events:
        print("executive_events.csv has no rows — no executive events to place on the timeline.")

    timeline = build_timeline(events, earnings)
    write_csv(timeline)
    print_summary(timeline)
    print(f"\nSaved {len(timeline)} rows to hw03/corporate_events_timeline.csv")


if __name__ == "__main__":
    main()
