"""LinkedIn data via Proxycurl's licensed API.

Deliberately NOT a LinkedIn scraper. We never log into linkedin.com, never
drive a headless browser against it, and never touch a member session cookie.
Proxycurl holds the data and the legal exposure that comes with it; we consume
an ordinary REST API. That is the difference between a lead list and a banned
account plus a cease-and-desist.
"""

from __future__ import annotations

from ..models import Lead
from ..utils import clean_text, domain_of
from .base import Enricher

PROFILE = "https://nubela.co/proxycurl/api/v2/linkedin"
RESOLVE = "https://nubela.co/proxycurl/api/linkedin/profile/resolve"


class ProxycurlEnricher(Enricher):
    name = "proxycurl"
    cost_per_lead_usd = 0.03

    def available(self) -> tuple[bool, str]:
        ok, why = super().available()
        if not ok:
            return ok, why
        if not self.settings.proxycurl_key:
            return False, "PROXYCURL_API_KEY not set"
        return True, ""

    def should_run(self, lead: Lead) -> bool:
        # Worth a credit only if we can identify them and don't already have the profile.
        if lead.linkedin_url and lead.full_name and lead.role:
            return False
        return bool(lead.linkedin_url or (lead.full_name and lead.company_domain))

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.settings.proxycurl_key}"}

    async def enrich(self, lead: Lead) -> Lead:
        url = lead.linkedin_url
        if not url:
            url = await self._resolve(lead)
            if not url:
                return lead
            lead.linkedin_url = url

        data = await self.client.get_json(
            PROFILE,
            params={"url": url, "extra": "include", "personal_email": "include"},
            headers=self._headers,
            respect_robots=False,
        )
        if not data:
            return lead

        first = data.get("first_name") or ""
        last = data.get("last_name") or ""
        if not lead.full_name and (first or last):
            lead.full_name = f"{first} {last}".strip()

        occupation = data.get("occupation") or ""
        if occupation and not self.settings.is_founder_title(lead.role):
            lead.role = occupation

        experiences = data.get("experiences") or []
        if experiences:
            current = experiences[0]
            if not lead.company:
                lead.company = current.get("company") or ""
            company_url = current.get("company_linkedin_profile_url") or ""
            if company_url:
                lead.notes.append(f"company LinkedIn: {company_url}")

        if not lead.location:
            city = data.get("city") or ""
            country = data.get("country_full_name") or ""
            lead.location = ", ".join(p for p in (city, country) if p)

        if not lead.bio:
            lead.bio = clean_text(data.get("summary") or "")

        # Proxycurl surfaces contact details the member chose to publish.
        for email in (data.get("personal_emails") or []):
            if email and not lead.email:
                from ..models import EmailStatus
                lead.email = email.lower()
                lead.email_status = EmailStatus.PUBLISHED
                lead.email_source = "proxycurl"
                break

        from ..models import harvest_socials
        harvest_socials(
            " ".join(filter(None, [data.get("summary"), *(data.get("personal_numbers") or [])])),
            lead,
        )

        if not lead.company_domain and lead.company:
            website = (data.get("experiences") or [{}])[0].get("company") or ""
            lead.company_domain = domain_of(website) or lead.company_domain

        lead.notes.append("linkedin enriched via proxycurl")
        return lead

    async def _resolve(self, lead: Lead) -> str:
        """Find the profile URL from a name + company, when we don't have it."""
        params = {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "company_domain": lead.company_domain,
            "enrich_profile": "skip",
        }
        if not params["first_name"] or not params["company_domain"]:
            return ""
        data = await self.client.get_json(
            RESOLVE, params=params, headers=self._headers, respect_robots=False
        )
        return (data or {}).get("url") or ""
