"""
test_run.py
───────────
Sanity test script to verify Stages 1-3 (and optionally 4) on a very small batch.
"""

import sys
import os

# Ensure the root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config

# Override config settings for a fast, light test run
config.MAX_PAGES = 1
config.HITS_PER_PAGE = 3  # Only fetch 3 companies
config.PROFILE_WORKERS = 1
config.JOBS_WORKERS = 1

from scraper.algolia import stage1_bulk_fetch
from scraper.social import stage2_enrich
from scraper.jobs import stage3_fetch_jobs
from scraper.linkedin import stage4_linkedin_members
from scraper.normalize import normalise
from scraper.export import save_json, save_excel

def main():
    print("Starting fast sanity test (all 4 stages)...")
    
    # 1. Stage 1
    raw_hits = stage1_bulk_fetch()
    print(f"Stage 1 fetched {len(raw_hits)} raw hits.")
    if not raw_hits:
        print("No hits fetched. Exiting.")
        return
        
    # 2. Stage 2
    enriched = stage2_enrich(raw_hits)
    print(f"Stage 2 enriched {len(enriched)} companies.")
    
    # 3. Stage 3
    jobs_by_slug = stage3_fetch_jobs(enriched)
    print(f"Stage 3 fetched jobs for {len(jobs_by_slug)} companies.")
    
    # 4. Stage 4
    li_by_slug = stage4_linkedin_members(
        enriched,
        li_at=config.LINKEDIN_LI_AT,
        headed=config.LINKEDIN_HEADED,
        channel=config.LINKEDIN_CHANNEL,
        rate_delay=config.LINKEDIN_RATE_DELAY,
        timeout=config.LINKEDIN_TIMEOUT,
    )
    print(f"Stage 4 fetched LinkedIn member counts for {len(li_by_slug)} companies.")
    
    # 5. Normalise
    startups = [
        normalise(
            c,
            jobs=jobs_by_slug.get(c.get("slug", ""), []),
            li_count=li_by_slug.get(c.get("slug", "")),
        )
        for c in enriched
    ]
    print(f"Normalized {len(startups)} startups.")
    
    # 6. Export
    ts = "test_run"
    json_path = save_json(startups, os.path.join(config.OUTPUT_DIR, f"yc_startups_{ts}.json"))
    excel_path = save_excel(startups, os.path.join(config.OUTPUT_DIR, f"yc_startups_{ts}.xlsx"))
    
    print("\n" + "=" * 60)
    print("SUCCESS! Sanity test completed successfully.")
    print(f"JSON  -> {json_path}")
    print(f"Excel -> {excel_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
