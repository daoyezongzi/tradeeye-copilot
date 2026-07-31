from pathlib import Path


def test_frontend_defines_api_wrapper_methods():
    content = Path("web/app.js").read_text(encoding="utf-8")

    assert "analyzeCompany(tsCode, period)" in content
    # 披露日扫描走 job 三件套；一次性的旧 wrapper 已无调用点，已清理
    assert "startDisclosureDayJob(date)" in content
    assert "getDisclosureDayJob(jobId)" in content
    assert "cancelDisclosureDayJob(jobId)" in content
    assert "analyzeDisclosureDay(date)" not in content
    assert "scanDisclosureDay(date)" not in content
    assert "disclosureDayBundle(date)" not in content
    assert "sendFeishuDisclosureDay(date)" in content
    assert "pollRss()" in content
    assert "/api/analyze/company" in content
    assert "/api/disclosure-day/jobs" in content
    assert "/api/notify/feishu/disclosure-day/" in content
    assert "/api/rss/poll" in content
    assert "if (!response.ok)" in content
    assert "catch (error)" in content


def test_frontend_has_minimal_real_data_controls():
    content = Path("web/index.html").read_text(encoding="utf-8")

    assert "company-ts-code" in content
    assert "company-period" in content
    assert "analyze-company" in content
    assert "disclosure-date" in content
    # 两个重复的扫描入口已合并为一个
    assert "start-disclosure-scan" in content
    assert "send-feishu" in content
    # RSS 与操作日志移入开发者折叠区，未删除
    assert "poll-rss" in content
    assert "operation-status" in content
