from io import StringIO
import csv
from typing import Protocol

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from copilot.agent.contracts import AgentChatRequest, AgentChatResult
from copilot.agent.exceptions import AgentCardNotFound, AgentLLMError, AgentSessionMismatch, AgentToolError
from copilot.eval.manual_review import PrecisionBreakdown
from copilot.models import AgentFactContext, Evidence
from copilot.report.builder import CompanyCard, DailySummary, QuarterlyReview
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import DisclosureAnalysisBundle, DisclosureScanResult
from copilot.service.notify_store import NotifyLogEvent
from copilot.service.review_store import StoredReviewLabel


class AnalyzeCompanyRequest(BaseModel):
    ts_code: str
    period: str


class AnalyzeDisclosureDayRequest(BaseModel):
    date: str
    resume_from_job_id: str | None = None


class AutomationDisclosureDayRequest(BaseModel):
    date: str
    notify: bool = True


class RssNotifyRequest(BaseModel):
    date: str | None = None


class RssNotifyResult(BaseModel):
    rss: RssPollResult
    sent: bool = False
    reason: str


class AutomationDisclosureDayResult(BaseModel):
    date: str
    job_id: str
    scan_status: str
    notify_sent: bool = False
    notify_reason: str | None = None


class ReviewLabelRequest(BaseModel):
    ts_code: str
    period: str
    rule_id: str
    label: str
    notes: str = ""
    severity: str | None = None
    industry: str | None = None
    reviewer: str | None = None


class FeishuCallbackAction(BaseModel):
    value: dict = Field(default_factory=dict)


class FeishuCallbackOperator(BaseModel):
    name: str | None = None
    user_id: str | None = None


class FeishuCallbackRequest(BaseModel):
    token: str | None = None
    challenge: str | None = None
    action: FeishuCallbackAction | None = None
    operator: FeishuCallbackOperator | None = None


class FeishuCallbackResult(BaseModel):
    ok: bool
    reason: str


class NotifyResult(BaseModel):
    sent: bool
    reason: str


class AppMeta(BaseModel):
    coverage_count: int
    company_names: dict[str, str]
    tushare_ready: bool
    feishu_ready: bool
    agent_ready: bool = False


class FeishuPreview(BaseModel):
    date: str
    text: str
    sendable: bool
    reason: str


class StockPoolItemResponse(BaseModel):
    ts_code: str
    name: str | None = None
    industry: str | None = None


class StockPoolUpsertRequest(BaseModel):
    ts_code: str
    name: str | None = None
    industry: str | None = None


class DisclosureJobStatus(BaseModel):
    job_id: str
    date: str
    status: str
    processed_count: int
    total_count: int
    ok_count: int
    data_problem_count: int
    owner_id: str | None = None
    resume_from_job_id: str | None = None
    current_ts_code: str | None = None
    current_name: str | None = None
    current_period: str | None = None
    current_stage: str
    elapsed_seconds: float
    logs: list[str]
    bundle: DisclosureAnalysisBundle | None = None


class PruneDisclosureJobsResult(BaseModel):
    deleted: int


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

    def start_disclosure_day_job(self, date: str, resume_from_job_id: str | None = None, owner_id: str | None = None) -> DisclosureJobStatus: ...

    def run_disclosure_day_job(self, job_id: str) -> DisclosureJobStatus: ...

    def list_disclosure_day_jobs(self, limit: int = 20, owner_id: str | None = None) -> list[DisclosureJobStatus]: ...

    def get_disclosure_day_job(self, job_id: str, owner_id: str | None = None) -> DisclosureJobStatus: ...

    def cancel_disclosure_day_job(self, job_id: str, owner_id: str | None = None) -> DisclosureJobStatus: ...

    def pause_disclosure_day_job(self, job_id: str, owner_id: str | None = None) -> DisclosureJobStatus: ...

    def resume_disclosure_day_job(self, job_id: str, owner_id: str | None = None) -> DisclosureJobStatus: ...

    def prune_disclosure_day_jobs(self, keep_recent: int = 20) -> int: ...

    def upsert_review_label(self, label: ReviewLabelRequest) -> StoredReviewLabel: ...

    def list_review_labels(self, ts_code: str | None = None, period: str | None = None) -> list[StoredReviewLabel]: ...

    def delete_review_label(self, ts_code: str, period: str, rule_id: str) -> bool: ...

    def get_review_metrics(self, ts_code: str | None = None, period: str | None = None) -> PrecisionBreakdown: ...

    def run_disclosure_automation(self, date: str, notify: bool = True) -> AutomationDisclosureDayResult: ...

    def list_notify_logs(self, limit: int = 20) -> list[NotifyLogEvent]: ...

    def poll_rss(self) -> RssPollResult: ...

    def poll_rss_and_notify_feishu(self, date: str | None = None) -> RssNotifyResult: ...

    def verify_feishu_callback_token(self, token: str | None) -> bool: ...

    def verify_automation_trigger_token(self, token: str | None) -> bool: ...

    def preview_feishu_disclosure_day(self, date: str) -> FeishuPreview: ...

    def notify_feishu_disclosure_day(self, date: str) -> NotifyResult: ...

    def list_stock_pool(self) -> list[StockPoolItemResponse]: ...

    def upsert_stock_pool_item(self, item: StockPoolUpsertRequest) -> StockPoolItemResponse: ...

    def remove_stock_pool_item(self, ts_code: str) -> bool: ...


def create_app(report_service: ReportService, agent_service=None) -> FastAPI:
    app = FastAPI(title="TradeEye Copilot")

    @app.post("/api/agent/chat", response_model=AgentChatResult)
    def agent_chat(request: AgentChatRequest):
        if agent_service is None:
            raise HTTPException(status_code=503, detail="Agent 服务未配置")
        try:
            return agent_service.answer_question(
                request.ts_code,
                request.period,
                request.question,
                session_id=request.session_id,
            )
        except AgentCardNotFound as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AgentSessionMismatch as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AgentToolError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except AgentLLMError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

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

    @app.get("/api/stock-pool", response_model=list[StockPoolItemResponse])
    def list_stock_pool():
        return report_service.list_stock_pool()

    @app.post("/api/stock-pool", response_model=StockPoolItemResponse)
    def upsert_stock_pool_item(item: StockPoolUpsertRequest):
        item.ts_code = item.ts_code.upper()
        return report_service.upsert_stock_pool_item(item)

    @app.delete("/api/stock-pool/{ts_code}")
    def remove_stock_pool_item(ts_code: str):
        return {"deleted": report_service.remove_stock_pool_item(ts_code.upper())}

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
    def start_disclosure_day_job(
        request: AnalyzeDisclosureDayRequest,
        background_tasks: BackgroundTasks,
        x_tradeeye_owner: str | None = Header(default=None),
    ):
        job = report_service.start_disclosure_day_job(
            request.date,
            resume_from_job_id=request.resume_from_job_id,
            owner_id=x_tradeeye_owner,
        )
        job_id = job.job_id if hasattr(job, "job_id") else job["job_id"]
        background_tasks.add_task(report_service.run_disclosure_day_job, job_id)
        return job

    @app.get("/api/disclosure-day/jobs", response_model=list[DisclosureJobStatus])
    def list_disclosure_day_jobs(limit: int = 20, x_tradeeye_owner: str | None = Header(default=None)):
        return report_service.list_disclosure_day_jobs(limit, owner_id=x_tradeeye_owner)

    @app.get("/api/disclosure-day/jobs/{job_id}", response_model=DisclosureJobStatus)
    def get_disclosure_day_job(job_id: str, x_tradeeye_owner: str | None = Header(default=None)):
        return report_service.get_disclosure_day_job(job_id, owner_id=x_tradeeye_owner)

    @app.post("/api/disclosure-day/jobs/{job_id}/cancel", response_model=DisclosureJobStatus)
    def cancel_disclosure_day_job(job_id: str, x_tradeeye_owner: str | None = Header(default=None)):
        return report_service.cancel_disclosure_day_job(job_id, owner_id=x_tradeeye_owner)

    @app.post("/api/disclosure-day/jobs/{job_id}/pause", response_model=DisclosureJobStatus)
    def pause_disclosure_day_job(job_id: str, x_tradeeye_owner: str | None = Header(default=None)):
        return report_service.pause_disclosure_day_job(job_id, owner_id=x_tradeeye_owner)

    @app.post("/api/disclosure-day/jobs/{job_id}/resume", response_model=DisclosureJobStatus)
    def resume_disclosure_day_job(job_id: str, x_tradeeye_owner: str | None = Header(default=None)):
        return report_service.resume_disclosure_day_job(job_id, owner_id=x_tradeeye_owner)

    @app.delete("/api/disclosure-day/jobs", response_model=PruneDisclosureJobsResult)
    def prune_disclosure_day_jobs(keep_recent: int = 20):
        return PruneDisclosureJobsResult(deleted=report_service.prune_disclosure_day_jobs(keep_recent))

    @app.get("/api/reviews/labels.csv")
    def export_review_labels_csv(ts_code: str | None = None, period: str | None = None):
        labels = report_service.list_review_labels(ts_code=ts_code, period=period)
        buffer = StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=["ts_code", "period", "rule_id", "label", "notes", "severity", "industry", "reviewer", "updated_at"],
        )
        writer.writeheader()
        for label in labels:
            writer.writerow(label.model_dump())
        return Response(content=buffer.getvalue(), media_type="text/csv")

    @app.get("/api/reviews/metrics", response_model=PrecisionBreakdown)
    def get_review_metrics(ts_code: str | None = None, period: str | None = None):
        return report_service.get_review_metrics(ts_code=ts_code, period=period)

    @app.post("/api/reviews/labels", response_model=StoredReviewLabel)
    def upsert_review_label(label: ReviewLabelRequest):
        return report_service.upsert_review_label(label)

    @app.get("/api/reviews/labels", response_model=list[StoredReviewLabel])
    def list_review_labels(ts_code: str | None = None, period: str | None = None):
        return report_service.list_review_labels(ts_code=ts_code, period=period)

    @app.delete("/api/reviews/labels/{ts_code}/{period}/{rule_id}")
    def delete_review_label(ts_code: str, period: str, rule_id: str):
        return {"deleted": report_service.delete_review_label(ts_code=ts_code, period=period, rule_id=rule_id)}

    @app.post("/api/automation/disclosure-day", response_model=AutomationDisclosureDayResult)
    def run_disclosure_automation(request: AutomationDisclosureDayRequest):
        return report_service.run_disclosure_automation(request.date, notify=request.notify)

    @app.post("/api/automation/disclosure-day/cron", response_model=AutomationDisclosureDayResult)
    def run_disclosure_automation_cron(request: AutomationDisclosureDayRequest, x_automation_token: str | None = Header(default=None)):
        if not report_service.verify_automation_trigger_token(x_automation_token):
            raise HTTPException(status_code=403, detail="invalid automation trigger token")
        return report_service.run_disclosure_automation(request.date, notify=request.notify)

    @app.post("/api/rss/poll", response_model=RssPollResult)
    def poll_rss():
        return report_service.poll_rss()

    @app.post("/api/rss/poll/notify", response_model=RssNotifyResult)
    def poll_rss_and_notify_feishu(request: RssNotifyRequest):
        return report_service.poll_rss_and_notify_feishu(request.date)

    @app.get("/api/notify/logs", response_model=list[NotifyLogEvent])
    def list_notify_logs(limit: int = 20):
        return report_service.list_notify_logs(limit)

    @app.post("/api/notify/feishu/callback")
    def feishu_callback(callback: FeishuCallbackRequest):
        verify_callback = getattr(report_service, "verify_feishu_callback_token", lambda token: True)
        if not verify_callback(callback.token):
            raise HTTPException(status_code=403, detail="invalid feishu callback token")
        if callback.challenge is not None:
            return {"challenge": callback.challenge}
        if callback.action is None:
            return FeishuCallbackResult(ok=False, reason="ignored")
        value = callback.action.value
        if value.get("action") != "review_label":
            return FeishuCallbackResult(ok=False, reason="ignored")
        reviewer = None
        if callback.operator is not None:
            reviewer = callback.operator.name or callback.operator.user_id
        report_service.upsert_review_label(
            ReviewLabelRequest(
                ts_code=value["ts_code"],
                period=value["period"],
                rule_id=value["rule_id"],
                label=value["label"],
                notes=value.get("notes", ""),
                severity=value.get("severity"),
                industry=value.get("industry"),
                reviewer=reviewer,
            )
        )
        return FeishuCallbackResult(ok=True, reason="review_recorded")

    @app.post("/api/notify/feishu/disclosure-day/{date}/preview", response_model=FeishuPreview)
    def preview_feishu_disclosure_day(date: str):
        return report_service.preview_feishu_disclosure_day(date)

    @app.post("/api/notify/feishu/disclosure-day/{date}", response_model=NotifyResult)
    def notify_feishu_disclosure_day(date: str):
        return report_service.notify_feishu_disclosure_day(date)

    app.mount("/", StaticFiles(directory="web", html=True), name="web")
    return app
