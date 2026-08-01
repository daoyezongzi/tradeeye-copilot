import pandas as pd
import pytest

from copilot.datasource.fundamentals import (
    TushareFundamentalsClient,
    TushareFetchCancelled,
    normalize_company_profile,
    normalize_financial_snapshot,
)


def test_normalize_company_profile_reads_identity_and_industry():
    profile = normalize_company_profile(
        "600000.SH",
        pd.DataFrame([{"ts_code": "600000.SH", "name": "示例银行", "industry": "银行"}]),
    )

    assert profile.ts_code == "600000.SH"
    assert profile.name == "示例银行"
    assert profile.provider_industry == "银行"
    assert profile.source == "tushare.stock_basic"


def test_normalize_company_profile_keeps_empty_industry_unresolved():
    profile = normalize_company_profile("600000.SH", pd.DataFrame())

    assert profile.name is None
    assert profile.provider_industry is None
    income = pd.DataFrame([
        {"ts_code": "000001.SZ", "end_date": "20250630", "ann_date": "20250821", "revenue": 100.0, "n_income_attr_p": 10.0}
    ])
    balancesheet = pd.DataFrame([
        {"ts_code": "000001.SZ", "end_date": "20250630", "accounts_receiv": 20.0, "inventories": 15.0}
    ])
    cashflow = pd.DataFrame([
        {"ts_code": "000001.SZ", "end_date": "20250630", "n_cashflow_act": 8.0}
    ])
    indicator = pd.DataFrame([
        {"ts_code": "000001.SZ", "end_date": "20250630", "grossprofit_margin": 30.0, "profit_dedt": 9.0}
    ])

    snapshot = normalize_financial_snapshot("000001.SZ", "20250630", income, balancesheet, cashflow, indicator)

    assert snapshot.ts_code == "000001.SZ"
    assert snapshot.period == "20250630"
    assert snapshot.ann_date == "20250821"
    assert snapshot.revenue == 100.0
    assert snapshot.net_profit == 10.0
    assert snapshot.deducted_net_profit == 9.0
    assert snapshot.gross_margin_pct == 30.0
    assert snapshot.operating_cash_flow == 8.0
    assert snapshot.accounts_receivable == 20.0
    assert snapshot.inventory == 15.0




def test_normalize_financial_snapshot_keeps_missing_optional_fields_as_none():
    empty = pd.DataFrame()
    income = pd.DataFrame([
        {"ts_code": "000001.SZ", "end_date": "20250630", "ann_date": "20250821", "revenue": 100.0, "n_income_attr_p": 10.0}
    ])

    snapshot = normalize_financial_snapshot("000001.SZ", "20250630", income, empty, empty, empty)

    assert snapshot.accounts_receivable is None
    assert snapshot.inventory is None
    assert snapshot.operating_cash_flow is None


class ProgressProApi:
    def __init__(self):
        self.calls = []

    def income(self, **kwargs):
        self.calls.append("income")
        return pd.DataFrame([
            {"ts_code": kwargs["ts_code"], "end_date": kwargs["period"], "ann_date": "20250821", "revenue": 100.0, "n_income_attr_p": 10.0}
        ])

    def balancesheet(self, **kwargs):
        self.calls.append("balancesheet")
        return pd.DataFrame([{"ts_code": kwargs["ts_code"], "end_date": kwargs["period"], "accounts_receiv": 20.0, "inventories": 15.0}])

    def cashflow(self, **kwargs):
        self.calls.append("cashflow")
        return pd.DataFrame([{"ts_code": kwargs["ts_code"], "end_date": kwargs["period"], "n_cashflow_act": 8.0}])

    def fina_indicator(self, **kwargs):
        self.calls.append("fina_indicator")
        return pd.DataFrame([{"ts_code": kwargs["ts_code"], "end_date": kwargs["period"], "grossprofit_margin": 30.0, "profit_dedt": 9.0}])


def test_tushare_client_reports_table_fetch_progress():
    stages = []
    client = TushareFundamentalsClient(ProgressProApi(), progress_callback=lambda stage, ts_code, period: stages.append((stage, ts_code, period)))

    snapshot = client.fetch_snapshot("000001.SZ", "20250630")

    assert snapshot.revenue == 100.0
    assert stages == [
        ("fetch_income", "000001.SZ", "20250630"),
        ("fetch_balancesheet", "000001.SZ", "20250630"),
        ("fetch_cashflow", "000001.SZ", "20250630"),
        ("fetch_indicator", "000001.SZ", "20250630"),
    ]


def test_tushare_client_stops_between_table_fetches_when_cancelled():
    stages = []

    def progress(stage, ts_code, period):
        stages.append(stage)

    client = TushareFundamentalsClient(
        ProgressProApi(),
        progress_callback=progress,
        should_cancel=lambda: "fetch_income" in stages,
    )

    with pytest.raises(TushareFetchCancelled):
        client.fetch_snapshot("000001.SZ", "20250630")

    assert stages == ["fetch_income"]
