"""Polite HTTP client: retries with backoff, per-host spacing, no auth bypassing."""
from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}


class SourceError(RuntimeError):
    pass


class Http:
    def __init__(self, cfg: dict):
        self.timeout = cfg.get("timeout", 25)
        self.retries = cfg.get("retries", 3)
        self.backoff = cfg.get("backoff", 2.0)
        self.intervals = cfg.get("min_interval_seconds", {})
        self.s = requests.Session()
        self.s.headers["User-Agent"] = cfg.get("user_agent", "remote-job-agent/1.0")
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self.calls = 0

    def _wait(self, host: str) -> None:
        gap = self.intervals.get(host, self.intervals.get("default", 0.5))
        with self._lock:
            now = time.monotonic()
            wait = self._last.get(host, 0) + gap - now
            self._last[host] = max(now, self._last.get(host, 0) + gap)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str, *, params=None, accept_status=(200,), allow_redirects=True) -> requests.Response:
        host = urlparse(url).netloc
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            self._wait(host)
            self.calls += 1
            try:
                r = self.s.get(url, params=params, timeout=self.timeout, allow_redirects=allow_redirects)
            except requests.RequestException as exc:   # network blip — retry
                last_exc = exc
            else:
                if r.status_code in accept_status:
                    return r
                if r.status_code not in RETRY_STATUS:
                    raise SourceError(f"HTTP {r.status_code} for {url}")
                last_exc = SourceError(f"HTTP {r.status_code} for {url}")
                ra = r.headers.get("Retry-After", "")
                if r.status_code == 429 and (not ra.isdigit() or int(ra) > 30):
                    raise SourceError(f"HTTP 429 (rate limited) for {url}")   # don't stall the whole run
                if ra.isdigit():
                    time.sleep(int(ra))
            if attempt < self.retries:
                time.sleep(self.backoff * (2 ** attempt))
        raise SourceError(str(last_exc))

    def json(self, url: str, **kw):
        return self.get(url, **kw).json()
