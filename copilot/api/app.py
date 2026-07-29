from typing import Protocol

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from copilot.models import Evidence
from copilot.report.builder import CompanyCard, DailySummary


class ReportService(Protocol):
    def get_company_card(self, ts_code: str, period: str) -> CompanyCard | None: ...

    def get_daily_summary(self, date: str) -> DailySummary | None: ...

    def get_evidence(self, ts_code: str, period: str, rule_id: str) -> list[Evidence]: ...


def create_app(report_service: ReportService) -> FastAPI:
    app = FastAPI(title="TradeEye Copilot")

    @app.get("/api/company/{ts_code}/{period}", response_model=CompanyCard)
    def company_card(ts_code: str, period: str):
        card = report_service.get_company_card(ts_code, period)
        if card is None:
            raise HTTPException(status_code=404, detail="company card not found")
        return card

    @app.get("/api/daily/{date}", response_model=DailySummary)
    def daily_summary(date: str):
        summary = report_service.get_daily_summary(date)
        if summary is None:
            raise HTTPException(status_code=404, detail="daily summary not found")
        return summary

    @app.get("/api/evidence/{ts_code}/{period}/{rule_id}", response_model=list[Evidence])
    def evidence(ts_code: str, period: str, rule_id: str):
        return report_service.get_evidence(ts_code, period, rule_id)

    app.mount("/", StaticFiles(directory="web", html=True), name="web")
    return app
