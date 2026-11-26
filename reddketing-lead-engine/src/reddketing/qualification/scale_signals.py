"""Signs that a company is an established business, used when revenue is not publicly estimable.

A company with enough of these is assumed to make at least the $50K MRR floor. The assumption is
labelled as such everywhere it is shown; no revenue figure is invented.
"""
from __future__ import annotations

from ..models import CompanyProfile

USER_SIGNALS = {"paying_customers": 200, "business_customers": 200, "total_users": 10_000,
                "app_downloads": 50_000, "app_ratings_count": 1_000, "reviews_count": 200,
                "monthly_traffic": 100_000, "employees": 15}


def scale_signals(p: CompanyProfile) -> list[str]:
    ex = p.extraction
    found: list[str] = []
    users = max(((s.numeric_value or 0) for s in ex.signals
                 if s.signal_type in ("total_users", "paying_customers", "business_customers")), default=0)
    if users >= 10_000:
        found.append(f"{users:,.0f} users (10,000+ users is taken as at least $50K MRR)")
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


USER_COUNT_TYPES = ("total_users", "paying_customers", "business_customers", "app_downloads")


def max_signal(p: CompanyProfile, *types: str) -> float:
    return max((s.numeric_value or 0 for s in p.extraction.signals if s.signal_type in types), default=0)


def has_10k_users(p: CompanyProfile) -> bool:
    """Owner rule: about 10,000 active users means at least $50K MRR can be assumed."""
    return max_signal(p, "total_users", "paying_customers", "business_customers") >= 10_000


def size_exclusion(p: CompanyProfile, settings) -> str:
    """Reason the company is too large (or owned by another company) to prospect; empty if it fits."""
    lim = settings.get("size_limits", {}) or {}
    ex = p.extraction
    from ..utils.normalize import is_hobby_host
    if is_hobby_host(p.domain or "") or is_hobby_host(getattr(p, "website", "") or ""):
        return "Side project on free hosting, not an operating business"
    users = max_signal(p, *USER_COUNT_TYPES)
    if users >= float(lim.get("max_users", 100_000)):
        return f"Too large: {users:,.0f}+ users/customers/downloads (limit {lim.get('max_users', 100_000):,})"
    mid = p.revenue.mrr_mid
    if mid and p.revenue.confidence.value != "Assumed" and mid > float(lim.get("max_mrr_usd", 5_000_000)):
        return f"Too large: estimated MRR ${mid / 1e6:,.1f}M (limit ${float(lim.get('max_mrr_usd', 5e6)) / 1e6:,.0f}M)"
    funding_cap = lim.get("max_total_funding_usd")  # null = no funding limit
    funding = ex.funding.total_funding_usd or 0
    if funding_cap and funding >= float(funding_cap):
        return f"Too large: ${funding / 1e6:,.0f}M total funding"
    employees = max_signal(p, "employees")
    if employees >= float(lim.get("max_employees", 500)):
        return f"Too large: {employees:,.0f} employees"
    traffic = max_signal(p, "monthly_traffic")
    if traffic >= float(lim.get("max_monthly_traffic", 2_000_000)):
        return f"Too large: {traffic:,.0f} monthly visits"
    domain = (p.domain or "").lower()
    if any(domain == d or domain.endswith("." + d) for d in lim.get("big_company_domains", [])):
        return f"Product of a large company ({domain})"
    if lim.get("exclude_owned_by_other_company", True) and (ex.parent_company or "").strip():
        return f"Owned by {ex.parent_company.strip()}"
    return ""


def below_floor_by_own_data(p: CompanyProfile, floor_usd: float) -> bool:
    """Evidence-based estimate exists and its upper bound is under the floor: don't assume otherwise."""
    rev = p.revenue
    return (rev.mrr_high is not None and rev.mrr_high > 0 and rev.mrr_high < floor_usd
            and rev.confidence.value in ("High", "Medium", "Low"))


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
