from collections import Counter
from pydantic import BaseModel

from copilot.models import Finding


class BacktestCompanyResult(BaseModel):
    ts_code: str
    period: str
    status: str
    findings: list[Finding]
    elapsed_seconds: float | None = None


class BacktestSummary(BaseModel):
    start_date: str
    end_date: str
    coverage_count: int
    disclosed_count: int
    ok_count: int
    data_incomplete_count: int
    finding_count: int
    finding_distribution: dict[str, int]
    company_results: list[BacktestCompanyResult]


def summarize_backtest(
    start_date: str,
    end_date: str,
    coverage_count: int,
    results: list[BacktestCompanyResult],
) -> BacktestSummary:
    distribution = Counter()
    for result in results:
        for finding in result.findings:
            distribution[finding.rule_id] += 1
    return BacktestSummary(
        start_date=start_date,
        end_date=end_date,
        coverage_count=coverage_count,
        disclosed_count=len(results),
        ok_count=sum(1 for result in results if result.status == "OK"),
        data_incomplete_count=sum(1 for result in results if result.status == "DATA_INCOMPLETE"),
        finding_count=sum(len(result.findings) for result in results),
        finding_distribution=dict(sorted(distribution.items())),
        company_results=results,
    )
