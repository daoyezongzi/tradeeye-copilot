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


def test_workbench_information_architecture_has_four_views(html):
    for view in ["workbench", "company", "review", "diagnostics"]:
        assert f'id="view-{view}"' in html
        assert f'id="tab-{view}"' in html
    assert 'role="tablist"' in html
    assert 'role="tabpanel"' in html


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
    assert 'id="export-menu-csv"' in html
    assert 'id="export-menu-json"' in html
    assert "exportBundleCsv" in js
    assert "exportBundleJson" in js
    assert "function csvCell(value)" in js
    # CSV 注入/断行需要转义
    assert 'text.replace(/"/g, \'""\')' in js


def test_stable_hash_urls_for_day_and_company(js):
    assert 'parts[0] === "day"' in js
    assert 'parts[0] === "company"' in js
    assert "#/company/${card.ts_code}/${card.period}" in js
    assert 'window.addEventListener("hashchange", applyRoute)' in js


def test_review_state_ui_exports_manual_review_columns(html, js):
    assert 'id="view-review"' in html
    assert 'id="export-review-csv"' in html
    assert "REVIEW_STORAGE_KEY" in js
    assert "renderReviewActions" in js
    # 列结构需与 eval/manual_review_template.csv 对齐，并保留评估分组需要的维度
    template_header = Path("eval/manual_review_template.csv").read_text(encoding="utf-8").splitlines()[0]
    assert template_header == "ts_code,period,rule_id,label,notes,severity,industry"
    expected = '["' + '", "'.join(template_header.split(",")) + '"]'
    assert expected in js
    assert "severity: card.max_severity || \"\"" in js
    assert "industry: scanEvent?.industry || \"unknown\"" in js


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
    assert 'id="stop-disclosure-scan"' in html
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
