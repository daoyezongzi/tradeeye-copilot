from copilot.config import load_settings
from copilot.industry import Industry, industry_for_ts_code, resolve_classification
from copilot.models import MappingStatus


def test_load_settings_reads_company_industries(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
eval:
  coverage_pool:
    - 000001.SZ
    - 920056.BJ
  company_industries:
    000001.SZ: bank
    920056.BJ: generic
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, env_path=tmp_path / "missing.env")

    assert settings.eval.company_industries == {"000001.SZ": "bank", "920056.BJ": "generic"}


def test_load_settings_reads_company_names(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
eval:
  coverage_pool:
    - 603026.SH
  company_names:
    603026.SH: 石大胜华
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, env_path=tmp_path / "missing.env")

    assert settings.eval.company_names == {"603026.SH": "石大胜华"}


def test_industry_for_ts_code_defaults_to_unknown():
    assert industry_for_ts_code("000001.SZ", {"000001.SZ": "bank"}) == Industry.BANK
    assert industry_for_ts_code("920056.BJ", {"920056.BJ": "generic"}) == Industry.GENERIC
    assert industry_for_ts_code("300750.SZ", {}) == Industry.UNKNOWN


def test_known_provider_industry_maps_to_special_profile():
    result = resolve_classification(
        provider_industry="银行",
        industry_profiles={"银行": "bank_v1"},
    )

    assert result.mapping_status == MappingStatus.MAPPED
    assert result.rule_profile_id == "bank_v1"
    assert result.provider_industry == "银行"


def test_unknown_provider_industry_uses_generic_without_claiming_generic_industry():
    result = resolve_classification(
        provider_industry="新行业",
        industry_profiles={"银行": "bank_v1"},
    )

    assert result.mapping_status == MappingStatus.UNMAPPED
    assert result.rule_profile_id == "generic"
    assert result.provider_industry == "新行业"


def test_missing_provider_industry_is_unavailable():
    result = resolve_classification(
        provider_industry=None,
        industry_profiles={"银行": "bank_v1"},
    )

    assert result.mapping_status == MappingStatus.UNAVAILABLE
    assert result.rule_profile_id == "generic"
