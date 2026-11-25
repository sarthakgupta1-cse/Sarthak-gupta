"""Funding facts: validation and recency checks."""
from __future__ import annotations

import re
from datetime import date, timedelta

from ..models import CompanyProfile


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    text = text.strip()
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 15))
        except ValueError:
            return None
    return None


def funding_is_recent(profile: CompanyProfile, today: date, lookback_days: int) -> bool:
    f = profile.extraction.funding
    d = parse_date(f.latest_date) or parse_date(profile.candidate.funding_hint.get("date"))
    if not d:
        return False
    return today - timedelta(days=lookback_days) <= d <= today + timedelta(days=2)


def funding_date(profile: CompanyProfile) -> str:
    f = profile.extraction.funding
    return f.latest_date or profile.candidate.funding_hint.get("date") or ""


def funding_amount(profile: CompanyProfile) -> float | None:
    f = profile.extraction.funding
    return f.latest_amount_usd or profile.candidate.funding_hint.get("amount_usd")


def funding_round(profile: CompanyProfile) -> str:
    f = profile.extraction.funding
    return f.latest_round or profile.candidate.funding_hint.get("round") or ""


def funding_source(profile: CompanyProfile) -> str:
    f = profile.extraction.funding
    return profile.source_url(f.source_id) or profile.candidate.funding_hint.get("source_url", "")


def validate_funding(profile: CompanyProfile) -> list[str]:
    """Drop funding facts whose cited source is missing; never let funding masquerade as revenue."""
    notes = []
    f = profile.extraction.funding
    if (f.latest_amount_usd or f.latest_round) and not profile.source_url(f.source_id):
        if not profile.candidate.funding_hint.get("source_url"):
            notes.append("Funding details removed: no valid source cited")
            f.latest_amount_usd = None
            f.latest_round = None
            f.latest_date = None
            f.total_funding_usd = None
    if f.latest_amount_usd and f.latest_amount_usd > 5e10:
        notes.append("Implausible funding amount removed")
        f.latest_amount_usd = None
    return notes
