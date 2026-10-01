"""
HW3 Part 5C - Cross-validate earnings with yfinance.

Gets the most recent quarterly revenue and net income for a ticker from
Yahoo Finance, as a second, independent source for the 8-K text extraction.

Run from the repository root (venv active):
    python -m pip install yfinance
    python hw03/hw03_yfinance_check.py
"""

import yfinance as yf

TICKER = "WMT"


# Returns the first matching row label found in the income statement.
def pick_row(stmt, labels):
    for label in labels:
        if label in stmt.index:
            return label
    return None


def main():
    stmt = yf.Ticker(TICKER).quarterly_income_stmt
    if stmt is None or stmt.empty:
        print(f"No quarterly income statement returned for {TICKER}.")
        return

    latest = stmt.columns[0]          # columns are quarter-end dates, newest first
    print(f"{TICKER} most recent quarter ended: {latest.date()}")

    rows = {
        "Revenue": ["Total Revenue", "Operating Revenue"],
        "Net Income": ["Net Income", "Net Income Common Stockholders"],
        "Diluted EPS": ["Diluted EPS"],
    }
    for name, labels in rows.items():
        label = pick_row(stmt, labels)
        if label is None:
            print(f"  {name}: not available")
            continue
        value = stmt.loc[label, latest]
        if name == "Diluted EPS":
            print(f"  {name} ({label}): ${value:.2f}")
        else:
            print(f"  {name} ({label}): ${value / 1e6:,.1f}M")


if __name__ == "__main__":
    main()
