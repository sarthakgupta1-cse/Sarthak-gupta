"""Spreadsheet backends: Google Sheets (gspread) for production, in-memory for tests/dry runs.

All writes use RAW value input so scraped text can never be evaluated as a formula.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Protocol

from ..config import env
from .schema import COLUMNS, TAB_ORDER

logger = logging.getLogger(__name__)
MAX_CELL = 45_000  # Google Sheets hard limit is 50,000 characters per cell


class SheetsError(Exception):
    pass


def _cell(value: Any) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple, set)):
        value = "\n".join(str(v) for v in value if v not in (None, ""))
    text = str(value)
    return text if len(text) <= MAX_CELL else text[: MAX_CELL - 20] + " …[truncated]"


class SheetsBackend(Protocol):
    def ensure_schema(self) -> None: ...
    def read_records(self, tab: str) -> list[dict[str, str]]: ...
    def append_rows(self, tab: str, rows: list[dict[str, Any]]) -> int: ...
    def update_where(self, tab: str, key_col: str, key_value: str, updates: dict[str, Any]) -> bool: ...
    @property
    def url(self) -> str: ...


class MemorySheets:
    """Same contract as GoogleSheets, stored in memory (optionally failing on demand for tests)."""

    def __init__(self):
        self.tabs: dict[str, list[list[Any]]] = {}
        self.fail_on: set[str] = set()

    @property
    def url(self) -> str:
        return "memory://reddketing"

    def _check(self, op: str):
        if op in self.fail_on:
            raise SheetsError(f"simulated failure on {op}")

    def ensure_schema(self) -> None:
        self._check("ensure_schema")
        for tab in TAB_ORDER:
            self.tabs.setdefault(tab, [list(COLUMNS[tab])])

    def read_records(self, tab: str) -> list[dict[str, str]]:
        self._check("read")
        rows = self.tabs.get(tab, [])
        if not rows:
            return []
        header = rows[0]
        return [{h: (r[i] if i < len(r) else "") for i, h in enumerate(header)} for r in rows[1:]]

    def append_rows(self, tab: str, rows: list[dict[str, Any]]) -> int:
        self._check("append")
        header = self.tabs[tab][0]
        for row in rows:
            self.tabs[tab].append([_cell(row.get(h)) for h in header])
        return len(rows)

    def update_where(self, tab: str, key_col: str, key_value: str, updates: dict[str, Any]) -> bool:
        self._check("update")
        header = self.tabs[tab][0]
        k = header.index(key_col)
        for r in self.tabs[tab][1:]:
            if str(r[k]) == str(key_value):
                for col, val in updates.items():
                    r[header.index(col)] = _cell(val)
                return True
        return False


class GoogleSheets:
    """gspread-backed implementation authenticated with a service account (spreadsheets scope only)."""
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self, spreadsheet_id: str | None = None, service_account_json: str | None = None):
        import gspread
        from google.oauth2.service_account import Credentials

        self._gspread = gspread
        spreadsheet_id = spreadsheet_id or env("SPREADSHEET_ID")
        raw = service_account_json or env("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not spreadsheet_id or not raw:
            raise SheetsError("SPREADSHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON must be set")
        try:
            info = json.loads(raw)
        except json.JSONDecodeError:
            try:
                info = json.loads(base64.b64decode(raw).decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                raise SheetsError("GOOGLE_SERVICE_ACCOUNT_JSON is neither JSON nor base64 JSON") from exc
        creds = Credentials.from_service_account_info(info, scopes=self.SCOPES)
        self.client_email = info.get("client_email", "")
        self.gc = gspread.authorize(creds)
        try:
            self.sh = self._retry(lambda: self.gc.open_by_key(spreadsheet_id))
        except Exception as exc:  # noqa: BLE001
            raise SheetsError(f"Cannot open spreadsheet. Share it with {self.client_email} as Editor. ({exc})") from exc
        self._ws_cache: dict[str, Any] = {}
        self._header_cache: dict[str, list[str]] = {}

    @property
    def url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.sh.id}/edit"

    def _retry(self, fn, attempts: int = 5):
        for i in range(attempts):
            try:
                return fn()
            except self._gspread.exceptions.APIError as exc:
                status = getattr(getattr(exc, "response", None), "status_code", 0)
                if status in (429, 500, 502, 503) and i < attempts - 1:
                    time.sleep(min(60, 2 ** i * 3))
                    continue
                raise SheetsError(f"Sheets API error {status}: {exc}") from exc
        raise SheetsError("Sheets API retries exhausted")

    def _ws(self, tab: str):
        if tab not in self._ws_cache:
            self._ws_cache[tab] = self._retry(lambda: self.sh.worksheet(tab))
        return self._ws_cache[tab]

    def ensure_schema(self) -> None:
        existing = {ws.title: ws for ws in self._retry(self.sh.worksheets)}
        for tab in TAB_ORDER:
            cols = COLUMNS[tab]
            if tab not in existing:
                ws = self._retry(lambda: self.sh.add_worksheet(title=tab, rows=1000, cols=len(cols)))
                self._retry(lambda: ws.update(range_name="A1", values=[cols], value_input_option="RAW"))
                self._retry(lambda: ws.freeze(rows=1))
            else:
                ws = existing[tab]
                header = self._retry(lambda: ws.row_values(1))
                if header != cols[: len(header)] or len(header) < len(cols):
                    if not header:
                        self._retry(lambda: ws.update(range_name="A1", values=[cols], value_input_option="RAW"))
                    else:
                        # Append any new columns without moving existing data.
                        missing = [c for c in cols if c not in header]
                        if missing:
                            new_header = header + missing
                            if ws.col_count < len(new_header):
                                self._retry(lambda: ws.add_cols(len(new_header) - ws.col_count))
                            self._retry(lambda: ws.update(range_name="A1", values=[new_header], value_input_option="RAW"))
            self._ws_cache[tab] = ws
        # Remove the default empty "Sheet1" if it exists and is empty.
        if "Sheet1" in existing and len(existing) >= 1:
            try:
                if not self._retry(lambda: existing["Sheet1"].get_all_values()):
                    self._retry(lambda: self.sh.del_worksheet(existing["Sheet1"]))
            except SheetsError:
                pass

    def _header(self, tab: str) -> list[str]:
        if tab not in self._header_cache:
            self._header_cache[tab] = self._retry(lambda: self._ws(tab).row_values(1))
        return self._header_cache[tab]

    def read_records(self, tab: str) -> list[dict[str, str]]:
        values = self._retry(lambda: self._ws(tab).get_all_values())
        if not values:
            return []
        header = values[0]
        self._header_cache[tab] = header
        return [{h: (r[i] if i < len(r) else "") for i, h in enumerate(header)} for r in values[1:] if any(r)]

    def append_rows(self, tab: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        header = self._header(tab)
        values = [[_cell(row.get(h)) for h in header] for row in rows]
        self._retry(lambda: self._ws(tab).append_rows(values, value_input_option="RAW",
                                                      insert_data_option="INSERT_ROWS", table_range="A1"))
        return len(rows)

    def update_where(self, tab: str, key_col: str, key_value: str, updates: dict[str, Any]) -> bool:
        ws = self._ws(tab)
        values = self._retry(ws.get_all_values)
        header = values[0] if values else self._header(tab)
        k = header.index(key_col)
        for idx, r in enumerate(values[1:], start=2):
            if k < len(r) and str(r[k]) == str(key_value):
                data = []
                for col, val in updates.items():
                    c = header.index(col) + 1
                    data.append({"range": self._gspread.utils.rowcol_to_a1(idx, c), "values": [[_cell(val)]]})
                self._retry(lambda: ws.batch_update(data, value_input_option="RAW"))
                return True
        return False
