# Reddketing Lead Intelligence Engine

A cloud-hosted prospecting system for [Reddketing](https://reddketing.com/), a Reddit-only organic
marketing agency. Every day at **08:00 IST** it runs on GitHub Actions, without your computer, and:

1. discovers companies from free sources (funding news feeds, Google News, Hacker News, Product Hunt)
   and a low-cost search API, rotating through ~60 categories where Reddit influences buying;
2. researches each candidate: official site, pricing, about/team/careers pages, third-party articles,
   news headlines;
3. estimates monthly revenue with a business-model-specific formula (SaaS, mobile, eCommerce,
   marketplace) and labels confidence as High, Medium, Low or Insufficient;
4. scores Reddit fit and overall lead quality (0–100, six components);
5. finds founders and marketing decision-makers named in public sources (no guessed emails);
6. checks every historical record so no company is ever emailed twice;
7. writes everything to the Google Sheet **Reddketing - Company Intelligence Database**;
8. emails a report with **up to 15 revenue-qualified companies** (estimated ≥ $50K MRR) and
   **up to 5 recently funded companies** (last 6 months), kept as separate lists.

It reports fewer than 15 when fewer meet the evidence bar. It never invents revenue, customers,
traffic, funding, people or emails, and it never contacts companies or posts on Reddit.

---

## Quick start (local)

```bash
cd reddketing-lead-engine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in values (see docs/SETUP.md)
export PYTHONPATH=src
python -m reddketing.main doctor            # checks config and credentials; spends nothing
python -m pytest -q                         # 48 offline tests, no keys needed
python -m reddketing.main run --dry-run     # in-memory sheet, report written to out/, no email
python -m reddketing.main run               # the real thing
```

Other commands: `init-sheet` (create/repair tabs), `test-email` (delivery test with no leads),
`budget` (month-to-date API spend).

## Deploying to the cloud

Full step-by-step instructions are in **[docs/SETUP.md](docs/SETUP.md)**. In short:

1. Create a Google Cloud project, enable the Sheets and Gmail APIs.
2. Create a service account, download its JSON key, and share the spreadsheet with its
   `client_email` as **Editor**.
3. Create an OAuth client (Desktop) and run `scripts/get_gmail_refresh_token.py` once to get a
   Gmail refresh token with the `gmail.send` scope only. Publish the OAuth consent screen to
   "In production" so the token does not expire after 7 days.
4. Get an Anthropic API key (default LLM: Claude Haiku 5.5) and a Brave Search API key.
5. Add the secrets listed below in GitHub → Settings → Secrets and variables → Actions.
6. GitHub → Actions → **Reddketing daily discovery** → Run workflow, first with **dry run**
   checked, then without.

The workflow file is at the repository root: `.github/workflows/reddketing-daily-discovery.yml`.
Main run at cron `23 2 * * *` (07:53 IST), with backup slots at 09:11, 10:43 and 13:17 IST.
GitHub sometimes starts scheduled runs late or skips them; a backup slot does nothing if the day's
report was already sent, and otherwise runs or resumes it. The app files every run under the IST date.

### GitHub Secrets

| Secret | Required | What it is |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | yes | Service-account key JSON (raw or base64) |
| `SPREADSHEET_ID` | yes | The ID in the sheet URL between `/d/` and `/edit` |
| `REPORT_RECIPIENT` | yes | Address that receives the daily report |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER` | yes (Gmail API) | OAuth client and refresh token for sending |
| `SMTP_USERNAME`, `SMTP_APP_PASSWORD` | for SMTP (used automatically when no Gmail refresh token is set) | Gmail App Password alternative |
| `ANTHROPIC_API_KEY` | yes (default LLM) | Or `GEMINI_API_KEY` / `OPENAI_API_KEY` with the matching variable |
| `BRAVE_SEARCH_API_KEY` | recommended | Or `SERPER_API_KEY` |
| `PRODUCT_HUNT_TOKEN` | optional | Free developer token; adds Product Hunt launches |

Optional repository **variables** (not secrets): `LLM_PROVIDER` (`anthropic`|`gemini`|`openai`),
`SEARCH_PROVIDER` (`brave`|`serper`|`none`), `EMAIL_TRANSPORT` (`gmail_api`|`smtp`).

## Cost

Estimated **₹800–₹950 per month** with Claude Haiku 5.5 at default settings (up to 60 companies researched a day); the hard cap is ₹1,500.
Details and the pricing sources are in [docs/COSTS.md](docs/COSTS.md). The budget tracker reads
month-to-date spend from the Daily Run Log tab, cuts optional research at 80% and stops paid calls
at 100%. It never buys or upgrades anything.

## Documentation

| Document | Contents |
|---|---|
| [docs/SETUP.md](docs/SETUP.md) | Google Cloud, Sheets, Gmail, API keys, GitHub secrets, first run |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Pipeline, revenue model, scoring, dedupe, recovery, extension points |
| [docs/COSTS.md](docs/COSTS.md) | Provider comparison, monthly estimate, budget controls |
| [docs/SECURITY.md](docs/SECURITY.md) | Secrets handling, scopes, credential rotation |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common failures and fixes |

## Project layout

```
reddketing-lead-engine/
├── config/            settings.yaml (limits, prices, budget), categories.yaml (rotation, exclusions)
├── src/reddketing/
│   ├── discovery/     query planner, free-source + search discovery, funding discovery, filtering
│   ├── research/      source gathering, LLM synthesis, revenue estimator, pricing, contacts, funding
│   ├── qualification/ exclusion rules, confidence labels, 100-point scoring
│   ├── database/      Sheets schema + backends, duplicate detection, run state/lock, row builders
│   ├── reporting/     HTML/text report, Gmail API + SMTP senders
│   ├── providers/     search (Brave/Serper), LLM (Anthropic/Gemini/OpenAI), free feeds
│   ├── monitoring/    budget tracker, JSON logging with secret redaction
│   ├── pipeline.py    orchestration, checkpoints, recovery
│   └── main.py        CLI
├── templates/         email templates (HTML + plain text, success + failure)
├── scripts/           get_gmail_refresh_token.py
└── tests/             48 offline tests with fakes
```

The suggested `src/email/` package was renamed `reporting/` because a top-level package named
`email` would shadow Python's standard-library `email` module that the sender depends on.
