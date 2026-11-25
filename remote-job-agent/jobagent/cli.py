"""Command line entry point:  python -m jobagent <command>

  discover   fetch + evaluate + dedupe + verify           → out/state.json
  plan       build sheet ops, report, stats, review, db    → out/plan.json, out/report.*
  run        discover + plan
  override   change one new job's decision after review
  set-original  attach + verify the employer's own posting for a new job
  setup      print the one-time spreadsheet setup ops/requests
  ops        print sheet ops in batches (for applying through the Sheets connector)
  docs       build CV + cover letter for qualified jobs (needs profile/profile.yaml)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import ROOT

LOG_DIR = ROOT / "logs"


def _logging(verbose: bool) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stderr),
                logging.FileHandler(LOG_DIR / f"run-{datetime.now():%Y-%m-%d}.log", encoding="utf-8")]
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format=fmt, handlers=handlers)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jobagent")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("discover", "run"):
        p = sub.add_parser(name)
        p.add_argument("--index", type=Path, help="JSON of _Index!A2:I values")
        p.add_argument("--all-ids", type=Path, help="JSON of 'All Jobs'!A2:A values")
        p.add_argument("--nv-ids", type=Path, help="JSON of 'Needs Verification'!A2:A values")
        p.add_argument("--only", nargs="*", help="limit to sources whose name contains these words")
        if name == "run":
            p.add_argument("--sheet-url", default="")
    p = sub.add_parser("plan")
    p.add_argument("--sheet-url", default="")
    p = sub.add_parser("override")
    p.add_argument("job_id")
    p.add_argument("decision", choices=["qualified", "needs_verification", "rejected"])
    p.add_argument("reason")
    p = sub.add_parser("set-original")
    p.add_argument("job_id")
    p.add_argument("url")
    p = sub.add_parser("setup")
    p.add_argument("--sheet-ids", type=Path, help="JSON {tab title: sheetId} once the tabs exist")
    p = sub.add_parser("ops")
    p.add_argument("--file", type=Path, default=ROOT / "out" / "plan.json")
    p.add_argument("--max-rows", type=int, default=25, help="split big appends into batches of this many rows")
    p = sub.add_parser("docs")
    p.add_argument("--limit", type=int, default=0)

    a = ap.parse_args(argv)
    _logging(a.verbose)

    if a.cmd in ("discover", "run"):
        from .pipeline import discover, plan
        st = discover(a.index, a.all_ids, a.nv_ids, only_sources=a.only)
        print(json.dumps({"new_jobs": len(st["new_jobs"]), "promoted": len(st["promoted"]),
                          "status_changes": len(st["status_changes"]), "counts": st["counts"],
                          "sources": [(s["name"], s["listings"], s["n_errors"]) for s in st["sources"]]}, indent=1))
        if a.cmd == "run":
            print(json.dumps(plan(sheet_url=a.sheet_url), indent=1, ensure_ascii=False))
    elif a.cmd == "plan":
        from .pipeline import plan
        print(json.dumps(plan(sheet_url=a.sheet_url), indent=1, ensure_ascii=False))
    elif a.cmd == "override":
        from .pipeline import override
        ok = override(a.job_id, a.decision, a.reason)
        print("updated" if ok else "job id not found among today's new jobs")
        return 0 if ok else 1
    elif a.cmd == "set-original":
        from .pipeline import set_original
        print(set_original(a.job_id, a.url))
    elif a.cmd == "setup":
        from . import sheets as S
        if a.sheet_ids:
            ids = json.loads(a.sheet_ids.read_text())
            print(json.dumps(S.setup_format_requests(ids), ensure_ascii=False))
        else:
            print(json.dumps(S.setup_values(), ensure_ascii=False, indent=1))
    elif a.cmd == "ops":
        ops = json.loads(a.file.read_text(encoding="utf-8"))["ops"]
        batches = []
        for op in ops:
            vals = op["values"]
            for i in range(0, len(vals), a.max_rows if op["op"] == "append" else len(vals) or 1):
                batches.append({**op, "values": vals[i:i + a.max_rows] if op["op"] == "append" else vals})
        for i, b in enumerate(batches, 1):
            print(f"### op {i}/{len(batches)}: {b['op']} {b['range']} ({len(b['values'])} rows)")
            print(json.dumps(b["values"], ensure_ascii=False))
    elif a.cmd == "docs":
        from .applications.generate import generate_all
        print(json.dumps(generate_all(limit=a.limit), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
