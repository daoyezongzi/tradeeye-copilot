import pandas as pd

from copilot.datasource.fundamentals import normalize_financial_snapshot


def test_normalize_financial_snapshot_combines_four_tables():
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
