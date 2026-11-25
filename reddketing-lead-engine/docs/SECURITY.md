# Security

## Secrets

- All credentials live in GitHub Actions encrypted secrets (or a local, git-ignored `.env`).
  Nothing secret is in the repository; `.env.example` holds variable names only.
- The report recipient address is also a secret (`REPORT_RECIPIENT`), so it is not in the code.
- Logs are JSON and pass through a redactor that removes the values of all known secret variables
  and common key patterns (`sk-ant-…`, `AIza…`, OAuth access/refresh tokens, private keys).
  GitHub additionally masks secret values in workflow logs.
- `.gitignore` excludes `.env`, `*service_account*.json`, `client_secret*.json`, `token.json`,
  `*.pem`, caches and output.

## Least privilege

| Credential | Scope |
|---|---|
| Service account | `https://www.googleapis.com/auth/spreadsheets`; can open only sheets shared with it; no IAM roles |
| Gmail OAuth token | `https://www.googleapis.com/auth/gmail.send` only (cannot read mail) |
| GitHub workflow token | `contents: read` |
| LLM / search keys | Provider defaults; set spend limits in each provider's dashboard as a second cap |

## Untrusted web content

Every fetched page, snippet and headline is wrapped as `<untrusted_source>` data, and the system
prompt tells the model to ignore instructions inside it. The model's output is then validated by
code: facts must cite a source that was actually retrieved, numbers must appear in that source,
people must be named in it, and LinkedIn URLs and emails must appear verbatim in retrieved text.
Sheet writes use `RAW` input, so scraped text can never run as a formula, and the email template
auto-escapes HTML.

## Rotating credentials

| Credential | How to rotate |
|---|---|
| Service-account key | Cloud console → IAM → Service accounts → Keys → Add key (JSON) → update `GOOGLE_SERVICE_ACCOUNT_JSON` → delete the old key |
| Gmail refresh token | Re-run `scripts/get_gmail_refresh_token.py` → update `GMAIL_REFRESH_TOKEN`; revoke the old grant at <https://myaccount.google.com/permissions> |
| OAuth client secret | Credentials → your OAuth client → Reset secret → re-run the token script → update both secrets |
| Anthropic / Gemini / OpenAI key | Create a new key in the console → update the secret → delete the old key |
| Brave / Serper key | Same pattern in their dashboards |
| SMTP App Password | Delete it at <https://myaccount.google.com/apppasswords>, create a new one, update the secret |

After rotating, run **Actions → Reddketing daily discovery → Run workflow** with **Dry run** to
confirm, or `python -m reddketing.main doctor` locally.

## What the system never does

It never emails, messages or otherwise contacts discovered companies, never posts on Reddit,
never buys or upgrades a paid plan, and stores only public professional contact details.
