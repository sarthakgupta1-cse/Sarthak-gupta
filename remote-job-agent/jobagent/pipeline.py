"""End-to-end daily run.

  discover():  fetch all sources → evaluate → dedupe (within run + against history)
               → verify new vacancies → re-check older open vacancies → out/state.json
  plan():      state.json → sheet operations, email report, stats, review file, SQLite backup

They are separate steps so the Claude session can review the evaluations, override
any of them (`jobagent override`), and re-plan without fetching everything again.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import sheets as S
from .classify import category_for, is_excluded_title
from .config import ROOT, load_companies, load_settings
from .db import Store
from .dedup import DedupIndex, IndexEntry, keys_for, scope_of, source_rank
from .filters import OK, REJECT, UNCLEAR, check_employment, check_experience, check_location
from .http import Http
from .models import NEEDS_VERIFICATION, QUALIFIED, REJECTED, Evaluation, Job, RawJob
from .report import build as build_report
from .salary import FX, evaluate_salary
from .skills import extract_skills
from .sources import build_sources
from .text import clip
from .verify import check_open, company_site_from, find_original

log = logging.getLogger("jobagent")
OUT = ROOT / "out"

LIMITATIONS = [
    "Searched only public APIs, RSS feeds and employer career-board APIs, plus any pages the session researched by hand.",
    "LinkedIn, Indeed, Glassdoor and FlexJobs need a login or forbid automated access, so they are not scraped.",
    "This does not cover every vacancy worldwide.",
]


# --------------------------------------------------------------------------- evaluation

def evaluate(raw: RawJob, settings: dict, fx: FX) -> Evaluation:
    ev = Evaluation()
    ev.category = category_for(raw.title)
    if not ev.category or is_excluded_title(raw.title):
        ev.decision, ev.reject_bucket, ev.reasons = REJECTED, "relevance", ["not one of your target roles"]
        return ev

    verdicts: list[tuple[str, str, str]] = []           # (verdict, bucket, reason)

    v, label, reason = check_employment(raw)
    ev.employment_type = label
    verdicts.append((v, "type", reason))

    v, ev.remote_eligibility, ev.india_eligibility, reason = check_location(raw)
    verdicts.append((v, "location", reason))

    v, ev.experience, reason = check_experience(raw, settings["experience"])
    verdicts.append((v, "experience", reason))

    sal = evaluate_salary(raw, fx, settings["salary"], full_time=ev.employment_type.startswith("Full-time"))
    ev.original_salary, ev.currency, ev.salary_frequency = sal["original"], sal["currency"], sal["frequency"]
    ev.monthly_usd, ev.monthly_inr = sal["monthly_usd"], sal["monthly_inr"]
    ev.fixed_salary_verified, ev.commission = sal["verified"], sal["commission"]
    ev.notes += [n for n in sal["notes"] if n]
    verdicts.append((sal["verdict"], "salary", sal["reason"]))

    rejects = [(b, r) for v, b, r in verdicts if v == REJECT]
    unclear = [r for v, b, r in verdicts if v == UNCLEAR and r]
    if rejects:
        ev.decision = REJECTED
        ev.reject_bucket = rejects[0][0]
        ev.reasons = [r for _, r in rejects]
    elif unclear:
        ev.decision, ev.reasons = NEEDS_VERIFICATION, unclear
    else:
        ev.decision = QUALIFIED
    return ev


# --------------------------------------------------------------------------- history input

def _values(path: Path | None) -> list[list]:
    if not path or not Path(path).exists():
        return []
    d = json.loads(Path(path).read_text(encoding="utf-8") or "[]")
    if isinstance(d, dict):
        d = d.get("values") or d.get("valueRange", {}).get("values") or []
    return [r for r in d if isinstance(r, list)]


def load_history(index_file, all_ids_file, nv_ids_file):
    idx = DedupIndex()
    index_rows = []
    for row in _values(index_file):
        row = (row + [""] * 9)[:9]
        index_rows.append(row[0])
        if not row[0]:
            continue
        idx.add(IndexEntry(*[str(x) for x in row]))
    all_ids = [str((r or [""])[0]) for r in _values(all_ids_file)]
    nv_ids = [str((r or [""])[0]) for r in _values(nv_ids_file)]
    idx.extra_ids = set(filter(None, all_ids + nv_ids)) - set(idx.by_id)
    return idx, all_ids, nv_ids, index_rows


# --------------------------------------------------------------------------- discover

def discover(index_file=None, all_ids_file=None, nv_ids_file=None, settings_path=None,
             only_sources: list[str] | None = None, tracker_ids_file=None) -> dict:
    settings = load_settings(settings_path)
    tz = ZoneInfo(settings["timezone"])
    now = datetime.now(tz)
    run_date = now.date().isoformat()
    http = Http(settings["http"])
    fx = FX.load(http, settings["salary"]["fx_url"])
    idx, all_ids, nv_ids, index_rows = load_history(index_file, all_ids_file, nv_ids_file)

    sources = build_sources(settings, http, load_companies(settings))
    if only_sources:
        sources = [s for s in sources if any(o.lower() in s.name.lower() for o in only_sources)]
    log.info("fetching %d sources", len(sources))
    with cf.ThreadPoolExecutor(len(sources) or 1) as ex:
        results = list(ex.map(lambda s: s.safe_fetch(), sources))

    src_stats, ok_boards, raws = [], set(), []
    for r in results:
        src_stats.append({"name": r.name, "listings": len(r.jobs), "errors": r.errors[:5], "n_errors": len(r.errors),
                          "sub_sources": r.sub_sources, "ok": r.ok})
        ok_boards |= set(r.ok_boards)
        raws += r.jobs
        log.info("%-32s %4d listings, %d errors", r.name, len(r.jobs), len(r.errors))

    # ---- evaluate + group duplicates within this run
    groups: dict[str, list[Job]] = {}
    alias: dict[str, str] = {}
    counts = {"listings": len(raws), "relevant": 0, "rej_salary": 0, "rej_location": 0, "rej_experience": 0,
              "rej_type": 0, "rej_relevance": 0, "rej_closed": 0, "duplicates": 0}
    today_url_keys: set[str] = set()
    for raw in raws:
        ev = evaluate(raw, settings, fx)
        scope = scope_of(ev.india_eligibility, ev.remote_eligibility)
        job_id, title_key, url_keys = keys_for(raw.company, raw.title, scope, [raw.apply_url, raw.source_url])
        today_url_keys |= set(url_keys)
        job = Job(raw=raw, ev=ev, job_id=job_id, url_key=",".join(url_keys))
        job.title_key, job.scope = title_key, scope  # type: ignore[attr-defined]
        if ev.reject_bucket == "relevance":
            counts["rej_relevance"] += 1
            continue
        counts["relevant"] += 1
        gkey = alias.get(job_id) or next((alias[k] for k in url_keys if k in alias), None) or alias.get("t:" + title_key)
        if gkey is None:
            gkey = job_id
            groups[gkey] = []
        else:
            counts["duplicates"] += 1
        groups[gkey].append(job)
        for k in [job_id, *url_keys, "t:" + title_key]:
            alias.setdefault(k, gkey)

    OUT.mkdir(exist_ok=True)
    with open(OUT / "rejected.jsonl", "w", encoding="utf-8") as fh:     # audit trail for every rejection
        for members in groups.values():
            for j in members:
                if j.ev.decision == REJECTED:
                    fh.write(json.dumps({"bucket": j.ev.reject_bucket, "reason": "; ".join(j.ev.reasons),
                                         "company": j.raw.company, "title": j.raw.title, "source": j.raw.source,
                                         "location": j.raw.location_text[:80], "url": j.raw.apply_url},
                                        ensure_ascii=False) + "\n")

    rank = {QUALIFIED: 0, NEEDS_VERIFICATION: 1, REJECTED: 2}
    best: list[Job] = []
    for members in groups.values():
        members.sort(key=lambda j: (rank[j.ev.decision], source_rank(j)))
        top = members[0]
        official = next((m for m in members if m.raw.is_official), None)
        if official and official is not top:
            top.original_url = official.raw.apply_url
        top.also_listed = sorted({m.raw.source for m in members if m is not top})
        best.append(top)

    # ---- compare with history
    new_jobs, seen_existing, promoted, existing_nv = [], {}, [], []
    requalified: dict[str, str] = {}
    for job in best:
        if job.ev.decision == REJECTED:
            counts["rej_" + (job.ev.reject_bucket or "type")] = counts.get("rej_" + (job.ev.reject_bucket or "type"), 0) + 1
            hit = idx.match(job.job_id, job.title_key, job.url_key.split(","), job.scope)  # type: ignore[attr-defined]
            if hit and idx.by_id[hit].tab in ("N", "NR") and idx.by_id[hit].status.startswith("Open"):
                requalified[hit] = "; ".join(job.ev.reasons)[:100]     # an earlier lead now fails a rule
            continue
        hit = idx.match(job.job_id, job.title_key, job.url_key.split(","), job.scope)  # type: ignore[attr-defined]
        if hit:
            counts["duplicates"] += 1
            seen_existing[hit] = job
            entry = idx.by_id.get(hit)
            if entry and entry.tab == "N" and job.ev.decision == QUALIFIED:   # "NR" = reviewer kept it in NV
                job.job_id = hit
                promoted.append(job)
            elif entry and entry.tab in ("N", "NR"):
                job.job_id = hit
                existing_nv.append(job)          # reviewable: `override <id> qualified` can promote it
            continue
        new_jobs.append(job)

    # ---- verify new vacancies on their original posting
    def _verify(job: Job) -> Job:
        raw = job.raw
        if not job.original_url and not raw.is_official:
            job.original_url = find_original(raw.apply_url or raw.source_url, http)
        target = job.original_url or raw.apply_url or raw.source_url
        status = "Open" if raw.is_official else check_open(target, http)
        if status == "Unknown" and job.original_url:
            status = check_open(raw.apply_url or raw.source_url, http)
        job.ev.notes.append(f"vacancy check: {status}" + ("" if status != "Unknown" else f" (listed on {raw.source} {run_date})"))
        if status == "Closed":
            job.ev.decision, job.ev.reject_bucket = REJECTED, "closed"
            job.ev.reasons = ["posting is closed"]
        elif status == "Unknown" and job.ev.decision == QUALIFIED:
            job.ev.decision = NEEDS_VERIFICATION
            job.ev.reasons = ["original employer posting not yet located/confirmed open"]
        return job

    with cf.ThreadPoolExecutor(6) as ex:
        new_jobs = list(ex.map(_verify, new_jobs))
        promoted = [j for j in ex.map(_verify, promoted) if j.ev.decision == QUALIFIED]   # same bar as new jobs
    counts["rej_closed"] = sum(1 for j in new_jobs if j.ev.decision == REJECTED)
    new_jobs = [j for j in new_jobs if j.ev.decision != REJECTED]

    # ---- re-check previously discovered open vacancies
    status_changes: dict[str, tuple[str, str]] = {}     # job_id -> (status, note)
    for jid in seen_existing:
        status_changes[jid] = ("Open", "seen again today")
    for jid, why in requalified.items():
        if jid not in seen_existing:
            status_changes[jid] = ("Rejected", why)
    to_check = [e for e in idx.by_id.values() if e.status.startswith("Open") and e.job_id not in seen_existing
                and e.job_id not in requalified]
    to_check.sort(key=lambda e: e.last_verified or "")
    budget = settings["liveness"]["max_checks_per_run"]

    def _live(e: IndexEntry):
        m = re.search(r"(greenhouse\.io|lever\.co|ashbyhq\.com)/(?:v\d+/boards/|embed/job_app\?for=)?([\w-]+)", e.check_url or "")
        if m and m.group(2).lower() in ok_boards:
            uk = keys_for("", "", "", [e.check_url])[2]
            if not set(uk) & today_url_keys:
                return e.job_id, ("Closed", "removed from the employer's careers page")
            return e.job_id, ("Open", "still on the employer's careers page")
        st = check_open(e.check_url, http)
        if st == "Unknown" and e.last_verified and (now.date() - datetime.fromisoformat(e.last_verified).date()).days > 21:
            return e.job_id, ("Unverified", f"not seen or reachable since {e.last_verified}")
        return e.job_id, (st, "posting checked")

    with cf.ThreadPoolExecutor(6) as ex:
        for jid, (st, note) in ex.map(_live, to_check[:budget]):
            if st in ("Open", "Closed", "Unverified"):
                status_changes[jid] = (st, note)

    state = {
        "run_date": run_date, "started": now.strftime("%Y-%m-%d %H:%M %Z"), "fx": f"{fx.source}, {fx.as_of}",
        "fx_inr_per_usd": fx.rates.get("INR"),
        "sources": src_stats, "counts": counts, "http_calls": http.calls,
        "new_jobs": [j.to_dict() | {"title_key": j.title_key, "scope": j.scope} for j in new_jobs],  # type: ignore[attr-defined]
        "promoted": [j.to_dict() | {"title_key": j.title_key, "scope": j.scope} for j in promoted],  # type: ignore[attr-defined]
        "existing_nv": [j.to_dict() | {"title_key": j.title_key, "scope": j.scope} for j in existing_nv],  # type: ignore[attr-defined]
        "status_changes": status_changes,
        "history": {"all_ids": all_ids, "nv_ids": nv_ids, "index_rows": index_rows,
                    "tracker_ids": [str((r or [""])[0]) for r in _values(tracker_ids_file)],
                    "index": {k: vars(v) for k, v in idx.by_id.items()}},
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "state.json").write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
    log.info("discover done: %d new, %d promoted, %d status changes", len(new_jobs), len(promoted), len(status_changes))
    return state


# --------------------------------------------------------------------------- plan

def _load_job(d: dict) -> Job:
    j = Job.from_dict(d)
    j.title_key, j.scope = d.get("title_key", ""), d.get("scope", "")  # type: ignore[attr-defined]
    return j


def job_row(job: Job, run_date: str, settings: dict) -> list:
    raw, ev = job.raw, job.ev
    notes = []
    if job.ev.decision == NEEDS_VERIFICATION:
        notes.append("NEEDS VERIFICATION: " + "; ".join(ev.reasons))
    if ev.monthly_inr and ev.currency != "INR":
        notes.append(f"≈ ₹{ev.monthly_inr:,.0f}/month")
    if job.also_listed:
        notes.append("Also listed on: " + ", ".join(job.also_listed))
    if raw.industry:
        notes.append(f"Industry: {raw.industry}")
    notes += [n for n in ev.notes if n]
    link = re.sub(r"[?&]utm_[^&]*", "", job.original_url or raw.apply_url or raw.source_url)
    source = raw.source + ("" if not job.original_url else " (original employer posting linked)")
    return [
        job.job_id, run_date, raw.company, raw.company_website or company_site_from(job.original_url or raw.apply_url),
        raw.title, ev.category, raw.location_text or "Not stated", ev.remote_eligibility, ev.india_eligibility,
        ev.employment_type, ev.experience, ev.original_salary or "Not disclosed", ev.currency, ev.salary_frequency,
        ev.monthly_usd if ev.monthly_usd is not None else "", ev.fixed_salary_verified, ev.commission,
        clip(raw.description, settings["description_max_chars"]), extract_skills(raw.description + " " + raw.title),
        raw.posted_at, run_date, "Open", source, link, raw.recruiter or "",
        "No – awaiting updated resume", "No – awaiting updated resume", "Not Applied", " | ".join(notes),
    ]


def plan(settings_path=None, sheet_url: str = "") -> dict:
    settings = load_settings(settings_path)
    state = json.loads((OUT / "state.json").read_text(encoding="utf-8"))
    run_date = state["run_date"]
    new_jobs = [_load_job(d) for d in state["new_jobs"]]
    promoted = [_load_job(d) for d in state["promoted"]]
    hist = state["history"]
    index = {k: IndexEntry(**v) for k, v in hist["index"].items()}

    new_q = [j for j in new_jobs if j.ev.decision == QUALIFIED]
    new_nv = [j for j in new_jobs if j.ev.decision == NEEDS_VERIFICATION]

    ops: list[dict] = []
    # 1. new rows (kept raw for the bulk .xlsx path; the append ops are the small-day fallback)
    new_rows = {
        S.ALL_JOBS: [job_row(j, run_date, settings) for j in new_q + promoted],
        S.NEEDS: [job_row(j, run_date, settings) for j in new_nv],
        S.TRACKER: [[j.job_id, j.raw.company, j.raw.title, "", "", "", "Not Applied", "", "", j.raw.recruiter or "", ""]
                    for j in new_q + promoted],
    }
    ops += S.append_op(S.ALL_JOBS, new_rows[S.ALL_JOBS], S.LAST_JOB_COL)
    ops += S.append_op(S.NEEDS, new_rows[S.NEEDS], S.LAST_JOB_COL)
    ops += S.append_op(S.TRACKER, new_rows[S.TRACKER], S.col_letter(len(S.TRACKER_COLUMNS) - 1))

    # 2. Last Verified Date + Job Status on existing rows (by live row order)
    closed_labels, changes_all, changes_nv, idx_changes, idx_dates, dropped_labels = [], {}, {}, {}, {}, []
    for jid, (st, note) in state["status_changes"].items():
        e = index.get(jid)
        if st == "Closed":
            status, verified = f"Closed (detected {run_date})", run_date
        elif st == "Unverified":
            status, verified = f"Unverified – {note}", (e.last_verified if e else run_date)
        elif st == "Rejected":
            status, verified = f"No longer qualifies – {note}", run_date
            dropped_labels.append(f"{e.label if e else jid} ({note})")
        else:
            status, verified = "Open", run_date
        if e and e.status.startswith("Open") and st == "Closed":
            closed_labels.append(e.label or jid)
        target = changes_nv if (e and e.tab in ("N", "NR")) else changes_all
        target[jid] = [verified, status]
        if e:
            new_status = {"Unverified": "Unverified", "Rejected": "Rejected"}.get(st, status)
            if new_status == e.status:              # unchanged: only the date moves (small write)
                if e.last_verified != verified:
                    idx_dates[jid] = [verified]
            else:
                gone = st in ("Closed", "Rejected")
                idx_changes[jid] = [new_status, "" if gone else e.check_url, verified, "" if gone else e.label]
        if e and e.last_verified == verified and target.get(jid) and e.status.startswith(status.split(" ")[0]):
            target.pop(jid)                          # same-day retry: nothing to write
    new_index_rows = []
    for j in promoted:            # NV row is marked moved; index entry re-added under tab A
        changes_nv[j.job_id] = [run_date, "Moved to All Jobs (verified)"]
        e = index.get(j.job_id)
        if e:
            idx_changes[j.job_id] = ["Moved", "", run_date, ""]
            new_index_rows.append([j.job_id, e.title_key, e.url_key, e.scope, "A", "Open", e.check_url, run_date, e.label])
    ops += S.range_updates(S.ALL_JOBS, S.VERIFIED_COL, S.STATUS_COL, hist["all_ids"], changes_all)
    ops += S.range_updates(S.NEEDS, S.VERIFIED_COL, S.STATUS_COL, hist["nv_ids"], changes_nv)

    # 3. hidden _Index: status updates for known rows, then new rows
    ops += S.range_updates(S.INDEX, "F", "I", hist["index_rows"], idx_changes)
    ops += S.range_updates(S.INDEX, "H", "H", hist["index_rows"], {k: v for k, v in idx_dates.items() if k not in idx_changes})
    for j in new_q + new_nv:
        reviewed = any(n.startswith("reviewed:") for n in j.ev.notes)
        tab = "A" if j.ev.decision == QUALIFIED else ("NR" if reviewed else "N")
        check = (j.original_url or j.raw.apply_url or j.raw.source_url).split("?utm")[0]
        new_index_rows.append([j.job_id, j.title_key, j.url_key, j.scope, tab, "Open",  # type: ignore[attr-defined]
                               check, run_date, f"{j.raw.company} — {j.raw.title}"[:90]])
    ops += S.append_op(S.INDEX, new_index_rows, "I")
    new_rows[S.INDEX] = new_index_rows
    existing = {S.ALL_JOBS: len(hist["all_ids"]), S.NEEDS: len(hist["nv_ids"]),
                S.TRACKER: len(hist.get("tracker_ids", [])), S.INDEX: len(hist["index_rows"])}
    manifest = S.write_bulk_xlsx(OUT / "sync.xlsx", new_rows, existing)
    (OUT / "bulk.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    # 4. stats + report
    c = state["counts"]
    srcs = state["sources"]
    stats = {
        "sources_searched": sum(s["sub_sources"] for s in srcs),
        "sources_failed": sum(1 for s in srcs if not s["ok"]) + sum(s["n_errors"] for s in srcs if s["ok"]),
        "listings": c["listings"], "relevant": c["relevant"], "duplicates": c["duplicates"],
        "companies": len({j.raw.company for j in new_q + promoted}),
        "rej_salary": c.get("rej_salary", 0), "rej_location": c.get("rej_location", 0),
        "rej_experience": c.get("rej_experience", 0), "rej_type": c.get("rej_type", 0),
        "rej_relevance": c.get("rej_relevance", 0), "rej_closed": c.get("rej_closed", 0),
        "new_qualified": len(new_q), "new_nv": len(new_nv), "promoted": len(promoted),
        "closed": len(closed_labels),
        "high_paying": sum(1 for j in new_q + promoted if (j.ev.monthly_usd or 0) > settings["salary"]["high_pay_usd"]),
        "priority_band": sum(1 for j in new_q + promoted if j.ev.monthly_usd and 500 <= j.ev.monthly_usd <= 1000),
        "fx": state["fx"] + (f" (1 USD = ₹{state['fx_inr_per_usd']:.2f})" if state.get("fx_inr_per_usd") else ""),
        "source_detail": srcs,
    }
    tz = ZoneInfo(settings["timezone"])
    date_label = datetime.fromisoformat(run_date).strftime(settings["report"]["date_format"]).lstrip("0")
    subject = settings["report"]["subject_template"].format(date=date_label)
    stats["dropped"] = len(dropped_labels)
    # a lead verified today is a new verified opportunity for the reader, wherever it was first seen
    text, html_body = build_report(date_label, subject, new_q + promoted, new_nv,
                                   closed_labels + [f"no longer meets your rules: {d}" for d in dropped_labels],
                                   [], stats, sheet_url, LIMITATIONS)
    errors = "; ".join(f"{s['name']}: {s['n_errors']} errors" for s in srcs if s["n_errors"])[:450]
    stats_row = [run_date, state["started"], stats["sources_searched"], stats["sources_failed"], stats["listings"],
                 stats["companies"], stats["duplicates"], stats["rej_salary"], stats["rej_location"],
                 stats["rej_experience"], stats["rej_type"], stats["rej_relevance"], stats["new_qualified"] + stats["promoted"],
                 stats["new_nv"], stats["closed"], stats["high_paying"], stats["priority_band"],
                 "{SHEETS_STATUS}", "{EMAIL_STATUS}", errors or "none"]

    OUT.mkdir(exist_ok=True)
    (OUT / "plan.json").write_text(json.dumps({"run_date": run_date, "ops": ops}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "stats_row.json").write_text(json.dumps({"op": "append", "range": f"{S.q(S.STATS)}!A1:T1", "values": S._clean([stats_row])},
                                                   ensure_ascii=False), encoding="utf-8")
    (OUT / "report.txt").write_text(text, encoding="utf-8")
    (OUT / "report.html").write_text(html_body, encoding="utf-8")
    (OUT / "subject.txt").write_text(subject, encoding="utf-8")
    (OUT / "stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    _write_review(new_q, new_nv, promoted, closed_labels, stats)
    _write_db(state, new_jobs + promoted, index, run_date, stats)
    for j in new_q + new_nv:
        _write_jd(j)
    log.info("plan: %d ops, %d new qualified, %d needs verification", len(ops), len(new_q), len(new_nv))
    return {"ops": len(ops), "new_qualified": len(new_q), "new_nv": len(new_nv), "closed": len(closed_labels),
            "promoted": len(promoted), "subject": subject}


def _write_review(new_q, new_nv, promoted, closed, stats) -> None:
    lines = ["# Review before syncing",
             "Check each QUALIFIED job against its evidence. If one is wrong, run:",
             "`python -m jobagent override <JOB_ID> needs_verification|rejected \"reason\"` then `python -m jobagent plan`.", ""]
    for title, jobs in (("QUALIFIED", new_q), ("NEEDS VERIFICATION", new_nv), ("PROMOTED", promoted)):
        lines.append(f"## {title} ({len(jobs)})")
        for j in jobs:
            ev = j.ev
            lines.append(f"- **{j.job_id}** {j.raw.company} — {j.raw.title} [{ev.category}] via {j.raw.source}")
            lines.append(f"  - India: {ev.india_eligibility} | remote: {ev.remote_eligibility} | type: {ev.employment_type} | exp: {ev.experience}")
            lines.append(f"  - pay: {ev.original_salary or '—'} → {('$%.0f/mo' % ev.monthly_usd) if ev.monthly_usd else '—'} ({ev.fixed_salary_verified})"
                         + (f" | NEEDS: {'; '.join(ev.reasons)}" if ev.reasons else ""))
            lines.append(f"  - link: {j.original_url or j.raw.apply_url}")
            lines.append(f"  - text: {clip(j.raw.description, 260)}")
        lines.append("")
    lines.append(f"Closed today: {', '.join(closed) or 'none'}")
    (OUT / "review.md").write_text("\n".join(lines), encoding="utf-8")


def _write_db(state, jobs, index, run_date, stats) -> None:
    db_path = OUT / f"jobs-{run_date}.db"
    if db_path.exists():
        db_path.unlink()
    st = Store(db_path)
    for e in index.values():
        st.upsert_history(e)
    for j in jobs:
        st.save_job(j, run_date)
        st.sighting(run_date, j.job_id, j.raw.source, j.raw.source_url, j.ev.decision, "; ".join(j.ev.reasons))
    for jid, (s, note) in state["status_changes"].items():
        st.set_status(jid, s, run_date)
    st.log_run(run_date, state["started"], datetime.now().isoformat(timespec="seconds"),
               {k: v for k, v in stats.items() if k != "source_detail"})
    st.close()


def _safe(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s).strip("_")[:60] or "Unknown"


def _write_jd(job: Job) -> None:
    d = OUT / "Job_Applications" / _safe(job.raw.company) / _safe(job.raw.title)
    d.mkdir(parents=True, exist_ok=True)
    (d / "Job_Description.txt").write_text(
        f"{job.raw.title}\n{job.raw.company}\nJob ID: {job.job_id}\nSource: {job.raw.source}\n"
        f"Apply: {job.original_url or job.raw.apply_url}\n\n{job.raw.description}\n", encoding="utf-8")


# --------------------------------------------------------------------------- overrides

def override(job_id: str, decision: str, reason: str) -> bool:
    p = OUT / "state.json"
    state = json.loads(p.read_text(encoding="utf-8"))
    for d in state["new_jobs"]:
        if d["job_id"] == job_id:
            d["ev"]["decision"] = decision
            d["ev"]["reasons"] = [reason]
            d["ev"]["notes"].append(f"reviewed: {reason}")
            if decision == REJECTED:
                state["new_jobs"].remove(d)
            p.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
            return True
    # a job already in Needs Verification: a reviewer can promote it after checking the posting
    for d in state.get("existing_nv", []):
        if d["job_id"] == job_id and decision == QUALIFIED:
            d["ev"]["decision"] = QUALIFIED
            d["ev"]["reasons"] = []
            d["ev"]["notes"].append(f"reviewed: {reason}")
            state["existing_nv"].remove(d)
            state["promoted"].append(d)
            p.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
            return True
    return False


def set_original(job_id: str, url: str, settings_path=None) -> str:
    """Attach the employer's original posting (found by the session) to a new job and verify it."""
    settings = load_settings(settings_path)
    http = Http(settings["http"])
    p = OUT / "state.json"
    state = json.loads(p.read_text(encoding="utf-8"))
    for d in state["new_jobs"]:
        if d["job_id"] != job_id:
            continue
        status = check_open(url, http)
        d["original_url"] = url
        d["ev"]["notes"].append(f"original posting located; vacancy check: {status}")
        if status == "Closed":
            state["new_jobs"].remove(d)
        elif status == "Open":
            d["ev"]["reasons"] = [r for r in d["ev"]["reasons"] if "still open" not in r and "original" not in r]
            if d["ev"]["decision"] == NEEDS_VERIFICATION and not d["ev"]["reasons"]:
                d["ev"]["decision"] = QUALIFIED
        p.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
        return f"{job_id}: original posting {status}; decision now {d['ev']['decision'] if status != 'Closed' else 'removed (closed)'}"
    return f"{job_id}: not among today's new jobs"
