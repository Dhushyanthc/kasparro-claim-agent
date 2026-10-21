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
- provider.py: OpenAIProvider (no retries, errors mapped to AgentError) and FakeProvider (scripted, records requests)
- db.py + schema.sql: psycopg connection, run/answer/claim persistence (parameterized SQL, one transaction per answer)
- harness.py: deterministic scorer, diagnostics, compare, report writers (only module besides tests that loads gold)
- runner.py: run orchestrator (sequential, errors become answer rows, infrastructure failures fail the run)
- api.py: FastAPI routes /classify, /evaluation-runs; one error shape
- scripts/run_eval.py: CLI for runs and compare
- agent.py: tool schema and executor, output schema, prompt build (single regex pass), 3-turn loop, prompt sha256
- spans.py: Python-side quote location, claim validation, label derivation, overlap checks
- prompts/<version>/: system.md and user.md per agent version

## Versions in use
- agent v1 (frozen at tag v1-frozen): prompt sha256 0a09474cf5a361533e24972fbd44bde543298ebb190e6e5f839774429ee29ec0
- agent v2 (frozen at tag v2-frozen): prompt sha256 fd4c9d66cf612285db8e23f2eb1605757740f8fa74a9175fdfe4ff7e732acc17; differs from v1 by the single `occurrence` line in system.md
- runs (all gpt-4.1-mini): dev v1 a557da1a-c6f9-4ee8-9fef-67375139cfdc, dev v2 e5b844a9-7dcd-4e18-856e-9d598e04d132, check v1 35d050e7-28d5-4f27-b7a6-105a0d727a46, check v2 7a788ce5-f0d7-4ea4-b691-35c82980b411
- dataset long-brand-answers-50-v4, facts speaker-catalogue-v4, evaluator sentence-spans-and-labels-v4
- model: gpt-4.1 (OPENAI_MODEL in `.env`), temperature 0, seed 7, timeout 60 s, max 3 turns, 8192 output tokens

## Change log
- commit 1: project set up with uv, Docker Postgres 16 and Makefile; CSVs loaded with SHA-256 checks; `get_brand_facts` tool and executor with tests.
- commit 2: v1 prompts, OpenAI/Fake providers, 3-turn tool-calling loop, span location and claim validation in Python, labels derived from part statuses; 82 fake-provider tests including the gold-leak and injection checks.
- commit 3: schema and db layer, deterministic scorer with diagnostics and compare, run orchestrator, FastAPI routes, CLI; 135 tests. Smoke check on A01 and A02 (scratch run, not one of the four) with gpt-4.1: both answers ok, 19 claims stored, tool call and exchanges verified. v1 frozen (tag v1-frozen).
- commit 4: v2 prompt (one line: `occurrence`), four live runs, comparison report, README, 138 tests. Dev joint F1 v1 0.9060 -> v2 0.9566, answer errors 4 -> 1; check runs 10/10 ok each, quality metrics null.

## Decisions
- 2026-10-21: docker-compose host port is `${DB_PORT:-5432}`. On the dev machine 5432 is taken by a local PostgreSQL 18 and another project's container, so the local `.env` sets DB_PORT=5433 and DATABASE_URL to match. `.env.example` keeps the 5432 default.
- 2026-10-21: the remote already held an "Initial commit" with a stub README; the 4 project commits sit on top of it. The stub README is replaced in commit 4.
- 2026-10-21: on Windows `make` comes from msys64 (`C:\msys64\usr\bin`) and uv from `pip install --user uv` (0.11.33), so both need to be on PATH.
- 2026-10-21: gold list columns (`evidence_fact_ids`, `difficulty_tags`) are `|`-separated; blank evidence means no evidence (the unknown claims).
- 2026-10-21: tool tests live in tests/test_agent.py from commit 1 (the tool executor is in agent.py).
- 2026-10-21: `.gitattributes` keeps `data/*` and `*.csv` byte-exact (`-text`) and stores everything else as LF, because the dev machine has core.autocrlf on and conversion would break the SHA-256 check and the Makefile on a fresh clone.
- 2026-10-21: repeated-quote occurrences are counted without overlap (the next search starts after the previous hit).
- 2026-10-21: `AgentError` carries the partial `exchange` (messages, usage, final content, latency) so errored answers still get a trace; `classify` attaches it.
- 2026-10-21: test builders for fake completions live in tests/conftest.py and are imported with `from conftest import ...`.
- 2026-10-21: `run_split` takes optional `answer_ids`, `out_dir` and `run_id` so the smoke check can cover two answers, API runs and tests never write into `reports/`, and the API can name a failed run.
- 2026-10-21: compare also requires identical `answer_ids` and a completed development run on both sides.
- 2026-10-21: smoke check with gpt-5-nano was not run (reasoning model, may reject temperature 0). The smoke check with gpt-4.1-nano ran on A01 and A02 and both answers failed validation (a refuted part with no fact id; a duplicated claim): model slips, not code bugs, and no prompt change was made. Switched to gpt-4.1, which passed on the same two answers. A01 and A02 were used for the smoke check only.
- 2026-10-21: `agent_version` v2 is accepted by the API but prompts/v2 does not exist until stage 4, so it returns 500 until then.
- 2026-10-21: v2 change chosen from the v1 dev diagnosis: 3 of 4 answer errors were `occurrence` set to the running claim number, so the prompt line was fixed (table row: many invalid_output errors from one cause). The fourth error (reason over two sentences, A03) was left to keep one change.
- 2026-10-21: all four official runs use gpt-4.1-mini. gpt-6-luna was tried on A01/A02 only and rejected function tools without reasoning_effort=none on Chat Completions; dropped, no code changed. Scratch runs for the smoke checks (gpt-4.1-nano, gpt-4.1, gpt-6-luna) are in the database only.
- 2026-10-21: optional noise-floor repeat of the v1 dev run was not run; the 6 v1 to v2 regressions cannot be attributed to the prompt or to noise.
- 2026-10-21: the v1 dev run reports git_dirty=true although it ran right after commit 3; cause not found.
- 2026-10-21: README times and the AI assistance section are left for the human to write.
