"""Tailored CV and cover letter per qualified job (DOCX + PDF).

Truthfulness by construction: every sentence of experience comes verbatim from
profile/profile.yaml, which is written from the user's own resume. Tailoring
only selects and reorders. Nothing is reworded into new claims.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from ..config import ROOT
from ..skills import extract_skills

PROFILE = ROOT / "profile" / "profile.yaml"
OUT = ROOT / "out"


def _safe(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s).strip("_")[:60] or "Unknown"


def _kw(job: dict) -> set[str]:
    raw = job["raw"]
    words = {w.strip().lower() for w in extract_skills(raw["description"] + " " + raw["title"], limit=40).split(",") if w.strip()}
    words |= {job["ev"]["category"].lower()}
    return words


def _score(text: str, tags: list[str], kws: set[str]) -> int:
    t = text.lower()
    return sum(2 for k in kws if k in {x.lower() for x in tags}) + sum(1 for k in kws if k in t)


def tailor(profile: dict, job: dict) -> dict:
    kws = _kw(job)
    cat = job["ev"]["category"]
    summary = (profile.get("summaries") or {}).get(cat) or profile.get("summary", "")
    skills = sorted(profile.get("skills", []), key=lambda s: (s.lower() not in kws and not any(s.lower() in k for k in kws)))
    exp = []
    for role in profile.get("experience", []):
        bullets = sorted(role.get("bullets", []), key=lambda b: -_score(b["text"], b.get("tags", []), kws))
        exp.append({**role, "bullets": [b["text"] for b in bullets]})
    projects = sorted(profile.get("projects", []), key=lambda p: -_score(p.get("description", ""), p.get("tags", []), kws))
    matched = [s for s in skills if s.lower() in kws or any(s.lower() in k for k in kws)]
    return {"summary": summary, "skills": skills, "experience": exp, "projects": projects[:3], "matched": matched}


def cover_letter_text(profile: dict, job: dict, t: dict, custom: str | None = None) -> str:
    if custom:
        return custom
    raw = job["raw"]
    top = [b for r in t["experience"] for b in r["bullets"][:1]][:2]
    matched = ", ".join(t["matched"][:4]) or ", ".join(t["skills"][:3])
    recent = t["experience"][0] if t["experience"] else None
    p1 = (f"I'm applying for the {raw['title']} role at {raw['company']}. ")
    p1 += (f"I work as {recent['title']} at {recent['company']}, and the role asks for {matched}, which is the work I do day to day."
           if recent else f"The role asks for {matched}, which matches the work I've been doing.")
    p2 = ("A few things from my work that relate to this role:\n" + "\n".join(f"• {b}" for b in top)) if top else ""
    p3 = (f"I'd welcome the chance to talk about how I could contribute to {raw['company']}'s marketing. "
          "I'm based in India and available to work remotely full-time.")
    return "\n\n".join(x for x in ["Dear Hiring Team,", p1, p2, p3, f"Kind regards,\n{profile['name']}"] if x)


def _docx_cv(path: Path, p: dict, t: dict, job: dict) -> None:
    from docx import Document
    from docx.shared import Pt
    d = Document()
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10.5)
    d.add_heading(p["name"], level=0)
    d.add_paragraph(" | ".join(filter(None, [p.get("location"), p.get("email"), p.get("phone"), *p.get("links", [])])))
    if p.get("headline"):
        d.add_paragraph(p["headline"]).runs[0].bold = True
    d.add_heading("Summary", level=1)
    d.add_paragraph(t["summary"])
    d.add_heading("Skills", level=1)
    d.add_paragraph(", ".join(t["skills"]))
    d.add_heading("Experience", level=1)
    for r in t["experience"]:
        para = d.add_paragraph()
        para.add_run(f"{r['title']} — {r['company']}").bold = True
        para.add_run(f"   {r.get('start', '')} – {r.get('end', '')}  {r.get('location', '')}")
        for b in r["bullets"]:
            d.add_paragraph(b, style="List Bullet")
    if t["projects"]:
        d.add_heading("Projects", level=1)
        for pr in t["projects"]:
            para = d.add_paragraph()
            para.add_run(pr["name"] + ": ").bold = True
            para.add_run(pr.get("description", ""))
    d.add_heading("Education", level=1)
    for e in p.get("education", []):
        d.add_paragraph(f"{e.get('degree', '')} — {e.get('school', '')} ({e.get('year', '')})")
    if p.get("certifications"):
        d.add_heading("Certifications", level=1)
        for c in p["certifications"]:
            d.add_paragraph(str(c), style="List Bullet")
    d.save(path)


def _docx_letter(path: Path, text: str) -> None:
    from docx import Document
    d = Document()
    for block in text.split("\n\n"):
        d.add_paragraph(block)
    d.save(path)


def _pdf(path: Path, blocks: list[tuple[str, str]]) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    ss = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    story = []
    for kind, txt in blocks:
        esc = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        style = {"title": ss["Title"], "h": ss["Heading3"], "b": ss["Bullet"]}.get(kind, ss["BodyText"])
        story.append(Paragraph(("• " + esc) if kind == "b" else esc, style))
        if kind in ("p",):
            story.append(Spacer(1, 4))
    doc.build(story)


def _cv_blocks(p, t):
    b = [("title", p["name"]), ("p", " | ".join(filter(None, [p.get("location"), p.get("email"), p.get("phone"), *p.get("links", [])])))]
    if p.get("headline"):
        b.append(("p", p["headline"]))
    b += [("h", "Summary"), ("p", t["summary"]), ("h", "Skills"), ("p", ", ".join(t["skills"])), ("h", "Experience")]
    for r in t["experience"]:
        b.append(("p", f"{r['title']} — {r['company']}   {r.get('start', '')} – {r.get('end', '')}  {r.get('location', '')}"))
        b += [("b", x) for x in r["bullets"]]
    if t["projects"]:
        b.append(("h", "Projects"))
        b += [("p", f"{pr['name']}: {pr.get('description', '')}") for pr in t["projects"]]
    b.append(("h", "Education"))
    b += [("p", f"{e.get('degree', '')} — {e.get('school', '')} ({e.get('year', '')})") for e in p.get("education", [])]
    return b


def generate_one(profile: dict, job: dict, base: Path, custom_letter: str | None = None) -> Path:
    raw = job["raw"]
    d = base / _safe(raw["company"]) / _safe(raw["title"])
    d.mkdir(parents=True, exist_ok=True)
    t = tailor(profile, job)
    letter = cover_letter_text(profile, job, t, custom_letter)
    _docx_cv(d / "Customized_CV.docx", profile, t, job)
    _pdf(d / "Customized_CV.pdf", _cv_blocks(profile, t))
    _docx_letter(d / "Cover_Letter.docx", letter)
    _pdf(d / "Cover_Letter.pdf", [("p", x) for x in letter.split("\n\n")])
    if not (d / "Job_Description.txt").exists():
        (d / "Job_Description.txt").write_text(f"{raw['title']}\n{raw['company']}\n\n{raw['description']}\n", encoding="utf-8")
    return d


def generate_all(limit: int = 0, profile_path: Path = PROFILE, state_path: Path | None = None) -> dict:
    if not profile_path.exists():
        return {"status": "skipped", "reason": "profile/profile.yaml not found: waiting for the updated resume"}
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    state = json.loads((state_path or OUT / "state.json").read_text(encoding="utf-8"))
    jobs = [j for j in state["new_jobs"] + state.get("promoted", []) if j["ev"]["decision"] == "qualified"]
    if limit:
        jobs = jobs[:limit]
    made = [str(generate_one(profile, j, OUT / "Job_Applications").relative_to(OUT)) for j in jobs]
    return {"status": "ok", "generated": len(made), "folders": made, "job_ids": [j["job_id"] for j in jobs]}
