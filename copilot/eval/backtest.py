from collections import Counter
from pydantic import BaseModel, Field

from copilot.models import Finding


class BacktestCompanyResult(BaseModel):
    ts_code: str
    period: str
    status: str
    findings: list[Finding]
    elapsed_seconds: float | None = None
    industry: str | None = None


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
    severity_distribution: dict[str, int] = Field(default_factory=dict)
    industry_distribution: dict[str, int] = Field(default_factory=dict)


def summarize_backtest(
    start_date: str,
    end_date: str,
    coverage_count: int,
    results: list[BacktestCompanyResult],
) -> BacktestSummary:
    rule_distribution = Counter()
    severity_distribution = Counter()
    industry_distribution = Counter()
    for result in results:
        if result.industry:
            industry_distribution[result.industry] += 1
        for finding in result.findings:
            rule_distribution[finding.rule_id] += 1
            severity_distribution[finding.severity.value] += 1
    return BacktestSummary(
        start_date=start_date,
        end_date=end_date,
        coverage_count=coverage_count,
        disclosed_count=len(results),
        ok_count=sum(1 for result in results if result.status == "OK"),
        data_incomplete_count=sum(1 for result in results if result.status == "DATA_INCOMPLETE"),
        finding_count=sum(len(result.findings) for result in results),
        finding_distribution=dict(sorted(rule_distribution.items())),
        company_results=results,
        severity_distribution=dict(sorted(severity_distribution.items())),
        industry_distribution=dict(sorted(industry_distribution.items())),
    )
