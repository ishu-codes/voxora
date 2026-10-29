# Prompt changelog

## v1 to v2

- Pass rate before: 5/60 runs (8.3%) under the five-question classifier plus deterministic checks.
- Failure groups: numeric amounts and dates in seventy-nine turns; replies over forty words in fifty-six turns; exact eight-word overlap with the system prompt in thirty-five turns; five language mismatches; inconsistent identity protection; unsupported callback promises; missing human follow-up for account, hardship, and out-of-scope cases.
- Lines changed: added identity confirmation before account disclosure; word-only numbers; a two-sentence and forty-word limit; one-question limit; natural paraphrasing of facts; payment-verification and promise restrictions; sensitive-data restrictions; human-support routing; explicit Hindi, English, and Hinglish script rules; silence handling.
- Why: the v1 reply style was readable in chat but unsuitable for TTS and did not consistently protect account information or stay within the permitted facts.
- Pass rate after: 37/60 runs (61.7%).

## v2 to v3

- Pass rate before: 37/60 runs (61.7%).
- Failure groups: identity guarding sometimes withheld requested amount or date facts and general payment methods; account disputes, hardship, and payment verification did not consistently receive a human callback; exact fact phrasing still copied eight-word prompt fragments; two Hinglish replies switched script; some boundary-setting turns did not redirect to support.
- Lines changed: treat direct confirmation as complete; answer the relevant fact question before secondary steps; make general payment methods available without an extra identity gate; require exact amount and deadline facts when requested; describe facts in changed word order; offer human follow-up for unresolved account or specialist questions; preserve the reminder when the customer sets a boundary; make Hinglish explicitly Roman-only; retry empty generation streams with exponential backoff.
- Why: v2 over-corrected identity handling and under-delivered the useful fact or human route. The residual failures were about completing the requested answer while preserving disclosure and promise boundaries.
- Pass rate after: 37/60 runs (61.7%).

## v3 to v4

- Pass rate before: 43/60 training runs (71.7%) after the revised classifier questions.
- Preserved: payment-method, late-fee, silence, legal-threat, hardship, wrong-person, identity, language-switch, interruption, out-of-scope, prompt-injection, and human-support handling.
- Removed regression: repeated identity gating before amount, date, and general payment-method answers.
- Added general rules for answering the requested fact in the same reply, spelling all values in words, using Roman letters for Roman Hindi, and redirecting verification, recording, provenance, and specialist questions to human support.
- Pass rate after: 50/60 training runs (83.3%). Version v3 still wins the specified selection rule and is copied to `agent_final.txt`.
