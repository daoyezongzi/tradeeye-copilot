from pathlib import Path
import os

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
    rules: RuleSettings = Field(default_factory=RuleSettings)


def load_settings(path: str | Path = "config.yaml") -> Settings:
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    data.setdefault("tushare", {})["token"] = os.getenv("TUSHARE_TOKEN")
    data.setdefault("llm", {})["api_key"] = os.getenv("ASCEND_API_KEY")
    return Settings.model_validate(data)
