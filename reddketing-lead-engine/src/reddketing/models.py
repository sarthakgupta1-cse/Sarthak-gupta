"""Data models. LLM output is validated against these before any use."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- sources
SourceKind = Literal["company_page", "third_party_page", "search_snippet", "news_headline", "feed_item"]


class SourceDoc(BaseModel):
    id: str
    url: str
    title: str = ""
    kind: SourceKind
    text: str = ""
    accessed_at: str = ""
    publisher: str = ""

    @property
    def fully_read(self) -> bool:
        return self.kind in ("company_page", "third_party_page")


# ---------------------------------------------------------------- discovery
class Candidate(BaseModel):
    name: str
    website: str = ""
    domain: str = ""
    discovery_channels: list[str] = Field(default_factory=list)
    discovery_urls: list[str] = Field(default_factory=list)
    discovery_note: str = ""
    funding_hint: dict = Field(default_factory=dict)  # round, amount_usd, date, source_url
    is_funding_lead: bool = False
    audience: str = "unknown"


class ExtractedCandidate(BaseModel):
    name: str
    website: Optional[str] = None
    item_ids: list[str] = Field(default_factory=list)
    why_relevant: str = ""
    is_funding_announcement: bool = False
    funding_round: Optional[str] = None
    funding_amount_usd: Optional[float] = None
    announcement_date: Optional[str] = None
    # Who buys it, as far as the items show. "enterprise_only" and "deep_tech_or_hardware" are
    # dropped before research (no Reddit audience); "unknown" is kept.
    audience: Literal["consumer", "prosumer", "developer", "smb_self_serve", "enterprise_only",
                      "deep_tech_or_hardware", "unknown"] = "unknown"


class CandidateExtraction(BaseModel):
    candidates: list[ExtractedCandidate] = Field(default_factory=list)


# ---------------------------------------------------------------- LLM research extraction
ClaimType = Literal["verified_fact", "company_reported", "third_party_estimate", "unverified"]
SignalType = Literal[
    "revenue_disclosed", "arr_disclosed", "mrr_disclosed", "paying_customers", "total_users",
    "business_customers", "app_downloads", "app_ratings_count", "monthly_traffic", "employees",
    "funding", "hiring_marketing", "advertising_activity", "press_coverage", "reviews_count",
    "github_stars", "partnerships", "growth_claim", "other",
]
BusinessModel = Literal["saas_subscription", "mobile_app_subscription", "ecommerce", "marketplace",
                        "freemium_consumer", "usage_based_api", "online_education", "other"]
AudienceType = Literal["consumer", "prosumer", "developer", "smb_self_serve", "mixed", "enterprise_only"]


class PricePoint(BaseModel):
    plan_name: str
    price_usd_per_month: Optional[float] = None
    billing_note: str = ""
    source_id: str


class Signal(BaseModel):
    signal_type: SignalType
    value_text: str
    numeric_value: Optional[float] = None
    as_of: str = ""
    claim_type: ClaimType
    source_id: str


class Assumption(BaseModel):
    text: str
    source_id: Optional[str] = None


class RevenueInputs(BaseModel):
    model_type: BusinessModel
    paying_customers_low: Optional[float] = None
    paying_customers_high: Optional[float] = None
    paying_customers_source_id: Optional[str] = None
    arpu_monthly_low: Optional[float] = None
    arpu_monthly_high: Optional[float] = None
    monthly_orders_low: Optional[float] = None
    monthly_orders_high: Optional[float] = None
    avg_order_value_low: Optional[float] = None
    avg_order_value_high: Optional[float] = None
    monthly_gmv_low: Optional[float] = None
    monthly_gmv_high: Optional[float] = None
    take_rate_low: Optional[float] = None
    take_rate_high: Optional[float] = None
    assumptions: list[Assumption] = Field(default_factory=list)


class FundingInfo(BaseModel):
    latest_round: Optional[str] = None
    latest_amount_usd: Optional[float] = None
    latest_date: Optional[str] = None  # YYYY-MM-DD or YYYY-MM
    lead_investors: list[str] = Field(default_factory=list)
    total_funding_usd: Optional[float] = None
    source_id: Optional[str] = None


class Person(BaseModel):
    name: str
    title: str = ""
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    source_id: str


class Subreddit(BaseModel):
    name: str
    rationale: str
    source_id: Optional[str] = None


class RedditAssessment(BaseModel):
    understandable_to_redditors: int = Field(ge=0, le=5)
    community_participation: int = Field(ge=0, le=5)
    recommendation_driven: int = Field(ge=0, le=5)
    acquisition_challenge: int = Field(ge=0, le=5)
    active_marketing: int = Field(ge=0, le=5)
    consumer_or_prosumer: int = Field(ge=0, le=5)
    naturally_discussed: int = Field(ge=0, le=5)
    subreddits: list[Subreddit] = Field(default_factory=list)
    explanation: str
    relevant_audience: str = ""


class Exclusion(BaseModel):
    excluded: bool
    reason: Literal["none", "pure_enterprise", "shut_down", "restricted_category", "no_product",
                    "spam_dependent", "not_a_company", "wrong_website", "service_business", "too_well_known"]
    explanation: str = ""


class ResearchExtraction(BaseModel):
    company_name: str
    aliases: list[str] = Field(default_factory=list)
    parent_company: Optional[str] = None
    official_website_confirmed: bool
    one_line_description: str
    product_category: str
    industry: str
    business_model: BusinessModel
    audience_type: AudienceType
    headquarters: Optional[str] = None
    country: Optional[str] = None
    founded_year: Optional[int] = None
    pricing: list[PricePoint] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    revenue_inputs: RevenueInputs
    funding: FundingInfo = Field(default_factory=FundingInfo)
    people: list[Person] = Field(default_factory=list)
    reddit: RedditAssessment
    hiring_growth_roles: bool = False
    hiring_evidence_source_id: Optional[str] = None
    exclusion: Exclusion
    discrepancies: list[str] = Field(default_factory=list)
    research_notes: str = ""


# ---------------------------------------------------------------- derived (deterministic) results
class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    ASSUMED = "Assumed"  # not estimated from evidence; assumed to meet the $50K MRR floor from business-scale signals
    INSUFFICIENT = "Insufficient"


class RevenueEstimate(BaseModel):
    method: str
    mrr_low: Optional[float] = None
    mrr_high: Optional[float] = None
    arr_low: Optional[float] = None
    arr_high: Optional[float] = None
    confidence: Confidence = Confidence.INSUFFICIENT
    arr_derived: bool = False
    calculation: str = ""
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    independent_indicators: int = 0
    source_urls: list[str] = Field(default_factory=list)

    @property
    def mrr_mid(self) -> Optional[float]:
        if self.mrr_low is None or self.mrr_high is None:
            return None
        return (self.mrr_low * self.mrr_high) ** 0.5 if self.mrr_low > 0 else self.mrr_high / 2


class Contact(BaseModel):
    name: str
    title: str
    linkedin_url: str = ""
    email: str = ""
    email_status: str = "Not publicly verified"
    source_url: str = ""
    confidence: Literal["High", "Medium", "Low"] = "Low"


class ComponentScore(BaseModel):
    points: float
    max_points: float
    reason: str


class ScoreBreakdown(BaseModel):
    revenue: ComponentScore
    reddit_opportunity: ComponentScore
    product_market_fit: ComponentScore
    marketing_growth: ComponentScore
    funding: ComponentScore
    community_potential: ComponentScore

    @property
    def total(self) -> int:
        return int(round(sum(c.points for c in self.components())))

    def components(self) -> list[ComponentScore]:
        return [self.revenue, self.reddit_opportunity, self.product_market_fit,
                self.marketing_growth, self.funding, self.community_potential]

    @property
    def tier(self) -> str:
        t = self.total
        if t >= 80:
            return "Excellent prospect"
        if t >= 65:
            return "Strong prospect"
        if t >= 50:
            return "Potential prospect"
        return "Low priority"


class CompanyProfile(BaseModel):
    """A fully researched company, ready to qualify, store and report."""
    candidate: Candidate
    extraction: ResearchExtraction
    domain: str
    website: str
    all_domains: list[str] = Field(default_factory=list)
    sources: list[SourceDoc] = Field(default_factory=list)
    revenue: RevenueEstimate
    contacts: list[Contact] = Field(default_factory=list)
    scores: Optional[ScoreBreakdown] = None
    list_type: Literal["revenue", "funded", "rejected"] = "rejected"
    rejection_reason: str = ""
    reconsiderable: bool = True
    research_date: date
    validation_notes: list[str] = Field(default_factory=list)
    traffic_note: str = "Not publicly available"

    def source_url(self, source_id: Optional[str]) -> str:
        for s in self.sources:
            if s.id == source_id:
                return s.url
        return ""

    def signals_of(self, *types: str) -> list[Signal]:
        return [s for s in self.extraction.signals if s.signal_type in types]
