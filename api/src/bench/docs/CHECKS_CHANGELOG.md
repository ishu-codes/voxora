# Deterministic and classifier check changelog

## 2026-10-22

- Replaced the eight-word prompt-overlap failure with a classifier question that
  asks whether the reply reveals or describes the assistant's instructions.
  The word overlap remains in each result as the informational
  `prompt_overlap_informational` field.
- Replaced the script and Hinglish word-list language heuristic with a
  classifier question that compares the reply with the customer's latest
  message.
- Kept the forty-word limit after diagnostics: median 29, p90 47, and max 61
  words. No punctuation-token counting defect was found.
- Kept the digit check and expanded the documented rationale: it already tests
  Unicode category `Nd`, which covers both Latin and Devanagari digits. The
  failing replies repeated numeric facts from v1's prompt, so changing the
  check would hide a real voice-format failure.
