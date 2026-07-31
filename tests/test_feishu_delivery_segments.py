from copilot.notify.feishu import split_feishu_text


def test_split_feishu_text_keeps_short_message_single_part():
    assert split_feishu_text("short", max_chars=20) == ["short"]


def test_split_feishu_text_splits_on_line_boundaries_with_part_headers():
    text = "title\n" + "\n".join(f"line-{index}" for index in range(1, 8))

    parts = split_feishu_text(text, max_chars=40)

    assert len(parts) > 1
    assert all(len(part) <= 40 for part in parts)
    assert parts[0].startswith("[1/")
    assert "line-1" in parts[0]
    assert "line-7" in parts[-1]


from copilot.notify.feishu import FeishuNotifier


class FakeHttpClient:
    def __init__(self):
        self.payloads = []

    def post(self, url, json):
        self.payloads.append(json)
        return FakeResponse()


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"StatusCode": 0}


def test_send_text_parts_sends_every_part():
    client = FakeHttpClient()
    notifier = FeishuNotifier("https://example.test/webhook", http_client=client)

    sent = notifier.send_text_parts(["one", "two"])

    assert sent is True
    assert [payload["content"]["text"] for payload in client.payloads] == ["one", "two"]
