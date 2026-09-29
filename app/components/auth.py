"""Simple shared-password authentication for a single-household deployment.

This replaces Supabase-Auth-backed OIDC login (st.login) with a single shared
password, appropriate for a private tool used by one household rather than
many independent accounts. Access control for this app is therefore enforced
at this password gate plus normal hosting privacy (private repo, private
Streamlit Cloud app, or local-only use) -- NOT by Supabase Row Level Security,
since there is no per-person Supabase Auth session anymore.

Setup: generate a SHA-256 hash of your chosen password and put it in secrets:

    python -c "import hashlib; print(hashlib.sha256(b'your-password').hexdigest())"

Then in .streamlit/secrets.toml (local) or the Streamlit Cloud secrets panel:

    APP_PASSWORD_HASH = "the hex string printed above"
"""
import hashlib

import streamlit as st

# A fixed identity used for household_members.user_id and
# audit_events.actor_user_id now that there's no per-person Supabase Auth
# account. It does not need to be secret -- it's just a consistent ID.
HOUSEHOLD_USER_ID = "00000000-0000-0000-0000-000000000001"


def _get_expected_hash():
    return st.secrets.get("APP_PASSWORD_HASH")


def require_login():
    if st.session_state.get("authenticated"):
        with st.sidebar:
            st.write("Signed in as **Household**")
            if st.button("Log out"):
                st.session_state["authenticated"] = False
                st.rerun()
        return {"sub": HOUSEHOLD_USER_ID, "name": "Household"}

    st.title("Claim Finder")
    st.write("Enter the household password to continue.")

    expected_hash = _get_expected_hash()
    if not expected_hash:
        st.error(
            "APP_PASSWORD_HASH is not configured. Add it to "
            ".streamlit/secrets.toml (local) or your Streamlit Cloud app's "
            "Secrets panel."
        )
        st.stop()

    password = st.text_input("Password", type="password")
    if st.button("Log in"):
        if hashlib.sha256(password.encode()).hexdigest() == expected_hash:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()
