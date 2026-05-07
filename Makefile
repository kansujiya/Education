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

clean: ## Remove caches and venv
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache .uv
