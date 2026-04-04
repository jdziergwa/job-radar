.PHONY: install dev types build start lint clean-db clean-web

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

clean-db:
	rm -rf data/*.db

clean-web:
	rm -rf web/.next web/node_modules web/out
