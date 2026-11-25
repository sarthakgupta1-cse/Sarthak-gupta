"""Daily email report (HTML + plain text). It never contains application URLs."""
from __future__ import annotations

import html
from collections import defaultdict

from .classify import TABS


def _pay(job) -> str:
    ev = job.ev
    if ev.monthly_usd is None:
        return "salary not disclosed"
    s = f"${ev.monthly_usd:,.0f}/month"
    if ev.currency == "INR" and ev.monthly_inr:
        s = f"₹{ev.monthly_inr:,.0f}/month (≈ ${ev.monthly_usd:,.0f})"
    elif ev.currency and ev.currency != "USD":
        s += f" (posted as {ev.original_salary})"
    return s


def build(date_label: str, subject: str, new_q: list, new_nv: list, closed: list[str], promoted: list[str],
          stats: dict, sheet_url: str, limitations: list[str]) -> tuple[str, str]:
    by_tab = defaultdict(list)
    for j in sorted(new_q, key=lambda j: -(j.ev.monthly_usd or 0)):
        by_tab[j.ev.category].append(j)
    companies = sorted({j.raw.company for j in new_q})
    high = stats.get("high_paying", 0)
    band = stats.get("priority_band", 0)

    # ---------------- plain text
    t = [f"Daily Remote Job Report", f"Date: {date_label}", ""]
    if new_q:
        t += [f"New Opportunities: {len(new_q)}", f"Companies Hiring: {len(companies)}",
              f"High-paying (> $1,000/month): {high}", f"Priority band ($500–$1,000/month): {band}", ""]
        for tab in TABS:
            if by_tab.get(tab):
                t.append(f"{tab} ({len(by_tab[tab])}):")
                t += [f"  • {j.raw.company} — {j.raw.title} — {_pay(j)}" for j in by_tab[tab]]
                t.append("")
        t.append("Companies hiring: " + ", ".join(companies))
    else:
        t.append("No new verified opportunities were found today.")
    t.append("")
    if new_nv:
        t.append(f"Needs Verification (salary or India eligibility unclear): {len(new_nv)} new. See the 'Needs Verification' tab.")
        t += [f"  • {j.raw.company} — {j.raw.title} ({'; '.join(j.ev.reasons)[:90]})" for j in new_nv[:15]]
        if len(new_nv) > 15:
            t.append(f"  … and {len(new_nv) - 15} more in the sheet")
        t.append("")
    if closed or promoted:
        t.append("Changes to earlier vacancies:")
        t += [f"  • Closed: {c}" for c in closed]
        t += [f"  • Now verified (moved to All Jobs): {p}" for p in promoted]
        t.append("")
    t += ["Run summary:",
          f"  Sources searched: {stats['sources_searched']} ({stats['sources_failed']} failed)",
          f"  Listings discovered: {stats['listings']} | relevant to your categories: {stats['relevant']}",
          f"  Duplicates removed: {stats['duplicates']}",
          f"  Rejected: salary {stats['rej_salary']}, location {stats['rej_location']}, experience {stats['rej_experience']}, "
          f"employment type {stats['rej_type']}",
          f"  Previously discovered vacancies now closed: {stats['closed']}",
          f"  Exchange rates: {stats['fx']}", ""]
    if sheet_url:
        t.append(f"Application links and full details: {sheet_url}")
    t.append("Limitations: " + " ".join(limitations))
    text = "\n".join(t)

    # ---------------- html
    e = html.escape
    h = ["<div style=\"font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222;max-width:680px\">",
         f"<h2 style=\"margin:0 0 4px\">Daily Remote Job Report</h2><div style=\"color:#666\">{e(date_label)}</div>"]
    if new_q:
        h.append("<table style=\"margin:14px 0;border-collapse:collapse\"><tr>" + "".join(
            f"<td style=\"padding:8px 14px;background:#F1F5FA;border:1px solid #DDE5EE;text-align:center\">"
            f"<div style=\"font-size:22px;font-weight:bold\">{v}</div><div style=\"color:#555;font-size:12px\">{k}</div></td>"
            for k, v in (("New opportunities", len(new_q)), ("Companies", len(companies)),
                         ("> $1,000/mo", high), ("$500–$1,000/mo", band))) + "</tr></table>")
        for tab in TABS:
            if by_tab.get(tab):
                h.append(f"<h3 style=\"margin:18px 0 6px;color:#1F3A5F\">{e(tab)} ({len(by_tab[tab])})</h3><ul style=\"margin:0;padding-left:20px\">")
                h += [f"<li><b>{e(j.raw.company)}</b> — {e(j.raw.title)} — {e(_pay(j))}</li>" for j in by_tab[tab]]
                h.append("</ul>")
    else:
        h.append("<p style=\"margin:16px 0;padding:12px;background:#F6F6F6\">No new verified opportunities were found today.</p>")
    if new_nv:
        h.append(f"<h3 style=\"margin:18px 0 6px;color:#B45F06\">Needs Verification ({len(new_nv)} new)</h3>"
                 "<p style=\"margin:0 0 6px;color:#555\">Salary or India eligibility isn't stated. These are kept apart in the 'Needs Verification' tab.</p><ul style=\"margin:0;padding-left:20px\">")
        h += [f"<li>{e(j.raw.company)} — {e(j.raw.title)} <span style=\"color:#888\">({e('; '.join(j.ev.reasons)[:90])})</span></li>" for j in new_nv[:15]]
        if len(new_nv) > 15:
            h.append(f"<li style=\"color:#888\">… and {len(new_nv) - 15} more in the sheet</li>")
        h.append("</ul>")
    if closed or promoted:
        h.append("<h3 style=\"margin:18px 0 6px\">Changes to earlier vacancies</h3><ul style=\"margin:0;padding-left:20px\">")
        h += [f"<li>Closed: {e(c)}</li>" for c in closed] + [f"<li>Now verified: {e(p)}</li>" for p in promoted]
        h.append("</ul>")
    h.append("<h3 style=\"margin:18px 0 6px\">Run summary</h3><table style=\"border-collapse:collapse;font-size:13px\">")
    rows = [("Sources searched", f"{stats['sources_searched']} ({stats['sources_failed']} failed)"),
            ("Listings discovered", f"{stats['listings']} (relevant: {stats['relevant']})"),
            ("Duplicates removed", stats["duplicates"]),
            ("Rejected — salary / location / experience / type",
             f"{stats['rej_salary']} / {stats['rej_location']} / {stats['rej_experience']} / {stats['rej_type']}"),
            ("Earlier vacancies now closed", stats["closed"]), ("Exchange rates", stats["fx"])]
    h += [f"<tr><td style=\"padding:3px 12px 3px 0;color:#555\">{e(str(k))}</td><td>{e(str(v))}</td></tr>" for k, v in rows]
    h.append("</table>")
    if sheet_url:
        h.append(f"<p style=\"margin-top:16px\">Application links and full details are in the "
                 f"<a href=\"{e(sheet_url)}\">Worldwide Remote Job Opportunities</a> sheet.</p>")
    h.append(f"<p style=\"color:#888;font-size:12px\">{e(' '.join(limitations))}</p></div>")
    return text, "".join(h)
