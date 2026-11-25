"""SQLite working store for a run.

The durable history lives in the Google Sheet (visible tabs plus the hidden
_Index tab). Each run rebuilds this database from that history, adds the day's
results, and uploads the file to Google Drive as a dated backup. Losing a
container therefore never loses data.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY, title_key TEXT, url_key TEXT, scope TEXT,
  decision TEXT, tab TEXT, status TEXT, company TEXT, title TEXT,
  first_seen TEXT, last_seen TEXT, last_verified TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS sightings (
  run_date TEXT, job_id TEXT, source TEXT, url TEXT, decision TEXT, reason TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  run_date TEXT, started TEXT, finished TEXT, stats TEXT
);
CREATE INDEX IF NOT EXISTS ix_title ON jobs(title_key);
CREATE INDEX IF NOT EXISTS ix_url ON jobs(url_key);
"""


class Store:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(path))
        self.con.executescript(SCHEMA)

    def upsert_history(self, e) -> None:
        self.con.execute(
            "INSERT OR IGNORE INTO jobs(job_id,title_key,url_key,scope,tab,status,last_verified,company,title) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (e.job_id, e.title_key, e.url_key, e.scope, e.tab, e.status, e.last_verified, *(e.label.split(" — ", 1) + [""])[:2]))

    def save_job(self, job, run_date: str) -> None:
        self.con.execute(
            "INSERT INTO jobs(job_id,title_key,url_key,scope,decision,tab,status,company,title,first_seen,last_seen,last_verified,data) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET last_seen=excluded.last_seen, "
            "last_verified=excluded.last_verified, data=excluded.data",
            (job.job_id, getattr(job, "title_key", ""), job.url_key, getattr(job, "scope", ""), job.ev.decision,
             job.ev.category, "Open", job.raw.company, job.raw.title, run_date, run_date, run_date,
             json.dumps(job.to_dict())))

    def sighting(self, run_date, job_id, source, url, decision, reason) -> None:
        self.con.execute("INSERT INTO sightings VALUES(?,?,?,?,?,?)", (run_date, job_id, source, url, decision, reason))

    def set_status(self, job_id, status, verified) -> None:
        self.con.execute("UPDATE jobs SET status=?, last_verified=? WHERE job_id=?", (status, verified, job_id))

    def log_run(self, run_date, started, finished, stats: dict) -> None:
        self.con.execute("INSERT INTO runs VALUES(?,?,?,?)", (run_date, started, finished, json.dumps(stats)))

    def commit(self):
        self.con.commit()

    def close(self):
        self.con.commit()
        self.con.close()
