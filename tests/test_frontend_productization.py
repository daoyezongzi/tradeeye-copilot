from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def html() -> str:
    return Path("web/index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js() -> str:
    return Path("web/app.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css() -> str:
    return Path("web/styles.css").read_text(encoding="utf-8")


def test_workbench_information_architecture_has_two_researcher_views(html):
    for view in ["workbench", "company"]:
        assert f'id="view-{view}"' in html
        assert f'id="tab-{view}"' in html
    for removed in ["review", "diagnostics"]:
        assert f'id="view-{removed}"' not in html
        assert f'id="tab-{removed}"' not in html
    assert 'role="tablist"' in html
    assert 'role="tabpanel"' in html


def test_advanced_sections_are_collapsed_disclosures(html, css):
    # 高级诊断与开发者工具各成一个原生 details：键盘可达、Ctrl+F 能搜到收起区内文字
    assert '<details id="adv-diagnostics"' in html
    assert '<details id="adv-developer"' in html
    # 默认收起：details 上不带 open 属性
    assert "open" not in html.split('<details id="adv-diagnostics"')[1].split(">")[0]
    assert "open" not in html.split('<details id="adv-developer"')[1].split(">")[0]
    # 容器 id 全部不变，因此 renderDiagnostics / loadQuarterly / setStatus 无需改动
    for container in ["diagnostic-status", "quarterly-review", "operation-status", "poll-rss"]:
        assert f'id="{container}"' in html
    assert ".fold {" in css


def test_job_history_has_refresh_and_restore_controls(html, js):
    assert 'id="job-history"' in html
    assert 'id="refresh-job-history"' in html
    assert 'id="prune-job-history"' in html
    assert "listDisclosureDayJobs" in js
    assert "pruneDisclosureDayJobs" in js
    assert "resumeDisclosureJob" in js
    assert "resume_from_job_id" in js
    assert "renderJobHistory" in js
    assert "loadJobHistory" in js
    assert "restoreDisclosureJob" in js
    assert "/api/disclosure-day/jobs?limit=" in js
    assert 'el("refresh-job-history").addEventListener("click", loadJobHistory)' in js
    assert 'el("prune-job-history").addEventListener("click", pruneJobHistory)' in js
    assert "loadJobHistory();" in js




def test_developer_panel_keeps_operations_without_review_exposure(html, js):
    assert 'id="automation-date" type="date"' in html
    assert 'id="run-automation"' in html
    assert 'id="automation-status"' in html
    assert 'id="refresh-notify-logs"' in html
    assert 'id="notify-log-table"' in html
    assert 'id="review-sync-status"' not in html
    assert "runDisclosureAutomation" in js
    assert "listNotifyLogs" in js
    assert "renderAutomationStatus" in js
    assert "renderNotifyLogs" in js
    assert "renderReviewSyncStatus" not in js
    assert '"/api/automation/disclosure-day"' in js
    assert '"/api/notify/logs?limit="' in js
    assert 'el("run-automation").addEventListener("click", runAutomation)' in js
    assert 'el("refresh-notify-logs").addEventListener("click", loadNotifyLogs)' in js


def test_feishu_preview_requires_send_confirmation(html, js):
    assert 'id="feishu-dialog"' in html
    assert 'id="feishu-preview-text"' in html
    assert 'id="cancel-feishu"' in html
    assert "previewFeishuDisclosureDay(date)" in js
    assert "/preview" in js
    # 发送只能来自预览弹窗中的确认按钮
    assert "confirmSendFeishu" in js
    assert 'sendFeishuButton.addEventListener("click", confirmSendFeishu)' in js
    # 后端判定不可发送时禁用确认按钮
    assert "sendFeishuButton.disabled = !preview.sendable" in js


def test_cards_group_by_severity_and_data_problems(html, js):
    assert 'id="severity-filters"' in html
    for value in ["RED", "YELLOW", "OK", "DATA"]:
        assert f'data-filter="{value}"' in html
    assert "renderDataProblemGroup" in js
    assert 'severityKey(card) === "RED"' in js
    assert 'event.status !== "OK"' in js


def test_company_names_come_from_meta_route(js):
    assert '"/api/meta"' in js
    assert "function displayName(tsCode)" in js
    assert "state.meta.company_names[tsCode]" in js


def test_navigation_views_exclude_review_route(js):
    assert 'const VIEWS = ["workbench", "company"]' in js
    assert 'review: "复核队列"' not in js
    assert 'if (VIEWS.includes(parts[0])) return { view: parts[0] };' in js
    assert 'navigate("#/workbench")' in js


def test_company_display_is_name_first_with_code_subtitle(js):
    assert "function companyTitle(tsCode)" in js
    assert "function companySubtitle(tsCode, period)" in js
    assert "return displayName(tsCode) || tsCode;" in js
    assert "return `${tsCode} · ${periodLabel(period)}`;" in js
    assert "name.textContent = companyTitle(card.ts_code);" in js
    assert "code.textContent = companySubtitle(card.ts_code, card.period);" in js
    assert "title: companyTitle(card.ts_code)" in js
    assert "subtitle: companySubtitle(card.ts_code, card.period)" in js


def test_scan_progress_reports_elapsed_time(html, js, css):
    assert 'id="scan-progress"' in html
    assert 'role="progressbar"' in html
    assert 'id="progress-elapsed"' in html
    assert "createProgress" in js
    assert "performance.now()" in js
    # 时长未知时使用 indeterminate，不伪造百分比
    assert 'data-mode="indeterminate"' in html
    assert "@keyframes indeterminate" in css
    assert "prefers-reduced-motion" in css


def test_exports_cover_csv_and_json(html, js):
    # 导出项收进顶栏「导出 ▾」菜单后改由 JS 创建，id 保持不变但不再出现在 HTML 里
    assert 'id="export-menu-csv"' not in html
    assert 'id="export-menu-json"' not in html
    assert 'id="export-menu-mount"' in html
    assert '<script src="/components.js"></script>' in html
    # 无 ES module，加载顺序即契约：components.js 必须先于 app.js
    assert html.index("/components.js") < html.index("/app.js")
    assert "export-menu-csv" in js
    assert "export-menu-json" in js
    assert "createMenuButton" in js
    assert "exportBundleCsv" in js
    assert "exportBundleJson" in js
    assert "function csvCell(value)" in js
    # CSV 注入/断行需要转义
    assert 'text.replace(/"/g, \'""\')' in js


def test_menu_component_is_keyboard_accessible():
    components = Path("web/components.js").read_text(encoding="utf-8")

    assert "function createMenuButton(" in components
    assert 'aria-haspopup", "menu"' in components
    assert 'aria-expanded' in components
    assert '"Escape"' in components
    assert '"ArrowDown"' in components
    assert '"ArrowUp"' in components
    # 点菜单外部要能关闭
    assert "wrap.contains(event.target)" in components


def test_stable_hash_urls_for_day_and_company(js):
    assert 'parts[0] === "day"' in js
    assert 'parts[0] === "company"' in js
    assert "#/company/${card.ts_code}/${card.period}" in js
    assert 'window.addEventListener("hashchange", applyRoute)' in js


def test_researcher_frontend_does_not_expose_review_ui_or_calls(html, js):
    for marker in [
        'id="view-review"',
        'id="tab-review"',
        'id="review-metrics"',
        'id="review-table"',
        'id="export-review-csv"',
        'id="review-sync-status"',
        'class="review-actions"',
        "renderReviewActions",
        "loadReviewLabels",
        "loadReviewMetrics",
        "renderReviewMetrics",
        "renderReviewSyncStatus",
        "exportReviewCsv",
        "saveReviewLabel",
        "clearReviewLabel",
        "setReviewLabel",
        "reviewLabels",
        '"/api/reviews/labels"',
        '"/api/reviews/metrics"',
        '"/api/reviews/labels.csv"',
    ]:
        assert marker not in html
        assert marker not in js
    template_header = Path("eval/manual_review_template.csv").read_text(encoding="utf-8").splitlines()[0]
    assert template_header == "ts_code,period,rule_id,label,notes,severity,industry"


def test_rendering_escapes_untrusted_values(js):
    assert "function escapeHtml(value)" in js
    # 表格用 innerHTML 拼接，每个插值都必须转义
    assert "escapeHtml(event.message)" in js
    assert "escapeHtml(entry.rule_id)" in js
    # 公司卡走 textContent，不用 innerHTML
    assert ".innerHTML = `" not in js.split("function renderCard(")[1].split("function renderDataProblemGroup(")[0]


def test_disclosure_date_uses_native_date_picker(html, js):
    assert 'id="disclosure-date" type="date"' in html
    # 控件值是 YYYY-MM-DD，接口与 hash 路由要求 YYYYMMDD
    assert "function toApiDate(value)" in js
    assert "function toInputDate(value)" in js
    assert "function selectedDate()" in js
    assert "el(\"disclosure-date\").value.trim()" not in js
    assert 'input[type="date"]' in Path("web/styles.css").read_text(encoding="utf-8")


def test_report_period_is_a_bounded_select(html, js):
    assert '<select id="company-period">' in html
    assert "function periodOptions(" in js
    for suffix in ["0331", "0630", "0930", "1231"]:
        assert suffix in js
    # 路由带入的报告期若不在选项内也要可选中
    assert "function ensurePeriodOption(period)" in js


def test_disclosure_scan_uses_cancellable_job_polling(html, js):
    # 扫描按钮是单节点三态，空闲态不再常驻一个永远灰着的停止按钮
    assert 'id="start-disclosure-scan"' in html
    assert 'id="stop-disclosure-scan"' not in html
    assert 'id="analyze-disclosure-day"' not in html
    assert 'id="scan-disclosure-day"' not in html
    # 三处 disabled 重置收敛到一个函数
    assert "function setScanState(next)" in js
    # disabled 只有一个赋值点，锁住"收敛"这个不变量
    assert js.count("scanButton.disabled") == 1
    assert 'setScanState("cancelling")' in js
    # 每条终止路径都要清 activeJobId，否则 loadDisclosureDay 的守卫会永久拦住下一次扫描：
    # 正常收尾（finishDisclosureJob）与轮询失败 catch 各一处
    assert js.count("state.activeJobId = null") == 2
    assert "/api/disclosure-day/jobs" in js
    assert "startDisclosureDayJob(date)" in js
    assert "getDisclosureDayJob(jobId)" in js
    assert "cancelDisclosureDayJob(jobId)" in js
    assert "pollDisclosureJob" in js
    assert "renderJobProgress" in js
    assert "current_ts_code" in js
    assert "current_stage" in js
    assert "stopDisclosureScan" in js


def test_summary_renders_severity_distribution(html, js, css):
    assert 'id="summary-distribution"' in html
    assert 'class="overview"' in html
    assert "renderDistribution" in js
    assert "node.style.flexGrow" in js
    for seg in ["seg-red", "seg-yellow", "seg-ok", "seg-data"]:
        assert seg in js
        assert f".{seg}" in css


def test_design_tokens_follow_material_and_apple_conventions(css):
    for token in [
        "--md-sys-color-primary",
        "--md-sys-color-surface-container",
        "--md-sys-color-on-surface-variant",
        "--md-sys-color-outline-variant",
    ]:
        assert token in css
    # 明暗双色
    assert "prefers-color-scheme: dark" in css
    assert "color-scheme: light dark" in css
    # HIG：功能层半透明材质浮于内容层之上
    assert "backdrop-filter" in css
    assert "-apple-system" in css
    # 8pt 栅格
    assert "--space-2: 8px" in css
    assert "--space-4: 16px" in css
