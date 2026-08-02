from pathlib import Path


def test_rss_feishu_reminder_workflow_runs_without_server():
    workflow = Path(".github/workflows/rss-feishu-reminder.yml").read_text(encoding="utf-8")
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "FEISHU_WEBHOOK" in workflow
    assert "TUSHARE_TOKEN" in workflow
    assert "RSS_FEEDS" in workflow
    assert "python -m copilot.rss.github_action" in workflow
    assert "TRADEEYE_API_BASE_URL" not in workflow
