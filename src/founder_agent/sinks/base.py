"""Sink contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Settings
from ..models import Lead

# Column order, shared by every sink so exports line up across formats.
COLUMNS = [
    "full_name", "first_name", "last_name", "role", "company", "company_domain",
    "company_url", "email", "email_status", "email_source", "linkedin_url",
    "twitter_handle", "telegram_handle", "github_username", "personal_site",
    "location", "headcount", "bio", "score", "source", "source_url",
    "launched_at", "discovered_at", "notes",
]


class Sink(ABC):
    name = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def available(self) -> tuple[bool, str]:
        return True, ""

    @abstractmethod
    def write(self, leads: list[Lead]) -> int:
        """Persist leads, returning how many rows were written or updated."""

    @staticmethod
    def rows(leads: list[Lead]) -> list[dict]:
        return [{c: lead.to_row().get(c, "") for c in COLUMNS} for lead in leads]
