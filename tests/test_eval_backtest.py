from copilot.eval.backtest import BacktestCompanyResult, summarize_backtest
from copilot.models import Evidence, Finding, Severity


def finding(rule_id, severity):
    return Finding(
        rule_id=rule_id,
        severity=severity,
        title=rule_id,
        detail=f"{rule_id} detail",
        evidence=[Evidence(source="tushare.income", field="revenue", period="20250630", value=100.0)],
        score=50.0,
    )


def test_summarize_backtest_counts_companies_and_findings():
    results = [
        BacktestCompanyResult(ts_code="000001.SZ", period="20250630", status="OK", findings=[finding("cashflow_quality", Severity.YELLOW)]),
        BacktestCompanyResult(ts_code="600000.SH", period="20250630", status="OK", findings=[finding("gross_margin_change", Severity.YELLOW), finding("non_recurring_profit_share", Severity.YELLOW)]),
        BacktestCompanyResult(ts_code="000002.SZ", period="20250630", status="DATA_INCOMPLETE", findings=[]),
    ]

    summary = summarize_backtest("20250801", "20250831", coverage_count=42, results=results)

    assert summary.coverage_count == 42
    assert summary.disclosed_count == 3
    assert summary.ok_count == 2
    assert summary.data_incomplete_count == 1
    assert summary.finding_count == 3
    assert summary.finding_distribution == {
        "cashflow_quality": 1,
        "gross_margin_change": 1,
        "non_recurring_profit_share": 1,
    }
