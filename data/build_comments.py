#!/usr/bin/env python3
"""Join drafted comments to the video index, using the same grouped ordering
as the uploaded Google Sheets (Part 1/2/3), so row numbers line up.

comments_raw.txt: one per line, "<grouped row #>@@@<comment text>"
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split_parts import PART1_ORDER

HERE = os.path.dirname(os.path.abspath(__file__))

def ordered_rows():
    rows = list(csv.DictReader(open(os.path.join(HERE, "porn_addiction_youtube_videos.csv"), encoding="utf-8")))
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["Category"], []).append(r)
    out = []
    for cat in PART1_ORDER:
        out.extend(by_cat.pop(cat, []))
    for cat in sorted(by_cat):
        out.extend(by_cat.pop(cat))
    return out

def main():
    rows = ordered_rows()
    comments = {}
    for line in open(os.path.join(HERE, "comments_raw.txt"), encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        n, _, text = line.partition("@@@")
        comments[int(n)] = text.strip()

    out = os.path.join(HERE, "video_comments.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["#", "Title", "Category", "URL", "Comment", "Posted?"])
        written = 0
        for i, r in enumerate(rows, 1):
            if i not in comments:
                continue
            w.writerow([i, r["Title"], r["Category"], r["URL"], comments[i], ""])
            written += 1

    lens = [len(c.split()) for c in comments.values()]
    print(f"{written} comments joined -> {out}")
    print(f"word count: min {min(lens)}, median {sorted(lens)[len(lens)//2]}, max {max(lens)}")
    print(f"remaining to write: {len(rows) - written}")
    # sanity: first and last mapped rows
    print(f"\nrow 1  -> {rows[0]['Title'][:55]}")
    print(f"row 82 -> {rows[81]['Title'][:55]}")

main()
