"""Builds the day's discovery query plan by rotating through categories and templates."""
from __future__ import annotations

import hashlib
import random
from datetime import date


def daily_rng(run_date: date, salt: str = "") -> random.Random:
    seed = int(hashlib.sha256(f"{run_date.isoformat()}|{salt}".encode()).hexdigest()[:12], 16)
    return random.Random(seed)


def plan_discovery_queries(categories_cfg: dict, run_date: date, n_queries: int) -> list[tuple[str, str]]:
    """Returns [(category_key, query)] — deterministic per date, rotating across categories."""
    rng = daily_rng(run_date, "queries")
    templates = categories_cfg.get("query_templates", [])
    pool: list[tuple[str, str]] = []
    for key, cat in categories_cfg.get("categories", {}).items():
        weight = 2 if cat.get("reddit_relevance") == "high" else 1
        for phrase in cat.get("phrases", []):
            pool.extend([(key, phrase)] * weight)
    rng.shuffle(pool)
    seen_phrases: set[str] = set()
    plan: list[tuple[str, str]] = []
    for key, phrase in pool:
        if phrase in seen_phrases:
            continue
        seen_phrases.add(phrase)
        template = rng.choice(templates)
        plan.append((key, template.format(category=phrase, year=run_date.year)))
        if len(plan) >= n_queries:
            break
    return plan
