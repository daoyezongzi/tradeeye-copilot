from enum import StrEnum


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
