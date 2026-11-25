"""CV/cover letter generation with a clearly fictional profile (the real one is not in the repo)."""
import yaml

from jobagent.applications.generate import generate_one, tailor

PROFILE = yaml.safe_load("""
name: Test Person
location: Testville, India
email: test@example.com
summary: Writer with email marketing experience.
skills: [Copywriting, SEO, Email marketing, Canva]
experience:
  - title: Writer
    company: Example Co
    start: Jan 2023
    end: Present
    bullets:
      - {text: Ran weekly newsletters., tags: [Email marketing]}
      - {text: Wrote SEO blog posts., tags: [SEO, Content writing]}
education: [{degree: BA, school: Test University, year: '2022'}]
""")
JOB = {"job_id": "RJ-TEST", "raw": {"company": "Acme", "title": "SEO Content Writer",
                                    "description": "We need SEO and Ahrefs skills."},
       "ev": {"category": "SEO and Growth"}}


def test_tailor_reorders_but_never_invents():
    t = tailor(PROFILE, JOB)
    assert t["experience"][0]["bullets"][0] == "Wrote SEO blog posts."
    all_bullets = {b["text"] for r in PROFILE["experience"] for b in r["bullets"]}
    assert set(t["experience"][0]["bullets"]) == all_bullets
    assert t["skills"][0] == "SEO"


def test_files_written(tmp_path):
    d = generate_one(PROFILE, JOB, tmp_path)
    for f in ("Customized_CV.pdf", "Customized_CV.docx", "Cover_Letter.pdf", "Cover_Letter.docx", "Job_Description.txt"):
        assert (d / f).stat().st_size > 0
    assert d.parent.name == "Acme" and d.name == "SEO_Content_Writer"
