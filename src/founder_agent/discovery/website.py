"""Company-site crawl: the /about and /team pages.

This is where a founder's name, title, photo and often their direct address
live, published deliberately by the company. We fetch a handful of well-known
paths, obey robots.txt, and never crawl deeper than the pages we name.

Used two ways: as a standalone source over a list of domains, and as an
enrichment step for leads that arrived with a domain but no human attached.
"""

from __future__ import annotations

import asyncio
import re

from bs4 import BeautifulSoup

from ..models import EmailStatus, Lead, extract_emails, harvest_socials
from ..utils import clean_text, domain_of, looks_like_person_name
from .base import DiscoverySource

# Tags that realistically hold a person's name on a team page.
_NAME_TAGS = ["h1", "h2", "h3", "h4", "h5", "strong", "b", "span", "p", "div", "figcaption"]


class WebsiteSource(DiscoverySource):
    name = "website"

    async def discover(self, limit: int, domains: list[str] | None = None) -> list[Lead]:
        domains = domains or []
        if not domains:
            self.log.info("no domains supplied; website source runs as an enricher")
            return []
        results = await asyncio.gather(
            *(self.crawl_domain(d) for d in domains[:limit]), return_exceptions=True
        )
        leads: list[Lead] = []
        for result in results:
            if isinstance(result, list):
                leads.extend(result)
        return leads

    async def crawl_domain(self, domain: str) -> list[Lead]:
        """Fetch the known team/about paths on one domain and pull out people."""
        domain = domain_of(domain) or domain
        if not domain:
            return []

        paths = self.config.get("paths", ["/about", "/team", "/contact"])
        base = f"https://{domain}"
        pages: list[tuple[str, str]] = []

        for path in paths:
            url = base + path
            resp = await self.client.get(url)
            if resp is None or resp.status_code >= 400:
                continue
            ctype = resp.headers.get("content-type", "")
            if "html" not in ctype:
                continue
            pages.append((url, resp.text))

        leads: list[Lead] = []
        for url, html in pages:
            leads.extend(self._people_from_page(html, url, domain))

        # Collapse repeats of the same person across /about and /team.
        merged: dict[str, Lead] = {}
        for lead in leads:
            key = lead.dedupe_key()
            if key in merged:
                merged[key].merge(lead)
            else:
                merged[key] = lead
        return list(merged.values())

    def _people_from_page(self, html: str, url: str, domain: str) -> list[Lead]:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        page_text = soup.get_text(" ", strip=True)
        company = ""
        if soup.title and soup.title.string:
            company = re.split(r"[|\-–—:]", soup.title.string)[0].strip()[:60]

        # Page-level contact details, used as a fallback for everyone found here.
        page_emails = [
            e for e in extract_emails(page_text) if domain in e or e.endswith(domain)
        ] or extract_emails(page_text)

        found: list[Lead] = []
        seen_names: set[str] = set()

        for tag in soup.find_all(_NAME_TAGS):
            text = tag.get_text(" ", strip=True)
            if not text or len(text) > 60 or not looks_like_person_name(text):
                continue
            if text in seen_names:
                continue

            # A title has to appear near the name for us to believe it's a founder.
            context = ""
            for rel in (tag.parent, tag.find_next_sibling(), tag.find_next()):
                if rel is not None:
                    context += " " + rel.get_text(" ", strip=True)[:300]
            matched = self.settings.match_founder_title(context)
            if not matched:
                continue

            seen_names.add(text)
            lead = Lead(
                full_name=text,
                role=matched.title(),
                company=company or domain,
                company_domain=domain,
                company_url=f"https://{domain}",
                source=self.name,
                source_url=url,
                bio=clean_text(context, 240),
                notes=[f"found on {url}"],
            )

            # Prefer a personal address over the page-wide one.
            personal = [e for e in extract_emails(context) if e not in ("",)]
            chosen = personal[0] if personal else (page_emails[0] if page_emails else "")
            if chosen:
                lead.email = chosen
                lead.email_status = EmailStatus.PUBLISHED
                lead.email_source = f"website:{url}"

            # Socials from the card around the name, then from the page footer.
            harvest_socials(str(tag.parent) if tag.parent else "", lead)
            harvest_socials(html, lead)
            found.append(lead)

        return found
