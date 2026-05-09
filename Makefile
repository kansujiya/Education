.PHONY: help install dev down logs lint format typecheck test demo seed clean

COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install: ## Install all workspace deps + dev extras
	uv sync --all-packages --extra dev

dev: ## Bring up the local stack (postgres, redis, minio, langfuse)
	$(COMPOSE) up -d
	@echo "Postgres :5432  Redis :6379  MinIO :9001  Langfuse :3001"

down: ## Stop the local stack
	$(COMPOSE) down

logs: ## Tail the local stack logs
	$(COMPOSE) logs -f

lint: ## Lint + format check
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-format
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Strict mypy on source
	uv run mypy packages/shared/src apps/api/src

test: ## Run the test suite
	uv run pytest

demo: ## Run the M-0 demo (requires ANTHROPIC_API_KEY in .env)
	uv run edu ask "Explain mutex in one paragraph in plain English."

migrate: ## Apply DB migrations to the configured DATABASE_URL
	cd infra/alembic && uv run alembic upgrade head

migrate-down: ## Roll back to base
	cd infra/alembic && uv run alembic downgrade base

seed: migrate ## M-1 demo: load AWS CCP syllabus via mcp-syllabus
	uv run edu load-exam aws-ccp
	uv run edu show-syllabus aws-ccp

teach: ## M-2 demo: stream a layman lesson + render mind map (requires ANTHROPIC_API_KEY)
	uv run edu teach --topic security.shared-resp

examine: ## M-3 demo: full Tutor↔Examiner Socratic loop (interactive)
	uv run edu teach --topic security.shared-resp --interactive

drill: ## M-4 demo: issue 6 cards for a topic
	uv run edu cards --topic security.shared-resp

dashboard: ## M-4 demo: print progress dashboard
	uv run edu progress

onboard: ## M-5 demo: persist a profile (90 days out, 60 min/day)
	uv run edu onboard --user u_demo --exam aws-ccp --exam-date 2026-08-01 --daily-minutes 60

plan-show: ## M-5 demo: print today + 7-day plan
	uv run edu plan --user u_demo

replan-demo: ## M-5 demo: simulate falling behind on a topic and replan
	uv run edu simulate-fall-behind --user u_demo --bump-mastered cloud-concepts.benefits

insight: ## M-6 demo: cutoffs / selection % / topic heatmap with provenance
	uv run edu insight --exam aws-ccp

export-bundle: ## M-6 demo: bundle a topic's lesson + mindmap + cards into a ZIP
	uv run edu export --user u_demo --topic security.shared-resp

serve: ## M-7: run the FastAPI app on http://127.0.0.1:8000 with auto-reload
	uv run uvicorn api.web.app:app --reload --port 8000

web-install: ## M-8: install the React + Vite client deps
	cd apps/web && pnpm install

web-dev: ## M-8: run the web client on http://localhost:5173 (proxies /v1 to :8000)
	cd apps/web && pnpm dev

web-build: ## M-8: typecheck + production bundle
	cd apps/web && pnpm build

web-test: ## M-8: vitest unit tests for the API client
	cd apps/web && pnpm test

loadtest: ## M-10: 10 concurrent users x 5 attempts each against the local API
	uv run python scripts/loadtest.py --base-url http://localhost:8000 --users 10 --attempts 5

acceptance: ## M-11: print the v0.1 acceptance runbook
	@cat docs/runbook-acceptance.md

clean: ## Remove caches and venv
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache .uv
