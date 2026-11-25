"""Google Sheets tab names and column layouts (the database schema)."""

DAILY = "Daily Discoveries"
MASTER = "Master Company Database"
FUNDED = "Recently Funded Companies"
REJECTED = "Rejected - Low Potential"
DUPLICATES = "Duplicate Detection Log"
RUN_LOG = "Daily Run Log"
RUN_STATE = "_RunState"

SCORE_COLS = ["Revenue Score", "Reddit Opportunity Score", "Product-Market Fit Score", "Marketing Growth Score",
              "Funding Score", "Community Potential Score", "Total Opportunity Score", "Opportunity Tier", "Score Reasons"]

CONTACT_COLS = ["Founder Names", "Decision-Maker Names", "Decision-Maker Designations", "LinkedIn URLs",
                "Public Business Email", "Contact Verification Status"]

COLUMNS: dict[str, list[str]] = {
    DAILY: [
        "Record ID", "Discovery Date", "Company Name", "Normalized Company Name", "Official Domain", "Website",
        "Industry", "Product Category", "Product Description", "Headquarters", "Country", "Founded Year",
        "Estimated MRR Minimum", "Estimated MRR Maximum", "Estimated ARR", "Revenue Confidence",
        "Revenue Evidence", "Revenue Calculation", "Revenue Assumptions", "Pricing",
        "Estimated Monthly Traffic", "Traffic Source", "Customer Count", "Customer Evidence", "Employee Count",
        "Total Funding", "Latest Funding Round", "Latest Funding Date", *CONTACT_COLS,
        "Reddit Suitability", "Relevant Subreddits", "Relevant Audience", "Reddketing Opportunity Explanation",
        *SCORE_COLS, "Primary Sources", "Sources Accessed Date", "Research Notes", "Lead Status",
    ],
    MASTER: [
        "Company Key", "Company Name", "Normalized Company Name", "Core Name", "Official Domain", "All Domains",
        "Aliases", "Parent Company", "Website", "Industry", "Product Category", "Product Description",
        "Headquarters", "Country", "List Type", "First Discovered Date", "Last Updated Date", "Emailed Date",
        "Times Seen", "Estimated MRR Minimum", "Estimated MRR Maximum", "Revenue Confidence", "Total Funding",
        "Latest Funding Round", "Latest Funding Date", "Decision-Maker Names", "LinkedIn URLs",
        "Public Business Email", "Total Opportunity Score", "Primary Sources", "Lead Status", "Notes",
    ],
    FUNDED: [
        "Record ID", "Discovery Date", "Company Name", "Normalized Company Name", "Official Domain", "Website",
        "Product Description", "Industry", "Headquarters", "Funding Round", "Amount Raised (USD)",
        "Announcement Date", "Lead Investors", "Total Known Funding (USD)", "Founders", "Employee Count",
        "Estimated MRR Minimum", "Estimated MRR Maximum", "Revenue Confidence", "Revenue Notes",
        "Reddit Marketing Opportunity", "Relevant Subreddits", "Decision-Maker Names",
        "Decision-Maker Designations", "LinkedIn URLs", "Public Business Email", "Contact Verification Status",
        *SCORE_COLS, "Sources", "Sources Accessed Date", "Research Notes", "Lead Status",
    ],
    REJECTED: [
        "Record ID", "Company Name", "Website", "Official Domain", "Rejection Date", "Reason for Rejection",
        "Evidence", "Can Be Reconsidered", "Reconsider After", "Total Opportunity Score",
        "Estimated MRR Range", "Revenue Confidence",
    ],
    DUPLICATES: [
        "Detection Date", "Newly Discovered Company", "New Domain", "Matched Existing Company", "Matched Domain",
        "Matching Name", "Duplicate Reason", "Match Strength", "Matched Tab", "Discovery Channel",
    ],
    RUN_LOG: [
        "Run ID", "Execution Date", "Start Time (IST)", "Completion Time (IST)", "Status",
        "Companies Discovered", "Companies Researched", "Companies Accepted", "Companies Rejected",
        "Duplicates Detected", "Funding Discoveries", "Search Queries", "LLM Calls", "LLM Input Tokens",
        "LLM Output Tokens", "HTTP Fetches", "Estimated API Cost (USD)", "Month-to-Date Cost (USD)",
        "Budget Mode", "Errors", "Email Delivery Status", "Google Sheets Update Status", "Notes",
    ],
    RUN_STATE: [
        "Run Date", "Run ID", "Stage", "Status", "Lock Owner", "Lock Heartbeat (UTC)", "Sheets Written At",
        "Email Sent At", "Email Message ID", "Attempts", "Last Error",
    ],
}

TAB_ORDER = [DAILY, MASTER, FUNDED, REJECTED, DUPLICATES, RUN_LOG, RUN_STATE]
