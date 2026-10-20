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

    const consumed = Math.floor(this.readPos);
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
};

export class AudioCapture {
  private context: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private muted: GainNode | null = null;

  async start(handlers: CaptureHandlers): Promise<void> {
    if (this.context) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone capture is not supported in this browser.");
    }

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    const context = new AudioContext({ latencyHint: "interactive" });
    await context.audioWorklet.addModule(getWorkletUrl());
    const source = context.createMediaStreamSource(this.stream);
    const node = new AudioWorkletNode(context, "voxora-capture", {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      processorOptions: { targetRate: TARGET_RATE },
    });
    const muted = context.createGain();
    muted.gain.value = 0;

    node.port.onmessage = (
      message: MessageEvent<{ pcm: ArrayBuffer; rms: number }>,
    ) => {
      const pcm = new Int16Array(message.data.pcm);
      handlers.onFrame(pcm);
      handlers.onLevel?.(message.data.rms);
    };

    source.connect(node);
    node.connect(muted);
    muted.connect(context.destination);

    this.context = context;
    this.node = node;
    this.source = source;
    this.muted = muted;

    if (context.state === "suspended") await context.resume();
  }

  get active(): boolean {
    return this.context !== null;
  }

  /** The live microphone stream, shared with the bar visualizer. */
  get mediaStream(): MediaStream | null {
    return this.stream;
  }

  async stop(): Promise<void> {
    try {
      this.node?.port.close();
      this.node?.disconnect();
      this.source?.disconnect();
      this.muted?.disconnect();
    } catch {
      /* ignore teardown races */
    }
    this.stream?.getTracks().forEach((track) => {
      track.stop();
    });
    if (this.context) await this.context.close().catch(() => undefined);
    this.context = null;
    this.stream = null;
    this.node = null;
    this.source = null;
    this.muted = null;
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
    if (context.state === "suspended") await context.resume();
  }

  get isSpeaking(): boolean {
    return this.sources.size > 0;
  }

  enqueue(pcm: Int16Array, sampleRate: number): void {
    if (!pcm.length || sampleRate <= 0) return;
    const context = this.ensureContext();
    if (context.state === "suspended") void context.resume();

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
      this.handlers.onFirstAudio?.();
    }

    source.onended = () => {
      this.sources.delete(source);
      if (this.sources.size === 0) {
        this.nextTime = 0;
        this.handlers.onSpeakingChange?.(false);
      }
    };
  }

  stop(): void {
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
