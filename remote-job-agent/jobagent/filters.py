"""Remote eligibility for India, employment type and experience level.

Each check returns (verdict, label, reason). verdict is "ok", "unclear" or "reject".
"unclear" sends the job to Needs Verification. It is never silently dropped and
never silently accepted.
"""
from __future__ import annotations

import re

from .classify import JUNIOR_TITLE, MANAGER_TITLE, is_senior_title
from .models import RawJob

OK, UNCLEAR, REJECT = "ok", "unclear", "reject"

# --------------------------------------------------------------------------- location

_INDIA = re.compile(r"\bindia\b|\bindian\b|bengaluru|bangalore|mumbai|delhi|gurgaon|gurugram|noida|hyderabad|"
                    r"pune|chennai|kolkata|ahmedabad|jaipur|kota|\bIST\b", re.I)
_GLOBAL = re.compile(r"worldwide|anywhere|\bglobal(?:ly)?\b|international|all countries|any country|"
                     r"any location|\bapac\b|asia[- ]?pacific|\basia\b|south asia|no location restriction|"
                     r"location[- ]independent|work from anywhere", re.I)
# Regions that do NOT include India.
_NON_INDIA_REGION = (r"(?:the\s+)?(?:us|u\.s\.?a?\.?|usa|united states|america|north america|canada|uk|u\.k\.|"
                     r"united kingdom|great britain|britain|england|ireland|eu|e\.u\.|europe|european union|eea|emea|"
                     r"latam|latin america|south america|central america|mexico|brazil|argentina|colombia|"
                     r"germany|france|spain|portugal|netherlands|poland|italy|australia|new zealand|anz|"
                     r"philippines|nigeria|kenya|south africa|africa|japan|singapore|israel|"
                     r"(?:est|pst|cst|mst|cet|gmt|bst)(?:\s+time\s*zone)?)")
_RESTRICTION_PATTERNS = [
    re.compile(r"(?:must|need to|needs to|required to|should|have to|has to)\s+(?:be\s+)?(?:currently\s+)?"
               r"(?:based|located|living|residing|reside|live)\s+(?:in|within)\s+" + _NON_INDIA_REGION + r"\b", re.I),
    re.compile(r"\b(?:only\s+(?:open|available)\s+to\s+(?:candidates|applicants|residents)\s+(?:in|of|from|based in)\s+)"
               + _NON_INDIA_REGION + r"\b", re.I),
    re.compile(r"\b(?:us|u\.s\.|usa|uk|canada|eu|europe|latam|emea|north america|americas)[- ](?:only|based only)\b", re.I),
    re.compile(r"\b(?:legally\s+)?(?:authori[sz]ed|eligible|permitted)\s+to\s+work\s+in\s+"
               r"(?:the\s+)?(?:us|u\.s\.?|usa|united states|uk|united kingdom|canada|eu|europe|australia)\b", re.I),
    re.compile(r"\bremote\s*(?:[-–(,:/]|\bin\b)\s*(?:us|u\.s\.?|usa|united states|uk|canada|europe|eu|latam|emea|"
               r"americas|north america|australia|germany|spain|brazil|mexico)\b", re.I),
    re.compile(r"\bresidents?\s+of\s+(?:the\s+)?(?:us|u\.s\.?|usa|united states|uk|canada|eu|europe)\s+only\b", re.I),
]
_ONSITE = re.compile(r"\bhybrid\b|\bon[- ]?site\b|\bin[- ]office\b|\bin-person\b|relocat(?:e|ion) (?:to|required)", re.I)
_REMOTE_WORD = re.compile(r"\bremote\b|work from home|\bwfh\b|distributed team|fully distributed", re.I)


def _restriction(text: str) -> str:
    for rx in _RESTRICTION_PATTERNS:
        m = rx.search(text)
        if m:
            return m.group(0)
    return ""


def check_location(job: RawJob) -> tuple[str, str, str, str]:
    """Return (verdict, remote_label, india_label, reason)."""
    locs = [l for l in job.locations if l and l.strip()]
    loc_blob = " | ".join(locs + [job.location_text])
    head = f"{job.title} | {loc_blob}"
    desc = job.description or ""

    if job.remote is False or _ONSITE.search(head):
        return REJECT, "On-site/hybrid", "No", f"not fully remote ({loc_blob or job.title})"

    india_listed = bool(_INDIA.search(loc_blob))
    global_listed = bool(_GLOBAL.search(loc_blob)) or (job.source == "Himalayas" and not locs)
    restricted_locs = bool(locs) and not india_listed and not global_listed and not all(
        re.fullmatch(r"\s*remote\s*", l, re.I) for l in locs)

    if restricted_locs:
        return REJECT, f"Remote ({', '.join(locs)[:80]})", "No", f"restricted to {', '.join(locs)[:80]}"

    restriction = _restriction(desc) or _restriction(head)
    india_in_desc = bool(re.search(r"\bindia\b", desc, re.I))
    if restriction and not india_listed and not india_in_desc:
        return REJECT, "Remote (location-restricted)", "No", f"posting says: “{restriction.strip()}”"

    is_remote = job.remote is True or bool(_REMOTE_WORD.search(head))
    if india_listed:
        if not is_remote:
            return UNCLEAR, f"Unclear ({loc_blob[:60]})", "Unclear", "India location listed but remote status not stated"
        return OK, "Remote – India eligible", "Yes (India listed)", ""
    if global_listed:
        note = f"; posting also says “{restriction.strip()}”" if restriction else ""
        if restriction:
            return UNCLEAR, "Remote – worldwide label", "Unclear", f"board says worldwide{note}"
        return OK, "Remote – worldwide", "Yes (worldwide)", ""
    if india_in_desc and is_remote:
        return OK, "Remote", "Yes (India mentioned in posting)", ""
    return UNCLEAR, f"Remote ({loc_blob[:60] or 'location not stated'})", "Unclear", "India eligibility not stated"


# --------------------------------------------------------------------------- employment type

_PART = re.compile(r"part[- ]?time", re.I)
_FULL = re.compile(r"full[- ]?time|\bpermanent\b|\b40\s*(?:hours|hrs)\b", re.I)
_INTERN = re.compile(r"\bintern(?:ship)?\b|\bapprentice", re.I)
_TEMP = re.compile(r"\btemporary\b|\btemp\b|\bseasonal\b|fixed[- ]term|\bgig\b|per (?:article|word|piece)|"
                   r"(?:\d+|three|six|3|6)[- ]months? contract", re.I)
_FREELANCE = re.compile(r"\bfreelance\b|\bfreelancer\b|project[- ]based|\bper project\b", re.I)
_CONTRACT = re.compile(r"\bcontract(?:or)?\b", re.I)
_COMMISSION_ONLY = re.compile(r"commission[- ]only|100\s*%\s*commission|commission[- ]based (?:role|position|pay|compensation)|"
                              r"(?:pay|compensation) is (?:purely |entirely )?commission", re.I)


def check_employment(job: RawJob) -> tuple[str, str, str]:
    stated = f"{job.employment_type} | {job.title}"
    desc = job.description or ""
    if _INTERN.search(stated):
        return REJECT, "Internship", "internship"
    if _PART.search(job.title or "") or (_PART.search(stated) and not _FULL.search(stated)):
        return REJECT, "Part-time", "part-time"     # a "Part-Time" title beats a board's type field
    if _FREELANCE.search(stated):
        return REJECT, "Freelance", "freelance-only"
    if _TEMP.search(stated):
        return REJECT, "Temporary", "temporary"
    if _COMMISSION_ONLY.search(stated + " " + desc):
        return REJECT, "Commission-only", "commission-only pay"
    if _FULL.search(stated):
        if _CONTRACT.search(stated):
            return OK, "Full-time (contractor)", ""
        return OK, "Full-time", ""
    if _CONTRACT.search(stated):
        if _FULL.search(desc) and not _TEMP.search(desc[:3000]):
            return OK, "Full-time (contractor)", ""
        return UNCLEAR, "Contract (hours not stated)", "contract role. Full-time hours not confirmed"
    # Nothing stated by the source: read the description.
    if _INTERN.search(desc[:400]):
        return REJECT, "Internship", "internship"
    if _FREELANCE.search(desc[:1500]) and not _FULL.search(desc):
        return REJECT, "Freelance", "freelance-only"
    if _PART.search(desc[:1500]) and not _FULL.search(desc):
        return REJECT, "Part-time", "part-time"
    if _FULL.search(desc):
        return OK, "Full-time", ""
    return UNCLEAR, "Not stated", "employment type not stated"


# --------------------------------------------------------------------------- experience

_YEARS = re.compile(
    r"(?P<a>\d{1,2}|one|two|three|four|five|six|seven|eight|ten)\s*(?:\+|plus)?\s*"
    r"(?:(?:-|–|to)\s*(?P<b>\d{1,2})\s*\+?\s*)?(?:years?|yrs?)", re.I)
_WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "ten": 10}
_EXP_CTX = re.compile(r"experience|exp\b|background|track record|working (?:in|as|with)|professional", re.I)
_FRESHER_OK = re.compile(r"fresher|entry[- ]level|\bjunior\b|early[- ]career|recent graduate|new grad|"
                         r"no (?:prior )?experience (?:required|needed)|graduates? (?:are )?welcome|0\s*[-–]\s*[12]\s*years?", re.I)
_MID_TEXT = re.compile(r"mid[- ]level experience|mid[- ]senior|intermediate[- ]level|experienced (?:professional|marketer|writer)", re.I)
_SENIOR_LEVELS = {"senior", "lead", "director", "executive", "manager", "head", "principal", "vp", "c-level", "staff"}
_JUNIOR_LEVELS = {"entry-level", "entry level", "junior", "intern", "graduate", "associate"}


def _min_years(desc: str) -> int | None:
    found = []
    for m in _YEARS.finditer(desc):
        ctx = desc[max(0, m.start() - 60): m.end() + 70]
        if not _EXP_CTX.search(ctx):
            continue
        if re.search(r"(?:founded|old|ago|history|anniversary|since|over the (?:past|last)|in business)", ctx, re.I):
            continue
        a = m.group("a").lower()
        n = _WORDNUM.get(a, None) if not a.isdigit() else int(a)
        if n is not None and n <= 20:
            found.append(n)
    return min(found) if found else None


def check_experience(job: RawJob, cfg: dict) -> tuple[str, str, str]:
    title = job.title or ""
    if is_senior_title(title):
        return REJECT, "Senior-level title", f"senior title: {title}"
    levels = {s.strip().lower() for s in job.seniority if s}
    desc = job.description or ""
    fresher = bool(_FRESHER_OK.search(desc)) or bool(JUNIOR_TITLE.search(title)) or bool(levels & _JUNIOR_LEVELS)
    if levels and levels <= _SENIOR_LEVELS:
        return REJECT, f"{'/'.join(sorted(levels)).title()} level", "board marks the role senior"

    if _MID_TEXT.search(desc) and not _FRESHER_OK.search(desc):
        return UNCLEAR, "Mid-level (stated in posting)", "posting asks for mid-level experience"
    yrs = _min_years(desc)
    max_any, max_fresh = cfg.get("max_years_any", 1), cfg.get("max_years_if_fresher_ok", 2)
    if yrs is not None:
        if yrs <= max_any:
            return OK, f"{yrs}+ years" if yrs else "No minimum stated (0 years)", ""
        if yrs <= max_fresh:
            if fresher:
                return OK, f"{yrs}+ years (entry-level/junior welcome)", ""
            return REJECT, f"{yrs}+ years", f"asks {yrs}+ years and does not mention freshers"
        return REJECT, f"{yrs}+ years", f"asks {yrs}+ years"
    if "mid-level" in levels and not fresher:
        return UNCLEAR, "Mid-level (years not stated)", "board marks mid-level; years not stated"
    if fresher:
        return OK, "Entry-level / junior", ""
    if MANAGER_TITLE.search(title):
        return UNCLEAR, "Not stated (manager/strategist title)", "manager-level title with no experience stated"
    return OK, "Not stated (no senior requirement found)", ""
