"""Evidence catalog helpers.

Evidence documents themselves stay in Google Drive. This module only manages
references (drive_file_id, drive_web_url) plus non-sensitive metadata used for
matching (merchant name, date range, document type).
"""
from datetime import date


def build_evidence_record(household_member_id: str, evidence_type: str, title: str,
                           drive_file_id: str, drive_web_url: str = None,
                           merchant_or_service: str = None,
                           document_date: date = None,
                           period_start: date = None,
                           period_end: date = None,
                           contains_sensitive_data: bool = False,
                           notes: str = None) -> dict:
    if not drive_file_id:
        raise ValueError("drive_file_id is required -- do not store raw file contents here.")
    return {
        "household_member_id": household_member_id,
        "evidence_type": evidence_type,
        "title": title,
        "merchant_or_service": merchant_or_service,
        "document_date": document_date.isoformat() if document_date else None,
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": period_end.isoformat() if period_end else None,
        "drive_file_id": drive_file_id,
        "drive_web_url": drive_web_url,
        "contains_sensitive_data": contains_sensitive_data,
        "notes": notes,
    }


def evidence_covers_period(evidence_row: dict, period_start: date, period_end: date) -> bool:
    ev_start = evidence_row.get("period_start")
    ev_end = evidence_row.get("period_end")
    if not ev_start or not period_start:
        return False
    ev_end = ev_end or date.max.isoformat()
    period_end = period_end or date.max
    return str(ev_start) <= str(period_end) and str(period_start) <= str(ev_end)
