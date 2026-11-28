"""Reddketing fit: exclusion rules and Reddit-suitability summary."""
from __future__ import annotations

from ..models import CompanyProfile

EXCLUSION_LABELS = {
    "pure_enterprise": "Pure enterprise software with no meaningful Reddit-reachable audience",
    "shut_down": "Company appears to have shut down",
    "restricted_category": "Restricted or unsuitable category",
    "no_product": "No verifiable product",
    "spam_dependent": "Marketing proposition depends on spam/fake reviews/manipulated engagement",
    "not_a_company": "Not an operating company",
    "wrong_website": "Website could not be confirmed as the company's official site",
    "service_business": "Agency or service business, not a product",
    "too_well_known": "Too large / already well known on Reddit",
}


def exclusion_reason(profile: CompanyProfile, settings) -> str:
    """Empty string if the company may be prospected; otherwise the reason."""
    ex = profile.extraction
    if ex.exclusion.excluded and ex.exclusion.reason != "none":
        label = EXCLUSION_LABELS.get(ex.exclusion.reason, ex.exclusion.reason)
        return f"{label}: {ex.exclusion.explanation}".strip(": ")
    text = f"{ex.product_category} {ex.industry} {ex.one_line_description}".lower()
    for word in settings.categories.get("restricted_categories", []):
        if word.lower() in text:
            return f"Restricted category ({word})"
    # Backup to the research model's "service_business" flag. Checked on the category and industry only,
    # so software *for* agencies (e.g. travel-agency software) is not caught.
    cat = f"{ex.product_category} {ex.industry}".lower()
    for phrase in settings.categories.get("service_business_phrases", []):
        if phrase.lower() in cat:
            return f"Agency or service business ({phrase}), not a product"
    if ex.audience_type == "enterprise_only" and ex.reddit.consumer_or_prosumer <= 1:
        flags = [w for w in settings.categories.get("enterprise_red_flags", []) if w.lower() in text]
        return "Enterprise-only audience" + (f" ({', '.join(flags)})" if flags else "")
    if not ex.official_website_confirmed:
        return EXCLUSION_LABELS["wrong_website"]
    return ""


def reddit_suitability(profile: CompanyProfile) -> str:
    r = profile.extraction.reddit
    avg = (r.understandable_to_redditors + r.community_participation + r.recommendation_driven
           + r.naturally_discussed + r.consumer_or_prosumer) / 5
    level = "High" if avg >= 3.8 else "Medium" if avg >= 2.6 else "Low"
    return (f"{level} — understandable {r.understandable_to_redditors}/5, community activity "
            f"{r.community_participation}/5, recommendation-driven {r.recommendation_driven}/5, "
            f"naturally discussed {r.naturally_discussed}/5, consumer/prosumer {r.consumer_or_prosumer}/5")


def subreddit_text(profile: CompanyProfile) -> str:
    subs = profile.extraction.reddit.subreddits
    if not subs:
        return "None identified from public sources"
    return "; ".join(f"{s.name}{'' if s.source_id else ' (audience fit, not source-verified)'}" for s in subs)
