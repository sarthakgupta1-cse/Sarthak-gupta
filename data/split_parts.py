#!/usr/bin/env python3
"""Split the 1016-row index into 3 category-grouped parts for Google Sheets upload.

Part 1 (already uploaded) is rows 1-340 of the grouped ordering below.
This script regenerates the same ordering and writes parts 2 and 3.
"""
import csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "porn_addiction_youtube_videos.csv")

# Category order used for Part 1 (first 340 rows), then everything else.
PART1_ORDER = [
    "TED / TEDx", "General / Overview", "NoFap / Reboot", "Neuroscience",
    "Your Brain on Porn (Gary Wilson)", "Dr. K / HealthyGamerGG",
    "Porn-Induced ED (PIED)", "Clinical / Therapy", "Personal Testimony",
    "Andrew Huberman", "Jordan Peterson", "Faith - Christian", "Faith - Catholic",
    "Faith - LDS", "Faith - Islam", "Faith - Eastern / Sadhguru",
    "Gabor Mate / Trauma", "Women & Porn Addiction", "Debate / Is It Real?",
    "Relationships & Marriage", "Betrayal Trauma / Partners", "Teens / Parents",
    "Teens / Students", "Withdrawal / Flatline", "Relapse Prevention",
    "Signs / Self-Assessment", "Escalation / Tolerance", "Mental Health Effects",
    "Triggers / Coping", "Beginner Guides",
]

def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["Category"], []).append(r)

    ordered = []
    for cat in PART1_ORDER:
        ordered.extend(by_cat.pop(cat, []))
    for cat in sorted(by_cat):          # everything not in PART1_ORDER
        ordered.extend(by_cat.pop(cat))

    assert len(ordered) == len(rows), (len(ordered), len(rows))
    print(f"total {len(ordered)}; part1 ends at grouped index 340")
    print(f"row 340 = {ordered[339]['Title'][:60]!r} ({ordered[339]['Category']})")
    print(f"row 341 = {ordered[340]['Title'][:60]!r} ({ordered[340]['Category']})")

    parts = [(2, ordered[340:678]), (3, ordered[678:])]
    for n, chunk in parts:
        out = os.path.join(HERE, f"part{n}.csv")
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["#", "Title", "Category", "Language", "Type", "URL", "Watched?", "Notes"])
            for i, r in enumerate(chunk, 341 if n == 2 else 679):
                w.writerow([i, r["Title"], r["Category"], r["Language"],
                            r["Type"], r["URL"], "", ""])
        print(f"part{n}: {len(chunk)} rows, {os.path.getsize(out)} bytes -> {out}")

main()
