from pathlib import Path


def test_frontend_defines_api_wrapper_methods():
    content = Path("web/app.js").read_text(encoding="utf-8")

    assert "analyzeCompany(tsCode, period)" in content
    assert "analyzeDisclosureDay(date)" in content
    assert "sendFeishuDisclosureDay(date)" in content
    assert "pollRss()" in content
    assert "/api/analyze/company" in content
    assert "/api/analyze/disclosure-day" in content
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
    assert "analyze-disclosure-day" in content
    assert "send-feishu" in content
    assert "poll-rss" in content
    assert "operation-status" in content
