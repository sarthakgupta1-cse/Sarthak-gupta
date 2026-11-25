"""Sheet layout: one line per row, readable header, frozen name column, sensible widths.

Long text (evidence, sources, notes) is clipped to the cell instead of wrapping, so every row stays
one line high; clicking a cell shows its full text. The requests are idempotent and are re-sent on
every run, so rows added later keep the same layout.
"""
from __future__ import annotations

from .schema import COLUMNS

HEADER_HEIGHT = 42
ROW_HEIGHT = 24
DEFAULT_WIDTH = 130

# Columns whose content is a sentence or a list: wider, still clipped.
WIDE = {
    "Product Description", "Revenue Evidence", "Revenue Calculation", "Revenue Assumptions", "Pricing",
    "Customer Evidence", "Reddketing Opportunity Explanation", "Score Reasons", "Primary Sources", "Sources",
    "Research Notes", "Reason for Rejection", "Evidence", "Errors", "Notes", "Revenue Notes",
    "Reddit Marketing Opportunity", "Relevant Audience", "Last Error", "Duplicate Reason",
}
MEDIUM = {
    "Company Name", "Newly Discovered Company", "Matched Existing Company", "Official Domain", "Website",
    "Industry", "Product Category", "Decision-Maker Names", "Decision-Maker Designations", "LinkedIn URLs",
    "Public Business Email", "Relevant Subreddits", "Founders", "Founder Names", "Lead Investors",
    "Headquarters", "Contact Verification Status", "Reddit Suitability", "Opportunity Tier", "Run ID",
    "Email Delivery Status", "Google Sheets Update Status",
}
NARROW = {"Revenue Score", "Reddit Opportunity Score", "Product-Market Fit Score", "Marketing Growth Score",
          "Funding Score", "Community Potential Score", "Total Opportunity Score", "Country", "Founded Year",
          "Revenue Confidence", "Lead Status", "Times Seen", "Match Strength", "Can Be Reconsidered", "Status",
          "Stage", "Attempts", "Budget Mode"}
HIDDEN_HELPERS = {"Record ID", "Normalized Company Name", "Core Name", "Company Key"}

HEADER_BG = {"red": 0.12, "green": 0.22, "blue": 0.39}
WHITE = {"red": 1, "green": 1, "blue": 1}


def width_for(column: str) -> int:
    if column in WIDE:
        return 280
    if column in MEDIUM:
        return 170
    if column in NARROW:
        return 95
    if column in HIDDEN_HELPERS:
        return 80
    return DEFAULT_WIDTH


def frozen_columns(header: list[str]) -> int:
    """Freeze up to and including the company-name column so it stays visible when scrolling right."""
    for name in ("Company Name", "Newly Discovered Company", "Run ID", "Run Date"):
        if name in header:
            return header.index(name) + 1
    return 0


def layout_requests(sheet_id: int, header: list[str], row_count: int) -> list[dict]:
    n_cols = len(header)
    whole = {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": row_count,
             "startColumnIndex": 0, "endColumnIndex": n_cols}
    reqs: list[dict] = [
        # Every cell: clip long text, vertically centred, one font.
        {"repeatCell": {"range": whole,
                        "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP", "verticalAlignment": "MIDDLE",
                                                       "textFormat": {"fontFamily": "Arial", "fontSize": 10}}},
                        "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment,"
                                  "userEnteredFormat.textFormat.fontFamily,userEnteredFormat.textFormat.fontSize"}},
        # Header row: bold white on navy, wrapped so long names fit.
        {"repeatCell": {"range": {**whole, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"backgroundColor": HEADER_BG, "wrapStrategy": "WRAP",
                                                       "verticalAlignment": "MIDDLE",
                                                       "textFormat": {"bold": True, "foregroundColor": WHITE,
                                                                      "fontFamily": "Arial", "fontSize": 10}}},
                        "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.wrapStrategy,"
                                  "userEnteredFormat.verticalAlignment,userEnteredFormat.textFormat"}},
        {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "ROWS",
                                                 "startIndex": 0, "endIndex": 1},
                                       "properties": {"pixelSize": HEADER_HEIGHT}, "fields": "pixelSize"}},
        {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "gridProperties": {
            "frozenRowCount": 1, "frozenColumnCount": frozen_columns(header)}},
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
    ]
    if row_count > 1:
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 1, "endIndex": row_count},
            "properties": {"pixelSize": ROW_HEIGHT}, "fields": "pixelSize"}})
    start = 0
    for i in range(1, n_cols + 1):  # one request per run of equal widths
        if i == n_cols or width_for(header[i]) != width_for(header[start]):
            reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": start, "endIndex": i},
                "properties": {"pixelSize": width_for(header[start])}, "fields": "pixelSize"}})
            start = i
    return reqs


def all_layout_requests(sheets: dict[str, tuple[int, int]]) -> list[dict]:
    """sheets: tab title -> (sheetId, rowCount). Only known tabs are formatted."""
    reqs: list[dict] = []
    for tab, (sheet_id, rows) in sheets.items():
        if tab in COLUMNS:
            reqs += layout_requests(sheet_id, COLUMNS[tab], rows)
    return reqs
