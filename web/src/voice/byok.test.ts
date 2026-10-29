import assert from "node:assert/strict";
import test from "node:test";

import {
  hasUnlimitedVoiceSettings,
  toConfigurePayload,
} from "../lib/voice-settings.ts";
import { DirectSentenceChunker } from "./byok.ts";

test("direct BYOK chunker streams speakable sentences", () => {
  const chunker = new DirectSentenceChunker();
  const chunks = chunker.feed(
    "This is a direct client response. It should be split into sentences. ",
  );

  assert.deepEqual(chunks, [
    "This is a direct client response.",
    "It should be split into sentences.",
  ]);
  assert.equal(chunker.flush(), null);
});

test("direct BYOK chunker flushes an unterminated tail", () => {
  const chunker = new DirectSentenceChunker();
  assert.deepEqual(chunker.feed("Short tail"), []);
  assert.equal(chunker.flush(), "Short tail");
});

test("only complete BYOK settings select the direct-client path", () => {
  assert.equal(
    hasUnlimitedVoiceSettings({
      sarvamApiKey: "sarvam",
      openaiApiKey: "llm",
      openaiBaseUrl: "",
      openaiModel: "",
    }),
    true,
  );
  assert.equal(
    hasUnlimitedVoiceSettings({
      sarvamApiKey: "sarvam",
      openaiApiKey: "",
      openaiBaseUrl: "",
      openaiModel: "",
    }),
    false,
  );
});

test("configure payload never includes browser provider keys", () => {
  const payload = toConfigurePayload({
    installation_id: "device-1",
    screen_width: 1440,
    screen_height: 900,
    viewport_width: 1280,
    viewport_height: 800,
    pixel_ratio: 1,
    color_depth: 24,
    timezone: "Asia/Kolkata",
    language: "en-IN",
    platform: "Linux",
    hardware_concurrency: 8,
    device_memory: 8,
    touch_points: 0,
    webdriver: false,
  });
  const serialized = JSON.stringify(payload);

  assert.equal("byok" in payload, false);
  assert.equal(serialized.includes("sarvam_api_key"), false);
  assert.equal(serialized.includes("openai_api_key"), false);
  assert.equal(serialized.includes("api-subscription-key"), false);
  assert.equal(serialized.includes("Authorization"), false);
});
