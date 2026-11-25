"""Pull the named tools/skills a posting asks for (for the Required Skills column)."""
from __future__ import annotations

import re

SKILLS = [
    "SEO", "Copywriting", "Content strategy", "Content marketing", "Editing", "Proofreading", "Blogging",
    "Social media", "Community management", "Email marketing", "Marketing automation", "Affiliate marketing",
    "Influencer marketing", "Partnerships", "Paid social", "PPC", "Google Ads", "Meta Ads", "TikTok", "Instagram",
    "LinkedIn", "YouTube", "Reddit", "X/Twitter", "Google Analytics", "GA4", "Google Search Console", "Looker Studio",
    "Ahrefs", "Semrush", "Moz", "Screaming Frog", "WordPress", "Webflow", "HubSpot", "Salesforce", "Klaviyo",
    "Mailchimp", "Braze", "Customer.io", "Iterable", "Canva", "Figma", "Adobe", "CapCut", "Hootsuite", "Sprout Social",
    "Buffer", "Later", "Notion", "Asana", "Jira", "Excel", "Google Sheets", "SQL", "HTML", "A/B testing", "CRO",
    "Analytics", "Impact.com", "PartnerStack", "CJ Affiliate", "ShareASale", "Rakuten", "Awin", "ChatGPT/AI tools",
    "Video", "Storytelling", "Research", "Fluent English",
]
_PATTERNS = {
    "SEO": r"\bseo\b", "PPC": r"\bppc\b", "GA4": r"\bga4\b", "CRO": r"\bcro\b|conversion rate optimi",
    "X/Twitter": r"\btwitter\b|\bx \(twitter\)", "ChatGPT/AI tools": r"chatgpt|\bgenai\b|generative ai|ai tools|\bllm",
    "Fluent English": r"fluent (?:in )?english|excellent (?:written )?english|native[- ]level english|english proficiency",
    "Meta Ads": r"meta ads|facebook ads|meta business", "Video": r"\bvideo\b", "Research": r"\bresearch\b",
    "Analytics": r"\banalytics\b", "Editing": r"\bediting\b|\bedit\b", "Social media": r"social media",
    "Adobe": r"adobe|photoshop|premiere|illustrator", "HTML": r"\bhtml\b", "SQL": r"\bsql\b",
}


def extract_skills(text: str, limit: int = 12) -> str:
    t = text or ""
    found = []
    for s in SKILLS:
        pat = _PATTERNS.get(s, r"\b" + re.escape(s.lower()) + r"\b")
        if re.search(pat, t, re.I):
            found.append(s)
        if len(found) >= limit:
            break
    return ", ".join(found)
