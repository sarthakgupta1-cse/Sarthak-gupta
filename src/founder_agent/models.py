"""Core data shapes. One Lead is one human being we might contact."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# An explicit t.me link is unambiguous; a bare @handle is not, so they are
# matched separately and the link always wins.
_TELEGRAM_LINK_RE = re.compile(
    r"(?:t\.me|telegram\.me)/([A-Za-z][A-Za-z0-9_]{4,31})\b", re.IGNORECASE
)
_TELEGRAM_AT_RE = re.compile(r"(?<![\w.@+-])@([A-Za-z][A-Za-z0-9_]{4,31})\b")
_TWITTER_RE = re.compile(r"(?:twitter\.com/|x\.com/)([A-Za-z0-9_]{1,15})\b", re.IGNORECASE)
_GITHUB_RE = re.compile(
    r"github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)\b", re.IGNORECASE
)
_LINKEDIN_RE = re.compile(r"(?:linkedin\.com/in/)([A-Za-z0-9\-_%]{3,100})", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# Handles that show up on every marketing site and are never a founder.
_HANDLE_DENYLIST = {
    "share", "intent", "home", "login", "signup", "about", "help", "privacy",
    "terms", "search", "explore", "settings", "telegram", "joinchat", "addstickers",
}


class EmailStatus:
    """How much we trust an address. Only VERIFIED should get cold outreach."""

    VERIFIED = "verified"        # provider confirmed the mailbox accepts mail
    GUESSED = "guessed"          # pattern-derived, unverified — do not send
    PUBLISHED = "published"      # the person published it themselves
    RISKY = "risky"              # catch-all or accept-all domain
    UNKNOWN = "unknown"


@dataclass
class Lead:
    """A founder, plus everything we learned about how to reach them."""

    full_name: str = ""
    role: str = ""
    company: str = ""
    company_domain: str = ""
    company_url: str = ""

    email: str = ""
    email_status: str = EmailStatus.UNKNOWN
    email_source: str = ""

    linkedin_url: str = ""
    twitter_handle: str = ""
    github_username: str = ""
    telegram_handle: str = ""
    personal_site: str = ""

    location: str = ""
    bio: str = ""
    headcount: int | None = None

    source: str = ""             # which discovery module found them
    source_url: str = ""         # the public page we found them on
    discovered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    launched_at: str = ""        # when their product launched, if known

    score: int = 0
    notes: list[str] = field(default_factory=list)

    # -- identity ----------------------------------------------------------
    @property
    def first_name(self) -> str:
        return self.full_name.split()[0] if self.full_name.strip() else ""

    @property
    def last_name(self) -> str:
        parts = self.full_name.split()
        return parts[-1] if len(parts) > 1 else ""

    def dedupe_key(self) -> str:
        """Strongest available identity signal, so merges are stable across runs."""
        if self.email:
            return f"email:{self.email.strip().lower()}"
        if self.linkedin_url:
            slug = _LINKEDIN_RE.search(self.linkedin_url)
            if slug:
                return f"li:{slug.group(1).lower()}"
        if self.full_name and self.company_domain:
            raw = f"{self.full_name.strip().lower()}|{self.company_domain.strip().lower()}"
            return "nc:" + hashlib.sha1(raw.encode()).hexdigest()[:16]
        if self.twitter_handle:
            return f"tw:{self.twitter_handle.lower()}"
        raw = f"{self.full_name}|{self.company}|{self.source_url}".lower()
        return "weak:" + hashlib.sha1(raw.encode()).hexdigest()[:16]

    def merge(self, other: Lead) -> Lead:
        """Fold another record for the same person into this one.

        Non-empty wins over empty; a verified email always beats a guessed one.
        """
        for key, value in asdict(other).items():
            if key in ("notes", "email", "email_status", "email_source", "score"):
                continue
            if not value:
                continue
            if not getattr(self, key, None):
                setattr(self, key, value)

        if other.email:
            rank = {
                EmailStatus.VERIFIED: 4,
                EmailStatus.PUBLISHED: 3,
                EmailStatus.RISKY: 2,
                EmailStatus.GUESSED: 1,
                EmailStatus.UNKNOWN: 0,
            }
            if not self.email or rank.get(other.email_status, 0) > rank.get(self.email_status, 0):
                self.email = other.email
                self.email_status = other.email_status
                self.email_source = other.email_source

        for note in other.notes:
            if note not in self.notes:
                self.notes.append(note)
        return self

    def to_row(self) -> dict[str, Any]:
        data = asdict(self)
        data["first_name"] = self.first_name
        data["last_name"] = self.last_name
        data["notes"] = "; ".join(self.notes)
        return data


def harvest_socials(text: str, lead: Lead) -> Lead:
    """Pull handles out of a blob of public text (a bio, a site footer, a README).

    Only ever reads text the person published about themselves. Telegram handles
    in particular are taken from public bios — we never enumerate Telegram itself.
    """
    if not text:
        return lead

    if not lead.linkedin_url:
        m = _LINKEDIN_RE.search(text)
        if m:
            lead.linkedin_url = f"https://www.linkedin.com/in/{m.group(1)}"

    if not lead.twitter_handle:
        m = _TWITTER_RE.search(text)
        if m and m.group(1).lower() not in _HANDLE_DENYLIST:
            lead.twitter_handle = m.group(1)

    if not lead.github_username:
        m = _GITHUB_RE.search(text)
        if m and m.group(1).lower() not in _HANDLE_DENYLIST:
            lead.github_username = m.group(1)

    if not lead.telegram_handle:
        lead.telegram_handle = _find_telegram(text)

    return lead


def _find_telegram(text: str) -> str:
    """A t.me link beats a bare @handle, and an email is never a handle.

    Without stripping emails first, 'ada@acme.com' yields the handle 'acme' —
    which is how you end up messaging a domain name.
    """
    for match in _TELEGRAM_LINK_RE.finditer(text):
        handle = match.group(1)
        if handle.lower() not in _HANDLE_DENYLIST:
            return handle

    # A bare @handle only counts when Telegram is named somewhere in the text.
    if "telegram" not in text.lower():
        return ""
    without_emails = _EMAIL_RE.sub(" ", text)
    for match in _TELEGRAM_AT_RE.finditer(without_emails):
        handle = match.group(1)
        if handle.lower() not in _HANDLE_DENYLIST:
            return handle
    return ""


def extract_emails(text: str) -> list[str]:
    """Published addresses only, with the obvious non-human ones dropped."""
    noise = ("example.com", "sentry.io", "@2x", ".png", ".jpg", ".svg", "@github.com")
    seen: list[str] = []
    for match in _EMAIL_RE.findall(text or ""):
        low = match.lower()
        if any(n in low for n in noise) or low in seen:
            continue
        seen.append(low)
    return seen
