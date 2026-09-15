from pathlib import Path

from founder_agent.discovery.website import WebsiteSource

FIXTURE = (Path(__file__).parent / "fixtures" / "team_page.html").read_text()


def _parse(settings):
    source = WebsiteSource(settings, client=None)
    return source._people_from_page(FIXTURE, "https://acmeanalytics.com/about", "acmeanalytics.com")


def test_extracts_only_founders_not_every_employee(settings):
    people = _parse(settings)
    names = {p.full_name for p in people}
    assert "Ada Lovelace" in names
    assert "Grace Hopper" in names
    # A junior support agent is not a founder and must not be picked up.
    assert "Bob Ordinary" not in names


def test_ignores_headings_that_are_not_people(settings):
    names = {p.full_name for p in _parse(settings)}
    assert "Our Team" not in names
    assert "Privacy Policy" not in names


def test_pulls_personal_email_and_telegram(settings):
    ada = next(p for p in _parse(settings) if p.full_name == "Ada Lovelace")
    assert ada.email == "ada@acmeanalytics.com"
    assert ada.telegram_handle == "adalovelace"
    assert ada.linkedin_url.endswith("/in/adalovelace")
    assert ada.role.lower().startswith("co-founder")


def test_company_and_provenance_recorded(settings):
    ada = next(p for p in _parse(settings) if p.full_name == "Ada Lovelace")
    assert ada.company == "Acme Analytics"
    assert ada.company_domain == "acmeanalytics.com"
    assert ada.source_url == "https://acmeanalytics.com/about"


def test_falls_back_to_page_email_when_no_personal_one(settings):
    grace = next(p for p in _parse(settings) if p.full_name == "Grace Hopper")
    # Grace has no personal address on the card, so the page-level one is used,
    # and the pipeline will later penalise it as a role address.
    assert grace.email.endswith("@acmeanalytics.com")
    assert grace.github_username == "ghopper"
