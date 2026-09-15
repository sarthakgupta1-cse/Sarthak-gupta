"""Small shared helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import tldextract

# Use the snapshot bundled with tldextract instead of fetching the Public Suffix
# List at import time: no network dependency, no surprise stall on a cold start.
_extract = tldextract.TLDExtract(suffix_list_urls=())

_NAME_RE = re.compile(r"^[A-Z][a-z'’\-]{1,20}(?:\s+[A-Z][a-zA-Z'’\-\.]{1,20}){1,2}$")


def domain_of(url_or_email: str) -> str:
    """Registrable domain for a URL or an email. 'https://blog.acme.co.uk/x' -> acme.co.uk"""
    if not url_or_email:
        return ""
    value = url_or_email.strip()
    if "@" in value and "://" not in value:
        value = value.split("@")[-1]
    if "://" not in value:
        value = "https://" + value
    ext = _extract(urlparse(value).netloc)
    if not ext.domain or not ext.suffix:
        return ""
    return f"{ext.domain}.{ext.suffix}".lower()


def looks_like_person_name(text: str) -> bool:
    """Cheap filter so we don't file 'Our Team' or 'Privacy Policy' as a human."""
    text = (text or "").strip()
    if not _NAME_RE.match(text):
        return False
    lowered = text.lower()
    noise = (
        "our team", "the team", "about us", "privacy policy", "terms of",
        "contact us", "get started", "learn more", "read more", "sign up",
        "log in", "book a", "case study", "all rights",
    )
    return not any(n in lowered for n in noise)


def clean_text(value: str, limit: int = 400) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()[:limit]
