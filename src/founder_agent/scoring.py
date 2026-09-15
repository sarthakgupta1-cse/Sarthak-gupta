"""Score a lead by how reachable and how on-target it is.

The score exists so a human works the top of the list first. It is not a
quality judgement about the person.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .compliance import is_freemail, is_role_address
from .config import Settings
from .models import EmailStatus, Lead


def score_lead(lead: Lead, settings: Settings) -> int:
    weights = settings.scoring.get("weights", {})
    score = 0

    if lead.email:
        if lead.email_status == EmailStatus.VERIFIED:
            score += weights.get("verified_email", 30)
        else:
            score += weights.get("any_email", 15)
        # A role address isn't a person, and a freemail address is a weaker B2B basis.
        if is_role_address(lead.email):
            score -= 20
            lead.notes.append("role address, not a person")
        if is_freemail(lead.email):
            score -= 5

    if lead.linkedin_url:
        score += weights.get("linkedin_url", 20)
    if settings.is_founder_title(lead.role):
        score += weights.get("is_founder_title", 20)
    if lead.twitter_handle:
        score += weights.get("twitter_handle", 8)
    if lead.telegram_handle:
        score += weights.get("telegram_handle", 8)
    if lead.github_username:
        score += weights.get("github_username", 6)
    if lead.company_domain:
        score += weights.get("company_domain", 10)

    # A launch in the last 90 days means they're in a buying window.
    if lead.launched_at:
        try:
            launched = datetime.fromisoformat(lead.launched_at.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - launched).days <= 90:
                score += weights.get("recent_launch", 12)
        except (ValueError, TypeError):
            pass

    # Headcount ceiling: we're after founders we can reach, not enterprises.
    max_headcount = settings.targeting.get("max_headcount")
    if max_headcount and lead.headcount and lead.headcount > max_headcount:
        score -= 15
        lead.notes.append(f"headcount {lead.headcount} over target")

    if not lead.full_name:
        score -= 10

    lead.score = max(score, 0)
    return lead.score


def is_contactable(lead: Lead) -> bool:
    """Only verified or self-published addresses should ever receive cold mail."""
    return bool(lead.email) and lead.email_status in (
        EmailStatus.VERIFIED,
        EmailStatus.PUBLISHED,
    ) and not is_role_address(lead.email)
