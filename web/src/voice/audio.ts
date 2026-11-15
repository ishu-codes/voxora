/**
 * Browser audio I/O for the voice session.
 *
 * Capture runs an AudioWorklet that resamples microphone audio to 16 kHz mono
 * PCM16 and posts fixed 20 ms frames (matching the backend frame size). Playback
 * schedules PCM16 chunks on the Web Audio clock so consecutive TTS chunks join
 * without gaps, and `stop()` can cut a turn off within a frame.
 */

const TARGET_RATE = 16_000;
export const FRAME_SAMPLES = 320; // 20 ms @ 16 kHz
const WORKLET_FALLBACK_MS = 1_200;
const CAPTURE_START_TIMEOUT_MS = 4_000;
const SCRIPT_PROCESSOR_BUFFER = 1_024;

const WORKLET_SOURCE = `
class VoxoraCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const target = (options.processorOptions && options.processorOptions.targetRate) || 16000;
    this.ratio = sampleRate / target;
    this.input = [];
    this.readPos = 0;
    this.frame = [];
  }

  process(inputs, outputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel && channel.length) {
      for (let i = 0; i < channel.length; i += 1) this.input.push(channel[i]);
    }

    while (this.readPos + 1 < this.input.length) {
      const index = Math.floor(this.readPos);
      const frac = this.readPos - index;
      const sample = this.input[index] * (1 - frac) + this.input[index + 1] * frac;
      this.frame.push(sample);
      this.readPos += this.ratio;

      if (this.frame.length === 320) {
        const pcm = new Int16Array(320);
        let sum = 0;
        for (let i = 0; i < 320; i += 1) {
          const value = Math.max(-1, Math.min(1, this.frame[i]));
          pcm[i] = value < 0 ? value * 0x8000 : value * 0x7fff;
          sum += value * value;
        }
        this.port.postMessage({ pcm: pcm.buffer, rms: Math.sqrt(sum / 320) }, [pcm.buffer]);
        this.frame.length = 0;
      }
    }

    const consumed = Math.min(Math.floor(this.readPos), this.input.length);
    if (consumed > 0) {
      this.input = this.input.slice(consumed);
      this.readPos -= consumed;
    }

    if (outputs[0] && outputs[0][0]) outputs[0][0].fill(0);
    return true;
  }
}
registerProcessor("voxora-capture", VoxoraCapture);
`;

function rmsOf(samples: Int16Array): number {
  let sum = 0;
  for (let i = 0; i < samples.length; i += 1) {
    const value = samples[i] / 32768;
    sum += value * value;
  }
  return Math.sqrt(sum / samples.length);
}

/**
 * Streaming linear resampler used by the ScriptProcessor fallback. Keeping the
 * fractional read position between callbacks avoids dropping a sample at every
 * audio block boundary.
 */
export class PcmFrameResampler {
  private input: number[] = [];
  private frame: number[] = [];
  private readPos = 0;
  private readonly step: number;

  constructor(inputRate: number, targetRate = TARGET_RATE) {
    if (inputRate <= 0 || targetRate <= 0) {
      throw new Error("Audio sample rates must be positive.");
    }
    this.step = inputRate / targetRate;
  }

  push(samples: Float32Array): Int16Array[] {
    const frames: Int16Array[] = [];
    for (let i = 0; i < samples.length; i += 1) {
      this.input.push(samples[i]);
    }

    while (this.readPos + 1 < this.input.length) {
      const index = Math.floor(this.readPos);
      const fraction = this.readPos - index;
      const current = this.input[index] ?? 0;
      const next = this.input[index + 1] ?? current;
      this.frame.push(current * (1 - fraction) + next * fraction);
      this.readPos += this.step;

      if (this.frame.length === FRAME_SAMPLES) {
        const pcm = new Int16Array(FRAME_SAMPLES);
        for (let frameIndex = 0; frameIndex < FRAME_SAMPLES; frameIndex += 1) {
          const value = Math.max(-1, Math.min(1, this.frame[frameIndex]));
          pcm[frameIndex] = value < 0 ? value * 0x8000 : value * 0x7fff;
        }
        frames.push(pcm);
        this.frame = [];
      }
    }

    const consumed = Math.min(Math.floor(this.readPos), this.input.length);
    if (consumed > 0) {
      this.input = this.input.slice(consumed);
      this.readPos -= consumed;
    }
    return frames;
  }
}

let workletUrl: string | null = null;
function getWorkletUrl(): string {
  if (!workletUrl) {
    workletUrl = URL.createObjectURL(
      new Blob([WORKLET_SOURCE], { type: "text/javascript" }),
    );
  }
  return workletUrl;
}

export type CaptureHandlers = {
  onFrame: (pcm: Int16Array) => void;
  onLevel?: (rms: number) => void;
  /** Called when the microphone stream dies or stops producing frames. */
  onStreamLost?: (reason: string) => void;
};

function audioContextCtor() {
  const Ctor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext })
      .webkitAudioContext;
  if (!Ctor) {
    throw new Error("Audio capture is not supported in this browser.");
  }
  return Ctor;
}

/** Wait for resume, but never let a stuck promise block the session start. */
async function resumeContext(context: AudioContext): Promise<void> {
  if (context.state !== "suspended") return;
  await Promise.race([
    context.resume().catch(() => undefined),
    new Promise<void>((resolve) => {
      window.setTimeout(resolve, 300);
    }),
  ]);
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export class AudioCapture {
  private context: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private scriptNode: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private muted: GainNode | null = null;
  private handlers: CaptureHandlers | null = null;
  private healthTimer: number | null = null;
  private workletFallbackTimer: number | null = null;
  private lastFrameAt = 0;
  private lost = false;
  private closing = false;
  private backend: "worklet" | "script" | null = null;
  private firstFrameResolve: (() => void) | null = null;
  private firstFramePromise: Promise<void> | null = null;

  async start(handlers: CaptureHandlers): Promise<void> {
    if (this.context) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone capture is not supported in this browser.");
    }

    this.handlers = handlers;
    this.closing = false;
    this.lost = false;
    this.firstFramePromise = new Promise((resolve) => {
      this.firstFrameResolve = resolve;
    });

    // Create the context synchronously in the click handler before awaiting
    // permission. A context created after the permission prompt can start
    // suspended and never deliver frames.
    const context = new (audioContextCtor())({ latencyHint: "interactive" });
    this.context = context;
    await resumeContext(context);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (!stream.getAudioTracks().length) {
        stream.getTracks().forEach((track) => {
          track.stop();
        });
        throw new Error("The microphone did not provide an audio track.");
      }
      this.stream = stream;
      const source = context.createMediaStreamSource(stream);
      const muted = context.createGain();
      muted.gain.value = 0;
      muted.connect(context.destination);
      this.source = source;
      this.muted = muted;
      this.lastFrameAt = performance.now();

      await resumeContext(context);
      if (context.state !== "running") {
        throw new Error(
          "The browser could not start audio capture. Press Start again and allow microphone access.",
        );
      }

      let workletStarted = false;
      if (context.audioWorklet && typeof AudioWorkletNode === "function") {
        try {
          await context.audioWorklet.addModule(getWorkletUrl());
          this.startWorklet(context);
          workletStarted = true;
        } catch (cause) {
          if (process.env.NODE_ENV !== "production") {
            console.warn(
              "[voice] AudioWorklet capture unavailable; using ScriptProcessor",
              cause,
            );
          }
        }
      }
      if (!workletStarted) this.startScriptProcessor(context);

      const track = stream.getAudioTracks()[0];
      track?.addEventListener("ended", this.handleTrackEnded);
      context.addEventListener("statechange", this.handleContextState);

      this.healthTimer = window.setInterval(() => this.checkHealth(), 1_500);
      await Promise.race([
        this.firstFramePromise,
        wait(CAPTURE_START_TIMEOUT_MS).then(() => {
          throw new Error(
            "The microphone is connected but is not producing audio frames.",
          );
        }),
      ]);
    } catch (cause) {
      await this.stop();
      throw cause;
    }
  }

  private startWorklet(context: AudioContext): void {
    const source = this.source;
    const muted = this.muted;
    const handlers = this.handlers;
    if (!source || !muted || !handlers) return;

    const node = new AudioWorkletNode(context, "voxora-capture", {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      channelCount: 1,
      channelCountMode: "explicit",
      processorOptions: { targetRate: TARGET_RATE },
    });
    node.port.onmessage = (
      message: MessageEvent<{ pcm: ArrayBuffer; rms: number }>,
    ) => {
      if (this.backend !== "worklet" || this.closing) return;
      const pcm = new Int16Array(message.data.pcm);
      this.emitFrame(pcm, message.data.rms);
    };
    node.port.onmessageerror = () => {
      if (this.backend === "worklet") {
        this.startScriptProcessor(context);
      }
    };

    source.connect(node);
    node.connect(muted);
    this.node = node;
    this.backend = "worklet";

    // Some browser/device combinations initialize a worklet but never schedule
    // it. A ScriptProcessor is slower but reliable, so switch automatically
    // unless the first frame proves the worklet path is live.
    this.workletFallbackTimer = window.setTimeout(() => {
      if (this.backend === "worklet" && !this.closing) {
        if (process.env.NODE_ENV !== "production") {
          console.info("[voice] AudioWorklet produced no frames; falling back");
        }
        this.startScriptProcessor(context);
      }
    }, WORKLET_FALLBACK_MS);
  }

  private startScriptProcessor(context: AudioContext): boolean {
    const source = this.source;
    const muted = this.muted;
    if (!source || !muted || this.closing || this.backend === "script") {
      return false;
    }
    if (typeof context.createScriptProcessor !== "function") return false;

    if (this.workletFallbackTimer != null) {
      window.clearTimeout(this.workletFallbackTimer);
      this.workletFallbackTimer = null;
    }
    try {
      this.node?.port.close();
      this.node?.disconnect();
    } catch {
      /* ignore a worklet teardown race */
    }
    this.node = null;

    const resampler = new PcmFrameResampler(context.sampleRate);
    const node = context.createScriptProcessor(SCRIPT_PROCESSOR_BUFFER, 1, 1);
    node.onaudioprocess = (event) => {
      if (this.backend !== "script" || this.closing) return;
      const frames = resampler.push(event.inputBuffer.getChannelData(0));
      for (const frame of frames) this.emitFrame(frame, rmsOf(frame));
    };
    source.connect(node);
    node.connect(muted);
    this.scriptNode = node;
    this.backend = "script";
    return true;
  }

  private emitFrame(pcm: Int16Array, rms: number): void {
    this.lastFrameAt = performance.now();
    if (this.firstFrameResolve) {
      this.firstFrameResolve();
      this.firstFrameResolve = null;
      if (this.workletFallbackTimer != null) {
        window.clearTimeout(this.workletFallbackTimer);
        this.workletFallbackTimer = null;
      }
    }
    this.handlers?.onFrame(pcm);
    this.handlers?.onLevel?.(rms);
  }

  private handleTrackEnded = () => {
    this.reportLost("track-ended");
  };

  private handleContextState = () => {
    if (this.closing || !this.context) return;
    if (this.context.state === "suspended") {
      void this.context.resume().catch(() => undefined);
    }
  };

  private reportLost(reason: string): void {
    if (this.closing || this.lost) return;
    this.lost = true;
    const track = this.stream?.getAudioTracks()[0];
    if (process.env.NODE_ENV !== "production") {
      console.info("[voice] capture lost", {
        reason,
        context: this.context?.state ?? "missing",
        track: track?.readyState ?? "missing",
        muted: track?.muted ?? null,
        frameGapMs: Math.round(performance.now() - this.lastFrameAt),
      });
    }
    this.handlers?.onStreamLost?.(reason);
  }

  private checkHealth(): void {
    if (this.closing) return;
    const track = this.stream?.getAudioTracks()[0];
    const now = performance.now();

    if (!this.context || !this.stream || !track) {
      this.reportLost("missing-stream");
      return;
    }
    if (this.context.state === "closed") {
      this.reportLost("context-closed");
      return;
    }
    if (track.readyState === "ended") {
      this.reportLost("track-ended");
      return;
    }
    if (this.context.state === "suspended") {
      void this.context.resume().catch(() => undefined);
    }
    // The worklet posts a 20 ms frame even during silence. A multi-second gap
    // means the graph stalled or the device was taken away. `track.muted` is
    // deliberately not a trigger: browsers report it transiently (and
    // sometimes incorrectly), while a real mute also stops the frames.
    if (now - this.lastFrameAt > 4_000) {
      this.reportLost("no-audio-frames");
    }
  }

  async resume(): Promise<void> {
    if (this.context) await resumeContext(this.context);
  }

  get active(): boolean {
    return this.context !== null;
  }

  /** The live microphone stream, shared with the bar visualizer and VAD. */
  get mediaStream(): MediaStream | null {
    return this.stream;
  }

  /** The running context, shared with the local VAD to avoid a second one. */
  get audioContext(): AudioContext | null {
    return this.context;
  }

  async stop(): Promise<void> {
    this.closing = true;
    if (this.healthTimer != null) {
      window.clearInterval(this.healthTimer);
      this.healthTimer = null;
    }
    if (this.workletFallbackTimer != null) {
      window.clearTimeout(this.workletFallbackTimer);
      this.workletFallbackTimer = null;
    }
    this.firstFrameResolve = null;
    this.firstFramePromise = null;
    const track = this.stream?.getAudioTracks()[0];
    track?.removeEventListener("ended", this.handleTrackEnded);
    this.context?.removeEventListener("statechange", this.handleContextState);
    try {
      this.node?.port.close();
      this.node?.disconnect();
      if (this.scriptNode) this.scriptNode.onaudioprocess = null;
      this.scriptNode?.disconnect();
      this.source?.disconnect();
      this.muted?.disconnect();
    } catch {
      /* ignore teardown races */
    }
    this.stream?.getTracks().forEach((item) => {
      item.stop();
    });
    if (this.context) await this.context.close().catch(() => undefined);
    this.context = null;
    this.stream = null;
    this.node = null;
    this.scriptNode = null;
    this.source = null;
    this.muted = null;
    this.handlers = null;
    this.backend = null;
  }
}

export function decodePcm16(base64: string): Int16Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Int16Array(
    bytes.buffer,
    bytes.byteOffset,
    Math.floor(bytes.byteLength / 2),
  );
}

export type PlayerHandlers = {
  onSpeakingChange?: (speaking: boolean) => void;
  onFirstAudio?: () => void;
};

export class AudioPlayer {
  private context: AudioContext | null = null;
  private gain: GainNode | null = null;
  private sources = new Set<AudioBufferSourceNode>();
  private startTimers = new Set<number>();
  private nextTime = 0;

  private readonly handlers: PlayerHandlers;

  constructor(handlers: PlayerHandlers = {}) {
    this.handlers = handlers;
  }

  private ensureContext(): AudioContext {
    if (!this.context) {
      this.context = new AudioContext({ latencyHint: "interactive" });
      this.gain = this.context.createGain();
      this.gain.connect(this.context.destination);
    }
    return this.context;
  }

  async resume(): Promise<void> {
    const context = this.ensureContext();
    if (context.state === "suspended") {
      await context.resume().catch(() => undefined);
    }
  }

  get isSpeaking(): boolean {
    return this.sources.size > 0;
  }

  enqueue(
    pcm: Int16Array,
    sampleRate: number,
    onPlaybackStart?: () => void,
  ): void {
    if (!pcm.length || sampleRate <= 0) return;
    const context = this.ensureContext();
    if (context.state === "suspended") {
      void context.resume().catch(() => undefined);
    }

    const buffer = context.createBuffer(1, pcm.length, sampleRate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i += 1) channel[i] = pcm[i] / 32768;

    const source = context.createBufferSource();
    source.buffer = buffer;
    if (!this.gain) return;
    source.connect(this.gain);

    const idle = this.sources.size === 0;
    const startAt = Math.max(context.currentTime + 0.02, this.nextTime);
    source.start(startAt);
    this.nextTime = startAt + buffer.duration;
    this.sources.add(source);
    if (idle) {
      this.handlers.onSpeakingChange?.(true);
    }
    if (onPlaybackStart || (idle && this.handlers.onFirstAudio)) {
      const outputLatency = Math.max(
        0,
        context.outputLatency ?? context.baseLatency ?? 0,
      );
      this.schedulePlaybackStart(context, startAt + outputLatency, () => {
        if (idle) this.handlers.onFirstAudio?.();
        onPlaybackStart?.();
      });
    }

    source.onended = () => {
      this.sources.delete(source);
      if (this.sources.size === 0) {
        this.nextTime = 0;
        this.handlers.onSpeakingChange?.(false);
      }
    };
  }

  private schedulePlaybackStart(
    context: AudioContext,
    startAt: number,
    onPlaybackStart: () => void,
  ): void {
    const scheduleCheck = () => {
      const remainingMs = (startAt - context.currentTime) * 1000;
      const delay =
        context.state === "running"
          ? Math.max(0, Math.min(remainingMs, 25))
          : 50;
      const timer = window.setTimeout(() => {
        this.startTimers.delete(timer);
        const remaining = (startAt - context.currentTime) * 1000;
        if (context.state === "running" && remaining <= 0) {
          onPlaybackStart();
          return;
        }
        scheduleCheck();
      }, delay);
      this.startTimers.add(timer);
    };

    scheduleCheck();
  }

  stop(): void {
    for (const timer of this.startTimers) window.clearTimeout(timer);
    this.startTimers.clear();
    for (const source of this.sources) {
      source.onended = null;
      try {
        source.stop();
      } catch {
        /* already stopped */
      }
    }
    const wasSpeaking = this.sources.size > 0;
    this.sources.clear();
    this.nextTime = 0;
    if (wasSpeaking) this.handlers.onSpeakingChange?.(false);
  }

  async close(): Promise<void> {
    this.stop();
    if (this.context) {
      await this.context.close().catch(() => undefined);
      this.context = null;
      this.gain = null;
    }
  }
}
