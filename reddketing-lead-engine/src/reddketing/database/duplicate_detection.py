"""Multi-signal duplicate detection against every historical record.

Signals, strongest first:
  1. root domain (any domain ever recorded for the company, including redirect targets)
  2. domain label across TLDs (example.com vs example.de) when names also agree
  3. normalised name / alias equality
  4. normalised name equal to an existing company's domain label ("Example AI" vs exampleai.com)
  5. parent-company relationship (a product of an already-listed company)
  6. fuzzy core-name match (conservative: treated as duplicate so nobody is emailed twice)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from ..utils.normalize import core_name, domain_label, normalize_name, root_domain, similarity
from . import schema


@dataclass
class KnownCompany:
    name: str
    domains: set[str]
    names: set[str]           # normalised names + aliases
    core: str
    parent: str
    tab: str
    reconsider_after: str = ""   # for rejected rows only
    reconsiderable: bool = False


@dataclass
class DuplicateMatch:
    existing_name: str
    existing_domain: str
    reason: str
    strength: str     # "strong" | "probable"
    tab: str
    matching_name: str = ""


@dataclass
class DuplicateIndex:
    companies: list[KnownCompany] = field(default_factory=list)
    by_domain: dict[str, KnownCompany] = field(default_factory=dict)
    by_label: dict[str, list[KnownCompany]] = field(default_factory=dict)
    by_name: dict[str, KnownCompany] = field(default_factory=dict)

    def add(self, kc: KnownCompany) -> None:
        self.companies.append(kc)
        for d in kc.domains:
            self.by_domain.setdefault(d, kc)
            lbl = domain_label(d)
            if lbl:
                self.by_label.setdefault(lbl, []).append(kc)
        for n in kc.names:
            if n:
                self.by_name.setdefault(n, kc)

    # ------------------------------------------------------------------
    @classmethod
    def from_sheets(cls, master_rows: list[dict], rejected_rows: list[dict] | None = None,
                    daily_rows: list[dict] | None = None, funded_rows: list[dict] | None = None) -> "DuplicateIndex":
        idx = cls()
        for r in master_rows:
            domains = {root_domain(d) for d in _split(r.get("All Domains")) + [r.get("Official Domain", ""),
                                                                                r.get("Website", "")]}
            names = {normalize_name(r.get("Company Name", "")), r.get("Normalized Company Name", "")}
            names |= {normalize_name(a) for a in _split(r.get("Aliases"))}
            idx.add(KnownCompany(r.get("Company Name", ""), {d for d in domains if d}, {n for n in names if n},
                                 r.get("Core Name") or core_name(r.get("Company Name", "")),
                                 normalize_name(r.get("Parent Company", "")), schema.MASTER))
        # Daily/Funded rows are also in Master, but index them too in case Master was edited by hand.
        for tab, rows in ((schema.DAILY, daily_rows or []), (schema.FUNDED, funded_rows or [])):
            for r in rows:
                d = root_domain(r.get("Official Domain", "") or r.get("Website", ""))
                idx.add(KnownCompany(r.get("Company Name", ""), {d} if d else set(),
                                     {normalize_name(r.get("Company Name", ""))},
                                     core_name(r.get("Company Name", "")), "", tab))
        for r in rejected_rows or []:
            d = root_domain(r.get("Official Domain", "") or r.get("Website", ""))
            idx.add(KnownCompany(r.get("Company Name", ""), {d} if d else set(),
                                 {normalize_name(r.get("Company Name", ""))}, core_name(r.get("Company Name", "")),
                                 "", schema.REJECTED, r.get("Reconsider After", ""),
                                 str(r.get("Can Be Reconsidered", "")).lower() in ("yes", "true")))
        return idx

    def match(self, name: str, url_or_domain: str = "", *, aliases: list[str] | None = None,
              parent: str = "", extra_domains: list[str] | None = None) -> DuplicateMatch | None:
        domains = {root_domain(d) for d in [url_or_domain, *(extra_domains or [])]}
        domains.discard("")
        nname = normalize_name(name)
        ncore = core_name(name)
        alias_names = {normalize_name(a) for a in (aliases or [])} - {""}

        for d in domains:  # 1. exact root domain
            kc = self.by_domain.get(d)
            if kc:
                return DuplicateMatch(kc.name, d, f"same root domain ({d})", "strong", kc.tab, kc.name)
        for d in domains:  # 2. same label, different TLD + name agreement
            for kc in self.by_label.get(domain_label(d), []):
                if similarity(nname, normalize_name(kc.name)) >= 0.75 or ncore == kc.core:
                    other = next(iter(kc.domains), "")
                    return DuplicateMatch(kc.name, other, f"country/TLD variant of {other}", "strong", kc.tab, kc.name)
        for n in {nname} | alias_names:  # 3. name / alias
            kc = self.by_name.get(n)
            if kc and n:
                return DuplicateMatch(kc.name, next(iter(kc.domains), ""), "same normalised name or alias",
                                      "strong", kc.tab, kc.name)
        if nname and nname in self.by_label:  # 4. name == existing domain label
            kc = self.by_label[nname][0]
            return DuplicateMatch(kc.name, next(iter(kc.domains), ""), "name matches existing domain",
                                  "strong", kc.tab, kc.name)
        for d in domains:
            lbl = domain_label(d)
            kc = self.by_name.get(lbl)
            if kc and len(lbl) >= 4:
                return DuplicateMatch(kc.name, next(iter(kc.domains), ""), "domain matches existing name",
                                      "strong", kc.tab, kc.name)
        nparent = normalize_name(parent)
        if nparent:  # 5. parent company
            kc = self.by_name.get(nparent)
            if kc:
                return DuplicateMatch(kc.name, next(iter(kc.domains), ""), f"product of existing company {kc.name}",
                                      "probable", kc.tab, kc.name)
        if len(ncore) >= 5:  # 6. fuzzy core name
            for kc in self.companies:
                if kc.core and kc.core == ncore:
                    return DuplicateMatch(kc.name, next(iter(kc.domains), ""), "same core brand name",
                                          "probable", kc.tab, kc.name)
        return None

    @staticmethod
    def rejected_is_reconsiderable(m: DuplicateMatch, index: "DuplicateIndex", today: date) -> bool:
        if m.tab != schema.REJECTED:
            return False
        for kc in index.companies:
            if kc.tab == schema.REJECTED and kc.name == m.existing_name and kc.reconsiderable and kc.reconsider_after:
                try:
                    return date.fromisoformat(kc.reconsider_after) <= today
                except ValueError:
                    return False
        return False


def reconsider_date(today: date, days: int) -> str:
    return (today + timedelta(days=days)).isoformat()


def _split(value) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in str(value).replace(",", "\n").splitlines() if p.strip()]
