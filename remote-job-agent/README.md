# Remote Job Agent

Finds full-time remote **content writing, social media, affiliate, SEO/growth and digital marketing** jobs
open to applicants in India. It checks each one against strict filters, removes duplicates, keeps a Google
Sheet up to date and emails a daily report. It runs every day at **08:00 IST** in Anthropic's cloud, so your
computer can stay off.

It never applies to jobs, never messages recruiters and never pays for anything.

## How a daily run works

```
08:00 IST  scheduled Claude cloud session (fresh container)
   │
   ├─ 1. retry guard ── Daily Statistics + Gmail sent folder: has today already run?
   ├─ 2. load history ─ hidden _Index tab + Job ID columns (the durable dedup memory)
   ├─ 3. web research ─ LinkedIn posts, Wellfound, YC, career pages: opened by hand, facts only
   ├─ 4. discover ───── python -m jobagent discover
   │      sources → evaluate (relevance, type, location, experience, salary)
   │      → dedupe (within run + against history) → verify original posting is open
   │      → re-check older open jobs (closed / still open)
   ├─ 5. review ─────── Claude checks every "qualified" job's evidence; overrides if wrong
   ├─ 6. sync sheet ─── new rows: .xlsx → Drive upload → copied into the sheet (bulk, exact)
   │                    existing rows: small update ops (dates, statuses) via the Sheets connector
   ├─ 7. documents ──── tailored CV + cover letter (once profile.yaml exists)
   ├─ 8. backup ─────── SQLite snapshot, state, plan, report, log → Google Drive
   ├─ 9. email ──────── Gmail connector → daily report (no application links)
   └─ 10. record ────── row in Daily Statistics
```

The full operating procedure is in [RUNBOOK.md](RUNBOOK.md).

**Why a Claude scheduled task rather than GitHub Actions:** your Gmail, Sheets and Drive are already connected to
Claude through OAuth, so there is no Google Cloud project, no refresh token and no secret to store or leak. The run
also gets a reviewer that can read postings and search for originals. Running Python alone can't do that judgement.
There is no extra cost; the run uses your existing Claude plan's allowance.

## Filter rules

| Rule | Where | Behaviour |
|---|---|---|
| Role relevance | `classify.py` | Title must match one of the 6 category groups (≈50 titles and synonyms). Engineers, sales reps, moderators, AI-trainer gigs, designers etc. are excluded. |
| Remote + India | `filters.check_location` | Must be fully remote. India listed, or genuinely worldwide/APAC. Restriction phrases in the description ("must be based in the US", "authorized to work in the UK", "Remote – US", "EMEA only"…) override a board's "Worldwide" label. Unclear → Needs Verification. |
| Full-time | `filters.check_employment` | Full-time employees or full-time contractors. Part-time, internships, freelance, temporary, commission-only → rejected. "Contract" with no hours stated → Needs Verification. |
| Experience | `filters.check_experience` | Senior/lead/head/director titles rejected. 0–1 year OK. 1–2 years only if the posting welcomes freshers/juniors. Manager titles with no years stated → Needs Verification. |
| Fixed salary | `salary.py` | Bottom of the range, base pay only. INR roles ≥ ₹50,000/month, others ≥ $500/month. OTE/commission never counted. No salary or no pay frequency → Needs Verification. Nothing is estimated. Live FX rates (open.er-api.com) with the date recorded. |
| Open vacancy | `verify.py` | Employer career-page listings count as verified. Aggregator listings must have the employer's original posting located and open, otherwise Needs Verification. |

## Duplicate detection

Each vacancy gets three keys (`dedup.py`): **Job ID** = hash(company | title | remote scope), **title key** =
hash(company | title), and **URL keys** = hash of each canonical URL (tracking parameters stripped). A listing
matches an existing one by ID, by any shared URL, or by title key when the scopes don't contradict each other
(for example "India" vs "LATAM" are different openings). Within one run, duplicates from several boards merge
into one row: the employer's own posting becomes the application link and the others go under "Also listed on".
History lives in the sheet, so a job is never "new" twice.

## Sources

| Source | Method | Notes |
|---|---|---|
| Himalayas | public search API, `country=IN`, 25 queries | best structured data (salary, seniority, location restrictions); job pages block bots, so they are never fetched |
| We Work Remotely | RSS | "Anywhere" label is checked against the description |
| Remote OK | public API | salary fields trusted only if the description repeats them |
| Jobicy | public API, 4 industries | |
| Working Nomads | public API | |
| Remotive | public API | free feed is ~15 jobs; ≤4 calls/day per their terms |
| 31 Greenhouse, 7 Lever, 32 Ashby career boards | public job-board APIs | the employers' own postings (`config/companies.yaml`), e.g. GitLab, Notion, Zapier, Canonical, Wise, Groww, Coinbase, ElevenLabs |
| Web research | the Claude session reads pages | LinkedIn posts, Wellfound, YC, Indeed, career pages. Only pages it actually opened, no logins, no CAPTCHA bypass |

**Not supported:** automated LinkedIn, Indeed, Glassdoor, FlexJobs and Naukri scraping (login walls or terms of
service forbid it). FlexJobs is also paid. Their postings reach the system only through the bounded web-research step.

## Where things live

| What | Where |
|---|---|
| Code | this folder (public repo, no personal data) |
| Jobs, history, statuses | Google Sheet "Worldwide Remote Job Opportunities" (hidden `_Index` tab = dedup memory) |
| SQLite database | built fresh each run at `out/jobs-<date>.db`, archived daily to Drive "Remote Job Agent/Run Backups" |
| Run logs | `logs/run-<date>.log`, archived to the same Drive folder. Each run is also a row in "Daily Statistics" |
| CVs / cover letters | Drive "Remote Job Agent/Job_Applications/<Company>/<Job_Title>/" |
| Your profile (facts for CVs) | `profile/profile.yaml`, gitignored. The master copy goes in your Drive folder |

## Commands

```bash
pip install -r requirements.txt
python -m jobagent run                       # discover + plan with no history (local test)
python -m jobagent discover --index out/index.json --all-ids out/all_ids.json --nv-ids out/nv_ids.json
python -m jobagent override RJ-XXXX needs_verification "reason"
python -m jobagent set-original RJ-XXXX https://company.com/careers/123
python -m jobagent plan --sheet-url URL      # sheet ops, report, stats, review, db
python -m jobagent ops                       # print the sheet operations to apply
python -m jobagent docs                      # CVs + cover letters (needs profile/profile.yaml)
python -m jobagent bulk-requests '{"NV": 123}' # paste uploaded rows into place (see RUNBOOK step 6)
python -m pytest -q                          # 29 tests
```

## CVs and cover letters

`jobagent docs` builds `Customized_CV.docx/.pdf`, `Cover_Letter.docx/.pdf` and `Job_Description.txt` per qualified
job. Every experience line comes word for word from `profile/profile.yaml`. Tailoring only selects and reorders
bullets and skills to match the posting's keywords, so it can't invent anything. **This step is off until you
upload an updated resume.** Copy `profile/profile.example.yaml`, fill it from your real CV, and put it in the
"Remote Job Agent" Drive folder as `profile.yaml`.

## Limitations

- Coverage is wide but not "every job worldwide". Most remote marketing postings don't publish a salary, and
  under your rules those go to **Needs Verification**, never the main sheet.
- Location and experience checks are pattern-based. The daily review step catches most mistakes, and
  `out/rejected.jsonl` keeps every rejection with its reason for auditing.
- Closed-job detection is definitive for employer career boards. For other sites it checks the page, and a job
  not seen or reachable for 21 days is marked "Unverified".
