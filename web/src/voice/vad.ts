/**
 * Local, in-browser speech detection with Silero VAD.
 *
 * The agent already streams 16 kHz PCM to the backend, so this detector is not
 * used for transcription. It provides two things the energy loop cannot:
 * a confirmed speech onset for immediate barge-in, and a local gate that keeps
 * silence off the wire while no one is talking.
 *
 * `@ricky0123/vad-web` loads its model and ONNX Runtime WASM from `/vad/`. The
 * files are copied there by `scripts/copy-vad-assets.mjs` during dev/build.
 */

import type { MicVAD, RealTimeVADOptions } from "@ricky0123/vad-web";

function envNumber(raw: string | undefined, fallback: number): number {
  if (!raw) return fallback;
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

const ASSET_PATH = "/vad/";
const VAD_START_TIMEOUT_MS = 2_500;

/** Confirmed speech duration before an interruption is allowed. */
export const MIN_SPEECH_MS = envNumber(
  process.env.NEXT_PUBLIC_VAD_MIN_SPEECH_MS,
  200,
);
/** Silence before the VAD ends a local utterance. */
export const REDEMPTION_MS = envNumber(
  process.env.NEXT_PUBLIC_VAD_REDEMPTION_MS,
  650,
);
/** Audio kept before speech onset so first syllables are not lost. */
export const PRE_SPEECH_PAD_MS = envNumber(
  process.env.NEXT_PUBLIC_VAD_PRE_SPEECH_PAD_MS,
  500,
);

const IDLE_POSITIVE_THRESHOLD = envNumber(
  process.env.NEXT_PUBLIC_VAD_POSITIVE_THRESHOLD,
  0.42,
);
// Assistant playback leaks into the microphone even with echo cancellation.
// Require a little more confidence while TTS is audible.
const PLAYBACK_POSITIVE_THRESHOLD = envNumber(
  process.env.NEXT_PUBLIC_VAD_PLAYBACK_THRESHOLD,
  0.6,
);
const NEGATIVE_THRESHOLD = envNumber(
  process.env.NEXT_PUBLIC_VAD_NEGATIVE_THRESHOLD,
  0.25,
);

export type LocalVadHandlers = {
  getStream: () => MediaStream;
  onSpeechStart: () => void;
  onSpeechRealStart: () => void;
  onSpeechEnd: (audio: Float32Array) => void;
  onMisfire: () => void;
};

export type LocalVadTuning = {
  positiveSpeechThreshold: number;
  negativeSpeechThreshold: number;
  minSpeechMs: number;
  redemptionMs: number;
  preSpeechPadMs: number;
};

export const DEFAULT_TUNING: LocalVadTuning = {
  positiveSpeechThreshold: IDLE_POSITIVE_THRESHOLD,
  negativeSpeechThreshold: NEGATIVE_THRESHOLD,
  minSpeechMs: MIN_SPEECH_MS,
  redemptionMs: REDEMPTION_MS,
  preSpeechPadMs: PRE_SPEECH_PAD_MS,
};

export class LocalVad {
  private instance: MicVAD | null = null;
  private context: AudioContext | null = null;
  private ownsContext = true;
  private firstFrameResolve: (() => void) | null = null;
  private assistantSpeaking = false;
  private readonly handlers: LocalVadHandlers;
  private readonly tuning: LocalVadTuning;
  private readonly providedContext: AudioContext | null;

  constructor(
    handlers: LocalVadHandlers,
    tuning: Partial<LocalVadTuning> = {},
    options: { audioContext?: AudioContext | null } = {},
  ) {
    this.handlers = handlers;
    this.tuning = { ...DEFAULT_TUNING, ...tuning };
    this.providedContext = options.audioContext ?? null;
  }

  /** Load the Silero model and start listening. Safe to call once per session. */
  async start(): Promise<void> {
    if (this.instance) return;

    // Prefer the microphone capture's context. It was created in the Start
    // gesture and is already running, so the VAD cannot end up suspended on a
    // second, later-created context.
    const context =
      this.providedContext ?? new AudioContext({ latencyHint: "interactive" });
    this.context = context;
    this.ownsContext = this.providedContext === null;
    if (this.ownsContext) {
      context.addEventListener("statechange", this.handleContextState);
    }
    if (context.state === "suspended") {
      await context.resume().catch(() => undefined);
    }

    let lastError: unknown;
    try {
      try {
        await this.startInstance(context, "auto");
      } catch (cause) {
        lastError = cause;
        // The packaged AudioWorklet normally works, but if it is initialized
        // without delivering frames, the ScriptProcessor path uses its own
        // graph and supplies the same model frames.
        await this.safeDestroyInstance();
        if (process.env.NODE_ENV !== "production") {
          console.info(
            "[voice] local VAD worklet unavailable; using ScriptProcessor",
            cause,
          );
        }
        await this.startInstance(context, "ScriptProcessor");
      }
    } catch (cause) {
      lastError = cause;
      await this.safeDestroyInstance();
      await this.closeContext();
      throw lastError;
    }
  }

  private async startInstance(
    context: AudioContext,
    processorType: "auto" | "ScriptProcessor",
  ): Promise<void> {
    const firstFrame = new Promise<void>((resolve) => {
      this.firstFrameResolve = resolve;
    });
    try {
      const { MicVAD: Vad } = await import("@ricky0123/vad-web");
      const options: Partial<RealTimeVADOptions> = {
        model: "legacy",
        baseAssetPath: ASSET_PATH,
        onnxWASMBasePath: ASSET_PATH,
        processorType,
        startOnLoad: false,
        audioContext: context,
        getStream: async () => this.handlers.getStream(),
        // The capture pipeline owns the microphone tracks. Pausing the VAD must
        // not stop the stream that feeds STT.
        pauseStream: async () => undefined,
        resumeStream: async () => this.handlers.getStream(),
        ...this.tuning,
        ...this.thresholds(),
        onFrameProcessed: () => this.markFirstFrame(),
        onSpeechStart: () => this.handlers.onSpeechStart(),
        onSpeechRealStart: () => this.handlers.onSpeechRealStart(),
        onSpeechEnd: (audio: Float32Array) => this.handlers.onSpeechEnd(audio),
        onVADMisfire: () => this.handlers.onMisfire(),
      };
      const instance = await Vad.new(options);
      this.instance = instance;
      await instance.start();
      await Promise.race([
        firstFrame,
        new Promise<never>((_, reject) => {
          window.setTimeout(
            () =>
              reject(
                new Error(
                  "Local voice detection received no microphone frames.",
                ),
              ),
            VAD_START_TIMEOUT_MS,
          );
        }),
      ]);
    } catch (cause) {
      await this.safeDestroyInstance();
      throw cause;
    } finally {
      this.firstFrameResolve = null;
    }
  }

  private markFirstFrame(): void {
    if (!this.firstFrameResolve) return;
    this.firstFrameResolve();
    this.firstFrameResolve = null;
  }

  private async safeDestroyInstance(): Promise<void> {
    const instance = this.instance;
    this.instance = null;
    if (!instance) return;
    try {
      await instance.destroy();
    } catch {
      // MicVAD cannot tear down a graph it never finished constructing.
    }
  }

  private handleContextState = () => {
    if (this.context?.state === "suspended") {
      void this.context.resume().catch(() => undefined);
    }
  };

  /** Resume the VAD graph after the tab or device was suspended. */
  async resume(): Promise<void> {
    if (this.context?.state === "suspended") {
      await this.context.resume().catch(() => undefined);
    }
  }

  /**
   * Raise the onset threshold while TTS is playing. Cancellation is still
   * available at any point; this only rejects quiet/noisy frames that are
   * likely echo rather than the user.
   */
  setAssistantSpeaking(speaking: boolean): void {
    if (this.assistantSpeaking === speaking) return;
    this.assistantSpeaking = speaking;
    this.instance?.setOptions(this.thresholds());
  }

  get isListening(): boolean {
    return this.instance?.listening ?? false;
  }

  private thresholds(): Pick<
    LocalVadTuning,
    "positiveSpeechThreshold" | "negativeSpeechThreshold" | "minSpeechMs"
  > {
    const positive = this.assistantSpeaking
      ? PLAYBACK_POSITIVE_THRESHOLD
      : this.tuning.positiveSpeechThreshold;
    return {
      positiveSpeechThreshold: positive,
      negativeSpeechThreshold: Math.min(
        this.tuning.negativeSpeechThreshold,
        positive - 0.05,
      ),
      minSpeechMs: this.tuning.minSpeechMs,
    };
  }

  private async closeContext(): Promise<void> {
    const context = this.context;
    this.context = null;
    if (!context) return;
    if (!this.ownsContext) return;
    context.removeEventListener("statechange", this.handleContextState);
    await context.close().catch(() => undefined);
  }

  async destroy(): Promise<void> {
    await this.safeDestroyInstance();
    await this.closeContext();
  }
}

export function float32ToPcm16(samples: Float32Array): Int16Array {
  const pcm = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i += 1) {
    const value = Math.max(-1, Math.min(1, samples[i]));
    pcm[i] = value < 0 ? value * 0x8000 : value * 0x7fff;
  }
  return pcm;
}
