#!/usr/bin/env bash

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
BASE_URL_API="$BASE_URL/api/v1"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$API_DIR"

install() {
    # Runtime deps plus the pytest development group.
    uv sync --group dev
}

activate() {
    if [ ! -d .venv ]; then
        install
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
    export PYTHONPATH="$API_DIR:$API_DIR/src:$PROJECT_ROOT:$PYTHONPATH"
}

case "$1" in
    install)
        install
    ;;

    dev)
        activate
        uvicorn main:app --reload --host 0.0.0.0 --port "${PORT:-8000}"
    ;;

    serve)
        activate
        uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;

    test)
        activate
        pytest -q
    ;;

    health)
        curl -s -X GET "$BASE_URL/healthz"
    ;;

    config)
        curl -s -X GET "$BASE_URL_API/voice/config"
    ;;

    metrics)
        curl -s -X GET "$BASE_URL_API/voice/metrics"
    ;;

    bench)
        activate
        python -m scripts.benchmark --server-metrics "${@:2}"
    ;;

    *)
        echo "Usage: $0 {install|dev|serve|test|health|config|metrics|bench}"
        exit 1
    ;;
esac
