"""Google Sheets output.

Upserts by dedupe key rather than appending, so re-running the agent updates
the row a founder already has instead of stacking duplicates under your team.

Setup (once):
  1. GCP console -> create a project -> enable the Google Sheets API and the
     Google Drive API.
  2. Create a service account, add a JSON key, save it as service_account.json.
  3. Open the target spreadsheet and Share it with the service account's
     client_email (Editor). This step is the one everybody forgets.
  4. Put the spreadsheet ID and the key path in .env.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..models import Lead
from .base import COLUMNS, Sink

log = logging.getLogger("founder_agent.sinks.gsheets")

# A header row plus the key column we use to find existing rows.
KEY_COLUMN = "dedupe_key"
HEADER = [KEY_COLUMN, *COLUMNS]


class GoogleSheetsSink(Sink):
    name = "gsheets"

    def available(self) -> tuple[bool, str]:
        if not self.settings.google_sheet_id:
            return False, "GOOGLE_SHEET_ID not set"
        key_file = self.settings.google_sa_file
        if not key_file or not Path(key_file).exists():
            return False, f"service account file not found at {key_file!r}"
        return True, ""

    def _worksheet(self):
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]
        creds = Credentials.from_service_account_file(
            self.settings.google_sa_file, scopes=scopes
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(self.settings.google_sheet_id)

        title = self.settings.google_worksheet or "Leads"
        try:
            worksheet = spreadsheet.worksheet(title)
        except Exception:
            worksheet = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(HEADER))

        # Make sure the header exists and matches what we're about to write.
        current = worksheet.row_values(1)
        if current != HEADER:
            worksheet.update(range_name="A1", values=[HEADER])
            worksheet.freeze(rows=1)
        return worksheet

    def write(self, leads: list[Lead]) -> int:
        if not leads:
            return 0
        worksheet = self._worksheet()

        # One read to find which founders already have a row.
        existing_keys = worksheet.col_values(1)[1:]  # skip header
        row_of = {key: idx + 2 for idx, key in enumerate(existing_keys) if key}

        updates: list[dict] = []
        appends: list[list] = []

        for lead in leads:
            key = lead.dedupe_key()
            row = lead.to_row()
            values = [key] + [_cell(row.get(c, "")) for c in COLUMNS]
            if key in row_of:
                index = row_of[key]
                updates.append({"range": f"A{index}", "values": [values]})
            else:
                appends.append(values)

        if updates:
            worksheet.batch_update(updates, value_input_option="RAW")
            log.info("updated %d existing rows", len(updates))
        if appends:
            worksheet.append_rows(appends, value_input_option="RAW")
            log.info("appended %d new rows", len(appends))

        return len(updates) + len(appends)


def _cell(value) -> str:
    """Sheets treats a leading '=' or '+' as a formula — neutralise it."""
    if value is None:
        return ""
    text = str(value)
    if text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text
