"""Plain CSV, for when you just want the file."""

from __future__ import annotations

import csv
from pathlib import Path

from ..models import Lead
from .base import COLUMNS, Sink


class CsvSink(Sink):
    name = "csv"

    def write(self, leads: list[Lead]) -> int:
        path = Path(self.settings.output.get("csv_path", "./out/leads.csv"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows(leads))
        return len(leads)
