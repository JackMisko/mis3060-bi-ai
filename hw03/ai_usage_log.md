# AI Usage Log
**Assignment: HW3**

**Student: Jack Miskiewicz**

**Date: 9/30**

---

## 1. Prompts sent to Claude Cowork

The full text of each prompt is below. Prompts 1 and 2 are the two specifications from `hw03/specifications.md`, sent as separate conversations. Prompt 3 is the timeline prompt from the assignment.

### Prompt 1 — Specification A (Earnings Pipeline → `hw03_earnings.py`)

#### Specification A — Earnings Pipeline (Item 2.02)

##### Your task

Write a Python script saved as `hw03/hw03_earnings.py`. It pulls the four most recent quarterly earnings press releases for five companies from SEC EDGAR, extracts headline financial figures from each release, prints one line per filing, and saves everything to `hw03/earnings_history.csv`. Implement exactly what is described here. Where this specification makes a choice, follow it rather than substituting your own. Where it is silent, choose the simplest approach that does not crash and does not invent data.

The script will be run from the repository root with `python hw03/hw03_earnings.py`, inside a virtual environment that already has `requests` and `beautifulsoup4` installed.

##### Companies

Use these five companies and CIKs exactly as written. Do not look up, verify, or change the CIK numbers.

| Company | Ticker | SEC CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

Store these as a list of dictionaries at the top of the script (`company`, `ticker`, `cik`), keeping the CIK as a 10-character string with its leading zeros.

##### Libraries

- Use only `requests`, `beautifulsoup4`, and the Python standard library (`re`, `csv`, `time`, `datetime`, `pathlib`, `html`).
- Do not use pandas, EDGAR wrapper libraries (such as `edgartools` or `sec-edgar-downloader`), or the SEC XBRL APIs (`companyfacts`, `companyconcept`, `frames`). The point of this pipeline is to extract figures from the press release text itself.

##### Rules for every HTTP request

1. **User-Agent on every request.** Define a constant `HEADERS = {"User-Agent": "MIS3060 Villanova jmiskiew@villanova.edu", "Accept-Encoding": "gzip, deflate"}`. Write one helper function, `sec_get(url)`, that calls `requests.get(url, headers=HEADERS, timeout=30)`. Every HTTP request in the script must go through this helper. There must be no other `requests.get()` call anywhere in the file.
2. **Rate limit.** The SEC allows at most 10 requests per second. Inside `sec_get`, sleep 0.2 seconds after every request.
3. **Retries.** If a response has status 429 or any 5xx, or the connection fails, retry up to 3 more times, waiting 2, 4, and then 8 seconds. If the status is 403, print `WARNING: SEC returned 403 — check the User-Agent header` and treat the request as failed.
4. **Failures never crash the script.** If a request still fails after the retries, `sec_get` returns `None`. The caller prints a warning naming the ticker and URL, then moves on.

##### Step 1 — Get each company's filing list

- Request `https://data.sec.gov/submissions/CIK{cik}.json`, where `{cik}` is the 10-digit CIK with leading zeros.
- In the JSON, `filings.recent` holds parallel arrays, including `accessionNumber`, `filingDate`, `reportDate`, `form`, `items`, and `primaryDocument`. Position `i` in every array describes the same filing. Zip the arrays into one record per filing.
- Keep only records where:
  - `form` is exactly `"8-K"`. Exclude `8-K/A` amendments so the same quarter is not counted twice.
  - `"2.02"` is one of the items. The `items` value is a comma-separated string such as `"2.02,9.01"`. Split it on commas, strip whitespace, and check for `"2.02"` in the resulting list.
- Sort the kept records by `filingDate`, newest first.
- If the submissions request fails, print `WARNING: [TICKER] could not load submissions — skipping company` and continue with the next company.

##### Step 2 — Select the four most recent quarters

- Walk the sorted list and select filings until you have four.
- **One filing per quarter:** skip any filing whose `filingDate` is within 45 days of a filing you have already selected for that company. Companies sometimes file a second Item 2.02 8-K in the same quarter, and this rule keeps only the newest one.
- If a company has fewer than four qualifying filings, process the ones it has and print `NOTE: [TICKER] has only N Item 2.02 filings available`.

##### Step 3 — Find and download the press release exhibit

For each selected filing:

1. **Build the filing folder URL:**
   - `cik_int` is the CIK as an integer, with no leading zeros (for example, `320193`).
   - `acc_nodash` is the accession number with its dashes removed.
   - The folder is `https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/`.
2. **Build the filing index URL:** `{folder}{accessionNumber}-index.htm`, where the accession number keeps its dashes. For example: `https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123-index.htm`.
3. **Download the index page** and parse its document table. Each row has a Seq, Description, Document (a link), Type, and Size.
4. **Choose the press release exhibit, in this order:**
   1. The row whose Type is exactly `EX-99.1` and whose document ends in `.htm` or `.html`.
   2. Otherwise, the first row whose Type starts with `EX-99` and whose document ends in `.htm` or `.html`.
   3. Otherwise, the first `.htm` document whose filename contains `ex99`, `ex-99`, or `ex991` (case-insensitive).
   4. Never choose a `.pdf`, `.xml`, `.jpg`, `.gif`, `.xsd`, or `.txt` file.
5. **Clean up the link.** Some index links point to the inline-XBRL viewer (`/ix?doc=/Archives/...`). Remove the `/ix?doc=` prefix, then join the path with `https://www.sec.gov`.
6. **If no exhibit is found, or the download fails,** print `WARNING: [TICKER] [filing_date] — press release exhibit not found, continuing`. Still write a row for the filing with all four extracted fields set to `"NOT_FOUND"`, then continue with the next filing. Do not crash.

##### Step 4 — Strip HTML to plain text

- Parse the exhibit with `BeautifulSoup(html, "html.parser")`.
- Remove all `script` and `style` tags, and any `ix:header` element (hidden inline-XBRL metadata).
- Call `get_text(separator=" ")`.
- Unescape HTML entities.
- Replace non-breaking spaces (`\xa0`) and other Unicode spaces with normal spaces.
- Replace curly quotes and apostrophes with straight ones, and en/em dashes with `-`.
- Collapse every run of whitespace into a single space.
- Save the plain text to `hw03/raw_text/{TICKER}_{filing_date}.txt`, creating the folder if needed. This lets a failed extraction be debugged by reading the first 3,000 characters of the source.

##### Step 5 — Extract the four fields

Write one function per field: `extract_revenue`, `extract_eps`, `extract_net_income`, and `extract_period`. Each takes the plain text and returns either a value or the string `"NOT_FOUND"`.

**General rules for all fields:**

- **Match case-insensitively.**
- **Search the narrative first, then the tables.** First search the opening 5,000 characters of the text, where the headline results are stated. Only if nothing matches there, search the full text, which includes the financial statement tables.
- **Take the current quarter.** In the narrative, take the first qualifying match. In a table row, the first number after the row label is the current quarter, and later numbers are prior periods.
- **Prefer GAAP figures.** Reject a match if the 60 characters before it contain `adjusted`, `non-GAAP`, or `excluding`, and keep searching.
- **Handle units:**
  - Narrative figures carry their own unit (`billion` or `million`).
  - A table figure with no unit word is in millions if the text contains `in millions` (the usual table header). If no unit can be determined, return `"NOT_FOUND"` rather than guessing.
  - Numbers in parentheses, such as `(1,234)`, are negative.
- **Normalize money to USD millions.** Store revenue and net income as numbers in millions of US dollars, rounded to 1 decimal place, with no `$` sign and no commas. For example, `$94.9 billion` becomes `94900.0`, and `94,930` from an "in millions" table becomes `94930.0`.

**Revenue (`revenue_reported`):**

- Each company words revenue differently:

  | Company | Wording |
  |---|---|
  | Apple | "revenue of $X billion" or "Total net sales" |
  | Microsoft | "Revenue was $X billion" |
  | NVIDIA | "revenue of $X billion" or "Revenue" |
  | JPMorgan | "reported revenue of $X billion" or "Total net revenue" |
  | Walmart | "Consolidated revenue of $X billion" or "Total revenues" |

- The pattern must accept these labels: `total net sales`, `net sales`, `total revenues`, `total net revenue`, `reported revenue`, `consolidated revenue`, `net revenue`, `revenues`, `revenue`.
- It must also allow connecting words between the label and the number: `of`, `was`, `were`, `totaled`, `reached`, `increased X% to`, `grew X% to`, or `up X% to`.
- The number follows a `$` with optional whitespace: `\$\s?[\d,]+(\.\d+)?`.
- For JPMorgan, prefer "reported revenue" over "managed revenue".

**Diluted EPS (`eps_diluted`):**

- Match phrasings such as:
  - `diluted earnings per share of/was/were $X`
  - `earnings per diluted share ... $X`
  - `diluted EPS of $X`
  - `EPS of $X` (used by JPMorgan and Walmart)
- In the tables, fall back to the `Diluted` row under the earnings-per-share section.
- Store the value as a number with 2 decimal places and no `$` sign, for example `1.64`. EPS is per share, so do not convert it to millions.

**Net income (`net_income`):**

- Match `net income of/was/were $X billion/million` in the narrative.
- In the tables, fall back to the `Net income` row.
- If a row labeled `net income attributable to [company name]` exists, prefer it. This is the figure EPS is based on, which matters for Walmart.
- Normalize to USD millions as described above.

**Reporting period (`period`):**

- Normalize every period to the form `"{ordinal} quarter fiscal {YYYY}"`, for example `"fourth quarter fiscal 2024"`. The ordinal is spelled out in lowercase: first, second, third, fourth.
- Recognize these forms:
  - Apple: "fiscal 2025 third quarter" (year before quarter)
  - Microsoft: "fourth quarter fiscal year 2025"
  - NVIDIA: "second quarter of fiscal 2026"
  - JPMorgan: "second-quarter 2025" or "2Q25". JPMorgan's fiscal year is the calendar year, so write "second quarter fiscal 2025".
  - Walmart: "Q2 FY26"
  - General: `Q1`–`Q4`, `1Q`–`4Q`, spelled-out ordinals with or without a hyphen, `fiscal`, `fiscal year`, and `FY`.
- Convert two-digit years to four digits (`26` becomes `2026`).
- If no period is found, return `"NOT_FOUND"`. Do not derive the period from the filing date.

##### Step 6 — Missing values

- **Use `"NOT_FOUND"` for any failed extraction.** Whenever a field's pattern finds no match, store the exact string `"NOT_FOUND"`. Never store a blank, `None`, `0`, or `NaN`, and never fill a gap with a value from another filing or an estimate. Blank cells and missing data are different things.
- **Always fill the identifying fields.** `company`, `ticker`, `cik`, and `filing_date` come from the company list and the submissions data, so they are always filled, even when every extracted field is `"NOT_FOUND"`.
- **Never force a match.** A `"NOT_FOUND"` is better than a wrong number. Do not loosen a pattern until it matches something that is not actually the figure asked for.

##### Step 7 — Print each row as it is processed

After each filing is processed, print one line in exactly this format:

```
AAPL | fourth quarter fiscal 2024 | Revenue: $94,930.0M | EPS: $1.64 | Net Income: $14,736.0M
```

- The line is the ticker, then the period, then the three figures, separated by ` | `.
- Revenue and net income are shown in millions with thousands separators and an `M` suffix.
- EPS is shown with 2 decimal places.
- A field that was not found prints as `NOT_FOUND` with no `$` sign, for example `Revenue: NOT_FOUND`.

##### Step 8 — Save the CSV

- **Location:** save to `earnings_history.csv` in the same folder as the script, using `Path(__file__).resolve().parent / "earnings_history.csv"`. This way the file lands in `hw03/` no matter which folder the script is run from.
- **Columns, in this exact order:** `company`, `ticker`, `cik`, `filing_date`, `period`, `revenue_reported`, `eps_diluted`, `net_income`.
- **Column formats:**
  - `cik` is the 10-digit string with leading zeros.
  - `filing_date` is `YYYY-MM-DD`, taken from `filingDate`.
- **Row order:** companies in the order of the table above; within each company, newest filing first.
- **Writing:** use `csv.DictWriter` with UTF-8 encoding and `newline=""`. Overwrite the file on each run.
- **Closing summary:** after saving, print `Saved N rows to hw03/earnings_history.csv`, followed by a count of `"NOT_FOUND"` values per field and the number of rows where revenue, EPS, and net income are all `"NOT_FOUND"`.

##### Code structure

- Put constants at the top: `HEADERS`, `COMPANIES`, `OUTPUT_PATH`, `RAW_TEXT_DIR`.
- Write small, single-purpose functions: `sec_get`, `get_filings`, `select_recent_quarters`, `find_exhibit_url`, `html_to_text`, `extract_revenue`, `extract_eps`, `extract_net_income`, `extract_period`, `write_csv`, and `main`.
- End the file with `if __name__ == "__main__": main()`.
- Wrap the processing of each filing in `try/except`. An unexpected error on one filing prints a warning with the ticker, filing date, and error message, records a row with `"NOT_FOUND"` fields, and moves on.
- Add a short comment above each function explaining what it does. Do not hardcode any figure, URL, or accession number taken from a specific filing.

##### Definition of done

1. `python hw03/hw03_earnings.py` runs from start to finish without crashing.
2. It prints up to 20 rows (5 companies × 4 quarters), then the save confirmation and summary.
3. `hw03/earnings_history.csv` exists with the exact columns above, and no empty cells.
4. Check the output against the source text. Open at least one saved raw text file per company and confirm that the extracted revenue, EPS, net income, and period match what the press release says. Report any mismatches or `"NOT_FOUND"` values, and explain why each happened.

### Prompt 2 — Specification B (Executive Events Pipeline → `hw03_executives.py`)

#### Specification B — Executive Events Pipeline (Item 5.02)

##### Your task

Write a Python script saved as `hw03/hw03_executives.py`. It finds every Item 5.02 8-K filed in the past 12 months by five companies, extracts each executive or director departure and appointment, prints one line per event, and saves everything to `hw03/executive_events.csv`. Implement exactly what is described here. Where this specification makes a choice, follow it rather than substituting your own. Where it is silent, choose the simplest approach that does not crash and does not invent data.

The script will be run from the repository root with `python hw03/hw03_executives.py`, inside a virtual environment that already has `requests` and `beautifulsoup4` installed.

##### Companies

Use these five companies and CIKs exactly as written. Do not look up, verify, or change the CIK numbers.

| Company | Ticker | SEC CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

Store these as a list of dictionaries at the top of the script (`company`, `ticker`, `cik`), keeping the CIK as a 10-character string with its leading zeros.

##### Libraries

Use only `requests`, `beautifulsoup4`, and the Python standard library (`re`, `csv`, `time`, `datetime`, `pathlib`, `html`). Do not use pandas or EDGAR wrapper libraries.

##### Rules for every HTTP request

1. **User-Agent on every request.** Define a constant `HEADERS = {"User-Agent": "MIS3060 Villanova jmiskiew@villanova.edu", "Accept-Encoding": "gzip, deflate"}`. Write one helper function, `sec_get(url)`, that calls `requests.get(url, headers=HEADERS, timeout=30)`. Every HTTP request in the script must go through this helper. There must be no other `requests.get()` call anywhere in the file.
2. **Rate limit.** The SEC allows at most 10 requests per second. Inside `sec_get`, sleep 0.2 seconds after every request.
3. **Retries.** If a response has status 429 or any 5xx, or the connection fails, retry up to 3 more times, waiting 2, 4, and then 8 seconds. If the status is 403, print `WARNING: SEC returned 403 — check the User-Agent header` and treat the request as failed.
4. **Failures never crash the script.** If a request still fails after the retries, `sec_get` returns `None`. The caller prints a warning naming the ticker and URL, then moves on.

##### Step 1 — Find Item 5.02 filings from the past 12 months

- At the start, compute the window: `start = today − 365 days`, `end = today`. Print it as `Window: YYYY-MM-DD to YYYY-MM-DD`.
- For each company, request `https://data.sec.gov/submissions/CIK{cik}.json`, where `{cik}` is the 10-digit CIK with leading zeros.
- In the JSON, `filings.recent` holds parallel arrays, including `accessionNumber`, `filingDate`, `reportDate`, `form`, `items`, and `primaryDocument`. Position `i` in every array describes the same filing. Zip the arrays into one record per filing.
- Keep only records where all of these hold:
  - `form` is exactly `"8-K"`. Exclude `8-K/A` amendments so the same event is not counted twice.
  - `"5.02"` is one of the items. The `items` value is a comma-separated string such as `"5.02,9.01"`. Split it on commas, strip whitespace, and check for `"5.02"` in the list.
  - `filingDate` falls between `start` and `end`, inclusive.
- Sort the kept filings by `filingDate`, newest first.
- **If a company has no matching filings,** print exactly `[TICKER]: No executive events in past 12 months`, for example `JPM: No executive events in past 12 months`. This is valid data, not an error. Write no rows for that company and continue to the next one.
- If the submissions request fails, print `WARNING: [TICKER] could not load submissions — skipping company` and continue. A failed request is not the same as having no events, so do not print the no-events message in this case.

##### Step 2 — Download the 8-K and strip HTML

- **Build the URL:**
  - `cik_int` is the CIK as an integer, with no leading zeros.
  - `acc_nodash` is the accession number with its dashes removed.
  - The main 8-K document is at `https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{primaryDocument}`.
- **Download and clean the document:**
  - Parse it with `BeautifulSoup(html, "html.parser")`.
  - Remove `script`, `style`, and `ix:header` elements.
  - Call `get_text(separator=" ")` and unescape HTML entities.
  - Replace non-breaking spaces and other Unicode spaces with normal spaces.
  - Replace curly quotes and apostrophes with straight ones, and en/em dashes with `-`.
  - Collapse every run of whitespace into a single space.
- **Save the text** to `hw03/raw_text/{TICKER}_{filing_date}_{acc_nodash}.txt`, creating the folder if needed, for debugging.
- **If the download fails,** print `WARNING: [TICKER] [filing_date] — could not download 8-K, continuing`. Write one row for the filing with `event_type`, `person_name`, `title`, and `effective_date` all set to `"NOT_FOUND"`, then continue.

##### Step 3 — Isolate the Item 5.02 section

- Find the first match of `Item\s*5\.02` (case-insensitive).
- The section runs from that point to whichever comes first:
  - the next item heading (`Item\s*\d{1,2}\.\d{2}`, excluding the 5.02 match itself), or
  - the word `SIGNATURE`.
- If `Item 5.02` cannot be located, use the whole document text and print a note.

##### Step 4 — Extract the events

Split the section into sentences by breaking on `. ` followed by a capital letter. Do not split after common abbreviations: `Mr.`, `Ms.`, `Mrs.`, `Dr.`, `Jr.`, `Sr.`, `Inc.`, `Co.`, or single-letter middle initials such as `E.`.

**Classify each sentence:**

- **Departure keywords:** `resign`, `resigned`, `resignation`, `retire`, `retired`, `retirement`, `step down`, `stepping down`, `depart`, `departure`, `will leave`, `terminated`, `termination of employment`, `will not stand for re-election`, `not to stand for re-election`, `ceased to serve`.
- **Appointment keywords:** `appoint`, `appointed`, `appointment`, `elect`, `elected`, `named`, `promoted`, `will succeed`, `will become`, `will serve as`, `hired`.
- A sentence can contain both kinds of keyword.

**Person name:**

- A full name is 2 to 4 capitalized words. It may include a middle initial (`Jeffrey E. Williams`) and a suffix (`Jr.`, `Sr.`, `III`).
- Take the name nearest to the keyword in the same sentence.
- Reject candidates that are not names, including company names and these words: `Board`, `Directors`, `Company`, `Committee`, `Chief`, `Officer`, `President`, `Vice`, `Executive`, `Item`, `Form`, `Exchange`, `Securities`, `Inc`, `Corporation`, and month names.
- If a sentence refers to someone only by `Mr./Ms./Dr. Lastname`, match that last name to a full name found earlier in the section.
- If no name can be found, use `"NOT_FOUND"`.

**Title:**

- In the same sentence, capture the longest title phrase near the person's name. Recognized titles:
  - `Chief ___ Officer` (for example CEO, CFO, COO, CTO, CAO, CLO)
  - `President`, `Chairman`, `Chair`, `Lead Independent Director`
  - `Executive Vice President ...`, `Senior Vice President ...`
  - `General Counsel`, `Corporate Secretary`, `Controller`, `Treasurer`, `Principal Accounting Officer`
- Keep joined titles whole, for example `Senior Vice President and Chief Financial Officer`.
- If the person is described as a `director` or `member of the Board`, the title is `Director`.
- If no title is found, use `"NOT_FOUND"`.

**Effective date:**

- Look first in the same sentence, then in the rest of the section, for `effective` or `effective as of`, followed by a date in the form `Month D, YYYY` or `Month YYYY`.
- Normalize the date to `YYYY-MM-DD`. For `Month YYYY` with no day, use the first of the month.
- If the text says `effective immediately`, use the filing's `reportDate`. On an 8-K, `reportDate` is the date of the earliest event reported.
- Otherwise, use `"NOT_FOUND"`. Do not fall back to the filing date.

**Event type and rows:**

- Each event is one person plus one event type. Each event gets its own row.
- **Separate rows for separate people.** If a filing reports that one person is departing and another is being appointed (for example, a CFO retires and a successor is named), that is two rows: one `departure` and one `appointment`.
- **`both` for one person changing roles.** Use `"both"` only when the same person leaves one role and takes a different role in the same filing (for example, moving from CFO to COO). Record that as a single row, with the title written as `old title -> new title`.
- **Merge repeated mentions.** If the same person and event type appear in several sentences, merge them into one row. Take each field from whichever sentence supplied it.
- **Filings with no departure or appointment.** Some Item 5.02 filings report only compensation arrangements (Item 5.02(e)). If a filing's Item 5.02 section contains no departure or appointment keywords, write one row for it with `event_type`, `person_name`, `title`, and `effective_date` all set to `"NOT_FOUND"`, so the filing stays visible in the data. Print `NOTE: [TICKER] [filing_date] — Item 5.02 filing with no departure/appointment detected`.

##### Step 5 — Missing values

- **Use `"NOT_FOUND"` for any failed extraction.** Whenever a field cannot be extracted, store the exact string `"NOT_FOUND"`. Never store a blank, `None`, or a guessed value.
- **Always fill the identifying fields.** `company`, `ticker`, `cik`, and `filing_date` are always filled.
- **Never force a match.** A `"NOT_FOUND"` is better than a wrong name or title.

##### Step 6 — Print each event as it is processed

For every event row, print one line in exactly this format, using the filing date:

```
MSFT | 2026-03-14 | appointment | Jane Q. Doe | Executive Vice President and Chief Financial Officer
```

The line is the ticker, filing date, event type, name, and title, separated by ` | `. Any field that is `"NOT_FOUND"` prints as `NOT_FOUND`.

##### Step 7 — Save the CSV

- **Location:** save to `executive_events.csv` in the same folder as the script, using `Path(__file__).resolve().parent / "executive_events.csv"`, so the file lands in `hw03/` no matter which folder the script is run from.
- **Columns, in this exact order:** `company`, `ticker`, `cik`, `filing_date`, `event_type`, `person_name`, `title`, `effective_date`.
- **Column formats:**
  - `cik` is the 10-digit string with leading zeros.
  - `filing_date` is `YYYY-MM-DD`.
  - `event_type` is one of `departure`, `appointment`, `both`, or `NOT_FOUND`.
- **Row order:** companies in the order of the table above; within each company, newest filing first.
- **Empty results:** always write the header row, even if there are zero events across all five companies.
- **Writing:** use `csv.DictWriter` with UTF-8 encoding and `newline=""`. Overwrite the file on each run.
- **Closing summary:** after saving, print `Saved N events to hw03/executive_events.csv`, followed by a per-company count of filings found and events extracted.

##### Code structure

- Put constants at the top: `HEADERS`, `COMPANIES`, `OUTPUT_PATH`, `RAW_TEXT_DIR`, and the departure, appointment, and title keyword lists.
- Write small, single-purpose functions: `sec_get`, `get_5_02_filings`, `download_8k_text`, `html_to_text`, `isolate_item_502`, `split_sentences`, `extract_events`, `find_name`, `find_title`, `find_effective_date`, `write_csv`, and `main`.
- End the file with `if __name__ == "__main__": main()`.
- Wrap the processing of each filing in `try/except`. An unexpected error on one filing prints a warning with the ticker, filing date, and error message, records a `"NOT_FOUND"` row, and moves on.
- Add a short comment above each function explaining what it does. Do not hardcode any names, titles, dates, or accession numbers from specific filings.

##### Definition of done

1. `python hw03/hw03_executives.py` runs from start to finish without crashing.
2. Every company either has at least one printed event line, or the exact message `[TICKER]: No executive events in past 12 months`.
3. **Both edge cases work:**
   - A company with zero Item 5.02 filings in the window prints the no-events message and does not crash.
   - A single filing that reports a departure and an appointment of two different people produces two rows in the CSV.
4. `hw03/executive_events.csv` exists with the exact columns above, and no empty cells.
5. Check the output against the source text. For each filing, read the saved Item 5.02 text and confirm the extracted event type, name, title, and effective date. Report any mismatches or `"NOT_FOUND"` values, and explain why each happened.

### Prompt 3 — Timeline (→ `hw03_timeline.py`)

> Write a Python script that reads `hw03/earnings_history.csv` and `hw03/executive_events.csv`. Do the following:
>
> 1. For each executive event in the events table, calculate the number of days between the executive event's `filing_date` and the nearest earnings filing date for the same company in the earnings table. Call this `days_to_nearest_earnings`.
> 2. Add a column `event_timing` that categorizes each executive event as: `'before earnings'` if the event came before the nearest earnings filing, `'after earnings'` if it came after, or `'same week'` if within 7 days of an earnings filing.
> 3. Save the combined table to `hw03/corporate_events_timeline.csv` with all columns from both source tables plus `days_to_nearest_earnings` and `event_timing`.
> 4. Print a summary: for each company, list any executive events and whether they occurred before or after the nearest earnings announcement.
> 5. Print a final count: how many events occurred before vs. after an earnings announcement across all five companies.

---

## 2. Which companies' extractions required iteration

The SEC site was blocked from Claude's environment, so the regex patterns were tuned against real press release and 8-K wording before my first run. After that, the earnings pipeline needed no follow-up fixes: all 20 rows extracted on the first run, with zero `NOT_FOUND` values.

**Earnings (`hw03_earnings.py`): pattern changes made before the first run**
- **Walmart:** the release's bullet line reads "…up 17.4% adjusted (cc) • eCommerce sales up 23% globally • GAAP EPS of $0.80". A strict "reject if 'adjusted' appears in the 60 characters before the number" rule would have thrown out the real GAAP EPS. The check was changed to stop at bullet, semicolon and sentence breaks.
- **JPMorgan:** EPS appears as "NET INCOME OF $15.0 BILLION ( $5.24 PER SHARE)", so a pattern for "($X per share)" was added. A "$1.40 per share" dividend appears later in the release, so EPS matches near the word "dividend" are now rejected.
- **Apple:** the "Total net sales" table row sits right after a "Services" row, which the segment filter would have wrongly rejected. The segment filter was limited to narrative sentences, and an Apple-style "Earnings per share: Basic … Diluted $X" table pattern was added.

**Executive events (`hw03_executives.py`): pattern changes made before the first run**
- **Apple:** Tim Cook's change is worded "will transition from his role as Chief Executive Officer to Executive Chair", and "transition" is not in the spec's keyword list. A pattern was added that records this as one `both` row. The first version also treated the defined term "the Transition Date" as a departure keyword, which was fixed. For John Ternus, the title first came back as his old role (SVP of Hardware Engineering); appointments now take the title after "as".
- **Walmart:** titles are written in lowercase ("president and chief executive officer"), and effective dates read "effective on the close of business on January 31, 2026". Title matching was made case-insensitive, and the date search now allows a few words after "effective".

**Known issues found in validation, not yet fixed:**
- **JPMorgan:** phrases such as "Compensatory Arrangements" and "Community Banking" were captured as person names.
- **NVIDIA:** "Worldwide Field" was captured as a name, and "Nora Johnson" is a duplicate of "Suzanne Nora Johnson".
- **Walmart:** a false departure row for John Furner comes from his non-compete agreement wording ("…if Mr. Furner is terminated…").
- **Impact:** these inflate event row counts but not the filing-level timing (see `validation.md` 5B and `analysis.md`).

---

## 3. Something the script did that I would not have thought to specify

**The removal of the Item 5.02 section heading before keyword matching.** Every Item 5.02 section begins with the standard heading "Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers; Compensatory Arrangements of Certain Officers." That one heading contains three of the event keywords (departure, election, appointment). Without removing it, every filing, including compensation-only ones, would have produced false departure and appointment events. My specification said to isolate the section starting at "Item 5.02" but never said to strip the heading itself.

**Was it correct?** Yes. Compensation-only filings (MSFT 2025-12-08, NVDA 2026-03-06) correctly came out as `NOT_FOUND` rows rather than fake events. However, the same keyword idea still misfires on other boilerplate, such as non-compete "termination of employment" language, so the approach needed further adjustment rather than being fully solved.

---

## Reflection

I used Claude Cowork to write both specifications, generate all three scripts, and help validate the output against Walmart's investor relations release, Walmart's corporate announcement and yfinance. What surprised me was how much the press release wording differs between companies (GAAP vs. adjusted EPS on the same line, lowercase titles, defined terms like "Transition Date"), and that the extraction had to handle each one. The earnings numbers validated cleanly across three sources. Next time I would add a stop-list of common filing phrases and skip boilerplate sentences in the executive pipeline, since name extraction was its weakest point.
