"""Command-line entry point.

  python -m reddketing.main run                # production daily run
  python -m reddketing.main run --dry-run      # in-memory sheets, report written to out/, no email
  python -m reddketing.main doctor             # check configuration and credentials (no paid calls)
  python -m reddketing.main init-sheet         # create tabs + headers in the spreadsheet
  python -m reddketing.main test-email         # send a short delivery test (contains no leads)
  python -m reddketing.main budget             # month-to-date API spend
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .config import PROJECT_ROOT, env, load_settings
from .monitoring.budget_tracker import BudgetTracker
from .monitoring.logger import get_logger, setup_logging

logger = get_logger("reddketing")


def build_services(settings, *, dry_run: bool = False):
    from .database.google_sheets import GoogleSheets, MemorySheets
    from .pipeline import Services
    from .providers.llm_provider import build_llm_provider
    from .providers.news_feeds import FreeSources
    from .providers.search_provider import build_search_provider
    from .reporting.gmail_client import build_sender
    from .utils.http import HttpClient

    budget = BudgetTracker(settings)
    sheets = MemorySheets() if dry_run else GoogleSheets()
    cache = settings.cache_dir
    return Services(settings=settings, sheets=sheets, budget=budget, http=HttpClient(settings, cache),
                    search=build_search_provider(settings, budget, cache), free=FreeSources(settings),
                    llm_factory=lambda: build_llm_provider(settings, budget, cache),
                    sender_factory=None if dry_run else build_sender)


def cmd_run(args, settings) -> int:
    from .pipeline import run_pipeline
    svc = build_services(settings, dry_run=args.dry_run)
    run_date = date.fromisoformat(args.date) if args.date else None
    out_dir = Path(args.out) if args.dry_run else None
    result = run_pipeline(svc, run_date=run_date, force_lock=args.force, dry_run_dir=out_dir)
    logger.info("run finished", extra={"data": result.__dict__})
    print(f"status={result.status} revenue={result.revenue_count} funded={result.funded_count} "
          f"duplicates={result.duplicates} email={result.email_status} {result.message}")
    if result.report_html_path:
        print(f"report: {result.report_html_path}")
    return 0 if result.status in ("success", "already_completed", "locked") else 1


def cmd_doctor(args, settings) -> int:
    ok = True

    def line(name, status, detail=""):
        nonlocal ok
        ok = ok and status != "MISSING" and status != "ERROR"
        print(f"  [{status:^7}] {name}{(' — ' + detail) if detail else ''}")

    print("Reddketing lead engine — configuration check (no paid API calls are made)\n")
    line("REPORT_RECIPIENT", "ok" if settings.recipient else "MISSING")
    line("SPREADSHEET_ID", "ok" if env("SPREADSHEET_ID") else "MISSING")
    line("GOOGLE_SERVICE_ACCOUNT_JSON", "ok" if env("GOOGLE_SERVICE_ACCOUNT_JSON") else "MISSING")
    from reddketing.reporting.gmail_client import email_transport
    transport = email_transport()
    if transport == "smtp":
        line("SMTP credentials", "ok" if env("SMTP_APP_PASSWORD") and (env("SMTP_USERNAME") or env("GMAIL_SENDER")) else "MISSING")
    else:
        missing = [k for k in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "GMAIL_SENDER") if not env(k)]
        line("Gmail API OAuth", "ok" if not missing else "MISSING", ", ".join(missing))
    key = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}.get(settings.llm_provider)
    line(f"LLM provider {settings.llm_provider} ({settings.llm_model})", "ok" if key and env(key) else "MISSING", key or "")
    skey = {"brave": "BRAVE_SEARCH_API_KEY", "serper": "SERPER_API_KEY"}.get(settings.search_provider)
    line(f"Search provider {settings.search_provider}",
         "ok" if (skey and env(skey)) else ("warn" if settings.search_provider == "none" else "MISSING"),
         "free sources only" if settings.search_provider == "none" else (skey or ""))
    line("Product Hunt token (optional)", "ok" if env("PRODUCT_HUNT_TOKEN") else "skip")
    if env("SPREADSHEET_ID") and env("GOOGLE_SERVICE_ACCOUNT_JSON") and not args.offline:
        try:
            from .database.google_sheets import GoogleSheets
            gs = GoogleSheets()
            gs.read_records(gs.sh.worksheets()[0].title)
            line("Google Sheets access", "ok", gs.url)
        except Exception as exc:  # noqa: BLE001
            line("Google Sheets access", "ERROR", str(exc)[:300])
    print(f"\nMonthly budget: ₹{settings.get('budget.monthly_budget_inr')} ≈ ${settings.monthly_budget_usd:.2f}")
    print("Result:", "READY" if ok else "NOT READY — fix the MISSING/ERROR items above")
    return 0 if ok else 1


def cmd_init_sheet(args, settings) -> int:
    from .database.google_sheets import GoogleSheets
    gs = GoogleSheets()
    gs.ensure_schema()
    print(f"Spreadsheet ready: {gs.url}")
    return 0


def cmd_test_email(args, settings) -> int:
    from .reporting.gmail_client import build_sender
    if not settings.recipient:
        print("REPORT_RECIPIENT is not set")
        return 1
    subject = "Reddketing lead engine — email delivery test"
    text = ("This is a delivery test from the Reddketing lead engine. It contains no company data.\n"
            "If you received it, email delivery is configured correctly.")
    html = f"<p>{text.replace(chr(10), '<br>')}</p>"
    mid = build_sender().send(settings.recipient, subject, html, text)
    print(f"sent: {mid}")
    return 0


def cmd_budget(args, settings) -> int:
    from .database.google_sheets import GoogleSheets
    from .pipeline import month_spend, now_ist
    gs = GoogleSheets()
    spent = month_spend(gs, now_ist().date().isoformat())
    b = BudgetTracker(settings, spent)
    print(f"Month-to-date estimated API spend: ${spent:.2f} of ${b.monthly_budget:.2f} "
          f"({b.fraction_used:.0%}); mode = {b.mode}")
    return 0


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reddketing")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true", help="in-memory sheets, no email; report saved to --out")
    r.add_argument("--out", default=str(PROJECT_ROOT / "out"))
    r.add_argument("--date", help="override run date (YYYY-MM-DD, IST)")
    r.add_argument("--force", action="store_true", help="take over a stale lock / re-run a completed date")
    d = sub.add_parser("doctor")
    d.add_argument("--offline", action="store_true", help="skip the live Google Sheets check")
    sub.add_parser("init-sheet")
    sub.add_parser("test-email")
    sub.add_parser("budget")
    args = parser.parse_args(argv)
    setup_logging(args.log_level)
    settings = load_settings()
    handler = {"run": cmd_run, "doctor": cmd_doctor, "init-sheet": cmd_init_sheet,
               "test-email": cmd_test_email, "budget": cmd_budget}[args.command]
    return handler(args, settings)


if __name__ == "__main__":
    sys.exit(cli())
