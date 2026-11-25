"""Decision-maker validation: every person, LinkedIn URL and email must appear in a retrieved source."""
from __future__ import annotations

from ..models import Contact, Person, SourceDoc
from ..utils.normalize import root_domain
from ..utils.text import canonical_linkedin, find_emails, find_linkedin_urls

ROLE_PRIORITY = ["founder", "co-founder", "ceo", "chief executive", "cmo", "chief marketing", "head of growth",
                 "vp marketing", "vp of marketing", "growth marketing", "head of acquisition", "marketing director",
                 "director of marketing", "head of marketing", "cto", "coo"]


def role_rank(title: str) -> int:
    t = (title or "").lower()
    for i, r in enumerate(ROLE_PRIORITY):
        if r in t:
            return i
    return len(ROLE_PRIORITY)


def validate_people(people: list[Person], sources: list[SourceDoc], company_domain: str) -> tuple[list[Contact], list[str]]:
    by_id = {s.id: s for s in sources}
    all_text = "\n".join(f"{s.url}\n{s.title}\n{s.text}" for s in sources)
    known_linkedin = find_linkedin_urls(all_text)
    page_emails: dict[str, str] = {}
    for s in sources:
        if s.fully_read:
            for e in find_emails(s.text):
                page_emails.setdefault(e, s.url)
    notes: list[str] = []
    contacts: list[Contact] = []
    seen = set()
    for p in people:
        src = by_id.get(p.source_id)
        name = " ".join(p.name.split())
        if not src or name.lower() in seen or len(name) < 3:
            notes.append(f"Dropped person '{name}': no valid source")
            continue
        haystack = f"{src.title} {src.text}".lower()
        if name.lower() not in haystack and name.split()[-1].lower() not in haystack:
            notes.append(f"Dropped person '{name}': name not found in cited source {src.url}")
            continue
        seen.add(name.lower())
        li = canonical_linkedin(p.linkedin_url or "")
        if li and li not in known_linkedin:
            notes.append(f"Removed unverified LinkedIn URL for {name}")
            li = ""
        email, status = "", "Not publicly verified"
        if p.email:
            e = p.email.strip().lower()
            if e in page_emails:
                email = e
                status = f"Publicly listed on {page_emails[e]}"
                if root_domain(e.split("@")[-1]) != company_domain:
                    status += " (non-company domain)"
            else:
                notes.append(f"Removed unverified email for {name}")
        confidence = "High" if src.kind == "company_page" else ("Medium" if src.fully_read else "Low")
        contacts.append(Contact(name=name, title=p.title.strip()[:120], linkedin_url=li, email=email,
                                email_status=status, source_url=src.url, confidence=confidence))
    contacts.sort(key=lambda c: role_rank(c.title))
    return contacts[:6], notes


def generic_business_email(sources: list[SourceDoc], company_domain: str) -> str:
    """A role address (hello@, press@, partnerships@...) printed on the company's own pages, if any."""
    preferred = ("partnerships", "marketing", "growth", "press", "media", "hello", "contact", "info", "team")
    found = []
    for s in sources:
        if s.kind != "company_page":
            continue
        for e in find_emails(s.text):
            if root_domain(e.split("@")[-1]) == company_domain:
                found.append((e, s.url))
    for p in preferred:
        for e, url in found:
            if e.startswith(p + "@"):
                return f"{e} (listed on {url})"
    return f"{found[0][0]} (listed on {found[0][1]})" if found else ""
