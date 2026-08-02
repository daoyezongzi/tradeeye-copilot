from datetime import datetime, UTC
import os

import yaml

from copilot.datasource.tushare_client import TushareTokenMissing, create_tushare_pro
from copilot.rss.actions import run_rss_feishu_reminder, run_tushare_feishu_reminder


def _split_env_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]


def _load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def main() -> int:
    config = _load_config(os.getenv("TRADEEYE_CONFIG", "config.yaml"))
    rss_config = config.get("rss", {})
    eval_config = config.get("eval", {})
    feeds = _split_env_list(os.getenv("RSS_FEEDS")) or rss_config.get("feeds", [])
    company_names = eval_config.get("company_names", {})
    company_to_ts_code = {name: ts_code for ts_code, name in company_names.items()} or rss_config.get("company_names", {})
    date = os.getenv("DISCLOSURE_DATE") or datetime.now(UTC).strftime("%Y%m%d")
    try:
        pro = create_tushare_pro(os.getenv("TUSHARE_TOKEN"))
    except TushareTokenMissing:
        pro = None
    if pro is not None:
        result = run_tushare_feishu_reminder(
            pro_api=pro,
            coverage_pool=eval_config.get("coverage_pool", []),
            company_names=company_names,
            webhook_url=os.getenv("FEISHU_WEBHOOK"),
            date=date,
        )
    else:
        result = run_rss_feishu_reminder(
            feeds=feeds,
            max_entries=int(os.getenv("RSS_MAX_ENTRIES", rss_config.get("max_entries", 50))),
            company_to_ts_code=company_to_ts_code,
            company_names=company_names,
            webhook_url=os.getenv("FEISHU_WEBHOOK"),
            date=date,
        )
    print(result.model_dump_json())
    return 0 if result.reason in {"ok", "no_matches", "webhook_not_configured"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
