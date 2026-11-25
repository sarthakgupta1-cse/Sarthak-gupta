"""Google Sheets layout and sync planning.

Python never holds Google credentials. It produces a list of sheet operations
(append / update a range), and the scheduled Claude session applies them through
the Google Sheets connector it already has (OAuth, scoped to the user's account).

Rules the plan follows:
* Only system-owned cells are written. Application Status, CV/Cover Letter
  flags, Recruiter Details and Notes on existing rows are never overwritten.
* Existing rows are found by Job ID (column A) right before writing, so sorting
  or filtering the sheet by hand never breaks updates.
* Category tabs are live QUERY() views of All Jobs, so they cannot drift out of sync.
"""
from __future__ import annotations

from .classify import TABS

SPREADSHEET_TITLE = "Worldwide Remote Job Opportunities"

ALL_JOBS = "All Jobs"
NEEDS = "Needs Verification"
TRACKER = "Applications Tracker"
STATS = "Daily Statistics"
INDEX = "_Index"

JOB_COLUMNS = [
    "Job ID", "Date Discovered", "Company Name", "Company Website", "Job Title", "Category", "Country",
    "Remote Eligibility", "India Eligibility", "Employment Type", "Experience Required", "Original Salary",
    "Currency", "Salary Frequency", "Monthly Salary Equivalent", "Fixed Salary Verified", "Commission Available",
    "Job Description", "Required Skills", "Job Posting Date", "Last Verified Date", "Job Status",
    "Source Website", "Direct Application Link", "Recruiter Details", "CV Prepared", "Cover Letter Prepared",
    "Application Status", "Additional Notes",
]
TRACKER_COLUMNS = ["Job ID", "Company Name", "Job Title", "Application Date", "CV Version", "Cover Letter Version",
                   "Application Status", "Interview Status", "Follow-up Date", "Recruiter Contact", "Notes"]
STATS_COLUMNS = ["Run Date", "Run Started (IST)", "Sources Searched", "Sources Failed", "Listings Discovered",
                 "Unique Companies", "Duplicates Removed", "Rejected – Salary", "Rejected – Location",
                 "Rejected – Experience", "Rejected – Employment Type", "Rejected – Not Relevant",
                 "New Verified Qualifying", "New Needs Verification", "Previously Discovered Now Closed",
                 "High-Paying (>$1,000/mo)", "Priority Band ($500–$1,000/mo)", "Sheets Sync", "Email Status",
                 "Errors / Notes"]
INDEX_COLUMNS = ["Job ID", "Title Key", "URL Keys", "Scope", "Tab", "Status", "Check URL", "Last Verified", "Label"]

APPLICATION_STATUSES = ["Not Applied", "Ready to Apply", "Applied", "Assessment", "Interview", "Rejected",
                        "Offer Received", "Closed"]

TAB_ORDER = [ALL_JOBS, *TABS, NEEDS, TRACKER, STATS, INDEX]


def col_letter(idx0: int) -> str:
    s, n = "", idx0 + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def col_of(name: str, columns=JOB_COLUMNS) -> str:
    return col_letter(columns.index(name))


def q(tab: str) -> str:
    return "'" + tab.replace("'", "''") + "'"


LAST_JOB_COL = col_letter(len(JOB_COLUMNS) - 1)          # AC
VERIFIED_COL = col_of("Last Verified Date")              # U
STATUS_COL = col_of("Job Status")                        # V
MONTHLY_COL_IDX = JOB_COLUMNS.index("Monthly Salary Equivalent")
APP_STATUS_IDX = JOB_COLUMNS.index("Application Status")


# --------------------------------------------------------------------------- one-time setup

def _rgb(h: str) -> dict:
    h = h.lstrip("#")
    return {"red": round(int(h[0:2], 16) / 255, 3), "green": round(int(h[2:4], 16) / 255, 3), "blue": round(int(h[4:6], 16) / 255, 3)}


def _cf_rule(index: int, grid_range: dict, formula: str, fmt: dict) -> dict:
    return {"addConditionalFormatRule": {"index": index, "rule": {
        "ranges": [grid_range],
        "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": formula}]},
                        "format": fmt}}}}


def setup_values() -> list[dict]:
    """Header rows + category QUERY formulas, as update_values calls."""
    ops = []
    hdr = [JOB_COLUMNS]
    for tab in (ALL_JOBS, NEEDS):
        ops.append({"op": "update", "range": f"{q(tab)}!A1:{LAST_JOB_COL}1", "values": hdr})
    for tab in TABS:
        f = (f"=QUERY({q(ALL_JOBS)}!A1:{LAST_JOB_COL}, \"select * where F = '{tab}' "
             f"order by B desc\", 1)")
        ops.append({"op": "update", "range": f"{q(tab)}!A1", "values": [[f]]})
    ops.append({"op": "update", "range": f"{q(TRACKER)}!A1:{col_letter(len(TRACKER_COLUMNS)-1)}1", "values": [TRACKER_COLUMNS]})
    ops.append({"op": "update", "range": f"{q(STATS)}!A1:{col_letter(len(STATS_COLUMNS)-1)}1", "values": [STATS_COLUMNS]})
    ops.append({"op": "update", "range": f"{q(INDEX)}!A1:{col_letter(len(INDEX_COLUMNS)-1)}1", "values": [INDEX_COLUMNS]})
    return ops


def setup_format_requests(sheet_ids: dict[str, int]) -> list[dict]:
    """batchUpdate requests: frozen headers, filters, widths, highlighting, dropdowns, hidden index."""
    reqs: list[dict] = []
    header_fmt = {"userEnteredFormat": {"textFormat": {"bold": True, "foregroundColorStyle": {"rgbColor": _rgb("#FFFFFF")}},
                                        "backgroundColorStyle": {"rgbColor": _rgb("#1F3A5F")},
                                        "wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE"}}
    n_job = len(JOB_COLUMNS)
    for tab, sid in sheet_ids.items():
        ncols = {TRACKER: len(TRACKER_COLUMNS), STATS: len(STATS_COLUMNS), INDEX: len(INDEX_COLUMNS)}.get(tab, n_job)
        reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                                               "fields": "gridProperties.frozenRowCount"}})
        reqs.append({"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0,
                                              "endColumnIndex": ncols},
                                    "cell": header_fmt, "fields": "userEnteredFormat.textFormat,userEnteredFormat.backgroundColorStyle,userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment"}})
        if tab in (ALL_JOBS, NEEDS, TRACKER, STATS):
            reqs.append({"setBasicFilter": {"filter": {"range": {"sheetId": sid, "startRowIndex": 0, "startColumnIndex": 0,
                                                                 "endColumnIndex": ncols}}}})
        if tab in (ALL_JOBS, NEEDS):
            reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenColumnCount": 1}},
                                                   "fields": "gridProperties.frozenColumnCount"}})
            # column widths: description narrow + clipped so rows stay one line tall
            reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0,
                                                                 "endIndex": n_job}, "properties": {"pixelSize": 140}, "fields": "pixelSize"}})
            for name, px in (("Job Title", 240), ("Job Description", 320), ("Direct Application Link", 260),
                             ("Additional Notes", 320), ("Required Skills", 220)):
                i = JOB_COLUMNS.index(name)
                reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i,
                                                                     "endIndex": i + 1}, "properties": {"pixelSize": px}, "fields": "pixelSize"}})
            reqs.append({"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": n_job},
                                        "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP", "verticalAlignment": "TOP"}},
                                        "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment"}})
            reqs.append({"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": MONTHLY_COL_IDX,
                                                  "endColumnIndex": MONTHLY_COL_IDX + 1},
                                        "cell": {"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "\"$\"#,##0\"/mo\""}}},
                                        "fields": "userEnteredFormat.numberFormat"}})
            rng = {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": n_job}
            m = col_of("Monthly Salary Equivalent")
            # Highest priority first: new today (blue Job ID), closed (grey), high-paying (gold), priority band (green)
            id_col = {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 1}
            reqs.append(_cf_rule(0, id_col, '=OR($B2=TODAY(),$B2=TEXT(TODAY(),"yyyy-mm-dd"))',
                                 {"backgroundColorStyle": {"rgbColor": _rgb("#CFE2F3")}, "textFormat": {"bold": True}}))
            reqs.append(_cf_rule(1, rng, f'=REGEXMATCH(${STATUS_COL}2,"^(Closed|Moved)")',
                                 {"textFormat": {"strikethrough": True, "foregroundColorStyle": {"rgbColor": _rgb("#999999")}}}))
            if tab == ALL_JOBS:   # pay bands only for confirmed jobs
              reqs.append(_cf_rule(2, rng, f"=AND(ISNUMBER(${m}2),${m}2>1000)",
                                 {"backgroundColorStyle": {"rgbColor": _rgb("#FFF2CC")}}))
              reqs.append(_cf_rule(3, rng, f"=AND(ISNUMBER(${m}2),${m}2>=500,${m}2<=1000)",
                                 {"backgroundColorStyle": {"rgbColor": _rgb("#D9EAD3")}}))
            reqs.append({"setDataValidation": {"range": {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": APP_STATUS_IDX,
                                                         "endColumnIndex": APP_STATUS_IDX + 1},
                                               "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": s} for s in APPLICATION_STATUSES]},
                                                        "strict": False, "showCustomUi": True}}})
        if tab == TRACKER:
            i = TRACKER_COLUMNS.index("Application Status")
            reqs.append({"setDataValidation": {"range": {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": i, "endColumnIndex": i + 1},
                                               "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": s} for s in APPLICATION_STATUSES]},
                                                        "strict": False, "showCustomUi": True}}})
            reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0,
                                                                 "endIndex": len(TRACKER_COLUMNS)}, "properties": {"pixelSize": 150}, "fields": "pixelSize"}})
        if tab == INDEX:
            reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid, "hidden": True}, "fields": "hidden"}})
    colors = {ALL_JOBS: "#1F3A5F", NEEDS: "#E69138", TRACKER: "#6AA84F", STATS: "#674EA7"}
    for tab, sid in sheet_ids.items():
        c = colors.get(tab, "#3D85C6" if tab in TABS else None)
        if c:
            reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid, "tabColorStyle": {"rgbColor": _rgb(c)}},
                                                   "fields": "tabColorStyle"}})
    return reqs


# --------------------------------------------------------------------------- per-run plan

_LOOKS_PARSED = __import__("re").compile(r"^[=+\-@]|^[\d.,:/ eE+\-]+$|^\d{4}-\d{2}")


def cell(v):
    """Keep text as text: Sheets would otherwise turn '1E5', '2026-11-25' or '=x' into numbers/dates/formulas."""
    if isinstance(v, str) and v and _LOOKS_PARSED.search(v):
        return "'" + v
    return v


def _clean(rows: list[list]) -> list[list]:
    return [[cell(v) for v in r] for r in rows]


def _runs(rows: list[int]) -> list[list[int]]:
    """Group sorted row numbers into contiguous runs."""
    out: list[list[int]] = []
    for r in sorted(rows):
        if out and r == out[-1][-1] + 1:
            out[-1].append(r)
        else:
            out.append([r])
    return out


def range_updates(tab: str, first_col: str, last_col: str, row_ids: list[str],
                  changes: dict[str, list], header_rows: int = 1) -> list[dict]:
    """Turn {job_id: [values...]} into contiguous update_values ops using the live row order."""
    pos = {jid: i + 1 + header_rows for i, jid in enumerate(row_ids) if jid}
    rows = {pos[j]: v for j, v in changes.items() if j in pos}
    ops = []
    for run in _runs(list(rows)):
        ops.append({"op": "update", "range": f"{q(tab)}!{first_col}{run[0]}:{last_col}{run[-1]}",
                    "values": _clean([rows[r] for r in run])})
    return ops


def append_op(tab: str, rows: list[list], last_col: str) -> list[dict]:
    if not rows:
        return []
    return [{"op": "append", "range": f"{q(tab)}!A1:{last_col}1", "values": _clean(rows)}]
