# YCombinator Startup Scraper

A robust and modular Python command-line utility designed to extract, enrich, and export structured data from YCombinator-backed startup profiles and active remote job listings. 

The tool implements a four-stage ETL pipeline, incorporating direct API queries, multi-threaded HTML parsing, and automated browser sessions with session persistence and automated authentication recovery.

## Pipeline Architecture

The scraper executes sequentially in four distinct stages:

1. **Stage 1 (Index Extraction):** Performs paginated queries against YCombinator's public Algolia search index to retrieve baseline startup metadata matching specified filters (e.g., remote hiring status, team size, industries).
2. **Stage 2 (Social Link Parsing):** Concurrently requests and parses company profile pages on `ycombinator.com` to extract verified social media links (LinkedIn, Twitter/X, GitHub, Crunchbase) and primary company website URLs.
3. **Stage 3 (Remote Job Crawling):** Crawls associated YC job boards to extract active role postings, geographic locations, salary ranges, equity offerings, and direct application links.
4. **Stage 4 (LinkedIn Member Metrics):** Utilizes Playwright automation to navigate to LinkedIn company pages and retrieve total employee/member counts.

## Directory Layout

```text
yc-scraper/
├── requirements.txt       # Python dependencies
├── README.md              # Documentation
├── config.py              # Central settings and parameters
├── main.py                # Pipeline entry point
├── test_run.py            # Development/sanity test runner (3-company limit)
├── scraper/
│   ├── __init__.py
│   ├── algolia.py         # Algolia query execution (Stage 1)
│   ├── social.py          # YC profile HTML parsing (Stage 2)
│   ├── jobs.py            # YC job board scraping (Stage 3)
│   ├── linkedin.py        # Playwright LinkedIn automations (Stage 4)
│   ├── normalize.py       # Data validation and normalization
│   └── export.py          # JSON and formatted Excel exporters
└── data/                  # Output and persistent browser profile storage (git-ignored)
```

## Installation & Environment Setup

This project uses the `uv` package manager to ensure fast execution, deterministic dependency resolution, and isolated virtual environments.

### 1. Prerequisite Checklist

- Python 3.10 or higher.
- `uv` installed on your system.

### 2. Download and Initialize

Clone the repository and install the required browser binaries for Playwright:

```powershell
# Clone the repository
git clone <repository-url>
cd yc-scraper

# Install the required Playwright browser binary (Chromium)
uv run playwright install chromium
```

## Configuration

All functional parameters, API credentials, and runtime behaviors are defined in `config.py`.

### 1. Algolia Filtering

Customize startup search criteria by modifying the `FILTERS` dictionary in `config.py`:

```python
FILTERS = {
    "facetFilters": [
        ["isHiring:true"],
        ["regions:Fully Remote"],
    ],
    "numericFilters": [
        "team_size >= 1"
    ],
}
```

### 2. LinkedIn Authentication and Session Persistence

LinkedIn implements aggressive anti-bot protections. To bypass standard roadblocks and avoid repeated login prompts, the scraper maintains a persistent browser profile state.

1. **Extract Cookie Value:** Log into your LinkedIn account in your standard browser. Open Developer Tools, navigate to the Storage/Application tab, select Cookies, and copy the value of the `li_at` cookie.
2. **Configure Settings in `config.py`:**
   ```python
   # Paste your li_at token
   LINKEDIN_LI_AT = "AQEDATxeSykB3FVa..."
   
   # Browser visibility
   LINKEDIN_HEADED = False
   
   # Set to "msedge" if you extracted your cookie from Microsoft Edge,
   # "chrome" for Google Chrome, or None for the default Chromium.
   LINKEDIN_CHANNEL = "msedge"
   ```
3. **Session Context (`data/browser_profile/`):** The scraper initializes a persistent browser context on disk. Authentication credentials and session cookies are preserved here across executions.

### 3. Session Recovery and Anti-Bot Handling

If the persistent session expires or encounters a redirect loop (often caused by invalid, expired, or locked session tokens), the scraper:
1. Automatically detects the authentication loop.
2. Clears the corrupted profile context in `data/browser_profile/`.
3. Spins up a headed browser window (`LINKEDIN_HEADED = True` is forced temporarily) to allow manual authentication or CAPTCHA resolution.
4. Saves the newly validated state to disk, returning to headless runs on subsequent invocations.

## Running the Scraper

### Sanity Check (Highly Recommended)

Executes a lightweight, end-to-end run limited to 3 companies to verify that selectors, paths, and network configurations are functioning properly:

```powershell
uv run test_run.py
```

### Full Production Execution

Executes the pipeline across all matching startups returned by the Algolia filters:

```powershell
uv run main.py
```

## Data Output

Processed results are saved to the `data/` directory with a unique timestamp suffix (`yc_startups_YYYYMMDD_HHMMSS`):

- **JSON Data (`.json`):** Contains the complete, structured hierarchical dataset.
- **Excel Workbook (`.xlsx`):** A professionally formatted spreadsheet containing two sheets:
  - *YC Startups:* Consolidated company profiles, social URLs, and employee metrics.
  - *Remote Jobs:* Active remote listings with salary, equity, and direct links.
  - Features automatic column width optimization, enabled filter toggles, frozen header rows, and functional hyperlinks.
- **Execution Log (`scraper.log`):** Detailed application logging output for troubleshooting.
