# Architecture

## Pipeline

```
 GitHub Actions cron 02:30 UTC (08:00 IST) / manual dispatch      concurrency group = single writer
   │
   ▼
 setup ─ ensure tabs ─ _RunState lock for the IST date ─ month-to-date spend → budget mode
   │
   ▼
 DISCOVERY (free first)
   funding: TechCrunch/EU-Startups/VentureBeat/Tech in Asia/Inc42 RSS, Google News RSS, 2 news searches
   growth:  Hacker News Show HN (Algolia), Product Hunt (token), ~12 rotated category searches
   LLM extracts company names + websites from item lists (item IDs mapped back in code)
   │
   ▼
 FILTER  in-batch merge → historical dedupe (before spending) → domain resolution → restricted words
         → prioritise (funding leads + multi-channel candidates) → cap 40 (20 in reduced mode)
   │
   ▼
 RESEARCH per company (checkpointed to disk)
   official site + pricing/about/team/careers/press pages (robots.txt respected, 1 req/s/host)
   ≤ 2 searches: financial signals, people; ≤ 2 third-party articles opened; Google News headlines
   LLM (Haiku 5.5, JSON schema) → ResearchExtraction with source IDs on every fact
   VALIDATION in code: unknown source IDs dropped; numbers must appear in the cited source;
   people must be named in it; LinkedIn/email must appear verbatim; funding needs a source
   │
   ▼
 REVENUE ESTIMATE (deterministic) → CONFIDENCE → EXCLUSIONS → SCORE (0–100)
   │
   ▼
 SELECT  revenue list (≤ 15) · funded list (≤ 5) · rejected (with reason, reconsider date)
   │
   ▼
 WRITE   final dedupe vs fresh Master read → Master → Daily / Funded → Rejected → Duplicate log
         (idempotent by Company Key / Record ID)                              stage = sheets_written
   │
   ▼
 EMAIL   rebuilt from stored rows; rows already emailed on an earlier date are removed;
         HTML + plain text; Master "Emailed Date" set                         stage = emailed
   │
   ▼
 RUN LOG row (counts, usage, cost, errors, statuses)                          stage = completed
```

On any exception: `_RunState` is marked failed with the error, a failure email is sent instead of
a report, and the run log records it. The workflow retries once after 10 minutes, resuming from
the saved stage.

## Where the LLM is used, and where it is not

LLM: turning noisy headlines/search results into company names; reading a company's sources and
returning a structured record (description, category, audience, pricing, evidence-linked signals,
revenue inputs and assumptions, funding, people, Reddit ratings, exclusion flags, discrepancies).

Python: dedupe, domain/name normalisation, every revenue calculation, confidence labels, all
scoring arithmetic, validation of the LLM's claims against sources, budget, Sheets, email.

## Revenue estimation (`research/revenue_estimator.py`)

1. **Disclosed figures first.** MRR, ARR or revenue stated in a source → ±10% range. ARR becomes
   an "ARR-derived monthly equivalent" (ARR / 12), never "verified MRR". High confidence only if
   company-reported or verified *and* the page was opened; snippet-only or third-party
   estimates → Medium.
2. **Modelled otherwise**, by business model:
   - SaaS / app / education: paying customers × ARPU. ARPU from public paid plans (lowest paid to
     typical plan). Paying customers from a stated paying/business-customer count; else stated
     users × active share × freemium conversion; else downloads × download-to-payer rate.
   - eCommerce: monthly orders × average order value; orders from stated visits × conversion.
   - Marketplace: GMV × take rate (GMV is never reported as revenue).
   Every benchmark rate comes from `config/settings.yaml → revenue_assumptions` and is written out
   as an assumption.
3. **Confidence** (`qualification/confidence_scoring.py`):
   - High: disclosed revenue from a page that was read.
   - Medium: evidenced customer count and evidenced pricing, ≥ 3 indicator types, ≥ 2 source
     domains, range spread ≤ 12×.
   - Low: an estimate exists with ≥ 2 independent indicators.
   - Insufficient: otherwise. Funding is never an input.
4. **Qualification:** High/Medium need the geometric midpoint ≥ $50K MRR; Low needs the *lower*
   bound ≥ $50K and ≥ 2 indicators; all need a total score ≥ 45.

## Lead score (`qualification/opportunity_scoring.py`)

| Component | Max | Built from |
|---|---|---|
| Revenue & financial potential | 20 | MRR midpoint tier × confidence multiplier (1.0 / 0.9 / 0.75 / 0.5) |
| Reddit marketing opportunity | 25 | understandable + recommendation-driven + naturally discussed + consumer/prosumer + acquisition challenge (0–5 each) |
| Product-market fit & audience | 15 | audience type (8) + public self-serve pricing (4) + documented adoption (3) |
| Marketing investment & growth | 15 | active marketing (5) + hiring growth roles (5) + growth signals (≤ 5) |
| Funding & financial strength | 10 | funding size tiers (≤ 9) + raised in the last 6 months (+1); self-funded with solid revenue gets 5 |
| Community potential | 15 | audience community participation × 2 + subreddits (≤ 5; source-backed count double) |

80–100 Excellent · 65–79 Strong · 50–64 Potential · < 50 Low priority. Funding is capped at 10 points,
so a $100M company with no Reddit audience scores below a smaller consumer product Reddit
discusses (there is a test for this).

## Duplicate prevention (`database/duplicate_detection.py`)

Checked against Master, Daily, Funded and Rejected history, before research (to save money),
after research (redirect domains, aliases, parent company found), and again against a fresh
Master read just before writing; the email builder drops any row whose company was emailed on an
earlier date.

Signals: root domain (all domains ever seen, including redirect targets) · same domain label on a
different TLD with agreeing names · normalised name or alias · name equals an existing domain
label (`Example AI` ↔ `exampleai.com`) · parent company · fuzzy core brand name (≥ 5 chars,
treated as duplicate). Private suffixes (`*.myshopify.com`, `*.vercel.app`) do not collide.
A product of an already-listed parent is logged as a duplicate, not a new lead.

Rejected companies are re-researched only if marked reconsiderable and their reconsider date has
passed (quota overflow: next day; research failures: 14 days; weak evidence: 90 days).

## Recovery and idempotency

- `_RunState` row per IST date: stage (`started → researched → sheets_written → emailed →
  completed`), status, lock owner and heartbeat (stale after 3 hours), attempts, last error.
- GitHub `concurrency` prevents parallel runs; the sheet lock covers manual/local runs too.
- Research checkpoints in `.cache/runs/<date>/`; LLM, search and page caches in `.cache/`, all
  carried between runs by `actions/cache`.
- Rows written by a failed attempt earlier the same day are not treated as history, so the retry
  selects the same companies and the idempotent writes skip what already exists.

## Extension points

| Future feature | Where |
|---|---|
| Reddit-specific search/monitoring | New `SearchProvider` subclass; call it from `research/company_research.py` |
| Paid traffic data (Similarweb etc.) | `research/traffic_research.py` |
| Contact enrichment / email verification | `research/contact_research.py` (keep the "never guess" rule) |
| Personalised pitch or outreach drafts | New module reading Daily rows; drafts only, never auto-send |
| CRM sync, lead status tracking | "Lead Status" column exists in Daily/Funded/Master |
| Re-research and growth monitoring | Iterate Master rows by "Last Updated Date" and re-run research |
| Funding alerts | `discovery/funding_discovery.py` + a second workflow |
