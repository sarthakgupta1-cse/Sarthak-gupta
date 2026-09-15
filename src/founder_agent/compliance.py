"""Guardrails. These are not decoration — they are what keeps this legal and
keeps your sending domain out of a blocklist.

Three things happen here:
  1. robots.txt is honoured before any page fetch.
  2. A suppression list (opt-outs, competitors, personal domains) is enforced
     at write time, so a removal request survives the next run.
  3. Every lead carries provenance, which is what a GDPR Art. 14 request or a
     CAN-SPAM complaint actually asks you to produce.
"""

from __future__ import annotations

import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

SUPPRESSION_FILE = Path("data/suppression.txt")

# Free-mail domains: a founder's personal address is a weaker B2B basis to
# process under legitimate interest, so we keep them but mark them.
FREEMAIL = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "proton.me", "protonmail.com", "aol.com", "gmx.com", "mail.com",
}

# Role addresses are not a person — mailing them is noise and hurts reputation.
ROLE_PREFIXES = {
    "info", "support", "admin", "sales", "contact", "hello", "help", "billing",
    "noreply", "no-reply", "webmaster", "postmaster", "abuse", "privacy", "legal",
    "careers", "jobs", "press", "security", "team",
}


class RobotsCache:
    """One parsed robots.txt per host, fetched once per run."""

    def __init__(self, user_agent: str, enabled: bool = True) -> None:
        self.user_agent = user_agent
        self.enabled = enabled
        self._cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    async def allowed(self, url: str, client) -> bool:
        if not self.enabled:
            return True
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host not in self._cache:
            self._cache[host] = await self._fetch(host, client)
        parser = self._cache[host]
        if parser is None:
            return True  # no robots.txt served == no restriction
        return parser.can_fetch(self.user_agent, url)

    async def _fetch(self, host: str, client):
        try:
            resp = await client.get(f"{host}/robots.txt", respect_robots=False)
            if resp is None or resp.status_code >= 400:
                return None
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(resp.text.splitlines())
            return parser
        except Exception:
            return None


def load_suppression() -> set[str]:
    """Emails, domains and LinkedIn slugs that must never be written or contacted."""
    if not SUPPRESSION_FILE.exists():
        return set()
    entries = set()
    for line in SUPPRESSION_FILE.read_text().splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            entries.add(line)
    return entries


def suppress(entry: str) -> None:
    """Record an opt-out. Call this the moment someone asks to be removed."""
    SUPPRESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = load_suppression()
    entry = entry.strip().lower()
    if entry in existing:
        return
    with SUPPRESSION_FILE.open("a") as fh:
        fh.write(entry + "\n")


def is_suppressed(lead, suppression: set[str]) -> bool:
    if not suppression:
        return False
    email = (lead.email or "").lower()
    if email and email in suppression:
        return True
    if email and email.split("@")[-1] in suppression:
        return True
    domain = (lead.company_domain or "").lower()
    if domain and domain in suppression:
        return True
    linkedin = (lead.linkedin_url or "").lower()
    return bool(linkedin and any(s in linkedin for s in suppression if s.startswith("linkedin")))


def is_role_address(email: str) -> bool:
    if "@" not in (email or ""):
        return False
    return email.split("@")[0].strip().lower() in ROLE_PREFIXES


def is_freemail(email: str) -> bool:
    if "@" not in (email or ""):
        return False
    return email.split("@")[-1].strip().lower() in FREEMAIL
