STATUS = {
    "unknown_brand": 404,
    "provider_error": 502,
    "timeout": 504,
    "invalid_output": 502,
    "illegal_tool": 502,
    "unknown_requested_brand": 502,
    "turn_limit": 502,
}


class AgentError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        assert kind in STATUS, kind
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.exchange: dict | None = None
