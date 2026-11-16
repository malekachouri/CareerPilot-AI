# Developer shortcuts. Everything also works with plain docker compose / uv / pnpm commands.
.PHONY: help up down logs dev-deps api web test lint typecheck api-client e2e admin

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

up: ## Build and start the whole stack (http://localhost:3000)
	@test -f .env || cp .env.example .env
	docker compose up -d --build --wait

down: ## Stop the stack (data volumes are kept)
	docker compose down

logs: ## Follow logs of all services
	docker compose logs -f --tail 100

dev-deps: ## Start only Postgres + Valkey for local development
	docker compose up -d --wait postgres valkey

api: ## Run the API with hot reload (needs dev-deps)
	cd apps/api && uv sync && uv run alembic upgrade head && uv run uvicorn careerpilot.main:app --reload

web: ## Run the web app with hot reload (needs api)
	cd apps/web && pnpm install && pnpm dev

test: ## Run backend and frontend tests (needs dev-deps)
	cd apps/api && uv run pytest -q
	cd apps/web && pnpm test

lint: ## Lint and format-check everything
	cd apps/api && uv run ruff check . && uv run ruff format --check .
	cd apps/web && pnpm lint

typecheck: ## Static type checks
	cd apps/api && uv run mypy
	cd apps/web && pnpm typecheck

api-client: ## Regenerate the typed web client from the API schema
	./scripts/gen-api-client.sh

e2e: ## Browser smoke test against the running stack
	cd apps/web && BASE_URL=http://localhost:3000 pnpm e2e

admin: ## Create an admin account: make admin EMAIL=you@example.org
	docker compose run --rm api careerpilot create-admin --email $(EMAIL)
