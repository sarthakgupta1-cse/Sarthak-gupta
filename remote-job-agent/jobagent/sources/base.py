from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..models import RawJob

log = logging.getLogger(__name__)


@dataclass
class SourceResult:
    name: str
    jobs: list[RawJob] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    sub_sources: int = 1           # e.g. number of company boards searched
    ok_boards: list[str] = field(default_factory=list)   # ATS boards fully fetched (for closed-job detection)

    @property
    def ok(self) -> bool:
        return bool(self.jobs) or not self.errors


class Source:
    name = "base"

    def fetch(self) -> SourceResult:  # pragma: no cover - interface
        raise NotImplementedError

    def safe_fetch(self) -> SourceResult:
        """One failing source must never stop the run."""
        try:
            return self.fetch()
        except Exception as exc:  # noqa: BLE001 — logged and reported, run continues
            log.exception("source %s failed", self.name)
            return SourceResult(self.name, errors=[f"{type(exc).__name__}: {exc}"])
