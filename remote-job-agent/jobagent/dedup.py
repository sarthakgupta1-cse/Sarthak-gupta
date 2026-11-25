"""Duplicate detection.

Three keys per vacancy:
  job_id    = hash(company | title | remote scope). The stable ID shown in the sheet.
  title_key = hash(company | title). Catches the same role posted on two boards.
  url_key   = hash(canonical application/posting URL). Catches renamed copies.

Two listings are the same vacancy if any of these hold:
  * job_id matches;
  * url_key matches (any URL either listing carries);
  * title_key matches and the scopes don't contradict each other
    ("india" vs "latam" means two different openings; "unknown" matches anything).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .text import norm_company, norm_title, norm_url

_SOURCE_RANK = {"official": 0, "Himalayas": 2, "We Work Remotely": 3, "Remotive": 3, "Jobicy": 4,
                "Remote OK": 4, "Working Nomads": 5}


def _h(s: str, n: int = 10) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:n].upper()


def scope_of(india_label: str, remote_label: str) -> str:
    il = (india_label or "").lower()
    if "india" in il:
        return "india"
    if "worldwide" in il or "worldwide" in (remote_label or "").lower():
        return "worldwide"
    if il.startswith("no"):
        return "restricted"
    return "unknown"


def keys_for(company: str, title: str, scope: str, urls: list[str]) -> tuple[str, str, list[str]]:
    c, t = norm_company(company), norm_title(title)
    job_id = "RJ-" + _h(f"{c}|{t}|{scope if scope in ('india', 'worldwide') else 'remote'}", 8)
    title_key = _h(f"{c}|{t}")
    url_keys = sorted({_h(norm_url(u)) for u in urls if u})
    return job_id, title_key, url_keys


def source_rank(job) -> int:
    if job.raw.is_official:
        return 0
    if job.raw.source.startswith("Web research"):
        return 1
    return _SOURCE_RANK.get(job.raw.source, 6)


@dataclass
class IndexEntry:
    job_id: str
    title_key: str
    url_key: str
    scope: str
    tab: str
    status: str
    check_url: str = ""
    last_verified: str = ""
    label: str = ""            # "Company — Title" (kept for change reports)


@dataclass
class DedupIndex:
    by_id: dict[str, IndexEntry] = field(default_factory=dict)
    by_url: dict[str, str] = field(default_factory=dict)
    by_title: dict[str, list[str]] = field(default_factory=dict)
    extra_ids: set[str] = field(default_factory=set)      # IDs present in sheets but missing from _Index

    def add(self, e: IndexEntry) -> None:
        self.by_id[e.job_id] = e
        for uk in filter(None, e.url_key.split(",")):
            self.by_url[uk] = e.job_id
        self.by_title.setdefault(e.title_key, []).append(e.job_id)

    def match(self, job_id: str, title_key: str, url_keys: list[str], scope: str) -> str | None:
        if job_id in self.by_id or job_id in self.extra_ids:
            return job_id
        for uk in url_keys:
            if uk in self.by_url:
                return self.by_url[uk]
        for other in self.by_title.get(title_key, []):
            os_ = self.by_id[other].scope
            if "unknown" in (scope, os_) or scope == os_:
                return other
        return None
