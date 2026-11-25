from jobagent import sheets as S
from jobagent.dedup import DedupIndex, IndexEntry, keys_for
from jobagent.text import norm_company, norm_title, norm_url


def test_normalisers():
    assert norm_company("Acme Technologies Pvt. Ltd.") == "acme"
    assert norm_title("Sr. Content Writer (Remote) - India") == "senior content writer"
    assert norm_url("https://www.x.com/jobs/1?utm_source=a") == "x.com/jobs/1"


def test_same_job_two_boards_matches():
    a = keys_for("Acme Inc", "Content Writer (Remote)", "worldwide", ["https://acme.com/jobs/1"])
    b = keys_for("ACME", "Content Writer", "worldwide", ["https://himalayas.app/x?utm_source=api"])
    assert a[0] == b[0] and a[1] == b[1]


def test_index_match_rules():
    idx = DedupIndex()
    jid, tk, uks = keys_for("Acme", "SEO Writer", "india", ["https://acme.com/j/9"])
    idx.add(IndexEntry(jid, tk, ",".join(uks), "india", "A", "Open"))
    # same URL, retitled
    assert idx.match("RJ-X", "other", keys_for("x", "y", "", ["https://acme.com/j/9?ref=1"])[2], "unknown") == jid
    # same company+title, unknown scope
    assert idx.match("RJ-Y", tk, [], "unknown") == jid
    # same company+title but a different explicit scope → different vacancy
    assert idx.match("RJ-Z", tk, [], "worldwide") is None


def test_range_updates_contiguous():
    ops = S.range_updates("All Jobs", "U", "V", ["A", "B", "C", "", "E"], {"B": [1, 2], "C": [3, 4], "E": [5, 6]})
    assert [o["range"] for o in ops] == ["'All Jobs'!U3:V4", "'All Jobs'!U6:V6"]


def test_cell_sanitizer():
    assert S.cell("1E5A") == "1E5A" and S.cell("1E50") == "'1E50"
    assert S.cell("2026-11-25") == "'2026-11-25" and S.cell("=HYPERLINK()") == "'=HYPERLINK()"
    assert S.cell("RJ-AB12") == "RJ-AB12" and S.cell(700.0) == 700.0


def test_columns():
    assert len(S.JOB_COLUMNS) == 29 and S.LAST_JOB_COL == "AC"
    assert S.VERIFIED_COL == "U" and S.STATUS_COL == "V"
    assert S.col_of("Monthly Salary Equivalent") == "O" and S.col_of("Category") == "F"


def test_updates_as_requests():
    r = S.updates_as_requests([{"op": "update", "range": "'Needs Verification'!U5:V6", "values": [["'2026-11-25", "Open"], ["'2026-11-25", "x"]]}])[0]["updateCells"]
    assert r["start"] == {"sheetId": 7, "rowIndex": 4, "columnIndex": 20}
    assert r["rows"][0]["values"][0] == {"userEnteredValue": {"stringValue": "2026-11-25"}}
    assert S.updates_as_requests([{"op": "update", "range": "'_Index'!AB3", "values": [[1]]}])[0]["updateCells"]["start"]["columnIndex"] == 27
