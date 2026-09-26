"""Scheduled discovery job (run via GitHub Actions).

Pulls candidate settlements from free, public sources and writes them to
Supabase as status='needs_verification'. Nothing here ever sets status to
'verified' automatically -- a human confirms official-source indicators
(case number, administrator, official claim URL) in the Streamlit
Settlement Inbox page before a settlement can be matched or filed against.

Sources wired in:
1. Top Class Actions - "Open Lawsuit Settlements" category page (scrape).
2. Claim Depot - settlements listing page (scrape).
3. CourtListener/RECAP API - used to *verify* a candidate's case number and
   court actually exist once you have a case name/number to check. This is
   NOT a discovery source; call `verify_with_courtlistener()` from the
   Streamlit Settlement Inbox page or a follow-up job.

Both scrapers are best-effort: legal-news sites restructure their HTML
periodically. If a source stops parsing, that source simply contributes zero
candidates that run -- it never crashes the whole job and never marks
anything verified on its own.
"""
import os
import re
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "app"))
from components.database import get_service_client  # noqa: E402

USER_AGENT = "ClaimFinder/1.0 (personal household tool; contact via GitHub repo)"
REQUEST_TIMEOUT = 20

OFFICIAL_DOMAIN_HINTS = ("settlement", "claims", ".gov", "administrator")

TOP_CLASS_ACTIONS_URL = "https://topclassactions.com/category/lawsuit-settlements/open-lawsuit-settlements/"
CLAIM_DEPOT_URL = "https://www.claimdepot.com/settlements"

COURTLISTENER_BASE = "https://www.courtlistener.com/api/rest/v4"


def _get(url):
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        print(f"WARNING: failed to fetch {url}: {exc}")
        return None


def _parse_us_date(text):
    """Parse a MM/DD/YYYY or 'Month D, YYYY' date string into ISO format."""
    text = text.strip()
    for fmt in ("%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def scrape_top_class_actions():
    """Parse the Top Class Actions 'open settlements' category page.

    Each entry on the page follows a repeating pattern of:
      <heading with settlement title>
      "Settlement" label + payout description
      "Deadline" label + MM/DD/YYYY
      "SUBMIT A CLAIM" link (the official claim URL)

    We walk the headings and read forward through sibling text/links until
    the next heading, pulling out the deadline and the claim link.
    """
    html = _get(TOP_CLASS_ACTIONS_URL)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    headings = soup.find_all(["h2", "h3", "h4"])
    for heading in headings:
        title = heading.get_text(strip=True)
        if not title or "class action settlement" not in title.lower():
            continue

        block_text = []
        claim_url = None
        node = heading
        for _ in range(25):
            node = node.find_next_sibling()
            if node is None or node.name in ("h2", "h3", "h4"):
                break
            text = node.get_text(" ", strip=True)
            if text:
                block_text.append(text)
            link = node.find("a", href=True)
            if link and ("claim" in link.get_text(strip=True).lower()
                          or "submit" in link.get_text(strip=True).lower()):
                claim_url = link["href"]

        joined = " ".join(block_text)
        deadline_match = re.search(r"Deadline\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", joined)
        deadline_iso = _parse_us_date(deadline_match.group(1)) if deadline_match else None

        settlement_match = re.search(r"Settlement\s+(.+?)(?:Deadline|$)", joined)
        payout_description = settlement_match.group(1).strip() if settlement_match else None

        candidates.append({
            "case_name": title,
            "defendant": None,
            "case_number": None,
            "administrator": None,
            "official_claim_url": claim_url,
            "claim_deadline": deadline_iso,
            "class_period_start": None,
            "class_period_end": None,
            "geographic_scope": None,
            "proof_requirements": payout_description,
            "source_url": TOP_CLASS_ACTIONS_URL,
        })

    return candidates


def scrape_claim_depot():
    """Parse the Claim Depot settlements listing page.

    Each card follows a repeating pattern of:
      <status label: e.g. "Open for Claims" or "Preliminarily Approved">
      <settlement title, often ending in "Settlement">
      <payout amount>
      <deadline date> (only present for "Open for Claims" items)
      <days left>
      <category label>
      <one-sentence eligibility description>
    """
    html = _get(CLAIM_DEPOT_URL)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    for el in soup.find_all(string=re.compile(r"Settlement\s*$")):
        title = el.strip()
        if len(title) < 8 or ("class action" not in title.lower() and "settlement" not in title.lower()):
            continue

        card = el.parent
        for _ in range(4):
            if card and card.parent:
                card = card.parent
        card_text = card.get_text(" ", strip=True) if card else ""

        deadline_match = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December) "
            r"\d{1,2}, \d{4}", card_text
        )
        deadline_iso = _parse_us_date(deadline_match.group(0)) if deadline_match else None

        category_match = re.search(
            r"\b(Data Breach|Privacy|Labor|ERISA|Securities|Consumer Protection|BIPA|"
            r"False Advertising|Insurance|Housing|Antitrust|Fair Credit Reporting|"
            r"Text Messages|Automotive|Civil rights|Deceptive Pricing)\b", card_text
        )
        category = category_match.group(1) if category_match else None

        candidates.append({
            "case_name": title,
            "defendant": None,
            "case_number": None,
            "administrator": None,
            "official_claim_url": None,
            "claim_deadline": deadline_iso,
            "class_period_start": None,
            "class_period_end": None,
            "geographic_scope": None,
            "proof_requirements": category,
            "source_url": CLAIM_DEPOT_URL,
        })

    return candidates


def verify_with_courtlistener(case_name, case_number=None):
    """Look up a candidate case on CourtListener/RECAP to confirm it is real.

    Requires COURTLISTENER_API_TOKEN. Returns a dict with court, docket
    number, and CourtListener URL if a confident match is found, else None.
    This is a verification aid, not an automatic verifier -- a human still
    reviews and clicks "Mark verified" in the Settlement Inbox page.
    """
    token = os.environ.get("COURTLISTENER_API_TOKEN")
    if not token:
        print("COURTLISTENER_API_TOKEN not set -- skipping court verification.")
        return None

    params = {"q": case_number or case_name, "type": "r", "order_by": "score desc"}
    try:
        resp = requests.get(
            f"{COURTLISTENER_BASE}/search/",
            params=params,
            headers={"Authorization": f"Token {token}", "User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except requests.RequestException as exc:
        print(f"WARNING: CourtListener lookup failed: {exc}")
        return None

    if not results:
        return None

    top = results[0]
    return {
        "court": top.get("court"),
        "docket_number": top.get("docketNumber"),
        "case_name_found": top.get("caseName"),
        "courtlistener_url": f"https://www.courtlistener.com{top.get('absolute_url', '')}",
    }


def looks_official(url):
    url = (url or "").lower()
    return any(hint in url for hint in OFFICIAL_DOMAIN_HINTS)


def upsert_settlement(client, candidate):
    existing = client.table("settlements").select("id").eq(
        "case_name", candidate["case_name"]
    ).execute().data

    is_official = looks_official(candidate.get("official_claim_url") or "") and bool(
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


def discover_candidate_settlements():
    candidates = []
    candidates.extend(scrape_top_class_actions())
    candidates.extend(scrape_claim_depot())
    return candidates


def main():
    client = get_service_client()
    candidates = discover_candidate_settlements()
    processed = 0
    for candidate in candidates:
        if not candidate.get("case_name"):
            continue
        upsert_settlement(client, candidate)
        processed += 1
    print(f"Processed {processed} candidate settlement(s) from "
          f"{len(candidates)} scraped record(s).")


if __name__ == "__main__":
    main()
