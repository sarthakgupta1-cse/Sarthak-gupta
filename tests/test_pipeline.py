from conftest import FakeClient, FakeResponse

from founder_agent.pipeline import Pipeline

TEAM_HTML = """
<html><head><title>Acme | Team</title></head><body>
<h3>Ada Lovelace</h3><p>Co-Founder &amp; CEO</p>
<p>ada@acme.io — <a href="https://t.me/ada_founder">Telegram</a></p>
<a href="https://www.linkedin.com/in/adalovelace">in</a>
</body></html>
"""

HN_STORY = {
    "objectID": "999", "author": "ada", "created_at": "2026-09-01T00:00:00.000Z",
    "created_at_i": 1788220800,
    "title": "Launch HN: Acme (YC W24) – SaaS for developer tools",
    "url": "https://acme.io", "story_text": "ada@acme.io",
}


def _client():
    return FakeClient({
        "search_by_date": FakeResponse(json_data={"hits": [HN_STORY]}),
        "users/ada": FakeResponse(json_data={"about": "Founder"}),
        "acme.io/about": FakeResponse(text=TEAM_HTML),
        "acme.io": FakeResponse(text=TEAM_HTML),
        "api.github.com": FakeResponse(json_data={"items": []}),
    })


async def test_end_to_end_merges_sources_into_one_lead(settings, tmp_path):
    settings.output = {"sink": "csv", "csv_path": str(tmp_path / "out.csv")}
    report = await Pipeline(settings).run(
        limit=5, domains=["acme.io"], client=_client()
    )
    # HN and the website crawl describe the same founder; they must collapse.
    adas = [lead for lead in report.leads if lead.email == "ada@acme.io"]
    assert len(adas) == 1
    ada = adas[0]
    assert ada.full_name == "Ada Lovelace"
    assert ada.telegram_handle == "ada_founder"
    assert ada.linkedin_url.endswith("/in/adalovelace")
    assert ada.company_domain == "acme.io"


async def test_dry_run_writes_nothing(settings, tmp_path):
    csv_path = tmp_path / "out.csv"
    settings.output = {"sink": "csv", "csv_path": str(csv_path)}
    report = await Pipeline(settings).run(
        limit=5, domains=["acme.io"], dry_run=True, client=_client()
    )
    assert report.written == 0
    assert not csv_path.exists()
    assert report.leads


async def test_suppressed_leads_are_never_written(settings, tmp_path, monkeypatch):
    monkeypatch.setattr("founder_agent.pipeline.load_suppression", lambda: {"acme.io"})
    settings.output = {"sink": "csv", "csv_path": str(tmp_path / "out.csv")}
    report = await Pipeline(settings).run(limit=5, domains=["acme.io"], client=_client())
    assert report.suppressed > 0
    assert all(lead.company_domain != "acme.io" for lead in report.leads)


async def test_report_counts_contactable_leads(settings, tmp_path):
    settings.output = {"sink": "csv", "csv_path": str(tmp_path / "out.csv")}
    report = await Pipeline(settings).run(limit=5, domains=["acme.io"], client=_client())
    assert report.contactable >= 1
    assert report.written == len(report.leads)
