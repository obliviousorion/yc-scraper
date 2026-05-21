"""
config.py
─────────
Central configuration for the YC Startup Scraper.

All settings, credentials, filter parameters, and shared resources
(HTTP session, logger) are defined here.  Every other module imports
from this file — never the other way around.
"""

import os
import sys
import logging

import requests

# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT DIRECTORY
# ═══════════════════════════════════════════════════════════════════════════════
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════
# Force UTF-8 on the StreamHandler so Windows cp1252 consoles don't choke
# on Unicode characters in log messages.
_stream_handler = logging.StreamHandler(stream=sys.stdout)
_stream_handler.stream = open(
    sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        _stream_handler,
        logging.FileHandler(
            os.path.join(OUTPUT_DIR, "scraper.log"), encoding="utf-8"
        ),
    ],
)
log = logging.getLogger("yc_scraper")

# ═══════════════════════════════════════════════════════════════════════════════
# ALGOLIA  (YC's public company search index)
# ═══════════════════════════════════════════════════════════════════════════════
ALGOLIA_APP_ID = "45BWZJ1SGC"
ALGOLIA_API_KEY = (
    "NzllNTY5MzJiZGM2OTY2ZTQwMDEzOTNhYWZiZGRjODlhYzVkNjBmOGRjNzJi"
    "MWM4ZTU0ZDlhYTZjOTJiMjlhMWFuYWx5dGljc1RhZ3M9eWNkYyZyZXN0cmlj"
    "dEluZGljZXM9WUNDb21wYW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlfQnlfTG"
    "F1bmNoX0RhdGVfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVi"
    "bGljJTIyJTVE"
)
ALGOLIA_INDEX = "YCCompany_production"
ALGOLIA_ENDPOINT = (
    f"https://{ALGOLIA_APP_ID}-dsn.algolia.net"
    f"/1/indexes/{ALGOLIA_INDEX}/query"
)
ALGOLIA_HEADERS = {
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
}

# ── Search filters ────────────────────────────────────────────────────────────
FILTERS = {
    "facetFilters": [
        # ["industries:All Industries"],
        ["isHiring:true"],
        ["regions:Fully Remote"],

    ],
    "numericFilters": ["team_size >= 1", 
    # "team_size <= 50"
    ],
}
HITS_PER_PAGE = 100
MAX_PAGES = 20

# ═══════════════════════════════════════════════════════════════════════════════
# HTTP SESSION  (shared by Algolia, YC profile, and YC jobs requests)
# ═══════════════════════════════════════════════════════════════════════════════
YC_BASE = "https://www.ycombinator.com"

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.ycombinator.com/companies",
    }
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONCURRENCY & RATE LIMITS
# ═══════════════════════════════════════════════════════════════════════════════
PROFILE_WORKERS = 5  # Stage 2 parallel workers
JOBS_WORKERS = 5  # Stage 3 parallel workers
RATE_LIMIT_DELAY = 0.3  # seconds between YC requests per worker

# ═══════════════════════════════════════════════════════════════════════════════
# LINKEDIN  (Stage 4 — Playwright browser automation)
# ═══════════════════════════════════════════════════════════════════════════════
# To get your li_at cookie:
#   1. Log in to linkedin.com in your browser.
#   2. Open DevTools > Application (Chrome) or Storage (Firefox) > Cookies
#      > www.linkedin.com
#   3. Copy the value of the "li_at" cookie and paste it below.
#
# Note: li_at is tied to your account.  Keep it private and refresh it if
# requests start failing.
LINKEDIN_LI_AT = "AQEDATxeSykB3FVaAAABm1_XAOEAAAGeae6IP1YAJ-DvbO_OsE2wjoXK7AJYJlFF8DGhtddzlaHv2c9OyZR_YQKnLjJT3WFSdxIm-jXJnKjISMxKw9wY-89JpxW-04qaEjIn3dBF-TdEkF40gA9W2xmC"  # <── paste your li_at cookie value here

# Set to True to launch a visible browser window.  Useful for solving
# CAPTCHAs or debugging.  Set to False for normal headless operation.
LINKEDIN_HEADED = False

# Playwright browser channel. Set to "msedge" to launch your local Edge browser,
# "chrome" for Google Chrome, or None for Playwright's default bundled Chromium.
# (Recommended: "msedge" if you extracted cookies from Edge).
LINKEDIN_CHANNEL = "msedge"

# Seconds to wait between LinkedIn page loads (per-request, sequential).
# LinkedIn rate-limits aggressively — keep this >= 2.0 to be safe.
LINKEDIN_RATE_DELAY = 2.0

# Playwright page navigation timeout in milliseconds.
LINKEDIN_TIMEOUT = 30_000

# ═══════════════════════════════════════════════════════════════════════════════
# REMOTE JOB FILTER
# ═══════════════════════════════════════════════════════════════════════════════
# Only keep job listings whose location field contains any of these substrings.
# Matching is CASE-INSENSITIVE (location is lowered before comparison), so
# there is no need to add "Remote" or "REMOTE" variants.
# Set to None or () to keep every listing regardless of location.
REMOTE_KEYWORDS = ("remote", "remote-only", "remote only",)

# ═══════════════════════════════════════════════════════════════════════════════
# SOCIAL LINK LABEL MAPPING
# ═══════════════════════════════════════════════════════════════════════════════
# Maps the data-tooltip-content labels on YC profile anchors to dict keys.
LABEL_TO_KEY = {
    "linkedin": "linkedin_url",
    "twitter": "twitter_url",
    "x": "twitter_url",
    "facebook": "facebook_url",
    "github": "github_url",
    "crunchbase": "crunchbase_url",
    "website": "website_url",
}
