from datetime import date
import streamlit as st
from components.auth import require_login
from components.database import get_user_client, log_audit_event
from components.matching import ProfileRecord, SettlementRecord, score_match, LABEL_TO_STATUS
from components.evidence import evidence_matches_settlement
from components.redaction import safe_audit_metadata

st.set_page_config(page_title="Matches", layout="wide")
user = require_login()
client = get_user_client()

st.title("Eligibility Matches")
st.caption("Rule-based matching only -- every score is explainable. Review each match "
           "before treating it as eligible.")

members = client.table("household_members").select("*").eq(
    "user_id", user.get("sub")
).execute().data or []
verified_settlements = client.table("settlements").select("*").eq(
    "status", "verified"
).execute().data or []

def _parse_date(value):
    return date.fromisoformat(value) if value else None

if st.button("Run matching now"):
    created = 0
    for member in members:
        profiles = client.table("eligibility_profiles").select("*").eq(
            "household_member_id", member["id"]
        ).eq("active", True).execute().data or []
        evidence_rows = client.table("evidence").select("*").eq(
            "household_member_id", member["id"]
        ).execute().data or []

        for settlement in verified_settlements:
            best = None
            for profile in profiles:
                pr = ProfileRecord(
                    category=profile["category"],
                    entity_name=profile["entity_name"],
                    start_date=_parse_date(profile.get("start_date")),
                    end_date=_parse_date(profile.get("end_date")),
                    state_or_region=profile.get("state_or_region"),
                )
                sr = SettlementRecord(
                    defendant=settlement.get("defendant"),
                    class_period_start=_parse_date(settlement.get("class_period_start")),
                    class_period_end=_parse_date(settlement.get("class_period_end")),
                    geographic_scope=settlement.get("geographic_scope"),
                    proof_requirements=settlement.get("proof_requirements"),
                )
                has_evidence = any(
                    evidence_matches_settlement(
                        ev, sr.defendant, sr.class_period_start, sr.class_period_end
                    )
                    for ev in evidence_rows
                )
                result = score_match(pr, sr, has_evidence, has_notice_or_account_match=False)
                if best is None or result.score > best.score:
                    best = result

            if best and best.score >= 30:
                status = LABEL_TO_STATUS[best.label]
                existing = client.table("eligibility_matches").select("id").eq(
                    "settlement_id", settlement["id"]
                ).eq("household_member_id", member["id"]).execute().data
                payload = {
                    "settlement_id": settlement["id"],
                    "household_member_id": member["id"],
                    "status": status,
                    "confidence_score": best.score,
                    "match_explanation": " ".join(best.explanation),
                    "missing_information": " ".join(best.missing_information),
                }
                if existing:
                    client.table("eligibility_matches").update(payload).eq(
                        "id", existing[0]["id"]
                    ).execute()
                else:
                    client.table("eligibility_matches").insert(payload).execute()
                    created += 1
    log_audit_event(client, user.get("sub"), "matching_run", "eligibility_matches",
                     metadata=safe_audit_metadata(count=created))
    st.success(f"Matching complete. {created} new match(es) created.")
    st.rerun()

st.divider()
st.subheader("Current matches")
matches = client.table("eligibility_matches").select(
    "*, settlements(case_name, defendant, claim_deadline, official_claim_url), "
    "household_members(display_name)"
).order("confidence_score", desc=True).execute().data or []

for m in matches:
    settlement = m.get("settlements") or {}
    member = m.get("household_members") or {}
    with st.container(border=True):
        st.markdown(f"**{settlement.get('case_name','(unknown)')}** -- "
                     f"{member.get('display_name','')} -- score **{m['confidence_score']}** "
                     f"-- status `{m['status']}`")
        st.write(m["match_explanation"] or "No explanation recorded.")
        if m.get("missing_information"):
            st.warning(f"Missing: {m['missing_information']}")
        if settlement.get("claim_deadline"):
            st.write(f"Deadline: {settlement['claim_deadline']}")
        if settlement.get("official_claim_url"):
            st.write(f"Official claim link: {settlement['official_claim_url']}")

if not matches:
    st.write("No matches yet. Add eligibility records and verified settlements, then run matching.")
