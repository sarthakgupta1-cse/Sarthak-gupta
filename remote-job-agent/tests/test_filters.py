from jobagent.config import load_settings
from jobagent.filters import OK, REJECT, UNCLEAR, check_employment, check_experience, check_location
from jobagent.models import RawJob
from jobagent.classify import category_for, title_is_relevant

EXP = load_settings()["experience"]


def job(**kw):
    base = dict(source="Test", source_url="https://x.test/1", company="Acme", title="Content Writer")
    base.update(kw)
    return RawJob(**base)


def test_categories():
    assert category_for("SEO Content Writer") == "SEO and Growth"
    assert category_for("Junior Copywriter") == "Content Writing"
    assert category_for("Social Media Executive") == "Social Media"
    assert category_for("Affiliate Marketing Manager") == "Affiliate Marketing"
    assert category_for("Email Marketing Specialist") == "Digital Marketing"
    assert category_for("Brand Marketing Associate") == "Other Marketing Roles"
    assert not title_is_relevant("Senior Software Engineer, Growth")
    assert not title_is_relevant("Account Executive")
    assert not title_is_relevant("Content Moderator")


def test_location_india_listed():
    v, *_ = check_location(job(locations=["India"], remote=True))
    assert v == OK


def test_location_worldwide_but_us_only_in_text():
    v, _, india, reason = check_location(job(location_text="Anywhere in the World",
                                             description="This role is remote but you must be based in the United States."))
    assert v == REJECT and india == "No"


def test_location_restricted_list():
    v, *_ = check_location(job(locations=["United States", "Canada"], remote=True))
    assert v == REJECT


def test_location_hybrid():
    v, *_ = check_location(job(location_text="Hybrid - Bengaluru"))
    assert v == REJECT


def test_location_unknown_is_unclear():
    v, *_ = check_location(job(location_text="", description="Join our remote team."))
    assert v == UNCLEAR


def test_location_authorized_to_work():
    v, *_ = check_location(job(location_text="Worldwide", description="Candidates must be authorized to work in the US."))
    assert v == REJECT


def test_employment():
    assert check_employment(job(employment_type="Full-Time"))[0] == OK
    assert check_employment(job(employment_type="Part-Time"))[0] == REJECT
    assert check_employment(job(title="Marketing Intern"))[0] == REJECT
    assert check_employment(job(employment_type="Freelance"))[0] == REJECT
    assert check_employment(job(employment_type="Contract"))[0] == UNCLEAR
    assert check_employment(job(employment_type="Full-time contractor"))[0] == OK
    assert check_employment(job(employment_type="Full-time", description="This is a commission-only role"))[0] == REJECT


def test_experience():
    assert check_experience(job(title="Senior Content Writer"), EXP)[0] == REJECT
    assert check_experience(job(description="1+ years of experience in writing"), EXP)[0] == OK
    assert check_experience(job(description="2+ years of experience. Freshers with strong samples welcome."), EXP)[0] == OK
    assert check_experience(job(description="2+ years of experience in content"), EXP)[0] == REJECT
    assert check_experience(job(description="5+ years of experience"), EXP)[0] == REJECT
    assert check_experience(job(title="Junior Copywriter"), EXP)[0] == OK
    assert check_experience(job(title="Social Media Manager"), EXP)[0] == UNCLEAR
    assert check_experience(job(description="Founded 10 years ago, we have experience..."), EXP)[0] == OK
