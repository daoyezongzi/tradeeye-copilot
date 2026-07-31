from copilot.service.notify_store import NotifyLogStore


def test_notify_log_store_tracks_successful_send(tmp_path):
    store = NotifyLogStore(tmp_path / "notify.sqlite")
    store.init_schema()

    assert store.already_sent("feishu_disclosure_day", "20250825") is False

    first = store.record_attempt("feishu_disclosure_day", "20250825", sent=True, reason="ok")
    second = store.record_attempt("feishu_disclosure_day", "20250825", sent=False, reason="send_failed")

    assert first.sent is True
    assert second.sent is False
    assert store.already_sent("feishu_disclosure_day", "20250825") is True
    assert [event.reason for event in store.list_recent(limit=2)] == ["send_failed", "ok"]
