from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import time
import wave
from pathlib import Path

import httpx
import pytest
import websockets

SOURCE_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = SOURCE_ROOT.parent


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.integration
async def test_demo_server_completes_one_wav_turn():
    port = _free_port()
    env = {
        **os.environ,
        "DEMO_CODE": "benchmark-test-code",
        "DEMO_DAILY_SESSION_CAP": "100",
        "DEMO_SESSIONS_PER_IP_HOUR": "100",
        "PYTHONPATH": str(SOURCE_ROOT),
    }
    process = subprocess.Popen(
        [
            str(API_ROOT / ".venv" / "bin" / "uvicorn"),
            "demo.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=API_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        async with httpx.AsyncClient() as client:
            for _ in range(50):
                try:
                    response = await client.get(f"http://127.0.0.1:{port}/healthz")
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.1)
            else:
                raise AssertionError("demo server did not become healthy")

        with wave.open(
            str(SOURCE_ROOT / "data" / "wav" / "en01.wav"),
            "rb",
        ) as wav:
            pcm = wav.readframes(wav.getnframes())
        uri = f"ws://127.0.0.1:{port}/ws?code=benchmark-test-code"
        async with websockets.connect(uri, max_size=None) as socket:
            ready = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
            assert ready["type"] == "ready"
            await socket.send(json.dumps({"type": "speech_start"}))
            for offset in range(0, len(pcm), 640):
                await socket.send(pcm[offset : offset + 640])
            await socket.send(
                json.dumps({"type": "speech_end", "language": "en"})
            )
            seen: set[str] = set()
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                message = json.loads(
                    await asyncio.wait_for(socket.recv(), timeout=30)
                )
                seen.add(message["type"])
                if message["type"] == "error":
                    raise AssertionError(message["message"])
                if message["type"] == "turn.metrics":
                    break
            assert {"transcript.final", "assistant.done", "tts.audio"} <= seen
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
