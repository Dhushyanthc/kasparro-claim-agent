import re

from .errors import AgentError

STATUSES = ("established", "refuted", "not_in_facts")


def derive_label(parts: list[dict]) -> str:
    statuses = {p["status"] for p in parts}
    if "refuted" in statuses:
        return "contradicted"
    if "not_in_facts" in statuses:
        return "unknown"
    return "supported"


def invalid(message: str) -> AgentError:
    return AgentError("invalid_output", message)


def locate(quote: str, occurrence: int, ai_answer: str) -> tuple[int, int]:
    starts, i = [], ai_answer.find(quote)
    while i != -1:
        starts.append(i)
        i = ai_answer.find(quote, i + len(quote))
    if not starts:
        raise invalid("quote not found in answer")
    if not 1 <= occurrence <= len(starts):
        raise invalid("occurrence out of range")
    start = starts[occurrence - 1]
    return start, start + len(quote)


def check_parts(parts: object, retrieved: set[str]) -> list[dict]:
    if not isinstance(parts, list) or not parts:
        raise invalid("parts must be a non-empty list")
    for p in parts:
        if p["status"] not in STATUSES:
            raise invalid("unknown part status")
        if p["status"] != "not_in_facts" and not p["fact_ids"]:
            raise invalid("decided part cites no fact")
        if not set(p["fact_ids"]) <= retrieved:
            raise invalid("part cites a fact that was not retrieved")
    return parts


def build_claim(raw: dict, ai_answer: str, answer_id: str, retrieved: set[str]) -> dict:
    parts = check_parts(raw["parts"], retrieved)
    reason = raw["reason"]
    if not isinstance(reason, str) or not reason.strip():
        raise invalid("reason must not be empty")
    if len(re.split(r"(?<=[.!?])\s+", reason.strip())) > 2:
        raise invalid("reason must be at most two sentences")
    quote, occurrence = raw["quote"].strip(), raw["occurrence"]
    if not quote or not isinstance(occurrence, int) or isinstance(occurrence, bool):
        raise invalid("bad quote or occurrence")
    start, end = locate(quote, occurrence, ai_answer)
    return {"claim_id": f"{answer_id}:{start}:{end}", "start_char": start, "end_char": end,
            "quote": quote, "label": derive_label(parts),
            "fact_ids": sorted({f for p in parts for f in p["fact_ids"]}),
            "reason": reason, "parts": parts}


def finalize(raw_claims: object, ai_answer: str, answer_id: str, retrieved: set[str]) -> list[dict]:
    if not isinstance(raw_claims, list):
        raise invalid("claims must be a list")
    try:
        claims = [build_claim(raw, ai_answer, answer_id, retrieved) for raw in raw_claims]
    except (KeyError, TypeError, AttributeError):
        raise invalid("claim does not match the output schema") from None
    if len({c["claim_id"] for c in claims}) != len(claims):
        raise invalid("duplicate claim")
    claims.sort(key=lambda c: c["start_char"])
    if any(a["end_char"] > b["start_char"] for a, b in zip(claims, claims[1:])):
        raise invalid("overlapping claims")
    return claims
