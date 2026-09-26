"""Deterministic, auditable eligibility matching.

This intentionally avoids letting an LLM decide legal eligibility. Every score
comes from explicit, inspectable rules so you can see exactly why a settlement
was flagged as a possible match.

Phase 2 update: entity matching now uses normalized merchant names (see
components.normalization) instead of raw substring comparison, so "AMZN Mktp"
on a receipt correctly matches an "Amazon" settlement.
"""
from dataclasses import dataclass, field
from datetime import date

from components.normalization import normalize_merchant_name


@dataclass
class ProfileRecord:
    category: str
    entity_name: str
    start_date: date
    end_date: date
    state_or_region: str


@dataclass
class SettlementRecord:
    defendant: str
    class_period_start: date
    class_period_end: date
    geographic_scope: str
    proof_requirements: str


@dataclass
class MatchResult:
    score: int
    label: str
    explanation: list = field(default_factory=list)
    missing_information: list = field(default_factory=list)


def _date_ranges_overlap(a_start, a_end, b_start, b_end) -> bool:
    if not a_start or not b_start:
        return False
    a_end = a_end or date.max
    b_end = b_end or date.max
    return a_start <= b_end and b_start <= a_end


def _name_matches(profile_entity: str, defendant: str) -> bool:
    if not profile_entity or not defendant:
        return False
    profile_canonical = normalize_merchant_name(profile_entity)
    defendant_canonical = normalize_merchant_name(defendant)
    if not profile_canonical or not defendant_canonical:
        return False
    if profile_canonical == defendant_canonical:
        return True
    p = profile_entity.strip().lower()
    d = defendant.strip().lower()
    return p in d or d in p


def score_match(profile: ProfileRecord, settlement: SettlementRecord,
                 has_evidence: bool, has_notice_or_account_match: bool) -> MatchResult:
    score = 0
    explanation = []
    missing = []

    if _name_matches(profile.entity_name, settlement.defendant):
        score += 35
        explanation.append(f"Entity match: '{profile.entity_name}' aligns with defendant "
                            f"'{settlement.defendant}'.")
    else:
        missing.append("No clear entity/defendant name match on file.")

    if _date_ranges_overlap(profile.start_date, profile.end_date,
                             settlement.class_period_start, settlement.class_period_end):
        score += 25
        explanation.append("Your recorded usage period overlaps the settlement class period.")
    else:
        missing.append("No overlapping date range found between your records and the class period.")

    if settlement.geographic_scope and profile.state_or_region:
        scope = settlement.geographic_scope.strip().lower()
        region = profile.state_or_region.strip().lower()
        if scope in ("nationwide", "all states", "united states") or region in scope:
            score += 15
            explanation.append(f"Geographic scope '{settlement.geographic_scope}' includes "
                                f"'{profile.state_or_region}'.")
        else:
            missing.append("Geographic scope does not clearly include your state/region.")
    else:
        missing.append("Geographic scope or your state/region is not on file.")

    if has_evidence:
        score += 15
        explanation.append("Supporting evidence is linked in the evidence vault.")
    else:
        missing.append("No supporting document linked yet.")

    if has_notice_or_account_match:
        score += 10
        explanation.append("A settlement notice ID or account reference matches your records.")
    elif settlement.proof_requirements and "notice" in settlement.proof_requirements.lower():
        missing.append("This settlement appears to require a notice/account ID you have not matched yet.")

    if score >= 80:
        label = "strong_candidate"
    elif score >= 55:
        label = "possible_candidate"
    elif score >= 30:
        label = "weak_lead"
    else:
        label = "no_reliable_match"

    return MatchResult(score=score, label=label, explanation=explanation, missing_information=missing)


LABEL_TO_STATUS = {
    "strong_candidate": "ready_for_review",
    "possible_candidate": "evidence_needed",
    "weak_lead": "possible",
    "no_reliable_match": "not_eligible",
}
