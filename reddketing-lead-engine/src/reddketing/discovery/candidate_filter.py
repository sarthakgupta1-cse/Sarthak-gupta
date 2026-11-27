"""Initial filtering: in-batch dedupe, historical dedupe, domain resolution, restricted names."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..database.duplicate_detection import DuplicateIndex, DuplicateMatch
from ..models import Candidate
from ..providers.search_provider import SearchProvider
from ..utils.normalize import (core_name, domain_label, is_hobby_host, is_non_company_domain, normalize_name,
                               root_domain, similarity)

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    accepted: list[Candidate] = field(default_factory=list)
    duplicates: list[tuple[Candidate, DuplicateMatch]] = field(default_factory=list)
    dropped: list[tuple[Candidate, str]] = field(default_factory=list)


def merge_in_batch(cands: list[Candidate]) -> list[Candidate]:
    merged: dict[str, Candidate] = {}
    for c in cands:
        key = c.domain or normalize_name(c.name)
        if not key:
            continue
        alt = next((k for k, v in merged.items() if (c.domain and v.domain == c.domain)
                    or normalize_name(v.name) == normalize_name(c.name)), None)
        if alt:
            v = merged[alt]
            v.discovery_channels = sorted(set(v.discovery_channels) | set(c.discovery_channels))
            v.discovery_urls = list(dict.fromkeys(v.discovery_urls + c.discovery_urls))[:6]
            v.is_funding_lead = v.is_funding_lead or c.is_funding_lead
            v.funding_hint = v.funding_hint or c.funding_hint
            v.website = v.website or c.website
            v.domain = v.domain or c.domain
        else:
            merged[key] = c
    return list(merged.values())


def name_matches_domain(name: str, domain: str) -> bool:
    lbl = domain_label(domain)
    n, core = normalize_name(name), core_name(name)
    return bool(lbl) and (lbl == n or lbl == core or lbl.startswith(core) or similarity(lbl, n) >= 0.7
                          or (len(core) >= 4 and core in lbl))


GUESS_TLDS = ("com", "ai", "io", "app", "co")


def guess_domain(c: Candidate, http, blocklist: set[str]) -> bool:
    """Free resolution: try name.com/.ai/.io/.app/.co and accept a site whose title or text names the company."""
    core = core_name(c.name) or normalize_name(c.name)
    if not http or not core or len(core) < 3:
        return False
    name = c.name.lower().strip()
    for tld in GUESS_TLDS:
        domain = f"{core}.{tld}"
        if is_non_company_domain(domain, blocklist):
            continue
        res = http.get_text(f"https://{domain}", quick=True)
        if not res.ok:
            continue
        head = res.html[:20000].lower()
        title = head.split("<title", 1)[-1].split("</title>", 1)[0] if "<title" in head else ""
        if name in title or (core in title.replace(" ", "")) or name in head[:5000]:
            final = root_domain(res.final_url) or domain
            if is_non_company_domain(final, blocklist) or is_hobby_host(final):
                continue
            c.domain, c.website = final, f"https://{final}"
            return True
    return False


def resolve_domain(c: Candidate, search: SearchProvider, blocklist: set[str], allow_search: bool,
                   http=None) -> bool:
    if c.domain and not is_non_company_domain(c.domain, blocklist) and not is_hobby_host(c.domain):
        return True
    c.domain = c.website = ""
    if guess_domain(c, http, blocklist):
        return True
    if not allow_search:
        return False
    for r in search.search(f'"{c.name}" official website'):
        if is_non_company_domain(r.url, blocklist):
            continue
        if name_matches_domain(c.name, r.url) or c.name.lower() in r.title.lower():
            rd = root_domain(r.url)
            c.domain, c.website = rd, f"https://{rd}"
            return True
    return False


def filter_candidates(cands: list[Candidate], index: DuplicateIndex, search: SearchProvider, settings, *,
                      max_domain_lookups: int, today, http=None) -> FilterResult:
    blocklist = settings.non_company_domains
    restricted = [w.lower() for w in settings.categories.get("restricted_categories", [])]
    out = FilterResult()
    lookups = guesses = 0
    max_guesses = int(settings.get("discovery.max_domain_guesses", 40))
    for c in merge_in_batch(cands):
        c.name = " ".join(c.name.split())[:120]
        text = f"{c.name} {c.discovery_note}".lower()
        hit = next((w for w in restricted if w in text), None)
        if hit:
            out.dropped.append((c, f"restricted category ({hit})"))
            continue
        # Cheap duplicate check first (before spending a search query on domain resolution).
        m = index.match(c.name, c.domain)
        if m and not DuplicateIndex.rejected_is_reconsiderable(m, index, today):
            out.duplicates.append((c, m))
            continue
        if not c.domain or is_hobby_host(c.domain):
            allow = lookups < max_domain_lookups
            lookups += 1 if allow else 0
            guess_http = http if guesses < max_guesses else None
            guesses += 1 if guess_http else 0
            if not resolve_domain(c, search, blocklist, allow, guess_http):
                out.dropped.append((c, "no verifiable official website found"))
                continue
            m = index.match(c.name, c.domain)
            if m and not DuplicateIndex.rejected_is_reconsiderable(m, index, today):
                out.duplicates.append((c, m))
                continue
        if not c.website:
            c.website = f"https://{c.domain}"
        out.accepted.append(c)
    return out


AUDIENCE_RANK = {"consumer": 0, "prosumer": 0, "smb_self_serve": 1, "developer": 1, "unknown": 2}


def prioritise(cands: list[Candidate], limit: int, funded_share: float = 0.25) -> list[Candidate]:
    """Keep a mix of funding leads and growth/launch leads; prefer Reddit-reachable audiences,
    then multi-channel candidates."""
    def rank(c: Candidate):
        return (AUDIENCE_RANK.get(c.audience, 2), -len(c.discovery_channels), 0 if c.website else 1)
    funded = sorted([c for c in cands if c.is_funding_lead], key=rank)
    other = sorted([c for c in cands if not c.is_funding_lead], key=rank)
    n_f = min(len(funded), max(1, int(limit * funded_share)))
    chosen = funded[:n_f] + other[: limit - n_f]
    if len(chosen) < limit:
        rest = [c for c in funded[n_f:] + other[limit - n_f:] if c not in chosen]
        chosen += rest[: limit - len(chosen)]
    return chosen
