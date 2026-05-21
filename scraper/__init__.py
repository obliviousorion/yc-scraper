"""
scraper
───────
Core scraping modules for the YC Startup Scraper.

Stages:
  1. algolia   — Bulk-fetch companies from YC's Algolia search index
  2. social    — Enrich with social-media links from YC profile pages
  3. jobs      — Parse remote job listings from company /jobs pages
  4. linkedin  — Fetch LinkedIn associated-member counts via Playwright
"""
