import json
import subprocess
from pathlib import Path
from uuid import UUID, uuid4

import psycopg

from . import db, harness
from .agent import AgentInput, classify, prompt_sha256
from .config import (DATASET_VERSION, EVALUATOR_VERSION, FACT_VERSION, MAX_OUTPUT_TOKENS, MAX_TURNS, ROOT,
                     settings)
from .data import Answer, load_answers, verify_hashes
from .errors import AgentError


def git_state() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    try:
        return {"git_revision": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return {"git_revision": None, "git_dirty": None}


def run_config(version: str, split: str, provider, hashes: dict, answer_ids: list[str]) -> dict:
    return {"split": split, "agent_version": version, "prompt_sha256": prompt_sha256(version),
            "dataset_version": DATASET_VERSION, "fact_version": FACT_VERSION,
            "evaluator_version": EVALUATOR_VERSION, "provider": type(provider).__name__,
            "model": settings.openai_model, "temperature": 0, "seed": settings.openai_seed,
            "timeout_s": settings.request_timeout_s, "max_turns": MAX_TURNS, "max_tokens": MAX_OUTPUT_TOKENS,
            "file_hashes": hashes, "answer_ids": answer_ids, **git_state()}


def run_answer(answer: Answer, version: str, provider) -> tuple[dict, dict | None]:
    outcome = {"answer_id": answer.answer_id, "status": "ok", "error_type": None, "error_message": None}
    try:
        result = classify(AgentInput(answer.answer_id, answer.brand_id, answer.question, answer.ai_answer),
                          version, provider)
        return {**outcome, "claims": result.claims, "latency_ms": result.latency_ms}, result.exchange
    except AgentError as e:
        outcome |= {"status": "error", "error_type": e.kind, "error_message": e.message}
        return {**outcome, "claims": [], "latency_ms": e.exchange and e.exchange["latency_ms"]}, e.exchange


def run_split(version: str, split: str, provider, answer_ids: list[str] | None = None,
              out_dir: Path | None = None, run_id: UUID | None = None) -> str:
    hashes = verify_hashes()
    answers = sorted((a for a in load_answers().values()
                      if a.split == split and (answer_ids is None or a.answer_id in answer_ids)),
                     key=lambda a: a.answer_id)
    ids = [a.answer_id for a in answers]
    run_id = run_id or uuid4()
    trace = out_dir / "exchanges.jsonl" if out_dir else None
    if trace:
        out_dir.mkdir(parents=True, exist_ok=True)
        trace.write_text("", encoding="utf-8")
    with db.connect() as conn:
        db.apply_schema(conn)
        db.create_run(conn, run_id, split, version, run_config(version, split, provider, hashes, ids))
        try:
            outcomes = []
            for position, answer in enumerate(answers, 1):
                outcome, exchange = run_answer(answer, version, provider)
                db.save_answer(conn, run_id, position, outcome, trace and f"exchanges.jsonl#{answer.answer_id}")
                if trace:
                    line = {"answer_id": answer.answer_id, "status": outcome["status"],
                            "error_type": outcome["error_type"], "exchange": exchange}
                    with trace.open("a", encoding="utf-8", newline="\n") as f:
                        f.write(json.dumps(line, ensure_ascii=False) + "\n")
                outcomes.append(outcome)
            result = harness.score(split, ids, outcomes, {a.answer_id: a for a in answers})
            db.set_matches(conn, run_id, result["matches"])
            db.finish_run(conn, run_id, result["counts"], result["metrics"])
            if out_dir:
                harness.write_reports(out_dir, db.get_run(conn, run_id), result["diagnostics"])
        except Exception as e:
            try:
                db.fail_run(conn, run_id, type(e).__name__)
            except psycopg.Error:
                pass
            raise
    return str(run_id)
