from founder_agent.compliance import is_freemail, is_role_address, is_suppressed
from founder_agent.models import EmailStatus, Lead
from founder_agent.scoring import is_contactable, score_lead


def test_role_addresses_are_not_contactable():
    lead = Lead(email="info@acme.io", email_status=EmailStatus.VERIFIED)
    assert is_role_address(lead.email)
    assert not is_contactable(lead)


def test_only_verified_or_published_are_contactable():
    assert is_contactable(Lead(email="a@acme.io", email_status=EmailStatus.VERIFIED))
    assert is_contactable(Lead(email="a@acme.io", email_status=EmailStatus.PUBLISHED))
    # A guessed address must never receive cold mail — that is how domains burn.
    assert not is_contactable(Lead(email="a@acme.io", email_status=EmailStatus.GUESSED))
    assert not is_contactable(Lead(email="a@acme.io", email_status=EmailStatus.RISKY))
    assert not is_contactable(Lead())


def test_suppression_matches_email_and_whole_domain():
    suppression = {"ada@acme.io", "blocked.com"}
    assert is_suppressed(Lead(email="ada@acme.io"), suppression)
    assert is_suppressed(Lead(email="anyone@blocked.com"), suppression)
    assert is_suppressed(Lead(company_domain="blocked.com"), suppression)
    assert not is_suppressed(Lead(email="other@fine.com"), suppression)


def test_verified_founder_outscores_bare_record(settings):
    strong = Lead(
        full_name="Ada Lovelace", role="Co-Founder", company_domain="acme.io",
        email="ada@acme.io", email_status=EmailStatus.VERIFIED,
        linkedin_url="https://linkedin.com/in/ada", telegram_handle="ada",
    )
    weak = Lead(company="Acme")
    assert score_lead(strong, settings) > score_lead(weak, settings)
    assert score_lead(strong, settings) >= settings.scoring["min_score"]


def test_role_address_is_penalised(settings):
    person = Lead(full_name="Ada L", role="Founder", company_domain="acme.io",
                  email="ada@acme.io", email_status=EmailStatus.VERIFIED)
    generic = Lead(full_name="Ada L", role="Founder", company_domain="acme.io",
                   email="info@acme.io", email_status=EmailStatus.VERIFIED)
    assert score_lead(person, settings) > score_lead(generic, settings)


def test_freemail_detection():
    assert is_freemail("someone@gmail.com")
    assert not is_freemail("someone@acme.io")
