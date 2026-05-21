"""
scraper/social.py
─────────────────
Stage 2: Enrich companies with social-media links scraped from their
YC profile pages.

Each YC profile page (https://www.ycombinator.com/companies/<slug>) contains
anchor tags with a ``data-tooltip-content`` attribute whose value is the
platform label ("LinkedIn", "Twitter", "GitHub", etc.).  We parse those
anchors to extract the corresponding URLs.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from config import (
    SESSION,
    YC_BASE,
    PROFILE_WORKERS,
    RATE_LIMIT_DELAY,
    LABEL_TO_KEY,
    log,
)


def _parse_social_links(html: str) -> dict:
    """Extract social-media URLs from data-tooltip-content anchors."""
    soup = BeautifulSoup(html, "html.parser")
    socials: dict[str, str] = {}
    for a in soup.find_all("a", attrs={"data-tooltip-content": True}):
        label = a["data-tooltip-content"].strip().lower()
        href = a.get("href", "").strip()
        if href:
            key = LABEL_TO_KEY.get(label, f"{label}_url")
            socials[key] = href
    return socials


def _fetch_profile(slug: str) -> dict:
    """Fetch a single YC profile page and return its social links."""
    url = f"{YC_BASE}/companies/{slug}"
    try:
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
        socials = _parse_social_links(r.text)
        if not socials:
            log.warning("  No social anchors found for '%s'", slug)
        return socials
    except Exception as e:
        log.error("  Request failed for '%s': %s", slug, e)
        return {}
    finally:
        time.sleep(RATE_LIMIT_DELAY)


def stage2_enrich(companies: list[dict]) -> list[dict]:
    """
    Fetch social links for every company in parallel and merge them back
    into the company dicts.

    Returns a new list of enriched company dicts.
    """
    log.info("STAGE 2 ── Fetching social links for %d profiles ...", len(companies))
    results: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=PROFILE_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_profile, c["slug"]): c["slug"]
            for c in companies
            if c.get("slug")
        }
        done = 0
        for future in as_completed(futures):
            slug = futures[future]
            results[slug] = future.result()
            done += 1
            if done % 10 == 0 or done == len(futures):
                log.info("  %d / %d done.", done, len(futures))

    return [{**c, **results.get(c.get("slug", ""), {})} for c in companies]
