"""Loads config.yaml + .env into one settings object."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CONFIG_PATH = Path("config.yaml")


@dataclass
class Settings:
    targeting: dict[str, Any] = field(default_factory=dict)
    discovery: dict[str, Any] = field(default_factory=dict)
    enrichment: dict[str, Any] = field(default_factory=dict)
    politeness: dict[str, Any] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)

    # -- secrets, read from the environment only, never from config.yaml ----
    @property
    def github_token(self) -> str: return os.getenv("GITHUB_TOKEN", "")
    @property
    def producthunt_token(self) -> str: return os.getenv("PRODUCTHUNT_TOKEN", "")
    @property
    def proxycurl_key(self) -> str: return os.getenv("PROXYCURL_API_KEY", "")
    @property
    def apollo_key(self) -> str: return os.getenv("APOLLO_API_KEY", "")
    @property
    def hunter_key(self) -> str: return os.getenv("HUNTER_API_KEY", "")
    @property
    def google_sa_file(self) -> str: return os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    @property
    def google_sheet_id(self) -> str: return os.getenv("GOOGLE_SHEET_ID", "")
    @property
    def google_worksheet(self) -> str: return os.getenv("GOOGLE_SHEET_WORKSHEET", "Leads")
    @property
    def contact_email(self) -> str: return os.getenv("OUTREACH_FROM_EMAIL", "")

    @property
    def user_agent(self) -> str:
        ua = self.politeness.get("user_agent", "founder-agent/0.1")
        if self.contact_email and "contact:" not in ua:
            ua = f"founder-agent/0.1 (+contact: {self.contact_email})"
        return ua

    def founder_titles(self) -> list[str]:
        return [t.lower() for t in self.targeting.get("founder_titles", [])]

    def is_founder_title(self, role: str) -> bool:
        return bool(self.match_founder_title(role))

    def match_founder_title(self, text: str) -> str:
        """Longest matching title wins, so "Co-Founder & CEO" is not filed as
        plain "founder" just because that entry comes first in the config."""
        low = (text or "").lower()
        for title in sorted(self.founder_titles(), key=len, reverse=True):
            if title in low:
                return title
        return ""

    def enabled(self, section: str, name: str) -> bool:
        block = getattr(self, section, {}).get(name, {})
        if isinstance(block, bool):
            return block
        return bool(block.get("enabled", True))


def load_settings(path: str | Path = DEFAULT_CONFIG_PATH) -> Settings:
    path = Path(path)
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text()) or {}
    return Settings(
        targeting=raw.get("targeting", {}),
        discovery=raw.get("discovery", {}),
        enrichment=raw.get("enrichment", {}),
        politeness=raw.get("politeness", {}),
        scoring=raw.get("scoring", {}),
        output=raw.get("output", {}),
    )
