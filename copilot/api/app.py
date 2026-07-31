from typing import Protocol

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from copilot.models import Evidence
from copilot.report.builder import CompanyCard, DailySummary, QuarterlyReview
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import DisclosureAnalysisBundle, DisclosureScanResult


class AnalyzeCompanyRequest(BaseModel):
    ts_code: str
    period: str


class AnalyzeDisclosureDayRequest(BaseModel):
    date: str


class NotifyResult(BaseModel):
    sent: bool
    reason: str


class AppMeta(BaseModel):
    coverage_count: int
    company_names: dict[str, str]
    tushare_ready: bool
    feishu_ready: bool


class FeishuPreview(BaseModel):
    date: str
    text: str
    sendable: bool
    reason: str


class DisclosureJobStatus(BaseModel):
    job_id: str
    date: str
    status: str
    processed_count: int
    total_count: int
    ok_count: int
    data_problem_count: int
    current_ts_code: str | None = None
    current_name: str | None = None
    current_period: str | None = None
    current_stage: str
    elapsed_seconds: float
    logs: list[str]
    bundle: DisclosureAnalysisBundle | None = None


class ReportService(Protocol):
    def get_company_card(self, ts_code: str, period: str) -> CompanyCard | None: ...

    def get_daily_summary(self, date: str) -> DailySummary | None: ...

    def get_evidence(self, ts_code: str, period: str, rule_id: str) -> list[Evidence]: ...

    def get_quarterly_review(self) -> QuarterlyReview | None: ...

    def get_meta(self) -> AppMeta: ...

    def analyze_company(self, ts_code: str, period: str) -> CompanyAnalysisResult: ...

    def analyze_disclosure_day(self, date: str) -> DailySummary: ...

    def scan_disclosure_day(self, date: str) -> DisclosureScanResult: ...

    def analyze_disclosure_day_bundle(self, date: str) -> DisclosureAnalysisBundle: ...

    def start_disclosure_day_job(self, date: str) -> DisclosureJobStatus: ...

    def run_disclosure_day_job(self, job_id: str) -> DisclosureJobStatus: ...

    def get_disclosure_day_job(self, job_id: str) -> DisclosureJobStatus: ...

    def cancel_disclosure_day_job(self, job_id: str) -> DisclosureJobStatus: ...

    def poll_rss(self) -> RssPollResult: ...

    def preview_feishu_disclosure_day(self, date: str) -> FeishuPreview: ...

    def notify_feishu_disclosure_day(self, date: str) -> NotifyResult: ...


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

    @app.get("/api/quarterly", response_model=QuarterlyReview)
    def quarterly_review():
        review = report_service.get_quarterly_review()
        if review is None:
            raise HTTPException(status_code=404, detail="quarterly review not found")
        return review

    @app.get("/api/meta", response_model=AppMeta)
    def app_meta():
        return report_service.get_meta()

    @app.post("/api/analyze/company", response_model=CompanyAnalysisResult)
    def analyze_company(request: AnalyzeCompanyRequest):
        return report_service.analyze_company(request.ts_code, request.period)

    @app.post("/api/analyze/disclosure-day", response_model=DailySummary)
    def analyze_disclosure_day(request: AnalyzeDisclosureDayRequest):
        return report_service.analyze_disclosure_day(request.date)

    @app.post("/api/scan/disclosure-day", response_model=DisclosureScanResult)
    def scan_disclosure_day(request: AnalyzeDisclosureDayRequest):
        return report_service.scan_disclosure_day(request.date)

    @app.post("/api/disclosure-day/bundle", response_model=DisclosureAnalysisBundle)
    def disclosure_day_bundle(request: AnalyzeDisclosureDayRequest):
        return report_service.analyze_disclosure_day_bundle(request.date)

    @app.post("/api/disclosure-day/jobs", response_model=DisclosureJobStatus)
    def start_disclosure_day_job(request: AnalyzeDisclosureDayRequest, background_tasks: BackgroundTasks):
        job = report_service.start_disclosure_day_job(request.date)
        job_id = job.job_id if hasattr(job, "job_id") else job["job_id"]
        background_tasks.add_task(report_service.run_disclosure_day_job, job_id)
        return job

    @app.get("/api/disclosure-day/jobs/{job_id}", response_model=DisclosureJobStatus)
    def get_disclosure_day_job(job_id: str):
        return report_service.get_disclosure_day_job(job_id)

    @app.post("/api/disclosure-day/jobs/{job_id}/cancel", response_model=DisclosureJobStatus)
    def cancel_disclosure_day_job(job_id: str):
        return report_service.cancel_disclosure_day_job(job_id)

    @app.post("/api/rss/poll", response_model=RssPollResult)
    def poll_rss():
        return report_service.poll_rss()

    @app.post("/api/notify/feishu/disclosure-day/{date}/preview", response_model=FeishuPreview)
    def preview_feishu_disclosure_day(date: str):
        return report_service.preview_feishu_disclosure_day(date)

    @app.post("/api/notify/feishu/disclosure-day/{date}", response_model=NotifyResult)
    def notify_feishu_disclosure_day(date: str):
        return report_service.notify_feishu_disclosure_day(date)

    app.mount("/", StaticFiles(directory="web", html=True), name="web")
    return app
