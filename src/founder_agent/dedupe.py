"""Collapse the same human, found by several sources, into one record."""

from __future__ import annotations

from .models import Lead


def dedupe(leads: list[Lead]) -> list[Lead]:
    """Merge on the strongest shared identity signal, preserving field richness."""
    merged: dict[str, Lead] = {}
    # Aliases let a lead found by name+domain absorb one later found by email.
    alias: dict[str, str] = {}

    for lead in leads:
        keys = _identity_keys(lead)
        target = next((alias[k] for k in keys if k in alias), None)

        if target is None:
            primary = lead.dedupe_key()
            merged[primary] = lead
            for key in keys:
                alias[key] = primary
        else:
            merged[target].merge(lead)
            for key in keys:
                alias.setdefault(key, target)

    return list(merged.values())


def _identity_keys(lead: Lead) -> list[str]:
    """Every handle that uniquely identifies this person."""
    keys = [lead.dedupe_key()]
    if lead.email:
        keys.append(f"email:{lead.email.lower()}")
    if lead.linkedin_url:
        keys.append(f"li:{lead.linkedin_url.rstrip('/').lower().split('/in/')[-1]}")
    if lead.github_username:
        keys.append(f"gh:{lead.github_username.lower()}")
    if lead.twitter_handle:
        keys.append(f"tw:{lead.twitter_handle.lower()}")
    if lead.full_name and lead.company_domain:
        keys.append(f"nc:{lead.full_name.lower().strip()}|{lead.company_domain.lower()}")
    return keys
