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


def test_workbench_information_architecture_has_three_researcher_views(html):
    for view in ["workbench", "company", "stock-pool"]:
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


def test_manual_feishu_send_ui_is_hidden_but_backend_flow_remains(html, js):
    assert 'id="preview-feishu" class="tonal" hidden' in html
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
    assert 'const VIEWS = ["workbench", "company", "stock-pool"]' in js
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


def test_single_company_input_supports_company_name_candidates(html, js):
    assert 'list="company-ts-code-options"' in html
    assert 'id="company-ts-code-options"' in html
    assert "function renderCompanyOptions()" in js
    assert "function resolveCompanyInput(value)" in js
    assert "renderCompanyOptions();" in js
    assert 'const resolved = resolveCompanyInput(el("company-ts-code").value);' in js
    assert 'notify("请输入覆盖池内的股票代码或公司名称", true);' in js


def test_stock_pool_view_supports_editable_custom_pool(html, js):
    assert 'id="tab-stock-pool"' in html
    assert 'id="view-stock-pool"' in html
    assert 'id="stock-pool-list"' in html
    assert 'id="stock-pool-ts-code"' in html
    assert 'id="stock-pool-name"' in html
    assert 'id="add-stock-pool-item"' in html
    assert 'const VIEWS = ["workbench", "company", "stock-pool"]' in js
    assert 'listStockPool' in js
    assert 'upsertStockPoolItem' in js
    assert 'removeStockPoolItem' in js
    assert 'function renderStockPool(items)' in js
    assert 'data-remove-stock' in js
    assert '>删除</button>' in js
    assert 'function loadStockPool()' in js
    assert 'function addStockPoolItem()' in js


def test_quality_radar_uses_clear_status_colors_and_crisp_title(css):
    quality_js = Path("web/quality-view.js").read_text(encoding="utf-8")
    title_block = css.split(".quality__title {")[1].split("}")[0]
    assert "font-family: var(--sans)" in title_block
    assert "text-rendering: geometricPrecision" not in title_block
    assert "quality-radar__legend" not in quality_js
    assert "外圈正常" not in quality_js
    for cls, color in [
        (".quality-radar__ring--normal", "var(--sev-ok)"),
        (".quality-radar__ring--watch", "var(--sev-yellow)"),
        (".quality-radar__ring--anomaly", "var(--sev-red)"),
    ]:
        block = css.split(f"{cls} {{")[1].split("}")[0]
        assert f"stroke: {color}" in block
        assert f"fill: color-mix(in srgb, {color}" in block
        assert "stroke-width: 2" in block
    dot_block = css.split(".quality-radar__dot {")[1].split("}")[0]
    assert "stroke-width: 1.8" in dot_block


def test_quality_radar_labels_axes_and_has_more_side_space(css):
    quality_js = Path("web/quality-view.js").read_text(encoding="utf-8")
    assert "function radarAxisLabel" in quality_js
    assert "viewBox=\"-8 -8 116 116\"" in quality_js
    assert "quality-radar__label" in quality_js
    body_block = css.split(".quality__body {")[1].split("}")[0]
    assert "220px" in body_block
    svg_block = css.split(".quality-radar svg {")[1].split("}")[0]
    assert "220px" in svg_block
    assert ".quality-radar__label" in css


def test_agent_input_uses_same_body_font_and_chinese_action_buttons(css):
    agent_js = Path("web/agent-panel.js").read_text(encoding="utf-8")
    input_block = css.split(".agent-input textarea {")[1].split("}")[0]
    assert "font-family: var(--sans)" in input_block
    assert "font-size: 14px" in input_block
    assert "确认执行" in agent_js
    assert "取消" in agent_js
    assert "Retry" not in agent_js


def test_scan_progress_uses_indeterminate_without_elapsed_timer(html, js, css):
    assert 'id="scan-progress"' in html
    assert 'role="progressbar"' in html
    assert 'id="progress-elapsed"' not in html
    assert "createProgress" in js
    assert "const elapsedEl = elapsedId ? el(elapsedId) : null;" in js
    assert "if (elapsedEl)" in js
    # 时长未知时使用 indeterminate，不伪造百分比，也不在底部刷秒表
    assert 'data-mode="indeterminate"' in html
    assert "@keyframes indeterminate" in css
    assert "prefers-reduced-motion" in css


def test_card_expand_header_does_not_select_text(css):
    card_head_block = css.split(".card__head {")[1].split("}")[0]
    assert "user-select: none" in card_head_block
    card_body_block = css.split(".card__body {")[1].split("}")[0]
    assert "user-select: text" in card_body_block


def test_paused_jobs_with_bundle_render_results_and_stop_finishes(js):
    paused_branch = js.split('if (job.status === "paused") {')[1].split("state.activeJobId = job.job_id;")[0]
    assert "if (job.bundle)" in paused_branch
    assert "finishDisclosureJob(job);" in paused_branch
    stop_branch = js.split("async function stopDisclosureScan()")[1].split("async function loadDisclosureDay")[0]
    assert '["completed", "cancelled", "failed"].includes(job.status)' in stop_branch
    assert "finishDisclosureJob(job);" in stop_branch


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
        "precision_pct",
        "精确率",
    ]:
        assert marker not in html
        assert marker not in js
    template_header = Path("eval/manual_review_template.csv").read_text(encoding="utf-8").splitlines()[0]
    assert template_header == "ts_code,period,rule_id,label,notes,severity,industry"


def test_evidence_dialog_uses_readable_empty_state(js):
    show_evidence = js.split("async function showEvidence(card, finding)")[1].split("async function showAgentReference")[0]
    assert "暂无结构化依据" in show_evidence
    assert "JSON.stringify(evidence, null, 2)" not in show_evidence


def test_rendering_escapes_untrusted_values(js):
    assert "function escapeHtml(value)" in js
    # 表格用 innerHTML 拼接，每个插值都必须转义
    assert "escapeHtml(event.message)" in js
    assert "escapeHtml(event.ts_code)" in js
    assert "escapeHtml(event.status)" in js
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


def test_cancel_requested_scan_releases_start_button(js):
    stop_branch = js.split("async function stopDisclosureScan()")[1].split("async function loadDisclosureDay")[0]
    assert 'job.current_stage === "cancel_requested"' in stop_branch
    assert "state.activeJobId = null" in stop_branch
    assert 'setScanControls("idle")' in stop_branch


def test_day_route_does_not_auto_start_scan_on_refresh(js):
    apply_route = js.split("async function applyRoute()")[1].split("function navigate(hash)")[0]
    assert "loadDisclosureDay(route.date)" not in apply_route
    click_handler = js.split('scanButton.addEventListener("click", async () => {')[1].split("});", 1)[0]
    assert "loadDisclosureDay(date)" in click_handler


def test_disclosure_scan_uses_cancellable_job_polling(html, js):
    assert 'id="start-disclosure-scan"' in html
    assert 'id="pause-disclosure-scan"' in html
    assert 'id="resume-disclosure-scan"' in html
    assert 'id="stop-disclosure-scan"' in html
    assert 'id="analyze-disclosure-day"' not in html
    assert 'id="scan-disclosure-day"' not in html
    assert "function setScanControls(next)" in js
    assert "pauseDisclosureDayJob(jobId)" in js
    assert "resumeDisclosureDayJob(jobId)" in js
    assert "pauseDisclosureScan" in js
    assert "resumePausedDisclosureScan" in js
    assert "stopDisclosureScan" in js
    assert '"/api/disclosure-day/jobs/"' in js
    assert '"/pause"' in js
    assert '"/resume"' in js
    # 每条释放活跃 job 的路径都要清 activeJobId：正常收尾、轮询失败、暂停后继续创建新 job、停止请求已送达。
    assert js.count("state.activeJobId = null") >= 4
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
