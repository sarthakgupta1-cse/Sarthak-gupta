"""Vacancy verification: find the employer's original posting and check it is still open."""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

ATS_HOSTS = re.compile(
    r"greenhouse\.io|lever\.co|ashbyhq\.com|workable\.com|bamboohr\.com|recruitee\.com|smartrecruiters\.com|"
    r"breezy\.hr|jobvite\.com|teamtailor\.com|personio\.(?:de|com)|myworkdayjobs\.com|icims\.com|"
    r"rippling-ats\.com|ats\.rippling\.com|pinpointhq\.com|dover\.com|wellfound\.com|keka\.com|zohorecruit|"
    r"freshteam\.com|hirist|darwinbox|careers\.|/careers|/jobs/", re.I)
AGGREGATORS = re.compile(r"himalayas\.app|remotive\.com|remoteok\.com|jobicy\.com|weworkremotely\.com|"
                         r"workingnomads\.com", re.I)
# Sites that require login or block automated access. Never fetched (respecting their terms).
NO_FETCH = re.compile(r"linkedin\.com|indeed\.|glassdoor\.|flexjobs\.com|naukri\.com|facebook\.com|x\.com|twitter\.com|"
                      r"himalayas\.app|remoteok\.com", re.I)   # login walls / bot-blocking (HTTP 403) — never fetched
CLOSED = re.compile(r"no longer (?:accepting|available|open)|position (?:has been|is) (?:filled|closed)|"
                    r"job (?:is|has been) (?:closed|removed|filled|expired)|this job (?:has )?expired|"
                    r"posting (?:has )?(?:closed|expired)|vacancy (?:is )?closed|applications? (?:are |is )?closed|"
                    r"job not found|page not found|couldn.t find (?:that|this) job", re.I)
SKIP_LINK_HOSTS = re.compile(r"facebook|twitter|x\.com|linkedin|instagram|youtube|google|apple\.com/app|"
                             r"play\.google|t\.co$|bit\.ly", re.I)


def find_original(apply_url: str, http) -> str:
    """For an aggregator listing, return the employer-hosted application URL if the page links to one."""
    if not apply_url or not AGGREGATORS.search(apply_url) or NO_FETCH.search(apply_url):
        return ""
    try:
        r = http.get(apply_url)
    except Exception as exc:  # noqa: BLE001
        log.info("original-link lookup failed for %s: %s", apply_url, exc)
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    agg_host = urlparse(apply_url).netloc
    best = ""
    for a in soup.find_all("a", href=True):
        href = urljoin(apply_url, a["href"])
        host = urlparse(href).netloc
        if not host or agg_host in host or AGGREGATORS.search(host) or SKIP_LINK_HOSTS.search(host):
            continue
        label = (a.get_text(" ") or "").lower()
        if ATS_HOSTS.search(href) or "apply" in label:
            if ATS_HOSTS.search(href) and "apply" in label:
                return href.split("?utm")[0]
            best = best or href.split("?utm")[0]
    return best


def check_open(url: str, http) -> str:
    """'Open', 'Closed' or 'Unknown' (never guesses)."""
    if not url or NO_FETCH.search(url):
        return "Unknown"
    try:
        r = http.get(url, accept_status=(200, 404, 410, 403, 401))
    except Exception:  # noqa: BLE001
        return "Unknown"
    if r.status_code in (404, 410):
        return "Closed"
    if r.status_code in (401, 403):
        return "Unknown"
    if "error=true" in r.url or re.search(r"greenhouse\.io/[^/]+/?$", r.url):
        return "Closed"      # Greenhouse redirects removed jobs back to the board
    text = BeautifulSoup(r.text[:400000], "html.parser").get_text(" ")[:20000]
    if CLOSED.search(text):
        return "Closed"
    return "Open"


def company_site_from(url: str) -> str:
    """Company homepage guessed only from an employer-hosted URL (never from aggregators/ATS)."""
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    if not host or AGGREGATORS.search(host) or re.search(
            r"greenhouse|lever\.co|ashbyhq|workable|bamboohr|recruitee|smartrecruiters|breezy|jobvite|teamtailor|"
            r"personio|workday|icims|rippling|pinpoint|dover|wellfound|keka|zoho|freshteam|linkedin|indeed", host):
        return ""
    host = re.sub(r"^(careers|jobs|apply|work|join)\.", "", host)
    return f"https://{host}"
