# Voxora architecture

## What Voxora is

Voxora is a real-time voice assistant.

You speak into a browser. The browser captures your voice, detects when a turn
starts and ends, turns speech into text, sends the text to a language model, and
plays the generated answer as speech.

Audio and text move in small pieces. The app does not wait for a complete
recording or a complete answer before it starts working.

The project has two runtime modes:

1. The platform trial uses Voxora's backend and shared provider keys.
2. BYOK uses the user's own provider keys and calls providers from the browser.

## Main parts

```text
Browser
  microphone capture
  local voice detection
  playback and barge-in
        |
        | platform trial
        v
FastAPI backend
  WebSocket session
  server voice detection
  speech to text
  language model
  text to speech
  rate limits
        |
        v
Sarvam and an OpenAI-compatible model
```

The web app is in `web/`. The voice API is in `api/`.

## Platform trial path

The browser opens a WebSocket at `/api/v1/voice/ws`.

The backend checks the browser handshake, the client fingerprint, connection
limits, session limits, and usage limits. If the request is allowed, the backend
opens one voice session.

For each user turn, the backend does this work:

1. It receives 16 kHz mono PCM16 audio in 20 ms frames.
2. `EnergyVAD` finds the start and end of speech.
3. `SarvamSTT` sends speech to Sarvam and receives partial and final text.
4. `OpenAICompatibleLLM` streams response tokens.
5. `SentenceChunker` groups tokens into speakable sentences.
6. `SarvamTTS` turns each sentence into PCM16 audio.
7. `QueueTransport` sends audio chunks to the browser over the same WebSocket.

The language model and speech synthesis run at the same time. Speech synthesis
starts when the first sentence is ready, not after the full answer is ready.

The backend starts the Sarvam TTS socket when the user starts speaking. This
removes the TTS connection handshake from the first reply.

## BYOK path

When the browser has both a Sarvam key and an OpenAI-compatible endpoint, it
uses the direct BYOK path.

```text
Browser
  microphone frames
        |
        v
Sarvam speech-to-text REST API
        |
        v
User-configured LLM endpoint
        |
        v
Browser sentence chunker
        |
        v
Sarvam text-to-speech REST API
        |
        v
Browser audio playback
```

The browser does not open the Voxora backend voice WebSocket in this mode.
Provider requests go directly from the browser to the providers.

The direct path stores provider keys in browser local storage. The keys appear
in browser network requests. The LLM endpoint must allow the web origin through
CORS.

The direct path has no backend rate limits. Usage is limited by the user's
provider account.

The current direct STT request runs after a speech turn ends. It does not show
partial transcripts while the user speaks.

## Audio capture

`AudioCapture` in `web/src/voice/audio.ts` gets the microphone stream.

It uses an `AudioWorklet` to resample native audio to 16 kHz and create 320
sample PCM16 frames. Each frame represents 20 ms.

If the worklet does not produce frames, capture falls back to
`ScriptProcessor`. The worklet also falls back when the browser does not support
AudioWorklet.

Capture starts only after the browser produces its first real audio frame.
A watchdog rebuilds the graph if the track ends or frames stop.

Muting does three things:

1. It disables the microphone track.
2. It pauses local voice detection.
3. It clears buffered audio and blocks new transcription.

## Local voice detection

`LocalVad` in `web/src/voice/vad.ts` uses Silero through
`@ricky0123/vad-web`.

Silero decides when speech starts and ends. A pre-roll buffer keeps the first
part of the utterance. When speech is confirmed, the browser sends the buffered
audio and then sends live frames.

A sustained-energy fallback opens the audio gate if Silero misses speech. The
server-side `EnergyVAD` remains the final fallback for platform sessions.

The browser keeps the audio gate closed while waiting for voice detection. This
prevents silence from filling the network connection.

## Text and speech timing

The backend attaches the spoken sentence to the first audio chunk for that
sentence.

The browser queues the audio on the Web Audio clock. It reveals the sentence
text when that audio becomes audible. The reveal waits for the audio context to
run and accounts for output latency.

This keeps the transcript close to what the user hears. A long sentence still
appears as one text block at the start of the sentence. The text and voice do
not synchronize word by word.

If a short audio chunk ends before its reveal time, the reveal stays scheduled.
An explicit stop still cancels it.

## Barge-in

Barge-in means the user starts speaking while the assistant is talking.

The browser stops playback as soon as local VAD confirms speech. It sends a
turn-targeted interrupt for platform sessions. For BYOK sessions, it aborts the
active browser fetch requests.

The backend tracks a generation number and a turn id. A late event from an old
turn cannot cancel a newer turn or play stale audio.

The backend also has an energy VAD fallback. If the browser misses speech, the
server can detect it and cancel the response.

## Conversations

The transcript is stored in browser `sessionStorage`.

The history is available after a page refresh in the same tab. Closing the tab
clears it.

Platform sessions keep conversation history in server memory for the lifetime of
the WebSocket. The server sends recent history with each LLM request.

BYOK sessions build the conversation history in the browser and send it directly
to the configured LLM endpoint.

Provider keys are stored separately in browser local storage by the settings
page.

## Rate limits and abuse controls

Platform sessions use strict limits across reconnects.

The server builds a pseudonymous identity from the client IP, user agent, and
coarse browser signals. It hashes the values with HMAC using
`RATE_LIMIT_SECRET`.

The server does not log the raw browser fingerprint.

The default limits cover:

1. Connection attempts.
2. Sessions per hour and per day.
3. One active session per device identity.
4. Maximum session duration.
5. Platform turns.
6. STT transcript characters.
7. LLM response characters and approximate tokens.
8. TTS input characters.

The browser gate rejects missing origins, common command-line user agents,
WebDriver sessions, and incomplete browser fingerprints.

The gate is a deterrent. A client can spoof headers and JSON. Strong browser
attestation requires a service such as Cloudflare Turnstile or signed
attestation from a trusted bootstrap endpoint.

The rate limiter currently runs in one API process and uses memory. It resets on
restart and does not share counters between workers. A multi-worker deployment
needs Redis or another shared atomic store.

## Privacy boundaries

The platform path sends audio and conversation text through the Voxora backend.
The server then sends speech text to Sarvam and sends conversation messages to
the configured LLM.

The BYOK path sends provider requests directly from the browser. Voxora does not
receive the audio or provider credentials on the backend voice socket.

The browser still requests the voice catalog from the Voxora API. That request
does not include provider keys or conversation data.

The backend logs session state, timings, transcript text, and provider events
according to `LOG_LEVEL`. It does not log raw audio samples.

## Configuration

`NEXT_PUBLIC_API_URL` sets the backend URL for the web app.

The frontend reads it for catalog requests and converts the scheme to `ws` or
`wss` for platform voice sessions.

The backend reads provider settings and rate limits from environment variables.
`api/.env.example` documents the supported values.

## Main source files

| Area | File |
| --- | --- |
| Page layout and controls | `web/src/app/app/page.tsx` |
| Voice session state | `web/src/voice/useVoiceSession.ts` |
| Microphone and playback | `web/src/voice/audio.ts` |
| Local VAD | `web/src/voice/vad.ts` |
| Direct BYOK calls | `web/src/voice/byok.ts` |
| Wire protocol | `web/src/voice/protocol.ts` |
| HTTP and WebSocket endpoints | `api/src/voice/controller/router.py` |
| Voice application services | `api/src/voice/services/voice.py` |
| Provider construction and ownership | `api/src/voice/services/provider_bundle.py` |
| Voice catalog metadata | `api/src/voice/catalog/voices.json` |
| Turn pipeline | `api/src/voice/runtime/pipeline.py` |
| Sarvam adapters | `api/src/voice/providers/stt.py` and `api/src/voice/providers/tts.py` |
| LLM adapter | `api/src/voice/providers/llm.py` |
| Rate limits | `api/src/voice/security/rate_limit.py` |
| Settings | `api/src/voice/core/config.py` |

## Current limits

The project is a single-process prototype.

It has no accounts, database, or shared rate-limit store.

The platform voice socket and rate limits must move to a shared store before
running multiple API workers.

The direct BYOK path depends on provider CORS policies.

The browser client cannot set custom WebSocket headers. BYOK therefore uses
Sarvam REST endpoints for STT and TTS instead of the Sarvam streaming
WebSockets.
