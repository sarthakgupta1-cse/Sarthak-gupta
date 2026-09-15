from founder_agent.models import EmailStatus, Lead
from founder_agent.sinks.csv_ import CsvSink
from founder_agent.sinks.gsheets import _cell
from founder_agent.sinks.sqlite import SqliteSink


def _settings(settings, tmp_path):
    settings.output = {
        "sqlite_path": str(tmp_path / "leads.db"),
        "csv_path": str(tmp_path / "leads.csv"),
    }
    return settings


def test_sqlite_rerun_updates_instead_of_duplicating(settings, tmp_path):
    sink = SqliteSink(_settings(settings, tmp_path))
    lead = Lead(full_name="Ada", email="ada@acme.io", email_status=EmailStatus.GUESSED)
    sink.write([lead])
    sink.write([lead])
    assert len(sink.existing_keys()) == 1


def test_sqlite_rerun_never_blanks_a_known_field(settings, tmp_path):
    import sqlite3
    sink = SqliteSink(_settings(settings, tmp_path))
    sink.write([Lead(full_name="Ada Lovelace", email="ada@acme.io", role="Founder")])
    # A later, thinner sighting of the same person must not erase the role.
    sink.write([Lead(full_name="Ada Lovelace", email="ada@acme.io", role="")])
    conn = sqlite3.connect(sink.path)
    role = conn.execute("SELECT role FROM leads").fetchone()[0]
    conn.close()
    assert role == "Founder"


def test_csv_writes_all_columns(settings, tmp_path):
    settings = _settings(settings, tmp_path)
    CsvSink(settings).write([Lead(full_name="Ada", email="ada@acme.io")])
    content = (tmp_path / "leads.csv").read_text()
    assert "full_name" in content and "telegram_handle" in content
    assert "ada@acme.io" in content


def test_sheets_neutralises_formula_injection():
    # A scraped bio containing a formula must not execute inside the sheet.
    assert _cell("=IMPORTXML(A1,\"//x\")").startswith("'")
    assert _cell("+1-555").startswith("'")
    assert _cell("Ada Lovelace") == "Ada Lovelace"
