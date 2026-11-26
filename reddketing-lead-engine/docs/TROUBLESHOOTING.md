# Troubleshooting

Start with the **Daily Run Log** tab (status, errors, email and sheet status for every run) and
the GitHub Actions log. `python -m reddketing.main doctor` checks configuration without spending.

| Symptom | Likely cause | Fix |
|---|---|---|
| `Cannot open spreadsheet. Share it with …` | Sheet not shared with the service account | Share the sheet with the `client_email` as Editor |
| `SPREADSHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON must be set` | Missing secrets | Add both secrets (paste the whole JSON file) |
| `Gmail OAuth refresh failed … revoked or expired` | OAuth app still in "Testing" (7-day tokens), password changed, or grant revoked | Publish the consent screen to "In production", re-run the token script, update `GMAIL_REFRESH_TOKEN` |
| `SMTP authentication failed` | Wrong App Password or 2-Step Verification off | Create a new App Password |
| Failure email "Monthly API budget exhausted" | Month-to-date estimate ≥ ₹1,500 | Wait for the new month or raise `budget.monthly_budget_inr` deliberately |
| Run status `locked` | Another run for the same date is in progress, or one crashed in the last 3 hours | Wait, or run manually with **force** ticked |
| Status `already_completed` | Today's report was already sent | Expected; use **force** only to re-send |
| Few or zero revenue-qualified companies | Strict evidence bar, search key missing, or many duplicates | Check Rejected tab reasons; confirm `BRAVE_SEARCH_API_KEY`; this is by design rather than padding the list |
| `this API key is not scoped to a workspace` | The Anthropic key was created outside a workspace | Create a new key inside a workspace in the Anthropic Console, or add the secret `ANTHROPIC_WORKSPACE_ID` |
| Failure email "AI model unavailable during discovery" / "AI model failed for the first 3 companies" | The LLM refused or was overloaded for every request | Read the error in the email; re-run later with **force** ticked. Companies are not marked as researched, so nothing is lost |
| `anthropic authentication failed` | Bad or revoked key / no credit | Replace the key; add billing credit |
| `Brave HTTP 401/403` | Bad key or plan not active | Check the Brave dashboard subscription |
| `Brave HTTP 429` | Rate or credit limit | Lower `search.max_queries_per_run` |
| Feed errors like `eu-startups.com: HTTP 403` in notes | That site blocks automated feed readers on some days | Harmless; other sources continue |
| Scheduled run started late | GitHub delays scheduled jobs at busy times | Expected; the run still uses the IST date |
| Scheduled runs stopped | GitHub disables schedules in repos with no activity for 60 days | Actions tab → re-enable the workflow (any commit also resets the timer) |
| Email went to spam | First messages from a new OAuth app | Mark as "Not spam" once and add a filter |

## Recovery behaviour

- A failed run is retried once automatically after 10 minutes in the same workflow.
- Research is checkpointed per company; sheet writes are idempotent; the email is rebuilt from
  rows saved in Sheets. Re-running the same date never re-researches stored companies, never
  inserts duplicates, and never emails a lead that was already emailed. Every email contains only new
  leads; earlier leads stay in the sheet. An "add more leads" run emails just the leads it added.
- If the email fails after the sheet update, the next run (manual or the automatic retry) sends
  that day's report from the stored rows.
- To fully redo a date (rarely needed), delete that date's row in `_RunState` and that date's rows
  in the other tabs, then run with **run_date** set.
