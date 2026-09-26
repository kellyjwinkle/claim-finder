import pandas as pd
import streamlit as st
from components.auth import require_login
from components.database import get_user_client

st.set_page_config(page_title="Audit & Reports", layout="wide")
user = require_login()
client = get_user_client()

st.title("Audit & Reports")

st.subheader("Submitted claims")
submissions = client.table("claim_submissions").select(
    "*, eligibility_matches(settlements(case_name), household_members(display_name))"
).order("submitted_at", desc=True).execute().data or []

if submissions:
    rows = []
    for s in submissions:
        match = s.get("eligibility_matches") or {}
        settlement = (match.get("settlements") or {})
        member = (match.get("household_members") or {})
        rows.append({
            "Case": settlement.get("case_name"),
            "Household member": member.get("display_name"),
            "Submitted at": s.get("submitted_at"),
            "Confirmation #": s.get("confirmation_number"),
            "Outcome": s.get("outcome"),
            "Payment amount": s.get("payment_amount"),
            "Payment date": s.get("payment_date"),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.download_button("Export as CSV", df.to_csv(index=False), file_name="claim_submissions.csv")
else:
    st.write("No claims submitted yet.")

st.subheader("Recent activity")
events = client.table("audit_events").select("*").eq(
    "actor_user_id", user.get("sub")
).order("created_at", desc=True).limit(50).execute().data or []

for e in events:
    st.write(f"- `{e['created_at']}` **{e['event_type']}** on {e['entity_type']} {e.get('entity_id') or ''} "
              f"{e.get('metadata') or ''}")
