from founder_agent.models import EmailStatus, Lead, extract_emails, harvest_socials


def test_telegram_needs_context_for_bare_handle():
    """A bare @mention is not a Telegram handle unless Telegram is named nearby."""
    bare = Lead()
    harvest_socials("shout out to @someguy for the idea", bare)
    assert bare.telegram_handle == ""

    explicit = Lead()
    harvest_socials("ping me on Telegram: @someguy", explicit)
    assert explicit.telegram_handle == "someguy"

    link = Lead()
    harvest_socials("https://t.me/founderguy", link)
    assert link.telegram_handle == "founderguy"


def test_social_denylist_rejects_boilerplate_links():
    lead = Lead()
    harvest_socials('<a href="https://twitter.com/share?url=x">Share</a>', lead)
    assert lead.twitter_handle == ""


def test_verified_email_beats_guessed_on_merge():
    guessed = Lead(full_name="Ada", email="a@acme.io", email_status=EmailStatus.GUESSED)
    verified = Lead(email="ada@acme.io", email_status=EmailStatus.VERIFIED, email_source="hunter")
    guessed.merge(verified)
    assert guessed.email == "ada@acme.io"
    assert guessed.email_status == EmailStatus.VERIFIED


def test_merge_never_blanks_an_existing_value():
    full = Lead(full_name="Ada Lovelace", role="CEO", company="Acme")
    sparse = Lead(full_name="", role="", location="London")
    full.merge(sparse)
    assert full.full_name == "Ada Lovelace"
    assert full.role == "CEO"
    assert full.location == "London"


def test_dedupe_key_prefers_email_then_linkedin():
    assert Lead(email="A@Acme.io ").dedupe_key() == "email:a@acme.io"
    assert Lead(linkedin_url="https://linkedin.com/in/Ada/").dedupe_key() == "li:ada"
    assert Lead(full_name="Ada", company_domain="acme.io").dedupe_key().startswith("nc:")


def test_extract_emails_drops_asset_noise():
    text = "contact ada@acme.io, logo@2x.png, someone@example.com"
    assert extract_emails(text) == ["ada@acme.io"]
