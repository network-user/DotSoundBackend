.PHONY: dev dev-full seed-dev-worker reaper-dev infra migrate test test-cov test-fast lint format stop clean init backup backup-pg backup-list backup-restore backup-health backup-start backup-stop hooks admin-dev admin-build observability-up observability-down test-admin test-all bootstrap-admin bootstrap-admin-docker prod-deploy prod-deploy-backend prod-deploy-bot prod-deploy-frontend prod-logs prod-ps

hooks: ## Install repo git hooks (boundary check before push)
	git config core.hooksPath .githooks

dev: ## Start infra, run migrations, start backend
	docker compose up -d postgres minio redis
	timeout /t 4 /nobreak >nul 2>&1 || sleep 4
	poetry run alembic upgrade head
	poetry run python main.py

dev-full: ## Same as dev + seed local compute worker credentials
	docker compose up -d postgres minio redis
	timeout /t 4 /nobreak >nul 2>&1 || sleep 4
	poetry run alembic upgrade head
	poetry run python scripts/seed_dev_worker.py
	@echo .
	@echo Now in another terminal: cd ../DotSoundComputeWorker ^&^& make dev
	@echo .
	poetry run python main.py

seed-dev-worker: ## Create or rotate the local-dev compute worker
	poetry run python scripts/seed_dev_worker.py

reaper-dev: ## Run the lease reaper in a tight loop (dev only)
	poetry run python -c "import asyncio; from app.tasks.audio_compute_reaper import run_forever; asyncio.run(run_forever())"

infra: ## Start all Docker services (core only)
	docker compose up -d postgres minio redis

infra-all: ## Start all Docker services including tools
	docker compose --profile tools up -d

migrate: ## Run Alembic migrations
	poetry run alembic upgrade head

test: ## Run pytest
	poetry run pytest -v

test-cov: ## Run pytest with coverage (enforces 95% branch)
	poetry run pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=html --cov-report=json:coverage.json -v
	poetry run python scripts/check_branch_coverage.py

test-fast: ## Run fast tests only (skip slow/s3/redis)
	poetry run pytest -v -m "not slow and not s3 and not redis"

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

admin-dev: ## Start backend + frontend dev for admin work
	docker compose up -d postgres minio redis
	timeout /t 4 /nobreak >nul 2>&1 || sleep 4
	poetry run alembic upgrade head
	@echo Backend on :8000, frontend on :5173
	@echo Run separately: cd frontend && npm run dev
	poetry run python main.py

admin-build: ## Production build of frontend (admin chunk goes to assets/secure/)
	cd frontend && npm run build

observability-up: ## Start Prometheus + Grafana + Loki + Tempo + cAdvisor
	docker compose -f docker-compose.observability.yml up -d
	@echo Grafana on http://localhost:3001 (admin/admin)
	@echo Prometheus on http://localhost:9091

observability-down: ## Stop observability stack
	docker compose -f docker-compose.observability.yml down

test-admin: ## Run admin-specific tests only
	poetry run pytest -v tests/admin/ tests/observability/

test-all: test ## Backend + frontend unit tests
	cd frontend && npm run test

bootstrap-admin: ## Grant full admin to user. USAGE: make bootstrap-admin USER="--email me@x.com"
	poetry run python scripts/bootstrap_admin.py $(USER)

bootstrap-admin-docker: ## Same as bootstrap-admin, but inside docker compose. USAGE: make bootstrap-admin-docker USER="--email me@x.com"
	docker compose exec backend poetry run python scripts/bootstrap_admin.py $(USER)

prod-deploy: ## Full production deploy: pull all repos, build, migrate, roll
	./scripts/deploy.sh full

prod-deploy-backend: ## Rebuild only backend + worker (after Backend push)
	./scripts/deploy.sh only-backend

prod-deploy-bot: ## Rebuild only bot (after Bot push)
	./scripts/deploy.sh only-bot

prod-deploy-frontend: ## Rebuild only frontend + caddy (UI-only changes)
	./scripts/deploy.sh only-frontend

prod-logs: ## Tail production logs from all app services
	docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=200 backend worker bot frontend caddy

prod-ps: ## Show production container status
	docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
