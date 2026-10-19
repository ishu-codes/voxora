# Voxora Web

React + TypeScript client for Voxora, a low-latency real-time voice agent. The
browser captures microphone audio, streams 20 ms PCM frames to the FastAPI
backend, renders live transcripts, and plays streamed speech the moment it
arrives.

## Run

```bash
pnpm install
cp .env.example .env
pnpm dev            # http://localhost:3000
```

The API defaults to `http://localhost:8000` (see `VITE_API_URL`). Start it with
`cd ../api && ./run.sh serve`.

```bash
pnpm build          # tsc + vite build
pnpm lint           # oxlint
```

## Routes

| Path | Page |
| --- | --- |
| `/` | Marketing landing page |
| `/app` | Voice studio (microphone + transcript + latency panel) |
| `/privacy`, `/terms` | Legal pages |

## How the client works

```
microphone ─ AudioWorklet (resample → 16 kHz PCM16, 20 ms frames) ─ WebSocket
                                                                      │
   Web Audio playback queue ◀── audio.chunk ──┐                        │
   Speech Synthesis queue   ◀── speak.chunk ──┴── server pipeline ◀────┘
```

- `src/voice/audio.ts` — `AudioCapture` (AudioWorklet resampler that emits
  fixed 20 ms frames) and `AudioPlayer` (gapless PCM queue on the Web Audio
  clock with instant `stop()`).
- `src/voice/speech.ts` — Web Speech API wrappers: streaming speech recognition
  for browser-side STT and sentence-chunk playback for browser-side TTS.
- `src/voice/useVoiceSession.ts` — the session state machine. Owns the socket,
  message list, agent state, reconnect backoff, local barge-in detection and
  latency bookkeeping.
- `src/voice/protocol.ts` — typed mirror of the backend WebSocket events.
- `src/components/voice/*` — microphone orb, transcript and latency panels.
- `src/pages/VoicePage.tsx` — composes the studio and the diagnostics drawer.

### Interruption

The client runs a lightweight local VAD on the same frames it sends. When the
user starts speaking during playback, the playback queue is stopped on that
frame (well under the 200 ms p95 target) and the current turn's audio is
suppressed. The backend VAD detects the same onset, cancels the LLM/TTS tasks
and emits `turn.cancelled`, so no stale audio can reappear.

### Metrics

Every turn records the server-side `e2e_first_audio_ms` plus client-measured
`first_playback_ms` (end of local speech to first audible chunk) and
`barge_in_ms`. The client reports them back with a `metrics` message; the
latency panel shows per-turn values and rolling p50/p95 for the session.
