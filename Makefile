SHELL := /bin/bash

API_DIR := api
WEB_DIR := web
INFRA_COMPOSE := docker compose --env-file infra/.env -f infra/docker/docker-compose.yml

.PHONY: help install env api-install web-install dev api-dev api-serve web-dev \
	web-build test test-api test-integration test-web typecheck lint build check \
	health demo bench-stt bench-noise bench-latency bench-scenarios bench-heldout \
	bench-report calibrate infra-env infra-config infra-build infra-up infra-down \
	infra-logs

help:
	@echo "Voxora"
	@echo ""
	@echo "Setup:"
	@echo "  make install            Install API and web dependencies"
	@echo "  make env                Create api/.env from .env.example if missing"
	@echo ""
	@echo "Run:"
	@echo "  make dev                Start the API and web app together"
	@echo "  make api-dev            Start the FastAPI backend with reload"
	@echo "  make web-dev            Start the Next.js app"
	@echo "  make demo               Start the voice benchmark demo"
	@echo "  make infra-up           Build and start the local Docker stack"
	@echo "  make infra-down         Stop the local Docker stack"
	@echo ""
	@echo "Verify:"
	@echo "  make test               Run API and web tests"
	@echo "  make test-integration   Run the live local demo test"
	@echo "  make check              Run tests, typecheck, lint, and web build"
	@echo ""
	@echo "Benchmark:"
	@echo "  make bench-stt          Run clean STT comparisons"
	@echo "  make bench-noise        Run phone and noise conditions"
	@echo "  make bench-latency      Run the 100-turn latency benchmark"
	@echo "  make bench-scenarios    Run all training prompt versions"
	@echo "  make bench-heldout      Run the frozen held-out comparison"
	@echo "  make bench-report       Regenerate REPORT.md and NUMBERS.md"
	@echo "  make calibrate          Label the calibration sample"

install: api-install web-install

env:
	@test -f $(API_DIR)/.env || cp $(API_DIR)/.env.example $(API_DIR)/.env
	@echo "Environment file is ready at $(API_DIR)/.env"

api-install:
	cd $(API_DIR) && uv sync --group dev

web-install:
	cd $(WEB_DIR) && pnpm install

dev:
	@set -e; \
	(cd $(API_DIR) && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000) & API_PID=$$!; \
	(cd $(WEB_DIR) && pnpm dev) & WEB_PID=$$!; \
	trap 'kill $$API_PID $$WEB_PID 2>/dev/null || true' INT TERM EXIT; \
	wait

api-dev:
	cd $(API_DIR) && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

api-serve:
	cd $(API_DIR) && uv run uvicorn main:app --host 0.0.0.0 --port 8000

web-dev:
	cd $(WEB_DIR) && pnpm dev

web-build:
	cd $(WEB_DIR) && pnpm build

test: test-api test-web

test-api:
	cd $(API_DIR) && uv run pytest -q -m "not integration"

test-integration:
	cd $(API_DIR) && uv run pytest -q src/tests/test_demo_server.py -m integration

test-web:
	cd $(WEB_DIR) && pnpm test

typecheck:
	cd $(WEB_DIR) && pnpm typecheck

lint:
	cd $(WEB_DIR) && pnpm lint

build: web-build

check: test typecheck lint build

health:
	curl --fail --silent http://localhost:8000/healthz
	@echo ""

demo:
	@test -n "$$DEMO_CODE" || { echo "Set DEMO_CODE before starting the demo."; exit 1; }
	cd $(API_DIR) && PYTHONPATH=src uv run uvicorn demo.app:app --host 127.0.0.1 --port 8000

bench-stt:
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.runners.run_stt \
		--providers sarvam faster-whisper faster-whisper-nohint \
		--modes transcribe codemix translit \
		--wav-dir data/wav --condition clean

bench-noise:
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.runners.make_noisy
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.runners.run_noise

bench-latency:
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.runners.run_latency

bench-scenarios:
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.runners.run_scenarios --version v1 --runs 3
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.runners.run_scenarios --version v2 --runs 3
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.runners.run_scenarios --version v3 --runs 3
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.runners.run_scenarios --version v4 --runs 3
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.analysis.decisions

bench-heldout:
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.runners.run_scenarios --heldout --runs 3

bench-report:
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.analysis.report
	cd $(API_DIR) && PYTHONPATH=src uv run python -m bench.analysis.resume_numbers

calibrate:
	cd $(API_DIR) && PYTHONPATH=src uv run python -m tools.calibrate_judge --conversations 25 --stt 15

infra-env:
	@test -f infra/.env || cp infra/.env.example infra/.env
	@echo "Docker environment is ready at infra/.env"

infra-config:
	docker compose --env-file infra/.env.example -f infra/docker/docker-compose.yml config

infra-build: infra-env
	$(INFRA_COMPOSE) build

infra-up: infra-env
	$(INFRA_COMPOSE) up --build -d

infra-down:
	$(INFRA_COMPOSE) down

infra-logs:
	$(INFRA_COMPOSE) logs --follow
