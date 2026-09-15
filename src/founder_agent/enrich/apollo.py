"""Apollo.io — people search and person enrichment.

Two jobs: fill in a founder we already half-know, and (in search mode) find
founders at companies we only know by domain. Apollo returns work emails and
LinkedIn URLs under its own data licence.
"""

from __future__ import annotations

from ..models import EmailStatus, Lead
from ..utils import clean_text, domain_of
from .base import Enricher

MATCH = "https://api.apollo.io/api/v1/people/match"
SEARCH = "https://api.apollo.io/api/v1/mixed_people/search"


class ApolloEnricher(Enricher):
    name = "apollo"
    cost_per_lead_usd = 0.02

    def available(self) -> tuple[bool, str]:
        ok, why = super().available()
        if not ok:
            return ok, why
        if not self.settings.apollo_key:
            return False, "APOLLO_API_KEY not set"
        return True, ""

    def should_run(self, lead: Lead) -> bool:
        if lead.email and lead.email_status == EmailStatus.VERIFIED and lead.linkedin_url:
            return False
        return bool(lead.company_domain or lead.linkedin_url or lead.email)

    @property
    def _headers(self) -> dict:
        return {
            "X-Api-Key": self.settings.apollo_key,
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }

    async def enrich(self, lead: Lead) -> Lead:
        payload = {"reveal_personal_emails": False}
        if lead.email:
            payload["email"] = lead.email
        if lead.linkedin_url:
            payload["linkedin_url"] = lead.linkedin_url
        if lead.first_name:
            payload["first_name"] = lead.first_name
            payload["last_name"] = lead.last_name
        if lead.company_domain:
            payload["domain"] = lead.company_domain

        resp = await self.client.post(MATCH, json=payload, headers=self._headers)
        if resp is None or resp.status_code >= 400:
            if resp is not None and resp.status_code == 402:
                self.log.warning("Apollo credits exhausted")
            return lead

        person = (resp.json() or {}).get("person") or {}
        if not person:
            return lead
        return self._apply(lead, person)

    def _apply(self, lead: Lead, person: dict) -> Lead:
        if not lead.full_name:
            lead.full_name = person.get("name") or ""
        title = person.get("title") or ""
        if title and not self.settings.is_founder_title(lead.role):
            lead.role = title
        if not lead.linkedin_url:
            lead.linkedin_url = person.get("linkedin_url") or ""
        if not lead.twitter_handle and person.get("twitter_url"):
            lead.twitter_handle = person["twitter_url"].rstrip("/").split("/")[-1]
        if not lead.github_username and person.get("github_url"):
            lead.github_username = person["github_url"].rstrip("/").split("/")[-1]
        if not lead.location:
            lead.location = ", ".join(
                p for p in (person.get("city"), person.get("country")) if p
            )
        if not lead.bio:
            lead.bio = clean_text(person.get("headline") or "")

        org = person.get("organization") or {}
        if org:
            if not lead.company:
                lead.company = org.get("name") or ""
            if not lead.company_domain:
                lead.company_domain = domain_of(org.get("website_url") or "")
            if lead.headcount is None and org.get("estimated_num_employees"):
                lead.headcount = org["estimated_num_employees"]

        email = person.get("email") or ""
        # Apollo masks unverified addresses behind this placeholder — never send to it.
        if email and "email_not_unlocked" not in email:
            status = person.get("email_status") or ""
            if not lead.email or status == "verified":
                lead.email = email.lower()
                lead.email_status = (
                    EmailStatus.VERIFIED if status == "verified" else EmailStatus.GUESSED
                )
                lead.email_source = "apollo"

        lead.notes.append("apollo enriched")
        return lead

    async def search_founders(self, domains: list[str], per_company: int = 2) -> list[Lead]:
        """Discovery mode: given company domains, find the founders at each."""
        titles = self.settings.targeting.get("founder_titles", ["founder", "ceo"])
        payload = {
            "q_organization_domains_list": domains[:100],
            "person_titles": titles,
            "page": 1,
            "per_page": min(per_company * len(domains), 100),
        }
        resp = await self.client.post(SEARCH, json=payload, headers=self._headers)
        if resp is None or resp.status_code >= 400:
            self.log.warning(
                "Apollo search failed: %s", resp.status_code if resp else "no response"
            )
            return []

        leads: list[Lead] = []
        for person in (resp.json() or {}).get("people", []):
            lead = Lead(source="apollo", source_url=person.get("linkedin_url") or "")
            leads.append(self._apply(lead, person))
        return leads
