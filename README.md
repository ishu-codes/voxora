# Voxora

**From speech to intelligence and back, in real time.**

Voxora is a low-latency, real-time voice AI agent. You speak through your
microphone and hear the answer without uploading a recording or waiting for the
whole response: speech recognition, language generation and speech synthesis
overlap, and speaking again cancels the turn in flight.

```
browser mic ──20 ms PCM frames──▶ VAD ──▶ STT ──▶ LLM ──▶ TTS ──▶ browser playback
                                    ▲                           │
                                    └────── barge-in cancels ────┘
```

## Repository layout

| Path | Description |
| --- | --- |
| [`api/`](api) | FastAPI backend: WebSocket session, VAD, provider adapters, metrics. See [`api/README.md`](api/README.md). |
| [`web/`](web) | React + TypeScript client: capture, playback, transcript, latency panel. See [`web/README.md`](web/README.md). |
| [`PRD.md`](PRD.md) | Product requirements document this implementation follows. |

## Quick start

Two terminals:

```bash
# 1. backend
cd api
uv sync --group dev --extra dev
cp .env.example .env
./run.sh serve                 # http://localhost:8000

# 2. frontend
cd web
pnpm install
pnpm dev                       # http://localhost:3000
```

Open <http://localhost:3000/app>, press **Start**, allow the microphone and
talk. With no keys configured it runs on the browser recogniser, a built-in
demo responder and browser speech synthesis — enough to exercise streaming,
barge-in and the latency panel end to end.

For real answers, add a hosted key or a local model on the server:

```bash
# hosted (one key covers STT, LLM and TTS by default)
OPENAI_API_KEY=sk-... ./run.sh serve

# fully local
uv sync --extra stt
LLM_PROVIDER=ollama LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=llama3.2 \
STT_PROVIDER=faster-whisper TTS_PROVIDER=browser ./run.sh serve
```

## What is implemented

Product requirements: the MVP P0 set plus the P1 provider/configuration
requirements.

- **Live audio session** — continuous 16 kHz PCM16 frames over one WebSocket,
  no completed-recording upload.
- **Streaming pipeline** — VAD endpointing, provider-interface STT, token-level
  LLM streaming and sentence-buffered TTS that overlaps generation.
- **Early playback** — playback starts on the first synthesised clause, not the
  finished answer.
- **Interruption** — VAD barge-in cancels LLM and TTS work; the browser stops
  playback on the first voiced frame and drops the cancelled turn's audio.
- **Conversation context** — the session's recent history is sent with every
  request, so follow-ups work.
- **Latency instrumentation** — per-stage timings, `turn.metrics` events,
  client-measured first-audio and barge-in latency, and a p50/p95/p99 summary at
  `/api/v1/voice/metrics`.
- **Failure handling** — microphone denial, socket loss, recognition and model
  errors surface in the UI with reconnect backoff; a failed turn never leaves
  the session stuck.
- **Configuration** — every model and endpoint is an environment variable;
  provider credentials stay server-side.

Non-goals from the PRD (accounts, RAG, tools, telephony, mobile, speech-to-speech)
are out of scope for this MVP.

## Tests

```bash
cd api && ./run.sh test        # 24 tests, no network or database required
cd web && pnpm build && pnpm lint
```
