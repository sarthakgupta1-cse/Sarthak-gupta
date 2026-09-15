"""GitHub via the official REST API.

Open-core SaaS founders ship under their own account. A GitHub profile often
carries a real name, a company, a blog link and a public email — and the blog
link is the doorway to the company site crawl.
"""

from __future__ import annotations

import asyncio

from ..models import EmailStatus, Lead, harvest_socials
from ..utils import clean_text, domain_of
from .base import DiscoverySource

SEARCH = "https://api.github.com/search/repositories"
USER = "https://api.github.com/users/{login}"


class GitHubSource(DiscoverySource):
    name = "github"

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers

    async def discover(self, limit: int) -> list[Lead]:
        min_stars = self.config.get("min_stars", 150)
        keywords = self.settings.targeting.get("keywords", ["SaaS"])

        repos: list[dict] = []
        for keyword in keywords[:4]:
            params = {
                "q": f"{keyword} in:name,description,readme stars:>{min_stars}",
                "sort": "updated",
                "order": "desc",
                "per_page": 30,
            }
            data = await self.client.get_json(SEARCH, params=params, headers=self._headers())
            if not data:
                self.log.info("no GitHub results for %r (rate limited without a token?)", keyword)
                continue
            repos.extend(data.get("items", []))

        # One lead per owner, favouring the most-starred repo they own.
        by_owner: dict[str, dict] = {}
        for repo in repos:
            owner = (repo.get("owner") or {}).get("login")
            if not owner:
                continue
            if owner not in by_owner or repo.get("stargazers_count", 0) > by_owner[owner].get(
                "stargazers_count", 0
            ):
                by_owner[owner] = repo

        ranked = sorted(
            by_owner.values(), key=lambda r: r.get("stargazers_count", 0), reverse=True
        )[: limit * 2]

        results = await asyncio.gather(
            *(self._lead_from_repo(r) for r in ranked), return_exceptions=True
        )
        leads = [r for r in results if isinstance(r, Lead)]
        return leads[:limit]

    async def _lead_from_repo(self, repo: dict) -> Lead | None:
        owner = repo.get("owner") or {}
        login = owner.get("login")
        if not login:
            return None

        profile = await self.client.get_json(USER.format(login=login), headers=self._headers())
        if not profile:
            return None

        # Organisation accounts are companies, not people — skip to their site.
        is_org = profile.get("type") == "Organization"

        blog = profile.get("blog") or ""
        lead = Lead(
            full_name=profile.get("name") or "" if not is_org else "",
            role="Founder / Maintainer",
            company=(profile.get("company") or repo.get("name") or "").lstrip("@"),
            company_url=blog,
            company_domain=domain_of(blog),
            github_username=login,
            personal_site=blog,
            location=profile.get("location") or "",
            bio=clean_text(profile.get("bio") or ""),
            source=self.name,
            source_url=profile.get("html_url") or f"https://github.com/{login}",
            notes=[
                f"repo: {repo.get('full_name')} ({repo.get('stargazers_count', 0)}★)",
                clean_text(repo.get("description") or "", 160),
            ],
        )
        if profile.get("twitter_username"):
            lead.twitter_handle = profile["twitter_username"]

        public_email = profile.get("email")
        if public_email:
            lead.email = public_email.lower()
            lead.email_status = EmailStatus.PUBLISHED
            lead.email_source = "github_profile"

        harvest_socials(f"{profile.get('bio') or ''} {blog}", lead)
        lead.notes = [n for n in lead.notes if n]
        return lead
