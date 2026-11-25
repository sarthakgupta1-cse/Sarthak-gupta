"""Recently-funded company discovery (free feeds + Google News + optional news search)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from ..providers.news_feeds import FeedItem, FreeSources
from ..providers.search_provider import SearchProvider
from .search_engine import daily_rng

logger = logging.getLogger(__name__)

FUNDING_WORDS = ("raise", "raises", "raised", "funding", "seed", "series", "secures", "backed", "investment",
                 "round", "pre-seed", "led by")


def looks_like_funding(title: str) -> bool:
    t = title.lower()
    return any(w in t for w in FUNDING_WORDS)


def collect_funding_items(settings, free: FreeSources, search: SearchProvider, run_date: date,
                          news_queries: int = 3) -> list[FeedItem]:
    lookback = int(settings.get("targets.funding_lookback_days", 180))
    items: list[FeedItem] = []
    for feed in settings.get("discovery.free_feeds", []):
        items += [i for i in free.rss(feed["url"], feed["name"], "funding", max_age_days=lookback)
                  if looks_like_funding(i.title)]
    queries = list(settings.get("discovery.google_news_funding_queries", []))
    rng = daily_rng(run_date, "funding")
    rng.shuffle(queries)
    for q in queries[:4]:
        items += free.google_news(q, days=min(lookback, 30))
    # A few paid news searches widen coverage when budget allows.
    for q in queries[:news_queries]:
        for r in search.search(q, freshness="pm", news=True):
            items.append(FeedItem(r.title, r.url, r.snippet, r.published, "search:news", "funding"))
    # Deduplicate by title
    seen, unique = set(), []
    for it in items:
        k = it.title.strip().lower()[:120]
        if k and k not in seen:
            seen.add(k)
            unique.append(it)
    return unique


def within_lookback(date_text: str | None, run_date: date, days: int) -> bool | None:
    """True/False if a date can be parsed, None if unknown."""
    if not date_text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%d %B %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            d = datetime.strptime(date_text.strip()[:len(date_text.strip())], fmt).date()
            return run_date - timedelta(days=days) <= d <= run_date + timedelta(days=2)
        except ValueError:
            continue
    return None
