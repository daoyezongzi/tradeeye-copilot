from pathlib import Path
import json
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from copilot.config import load_settings
from copilot.eval.backtest import BacktestCompanyResult, summarize_backtest
from copilot.models import Evidence, Finding, Severity


def demo_result(ts_code: str) -> BacktestCompanyResult:
    finding = Finding(
        rule_id="cashflow_quality",
        severity=Severity.YELLOW,
        title="现金流质量偏弱",
        detail="经营活动现金流净额/净利润低于阈值",
        evidence=[Evidence(source="tushare.cashflow", field="operating_cash_flow", period="20250630", value=4.1)],
        score=23.0,
    )
    return BacktestCompanyResult(ts_code=ts_code, period="20250630", status="OK", findings=[finding], elapsed_seconds=108.0)


def main() -> None:
    settings = load_settings()
    results = [demo_result(ts_code) for ts_code in settings.eval.coverage_pool]
    summary = summarize_backtest(
        settings.eval.start_date,
        settings.eval.end_date,
        coverage_count=len(settings.eval.coverage_pool),
        results=results,
    )
    output = settings.eval.benchmark_output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
