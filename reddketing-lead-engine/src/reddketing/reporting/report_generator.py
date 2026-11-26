"""Builds the daily email (HTML + plain text) from the rows stored in Google Sheets.

Rendering from stored rows (not in-memory objects) means a retry after an email
failure re-sends exactly what was saved, without re-running research.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import TEMPLATE_DIR


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def money(v) -> str:
    x = _f(v)
    if not x:
        return str(v) if v else "Not publicly available"
    if x >= 1e6:
        return f"${x / 1e6:,.1f}M".replace(".0M", "M")
    if x >= 1e3:
        return f"${x / 1e3:,.0f}K" if x >= 1e4 else f"${x / 1e3:,.1f}K".replace(".0K", "K")
    return f"${x:,.0f}"


def mrr_range(row: dict) -> str:
    lo, hi = row.get("Estimated MRR Minimum"), row.get("Estimated MRR Maximum")
    if not _f(lo) and not _f(hi):
        return "Not publicly available"
    if row.get("Revenue Confidence") == "Assumed" or not _f(hi):
        return f"At least {money(lo)} per month (assumed, not verified)"
    return f"{money(lo)}–{money(hi)} per month"


def lines(text) -> list[str]:
    return [l for l in str(text or "").splitlines() if l.strip()]


NA_VALUES = {"", "not publicly available", "not found in public sources", "not publicly verified",
             "no decision-makers identified in public sources", "none identified from public sources"}


def _present(v) -> bool:
    return str(v or "").strip().lower() not in NA_VALUES


def mrr_short(row: dict) -> str:
    """Compact revenue for the summary table: "$60K–$980K (low confidence)" or "Assumed ≥ $50K"."""
    lo, hi = row.get("Estimated MRR Minimum"), row.get("Estimated MRR Maximum")
    if not _f(lo) and not _f(hi):
        return "Not publicly available"
    conf = str(row.get("Revenue Confidence") or "")
    if conf == "Assumed" or not _f(hi):
        return f"Assumed ≥ {money(lo)}"
    return f"{money(lo)}–{money(hi)} ({conf.lower()} confidence)"


def subreddits_short(row: dict) -> str:
    """Subreddit names without the '(audience fit, not source-verified)' notes."""
    text = str(row.get("Relevant Subreddits") or "")
    if not _present(text):
        return ""
    return ", ".join(part.split(" (")[0].strip() for part in text.split(";") if part.strip())


def contact_summary(row: dict) -> dict:
    """First named decision-maker with title and LinkedIn, how many more, and the public email."""
    people = [l for l in lines(row.get("Decision-Maker Designations")) if _present(l)]
    first = people[0].rstrip(" —-") if people else ""
    name = first.split(" — ")[0].strip() if first else ""
    linkedin = ""
    for l in lines(row.get("LinkedIn URLs")):
        if ": http" in l and (not name or l.startswith(name)):
            linkedin = l.split(": ", 1)[1].strip()
            break
    email = ""
    for l in lines(row.get("Public Business Email")):
        word = next((w for w in l.replace("(", " ").split() if "@" in w), "")
        if word:
            email = word.strip(".,;")
            break
    return {"person": first.replace(" — ", ", "), "linkedin": linkedin, "more": max(0, len(people) - 1),
            "email": email}


@dataclass
class ReportData:
    run_date: str
    revenue_rows: list[dict]
    funded_rows: list[dict]
    rejected_rows: list[dict] = field(default_factory=list)
    duplicates_avoided: int = 0
    insufficient: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    api_errors: list[str] = field(default_factory=list)
    sheet_url: str = ""
    usage: dict = field(default_factory=dict)

    def summary(self) -> dict:
        all_rows = self.revenue_rows + self.funded_rows
        scores = [_f(r.get("Total Opportunity Score")) for r in all_rows]
        conf = Counter(r.get("Revenue Confidence", "Insufficient") for r in self.revenue_rows)
        return {
            "revenue_count": len(self.revenue_rows), "funded_count": len(self.funded_rows),
            "duplicates": self.duplicates_avoided, "rejected": len(self.rejected_rows),
            "highest": int(max(scores)) if scores else 0,
            "average": round(sum(scores) / len(scores), 1) if scores else 0,
            "confidence": {k: conf.get(k, 0) for k in ("High", "Medium", "Low")},
        }

    def top(self, n: int = 5) -> list[dict]:
        tagged = [dict(r, _list="Revenue-qualified") for r in self.revenue_rows] + \
                 [dict(r, _list="Recently funded") for r in self.funded_rows]
        return sorted(tagged, key=lambda r: _f(r.get("Total Opportunity Score")), reverse=True)[:n]


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters.update(money=money, mrr_range=mrr_range, lines=lines, mrr_short=mrr_short,
                       subreddits_short=subreddits_short, contact_summary=contact_summary)
    return env


def render_daily_report(data: ReportData, subject: str) -> tuple[str, str]:
    env = _env()
    ctx = {"d": data, "s": data.summary(), "top": data.top(), "subject": subject}
    return env.get_template("daily_report.html").render(**ctx), env.get_template("daily_report.txt").render(**ctx)


def render_failure_report(run_date: str, error: str, stage: str, details: list[str], sheet_url: str,
                          subject: str) -> tuple[str, str]:
    env = _env()
    ctx = {"run_date": run_date, "error": error, "stage": stage, "details": details, "sheet_url": sheet_url,
           "subject": subject}
    return env.get_template("failure_report.html").render(**ctx), env.get_template("failure_report.txt").render(**ctx)
