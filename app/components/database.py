"""Supabase client wrapper for Claim Finder.

With shared-password authentication (see components.auth), there is no
per-person Supabase Auth session driving Row Level Security anymore. The
Streamlit app therefore uses the same service_role client as the scheduled
GitHub Actions job. Access control for this app is enforced by the password
gate in components.auth, not by Supabase RLS -- treat the deployed app and
its secrets with the same care you'd give any single-shared-login household
tool (private repo, private hosting, don't share the app URL/password
publicly).
"""
import os
from functools import lru_cache
from supabase import create_client, Client

try:
    import streamlit as st
    _SECRETS = st.secrets
except Exception:
    _SECRETS = {}


def _get(name: str) -> str:
    if name in os.environ:
        return os.environ[name]
    if name in _SECRETS:
        return _SECRETS[name]
    raise RuntimeError(f"Missing required config value: {name}")


@lru_cache(maxsize=1)
def get_service_client() -> Client:
    url = _get("SUPABASE_URL")
    key = _get("SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def get_user_client() -> Client:
    """Kept for compatibility with existing page code. Now returns the same
    service_role client as get_service_client(), since there is no separate
    per-user Supabase session under shared-password auth."""
    return get_service_client()


def log_audit_event(client: Client, actor_user_id: str, event_type: str,
                     entity_type: str, entity_id: str = None,
                     metadata: dict = None) -> None:
    """Insert an audit event. Never pass raw PII, tokens, or document contents
    in `metadata` -- only IDs, statuses, and non-sensitive labels."""
    client.table("audit_events").insert({
        "actor_user_id": actor_user_id,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metadata": metadata or {},
    }).execute()
