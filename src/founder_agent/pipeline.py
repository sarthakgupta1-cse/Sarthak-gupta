"""The agent loop: discover -> dedupe -> enrich -> score -> filter -> write.

Enrichment runs after dedupe, on purpose. Paid lookups are the expensive part,
so we collapse duplicates first and never spend two credits on one human.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field

from .compliance import is_suppressed, load_suppression
from .config import Settings
from .dedupe import dedupe
from .discovery import ALL_SOURCES
from .discovery.website import WebsiteSource
from .enrich import ALL_ENRICHERS
from .http import PoliteClient
from .models import Lead
from .scoring import is_contactable, score_lead
from .sinks import SINKS

log = logging.getLogger("founder_agent.pipeline")


@dataclass
class RunReport:
    discovered: int = 0
    after_dedupe: int = 0
    enriched: int = 0
    suppressed: int = 0
    below_threshold: int = 0
    written: int = 0
    contactable: int = 0
    estimated_cost_usd: float = 0.0
    skipped: dict[str, str] = field(default_factory=dict)
    http: dict[str, int] = field(default_factory=dict)
    leads: list[Lead] = field(default_factory=list)


class Pipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(
        self,
        limit: int = 50,
        domains: list[str] | None = None,
        dry_run: bool = False,
        sink_name: str | None = None,
        client: PoliteClient | None = None,
    ) -> RunReport:
        """Pass `client` to reuse an existing session (tests inject a fake here)."""
        report = RunReport()
        suppression = load_suppression()

        # nullcontext keeps an injected client from being closed out from under
        # its owner, while a client we create is still cleaned up properly.
        ctx = contextlib.nullcontext(client) if client else PoliteClient(self.settings)
        async with ctx as http:
            leads = await self._discover(http, limit, domains, report)
            report.discovered = len(leads)

            leads = dedupe(leads)
            report.after_dedupe = len(leads)
            log.info("deduped %d -> %d", report.discovered, report.after_dedupe)

            leads = await self._enrich(http, leads, report)

            # A founder found by domain alone still needs a human attached.
            leads = await self._backfill_from_websites(http, leads)

            leads = dedupe(leads)
            report.http = dict(getattr(http, "stats", {}))

        for lead in leads:
            score_lead(lead, self.settings)

        kept: list[Lead] = []
        min_score = self.settings.scoring.get("min_score", 0)
        for lead in leads:
            if is_suppressed(lead, suppression):
                report.suppressed += 1
                continue
            if lead.score < min_score:
                report.below_threshold += 1
                lead.notes.append(f"below min_score ({lead.score} < {min_score})")
            kept.append(lead)

        kept.sort(key=lambda lead: lead.score, reverse=True)
        report.contactable = sum(1 for lead in kept if is_contactable(lead))
        report.leads = kept

        if not dry_run:
            report.written = self._write(kept, sink_name)
        return report

    # -- stages ------------------------------------------------------------
    async def _discover(
        self, client: PoliteClient, limit: int, domains: list[str] | None, report: RunReport
    ) -> list[Lead]:
        tasks = []
        for source_cls in ALL_SOURCES:
            source = source_cls(self.settings, client)
            ok, why = source.available()
            if not ok:
                report.skipped[source.name] = why
                log.info("skipping source %s: %s", source.name, why)
                continue
            if isinstance(source, WebsiteSource):
                if not domains:
                    report.skipped[source.name] = "no --domains supplied"
                    continue
                tasks.append(source.discover(limit, domains=domains))
            else:
                tasks.append(source.discover(limit))

        if not tasks:
            log.warning("no discovery sources available")
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        leads: list[Lead] = []
        for result in results:
            if isinstance(result, Exception):
                log.warning("a discovery source failed: %s", result)
                continue
            leads.extend(result)
        return leads

    async def _enrich(
        self, client: PoliteClient, leads: list[Lead], report: RunReport
    ) -> list[Lead]:
        enrichers = []
        for enricher_cls in ALL_ENRICHERS:
            enricher = enricher_cls(self.settings, client)
            ok, why = enricher.available()
            if not ok:
                report.skipped[enricher.name] = why
                log.info("skipping enricher %s: %s", enricher.name, why)
                continue
            enrichers.append(enricher)

        if not enrichers:
            return leads

        # Enrichers run in sequence per lead (later ones use earlier results),
        # but leads run concurrently, bounded by the client's semaphore.
        async def enrich_one(lead: Lead) -> Lead:
            for enricher in enrichers:
                lead = await enricher.safe_enrich(lead)
            return lead

        results = await asyncio.gather(
            *(enrich_one(lead) for lead in leads), return_exceptions=True
        )
        enriched = [r for r in results if isinstance(r, Lead)]
        report.enriched = len(enriched)
        report.estimated_cost_usd = round(
            sum(e.cost_per_lead_usd * e.calls for e in enrichers), 2
        )
        return enriched

    async def _backfill_from_websites(
        self, client: PoliteClient, leads: list[Lead]
    ) -> list[Lead]:
        """For leads with a company but no named human, read the /about page."""
        if not self.settings.enabled("discovery", "website"):
            return leads

        source = WebsiteSource(self.settings, client)
        needy = [lead for lead in leads if lead.company_domain and not lead.full_name][:50]
        if not needy:
            return leads

        log.info("backfilling names for %d company-only leads", len(needy))
        results = await asyncio.gather(
            *(source.crawl_domain(lead.company_domain) for lead in needy), return_exceptions=True
        )
        for result in results:
            if isinstance(result, list):
                leads.extend(result)
        return leads

    def _write(self, leads: list[Lead], sink_name: str | None) -> int:
        name = sink_name or self.settings.output.get("sink", "csv")
        sink_cls = SINKS.get(name)
        if not sink_cls:
            raise ValueError(f"unknown sink {name!r}; choose from {list(SINKS)}")

        sink = sink_cls(self.settings)
        ok, why = sink.available()
        if not ok:
            log.error("sink %s unavailable: %s — falling back to CSV", name, why)
            sink = SINKS["csv"](self.settings)

        written = sink.write(leads)
        log.info("wrote %d rows via %s", written, sink.name)
        return written
