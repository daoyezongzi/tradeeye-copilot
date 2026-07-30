from copilot.report.builder import CompanyCard, DailySummary


class ReportCache:
    def __init__(self):
        self._companies: dict[tuple[str, str], CompanyCard] = {}
        self._daily: dict[str, DailySummary] = {}

    def put_company(self, card: CompanyCard) -> None:
        self._companies[(card.ts_code, card.period)] = card

    def get_company(self, ts_code: str, period: str) -> CompanyCard | None:
        return self._companies.get((ts_code, period))

    def put_daily(self, summary: DailySummary) -> None:
        self._daily[summary.date] = summary

    def get_daily(self, date: str) -> DailySummary | None:
        return self._daily.get(date)
