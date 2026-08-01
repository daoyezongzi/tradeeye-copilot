from copilot.datasource.fundamentals import CompanyProfile
from copilot.industry import Industry
from copilot.models import CompanyIdentity, PeriodSnapshot
from copilot.service.analyzer import AnalyzerService, CompanyAnalysisStatus


class FakeFundamentals:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.calls = []
        self.company_profile = None

    def fetch_snapshot(self, ts_code, period):
        self.calls.append((ts_code, period))
        snapshot = self.snapshots.get((ts_code, period))
        if snapshot is None:
            return PeriodSnapshot(ts_code=ts_code, period=period)
        return snapshot

    def fetch_company_profile(self, ts_code):
        if self.company_profile is not None:
            return self.company_profile
        return CompanyProfile(
            identity=CompanyIdentity(ts_code=ts_code, provider="tushare.stock_basic")
        )


class FakeStore:
    def __init__(self):
        self.snapshots = {}
        self.findings = {}

    def upsert_snapshot(self, snapshot):
        self.snapshots[(snapshot.ts_code, snapshot.period)] = snapshot

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))

    def replace_findings(self, ts_code, period, findings):
        self.findings[(ts_code, period)] = findings


def snapshot(
    ts_code="000001.SZ",
    period="20250630",
    revenue=100.0,
    net_profit=10.0,
    gross_margin_pct=30.0,
    operating_cash_flow=8.0,
    **overrides,
):
    data = {
        "ts_code": ts_code,
        "period": period,
        "ann_date": "20250821",
        "revenue": revenue,
        "net_profit": net_profit,
        "deducted_net_profit": 9.0,
        "gross_margin_pct": gross_margin_pct,
        "operating_cash_flow": operating_cash_flow,
        "accounts_receivable": 20.0,
        "inventory": 15.0,
    }
    data.update(overrides)
    return PeriodSnapshot(**data)


def test_analyze_company_fetches_three_periods_and_returns_card():
    current = snapshot(period="20250630", revenue=112.0, accounts_receivable=147.0)
    prior_quarter = snapshot(period="20250331")
    prior_year = snapshot(period="20240630", revenue=100.0, accounts_receivable=100.0)
    fundamentals = FakeFundamentals(
        {
            ("000001.SZ", "20250630"): current,
            ("000001.SZ", "20250331"): prior_quarter,
            ("000001.SZ", "20240630"): prior_year,
        }
    )
    store = FakeStore()
    service = AnalyzerService(fundamentals=fundamentals, store=store)

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.OK
    assert result.card.ts_code == "000001.SZ"
    assert result.card.period == "20250630"
    assert fundamentals.calls == [
        ("000001.SZ", "20250630"),
        ("000001.SZ", "20250331"),
        ("000001.SZ", "20240630"),
    ]
    assert store.findings[("000001.SZ", "20250630")][0].rule_id == "receivable_revenue_divergence"


def test_analyze_company_returns_data_not_ready_when_current_snapshot_missing_required_values():
    fundamentals = FakeFundamentals({})
    service = AnalyzerService(fundamentals=fundamentals, store=FakeStore())

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.DATA_NOT_READY
    assert "Tushare 暂未返回" in result.message
    assert result.card is None

def test_analyze_company_returns_data_incomplete_when_hard_check_fails():
    current = snapshot(period="20250630", revenue=-1.0)
    fundamentals = FakeFundamentals(
        {
            ("000001.SZ", "20250630"): current,
            ("000001.SZ", "20250331"): snapshot(period="20250331"),
            ("000001.SZ", "20240630"): snapshot(period="20240630"),
        }
    )
    service = AnalyzerService(fundamentals=fundamentals, store=FakeStore())

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.DATA_INCOMPLETE
    assert "current.revenue is negative" in result.message
    assert result.card is None


def test_analyze_company_attaches_classification_and_facts():
    current = snapshot(period="20250630")
    fundamentals = FakeFundamentals(
        {
            ("000001.SZ", "20250630"): current,
            ("000001.SZ", "20250331"): snapshot(period="20250331"),
            ("000001.SZ", "20240630"): snapshot(period="20240630"),
        }
    )
    fundamentals.company_profile = CompanyProfile(
        identity=CompanyIdentity(ts_code="000001.SZ", name="示例公司", provider="tushare.stock_basic"),
        provider_industry="新行业",
    )
    service = AnalyzerService(
        fundamentals=fundamentals,
        store=FakeStore(),
        industry_profiles={"银行": "bank_v1"},
    )

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.OK
    assert result.card.classification.mapping_status.value == "UNMAPPED"
    assert result.card.classification.rule_profile_id == "generic"
    assert result.card.facts
    assert result.card.rule_results


def test_bank_analyze_company_does_not_stop_on_generic_missing_fields():
    current = snapshot(
        period="20250630",
        gross_margin_pct=None,
        accounts_receivable=None,
        inventory=None,
    )
    fundamentals = FakeFundamentals(
        {
            ("000001.SZ", "20250630"): current,
            ("000001.SZ", "20250331"): snapshot(period="20250331"),
            ("000001.SZ", "20240630"): snapshot(period="20240630"),
        }
    )
    service = AnalyzerService(
        fundamentals=fundamentals,
        store=FakeStore(),
        company_industries={"000001.SZ": Industry.BANK.value},
    )

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.OK
    assert result.card is not None
