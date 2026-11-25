"""Salary extraction, conversion to monthly figures and the fixed-pay threshold.

Rules (see README):
* Only fixed base pay counts. OTE, commission, bonus and equity never count.
* The bottom of a range is the figure tested (conservative).
* No salary, no pay frequency, or OTE-only pay → Needs Verification. Nothing is guessed.
* Hourly pay is converted only for roles confirmed full-time (173.33 h/month).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date

log = logging.getLogger(__name__)

# Fallback only if the live FX API is unreachable. Units per 1 USD.
FALLBACK_RATES = {"USD": 1.0, "INR": 88.5, "EUR": 0.86, "GBP": 0.76, "CAD": 1.40, "AUD": 1.53,
                  "SGD": 1.30, "AED": 3.6725, "CHF": 0.80, "NZD": 1.75, "PHP": 58.0, "BRL": 5.4,
                  "MXN": 18.5, "PLN": 3.65, "SEK": 9.5, "NOK": 10.1, "DKK": 6.4, "JPY": 152.0, "ZAR": 17.5}


class FX:
    def __init__(self, rates: dict[str, float], as_of: str, source: str):
        self.rates, self.as_of, self.source = rates, as_of, source

    @classmethod
    def load(cls, http, url: str) -> "FX":
        try:
            d = http.json(url)
            if d.get("result") == "success" and d.get("rates"):
                as_of = (d.get("time_last_update_utc") or "")[5:16] or date.today().isoformat()
                return cls(d["rates"], as_of.strip(), "open.er-api.com")
        except Exception as exc:  # noqa: BLE001
            log.warning("FX fetch failed, using fallback table: %s", exc)
        return cls(FALLBACK_RATES, "fallback table 2026-11-25", "built-in fallback")

    def to_usd(self, amount: float, cur: str) -> float | None:
        r = self.rates.get(cur.upper())
        return amount / r if r else None

    def usd_to(self, amount_usd: float, cur: str) -> float | None:
        r = self.rates.get(cur.upper())
        return amount_usd * r if r else None


_CUR_TOKENS = [
    ("US$", "USD"), ("USD", "USD"), ("CA$", "CAD"), ("C$", "CAD"), ("CAD", "CAD"), ("A$", "AUD"), ("AU$", "AUD"),
    ("AUD", "AUD"), ("S$", "SGD"), ("SGD", "SGD"), ("NZ$", "NZD"), ("NZD", "NZD"), ("$", "USD"), ("₹", "INR"), ("INR", "INR"),
    ("Rs.", "INR"), ("Rs", "INR"), ("€", "EUR"), ("EUR", "EUR"), ("£", "GBP"), ("GBP", "GBP"), ("AED", "AED"),
    ("CHF", "CHF"), ("PHP", "PHP"), ("₱", "PHP"),
]
_CUR_RX = "|".join(re.escape(t) for t, _ in sorted(_CUR_TOKENS, key=lambda x: -len(x[0])))
_CUR_MAP = {t.lower(): c for t, c in _CUR_TOKENS}
_AMT = r"\d{1,3}(?:[,.\s]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_PER = (r"(?P<per>(?:/|per|an|a)\s*(?:hour|hr|month|mo|year|yr|annum|week|wk|day)\b|hourly|monthly|annually|"
        r"yearly|annual|weekly|daily|p\.?a\.?\b|pa\b|per annum|lpa\b)")
_MONEY = re.compile(
    rf"(?P<cur>{_CUR_RX})\s?(?P<a>{_AMT})\s?(?P<ka>[kK]|lakhs?|L\b)?"
    rf"(?:\s?(?:-|–|—|to)\s?(?:{_CUR_RX})?\s?(?P<b>{_AMT})\s?(?P<kb>[kK]|lakhs?|L\b)?)?"
    rf"(?:\s*(?P<cur2>USD|EUR|GBP|INR|CAD|AUD|SGD|NZD|AED|CHF|PHP)\b)?\s*(?:gross\s*)?{_PER}?",
    re.I)
_LPA = re.compile(r"(?P<a>\d+(?:\.\d+)?)\s*(?:-|–|to)?\s*(?P<b>\d+(?:\.\d+)?)?\s*(?:lpa|lakhs?\s*(?:per annum|p\.?a\.?|/\s*annum|ctc|per year)?)\b", re.I)
_NOT_PAY = re.compile(r"bonus|equity|stipend|budget|allowance|reimburs|revenue|raised|funding|\barr\b|valuation|"
                      r"million|billion|customers|users|grant|credit|learning|wellness|home office|per (?:article|word|post)|"
                      r"\bmrr\b|gmv|spend|ad spend|sales of|in sales|managing|manage(?:d)? (?:a )?budget|signing|referral", re.I)
_PER_BEFORE = re.compile(r"(hourly|monthly|annual|yearly|per annum|per month|per hour)", re.I)
_OTE = re.compile(r"\bOTE\b|on[- ]target earnings|including commission|incl\.? commission|with commission", re.I)
_BASE = re.compile(r"base (?:salary|pay|compensation)|fixed (?:salary|pay|compensation)", re.I)
_COMMISSION = re.compile(r"commission|incentive|performance bonus|revenue share", re.I)


@dataclass
class Pay:
    amount: float               # bottom of the range, in `currency`
    amount_max: float | None
    currency: str
    period: str                 # annual | monthly | hourly | weekly | daily | ""
    original: str               # as written
    evidence: str               # "structured field (Himalayas)" / "posting text"


def _to_float(s: str) -> float:
    s = s.strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):         # 50,000 / 50.000
        return float(re.sub(r"[.,]", "", s))
    return float(s.replace(",", ""))


def _period(tok: str | None) -> str:
    if not tok:
        return ""
    t = tok.lower()
    if "hour" in t or t.endswith("hr") or t == "hourly":
        return "hourly"
    if "month" in t or re.search(r"\bmo\b", t):
        return "monthly"
    if "week" in t or "wk" in t:
        return "weekly"
    if "day" in t or t == "daily":
        return "daily"
    if any(x in t for x in ("year", "yr", "annum", "annual", "p.a", "pa", "lpa")):
        return "annual"
    return ""


def extract_from_text(text: str) -> list[Pay]:
    out: list[Pay] = []
    if not text:
        return out
    for m in _MONEY.finditer(text):
        ctx = text[max(0, m.start() - 70): m.end() + 40]
        if _NOT_PAY.search(ctx):
            continue
        try:
            a = _to_float(m.group("a"))
            b = _to_float(m.group("b")) if m.group("b") else None
        except ValueError:
            continue
        mult_a = 1000 if (m.group("ka") or "").lower() == "k" else (100000 if (m.group("ka") or "").lower().startswith("l") else 1)
        mult_b = 1000 if (m.group("kb") or "").lower() == "k" else (100000 if (m.group("kb") or "").lower().startswith("l") else mult_a)
        a *= mult_a
        if b is not None:
            b *= mult_b
        cur = _CUR_MAP.get(m.group("cur").lower(), "USD")
        if m.group("cur2"):            # "$1,800 AUD": the trailing code is the real currency
            cur = m.group("cur2").upper()
        per = _period(m.group("per"))
        if not per:   # frequency is sometimes written just before: "Annual salary: $40,000"
            before = _PER_BEFORE.search(text[max(0, m.start() - 40): m.start()])
            per = _period(before.group(1)) if before else ""
        if re.search(r"lpa|lakh", m.group(0), re.I) and a < 1000:   # "₹6-8 LPA" = 6–8 lakh a year
            a *= 100000
            b = b * 100000 if b is not None and b < 1000 else b
        if a < 5:
            continue
        out.append(Pay(a, b, cur, per, m.group(0).strip(), "posting text"))
    for m in _LPA.finditer(text):
        ctx = text[max(0, m.start() - 70): m.end() + 40]
        if _NOT_PAY.search(ctx):
            continue
        a = float(m.group("a")) * 100000
        b = float(m.group("b")) * 100000 if m.group("b") else None
        out.append(Pay(a, b, "INR", "annual", m.group(0).strip(), "posting text"))
    seen, uniq = set(), []
    for p in out:                       # the same figure can match both patterns
        key = (round(p.amount), p.currency, p.period)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def monthly(amount: float, period: str, cfg: dict, full_time: bool) -> float | None:
    if period == "annual":
        return amount / 12
    if period == "monthly":
        return amount
    if period == "weekly":
        return amount * cfg.get("weeks_per_month", 4.33)
    if period == "daily":
        return amount * 21.67 if full_time else None
    if period == "hourly":
        return amount * cfg.get("hours_per_month", 173.33) if full_time else None
    return None


def _sane(usd_month: float) -> bool:
    return 50 <= usd_month <= 60000


def evaluate_salary(job, fx: FX, cfg: dict, full_time: bool) -> dict:
    """Return dict: verdict(ok|unclear|reject), fields for the sheet, reason."""
    desc = job.description or ""
    text_pays = extract_from_text(" ".join(filter(None, [job.salary_text, desc])))
    structured: Pay | None = None
    if job.salary_min and job.salary_currency:
        structured = Pay(float(job.salary_min), float(job.salary_max) if job.salary_max else None,
                         job.salary_currency.upper(), (job.salary_period or "").lower(),
                         _fmt_range(job.salary_min, job.salary_max, job.salary_currency, job.salary_period),
                         f"structured field ({job.source})")

    # Remote OK sometimes fills salary fields itself. Trust them only if the posting text agrees.
    if structured and job.source == "Remote OK" and not any(
            p.currency == structured.currency and abs(p.amount - structured.amount) / structured.amount < 0.15 for p in text_pays):
        structured = None
        remoteok_note = "Remote OK salary field not repeated in the posting, so it is ignored"
    else:
        remoteok_note = ""

    candidates = ([structured] if structured else []) + text_pays
    # An INR figure in the posting is the India-specific pay. Use it first.
    candidates.sort(key=lambda p: (p.currency != "INR", p.evidence != "posting text" if p.currency == "INR" else 0))
    commission_note = "Yes (mentioned)" if _COMMISSION.search(desc) else "Not mentioned"
    ote = bool(_OTE.search(desc)) and not _BASE.search(desc)

    out = {"original": "", "currency": "", "frequency": "", "monthly_usd": None, "monthly_inr": None,
           "verified": "", "commission": commission_note, "verdict": "unclear",
           "reason": "", "bucket": "", "notes": [remoteok_note] if remoteok_note else []}

    if not candidates:
        out["reason"] = "salary not disclosed"
        out["verified"] = "No – not disclosed"
        return out

    pay = None
    for p in candidates:
        if p.period:
            pay = p
            break
    if pay is None:
        p = candidates[0]
        out.update(original=p.original, currency=p.currency, frequency="Not stated",
                   reason="pay frequency not stated", verified="No – frequency unknown")
        return out

    m = monthly(pay.amount, pay.period, cfg, full_time)
    out.update(original=pay.original, currency=pay.currency, frequency=pay.period.title())
    if m is None:
        out.update(reason=f"{pay.period} pay but full-time hours not confirmed", verified="No – hours unknown")
        return out
    usd = fx.to_usd(m, pay.currency)
    if usd is None:
        out.update(reason=f"no exchange rate for {pay.currency}", verified="No – currency unknown")
        return out
    if not _sane(usd):
        out.update(reason=f"salary figure looks wrong ({pay.original})", verified="No – implausible figure")
        return out
    inr = fx.usd_to(usd, "INR")
    out.update(monthly_usd=round(usd, 2), monthly_inr=round(inr) if inr else None,
               verified=("Yes – " + pay.evidence) if pay.evidence == "posting text" or job.is_official
               else f"Listed by {job.source} (confirm on posting)")

    if ote:
        out.update(verdict="unclear", reason="pay quoted as OTE (includes commission). Base not stated",
                   verified="No – OTE only")
        return out

    if pay.currency == "INR":
        ok = m >= cfg["min_monthly_inr"]
        thr = f"₹{cfg['min_monthly_inr']:,}/month"
    else:
        ok = usd >= cfg["min_monthly_usd"]
        thr = f"${cfg['min_monthly_usd']}/month"
    if not ok:
        out.update(verdict="reject", bucket="salary",
                   reason=f"fixed pay ≈ ${usd:,.0f}/month (₹{inr:,.0f}) is below {thr}")
        return out
    out["verdict"] = "ok"
    return out


def _fmt_range(a, b, cur, per) -> str:
    def f(x):
        return f"{float(x):,.0f}"
    s = f"{cur} {f(a)}" + (f"–{f(b)}" if b and float(b) != float(a) else "")
    return s + (f" / {per}" if per else "")
