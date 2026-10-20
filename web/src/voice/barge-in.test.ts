import assert from "node:assert/strict";
import test from "node:test";

import { PcmFrameResampler } from "./audio.ts";
import { InterruptedTurns } from "./interrupted-turns.ts";
import { float32ToPcm16 } from "./vad.ts";

test("interrupting a turn invalidates its late events", () => {
  const turns = new InterruptedTurns();
  turns.begin("turn-a");
  assert.equal(turns.isActive("turn-a"), true);

  turns.interrupt("turn-a");
  assert.equal(turns.isCancelled("turn-a"), true);
  assert.equal(turns.isActive("turn-a"), false);
});

test("an old interrupt never marks a newer turn", () => {
  const turns = new InterruptedTurns();
  turns.begin("turn-a");
  turns.interrupt("turn-a");
  turns.begin("turn-b");

  turns.interrupt("turn-a");

  assert.equal(turns.isCancelled("turn-b"), false);
  assert.equal(turns.isActive("turn-b"), true);
});

test("settling a turn only clears that turn", () => {
  const turns = new InterruptedTurns();
  turns.begin("turn-a");
  turns.begin("turn-b");
  turns.settle("turn-a");
  assert.equal(turns.isActive("turn-b"), true);
});

test("cancelled ids stay bounded", () => {
  const turns = new InterruptedTurns(2);
  turns.interrupt("a");
  turns.interrupt("b");
  turns.interrupt("c");
  assert.equal(turns.isCancelled("a"), false);
  assert.equal(turns.isCancelled("b"), true);
  assert.equal(turns.isCancelled("c"), true);
});

test("VAD Float32 audio converts to clamped 16-bit PCM", () => {
  const pcm = float32ToPcm16(new Float32Array([0, 1, -1, 0.5, -0.5, 2]));
  assert.deepEqual(Array.from(pcm), [0, 32767, -32768, 16383, -16384, 32767]);
});

test("capture resampler keeps producing 20 ms frames across input blocks", () => {
  const resampler = new PcmFrameResampler(48_000);
  const frames: Int16Array[] = [];
  for (let block = 0; block < 150; block += 1) {
    const source = new Float32Array(128);
    for (let i = 0; i < source.length; i += 1) {
      source[i] = Math.sin(((block * 128 + i) / 48_000) * Math.PI * 2 * 440);
    }
    frames.push(...resampler.push(source));
  }

  assert.ok(frames.length >= 19, `expected frames, received ${frames.length}`);
  for (const frame of frames) {
    assert.equal(frame.length, 320);
    assert.ok(frame.some((sample) => sample !== 0));
  }
});
