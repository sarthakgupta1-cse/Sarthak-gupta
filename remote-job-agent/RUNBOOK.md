# Daily run procedure (for the scheduled Claude session)

A scheduled task starts a fresh Claude cloud session every day at **08:00 Asia/Kolkata**.
The task prompt supplies these values (they are kept out of this public repo):

| Name | Meaning |
|---|---|
| `SHEET_ID` / `SHEET_URL` | the "Worldwide Remote Job Opportunities" spreadsheet |
| `BACKUP_FOLDER_ID` | Drive folder "Remote Job Agent/Run Backups" |
| `APPS_FOLDER_ID` | Drive folder "Remote Job Agent/Job_Applications" |
| `PROFILE_FOLDER_ID` | Drive folder "Remote Job Agent" (holds `profile.yaml` once the user's updated resume is ready) |
| `REPORT_RECIPIENT` | email address that gets the daily report |

Hard rules, every run:
- Never submit applications, never message recruiters or companies, never pay for anything.
- Never invent salaries, recruiter names, URLs or job facts. Only write what a page or feed states.
- Never put application URLs in the email. They go only in the sheet.
- Never overwrite Application Status, CV/Cover Letter Prepared, Recruiter Details or Notes on existing rows.
  `jobagent` plans only system cells. Apply its ops exactly as printed.
- One failing step must not lose data: keep going, record the failure, and save the outputs to Drive.

All paths below are relative to `remote-job-agent/`. Today's date means the IST date.

## 0. Prepare
```bash
git clone --depth 1 --branch claude/vigilant-darwin-3ayl1g https://github.com/sarthakgupta1-cse/Sarthak-gupta.git 2>/dev/null || true
cd Sarthak-gupta/remote-job-agent && pip install -q -r requirements.txt && mkdir -p out
TZ=Asia/Kolkata date +%F     # today's date
```
(If the branch has been merged, clone the default branch instead.)

## 1. Retry guard. Don't do the same day twice
1. `get_values` `'Daily Statistics'!A2:S`. If a row for today already says `Sheets Sync = Done` **and** `Email Status = Sent`, stop: the run already finished.
2. Gmail `search_threads` with `in:sent to:<REPORT_RECIPIENT> subject:"Daily Remote Job Opportunities" newer_than:2d`. If today's subject is already there, skip step 9's send, but still finish the other steps.
3. If an earlier row says `Email Status = Failed`, look in `BACKUP_FOLDER_ID` for that day's `report-<date>.html`, read it, and send it first with its original subject.

## 2. Load history from the sheet
Save each result as JSON. If the app saved a large result to a file, use that path directly instead of retyping it.
- `get_values` `'_Index'!A2:I` → `out/index.json`
- `get_values` `'All Jobs'!A2:A` → `out/all_ids.json`
- `get_values` `'Needs Verification'!A2:A` → `out/nv_ids.json`
- `get_values` `'Applications Tracker'!A2:A` → `out/tracker_ids.json`

If any read fails, retry once. If it still fails, set SHEETS_STATUS to `Failed – could not read history` and skip steps 6–7, but still run discovery, back up the results to Drive and send the email.

## 3. Web research for sources without an API (≈15 minutes, bounded)
Run up to 12 web searches across sources that can't be called directly: LinkedIn job posts and recruiter posts,
Wellfound, YC Work at a Startup, Indeed, Dynamite Jobs, Reddit r/forhire / r/remotejs-style hiring threads,
and career pages of SaaS, AI, fintech, edtech, e-commerce, creator-economy and agency companies. Example queries:
- `"content writer" remote India "per month" site:wellfound.com`
- `"social media" OR "affiliate" remote "anywhere" hiring "₹" OR "USD" junior`
- `"we're hiring" "SEO executive" remote India salary`

Keep a candidate only if you opened its page and it states the title, the company, and remote work open to India or worldwide.
Write each one as an object in `out/manual_candidates.json`. Use only facts from the page:
```json
[{"company": "…", "title": "…", "source_url": "<page you read>", "apply_url": "<apply link on that page>",
  "site": "LinkedIn post|Wellfound|Company careers|…", "location_text": "…", "employment_type": "…",
  "salary_text": "<exact wording, or omit>", "description": "<the posting text you read>",
  "posted_at": "YYYY-MM-DD", "recruiter": "<only if named publicly on the page>", "is_official": true}]
```
Set `is_official: true` only for the employer's own careers page or ATS. Do not use pages behind a login, and do not get around a CAPTCHA.

## 4. Discover
```bash
python -m jobagent discover --index out/index.json --all-ids out/all_ids.json --nv-ids out/nv_ids.json \
    --tracker-ids out/tracker_ids.json
```

## 5. Review (quality gate)
Read `out/review.md`.
- For each **QUALIFIED** job, check that the evidence supports it: remote and open to India, full-time, fixed salary at or above the minimum, junior level.
  If not, run `python -m jobagent override <ID> needs_verification "<why>"`, or `rejected` for a clear fail.
- For **NEEDS VERIFICATION** jobs whose only reason is `original employer posting not yet located`, search for the
  employer's own posting (careers page or ATS), up to 10 jobs, highest salary first. Then run
  `python -m jobagent set-original <ID> <url>`. If that URL is open, the job is promoted automatically.
- A job you keep in Needs Verification with `override` is marked `NR` in `_Index` and is never promoted automatically later.
- Skim `out/rejected.jsonl` for obvious false rejections. If you find one, override it only after reading the posting.
Then run `python -m jobagent plan --sheet-url "$SHEET_URL"`.

## 6. Sync the sheet
**New rows: bulk path.** The data never passes through the chat, so it is exact and cheap at any size.
1. `sha256sum out/sync.xlsx`, then Drive `create_file(title="jobagent-sync-<date>", parentId=BACKUP_FOLDER_ID,
   contentMimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
   base64Content="sha256:<hex>:<absolute path>")`. Drive converts it to a Google Sheet.
2. `get_spreadsheet(<temp id>, fields=["sheets.properties"])` → the sheetId of each tab (`AJ`, `NV`, `TRK`, `IDX`).
3. For each tab: `copy_sheet_to_another_spreadsheet(<temp id>, <tab sheetId>, SHEET_ID)` → note the new sheetId.
4. `python -m jobagent bulk-requests '{"NV": <new id>, "IDX": <new id>, ...}'` → apply the printed list with one
   `update_spreadsheet(SHEET_ID, requests)` call. It appends rows, pastes values under the existing data, and deletes the temp tabs.
5. Drive `trash_file(<temp id>)`.
(Skip the bulk path when `out/bulk.json` is `[]`. For a handful of rows, `python -m jobagent ops` append ops also work.)

**Existing rows:** `python -m jobagent ops --updates-only` prints the remaining small `update` ops (dates, statuses).
Apply each with `update_values(SHEET_ID, range, values)`, copying the values exactly. A leading `'` keeps text as text.

Retry a failed call once. If it fails again, stop syncing, set SHEETS_STATUS = `Failed at <step>`, upload `out/plan.json` and
`out/sync.xlsx` (step 8), and carry on. Nothing is lost: tomorrow's run reads the sheet, and anything that didn't get in is discovered again.
If everything succeeds, SHEETS_STATUS = `Done`.

## 7. Application documents
If `profile.yaml` exists in `PROFILE_FOLDER_ID`, download it to `profile/profile.yaml` and run `python -m jobagent docs`.
Upload each generated folder's files to `APPS_FOLDER_ID/<Company>/<Job_Title>/`.
Then set `CV Prepared` and `Cover Letter Prepared` to `Yes – <date>` on those rows, using the Job ID to find the row.
If there is no profile yet, skip this step. The sheet already says "No – awaiting updated resume".

## 8. Back up to Drive (no data loss)
Upload to `BACKUP_FOLDER_ID` with `create_file`, `disableConversionToGoogleType: true`, and `base64Content` set to a
file reference (`sha256:<hex>:<absolute path>`, from `sha256sum`):
`out/jobs-<date>.db` (SQLite snapshot), `out/state.json` as `state-<date>.json`, `out/report.html` as `report-<date>.html`,
`out/plan.json` as `plan-<date>.json`, and `logs/run-<date>.log`.

## 9. Email
Send unless step 1 found today's report already sent:
`send_message(to=[REPORT_RECIPIENT], subject=<out/subject.txt>, htmlBody=<out/report.html>, body=<out/report.txt>)`.
Retry once if it fails. If it still fails, EMAIL_STATUS = `Failed – report saved to Drive`. Otherwise EMAIL_STATUS = `Sent`.

## 10. Record the run
Take `out/stats_row.json`, replace `{SHEETS_STATUS}` and `{EMAIL_STATUS}`, and `append_values` it to `'Daily Statistics'!A1:T1`.
Finish with a short summary: new qualified, new needs-verification, closed, failures.
