.PHONY: install dev types build start lint test clean-db clean-db-volume clean-web

COMPOSE ?= docker compose
PROJECT_NAME ?= $(notdir $(CURDIR))
API_DB_VOLUME ?= $(PROJECT_NAME)_api_data

install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd web && npm install

dev:
	@echo "Starting FastAPI on :8000 and Next.js on :3000"
	@trap 'kill 0' SIGINT; \
	  .venv/bin/uvicorn api.main:app --reload --port 8000 & \
	  cd web && npm run dev & \
	  wait

types:
	cd web && npx openapi-typescript http://localhost:8000/openapi.json -o src/lib/api/types.ts

build:
	cd web && npm run build

start: build
	.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000

lint:
	cd web && npm run lint && npx tsc --noEmit

test:
	.venv/bin/python -m pytest

clean-db:
	rm -f data/*.db
	@if [ -n "$$($(COMPOSE) ps -q api 2>/dev/null)" ]; then \
		echo "Removing Docker API database files from /app/data"; \
		$(COMPOSE) exec -T api sh -lc 'rm -f /app/data/*.db'; \
	elif docker volume inspect $(API_DB_VOLUME) >/dev/null 2>&1; then \
		echo "Docker DB volume '$(API_DB_VOLUME)' exists but the API container is not running."; \
		echo "Use 'make clean-db-volume' to remove the stopped Docker volume too."; \
	fi

clean-db-volume:
	@if [ -n "$$($(COMPOSE) ps -q api 2>/dev/null)" ]; then \
		echo "Stopping compose services before removing Docker DB volume"; \
		$(COMPOSE) down; \
	fi
	@docker volume rm -f $(API_DB_VOLUME) >/dev/null 2>&1 || true
	@echo "Removed Docker DB volume: $(API_DB_VOLUME)"

clean-web:
	rm -rf web/.next web/node_modules web/out
