"""Text helpers: HTML → text, normalisation for matching and fingerprints."""
from __future__ import annotations

import html
import re
import unicodedata

from bs4 import BeautifulSoup

_WS = re.compile(r"\s+")


def html_to_text(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)          # some feeds double-encode (&lt;p&gt;)
    if "<" in s and ">" in s:
        s = BeautifulSoup(s, "html.parser").get_text(" ")
    return _WS.sub(" ", s).strip()


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


_CO_SUFFIX = re.compile(
    r"\b(incorporated|inc|llc|l\.l\.c|ltd|limited|gmbh|corp|corporation|co|company|pvt|private|plc|sa|bv|ag|oy|ab|labs?|technologies|technology|hq|group)\b\.?",
    re.I)


def norm_company(name: str) -> str:
    s = ascii_fold(name or "").lower()
    s = s.replace("&", " and ")
    s = _CO_SUFFIX.sub(" ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return _WS.sub(" ", s).strip()


_TITLE_NOISE = re.compile(
    r"\((?:[^)]*(?:remote|worldwide|anywhere|full[- ]?time|contract|f/m|m/f|m/w/d|wfh)[^)]*)\)|"
    r"\b(remote|worldwide|anywhere|full[- ]?time|wfh|work from home|100%)\b", re.I)
_TITLE_ALIASES = [
    (re.compile(r"\bsr\.?\b"), "senior"),
    (re.compile(r"\bjr\.?\b"), "junior"),
    (re.compile(r"\bmgr\b"), "manager"),
    (re.compile(r"\bexec\b"), "executive"),
    (re.compile(r"\bseo\b"), "seo"),
    (re.compile(r"\bsmm\b"), "social media marketing"),
]


def norm_title(title: str) -> str:
    s = ascii_fold(title or "").lower()
    s = _TITLE_NOISE.sub(" ", s)
    # drop trailing location suffixes like " - US", " | India", " – LATAM"
    s = re.sub(r"\s[-|–—/]\s[^-|–—/]{1,30}$", " ", s) if re.search(r"\s[-|–—/]\s", s) else s
    for pat, rep in _TITLE_ALIASES:
        s = pat.sub(rep, s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return _WS.sub(" ", s).strip()


def norm_url(url: str) -> str:
    """Canonical form of a URL for duplicate detection (no scheme, query trackers, slashes)."""
    if not url:
        return ""
    u = url.strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = re.sub(r"[?#].*$", "", u)          # tracking params never identify a vacancy
    return u.rstrip("/")


def clip(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"
