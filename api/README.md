# Voxora API

FastAPI backend for Voxora, a low-latency streaming voice agent. It owns
session orchestration, voice activity detection, turn cancellation, provider
selection and latency metrics. STT, LLM and TTS are adapters behind small
protocols, so a stage can be swapped without touching the pipeline.

```
browser mic/16 kHz PCM ──WebSocket──▶ VAD ──▶ STT ──▶ LLM ──▶ TTS ──▶ audio/text events
                                        ▲                          │
                                        └──── barge-in cancels ◀────┘
```

## Quick start

```bash
uv sync --group dev --extra dev
cp .env.example .env
./run.sh serve          # or ./run.sh dev for hot reload
```

The service starts with **zero keys**:

| Stage | Zero-key default | With keys / local models |
| --- | --- | --- |
| STT | browser Web Speech recogniser | `STT_PROVIDER=openai` or `faster-whisper` |
| LLM | built-in demo responder | `LLM_PROVIDER=openai`/`ollama`/`groq` |
| TTS | browser Web Speech synthesis | `TTS_PROVIDER=openai` |

`auto` selection prefers a hosted key when present, then a locally installed
`faster-whisper` model, then the browser. Every choice is reported on the
`ready` event and at `/api/v1/voice/config`.

### Using a real model

```bash
# OpenAI (or any OpenAI-compatible gateway)
export OPENAI_API_KEY=sk-...
# Local models with Ollama
export LLM_PROVIDER=ollama LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=llama3.2 LLM_API_KEY=ollama
# Local speech recognition
uv sync --extra stt
export STT_PROVIDER=faster-whisper WHISPER_MODEL=base
```

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/api/v1/voice/config` | Active providers and targets (no secrets) |
| `GET` | `/api/v1/voice/metrics` | p50/p95/p99 per stage across recent turns |
| `DELETE` | `/api/v1/voice/metrics` | Reset the in-memory metrics registry |
| `WS` | `/api/v1/voice/ws` | Real-time voice session |

## WebSocket protocol

Client → server

| Payload | Meaning |
| --- | --- |
| binary frame | 20 ms of 16 kHz mono PCM16 (640 bytes); send continuously while the session is open |
| `{"type":"transcript","text":"…","final":true}` | Final transcript from browser-side STT (browser mode only) |
| `{"type":"transcript","text":"…","final":false}` | Interim transcript |
| `{"type":"interrupt","reason":"manual"}` | Stop the current turn |
| `{"type":"metrics","turn_id":"…","metrics":{"first_playback_ms":512}}` | Client-measured playback latency |
| `{"type":"ping"}` | Keepalive |

Server → client

| Event | Meaning |
| --- | --- |
| `ready` | Session id, audio format, selected providers, latency targets |
| `state` | `listening` / `thinking` / `speaking` |
| `audio.level` | Mic RMS for the level meter (throttled to 10 Hz) |
| `speech.start` | VAD detected the user speaking; the browser must stop playback |
| `transcript.partial` / `transcript.final` | Recognised user speech |
| `assistant.delta` | Incremental response tokens |
| `speak.chunk` / `speak.end` | Sentence chunks for browser TTS |
| `audio.chunk` | Base64 PCM16 audio from a server-side TTS provider |
| `assistant.done` | Full response text |
| `assistant.failed` / `turn.cancelled` / `turn.empty` | Turn outcomes |
| `turn.metrics` | Stage timings for the turn |
| `error` | Recoverable stage error (`stage`, `message`) |
| `pong` | Keepalive reply |

Audio chunks carry the `turn_id` that produced them. The browser drops any
chunk from a turn it has already cancelled, and the server stops emitting once
the generation counter advances, so no stale audio is played.

## Pipeline behaviour

- **Endpointing.** `EnergyVAD` tracks an adaptive noise floor, keeps a 300 ms
  pre-roll, and ends a turn after ~650 ms of silence. All thresholds are env
  vars.
- **Barge-in.** The first voiced frame of a new utterance cancels the running
  turn: outstanding LLM/TTS work is cancelled, `turn.cancelled` is emitted and
  the browser stops playback on `speech.start`. Cancellation propagates through
  `asyncio` tasks, so it is immediate even while the LLM is mid-stream.
- **Overlap.** LLM tokens flow into a bounded queue (16 sentences); a separate
  task synthesises each sentence as it arrives, so synthesis overlaps
  generation.
- **Backpressure.** The socket writer is a bounded queue. Audio and level
  events are dropped when a slow client saturates it; control events wait
  briefly and are counted as dropped rather than blocking inference.
- **History.** The last `MAX_HISTORY_MESSAGES` messages of the session are sent
  with every request, so follow-ups work. History is in memory per connection.

## Latency metrics

`GET /api/v1/voice/metrics` returns counts plus p50/p95/p99 for
`speech_duration_ms`, `stt_ms`, `llm_first_token_ms`, `tts_first_audio_ms`,
`e2e_first_audio_ms`, `total_ms`, and (after the browser reports them)
`first_playback_ms` and `barge_in_ms`. The browser reports its own user-perceived
timings, which is the number that matters: server metrics alone miss transport
and playback scheduling.

## Benchmarking

`scripts/benchmark.py` drives a real WebSocket session and reports
end-of-speech to first-audio latency (client monotonic clock) plus interruption
latency, in the p50/p95/p99 form the PRD asks for:

```bash
./run.sh bench --url ws://127.0.0.1:8000/api/v1/voice/ws --turns 10 --barge-in
python -m scripts.benchmark --turns 5 --wav sample_16k_mono.wav   # replay real speech
python -m scripts.benchmark --turns 10 --server-metrics           # compare with stage metrics
```

Without `--wav` the script sends synthetic tone frames and supplies the
transcript itself, which measures the generation and synthesis path in
browser-STT mode. Pass a 16 kHz mono WAV to exercise a server-side STT adapter.
Report results together with the model configuration, network conditions and
whether the run was warm or cold — the numbers only mean something in context.

## Tests

```bash
./run.sh test          # or: .venv/bin/python -m pytest -q
```

The suite covers the sentence chunker, VAD endpointing, full pipeline turns,
barge-in cancellation, provider failures, metrics aggregation and provider
selection. It needs no database, network or API keys.

## Layout

```
src/voice/
  config.py          # env-driven settings
  audio.py           # PCM helpers (no numpy)
  vad.py             # VAD protocol + EnergyVAD
  sentence.py        # token stream -> speakable phrases
  metrics.py         # latency registry + percentiles
  session.py         # per-connection history
  transport.py       # bounded WebSocket writer + test transport
  pipeline.py        # cancellable VAD -> STT -> LLM -> TTS orchestration
  router.py          # FastAPI routes and socket loop
  providers/         # base protocols + STT/LLM/TTS adapters
scripts/
  benchmark.py       # reproducible latency + interruption benchmark
```
