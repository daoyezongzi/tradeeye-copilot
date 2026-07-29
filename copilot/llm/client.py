from pydantic import BaseModel
import httpx


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_seconds: int = 60,
        http_client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)

    def chat(self, messages: list[ChatMessage], temperature: float = 0.2) -> str | None:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [message.model_dump() for message in messages],
            "temperature": temperature,
        }
        try:
            response = self.http_client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        data = response.json()
        return data["choices"][0]["message"]["content"]
