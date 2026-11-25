"""Offline fakes: HTTP, search, free feeds, LLM and email. No network, no keys, no real email."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from reddketing.config import load_settings
from reddketing.database.google_sheets import MemorySheets
from reddketing.models import CandidateExtraction, ExtractedCandidate, ResearchExtraction
from reddketing.monitoring.budget_tracker import BudgetTracker
from reddketing.pipeline import Services
from reddketing.providers.llm_provider import LLMError
from reddketing.providers.news_feeds import FeedItem
from reddketing.providers.search_provider import SearchProvider, SearchResult
from reddketing.utils.http import FetchResult


# ------------------------------------------------------------------ company fixtures (fictional)
def make_companies(n: int, prefix: str = "Testco") -> list[dict]:
    out = []
    for i in range(n):
        name = f"{prefix} {chr(65 + i % 26)}{i}"
        slug = re.sub(r"[^a-z0-9]", "", name.lower())
        out.append({"name": name, "domain": f"{slug}.example", "customers": 4000 + 500 * i, "price": 29,
                    "founder": f"Alex Founder{i}", "funded": False})
    return out


COMPANY_FILE_TLD = "example"  # .example is reserved (RFC 2606); tldextract treats it as unknown, so we patch below


def company_pages(c: dict) -> dict[str, str]:
    base = f"https://{c['domain']}"
    return {
        base: (f"<html><head><title>{c['name']} — the habit app people recommend</title></head><body>"
               f"<h1>{c['name']}</h1><p>Build better habits.</p><a href='/pricing'>Pricing</a>"
               f"<a href='/about'>About us</a><a href='/careers'>Careers</a></body></html>"),
        base + "/pricing": f"<html><title>Pricing</title><body>Free plan. Pro ${c['price']}/month. Team $79/month.</body></html>",
        base + "/about": (f"<html><title>About</title><body>{c['name']} was founded by {c['founder']}, CEO. "
                          f"We serve {c['customers']:,} paying customers. Contact hello@{c['domain']}. "
                          f"<a href='https://www.linkedin.com/in/{c['founder'].lower().replace(' ', '-')}'>LinkedIn</a>"
                          f"</body></html>"),
        base + "/careers": "<html><title>Careers</title><body>We are hiring a Growth Marketing Manager.</body></html>",
    }


class FakeHttp:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.requests_made = 0

    def get_text(self, url, use_cache=True):
        self.requests_made += 1
        url = url.rstrip("/")
        if url in self.pages:
            return FetchResult(url, url, 200, self.pages[url])
        return FetchResult(url, url, 404, "", "HTTP 404")


class FakeSearch(SearchProvider):
    name = "brave"

    def __init__(self, settings, budget, tmp, results=None, fail=False):
        super().__init__(settings, budget, tmp)
        self.results = results or {}
        self.fail = fail

    @property
    def available(self):
        return True

    def _raw_search(self, query, *, freshness, news):
        from reddketing.providers.search_provider import SearchError
        if self.fail:
            raise SearchError("Brave HTTP 503")
        for key, res in self.results.items():
            if key in query:
                return res
        return []


class FakeFree:
    def __init__(self, funding_items=None, launch_items=None):
        self.funding_items = funding_items or []
        self.launch_items = launch_items or []
        self.errors = []
        self.requests_made = 0

    def rss(self, url, name, kind, max_age_days):
        return self.funding_items if kind == "funding" and "techcrunch.com/category/venture" in url else []

    def google_news(self, query, days=30, kind="funding"):
        return []

    def hacker_news_launches(self, min_points, days=14):
        return self.launch_items

    def product_hunt(self, days=7):
        return []


def parse_sources(prompt: str) -> dict[str, str]:
    """url -> source_id from the rendered research prompt."""
    out = {}
    for m in re.finditer(r"<untrusted_source (\{.*?\})>", prompt):
        meta = json.loads(m.group(1))
        if "url" in meta:
            out[meta["url"]] = meta["source_id"]
    return out


class FakeLLM:
    """Deterministic stand-in for the LLM. Behaviour is driven by the company registry."""

    def __init__(self, companies: list[dict], budget: BudgetTracker | None = None):
        self.by_name = {c["name"]: c for c in companies}
        self.calls = 0
        self.errors: list[str] = []
        self.budget = budget
        self.fail_for: set[str] = set()

    def complete_json(self, system, user, output_model, cache=True):
        self.calls += 1
        if self.budget:
            self.budget.require_llm()
            self.budget.record_llm("claude-haiku-5-5", 3000, 800)
        if output_model is CandidateExtraction:
            items = re.findall(r'\{"item_id": "(I\d+)", "title": "(.*?)", "url": "(.*?)"', user)
            cands = []
            for item_id, title, url in items:
                name = title.split(" — ")[0].split(" raises")[0]
                if name in self.by_name:
                    c = self.by_name[name]
                    cands.append(ExtractedCandidate(name=name, website=f"https://{c['domain']}", item_ids=[item_id],
                                                    why_relevant="test", is_funding_announcement=c["funded"],
                                                    funding_round="Seed" if c["funded"] else None,
                                                    funding_amount_usd=3_000_000 if c["funded"] else None,
                                                    announcement_date=c.get("funding_date")))
            return CandidateExtraction(candidates=cands)
        name = re.search(r"Company: (.+)", user).group(1).strip()
        if name in self.fail_for:
            raise LLMError("simulated LLM outage")
        c = self.by_name[name]
        ids = parse_sources(user)
        base = f"https://{c['domain']}"
        about = ids.get(base + "/about", "S1")
        pricing = ids.get(base + "/pricing", "S1")
        careers = ids.get(base + "/careers")
        enterprise = c.get("enterprise", False)
        data = {
            "company_name": c["name"], "aliases": [], "parent_company": c.get("parent"),
            "official_website_confirmed": True,
            "one_line_description": "Habit-tracking app for individuals" if not enterprise else "ERP for manufacturers",
            "product_category": "Productivity app" if not enterprise else "ERP",
            "industry": "Consumer software" if not enterprise else "Enterprise software",
            "business_model": "saas_subscription",
            "audience_type": "enterprise_only" if enterprise else "prosumer",
            "headquarters": "Austin, USA", "country": "USA", "founded_year": 2020,
            "pricing": [{"plan_name": "Pro", "price_usd_per_month": c["price"], "billing_note": "", "source_id": pricing},
                        {"plan_name": "Team", "price_usd_per_month": 79, "billing_note": "", "source_id": pricing}],
            "signals": ([] if c.get("no_signals") else [
                {"signal_type": "paying_customers", "value_text": f"{c['customers']:,} paying customers",
                 "numeric_value": c["customers"], "as_of": "", "claim_type": "company_reported", "source_id": about},
                {"signal_type": "hiring_marketing", "value_text": "Hiring a Growth Marketing Manager",
                 "numeric_value": None, "as_of": "", "claim_type": "company_reported", "source_id": careers or about},
            ]) + c.get("extra_signals", []),
            "revenue_inputs": {"model_type": "saas_subscription", "assumptions": []},
            "funding": ({"latest_round": "Seed", "latest_amount_usd": 3_000_000, "latest_date": c.get("funding_date"),
                         "lead_investors": ["Example Ventures"], "total_funding_usd": 3_000_000, "source_id": about}
                        if c["funded"] else {}),
            "people": [{"name": c["founder"], "title": "Founder & CEO",
                        "linkedin_url": f"https://www.linkedin.com/in/{c['founder'].lower().replace(' ', '-')}",
                        "email": c.get("person_email"), "source_id": about},
                       {"name": "Imaginary Person", "title": "CMO", "linkedin_url": None, "email": None,
                        "source_id": about}],
            "reddit": ({"understandable_to_redditors": 1, "community_participation": 1, "recommendation_driven": 1,
                        "acquisition_challenge": 1, "active_marketing": 1, "consumer_or_prosumer": 0,
                        "naturally_discussed": 1, "subreddits": [], "explanation": "Enterprise buyers.",
                        "relevant_audience": "CFOs"} if enterprise else
                       {"understandable_to_redditors": 5, "community_participation": 4, "recommendation_driven": 5,
                        "acquisition_challenge": 4, "active_marketing": 4, "consumer_or_prosumer": 5,
                        "naturally_discussed": 4, "subreddits": [{"name": "r/getdisciplined", "rationale": "habits",
                                                                  "source_id": None}],
                        "explanation": "Habit apps are compared and recommended constantly on Reddit.",
                        "relevant_audience": "Self-improvement enthusiasts"}),
            "hiring_growth_roles": bool(careers), "hiring_evidence_source_id": careers,
            "exclusion": {"excluded": enterprise, "reason": "pure_enterprise" if enterprise else "none",
                          "explanation": "Enterprise procurement only" if enterprise else ""},
            "discrepancies": [], "research_notes": "fake",
        }
        return ResearchExtraction.model_validate(data)


class FakeSender:
    def __init__(self, fail_times: int = 0):
        self.sent: list[dict] = []
        self.fail_times = fail_times

    def send(self, recipient, subject, html, text):
        from reddketing.reporting.gmail_client import EmailError
        if self.fail_times > 0:
            self.fail_times -= 1
            raise EmailError("simulated Gmail outage")
        self.sent.append({"to": recipient, "subject": subject, "html": html, "text": text})
        return f"msg-{len(self.sent)}"


# ------------------------------------------------------------------ fixtures
@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("REPORT_RECIPIENT", "recipient@test.invalid")
    monkeypatch.setenv("REDDKETING_CACHE_DIR", str(tmp_path / "cache"))
    # Treat the reserved ".example" TLD as a real suffix for tests.
    import reddketing.utils.normalize as norm
    import tldextract
    monkeypatch.setattr(norm, "_EXTRACT", tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True,
                                                               extra_suffixes=["example"]))


@pytest.fixture
def settings(tmp_path):
    s = load_settings(load_env_file=False)
    s.cache_dir = tmp_path / "cache"
    return s


def build_world(settings, tmp_path, companies, *, launch=True, sender=None, sheets=None, budget_before=0.0):
    pages = {}
    for c in companies:
        pages.update(company_pages(c))
    funding_items = [FeedItem(f"{c['name']} raises $3M seed round", f"https://techcrunch.com/{i}", "",
                              c.get("funding_date") or "", "TechCrunch Venture", "funding")
                     for i, c in enumerate(companies) if c["funded"]]
    launch_items = [FeedItem(f"{c['name']} — habit app", f"https://{c['domain']}", "200 points", "", "Hacker News Show HN",
                             "launch") for c in companies if not c["funded"]] if launch else []
    budget = BudgetTracker(settings, budget_before)
    llm = FakeLLM(companies, budget)
    sender = sender or FakeSender()
    svc = Services(settings=settings, sheets=sheets or MemorySheets(), budget=budget, http=FakeHttp(pages),
                   search=FakeSearch(settings, budget, tmp_path / "cache"), free=FakeFree(funding_items, launch_items),
                   llm_factory=lambda: llm, sender_factory=lambda: sender)
    return svc, llm, sender
