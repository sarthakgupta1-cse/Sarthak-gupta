"""Traffic evidence.

Similarweb / Semrush / Ahrefs have no free API, and their pages block automated
access, so traffic is only taken from public figures the sources themselves state
(e.g. a press release saying "2M monthly visitors" or a cited third-party estimate).
A paid traffic provider can be added here later behind the same function.
"""
from __future__ import annotations

from ..models import CompanyProfile


def traffic_summary(profile: CompanyProfile) -> tuple[str, str]:
    """Returns (estimated monthly traffic text, traffic source text)."""
    sigs = [s for s in profile.signals_of("monthly_traffic") if s.claim_type != "unverified"]
    if not sigs:
        return "Not publicly available", "No public traffic figure found; paid traffic tools not configured"
    s = sigs[0]
    label = {"verified_fact": "verified", "company_reported": "company-reported",
             "third_party_estimate": "third-party estimate"}.get(s.claim_type, s.claim_type)
    return s.value_text, f"{label}: {profile.source_url(s.source_id)}"
