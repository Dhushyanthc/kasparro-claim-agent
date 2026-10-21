from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import settings

SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, connect_timeout=5, autocommit=True,
                           row_factory=dict_row, options="-c statement_timeout=10000")


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA.read_text(encoding="utf-8"))


def create_run(conn: psycopg.Connection, run_id: UUID, split: str, version: str, config: dict) -> None:
    conn.execute("INSERT INTO runs (run_id, split, agent_version, status, config) VALUES (%s, %s, %s, 'running', %s)",
                 (run_id, split, version, Jsonb(config)))


def save_answer(conn: psycopg.Connection, run_id: UUID, position: int, outcome: dict,
                trace_ref: str | None) -> None:
    claims = outcome["claims"]
    with conn.transaction():
        conn.execute(
            "INSERT INTO answer_results (run_id, answer_id, position, status, error_type, error_message,"
            " claim_count, latency_ms, trace_ref) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (run_id, outcome["answer_id"], position, outcome["status"], outcome["error_type"],
             outcome["error_message"], len(claims), outcome["latency_ms"], trace_ref))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO claim_results (run_id, answer_id, claim_id, start_char, end_char, quote, label,"
                " fact_ids, reason, parts) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [(run_id, outcome["answer_id"], c["claim_id"], c["start_char"], c["end_char"], c["quote"],
                  c["label"], c["fact_ids"], c["reason"], Jsonb(c["parts"])) for c in claims])


def set_matches(conn: psycopg.Connection, run_id: UUID, matches: dict[str, dict]) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany("UPDATE claim_results SET match = %s WHERE run_id = %s AND claim_id = %s",
                        [(Jsonb(m), run_id, claim_id) for claim_id, m in matches.items()])


def finish_run(conn: psycopg.Connection, run_id: UUID, counts: dict, metrics: dict | None) -> None:
    conn.execute("UPDATE runs SET status = 'completed', counts = %s, metrics = %s, finished_at = now()"
                 " WHERE run_id = %s", (Jsonb(counts), Jsonb(metrics) if metrics else None, run_id))


def fail_run(conn: psycopg.Connection, run_id: UUID, error: str) -> None:
    conn.execute("UPDATE runs SET status = 'failed', error = %s, finished_at = now() WHERE run_id = %s",
                 (error, run_id))


def get_run(conn: psycopg.Connection, run_id: UUID) -> dict | None:
    run = conn.execute(
        "SELECT run_id::text AS run_id, split, agent_version, status, config, counts, metrics, error,"
        " created_at, finished_at FROM runs WHERE run_id = %s", (run_id,)).fetchone()
    if run is None:
        return None
    answers = conn.execute(
        "SELECT answer_id, position, status, error_type, error_message, claim_count, latency_ms, trace_ref"
        " FROM answer_results WHERE run_id = %s ORDER BY position", (run_id,)).fetchall()
    claims = conn.execute(
        "SELECT answer_id, claim_id, start_char, end_char, quote, label, fact_ids, reason, parts, match"
        " FROM claim_results WHERE run_id = %s ORDER BY answer_id, start_char", (run_id,)).fetchall()
    for a in answers:
        a["claims"] = [{k: v for k, v in c.items() if k != "answer_id"}
                       for c in claims if c["answer_id"] == a["answer_id"]]
    return {**run, "answers": answers}
