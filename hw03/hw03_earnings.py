"""
HW3 - Earnings Pipeline (SEC 8-K Item 2.02)

For five companies, pulls the four most recent quarterly earnings press releases
from SEC EDGAR, extracts revenue, diluted EPS, net income and the reporting
period from the release text, prints one line per filing, and saves the rows
to hw03/earnings_history.csv.

Run from the repository root:
    python hw03/hw03_earnings.py
"""

import csv
import html
import re
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": "MIS3060 Villanova jmiskiew@villanova.edu",
    "Accept-Encoding": "gzip, deflate",
}

COMPANIES = [
    {"company": "Apple Inc.", "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation", "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.", "ticker": "JPM", "cik": "0000019617"},
    {"company": "Walmart Inc.", "ticker": "WMT", "cik": "0000104169"},
]

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR / "earnings_history.csv"
RAW_TEXT_DIR = SCRIPT_DIR / "raw_text"

CSV_COLUMNS = [
    "company", "ticker", "cik", "filing_date", "period",
    "revenue_reported", "eps_diluted", "net_income",
]

NOT_FOUND = "NOT_FOUND"
NARRATIVE_CHARS = 5000          # headline results live in the opening text
LOOKBACK_CHARS = 60             # window checked for "adjusted" / "non-GAAP" / "excluding"
SAME_QUARTER_DAYS = 45          # filings closer than this are treated as the same quarter

REQUEST_PAUSE = 0.2             # seconds; keeps us under SEC's 10 requests/second
RETRY_WAITS = [2, 4, 8]         # seconds between retries


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

# Sends every HTTP GET in this script. Always sets the SEC User-Agent header,
# pauses after each request, retries on 429/5xx/connection errors, and
# returns None (never raises) if the request ultimately fails.
def sec_get(url):
    attempts = len(RETRY_WAITS) + 1
    for attempt in range(attempts):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException:
            resp = None
        finally:
            time.sleep(REQUEST_PAUSE)

        if resp is not None:
            if resp.status_code == 200:
                return resp
            if resp.status_code == 403:
                print("WARNING: SEC returned 403 — check the User-Agent header")
                return None
            if resp.status_code != 429 and resp.status_code < 500:
                return None  # e.g. 404: retrying will not help

        if attempt < len(RETRY_WAITS):
            time.sleep(RETRY_WAITS[attempt])
    return None


# ---------------------------------------------------------------------------
# Step 1 and 2: filing list and quarter selection
# ---------------------------------------------------------------------------

# Downloads a company's submissions JSON and returns its Item 2.02 8-K filings
# (newest first) as a list of dicts. Returns None if the download fails.
def get_filings(cik):
    resp = sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if resp is None:
        return None
    try:
        recent = resp.json()["filings"]["recent"]
    except (ValueError, KeyError):
        return None

    keys = ["accessionNumber", "filingDate", "reportDate", "form", "items", "primaryDocument"]
    count = len(recent.get("accessionNumber", []))
    records = []
    for i in range(count):
        rec = {k: (recent.get(k) or [""] * count)[i] for k in keys}
        items = [x.strip() for x in (rec["items"] or "").split(",")]
        if rec["form"] == "8-K" and "2.02" in items:
            records.append(rec)

    records.sort(key=lambda r: r["filingDate"], reverse=True)
    return records


# Picks up to four filings, newest first, skipping any filing within 45 days
# of one already chosen so that each quarter is represented only once.
def select_recent_quarters(filings, limit=4):
    selected = []
    for rec in filings:
        d = date.fromisoformat(rec["filingDate"])
        if any(abs((d - date.fromisoformat(s["filingDate"])).days) < SAME_QUARTER_DAYS
               for s in selected):
            continue
        selected.append(rec)
        if len(selected) == limit:
            break
    return selected


# ---------------------------------------------------------------------------
# Step 3: find the press release exhibit
# ---------------------------------------------------------------------------

BAD_EXTENSIONS = (".pdf", ".xml", ".jpg", ".jpeg", ".gif", ".png", ".xsd", ".txt")


# Turns an index-page link into a full sec.gov URL, removing the inline-XBRL
# viewer prefix (/ix?doc=) when present.
def clean_link(href):
    href = href.strip()
    if href.startswith("/ix?doc="):
        href = href[len("/ix?doc="):]
    if href.startswith("http"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    return "https://www.sec.gov" + href


# Downloads the filing index page and returns the URL of the earnings press
# release exhibit (.htm), or None if no suitable exhibit exists.
def find_exhibit_url(cik, accession):
    cik_int = int(cik)
    acc_nodash = accession.replace("-", "")
    index_url = (f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
                 f"{acc_nodash}/{accession}-index.htm")
    resp = sec_get(index_url)
    if resp is None:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []  # (type, filename, href)
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            link = tds[2].find("a")
            if link is None or not link.get("href"):
                continue
            filename = link.get_text(strip=True) or link["href"].rsplit("/", 1)[-1]
            doc_type = tds[3].get_text(strip=True).upper()
            rows.append((doc_type, filename, link["href"]))

    def is_htm(name):
        lower = name.lower()
        return lower.endswith((".htm", ".html")) and not lower.endswith(BAD_EXTENSIONS)

    # 1) Type exactly EX-99.1
    for doc_type, filename, href in rows:
        if doc_type == "EX-99.1" and is_htm(filename):
            return clean_link(href)
    # 2) Any EX-99 type
    for doc_type, filename, href in rows:
        if doc_type.startswith("EX-99") and is_htm(filename):
            return clean_link(href)
    # 3) Filename looks like an exhibit 99
    for doc_type, filename, href in rows:
        lower = filename.lower()
        if is_htm(filename) and ("ex99" in lower or "ex-99" in lower or "ex991" in lower):
            return clean_link(href)
    return None


# ---------------------------------------------------------------------------
# Step 4: HTML to plain text
# ---------------------------------------------------------------------------

# Strips HTML down to a single line of normalized plain text.
def html_to_text(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for tag in soup.find_all(["ix:header"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    text = html.unescape(text)
    text = re.sub(r"[  -​  　]", " ", text)
    text = (text.replace("‘", "'").replace("’", "'")
                .replace("“", '"').replace("”", '"')
                .replace("–", "-").replace("—", "-"))
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Saves the plain text so failed extractions can be debugged later.
def save_raw_text(ticker, filing_date, text):
    RAW_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_TEXT_DIR / f"{ticker}_{filing_date}.txt").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Step 5: field extraction helpers
# ---------------------------------------------------------------------------

FLAGS = re.IGNORECASE
NON_GAAP_WORDS = ("adjusted", "non-gaap", "excluding")

# Returns the text just before position `pos` (up to 60 characters), cut off
# at the nearest bullet, semicolon or sentence break so that a word like
# "adjusted" in the previous bullet does not disqualify this one.
def lookback(text, pos, chars=LOOKBACK_CHARS):
    window = text[max(0, pos - chars):pos]
    parts = re.split(r"[•;]|\.\s|\|", window)
    return parts[-1].lower()


# True if the words just before a match mark it as a non-GAAP / adjusted figure.
def is_non_gaap(text, pos, extra_words=()):
    before = lookback(text, pos)
    return any(w in before for w in NON_GAAP_WORDS + tuple(extra_words))


# Converts a regex match of MONEY into USD millions (float), or None if the
# unit cannot be determined.
def to_millions(match, full_text):
    num = float(match.group("num").replace(",", ""))
    unit = (match.group("unit") or "").lower()
    if unit == "billion":
        value = num * 1000
    elif unit == "million":
        value = num
    elif re.search(r"in millions", full_text, FLAGS):
        value = num
    else:
        return None
    if match.group("neg"):
        value = -value
    return round(value, 1)


# Runs every pattern over `scope`, returning the earliest match that passes the
# non-GAAP check (and any extra rejection words).
def earliest_match(patterns, scope, extra_reject=()):
    hits = []
    for pat in patterns:
        for m in re.finditer(pat, scope, FLAGS):
            hits.append(m)
    hits.sort(key=lambda m: m.start())
    for m in hits:
        if not is_non_gaap(scope, m.start(), extra_reject):
            return m
    return None


# Searches the narrative (first 5,000 chars) and then the full text:
# narrative patterns first, table patterns second, in each scope.
# `extra_reject` words (e.g. segment names) only apply to narrative sentences;
# table rows sit next to unrelated labels, so they only get the non-GAAP check.
def search_scopes(text, narrative_patterns, table_patterns, extra_reject=()):
    for scope in (text[:NARRATIVE_CHARS], text):
        m = earliest_match(narrative_patterns, scope, extra_reject)
        if m:
            return m
        m = earliest_match(table_patterns, scope)
        if m:
            return m
    return None


# ---------------------------------------------------------------------------
# Step 5: the four extractors
# ---------------------------------------------------------------------------

REVENUE_LABEL = (r"(?:total net sales|net sales|total revenues|total net revenue|"
                 r"reported revenue|consolidated revenue|net revenue|revenues|revenue)")
REVENUE_CONNECTOR = (r"(?:of|was|were|totaled|reached|"
                     r"(?:increased|grew|was up|up|rose)\s+\d+(?:\.\d+)?\s?%\s+to)")
# Words just before "revenue" that mean it is a segment, not the company total.
SEGMENT_WORDS = (
    "managed", "data center", "cloud", "services", "gaming", "automotive",
    "visualization", "segment", "markets", "banking", "lending", "card",
    "wealth", "payments", "ecommerce", "e-commerce", "advertising", "iphone",
    "mac ", "ipad", "wearables", "international", "sam's club", "u.s.",
    "productivity", "computing", "networking", "search", "linkedin",
)


# Extracts quarterly revenue in USD millions, or NOT_FOUND.
def extract_revenue(text):
    narrative = [
        # "Revenue was $76.4 billion", "reported revenue of $44.9 billion"
        rf"\b{REVENUE_LABEL}\s+{REVENUE_CONNECTOR}\s+" + r"(?P<neg>\()?\$\s?(?P<num>\d[\d,]*(?:\.\d+)?)\s?(?P<unit>billion|million)?\b",
        # NVIDIA: "revenue for the second quarter ended July 27, 2025, of $46.7 billion"
        rf"\b{REVENUE_LABEL}\s+for the \w+ quarter[^$]{{0,60}}?\bof\s+" + r"(?P<neg>\()?\$\s?(?P<num>\d[\d,]*(?:\.\d+)?)\s?(?P<unit>billion|million)?\b",
    ]
    table = [
        # "Total net sales (1) $ 94,930", "Total revenues $187,937", "Net revenue - reported $ 44,912"
        r"\b(?:total net sales|total revenues|total net revenue|net revenue\s?-\s?reported|revenue)"
        r"\s*(?:\(\w\)\s*)?\s+" + r"(?P<neg>\()?\$?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?)\)?(?P<unit>)",
    ]
    m = search_scopes(text, narrative, table, extra_reject=SEGMENT_WORDS)
    if not m:
        return NOT_FOUND
    value = to_millions(m, text)
    return NOT_FOUND if value is None else value


# Extracts GAAP diluted EPS as a float with 2 decimals, or NOT_FOUND.
def extract_eps(text):
    eps_num = r"(?P<neg>\()?\$\s?(?P<num>\d+\.\d{2})"
    narrative = [
        r"\bdiluted earnings per share\s*(?:\([a-z0-9]\)\s*)?(?:of|was|were|:)?\s*" + eps_num,
        r"\bearnings per diluted share[^$]{0,40}?" + eps_num,
        r"\bdiluted EPS\d?\s*(?:of|was|were|:)?\s*" + eps_num,
        r"\bEPS\d?\s*(?:of|was|were|:)?\s*" + eps_num,
        # JPMorgan headline: "NET INCOME OF $15.0 BILLION ( $5.24 PER SHARE)"
        r"\(\s?" + eps_num + r"\s+per (?:diluted )?share\)",
        r"\bor\s+" + eps_num + r"\s+per (?:diluted )?share",
    ]
    table = [
        # JPMorgan: "Earnings per share - diluted $ 5.24"
        r"\bearnings per share\s?-\s?diluted\s*\$?\s?(?P<neg>\()?(?P<num>\d+\.\d{2})",
        # Walmart: "Diluted net income per common share attributable to Walmart 0.80"
        r"\bdiluted net income per (?:common )?share(?: attributable to [A-Za-z.&' ]{1,40}?)?\s*\$?\s?(?P<neg>\()?(?P<num>\d+\.\d{2})",
        # NVIDIA summary table: "Diluted earnings per share $1.08"
        r"\bdiluted earnings per share\s*\$?\s?(?P<neg>\()?(?P<num>\d+\.\d{2})",
        # Apple: "Earnings per share: Basic $ 0.97 $ 1.47 Diluted $ 0.97"
        r"\bearnings per share:?\s*basic[\s$\d.,()]{0,80}?\bdiluted\s*\$?\s?(?P<neg>\()?(?P<num>\d+\.\d{2})",
    ]
    m = search_scopes(text, narrative, table, extra_reject=("dividend",))
    if not m:
        return NOT_FOUND
    value = float(m.group("num"))
    if m.group("neg"):
        value = -value
    return round(value, 2)


# Extracts GAAP net income in USD millions, or NOT_FOUND. Prefers the
# "net income attributable to <Company>" row when the release has one.
def extract_net_income(text, company_name=""):
    money = r"(?P<neg>\()?\s?\$?\s?(?P<num>\d[\d,]*(?:\.\d+)?)\)?"
    narrative = [
        r"\bnet income\s+(?:of|was|were)\s+(?P<neg>\()?\$\s?(?P<num>\d[\d,]*(?:\.\d+)?)\s?(?P<unit>billion|million)\b",
    ]
    table = [r"\bnet income(?!\s*(?:attributable to noncontrolling|per |margin|\())\s+" + money + r"(?P<unit>)"]

    first_word = company_name.split()[0] if company_name else ""
    if first_word:
        attributable = (r"\bnet income attributable to " + re.escape(first_word)
                        + r"[A-Za-z.&' ]{0,30}?\s+" + money + r"(?P<unit>)")
        for scope in (text[:NARRATIVE_CHARS], text):
            m = earliest_match(narrative, scope)
            if m:
                break
            m = earliest_match([attributable], scope)
            if m:
                break
        else:
            m = None
        if m:
            value = to_millions(m, text)
            return NOT_FOUND if value is None else value

    m = search_scopes(text, narrative, table)
    if not m:
        return NOT_FOUND
    value = to_millions(m, text)
    return NOT_FOUND if value is None else value


ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
ORDINAL_WORDS = {1: "first", 2: "second", 3: "third", 4: "fourth"}
ORD = r"(?P<ord>first|second|third|fourth)"


# Converts a 2- or 4-digit year string to a 4-digit int.
def four_digit_year(y):
    y = int(y)
    return 2000 + y if y < 100 else y


# Extracts the reporting period as "{ordinal} quarter fiscal {YYYY}", or NOT_FOUND.
def extract_period(text):
    patterns = [
        # "fourth quarter fiscal year 2025", "second quarter of fiscal 2026", "second-quarter 2025"
        r"\b" + ORD + r"[\s-]quarter\s+(?:of\s+)?(?:fiscal\s+(?:year\s+)?|FY\s?)?(?P<year>\d{4})\b",
        # Apple: "fiscal 2025 third quarter"
        r"\bfiscal\s+(?:year\s+)?(?P<year>\d{4})\s+" + ORD + r"[\s-]quarter",
        # "Q2 FY26", "Q2 fiscal 2026"
        r"\bQ(?P<q>[1-4])\s*(?:FY\s?|fiscal\s+(?:year\s+)?)'?(?P<year>\d{4}|\d{2})\b",
        # "FY25 Q4"
        r"\bFY\s?'?(?P<year>\d{4}|\d{2})\s*Q(?P<q>[1-4])\b",
        # JPMorgan: "2Q25"
        r"\b(?P<q>[1-4])Q\s?(?P<year>\d{2})\b",
    ]
    for scope in (text[:NARRATIVE_CHARS], text):
        hits = []
        for pat in patterns:
            hits.extend(re.finditer(pat, scope, FLAGS))
        if not hits:
            continue
        m = min(hits, key=lambda h: h.start())
        groups = m.groupdict()
        if groups.get("ord"):
            q = ORDINALS[groups["ord"].lower()]
        else:
            q = int(groups["q"])
        year = four_digit_year(groups["year"])
        return f"{ORDINAL_WORDS[q]} quarter fiscal {year}"
    return NOT_FOUND


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

# Formats a value for the console line: money as "$94,930.0M", EPS as "$1.64".
def fmt(value, kind):
    if value == NOT_FOUND:
        return NOT_FOUND
    if kind == "money":
        return f"${value:,.1f}M"
    return f"${value:.2f}"


# Prints one processed row in the required format.
def print_row(row):
    print(f"{row['ticker']} | {row['period']} | "
          f"Revenue: {fmt(row['revenue_reported'], 'money')} | "
          f"EPS: {fmt(row['eps_diluted'], 'eps')} | "
          f"Net Income: {fmt(row['net_income'], 'money')}")


# Writes all rows to earnings_history.csv (overwriting any previous run).
def write_csv(rows):
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            out = {k: row[k] for k in CSV_COLUMNS}
            for k in ("revenue_reported", "net_income"):
                if out[k] != NOT_FOUND:
                    out[k] = f"{out[k]:.1f}"
            if out["eps_diluted"] != NOT_FOUND:
                out["eps_diluted"] = f"{out['eps_diluted']:.2f}"
            writer.writerow(out)


# Builds a row with identifying fields filled and every extracted field NOT_FOUND.
def empty_row(co, filing_date):
    return {
        "company": co["company"], "ticker": co["ticker"], "cik": co["cik"],
        "filing_date": filing_date, "period": NOT_FOUND,
        "revenue_reported": NOT_FOUND, "eps_diluted": NOT_FOUND, "net_income": NOT_FOUND,
    }


# Handles one filing end to end: find exhibit, download, strip, extract.
def process_filing(co, rec):
    row = empty_row(co, rec["filingDate"])
    exhibit_url = find_exhibit_url(co["cik"], rec["accessionNumber"])
    resp = sec_get(exhibit_url) if exhibit_url else None
    if resp is None:
        print(f"WARNING: {co['ticker']} {rec['filingDate']} — press release exhibit not found, continuing")
        return row

    text = html_to_text(resp.text)
    save_raw_text(co["ticker"], rec["filingDate"], text)

    row["period"] = extract_period(text)
    row["revenue_reported"] = extract_revenue(text)
    row["eps_diluted"] = extract_eps(text)
    row["net_income"] = extract_net_income(text, co["company"])
    return row


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Runs the pipeline for all five companies, then writes the CSV and a summary.
def main():
    rows = []
    for co in COMPANIES:
        filings = get_filings(co["cik"])
        if filings is None:
            print(f"WARNING: {co['ticker']} could not load submissions — skipping company")
            continue

        selected = select_recent_quarters(filings)
        if len(selected) < 4:
            print(f"NOTE: {co['ticker']} has only {len(selected)} Item 2.02 filings available")

        for rec in selected:
            try:
                row = process_filing(co, rec)
            except Exception as exc:  # one bad filing must not stop the run
                print(f"WARNING: {co['ticker']} {rec['filingDate']} — unexpected error: {exc}")
                row = empty_row(co, rec["filingDate"])
            print_row(row)
            rows.append(row)

    write_csv(rows)

    print(f"\nSaved {len(rows)} rows to hw03/earnings_history.csv")
    print("NOT_FOUND counts per field:")
    for field in ("period", "revenue_reported", "eps_diluted", "net_income"):
        n = sum(1 for r in rows if r[field] == NOT_FOUND)
        print(f"  {field}: {n}")
    all_missing = sum(
        1 for r in rows
        if r["revenue_reported"] == NOT_FOUND and r["eps_diluted"] == NOT_FOUND
        and r["net_income"] == NOT_FOUND
    )
    print(f"Rows with revenue, EPS and net income all NOT_FOUND: {all_missing}")


if __name__ == "__main__":
    main()
