"""
scraper/normalize.py
────────────────────
Transform raw Algolia hit dicts (enriched by Stages 2–4) into clean,
uniform output records ready for JSON / Excel export.
"""

from config import YC_BASE


def normalise(
    hit: dict,
    jobs: list[dict] | None = None,
    li_count: int | None = None,
) -> dict:
    """
    Build a normalised output record from a raw Algolia hit.

    Parameters
    ----------
    hit : dict
        Raw company dict (Algolia fields + Stage 2 social enrichments).
    jobs : list[dict] | None
        Remote job listings from Stage 3 (may be empty).
    li_count : int | None
        LinkedIn associated-member count from Stage 4 (may be None).
    """
    slug = hit.get("slug", "")
    jobs = jobs or []
    return {
        "name": hit.get("name"),
        "short_description": hit.get("one_liner"),
        "about": hit.get("long_description"),
        "batch": hit.get("batch"),
        "status": hit.get("status"),
        "team_size": hit.get("team_size"),
        "linkedin_members": li_count,
        "industries": ", ".join(hit.get("industries", [])),
        "regions": ", ".join(hit.get("regions", [])),
        "tags": ", ".join(hit.get("tags", [])),
        "yc_profile_url": f"{YC_BASE}/companies/{slug}" if slug else None,
        "yc_jobs_url": f"{YC_BASE}/companies/{slug}/jobs" if slug else None,
        "website_url": hit.get("website_url") or hit.get("website"),
        "linkedin_url": hit.get("linkedin_url"),
        "twitter_url": hit.get("twitter_url"),
        "facebook_url": hit.get("facebook_url"),
        "github_url": hit.get("github_url"),
        "crunchbase_url": hit.get("crunchbase_url"),
        "youtube_url": hit.get("youtube_url"),
        "instagram_url": hit.get("instagram_url"),
        "remote_jobs_count": len(jobs),
        "remote_jobs": jobs,
    }
