"""Enricher contract: take a Lead, return it with more filled in.

An enricher must never throw into the pipeline and must never blank a field
that already had a value — enrichment only ever adds.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..config import Settings
from ..http import PoliteClient
from ..models import Lead


class Enricher(ABC):
    name: str = "base"
    # Roughly what one lead costs in API credits, for the run cost estimate.
    cost_per_lead_usd: float = 0.0

    def __init__(self, settings: Settings, client: PoliteClient) -> None:
        self.settings = settings
        self.client = client
        self.log = logging.getLogger(f"founder_agent.enrich.{self.name}")
        self.calls = 0

    def available(self) -> tuple[bool, str]:
        if not self.settings.enabled("enrichment", self.name):
            return False, "disabled in config.yaml"
        return True, ""

    def should_run(self, lead: Lead) -> bool:
        """Skip work we don't need — every skipped call is money saved."""
        return True

    @abstractmethod
    async def enrich(self, lead: Lead) -> Lead:
        ...

    async def safe_enrich(self, lead: Lead) -> Lead:
        if not self.should_run(lead):
            return lead
        try:
            self.calls += 1
            return await self.enrich(lead)
        except Exception as exc:
            self.log.warning("enrichment failed for %s: %s", lead.full_name or lead.company, exc)
            lead.notes.append(f"{self.name}: failed")
            return lead
