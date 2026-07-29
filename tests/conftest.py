import pytest

from copilot.models import PeriodSnapshot


@pytest.fixture
def make_snapshot():
    def _make_snapshot(**overrides):
        data = {
            "ts_code": "000001.SZ",
            "period": "20250630",
            "ann_date": "20250821",
            "revenue": 100.0,
            "net_profit": 10.0,
            "deducted_net_profit": 9.0,
            "gross_margin_pct": 30.0,
            "operating_cash_flow": 8.0,
            "accounts_receivable": 20.0,
            "inventory": 15.0,
        }
        data.update(overrides)
        return PeriodSnapshot(**data)

    return _make_snapshot
