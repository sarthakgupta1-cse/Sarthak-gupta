from jobagent.config import load_settings
from jobagent.models import RawJob
from jobagent.salary import FALLBACK_RATES, FX, evaluate_salary, extract_from_text

CFG = load_settings()["salary"]
FXR = FX(FALLBACK_RATES, "test", "test")


def job(**kw):
    base = dict(source="Test", source_url="u", company="Acme", title="Writer")
    base.update(kw)
    return RawJob(**base)


def test_extract_variants():
    p = extract_from_text("Salary: $800 - $1,000 per month")[0]
    assert (p.amount, p.amount_max, p.currency, p.period) == (800, 1000, "USD", "monthly")
    assert extract_from_text("₹6-8 LPA")[0].amount == 600000
    assert extract_from_text("We raised $20 million") == []
    assert extract_from_text("$25/hr")[0].period == "hourly"
    p = extract_from_text("Salary : $1,800–$2,000 AUD per month")[0]
    assert (p.currency, p.period, p.amount) == ("AUD", "monthly", 1800)


def test_usd_monthly_ok():
    r = evaluate_salary(job(description="Pay: $700 per month, full-time"), FXR, CFG, True)
    assert r["verdict"] == "ok" and round(r["monthly_usd"]) == 700


def test_below_minimum_rejected():
    r = evaluate_salary(job(description="Pay: $300 per month"), FXR, CFG, True)
    assert r["verdict"] == "reject" and r["bucket"] == "salary"


def test_inr_threshold():
    assert evaluate_salary(job(description="Salary ₹45,000 per month"), FXR, CFG, True)["verdict"] == "reject"
    assert evaluate_salary(job(description="Salary ₹55,000 per month"), FXR, CFG, True)["verdict"] == "ok"
    assert evaluate_salary(job(description="CTC ₹6-8 LPA"), FXR, CFG, True)["verdict"] == "ok"   # 50k/month


def test_undisclosed_is_unclear():
    r = evaluate_salary(job(description="Competitive pay"), FXR, CFG, True)
    assert r["verdict"] == "unclear" and "not disclosed" in r["reason"]


def test_no_frequency_is_unclear():
    r = evaluate_salary(job(description="Salary: $40,000"), FXR, CFG, True)
    assert r["verdict"] == "unclear"


def test_ote_is_unclear():
    r = evaluate_salary(job(description="OTE $60,000 per year including commission"), FXR, CFG, True)
    assert r["verdict"] == "unclear"


def test_hourly_needs_full_time():
    assert evaluate_salary(job(description="$10 per hour"), FXR, CFG, False)["verdict"] == "unclear"
    assert evaluate_salary(job(description="$10 per hour"), FXR, CFG, True)["verdict"] == "ok"


def test_structured_annual_eur():
    r = evaluate_salary(job(salary_min=27000, salary_max=31000, salary_currency="EUR", salary_period="annual"), FXR, CFG, True)
    assert r["verdict"] == "ok" and r["monthly_usd"] > 2000


def test_remoteok_structured_ignored_without_text():
    r = evaluate_salary(job(source="Remote OK", salary_min=60000, salary_currency="USD", salary_period="annual"), FXR, CFG, True)
    assert r["verdict"] == "unclear"
