import streamlit as st
from components.auth import require_login
from components.database import get_user_client, log_audit_event
from components.redaction import safe_audit_metadata

st.set_page_config(page_title="Settlement Inbox", layout="wide")
user = require_login()
client = get_user_client()

st.title("Settlement Inbox")
st.caption("Review discovered settlements. Only mark 'Verified' when you can see a "
           "court name/case number, a named administrator, and an official claim URL.")

with st.expander("Add a settlement manually"):
    with st.form("add_settlement"):
        case_name = st.text_input("Case name *")
        defendant = st.text_input("Defendant / company")
        court = st.text_input("Court")
        case_number = st.text_input("Case number")
        administrator = st.text_input("Claims administrator")
        official_claim_url = st.text_input("Official claim URL")
        official_notice_url = st.text_input("Official notice URL")
        claim_deadline = st.date_input("Claim deadline", value=None)
        class_period_start = st.date_input("Class period start", value=None)
        class_period_end = st.date_input("Class period end", value=None)
        geographic_scope = st.text_input("Geographic scope (e.g. Nationwide, Florida)")
        proof_requirements = st.text_area("Proof requirements")
        source_url = st.text_input("Source URL you found this from *")
        is_official_source = st.checkbox("This source is the official administrator/court page")
        submitted = st.form_submit_button("Add settlement")

    if submitted:
        if not case_name or not source_url:
            st.error("Case name and source URL are required.")
        else:
            status = "needs_verification"
            if is_official_source and case_number and administrator and official_claim_url:
                status = "verified"
            row = {
                "case_name": case_name,
                "defendant": defendant or None,
                "court": court or None,
                "case_number": case_number or None,
                "administrator": administrator or None,
                "official_claim_url": official_claim_url or None,
                "official_notice_url": official_notice_url or None,
                "claim_deadline": str(claim_deadline) if claim_deadline else None,
                "class_period_start": str(class_period_start) if class_period_start else None,
                "class_period_end": str(class_period_end) if class_period_end else None,
                "geographic_scope": geographic_scope or None,
                "proof_requirements": proof_requirements or None,
                "status": status,
            }
            result = client.table("settlements").insert(row).execute()
            settlement_id = result.data[0]["id"] if result.data else None
            if settlement_id:
                client.table("settlement_sources").insert({
                    "settlement_id": settlement_id,
                    "source_type": "official_administrator" if is_official_source else "discovery",
                    "source_url": source_url,
                    "is_official": is_official_source,
                }).execute()
                log_audit_event(client, user.get("sub"), "settlement_added", "settlement",
                                 settlement_id, safe_audit_metadata(status=status))
            st.success(f"Added settlement with status: {status}")
            st.rerun()

st.subheader("Discovered / unverified settlements")
rows = client.table("settlements").select("*").in_(
    "status", ["discovered", "needs_verification"]
).execute().data or []

for row in rows:
    with st.container(border=True):
        st.markdown(f"**{row['case_name']}**  \n"
                     f"Defendant: {row.get('defendant') or 'unknown'} | "
                     f"Status: `{row['status']}`")
        sources = client.table("settlement_sources").select("*").eq(
            "settlement_id", row["id"]
        ).execute().data or []
        for s in sources:
            st.write(f"- [{s['source_type']}] {s['source_url']} "
                     f"({'official' if s['is_official'] else 'discovery only'})")
        c1, c2 = st.columns(2)
        if c1.button("Mark verified", key=f"verify_{row['id']}"):
            if row.get("case_number") and row.get("administrator") and row.get("official_claim_url"):
                client.table("settlements").update({"status": "verified"}).eq("id", row["id"]).execute()
                log_audit_event(client, user.get("sub"), "settlement_verified", "settlement", row["id"])
                st.rerun()
            else:
                st.error("Missing case number, administrator, or official claim URL -- cannot verify yet.")
        if c2.button("Archive", key=f"archive_{row['id']}"):
            client.table("settlements").update({"status": "archived"}).eq("id", row["id"]).execute()
            st.rerun()

if not rows:
    st.write("No unverified settlements in the queue.")
