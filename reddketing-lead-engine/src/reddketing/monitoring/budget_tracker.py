"""Monthly + per-run API budget enforcement.

Month-to-date spend comes from the Daily Run Log sheet (sum of the estimated cost
column for the current month) so it survives across stateless GitHub runs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    """Raised when a paid call is attempted after the budget/run cap is hit."""


@dataclass
class Usage:
    search_queries: int = 0
    search_cost: float = 0.0
    llm_calls: int = 0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_cost: float = 0.0
    http_fetches: int = 0
    by_provider: dict = field(default_factory=dict)

    @property
    def total_cost(self) -> float:
        return round(self.search_cost + self.llm_cost, 5)


class BudgetTracker:
    NORMAL, REDUCED, STOPPED = "normal", "reduced", "stopped"

    def __init__(self, settings, month_spend_before_usd: float = 0.0):
        self.settings = settings
        self.monthly_budget = settings.monthly_budget_usd
        self.month_before = float(month_spend_before_usd or 0.0)
        self.reduce_at = float(settings.get("budget.reduce_at_fraction", 0.8))
        self.stop_at = float(settings.get("budget.stop_at_fraction", 1.0))
        self.llm_prices = settings.get("pricing.llm_per_million_tokens", {})
        self.search_prices = settings.get("pricing.search_per_query", {})
        self.usage = Usage()
        self.max_llm_calls = int(settings.get("llm.max_calls_per_run"))
        self.warnings: list[str] = []
        self.set_month_before(self.month_before)

    def set_month_before(self, usd: float) -> None:
        """Set month-to-date spend (read from the run log) and recompute this run's limits."""
        self.month_before = float(usd or 0.0)
        self.start_mode = self.mode
        if self.start_mode == self.REDUCED:
            self.max_queries = int(self.settings.get("budget.reduced_max_queries"))
        else:
            self.max_queries = int(self.settings.get("search.max_queries_per_run"))
        if self.start_mode != self.NORMAL:
            self._check_thresholds()

    # ------------------------------------------------------------------ state
    @property
    def month_total(self) -> float:
        return self.month_before + self.usage.total_cost

    @property
    def fraction_used(self) -> float:
        return self.month_total / self.monthly_budget if self.monthly_budget else 1.0

    @property
    def mode(self) -> str:
        f = self.fraction_used
        if f >= self.stop_at:
            return self.STOPPED
        if f >= self.reduce_at:
            return self.REDUCED
        return self.NORMAL

    def max_candidates(self) -> int:
        if self.start_mode == self.REDUCED:
            return int(self.settings.get("budget.reduced_max_candidates"))
        return int(self.settings.get("targets.max_candidates_to_research"))

    # ------------------------------------------------------------------ checks
    def search_allowed(self, provider: str) -> bool:
        if provider == "none":
            return False
        return self.mode != self.STOPPED and self.usage.search_queries < self.max_queries

    def remaining_queries(self) -> int:
        return max(0, self.max_queries - self.usage.search_queries) if self.mode != self.STOPPED else 0

    def llm_allowed(self) -> bool:
        return self.mode != self.STOPPED and self.usage.llm_calls < self.max_llm_calls

    def require_search(self, provider: str) -> None:
        if not self.search_allowed(provider):
            raise BudgetExceeded(f"search budget exhausted (mode={self.mode}, "
                                 f"queries={self.usage.search_queries}/{self.max_queries})")

    def require_llm(self) -> None:
        if not self.llm_allowed():
            raise BudgetExceeded(f"LLM budget exhausted (mode={self.mode}, "
                                 f"calls={self.usage.llm_calls}/{self.max_llm_calls})")

    # ------------------------------------------------------------------ recording
    def record_search(self, provider: str, queries: int = 1) -> None:
        cost = float(self.search_prices.get(provider, 0.0)) * queries
        self.usage.search_queries += queries
        self.usage.search_cost += cost
        self.usage.by_provider[provider] = self.usage.by_provider.get(provider, 0) + queries
        self._check_thresholds()

    def record_llm(self, model: str, input_tokens: int, output_tokens: int) -> None:
        price = self.llm_prices.get(model)
        if price is None:
            # Unknown model: be conservative and charge a high default rather than zero.
            price = {"input": 1.0, "output": 5.0}
            self._warn(f"No price configured for model {model}; using conservative $1/$5 per 1M tokens.")
        cost = (input_tokens * float(price["input"]) + output_tokens * float(price["output"])) / 1_000_000
        self.usage.llm_calls += 1
        self.usage.llm_input_tokens += int(input_tokens)
        self.usage.llm_output_tokens += int(output_tokens)
        self.usage.llm_cost += cost
        self._check_thresholds()

    def _warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)
            logger.warning(msg)

    def _check_thresholds(self) -> None:
        f = self.fraction_used
        if f >= self.stop_at:
            self._warn(f"Monthly API budget reached ({f:.0%} of ${self.monthly_budget:.2f}). Paid calls stopped.")
        elif f >= self.reduce_at:
            self._warn(f"Monthly API budget at {f:.0%}; optional research calls reduced.")

    def summary(self) -> dict:
        u = self.usage
        return {
            "mode_at_start": self.start_mode,
            "mode_now": self.mode,
            "search_queries": u.search_queries,
            "search_cost_usd": round(u.search_cost, 4),
            "llm_calls": u.llm_calls,
            "llm_input_tokens": u.llm_input_tokens,
            "llm_output_tokens": u.llm_output_tokens,
            "llm_cost_usd": round(u.llm_cost, 4),
            "http_fetches": u.http_fetches,
            "run_cost_usd": round(u.total_cost, 4),
            "month_to_date_usd": round(self.month_total, 4),
            "monthly_budget_usd": round(self.monthly_budget, 2),
            "fraction_used": round(self.fraction_used, 4),
        }
