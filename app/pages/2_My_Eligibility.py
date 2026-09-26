import streamlit as st
from components.auth import require_login
from components.database import get_user_client
from components.redaction import mask_account_reference

st.set_page_config(page_title="My Eligibility", layout="wide")
user = require_login()
client = get_user_client()

st.title("My Eligibility Profile")
st.caption("Add household members and the accounts, subscriptions, purchases, or "
           "residency periods that could make you eligible for a settlement. "
           "Account numbers are masked before storage.")

st.subheader("Household members")
members = client.table("household_members").select("*").eq(
    "user_id", user.get("sub")
).execute().data or []

with st.form("add_member"):
    display_name = st.text_input("Name")
    relationship = st.selectbox("Relationship", ["self", "spouse", "child", "other"])
    email = st.text_input("Email (optional)")
    submitted = st.form_submit_button("Add household member")
    if submitted and display_name:
        client.table("household_members").insert({
            "user_id": user.get("sub"),
            "display_name": display_name,
            "relationship": relationship,
            "email": email or None,
        }).execute()
        st.rerun()

for m in members:
    st.write(f"- **{m['display_name']}** ({m.get('relationship', 'n/a')})")

st.divider()
st.subheader("Accounts, subscriptions, and purchase history")

if not members:
    st.info("Add a household member first.")
else:
    member_lookup = {m["display_name"]: m["id"] for m in members}
    with st.form("add_profile_record"):
        member_name = st.selectbox("Household member", list(member_lookup.keys()))
        category = st.selectbox("Category", [
            "subscription_service", "retail_purchase", "telecom", "banking_fees",
            "employment", "product_defect", "data_breach", "residency", "other"
        ])
        entity_name = st.text_input("Company / service name")
        account_reference = st.text_input("Account/order reference (will be masked)")
        start_date = st.date_input("Start date", value=None)
        end_date = st.date_input("End date (leave blank if ongoing)", value=None)
        state_or_region = st.text_input("State/region", value="Florida")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Add record")
        if submitted and entity_name:
            client.table("eligibility_profiles").insert({
                "household_member_id": member_lookup[member_name],
                "category": category,
                "entity_name": entity_name,
                "account_reference_masked": mask_account_reference(account_reference) if account_reference else None,
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
                "state_or_region": state_or_region or None,
                "notes": notes or None,
            }).execute()
            st.rerun()

    st.subheader("Current records")
    for m in members:
        recs = client.table("eligibility_profiles").select("*").eq(
            "household_member_id", m["id"]
        ).eq("active", True).execute().data or []
        if recs:
            st.markdown(f"**{m['display_name']}**")
            for r in recs:
                st.write(f"- {r['category']}: {r['entity_name']} "
                         f"({r.get('start_date','?')} to {r.get('end_date','ongoing')}) "
                         f"[{r.get('state_or_region','')}] {r.get('account_reference_masked') or ''}")
