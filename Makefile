.PHONY: dev infra migrate test lint format stop clean init

dev: ## Start infra, run migrations, start backend
	docker compose up -d postgres minio redis
	timeout /t 4 /nobreak >nul 2>&1 || sleep 4
	poetry run alembic upgrade head
	poetry run python main.py

infra: ## Start all Docker services (core only)
	docker compose up -d postgres minio redis

infra-all: ## Start all Docker services including tools
	docker compose --profile tools up -d

migrate: ## Run Alembic migrations
	poetry run alembic upgrade head

test: ## Run pytest
	poetry run pytest -v

lint: ## Run Ruff + Black check + mypy
	poetry run ruff check .
	poetry run black --check .
	poetry run mypy app/

format: ## Auto-format with Black + Ruff fix
	poetry run black .
	poetry run ruff check --fix .

stop: ## Stop all Docker services
	docker compose --profile tools down

clean: ## Stop and remove volumes
	docker compose --profile tools down -v

init: ## First-time project setup
	@echo Setting up DotSound Backend...
	copy .env.example .env 2>nul || cp .env.example .env
	docker compose up -d postgres minio redis
	timeout /t 5 /nobreak >nul 2>&1 || sleep 5
	poetry install
	poetry run alembic upgrade head
	@echo Setup complete! Run 'make dev' to start.
