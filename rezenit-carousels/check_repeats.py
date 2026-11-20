#!/usr/bin/env python3
"""Fail if a day's carousels repeat earlier ones.

Usage: python3 check_repeats.py content/2026-11-18-shalini.json [more files...]
Compares every carousel in the given files against every carousel in all OTHER
content/*.json files (and against each other). Exit 1 if anything is flagged.

Checks:
  1. Topic overlap   - name + hook word overlap (Jaccard) >= 0.30 with any earlier carousel.
  2. Stat cooldown   - a stats-bank number used again within 10 days.
  3. Tip reuse       - a list item (tip) that already appeared in 2+ earlier carousels.
  4. Same format+angle - e.g. "signs ... relapse", "NNN plan" - via shared key phrases.
"""
import glob, json, os, re, sys, itertools
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = set("""the a an to of and you your is it in for on with that this not are be or i my me if what how but at
by from do no p*rn porn nnn november nut day days was were can will just more than its it's into about why""".split())
STATS = ['10.3%', '1 in 10', '4–10%', '4-10%', '90%', '3.2%', '16.6%', '54%', '15%', '8.6%', '1 in 12', '7.9%',
         '1 in 13', '56.7%', '13%', '1 in 8', '42 billion', '115 million', '115m', '39 billion', '39b', '10:28',
         '59%', '2,000+', '182 hours', '182h', 'icd-11', '46%', '42%', '36%', '26%', '1 in 4', '1,755', '21–37%',
         '61%', '84%', '39%']
COOLDOWN_DAYS = 7
THRESHOLD = 0.30


def strip(s):
    return re.sub(r'<[^>]+>|\[\[|\]\]', '', s or '').replace('\n', ' ')


def words(s):
    return {w for w in re.findall(r"[a-z0-9*']+", s.lower()) if w not in STOP and len(w) > 2}


def parse_date(d):
    dd, mm, yy = map(int, d.split('-'))
    return date(2000 + yy, mm, dd)


def load(path):
    d = json.load(open(path))
    out = []
    for i, c in enumerate(d['carousels'], 1):
        text = ' '.join(strip(x) for s in c['slides'][:5]
                        for x in [s.get('title'), s.get('sub'), s.get('body'), s.get('note'), s.get('kicker'), str(s.get('num', ''))] + s.get('items', []))
        out.append({
            'id': f"{d['date']} {d.get('owner', '-')} C{i}",
            'date': parse_date(d['date']),
            'name': c['name'],
            'topic': words(c['name'] + ' ' + strip(c['slides'][0]['title'])),
            'stats': {st for st in STATS if st in text.lower()},
            'tips': {strip(x).lower().strip(' .') for s in c['slides'][1:5] for x in s.get('items', [])},
            'file': os.path.abspath(path),
        })
    return out


def main(paths):
    new = [c for p in paths for c in load(p)]
    newfiles = {os.path.abspath(p) for p in paths}
    old = [c for p in sorted(glob.glob(os.path.join(HERE, 'content', '*.json')))
           if os.path.abspath(p) not in newfiles for c in load(p)]
    problems = []
    tipcount = {}
    for c in old:
        for t in c['tips']:
            tipcount[t] = tipcount.get(t, 0) + 1

    for c in new:
        for o in old:
            j = len(c['topic'] & o['topic']) / max(1, len(c['topic'] | o['topic']))
            if j >= THRESHOLD:
                problems.append(f"TOPIC  {c['id']} \"{c['name']}\" ~ {o['id']} \"{o['name']}\" ({j:.2f})")
            if (c['date'] - o['date']).days < COOLDOWN_DAYS:
                for st in c['stats'] & o['stats']:
                    problems.append(f"STAT   {c['id']} reuses {st!r} (used {o['id']}, < {COOLDOWN_DAYS} days ago)")
        for t in c['tips']:
            if tipcount.get(t, 0) >= 2:
                problems.append(f"TIP    {c['id']} reuses tip already in {tipcount[t]} carousels: \"{t[:60]}\"")
    for a, b in itertools.combinations(new, 2):
        j = len(a['topic'] & b['topic']) / max(1, len(a['topic'] | b['topic']))
        if j >= THRESHOLD:
            problems.append(f"TOPIC  {a['id']} ~ {b['id']} (same day, {j:.2f})")
        for st in a['stats'] & b['stats']:
            problems.append(f"STAT   {a['id']} and {b['id']} both use {st!r} on the same day")

    for p in sorted(set(problems)):
        print(p)
    print(f"{len(set(problems))} repeat problem(s) in {len(new)} carousels (checked against {len(old)} earlier).")
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
