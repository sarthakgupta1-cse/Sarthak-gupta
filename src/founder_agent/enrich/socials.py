"""Socials and Telegram, from pages the person published themselves.

Where the handles come from, in order of preference:
  1. their personal site / link-in-bio page
  2. their GitHub profile README (github.com/<user>/<user>)
  3. the company site footer

Telegram specifically: we read t.me links the founder published. There is no
enumeration of Telegram itself, no member-list harvesting from groups, and no
resolution of phone numbers to accounts — those are both against Telegram's
ToS and, in most of the EU, unlawful processing.
"""

from __future__ import annotations

import re

from ..models import Lead, harvest_socials
from .base import Enricher

GITHUB_README = "https://raw.githubusercontent.com/{u}/{u}/HEAD/README.md"
GITHUB_API = "https://api.github.com/users/{u}"

_LINK_HUBS = ("linktr.ee", "bio.link", "beacons.ai", "carrd.co", "about.me")


class SocialsEnricher(Enricher):
    name = "socials"
    cost_per_lead_usd = 0.0

    def should_run(self, lead: Lead) -> bool:
        have = [lead.twitter_handle, lead.telegram_handle, lead.github_username, lead.linkedin_url]
        if all(have):
            return False
        return bool(lead.personal_site or lead.github_username or lead.company_domain)

    async def enrich(self, lead: Lead) -> Lead:
        # 1. Personal site / link hub — the densest source of handles.
        if lead.personal_site:
            await self._harvest_url(lead.personal_site, lead)

        # 2. GitHub profile README, where developers list every way to reach them.
        if lead.github_username:
            user = lead.github_username
            resp = await self.client.get(
                GITHUB_README.format(u=user), respect_robots=False
            )
            if resp is not None and resp.status_code < 400:
                harvest_socials(resp.text, lead)

            if not lead.personal_site:
                profile = await self.client.get_json(GITHUB_API.format(u=user))
                blog = (profile or {}).get("blog") or ""
                if blog:
                    lead.personal_site = blog
                    if any(hub in blog for hub in _LINK_HUBS):
                        await self._harvest_url(blog, lead)

        # 3. Company site footer, which usually carries the official socials.
        if lead.company_domain and not (lead.twitter_handle and lead.telegram_handle):
            await self._harvest_url(f"https://{lead.company_domain}", lead)

        return lead

    async def _harvest_url(self, url: str, lead: Lead) -> None:
        if not url:
            return
        if "://" not in url:
            url = "https://" + url
        resp = await self.client.get(url)
        if resp is None or resp.status_code >= 400:
            return
        if "html" not in resp.headers.get("content-type", "") and "text" not in resp.headers.get(
            "content-type", ""
        ):
            return
        # Keep it to the hrefs and visible text; scripts are full of false positives.
        html = re.sub(r"<script.*?</script>", " ", resp.text, flags=re.DOTALL | re.IGNORECASE)
        harvest_socials(html, lead)
