"""Candidates the scheduled Claude session found by web research.

This covers places with no public API that may not be scraped: LinkedIn hiring
posts, Wellfound, Indeed, YC Work at a Startup, company career pages and
Reddit hiring threads. The session reads those pages the way a person would,
writes only facts printed on the page into out/manual_candidates.json, and
this source sends them through exactly the same filters as everything else.

File format: a JSON list of objects with RawJob field names. At minimum:
  company, title, source_url, description.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import ROOT
from ..models import RawJob
from .base import Source, SourceResult

_FIELDS = set(RawJob.__dataclass_fields__)


class ManualSource(Source):
    name = "Web research (Claude session)"

    def __init__(self, cfg):
        self.path = Path(cfg.get("file", "out/manual_candidates.json"))
        if not self.path.is_absolute():
            self.path = ROOT / self.path

    def fetch(self) -> SourceResult:
        res = SourceResult(self.name)
        if not self.path.exists():
            return res
        for item in json.loads(self.path.read_text(encoding="utf-8")):
            clean = {k: v for k, v in item.items() if k in _FIELDS}
            clean.setdefault("source", f"Web research: {item.get('site', 'web')}")
            clean.setdefault("apply_url", clean.get("source_url", ""))
            if not (clean.get("company") and clean.get("title") and clean.get("source_url")):
                res.errors.append(f"skipped incomplete manual candidate: {item.get('title', '?')}")
                continue
            res.jobs.append(RawJob(**clean))
        return res
