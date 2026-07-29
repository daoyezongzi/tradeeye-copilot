from pathlib import Path

from copilot.config import load_settings


def test_load_settings_reads_yaml_and_environment(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
tushare:
  timeout_seconds: 12
  max_retries: 2
rules:
  thresholds:
    receivable_revenue_gap_pct: 25.0
    inventory_revenue_gap_pct: 26.0
    ocf_to_net_profit_pct: 55.0
    gross_margin_change_pct: 4.5
    non_recurring_profit_share_pct: 20.0
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TUSHARE_TOKEN", "token-for-test")

    settings = load_settings(config_path)

    assert settings.database.path == Path("tmp/app.sqlite")
    assert settings.tushare.token == "token-for-test"
    assert settings.tushare.timeout_seconds == 12
    assert settings.tushare.max_retries == 2
    assert settings.rules.thresholds.receivable_revenue_gap_pct == 25.0
    assert settings.rules.thresholds.non_recurring_profit_share_pct == 20.0


def test_load_settings_keeps_secret_optional_for_tests(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
tushare:
  timeout_seconds: 12
  max_retries: 2
rules:
  thresholds:
    receivable_revenue_gap_pct: 25.0
    inventory_revenue_gap_pct: 26.0
    ocf_to_net_profit_pct: 55.0
    gross_margin_change_pct: 4.5
    non_recurring_profit_share_pct: 20.0
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)

    settings = load_settings(config_path)

    assert settings.tushare.token is None


def test_load_settings_reads_llm_and_narrative_sections(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
tushare:
  timeout_seconds: 12
  max_retries: 2
llm:
  base_url: https://maas.example.com/v1
  model: ascend-test-model
  timeout_seconds: 45
narrative:
  pdf_cache_dir: data/pdf_cache
  max_section_chars: 12000
rules:
  thresholds:
    receivable_revenue_gap_pct: 25.0
    inventory_revenue_gap_pct: 26.0
    ocf_to_net_profit_pct: 55.0
    gross_margin_change_pct: 4.5
    non_recurring_profit_share_pct: 20.0
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("ASCEND_API_KEY", "ascend-key-for-test")

    settings = load_settings(config_path)

    assert settings.llm.base_url == "https://maas.example.com/v1"
    assert settings.llm.model == "ascend-test-model"
    assert settings.llm.api_key == "ascend-key-for-test"
    assert settings.llm.timeout_seconds == 45
    assert settings.narrative.pdf_cache_dir == Path("data/pdf_cache")
    assert settings.narrative.max_section_chars == 12000


def test_load_settings_reads_eval_and_feishu_sections(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
tushare:
  timeout_seconds: 12
  max_retries: 2
llm:
  base_url: https://maas.example.com/v1
  model: ascend-test-model
notify:
  feishu_enabled: true
eval:
  coverage_pool:
    - 000001.SZ
    - 600000.SH
  start_date: "20250801"
  end_date: "20250831"
  benchmark_output: artifacts/benchmark.json
rules:
  thresholds:
    receivable_revenue_gap_pct: 25.0
    inventory_revenue_gap_pct: 26.0
    ocf_to_net_profit_pct: 55.0
    gross_margin_change_pct: 4.5
    non_recurring_profit_share_pct: 20.0
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("FEISHU_WEBHOOK", "https://open.feishu.cn/webhook/test")

    settings = load_settings(config_path)

    assert settings.notify.feishu_enabled is True
    assert settings.notify.feishu_webhook == "https://open.feishu.cn/webhook/test"
    assert settings.eval.coverage_pool == ["000001.SZ", "600000.SH"]
    assert settings.eval.start_date == "20250801"
    assert settings.eval.end_date == "20250831"
    assert settings.eval.benchmark_output == Path("artifacts/benchmark.json")
