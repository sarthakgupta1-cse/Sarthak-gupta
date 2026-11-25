"""Revenue-confidence classification (kept separate from lead quality)."""
from __future__ import annotations

from ..models import Confidence

INDICATOR_TYPES = {"revenue_disclosed", "arr_disclosed", "mrr_disclosed", "paying_customers", "total_users",
                   "business_customers", "app_downloads", "app_ratings_count", "monthly_traffic", "employees",
                   "reviews_count", "github_stars", "hiring_marketing", "advertising_activity"}


def count_indicators(signals, has_pricing: bool) -> int:
    kinds = {s.signal_type for s in signals if s.signal_type in INDICATOR_TYPES and s.claim_type != "unverified"}
    return len(kinds) + (1 if has_pricing else 0)


def classify_disclosed(claim_type: str, fully_read: bool) -> Confidence:
    if claim_type in ("verified_fact", "company_reported") and fully_read:
        return Confidence.HIGH
    return Confidence.MEDIUM


def classify_modelled(*, customers_evidenced: bool, arpu_evidenced: bool, indicators: int,
                      source_domains: int, min_low: int, spread: float) -> Confidence:
    if customers_evidenced and arpu_evidenced and indicators >= 3 and source_domains >= 2 and spread <= 12:
        return Confidence.MEDIUM
    if indicators >= min_low:
        return Confidence.LOW
    return Confidence.INSUFFICIENT
