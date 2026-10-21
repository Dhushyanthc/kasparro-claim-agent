import copy

from openai import APIError, APITimeoutError, OpenAI
from openai.types.chat import ChatCompletion

from .config import settings
from .errors import AgentError


class OpenAIProvider:
    def __init__(self, client: OpenAI | None = None) -> None:
        if client is None:
            key = settings.openai_api_key
            if key is None or not key.get_secret_value():
                raise RuntimeError("OPENAI_API_KEY is not set")
            client = OpenAI(api_key=key.get_secret_value(), timeout=settings.request_timeout_s, max_retries=0)
        self.client = client

    def complete(self, request: dict) -> ChatCompletion:
        try:
            return self.client.chat.completions.create(**request)
        except APITimeoutError:
            raise AgentError("timeout", "provider request timed out") from None
        except APIError:
            raise AgentError("provider_error", "provider request failed") from None


class FakeProvider:
    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.requests: list[dict] = []

    def complete(self, request: dict) -> ChatCompletion:
        self.requests.append(copy.deepcopy(request))
        assert self.script, "FakeProvider script exhausted"
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
