from pathlib import Path
import os

from dotenv import load_dotenv
import yaml
from pydantic import BaseModel, Field


SECRET_ENV_FILES = (".tushare", ".feishu", ".deepseek", "tradeeye-copilot.env")
DEFAULT_SECRETS_DIR = Path.home() / "Documents" / ".secrets"


class DatabaseSettings(BaseModel):
    path: Path


class TushareSettings(BaseModel):
    timeout_seconds: int = 30
    max_retries: int = 3
    token: str | None = None


class LLMSettings(BaseModel):
    base_url: str = "https://maas.example.com/v1"
    model: str = "ascend-compatible-model"
    timeout_seconds: int = 60
    api_key: str | None = None


class NarrativeSettings(BaseModel):
    pdf_cache_dir: Path = Path("data/pdf_cache")
    max_section_chars: int = 12000


class NotifySettings(BaseModel):
    feishu_enabled: bool = False
    feishu_webhook: str | None = None
    feishu_verification_token: str | None = None
    public_base_url: str | None = None


class AutomationSettings(BaseModel):
    trigger_token: str | None = None


class EvalSettings(BaseModel):
    coverage_pool: list[str] = Field(default_factory=list)
    company_industries: dict[str, str] = Field(default_factory=dict)
    company_names: dict[str, str] = Field(default_factory=dict)
    industry_profiles: dict[str, str] = Field(default_factory=dict)
    start_date: str = "20250801"
    end_date: str = "20250831"
    benchmark_output: Path = Path("artifacts/benchmark.json")


class RssSettings(BaseModel):
    feeds: list[str] = Field(default_factory=list)
    max_entries: int = 50
    company_names: dict[str, str] = Field(default_factory=dict)


class RuleThresholds(BaseModel):
    receivable_revenue_gap_pct: float = 30.0
    inventory_revenue_gap_pct: float = 30.0
    ocf_to_net_profit_pct: float = 50.0
    gross_margin_change_pct: float = 5.0
    non_recurring_profit_share_pct: float = 30.0


class RuleSettings(BaseModel):
    thresholds: RuleThresholds = Field(default_factory=RuleThresholds)


class Settings(BaseModel):
    database: DatabaseSettings
    tushare: TushareSettings = Field(default_factory=TushareSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    narrative: NarrativeSettings = Field(default_factory=NarrativeSettings)
    notify: NotifySettings = Field(default_factory=NotifySettings)
    automation: AutomationSettings = Field(default_factory=AutomationSettings)
    eval: EvalSettings = Field(default_factory=EvalSettings)
    rss: RssSettings = Field(default_factory=RssSettings)
    rules: RuleSettings = Field(default_factory=RuleSettings)


def _load_secret_files(secrets_dir: str | Path | None) -> None:
    configured = os.getenv("TRADEEYE_SECRETS_DIR")
    base_dir = Path(secrets_dir or configured or DEFAULT_SECRETS_DIR)
    for name in SECRET_ENV_FILES:
        load_dotenv(base_dir / name, override=False)


def load_settings(
    path: str | Path = "config.yaml",
    env_path: str | Path = ".env",
    secrets_dir: str | Path | None = None,
) -> Settings:
    _load_secret_files(secrets_dir)
    load_dotenv(env_path, override=False)
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    data.setdefault("tushare", {})["token"] = os.getenv("TUSHARE_TOKEN")
    data.setdefault("llm", {})["api_key"] = os.getenv("LLM_API_KEY")
    data.setdefault("notify", {})["feishu_webhook"] = os.getenv("FEISHU_WEBHOOK")
    data.setdefault("notify", {})["feishu_verification_token"] = os.getenv("FEISHU_VERIFICATION_TOKEN")
    data.setdefault("notify", {})["public_base_url"] = os.getenv("PUBLIC_BASE_URL")
    data.setdefault("automation", {})["trigger_token"] = os.getenv("AUTOMATION_TRIGGER_TOKEN")
    llm = data.setdefault("llm", {})
    for key, env_name in (("base_url", "LLM_BASE_URL"), ("model", "LLM_MODEL")):
        env_value = os.getenv(env_name)
        if env_value:
            llm[key] = env_value
    rss = data.setdefault("rss", {})
    eval_settings = data.setdefault("eval", {})
    if not rss.get("company_names") and eval_settings.get("company_names"):
        rss["company_names"] = eval_settings["company_names"]
    return Settings.model_validate(data)
