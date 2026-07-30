from copilot.config import load_settings
from copilot.industry import Industry, industry_for_ts_code


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


def test_industry_for_ts_code_defaults_to_unknown():
    assert industry_for_ts_code("000001.SZ", {"000001.SZ": "bank"}) == Industry.BANK
    assert industry_for_ts_code("920056.BJ", {"920056.BJ": "generic"}) == Industry.GENERIC
    assert industry_for_ts_code("300750.SZ", {}) == Industry.UNKNOWN
