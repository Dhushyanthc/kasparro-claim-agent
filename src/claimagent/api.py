import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import agent, db, runner
from .errors import STATUS, AgentError
from .provider import OpenAIProvider

log = logging.getLogger("claimagent")


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClassifyRequest(StrictRequest):
    answer_id: str = Field(min_length=1, max_length=64)
    brand_id: str = Field(min_length=1, max_length=64)
    question: str = Field(max_length=4000)
    ai_answer: str = Field(min_length=1, max_length=20000)
    agent_version: Literal["v1", "v2"]


class RunRequest(StrictRequest):
    agent_version: Literal["v1", "v2"]
    split: Literal["development", "check"]


class ClaimOut(BaseModel):
    claim_id: str
    start_char: int
    end_char: int
    quote: str
    label: Literal["supported", "contradicted", "unknown"]
    fact_ids: list[str]
    reason: str
    parts: list[dict[str, Any]]


class ClassifyOut(BaseModel):
    answer_id: str
    agent_version: str
    claims: list[ClaimOut]


class RunCreated(BaseModel):
    run_id: str
    status: str
    counts: dict[str, Any] | None
    metrics: dict[str, Any] | None


class StoredClaim(ClaimOut):
    match: dict[str, Any] | None


class AnswerOut(BaseModel):
    answer_id: str
    position: int
    status: str
    error_type: str | None
    error_message: str | None
    claim_count: int
    latency_ms: int | None
    trace_ref: str | None
    claims: list[StoredClaim]


class RunOut(RunCreated):
    split: str
    agent_version: str
    config: dict[str, Any]
    error: str | None
    created_at: datetime
    finished_at: datetime | None
    answers: list[AnswerOut]


class ApiError(Exception):
    def __init__(self, status: int, type_: str, message: str, **extra: str) -> None:
        self.status, self.type, self.message, self.extra = status, type_, message, extra


def error_response(status: int, type_: str, message: str, **extra: str) -> JSONResponse:
    return JSONResponse({"error": {"type": type_, "message": message, **extra}}, status_code=status)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.provider = OpenAIProvider()
    try:
        with db.connect() as conn:
            db.apply_schema(conn)
    except psycopg.OperationalError:
        log.warning("database unavailable at startup; schema not applied")
    yield


app = FastAPI(title="Kasparro Claim Agent", lifespan=lifespan)


def get_provider(request: Request) -> Any:
    return request.app.state.provider


@app.exception_handler(RequestValidationError)
async def on_validation(_: Request, __: RequestValidationError) -> JSONResponse:
    return error_response(422, "validation_error", "request validation failed")


@app.exception_handler(AgentError)
async def on_agent_error(_: Request, e: AgentError) -> JSONResponse:
    return error_response(STATUS[e.kind], e.kind, e.message)


@app.exception_handler(ApiError)
async def on_api_error(_: Request, e: ApiError) -> JSONResponse:
    return error_response(e.status, e.type, e.message, **e.extra)


@app.exception_handler(psycopg.OperationalError)
async def on_database(_: Request, __: psycopg.OperationalError) -> JSONResponse:
    return error_response(503, "database_unavailable", "database is unavailable")


@app.exception_handler(Exception)
async def on_unexpected(_: Request, e: Exception) -> JSONResponse:
    log.error("unhandled error", exc_info=e)
    return error_response(500, "internal_error", "internal server error")


@app.post("/classify", response_model=ClassifyOut)
def classify(body: ClassifyRequest, provider: Any = Depends(get_provider)) -> dict:
    answer = agent.AgentInput(body.answer_id, body.brand_id, body.question, body.ai_answer)
    result = agent.classify(answer, body.agent_version, provider)
    return {"answer_id": body.answer_id, "agent_version": body.agent_version, "claims": result.claims}


@app.post("/evaluation-runs", status_code=201, response_model=RunCreated)
def create_evaluation_run(body: RunRequest, provider: Any = Depends(get_provider)) -> dict:
    run_id = uuid4()
    try:
        runner.run_split(body.agent_version, body.split, provider, run_id=run_id)
    except psycopg.OperationalError:
        raise
    except Exception as e:
        log.error("run failed", exc_info=e)
        raise ApiError(500, "run_failed", "the run failed part way", run_id=str(run_id)) from None
    with db.connect() as conn:
        return db.get_run(conn, run_id)


@app.get("/evaluation-runs/{run_id}", response_model=RunOut)
def read_evaluation_run(run_id: UUID) -> dict:
    with db.connect() as conn:
        run = db.get_run(conn, run_id)
    if run is None:
        raise ApiError(404, "not_found", "run not found")
    return run
