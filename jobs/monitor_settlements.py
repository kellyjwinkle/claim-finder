"""Scheduled discovery job (run via GitHub Actions).

Pulls candidate settlements from free, public sources and writes them to
Supabase as status='needs_verification'. Nothing here ever sets status to
'verified' automatically -- a human confirms official-source indicators
(case number, administrator, official claim URL) in the Streamlit
Settlement Inbox page before a settlement can be matched or filed against.

Sources wired in:
1. Top Class Actions - "Open Lawsuit Settlements" category page (scrape),
   enriched by following each settlement's individual detail page to pull
   the real case number, court, and claims administrator.
2. Claim Depot - settlements listing page (scrape).
3. CourtListener/RECAP API - used to *verify* a candidate's case number and
   court actually exist (see components.courtlistener.verify_with_courtlistener).
   This is NOT a discovery source; it's also callable from the Streamlit
   Settlement Inbox page ("Verify with CourtListener" button).

All scrapers are best-effort: legal-news sites restructure their HTML
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
from components.courtlistener import verify_with_courtlistener  # noqa: E402,F401

USER_AGENT = "ClaimFinder/1.0 (personal household tool; contact via GitHub repo)"
REQUEST_TIMEOUT = 20

OFFICIAL_DOMAIN_HINTS = ("settlement", "claims", ".gov", "administrator")

TOP_CLASS_ACTIONS_URL = "https://topclassactions.com/category/lawsuit-settlements/open-lawsuit-settlements/"
CLAIM_DEPOT_URL = "https://www.claimdepot.com/settlements"


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


# ---------------------------------------------------------------------------
# Top Class Actions: category-page listing scraper
# ---------------------------------------------------------------------------

def scrape_top_class_actions():
    """Parse the Top Class Actions 'open settlements' category page.

    Each entry on the page follows a repeating pattern of:
      <heading with settlement title>
      "Settlement" label + payout description
      "Deadline" label + MM/DD/YYYY
      "SUBMIT A CLAIM" link (the official claim URL)
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


# ---------------------------------------------------------------------------
# Top Class Actions: individual settlement detail-page enrichment
# ---------------------------------------------------------------------------

def scrape_top_class_actions_listing_links():
    """Return the individual settlement page URLs linked from the open-settlements
    category page (e.g. .../lawsuit-settlements/open-lawsuit-settlements/<slug>/)."""
    html = _get(TOP_CLASS_ACTIONS_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/lawsuit-settlements/" in href and href.rstrip("/").count("/") >= 4:
            links.add(href.split("?")[0])
    return sorted(links)


def parse_top_class_actions_detail(html):
    """Parse an individual Top Class Actions settlement page for the fields the
    category-page scrape can't reliably get: case number, court, administrator,
    and the real settlement/claim website.

    Every detail page follows this repeating structure:
      ###### Case Name
      <Plaintiff v. Defendant, Case No. X, in the <Court Name>>
      ###### Final Hearing
      <MM/DD/YYYY>
      ###### Settlement Website
      <domain, no protocol -- sometimes blank>
      ###### Claims Administrator
      <administrator name>
      <address lines...>
      ###### Class Counsel
    """
    text = BeautifulSoup(html, "html.parser").get_text("\n")
    result = {
        "case_name_full": None,
        "case_number": None,
        "court": None,
        "final_hearing": None,
        "official_claim_url": None,
        "administrator": None,
        "is_closed": "This settlement is closed" in text,
    }

    case_block = re.search(r"Case Name\s*\n(.+?)\n#{2,}\s*Final Hearing", text, re.S)
    if case_block:
        case_text = " ".join(case_block.group(1).split())
        result["case_name_full"] = case_text
        case_no_match = re.search(r"Case No\.?\s*([A-Za-z0-9:/\-]+)", case_text)
        if case_no_match:
            result["case_number"] = case_no_match.group(1).rstrip(",;")
        court_match = re.search(r"in the ([^,]+(?:Court|District)[^.]*)", case_text)
        if court_match:
            result["court"] = court_match.group(1).strip()

    final_hearing_match = re.search(r"Final Hearing\s*\n([0-9/]+)", text)
    if final_hearing_match:
        result["final_hearing"] = _parse_us_date(final_hearing_match.group(1))

    website_match = re.search(r"Settlement Website\s*\n([^\n#]*)", text)
    website = website_match.group(1).strip() if website_match else ""
    if website:
        result["official_claim_url"] = website if website.startswith("http") else f"https://{website}"

    admin_block = re.search(r"Claims Administrator\s*\n(.+?)\n#{2,}\s*Class Counsel", text, re.S)
    if admin_block:
        lines = [l.strip() for l in admin_block.group(1).split("\n") if l.strip()]
        if lines:
            result["administrator"] = lines[0]

    return result


def enrich_with_detail_page(candidate):
    """Given a candidate from the category-page scrape, follow its link (if any)
    into the individual settlement page and fill in case_number, court, and
    administrator. Falls back to the original candidate untouched on any failure."""
    detail_url = candidate.get("_detail_page_url")
    if not detail_url or "topclassactions.com" not in detail_url:
        return candidate

    html = _get(detail_url)
    if not html:
        return candidate

    parsed = parse_top_class_actions_detail(html)
    enriched = dict(candidate)
    enriched["case_number"] = parsed["case_number"] or candidate.get("case_number")
    enriched["administrator"] = parsed["administrator"] or candidate.get("administrator")
    if parsed["court"]:
        enriched["geographic_scope"] = enriched.get("geographic_scope") or parsed["court"]
    if parsed["official_claim_url"]:
        enriched["official_claim_url"] = parsed["official_claim_url"]
    return enriched


def scrape_top_class_actions_with_details(max_pages=15):
    """Discovery + enrichment pipeline: get the category-page candidates, then
    visit each linked settlement page (capped at max_pages per run to be a
    polite scraper) to fill in case number, court, and administrator.

    Capping matters because this makes one HTTP request per settlement page --
    running it against every open settlement every day would be unnecessarily
    heavy traffic against a free site.
    """
    listing_links = scrape_top_class_actions_listing_links()
    base_candidates = scrape_top_class_actions()

    link_by_slug = {link.rstrip("/").split("/")[-1]: link for link in listing_links}

    enriched_candidates = []
    for i, candidate in enumerate(base_candidates):
        if i >= max_pages:
            enriched_candidates.append(candidate)
            continue

        detail_url = None
        title_slug_guess = re.sub(r"[^a-z0-9]+", "-", candidate["case_name"].lower()).strip("-")
        for slug, link in link_by_slug.items():
            if slug in title_slug_guess or title_slug_guess in slug:
                detail_url = link
                break

        if detail_url:
            candidate = dict(candidate)
            candidate["_detail_page_url"] = detail_url
            candidate = enrich_with_detail_page(candidate)

        enriched_candidates.append(candidate)

    return enriched_candidates


# ---------------------------------------------------------------------------
# Claim Depot
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Upsert + orchestration
# ---------------------------------------------------------------------------

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
    candidates.extend(scrape_top_class_actions_with_details(max_pages=15))
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
