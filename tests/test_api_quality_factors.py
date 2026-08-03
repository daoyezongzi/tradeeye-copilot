from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, QualityFactorCompareResult, create_app
from copilot.quality.factors import FactorStatus, QualityFactor, QualityOverview
from copilot.report.builder import CompanyCard


def _factor(status=FactorStatus.NORMAL):
    return QualityFactor(
        factor_id="cashflow_quality",
        label="现金质量",
        status=status,
        summary="经营现金流对净利润有基本支撑。",
        rule_ids=["cashflow_quality"],
        fact_ids=["operating_cash_flow", "net_profit"],
    )


def _card(ts_code: str, period: str):
    return CompanyCard(
        ts_code=ts_code,
        period=period,
        fact_line="营收 100",
        findings=[],
        quality_factors=[_factor()],
        quality_overview=QualityOverview(
            status=FactorStatus.NORMAL,
            normal_count=1,
            watch_count=0,
            anomaly_count=0,
            not_evaluated_count=0,
            not_applicable_count=0,
            summary="正常 1 项",
        ),
    )


class FakeQualityService:
    def get_company_card(self, ts_code, period):
        return _card(ts_code, period)

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def get_meta(self):
        return AppMeta(coverage_count=0, company_names={}, tushare_ready=True, feishu_ready=False)

    def compare_quality_factors(self, items, mode):
        periods = {item.period for item in items}
        comparability = "STRICT" if mode != "custom" and len(periods) == 1 else "EXPLORATORY"
        warnings = [] if comparability == "STRICT" else ["期间不一致，仅供探索，不作为严格横向比较"]
        return QualityFactorCompareResult(
            mode=mode,
            comparability=comparability,
            warnings=warnings,
            items=[self.get_company_card(item.ts_code, item.period) for item in items],
        )


def test_quality_factor_compare_route_same_period_is_strict():
    client = TestClient(create_app(FakeQualityService()))

    response = client.post(
        "/api/quality-factors/compare",
        json={
            "mode": "same_period_companies",
            "items": [
                {"ts_code": "603026.SH", "period": "20250630"},
                {"ts_code": "600809.SH", "period": "20250630"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["comparability"] == "STRICT"
    assert payload["warnings"] == []
    assert payload["items"][0]["quality_factors"][0]["factor_id"] == "cashflow_quality"


def test_quality_factor_compare_route_custom_mixed_period_is_exploratory():
    client = TestClient(create_app(FakeQualityService()))

    response = client.post(
        "/api/quality-factors/compare",
        json={
            "mode": "custom",
            "items": [
                {"ts_code": "603026.SH", "period": "20250630"},
                {"ts_code": "603026.SH", "period": "20250331"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["comparability"] == "EXPLORATORY"
    assert "期间不一致" in payload["warnings"][0]
