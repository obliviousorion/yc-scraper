# YC Startup Scraper

A high-performance, modular Python scraper that collects YC-backed startup data through four sequential stages and exports to JSON + professionally styled, multi-sheet Excel files.

---

## 🚀 Key Features

* **Stage 1 (Algolia Bulk Fetch)**: paginated REST API extraction of active startups matching filters.
* **Stage 2 (Social Enrichment)**: extracts social links (LinkedIn, Twitter/X, GitHub, etc.) from YC company profiles.
* **Stage 3 (Remote Job Extraction)**: crawls YC job pages, capturing roles, salary, equity, and apply links.
* **Stage 4 (LinkedIn Member Extraction)**: crawls LinkedIn `/people/` pages via Playwright automation.
* **Advanced Bot-Bypass**: Uses a **Persistent Browser Profile** to retain session and tracking cookies, completely preventing HTTP 999 blocks.
* **Refined Session Recovery**: Automatically catches redirect loops (`ERR_TOO_MANY_REDIRECTS`), clears expired state, and provides a headed manual login window.
* **Beautiful Excel Sheets**: Auto-formats output with frozen panes, filtered headers, custom YC-orange theme styling, and active hyperlinks.

---

## 📂 Project Structure

```text
yc-scraper/
├── requirements.txt       # Project dependencies
├── README.md              # Documentation
├── config.py              # Central configuration & credentials
├── main.py                # Main script entry point
├── test_run.py            # Fast 3-company sanity verification
├── scraper/
│   ├── __init__.py
│   ├── algolia.py         # Stage 1: Algolia index fetching
│   ├── social.py          # Stage 2: YC profile parsing
│   ├── jobs.py            # Stage 3: Remote jobs crawler
│   ├── linkedin.py        # Stage 4: Playwright browser automation
│   ├── normalize.py       # Data normalisation
│   └── export.py          # JSON + styled Excel exporter
└── data/                  # Output & Persistent browser profile (auto-created)
```

---

## ⚙️ Installation & Setup (Using `uv`)

This project is optimized to run using [**`uv`**](https://github.com/astral-sh/uv), the ultra-fast Python package installer and resolver.

### Step 1: Run with `uv`
`uv` manages virtual environments and installs dependencies from `requirements.txt` automatically. Simply run:
```powershell
uv run main.py
```

### Step 2: Install Playwright Browsers (One-Time)
Install the Playwright browser binaries:
```powershell
uv run playwright install chromium
```

---

## 🔒 LinkedIn Scraper Configuration (Stage 4)

LinkedIn rate-limits standard requests aggressively. To scrape safely, the scraper launches a **Persistent Browser Session** using Microsoft Edge, keeping you authenticated between runs.

### One-Time Setup:
1. Open [**`config.py`**](file:///c:/projects/yc-scraper/config.py) and configure these settings:
   ```python
   LINKEDIN_HEADED = True      # Launch a visible browser window
   LINKEDIN_CHANNEL = "msedge"  # Use Microsoft Edge (matches your regular cookies)
   ```
2. Run the sanity test or main script:
   ```powershell
   uv run test_run.py
   ```
3. A Microsoft Edge window will launch. **Log in manually to your LinkedIn account** inside the opened window (and complete any verification/CAPTCHAs if prompted).
4. Once you reach your LinkedIn feed, the scraper will detect that the session is successfully authenticated, capture the active session, and automatically save it to `data/browser_profile/`.

**That's it!** All future runs will run completely hands-free. The scraper will launch in the background, detect the active session, and scrape company member counts automatically without prompting you to log in.

---

## 📊 Usage & Commands

### Run Sanity Test (Fast 3-company check)
Verifies all 4 stages of the scraper on a tiny batch:
```powershell
uv run test_run.py
```

### Run Full Production Scraper
Executes the scraper across all pages matching the filters in `config.py`:
```powershell
uv run main.py
```

---

## 💾 Exported Outputs

All results are exported into the `data/` directory:
* **`yc_startups_YYYYMMDD_HHMMSS.json`**: Complete, structured raw data.
* **`yc_startups_YYYYMMDD_HHMMSS.xlsx`**: Styled Excel sheet with two tabs:
  * *YC Startups*: Company metadata, descriptions, sizes, social links, and LinkedIn member counts.
  * *Remote Jobs*: Flattened lists of remote opportunities with salaries, equities, and application links.
* **`scraper.log`**: Standard run logs for diagnostic monitoring.
