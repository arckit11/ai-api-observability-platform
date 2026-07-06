SHELL := /bin/bash

.PHONY: help up down restart logs ps psql redis-cli kafka-topics clean \
        backend-build ml-install ml-run test lint

help:
	@echo "Common targets:"
	@echo "  make up               - start infra (postgres, redis, kafka, kafka-ui)"
	@echo "  make down             - stop infra"
	@echo "  make restart          - down + up"
	@echo "  make logs             - tail all container logs"
	@echo "  make ps               - list running containers"
	@echo "  make psql             - open psql shell into the platform db"
	@echo "  make redis-cli        - open redis-cli into the cache"
	@echo "  make kafka-topics     - list kafka topics"
	@echo "  make clean            - down + drop volumes (DATA LOSS)"
	@echo ""
	@echo "  make backend-build    - mvn -f backend/pom.xml package"
	@echo "  make ml-install       - install ml-service python deps"
	@echo "  make ml-run           - run ml-service locally (uvicorn)"

# ─── Infra ────────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f

ps:
	docker compose ps

psql:
	docker compose exec postgres psql -U $${POSTGRES_USER:-api_analytics} -d $${POSTGRES_DB:-api_analytics}

redis-cli:
	docker compose exec redis redis-cli

kafka-topics:
	docker compose exec kafka kafka-topics --bootstrap-server kafka:9092 --list

clean:
	docker compose down -v

# ─── Backend (Java / Maven) ───────────────────────────────────────────
backend-build:
	cd backend && mvn -B package -DskipTests

# ─── ML service (Python) ──────────────────────────────────────────────
ml-install:
	cd ml-service && python -m pip install -e ".[dev]"

ml-run:
	cd ml-service && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
