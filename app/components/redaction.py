"""Helpers to keep sensitive data out of logs, UI defaults, and audit metadata."""
import re

_ACCOUNT_TAIL = re.compile(r"(\d{4})$")


def mask_account_reference(raw_value: str) -> str:
    """Turn '1234567890123456' into '****3456'. Never store the raw value."""
    if not raw_value:
        return ""
    match = _ACCOUNT_TAIL.search(raw_value.strip())
    tail = match.group(1) if match else raw_value[-4:]
    return f"****{tail}"


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def safe_audit_metadata(**fields) -> dict:
    """Whitelist-only metadata builder for audit_events.metadata.
    Only pass IDs, enums, counts, booleans, and short labels here -- never
    raw documents, account numbers, tokens, or full addresses."""
    allowed_keys = {
        "settlement_id", "match_id", "evidence_id", "status", "score",
        "action", "source_type", "count", "deadline",
    }
    return {k: v for k, v in fields.items() if k in allowed_keys}
