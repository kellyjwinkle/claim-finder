"""Scheduled discovery job (run via GitHub Actions).

This script is a scaffold: it defines the pipeline shape and writes staging
records with status='needs_verification'. It intentionally does NOT auto-verify
anything -- a human must confirm official-source indicators in the Streamlit
Settlement Inbox page before a settlement can be matched or filed against.

To make this live, plug in your preferred search/fetch method inside
`discover_candidate_settlements()` (e.g. an internal search API, RSS feeds from
settlement administrators, or a curated list of sources you trust).
"""
import os
import sys
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "app"))
from components.database import get_service_client  # noqa: E402

OFFICIAL_DOMAIN_HINTS = (
    "settlement", "claims", ".gov", "administrator",
)


def discover_candidate_settlements():
    """Return a list of candidate settlement dicts with at least:
    case_name, source_url, and optionally defendant/case_number/administrator/
    official_claim_url/claim_deadline/class_period_start/class_period_end.

    Replace this stub with your real discovery logic.
    """
    return []


def looks_official(url):
    url = (url or "").lower()
    return any(hint in url for hint in OFFICIAL_DOMAIN_HINTS)


def upsert_settlement(client, candidate):
    existing = client.table("settlements").select("id").eq(
        "case_name", candidate["case_name"]
    ).execute().data
    is_official = looks_official(candidate.get("official_claim_url", "")) and bool(
        candidate.get("case_number") and candidate.get("administrator")
    )
    status = "verified" if is_official else "needs_verification"
    payload = {
        "case_name": candidate["case_name"],
        "defendant": candidate.get("defendant"),
        "case_number": candidate.get("case_number"),
        "administrator": candidate.get("administrator"),
        "official_claim_url": candidate.get("official_claim_url"),
        "claim_deadline": candidate.get("claim_deadline"),
        "class_period_start": candidate.get("class_period_start"),
        "class_period_end": candidate.get("class_period_end"),
        "geographic_scope": candidate.get("geographic_scope"),
        "proof_requirements": candidate.get("proof_requirements"),
        "status": status,
        "last_checked_at": datetime.utcnow().isoformat(),
    }
    if existing:
        settlement_id = existing[0]["id"]
        client.table("settlements").update(payload).eq("id", settlement_id).execute()
    else:
        result = client.table("settlements").insert(payload).execute()
        settlement_id = result.data[0]["id"]

    client.table("settlement_sources").insert({
        "settlement_id": settlement_id,
        "source_type": "official_administrator" if is_official else "discovery",
        "source_url": candidate["source_url"],
        "is_official": is_official,
    }).execute()
    return settlement_id


def main():
    client = get_service_client()
    candidates = discover_candidate_settlements()
    for candidate in candidates:
        upsert_settlement(client, candidate)
    print(f"Processed {len(candidates)} candidate settlement(s).")


if __name__ == "__main__":
    main()
