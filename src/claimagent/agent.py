import json

from .config import FACT_VERSION
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
