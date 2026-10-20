import assert from "node:assert/strict";
import test from "node:test";

import { hasUnlimitedVoiceSettings } from "../lib/voice-settings.ts";
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
