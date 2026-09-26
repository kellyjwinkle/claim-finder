import streamlit as st
from components.auth import require_login
from components.database import get_user_client
from components.evidence import build_evidence_record

st.set_page_config(page_title="Evidence Vault", layout="wide")
user = require_login()
client = get_user_client()

st.title("Evidence Vault")
st.caption("Reference documents stored in your private Google Drive evidence folder. "
           "This app stores only the Drive file ID/link and non-sensitive metadata -- "
           "never the document contents.")

members = client.table("household_members").select("*").eq(
    "user_id", user.get("sub")
).execute().data or []

if not members:
    st.info("Add a household member on the 'My Eligibility' page first.")
else:
    member_lookup = {m["display_name"]: m["id"] for m in members}
    with st.form("add_evidence"):
        member_name = st.selectbox("Household member", list(member_lookup.keys()))
        evidence_type = st.selectbox("Document type", [
            "receipt", "invoice", "order_confirmation", "account_statement",
            "claim_notice", "email", "screenshot", "submission_confirmation", "other"
        ])
        title = st.text_input("Short title (e.g. 'Amazon order Mar 2023')")
        merchant_or_service = st.text_input("Merchant / service name")
        document_date = st.date_input("Document date", value=None)
        period_start = st.date_input("Coverage period start", value=None)
        period_end = st.date_input("Coverage period end", value=None)
        drive_file_id = st.text_input("Google Drive file ID *")
        drive_web_url = st.text_input("Google Drive link (optional, for your reference)")
        contains_sensitive_data = st.checkbox("Contains account numbers, SSNs, or payment info")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Add evidence reference")

        if submitted:
            if not drive_file_id or not title:
                st.error("Title and Drive file ID are required.")
            else:
                record = build_evidence_record(
                    household_member_id=member_lookup[member_name],
                    evidence_type=evidence_type,
                    title=title,
                    drive_file_id=drive_file_id,
                    drive_web_url=drive_web_url or None,
                    merchant_or_service=merchant_or_service or None,
                    document_date=document_date,
                    period_start=period_start,
                    period_end=period_end,
                    contains_sensitive_data=contains_sensitive_data,
                    notes=notes or None,
                )
                client.table("evidence").insert(record).execute()
                st.success("Evidence reference added.")
                st.rerun()

    st.subheader("Catalog")
    for m in members:
        rows = client.table("evidence").select("*").eq(
            "household_member_id", m["id"]
        ).execute().data or []
        if rows:
            st.markdown(f"**{m['display_name']}**")
            for r in rows:
                sensitive_tag = " \U0001F512 sensitive" if r.get("contains_sensitive_data") else ""
                link = f" [open]({r['drive_web_url']})" if r.get("drive_web_url") else ""
                st.write(f"- [{r['evidence_type']}] {r['title']} -- "
                         f"{r.get('merchant_or_service','')} "
                         f"({r.get('period_start','?')} to {r.get('period_end','?')}){sensitive_tag}{link}")
