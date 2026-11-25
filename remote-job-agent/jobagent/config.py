from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_settings(path: str | os.PathLike | None = None) -> dict:
    p = Path(path) if path else ROOT / "config" / "settings.yaml"
    with open(p, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_companies(settings: dict) -> dict:
    rel = settings["sources"]["ats_boards"]["companies_file"]
    with open(ROOT / rel, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
