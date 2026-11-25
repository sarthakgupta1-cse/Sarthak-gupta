"""HTML -> readable text, link and email extraction."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}\b")
LINKEDIN_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|company)/[A-Za-z0-9_\-%.]+/?", re.I)


def html_to_text(html: str, max_chars: int | None = None) -> tuple[str, str]:
    """Returns (title, visible_text)."""
    soup = BeautifulSoup(html or "", "lxml")
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "template"]):
        tag.decompose()
    # Keep mailto: / linkedin hrefs visible so they can be verified against page text.
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:") or "linkedin.com/" in href:
            a.append(f" [{href.replace('mailto:', '')}]")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    if max_chars:
        text = text[:max_chars]
    return title, text


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html or "", "lxml")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        out.append((urljoin(base_url, href), a.get_text(" ", strip=True)[:80]))
    return out


def find_emails(text: str) -> set[str]:
    return {e.lower().rstrip(".") for e in EMAIL_RE.findall(text or "")
            if not e.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"))}


def find_linkedin_urls(text: str) -> set[str]:
    return {canonical_linkedin(u) for u in LINKEDIN_RE.findall(text or "")}


def canonical_linkedin(url: str) -> str:
    url = (url or "").strip()
    m = re.search(r"linkedin\.com/(in|company)/([A-Za-z0-9_\-%.]+)", url, re.I)
    if not m:
        return ""
    return f"https://www.linkedin.com/{m.group(1).lower()}/{m.group(2).strip('/').lower()}"


def digits_variants(value_text: str) -> list[str]:
    """Candidate number strings to look for when verifying a numeric claim against its source."""
    out = []
    for m in re.finditer(r"\d[\d,\.]*\s*(?:k|m|b|million|billion|thousand)?", value_text or "", re.I):
        token = m.group(0).strip()
        out.append(token.lower())
        out.append(token.replace(",", "").lower())
        leading = re.match(r"[\d,\.]+", token)
        if leading:
            out.append(leading.group(0).rstrip(".,"))
    return [o for o in dict.fromkeys(out) if o]
