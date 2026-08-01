from copilot.agent.store import AgentMessage, AgentSession, SQLiteAgentStore


def make_store(tmp_path):
    store = SQLiteAgentStore(tmp_path / "agent.sqlite")
    store.init_schema()
    return store


def test_create_or_get_session_reuses_same_card(tmp_path):
    store = make_store(tmp_path)

    first = store.create_or_get_session("000001.SZ", "20250630")
    second = store.create_or_get_session("000001.SZ", "20250630")
    other = store.create_or_get_session("000002.SZ", "20250630")

    assert first.session_id == second.session_id
    assert first.session_id != other.session_id
    assert first.ts_code == "000001.SZ"
    assert first.period == "20250630"


def test_get_session_returns_none_for_unknown(tmp_path):
    store = make_store(tmp_path)
    assert store.get_session("missing") is None


def test_append_and_list_messages_keeps_recent_rounds(tmp_path):
    store = make_store(tmp_path)
    session = store.create_or_get_session("000001.SZ", "20250630")

    for i in range(15):
        store.append_message(session.session_id, "user", f"q{i}")
        store.append_message(session.session_id, "assistant", f"a{i}", references=[{"fact_id": "revenue"}])

    recent = store.list_recent_messages(session.session_id, rounds=10)

    assert len(recent) == 20
    assert recent[0].role == "user"
    assert recent[0].content == "q5"
    assert recent[-1].content == "a14"
    assert recent[-1].references == [{"fact_id": "revenue"}]
