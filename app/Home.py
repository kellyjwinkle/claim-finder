import streamlit as st
from datetime import date
from components.auth import require_login
from components.database import get_user_client

st.set_page_config(page_title="Claim Finder", page_icon="\U0001F4CB", layout="wide")

user = require_login()
client = get_user_client()

st.title("Claim Finder Dashboard")
st.caption("Discover, verify, and track class-action settlement claims. "
           "Nothing is submitted automatically -- you review and submit every claim yourself.")

col1, col2, col3, col4 = st.columns(4)

try:
    settlements = client.table("settlements").select("id,status,claim_deadline").execute().data or []
    matches = client.table("eligibility_matches").select("id,status,confidence_score").execute().data or []
except Exception as e:
    settlements, matches = [], []
    st.warning(f"Could not load data yet -- confirm Supabase schema and RLS are set up. ({e})")

verified = [s for s in settlements if s["status"] == "verified"]
needs_verification = [s for s in settlements if s["status"] == "needs_verification"]
ready_for_review = [m for m in matches if m["status"] == "ready_for_review"]
evidence_needed = [m for m in matches if m["status"] == "evidence_needed"]

col1.metric("Verified settlements", len(verified))
col2.metric("Needs verification", len(needs_verification))
col3.metric("Ready for your review", len(ready_for_review))
col4.metric("Need more evidence", len(evidence_needed))

st.subheader("Upcoming deadlines")
today = date.today()
upcoming = sorted(
    [s for s in settlements if s.get("claim_deadline")],
    key=lambda s: s["claim_deadline"]
)[:10]
if upcoming:
    for s in upcoming:
        st.write(f"- **{s.get('claim_deadline')}** -- settlement id `{s['id']}` (status: {s['status']})")
else:
    st.write("No deadlines on file yet. Add settlements from the Settlement Inbox page.")

st.info("Use the sidebar pages: Settlement Inbox -> My Eligibility -> Evidence Vault -> "
        "Matches -> Claim Review -> Audit & Reports.")
