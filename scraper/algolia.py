"""
scraper/algolia.py
──────────────────
Stage 1: Bulk-fetch all matching companies from YC's Algolia search index.

Algolia returns structured JSON with company metadata including name, slug,
team_size, industries, regions, and (sometimes) social-link fields.
"""

import time

from config import (
    SESSION,
    ALGOLIA_ENDPOINT,
    ALGOLIA_HEADERS,
    FILTERS,
    HITS_PER_PAGE,
    MAX_PAGES,
    log,
)


def _fetch_page(page: int) -> dict:
    """Fetch a single page of results from Algolia."""
    resp = SESSION.post(
        ALGOLIA_ENDPOINT,
        headers=ALGOLIA_HEADERS,
        json={"hitsPerPage": HITS_PER_PAGE, "page": page, **FILTERS},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def stage1_bulk_fetch() -> list[dict]:
    """
    Paginate through Algolia to collect every company matching FILTERS.

    Returns a list of raw Algolia hit dicts.
    """
    log.info("STAGE 1 ── Algolia bulk fetch ...")
    first = _fetch_page(0)
    total_pages = min(first.get("nbPages", 1), MAX_PAGES)
    log.info("  %d results across %d pages.", first.get("nbHits", 0), total_pages)

    hits: list[dict] = list(first.get("hits", []))
    for p in range(1, total_pages):
        batch = _fetch_page(p).get("hits", [])
        if not batch:
            break
        hits.extend(batch)
        time.sleep(0.2)

    log.info("  Fetched %d companies.", len(hits))
    return hits
