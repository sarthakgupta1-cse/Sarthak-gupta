import pytest
from conftest import FakeClient, FakeResponse

from founder_agent.discovery.hackernews import HackerNewsSource
from founder_agent.models import EmailStatus

STORY = {
    "objectID": "12345",
    "author": "adalove",
    "title": "Launch HN: Acme Analytics (YC W24) – SaaS billing for developer tools",
    "url": "https://acmeanalytics.com",
    "story_text": "We built this after years of pain. Email us at founders@acmeanalytics.com",
    "created_at": "2026-08-01T10:00:00.000Z",
    "created_at_i": 1785535200,
}

PROFILE = {
    "username": "adalove",
    "about": "Founder of Acme. telegram: @adalove_hn | https://twitter.com/adalove",
}


@pytest.fixture
def client():
    return FakeClient({
        "search_by_date": FakeResponse(json_data={"hits": [STORY]}),
        "users/adalove": FakeResponse(json_data=PROFILE),
    })


async def test_parses_company_from_launch_hn_title(settings, client):
    leads = await HackerNewsSource(settings, client).discover(limit=5)
    assert len(leads) == 1
    lead = leads[0]
    # The title suffix (YC batch, tagline) must be stripped off the company name.
    assert lead.company == "Acme Analytics"
    assert lead.company_domain == "acmeanalytics.com"


async def test_captures_published_email_and_socials(settings, client):
    lead = (await HackerNewsSource(settings, client).discover(limit=5))[0]
    assert lead.email == "founders@acmeanalytics.com"
    assert lead.email_status == EmailStatus.PUBLISHED
    assert lead.telegram_handle == "adalove_hn"
    assert lead.twitter_handle == "adalove"


async def test_records_provenance(settings, client):
    lead = (await HackerNewsSource(settings, client).discover(limit=5))[0]
    assert lead.source == "hackernews"
    assert "item?id=12345" in lead.source_url
    assert lead.launched_at.startswith("2026-08-01")


async def test_story_without_launch_prefix_is_skipped(settings):
    plain = dict(STORY, title="Ask HN: how do you price a SaaS?")
    client = FakeClient({"search_by_date": FakeResponse(json_data={"hits": [plain]})})
    assert await HackerNewsSource(settings, client).discover(limit=5) == []
