"""Signs that a company is an established business, used when revenue is not publicly estimable.

A company with enough of these is assumed to make at least the $50K MRR floor. The assumption is
labelled as such everywhere it is shown; no revenue figure is invented.
"""
from __future__ import annotations

from ..models import CompanyProfile

USER_SIGNALS = {"paying_customers": 200, "business_customers": 200, "total_users": 5_000,
                "app_downloads": 50_000, "app_ratings_count": 1_000, "reviews_count": 200,
                "monthly_traffic": 100_000, "employees": 15}


def scale_signals(p: CompanyProfile) -> list[str]:
    ex = p.extraction
    found: list[str] = []
    paid = [pp for pp in ex.pricing if (pp.price_usd_per_month or 0) > 0]
    if paid:
        found.append(f"public paid pricing ({len(paid)} paid plan{'s' if len(paid) > 1 else ''})")
    total_funding = ex.funding.total_funding_usd or ex.funding.latest_amount_usd or 0
    if total_funding >= 3_000_000:
        found.append(f"raised ${total_funding / 1e6:,.1f}M")
    seen: set[str] = set()
    for s in ex.signals:
        floor = USER_SIGNALS.get(s.signal_type)
        if floor and (s.numeric_value or 0) >= floor and s.signal_type not in seen:
            seen.add(s.signal_type)
            found.append(f"{s.signal_type.replace('_', ' ')}: {s.value_text[:80]}")
        elif s.signal_type in ("press_coverage", "advertising_activity", "partnerships") and s.signal_type not in seen:
            seen.add(s.signal_type)
            found.append(s.signal_type.replace("_", " "))
    if ex.hiring_growth_roles:
        found.append("hiring growth/marketing roles")
    if ex.founded_year and ex.founded_year <= 2023:
        found.append(f"operating since {ex.founded_year}")
    return found


def assume_floor(p: CompanyProfile, floor_usd: float, signals: list[str]) -> None:
    """Mark the profile as assumed to make at least `floor_usd` MRR, keeping any evidence it has."""
    rev = p.revenue
    prior = (f"Evidence-based estimate was {rev.confidence.value.lower()}"
             + (f" ({rev.calculation})" if rev.calculation else "") + ". ") if rev.mrr_low else ""
    rev.method = "Assumed minimum"
    rev.calculation = (f"{prior}Assumed at least ${floor_usd:,.0f} MRR from business-scale signals: "
                       + "; ".join(signals or ["none found"]) + ". Not a measured figure.")
    rev.assumptions = [f"Revenue assumed at the ${floor_usd:,.0f}/month floor; not verified from public data"] \
        + rev.assumptions
    rev.mrr_low, rev.mrr_high, rev.arr_low, rev.arr_high = floor_usd, None, None, None
    rev.confidence = rev.confidence.__class__.ASSUMED
