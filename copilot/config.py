from pathlib import Path
import os

from dotenv import load_dotenv
import yaml
from pydantic import BaseModel, Field


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


class EvalSettings(BaseModel):
    coverage_pool: list[str] = Field(default_factory=list)
    start_date: str = "20250801"
    end_date: str = "20250831"
    benchmark_output: Path = Path("artifacts/benchmark.json")


class RssSettings(BaseModel):
    feeds: list[str] = Field(default_factory=list)
    max_entries: int = 50


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
    eval: EvalSettings = Field(default_factory=EvalSettings)
    rss: RssSettings = Field(default_factory=RssSettings)
    rules: RuleSettings = Field(default_factory=RuleSettings)


def load_settings(path: str | Path = "config.yaml", env_path: str | Path = ".env") -> Settings:
    load_dotenv(env_path, override=False)
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    data.setdefault("tushare", {})["token"] = os.getenv("TUSHARE_TOKEN")
    data.setdefault("llm", {})["api_key"] = os.getenv("ASCEND_API_KEY")
    data.setdefault("notify", {})["feishu_webhook"] = os.getenv("FEISHU_WEBHOOK")
    return Settings.model_validate(data)
