"""Collects raw discovery items from free sources and the search API, then extracts candidates."""
from __future__ import annotations

import logging
from datetime import date

from ..models import Candidate, CandidateExtraction
from ..providers.llm_provider import LLMError
from ..providers.news_feeds import FeedItem, FreeSources
from ..providers.search_provider import SearchProvider
from ..research.prompts import DISCOVERY_SYSTEM, discovery_user_prompt
from ..utils.normalize import is_non_company_domain, root_domain
from .search_engine import plan_discovery_queries

logger = logging.getLogger(__name__)


def collect_launch_items(settings, free: FreeSources, search: SearchProvider, run_date: date,
                         n_queries: int) -> list[FeedItem]:
    items: list[FeedItem] = []
    items += free.hacker_news_launches(int(settings.get("discovery.hacker_news_min_points", 150)))
    items += free.product_hunt()
    for category, query in plan_discovery_queries(settings.categories, run_date, n_queries):
        for r in search.search(query):
            items.append(FeedItem(r.title, r.url, r.snippet, r.published, f"search:{category}", "search"))
    return items


def extract_candidates(llm, items: list[FeedItem], blocklist: set[str], *, batch_size: int = 45,
                       funding: bool = False) -> list[Candidate]:
    """LLM turns noisy items into named companies. Item URLs are mapped back deterministically."""
    out: list[Candidate] = []
    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        try:
            result = llm.complete_json(DISCOVERY_SYSTEM, discovery_user_prompt(batch), CandidateExtraction)
        except LLMError as exc:
            logger.warning("candidate extraction failed for a batch: %s", exc)
            continue
        for c in result.candidates:
            idx = [int(i[1:]) for i in c.item_ids if i.startswith("I") and i[1:].isdigit() and int(i[1:]) < len(batch)]
            refs = [batch[i] for i in idx]
            website = c.website or ""
            # Prefer a company-owned URL that actually appeared in the items.
            for r in refs:
                if not is_non_company_domain(r.url, blocklist):
                    website = website or r.url
            if website and is_non_company_domain(website, blocklist):
                website = ""
            hint = {}
            if c.is_funding_announcement:
                hint = {"round": c.funding_round, "amount_usd": c.funding_amount_usd,
                        "date": c.announcement_date or (refs[0].published if refs else ""),
                        "headline": refs[0].title if refs else "", "source_url": refs[0].url if refs else "",
                        "publisher": refs[0].source if refs else ""}
            out.append(Candidate(
                name=c.name.strip(), website=website, domain=root_domain(website) if website else "",
                discovery_channels=sorted({r.source for r in refs}) or ["unknown"],
                discovery_urls=[r.url for r in refs][:5], discovery_note=c.why_relevant[:300],
                funding_hint=hint, is_funding_lead=funding or c.is_funding_announcement))
    return out
