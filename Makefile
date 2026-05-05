.PHONY: install dev types build start lint test test-cov clean-db clean-db-volume clean-web demo-snapshot readme-header

COMPOSE ?= docker compose
PROJECT_NAME ?= $(notdir $(CURDIR))
API_DB_VOLUME ?= $(PROJECT_NAME)_api_data

PYTHON ?= python3
VENV ?= .venv
UV := $(shell which uv 2>/dev/null)

install:
	@# Check Python version if not using uv (uv can manage its own python)
	@if [ -z "$(UV)" ]; then \
		$(PYTHON) -c 'import sys; exit(0) if sys.version_info >= (3, 11) else (print(f"Error: Python 3.11+ is required, but found {sys.version.split()[0]}"), exit(1))'; \
	fi
	@echo "Cleaning up any existing virtual environment..."
	rm -rf $(VENV)
	@if [ -n "$(UV)" ]; then \
		echo "Creating virtual environment and installing dependencies using uv..."; \
		$(UV) venv $(VENV) --python 3.11; \
		$(UV) pip install -r requirements.txt; \
	else \
		echo "Creating virtual environment using venv..."; \
		$(PYTHON) -m venv $(VENV); \
		$(VENV)/bin/python -m pip install --upgrade pip; \
		$(VENV)/bin/python -m pip install -r requirements.txt; \
	fi
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

test-cov:
	.venv/bin/python -m pytest --cov --cov-report=term-missing --cov-report=xml --cov-fail-under=57

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

demo-snapshot:
	.venv/bin/python scripts/build_demo_snapshot.py --profile demo --out web/public/demo-data

readme-header:
	python3 scripts/render_readme_header.py
	python3 scripts/render_readme_header.py --source .github/assets/readme-header-light-source.html --out .github/assets/readme-header-light.png
