"""The daily pipeline: discover -> filter -> research -> qualify -> store -> email -> log.

Recovery model
--------------
* `_RunState` (one row per IST date) records the last completed stage.
* Researched profiles are checkpointed to disk as they complete, so a crash
  mid-research does not re-spend on companies already done.
* Sheet writes are idempotent (Record ID / Company Key checks).
* The email is rendered from rows stored in Sheets, so an email retry never
  triggers new research or new inserts.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from .database import schema
from .database.duplicate_detection import DuplicateIndex, DuplicateMatch, KnownCompany, reconsider_date
from .database.records import daily_row, funded_row, master_row, rejected_row
from .database.run_state import LockHeld, RunState, RunStateStore
from .discovery.candidate_filter import filter_candidates, prioritise
from .discovery.funding_discovery import collect_funding_items
from .discovery.startup_discovery import DiscoveryFailed, collect_launch_items, extract_candidates
from .models import Candidate, CompanyProfile, Confidence
from .monitoring.budget_tracker import BudgetExceeded, BudgetTracker
from .providers.llm_provider import LLMConfigError, LLMError
from .qualification.opportunity_scoring import score_profile
from .qualification.reddketing_fit import exclusion_reason
from .qualification.scale_signals import (assume_floor, below_floor_by_own_data, has_10k_users, scale_signals,
                                          size_exclusion)
from .reporting.report_generator import ReportData, render_daily_report, render_failure_report
from .research.company_research import research_company
from .research.funding_research import funding_is_recent
from .utils.normalize import core_name, normalize_name

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

LIMITATIONS = [
    "Revenue figures are estimates from public signals unless marked as disclosed; confidence labels apply.",
    "Website traffic is reported only where a public source states it (no paid traffic tool is configured).",
    "Reddit suitability is assessed from public company information; no Reddit listening was performed.",
    "Emails are listed only when printed on a public page; none are guessed. LinkedIn URLs only when found in sources.",
]


@dataclass
class Services:
    settings: object
    sheets: object
    budget: BudgetTracker
    http: object
    search: object
    free: object
    llm_factory: Callable[[], object]
    sender_factory: Callable[[], object] | None
    _llm: object = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = self.llm_factory()
        return self._llm


@dataclass
class ResearchOutcome:
    revenue: list[CompanyProfile] = field(default_factory=list)
    funded: list[CompanyProfile] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    duplicates: list[tuple[str, str, DuplicateMatch, str]] = field(default_factory=list)
    insufficient: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    discovered: int = 0
    researched: int = 0


@dataclass
class RunResult:
    status: str
    run_date: str
    revenue_count: int = 0
    funded_count: int = 0
    duplicates: int = 0
    rejected: int = 0
    email_status: str = ""
    sheets_status: str = ""
    message: str = ""
    report_html_path: str = ""


# ============================================================== helpers
def now_ist() -> datetime:
    return datetime.now(IST)


def month_spend(sheets, run_date: str, settings=None) -> float:
    """Month-to-date spend from the run log, minus the search provider's free monthly credit."""
    total = queries = 0.0
    for r in sheets.read_records(schema.RUN_LOG):
        if str(r.get("Execution Date", "")).startswith(run_date[:7]):
            try:
                total += float(r.get("Estimated API Cost (USD)") or 0)
                queries += float(r.get("Search Queries") or 0)
            except ValueError:
                pass
    if settings is not None:
        price = float(settings.get(f"pricing.search_per_query.{settings.search_provider}", 0) or 0)
        credit = float(settings.get("search.monthly_free_credit_usd", 0) or 0)
        total -= min(credit, queries * price)
    return max(0.0, total)


def revenue_qualifies(p: CompanyProfile, settings) -> bool:
    threshold = float(settings.get("targets.revenue_threshold_mrr_usd", 50000))
    min_score = float(settings.get("qualification.min_total_score_revenue_list", 45))
    min_ind = int(settings.get("qualification.min_independent_indicators_low_confidence", 2))
    rev = p.revenue
    if rev.mrr_low is None or not p.scores or p.scores.total < min_score:
        return False
    if rev.confidence in (Confidence.HIGH, Confidence.MEDIUM):
        return (rev.mrr_mid or 0) >= threshold
    if rev.confidence == Confidence.LOW:
        return rev.mrr_low >= threshold and rev.independent_indicators >= min_ind
    return False


class Checkpoint:
    """Disk checkpoint of researched profiles for the current date (persisted via actions/cache)."""

    def __init__(self, cache_dir: Path, run_date: str):
        self.dir = Path(cache_dir) / "runs" / run_date
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / f"{normalize_name(key) or 'unknown'}.json"

    def load(self, key: str):
        path = self._path(key)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                if data.get("type") == "profile":
                    return CompanyProfile.model_validate(data["profile"])
                return data.get("error", "research failed earlier today")
            except (ValueError, KeyError):
                return None
        return None

    def save(self, key: str, value) -> None:
        payload = ({"type": "profile", "profile": value.model_dump(mode="json")} if isinstance(value, CompanyProfile)
                   else {"type": "error", "error": str(value)})
        self._path(key).write_text(json.dumps(payload, default=str))


# ============================================================== research phase
def research_phase(svc: Services, run_date: date, index: DuplicateIndex) -> ResearchOutcome:
    s, budget = svc.settings, svc.budget
    out = ResearchOutcome()
    blocklist = s.non_company_domains
    n_queries = int(s.get("search.discovery_queries_per_run", 12))
    if budget.start_mode == BudgetTracker.REDUCED:
        n_queries = max(3, n_queries // 2)

    funding_items = collect_funding_items(s, svc.free, svc.search, run_date,
                                          news_queries=2 if budget.start_mode == BudgetTracker.NORMAL else 0)
    launch_items = collect_launch_items(s, svc.free, svc.search, run_date, n_queries)
    logger.info("discovery items collected", extra={"data": {"funding": len(funding_items), "launch": len(launch_items)}})
    cands: list[Candidate] = []
    batch = int(s.llm_setting("discovery_batch_size", 45))
    discovery_failures: list[str] = []
    for group, kwargs in ((funding_items, {"funding": True}), (launch_items, {})):
        if not group:
            continue
        try:
            cands += extract_candidates(svc.llm, group, blocklist, batch_size=batch, **kwargs)
        except BudgetExceeded as exc:
            out.errors.append(str(exc))
            break
        except DiscoveryFailed as exc:
            discovery_failures.append(str(exc))
            out.errors.append(str(exc))
    if discovery_failures and not cands:
        # Nothing could be read: report a failure rather than an empty "success".
        raise LLMError("AI model unavailable during discovery: " + discovery_failures[-1])
    cands = cands[: int(s.get("targets.max_discovery_candidates", 150))]
    out.discovered = len(cands)

    fr = filter_candidates(cands, index, svc.search, s, max_domain_lookups=8, today=run_date)
    for c, m in fr.duplicates:
        out.duplicates.append((c.name, c.domain, m, ", ".join(c.discovery_channels)))
    for c, reason in fr.dropped:
        out.insufficient.append(f"{c.name}: {reason}")

    chosen = prioritise(fr.accepted, budget.max_candidates())
    checkpoint = Checkpoint(s.cache_dir, run_date.isoformat())
    lookback = int(s.get("targets.funding_lookback_days", 180))
    reconsider_days = int(s.get("targets.reconsider_after_days", 90))
    per_company_q = int(s.get("search.research_queries_per_company", 2))

    llm_failures = fresh = 0
    backups: list[CompanyProfile] = []
    for c in chosen:
        if fresh >= 3 and llm_failures == fresh:
            # The first companies all failed in the LLM: stop and report a failure (a retry resumes here).
            raise LLMError(f"AI model failed for the first {fresh} companies researched; last error: {out.errors[-1]}")
        if not budget.llm_allowed():
            out.errors.append("LLM budget/run cap reached; remaining candidates deferred to a later run")
            break
        profile = checkpoint.load(c.domain or c.name)
        if profile is None:
            fresh += 1
            reserve = 4  # keep a few queries for funding/domain lookups later in the run
            q_budget = max(0, min(per_company_q, budget.remaining_queries() - reserve))
            try:
                profile = research_company(c, http=svc.http, search=svc.search, free=svc.free, llm=svc.llm,
                                           settings=s, today=run_date, query_budget=q_budget)
            except BudgetExceeded as exc:
                out.errors.append(str(exc))
                break
            except LLMConfigError:
                raise
            except LLMError as exc:
                out.errors.append(f"{c.name}: {exc}")
                llm_failures += 1
                out.rejected.append(rejected_row(c.name, run_date.isoformat(), f"research failed ({exc})",
                                                 website=c.website, domain=c.domain, reconsiderable=True,
                                                 reconsider_after=reconsider_date(run_date, 1)))
                out.researched += 1
                continue  # not checkpointed, so a retry researches it again
            except Exception as exc:  # noqa: BLE001 — one bad site must not kill the run
                logger.exception("research crashed for %s", c.name)
                out.errors.append(f"{c.name}: unexpected {exc.__class__.__name__}: {exc}")
                profile = f"research failed ({exc.__class__.__name__})"
            checkpoint.save(c.domain or c.name, profile)
        out.researched += 1

        if isinstance(profile, str):
            out.rejected.append(rejected_row(c.name, run_date.isoformat(), profile, website=c.website, domain=c.domain,
                                             reconsiderable=True, reconsider_after=reconsider_date(run_date, 14)))
            continue

        ex = profile.extraction
        m = index.match(ex.company_name, profile.domain, aliases=ex.aliases, parent=ex.parent_company or "",
                        extra_domains=profile.all_domains)
        if m and not DuplicateIndex.rejected_is_reconsiderable(m, index, run_date):
            out.duplicates.append((ex.company_name, profile.domain, m, ", ".join(c.discovery_channels)))
            continue

        score_profile(profile, run_date, lookback)
        too_big = size_exclusion(profile, s)
        reason = exclusion_reason(profile, s) or too_big
        permanent = any(k in reason.lower() for k in ("restricted", "shut down", "spam", "not an operating"))
        if reason:
            profile.list_type, profile.rejection_reason = "rejected", reason
            out.rejected.append(rejected_row(profile, run_date.isoformat(), reason, reconsiderable=not permanent,
                                             reconsider_after=reconsider_date(run_date, 365 if too_big
                                                                              else reconsider_days)))
        elif revenue_qualifies(profile, s):
            profile.list_type = "revenue"
            out.revenue.append(profile)
        elif funding_is_recent(profile, run_date, lookback) and \
                profile.scores.total >= float(s.get("qualification.min_total_score_funded_list", 45)):
            profile.list_type = "funded"
            out.funded.append(profile)
        else:
            # Not proven from evidence: kept as a reserve to fill the daily quota with an assumed $50K floor.
            backups.append(profile)
        # Make same-run duplicates impossible (e.g. two names for one company).
        index.add(KnownCompany(ex.company_name, set(profile.all_domains) | {profile.domain},
                               {normalize_name(ex.company_name)} | {normalize_name(a) for a in ex.aliases},
                               core_name(ex.company_name), normalize_name(ex.parent_company or ""), "this run"))

    # Final selection with quota overflow deferred (not lost, not emailed).
    n_rev = int(s.get("targets.revenue_qualified_per_day", 15))
    n_fund = int(s.get("targets.funded_per_day", 5))
    # Fill the revenue list to the daily target: companies without public revenue evidence are assumed
    # to meet the floor, strongest business-scale signals first. Labelled "Assumed" everywhere.
    floor = float(s.get("targets.revenue_threshold_mrr_usd", 50000))
    min_signals = int(s.get("qualification.min_scale_signals_for_assumption", 1))
    ranked = sorted(((scale_signals(p), p) for p in backups),
                    key=lambda t: (has_10k_users(t[1]), len(t[0]), t[1].scores.total), reverse=True)
    for signals, p in ranked:
        if below_floor_by_own_data(p, floor):
            p.list_type = "rejected"
            out.rejected.append(rejected_row(p, run_date.isoformat(),
                                             f"Own data shows below ${floor:,.0f}/month "
                                             f"(up to ${p.revenue.mrr_high:,.0f})", reconsiderable=True,
                                             reconsider_after=reconsider_date(run_date, 90)))
            continue
        if len(out.revenue) < n_rev and len(signals) >= min_signals:
            assume_floor(p, floor, signals)
            p.list_type = "revenue"
            out.revenue.append(p)
            out.insufficient.append(f"{p.extraction.company_name}: revenue assumed at the ${floor:,.0f} floor "
                                    f"({len(signals)} business-scale signal(s))")
        else:
            why = (f"Fewer business-scale signals than the companies selected ({len(signals)})"
                   if len(out.revenue) >= n_rev else "No business-scale signals found in public sources")
            p.list_type = "rejected"
            out.rejected.append(rejected_row(p, run_date.isoformat(), why, reconsiderable=True,
                                             reconsider_after=reconsider_date(run_date, 7)))
    # Prefer the $50K-$1M band; $1M-$5M companies rank after it.
    band_max = float(s.get("size_limits.target_max_mrr_usd", 1_000_000))
    out.revenue.sort(key=lambda p: ((p.revenue.mrr_mid or 0) <= band_max, p.scores.total), reverse=True)
    out.funded.sort(key=lambda p: p.scores.total, reverse=True)
    for overflow in out.revenue[n_rev:] + out.funded[n_fund:]:
        out.rejected.append(rejected_row(overflow, run_date.isoformat(), "Qualified but daily quota reached — deferred",
                                         reconsiderable=True, reconsider_after=reconsider_date(run_date, 1)))
    out.revenue, out.funded = out.revenue[:n_rev], out.funded[:n_fund]
    out.errors += svc.search.errors + getattr(svc.free, "errors", [])[:10] + getattr(svc.llm, "errors", [])
    return out


# ============================================================== write phase
def write_phase(sheets, out: ResearchOutcome, run_date: str) -> dict:
    """Idempotent: re-running for the same date never inserts the same record twice."""
    master = sheets.read_records(schema.MASTER)
    master_keys = {r.get("Company Key") for r in master}
    # Final duplicate check against a fresh read (guards against a concurrent/manual insert).
    fresh_index = DuplicateIndex.from_sheets(master)
    keep_rev, keep_fund = [], []
    for p in out.revenue + out.funded:
        m = fresh_index.match(p.extraction.company_name, p.domain, extra_domains=p.all_domains)
        if m and p.domain not in master_keys:
            out.duplicates.append((p.extraction.company_name, p.domain, m, "final check"))
            continue
        if p.domain in master_keys:
            existing = next(r for r in master if r.get("Company Key") == p.domain)
            if existing.get("First Discovered Date") != run_date:
                out.duplicates.append((p.extraction.company_name, p.domain,
                                       DuplicateMatch(existing.get("Company Name", ""), p.domain, "already in master",
                                                      "strong", schema.MASTER), "final check"))
                continue
        (keep_rev if p.list_type == "revenue" else keep_fund).append(p)
    out.revenue, out.funded = keep_rev, keep_fund

    new_master = [master_row(p, run_date, p.list_type) for p in out.revenue + out.funded if p.domain not in master_keys]
    sheets.append_rows(schema.MASTER, new_master)

    def append_new(tab, rows, key="Record ID"):
        existing = {r.get(key) for r in sheets.read_records(tab)}
        fresh = [r for r in rows if r.get(key) not in existing]
        sheets.append_rows(tab, fresh)
        return len(fresh)

    counts = {
        "daily": append_new(schema.DAILY, [daily_row(p, run_date) for p in out.revenue]),
        "funded": append_new(schema.FUNDED, [funded_row(p, run_date) for p in out.funded]),
        "rejected": append_new(schema.REJECTED, out.rejected),
        "master": len(new_master),
    }
    dup_rows = [{"Detection Date": run_date, "Newly Discovered Company": n, "New Domain": d,
                 "Matched Existing Company": m.existing_name, "Matched Domain": m.existing_domain,
                 "Matching Name": m.matching_name, "Duplicate Reason": m.reason, "Match Strength": m.strength,
                 "Matched Tab": m.tab, "Discovery Channel": ch} for n, d, m, ch in out.duplicates]
    existing_dups = {(r.get("Detection Date"), r.get("Newly Discovered Company")) for r in sheets.read_records(schema.DUPLICATES)}
    dup_rows = [r for r in dup_rows if (r["Detection Date"], r["Newly Discovered Company"]) not in existing_dups]
    sheets.append_rows(schema.DUPLICATES, dup_rows)
    counts["duplicates"] = len(dup_rows)
    return counts


# ============================================================== email phase
def build_report_from_sheets(sheets, run_date: str, *, extra_notes: dict | None = None) -> tuple[ReportData, list[str]]:
    master = {r.get("Company Key"): r for r in sheets.read_records(schema.MASTER)}
    blocked: list[str] = []

    def eligible(row) -> bool:
        m = master.get(row.get("Official Domain"))
        emailed = (m or {}).get("Emailed Date", "")
        if emailed and emailed != run_date:
            blocked.append(row.get("Company Name", ""))
            return False
        return True

    rev = [r for r in sheets.read_records(schema.DAILY) if r.get("Discovery Date") == run_date and eligible(r)]
    fund = [r for r in sheets.read_records(schema.FUNDED) if r.get("Discovery Date") == run_date and eligible(r)]
    key = lambda r: float(r.get("Total Opportunity Score") or 0)  # noqa: E731
    rev.sort(key=key, reverse=True)
    fund.sort(key=key, reverse=True)
    rejected = [r for r in sheets.read_records(schema.REJECTED) if r.get("Rejection Date") == run_date]
    dups = [r for r in sheets.read_records(schema.DUPLICATES) if r.get("Detection Date") == run_date]
    notes = extra_notes or {}
    data = ReportData(run_date=run_date, revenue_rows=rev, funded_rows=fund, rejected_rows=rejected,
                      duplicates_avoided=len(dups), insufficient=notes.get("insufficient", []),
                      limitations=LIMITATIONS + notes.get("limitations", []), api_errors=notes.get("errors", []),
                      sheet_url=sheets.url, usage=notes.get("usage", {}))
    return data, blocked


def mark_emailed(sheets, data: ReportData, run_date: str) -> None:
    for r in data.revenue_rows + data.funded_rows:
        sheets.update_where(schema.MASTER, "Company Key", r.get("Official Domain"),
                            {"Emailed Date": run_date, "Last Updated Date": run_date})


# ============================================================== orchestration
def run_pipeline(svc: Services, *, run_date: date | None = None, force_lock: bool = False,
                 dry_run_dir: Path | None = None) -> RunResult:
    s, sheets = svc.settings, svc.sheets
    started = now_ist()
    run_date = run_date or started.date()
    rd = run_date.isoformat()
    run_id = f"{rd}-{os.getenv('GITHUB_RUN_ID', 'local')}"
    subject = s.get("email.subject_template").format(date=rd)
    result = RunResult(status="started", run_date=rd)
    store = RunStateStore(sheets)
    state: RunState | None = None
    out = ResearchOutcome()
    stage = "setup"
    log_errors: list[str] = []
    try:
        sheets.ensure_schema()
        existing = store.get(rd)
        if existing and existing.get("Stage") in ("emailed", "completed") and not force_lock:
            result.status, result.message = "already_completed", f"Run for {rd} already emailed; nothing to do."
            return result
        state = store.acquire(rd, run_id, force=force_lock)
        svc.budget.set_month_before(month_spend(sheets, rd, s))

        if not state.reached("sheets_written"):
            if svc.budget.mode == BudgetTracker.STOPPED:
                raise BudgetExceeded(f"Monthly API budget exhausted (${svc.budget.month_total:.2f} of "
                                     f"${svc.budget.monthly_budget:.2f}); research skipped until next month.")
            stage = "research"
            # Rows written earlier *today* by a partially failed attempt are not "history":
            # excluding them lets the retry re-select the same companies (writes are idempotent).
            def hist(tab, col):
                return [r for r in sheets.read_records(tab) if r.get(col) != rd]
            index = DuplicateIndex.from_sheets(hist(schema.MASTER, "First Discovered Date"),
                                               hist(schema.REJECTED, "Rejection Date"),
                                               hist(schema.DAILY, "Discovery Date"), hist(schema.FUNDED, "Discovery Date"))
            out = research_phase(svc, run_date, index)
            store.advance(state, "researched")
            stage = "sheets_write"
            counts = write_phase(sheets, out, rd)
            result.sheets_status = f"ok ({counts})"
            store.advance(state, "sheets_written")
        else:
            result.sheets_status = "already written earlier today (resumed)"

        stage = "email"
        notes = {"insufficient": out.insufficient, "errors": out.errors + svc.budget.warnings,
                 "usage": svc.budget.summary()}
        data, blocked = build_report_from_sheets(sheets, rd, extra_notes=notes)
        if blocked:
            data.api_errors.append(f"Final duplicate check removed previously emailed: {', '.join(blocked)}")
        html, text = render_daily_report(data, subject)
        if dry_run_dir is not None:
            dry_run_dir.mkdir(parents=True, exist_ok=True)
            path = dry_run_dir / f"report-{rd}.html"
            path.write_text(html)
            (dry_run_dir / f"report-{rd}.txt").write_text(text)
            result.report_html_path = str(path)
            result.email_status = "dry run — not sent"
        else:
            recipient = s.recipient
            if not recipient:
                raise RuntimeError("REPORT_RECIPIENT is not set")
            message_id = svc.sender_factory().send(recipient, subject, html, text)
            result.email_status = f"sent ({message_id})"
        mark_emailed(sheets, data, rd)
        store.advance(state, "emailed", **{"Email Message ID": result.email_status[:200]})
        result.revenue_count, result.funded_count = len(data.revenue_rows), len(data.funded_rows)
        result.duplicates, result.rejected = data.duplicates_avoided, len(data.rejected_rows)
        result.status = "success"
        store.advance(state, "completed")
        store.release(state, "success")
    except LockHeld as exc:
        result.status, result.message = "locked", str(exc)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("run failed at stage %s", stage)
        result.status, result.message = "failed", f"{exc.__class__.__name__}: {exc}"
        log_errors.append(result.message)
        if not result.email_status:
            result.email_status = "not sent (run failed)"
        if not result.sheets_status:
            result.sheets_status = "not written" if stage in ("setup", "research", "sheets_write") else "ok"
        if state is not None:
            try:
                store.release(state, "failed", result.message)
            except Exception:  # noqa: BLE001
                log_errors.append("could not update run state")
        _send_failure(svc, rd, result.message, stage, out, dry_run_dir)
    finally:
        _append_run_log(svc, result, run_id, rd, started, out, log_errors)
    return result


def _send_failure(svc: Services, rd: str, error: str, stage: str, out: ResearchOutcome, dry_run_dir) -> None:
    s = svc.settings
    subject = s.get("email.failure_subject_template").format(date=rd)
    details = out.errors[:10] + svc.budget.warnings
    try:
        url = svc.sheets.url
    except Exception:  # noqa: BLE001
        url = ""
    html, text = render_failure_report(rd, error, stage, details, url, subject)
    if dry_run_dir is not None:
        Path(dry_run_dir).mkdir(parents=True, exist_ok=True)
        (Path(dry_run_dir) / f"failure-{rd}.html").write_text(html)
        return
    try:
        if s.recipient and svc.sender_factory:
            svc.sender_factory().send(s.recipient, subject, html, text)
    except Exception as exc:  # noqa: BLE001
        logger.error("failure notification could not be sent: %s", exc)


def _append_run_log(svc: Services, result: RunResult, run_id: str, rd: str, started: datetime,
                    out: ResearchOutcome, log_errors: list[str]) -> None:
    if result.status == "already_completed":
        return
    u = svc.budget.summary()
    row = {
        "Run ID": run_id, "Execution Date": rd, "Start Time (IST)": started.strftime("%Y-%m-%d %H:%M:%S"),
        "Completion Time (IST)": now_ist().strftime("%Y-%m-%d %H:%M:%S"), "Status": result.status,
        "Companies Discovered": out.discovered, "Companies Researched": out.researched,
        "Companies Accepted": len(out.revenue) + len(out.funded), "Companies Rejected": len(out.rejected),
        "Duplicates Detected": len(out.duplicates), "Funding Discoveries": len(out.funded),
        "Search Queries": u["search_queries"], "LLM Calls": u["llm_calls"], "LLM Input Tokens": u["llm_input_tokens"],
        "LLM Output Tokens": u["llm_output_tokens"], "HTTP Fetches": getattr(svc.http, "requests_made", 0),
        "Estimated API Cost (USD)": u["run_cost_usd"], "Month-to-Date Cost (USD)": u["month_to_date_usd"],
        "Budget Mode": u["mode_now"], "Errors": "\n".join((log_errors + out.errors)[:30]),
        "Email Delivery Status": result.email_status, "Google Sheets Update Status": result.sheets_status,
        "Notes": result.message,
    }
    try:
        svc.sheets.append_rows(schema.RUN_LOG, [row])
    except Exception as exc:  # noqa: BLE001
        logger.error("could not write run log: %s", exc, extra={"data": row})
