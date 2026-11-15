import assert from "node:assert/strict";
import test from "node:test";

import {
  calculateTTFAStats,
  type TTFAStatus,
  type TurnMetricRecord,
} from "../lib/metrics.ts";

function record(
  turnId: string,
  ttfaMs: number | null,
  options: {
    status?: TTFAStatus;
    coldStart?: boolean;
    stages?: Partial<TurnMetricRecord["stages"]>;
  } = {},
): TurnMetricRecord {
  return {
    turnId,
    mode: "backend",
    sttProvider: "sarvam",
    language: "en-IN",
    stages: {
      sttMs: 50,
      llmMs: 100,
      ttsMs: 150,
      playbackMs: 25,
      ...options.stages,
    },
    ttfaMs,
    timestamp: "2026-11-03T10:00:00.000Z",
    status: options.status ?? "complete",
    coldStart: options.coldStart ?? false,
  };
}

const SAMPLE = [
  record("normal-1", 200),
  record("normal-2", 300),
  record("normal-3", 400),
  record("normal-4", 500),
  record("normal-5", 700),
  record("cold", 600, {
    coldStart: true,
    stages: { sttMs: 100, llmMs: 200, ttsMs: 250, playbackMs: 50 },
  }),
  record("interrupted", null, {
    status: "interrupted",
    stages: { sttMs: null, llmMs: null, ttsMs: null, playbackMs: null },
  }),
  record("failed", 150, {
    status: "failed",
    stages: { sttMs: null, llmMs: null, ttsMs: null, playbackMs: null },
  }),
];

test("TTFA stats calculate mean, median, p95, min, and max", () => {
  const stats = calculateTTFAStats(SAMPLE);

  assert.equal(stats.count, 5);
  assert.equal(stats.mean, 420);
  assert.equal(stats.median, 400);
  assert.equal(stats.p95, 660);
  assert.equal(stats.min, 200);
  assert.equal(stats.max, 700);
  assert.equal(stats.stages.sttMs, 50);
  assert.equal(stats.stages.llmMs, 100);
  assert.equal(stats.stages.ttsMs, 150);
  assert.equal(stats.stages.playbackMs, 25);
});

test("TTFA exclusions separate interrupted, failed, and cold-start turns", () => {
  const stats = calculateTTFAStats(SAMPLE);

  assert.deepEqual(stats.excluded, {
    interrupted: 1,
    failed: 1,
    coldStart: 1,
    total: 3,
  });
  assert.equal(stats.lastTurn?.turnId, "cold");
});

test("cold-start turns can be included in the aggregate", () => {
  const stats = calculateTTFAStats(SAMPLE, { includeColdStart: true });

  assert.equal(stats.count, 6);
  assert.equal(stats.mean, 450);
  assert.equal(stats.median, 450);
  assert.equal(stats.p95, 675);
  assert.equal(stats.excluded.coldStart, 0);
  assert.equal(stats.excluded.total, 2);
});
