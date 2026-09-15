# founder-agent

An agent that finds SaaS founders and enriches them with contact data — email,
LinkedIn, X, GitHub and Telegram — then upserts them into Google Sheets.

It is built around one deliberate constraint: **every source is either an
official API or a page the founder published about themselves.** No LinkedIn
session cookies, no headless browser pretending to be a member, no Telegram
group harvesting. That constraint is what keeps the list usable — see
[Why it works this way](#why-it-works-this-way).

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

cp .env.example .env        # fill in whatever keys you have — all optional
founder-agent doctor        # shows what's usable right now
founder-agent run --limit 25 --dry-run
```

`doctor` is the first thing to run. It prints every source, enricher and sink
with a ready/skipped status, so you can see exactly what a run will do before
spending a credit.

### Commands

| Command | What it does |
|---|---|
| `founder-agent run` | Full pass: discover → dedupe → enrich → score → write |
| `founder-agent crawl acme.io,beta.com` | Find the founders at companies you already know |
| `founder-agent doctor` | Readiness check for every component |
| `founder-agent optout <email\|domain>` | Suppress someone permanently |

Useful flags: `--limit N`, `--domains a.com,b.com`, `--sink csv|sqlite|gsheets`,
`--dry-run`, `-v`.

---

## How it works

```
  discovery              dedupe          enrichment           output
┌──────────────┐                     ┌───────────────┐
│ Hacker News  │──┐                  │ Proxycurl     │ LinkedIn
│ Product Hunt │──┤   ┌──────────┐   │ Apollo        │ person + org
│ GitHub       │──┼──▶│ merge on │──▶│ Hunter        │ find + verify email
│ company site │──┘   │ identity │   │ socials       │ X / GitHub / Telegram
└──────────────┘      └──────────┘   └───────────────┘
                                             │
                                             ▼
                                     score → suppress → Google Sheets
```

Enrichment runs **after** dedupe, on purpose: paid lookups are the expensive
part, so duplicates are collapsed first and no human costs two credits.

### Discovery sources

| Source | Key needed | What it gives you |
|---|---|---|
| **Hacker News** | none | `Launch HN` / `Show HN` posters — founders who self-identify. Their HN profile often carries an email and socials. |
| **Product Hunt** | free token | Makers on recent launches, with X handles. |
| **GitHub** | optional PAT | Open-core founders: real name, company, blog link, sometimes a public email. |
| **Company site** | none | `/about` and `/team` pages — names, titles, direct addresses. |

The company-site crawler only fetches the handful of paths named in
`config.yaml`, obeys `robots.txt`, and never follows links deeper.

### Enrichment

| Provider | Cost/lead | Role |
|---|---|---|
| **Proxycurl** | ~$0.03 | LinkedIn profile data, via a licensed API |
| **Apollo** | ~$0.02 | Person + org enrichment, work emails, headcount |
| **Hunter** | ~$0.01 | Finds work emails and — critically — verifies them |
| **socials** | free | X / GitHub / Telegram from personal sites and profile READMEs |

Each enricher skips leads it can't improve, so a lead that already has a
verified email and a LinkedIn URL costs nothing further. The run report prints
an estimated spend.

### Email trust levels

This is the part that protects your sending domain:

| Status | Meaning | Safe to cold-email? |
|---|---|---|
| `verified` | Provider confirmed the mailbox accepts mail | **yes** |
| `published` | The person published it themselves | **yes** |
| `risky` | Catch-all / disposable domain | no |
| `guessed` | Pattern-derived, unverified | **no** |
| `unknown` | No signal | no |

`is_contactable()` allows only `verified` and `published`, and excludes role
addresses (`info@`, `sales@`). Mailing guessed addresses at volume is the
single fastest way to get a domain blocklisted.

---

## Output: Google Sheets

Rows are **upserted by identity**, not appended — re-running updates the row a
founder already has instead of stacking duplicates.

One-time setup:

1. GCP console → new project → enable the **Google Sheets API** and **Google Drive API**.
2. Create a service account → add a JSON key → save as `service_account.json`.
3. Open your spreadsheet → **Share** it with the service account's `client_email` as Editor.
   *This is the step everyone forgets — without it you get a 403.*
4. Put `GOOGLE_SHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_FILE` in `.env`.

Values starting with `=`, `+`, `-` or `@` are escaped before writing, so a
scraped bio containing `=IMPORTXML(...)` can't execute inside your sheet.

`sqlite` and `csv` sinks are also available and need no setup. If the Sheets
sink isn't configured, a run falls back to CSV rather than losing the data.

---

## Why it works this way

**LinkedIn.** Scraping linkedin.com with a member session breaches the User
Agreement, and LinkedIn enforces it — accounts get restricted in days, which
costs you the profile you actually use. `hiQ v. LinkedIn` is often cited as
permission to scrape; it addressed the CFAA only, and left contract and
copyright claims fully intact. So we buy the same data from a provider that
licenses it and carries that exposure. It is cheaper than replacing a banned
account.

**Telegram.** Handles are read from links founders published — a `t.me/…` in a
site footer, a bio, a GitHub README. There is no group-member harvesting and no
phone-number-to-account resolution; both breach Telegram's ToS, and the latter
is unlawful processing under GDPR in most of the EU.

**Email.** Work addresses at a company you have a genuine B2B reason to contact
are usually defensible under GDPR **legitimate interest** (Art. 6(1)(f)) — but
that basis requires you to say where you got the data, offer an opt-out, and
honour it. Hence `source_url` on every lead and the `optout` command.

Under CAN-SPAM, every message needs a real postal address and a working
unsubscribe. The `OUTREACH_*` variables in `.env` exist so that information
lives with the pipeline that generated the list.

**This is not legal advice.** Rules differ by jurisdiction, and Germany and
Canada (CASL) in particular are stricter than the US. If you're sending at
volume, have counsel look at your setup.

### Built-in guardrails

- `robots.txt` honoured before any page fetch
- Per-host rate limiting (default 1 req/s) with `Retry-After` backoff
- `source_url` recorded on every lead — this is what a GDPR Art. 14 request asks for
- Suppression list enforced at write time, so an opt-out survives every future run
- Role addresses and freemail flagged and down-ranked
- Response caching, so re-runs don't re-hit the same pages

Handle an opt-out the moment it arrives:

```bash
founder-agent optout ada@acme.io     # or a whole domain
```

---

## Configuration

`config.yaml` holds targeting and behaviour; `.env` holds secrets only.

```yaml
targeting:
  keywords: ["B2B SaaS", "developer tools"]
  founder_titles: [founder, co-founder, ceo, cto]
  max_headcount: 200          # skip anything enterprise-sized

politeness:
  rate_limit_per_host: 1.0    # be a good guest
  respect_robots_txt: true

scoring:
  min_score: 40               # below this, leads are kept but flagged
```

Scoring exists so a human works the top of the list first: verified email +30,
LinkedIn +20, founder title +20, a launch in the last 90 days +12, role address
−20.

---

## Development

```bash
pip install -e ".[dev]"
pytest -q          # 29 tests, no network required
```

Tests run against fixtures rather than live APIs, so the parsing logic — which
is where the bugs actually are — is verified offline and deterministically.

```
src/founder_agent/
├── discovery/    hackernews · producthunt · github_ · website
├── enrich/       proxycurl · apollo · hunter · socials
├── sinks/        gsheets · sqlite · csv_
├── pipeline.py   orchestration
├── compliance.py robots · suppression · role/freemail
├── scoring.py    ranking + contactability
└── http.py       rate limiting · retries · caching
```

Adding a source means subclassing `DiscoverySource` and adding it to
`ALL_SOURCES`; the pipeline picks it up automatically.
