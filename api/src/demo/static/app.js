const statusEl = document.querySelector("#status");
const transcriptEl = document.querySelector("#conversation");
let socket;
let audioContext;
let stream;
let player;
let speaking = false;
let silenceChunks = 0;
let preRoll = [];
let sessionTimer;

function append(role, text, metrics = "") {
  const block = document.createElement("div");
  block.innerHTML = `<strong>${role}:</strong> ${text}<div class="metrics">${metrics}</div>`;
  transcriptEl.appendChild(block);
}

function stopPlayback() {
  if (player) {
    try { player.stop(); } catch (_) {}
    player = null;
  }
}

function playPcm(base64, sampleRate) {
  stopPlayback();
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  const samples = new Int16Array(bytes.buffer);
  const buffer = audioContext.createBuffer(1, samples.length, sampleRate);
  const channel = buffer.getChannelData(0);
  for (let i = 0; i < samples.length; i += 1) channel[i] = samples[i] / 32768;
  player = audioContext.createBufferSource();
  player.buffer = buffer;
  player.connect(audioContext.destination);
  player.start();
}

async function start() {
  const code = encodeURIComponent(document.querySelector("#code").value);
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${scheme}://${location.host}/ws?code=${code}`);
  socket.binaryType = "arraybuffer";
  audioContext = new AudioContext();
  await audioContext.audioWorklet.addModule("/static/worklet.js");
  stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true}});
  const source = audioContext.createMediaStreamSource(stream);
  const capture = new AudioWorkletNode(audioContext, "voxora-capture", {
    processorOptions: {targetRate: 16000},
  });
  const silentGain = audioContext.createGain();
  silentGain.gain.value = 0;
  source.connect(capture).connect(silentGain).connect(audioContext.destination);

  capture.port.onmessage = (event) => {
    if (event.data.type !== "pcm" || socket.readyState !== WebSocket.OPEN) return;
    const pcm = new Uint8Array(event.data.buffer);
    const samples = new Int16Array(event.data.buffer);
    let sum = 0;
    for (const sample of samples) sum += (sample / 32768) ** 2;
    const rms = Math.sqrt(sum / samples.length);
    if (player && rms > 0.025) {
      stopPlayback();
      socket.send(JSON.stringify({type: "cancel"}));
    }
    if (!speaking && rms > 0.018) {
      speaking = true;
      silenceChunks = 0;
      socket.send(JSON.stringify({type: "speech_start"}));
      for (const chunk of preRoll) socket.send(chunk);
      preRoll = [];
    }
    if (speaking) {
      socket.send(pcm);
      if (rms < 0.012) {
        silenceChunks += 1;
        if (silenceChunks >= 33) {
          speaking = false;
          socket.send(JSON.stringify({
            type: "speech_end",
            language: document.querySelector("#language").value,
          }));
        }
      } else {
        silenceChunks = 0;
      }
    } else {
      preRoll.push(pcm.slice());
      if (preRoll.length > 15) preRoll.shift();
    }
  };

  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "ready") {
      statusEl.textContent = `Connected. Session ${message.session_id}.`;
      sessionTimer = setTimeout(stop, 180000);
    } else if (message.type === "transcript.final") {
      append("You", message.text);
    } else if (message.type === "assistant.done") {
      append("Ritu", message.text);
    } else if (message.type === "tts.audio") {
      playPcm(message.audio, message.sample_rate);
    } else if (message.type === "turn.metrics") {
      append("Latency", "", `STT ${message.stt_final_ms} ms · LLM ${message.llm_ms} ms · TTS first ${message.tts_first_audio_ms} ms · end-to-end ${message.end_to_end_ms} ms`);
    } else if (message.type === "playback.stop") {
      stopPlayback();
    } else if (message.type === "session.limit" || message.type === "error") {
      statusEl.textContent = message.message;
    }
  };
  socket.onclose = (event) => {
    statusEl.textContent = `Disconnected: ${event.reason || "session ended"}.`;
    stop();
  };
}

function stop() {
  clearTimeout(sessionTimer);
  if (socket && socket.readyState <= WebSocket.OPEN) socket.close();
  if (stream) stream.getTracks().forEach((track) => track.stop());
  if (audioContext) audioContext.close();
  stopPlayback();
  statusEl.textContent = "Disconnected.";
}

document.querySelector("#start").addEventListener("click", () => start().catch((error) => {
  statusEl.textContent = `${error.name}: ${error.message}`;
}));
document.querySelector("#stop").addEventListener("click", stop);
