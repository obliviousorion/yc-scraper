#!/usr/bin/env python3
"""
main.py
───────
Entry point for the YC Startup Scraper.

Orchestrates the four scraping stages, normalises results, exports to
JSON + Excel, and prints a coverage report.

Usage:
    python main.py
"""

import os
import sys
from datetime import datetime

# Ensure the project root is importable regardless of how the script is invoked.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    log,
    OUTPUT_DIR,
    LINKEDIN_LI_AT,
    LINKEDIN_HEADED,
    LINKEDIN_CHANNEL,
    LINKEDIN_RATE_DELAY,
    LINKEDIN_TIMEOUT,
)
from scraper.algolia import stage1_bulk_fetch
from scraper.social import stage2_enrich
from scraper.jobs import stage3_fetch_jobs
from scraper.linkedin import stage4_linkedin_members
from scraper.normalize import normalise
from scraper.export import save_json, save_excel


def main():
    start_time = datetime.now()
    log.info("=" * 60)
    log.info("YC Startup Scraper — run started at %s", start_time.isoformat())
    log.info("=" * 60)

    # ── Stage 1 — Algolia bulk fetch ──────────────────────────────────────
    raw_hits = stage1_bulk_fetch()

    # ── Stage 2 — Social links ────────────────────────────────────────────
    enriched = stage2_enrich(raw_hits)

    # ── Stage 3 — Remote job listings ─────────────────────────────────────
    jobs_by_slug = stage3_fetch_jobs(enriched)

    # ── Stage 4 — LinkedIn member counts (Playwright) ─────────────────────
    li_by_slug = stage4_linkedin_members(
        enriched,
        li_at=LINKEDIN_LI_AT,
        headed=LINKEDIN_HEADED,
        channel=LINKEDIN_CHANNEL,
        rate_delay=LINKEDIN_RATE_DELAY,
        timeout=LINKEDIN_TIMEOUT,
    )

    # ── Normalise ─────────────────────────────────────────────────────────
    startups = [
        normalise(
            c,
            jobs=jobs_by_slug.get(c.get("slug", ""), []),
            li_count=li_by_slug.get(c.get("slug", "")),
        )
        for c in enriched
    ]

    # ── Coverage report ───────────────────────────────────────────────────
    log.info("== Coverage report ==")
    for field in (
        "linkedin_url",
        "twitter_url",
        "facebook_url",
        "github_url",
        "website_url",
        "linkedin_members",
    ):
        filled = sum(
            1
            for s in startups
            if s.get(field) is not None and s.get(field) != ""
        )
        log.info("  %-22s %d / %d", field, filled, len(startups))

    total_jobs = sum(s.get("remote_jobs_count", 0) for s in startups)
    companies_with_jobs = sum(
        1 for s in startups if s.get("remote_jobs_count", 0) > 0
    )
    log.info(
        "  %-22s %d remote jobs across %d companies",
        "remote_jobs",
        total_jobs,
        companies_with_jobs,
    )

    # ── Export ─────────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = save_json(startups, os.path.join(OUTPUT_DIR, f"yc_startups_{ts}.json"))
    excel_path = save_excel(
        startups, os.path.join(OUTPUT_DIR, f"yc_startups_{ts}.xlsx")
    )

    elapsed = datetime.now() - start_time
    print(f"\n{'=' * 60}")
    print(f"Done! {len(startups)} companies, {total_jobs} remote jobs exported.")
    print(f"  JSON  -> {json_path}")
    print(f"  Excel -> {excel_path}")
    print(f"  Time  -> {elapsed}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
