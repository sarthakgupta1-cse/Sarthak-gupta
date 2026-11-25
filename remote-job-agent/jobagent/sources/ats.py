"""Employer career pages via the public job-board APIs of Greenhouse, Lever and Ashby.

These APIs exist so career pages can be embedded anywhere, so using them is
ToS-friendly. Postings found here count as *official* sources.
"""
from __future__ import annotations

import concurrent.futures as cf
import logging

from ..classify import title_is_relevant
from ..models import RawJob
from ..text import html_to_text
from .base import Source, SourceResult

log = logging.getLogger(__name__)


def _co_name(entry: dict) -> str:
    return entry.get("name") or entry["slug"].replace("-", " ").title()


class _BoardSource(Source):
    workers = 6

    def __init__(self, http, companies: list[dict]):
        self.http, self.companies = http, companies or []

    def board(self, entry: dict) -> list[RawJob]:  # pragma: no cover - interface
        raise NotImplementedError

    def fetch(self) -> SourceResult:
        res = SourceResult(self.name, sub_sources=len(self.companies))
        with cf.ThreadPoolExecutor(self.workers) as ex:
            futs = {ex.submit(self.board, c): c for c in self.companies}
            for f in cf.as_completed(futs):
                c = futs[f]
                try:
                    res.jobs.extend(f.result())
                    res.ok_boards.append(c["slug"].lower())
                except Exception as exc:  # noqa: BLE001 — one dead board never stops the rest
                    res.errors.append(f"{c['slug']}: {exc}")
        return res


class GreenhouseSource(_BoardSource):
    name = "Greenhouse career pages"

    def board(self, c):
        d = self.http.json(f"https://boards-api.greenhouse.io/v1/boards/{c['slug']}/jobs", params={"content": "true"})
        out = []
        for j in d.get("jobs", []):
            if not title_is_relevant(j.get("title", "")):
                continue
            loc = (j.get("location") or {}).get("name", "")
            out.append(RawJob(
                source=f"Greenhouse ({c['slug']})", source_url=j.get("absolute_url", ""),
                apply_url=j.get("absolute_url", ""), external_id=str(j.get("id", "")),
                is_official=True, company=_co_name(c), title=j.get("title", ""),
                location_text=loc, locations=[x.strip() for x in loc.replace(";", ",").split(",") if x.strip()],
                remote=("remote" in loc.lower()) or None,
                description=html_to_text(j.get("content", "")),
                posted_at=(j.get("first_published") or j.get("updated_at") or "")[:10],
                industry=c.get("industry", ""),
            ))
        return out


class LeverSource(_BoardSource):
    name = "Lever career pages"

    def board(self, c):
        data = self.http.json(f"https://api.lever.co/v0/postings/{c['slug']}", params={"mode": "json"})
        out = []
        for j in data:
            if not title_is_relevant(j.get("text", "")):
                continue
            cat = j.get("categories") or {}
            locs = cat.get("allLocations") or ([cat.get("location")] if cat.get("location") else [])
            sal = j.get("salaryRange") or {}
            interval = (sal.get("interval") or "").lower()
            period = {"per-year-salary": "annual", "per-month-salary": "monthly",
                      "per-hour-wage": "hourly", "per-week-salary": "weekly"}.get(interval, interval)
            desc = " ".join(filter(None, [j.get("descriptionPlain", ""),
                                          " ".join(html_to_text(x.get("content", "")) for x in j.get("lists", [])),
                                          j.get("additionalPlain", "")]))
            out.append(RawJob(
                source=f"Lever ({c['slug']})", source_url=j.get("hostedUrl", ""),
                apply_url=j.get("applyUrl") or j.get("hostedUrl", ""), external_id=j.get("id", ""),
                is_official=True, company=_co_name(c), title=j.get("text", ""),
                location_text=", ".join(locs), locations=locs,
                remote=(j.get("workplaceType") == "remote") if j.get("workplaceType") else None,
                employment_type=cat.get("commitment", ""),
                salary_min=sal.get("min"), salary_max=sal.get("max"),
                salary_currency=sal.get("currency", "") or "", salary_period=period,
                description=desc, industry=c.get("industry", ""),
                posted_at=_ms_date(j.get("createdAt")),
            ))
        return out


class AshbySource(_BoardSource):
    name = "Ashby career pages"

    def board(self, c):
        d = self.http.json(f"https://api.ashbyhq.com/posting-api/job-board/{c['slug']}",
                           params={"includeCompensation": "true"})
        out = []
        for j in d.get("jobs", []):
            if not j.get("isListed", True) or not title_is_relevant(j.get("title", "")):
                continue
            locs = [j.get("location", "")] + [x.get("location", "") for x in j.get("secondaryLocations", []) or []]
            locs = [x for x in locs if x]
            smin = smax = None
            cur = period = ""
            comp = j.get("compensation") or {}
            for comp_part in comp.get("summaryComponents", []) or []:
                if comp_part.get("compensationType") == "Salary":
                    smin, smax = comp_part.get("minValue"), comp_part.get("maxValue")
                    cur = comp_part.get("currencyCode", "") or ""
                    iv = (comp_part.get("interval") or "").upper()
                    period = {"1 YEAR": "annual", "1 MONTH": "monthly", "1 HOUR": "hourly", "1 WEEK": "weekly"}.get(iv, iv.lower())
                    break
            wt = (j.get("workplaceType") or "").lower()
            out.append(RawJob(
                source=f"Ashby ({c['slug']})", source_url=j.get("jobUrl", ""),
                apply_url=j.get("applyUrl") or j.get("jobUrl", ""), external_id=j.get("id", ""),
                is_official=True, company=_co_name(c), title=j.get("title", ""),
                location_text=", ".join(locs), locations=locs,
                remote=True if (j.get("isRemote") or wt == "remote") else (False if wt in ("onsite", "hybrid") else None),
                employment_type=j.get("employmentType", "") or "",
                salary_min=smin, salary_max=smax, salary_currency=cur, salary_period=period,
                salary_text=comp.get("compensationTierSummary", "") or "",
                description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", "")),
                posted_at=(j.get("publishedAt") or "")[:10], industry=c.get("industry", ""),
            ))
        return out


def _ms_date(v) -> str:
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ""
