"""Supabase client wrapper for Claim Finder.

Two clients are exposed:
- get_user_client(): uses the anon key + the logged-in user's session (RLS applies).
- get_service_client(): uses the service role key. Only for scheduled jobs run
  server-side (GitHub Actions). Never import this into browser-facing Streamlit code.
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
def get_user_client() -> Client:
    url = _get("SUPABASE_URL")
    key = _get("SUPABASE_ANON_KEY")
    return create_client(url, key)


@lru_cache(maxsize=1)
def get_service_client() -> Client:
    url = _get("SUPABASE_URL")
    key = _get("SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


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
