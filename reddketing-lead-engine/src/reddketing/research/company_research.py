"""Per-company research: gather sources, let the LLM synthesise, then validate deterministically."""
from __future__ import annotations

import re

import logging
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from ..models import Candidate, CompanyProfile, ResearchExtraction, RevenueEstimate, SourceDoc
from ..providers.news_feeds import FreeSources
from ..providers.search_provider import SearchProvider
from ..utils.http import HttpClient
from ..utils.normalize import is_non_company_domain, root_domain
from ..utils.text import digits_variants, extract_links, html_to_text
from . import prompts
from .contact_research import validate_people
from .funding_research import validate_funding
from .pricing_research import pick_internal_pages
from .revenue_estimator import apply_to_profile

logger = logging.getLogger(__name__)
UNFETCHABLE = {"linkedin.com", "crunchbase.com", "x.com", "twitter.com", "facebook.com", "instagram.com",
               "pitchbook.com", "zoominfo.com", "similarweb.com", "g2.com", "glassdoor.com"}


class SourceCollector:
    def __init__(self):
        self.docs: list[SourceDoc] = []
        self.urls: set[str] = set()
        self.accessed = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def add(self, url, kind, title, text, publisher="") -> SourceDoc | None:
        key = url.split("#")[0].rstrip("/")
        if not text or key in self.urls:
            return None
        self.urls.add(key)
        doc = SourceDoc(id=f"S{len(self.docs) + 1}", url=url, title=title or "", kind=kind, text=text,
                        accessed_at=self.accessed, publisher=publisher)
        self.docs.append(doc)
        return doc


def gather_sources(candidate: Candidate, http: HttpClient, search: SearchProvider, free: FreeSources,
                   settings, *, query_budget: int) -> tuple[list[SourceDoc], list[str], str]:
    """Returns (sources, all_domains_seen, homepage_error)."""
    max_chars = int(settings.llm_setting("max_chars_per_document", 6000))
    max_docs = int(settings.llm_setting("max_documents_per_company", 9))
    blocklist = settings.non_company_domains
    col = SourceCollector()
    domains = {candidate.domain}
    home = http.get_text(candidate.website or f"https://{candidate.domain}")
    if not home.ok:
        return [], sorted(domains), home.error or f"HTTP {home.status}"
    final_root = root_domain(home.final_url)
    if final_root:
        domains.add(final_root)
    title, text = html_to_text(home.html, max_chars)
    col.add(home.final_url, "company_page", title, text)
    for kind, url in pick_internal_pages(extract_links(home.html, home.final_url), final_root or candidate.domain).items():
        if len([d for d in col.docs if d.kind == "company_page"]) >= 6:
            break
        res = http.get_text(url)
        if res.ok:
            t, body = html_to_text(res.html, max_chars)
            col.add(res.final_url, "company_page", f"[{kind}] {t}", body)

    # Funding hint from discovery (headline-level evidence)
    hint = candidate.funding_hint
    hint_url = hint.get("source_url") or (candidate.discovery_urls[0] if candidate.discovery_urls else "")
    if hint.get("headline") and hint_url:
        col.add(hint_url, "news_headline", hint["headline"], f"Headline: {hint['headline']} (published {hint.get('date', '')})",
                hint.get("publisher", ""))

    # Paid search (budgeted): financial signals, then people.
    name = candidate.name
    queries = [f'"{name}" revenue OR ARR OR customers OR users OR downloads OR raised',
               f'"{name}" founder OR CEO OR CMO OR "head of growth" OR "VP marketing"'][:max(0, query_budget)]
    third_party_fetched = 0
    for q in queries:
        for r in search.search(q):
            rd = root_domain(r.url)
            snippet = f"{r.title}. {r.snippet}".strip()
            if rd in domains:
                continue
            col.add(r.url, "search_snippet", r.title, snippet + (f" (dated {r.published})" if r.published else ""))
            if (q is queries[0] and third_party_fetched < 2 and rd not in UNFETCHABLE
                    and name.split()[0].lower() in snippet.lower()):
                res = http.get_text(r.url)
                if res.ok:
                    t, body = html_to_text(res.html, max_chars)
                    if name.split()[0].lower() in body.lower():
                        col.add(res.final_url, "third_party_page", t, body)
                        third_party_fetched += 1

    # Free: Google News headlines for the company name.
    for it in free.google_news(f'"{name}"', days=180, kind="company")[:4]:
        col.add(it.url, "news_headline", it.title, f"Headline: {it.title} (published {it.published})", it.source)

    # Keep company pages + best third-party pages within the document budget; snippets are short.
    pages = [d for d in col.docs if d.kind in ("company_page", "third_party_page")][:max_docs]
    small = [d for d in col.docs if d.kind not in ("company_page", "third_party_page")][:16]
    return pages + small, sorted(d for d in domains if d and not is_non_company_domain(d, blocklist)), ""


_SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "mn": 1e6, "mm": 1e6, "m": 1e6,
          "billion": 1e9, "bn": 1e9, "b": 1e9}
_AMOUNT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(thousand|million|billion|mn|mm|bn|k|m|b)\b", re.I)


def scaled_value(numeric: float | None, text: str) -> float | None:
    """Fix numbers given in units ("$2B" sent as 2, "10k users" as 10) using the signal's own text."""
    if numeric is None or numeric <= 0 or numeric >= 1000:
        return numeric
    for num, unit in _AMOUNT.findall(text or ""):
        try:
            n = float(num.replace(",", "."))
        except ValueError:
            continue
        if abs(n - numeric) <= max(0.01 * numeric, 0.001):
            return numeric * _SCALE[unit.lower()]
    return numeric


def _normalise_amounts(ex: ResearchExtraction, notes: list[str]) -> None:
    for s in ex.signals:
        fixed = scaled_value(s.numeric_value, s.value_text)
        if fixed != s.numeric_value:
            notes.append(f"Scaled '{s.value_text}' from {s.numeric_value:g} to {fixed:,.0f}")
            s.numeric_value = fixed


def _verify_numbers(ex: ResearchExtraction, by_id: dict[str, SourceDoc], notes: list[str]) -> None:
    for s in ex.signals:
        src = by_id.get(s.source_id)
        if not src:
            continue
        hay = f"{src.title} {src.text}".lower()
        hay_nocomma = hay.replace(",", "")
        variants = digits_variants(s.value_text)
        if variants and not any(v in hay or v in hay_nocomma for v in variants):
            if s.claim_type != "unverified":
                notes.append(f"Signal '{s.value_text}' not found verbatim in {src.url}; marked unverified")
            s.claim_type = "unverified"


def validate_extraction(ex: ResearchExtraction, sources: list[SourceDoc], company_domain: str) -> list[str]:
    """Removes anything not grounded in a retrieved source. Returns human-readable notes."""
    by_id = {s.id: s for s in sources}
    notes: list[str] = []
    before = len(ex.signals)
    ex.signals = [s for s in ex.signals if s.source_id in by_id]
    if len(ex.signals) < before:
        notes.append(f"Dropped {before - len(ex.signals)} signals citing unknown sources")
    ex.pricing = [p for p in ex.pricing if p.source_id in by_id and
                  (p.price_usd_per_month is None or 0 <= p.price_usd_per_month < 100_000)]
    _normalise_amounts(ex, notes)
    _verify_numbers(ex, by_id, notes)
    if ex.revenue_inputs.paying_customers_source_id not in by_id:
        ex.revenue_inputs.paying_customers_source_id = None
    ex.reddit.subreddits = [s for s in ex.reddit.subreddits if s.name.strip()][:8]
    for sr in ex.reddit.subreddits:
        sr.name = "r/" + sr.name.strip().removeprefix("/").removeprefix("r/").strip("/ ")
        if sr.source_id not in by_id:
            sr.source_id = None
    if ex.founded_year and not (1900 <= ex.founded_year <= date.today().year):
        ex.founded_year = None
    if ex.hiring_evidence_source_id not in by_id:
        ex.hiring_growth_roles = False
        ex.hiring_evidence_source_id = None
    return notes


def research_company(candidate: Candidate, *, http: HttpClient, search: SearchProvider, free: FreeSources,
                     llm, settings, today: date, query_budget: int) -> CompanyProfile | str:
    """Returns a CompanyProfile, or an error string if the company could not be researched."""
    sources, domains, err = gather_sources(candidate, http, search, free, settings, query_budget=query_budget)
    if err or not sources:
        return f"official website unreachable ({err or 'no content'})"
    context = candidate.discovery_note
    if candidate.funding_hint:
        context += f" | funding hint: {candidate.funding_hint.get('headline', '')}"
    ex = llm.complete_json(prompts.research_system(settings),
                           prompts.research_user_prompt(candidate.name, candidate.domain, today.isoformat(), sources, context),
                           ResearchExtraction)
    notes = validate_extraction(ex, sources, candidate.domain)
    contacts, contact_notes = validate_people(ex.people, sources, candidate.domain)
    website = next((s.url for s in sources if s.kind == "company_page"), candidate.website)
    profile = CompanyProfile(
        candidate=candidate, extraction=ex, domain=root_domain(website) or candidate.domain,
        website=f"{urlparse(website).scheme}://{urlparse(website).netloc}", all_domains=domains, sources=sources,
        revenue=RevenueEstimate(method="pending"), contacts=contacts, research_date=today,
        validation_notes=notes + contact_notes)
    profile.validation_notes += validate_funding(profile)
    apply_to_profile(profile, settings)
    return profile
