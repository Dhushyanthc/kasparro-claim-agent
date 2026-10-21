import hashlib
import json
import re
import secrets
import time
from dataclasses import dataclass
from functools import cache

from . import spans
from .config import FACT_VERSION, MAX_OUTPUT_TOKENS, MAX_TURNS, PROMPTS_DIR, settings
from .data import Fact, load_facts
from .errors import AgentError

TOOL_NAME = "get_brand_facts"
TOOL = {"type": "function", "function": {
    "name": TOOL_NAME, "strict": True,
    "description": "Read-only catalogue lookup. Returns every fact row for one brand "
                   f"(fact_version {FACT_VERSION}). Valid brand_id values: "
                   "cleartrail, stonewave, cloudnote. Never call it for any other brand.",
    "parameters": {"type": "object", "additionalProperties": False, "required": ["brand_id"],
                   "properties": {"brand_id": {"type": "string",
                                  "description": "One of: cleartrail, stonewave, cloudnote."}}}}}
TOOL_CHOICE = {1: "required", 2: "auto", 3: "none"}
PLACEHOLDER = re.compile(r"\{(brand_id|nonce|question|ai_answer)\}")


@dataclass(frozen=True)
class AgentInput:
    answer_id: str
    brand_id: str
    question: str
    ai_answer: str


@dataclass(frozen=True)
class AgentResult:
    claims: list[dict]
    exchange: dict
    latency_ms: int


def fact_row(f: Fact) -> dict:
    return {"fact_id": f.fact_id, "model_id": f.model_id, "field": f.field, "value": f.value,
            "unit": f.unit, "condition": f.condition,
            "valid_from": f.valid_from.isoformat(), "valid_to": f.valid_to.isoformat()}


def execute_tool(name: str, raw_args: str) -> tuple[str, str]:
    if name != TOOL_NAME:
        raise AgentError("illegal_tool", "model called a tool that is not available")
    try:
        args = json.loads(raw_args)
    except (TypeError, ValueError):
        raise AgentError("invalid_output", "tool arguments are not valid JSON") from None
    if not isinstance(args, dict) or set(args) != {"brand_id"} or not isinstance(args["brand_id"], str):
        raise AgentError("invalid_output", "tool arguments do not match the schema")
    brand_id = args["brand_id"]
    facts = load_facts()
    if brand_id not in facts:
        raise AgentError("unknown_requested_brand", "model requested a brand that is not in the catalogue")
    payload = {"brand_id": brand_id, "fact_version": FACT_VERSION,
               "facts": [fact_row(f) for f in facts[brand_id]]}
    return brand_id, json.dumps(payload, separators=(",", ":"))


def output_schema(fact_ids: list[str]) -> dict:
    part = {"type": "object", "additionalProperties": False,
            "required": ["assertion", "status", "fact_ids"],
            "properties": {"assertion": {"type": "string"},
                           "status": {"type": "string", "enum": ["established", "refuted", "not_in_facts"]},
                           "fact_ids": {"type": "array", "items": {"type": "string", "enum": fact_ids}}}}
    claim = {"type": "object", "additionalProperties": False,
             "required": ["quote", "occurrence", "parts", "reason"],
             "properties": {"quote": {"type": "string"}, "occurrence": {"type": "integer"},
                            "parts": {"type": "array", "items": part}, "reason": {"type": "string"}}}
    return {"type": "json_schema", "json_schema": {"name": "claim_extraction", "strict": True,
            "schema": {"type": "object", "additionalProperties": False, "required": ["claims"],
                       "properties": {"claims": {"type": "array", "items": claim}}}}}


@cache
def response_format() -> dict:
    return output_schema([f.fact_id for rows in load_facts().values() for f in rows])


@cache
def load_prompts(version: str) -> tuple[str, str]:
    system, user = ((PROMPTS_DIR / version / name).read_bytes() for name in ("system.md", "user.md"))
    return system.decode("utf-8"), user.decode("utf-8")


def prompt_sha256(version: str) -> str:
    digest = hashlib.sha256()
    for part in (*load_prompts(version), json.dumps(TOOL, sort_keys=True),
                 json.dumps(response_format(), sort_keys=True)):
        digest.update(part.encode("utf-8"))
    return digest.hexdigest()


def build_messages(version: str, answer: AgentInput) -> list[dict]:
    system, template = load_prompts(version)
    nonce = secrets.token_hex(6)
    while nonce in answer.question or nonce in answer.ai_answer:
        nonce = secrets.token_hex(6)
    values = {"brand_id": answer.brand_id, "nonce": nonce,
              "question": answer.question, "ai_answer": answer.ai_answer}
    user = PLACEHOLDER.sub(lambda m: values[m.group(1)], template)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run_turns(answer: AgentInput, version: str, provider, exchange: dict) -> list[dict]:
    messages = exchange["messages"] = build_messages(version, answer)
    retrieved: set[str] = set()
    for turn in range(1, MAX_TURNS + 1):
        response = provider.complete({
            "model": settings.openai_model, "messages": messages, "tools": [TOOL],
            "tool_choice": TOOL_CHOICE[turn], "parallel_tool_calls": False,
            "response_format": response_format(), "temperature": 0, "seed": settings.openai_seed,
            "max_completion_tokens": MAX_OUTPUT_TOKENS})
        if response.usage:
            exchange["usage"].append({"prompt_tokens": response.usage.prompt_tokens,
                                      "completion_tokens": response.usage.completion_tokens})
        choice = response.choices[0]
        message = choice.message
        if message.refusal:
            raise AgentError("provider_error", "model refused the request")
        if message.tool_calls:
            messages.append({"role": "assistant", "content": message.content, "tool_calls": [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in message.tool_calls]})
            for call in message.tool_calls:
                brand_id, payload = execute_tool(call.function.name, call.function.arguments)
                retrieved |= {f.fact_id for f in load_facts()[brand_id]}
                messages.append({"role": "tool", "tool_call_id": call.id, "content": payload})
            continue
        if choice.finish_reason == "length":
            raise AgentError("invalid_output", "model output was truncated")
        if not retrieved:
            raise AgentError("invalid_output", "model answered without retrieving facts")
        exchange["final_content"] = message.content
        try:
            raw = json.loads(message.content)
            raw_claims = raw["claims"] if isinstance(raw, dict) and set(raw) == {"claims"} else None
        except (TypeError, ValueError):
            raw_claims = None
        if raw_claims is None:
            raise AgentError("invalid_output", "model output is not the expected JSON object")
        return spans.finalize(raw_claims, answer.ai_answer, answer.answer_id, retrieved)
    raise AgentError("turn_limit", "no final answer after the turn limit")


def classify(answer: AgentInput, version: str, provider) -> AgentResult:
    if answer.brand_id not in load_facts():
        raise AgentError("unknown_brand", "brand is not in the catalogue")
    exchange: dict = {"messages": [], "usage": [], "final_content": None}
    started = time.perf_counter()
    try:
        claims = run_turns(answer, version, provider, exchange)
    except AgentError as e:
        e.exchange = exchange
        raise
    finally:
        exchange["latency_ms"] = round((time.perf_counter() - started) * 1000)
    return AgentResult(claims, exchange, exchange["latency_ms"])
