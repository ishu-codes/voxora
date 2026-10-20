This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Voice client

Barge-in uses Silero VAD locally through `@ricky0123/vad-web`. `pnpm dev` and
`pnpm build` copy the model, AudioWorklet and ONNX Runtime WASM into
`public/vad/` before Next.js starts; the directory is generated and not
committed. If the model cannot load, the session keeps streaming audio and
falls back to server-side VAD.

Tuning variables: `NEXT_PUBLIC_VAD_MIN_SPEECH_MS` (confirmed onset, default
200), `NEXT_PUBLIC_VAD_REDEMPTION_MS` (end-of-speech silence, default 650),
`NEXT_PUBLIC_VAD_PRE_SPEECH_PAD_MS` (pre-roll, default 500),
`NEXT_PUBLIC_VAD_POSITIVE_THRESHOLD`, `NEXT_PUBLIC_VAD_PLAYBACK_THRESHOLD` and
`NEXT_PUBLIC_VAD_NEGATIVE_THRESHOLD`.

The `/app` session is owned by `web/src/voice/voice-session-provider.tsx`, so
every child under that layout reads the same connection, transcript and playback
state. Transcript messages are persisted to `sessionStorage` with Zustand and
can be cleared from the conversation panel. If the microphone track ends, mutes,
or stops producing frames — including after a tab or device suspension — the
client reacquires the device and restarts local VAD without dropping the
WebSocket. If Silero misses speech, a sustained-energy fallback opens the audio
gate so the utterance still reaches STT. The bar visualizer reflects
connecting, initializing, listening, speaking and thinking states, and resumes
its analyser after the page becomes visible again. Assistant text is revealed
when the corresponding sentence's first audio chunk begins playback, rather
than when the LLM token arrives.

When both a Sarvam key and an OpenAI-compatible endpoint are configured, the
browser uses the direct BYOK path: Sarvam STT/TTS and the LLM are requested
without opening the Voxora backend voice socket. Provider keys therefore remain
in the browser, but direct LLM endpoints must include the web origin in their
CORS policy. Platform-trial sessions continue through the backend and are
subject to cross-session rate and usage limits.

```bash
pnpm test        # interruption, PCM conversion and transcript persistence
pnpm typecheck
pnpm lint
```

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
