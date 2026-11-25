"""Free discovery sources: RSS feeds, Google News RSS search, Hacker News (Algolia), Product Hunt."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import httpx

from ..config import env

logger = logging.getLogger(__name__)


@dataclass
class FeedItem:
    title: str
    url: str
    summary: str
    published: str
    source: str          # human name of the feed/channel
    kind: str            # "funding" | "launch" | "search"


def _entry_date(entry) -> str:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            return time.strftime("%Y-%m-%d", val)
    return ""


class FreeSources:
    def __init__(self, settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=20, follow_redirects=True,
                                             headers={"User-Agent": settings.get("http.user_agent")})
        self.errors: list[str] = []
        self.requests_made = 0

    def _get(self, url: str, **kw) -> httpx.Response | None:
        try:
            self.requests_made += 1
            resp = self.client.get(url, **kw)
            if resp.status_code == 200:
                return resp
            self.errors.append(f"{url}: HTTP {resp.status_code}")
        except httpx.HTTPError as exc:
            self.errors.append(f"{url}: {exc.__class__.__name__}")
        return None

    def rss(self, url: str, name: str, kind: str, max_age_days: int) -> list[FeedItem]:
        resp = self._get(url)
        if resp is None:
            return []
        feed = feedparser.parse(resp.content)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).strftime("%Y-%m-%d")
        items = []
        for e in feed.entries[:60]:
            published = _entry_date(e)
            if published and published < cutoff:
                continue
            summary = e.get("summary", "") or ""
            items.append(FeedItem(e.get("title", ""), e.get("link", ""), summary[:600], published, name, kind))
        return items

    def google_news(self, query: str, days: int = 30, kind: str = "funding") -> list[FeedItem]:
        """Google News RSS search. Links are Google redirect URLs, so items are treated as headlines only."""
        q = quote_plus(f"{query} when:{days}d")
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        items = self.rss(url, f"Google News: {query}", kind, max_age_days=days + 1)
        for it in items:
            it.summary = ""  # Google News summaries are HTML link blobs; headline is the signal
        return items

    def hacker_news_launches(self, min_points: int, days: int = 14) -> list[FeedItem]:
        since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
        url = ("https://hn.algolia.com/api/v1/search_by_date?tags=show_hn"
               f"&numericFilters=points>{min_points},created_at_i>{since}&hitsPerPage=50")
        resp = self._get(url)
        if resp is None:
            return []
        out = []
        for h in resp.json().get("hits", []):
            link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
            out.append(FeedItem(h.get("title", ""), link, f"{h.get('points')} points on Hacker News",
                                (h.get("created_at") or "")[:10], "Hacker News Show HN", "launch"))
        return out

    def product_hunt(self, days: int = 7) -> list[FeedItem]:
        token = env("PRODUCT_HUNT_TOKEN")
        if not token:
            return []
        posted_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = """query($after: DateTime!) { posts(order: VOTES, postedAfter: $after, first: 40) {
            edges { node { name tagline website url votesCount createdAt } } } }"""
        try:
            self.requests_made += 1
            resp = self.client.post("https://api.producthunt.com/v2/api/graphql",
                                    json={"query": query, "variables": {"after": posted_after}},
                                    headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
            edges = resp.json().get("data", {}).get("posts", {}).get("edges", [])
        except (httpx.HTTPError, ValueError) as exc:
            self.errors.append(f"Product Hunt: {exc.__class__.__name__}")
            return []
        return [FeedItem(f"{n['name']} — {n.get('tagline', '')}", n.get("website") or n.get("url"),
                         f"{n.get('votesCount')} upvotes on Product Hunt", (n.get("createdAt") or "")[:10],
                         "Product Hunt", "launch") for n in (e["node"] for e in edges)]
