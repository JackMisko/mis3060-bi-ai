"""
HW3 - Executive Events Pipeline (SEC 8-K Item 5.02)

For five companies, finds every Item 5.02 8-K filed in the past 12 months,
extracts each director/officer departure and appointment from the filing text,
prints one line per event, and saves the events to hw03/executive_events.csv.

Run from the repository root:
    python hw03/hw03_executives.py
"""

import csv
import html
import re
import time
from datetime import date, datetime, timedelta
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
OUTPUT_PATH = SCRIPT_DIR / "executive_events.csv"
RAW_TEXT_DIR = SCRIPT_DIR / "raw_text"

CSV_COLUMNS = [
    "company", "ticker", "cik", "filing_date", "event_type",
    "person_name", "title", "effective_date",
]

NOT_FOUND = "NOT_FOUND"
WINDOW_DAYS = 365
REQUEST_PAUSE = 0.2             # seconds; keeps us under SEC's 10 requests/second
RETRY_WAITS = [2, 4, 8]         # seconds between retries

# Keyword lists. Each entry is a regex matched case-insensitively on word
# boundaries, so "elect" does not fire on "election".
DEPARTURE_KEYWORDS = [
    r"resign(?:s|ed|ation)?", r"retire(?:s|d|ment)?", r"step(?:s|ped)? down",
    r"stepping down", r"depart(?:s|ed|ure)?", r"will leave", r"terminated",
    r"termination of (?:his |her )?employment",
    r"will not stand for re-?election", r"not to stand for re-?election",
    r"ceased to serve",
]
# Not in the spec's list: role changes worded as "will transition from his role
# as X to Y" or "will transition his role as X to <Name>" are handled by the
# TRANSITION_* patterns in extract_events.
APPOINTMENT_KEYWORDS = [
    r"appoint(?:s|ed|ment)?", r"elect(?:s|ed)?",
    r"named(?! executive officers?)",   # skip the comp term "named executive officer"
    r"promoted", r"will succeed", r"will become", r"will serve as", r"hired",
]

# Title building blocks, longest / most specific first.
TITLE_PATTERNS = [
    r"lead independent director",
    r"(?:(?:executive|senior|corporate)\s+)?vice\s+president"
    r"(?:\s+of\s+(?-i:[A-Z][A-Za-z&]+)(?:\s+(?-i:[A-Z][A-Za-z&]+)){0,2})?",
    r"chief(?:\s+[a-z&]+){1,3}\s+officer",
    r"(?:executive\s+)?chair(?:man|woman|person)?(?:\s+of\s+the\s+board(?:\s+of\s+directors)?)?",
    r"general\s+counsel", r"corporate\s+secretary", r"principal\s+accounting\s+officer",
    r"principal\s+financial\s+officer", r"controller", r"treasurer",
    r"president",
    r"(?-i:director)(?!s)", r"(?-i:Director)(?!s)", r"member\s+of\s+the\s+board(?:\s+of\s+directors)?",
]
TITLE_RE = re.compile(r"\b(?:" + "|".join(TITLE_PATTERNS) + r")\b", re.IGNORECASE)

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
MONTH_RE = "|".join(MONTHS)

# Capitalized words that are never part of a person's name.
NAME_STOPWORDS = set("""
Board Directors Director Company Committee Chief Officer Officers President Vice
Executive Senior Chair Chairman Chairwoman Lead Independent Item Form Exchange
Securities Commission Inc Corporation Corp Co LLC Ltd Regulation Report Current
Annual Meeting Section Act General Counsel Secretary Treasurer Controller
Principal Financial Accounting Operating Operations Technology Legal People
Hardware Engineering Global Group Transition Date Effective Agreement Plan
Award Awards Stock Equity Compensation Incentive Program Letter Offer Exhibit
Apple Microsoft NVIDIA Nvidia JPMorgan Chase Walmart Stores Bank America U.S.
On In As The A An At By For Of To And Or If Upon Following During After Before
Mr Ms Mrs Dr He She They His Her It This That Such Each Any No There
Monday Tuesday Wednesday Thursday Friday Saturday Sunday Commonwealth State
New York California Washington Delaware Arkansas Santa Clara Cupertino Redmond
""".split()) | set(MONTHS)

SUFFIXES = {"Jr.", "Sr.", "II", "III", "IV"}
ABBREVIATIONS = {"Mr", "Ms", "Mrs", "Dr", "Jr", "Sr", "Inc", "Co", "Corp", "No", "St"}


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
# Step 1: find Item 5.02 filings in the window
# ---------------------------------------------------------------------------

# Returns the company's Item 5.02 8-K filings filed between start and end
# (inclusive), newest first, or None if the submissions request fails.
def get_5_02_filings(cik, start, end):
    resp = sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if resp is None:
        return None
    try:
        recent = resp.json()["filings"]["recent"]
    except (ValueError, KeyError):
        return None

    keys = ["accessionNumber", "filingDate", "reportDate", "form", "items", "primaryDocument"]
    count = len(recent.get("accessionNumber", []))
    columns = {k: recent.get(k) or [""] * count for k in keys}
    filings = []
    for i in range(count):
        rec = {k: columns[k][i] for k in keys}
        items = [x.strip() for x in (rec["items"] or "").split(",")]
        if rec["form"] != "8-K" or "5.02" not in items:
            continue
        try:
            filed = date.fromisoformat(rec["filingDate"])
        except ValueError:
            continue
        if start <= filed <= end:
            filings.append(rec)

    filings.sort(key=lambda r: r["filingDate"], reverse=True)
    return filings


# ---------------------------------------------------------------------------
# Step 2: download and clean the 8-K
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


# Downloads the main 8-K document, strips HTML, saves the text for debugging,
# and returns the plain text (or None if the download fails).
def download_8k_text(ticker, cik, rec):
    if not rec.get("primaryDocument"):
        return None
    acc_nodash = rec["accessionNumber"].replace("-", "")
    url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
           f"{acc_nodash}/{rec['primaryDocument']}")
    resp = sec_get(url)
    if resp is None:
        return None
    text = html_to_text(resp.text)
    RAW_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_TEXT_DIR / f"{ticker}_{rec['filingDate']}_{acc_nodash}.txt").write_text(
        text, encoding="utf-8")
    return text


# ---------------------------------------------------------------------------
# Step 3: isolate Item 5.02
# ---------------------------------------------------------------------------

# Standard Item 5.02 heading. Removed before keyword search because it
# contains "Departure", "Election" and "Appointment".
HEADING_RE = re.compile(
    r"^Item\s*5\.02\.?\s*(?:Departure of Directors or (?:Certain |Principal )?Officers[^.]*\.)?",
    re.IGNORECASE)


# Returns the text of the Item 5.02 section (heading removed), or the whole
# document if Item 5.02 cannot be found. Second value says whether it was found.
def isolate_item_502(text):
    start = re.search(r"Item\s*5\.02", text, re.IGNORECASE)
    if not start:
        return text, False
    rest = text[start.start():]
    end = len(rest)
    for m in re.finditer(r"Item\s*(\d{1,2}\.\d{2})", rest[1:], re.IGNORECASE):
        if m.group(1) != "5.02":          # later references to 5.02(c) etc. are not a new item
            end = min(end, m.start() + 1)
            break
    sig = re.search(r"\b(?:SIGNATURES?|Signatures?)\b", rest)
    if sig:
        end = min(end, sig.start())
    section = rest[:end]
    section = HEADING_RE.sub("", section, count=1).strip()
    return section, True


# ---------------------------------------------------------------------------
# Step 4: sentences, names, titles, dates
# ---------------------------------------------------------------------------

# Splits text into sentences on ". " + capital letter, without splitting after
# honorifics, "Inc.", "Co.", suffixes, or single-letter middle initials.
def split_sentences(text):
    sentences, last = [], 0
    for m in re.finditer(r"\.\s+(?=[A-Z\"(])", text):
        word = re.search(r"([A-Za-z]+)$", text[last:m.start()])
        token = word.group(1) if word else ""
        if token in ABBREVIATIONS or (len(token) == 1 and token.isupper()):
            continue
        sentences.append(text[last:m.start() + 1].strip())
        last = m.end()
    if text[last:].strip():
        sentences.append(text[last:].strip())
    return sentences


NAME_RUN_RE = re.compile(r"(?:[A-Z][A-Za-z'\-]+|[A-Z]\.)(?:\s+(?:[A-Z][A-Za-z'\-]+|[A-Z]\.))*")
HONORIFIC_RE = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.\s+([A-Z][A-Za-z'\-]+)")


# Returns candidate full names in a sentence as (start, end, name) tuples.
def name_candidates(sentence):
    found = []
    for run in NAME_RUN_RE.finditer(sentence):
        tokens = [(t.group(), run.start() + t.start(), run.start() + t.end())
                  for t in re.finditer(r"\S+", run.group())]
        segment = []
        for tok in tokens + [("", 0, 0)]:                  # sentinel flushes the last segment
            word = tok[0]
            bare = re.sub(r"'s$", "", word).rstrip(".")
            if bare in ("Jr", "Sr") and segment:
                segment.append((bare + ".", tok[1], tok[2]))
                continue
            if word and bare not in NAME_STOPWORDS and not word.endswith("'s"):
                segment.append(tok)
                continue
            if word.endswith("'s") and bare not in NAME_STOPWORDS:
                segment.append((bare, tok[1], tok[2] - 2))  # possessive ends the name
            full_words = [t for t in segment if len(t[0].rstrip(".")) > 1]
            if 2 <= len(segment) <= 4 and full_words and not segment[0][0].islower():
                start, end = segment[0][1], segment[-1][2]
                name = " ".join(t[0] for t in segment)
                suffix = re.match(r",?\s+(Jr\.|Sr\.|II|III|IV)\b", sentence[end:])
                if suffix:
                    name += " " + suffix.group(1)
                    end += suffix.end()
                found.append((start, end, name))
            segment = []
    return found


# Finds the person a keyword refers to: the full name nearest the keyword in
# the sentence, or a "Mr./Ms. Lastname" resolved against names seen earlier.
def find_name(sentence, kw_start, kw_end, known_names):
    candidates = list(name_candidates(sentence))
    for m in HONORIFIC_RE.finditer(sentence):
        last = m.group(1)
        match = next((n for n in reversed(known_names) if n.split()[-1].rstrip(".") == last
                      or (n.split()[-1] in SUFFIXES and n.split()[-2] == last)), None)
        if match:
            candidates.append((m.start(), m.end(), match))
    if not candidates:
        return NOT_FOUND, None

    def distance(c):
        start, end, _ = c
        if end <= kw_start:
            return kw_start - end
        if start >= kw_end:
            return start - kw_end
        return 0

    best = min(candidates, key=distance)
    return best[2], best


# Returns every title phrase in a sentence as (start, end, text), merging
# adjacent atoms joined by "and" / "," (e.g. "President and Chief Executive Officer").
def title_phrases(sentence):
    atoms = [(m.start(), m.end(), m.group()) for m in TITLE_RE.finditer(sentence)]
    phrases = []
    for atom in atoms:
        if phrases and re.fullmatch(r"\s*,?\s*(?:and\s+)?(?:an?\s+)?",
                                    sentence[phrases[-1][1]:atom[0]], re.IGNORECASE):
            prev = phrases[-1]
            phrases[-1] = (prev[0], atom[1], prev[2] + [atom[2]])
        else:
            phrases.append((atom[0], atom[1], [atom[2]]))
    return [(s, e, clean_title(parts)) for s, e, parts in phrases]


# Normalizes title atoms to Title Case, maps director wording to "Director",
# and joins them with " and ".
def clean_title(parts):
    small = {"and", "of", "the"}
    out = []
    for part in parts:
        if re.fullmatch(r"director|member\s+of\s+the\s+board(?:\s+of\s+directors)?", part, re.IGNORECASE):
            part = "Director"
        words = re.sub(r"\s+", " ", part).split(" ")
        part = " ".join(w if w.lower() in small and i else (w if w.isupper() else w.capitalize())
                        for i, w in enumerate(words))
        if part not in out:
            out.append(part)
    return " and ".join(out)


# Picks the title for an event. Appointments take the first title after the
# keyword (the new role); otherwise the title closest to the person's name.
def find_title(sentence, event_type, kw_end, name_span):
    phrases = title_phrases(sentence)
    if not phrases:
        return NOT_FOUND
    if event_type == "appointment":
        # The new role usually follows "as" ("appointed X, currently SVP, as CEO").
        as_match = re.search(r"\bas\s+(?!of\b)", sentence[kw_end:], re.IGNORECASE)
        if as_match:
            after_as = [p for p in phrases if p[0] >= kw_end + as_match.start()]
            if after_as:
                return after_as[0][2]
        after = [p for p in phrases if p[0] >= kw_end]
        if after:
            return after[0][2]
    anchor = name_span or (kw_end, kw_end)
    def distance(p):
        if p[1] <= anchor[0]:
            return anchor[0] - p[1]
        if p[0] >= anchor[1]:
            return p[0] - anchor[1]
        return 0
    return min(phrases, key=distance)[2]


DATE_FULL = rf"({MONTH_RE})\s+(\d{{1,2}}),?\s+(\d{{4}})"
DATE_MONTH = rf"({MONTH_RE})\s+(\d{{4}})"


# Finds "effective [as of / on ...] <date>" first in the sentence, then in the
# whole section. "effective immediately" uses the filing's reportDate.
def find_effective_date(sentence, section, report_date):
    for scope in (sentence, section):
        if re.search(r"\beffective\s+immediately\b", scope, re.IGNORECASE):
            return report_date or NOT_FOUND
        m = re.search(r"\beffective\b[^.;]{0,50}?\b" + DATE_FULL, scope, re.IGNORECASE)
        if m:
            return to_iso(m.group(1), m.group(2), m.group(3))
        m = re.search(r"\beffective\b[^.;]{0,50}?\b" + DATE_MONTH, scope, re.IGNORECASE)
        if m:
            return to_iso(m.group(1), "1", m.group(2))
    return NOT_FOUND


# Converts month name, day and year strings to YYYY-MM-DD.
def to_iso(month, day, year):
    try:
        return datetime.strptime(f"{month.title()} {int(day)} {year}", "%B %d %Y").strftime("%Y-%m-%d")
    except ValueError:
        return NOT_FOUND


KEYWORD_RES = (
    [("departure", re.compile(rf"\b{k}\b", re.IGNORECASE)) for k in DEPARTURE_KEYWORDS]
    + [("appointment", re.compile(rf"\b{k}\b", re.IGNORECASE)) for k in APPOINTMENT_KEYWORDS]
)
TRANSITION_FROM_RE = re.compile(r"\btransition(?:s|ing)?\s+from\s+(?:his|her|their)\s+role\s+as\b",
                                re.IGNORECASE)
TRANSITION_TO_NAME_RE = re.compile(r"\btransition(?:s|ing)?\s+(?:his|her|their)\s+role\s+as\b(.{0,80}?)\bto\s+"
                                   r"(?=[A-Z])", re.IGNORECASE)


# Extracts all events from one Item 5.02 section. Returns a list of dicts with
# event_type, person_name, title and effective_date (one per person + event).
def extract_events(section, report_date):
    events = []            # in order of first appearance
    known_names = []

    def add(event_type, name, title, eff):
        for ev in events:
            if ev["person_name"] == name and ev["event_type"] == event_type:
                if ev["title"] == NOT_FOUND:
                    ev["title"] = title
                if ev["effective_date"] == NOT_FOUND:
                    ev["effective_date"] = eff
                return
        events.append({"event_type": event_type, "person_name": name,
                       "title": title, "effective_date": eff})

    for sentence in split_sentences(section):
        eff = find_effective_date(sentence, section, report_date)

        # Role change for one person: "will transition from his role as CEO to Executive Chair"
        tf = TRANSITION_FROM_RE.search(sentence)
        if tf:
            name, span = find_name(sentence, tf.start(), tf.end(), known_names)
            phrases = [p for p in title_phrases(sentence) if p[0] >= tf.end()]
            old = phrases[0][2] if phrases else NOT_FOUND
            new = NOT_FOUND
            if phrases:
                to_match = re.search(r"\bto\s+", sentence[phrases[0][1]:])
                if to_match:
                    later = [p for p in phrases[1:] if p[0] >= phrases[0][1] + to_match.start()]
                    new = later[0][2] if later else NOT_FOUND
            add("both", name, f"{old} -> {new}", eff)

        # Handover: "X will transition his role as COO ... to Y"
        tt = TRANSITION_TO_NAME_RE.search(sentence)
        if tt and not tf:
            role = next((p[2] for p in title_phrases(sentence)
                         if tt.start() <= p[0] < tt.end()), NOT_FOUND)
            old_name, _ = find_name(sentence[:tt.start()], tt.start(), tt.start(), known_names)
            new_name, _ = find_name(sentence[tt.end():], 0, 0, known_names)
            add("departure", old_name, role, eff)
            add("appointment", new_name, role, eff)

        for event_type, pattern in KEYWORD_RES:
            for kw in pattern.finditer(sentence):
                name, span = find_name(sentence, kw.start(), kw.end(), known_names)
                title = find_title(sentence, event_type, kw.end(), span[:2] if span else None)
                add(event_type, name, title, eff)

        for _, _, n in name_candidates(sentence):
            if n not in known_names:
                known_names.append(n)

    # Drop nameless events when the filing already has a named event of that type.
    named_types = {e["event_type"] for e in events if e["person_name"] != NOT_FOUND}
    events = [e for e in events
              if e["person_name"] != NOT_FOUND or e["event_type"] not in named_types]

    # Same person leaving one role and taking a different one -> a single "both" row.
    merged = []
    for ev in events:
        if ev["event_type"] == "appointment":
            dep = next((m for m in merged if m["event_type"] == "departure"
                        and m["person_name"] == ev["person_name"] != NOT_FOUND
                        and NOT_FOUND not in (m["title"], ev["title"])
                        and m["title"] != ev["title"]), None)
            if dep:
                dep["event_type"] = "both"
                dep["title"] = f"{dep['title']} -> {ev['title']}"
                if dep["effective_date"] == NOT_FOUND:
                    dep["effective_date"] = ev["effective_date"]
                continue
        merged.append(ev)
    return merged


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

# Prints one event in the required format.
def print_event(row):
    print(f"{row['ticker']} | {row['filing_date']} | {row['event_type']} | "
          f"{row['person_name']} | {row['title']}")


# Writes all events to executive_events.csv (header always written).
def write_csv(rows):
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (row[k] if row[k] not in ("", None) else NOT_FOUND)
                             for k in CSV_COLUMNS})


# Builds a row for a filing whose events could not be extracted.
def not_found_row(co, filing_date):
    return {"company": co["company"], "ticker": co["ticker"], "cik": co["cik"],
            "filing_date": filing_date, "event_type": NOT_FOUND, "person_name": NOT_FOUND,
            "title": NOT_FOUND, "effective_date": NOT_FOUND}


# Handles one filing end to end and returns its event rows.
def process_filing(co, rec):
    text = download_8k_text(co["ticker"], co["cik"], rec)
    if text is None:
        print(f"WARNING: {co['ticker']} {rec['filingDate']} — could not download 8-K, continuing")
        return [not_found_row(co, rec["filingDate"])]

    section, found = isolate_item_502(text)
    if not found:
        print(f"NOTE: {co['ticker']} {rec['filingDate']} — Item 5.02 heading not found, using full text")

    events = extract_events(section, rec.get("reportDate") or "")
    if not events:
        print(f"NOTE: {co['ticker']} {rec['filingDate']} — Item 5.02 filing with no "
              f"departure/appointment detected")
        return [not_found_row(co, rec["filingDate"])]

    rows = []
    for ev in events:
        row = not_found_row(co, rec["filingDate"])
        row.update(ev)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Runs the pipeline for all five companies, then writes the CSV and a summary.
def main():
    end = date.today()
    start = end - timedelta(days=WINDOW_DAYS)
    print(f"Window: {start.isoformat()} to {end.isoformat()}")

    all_rows, summary = [], []
    for co in COMPANIES:
        filings = get_5_02_filings(co["cik"], start, end)
        if filings is None:
            print(f"WARNING: {co['ticker']} could not load submissions — skipping company")
            summary.append((co["ticker"], "failed", 0))
            continue
        if not filings:
            print(f"{co['ticker']}: No executive events in past 12 months")
            summary.append((co["ticker"], 0, 0))
            continue

        company_rows = []
        for rec in filings:
            try:
                rows = process_filing(co, rec)
            except Exception as exc:  # one bad filing must not stop the run
                print(f"WARNING: {co['ticker']} {rec['filingDate']} — unexpected error: {exc}")
                rows = [not_found_row(co, rec["filingDate"])]
            for row in rows:
                print_event(row)
            company_rows.extend(rows)
        all_rows.extend(company_rows)
        events = sum(1 for r in company_rows if r["event_type"] != NOT_FOUND)
        summary.append((co["ticker"], len(filings), events))

    write_csv(all_rows)

    print(f"\nSaved {len(all_rows)} events to hw03/executive_events.csv")
    print("Per company: filings found / events extracted")
    for ticker, n_filings, n_events in summary:
        print(f"  {ticker}: {n_filings} filings / {n_events} events")


if __name__ == "__main__":
    main()
