from copilot.config import load_settings


def test_load_settings_reads_dotenv_without_printing_values(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
llm:
  base_url: https://maas.example.com/v1
  model: ascend-compatible-model
rss:
  feeds:
    - https://example.com/rss.xml
  max_entries: 25
""".strip(),
        encoding="utf-8",
    )
    env_path.write_text(
        "TUSHARE_TOKEN=token-from-dotenv\nFEISHU_WEBHOOK=https://open.feishu.cn/test\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.delenv("FEISHU_WEBHOOK", raising=False)

    settings = load_settings(config_path, env_path=env_path)

    assert settings.tushare.token == "token-from-dotenv"
    assert settings.notify.feishu_webhook == "https://open.feishu.cn/test"
    assert settings.rss.feeds == ["https://example.com/rss.xml"]
    assert settings.rss.max_entries == 25


def test_load_settings_reads_rss_company_names(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
rss:
  company_names:
    平安银行: 000001.SZ
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, env_path=tmp_path / "missing.env")

    assert settings.rss.company_names == {"平安银行": "000001.SZ"}


def test_load_settings_environment_overrides_dotenv(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
llm:
  base_url: https://maas.example.com/v1
  model: ascend-compatible-model
""".strip(),
        encoding="utf-8",
    )
    env_path.write_text("TUSHARE_TOKEN=token-from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("TUSHARE_TOKEN", "token-from-env")

    settings = load_settings(config_path, env_path=env_path)

    assert settings.tushare.token == "token-from-env"
