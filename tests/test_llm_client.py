import httpx

from copilot.llm.client import ChatMessage, LLMClient


def test_llm_client_posts_openai_compatible_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["json"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "归因文本"}}]},
        )

    client = LLMClient(
        base_url="https://maas.example.com/v1",
        model="ascend-model",
        api_key="secret-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.chat([ChatMessage(role="user", content="解释变化")])

    assert captured["url"] == "https://maas.example.com/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret-key"
    assert '"model":"ascend-model"' in captured["json"].replace(" ", "")
    assert result == "归因文本"


def test_llm_client_returns_none_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = LLMClient(
        base_url="https://maas.example.com/v1",
        model="ascend-model",
        api_key="secret-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert client.chat([ChatMessage(role="user", content="解释变化")]) is None
