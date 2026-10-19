"""Development entry point with optional Prometheus instrumentation.

Run with ``./run.sh dev`` for hot reload, or ``uvicorn main-dev:app`` directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402

try:  # Prometheus is part of the dev dependency group.
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app)
except Exception:  # pragma: no cover - optional dependency
    pass
