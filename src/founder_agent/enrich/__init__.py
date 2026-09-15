"""Enrichment: turn a thin lead into one you can actually contact."""

from .apollo import ApolloEnricher
from .base import Enricher
from .hunter import HunterEnricher
from .proxycurl import ProxycurlEnricher
from .socials import SocialsEnricher

# Order matters: identity first (who are they), then email, then socials.
ALL_ENRICHERS = [ProxycurlEnricher, ApolloEnricher, HunterEnricher, SocialsEnricher]

__all__ = [
    "ALL_ENRICHERS",
    "ApolloEnricher",
    "Enricher",
    "HunterEnricher",
    "ProxycurlEnricher",
    "SocialsEnricher",
]
