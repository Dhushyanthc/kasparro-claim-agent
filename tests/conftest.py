import json

import pytest
from openai.types.chat import ChatCompletion

from claimagent.data import load_answers, load_facts


@pytest.fixture(scope="session")
def answers():
    return load_answers()


@pytest.fixture(scope="session")
def facts():
    return load_facts()


def completion(content=None, tool_calls=None, refusal=None, finish_reason="stop") -> ChatCompletion:
    message = {"role": "assistant", "content": content, "refusal": refusal}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return ChatCompletion.model_validate({
        "id": "c", "object": "chat.completion", "created": 0, "model": "fake",
        "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})


def tool_turn(brand="cleartrail", name="get_brand_facts", arguments=None, call_id="call_1") -> ChatCompletion:
    args = json.dumps({"brand_id": brand}) if arguments is None else arguments
    call = {"id": call_id, "type": "function", "function": {"name": name, "arguments": args}}
    return completion(tool_calls=[call], finish_reason="tool_calls")


def final_turn(claims: list) -> ChatCompletion:
    return completion(content=json.dumps({"claims": claims}))


def part(status: str, fact_ids=(), assertion="assertion") -> dict:
    return {"assertion": assertion, "status": status, "fact_ids": list(fact_ids)}


def claim(quote: str, parts: list, occurrence: int = 1, reason: str = "Checked against the catalogue.") -> dict:
    return {"quote": quote, "occurrence": occurrence, "parts": parts, "reason": reason}
