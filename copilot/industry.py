from enum import StrEnum

from copilot.models import ClassificationResult, MappingStatus


class Industry(StrEnum):
    GENERIC = "generic"
    BANK = "bank"
    UNKNOWN = "unknown"


def industry_for_ts_code(ts_code: str, company_industries: dict[str, str]) -> Industry:
    raw = company_industries.get(ts_code)
    if raw == Industry.BANK.value:
        return Industry.BANK
    if raw == Industry.GENERIC.value:
        return Industry.GENERIC
    return Industry.UNKNOWN


def resolve_classification(
    provider_industry: str | None,
    industry_profiles: dict[str, str],
) -> ClassificationResult:
    if provider_industry is None:
        return ClassificationResult(
            provider="tushare.stock_basic",
            mapping_status=MappingStatus.UNAVAILABLE,
            rule_profile_id="generic",
            industry_field="industry",
        )
    profile = industry_profiles.get(provider_industry)
    return ClassificationResult(
        provider="tushare.stock_basic",
        provider_industry=provider_industry,
        mapping_status=MappingStatus.MAPPED if profile else MappingStatus.UNMAPPED,
        rule_profile_id=profile or "generic",
        industry_field="industry",
        source_value=provider_industry,
    )
