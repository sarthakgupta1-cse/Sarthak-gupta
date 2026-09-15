"""Hunter.io — find and verify work email addresses.

Verification is the point. An unverified guess sent at volume is how a sending
domain gets blocklisted, so anything Hunter can't confirm is written as
GUESSED and held back from outreach by the pipeline.
"""

from __future__ import annotations

from ..compliance import is_role_address
from ..models import EmailStatus, Lead
from .base import Enricher

FIND = "https://api.hunter.io/v2/email-finder"
VERIFY = "https://api.hunter.io/v2/email-verifier"
DOMAIN = "https://api.hunter.io/v2/domain-search"

# Hunter's verdicts, mapped onto how much we trust the address.
_STATUS_MAP = {
    "valid": EmailStatus.VERIFIED,
    "accept_all": EmailStatus.RISKY,
    "webmail": EmailStatus.RISKY,
    "disposable": EmailStatus.RISKY,
    "invalid": EmailStatus.UNKNOWN,
    "unknown": EmailStatus.UNKNOWN,
}


class HunterEnricher(Enricher):
    name = "hunter"
    cost_per_lead_usd = 0.01

    def available(self) -> tuple[bool, str]:
        ok, why = super().available()
        if not ok:
            return ok, why
        if not self.settings.hunter_key:
            return False, "HUNTER_API_KEY not set"
        return True, ""

    def should_run(self, lead: Lead) -> bool:
        if lead.email and lead.email_status == EmailStatus.VERIFIED:
            return False
        return bool(lead.company_domain)

    async def enrich(self, lead: Lead) -> Lead:
        key = self.settings.hunter_key

        # 1. Verify what we already have rather than paying to find it again.
        if lead.email:
            data = await self.client.get_json(
                VERIFY, params={"email": lead.email, "api_key": key}, respect_robots=False
            )
            result = (data or {}).get("data") or {}
            if result:
                status = _STATUS_MAP.get(result.get("status", ""), EmailStatus.UNKNOWN)
                lead.email_status = status
                lead.notes.append(f"hunter verify: {result.get('status')}")
                if status == EmailStatus.VERIFIED:
                    return lead
                if status == EmailStatus.UNKNOWN:
                    lead.notes.append(f"dropped invalid address {lead.email}")
                    lead.email = ""
                    lead.email_source = ""

        # 2. Find the person's address by name at their domain.
        if lead.first_name and lead.company_domain:
            data = await self.client.get_json(
                FIND,
                params={
                    "domain": lead.company_domain,
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "api_key": key,
                },
                respect_robots=False,
            )
            result = (data or {}).get("data") or {}
            email = result.get("email")
            if email:
                score = result.get("score") or 0
                verification = (result.get("verification") or {}).get("status") or ""
                lead.email = email.lower()
                lead.email_status = (
                    EmailStatus.VERIFIED
                    if verification == "valid" or score >= 90
                    else EmailStatus.GUESSED
                )
                lead.email_source = "hunter_finder"
                lead.notes.append(f"hunter finder: confidence {score}")
                if lead.email_status == EmailStatus.VERIFIED:
                    return lead

        # 3. Last resort: pull the domain's known people and look for a founder.
        if not lead.email and lead.company_domain:
            data = await self.client.get_json(
                DOMAIN,
                params={"domain": lead.company_domain, "api_key": key, "limit": 10},
                respect_robots=False,
            )
            result = (data or {}).get("data") or {}
            for record in result.get("emails", []):
                address = record.get("value") or ""
                if not address or is_role_address(address):
                    continue
                position = record.get("position") or ""
                if not self.settings.is_founder_title(position):
                    continue
                lead.email = address.lower()
                lead.email_status = (
                    EmailStatus.VERIFIED
                    if record.get("verification", {}).get("status") == "valid"
                    else EmailStatus.GUESSED
                )
                lead.email_source = "hunter_domain_search"
                if not lead.full_name:
                    first = record.get("first_name") or ""
                    last = record.get("last_name") or ""
                    lead.full_name = f"{first} {last}".strip()
                if position and not self.settings.is_founder_title(lead.role):
                    lead.role = position
                break

        return lead
