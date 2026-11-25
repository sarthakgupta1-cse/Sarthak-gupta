"""Converts CompanyProfiles into sheet rows."""
from __future__ import annotations

from datetime import date

from ..models import CompanyProfile
from ..qualification.opportunity_scoring import score_reasons_text
from ..qualification.reddketing_fit import reddit_suitability, subreddit_text
from ..research.contact_research import generic_business_email
from ..research.funding_research import funding_amount, funding_date, funding_round, funding_source
from ..research.pricing_research import format_pricing
from ..research.revenue_estimator import usd
from ..research.traffic_research import traffic_summary
from ..utils.normalize import core_name, normalize_name
from . import schema

NA = "Not publicly available"


def record_id(run_date: str, domain: str) -> str:
    return f"{run_date}:{domain}"


def _num(x):
    return round(x) if isinstance(x, (int, float)) else ""


def _contacts(p: CompanyProfile) -> dict:
    founders = [c.name for c in p.contacts if "founder" in c.title.lower()]
    generic = generic_business_email(p.sources, p.domain)
    emails = [f"{c.name}: {c.email}" for c in p.contacts if c.email]
    if generic:
        emails.append(f"General: {generic}")
    statuses = [f"{c.name}: {c.email_status}; identified via {c.source_url} (confidence {c.confidence})"
                for c in p.contacts]
    return {
        "Founder Names": ", ".join(founders) or NA,
        "Decision-Maker Names": ", ".join(c.name for c in p.contacts) or NA,
        "Decision-Maker Designations": "\n".join(f"{c.name} — {c.title}" for c in p.contacts) or NA,
        "LinkedIn URLs": "\n".join(f"{c.name}: {c.linkedin_url}" for c in p.contacts if c.linkedin_url) or "Not found in public sources",
        "Public Business Email": "\n".join(emails) or "Not publicly verified",
        "Contact Verification Status": "\n".join(statuses) or "No decision-makers identified in public sources",
    }


def _scores(p: CompanyProfile) -> dict:
    s = p.scores
    if not s:
        return {}
    return {"Revenue Score": s.revenue.points, "Reddit Opportunity Score": s.reddit_opportunity.points,
            "Product-Market Fit Score": s.product_market_fit.points, "Marketing Growth Score": s.marketing_growth.points,
            "Funding Score": s.funding.points, "Community Potential Score": s.community_potential.points,
            "Total Opportunity Score": s.total, "Opportunity Tier": s.tier, "Score Reasons": score_reasons_text(s)}


def _sources_text(p: CompanyProfile) -> str:
    lines = []
    for s in p.sources:
        label = {"company_page": "official site", "third_party_page": "article/page read",
                 "search_snippet": "search snippet (not fully read)", "news_headline": "news headline",
                 "feed_item": "feed item"}[s.kind]
        lines.append(f"[{label}] {s.url}")
    return "\n".join(lines[:20])


def _signal_text(p: CompanyProfile, *types) -> str:
    sigs = p.signals_of(*types)
    if not sigs:
        return NA
    return "\n".join(f"{s.value_text} ({s.claim_type.replace('_', ' ')}) — {p.source_url(s.source_id)}" for s in sigs[:5])


def _first_value(p: CompanyProfile, *types) -> str:
    for s in p.signals_of(*types):
        if s.claim_type != "unverified":
            return s.value_text
    return NA


def common_fields(p: CompanyProfile, run_date: str) -> dict:
    ex = p.extraction
    f = ex.funding
    traffic, traffic_src = traffic_summary(p)
    rev = p.revenue
    revenue_notes = []
    if rev.arr_derived:
        revenue_notes.append("ARR-derived monthly equivalent, not independently verified MRR.")
    if ex.discrepancies:
        revenue_notes.append("Source discrepancies: " + "; ".join(ex.discrepancies))
    return {
        "Record ID": record_id(run_date, p.domain), "Discovery Date": run_date, "Company Name": ex.company_name,
        "Normalized Company Name": normalize_name(ex.company_name), "Official Domain": p.domain, "Website": p.website,
        "Industry": ex.industry, "Product Category": ex.product_category, "Product Description": ex.one_line_description,
        "Headquarters": ex.headquarters or NA, "Country": ex.country or NA, "Founded Year": ex.founded_year or NA,
        "Estimated MRR Minimum": _num(rev.mrr_low) or NA, "Estimated MRR Maximum": _num(rev.mrr_high) or NA,
        "Estimated ARR": (f"{usd(rev.arr_low)}–{usd(rev.arr_high)}" if rev.arr_low else NA),
        "Revenue Confidence": rev.confidence.value,
        "Revenue Evidence": "\n".join(rev.evidence) or NA,
        "Revenue Calculation": f"{rev.method}. {rev.calculation}",
        "Revenue Assumptions": "\n".join(rev.assumptions) or "None",
        "Pricing": format_pricing(ex.pricing), "Estimated Monthly Traffic": traffic, "Traffic Source": traffic_src,
        "Customer Count": _first_value(p, "paying_customers", "business_customers", "total_users"),
        "Customer Evidence": _signal_text(p, "paying_customers", "business_customers", "total_users", "app_downloads",
                                          "app_ratings_count", "reviews_count"),
        "Employee Count": _first_value(p, "employees"),
        "Total Funding": usd(f.total_funding_usd) if f.total_funding_usd else NA,
        "Latest Funding Round": funding_round(p) or NA, "Latest Funding Date": funding_date(p) or NA,
        **_contacts(p),
        "Reddit Suitability": reddit_suitability(p), "Relevant Subreddits": subreddit_text(p),
        "Relevant Audience": ex.reddit.relevant_audience or NA,
        "Reddketing Opportunity Explanation": ex.reddit.explanation,
        **_scores(p),
        "Primary Sources": _sources_text(p),
        "Sources Accessed Date": p.sources[0].accessed_at if p.sources else run_date,
        "Research Notes": "\n".join(filter(None, [ex.research_notes, *revenue_notes, *p.validation_notes[:8],
                                                  "Reddit fit assessed from public info; no Reddit listening performed."])),
        "Lead Status": "New",
    }


def daily_row(p: CompanyProfile, run_date: str) -> dict:
    return common_fields(p, run_date)


def funded_row(p: CompanyProfile, run_date: str) -> dict:
    c = common_fields(p, run_date)
    f = p.extraction.funding
    amount = funding_amount(p)
    src = funding_source(p)
    return {
        **c,
        "Funding Round": funding_round(p) or NA, "Amount Raised (USD)": _num(amount) or NA,
        "Announcement Date": funding_date(p) or NA,
        "Lead Investors": ", ".join(f.lead_investors) or NA,
        "Total Known Funding (USD)": _num(f.total_funding_usd) or NA,
        "Founders": c["Founder Names"],
        "Revenue Notes": (f"{c['Revenue Calculation']} Funding is not revenue." if p.revenue.mrr_low
                          else "Revenue not publicly verifiable; listed as a funding-backed prospect."),
        "Reddit Marketing Opportunity": f"{c['Reddit Suitability']}. {c['Reddketing Opportunity Explanation']}",
        "Sources": (f"[funding] {src}\n" if src else "") + c["Primary Sources"],
    }


def master_row(p: CompanyProfile, run_date: str, list_type: str) -> dict:
    c = common_fields(p, run_date)
    ex = p.extraction
    return {
        "Company Key": p.domain, "Company Name": ex.company_name, "Normalized Company Name": normalize_name(ex.company_name),
        "Core Name": core_name(ex.company_name), "Official Domain": p.domain,
        "All Domains": "\n".join(sorted(set(p.all_domains) | {p.domain})), "Aliases": "\n".join(ex.aliases),
        "Parent Company": ex.parent_company or "", "Website": p.website, "Industry": ex.industry,
        "Product Category": ex.product_category, "Product Description": ex.one_line_description,
        "Headquarters": c["Headquarters"], "Country": c["Country"], "List Type": list_type,
        "First Discovered Date": run_date, "Last Updated Date": run_date, "Emailed Date": "", "Times Seen": 1,
        "Estimated MRR Minimum": c["Estimated MRR Minimum"], "Estimated MRR Maximum": c["Estimated MRR Maximum"],
        "Revenue Confidence": c["Revenue Confidence"], "Total Funding": c["Total Funding"],
        "Latest Funding Round": c["Latest Funding Round"], "Latest Funding Date": c["Latest Funding Date"],
        "Decision-Maker Names": c["Decision-Maker Names"], "LinkedIn URLs": c["LinkedIn URLs"],
        "Public Business Email": c["Public Business Email"],
        "Total Opportunity Score": c.get("Total Opportunity Score", ""), "Primary Sources": c["Primary Sources"],
        "Lead Status": "New" if list_type != "rejected" else "Rejected", "Notes": "",
    }


def rejected_row(p_or_name, run_date: str, reason: str, *, website: str = "", domain: str = "", evidence: str = "",
                 reconsiderable: bool = True, reconsider_after: str = "") -> dict:
    if isinstance(p_or_name, CompanyProfile):
        p = p_or_name
        return {"Record ID": record_id(run_date, p.domain), "Company Name": p.extraction.company_name,
                "Website": p.website, "Official Domain": p.domain, "Rejection Date": run_date,
                "Reason for Rejection": reason, "Evidence": evidence or p.revenue.calculation,
                "Can Be Reconsidered": reconsiderable, "Reconsider After": reconsider_after if reconsiderable else "",
                "Total Opportunity Score": p.scores.total if p.scores else "",
                "Estimated MRR Range": (f"{usd(p.revenue.mrr_low)}–{usd(p.revenue.mrr_high)}" if p.revenue.mrr_low else NA),
                "Revenue Confidence": p.revenue.confidence.value}
    return {"Record ID": record_id(run_date, domain or normalize_name(str(p_or_name))), "Company Name": p_or_name,
            "Website": website, "Official Domain": domain, "Rejection Date": run_date, "Reason for Rejection": reason,
            "Evidence": evidence, "Can Be Reconsidered": reconsiderable,
            "Reconsider After": reconsider_after if reconsiderable else "", "Total Opportunity Score": "",
            "Estimated MRR Range": NA, "Revenue Confidence": "Insufficient"}


def tabs_for_rows() -> dict:
    return {"daily": schema.DAILY, "funded": schema.FUNDED, "master": schema.MASTER, "rejected": schema.REJECTED}


def today_str(d: date) -> str:
    return d.isoformat()
