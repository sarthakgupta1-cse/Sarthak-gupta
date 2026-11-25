"""Pluggable web-search providers (Brave, Serper) with caching and budget control.

Adding a provider (e.g. a Reddit-focused search API later) means implementing
`_raw_search` in a subclass and registering it in `build_search_provider`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from ..config import env
from ..monitoring.budget_tracker import BudgetExceeded, BudgetTracker
from ..utils.cache import DiskCache
from ..utils.http import backoff_sleep

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    published: str = ""
    provider: str = ""


class SearchError(Exception):
    pass


class SearchProvider:
    name = "base"

    def __init__(self, settings, budget: BudgetTracker, cache_root, client: httpx.Client | None = None):
        self.settings = settings
        self.budget = budget
        self.cache = DiskCache(cache_root, f"search-{self.name}")
        self.ttl = float(settings.get("search.cache_ttl_days", 14)) * 86400
        self.count = int(settings.get("search.results_per_query", 10))
        self.client = client or httpx.Client(timeout=20)
        self.errors: list[str] = []

    @property
    def available(self) -> bool:
        return True

    def search(self, query: str, *, freshness: str | None = None, news: bool = False) -> list[SearchResult]:
        """Cached, budget-checked search. Returns [] on failure (errors are recorded)."""
        key = f"{query}|{freshness}|{news}|{self.count}"
        cached = self.cache.get(key, self.ttl)
        if cached is not None:
            return [SearchResult(**r) for r in cached]
        if not self.available:
            return []
        try:
            self.budget.require_search(self.name)
        except BudgetExceeded as exc:
            self._error(str(exc))
            return []
        last = None
        for attempt in range(3):
            try:
                results = self._raw_search(query, freshness=freshness, news=news)
                self.budget.record_search(self.name)
                self.cache.set(key, [r.__dict__ for r in results])
                return results
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last = f"network error: {exc}"
            except SearchError as exc:
                last = str(exc)
                if "HTTP 4" in last and "HTTP 429" not in last:
                    break  # auth / bad request: do not retry
            backoff_sleep(attempt)
        self._error(f"search failed for {query!r}: {last}")
        return []

    def _error(self, msg: str) -> None:
        logger.warning(msg)
        if len(self.errors) < 20:
            self.errors.append(msg)

    def _raw_search(self, query: str, *, freshness: str | None, news: bool) -> list[SearchResult]:
        raise NotImplementedError


class BraveSearch(SearchProvider):
    """Brave Search API — https://api-dashboard.search.brave.com (Search plan)."""
    name = "brave"
    URL = "https://api.search.brave.com/res/v1/web/search"
    NEWS_URL = "https://api.search.brave.com/res/v1/news/search"

    @property
    def available(self) -> bool:
        return bool(env("BRAVE_SEARCH_API_KEY"))

    def _raw_search(self, query, *, freshness, news):
        params = {"q": query, "count": min(self.count, 20)}
        if freshness:  # pd / pw / pm / py
            params["freshness"] = freshness
        resp = self.client.get(self.NEWS_URL if news else self.URL, params=params, headers={
            "Accept": "application/json", "X-Subscription-Token": env("BRAVE_SEARCH_API_KEY") or ""})
        if resp.status_code != 200:
            raise SearchError(f"Brave HTTP {resp.status_code}")
        data = resp.json()
        items = data.get("results", []) if news else data.get("web", {}).get("results", [])
        return [SearchResult(title=i.get("title", ""), url=i.get("url", ""),
                             snippet=" ".join(filter(None, [i.get("description", "")] + i.get("extra_snippets", [])[:2])),
                             published=i.get("age", "") or i.get("page_age", ""), provider=self.name)
                for i in items if i.get("url")]


class SerperSearch(SearchProvider):
    """Serper.dev Google results — https://serper.dev."""
    name = "serper"
    URL = "https://google.serper.dev/search"
    NEWS_URL = "https://google.serper.dev/news"

    @property
    def available(self) -> bool:
        return bool(env("SERPER_API_KEY"))

    def _raw_search(self, query, *, freshness, news):
        body = {"q": query, "num": min(self.count, 10)}
        tbs = {"pd": "qdr:d", "pw": "qdr:w", "pm": "qdr:m", "py": "qdr:y"}.get(freshness or "")
        if tbs:
            body["tbs"] = tbs
        resp = self.client.post(self.NEWS_URL if news else self.URL, json=body,
                                headers={"X-API-KEY": env("SERPER_API_KEY") or ""})
        if resp.status_code != 200:
            raise SearchError(f"Serper HTTP {resp.status_code}")
        data = resp.json()
        items = data.get("news", []) if news else data.get("organic", [])
        return [SearchResult(title=i.get("title", ""), url=i.get("link", ""), snippet=i.get("snippet", ""),
                             published=i.get("date", ""), provider=self.name) for i in items if i.get("link")]


class NullSearch(SearchProvider):
    """No paid search configured: discovery relies on free feeds only."""
    name = "none"

    @property
    def available(self) -> bool:
        return False

    def _raw_search(self, query, *, freshness, news):
        return []


def build_search_provider(settings, budget, cache_root, client=None) -> SearchProvider:
    choice = settings.search_provider
    cls = {"brave": BraveSearch, "serper": SerperSearch}.get(choice, NullSearch)
    provider = cls(settings, budget, cache_root, client)
    if not provider.available and cls is not NullSearch:
        logger.warning("Search provider %s selected but its API key is missing; using free sources only.", choice)
        return NullSearch(settings, budget, cache_root, client)
    return provider
