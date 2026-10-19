/**
 * Web Speech API helpers.
 *
 * `BrowserSpeaker` plays server-provided sentence chunks through speech
 * synthesis; `createRecognition` exposes the streaming recogniser used when the
 * backend selects browser-side STT.
 */

type RecognitionResult = {
  isFinal: boolean;
  0: { transcript: string };
};

type RecognitionEvent = {
  resultIndex: number;
  results: { length: number; [index: number]: RecognitionResult };
};

type RecognitionErrorEvent = { error: string; message?: string };

export type Recognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
};

type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  const scope = window as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null;
}

export function supportsBrowserStt(): boolean {
  return recognitionCtor() !== null;
}

export function createRecognition(options: {
  lang?: string;
  onPartial: (text: string) => void;
  onFinal: (text: string) => void;
  onError: (error: string) => void;
}): Recognition | null {
  const Ctor = recognitionCtor();
  if (!Ctor) return null;
  const recognition = new Ctor();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = options.lang ?? navigator.language ?? "en-US";
  recognition.maxAlternatives = 1;

  recognition.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i];
      const text = result[0]?.transcript ?? "";
      if (result.isFinal) options.onFinal(text);
      else interim += text;
    }
    if (interim.trim()) options.onPartial(interim.trim());
  };
  recognition.onerror = (event) => {
    // `no-speech` and `aborted` are normal in a continuous session.
    if (event.error === "no-speech" || event.error === "aborted") return;
    options.onError(event.error || "speech recognition error");
  };
  return recognition;
}

export class BrowserSpeaker {
  private pending = 0;
  private speaking = false;
  private voice: SpeechSynthesisVoice | null = null;
  private readonly handlers: { onStart: () => void; onEnd: () => void };

  constructor(handlers: { onStart: () => void; onEnd: () => void }) {
    this.handlers = handlers;
  }

  get supported(): boolean {
    return typeof window !== "undefined" && "speechSynthesis" in window;
  }

  /** Voices load asynchronously in Chrome, so refresh on demand. */
  private pickVoice(): SpeechSynthesisVoice | null {
    if (!this.supported) return null;
    if (this.voice) return this.voice;
    const voices = window.speechSynthesis.getVoices();
    if (!voices.length) return null;
    const preferred =
      voices.find((voice) => voice.lang.startsWith("en") && voice.localService) ??
      voices.find((voice) => voice.lang.startsWith("en")) ??
      voices[0];
    this.voice = preferred ?? null;
    return this.voice;
  }

  primeVoices(): void {
    if (!this.supported) return;
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => {
      this.voice = null;
      this.pickVoice();
    };
  }

  speak(text: string): void {
    if (!text.trim()) return;
    if (!this.supported) {
      // No synthesis available: still signal so the UI does not hang.
      if (!this.speaking) {
        this.speaking = true;
        this.handlers.onStart();
      }
      this.handlers.onEnd();
      this.speaking = false;
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    const voice = this.pickVoice();
    if (voice) utterance.voice = voice;
    utterance.rate = 1;
    utterance.pitch = 1;
    this.pending += 1;
    utterance.onstart = () => {
      if (!this.speaking) {
        this.speaking = true;
        this.handlers.onStart();
      }
    };
    utterance.onend = () => {
      this.pending = Math.max(0, this.pending - 1);
      if (this.pending === 0) {
        this.speaking = false;
        this.handlers.onEnd();
      }
    };
    utterance.onerror = () => {
      this.pending = Math.max(0, this.pending - 1);
      if (this.pending === 0) {
        this.speaking = false;
        this.handlers.onEnd();
      }
    };
    window.speechSynthesis.speak(utterance);
  }

  get isSpeaking(): boolean {
    return this.speaking;
  }

  stop(): void {
    if (this.supported) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        /* ignore */
      }
    }
    this.pending = 0;
    if (this.speaking) {
      this.speaking = false;
      this.handlers.onEnd();
    }
  }
}
