"""Persistent run state + single-writer lock stored in the _RunState tab.

Stages: started -> researched -> sheets_written -> emailed -> completed.
A retry on the same date resumes from the last completed stage, so companies are
never researched/inserted twice and a failed email is re-sent from stored rows.
"""
from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import schema

LOCK_TTL = timedelta(hours=3)
STAGES = ["started", "researched", "sheets_written", "emailed", "completed"]


class LockHeld(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class RunState:
    run_date: str
    run_id: str
    stage: str = "started"
    status: str = "running"
    attempts: int = 1

    def reached(self, stage: str) -> bool:
        return STAGES.index(self.stage) >= STAGES.index(stage)


class RunStateStore:
    def __init__(self, sheets):
        self.sheets = sheets
        self.owner = f"{os.getenv('GITHUB_RUN_ID', 'local')}@{socket.gethostname()}"

    def get(self, run_date: str) -> dict | None:
        for row in self.sheets.read_records(schema.RUN_STATE):
            if row.get("Run Date") == run_date:
                return row
        return None

    def acquire(self, run_date: str, run_id: str, *, force: bool = False) -> RunState:
        row = self.get(run_date)
        if row is None:
            self.sheets.append_rows(schema.RUN_STATE, [{
                "Run Date": run_date, "Run ID": run_id, "Stage": "started", "Status": "running",
                "Lock Owner": self.owner, "Lock Heartbeat (UTC)": _now(), "Attempts": 1}])
            return RunState(run_date, run_id)
        status = row.get("Status", "")
        heartbeat = row.get("Lock Heartbeat (UTC)", "")
        if status == "running" and not force and row.get("Lock Owner") != self.owner:
            try:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat)
            except ValueError:
                age = LOCK_TTL + timedelta(seconds=1)
            if age < LOCK_TTL:
                raise LockHeld(f"run for {run_date} is locked by {row.get('Lock Owner')} (heartbeat {heartbeat})")
        attempts = int(row.get("Attempts") or 0) + 1
        self.sheets.update_where(schema.RUN_STATE, "Run Date", run_date, {
            "Status": "running", "Lock Owner": self.owner, "Lock Heartbeat (UTC)": _now(), "Attempts": attempts})
        return RunState(run_date, row.get("Run ID") or run_id, row.get("Stage") or "started", "running", attempts)

    def advance(self, state: RunState, stage: str, **extra) -> None:
        state.stage = stage
        updates = {"Stage": stage, "Lock Heartbeat (UTC)": _now()}
        if stage == "sheets_written":
            updates["Sheets Written At"] = _now()
        if stage == "emailed":
            updates["Email Sent At"] = _now()
        updates.update(extra)
        self.sheets.update_where(schema.RUN_STATE, "Run Date", state.run_date, updates)

    def release(self, state: RunState, status: str, error: str = "") -> None:
        state.status = status
        self.sheets.update_where(schema.RUN_STATE, "Run Date", state.run_date, {
            "Status": status, "Lock Owner": "", "Last Error": error[:2000], "Lock Heartbeat (UTC)": _now()})
