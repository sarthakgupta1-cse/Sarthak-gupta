"""Every discovery source yields Leads and knows when to sit a run out."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..config import Settings
from ..http import PoliteClient
from ..models import Lead


class DiscoverySource(ABC):
    name: str = "base"

    def __init__(self, settings: Settings, client: PoliteClient) -> None:
        self.settings = settings
        self.client = client
        self.log = logging.getLogger(f"founder_agent.discovery.{self.name}")

    @property
    def config(self) -> dict:
        block = self.settings.discovery.get(self.name, {})
        return block if isinstance(block, dict) else {}

    def available(self) -> tuple[bool, str]:
        """(can_run, reason_if_not). Missing credentials are a skip, not a crash."""
        if not self.settings.enabled("discovery", self.name):
            return False, "disabled in config.yaml"
        return True, ""

    @abstractmethod
    async def discover(self, limit: int) -> list[Lead]:
        ...
