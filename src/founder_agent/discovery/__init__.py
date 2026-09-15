"""Discovery: find founders who have made themselves publicly findable."""

from .base import DiscoverySource
from .github_ import GitHubSource
from .hackernews import HackerNewsSource
from .producthunt import ProductHuntSource
from .website import WebsiteSource

ALL_SOURCES = [HackerNewsSource, ProductHuntSource, GitHubSource, WebsiteSource]

__all__ = [
    "ALL_SOURCES",
    "DiscoverySource",
    "GitHubSource",
    "HackerNewsSource",
    "ProductHuntSource",
    "WebsiteSource",
]
