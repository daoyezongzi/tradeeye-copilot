from pathlib import Path

from pydantic import BaseModel, Field
import yaml


class Watchlist(BaseModel):
    coverage_pool: list[str] = Field(default_factory=list)
    company_names: dict[str, str] = Field(default_factory=dict)
    company_industries: dict[str, str] = Field(default_factory=dict)


def load_watchlist_yaml(path: str | Path) -> Watchlist:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    watchlist = Watchlist.model_validate(data)
    missing = [
        code
        for code in watchlist.coverage_pool
        if code not in watchlist.company_names or code not in watchlist.company_industries
    ]
    if missing:
        raise ValueError(f"watchlist missing name or industry for: {', '.join(missing)}")
    return watchlist
