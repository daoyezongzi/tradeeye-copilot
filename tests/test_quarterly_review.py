from copilot.eval.backtest import BacktestCompanyResult, BacktestSummary
from copilot.models import Evidence, Finding, Severity
from copilot.report.builder import build_quarterly_review


def finding(rule_id):
    return Finding(
        rule_id=rule_id,
        severity=Severity.YELLOW,
        title=rule_id,
        detail=f"{rule_id} detail",
        evidence=[Evidence(source="tushare.income", field="revenue", period="20250630", value=100.0)],
        score=50.0,
    )


def test_build_quarterly_review_from_backtest_summary():
    summary = BacktestSummary(
        start_date="20250801",
        end_date="20250831",
        coverage_count=42,
        disclosed_count=2,
        ok_count=2,
        data_incomplete_count=0,
        finding_count=3,
        finding_distribution={"cashflow_quality": 2, "gross_margin_change": 1},
        company_results=[
            BacktestCompanyResult(ts_code="000001.SZ", period="20250630", status="OK", findings=[finding("cashflow_quality")]),
            BacktestCompanyResult(ts_code="600000.SH", period="20250630", status="OK", findings=[finding("cashflow_quality"), finding("gross_margin_change")]),
        ],
    )

    review = build_quarterly_review(summary, precision_pct=88.9)

    assert review.period_label == "20250801-20250831"
    assert review.coverage_count == 42
    assert review.precision_pct == 88.9
    assert review.top_rules[0].rule_id == "cashflow_quality"
    assert review.top_rules[0].count == 2
