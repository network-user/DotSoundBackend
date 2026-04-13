.PHONY: dev infra migrate test lint format stop clean init backup backup-pg backup-list backup-restore backup-health backup-start backup-stop

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

test-cov: ## Run pytest with coverage
	poetry run pytest --cov=app --cov-report=term-missing --cov-report=html -v

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

backup: ## Run full backup (PostgreSQL + Redis + configs)
	docker compose --profile backup run --rm backup /scripts/backup.sh full

backup-pg: ## Run PostgreSQL-only backup
	docker compose --profile backup run --rm backup /scripts/backup.sh pg

backup-list: ## List available backups
	docker compose --profile backup run --rm backup sh -c "ls -lhR /backups/daily/ /backups/weekly/ /backups/monthly/ 2>/dev/null || echo 'No backups yet'"

backup-restore: ## Restore from backup (interactive)
	@echo Available backups:
	docker compose --profile backup run --rm backup sh -c "ls -1d /backups/daily/* 2>/dev/null || echo 'No backups'"
	@echo Run: docker compose --profile backup run --rm backup /scripts/restore.sh /backups/daily/YYYYMMDD_HHMMSS

backup-health: ## Check health of latest backup
	docker compose --profile backup run --rm backup /scripts/backup-healthcheck.sh

backup-start: ## Start automatic backup cron service
	docker compose --profile backup up -d backup

backup-stop: ## Stop backup cron service
	docker compose --profile backup stop backup
