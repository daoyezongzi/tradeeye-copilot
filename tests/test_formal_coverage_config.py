from pathlib import Path

from copilot.config import load_settings
from copilot.industry import Industry
from copilot.watchlist import load_watchlist_yaml


def test_config_formal_coverage_pool_is_complete_and_supported():
    settings = load_settings(env_path=Path(".missing-env-for-formal-coverage-test"))
    supported = {Industry.GENERIC.value, Industry.BANK.value}

    assert len(settings.eval.coverage_pool) == 100
    assert len(set(settings.eval.coverage_pool)) == 100
    assert all(code in settings.eval.company_names for code in settings.eval.coverage_pool)
    assert all(code in settings.eval.company_industries for code in settings.eval.coverage_pool)
    assert all(settings.eval.company_industries[code] in supported for code in settings.eval.coverage_pool)


def test_rss_company_names_mirror_formal_coverage_names():
    settings = load_settings(env_path=Path(".missing-env-for-formal-coverage-test"))

    assert settings.rss.company_names == settings.eval.company_names


def test_watchlist_loader_rejects_unknown_industry(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        """
coverage_pool:
  - 000001.SZ
company_names:
  000001.SZ: 平安银行
company_industries:
  000001.SZ: insurance
""".strip(),
        encoding="utf-8",
    )

    try:
        load_watchlist_yaml(path)
    except ValueError as exc:
        assert "unsupported industry" in str(exc)
        assert "000001.SZ" in str(exc)
    else:
        raise AssertionError("expected ValueError")
