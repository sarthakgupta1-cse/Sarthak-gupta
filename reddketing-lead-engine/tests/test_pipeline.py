"""End-to-end pipeline tests (TESTS 1, 5, 7, 8, 12, 13, 14 of the spec) on mock data."""
from __future__ import annotations

from datetime import date, timedelta

from reddketing.database import schema
from reddketing.database.google_sheets import MemorySheets
from reddketing.pipeline import run_pipeline

from conftest import FakeSender, build_world, make_companies

D1 = date(2026, 11, 20)


def test_1_fifteen_companies_researched_and_reported(settings, tmp_path):
    companies = make_companies(20)
    svc, llm, sender = build_world(settings, tmp_path, companies)
    res = run_pipeline(svc, run_date=D1)
    assert res.status == "success", res.message
    assert res.revenue_count == 15                     # quota respected
    daily = svc.sheets.read_records(schema.DAILY)
    assert len(daily) == 15
    # overflow is deferred (recorded, reconsiderable tomorrow), not lost and not emailed
    deferred = [r for r in svc.sheets.read_records(schema.REJECTED) if "quota" in r["Reason for Rejection"]]
    assert len(deferred) == 5 and all(r["Can Be Reconsidered"] == "Yes" for r in deferred)
    assert len(sender.sent) == 1
    mail = sender.sent[0]
    assert mail["subject"] == "Reddketing Daily Lead Intelligence Report - 2026-11-20"
    for section in ("1. Daily summary", "2. New revenue-qualified", "3. Recently funded", "4. Top opportunities",
                    "5. Research notes", "6. Database"):
        assert section in mail["html"]
    assert "Imaginary Person" not in mail["html"]      # ungrounded person never reaches the email
    run_log = svc.sheets.read_records(schema.RUN_LOG)
    assert run_log[-1]["Status"] == "success" and run_log[-1]["Email Delivery Status"].startswith("sent")


def test_5_13_company_never_emailed_twice_across_runs(settings, tmp_path):
    companies = make_companies(6)
    sheets = MemorySheets()
    svc, _, sender = build_world(settings, tmp_path, companies, sheets=sheets)
    assert run_pipeline(svc, run_date=D1).status == "success"
    first = {r["Company Name"] for r in sheets.read_records(schema.DAILY)}
    assert len(first) == 6

    svc2, _, sender2 = build_world(settings, tmp_path, companies, sheets=sheets)
    res2 = run_pipeline(svc2, run_date=D1 + timedelta(days=1))
    assert res2.status == "success"
    assert res2.revenue_count == 0
    assert res2.duplicates == 6
    dups = [r for r in sheets.read_records(schema.DUPLICATES) if r["Detection Date"] == "2026-11-21"]
    assert {r["Newly Discovered Company"] for r in dups} == first
    for name in first:  # previously emailed companies never appear in the lead sections again
        section2 = sender2.sent[0]["html"].split("3. Recently funded")[0]
        assert name not in section2


def test_13_final_check_blocks_previously_emailed_row(settings, tmp_path):
    from reddketing.pipeline import build_report_from_sheets
    sheets = MemorySheets()
    sheets.ensure_schema()
    sheets.append_rows(schema.MASTER, [{"Company Key": "dup.example", "Company Name": "Dup", "Emailed Date": "2026-11-01"}])
    sheets.append_rows(schema.DAILY, [{"Record ID": "x", "Discovery Date": "2026-11-20", "Company Name": "Dup",
                                       "Official Domain": "dup.example", "Total Opportunity Score": 70}])
    data, blocked = build_report_from_sheets(sheets, "2026-11-20")
    assert data.revenue_rows == [] and blocked == ["Dup"]


def test_7_funded_companies_kept_separate(settings, tmp_path):
    companies = make_companies(4)
    for c in companies[:2]:
        c.update(funded=True, no_signals=True, funding_date=(D1 - timedelta(days=30)).isoformat())
    companies[2].update(funded=True, no_signals=True, funding_date=(D1 - timedelta(days=400)).isoformat())
    svc, _, sender = build_world(settings, tmp_path, companies)
    res = run_pipeline(svc, run_date=D1)
    assert res.status == "success"
    funded = {r["Company Name"] for r in svc.sheets.read_records(schema.FUNDED)}
    daily = {r["Company Name"] for r in svc.sheets.read_records(schema.DAILY)}
    assert funded == {companies[0]["name"], companies[1]["name"]}
    # Old funding does not make a company "recently funded"; it fills the revenue list as an assumed lead.
    assert daily == {companies[2]["name"], companies[3]["name"]}
    assert not funded & daily
    stale = next(r for r in svc.sheets.read_records(schema.DAILY) if r["Company Name"] == companies[2]["name"])
    assert stale["Revenue Confidence"] == "Assumed" and "Assumed at least $50,000" in stale["Revenue Calculation"]
    row = next(r for r in svc.sheets.read_records(schema.FUNDED))
    assert row["Revenue Confidence"] == "Insufficient"
    assert "Funding does not imply revenue" in sender.sent[0]["html"]


def test_8_sheets_rows_complete_and_idempotent(settings, tmp_path):
    companies = make_companies(3)
    svc, _, _ = build_world(settings, tmp_path, companies)
    run_pipeline(svc, run_date=D1)
    for tab in schema.TAB_ORDER:
        assert svc.sheets.tabs[tab][0] == schema.COLUMNS[tab]
    master = svc.sheets.read_records(schema.MASTER)
    assert len(master) == 3 and all(r["Emailed Date"] == "2026-11-20" for r in master)
    assert all(r["First Discovered Date"] == "2026-11-20" for r in master)
    from reddketing.pipeline import write_phase, ResearchOutcome
    before = {t: len(svc.sheets.tabs[t]) for t in schema.TAB_ORDER}
    write_phase(svc.sheets, ResearchOutcome(), "2026-11-20")
    assert {t: len(svc.sheets.tabs[t]) for t in schema.TAB_ORDER} == before


def test_12_partial_failure_email_then_recovery_without_reresearch(settings, tmp_path):
    companies = make_companies(5)
    sheets = MemorySheets()
    failing = FakeSender(fail_times=10)
    svc, llm, _ = build_world(settings, tmp_path, companies, sheets=sheets, sender=failing)
    res = run_pipeline(svc, run_date=D1)
    assert res.status == "failed"
    state = sheets.read_records(schema.RUN_STATE)[0]
    assert state["Stage"] == "sheets_written" and state["Status"] == "failed"
    assert len(sheets.read_records(schema.DAILY)) == 5
    log = sheets.read_records(schema.RUN_LOG)[-1]
    assert log["Status"] == "failed" and "not sent" in log["Email Delivery Status"]

    good = FakeSender()
    svc2, llm2, _ = build_world(settings, tmp_path, companies, sheets=sheets, sender=good)
    res2 = run_pipeline(svc2, run_date=D1)
    assert res2.status == "success"
    assert llm2.calls == 0                      # nothing re-researched
    assert len(sheets.read_records(schema.DAILY)) == 5   # nothing re-inserted
    assert len(good.sent) == 1 and res2.revenue_count == 5

    res3 = run_pipeline(svc2, run_date=D1)      # a third trigger the same day is a no-op
    assert res3.status == "already_completed" and len(good.sent) == 1


def test_12_sheets_failure_reports_failure_and_never_sends_success(settings, tmp_path):
    companies = make_companies(3)
    sheets = MemorySheets()
    svc, _, sender = build_world(settings, tmp_path, companies, sheets=sheets)
    sheets.ensure_schema()
    original = sheets.append_rows

    def flaky(tab, rows):
        if tab == schema.DAILY:
            from reddketing.database.google_sheets import SheetsError
            raise SheetsError("simulated 503")
        return original(tab, rows)
    sheets.append_rows = flaky
    res = run_pipeline(svc, run_date=D1)
    assert res.status == "failed"
    assert len(sender.sent) == 1 and "failed" in sender.sent[0]["subject"].lower()   # failure notice only

    sheets.append_rows = original
    svc2, llm2, sender2 = build_world(settings, tmp_path, companies, sheets=sheets)
    res2 = run_pipeline(svc2, run_date=D1)
    assert res2.status == "success" and res2.revenue_count == 3
    assert llm2.calls <= 2        # research reloaded from checkpoint; only discovery extraction (cached in prod)
    assert len({r["Company Key"] for r in sheets.read_records(schema.MASTER)}) == len(sheets.read_records(schema.MASTER))


def test_11_llm_failure_for_one_company_does_not_kill_run(settings, tmp_path):
    companies = make_companies(4)
    svc, llm, sender = build_world(settings, tmp_path, companies)
    llm.fail_for.add(companies[0]["name"])
    res = run_pipeline(svc, run_date=D1)
    assert res.status == "success" and res.revenue_count == 3
    rej = svc.sheets.read_records(schema.REJECTED)
    assert any("research failed" in r["Reason for Rejection"] and r["Can Be Reconsidered"] == "Yes" for r in rej)
    assert "simulated LLM outage" in sender.sent[0]["html"]


def test_14_budget_exhausted_skips_paid_research(settings, tmp_path):
    companies = make_companies(3)
    svc, llm, sender = build_world(settings, tmp_path, companies, budget_before=0)
    svc.sheets.ensure_schema()
    svc.sheets.append_rows(schema.RUN_LOG, [{"Run ID": "old", "Execution Date": "2026-11-05",
                                             "Estimated API Cost (USD)": settings.monthly_budget_usd + 1}])
    res = run_pipeline(svc, run_date=D1)
    assert res.status == "failed" and "budget" in res.message.lower()
    assert llm.calls == 0
    assert "failed" in sender.sent[0]["subject"].lower()


def test_concurrent_run_is_locked_out(settings, tmp_path):
    from reddketing.database.run_state import RunStateStore
    companies = make_companies(2)
    svc, llm, sender = build_world(settings, tmp_path, companies)
    svc.sheets.ensure_schema()
    other = RunStateStore(svc.sheets)
    other.owner = "another-runner"
    other.acquire("2026-11-20", "other")
    res = run_pipeline(svc, run_date=D1)
    assert res.status == "locked" and llm.calls == 0 and not sender.sent


def test_total_llm_outage_in_discovery_sends_failure_not_empty_report(settings, tmp_path):
    from reddketing.providers.llm_provider import LLMError
    svc, llm, sender = build_world(settings, tmp_path, make_companies(3))

    def down(*a, **k):
        raise LLMError("gemini HTTP 503 (retryable)")
    llm.complete_json = down
    res = run_pipeline(svc, run_date=D1)
    assert res.status == "failed" and "discovery" in res.message
    assert "failed" in sender.sent[0]["subject"].lower()


def test_llm_key_misconfiguration_stops_run_immediately(settings, tmp_path):
    from reddketing.providers.llm_provider import LLMConfigError
    svc, llm, sender = build_world(settings, tmp_path, make_companies(3))
    calls = []

    def bad_key(*a, **k):
        calls.append(1)
        raise LLMConfigError("anthropic: this API key is not scoped to a workspace")
    llm.complete_json = bad_key
    res = run_pipeline(svc, run_date=D1)
    assert res.status == "failed" and "workspace" in res.message and len(calls) == 1
    assert "failed" in sender.sent[0]["subject"].lower()


def test_research_stops_when_first_companies_all_fail(settings, tmp_path):
    companies = make_companies(6)
    svc, llm, sender = build_world(settings, tmp_path, companies)
    llm.fail_for.update(c["name"] for c in companies)
    res = run_pipeline(svc, run_date=D1)
    assert res.status == "failed" and "first 3 companies" in res.message
    assert "failed" in sender.sent[0]["subject"].lower()


def test_revenue_list_filled_to_target_with_assumed_companies(settings, tmp_path):
    companies = make_companies(6)
    for c in companies[2:]:
        c.update(no_signals=True)  # no public revenue evidence
    svc, _, sender = build_world(settings, tmp_path, companies)
    res = run_pipeline(svc, run_date=D1)
    rows = svc.sheets.read_records(schema.DAILY)
    assert res.status == "success" and len(rows) == 6
    assumed = [r for r in rows if r["Revenue Confidence"] == "Assumed"]
    assert len(assumed) == 4 and all(r["Estimated MRR Minimum"] in ("50000", 50000, "50000.0") for r in assumed)
    assert "assumed, not verified" in sender.sent[0]["html"]


def test_too_large_owned_and_below_floor_companies_are_not_leads(settings, tmp_path):
    companies = make_companies(5)
    companies[0].update(customers=150_000)                       # 150K paying customers: too large
    companies[1].update(parent="Microsoft")                     # product of a large company
    companies[2].update(customers=40)                           # own data: ~$1.2K-$3K MRR, below floor
    companies[3].update(no_signals=True, extra_signals=[        # "20k users" sent as 20: scaled, 10K+ rule
        {"signal_type": "total_users", "value_text": "Over 20k users", "numeric_value": 20,
         "as_of": "", "claim_type": "company_reported", "source_id": "S1"}])
    svc, _, sender = build_world(settings, tmp_path, companies)
    run_pipeline(svc, run_date=D1)
    daily = {r["Company Name"]: r for r in svc.sheets.read_records(schema.DAILY)}
    rejected = {r["Company Name"]: r["Reason for Rejection"] for r in svc.sheets.read_records(schema.REJECTED)}
    assert rejected[companies[0]["name"]].startswith("Too large: 150,000")
    assert rejected[companies[1]["name"]] == "Owned by Microsoft"
    assert rejected[companies[2]["name"]].startswith("Own data shows below $50,000")
    assumed = daily[companies[3]["name"]]
    assert assumed["Revenue Confidence"] == "Assumed" and "20,000 users" in assumed["Revenue Calculation"]
    assert companies[4]["name"] in daily


def test_scaled_value_fixes_unit_numbers():
    from reddketing.research.company_research import scaled_value
    assert scaled_value(2, "$2B in revenue") == 2e9
    assert scaled_value(1.5, "$1.5M ARR") == 1.5e6
    assert scaled_value(10, "10k users") == 10_000
    assert scaled_value(25000, "25,000 users") == 25000
    assert scaled_value(3, "3 plans") == 3


def test_heavy_funding_alone_does_not_exclude(settings):
    from types import SimpleNamespace
    from reddketing.models import Confidence
    from reddketing.qualification.scale_signals import size_exclusion
    p = SimpleNamespace(domain="newco.example", revenue=SimpleNamespace(mrr_mid=200_000, confidence=Confidence.MEDIUM),
                        extraction=SimpleNamespace(signals=[], parent_company=None,
                                                   funding=SimpleNamespace(total_funding_usd=400_000_000)))
    assert size_exclusion(p, settings) == ""


def test_add_more_keeps_todays_leads_and_adds_new_ones(settings, tmp_path):
    first, second = make_companies(3, "Alpha"), make_companies(3, "Beta")
    svc, _, sender = build_world(settings, tmp_path, first)
    assert run_pipeline(svc, run_date=D1).status == "success"
    svc2, llm2, sender2 = build_world(settings, tmp_path, first + second, sheets=svc.sheets)
    assert run_pipeline(svc2, run_date=D1).status == "already_completed"
    res = run_pipeline(svc2, run_date=D1, add_more=True)
    names = [r["Company Name"] for r in svc2.sheets.read_records(schema.DAILY)]
    assert res.status == "success" and len(names) == 6 and len(set(names)) == 6
    assert set(c["name"] for c in second) <= set(names)
    # The top-up email lists only the new leads; the earlier ones stay in the sheet.
    html = sender2.sent[-1]["html"]
    assert all(c["name"] in html for c in second) and not any(c["name"] in html for c in first)


def test_extra_pass_runs_when_under_target_and_adds_no_duplicates(settings, tmp_path):
    companies = make_companies(3)
    svc, _, sender = build_world(settings, tmp_path, companies)
    queries = []
    orig = svc.search._raw_search
    def spy(query, **k):
        queries.append(query)
        return orig(query, **k)
    svc.search._raw_search = spy
    res = run_pipeline(svc, run_date=D1)
    names = [r["Company Name"] for r in svc.sheets.read_records(schema.DAILY)]
    assert res.status == "success" and len(names) == len(set(names)) == 3
    assert len(queries) > int(settings.get("search.discovery_queries_per_run"))  # extra pass searched again


def test_enterprise_and_deep_tech_candidates_dropped_before_research(settings):
    from reddketing.discovery.startup_discovery import extract_candidates
    from reddketing.models import CandidateExtraction, ExtractedCandidate
    from reddketing.providers.news_feeds import FeedItem

    class LLM:
        def complete_json(self, *a, **k):
            return CandidateExtraction(candidates=[
                ExtractedCandidate(name="Brightloop", item_ids=["I0"], audience="consumer"),
                ExtractedCandidate(name="Kalepa", item_ids=["I1"], audience="enterprise_only"),
                ExtractedCandidate(name="Hypersonica", item_ids=["I2"], audience="deep_tech_or_hardware")])
    items = [FeedItem(f"{n} news", f"https://{n.lower()}.io", "", "", "news", "launch")
             for n in ("Brightloop", "Kalepa", "Hypersonica")]
    out = extract_candidates(LLM(), items, set())
    assert [c.name for c in out] == ["Brightloop"] and out[0].audience == "consumer"
