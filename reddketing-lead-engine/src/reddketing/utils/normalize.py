"""Company-name and domain normalisation used for duplicate detection."""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

import tldextract

# Offline extractor: use the bundled public-suffix snapshot, include private
# suffixes so foo.myshopify.com / foo.vercel.app resolve to the store, not the host.
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)

LEGAL_SUFFIXES = {
    "inc", "incorporated", "llc", "ltd", "limited", "plc", "gmbh", "ag", "sa", "sas", "bv", "pvt",
    "private", "corp", "corporation", "co", "company", "pty", "oy", "ab", "srl", "spa", "kk",
}
GENERIC_BRAND_TOKENS = {"ai", "app", "apps", "hq", "io", "labs", "lab", "the", "technologies", "technology",
                        "tech", "software", "studio", "studios", "global", "group", "official", "online", "inc"}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _tokens(name: str) -> list[str]:
    name = strip_accents(name or "").lower().replace("&", " and ")
    name = re.sub(r"\.(com|io|ai|app|co|net|org|so|dev)\b", r" \1", name)
    return [t for t in re.split(r"[^a-z0-9]+", name) if t]


def normalize_name(name: str) -> str:
    """'Example AI, Inc.' -> 'exampleai'; 'ExampleAI.com' -> 'exampleaicom' minus tld -> 'exampleai'."""
    toks = [t for t in _tokens(name) if t not in LEGAL_SUFFIXES]
    if len(toks) > 1 and toks[-1] in {"com", "net", "org", "co", "so", "dev"}:
        toks = toks[:-1]
    return "".join(toks)


def core_name(name: str) -> str:
    """Name with generic brand tokens removed: 'Example AI Labs' -> 'example'."""
    toks = [t for t in _tokens(name) if t not in LEGAL_SUFFIXES]
    if len(toks) > 1 and toks[-1] in {"com", "net", "org", "co", "so", "dev"}:
        toks = toks[:-1]
    core = [t for t in toks if t not in GENERIC_BRAND_TOKENS]
    return "".join(core) or "".join(toks)


def ensure_url(url_or_domain: str) -> str:
    url_or_domain = (url_or_domain or "").strip()
    if not url_or_domain:
        return ""
    if not re.match(r"^https?://", url_or_domain, re.I):
        url_or_domain = "https://" + url_or_domain
    return url_or_domain


def root_domain(url_or_domain: str) -> str:
    """https://www.app.example.co.uk/path -> example.co.uk ('' if not a valid domain)."""
    if not url_or_domain:
        return ""
    host = urlparse(ensure_url(url_or_domain)).hostname or ""
    host = host.lower().strip(".")
    if not host or re.fullmatch(r"[\d.]+", host):
        return ""
    ext = _EXTRACT(host)
    if not ext.domain or not ext.suffix:
        return ""
    return f"{ext.domain}.{ext.suffix}"


def domain_label(url_or_domain: str) -> str:
    """example.co.uk -> 'example' (used to match country-specific domains)."""
    rd = root_domain(url_or_domain)
    if not rd:
        return ""
    return _EXTRACT(rd).domain.lower()


def is_non_company_domain(url_or_domain: str, blocklist: set[str]) -> bool:
    rd = root_domain(url_or_domain)
    if not rd:
        return True
    return rd in blocklist or any(rd.endswith("." + b) for b in blocklist)


def similarity(a: str, b: str) -> float:
    """Character-bigram Dice similarity of two normalised strings (0..1)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    def grams(s: str) -> list[str]:
        return [s[i:i + 2] for i in range(len(s) - 1)] or [s]
    ga, gb = grams(a), grams(b)
    pool = list(gb)
    hits = 0
    for g in ga:
        if g in pool:
            hits += 1
            pool.remove(g)
    return 2 * hits / (len(ga) + len(gb))
