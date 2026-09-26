"""CourtListener/RECAP verification helper, shared by the Streamlit Settlement
Inbox page and the scheduled discovery job.

This is a verification aid only -- it never marks a settlement as verified by
itself. A human always reviews the result and clicks "Apply this data" (in the
Streamlit UI) or "Mark verified" before a settlement is treated as real.
"""
import os

import requests

USER_AGENT = "ClaimFinder/1.0 (personal household tool; contact via GitHub repo)"
REQUEST_TIMEOUT = 20
COURTLISTENER_BASE = "https://www.courtlistener.com/api/rest/v4"


def get_courtlistener_token():
    if "COURTLISTENER_API_TOKEN" in os.environ:
        return os.environ["COURTLISTENER_API_TOKEN"]
    try:
        import streamlit as st
        return st.secrets.get("COURTLISTENER_API_TOKEN")
    except Exception:
        return None


def verify_with_courtlistener(case_name, case_number=None):
    """Look up a candidate case on CourtListener/RECAP to confirm it is real.

    Requires COURTLISTENER_API_TOKEN (env var or Streamlit secret). Returns a
    dict with court, docket number, case name, and CourtListener URL if a
    confident match is found, else None. Never raises -- callers should treat
    None as "couldn't verify," not "confirmed not real."
    """
    token = get_courtlistener_token()
    if not token:
        return {"error": "COURTLISTENER_API_TOKEN is not configured."}

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
        return {"error": f"CourtListener lookup failed: {exc}"}

    if not results:
        return {"error": "No matching docket found on CourtListener."}

    top = results[0]
    return {
        "court": top.get("court"),
        "docket_number": top.get("docketNumber"),
        "case_name_found": top.get("caseName"),
        "courtlistener_url": f"https://www.courtlistener.com{top.get('absolute_url', '')}",
    }
