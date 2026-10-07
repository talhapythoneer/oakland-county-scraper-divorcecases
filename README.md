# Oakland County Court Explorer Scraper

Built by [Talha Pythoneer](https://www.talhapythoneer.com), web scraping and AI agents.

A Selenium scraper for the [Oakland County, Michigan Court Explorer](https://courtexplorer.oakgov.com/OaklandCounty). It collects circuit court divorce cases (case types `DM` to `DO`) for a range of case years and saves case details, parties, attorneys and recent docket entries to CSV.

## How it works

1. For each letter `a` to `z`, it runs an Advanced Search by party last name, case year range and case type.
2. It walks every page of results and opens each case's detail page.
3. It writes one CSV row per party with the case number, file date, judge, the 10 latest docket entries, party type, party name and attorney.

### reCAPTCHA Enterprise v3

The search form is protected by Google reCAPTCHA Enterprise v3, which is invisible and score based. When Search is clicked, the page calls `grecaptcha.enterprise.execute()` itself and overwrites the hidden token field, so a token from a solving service (2Captcha etc.) is never used. Oakland then rejects low scores with *"reCaptcha Score is below threshold. Suspicious activity detected."*

So instead of solving the captcha, the scraper makes the browser score well:

- Runs Chrome through [undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver), which hides automation flags.
- Types into the search fields at a human pace with random pauses.
- Detects the "below threshold" page and retries the search (up to 8 times, 15 to 30 seconds apart).

### Other features

- **Automatic chromedriver:** [webdriver-manager](https://github.com/SergeyPirogov/webdriver_manager) detects the installed Chrome version and downloads the matching chromedriver. Nothing to download by hand.
- **Resumable, no duplicates:** each case is listed once per party in the search results. The scraper reads the case number from the results table and skips cases already in the CSV or already scraped in this run, so it can be stopped and re-run at any time.
- The CSV is flushed after every case, so an interrupted run loses nothing.

## Setup

Requires Python 3.10+ and Google Chrome.

```bash
pip install -r requirements.txt
```

## Usage

Set the case year range in `inputFile.txt`:

```
startYear=2023
endYear=2024
```

Then run:

```bash
python oaklandCounty.py
```

Keep the Chrome window visible (headless mode gets a low reCAPTCHA score), and run from a normal home or office connection rather than a datacenter server.

## Output

`Oakland_County_Data.csv` (created on the first run, appended on later runs):

| Column | Example |
|---|---|
| Case Number | `2024-500000-DM` |
| File Date | `01/15/2024` |
| Case Judge | `JANE A. SMITH` |
| Docket Info | `03/01/2024: FINAL DISPOSITION; 02/20/2024: JUDGMENT FILED; ...` |
| Party Type | `Plaintiff - 0001` |
| Party Name | `DOE JANE` |
| Attorney Name | `JOHN Q,PUBLIC,` |
| Disposition Text | |
| Disposition Date | |

Example values are placeholders, not real records.
