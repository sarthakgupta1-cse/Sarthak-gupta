#!/usr/bin/env python3
"""Merge the original 363-row table with the expansion rows into one CSV.

Original rows live in build_sheet.ROWS (tuples). Expansion rows live in
extra_rows.txt, one per line, '@@@'-delimited:
    title @@@ category @@@ language @@@ kind @@@ id
Deduplicated by YouTube id/path; first occurrence wins.
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sheet import ROWS as BASE_ROWS, url_for

HERE = os.path.dirname(os.path.abspath(__file__))

def load_extra(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("@@@")
            if len(parts) != 5:
                print(f"  ! malformed line {n}: {len(parts)} fields", file=sys.stderr)
                continue
            title, cat, lang, kind, ident = (p.strip() for p in parts)
            out.append((title, cat, lang, kind, ident))
    return out

def main(out_path):
    extra = load_extra(os.path.join(HERE, "extra_rows.txt"))
    print(f"base rows:  {len(BASE_ROWS)}")
    print(f"extra rows: {len(extra)}")

    seen, rows, dupes = set(), [], 0
    for title, cat, lang, kind, ident in list(BASE_ROWS) + extra:
        if ident in seen:
            dupes += 1
            continue
        seen.add(ident)
        rows.append((title, cat, lang, kind, ident))

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["#", "Title", "Category", "Language", "Type",
                    "URL", "Video / Playlist ID", "Watched?", "Rating", "Notes"])
        for i, (title, cat, lang, kind, ident) in enumerate(rows, 1):
            w.writerow([i, title, cat, lang, kind.capitalize(),
                        url_for(kind, ident), ident, "", "", ""])

    print(f"duplicates dropped: {dupes}")
    print(f"UNIQUE ROWS WRITTEN: {len(rows)} -> {out_path}")
    cats, langs, kinds = {}, {}, {}
    for _, c, l, k, _ in rows:
        cats[c] = cats.get(c, 0) + 1
        langs[l] = langs.get(l, 0) + 1
        kinds[k] = kinds.get(k, 0) + 1
    print(f"\ncategories: {len(cats)}   languages: {len(langs)}")
    print("types: " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "porn_addiction_youtube_videos.csv"))
