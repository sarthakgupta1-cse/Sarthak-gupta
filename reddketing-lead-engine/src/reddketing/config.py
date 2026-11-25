"""Configuration loading: YAML settings + environment secrets."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
TEMPLATE_DIR = PROJECT_ROOT / "templates"
DEFAULT_CACHE_DIR = PROJECT_ROOT / ".cache"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader for local runs (never overrides real env vars)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


@dataclass
class Settings:
    raw: dict[str, Any]
    categories: dict[str, Any]
    cache_dir: Path = field(default=DEFAULT_CACHE_DIR)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    # Convenience accessors -------------------------------------------------
    @property
    def llm_provider(self) -> str:
        return (os.getenv(self.get("llm.provider_env", "LLM_PROVIDER")) or self.get("llm.default_provider")).lower()

    @property
    def search_provider(self) -> str:
        return (os.getenv(self.get("search.provider_env", "SEARCH_PROVIDER")) or self.get("search.default_provider")).lower()

    def llm_setting(self, key: str, default: Any = None) -> Any:
        """llm.<key>, overridden by llm.provider_overrides.<provider>.<key> when present."""
        override = self.get(f"llm.provider_overrides.{self.llm_provider}.{key}")
        return override if override is not None else self.get(f"llm.{key}", default)

    @property
    def llm_model(self) -> str:
        override = os.getenv("LLM_MODEL")
        return override or self.get(f"llm.models.{self.llm_provider}")

    @property
    def recipient(self) -> str | None:
        return os.getenv(self.get("email.recipient_env", "REPORT_RECIPIENT")) or None

    @property
    def monthly_budget_usd(self) -> float:
        return float(self.get("budget.monthly_budget_inr")) / float(self.get("budget.inr_per_usd"))

    @property
    def non_company_domains(self) -> set[str]:
        return {d.lower() for d in self.get("discovery.non_company_domains", [])}


def load_settings(config_dir: Path | None = None, *, load_env_file: bool = True) -> Settings:
    config_dir = config_dir or CONFIG_DIR
    if load_env_file:
        _load_dotenv(PROJECT_ROOT / ".env")
    raw = yaml.safe_load((config_dir / "settings.yaml").read_text())
    categories = yaml.safe_load((config_dir / "categories.yaml").read_text())
    cache_dir = Path(os.getenv("REDDKETING_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
    return Settings(raw=raw, categories=categories, cache_dir=cache_dir)


def env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None
