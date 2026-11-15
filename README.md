# Voxora

![Voxora voice agent benchmark](docs/banner.png)

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
| [`infra/`](infra) | Docker Compose stack for the API and web client. See [`infra/README.md`](infra/README.md). |
| [`PRD.md`](PRD.md) | Product requirements document this implementation follows. |
| [`PRD2.md`](PRD2.md) | Gnani provider, scenario and speech-only benchmark requirements. |

## Quick start

Two terminals:

```bash
# 1. backend
cd api
uv sync --group dev
cp .env.example .env
# add SARVAM_API_KEY, GNANI_API_KEY and your LLM credentials to .env
./run.sh serve                 # http://localhost:8000

# 2. frontend
cd web
pnpm install
pnpm dev                       # http://localhost:3000
```

Open <http://localhost:3000/app>, choose a scenario and speech providers, press
**Start**, and allow the microphone. The language model can be any
OpenAI-compatible endpoint. Gnani Prisma and Timbre calls run only on the
FastAPI server.

To run both services in containers instead:

```bash
cp infra/.env.example infra/.env
# add SARVAM_API_KEY and the LLM credentials to infra/.env
make infra-up                  # http://localhost:3000/app
```

Stop the stack with `make infra-down`.

```bash
# backend .env
SARVAM_API_KEY=sk_...
GNANI_API_KEY=...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-...
```

Without an LLM key the backend falls back to a small demo responder. A selected
speech provider reports a clear configuration error when its key is missing.

## Gnani challenge implementation

### Speech providers

| Stage | Provider and model | Transport |
| --- | --- | --- |
| STT | Gnani Prisma v2.5 | `wss://api.vachana.ai/stt/v3/stream` |
| STT | Sarvam Saaras v3 realtime | Sarvam streaming WebSocket |
| STT | OpenAI Whisper base locally | Transformers pipeline over a VAD-bounded turn |
| TTS | Gnani Timbre v2.5 | `wss://api.vachana.ai/api/v1/tts` |
| TTS | Sarvam Bulbul v3 | Sarvam streaming WebSocket |

Provider credentials stay in `api/.env`. `GNANI_API_KEY` is never included in a
browser response or voice WebSocket frame. Gnani requests retry transient
connection and rate-limit failures with bounded exponential backoff.

### Scenarios

Scenario data lives in `api/src/voice/scenarios/`.

| Scenario | Language | Behavior |
| --- | --- | --- |
| Kirana order | Hinglish | Reads back grocery items, quantities and rupee total from a fixed catalog |
| Pizza order | English | Confirms size, toppings and quantity, then reads back the total |
| EMI reminder | Hindi, English or Hinglish | Outbound opening line, payment-date request, and bounded handling for paid, hardship, wrong-number and dispute cases |

The EMI prompt is based on `api/src/prompts/agent_v4.txt`. The selected
scenario sets the system prompt, language hint, opening line and default voice.
Only the EMI scenario speaks first.

### Speech benchmark

The speech-only runner is separate from the existing LLM and conversation
benchmark:

```bash
cd api
PYTHONPATH=src uv run python -m bench.runners.run_prd2 --runs 3
```

It runs all 45 utterances over clean, phone, three pink-noise levels and babble,
then runs 20 TTS sentences in English, Hindi and Hinglish. Every STT item and
TTS item runs three times, sequentially. Raw rows are written under
`api/src/results/prd2/`; the latest summary is available at
`/api/v1/voice/benchmark` and rendered at `/benchmark`.

Normalization applies NFC, lowercasing, punctuation removal, numeral-to-word
conversion and deterministic Devanagari-to-Latin transliteration to both the
reference and hypothesis. The transliteration is spelling-based rather than
phonetic, so it can inflate error rates for script and spelling variants.

TTS intelligibility is measured by transcribing every generated clip with the
same Faster Whisper base model. This is a proxy, not a human listening test.

### Measured results

Full tables, all noise conditions, raw run names and failure details are in
[`api/src/results/prd2/REPORT.md`](api/src/results/prd2/REPORT.md). The run used
three repeats per item, one request at a time.

Clean STT results:

| Provider | English WER | Hindi WER | Hinglish WER | Final transcript p50, English / Hindi / Hinglish |
| --- | ---: | ---: | ---: | ---: |
| Gnani Prisma v2.5 | 0.0% | 11.1% | 80.0% | 190 / 199 / 203 ms |
| Sarvam Saaras v3 | 0.0% | 0.0% | 81.8% | 613 / 636 / 595 ms |
| Faster Whisper base | 7.7% | 100.0% | 100.0% | 717 / 841 / 1746 ms |

Gnani had the lowest final-transcript latency in every clean language and
across the six audio conditions. Its clean English and Hindi word error rates
were as low as or lower than both comparators. Hinglish remained difficult for
Gnani and Sarvam, with both near 80% normalized WER. Faster Whisper's Hindi and
Hinglish scores were dominated by script and spelling differences in the
deterministic comparison space.

TTS results across all 20 sentences:

| Provider | First audio p50, English / Hindi / Hinglish | Total synthesis p50, English / Hindi / Hinglish | RTF p50, English / Hindi / Hinglish | Round-trip WER, English / Hindi / Hinglish |
| --- | ---: | ---: | ---: | ---: |
| Gnani Timbre v2.5 | 148 / 151 / 142 ms | 1517 / 1461 / 1468 ms | 0.496 / 0.565 / 0.548 | 0.0% / 100% / 77.5% |
| Sarvam Bulbul v3 | 178 / 184 / 194 ms | 689 / 616 / 702 ms | 0.204 / 0.206 / 0.210 | 0.0% / 100% / 87.5% |

Timbre reached first audio sooner, while Bulbul completed full synthesis faster.
The corrected final matrix recorded no STT or TTS failures: 2,430 STT requests
and 120 TTS requests all returned audio or a transcript.

The Hindi round-trip scores are not a TTS ranking. Faster Whisper base often
returned Hindi speech in Perso-Arabic script, which the documented normalization
does not transliterate. Both providers therefore score 100% WER in Hindi even
when the generated speech is intelligible. English round-trip WER was 0% for
both providers. These measurements are STT proxies and do not replace listening
tests with native speakers.

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
