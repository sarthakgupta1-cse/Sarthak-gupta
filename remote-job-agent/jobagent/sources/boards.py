"""Remote job boards with public, documented feeds.

Each adapter only maps fields. Every judgement (relevance, eligibility, salary)
happens later in the filters, the same way for every source.
"""
from __future__ import annotations

import ast
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from ..models import RawJob
from ..text import html_to_text
from .base import Source, SourceResult

log = logging.getLogger(__name__)


def _listish(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x]
    if isinstance(v, str) and v.startswith("["):
        try:
            return [str(x) for x in ast.literal_eval(v) if x]
        except (ValueError, SyntaxError):
            return [v]
    return [str(v)] if v else []


def _num(v):
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _epoch_date(v) -> str:
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def _iso_date(v: str) -> str:
    if not v:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(v.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return v[:10]


class HimalayasSource(Source):
    """himalayas.app public search API. `country=IN` keeps India-eligible + worldwide roles."""

    name = "Himalayas"
    URL = "https://himalayas.app/jobs/api/search"

    def __init__(self, http, cfg):
        self.http, self.cfg = http, cfg

    def fetch(self) -> SourceResult:
        res = SourceResult(self.name)
        seen: set[str] = set()
        for q in self.cfg["queries"]:
            for page in range(1, self.cfg.get("max_pages_per_query", 2) + 1):
                try:
                    d = self.http.json(self.URL, params={"q": q, "country": self.cfg.get("country", "IN"), "page": page})
                except Exception as exc:  # noqa: BLE001
                    res.errors.append(f"query '{q}' p{page}: {exc}")
                    break
                jobs = d.get("jobs") or []
                if not jobs:
                    if d.get("ok") is False:
                        res.errors.append(f"query '{q}': {d.get('errors')}")
                    break
                for j in jobs:
                    guid = j.get("guid") or j.get("applicationLink", "")
                    if guid in seen:
                        continue
                    seen.add(guid)
                    res.jobs.append(RawJob(
                        source=self.name, source_url=guid,
                        apply_url=(j.get("applicationLink") or guid),
                        company=j.get("companyName", ""), title=j.get("title", ""),
                        company_website="",
                        locations=_listish(j.get("locationRestrictions")),
                        location_text=", ".join(_listish(j.get("locationRestrictions"))) or "Worldwide",
                        remote=True,
                        employment_type=j.get("employmentType") or "",
                        seniority=_listish(j.get("seniority")),
                        salary_min=_num(j.get("minSalary")), salary_max=_num(j.get("maxSalary")),
                        salary_currency=(j.get("currency") or "") if str(j.get("currency")) != "None" else "",
                        salary_period=(j.get("salaryPeriod") or "").lower(),
                        description=html_to_text(j.get("description", "")),
                        posted_at=_epoch_date(j.get("pubDate")),
                        tags=_listish(j.get("categories")),
                    ))
                if len(jobs) < 20:
                    break
        res.sub_sources = len(self.cfg["queries"])
        return res


class RemotiveSource(Source):
    name = "Remotive"
    URL = "https://remotive.com/api/remote-jobs"

    def __init__(self, http, cfg):
        self.http, self.cfg = http, cfg

    def fetch(self) -> SourceResult:
        res = SourceResult(self.name)
        d = self.http.json(self.URL)       # one call; free feed ignores filters
        for j in d.get("jobs", []):
            loc = j.get("candidate_required_location") or ""
            res.jobs.append(RawJob(
                source=self.name, source_url=j.get("url", ""), apply_url=j.get("url", ""),
                external_id=str(j.get("id", "")),
                company=j.get("company_name", ""), title=j.get("title", ""),
                location_text=loc, locations=[x.strip() for x in loc.split(",") if x.strip()],
                remote=True, employment_type=(j.get("job_type") or "").replace("_", "-"),
                salary_text=j.get("salary") or "",
                description=html_to_text(j.get("description", "")),
                posted_at=_iso_date(j.get("publication_date", "")),
                tags=_listish(j.get("tags")) + [j.get("category", "")],
            ))
        return res


class RemoteOKSource(Source):
    name = "Remote OK"
    URL = "https://remoteok.com/api"

    def __init__(self, http, cfg):
        self.http, self.cfg = http, cfg

    def fetch(self) -> SourceResult:
        res = SourceResult(self.name)
        data = self.http.json(self.URL)
        for j in data:
            if not isinstance(j, dict) or "position" not in j:
                continue                     # first element is the legal notice
            loc = j.get("location") or ""
            res.jobs.append(RawJob(
                source=self.name, source_url=j.get("url", ""), apply_url=j.get("apply_url") or j.get("url", ""),
                external_id=str(j.get("id", "")),
                company=j.get("company", ""), title=j.get("position", ""),
                location_text=loc, locations=[x.strip() for x in loc.split(",") if x.strip()],
                remote=True,
                # Remote OK's salary fields aren't always employer-stated, so the
                # salary filter only trusts them when the description repeats the figure.
                salary_min=_num(j.get("salary_min")), salary_max=_num(j.get("salary_max")),
                salary_currency="USD" if _num(j.get("salary_min")) else "",
                salary_period="annual" if _num(j.get("salary_min")) else "",
                description=html_to_text(j.get("description", "")),
                posted_at=_iso_date(j.get("date", "")),
                tags=_listish(j.get("tags")),
            ))
        return res


class JobicySource(Source):
    name = "Jobicy"
    URL = "https://jobicy.com/api/v2/remote-jobs"

    def __init__(self, http, cfg):
        self.http, self.cfg = http, cfg

    def fetch(self) -> SourceResult:
        res = SourceResult(self.name)
        seen = set()
        for ind in self.cfg.get("industries", ["marketing"]):
            try:
                d = self.http.json(self.URL, params={"count": 100, "industry": ind})
            except Exception as exc:  # noqa: BLE001
                res.errors.append(f"industry '{ind}': {exc}")
                continue
            for j in d.get("jobs", []) or []:
                if j.get("id") in seen:
                    continue
                seen.add(j.get("id"))
                geo = j.get("jobGeo") or ""
                res.jobs.append(RawJob(
                    source=self.name, source_url=j.get("url", ""), apply_url=j.get("url", ""),
                    external_id=str(j.get("id", "")),
                    company=j.get("companyName", ""), title=html_to_text(j.get("jobTitle", "")),
                    location_text=geo, locations=[x.strip() for x in geo.split(",") if x.strip()],
                    remote=True, employment_type=", ".join(_listish(j.get("jobType"))),
                    seniority=[j.get("jobLevel")] if j.get("jobLevel") else [],
                    salary_min=_num(j.get("salaryMin") or j.get("annualSalaryMin")),
                    salary_max=_num(j.get("salaryMax") or j.get("annualSalaryMax")),
                    salary_currency=j.get("salaryCurrency") or "",
                    salary_period=(j.get("salaryPeriod") or ("annual" if j.get("annualSalaryMin") else "")).lower(),
                    description=html_to_text(j.get("jobDescription", "")),
                    posted_at=_iso_date(j.get("pubDate", "")),
                    tags=_listish(j.get("jobIndustry")),
                ))
        res.sub_sources = len(self.cfg.get("industries", []))
        return res


class WeWorkRemotelySource(Source):
    name = "We Work Remotely"

    def __init__(self, http, cfg):
        self.http, self.cfg = http, cfg

    def fetch(self) -> SourceResult:
        res = SourceResult(self.name)
        for feed in self.cfg["feeds"]:
            try:
                root = ET.fromstring(self.http.get(feed).content)
            except Exception as exc:  # noqa: BLE001
                res.errors.append(f"{feed}: {exc}")
                continue
            for it in root.iter("item"):
                g = lambda tag: (it.findtext(tag) or "").strip()  # noqa: E731
                raw_title = g("title")
                company, _, title = raw_title.partition(":")
                if not title:
                    company, title = "", raw_title
                region = g("region")
                res.jobs.append(RawJob(
                    source=self.name, source_url=g("link"), apply_url=g("link"),
                    company=company.strip(), title=title.strip(),
                    location_text=region or g("country"),
                    locations=[x.strip() for x in (region or "").split(",") if x.strip()],
                    remote=True, employment_type=g("type"),
                    description=html_to_text(g("description")),
                    posted_at=_iso_date(g("pubDate")),
                    tags=[g("category")],
                ))
        res.sub_sources = len(self.cfg["feeds"])
        return res


class WorkingNomadsSource(Source):
    name = "Working Nomads"
    URL = "https://www.workingnomads.com/api/exposed_jobs/"

    def __init__(self, http, cfg):
        self.http, self.cfg = http, cfg

    def fetch(self) -> SourceResult:
        res = SourceResult(self.name)
        for j in self.http.json(self.URL):
            loc = j.get("location") or ""
            res.jobs.append(RawJob(
                source=self.name, source_url=j.get("url", ""), apply_url=j.get("url", ""),
                company=j.get("company_name", ""), title=j.get("title", ""),
                location_text=loc, locations=[x.strip() for x in loc.split(",") if x.strip()],
                remote=True, description=html_to_text(j.get("description", "")),
                posted_at=_iso_date(j.get("pub_date", "")),
                tags=(j.get("tags") or "").split(",") + [j.get("category_name", "")],
            ))
        return res
