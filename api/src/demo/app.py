"""Passcode-protected voice-agent demo with server-side provider keys."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import uuid
import wave
from collections import defaultdict, deque
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bench.core.config import ROOT, load_config
from bench.datasets.scenarios import load_prompt
from bench.providers.faster_whisper_stt import FasterWhisperSTT
from bench.providers.llm import LLMClient
from bench.providers.sarvam_stt import SarvamSTT
from bench.providers.sarvam_tts import SarvamTTS
from bench.utils.results import read_json

DEMO_DIR = Path(__file__).resolve().parent
SESSION_CAP_S = 180
MAX_SESSIONS_PER_IP_HOUR = int(os.getenv("DEMO_SESSIONS_PER_IP_HOUR", "5"))
DAILY_SESSION_CAP = int(os.getenv("DEMO_DAILY_SESSION_CAP", "100"))

app = FastAPI(title="Voxora benchmark demo")
app.mount("/static", StaticFiles(directory=DEMO_DIR / "static"), name="static")


class Limits:
    def __init__(self) -> None:
        self.by_ip: dict[str, deque[float]] = defaultdict(deque)
        self.daily_sessions = 0
        self.day = time.strftime("%Y-%m-%d")

    def allow(self, ip: str) -> tuple[bool, str]:
        today = time.strftime("%Y-%m-%d")
        if today != self.day:
            self.day = today
            self.daily_sessions = 0
        if self.daily_sessions >= DAILY_SESSION_CAP:
            return False, "The demo has reached today's session limit."
        now = time.time()
        events = self.by_ip[ip]
        while events and events[0] < now - 3600:
            events.popleft()
        if len(events) >= MAX_SESSIONS_PER_IP_HOUR:
            return False, "This network has reached the hourly session limit."
        events.append(now)
        self.daily_sessions += 1
        return True, ""


limits = Limits()


def _best_providers() -> dict[str, dict[str, str]]:
    path = ROOT / "results" / "stt_best.json"
    if path.exists():
        payload = read_json(path)
        return payload.get("languages", {})
    return {
        "en": {"provider": "sarvam", "mode": "transcribe"},
        "hi": {"provider": "sarvam", "mode": "transcribe"},
        "hinglish": {"provider": "sarvam", "mode": "transcribe"},
    }


def _write_pcm_wav(pcm: bytes, path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(DEMO_DIR / "static" / "index.html")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_session(websocket: WebSocket) -> None:
    expected_code = os.getenv("DEMO_CODE", "")
    code = websocket.query_params.get("code", "")
    if not expected_code or code != expected_code:
        await websocket.close(code=1008, reason="Invalid demo passcode.")
        return
    ip = websocket.client.host if websocket.client else "unknown"
    allowed, message = limits.allow(ip)
    if not allowed:
        await websocket.close(code=1013, reason=message)
        return

    await websocket.accept()
    session_id = uuid.uuid4().hex[:8]
    config = load_config()
    prompt = load_prompt("final")
    best = _best_providers()
    llm = LLMClient(
        config,
        config.llm,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        model=config.llm_model,
        temperature=float(config.llm.temperature),
    )
    tts = SarvamTTS(config)
    history: list[dict[str, str]] = []
    audio_buffer = bytearray()
    turn_task: asyncio.Task[None] | None = None
    deadline = asyncio.get_running_loop().time() + SESSION_CAP_S
    await websocket.send_json(
        {
            "type": "ready",
            "session_id": session_id,
            "sample_rate": 16000,
            "session_cap_s": SESSION_CAP_S,
        }
    )

    async def send_turn(language: str, pcm: bytes) -> None:
        started = time.perf_counter()
        stt = None
        try:
            selection = best.get(language, best["en"])
            if selection["provider"].startswith("faster-whisper"):
                stt = FasterWhisperSTT(
                    config,
                    use_language_hint=selection["mode"] == "transcribe",
                )
            else:
                stt = SarvamSTT(config, selection["mode"])
            with NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                temp_path = Path(handle.name)
            _write_pcm_wav(pcm, temp_path)
            stt_result = await stt.transcribe_file(str(temp_path), language)
            temp_path.unlink(missing_ok=True)
            await websocket.send_json(
                {
                    "type": "transcript.final",
                    "text": stt_result.text,
                    "language": language,
                }
            )
            messages = [
                {"role": "system", "content": prompt},
                *history,
                {"role": "user", "content": stt_result.text},
            ]
            reply = await llm.complete(messages)
            history.extend(
                [
                    {"role": "user", "content": stt_result.text},
                    {"role": "assistant", "content": reply},
                ]
            )
            await websocket.send_json({"type": "assistant.done", "text": reply})
            tts_language = {"en": "en-IN", "hi": "hi-IN", "hinglish": "hi-IN"}[language]
            tts_result = await tts.synthesize(reply, tts_language)
            await websocket.send_json(
                {
                    "type": "tts.audio",
                    "encoding": "linear16",
                    "sample_rate": int(config.tts["sample_rate_hz"]),
                    "audio": base64.b64encode(tts_result.audio_bytes).decode("ascii"),
                    "text": reply,
                }
            )
            now = time.perf_counter()
            await websocket.send_json(
                {
                    "type": "turn.metrics",
                    "stt_final_ms": round((stt_result.t_final - started) * 1000, 1),
                    "llm_ms": round(
                        (tts_result.t_request_sent - stt_result.t_final) * 1000,
                        1,
                    ),
                    "tts_first_audio_ms": round(
                        (tts_result.t_first_audio_byte - tts_result.t_request_sent)
                        * 1000,
                        1,
                    ),
                    "end_to_end_ms": round(
                        (tts_result.t_first_audio_byte - started) * 1000,
                        1,
                    ),
                    "total_ms": round((now - started) * 1000, 1),
                }
            )
        except asyncio.CancelledError:
            await websocket.send_json({"type": "turn.cancelled"})
            raise
        except Exception as exc:
            await websocket.send_json(
                {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
            )
        finally:
            if stt is not None:
                await stt.close()

    try:
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                await websocket.send_json(
                    {"type": "session.limit", "message": "The three-minute session cap was reached."}
                )
                break
            message = await asyncio.wait_for(websocket.receive(), timeout=remaining)
            if message.get("type") == "websocket.disconnect":
                break
            if (data := message.get("bytes")) is not None:
                audio_buffer.extend(data)
                continue
            try:
                event = json.loads(message.get("text") or "{}")
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "speech_start":
                audio_buffer.clear()
                if turn_task and not turn_task.done():
                    turn_task.cancel()
                    await websocket.send_json({"type": "playback.stop"})
            elif kind == "speech_end":
                language = str(event.get("language", "en"))
                pcm = bytes(audio_buffer)
                audio_buffer.clear()
                if pcm:
                    if turn_task and not turn_task.done():
                        turn_task.cancel()
                    turn_task = asyncio.create_task(send_turn(language, pcm))
            elif kind == "cancel" and turn_task and not turn_task.done():
                turn_task.cancel()
                await websocket.send_json({"type": "playback.stop"})
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if turn_task and not turn_task.done():
            turn_task.cancel()
        await llm.close()
        await tts.close()
