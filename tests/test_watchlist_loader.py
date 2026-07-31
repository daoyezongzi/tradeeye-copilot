from copilot.watchlist import load_watchlist_yaml


def test_load_watchlist_yaml_reads_codes_names_and_industries(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        """
coverage_pool:
  - 000001.SZ
  - 603026.SH
company_names:
  000001.SZ: 平安银行
  603026.SH: 石大胜华
company_industries:
  000001.SZ: bank
  603026.SH: generic
""".strip(),
        encoding="utf-8",
    )

    watchlist = load_watchlist_yaml(path)

    assert watchlist.coverage_pool == ["000001.SZ", "603026.SH"]
    assert watchlist.company_names == {"000001.SZ": "平安银行", "603026.SH": "石大胜华"}
    assert watchlist.company_industries == {"000001.SZ": "bank", "603026.SH": "generic"}


def test_load_watchlist_yaml_requires_every_code_to_have_name_and_industry(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        """
coverage_pool:
  - 000001.SZ
company_names: {}
company_industries: {}
""".strip(),
        encoding="utf-8",
    )

    try:
        load_watchlist_yaml(path)
    except ValueError as exc:
        assert "000001.SZ" in str(exc)
    else:
        raise AssertionError("expected ValueError")
