"""SQLite: the run-to-run memory.

This is what makes the agent idempotent. Re-running never duplicates a person,
and `first_seen` is preserved so you can tell a new founder from one you've
already worked.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..models import Lead
from .base import COLUMNS, Sink


class SqliteSink(Sink):
    name = "sqlite"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self.path = Path(settings.output.get("sqlite_path", "./data/leads.db"))

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        cols = ",\n  ".join(f'"{c}" TEXT' for c in COLUMNS if c not in ("score", "headcount"))
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS leads (
  dedupe_key TEXT PRIMARY KEY,
  {cols},
  score INTEGER DEFAULT 0,
  headcount INTEGER,
  first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
  last_seen TEXT DEFAULT CURRENT_TIMESTAMP
)"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score)")
        conn.commit()
        return conn

    def write(self, leads: list[Lead]) -> int:
        conn = self._connect()
        written = 0
        try:
            for lead in leads:
                row = {c: lead.to_row().get(c, "") for c in COLUMNS}
                row["dedupe_key"] = lead.dedupe_key()
                fields = list(row.keys())
                placeholders = ",".join("?" for _ in fields)
                columns = ",".join(f'"{f}"' for f in fields)
                # Never overwrite a filled column with an empty one on re-run.
                updates = ",".join(
                    f'"{f}"=COALESCE(NULLIF(excluded."{f}", \'\'), leads."{f}")'
                    for f in fields
                    if f != "dedupe_key"
                )
                conn.execute(
                    f"INSERT INTO leads ({columns}) "
                    f"VALUES ({placeholders}) "
                    f"ON CONFLICT(dedupe_key) DO UPDATE SET {updates}, last_seen=CURRENT_TIMESTAMP",
                    [row[f] for f in fields],
                )
                written += 1
            conn.commit()
        finally:
            conn.close()
        return written

    def existing_keys(self) -> set[str]:
        """Keys already on file, so a run can skip paid enrichment for them."""
        if not self.path.exists():
            return set()
        conn = sqlite3.connect(self.path)
        try:
            cur = conn.execute("SELECT dedupe_key FROM leads")
            return {r[0] for r in cur.fetchall()}
        except sqlite3.OperationalError:
            return set()
        finally:
            conn.close()
