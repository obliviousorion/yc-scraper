"""
scraper/linkedin.py
───────────────────
Stage 4: Fetch LinkedIn associated-member counts via Playwright browser
automation.

Why Playwright?
  LinkedIn blocks plain HTTP requests (``requests.get``) with HTTP 999 and
  serves a tiny JavaScript-only auth-wall page.  Playwright renders the
  full page — including all client-side JS — so we can read the member
  count exactly as a human would see it in a browser.

Authentication:
  A valid ``li_at`` session cookie must be injected into the browser
  context.  See config.py for instructions on how to obtain it.

Rate limiting:
  Requests are made *sequentially* (not threaded) with a configurable
  delay between pages to minimise the risk of account throttling.
"""

import re
import time

from config import log

# ── Regex patterns for member-count extraction ────────────────────────────────
# These are tried in order against both the visible page text and the raw
# HTML source (which may contain JSON data blobs).

_MEMBERS_PATTERNS = [
    # "96 associated members"
    re.compile(r"([\d,]+)\s+associated\s+members", re.IGNORECASE),
    # "150 employees on LinkedIn"
    re.compile(r"([\d,]+)\s+employees?\s+on\s+LinkedIn", re.IGNORECASE),
    # JSON: "associatedMembersCount":96  /  "associatedMembers":96
    re.compile(r'"associatedMembers(?:Count)?"\s*:\s*(\d+)'),
    # JSON: "staffCount":96
    re.compile(r'"staffCount"\s*:\s*(\d+)'),
    # Visible text: "150 employees"  (broad — tried last)
    re.compile(r"([\d,]+)\s+employees?", re.IGNORECASE),
]

# Fallback: staffCountRange / employeeCountRange → take the upper bound.
_RANGE_RE = re.compile(
    r'"(?:staffCountRange|employeeCountRange)"\s*:\s*'
    r'\{\s*"start"\s*:\s*(\d+)\s*,\s*"end"\s*:\s*(\d+)\s*\}'
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_people_url(linkedin_url: str) -> str | None:
    """
    Convert a LinkedIn company URL to its /people/ tab URL.

    Handles both trailing-slash and slash-free variants:
      https://www.linkedin.com/company/acme/    → .../acme/people/
      https://www.linkedin.com/company/acme     → .../acme/people/
    Returns None if the URL doesn't look like a LinkedIn company page.
    """
    if not linkedin_url:
        return None
    url = linkedin_url.rstrip("/")
    if "linkedin.com/company/" not in url:
        return None
    return f"{url}/people/"


def _extract_count(text: str) -> int | None:
    """Try every regex pattern against *text* and return the first match."""
    for pattern in _MEMBERS_PATTERNS:
        m = pattern.search(text)
        if m:
            return int(m.group(1).replace(",", ""))

    # Range fallback — return the upper bound as an approximation.
    m = _RANGE_RE.search(text)
    if m:
        return int(m.group(2))

    return None


# ── Playwright-based scraper ──────────────────────────────────────────────────

class LinkedInScraper:
    """
    Context-manager that drives a Playwright Chromium browser to scrape
    LinkedIn company /people/ pages for the associated-member count.

    Usage::

        with LinkedInScraper(li_at="...", headed=False) as scraper:
            count = scraper.get_member_count("https://linkedin.com/company/acme")
    """

    def __init__(
        self,
        li_at: str,
        headed: bool = False,
        channel: str | None = None,
        rate_delay: float = 2.0,
        timeout: int = 30_000,
    ):
        self.li_at = li_at
        self.headed = headed
        self.channel = channel
        self.rate_delay = rate_delay
        self.timeout = timeout
        self._pw = None
        self._browser = None
        self._context = None

    # ── Context manager ───────────────────────────────────────────────────

    def __enter__(self):
        import os
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        
        # Define a persistent browser profile directory under data/browser_profile
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        profile_dir = os.path.join(project_root, "data", "browser_profile")
        os.makedirs(profile_dir, exist_ok=True)
        
        launch_kwargs = {
            "headless": not self.headed,
        }
        
        is_firefox = (self.channel == "firefox")
        if is_firefox:
            browser_type = self._pw.firefox
        else:
            browser_type = self._pw.chromium
            launch_kwargs["args"] = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-search-engine-choice-screen",
            ]
            if self.channel:
                launch_kwargs["channel"] = self.channel

        launch_args = {
            "user_data_dir": profile_dir,
            "viewport": {"width": 1280, "height": 800},
            **launch_kwargs
        }
        if not self.channel:
            # Only use default chromium UA override if not using a specific browser channel like Edge
            launch_args["user_agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )

        self._context = browser_type.launch_persistent_context(**launch_args)
        
        # Check if the persistent profile already has a valid session.
        log.info("  Playwright persistent browser context launched (headed=%s).", self.headed)
        
        is_authenticated = False
        try:
            pages = self._context.pages
            page = pages[0] if pages else self._context.new_page()
            # Visit the homepage to check current authentication status
            log.info("  Checking existing browser profile session...")
            page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=15_000)
            page.wait_for_timeout(2000)
            if any(term in page.url for term in ("feed", "mynetwork", "messaging", "notifications", "jobs", "company", "/in/")):
                log.info("  Using existing active session from browser profile.")
                is_authenticated = True
        except Exception as e:
            if "ERR_TOO_MANY_REDIRECTS" in str(e):
                log.warning("  Too many redirects on startup check. Session in browser profile is likely corrupted/expired.")
            else:
                log.debug("  Initial session check failed: %s", e)

        # If not authenticated, try injecting the li_at cookie from config.py
        if not is_authenticated:
            try:
                current_cookies = self._context.cookies()
                existing_li_at = next((c.get("value") for c in current_cookies if c.get("name") == "li_at"), None)
            except Exception:
                existing_li_at = None
                
            if self.li_at and existing_li_at != self.li_at:
                log.info("  Injecting fresh LinkedIn li_at cookie from config.py into browser context...")
                try:
                    self._context.add_cookies(
                        [
                            {
                                "name": "li_at",
                                "value": self.li_at,
                                "domain": ".linkedin.com",
                                "path": "/",
                            },
                        ]
                    )
                except Exception as cookie_err:
                    log.warning("  Could not inject cookie: %s", cookie_err)

            # Re-verify session after injecting cookie
            if self.li_at:
                log.info("  Establishing LinkedIn session...")
                try:
                    pages = self._context.pages
                    page = pages[0] if pages else self._context.new_page()
                    try:
                        page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=15_000)
                    except Exception as goto_err:
                        if "ERR_TOO_MANY_REDIRECTS" in str(goto_err):
                            log.warning("  Too many redirects on startup. The li_at cookie in config.py is invalid/expired.")
                            log.info("  Clearing cookies to break the redirect loop and loading login page...")
                            self._context.clear_cookies()
                            page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=15_000)
                        else:
                            raise goto_err
                    page.wait_for_timeout(2000)
                    
                    # Check if we are on a login or challenge screen
                    if "login" in page.url or "checkpoint" in page.url or "challenge" in page.url:
                        log.warning("  Action required: session is not fully authenticated or checkpoint triggered.")
                        if self.headed:
                            log.warning("  Please check the opened Edge browser window, log in or solve the CAPTCHA/checkpoint.")
                            log.warning("  Waiting up to 90 seconds for manual authentication to complete...")
                            try:
                                # Wait until we are redirected to the feed/home or another authenticated page
                                page.wait_for_url(
                                    lambda url: "feed" in url or "mynetwork" in url or "company" in url or "/in/" in url or ("linkedin.com" in url and "login" not in url and "checkpoint" not in url),
                                    timeout=90_000
                                )
                                log.info("  Session successfully authenticated!")
                                page.wait_for_timeout(2000)
                            except Exception:
                                log.warning("  Authentication did not complete in time, will proceed anyway.")
                        else:
                            log.warning("  Browser is headless. Set LINKEDIN_HEADED=True in config.py to log in manually.")
                except Exception as e:
                    log.warning("  Could not complete initial session check: %s", e)

        return self

    def __exit__(self, *exc):
        if self._context:
            self._context.close()
        if self._pw:
            self._pw.stop()
        log.info("  Playwright browser closed.")

    # ── Public API ────────────────────────────────────────────────────────

    def get_member_count(self, linkedin_url: str) -> int | None:
        """
        Navigate to the /people/ page and extract the member count.

        Returns the integer count, or None on any error.
        """
        people_url = _build_people_url(linkedin_url)
        if not people_url:
            return None

        pages = self._context.pages
        page = pages[0] if pages else self._context.new_page()
        try:
            page.goto(
                people_url,
                wait_until="domcontentloaded",
                timeout=self.timeout,
            )

            # Give client-side JS time to render the member count.
            page.wait_for_timeout(3000)

            # ── Auth-wall check ───────────────────────────────────────────
            if "authwall" in page.url or "login" in page.url:
                log.warning(
                    "  LinkedIn auth wall for: %s — check your li_at cookie.",
                    people_url,
                )
                return None

            # ── CAPTCHA / challenge check ─────────────────────────────────
            if "checkpoint" in page.url or "challenge" in page.url:
                if self.headed:
                    log.warning(
                        "  CAPTCHA detected — solve it in the browser window. "
                        "Waiting up to 2 minutes ..."
                    )
                    try:
                        page.wait_for_url("**/people/**", timeout=120_000)
                        page.wait_for_timeout(3000)
                    except Exception:
                        log.error("  CAPTCHA not solved in time.")
                        return None
                else:
                    log.warning(
                        "  CAPTCHA detected. Set LINKEDIN_HEADED=True in "
                        "config.py to solve it manually."
                    )
                    return None

            # ── Extract the count ─────────────────────────────────────────
            # Strategy 1: visible body text (most reliable on rendered page)
            try:
                body_text = page.inner_text("body")
                count = _extract_count(body_text)
                if count is not None:
                    log.info("  %s → %d members (text)", people_url, count)
                    return count
            except Exception:
                pass

            # Strategy 2: raw page HTML source (for JSON blobs in <code> etc.)
            try:
                html = page.content()
                count = _extract_count(html)
                if count is not None:
                    log.info("  %s → %d members (html)", people_url, count)
                    return count
            except Exception:
                pass

            log.warning("  Member count not found for: %s", people_url)
            return None

        except Exception as e:
            if "ERR_TOO_MANY_REDIRECTS" in str(e):
                log.warning("  Too many redirects for: %s", people_url)
                log.warning("  Your session may have expired. Clearing cookies and trying login screen...")
                self._context.clear_cookies()
                try:
                    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=20_000)
                    if self.headed:
                        log.warning("  Please log in manually in the opened Edge browser window.")
                        log.warning("  Waiting up to 90 seconds for login to complete...")
                        page.wait_for_url("**/feed/**", timeout=90_000)
                        log.info("  Login successful! Retrying original URL...")
                        page.goto(people_url, wait_until="domcontentloaded", timeout=self.timeout)
                        page.wait_for_timeout(3000)
                        
                        # Now continue extracting
                        body_text = page.inner_text("body")
                        count = _extract_count(body_text)
                        if count is not None:
                            log.info("  %s → %d members (text, retry)", people_url, count)
                            return count
                except Exception as retry_err:
                    log.error("  Retry / manual login failed: %s", retry_err)
            log.error("  Playwright error for '%s': %s", people_url, e)
            return None
        finally:
            if len(self._context.pages) > 1:
                page.close()
            time.sleep(self.rate_delay)


# ── Stage 4 public entry point ────────────────────────────────────────────────

def stage4_linkedin_members(
    companies: list[dict],
    li_at: str,
    headed: bool = False,
    channel: str | None = None,
    rate_delay: float = 2.0,
    timeout: int = 30_000,
) -> dict[str, int | None]:
    """
    Fetch LinkedIn associated-member counts for every company that has a
    ``linkedin_url``.

    Returns a ``slug → count`` mapping (``None`` = not found / error).

    If ``li_at`` is empty or Playwright is not installed, the stage is
    skipped gracefully with a helpful log message.
    """
    eligible = [c for c in companies if c.get("linkedin_url")]
    log.info(
        "STAGE 4 ── Fetching LinkedIn member counts for %d companies ...",
        len(eligible),
    )

    # ── Guard: missing cookie or profile ──────────────────────────────────
    import os
    has_profile = False
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    profile_dir = os.path.join(project_root, "data", "browser_profile")
    if os.path.exists(profile_dir) and os.listdir(profile_dir):
        has_profile = True

    if not li_at and not has_profile:
        log.warning(
            "  Skipping Stage 4: set LINKEDIN_LI_AT in config.py or log in manually "
            "to establish a persistent session."
        )
        return {}

    # ── Guard: Playwright not installed ───────────────────────────────────
    try:
        import playwright  # noqa: F401
    except ImportError:
        log.error(
            "  Playwright is not installed.  Install it with:\n"
            "    pip install playwright\n"
            "    playwright install chromium\n"
            "  Stage 4 skipped."
        )
        return {}

    # ── Scrape sequentially with a shared browser context ─────────────────
    results: dict[str, int | None] = {}

    with LinkedInScraper(
        li_at=li_at,
        headed=headed,
        channel=channel,
        rate_delay=rate_delay,
        timeout=timeout,
    ) as scraper:
        for i, company in enumerate(eligible, 1):
            slug = company.get("slug", "")
            linkedin_url = company.get("linkedin_url", "")
            results[slug] = scraper.get_member_count(linkedin_url)

            if i % 5 == 0 or i == len(eligible):
                log.info("  %d / %d done.", i, len(eligible))

    found = sum(1 for v in results.values() if v is not None)
    log.info("  Member count found for %d / %d companies.", found, len(eligible))
    return results
