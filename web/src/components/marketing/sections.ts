/**
 * Single source of truth for Voxora marketing copy.
 * No JSX file should contain literal marketing text.
 */

export const ANNOUNCEMENT_STRIP = {
  left: "Voxora is live — no sign-up, just talk.",
  right: [
    { label: "First audio p50", value: "≤ 700 ms" },
    { label: "Barge-in p95", value: "≤ 200 ms" },
    { label: "Pipeline", value: "STT → LLM → TTS" },
  ],
};

export const HERO_COPY = {
  kicker: "//from speech to intelligence, in real time.",
  headline1: "Talk to AI.",
  headline2: "Hear it think.",
  subhead:
    "Voxora streams your microphone through speech recognition, a language model and speech synthesis — overlapping every stage so the answer starts playing before it has finished being written.",
  primary: { label: "Start a conversation", to: "/app" },
  secondary: { label: "See how it works", href: "#pipeline" },
};

export const PIPELINE_COPY = {
  heading: "//a pipeline you can cancel.",
  subhead:
    "Audio is never uploaded as a finished recording. The browser sends 20 ms PCM frames, the server endpoints your turn with VAD, and each stage hands off incrementally so latency compounds only once.",
};

export const PIPELINE_TERMINAL = {
  command: "wscat -c ws://localhost:8000/api/v1/voice/ws",
  body: `{"type":"ready","stt":"whisper","llm":"llama3.2","tts":"pcm24k"}`,
  stream: [
    `{"type":"speech.start","turn_id":"a1f3-1"}`,
    `{"type":"transcript.final","text":"How does a database index work?"}`,
    `{"type":"assistant.delta","text":"A database index is "}`,
    `{"type":"assistant.delta","text":"a data structure that "}`,
    `{"type":"audio.chunk","turn_id":"a1f3-1","sample_rate":24000}`,
    `{"type":"turn.metrics","e2e_first_audio_ms":612}`,
  ],
};

export const STREAMING_COPY = {
  heading: "//stop waiting for whole recordings.",
  subhead:
    "A blocking voice UI records, uploads, transcribes and synthesises before you hear anything. Voxora starts speaking from the first generated sentence.",
  without: {
    label: "Blocking pipeline",
    answer:
      "Records the entire utterance · uploads it · transcribes the whole file · waits for the full LLM answer · synthesises every word · then plays. You listen to silence for seconds.",
    badges: ["full upload", "no overlap", "no barge-in"],
  },
  with: {
    label: "Voxora streaming",
    answer:
      "Frames stream while you speak · VAD endpoints the turn · tokens flow into sentence chunks · speech starts on the first clause · a new utterance cancels everything in flight.",
    badges: ["streaming", "cancelable", "0 stale chunks"],
  },
};

export const CAPABILITIES_COPY = {
  heading: "Hello, Voxora.",
  subhead:
    "Every stage is a small interface, so you can swap models without touching the pipeline.",
  items: [
    {
      num: "01",
      title: "Streaming speech recognition",
      command: "STT_PROVIDER=gnani|sarvam|faster-whisper",
      description:
        "Audio frames flow continuously. Partial transcripts update the UI while the turn is still open.",
    },
    {
      num: "02",
      title: "VAD endpointing",
      command: "VAD_END_SILENCE_MS=650",
      description:
        "An adaptive energy detector with pre-roll decides when you have finished speaking.",
    },
    {
      num: "03",
      title: "Token-level LLM streaming",
      command: "LLM_PROVIDER=ollama",
      description:
        "Any OpenAI-compatible endpoint works: hosted APIs, Ollama, vLLM or llama.cpp.",
    },
    {
      num: "04",
      title: "Sentence-buffered TTS",
      command: "TTS_PROVIDER=openai",
      description:
        "Tokens are grouped into speakable clauses and synthesised while generation continues.",
    },
    {
      num: "05",
      title: "Barge-in cancellation",
      command: "reason: barge_in",
      description:
        "Speaking mid-answer cancels the LLM and TTS tasks instantly. No stale audio is ever played.",
    },
    {
      num: "06",
      title: "Browser playback queue",
      command: "Web Audio + 20 ms frames",
      description:
        "PCM chunks are scheduled on the audio clock so speech joins gaplessly and stops on one frame.",
    },
    {
      num: "07",
      title: "Latency you can see",
      command: "GET /api/v1/voice/metrics",
      description:
        "Per-stage timings, p50/p95/p99 summaries, and client-measured first-audio and barge-in latency.",
    },
  ],
};

export const DEPLOYMENT_COPY = {
  heading: "Run it your way.",
  subhead:
    "Every provider is configuration, not code. Mix hosted and local stages per deployment.",
};

export const DEPLOYMENTS = [
  {
    name: "Local",
    price: "Self-hosted",
    period: "",
    description: "Nothing leaves your machine.",
    features: [
      "faster-whisper speech recognition",
      "Ollama or llama.cpp for generation",
      "Piper or browser speech synthesis",
      "Metrics endpoint on localhost",
    ],
    cta: "Start talking",
    to: "/app",
    highlight: false,
  },
  {
    name: "Hosted",
    price: "API keys",
    period: "",
    description: "Lowest setup, fastest first audio.",
    features: [
      "Hosted Whisper transcription",
      "Streaming chat completions",
      "Hosted PCM text-to-speech",
      "Keys stay on the server",
    ],
    cta: "Start talking",
    to: "/app",
    highlight: true,
  },
  {
    name: "Hybrid",
    price: "Mix & match",
    period: "",
    description: "Local where it matters, hosted where it is fast.",
    features: [
      "Local STT, hosted LLM",
      "Hosted STT, local TTS",
      "Per-stage provider selection",
      "Same WebSocket protocol",
    ],
    cta: "Start talking",
    to: "/app",
    highlight: false,
  },
];

export const LATENCY_PROPS = [
  { label: "First audio p50 target", value: "≤ 700 ms" },
  { label: "Barge-in p95 target", value: "≤ 200 ms" },
  { label: "Stale chunks after cancel", value: "0" },
];

export const LATENCY_COPY = {
  heading: "//latency is the product.",
  subhead:
    "Every turn is timed from the end-of-speech decision to the first audible chunk, then aggregated. Warm-up, cold starts and concurrency are part of the report, not excuses.",
};

export const FAQ_ITEMS = [
  {
    q: "Does Voxora upload my whole recording?",
    a: "No. The browser streams 20 ms PCM frames over a WebSocket. The server detects the end of your turn with VAD and transcribes on the fly, so nothing waits for a completed file.",
  },
  {
    q: "What does 'streaming' actually mean here?",
    a: "Each stage hands off partial work: transcript segments feed the language model, generated tokens are grouped into sentences, and the first sentence starts synthesising while later ones are still being written.",
  },
  {
    q: "How does interruption work?",
    a: "The first voiced frames of a new utterance cancel the running turn. The server cancels outstanding generation and the browser stops its playback queue immediately, so you never hear a stale answer.",
  },
  {
    q: "Which models can I use?",
    a: "Any OpenAI-compatible chat endpoint (OpenAI, Groq, vLLM, llama.cpp, Ollama), Whisper-family speech recognition (hosted or faster-whisper locally), and PCM or browser speech synthesis. Set it all through environment variables.",
  },
  {
    q: "Where do API keys live?",
    a: "Only on the server. The React app talks to your backend over one WebSocket and never sees provider credentials.",
  },
  {
    q: "Do I need a GPU?",
    a: "No. The zero-key defaults use the browser recogniser and speech synthesis with a built-in demo responder. Add a GPU only if you want local open-weight STT or a local LLM.",
  },
  {
    q: "How do I measure the latency myself?",
    a: "Open the Latency panel during a session. It shows per-turn server timings plus client-measured first-audio and barge-in latency, and the backend exposes p50/p95/p99 at /api/v1/voice/metrics.",
  },
];

export const FAQ_COPY = {
  heading: "Questions, answered.",
};

export const STACK_COPY = {
  heading: "Built from open pieces.",
  subhead:
    "Replace any slot independently; the orchestrator only knows the interface.",
};

export const STACK_ITEMS = [
  {
    slot: "VAD",
    options: "Silero VAD · energy detector",
    detail: "Frame-level speech detection with adaptive noise floor",
  },
  {
    slot: "STT",
    options: "faster-whisper · Kyutai · Parakeet · hosted Whisper",
    detail: "Partial or final transcript events per provider capability",
  },
  {
    slot: "LLM",
    options: "Qwen · Llama · Gemma · hosted streaming API",
    detail: "Token stream over an OpenAI-compatible endpoint",
  },
  {
    slot: "TTS",
    options: "Pocket TTS · Kokoro · hosted streaming TTS",
    detail: "Sentence chunks in, raw PCM out",
  },
];

export const SECONDARY_CTA = {
  heading: "Ready to talk to your machine?",
  subhead:
    "Open the studio, allow the microphone, and speak. Nothing to install, nothing to sign up for.",
  primary: { label: "Start a conversation", to: "/app" },
  secondary: { label: "Read the protocol", href: "#pipeline" },
};

export const FOOTER_COPY = {
  tagline:
    "A low-latency, real-time voice AI agent: streaming STT, LLM and TTS in one cancellable pipeline.",
};

export const FOOTER_COLUMNS = [
  {
    title: "Product",
    links: [
      { label: "How it works", href: "/#pipeline" },
      { label: "Capabilities", href: "/#capabilities" },
      { label: "Latency", href: "/#latency" },
      { label: "FAQ", href: "/#faq" },
      { label: "Studio", href: "/app" },
    ],
  },
  {
    title: "Developers",
    links: [
      { label: "Protocol", href: "/#pipeline" },
      { label: "Deployment", href: "/#deployment" },
      { label: "Metrics", href: "/#latency" },
      { label: "API README", href: "#stack" },
      { label: "Providers", href: "/#stack" },
    ],
  },
  {
    title: "Architecture",
    links: [
      { label: "STT adapters", href: "/#stack" },
      { label: "LLM adapters", href: "/#stack" },
      { label: "TTS adapters", href: "/#stack" },
      { label: "VAD", href: "/#stack" },
      { label: "Cancellation", href: "/#pipeline" },
    ],
  },
];

export const FOOTER_LEGAL = [
  { label: "Privacy", href: "/privacy" },
  { label: "Terms", href: "/terms" },
];
