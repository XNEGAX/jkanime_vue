"""
hentaid.tv scraper — an HLS-only source.

Site shape:
  - Series page: https://hentaid.tv/ver/<slug>/
  - Episode:     https://hentaid.tv/ver/<slug>/episodio-N

Deliberate divergence from the other two sources: this scraper does NOT go
through `shared_scraper_session` (`cache.py:225`), which
`LatanimeScraper._get_scraper` (`latanime.py:71`) relies on to keep one
process-wide Cloudflare session alive. Under shared-session concurrency
hentaid.tv returns truncated bodies and the manifest handshake fails on them,
so every call builds a local `requests.Session` and closes it in `finally`;
`SCRAPE_CACHE` is unused for the same reason, since its 24h TTL would hand back
a dead signed manifest. Throttling is a process-global start gate instead,
which keeps request starts spaced apart without ever holding the lock across a
request body.
"""
import logging
import re
import threading
import time
from contextlib import contextmanager

import requests

from .base import BaseScraper
from . import register_scraper

logger = logging.getLogger(__name__)

# Process-global start gate. The callers are request threads (views) *and*
# background workers (tasks), so the floor has to live in the scraper: throttling
# in `tasks.py` would miss the web path, and throttling per-instance would miss
# the fact that both paths share one process.
_GATE_LOCK = threading.Lock()
_NEXT_ALLOWED = 0.0
GATE_MIN_INTERVAL_S = 1.2


def _await_slot() -> None:
    """
    Block until this process is allowed to start another request.

    The lock covers the wait and the timestamp update only — never the request
    itself — so starts stay at least `GATE_MIN_INTERVAL_S` apart globally while
    the request bodies still overlap.
    """
    global _NEXT_ALLOWED
    with _GATE_LOCK:
        wait = _NEXT_ALLOWED - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _NEXT_ALLOWED = time.monotonic() + GATE_MIN_INTERVAL_S


class HentaidTVScraper(BaseScraper):
    BASE_URL = "https://hentaid.tv"
    SOURCE_NAME = "hentaidtv"
    SERIE_URL_TEMPLATE = "{base}/ver/{slug}/"
    TIMEOUT = 60

    # Storage-worthy ceiling, used to pick a variant. A class constant and not
    # an env knob on purpose: this project reads no environment variable
    # outside DJANGO_SETTINGS_MODULE, so an override would be a silent no-op.
    HLS_MAX_HEIGHT = 720

    # "hls" is a transport tag, not a file host, so it is the only entry.
    SERVER_PRIORITY = ["hls"]

    # Empty on purpose: the manifest is fetched by ffmpeg, not by
    # `_stream_from_server`, and unknown servers already send no Referer.
    REFERER_MAP: dict = {}

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    # ------------------------------------------------------------------
    #  Transport primitives
    # ------------------------------------------------------------------

    @contextmanager
    def _session(self):
        """
        Yield a private `requests.Session`, always closed on exit.

        Private by design, see the module docstring. It is reused across the
        requests of a single call only, never across calls.

        The name is deliberately NOT the `_session = None` / `_session_lock` slot
        that `shared_scraper_session` expects, so passing this class to that
        helper raises a `TypeError` naming it instead of silently handing back a
        context manager. Do not "fix" this into a shared session: see why in the
        module docstring.
        """
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        })
        try:
            yield session
        finally:
            session.close()

    def _get(self, session, url: str, *, params=None, headers=None):
        """One gated GET. The gate throttles starts, not the request body."""
        _await_slot()
        resp = session.get(url, params=params, headers=headers, timeout=self.TIMEOUT)
        resp.raise_for_status()
        return resp

    def _extract_slug(self, url: str) -> str:
        """Extract the slug from a `/ver/<slug>` series or episode URL."""
        match = re.search(r'hentaid\.tv/ver/([^/\s?#]+)', url)
        if match:
            return match.group(1)
        return ""

    # ------------------------------------------------------------------
    #  BaseScraper API
    # ------------------------------------------------------------------

    def get_all_series(self) -> list[dict]:
        """The site crawler is out of scope for this change."""
        return []

    def get_series_info(self, url: str) -> dict | None:
        """
        Not implemented yet.

        Returns None so the view answers with its documented "could not read the
        series" error instead of raising.
        """
        logger.warning(f"hentaidtv: series parsing is not implemented yet ({url})")
        return None

    def get_episodes(self, slug: str) -> list[dict]:
        """
        Not implemented yet. Returns [] so the caller creates no chapters
        instead of raising.
        """
        logger.warning(f"hentaidtv: episode listing is not implemented yet ({slug})")
        return []

    def get_download_urls(self, episode_url: str) -> list[dict]:
        """
        Not implemented yet: the manifest handshake lands in a later slice.

        Returns [] so the download fails with the existing "no servers found"
        message, never with a traceback.
        """
        logger.warning(f"hentaidtv: HLS resolution is not implemented yet ({episode_url})")
        return []


# Register the scraper. The key is taken from `SOURCE_NAME` rather than written
# as a literal so it cannot drift: `get_scraper()` falls back to jkanime
# silently when the key is missing from the registry.
register_scraper(HentaidTVScraper.SOURCE_NAME, HentaidTVScraper)
