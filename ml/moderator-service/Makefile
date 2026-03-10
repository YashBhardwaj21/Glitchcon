# Makefile for AI Moderation Microservice
# Usage: make <target>

.PHONY: dev test seed build lint format clean logs help

COMPOSE_FILE=docker-compose.yml
COMPOSE_DEV_FILE=docker-compose.dev.yml
SERVICE_DIR=service
SDK_DIR=sdk

help: ## Show this help message
	@echo "AI Moderation Microservice — Available Commands"
	@echo "================================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ─── Development ──────────────────────────────────────────────────────────────
dev: ## Start full dev stack (postgres, redis, celery, flower, fastapi with hot reload)
	docker compose -f $(COMPOSE_DEV_FILE) up

dev-detach: ## Start dev stack in background
	docker compose -f $(COMPOSE_DEV_FILE) up -d

stop: ## Stop all containers
	docker compose -f $(COMPOSE_DEV_FILE) down

# ─── Production ───────────────────────────────────────────────────────────────
build: ## Build all Docker images
	docker compose -f $(COMPOSE_FILE) build

up: ## Start production stack
	docker compose -f $(COMPOSE_FILE) up -d

down: ## Stop production stack
	docker compose -f $(COMPOSE_FILE) down

# ─── Database ─────────────────────────────────────────────────────────────────
migrate: ## Run Alembic migrations
	docker compose -f $(COMPOSE_DEV_FILE) exec service alembic upgrade head

migrate-rollback: ## Rollback last migration
	docker compose -f $(COMPOSE_DEV_FILE) exec service alembic downgrade -1

# ─── Seeding ──────────────────────────────────────────────────────────────────
seed: ## Run seed script (profiles, keywords, templates, API keys)
	docker compose -f $(COMPOSE_DEV_FILE) exec service python scripts/seed.py

load-wordlists: ## Load multilingual profanity/keyword word lists
	docker compose -f $(COMPOSE_DEV_FILE) exec service python scripts/load_wordlists.py

evaluate: ## Run per-language F1 evaluation
	docker compose -f $(COMPOSE_DEV_FILE) exec service python scripts/evaluate_pipeline.py

# ─── Testing ──────────────────────────────────────────────────────────────────
test: ## Run all unit tests
	cd $(SERVICE_DIR) && python -m pytest tests/ -v --ignore=tests/e2e -x

test-sdk: ## Run SDK unit tests
	cd $(SDK_DIR) && python -m pytest tests/ -v -x

test-e2e: ## Run end-to-end tests (requires running stack)
	cd $(SERVICE_DIR) && python -m pytest tests/e2e/ -v -m e2e

test-all: test test-sdk ## Run all tests (service + sdk)

# ─── Code Quality ─────────────────────────────────────────────────────────────
lint: ## Run ruff linter
	ruff check $(SERVICE_DIR)/app/ $(SDK_DIR)/moderator_sdk/

format: ## Run ruff formatter + isort
	ruff format $(SERVICE_DIR)/app/ $(SDK_DIR)/moderator_sdk/
	ruff check --fix $(SERVICE_DIR)/app/ $(SDK_DIR)/moderator_sdk/

# ─── Logs ─────────────────────────────────────────────────────────────────────
logs: ## Tail service logs
	docker compose -f $(COMPOSE_DEV_FILE) logs -f service

logs-all: ## Tail all container logs
	docker compose -f $(COMPOSE_DEV_FILE) logs -f

# ─── Cleanup ──────────────────────────────────────────────────────────────────
clean: ## Remove containers, volumes, and orphans
	docker compose -f $(COMPOSE_DEV_FILE) down -v --remove-orphans

clean-cache: ## Clear Redis cache
	docker compose -f $(COMPOSE_DEV_FILE) exec redis redis-cli FLUSHALL
