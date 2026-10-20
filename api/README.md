# Voxora API

FastAPI backend for Voxora, a low-latency streaming voice agent. It owns
session orchestration, voice activity detection, turn cancellation and latency
metrics. Speech recognition and synthesis use Sarvam's streaming WebSocket
models; the language model is any OpenAI-compatible endpoint.

```
browser mic/16 kHz PCM ──WebSocket──▶ VAD ──▶ Sarvam STT ──▶ LLM ──▶ Sarvam TTS ──▶ audio/text events
                                        ▲                                          │
                                        └──── barge-in cancels ◀──────────────────┘
```

## Quick start

```bash
uv sync --group dev
cp .env.example .env
# Put your Sarvam key in .env
./run.sh serve          # or ./run.sh dev for hot reload
```

The speech stages require a Sarvam key:

```bash
export SARVAM_API_KEY=sk_...
```

The LLM needs a key too unless you use Ollama or the demo responder:

```bash
# DeepSeek (or any OpenAI-compatible gateway)
export LLM_BASE_URL=https://api.deepseek.com
export LLM_MODEL=deepseek-chat
export LLM_API_KEY=sk-...

# Local models with Ollama
export LLM_PROVIDER=ollama LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=llama3.2 LLM_API_KEY=ollama
```

Without an LLM key the backend uses a small demo responder so you can exercise
audio capture, VAD, barge-in and playback. The speech stages always call Sarvam.

## Sarvam configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `SARVAM_API_KEY` | — | Sarvam subscription key |
| `SARVAM_WS_URL` | `wss://api.sarvam.ai` | Sarvam WebSocket origin |
| `STT_MODEL` | `saaras:v3-realtime` | Saaras realtime model |
| `STT_LANGUAGE` | `en-IN` | BCP-47 code or `auto` |
| `STT_STREAM_TYPE` | `fast` | `fast`, `balanced` or `simulated` |
| `STT_MODE` | `transcribe` | `transcribe`, `translate`, `verbatim`, `translit` or `codemix` |
| `TTS_MODEL` | `bulbul:v3` | Bulbul streaming model |
| `TTS_VOICE` | `shubh` | Speaker; must match the model |
| `TTS_LANGUAGE` | `en-IN` | BCP-47 language code |
| `TTS_SAMPLE_RATE` | `22050` | `8000`, `16000`, `22050` or `24000` |
| `TTS_SPEED` | `1.0` | Sarvam `pace` |
| `TTS_TEMPERATURE` | `0.6` | Bulbul v3/v4 only |

Sarvam STT accepts PCM16 mono at 16 kHz, which is also the format the browser
sends. Sarvam TTS is configured for `linear16` output, so audio chunks go
straight to the browser without a decode step.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/api/v1/voice/config` | Active providers and models (no secrets) |
| `GET` | `/api/v1/voice/voices` | Speakers supported by the configured Bulbul model |
| `GET` | `/api/v1/voice/metrics` | p50/p95/p99 per stage across recent turns |
| `DELETE` | `/api/v1/voice/metrics` | Reset the in-memory metrics registry |
| `WS` | `/api/v1/voice/ws` | Real-time voice session |

## Bring-your-own keys

The server can run on shared platform keys with a per-session trial
(`PLATFORM_MAX_TURNS`, default 20). A browser may instead send a `configure`
frame as the first WebSocket message:

```json
{
  "type": "configure",
  "byok": {
    "sarvam_api_key": "sk_...",
    "openai_api_key": "sk-...",
    "openai_base_url": "https://api.deepseek.com",
    "openai_model": "deepseek-chat"
  }
}
```

Keys are held in memory for that socket only and are never logged. Supplying
both a Sarvam key and an OpenAI-compatible endpoint removes the trial limit.
Audio sent before the `configure` frame is buffered briefly, so capture can
start immediately.

## Voice catalog

`GET /api/v1/voice/voices` returns the speaker list for the configured Bulbul
version, a valid default speaker, and the supported language codes. The browser
caches it for a day and sends `{"type":"voice","voice":"ritu"}` when the user
picks a different speaker.

## WebSocket protocol

Client → server

| Payload | Meaning |
| --- | --- |
| binary frame | 20 ms of 16 kHz mono PCM16 (640 bytes); send continuously while the session is open |
| `{"type":"interrupt","reason":"manual"}` | Stop the current turn |
| `{"type":"voice","voice":"ritu"}` | Select a Sarvam speaker for the rest of the session |
| `{"type":"metrics","turn_id":"…","metrics":{"first_playback_ms":512}}` | Client-measured playback latency |
| `{"type":"ping"}` | Keepalive |

Server → client

| Event | Meaning |
| --- | --- |
| `ready` | Session id, audio format, selected models, latency targets |
| `state` | `listening` / `thinking` / `speaking` |
| `audio.level` | Mic RMS for the level meter (throttled to 10 Hz) |
| `speech.start` | VAD detected the user speaking; the browser must stop playback |
| `transcript.partial` / `transcript.final` | Partial and final Sarvam transcripts |
| `assistant.delta` | Incremental response tokens |
| `audio.chunk` | Base64 PCM16 audio from Sarvam TTS |
| `assistant.done` | Full response text |
| `assistant.failed` / `turn.cancelled` / `turn.empty` | Turn outcomes |
| `turn.metrics` | Stage timings for the turn |
| `error` | Recoverable stage error (`stage`, `message`) |
| `pong` | Keepalive reply |

Audio chunks carry the `turn_id` that produced them. The browser drops any
chunk from a turn it has already cancelled, and the server stops emitting once
the generation counter advances, so no stale audio is played.

## Pipeline behaviour

- **Streaming STT.** One Sarvam WebSocket is opened per session. The energy VAD
  sends `speech_start` when the user begins and pushes each subsequent 20 ms
  frame, so partial transcripts arrive while they speak. At `speech_end` the
  adapter finalises the utterance and returns the final transcript.
- **Endpointing.** `EnergyVAD` tracks an adaptive noise floor, keeps a 300 ms
  pre-roll, and ends a turn after ~650 ms of silence. All thresholds are env
  vars. The pre-roll is sent to Sarvam with the first frame of the utterance.
- **Barge-in.** The first voiced frame of a new utterance cancels the running
  turn: outstanding LLM/TTS work is cancelled, the TTS socket is discarded,
  `turn.cancelled` is emitted and the browser stops playback on `speech.start`.
- **Overlap.** LLM tokens flow into a bounded queue (16 sentences); a separate
  task synthesises each sentence as it arrives, so synthesis overlaps
  generation. The Sarvam TTS socket is reused within a turn.
- **Backpressure.** The socket writer is a bounded queue. Audio and level
  events are dropped when a slow client saturates it; control events wait
  briefly and are counted as dropped rather than blocking inference.
- **History.** The last `MAX_HISTORY_MESSAGES` messages of the session are sent
  with every request, so follow-ups work. History is in memory per connection.

## Logging

Every session is tagged with its short id (`session=1a2b3c4d`) so concurrent
conversations stay separable. Each stage logs at two levels:

- `INFO` — socket connect/close and the client address, the optional `configure`
  frame (booleans and model names only, never keys), VAD speech start/end,
  Sarvam STT connection and final transcript with latency, the LLM request
  (provider, model, endpoint, message count) and the full reply, TTS connection
  and per-sentence request/completion, first audio delivered to the client, and
  per-turn chunk/byte totals.
- `DEBUG` — raw Sarvam frames, partial transcripts, every uploaded PCM frame and
  every synthesised chunk, outbound WebSocket events, and dropped frames. Set
  `LOG_LEVEL=DEBUG` for frame-level tracing.

Audio samples are never logged, and API keys are never logged. Transcripts, LLM
replies and TTS text are logged at `INFO`, so treat production logs as sensitive
user data and set `LOG_LEVEL=WARNING` if that is not acceptable.

## Reliability, scaling and privacy

- **Session isolation.** Each conversation gets its own Sarvam STT and TTS
  sockets. Provider failures are caught per turn (`ProviderError`) and per
  connection, so one conversation's errors never surface in another.
- **Bounded buffering.** The sentence hand-off queue is capped at 16 items and
  the socket writer at `MAX_OUTPUT_QUEUE`. Overflow drops audio rather than
  growing memory.
- **Timeouts and cancellation.** Every stage is cancellable through the turn's
  `asyncio` task. STT finalisation and TTS streams have hard timeouts, and each
  turn advances a generation counter that drops late output. Sarvam has no
  server-side TTS cancel, so an interrupted socket is discarded before the next
  reply.
- **Per-session accounting.** Each session logs turn count, dropped events and
  runtime on close; `GET /api/v1/voice/metrics` aggregates latency across turns.
- **No raw audio logging.** Logs and metric records contain identifiers,
  timings and text — never audio samples.
- **Secrets are not exposed.** Platform keys stay in the server environment.
  Browser-supplied BYOK keys live only in that socket's private provider bundle,
  are never written to disk, and are never included in `/config` or logs.

Before a public deployment, add authentication, per-user rate limits and TLS
(WebSocket `wss://`); these are intentionally out of scope for this MVP.

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
latency. Replay a 16 kHz mono WAV so Sarvam receives real speech:

```bash
./run.sh bench --wav sample_16k_mono.wav --turns 10 --barge-in
python -m scripts.benchmark --wav sample_16k_mono.wav --turns 10 --server-metrics
```

Report results together with the Sarvam model, LLM model, network conditions and
whether the run was warm or cold — the numbers only mean something in context.

## Tests

```bash
./run.sh test          # or: .venv/bin/python -m pytest -q
```

The suite covers the sentence chunker, VAD endpointing, full pipeline turns,
streaming partials, barge-in cancellation, provider failures, metrics
aggregation and provider construction. It needs no network or API keys; Sarvam
sockets are replaced with in-memory fakes.

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
  providers/
    base.py          # provider protocols and errors
    stt.py           # Sarvam Saaras streaming STT
    llm.py           # OpenAI-compatible streaming LLM + demo responder
    tts.py           # Sarvam Bulbul streaming TTS
scripts/
  benchmark.py       # reproducible latency + interruption benchmark
```
