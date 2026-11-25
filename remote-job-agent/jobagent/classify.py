"""Job category, relevance and seniority, all decided from the title.

Matching on the title (not the description) is deliberate. Almost every job
description says "marketing" somewhere, so using it would flag engineers and
sales reps as marketing roles.
"""
from __future__ import annotations

import re

TABS = ["Content Writing", "Social Media", "Affiliate Marketing", "Digital Marketing",
        "SEO and Growth", "Other Marketing Roles"]

# Order matters: first match wins (most specific first).
_CATEGORY_RULES: list[tuple[str, str]] = [
    ("Affiliate Marketing", r"affiliate|partnerships? marketing|partner marketing|influencer partnerships?|"
                            r"creator partnerships?|creator (?:program|relations)|partner(?:ship)?s? (?:manager|specialist|associate|executive|coordinator)"),
    ("Social Media", r"social media|social[- ]content|\bsocial (?:manager|specialist|strategist|lead|coordinator|executive|marketing)|"
                     r"instagram|tiktok|youtube|linkedin (?:marketing|content)|community (?:manager|marketing|specialist|associate|coordinator|lead|moderator)|"
                     r"reddit|\bsmm\b"),
    ("SEO and Growth", r"\bseo\b|search engine|\bsem\b|\bppc\b|paid (?:ads|media|social|search|acquisition|marketing)|"
                       r"google ads|meta ads|facebook ads|growth|performance marketing|user acquisition|"
                       r"acquisition marketing|\bcro\b|conversion rate"),
    ("Content Writing", r"content writ|writer|copywrit|copy writ|copy ?editor|content strateg|content marketing|"
                        r"content (?:specialist|editor|manager|associate|executive|lead|producer|coordinator)|"
                        r"\beditor\b|blog|technical content|ghostwrit|storytell|content distribution"),
    ("Other Marketing Roles", r"brand marketing|marketing operations|marketing ops|product marketing|field marketing|"
                              r"event marketing|demand gen"),
    ("Digital Marketing", r"digital marketing|email marketing|e-?mail (?:specialist|marketer)|lifecycle|crm marketing|"
                          r"marketing automation|influencer marketing|online reputation|\borm\b|"
                          r"marketing (?:associate|executive|specialist|coordinator|assistant|generalist)|"
                          r"digital (?:specialist|executive|associate)|ecommerce marketing|e-commerce marketing"),
    ("Other Marketing Roles", r"brand marketing|brand (?:specialist|associate|coordinator)|marketing operations|"
                              r"marketing ops|product marketing|field marketing|event marketing|demand gen|"
                              r"marketing analyst|\bmarketing\b|marketer|public relations|\bpr (?:specialist|associate)|"
                              r"communications (?:specialist|associate|coordinator)"),
]
_CATEGORY_RX = [(tab, re.compile(p, re.I)) for tab, p in _CATEGORY_RULES]

# Titles that contain marketing-ish words but are a different job.
_EXCLUDE = re.compile(
    r"engineer|developer|\bdevops\b|architect|scientist|data analyst|programmer|"
    r"account executive|\bsdr\b|\bbdr\b|sales (?:development|representative|rep|executive|manager|associate)|"
    r"business development rep|customer success|customer support|support (?:specialist|agent)|"
    r"recruit|talent acquisition|\bhr\b|teacher|tutor|\besl\b|nurse|driver|"
    r"content (?:moderator|moderation|reviewer|review)|annotat|ai (?:trainer|tutor|writing evaluator)|"
    r"data label|rater|transcri|translator|interpreter|"
    r"graphic designer|ui/ux|ux designer|product designer|video editor|motion designer|"
    r"paralegal|attorney|lawyer|accountant|bookkeep|actuar|underwrit|"
    r"legal writer|grant writer|medical writer|medical copy|clinical|pharma",
    re.I)

_SENIOR = re.compile(
    r"\bsenior\b|\bsr\.?\b|\blead\b|\bprincipal\b|\bstaff\b|\bhead of\b|\bhead,|\bdirector\b|\bvp\b|"
    r"vice president|\bchief\b|\bcmo\b|\bexecutive director\b|\bmanaging\b|\bgroup manager\b|"
    r"\bmanager ii\b|\bmanager iii\b|\b(?:iii|iv)\b|\bexpert\b",
    re.I)

JUNIOR_TITLE = re.compile(r"\bjunior\b|\bjr\.?\b|entry[- ]level|\bassociate\b|\btrainee\b|\bfresher\b|"
                          r"\bgraduate\b|\bassistant\b|\bcoordinator\b|\bexecutive\b|\bi\b$", re.I)
MANAGER_TITLE = re.compile(r"\bmanager\b|\bstrategist\b", re.I)


def category_for(title: str) -> str:
    for tab, rx in _CATEGORY_RX:
        if rx.search(title or ""):
            return tab
    return ""


def is_excluded_title(title: str) -> bool:
    return bool(_EXCLUDE.search(title or ""))


def is_senior_title(title: str) -> bool:
    return bool(_SENIOR.search(title or ""))


def title_is_relevant(title: str) -> bool:
    """Cheap pre-filter used by sources that list hundreds of jobs per company."""
    return bool(category_for(title)) and not is_excluded_title(title)
