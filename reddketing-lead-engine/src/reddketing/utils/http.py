"""Polite HTTP fetching: caching, retries with backoff, per-host delay, robots.txt."""
from __future__ import annotations

import logging
import random
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .cache import DiskCache

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    html: str
    error: str | None = None
    from_cache: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300 and bool(self.html)


class TransientHTTPError(Exception):
    pass


def backoff_sleep(attempt: int, base: float = 1.0, cap: float = 30.0) -> None:
    time.sleep(min(cap, base * (2 ** attempt)) + random.uniform(0, 0.5))


class HttpClient:
    def __init__(self, settings, cache_root, *, client: httpx.Client | None = None):
        self.timeout = float(settings.get("http.timeout_seconds", 20))
        self.max_retries = int(settings.get("http.max_retries", 3))
        self.delay = float(settings.get("http.per_host_delay_seconds", 1.0))
        self.respect_robots = bool(settings.get("http.respect_robots_txt", True))
        self.user_agent = settings.get("http.user_agent")
        self.ttl = float(settings.get("http.page_cache_ttl_days", 7)) * 86400
        self.cache = DiskCache(cache_root, "pages")
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.client = client or httpx.Client(
            timeout=self.timeout, follow_redirects=True,
            headers={"User-Agent": self.user_agent, "Accept-Language": "en-US,en;q=0.8"},
        )
        self.requests_made = 0

    # ------------------------------------------------------------------
    def _wait_for_host(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            gap = time.monotonic() - last
            if gap < self.delay:
                time.sleep(self.delay - gap)
        self._last_hit[host] = time.monotonic()

    def _allowed(self, url: str, timeout: float = 10) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self.client.get(base + "/robots.txt", timeout=timeout)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp = None  # no robots.txt -> allowed
            except httpx.HTTPError:
                rp = None
            self._robots[base] = rp
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(self.user_agent, url)

    def get_text(self, url: str, *, use_cache: bool = True, quick: bool = False) -> FetchResult:
        """quick=True: one attempt with short timeouts (used for cheap checks such as guessing a domain)."""
        if use_cache:
            cached = self.cache.get(url, self.ttl)
            if cached:
                return FetchResult(**cached, from_cache=True)
        if not self._allowed(url, timeout=5 if quick else 10):
            return FetchResult(url, url, 0, "", error="disallowed by robots.txt")
        host = urlparse(url).netloc
        last_error = None
        for attempt in range(1 if quick else self.max_retries):
            self._wait_for_host(host)
            try:
                self.requests_made += 1
                resp = self.client.get(url, timeout=6) if quick else self.client.get(url)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise TransientHTTPError(f"HTTP {resp.status_code}")
                ctype = resp.headers.get("content-type", "")
                body = resp.text if ("html" in ctype or "xml" in ctype or "text" in ctype or not ctype) else ""
                result = FetchResult(url, str(resp.url), resp.status_code, body[:800_000],
                                     None if resp.status_code < 400 else f"HTTP {resp.status_code}")
                if result.ok:
                    self.cache.set(url, {"url": url, "final_url": result.final_url, "status": result.status,
                                         "html": result.html, "error": None})
                return result
            except (httpx.TimeoutException, httpx.TransportError, TransientHTTPError) as exc:
                last_error = str(exc)
                if attempt < self.max_retries - 1:
                    backoff_sleep(attempt)
            except httpx.HTTPError as exc:  # invalid URL etc. — not retryable
                return FetchResult(url, url, 0, "", error=str(exc))
        return FetchResult(url, url, 0, "", error=last_error or "failed")
