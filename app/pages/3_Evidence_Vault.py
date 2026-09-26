import streamlit as st
from datetime import datetime
from components.auth import require_login
from components.database import get_user_client, log_audit_event
from components.evidence import build_evidence_record
from components.normalization import normalize_merchant_name, find_merchant_mentions
from components.drive_ocr import extract_text_from_drive_file
from components.redaction import safe_audit_metadata

st.set_page_config(page_title="Evidence Vault", layout="wide")
user = require_login()
client = get_user_client()

st.title("Evidence Vault")
st.caption("Reference documents stored in your private Google Drive evidence folder. "
           "This app stores only the Drive file ID/link and non-sensitive metadata -- "
           "never the document contents. Text extraction (OCR) results are stored so "
           "matching can find the merchant name, but the underlying file always stays "
           "in Drive.")

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
                if merchant_or_service:
                    record["normalized_merchant"] = normalize_merchant_name(merchant_or_service)
                client.table("evidence").insert(record).execute()
                st.success("Evidence reference added.")
                st.rerun()

    st.subheader("Catalog")
    for m in members:
        rows = client.table("evidence").select("*").eq(
            "household_member_id", m["id"]
        ).execute().data or []
        if not rows:
            continue

        st.markdown(f"**{m['display_name']}**")
        for r in rows:
            sensitive_tag = " \U0001F512 sensitive" if r.get("contains_sensitive_data") else ""
            link = f" [open]({r['drive_web_url']})" if r.get("drive_web_url") else ""
            merchant_tag = f" -- normalized: `{r['normalized_merchant']}`" if r.get("normalized_merchant") else ""

            with st.container(border=True):
                st.write(f"[{r['evidence_type']}] {r['title']} -- "
                         f"{r.get('merchant_or_service','')} "
                         f"({r.get('period_start','?')} to {r.get('period_end','?')})"
                         f"{sensitive_tag}{link}{merchant_tag}")

                if r.get("extracted_text"):
                    with st.expander("View extracted text"):
                        st.text(r["extracted_text"][:3000])
                    if r.get("ocr_processed_at"):
                        st.caption(f"Text extracted: {r['ocr_processed_at']}")

                if st.button("Extract & analyze from Drive", key=f"ocr_{r['id']}"):
                    with st.spinner("Reading file from Drive and extracting text..."):
                        result = extract_text_from_drive_file(r["drive_file_id"])

                    if result.get("error"):
                        st.error(f"Could not extract text: {result['error']}")
                    else:
                        extracted_text = result.get("text") or ""
                        mentions = find_merchant_mentions(extracted_text)
                        detected_merchant = mentions[0] if mentions else r.get("normalized_merchant")

                        update_payload = {
                            "extracted_text": extracted_text,
                            "ocr_processed_at": datetime.utcnow().isoformat(),
                        }
                        if detected_merchant and not r.get("normalized_merchant"):
                            update_payload["normalized_merchant"] = detected_merchant

                        client.table("evidence").update(update_payload).eq("id", r["id"]).execute()
                        log_audit_event(
                            client, user.get("sub"), "evidence_ocr_processed", "evidence",
                            r["id"], safe_audit_metadata(evidence_id=r["id"])
                        )
                        st.success(
                            f"Extracted {len(extracted_text)} characters. "
                            f"Detected merchants: {', '.join(mentions) if mentions else 'none recognized'}."
                        )
                        st.rerun()
