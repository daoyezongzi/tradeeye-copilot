# TradeEye Copilot

A 股财报披露即时研判系统。当前阶段先实现结构化财务快照、硬校验、异常规则引擎与可复核 Evidence。

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
```

## Runtime secrets

Secrets are read from environment variables only. Do not commit `.env`.

- `TUSHARE_TOKEN`
- `ASCEND_API_KEY`
- `FEISHU_WEBHOOK`
