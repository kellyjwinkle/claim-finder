"""Authentication wrapper using Streamlit's built-in OIDC support (st.login).

Configure the [auth] section in .streamlit/secrets.toml (never commit real
values). See Streamlit docs: st.login / st.user / st.logout.
"""
import streamlit as st


def require_login():
    if not getattr(st.user, "is_logged_in", False):
        st.title("Claim Finder")
        st.write("Sign in to view your household's settlement dashboard.")
        st.button("Log in", on_click=st.login)
        st.stop()
    with st.sidebar:
        st.write(f"Signed in as **{st.user.get('name', st.user.get('email', 'user'))}**")
        st.button("Log out", on_click=st.logout)
    return st.user
