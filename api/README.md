# Voxora extended benchmark

This harness evaluates the voice agent with recorded audio, classifier-based
semantic scoring, noise conditions, conversation scenarios, and a live demo.
Generated metrics live in [REPORT.md](REPORT.md) and
[NUMBERS.md](NUMBERS.md); this section documents how to reproduce
them.

## Benchmark package layout

- `src/bench/runners/` contains executable benchmark workflows and data generation.
- `src/bench/analysis/` derives reports, provider selections, and prompt decisions
  from saved results.
- `src/bench/evaluation/` contains deterministic scoring, STT metrics, and the
  classifier judge.
- `src/bench/providers/` contains STT, TTS, and LLM provider adapters.
- `src/bench/utils/` contains shared audio, normalization, and persistence helpers.
- `src/bench/datasets/` loads scenario, prompt, and utterance metadata.
- `src/bench/core/` owns typed configuration and path resolution.
- `src/bench/docs/` contains benchmark changelogs.

## Current results

- Clean and five degraded audio conditions each contain 225 provider/mode rows
  with zero recorded request errors.
- The official latency run contains 100 measured turns with zero failures after
  five discarded warmups.
- Training-scenario pass rates are 7/60 for v1, 43/60 for v2, 55/60 for v3,
  and 50/60 for v4. The selected final prompt is v3.
- Final classifier calibration measured 87.5% overall agreement, 88.0%
  conversation agreement, and no false passes. The held-out evaluation is
  complete.
- The held-out pass rate is 0/30 for v1 and 14/30 for the final prompt.
- Headline values and their report sources are in
  [NUMBERS.md](NUMBERS.md:1).

## Classifier usage

The benchmark uses `api/src/classification/classifier.py` with the model and endpoint
configured in `config.yaml`. It sends a text state and named questions in JSON.
Noul questions return a probability that the answer is true. Scenario judging
sends five questions per conversation: expected behaviors, forbidden behaviors,
fact accuracy, instruction leakage, and language mirroring. Instruction leakage
uses `yes=bad`; the other four use `yes=good`. STT semantic questions use
`yes=good`, as do entity questions. At most five questions are sent per call.

## Run speech-to-text

```bash
PYTHONPATH=src uv run python -m bench.runners.run_stt \
  --providers sarvam faster-whisper faster-whisper-nohint \
  --modes transcribe codemix translit \
  --wav-dir data/wav --condition clean
PYTHONPATH=src uv run python -m bench.analysis.best_providers
```

Faster Whisper uses the local `base` model, beam size five, `float16` on
available CUDA hardware, and `int8` on CPU. The model is cached under
`src/data/models/faster-whisper`. Sarvam and Faster Whisper use the same `en` or
`hi` language hint policy, followed by a separate no-hint Whisper condition.
The OpenAI Whisper API adapter remains available but is reported as not run
when `WHISPER_API_KEY` is absent.

WER and CER are calculated only when detected output script equals reference
script. Devanagari, Latin, mixed, and empty scripts are detected from Unicode
ranges. Non-comparable rows remain in results with `wer_comparable=false`.
Classifier semantic and entity metrics are calculated for all successful rows,
including cross-script output.

Entity annotations are stored in `src/data/utterances.csv`. Amount, date, and name
accuracy are the share of classifier entity questions answered true.

## Run noise tests

```bash
PYTHONPATH=src uv run python -m bench.runners.make_noisy
PYTHONPATH=src uv run python -m bench.runners.run_noise
```

The generator creates clean, phone, pink-noise at twenty, ten, and five dB SNR,
and three-speaker babble at ten dB SNR. It uses a fixed seed. Phone audio is
band-limited, mu-law round-tripped, and saved at 8 kHz. Sarvam is sent the 8 kHz
phone audio with a matching declared rate; Faster Whisper receives a 16 kHz
upsampled copy because the local model path normalizes it to 16 kHz.

## Run scenarios

```bash
PYTHONPATH=src uv run python -m bench.runners.run_scenarios --version v1 --runs 3
PYTHONPATH=src uv run python -m bench.runners.run_scenarios --version v2 --runs 3
PYTHONPATH=src uv run python -m bench.runners.run_scenarios --version v3 --runs 3
PYTHONPATH=src uv run python -m bench.runners.run_scenarios --version v4 --runs 3
PYTHONPATH=src uv run python -m bench.analysis.decisions
PYTHONPATH=src uv run python -m bench.runners.run_scenarios --heldout --runs 3
```

Prompts v1–v3 remain unchanged. `DECISIONS.md` applies the specified selection
rule and copies the winner to `prompts/agent_final.txt`. The training scenarios
were used to write the prompts. Held-out evaluation occurs only after
calibration is complete.

The forty-word, digit, markdown, and emoji checks remain deterministic. The
digit check covers every Unicode `Nd` digit. Prompt overlap is informational;
instruction leakage and language mirroring are classifier questions stored with
each conversation result. Diagnostic evidence is in `results/diagnostics/`.

## Run latency

```bash
PYTHONPATH=src uv run python -m bench.runners.run_latency
```

The official run discards five warmups and measures twenty-five mixed-language
utterances four times. Each audio stream is paced at real time in 100 ms chunks.
`t0` is the instant after the last audio chunk is sent.

- `stt_final_ms`: `t0` to final transcript.
- `llm_first_token_ms`: final transcript to first LLM token.
- `tts_first_audio_ms`: first complete sentence sent to TTS to first audio byte.
- `end_to_end_ms`: `t0` to first TTS audio byte.

The runner records the stage sum and flags turns whose difference exceeds fifty
milliseconds. The difference includes assembling the first complete sentence
after the first token and scheduling or network gaps between stages. A 100-turn
sample makes p95 depend on the five slowest turns.

## Run the demo

```bash
export DEMO_CODE=choose-a-passcode
PYTHONPATH=src uv run uvicorn demo.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The microphone is captured by an AudioWorklet,
downsampled to mono PCM16 at 16 kHz, sent over WebSocket, and played back with
the TTS sample rate. Speech onset stops playback and cancels the active turn.
Keys stay on the server. Sessions are capped at three minutes, with hourly
per-IP and daily session caps controlled by `DEMO_SESSIONS_PER_IP_HOUR` and
`DEMO_DAILY_SESSION_CAP`.

For Google Cloud Run, review `src/demo/deploy.sh`. It refuses to proceed without an
authenticated `gcloud` project, enables only one instance, keeps the request
timeout above the session cap, and reads secrets from Secret Manager.

```bash
chmod +x src/demo/deploy.sh
./src/demo/deploy.sh
```

## Limitations

- English, Hindi, and Hinglish cells contain fifteen training utterances each.
- There are twenty training scenarios and ten held-out scenarios, each run three
  times per prompt version.
- Official latency uses one hundred turns after five warmups.
- The classifier is a model. Human calibration measured 87.5% overall
  agreement, but the conversation sample contained no human failures, so the
  false-pass rate could not be estimated from that sample.
- Prompts were developed against the training scenarios, so their pass rate is a
  training score.
- No results cover real phone calls or concurrent users.
- Faster Whisper `base` is a small model and may underperform on code-mixed
  speech and Devanagari output.

## Assumptions

- The downloaded recordings in `src/data/wav` remain the source of truth.
- The machine has no CUDA-capable device, so Faster Whisper runs with `int8`.
- Optional Faster Whisper `small` is not run when the base benchmark already
  exceeds the available run window.
- An exact prompt-selection tie is resolved by choosing the earlier version
  identifier; this is recorded in `DECISIONS.md`.

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

## Abuse controls

Rate limits apply across WebSocket reconnects. The server HMACs the caller IP,
user agent and coarse browser signals into pseudonymous bucket keys; raw device
signals are not retained in logs. Shared-platform usage defaults to 10 queries
per rolling hour. The quota is enforced against both the device identity and
the caller IP, so changing a browser fingerprint does not reset the IP's
allowance. Every session also obeys connection, concurrency, provider-turn,
usage-budget and session-duration limits.

`ALLOWED_UNLIMITED` is a comma-separated list of IP addresses or CIDR ranges
that bypass rate limits. It is empty by default and should contain only trusted
operator addresses.

| Variable | Default | Meaning |
| --- | --- | --- |
| `RATE_LIMIT_ENABLED` | `true` | Enable cross-session abuse controls |
| `REQUIRE_BROWSER_CLIENT` | `true` | Reject curl, WebDriver and incomplete browser handshakes |
| `RATE_LIMIT_SECRET` | generated | HMAC key for device/IP fingerprints |
| `TRUST_PROXY_HEADERS` | `false` | Trust proxy-supplied client IP headers |
| `ALLOWED_UNLIMITED` | none | Comma-separated IPs/CIDRs that bypass all limits |
| `RATE_LIMIT_IDENTITY_ATTEMPTS_10M` | `5` | Connection attempts per identity |
| `RATE_LIMIT_IDENTITY_SESSIONS_HOUR` | `10` | Sessions per identity per hour |
| `RATE_LIMIT_PLATFORM_TURNS_HOUR` | `10` | Shared-key queries per device and IP per hour |
| `RATE_LIMIT_PLATFORM_TURNS_DAY` | `240` | Shared-key queries per device and IP per day |
| `RATE_LIMIT_STT_CHARS_HOUR` / `_DAY` | `30000` / `120000` | Final transcript characters |
| `RATE_LIMIT_LLM_CHARS_HOUR` / `_DAY` | `30000` / `120000` | Generated response characters |
| `RATE_LIMIT_LLM_TOKENS_HOUR` / `_DAY` | `8000` / `32000` | Approximate generated tokens |
| `RATE_LIMIT_TTS_CHARS_HOUR` / `_DAY` | `30000` / `120000` | Characters submitted to TTS |
| `RATE_LIMIT_MAX_CONCURRENT_IDENTITY` | `1` | Active sessions per identity |
| `RATE_LIMIT_MAX_SESSION_SECONDS` | `900` | Maximum WebSocket session duration |

The limiter is process-local. Multi-worker deployments should replace its
in-memory windows with Redis-backed atomic counters so limits are shared across
workers and survive restarts.

`REQUIRE_BROWSER_CLIENT=true` rejects missing origins, common command-line user
agents, WebDriver sessions and fingerprints without viewport/environment data.
This is an abuse deterrent, not cryptographic browser attestation: headers and
client signals can be spoofed. High-value deployments should add a Cloudflare
Turnstile or signed-attestation check during session bootstrap and retain the
server-derived IP quotas as a second layer.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/api/v1/voice/config` | Active providers and models (no secrets) |
| `GET` | `/api/v1/voice/voices` | Speakers supported by the configured Bulbul model |
| `GET` | `/api/v1/voice/metrics` | p50/p95/p99 per stage across recent turns |
| `DELETE` | `/api/v1/voice/metrics` | Reset the in-memory metrics registry |
| `WS` | `/api/v1/voice/ws` | Real-time voice session |

## Provider credentials

The backend uses credentials from its server environment. WebSocket clients
cannot replace Sarvam or LLM keys through a configure frame. The optional
`configure` frame supplies coarse browser signals for abuse controls, and audio
sent immediately after connecting is buffered briefly.

Backend sessions use the strict shared-platform limits above. The browser BYOK
path calls the user's providers directly and never opens the backend voice
socket, so it is not subject to the shared-platform query quota. When the free
quota is exhausted, the web client shows the reset time and a link to settings
for adding provider keys.

## Voice catalog

`GET /api/v1/voice/voices` returns the speaker list for the configured Bulbul
version, a valid default speaker, and the supported language codes. The browser
caches it for a day and sends `{"type":"voice","voice":"ritu"}` when the user
picks a different speaker. Voice names, gender, descriptions, model mappings,
languages, and cache metadata live in
`src/voice/catalog/voices.json`. The API validates and caches this file during
startup; restart the process after changing it.

## WebSocket protocol

Client → server

| Payload | Meaning |
| --- | --- |
| binary frame | 20 ms of 16 kHz mono PCM16 (640 bytes); send while the local VAD gate is open, or continuously when local VAD is unavailable |
| `{"type":"interrupt","reason":"manual","turn_id":"…"}` | Stop a specific turn; `turn_id` is optional, and a stale id is ignored |
| `{"type":"voice","voice":"ritu"}` | Select a Sarvam speaker for the rest of the session |
| `{"type":"metrics","turn_id":"…","metrics":{"first_playback_ms":512}}` | Client-measured playback latency |
| `{"type":"ping"}` | Keepalive |

Server → client

| Event | Meaning |
| --- | --- |
| `ready` | Session id, audio format, selected models, latency targets |
| `state` | `listening` / `thinking` / `speaking` |
| `audio.level` | Mic RMS for the level meter (throttled to 10 Hz) |
| `speech.start` | Server VAD detected the user speaking; fallback signal to stop playback when local VAD is unavailable |
| `transcript.partial` / `transcript.final` | Partial and final Sarvam transcripts |
| `audio.chunk` | Base64 PCM16 audio from Sarvam TTS; the first chunk of each sentence carries its spoken `text` |
| `assistant.done` | Full response text |
| `assistant.failed` / `turn.cancelled` / `turn.empty` | Turn outcomes |
| `turn.metrics` | Stage timings for the turn |
| `error` | Recoverable stage error (`stage`, `message`) |
| `pong` | Keepalive reply |

Audio chunks carry the `turn_id` that produced them. The browser drops any
chunk from a turn it has already cancelled, and the server checks both the
generation counter and the targeted turn id, so no stale audio is played.

## Pipeline behaviour

- **Streaming STT.** One Sarvam WebSocket is opened per session. The energy VAD
  sends `speech_start` when the user begins and pushes each subsequent 20 ms
  frame, so partial transcripts arrive while they speak. At `speech_end` the
  adapter finalises the utterance and returns the final transcript.
- **Endpointing.** `EnergyVAD` tracks an adaptive noise floor, keeps a 300 ms
  pre-roll, and ends a turn after ~650 ms of silence. All thresholds are env
  vars. The pre-roll is sent to Sarvam with the first frame of the utterance.
- **Barge-in.** Silero VAD runs in the browser with local `@ricky0123/vad-web`
  assets. Once speech onset is confirmed it stops playback immediately and sends
  `{"type":"interrupt","reason":"barge_in","turn_id":"…"}`. The server cancels
  that turn's outstanding LLM/TTS work and discards its TTS socket; an interrupt
  for an older turn is ignored, so late frames cannot cancel a newer reply. The
  server-side energy VAD remains the backstop when the browser VAD is unavailable
  or misses onset.
- **Overlap.** LLM tokens flow into a bounded queue (16 sentences); a separate
  task synthesises each sentence as it arrives, so synthesis overlaps
  generation. The Sarvam TTS socket is prewarmed when speech starts, then reused
  within a turn. Sentence text is attached to the first audio chunk so the
  browser can reveal it when playback actually begins.
- **Backpressure.** The socket writer is a bounded queue. Audio and level
  events are dropped when a slow client saturates it; control events wait
  briefly and are counted as dropped rather than blocking inference.
- **History.** The last `MAX_HISTORY_MESSAGES` messages of the session are sent
  with every request, so follow-ups work. History is in memory per connection.
- **Abuse controls.** IP and device windows span reconnects, and the server
  blocks additional concurrent sessions before providers are initialized.

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
  turn advances a generation counter that drops late output. Interrupts name the
  turn they target, so a delayed barge-in cannot cancel a newer reply. Sarvam has
  no server-side TTS cancel, so an interrupted socket is discarded before the
  next reply.
- **Per-session accounting.** Each session logs turn count, dropped events and
  runtime on close; `GET /api/v1/voice/metrics` aggregates latency across turns.
- **No raw audio logging.** Logs and metric records contain identifiers,
  timings and text — never audio samples.
- **Secrets are not exposed.** Provider keys stay in the server environment.
  WebSocket clients cannot supply replacement provider keys.

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
PYTHONPATH=src python -m scripts.benchmark --wav sample_16k_mono.wav --turns 10 --server-metrics
```

Report results together with the Sarvam model, LLM model, network conditions and
whether the run was warm or cold — the numbers only mean something in context.

## Tests

```bash
./run.sh test          # or: .venv/bin/python -m pytest -q
```

The suite covers the sentence chunker, VAD endpointing, full pipeline turns,
streaming partials, turn-targeted barge-in cancellation, stale interrupt
handling, provider failures, metrics aggregation and provider construction. It
needs no network or API keys; Sarvam sockets are replaced with in-memory fakes.

## Layout

```
src/
  bench/             # benchmark providers, runners, scoring, and reports
  classification/    # conversation classifier client
  data/              # recordings, transcripts, and scenarios
  demo/              # benchmark demo and deployment assets
  prompts/           # agent and classifier prompts
  results/           # generated benchmark results
  scripts/
    benchmark.py     # reproducible latency + interruption benchmark
  tests/             # backend and benchmark tests
  tools/             # calibration and recording utilities
  voice/
    audio/
      processing.py  # PCM helpers without numpy
      sentence.py    # token stream -> speakable phrases
      vad.py         # VAD protocol + EnergyVAD
    catalog/
      voices.py      # validated runtime catalog loader
      voices.json    # voice, model, language, and cache metadata
    controller/
      router.py      # FastAPI HTTP and WebSocket endpoints
    core/
      config.py      # environment-driven settings
      metrics.py     # latency registry + percentiles
    providers/
      base.py        # provider protocols and errors
      stt.py         # Sarvam Saaras streaming STT
      llm.py         # OpenAI-compatible streaming LLM + demo responder
      tts.py         # Sarvam Bulbul streaming TTS
    runtime/
      pipeline.py    # cancellable VAD -> STT -> LLM -> TTS orchestration
      session.py     # per-connection history
      transport.py   # bounded WebSocket writer + test transport
    security/
      rate_limit.py  # identity, connection, usage, and session limits
    services/
      provider_bundle.py # provider construction and lifecycle
      voice.py           # configuration, session, and control-frame services
config.yaml          # benchmark configuration
main.py              # FastAPI application entry point
```
