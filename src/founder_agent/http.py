"""One shared HTTP client: per-host rate limiting, retries, on-disk caching,
and robots.txt enforcement.

Every network call in this project goes through here. That is deliberate — it
means politeness is structural rather than something each module remembers.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .compliance import RobotsCache

log = logging.getLogger("founder_agent.http")

CACHE_DIR = Path(".cache")


class RateLimiter:
    """Token-bucket-ish throttle applied per hostname."""

    def __init__(self, per_second: float) -> None:
        self.min_interval = 1.0 / per_second if per_second > 0 else 0.0
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait(self, host: str) -> None:
        if self.min_interval <= 0:
            return
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            elapsed = now - self._last.get(host, 0.0)
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last[host] = time.monotonic()


class PoliteClient:
    """Async HTTP with the manners a scraper owes the sites it reads."""

    def __init__(self, settings) -> None:
        pol = settings.politeness
        self.settings = settings
        self.limiter = RateLimiter(pol.get("rate_limit_per_host", 1.0))
        self.timeout = pol.get("timeout_seconds", 20)
        self.cache_ttl = pol.get("cache_ttl_hours", 24) * 3600
        self.semaphore = asyncio.Semaphore(pol.get("concurrency", 5))
        self.robots = RobotsCache(
            settings.user_agent, enabled=pol.get("respect_robots_txt", True)
        )
        self._client: httpx.AsyncClient | None = None
        self.stats = {"requests": 0, "cache_hits": 0, "errors": 0, "robots_blocked": 0}

    async def __aenter__(self) -> PoliteClient:
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            },
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            await self._client.aclose()

    # -- cache -------------------------------------------------------------
    def _cache_path(self, method: str, url: str, body: Any) -> Path:
        key = hashlib.sha1(f"{method}{url}{json.dumps(body, sort_keys=True, default=str)}".encode())
        return CACHE_DIR / f"{key.hexdigest()}.json"

    def _read_cache(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        if self.cache_ttl and (time.time() - path.stat().st_mtime) > self.cache_ttl:
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            return None

    def _write_cache(self, path: Path, status: int, text: str) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"status": status, "text": text}))
        except Exception:
            pass  # a cache miss is never worth failing a run over

    # -- requests ----------------------------------------------------------
    async def request(
        self,
        method: str,
        url: str,
        *,
        respect_robots: bool = True,
        use_cache: bool = True,
        **kwargs,
    ) -> httpx.Response | None:
        """Returns None when the request was blocked or failed after retries."""
        assert self._client is not None, "use PoliteClient as an async context manager"

        cache_key = self._cache_path(method, url, kwargs.get("json") or kwargs.get("params"))
        if use_cache and method == "GET":
            cached = self._read_cache(cache_key)
            if cached is not None:
                self.stats["cache_hits"] += 1
                return httpx.Response(
                    cached["status"], text=cached["text"], request=httpx.Request(method, url)
                )

        if respect_robots and not await self.robots.allowed(url, self):
            self.stats["robots_blocked"] += 1
            log.info("robots.txt disallows %s — skipping", url)
            return None

        host = urlparse(url).netloc
        backoff = 1.0
        for attempt in range(4):
            async with self.semaphore:
                await self.limiter.wait(host)
                try:
                    self.stats["requests"] += 1
                    resp = await self._client.request(method, url, **kwargs)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    log.debug("network error on %s (%s), retry %d", url, exc, attempt + 1)
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

            # 429/503 mean slow down — honour Retry-After when the server sends it.
            if resp.status_code in (429, 503):
                wait = float(resp.headers.get("Retry-After", backoff) or backoff)
                log.warning("%s returned %d, backing off %.1fs", host, resp.status_code, wait)
                await asyncio.sleep(min(wait, 60))
                backoff *= 2
                continue

            if resp.status_code >= 500:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            if use_cache and method == "GET" and resp.status_code < 400:
                self._write_cache(cache_key, resp.status_code, resp.text)
            return resp

        self.stats["errors"] += 1
        log.warning("giving up on %s after retries", url)
        return None

    async def get(self, url: str, **kwargs) -> httpx.Response | None:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response | None:
        return await self.request("POST", url, respect_robots=False, use_cache=False, **kwargs)

    async def get_json(self, url: str, **kwargs) -> Any | None:
        resp = await self.get(url, **kwargs)
        if resp is None or resp.status_code >= 400:
            return None
        try:
            return resp.json()
        except Exception:
            return None
