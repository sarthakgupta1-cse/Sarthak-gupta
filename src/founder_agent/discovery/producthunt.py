"""Product Hunt via the official GraphQL v2 API.

Makers list themselves on their own launches, which is about as clear a signal
of 'this is a founder, and they want to be found' as exists. Needs a free
developer token; the source sits the run out quietly without one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import EmailStatus, Lead, extract_emails, harvest_socials
from ..utils import clean_text, domain_of
from .base import DiscoverySource

API = "https://api.producthunt.com/v2/api/graphql"

QUERY = """
query($after: String, $postedAfter: DateTime) {
  posts(order: VOTES, postedAfter: $postedAfter, first: 20, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges { node {
      name tagline description url website votesCount createdAt
      topics(first: 5) { edges { node { name } } }
      makers { name headline twitterUsername websiteUrl username }
    } }
  }
}
"""


class ProductHuntSource(DiscoverySource):
    name = "producthunt"

    def available(self) -> tuple[bool, str]:
        ok, why = super().available()
        if not ok:
            return ok, why
        if not self.settings.producthunt_token:
            return False, "PRODUCTHUNT_TOKEN not set"
        return True, ""

    async def discover(self, limit: int) -> list[Lead]:
        days_back = self.config.get("days_back", 30)
        posted_after = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).isoformat(timespec="seconds")

        headers = {
            "Authorization": f"Bearer {self.settings.producthunt_token}",
            "Content-Type": "application/json",
        }
        keywords = [k.lower() for k in self.settings.targeting.get("keywords", [])]
        leads: list[Lead] = []
        cursor = None

        while len(leads) < limit:
            resp = await self.client.post(
                API,
                headers=headers,
                json={"query": QUERY, "variables": {"after": cursor, "postedAfter": posted_after}},
            )
            if resp is None or resp.status_code >= 400:
                self.log.warning(
                    "Product Hunt returned %s",
                    resp.status_code if resp else "no response",
                )
                break

            payload = resp.json()
            if "errors" in payload:
                self.log.warning("Product Hunt error: %s", payload["errors"][:1])
                break

            posts = payload.get("data", {}).get("posts", {})
            for edge in posts.get("edges", []):
                node = edge["node"]
                blob = " ".join([
                    node.get("tagline") or "", node.get("description") or "",
                    " ".join(t["node"]["name"] for t in node.get("topics", {}).get("edges", [])),
                ]).lower()
                # Keep it to software companies we'd actually pitch.
                generic = ("software", "api", "platform", "tool", "app")
                on_target = (
                    not keywords
                    or any(k in blob for k in keywords)
                    or "saas" in blob
                    or any(t in blob for t in generic)
                )
                if not on_target:
                    continue

                website = node.get("website") or ""
                for maker in node.get("makers", []) or []:
                    lead = Lead(
                        full_name=maker.get("name") or "",
                        role=clean_text(maker.get("headline") or "", 120) or "Maker / Founder",
                        company=node.get("name") or "",
                        company_url=website,
                        company_domain=domain_of(website),
                        twitter_handle=maker.get("twitterUsername") or "",
                        personal_site=maker.get("websiteUrl") or "",
                        bio=clean_text(node.get("tagline") or ""),
                        source=self.name,
                        source_url=node.get("url") or "",
                        launched_at=node.get("createdAt") or "",
                        notes=[
                            f"PH launch: {node.get('name')} "
                            f"({node.get('votesCount', 0)} votes)"
                        ],
                    )
                    text = f"{maker.get('headline') or ''} {maker.get('websiteUrl') or ''}"
                    harvest_socials(text, lead)
                    found = extract_emails(text)
                    if found:
                        lead.email = found[0]
                        lead.email_status = EmailStatus.PUBLISHED
                        lead.email_source = "producthunt_profile"
                    leads.append(lead)
                    if len(leads) >= limit:
                        break
                if len(leads) >= limit:
                    break

            page = posts.get("pageInfo", {})
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")

        return leads[:limit]
