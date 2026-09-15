"""Hacker News via the public Algolia API.

'Launch HN' and 'Show HN' threads are the single richest free source of SaaS
founders: the founder posts under their own account, says what they built, and
almost always drops a contact address in the thread. No key, no ToS grey area.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone

from ..models import EmailStatus, Lead, extract_emails, harvest_socials
from .base import DiscoverySource

SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"
USER_URL = "https://hn.algolia.com/api/v1/users/{username}"

# "Launch HN: Acme (YC W24) – AI for invoices"  ->  Acme
_TITLE_RE = re.compile(r"^(?:Launch HN|Show HN):\s*([^–—\-(|,]+)", re.IGNORECASE)


class HackerNewsSource(DiscoverySource):
    name = "hackernews"

    async def discover(self, limit: int) -> list[Lead]:
        queries = self.config.get("queries", ["Launch HN", "Show HN"])
        per_query = self.config.get("hits_per_query", 100)
        keywords = [k.lower() for k in self.settings.targeting.get("keywords", [])]
        max_age = self.settings.targeting.get("max_age_days")

        cutoff = None
        if max_age:
            cutoff = datetime.now(timezone.utc) - timedelta(days=int(max_age))

        stories: list[dict] = []
        for query in queries:
            params = {
                "query": query,
                "tags": "story",
                "hitsPerPage": min(per_query, 1000),
            }
            if cutoff:
                params["numericFilters"] = f"created_at_i>{int(cutoff.timestamp())}"
            data = await self.client.get_json(SEARCH_URL, params=params)
            if not data:
                self.log.warning("no response for query %r", query)
                continue
            stories.extend(data.get("hits", []))

        # The queries overlap ("Show HN" also matches some Launch HN posts), so
        # collapse by story id before we spend a profile fetch on each author.
        unique: dict[str, dict] = {}
        for story in stories:
            key = str(story.get("objectID") or "")
            if key and key not in unique:
                unique[key] = story
        stories = list(unique.values())

        self.log.info("fetched %d unique HN stories", len(stories))

        # Prefer stories that look like SaaS, then the most recent.
        def relevance(story: dict) -> tuple[int, int]:
            blob = f"{story.get('title','')} {story.get('story_text','') or ''}".lower()
            hits = sum(1 for k in keywords if k in blob)
            return (hits, story.get("created_at_i", 0))

        stories.sort(key=relevance, reverse=True)
        stories = stories[: limit * 2]  # over-fetch; many yield nothing usable

        tasks = [self._lead_from_story(s) for s in stories]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        leads: list[Lead] = []
        for result in results:
            if isinstance(result, Exception):
                self.log.debug("story failed: %s", result)
                continue
            if result:
                leads.append(result)
            if len(leads) >= limit:
                break
        return leads

    async def _lead_from_story(self, story: dict) -> Lead | None:
        author = story.get("author")
        title = story.get("title") or ""
        if not author:
            return None

        company = ""
        m = _TITLE_RE.match(title)
        if m:
            company = m.group(1).strip()
        if not company:
            return None

        lead = Lead(
            company=company,
            role="Founder",  # self-identified by posting a Launch/Show HN
            source=self.name,
            source_url=f"https://news.ycombinator.com/item?id={story.get('objectID')}",
            company_url=story.get("url") or "",
            notes=[f"HN: {title}"],
        )
        created = story.get("created_at")
        if created:
            lead.launched_at = created

        if lead.company_url:
            from ..utils import domain_of
            lead.company_domain = domain_of(lead.company_url)

        # The submission text often carries the founder's own contact details.
        blob = " ".join(filter(None, [story.get("story_text"), title]))

        # The HN profile is where founders put their email and socials.
        profile = await self.client.get_json(USER_URL.format(username=author))
        if profile:
            about = profile.get("about") or ""
            blob += " " + about
            if about:
                lead.bio = re.sub(r"<[^>]+>", " ", about)[:400].strip()

        lead.notes.append(f"HN user: {author}")
        harvest_socials(blob, lead)

        emails = extract_emails(blob)
        if emails:
            lead.email = emails[0]
            lead.email_status = EmailStatus.PUBLISHED
            lead.email_source = "hn_profile"

        # HN usernames are pseudonyms; a real name has to come from enrichment.
        lead.notes.append("name pending enrichment" if not lead.full_name else "")
        lead.notes = [n for n in lead.notes if n]
        return lead
