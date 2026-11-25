"""Reddketing lead score (0-100) — deterministic arithmetic over validated evidence.

A Revenue & financial potential .......... 20
B Reddit marketing opportunity ........... 25
C Product-market fit & audience .......... 15
D Marketing investment & growth .......... 15
E Funding & financial strength ........... 10
F Relevant Reddit community potential .... 15
Funding is capped at 10 points so a well-funded company without a Reddit
audience cannot outrank a smaller company with a strong Reddit opportunity.
"""
from __future__ import annotations

from datetime import date

from ..models import ComponentScore, CompanyProfile, Confidence, ScoreBreakdown
from ..research.funding_research import funding_is_recent
from ..research.revenue_estimator import usd

CONF_MULT = {Confidence.HIGH: 1.0, Confidence.MEDIUM: 0.9, Confidence.LOW: 0.75, Confidence.INSUFFICIENT: 0.5}
AUDIENCE_POINTS = {"consumer": 8, "prosumer": 8, "developer": 8, "smb_self_serve": 6, "mixed": 5, "enterprise_only": 1}


def _clamp(x: float, hi: float) -> float:
    return round(max(0.0, min(hi, x)), 1)


def score_revenue(p: CompanyProfile) -> ComponentScore:
    mid = p.revenue.mrr_mid
    if mid is None:
        base, why = 3, "Revenue not publicly estimable"
    else:
        tiers = [(500_000, 20), (200_000, 17), (100_000, 14), (50_000, 11), (20_000, 6)]
        base = next((pts for floor, pts in tiers if mid >= floor), 2)
        why = f"Estimated MRR midpoint {usd(mid)}"
    mult = CONF_MULT[p.revenue.confidence]
    return ComponentScore(points=_clamp(base * mult, 20), max_points=20,
                          reason=f"{why}; confidence {p.revenue.confidence.value} (x{mult})")


def score_reddit(p: CompanyProfile) -> ComponentScore:
    r = p.extraction.reddit
    pts = (r.understandable_to_redditors + r.recommendation_driven + r.naturally_discussed
           + r.consumer_or_prosumer + r.acquisition_challenge)
    return ComponentScore(points=_clamp(pts, 25), max_points=25, reason=(
        f"understandable {r.understandable_to_redditors}, recommendation-driven {r.recommendation_driven}, "
        f"naturally discussed {r.naturally_discussed}, consumer/prosumer {r.consumer_or_prosumer}, "
        f"acquisition challenge {r.acquisition_challenge} (each /5). {r.explanation[:240]}"))


def score_pmf(p: CompanyProfile) -> ComponentScore:
    ex = p.extraction
    pts = AUDIENCE_POINTS.get(ex.audience_type, 4)
    reasons = [f"audience {ex.audience_type} ({pts}/8)"]
    if any(pp.price_usd_per_month for pp in ex.pricing):
        pts += 4
        reasons.append("public self-serve pricing (+4)")
    adoption = p.signals_of("paying_customers", "total_users", "business_customers", "app_downloads",
                            "app_ratings_count", "reviews_count")
    if any(s.claim_type != "unverified" for s in adoption):
        pts += 3
        reasons.append("documented user/customer adoption (+3)")
    return ComponentScore(points=_clamp(pts, 15), max_points=15, reason="; ".join(reasons))


def score_marketing(p: CompanyProfile) -> ComponentScore:
    ex = p.extraction
    pts, reasons = float(ex.reddit.active_marketing), [f"active marketing {ex.reddit.active_marketing}/5"]
    if ex.hiring_growth_roles:
        pts += 5
        reasons.append("hiring marketing/growth roles (+5)")
    growth = {s.signal_type for s in p.signals_of("advertising_activity", "press_coverage", "growth_claim",
                                                  "monthly_traffic", "hiring_marketing")
              if s.claim_type != "unverified"}
    extra = min(5, 2 * len(growth))
    if extra:
        pts += extra
        reasons.append(f"growth signals: {', '.join(sorted(growth))} (+{extra})")
    return ComponentScore(points=_clamp(pts, 15), max_points=15, reason="; ".join(reasons))


def score_funding(p: CompanyProfile, today: date, lookback_days: int) -> ComponentScore:
    f = p.extraction.funding
    amount = f.total_funding_usd or f.latest_amount_usd or p.candidate.funding_hint.get("amount_usd")
    if not amount:
        if p.revenue.confidence in (Confidence.HIGH, Confidence.MEDIUM) and (p.revenue.mrr_mid or 0) >= 50_000:
            pts, why = 5, "No disclosed funding; revenue suggests self-funded strength"
        else:
            pts, why = 2, "No funding publicly disclosed"
    else:
        pts = 4 if amount < 1e6 else 6 if amount < 1e7 else 8 if amount < 5e7 else 9
        why = f"Known funding {usd(amount)}"
    if funding_is_recent(p, today, lookback_days):
        pts += 1
        why += "; raised within lookback window (+1)"
    return ComponentScore(points=_clamp(pts, 10), max_points=10, reason=why)


def score_community(p: CompanyProfile) -> ComponentScore:
    r = p.extraction.reddit
    sub_pts = sum(2 if s.source_id else 1 for s in r.subreddits)
    pts = r.community_participation * 2 + min(5, sub_pts)
    return ComponentScore(points=_clamp(pts, 15), max_points=15, reason=(
        f"audience community participation {r.community_participation}/5 (x2); "
        f"{len(r.subreddits)} relevant subreddit(s) identified (+{min(5, sub_pts)})"))


def score_profile(p: CompanyProfile, today: date, lookback_days: int = 180) -> ScoreBreakdown:
    s = ScoreBreakdown(revenue=score_revenue(p), reddit_opportunity=score_reddit(p), product_market_fit=score_pmf(p),
                       marketing_growth=score_marketing(p), funding=score_funding(p, today, lookback_days),
                       community_potential=score_community(p))
    p.scores = s
    return s


def score_reasons_text(s: ScoreBreakdown) -> str:
    names = ["Revenue", "Reddit opportunity", "Product-market fit", "Marketing & growth", "Funding", "Community"]
    return "\n".join(f"{n}: {c.points:g}/{c.max_points:g} — {c.reason}" for n, c in zip(names, s.components()))
