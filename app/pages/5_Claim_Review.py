from datetime import datetime
import streamlit as st
from components.auth import require_login
from components.database import get_user_client, log_audit_event
from components.redaction import safe_audit_metadata

st.set_page_config(page_title="Claim Review", layout="wide")
user = require_login()
client = get_user_client()

st.title("Claim Review")
st.caption("Prepare a claim packet here. Nothing is submitted for you -- you review "
           "the checklist, open the official claim link yourself, submit it, and then "
           "log the confirmation below.")

reviewable = client.table("eligibility_matches").select(
    "*, settlements(case_name, defendant, official_claim_url, claim_deadline, "
    "proof_requirements), household_members(display_name)"
).in_("status", ["ready_for_review", "evidence_needed"]).execute().data or []

for m in reviewable:
    settlement = m.get("settlements") or {}
    member = m.get("household_members") or {}
    with st.container(border=True):
        st.markdown(f"### {settlement.get('case_name','(unknown)')} -- {member.get('display_name','')}")
        st.write(f"Confidence score: **{m['confidence_score']}**")
        st.write(m["match_explanation"])
        if m.get("missing_information"):
            st.warning(f"Before filing, resolve: {m['missing_information']}")
        st.write(f"Proof requirements: {settlement.get('proof_requirements') or 'Not recorded'}")
        st.write(f"Deadline: {settlement.get('claim_deadline') or 'Not recorded'}")

        draft = client.table("claim_drafts").select("*").eq("match_id", m["id"]).execute().data
        draft = draft[0] if draft else None

        checklist_text = st.text_area(
            "Checklist / notes to prepare before filing",
            value=(draft.get("checklist") if draft else "") or "",
            key=f"checklist_{m['id']}"
        )
        reviewed = st.checkbox(
            "I have personally reviewed this match, confirm the facts are accurate, "
            "and I am ready to submit the claim myself on the official site.",
            key=f"reviewed_{m['id']}",
            value=bool(draft and draft.get("ready_for_manual_submission")),
        )

        if st.button("Save claim draft", key=f"save_{m['id']}"):
            payload = {
                "match_id": m["id"],
                "official_claim_url": settlement.get("official_claim_url") or "",
                "checklist": checklist_text,
                "ready_for_manual_submission": reviewed,
                "user_reviewed_at": datetime.utcnow().isoformat() if reviewed else None,
            }
            if draft:
                client.table("claim_drafts").update(payload).eq("id", draft["id"]).execute()
            else:
                client.table("claim_drafts").insert(payload).execute()
            if reviewed:
                client.table("eligibility_matches").update(
                    {"status": "ready_for_review"}
                ).eq("id", m["id"]).execute()
                log_audit_event(client, user.get("sub"), "claim_draft_reviewed",
                                 "eligibility_matches", m["id"], safe_audit_metadata(status="ready_for_review"))
            st.success("Saved.")
            st.rerun()

        if settlement.get("official_claim_url"):
            st.link_button("Open official claim site", settlement["official_claim_url"])

        with st.expander("Log that you submitted this claim"):
            with st.form(f"submit_form_{m['id']}"):
                confirmation_number = st.text_input("Confirmation number")
                confirmation_drive_file_id = st.text_input("Drive file ID of confirmation screenshot/email")
                submission_notes = st.text_area("Notes")
                submit_click = st.form_submit_button("I submitted this claim myself")
                if submit_click:
                    members_row = client.table("household_members").select("id").eq(
                        "user_id", user.get("sub")
                    ).limit(1).execute().data
                    submitted_by = members_row[0]["id"] if members_row else None
                    client.table("claim_submissions").insert({
                        "match_id": m["id"],
                        "submitted_by_member_id": submitted_by,
                        "submitted_at": datetime.utcnow().isoformat(),
                        "confirmation_number": confirmation_number or None,
                        "confirmation_drive_file_id": confirmation_drive_file_id or None,
                        "submission_notes": submission_notes or None,
                        "outcome": "submitted",
                    }).execute()
                    client.table("eligibility_matches").update(
                        {"status": "submitted"}
                    ).eq("id", m["id"]).execute()
                    log_audit_event(client, user.get("sub"), "claim_submitted_by_user",
                                     "eligibility_matches", m["id"])
                    st.success("Logged. Tracked on the Audit & Reports page.")
                    st.rerun()

if not reviewable:
    st.write("Nothing ready for review yet. Check the Matches page.")
