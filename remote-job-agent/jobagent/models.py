"""Data model shared by every stage of the pipeline."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

QUALIFIED = "qualified"
NEEDS_VERIFICATION = "needs_verification"
REJECTED = "rejected"


@dataclass
class RawJob:
    """A listing as one source reported it — nothing inferred yet."""

    source: str                       # e.g. "Himalayas", "Greenhouse: gitlab"
    source_url: str                   # where we saw it
    company: str
    title: str
    apply_url: str = ""               # best application link the source gave us
    company_website: str = ""
    external_id: str = ""             # source's own job id, when it has one
    is_official: bool = False         # True = employer's own career page / ATS
    location_text: str = ""           # free-text location ("Worldwide", "Remote - US")
    locations: list[str] = field(default_factory=list)   # structured allow-list, if any
    remote: Optional[bool] = None
    employment_type: str = ""         # as stated by the source
    seniority: list[str] = field(default_factory=list)
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = ""
    salary_period: str = ""           # annual | monthly | hourly | weekly | daily
    salary_text: str = ""             # free-text salary as the source wrote it
    description: str = ""             # plain text
    posted_at: str = ""               # ISO date
    tags: list[str] = field(default_factory=list)
    industry: str = ""
    recruiter: str = ""               # only when publicly stated on the posting — never inferred


@dataclass
class Evaluation:
    """What the filters concluded about a RawJob."""

    decision: str = REJECTED                  # qualified | needs_verification | rejected
    reasons: list[str] = field(default_factory=list)       # why rejected / unverified
    reject_bucket: str = ""                   # salary | location | experience | type | relevance | other
    category: str = ""                        # sheet tab name
    remote_eligibility: str = ""
    india_eligibility: str = ""               # Yes / No / Unclear (+ evidence)
    employment_type: str = ""
    experience: str = ""
    original_salary: str = ""
    currency: str = ""
    salary_frequency: str = ""
    monthly_usd: Optional[float] = None
    monthly_inr: Optional[float] = None
    fixed_salary_verified: str = ""
    commission: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class Job:
    raw: RawJob
    ev: Evaluation
    job_id: str = ""
    url_key: str = ""
    also_listed: list[str] = field(default_factory=list)
    original_url: str = ""            # employer-hosted posting, when we could find it

    def to_dict(self) -> dict:
        return {"job_id": self.job_id, "url_key": self.url_key, "also_listed": self.also_listed,
                "original_url": self.original_url, "raw": asdict(self.raw), "ev": asdict(self.ev)}

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        return cls(raw=RawJob(**d["raw"]), ev=Evaluation(**d["ev"]), job_id=d.get("job_id", ""),
                   url_key=d.get("url_key", ""), also_listed=d.get("also_listed", []),
                   original_url=d.get("original_url", ""))
