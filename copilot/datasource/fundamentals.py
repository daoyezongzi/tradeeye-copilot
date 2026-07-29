from collections.abc import Callable
import time

import pandas as pd

from copilot.models import PeriodSnapshot


def _first_value(frame: pd.DataFrame, column: str):
    if frame.empty or column not in frame.columns:
        return None
    value = frame.iloc[0][column]
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def normalize_financial_snapshot(
    ts_code: str,
    period: str,
    income: pd.DataFrame,
    balancesheet: pd.DataFrame,
    cashflow: pd.DataFrame,
    indicator: pd.DataFrame,
) -> PeriodSnapshot:
    return PeriodSnapshot(
        ts_code=ts_code,
        period=period,
        ann_date=_first_value(income, "ann_date"),
        revenue=_first_value(income, "revenue"),
        net_profit=_first_value(income, "n_income_attr_p"),
        deducted_net_profit=_first_value(indicator, "profit_dedt"),
        gross_margin_pct=_first_value(indicator, "grossprofit_margin"),
        operating_cash_flow=_first_value(cashflow, "n_cashflow_act"),
        accounts_receivable=_first_value(balancesheet, "accounts_receiv"),
        inventory=_first_value(balancesheet, "inventories"),
    )


class TushareFundamentalsClient:
    def __init__(self, pro_api, max_retries: int = 3, sleep_seconds: float = 0.5):
        self.pro_api = pro_api
        self.max_retries = max_retries
        self.sleep_seconds = sleep_seconds

    def _call(self, fn: Callable, **kwargs) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                result = fn(**kwargs)
                return result if result is not None else pd.DataFrame()
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(self.sleep_seconds * (2 ** attempt))
        raise RuntimeError(f"tushare call failed after {self.max_retries} attempts") from last_error

    def fetch_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot:
        params = {"ts_code": ts_code, "period": period}
        income = self._call(self.pro_api.income, **params)
        balancesheet = self._call(self.pro_api.balancesheet, **params)
        cashflow = self._call(self.pro_api.cashflow, **params)
        indicator = self._call(self.pro_api.fina_indicator, **params)
        return normalize_financial_snapshot(ts_code, period, income, balancesheet, cashflow, indicator)
