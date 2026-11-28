"""Unit tests: revenue (TEST 2), Reddit scoring (3), contacts (4), dedupe (6), report (9),
email (10), API failures (11), budget (14)."""
from __future__ import annotations

from datetime import date

import httpx
import pytest

from reddketing.database.duplicate_detection import DuplicateIndex
from reddketing.models import (Candidate, CompanyProfile, Confidence, Person, ResearchExtraction, RevenueEstimate,
                               SourceDoc)
from reddketing.monitoring.budget_tracker import BudgetExceeded, BudgetTracker
from reddketing.qualification.opportunity_scoring import score_profile
from reddketing.research.contact_research import validate_people
from reddketing.research.revenue_estimator import estimate_revenue
from reddketing.utils.normalize import core_name, domain_label, normalize_name, root_domain

TODAY = date(2026, 11, 20)


def src(i, url, text, kind="company_page"):
    return SourceDoc(id=f"S{i}", url=url, title="t", kind=kind, text=text)


def extraction(**over) -> ResearchExtraction:
    base = {
        "company_name": "Acme", "official_website_confirmed": True, "one_line_description": "x",
        "product_category": "App", "industry": "Software", "business_model": "saas_subscription",
        "audience_type": "prosumer", "pricing": [], "signals": [], "revenue_inputs": {"model_type": "saas_subscription"},
        "reddit": {"understandable_to_redditors": 4, "community_participation": 4, "recommendation_driven": 4,
                   "acquisition_challenge": 3, "active_marketing": 3, "consumer_or_prosumer": 4,
                   "naturally_discussed": 4, "subreddits": [], "explanation": "fit"},
        "exclusion": {"excluded": False, "reason": "none"},
    }
    base.update(over)
    return ResearchExtraction.model_validate(base)


# ------------------------------------------------------------------ TEST 2: revenue + confidence
def test_disclosed_arr_is_high_confidence_and_labelled(settings):
    sources = [src(1, "https://acme.example/blog", "We crossed $1.2M ARR this year")]
    ex = extraction(signals=[{"signal_type": "arr_disclosed", "value_text": "$1.2M ARR", "numeric_value": 1_200_000,
                              "claim_type": "company_reported", "source_id": "S1"}])
    rev = estimate_revenue(ex, sources, settings)
    assert rev.confidence == Confidence.HIGH and rev.arr_derived
    assert rev.mrr_low == pytest.approx(90_000) and rev.mrr_high == pytest.approx(110_000)
    assert "ARR-derived" in rev.method


def test_snippet_only_disclosure_capped_at_medium(settings):
    sources = [src(1, "https://news.example/a", "Acme hits $2M in annual revenue", kind="search_snippet")]
    ex = extraction(signals=[{"signal_type": "revenue_disclosed", "value_text": "$2M annual revenue",
                              "numeric_value": 2_000_000, "claim_type": "verified_fact", "source_id": "S1"}])
    rev = estimate_revenue(ex, sources, settings)
    assert rev.confidence == Confidence.MEDIUM
    assert any("snippet" in a for a in rev.assumptions)


def test_saas_model_customers_times_arpu(settings):
    sources = [src(1, "https://acme.example/pricing", "Pro $20/month, Team $60/month"),
               src(2, "https://acme.example/about", "5,000 paying customers"),
               src(3, "https://press.example/x", "Acme has 40,000 users", kind="third_party_page")]
    ex = extraction(
        pricing=[{"plan_name": "Pro", "price_usd_per_month": 20, "source_id": "S1"},
                 {"plan_name": "Team", "price_usd_per_month": 60, "source_id": "S1"}],
        signals=[{"signal_type": "paying_customers", "value_text": "5,000 paying customers", "numeric_value": 5000,
                  "claim_type": "company_reported", "source_id": "S2"},
                 {"signal_type": "total_users", "value_text": "40,000 users", "numeric_value": 40000,
                  "claim_type": "third_party_estimate", "source_id": "S3"}])
    rev = estimate_revenue(ex, sources, settings)
    assert rev.mrr_low == pytest.approx(4500 * 20) and rev.mrr_high == pytest.approx(5250 * 60)
    assert rev.confidence == Confidence.MEDIUM
    assert "ARPU" in rev.calculation and rev.arr_low == pytest.approx(rev.mrr_low * 12)


def test_users_only_model_is_low_and_assumptions_written(settings):
    sources = [src(1, "https://acme.example/pricing", "Pro $10/month"),
               src(2, "https://acme.example", "Loved by 1,000,000 users")]
    ex = extraction(pricing=[{"plan_name": "Pro", "price_usd_per_month": 10, "source_id": "S1"}],
                    signals=[{"signal_type": "total_users", "value_text": "1,000,000 users", "numeric_value": 1e6,
                              "claim_type": "company_reported", "source_id": "S2"}])
    rev = estimate_revenue(ex, sources, settings)
    assert rev.confidence == Confidence.LOW
    assert any("active" in a and "pay" in a for a in rev.assumptions)


def test_ecommerce_and_marketplace_models(settings):
    sources = [src(1, "https://shop.example", "500,000 monthly visitors. Products from $40")]
    ex = extraction(business_model="ecommerce", revenue_inputs={"model_type": "ecommerce", "avg_order_value_low": 40,
                                                                 "avg_order_value_high": 60},
                    signals=[{"signal_type": "monthly_traffic", "value_text": "500,000 monthly visitors",
                              "numeric_value": 500000, "claim_type": "company_reported", "source_id": "S1"}])
    rev = estimate_revenue(ex, sources, settings)
    assert rev.mrr_low == pytest.approx(500000 * 0.01 * 40) and rev.mrr_high == pytest.approx(500000 * 0.03 * 60)
    ex2 = extraction(business_model="marketplace", revenue_inputs={"model_type": "marketplace",
                                                                    "monthly_gmv_low": 1e6, "monthly_gmv_high": 2e6})
    rev2 = estimate_revenue(ex2, sources, settings)
    assert rev2.mrr_low == pytest.approx(50_000) and "GMV is not revenue" in rev2.calculation


def test_no_inputs_means_insufficient_not_invented(settings):
    rev = estimate_revenue(extraction(), [src(1, "https://a.example", "hello")], settings)
    assert rev.confidence == Confidence.INSUFFICIENT and rev.mrr_low is None


def test_funding_never_counts_as_revenue(settings):
    sources = [src(1, "https://tc.example/a", "Acme raises $20M Series A", kind="third_party_page")]
    ex = extraction(signals=[{"signal_type": "funding", "value_text": "$20M Series A", "numeric_value": 2e7,
                              "claim_type": "verified_fact", "source_id": "S1"}])
    assert estimate_revenue(ex, sources, settings).mrr_low is None


def test_unverifiable_number_is_marked_unverified():
    from reddketing.research.company_research import validate_extraction
    sources = [src(1, "https://acme.example", "We have lots of customers")]
    ex = extraction(signals=[{"signal_type": "paying_customers", "value_text": "90,000 customers",
                              "numeric_value": 90000, "claim_type": "company_reported", "source_id": "S1"},
                             {"signal_type": "employees", "value_text": "50", "numeric_value": 50,
                              "claim_type": "company_reported", "source_id": "S9"}])
    notes = validate_extraction(ex, sources, "acme.example")
    assert len(ex.signals) == 1 and ex.signals[0].claim_type == "unverified"
    assert any("unknown sources" in n for n in notes)


# ------------------------------------------------------------------ TEST 3: Reddit scoring
def _profile(ex, rev=None):
    return CompanyProfile(candidate=Candidate(name=ex.company_name), extraction=ex, domain="acme.example",
                          website="https://acme.example", revenue=rev or RevenueEstimate(method="x"), research_date=TODAY)


def test_reddit_fit_outweighs_funding():
    consumer = extraction()
    enterprise = extraction(audience_type="enterprise_only", reddit={
        "understandable_to_redditors": 1, "community_participation": 0, "recommendation_driven": 1,
        "acquisition_challenge": 1, "active_marketing": 2, "consumer_or_prosumer": 0, "naturally_discussed": 0,
        "subreddits": [], "explanation": "procurement"},
        funding={"latest_round": "Series C", "latest_amount_usd": 1e8, "total_funding_usd": 1e8, "source_id": "S1"})
    s_cons = score_profile(_profile(consumer), TODAY)
    s_ent = score_profile(_profile(enterprise), TODAY)
    assert s_cons.total > s_ent.total
    assert s_ent.funding.points <= 10 and s_cons.reddit_opportunity.points > s_ent.reddit_opportunity.points
    # No revenue evidence and no pricing: a good Reddit fit alone stays below "Potential".
    assert s_cons.tier == "Low priority" and s_cons.reddit_opportunity.points == 19
    assert all(c.points <= c.max_points for c in s_cons.components())


def test_enterprise_only_excluded(settings):
    from reddketing.qualification.reddketing_fit import exclusion_reason
    ex = extraction(audience_type="enterprise_only", product_category="ERP", reddit={
        "understandable_to_redditors": 1, "community_participation": 0, "recommendation_driven": 0,
        "acquisition_challenge": 1, "active_marketing": 1, "consumer_or_prosumer": 0, "naturally_discussed": 0,
        "subreddits": [], "explanation": "x"})
    assert "Enterprise-only" in exclusion_reason(_profile(ex), settings)
    gamb = extraction(product_category="Online casino")
    assert "Restricted" in exclusion_reason(_profile(gamb), settings)
    assert exclusion_reason(_profile(extraction()), settings) == ""


# ------------------------------------------------------------------ TEST 4: decision-makers
def test_people_must_be_grounded():
    sources = [src(1, "https://acme.example/about",
                   "Founded by Jane Roe (CEO). Write to jane@acme.example. https://www.linkedin.com/in/janeroe")]
    people = [Person(name="Jane Roe", title="Founder & CEO", linkedin_url="https://linkedin.com/in/JaneRoe/",
                     email="jane@acme.example", source_id="S1"),
              Person(name="Ghost Writer", title="CMO", linkedin_url="https://linkedin.com/in/ghost",
                     email="ghost@acme.example", source_id="S1"),
              Person(name="Bob Smith", title="VP Marketing", source_id="S7")]
    contacts, notes = validate_people(people, sources, "acme.example")
    assert [c.name for c in contacts] == ["Jane Roe"]
    jane = contacts[0]
    assert jane.linkedin_url == "https://www.linkedin.com/in/janeroe"
    assert jane.email == "jane@acme.example" and jane.email_status.startswith("Publicly listed")
    assert jane.confidence == "High"


def test_guessed_email_not_kept():
    sources = [src(1, "https://acme.example/about", "Jane Roe is our CEO")]
    contacts, notes = validate_people([Person(name="Jane Roe", title="CEO", email="jane@acme.example",
                                              linkedin_url="https://linkedin.com/in/made-up", source_id="S1")],
                                      sources, "acme.example")
    assert contacts[0].email == "" and contacts[0].email_status == "Not publicly verified"
    assert contacts[0].linkedin_url == ""


# ------------------------------------------------------------------ TEST 6: duplicate detection
def test_domain_and_name_normalisation():
    assert normalize_name("Example AI, Inc.") == "exampleai"
    assert normalize_name("ExampleAI.com") == "exampleai"
    assert core_name("Example AI Labs") == "example"
    assert root_domain("https://www.app.example.co.uk/x?y") == "example.co.uk"
    assert domain_label("example.de") == "example"
    assert root_domain("https://cool-store.myshopify.com") == "cool-store.myshopify.com"


@pytest.fixture
def index():
    return DuplicateIndex.from_sheets([
        {"Company Name": "Example AI", "Official Domain": "exampleai.com", "All Domains": "exampleai.com\nexample-ai.io",
         "Aliases": "ExAI"},
        {"Company Name": "Brightwave", "Official Domain": "brightwave.com"},
        {"Company Name": "Cool Store", "Official Domain": "cool-store.myshopify.com"},
    ])


@pytest.mark.parametrize("name,domain,reason", [
    ("Something Else", "https://www.exampleai.com/pricing", "same root domain"),
    ("Example AI", "", "same normalised name"),
    ("ExampleAI.com", "", "same normalised name"),
    ("EXAMPLE ai", "", "same normalised name"),
    ("ExAI", "", "same normalised name"),
    ("Brightwave", "brightwave.de", "country/TLD variant"),
    ("New Name", "https://example-ai.io", "same root domain"),
    ("Exampleai", "exampleai.app", "country/TLD variant"),
])
def test_duplicate_detected(index, name, domain, reason):
    m = index.match(name, domain)
    assert m is not None and reason.split()[0] in m.reason


def test_parent_company_and_non_duplicates(index):
    m = index.match("Brightwave Studio", "bwstudio.com", parent="Brightwave")
    assert m is not None
    assert index.match("Other Store", "other-store.myshopify.com") is None   # private suffixes do not collide
    assert index.match("Totally New", "totallynew.com") is None


def test_redirect_domain_counts(index):
    assert index.match("Rebranded", "rebrand.com", extra_domains=["exampleai.com"]) is not None


# ------------------------------------------------------------------ TEST 9 + 10: report + email
def test_report_rendering_escapes_untrusted_text_and_has_text_fallback():
    from reddketing.reporting.report_generator import ReportData, render_daily_report
    row = {"Company Name": "<script>alert(1)</script>Evil", "Website": "https://evil.example",
           "Total Opportunity Score": 71, "Estimated MRR Minimum": 60000, "Estimated MRR Maximum": 90000,
           "Revenue Confidence": "Medium", "Revenue Evidence": "a\nb", "Primary Sources": "[official site] https://e"}
    html, text = render_daily_report(ReportData("2026-11-20", [row], [], sheet_url="https://sheet"), "Subj")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "$60K–$90K per month" in html and "$60K–$90K per month" in text
    assert "New leads at a glance" in html and "NEW LEADS AT A GLANCE" in text
    assert "6. DATABASE" in text and "https://sheet" in text


def test_email_message_is_multipart():
    from reddketing.reporting.gmail_client import build_message
    msg = build_message("sender@test.invalid", "to@test.invalid", "S", "<p>hi</p>", "hi")
    types = [p.get_content_type() for p in msg.iter_parts()]
    assert types == ["text/plain", "text/html"]


def test_gmail_api_sender_posts_raw_message(monkeypatch):
    from reddketing.reporting import gmail_client
    for k, v in {"GMAIL_CLIENT_ID": "id", "GMAIL_CLIENT_SECRET": "secret", "GMAIL_REFRESH_TOKEN": "tok",
                 "GMAIL_SENDER": "sender@test.invalid"}.items():
        monkeypatch.setenv(k, v)
    posted = {}

    class Resp:
        status_code = 200
        text = ""
        def json(self):
            return {"id": "abc123"}

    class Session:
        def post(self, url, json, timeout):
            posted.update(url=url, json=json)
            return Resp()
    sender = gmail_client.GmailApiSender()
    monkeypatch.setattr(sender, "_session", lambda: Session())
    assert sender.send("to@test.invalid", "S", "<p>x</p>", "x") == "abc123"
    assert posted["url"].endswith("/messages/send") and "raw" in posted["json"]


def test_missing_gmail_credentials_raise_clear_error(monkeypatch):
    from reddketing.reporting.gmail_client import EmailError, GmailApiSender
    for k in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "GMAIL_SENDER"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(EmailError):
        GmailApiSender()


# ------------------------------------------------------------------ TEST 11: API failures
def test_search_http_failures_are_contained(settings, tmp_path, monkeypatch):
    from reddketing.providers.search_provider import BraveSearch
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "k")
    monkeypatch.setattr("reddketing.providers.search_provider.backoff_sleep", lambda *a, **k: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503)
    budget = BudgetTracker(settings)
    s = BraveSearch(settings, budget, tmp_path, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert s.search("anything") == []
    assert calls["n"] == 3 and s.errors and budget.usage.search_queries == 0


def test_search_auth_error_not_retried(settings, tmp_path, monkeypatch):
    from reddketing.providers.search_provider import BraveSearch
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "k")
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401)
    s = BraveSearch(settings, BudgetTracker(settings), tmp_path, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert s.search("x") == [] and calls["n"] == 1


def test_search_success_is_cached_and_billed_once(settings, tmp_path, monkeypatch):
    from reddketing.providers.search_provider import BraveSearch
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "k")

    def handler(request):
        return httpx.Response(200, json={"web": {"results": [{"title": "T", "url": "https://a.example", "description": "d"}]}})
    budget = BudgetTracker(settings)
    s = BraveSearch(settings, budget, tmp_path, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert len(s.search("q")) == 1 and len(s.search("q")) == 1
    assert budget.usage.search_queries == 1 and budget.usage.search_cost == pytest.approx(0.005)


def test_llm_malformed_output_is_repaired(settings, tmp_path):
    from reddketing.models import CandidateExtraction
    from reddketing.providers.llm_provider import LLMProvider, LLMResponse

    class Flaky(LLMProvider):
        name = "fake"
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.n = 0
        def _call(self, system, user, schema):
            self.n += 1
            if self.n == 1:
                return LLMResponse("Sure! {not json", 100, 10)
            return LLMResponse('```json\n{"candidates": [{"name": "Acme"}]}\n```', 120, 20)
    budget = BudgetTracker(settings)
    p = Flaky("claude-haiku-5-5", budget, tmp_path)
    out = p.complete_json("sys", "user", CandidateExtraction)
    assert out.candidates[0].name == "Acme" and p.n == 2 and budget.usage.llm_calls == 2


def test_llm_hard_failure_raises(settings, tmp_path):
    from reddketing.models import CandidateExtraction
    from reddketing.providers.llm_provider import LLMError, LLMProvider

    class Down(LLMProvider):
        name = "fake"
        def _call(self, system, user, schema):
            raise LLMError("auth failed")
    with pytest.raises(LLMError):
        Down("m", BudgetTracker(settings), tmp_path).complete_json("s", "u", CandidateExtraction, cache=False)


def test_llm_switches_to_fallback_model_when_overloaded(settings, tmp_path, monkeypatch):
    from reddketing.models import CandidateExtraction
    from reddketing.providers import llm_provider as lp

    monkeypatch.setattr(lp, "backoff_sleep", lambda *a, **k: None)
    seen = []

    class Busy(lp.LLMProvider):
        name = "fake"
        def _call(self, system, user, schema):
            seen.append(self.model)
            if self.model == "main":
                raise lp.LLMError("fake HTTP 503 (retryable)")
            return lp.LLMResponse('{"candidates": [{"name": "Acme"}]}', 10, 5)

    p = Busy("main", BudgetTracker(settings), tmp_path, fallback_models=["backup"])
    out = p.complete_json("s", "u", CandidateExtraction, cache=False)
    assert out.candidates[0].name == "Acme" and seen == ["main", "main", "backup"]
    p.complete_json("s", "u2", CandidateExtraction, cache=False)
    assert seen[-1] == "backup"  # stays on the working model for the rest of the run


def test_strict_schema_is_self_contained():
    from reddketing.providers.llm_provider import strict_json_schema
    schema = strict_json_schema(ResearchExtraction)
    text = str(schema)
    assert "$ref" not in text and "$defs" not in schema
    assert schema["additionalProperties"] is False and set(schema["required"]) == set(schema["properties"])


# ------------------------------------------------------------------ TEST 14: budget
def test_budget_modes_and_caps(settings):
    budget_usd = settings.monthly_budget_usd
    assert BudgetTracker(settings, 0).mode == "normal"
    reduced = BudgetTracker(settings, budget_usd * 0.85)
    assert reduced.mode == "reduced" and reduced.max_queries == settings.get("budget.reduced_max_queries")
    assert reduced.max_candidates() == settings.get("budget.reduced_max_candidates")
    stopped = BudgetTracker(settings, budget_usd)
    assert stopped.mode == "stopped" and not stopped.search_allowed("brave") and not stopped.llm_allowed()
    with pytest.raises(BudgetExceeded):
        stopped.require_llm()


def test_run_caps_and_crossing_threshold_mid_run(settings):
    b = BudgetTracker(settings, settings.monthly_budget_usd - 0.004)
    assert b.search_allowed("brave")
    b.record_search("brave")           # $0.005 pushes the month over 100%
    assert b.mode == "stopped" and not b.search_allowed("brave")
    assert any("budget" in w.lower() for w in b.warnings)
    c = BudgetTracker(settings)
    for _ in range(c.max_queries):
        c.record_search("brave")
    assert not c.search_allowed("brave")
    assert not c.search_allowed("none")


def test_unknown_model_price_is_conservative(settings):
    b = BudgetTracker(settings)
    b.record_llm("mystery-model", 1_000_000, 0)
    assert b.usage.llm_cost == pytest.approx(1.0) and b.warnings


def test_query_plan_rotates_and_is_deterministic(settings):
    from reddketing.discovery.search_engine import plan_discovery_queries
    a = plan_discovery_queries(settings.categories, TODAY, 12)
    b = plan_discovery_queries(settings.categories, TODAY, 12)
    c = plan_discovery_queries(settings.categories, date(2026, 11, 21), 12)
    assert a == b and a != c and len(a) == 12


def test_secrets_redacted_in_logs(monkeypatch):
    from reddketing.monitoring.logger import redact
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secretvalue1234567890")
    assert "secretvalue" not in redact("calling with sk-ant-secretvalue1234567890")
    assert "AIza" not in redact("key=AIzaSyA1234567890abcdefghijklmnop")


def test_email_transport_auto_detects_smtp(monkeypatch):
    from reddketing.reporting.gmail_client import email_transport
    for k in ("EMAIL_TRANSPORT", "SMTP_APP_PASSWORD", "GMAIL_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert email_transport() == "gmail_api"
    monkeypatch.setenv("SMTP_APP_PASSWORD", "x")
    assert email_transport() == "smtp"
    monkeypatch.setenv("EMAIL_TRANSPORT", "gmail_api")
    assert email_transport() == "gmail_api"


def test_anthropic_schema_fits_union_limit_and_fallback_carries_schema(settings, tmp_path):
    import json as _json
    from reddketing.models import ResearchExtraction
    from reddketing.providers.llm_provider import optional_instead_of_nullable, schema_instruction, strict_json_schema

    schema = optional_instead_of_nullable(strict_json_schema(ResearchExtraction))
    text = _json.dumps(schema)
    assert text.count('"anyOf"') <= 16 and '"null"' not in text
    assert "company_name" in schema["required"] and "country" not in schema["required"]
    # An object with only the required fields still validates (nullable fields default to None).
    assert "official_website_confirmed" in schema_instruction(strict_json_schema(ResearchExtraction))


def test_sheet_layout_keeps_rows_one_line_and_freezes_name_column():
    from reddketing.database import schema
    from reddketing.database.layout import ROW_HEIGHT, all_layout_requests

    reqs = all_layout_requests({schema.DAILY: (0, 1000), schema.REJECTED: (3, 50)})
    clip = [r for r in reqs if "repeatCell" in r
            and r["repeatCell"]["cell"]["userEnteredFormat"].get("wrapStrategy") == "CLIP"]
    assert len(clip) == 2
    heights = [r["updateDimensionProperties"] for r in reqs if "updateDimensionProperties" in r
               and r["updateDimensionProperties"]["range"]["dimension"] == "ROWS"
               and r["updateDimensionProperties"]["range"]["startIndex"] == 1]
    assert {h["properties"]["pixelSize"] for h in heights} == {ROW_HEIGHT}
    frozen = {r["updateSheetProperties"]["properties"]["sheetId"]:
              r["updateSheetProperties"]["properties"]["gridProperties"]["frozenColumnCount"]
              for r in reqs if "updateSheetProperties" in r}
    assert frozen == {0: 3, 3: 2}  # through "Company Name" on each tab


def test_hobby_hosts_and_article_domains_are_not_company_sites():
    from reddketing.utils.normalize import is_hobby_host
    assert is_hobby_host("https://exitpath-ruddy.vercel.app") and is_hobby_host("onurgumus.github.io")
    assert not is_hobby_host("https://acme.com") and not is_hobby_host("shop.myshopify.com")


def test_discovery_does_not_use_news_article_domain_as_company_site(settings):
    from reddketing.discovery.startup_discovery import extract_candidates
    from reddketing.models import CandidateExtraction, ExtractedCandidate
    from reddketing.providers.news_feeds import FeedItem

    class LLM:
        def complete_json(self, *a, **k):
            return CandidateExtraction(candidates=[
                ExtractedCandidate(name="Dreamteam", website="https://www.pymnts.com/x", item_ids=["I0"]),
                ExtractedCandidate(name="Brightloop", item_ids=["I1"])])
    items = [FeedItem("Dreamteam raises $10M", "https://www.pymnts.com/x", "", "", "news", "funding"),
             FeedItem("Brightloop launches", "https://brightloop.io/launch", "", "", "hn", "launch")]
    out = {c.name: c.domain for c in extract_candidates(LLM(), items, set())}
    assert out == {"Dreamteam": "", "Brightloop": "brightloop.io"}


def test_guess_domain_tries_common_tlds_and_checks_the_page():
    from reddketing.discovery.candidate_filter import guess_domain
    from reddketing.models import Candidate
    from reddketing.utils.http import FetchResult

    class Http:
        def get_text(self, url, **k):
            if url == "https://brightloop.ai":
                return FetchResult(url, url, 200, "<html><title>Brightloop – habit app</title></html>")
            if url == "https://brightloop.com":
                return FetchResult(url, url, 200, "<html><title>Domain for sale</title></html>")
            return FetchResult(url, url, 404, "", "HTTP 404")
    c = Candidate(name="Brightloop")
    assert guess_domain(c, Http(), set()) and c.domain == "brightloop.ai"


def test_agencies_excluded_but_software_for_agencies_is_not(settings):
    from types import SimpleNamespace
    from reddketing.qualification.reddketing_fit import exclusion_reason

    def profile(category, industry, desc, reason="none"):
        ex = SimpleNamespace(exclusion=SimpleNamespace(excluded=reason != "none", reason=reason, explanation=""),
                             product_category=category, industry=industry, one_line_description=desc,
                             audience_type="smb_self_serve", reddit=SimpleNamespace(consumer_or_prosumer=3),
                             official_website_confirmed=True)
        return SimpleNamespace(extraction=ex)
    agency = profile("Game and software development services (agency / outsourced studio)", "Game development",
                     "Digital product development agency")
    assert exclusion_reason(agency, settings).startswith("Agency or service business")
    flagged = profile("Marketing", "Marketing", "Growth partner", reason="service_business")
    assert exclusion_reason(flagged, settings).startswith("Agency or service business")
    travel_sw = profile("Travel itinerary builder and travel agency operations software", "Travel technology",
                        "Itinerary software for travel advisors and agencies")
    assert exclusion_reason(travel_sw, settings) == ""


def test_email_summary_table_formats():
    from reddketing.reporting.report_generator import contact_summary, money, mrr_short, subreddits_short
    assert money(60000) == "$60K" and money(979200) == "$979K" and money(2625000) == "$2.6M" and money(5e6) == "$5M"
    assert mrr_short({"Estimated MRR Minimum": "50000", "Estimated MRR Maximum": "Not publicly available",
                      "Revenue Confidence": "Assumed"}) == "Assumed ≥ $50K"
    assert mrr_short({"Estimated MRR Minimum": "300000", "Estimated MRR Maximum": "366667",
                      "Revenue Confidence": "Medium"}) == "$300K–$367K (medium confidence)"
    assert subreddits_short({"Relevant Subreddits": "r/SaaS (audience fit, not source-verified); r/ObsidianMD"}) \
        == "r/SaaS, r/ObsidianMD"
    c = contact_summary({"Decision-Maker Designations": "Nirbhay Handa — CEO\nLee Smith — Co-Founder",
                         "LinkedIn URLs": "Nirbhay Handa: https://www.linkedin.com/in/nh",
                         "Public Business Email": "General: press@multipolitan.com (listed on https://x)"})
    assert c == {"person": "Nirbhay Handa, CEO", "linkedin": "https://www.linkedin.com/in/nh", "more": 1,
                 "email": "press@multipolitan.com"}


def test_too_well_known_flag_excludes(settings):
    from types import SimpleNamespace
    from reddketing.qualification.reddketing_fit import exclusion_reason
    ex = SimpleNamespace(exclusion=SimpleNamespace(excluded=True, reason="too_well_known", explanation="Category leader"),
                         product_category="AI code editor", industry="Developer tools", one_line_description="",
                         audience_type="developer", reddit=SimpleNamespace(consumer_or_prosumer=3),
                         official_website_confirmed=True)
    assert exclusion_reason(SimpleNamespace(extraction=ex), settings).startswith("Too large / already well known")
