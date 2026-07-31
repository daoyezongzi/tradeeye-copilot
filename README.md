# TradeEye Copilot

TradeEye Copilot 是面向买方研究员的 A 股财报披露即时研判系统。财报落地后，系统输出结构化财务事实、规则驱动异常、依据溯源、归因摘要与市场上下文。不提供荐股、买卖建议或目标价。

## 核心定位

披露高峰期研究员不缺财报摘要，缺的是优先级排序与可复核异常发现。本项目把主线从“总结财报”改为“找出值得追问的问题”。

## 架构

```text
披露日历 -> Context 装配 -> 硬校验 -> 规则引擎 -> 报告编排 -> Web / 飞书
                         \-> PDF 原文抽取 -> 昇腾 API 语气对比/归因
```

核心原则：LLM 永不接触算术。财务数字来自 Tushare 与 pandas，LLM 只负责措辞判断和文字归因。

## 功能

- 当日汇总：披露公司全量覆盖，按异常严重度排序
- 公司研判卡：事实、异常、归因、市场四层结构
- 依据溯源：每条 Finding 携带 `Evidence(source, field, period, value)`
- 硬校验：数据不完整或交叉验算失败时不出研判卡
- 披露季复盘：覆盖池、命中数、规则分布、人工复核精确率
- 飞书推送：静态 webhook 文本提醒，无公网 callback 依赖

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
```

## Runtime config

Secrets are read from environment variables only:

- `TUSHARE_TOKEN`
- `ASCEND_API_KEY`
- `FEISHU_WEBHOOK`

Non-secret settings are in `config.yaml`.

## Run local server

```bash
uvicorn copilot.api.real_app:app --reload
```

Open the local dashboard and click `依据` to inspect evidence JSON.

## Run benchmark scaffold

```bash
python eval/run_backtest.py
```

Generated benchmark artifacts are written to `artifacts/` and are not committed.

## Test

```bash
pytest -q
```

## Compliance boundary

TradeEye Copilot only presents facts, rule-triggered anomalies, source evidence, and market reaction context. It does not output investment advice, target prices, or buy/sell/hold recommendations.
