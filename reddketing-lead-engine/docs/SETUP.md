# Setup guide

Follow these steps once. Budget about 30–45 minutes. Everything after step 7 runs in the cloud.

The spreadsheet **Reddketing - Company Intelligence Database** already exists in your Google Drive,
with all seven tabs and header rows. If you ever need to recreate it, run
`python -m reddketing.main init-sheet` against an empty Google Sheet.

---

## 1. Google Cloud project

1. Open <https://console.cloud.google.com/> signed in as the Google account that owns the spreadsheet.
2. Top bar → project picker → **New project** → name it `reddketing-lead-engine` → **Create**. Select it.
3. **APIs & Services → Library**. Search for and **Enable** both:
   - **Google Sheets API**
   - **Gmail API**

## 2. Service account for Google Sheets

1. **IAM & Admin → Service accounts → Create service account**.
   Name: `reddketing-sheets`. Click **Create and continue**, skip the optional role steps, **Done**.
   (It needs no project roles; access comes from sharing the sheet with it.)
2. Click the new account → **Keys → Add key → Create new key → JSON** → **Create**. A `.json` file downloads.
3. Open the file and copy the `client_email` value (it ends in `iam.gserviceaccount.com`).
4. Open the spreadsheet → **Share** → paste the `client_email` → role **Editor** → untick
   "Notify people" → **Share**.
5. Copy the spreadsheet ID from its URL: `https://docs.google.com/spreadsheets/d/<THIS PART>/edit`.

The app requests only the `spreadsheets` scope, and the service account can open only sheets
shared with it.

> Some Google Workspace organisations block service-account key creation by policy
> (`iam.disableServiceAccountKeyCreation`). A personal gmail.com account is not affected.

## 3. Gmail sending (recommended: Gmail API, `gmail.send` scope only)

1. **APIs & Services → OAuth consent screen** (or **Google Auth Platform → Branding**).
   - User type: **External** → Create.
   - App name `Reddketing Lead Engine`, your email as support and developer contact → Save.
   - **Audience / Test users**: add the Gmail address that will send the report.
   - **Publishing status → Publish app → In production.** This matters: while an app is in
     "Testing", Google expires its refresh tokens after 7 days and the daily email would stop.
     For your own account you will see an "unverified app" warning once; that is expected, and
     verification is not required for personal use.
2. **Credentials → Create credentials → OAuth client ID** → Application type **Desktop app** →
   name `reddketing-cli` → Create → **Download JSON** (save as `client_secret.json`).
3. On any computer with a browser, once:
   ```bash
   pip install google-auth-oauthlib
   python scripts/get_gmail_refresh_token.py client_secret.json
   ```
   Sign in with the sending Gmail account, click **Advanced → Go to Reddketing Lead Engine
   (unsafe)** on the unverified-app screen, and allow "Send email on your behalf".
   The script prints `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` and `GMAIL_REFRESH_TOKEN`.
4. Delete `client_secret.json` afterwards or keep it somewhere private. Never commit it.

**Alternative without a computer: OAuth Playground.** In step 2 choose **Web application** and add
the redirect URI `https://developers.google.com/oauthplayground`. Then open
<https://developers.google.com/oauthplayground>, click the gear icon → "Use your own OAuth
credentials" → paste the client ID and secret. In step 1 enter the scope
`https://www.googleapis.com/auth/gmail.send`, **Authorize APIs**, sign in, then **Exchange
authorization code for tokens** and copy the refresh token.

**Simpler alternative: SMTP with an App Password.** Turn on 2-Step Verification for the Google
account, create an App Password at <https://myaccount.google.com/apppasswords>, then set the
secrets `SMTP_USERNAME` (the Gmail address)
and `SMTP_APP_PASSWORD` (16 characters, no spaces).

## 4. LLM API key (default: Anthropic, Claude Haiku 5.5)

1. <https://console.anthropic.com/> → sign up → **Billing**: add a small prepaid credit (for
   example $5, which lasts more than a month at default settings). Optionally set a monthly spend
   limit in the console as a second safety net.
2. **API keys → Create key**, choose a **workspace** (for example "Default") → copy it (`sk-ant-...`).
   A key that is not scoped to a workspace fails with "must include the anthropic-workspace-id
   header". Either create a new key inside a workspace, or add the workspace's ID (Console →
   Settings → Workspaces) as the secret `ANTHROPIC_WORKSPACE_ID`.

Alternatives: Gemini (`GEMINI_API_KEY` from <https://aistudio.google.com/apikey>; set variable
`LLM_PROVIDER=gemini`; uses `gemini-3.5-flash-lite`, falling back to `gemini-3.5-flash` when it is
overloaded; costs more than Haiku, see COSTS.md) or OpenAI (`OPENAI_API_KEY`; `LLM_PROVIDER=openai`). Note that free-tier
Gemini usage may be used by Google to improve its products; a billed key is not.

## 5. Search API key (default: Brave Search)

1. <https://api-dashboard.search.brave.com/> → sign up → subscribe to the **Search** plan.
   A card is required; the plan includes a $5 monthly credit (about 1,000 queries), and the
   engine uses about 50 queries on a normal day and at most 70 (about $2.50–$5.50 a month beyond the credit).
2. Set a usage limit in the Brave dashboard if offered.
3. **API keys → Add API key** → copy it.

Alternative: Serper (<https://serper.dev>, 2,500 free queries once, no card); set
`SEARCH_PROVIDER=serper` and `SERPER_API_KEY`. With no search key at all
(`SEARCH_PROVIDER=none`), discovery uses only free feeds and research uses only company websites
and news headlines, so expect fewer qualified companies.

Optional: a Product Hunt developer token (<https://www.producthunt.com/v2/oauth/applications> →
create an application → "Create token") as `PRODUCT_HUNT_TOKEN`.

## 6. GitHub secrets

Repository → **Settings → Secrets and variables → Actions**.

**Secrets** tab → **New repository secret**, one per row:

| Name | Value |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | The whole contents of the service-account JSON file |
| `SPREADSHEET_ID` | From step 2.5 |
| `REPORT_RECIPIENT` | The address that should receive the daily report |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN` | From step 3 |
| `GMAIL_SENDER` | The Gmail address that authorised the token |
| `ANTHROPIC_API_KEY` (or `GEMINI_API_KEY` / `OPENAI_API_KEY`) | From step 4 |
| `BRAVE_SEARCH_API_KEY` | From step 5 |
| `PRODUCT_HUNT_TOKEN` | Optional |

**Variables** (optional, at Settings → Secrets and variables → Actions → Variables): `LLM_PROVIDER` (default `anthropic`), `SEARCH_PROVIDER` (default `brave`), `EMAIL_TRANSPORT` (default: `smtp` when only an App Password is set, otherwise `gmail_api`).

## 7. First runs

1. Merge the pull request into the default branch (scheduled workflows run only from the default
   branch).
2. **Actions → Reddketing daily discovery → Run workflow** with **Dry run** ticked. This uses an
   in-memory sheet and sends no email; download the `reddketing-dry-run-report` artifact and open
   the HTML report.
3. Run it again with **Dry run** unticked. Check the spreadsheet and your inbox.
4. From then on it runs every day at 08:00 IST. A manual run uses the same button.

Manual-run options: **run_date** re-runs a specific IST date; **force** takes over a stale lock
or re-sends a report already emailed that day. Neither repeats research for companies already
stored.

## 8. Local runs (optional)

```bash
cd reddketing-lead-engine
pip install -r requirements.txt
cp .env.example .env      # fill in values; .env is git-ignored
export PYTHONPATH=src
python -m reddketing.main doctor
python -m reddketing.main test-email
python -m reddketing.main run --dry-run
```
