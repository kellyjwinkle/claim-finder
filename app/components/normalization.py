"""Vendor/merchant name normalization for matching evidence against settlements.

Bank and card statements produce messy merchant strings like "AMZN Mktp US*2K3"
or "VZWRLSS*APOCC VISN". This module maps common variants to a canonical name
so the matching engine can compare "Amazon" (from a settlement) against
"AMZN Mktp" (from a receipt) reliably.

The alias list is intentionally small and household-focused (retail, telecom,
credit bureaus, social platforms, insurance, delivery apps) rather than
exhaustive -- extend CANONICAL_MERCHANTS as you add evidence for new vendors.
"""
import difflib
import re

CANONICAL_MERCHANTS = {
    "amazon": ["amazon", "amzn mktp", "amazon.com", "amazon marketplace", "amzn", "prime video", "amazon prime"],
    "walmart": ["walmart", "wal-mart", "wm supercenter", "walmart.com", "wal mart"],
    "target": ["target", "target.com", "target corp"],
    "at&t": ["at&t", "att", "at and t", "at&t mobility", "att*bill"],
    "verizon": ["verizon", "vzwrlss", "verizon wireless"],
    "t-mobile": ["t-mobile", "tmobile", "t mobile"],
    "equifax": ["equifax"],
    "experian": ["experian"],
    "transunion": ["transunion", "trans union"],
    "meta": ["meta", "facebook", "instagram", "fb.com"],
    "google": ["google", "google llc", "google play", "youtube premium"],
    "capital one": ["capital one", "capitalone", "cap one"],
    "wells fargo": ["wells fargo", "wellsfargo"],
    "uber": ["uber", "uber trip", "uber eats"],
    "doordash": ["doordash", "door dash"],
    "ticketmaster": ["ticketmaster", "ticket master", "livenation"],
    "publix": ["publix"],
    "progressive": ["progressive", "progressive insurance"],
    "allstate": ["allstate"],
    "state farm": ["state farm", "statefarm"],
}

ALIAS_TO_CANONICAL = {}
for _canonical, _aliases in CANONICAL_MERCHANTS.items():
    for _alias in _aliases:
        ALIAS_TO_CANONICAL[_alias] = _canonical


def normalize_merchant_name(raw_name, cutoff=0.72):
    """Return a canonical merchant name for a messy raw string, or a cleaned
    version of the input if no canonical match is found. Returns None for
    empty input."""
    if not raw_name:
        return None

    cleaned = re.sub(r"[^a-z0-9&\s]", " ", raw_name.lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return None

    if cleaned in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[cleaned]

    cleaned_nospace = cleaned.replace(" ", "")
    for alias, canonical in ALIAS_TO_CANONICAL.items():
        alias_nospace = alias.replace(" ", "")
        if alias in cleaned or cleaned in alias or alias_nospace in cleaned_nospace:
            return canonical

    matches = difflib.get_close_matches(cleaned, ALIAS_TO_CANONICAL.keys(), n=1, cutoff=cutoff)
    if matches:
        return ALIAS_TO_CANONICAL[matches[0]]

    return cleaned


def find_merchant_mentions(text, limit=5):
    """Scan free text (e.g. OCR output from a receipt) for known canonical
    merchant names. Returns a de-duplicated list of canonical names found,
    in order of first appearance, capped at `limit`."""
    if not text:
        return []
    lowered = text.lower()
    found = []
    for alias, canonical in ALIAS_TO_CANONICAL.items():
        if alias in lowered and canonical not in found:
            found.append(canonical)
        if len(found) >= limit:
            break
    return found
