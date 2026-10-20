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
uv sync --group dev
cp .env.example .env
# add SARVAM_API_KEY and your LLM credentials to .env
./run.sh serve                 # http://localhost:8000

# 2. frontend
cd web
pnpm install
pnpm dev                       # http://localhost:3000
```

Open <http://localhost:3000/app>, press **Start**, allow the microphone and
talk. Speech recognition and synthesis run on Sarvam's streaming models; the
language model can be any OpenAI-compatible endpoint.

```bash
# backend .env
SARVAM_API_KEY=sk_...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-...
```

Without an LLM key the backend falls back to a small demo responder. Without a
Sarvam key the voice session returns a clear configuration error.

## What is implemented

Product requirements: the MVP P0 set plus the P1 provider/configuration
requirements.

- **Live audio session** — 16 kHz PCM16 frames over one WebSocket, no
  completed-recording upload. Local VAD keeps silence on the device and streams
  confirmed speech with a short pre-roll; it falls back to continuous streaming
  if VAD cannot start.
- **Streaming pipeline** — VAD endpointing, Sarvam Saaras partial transcripts,
  token-level LLM streaming and sentence-buffered Sarvam Bulbul synthesis that
  overlaps generation.
- **Early playback** — playback starts on the first synthesised clause, not the
  finished answer.
- **Interruption** — Silero VAD (`@ricky0123/vad-web`, local ONNX assets)
  confirms speech onset in the browser, stops playback immediately and sends a
  turn-targeted `interrupt`. The server cancels only that turn and drops late
  events from cancelled turns.
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
cd api && ./run.sh test        # no network or database required
cd web && pnpm test && pnpm typecheck && pnpm lint && pnpm build
```
