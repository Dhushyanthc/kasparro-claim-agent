SHELL := bash
.SHELLFLAGS := -o pipefail -c

.PHONY: db test run compare api

db:
	docker compose up -d db

test:
	uv run pytest -v 2>&1 | tee reports/test_output.txt

run:
	uv run python scripts/run_eval.py --version $(V) --split $(S)

compare:
	uv run python scripts/run_eval.py --compare $(A) $(B)

api:
	uv run uvicorn claimagent.api:app
