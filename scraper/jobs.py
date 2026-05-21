"""
scraper/jobs.py
───────────────
Stage 3: Fetch and parse remote job listings from each company's
YC /jobs page.

Each listing row is anchored by a title <a> whose href starts with
    /companies/{slug}/jobs/
From there we walk up to the enclosing container and extract location,
salary, equity, experience, and the Apply Now link.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from config import (
    SESSION,
    YC_BASE,
    JOBS_WORKERS,
    RATE_LIMIT_DELAY,
    REMOTE_KEYWORDS,
    log,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _classify_detail(text: str, job: dict) -> None:
    """Slot a detail chip into the right field based on its content."""
    if "$" in text and not job["salary"]:
        job["salary"] = text
    elif "%" in text and not job["equity"]:
        job["equity"] = text
    elif "year" in text.lower() and not job["experience"]:
        job["experience"] = text


def _parse_job_listings(html: str, slug: str) -> list[dict]:
    """
    Parse all job-listing rows from a company's /jobs page.

    Each listing is anchored by a title <a> whose href starts with
        /companies/{slug}/jobs/
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[dict] = []
    seen_paths: set[str] = set()
    expected_prefix = f"/companies/{slug}/jobs/"

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not href.startswith(expected_prefix):
            continue
        if href in seen_paths:
            continue
        seen_paths.add(href)

        title = anchor.get_text(strip=True)
        if not title:
            continue

        listing = anchor.find_parent("div", class_="py-4")
        if listing is None:
            continue

        detail_texts = [
            d.get_text(strip=True)
            for d in listing.find_all("div", class_="capitalize")
            if d.get_text(strip=True)
        ]

        job: dict = {
            "title": title,
            "location": detail_texts[0] if detail_texts else "",
            "salary": "",
            "equity": "",
            "experience": "",
            "job_url": f"{YC_BASE}{href}",
            "apply_url": "",
        }
        for txt in detail_texts[1:]:
            _classify_detail(txt, job)

        apply_anchor = listing.find("a", class_="ycdc-btn")
        if apply_anchor and apply_anchor.get("href"):
            job["apply_url"] = apply_anchor["href"].strip()

        jobs.append(job)

    return jobs


def _is_remote_job(job: dict) -> bool:
    """Check whether a job's location matches the remote keywords filter."""
    if not REMOTE_KEYWORDS:
        return True
    loc = (job.get("location") or "").lower()
    return any(kw in loc for kw in REMOTE_KEYWORDS)


def _fetch_jobs(slug: str) -> list[dict]:
    """Fetch the /jobs page for a company and return matching remote listings."""
    url = f"{YC_BASE}/companies/{slug}/jobs"
    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        all_jobs = _parse_job_listings(r.text, slug)
        remote_jobs = [j for j in all_jobs if _is_remote_job(j)]
        if all_jobs and not remote_jobs:
            log.debug("  '%s' had %d listing(s) but 0 remote", slug, len(all_jobs))
        return remote_jobs
    except Exception as e:
        log.error("  Jobs request failed for '%s': %s", slug, e)
        return []
    finally:
        time.sleep(RATE_LIMIT_DELAY)


# ── Public API ────────────────────────────────────────────────────────────────

def stage3_fetch_jobs(companies: list[dict]) -> dict[str, list[dict]]:
    """
    Fetch job listings for every company in parallel.

    Returns a slug -> [job_dicts] mapping.
    """
    log.info("STAGE 3 ── Fetching job listings for %d companies ...", len(companies))
    results: dict[str, list[dict]] = {}

    with ThreadPoolExecutor(max_workers=JOBS_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_jobs, c["slug"]): c["slug"]
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

    total_jobs = sum(len(v) for v in results.values())
    with_jobs = sum(1 for v in results.values() if v)
    log.info("  Found %d remote jobs across %d companies.", total_jobs, with_jobs)
    return results
