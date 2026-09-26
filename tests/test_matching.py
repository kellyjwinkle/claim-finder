from datetime import date
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "app"))
from components.matching import ProfileRecord, SettlementRecord, score_match


def test_strong_match():
    profile = ProfileRecord(
        category="subscription_service",
        entity_name="Acme Streaming",
        start_date=date(2022, 1, 1),
        end_date=date(2024, 1, 1),
        state_or_region="Florida",
    )
    settlement = SettlementRecord(
        defendant="Acme Streaming Inc.",
        class_period_start=date(2021, 6, 1),
        class_period_end=date(2023, 6, 1),
        geographic_scope="Nationwide",
        proof_requirements="No proof required",
    )
    result = score_match(profile, settlement, has_evidence=True, has_notice_or_account_match=False)
    assert result.score >= 80
    assert result.label == "strong_candidate"


def test_no_match():
    profile = ProfileRecord(
        category="retail_purchase",
        entity_name="Local Hardware Store",
        start_date=date(2020, 1, 1),
        end_date=date(2020, 6, 1),
        state_or_region="Colorado",
    )
    settlement = SettlementRecord(
        defendant="Big Tech Corp",
        class_period_start=date(2023, 1, 1),
        class_period_end=date(2023, 12, 31),
        geographic_scope="California only",
        proof_requirements="Notice ID required",
    )
    result = score_match(profile, settlement, has_evidence=False, has_notice_or_account_match=False)
    assert result.score < 30
    assert result.label == "no_reliable_match"
