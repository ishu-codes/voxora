class VoxoraCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.targetRate = options.processorOptions.targetRate || 16000;
    this.sourceRate = sampleRate;
    this.ratio = this.sourceRate / this.targetRate;
    this.sum = 0;
    this.count = 0;
    this.output = [];
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;
    for (let i = 0; i < channel.length; i += 1) {
      this.sum += channel[i];
      this.count += 1;
      if (this.count >= this.ratio) {
        const sample = Math.max(-1, Math.min(1, this.sum / this.count));
        this.output.push(Math.round(sample * 32767));
        this.sum = 0;
        this.count = 0;
      }
    }
    if (this.output.length >= 320) {
      const pcm = new Int16Array(this.output.slice(0, 320));
      this.output = this.output.slice(320);
      this.port.postMessage({type: "pcm", buffer: pcm.buffer}, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor("voxora-capture", VoxoraCapture);
