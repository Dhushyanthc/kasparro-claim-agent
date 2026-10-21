# Kasparro Claim Agent

## What this is
A Python agent that extracts factual claim sentences from one long AI answer about speaker products and labels each `supported`, `contradicted` or `unknown` using only the supplied catalogue.
Around it: a deterministic evaluation harness, a v1 baseline and a v2 candidate (one change apart), a thin FastAPI service on PostgreSQL, and fake-provider tests.
Full instructions are in EXECUTION.md; when it and anything else disagree, EXECUTION.md wins.

## Rules (never break)
- Never pre-fetch facts in Python or paste them into the prompt; the model requests `get_brand_facts` itself.
- No tool other than `get_brand_facts`.
- Never send answer_id, gold spans, labels, explanations, difficulty tags or scores to the model or the tool.
- No inference module imports `gold.py`.
- No LLM judge, fuzzy matching or text normalization in scoring.
- Never strip, normalize, re-encode or re-save `ai_answer` or the CSV files.
- Never turn an error into `unknown`, drop one bad claim and keep the rest, or add repair turns.
- No provider retries (`max_retries=0`).
- Do not tune prompts on A41 to A50; do not read check answers while designing prompts.
- Never hardcode labels or infer them from answer IDs or positions.
- No React, Langfuse, concurrency, ORM, Alembic, Celery or extra services.
- Do not change pinned dependency versions.
- Never commit `.env`, keys or raw provider headers; never print the API key.
- At most 4 commits; no amend or force-push after pushing.
- Never invent or edit run outputs; every reported number comes from a real run.
- Parameterized SQL only (`%s` with psycopg).

## Commands
make db | make test | make run V=v1 S=development | make compare A=<run_id> B=<run_id> | make api

## Architecture map
- config.py: settings, versions, constants, paths
- data.py: CSV loading, typed facts, hash check
- gold.py: gold loader (harness and tests only)
- errors.py: AgentError and the kind to HTTP status table
- agent.py: tool schema and executor (prompt build and 3-turn loop arrive in commit 2)

## Versions in use
- agent: v1 (prompts not yet written; prompt sha256 per version is recorded from commit 2)
- dataset long-brand-answers-50-v4, facts speaker-catalogue-v4, evaluator sentence-spans-and-labels-v4
- model: set in `.env` (OPENAI_MODEL), timeout 60 s

## Change log
- commit 1: project set up with uv, Docker Postgres 16 and Makefile; CSVs loaded with SHA-256 checks; `get_brand_facts` tool and executor with tests.

## Decisions
- 2026-10-21: docker-compose host port is `${DB_PORT:-5432}`. On the dev machine 5432 is taken by a local PostgreSQL 18 and another project's container, so the local `.env` sets DB_PORT=5433 and DATABASE_URL to match. `.env.example` keeps the 5432 default.
- 2026-10-21: the remote already held an "Initial commit" with a stub README; the 4 project commits sit on top of it. The stub README is replaced in commit 4.
- 2026-10-21: on Windows `make` comes from msys64 (`C:\msys64\usr\bin`) and uv from `pip install --user uv` (0.11.33), so both need to be on PATH.
- 2026-10-21: gold list columns (`evidence_fact_ids`, `difficulty_tags`) are `|`-separated; blank evidence means no evidence (the unknown claims).
- 2026-10-21: tool tests live in tests/test_agent.py from commit 1 (the tool executor is in agent.py).
- 2026-10-21: `.gitattributes` keeps `data/*` and `*.csv` byte-exact (`-text`) and stores everything else as LF, because the dev machine has core.autocrlf on and conversion would break the SHA-256 check and the Makefile on a fresh clone.
