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

    settings = load_settings(config_path, env_path=env_path, secrets_dir=tmp_path / "missing-secrets")

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


def test_load_settings_reads_service_secret_files_before_dotenv(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    secrets_dir = tmp_path / ".secrets"
    secrets_dir.mkdir()
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
    env_path.write_text(
        "TUSHARE_TOKEN=token-from-dotenv\nFEISHU_WEBHOOK=https://open.feishu.cn/dotenv\n",
        encoding="utf-8",
    )
    (secrets_dir / ".tushare").write_text("TUSHARE_TOKEN=token-from-secret-file\n", encoding="utf-8")
    (secrets_dir / ".feishu").write_text("FEISHU_WEBHOOK=https://open.feishu.cn/secret-file\n", encoding="utf-8")
    (secrets_dir / ".deepseek").write_text(
        "LLM_API_KEY=deepseek-key\nLLM_BASE_URL=https://api.deepseek.com/v1\nLLM_MODEL=deepseek-chat\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.delenv("FEISHU_WEBHOOK", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    settings = load_settings(config_path, env_path=env_path, secrets_dir=secrets_dir)

    assert settings.tushare.token == "token-from-secret-file"
    assert settings.notify.feishu_webhook == "https://open.feishu.cn/secret-file"
    assert settings.llm.api_key == "deepseek-key"
    assert settings.llm.base_url == "https://api.deepseek.com/v1"
    assert settings.llm.model == "deepseek-chat"


def test_load_settings_environment_overrides_service_secret_files(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    secrets_dir = tmp_path / ".secrets"
    secrets_dir.mkdir()
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
    (secrets_dir / ".tushare").write_text("TUSHARE_TOKEN=token-from-secret-file\n", encoding="utf-8")
    monkeypatch.setenv("TUSHARE_TOKEN", "token-from-env")

    settings = load_settings(config_path, env_path=tmp_path / "missing.env", secrets_dir=secrets_dir)

    assert settings.tushare.token == "token-from-env"


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
