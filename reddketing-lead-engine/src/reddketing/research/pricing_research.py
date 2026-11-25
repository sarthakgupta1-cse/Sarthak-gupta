"""Pricing page discovery and price-point sanity checks."""
from __future__ import annotations

import re
from statistics import median

from ..models import PricePoint

PRICE_RE = re.compile(r"(?:US\$|\$|USD\s?)(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:/|per|a)?\s*(mo|month|yr|year|user)?", re.I)
PAGE_HINTS = {
    "pricing": ("pricing", "plans", "price", "subscribe", "premium", "upgrade"),
    "about": ("about", "company", "our-story", "who-we-are", "mission"),
    "team": ("team", "leadership", "founders", "people"),
    "careers": ("careers", "jobs", "join-us", "hiring", "work-with-us"),
    "press": ("press", "newsroom", "media", "news", "blog/announc"),
    "customers": ("customers", "case-studies", "testimonials", "stories", "reviews"),
}


def pick_internal_pages(links: list[tuple[str, str]], root: str, limit_per_kind: int = 1) -> dict[str, str]:
    """From homepage links choose the best URL per page type on the same root domain.

    A link qualifies when its first path segment is a hint word (e.g. /pricing, /about-us,
    /company/team) or its anchor text is exactly a hint word. The shallowest match wins.
    """
    from urllib.parse import urlparse
    from ..utils.normalize import root_domain
    best: dict[str, tuple[int, str]] = {}
    for url, label in links:
        if root_domain(url) != root:
            continue
        segs = [x for x in urlparse(url).path.lower().split("/") if x]
        if len(segs) > 2:
            continue
        label_l = (label or "").lower().strip()
        for kind, hints in PAGE_HINTS.items():
            first = segs[0] if segs else ""
            last = segs[-1] if segs else ""
            hit = any(first == h or first.startswith(h + "-") or last == h for h in hints) or label_l in hints
            if hit:
                depth = len(segs)
                if kind not in best or depth < best[kind][0]:
                    best[kind] = (depth, url.split("#")[0].split("?")[0])
    return {k: v[1] for k, v in best.items()}


def prices_in_text(text: str) -> list[float]:
    out = []
    for m in PRICE_RE.finditer(text or ""):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        if unit in ("yr", "year"):
            value = value / 12
        if 0.5 <= value <= 5000:
            out.append(round(value, 2))
    return out


def paid_price_range(pricing: list[PricePoint]) -> tuple[float, float] | None:
    """(low, high) monthly price of self-serve paid plans; enterprise/custom plans ignored."""
    paid = sorted(p.price_usd_per_month for p in pricing
                  if p.price_usd_per_month and p.price_usd_per_month > 0 and "enterprise" not in p.plan_name.lower())
    if not paid:
        return None
    low = paid[0]
    high = max(low, median(paid)) if len(paid) > 2 else paid[-1]
    return low, high


def format_pricing(pricing: list[PricePoint]) -> str:
    if not pricing:
        return "Not publicly available"
    parts = []
    for p in pricing[:8]:
        price = f"${p.price_usd_per_month:,.2f}/mo" if p.price_usd_per_month is not None else "custom/free"
        parts.append(f"{p.plan_name}: {price}{(' (' + p.billing_note + ')') if p.billing_note else ''}")
    return "; ".join(parts)
