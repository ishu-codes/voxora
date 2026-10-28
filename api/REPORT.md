# Voice-agent benchmark report

Generated from `results/` at 2026-10-28 03:35 UTC. Every numeric result below is derived from raw JSON files in that directory.

## Speech-to-text

### Provider coverage

| Provider | Modes | Status |
| --- | --- | --- |
| faster-whisper-base | configured modes | run |
| sarvam | configured modes | run |
| openai-whisper | transcribe | not run (WHISPER_API_KEY unavailable) |

### By provider, mode, and language

| Provider | Mode | Language | Count | Errors | Empty | Semantic | Amount | Date | Name | Comparable WER mean | Comparable CER mean | Comparable n | Script mismatch |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| faster-whisper-base | transcribe | en | 15 | 0 | 0 | 80.0% | 100.0% | 100.0% | 100.0% | 7.6% | 5.5% | 15 | 0 |
| faster-whisper-base | transcribe | hi | 15 | 0 | 0 | 80.0% | 66.7% | 50.0% | 0.0% | 88.9% | 39.1% | 1 | 14 |
| faster-whisper-base | transcribe | hinglish | 15 | 0 | 0 | 73.3% | 33.3% | 50.0% | 100.0% | 88.5% | 53.2% | 12 | 3 |
| faster-whisper-base | transcribe-no-hint | en | 15 | 0 | 0 | 80.0% | 100.0% | 100.0% | 100.0% | 7.6% | 5.5% | 15 | 0 |
| faster-whisper-base | transcribe-no-hint | hi | 15 | 0 | 0 | 73.3% | 66.7% | 75.0% | 0.0% | 88.9% | 39.1% | 1 | 14 |
| faster-whisper-base | transcribe-no-hint | hinglish | 15 | 0 | 0 | 80.0% | 33.3% | 50.0% | 100.0% | 89.4% | 55.5% | 12 | 3 |
| sarvam | codemix | en | 15 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% | 7.7% | 7.7% | 15 | 0 |
| sarvam | codemix | hi | 15 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% | 13.6% | 10.6% | 11 | 4 |
| sarvam | codemix | hinglish | 15 | 0 | 0 | 93.3% | 100.0% | 75.0% | 100.0% | not run | not run | 0 | 15 |
| sarvam | transcribe | en | 15 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% | 5.2% | 4.8% | 15 | 0 |
| sarvam | transcribe | hi | 15 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% | 8.4% | 6.4% | 15 | 0 |
| sarvam | transcribe | hinglish | 15 | 0 | 0 | 100.0% | 100.0% | 75.0% | 100.0% | not run | not run | 0 | 15 |
| sarvam | translit | en | 15 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% | 5.8% | 5.5% | 15 | 0 |
| sarvam | translit | hi | 15 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% | not run | not run | 0 | 15 |
| sarvam | translit | hinglish | 15 | 0 | 0 | 100.0% | 100.0% | 75.0% | 100.0% | 23.8% | 18.3% | 15 | 0 |

### Best provider and mode per language

| Language | Provider | Mode | Semantic | Entity accuracy |
| --- | --- | --- | --- | --- |
| en | sarvam | codemix | 100.0% | 100.0% |
| hi | sarvam | codemix | 100.0% | 100.0% |
| hinglish | sarvam | transcribe | 100.0% | 87.5% |

### Noise and phone conditions

| Condition | Provider | Mode | Count | Errors | Semantic | Entity accuracy | Comparable WER mean | Semantic change | WER change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| babble_10db | faster-whisper-base | transcribe | 45 | 0 | 46.7% | 33.3% | 65.0% | -31.1% | 19.8% |
| babble_10db | faster-whisper-base | transcribe-no-hint | 45 | 0 | 42.2% | 37.5% | 66.7% | -35.6% | 21.1% |
| babble_10db | sarvam | codemix | 45 | 0 | 95.6% | 95.8% | 9.6% | -2.2% | -0.6% |
| babble_10db | sarvam | transcribe | 45 | 0 | 97.8% | 95.8% | 6.2% | -2.2% | -0.5% |
| babble_10db | sarvam | translit | 45 | 0 | 100.0% | 95.8% | 15.1% | 0.0% | 0.3% |
| clean | faster-whisper-base | transcribe | 45 | 0 | 77.8% | 66.7% | 45.2% | 0.0% | 0.0% |
| clean | faster-whisper-base | transcribe-no-hint | 45 | 0 | 77.8% | 70.8% | 45.6% | 0.0% | 0.0% |
| clean | sarvam | codemix | 45 | 0 | 97.8% | 95.8% | 10.2% | 0.0% | 0.0% |
| clean | sarvam | transcribe | 45 | 0 | 100.0% | 95.8% | 6.8% | 0.0% | 0.0% |
| clean | sarvam | translit | 45 | 0 | 100.0% | 95.8% | 14.8% | 0.0% | 0.0% |
| phone | faster-whisper-base | transcribe | 45 | 0 | 73.3% | 70.8% | 50.5% | -4.4% | 5.3% |
| phone | faster-whisper-base | transcribe-no-hint | 45 | 0 | 73.3% | 58.3% | 49.1% | -4.4% | 3.5% |
| phone | sarvam | codemix | 45 | 0 | 97.8% | 91.7% | 5.9% | 0.0% | -4.4% |
| phone | sarvam | transcribe | 45 | 0 | 97.8% | 95.8% | 7.5% | -2.2% | 0.7% |
| phone | sarvam | translit | 45 | 0 | 95.6% | 95.8% | 14.8% | -4.4% | 0.0% |
| pink_10db | faster-whisper-base | transcribe | 45 | 0 | 66.7% | 50.0% | 47.4% | -11.1% | 2.2% |
| pink_10db | faster-whisper-base | transcribe-no-hint | 45 | 0 | 60.0% | 54.2% | 48.9% | -17.8% | 3.4% |
| pink_10db | sarvam | codemix | 45 | 0 | 91.1% | 87.5% | 13.4% | -6.7% | 3.2% |
| pink_10db | sarvam | transcribe | 45 | 0 | 91.1% | 91.7% | 8.2% | -8.9% | 1.4% |
| pink_10db | sarvam | translit | 45 | 0 | 95.6% | 91.7% | 17.8% | -4.4% | 3.0% |
| pink_20db | faster-whisper-base | transcribe | 45 | 0 | 73.3% | 70.8% | 44.5% | -4.4% | -0.7% |
| pink_20db | faster-whisper-base | transcribe-no-hint | 45 | 0 | 68.9% | 66.7% | 51.8% | -8.9% | 6.3% |
| pink_20db | sarvam | codemix | 45 | 0 | 97.8% | 87.5% | 11.2% | 0.0% | 1.0% |
| pink_20db | sarvam | transcribe | 45 | 0 | 97.8% | 91.7% | 6.3% | -2.2% | -0.5% |
| pink_20db | sarvam | translit | 45 | 0 | 97.8% | 91.7% | 16.4% | -2.2% | 1.5% |
| pink_5db | faster-whisper-base | transcribe | 45 | 0 | 42.2% | 29.2% | 59.0% | -35.6% | 13.8% |
| pink_5db | faster-whisper-base | transcribe-no-hint | 45 | 0 | 40.0% | 33.3% | 61.7% | -37.8% | 16.1% |
| pink_5db | sarvam | codemix | 45 | 0 | 84.4% | 83.3% | 11.5% | -13.3% | 1.3% |
| pink_5db | sarvam | transcribe | 45 | 0 | 84.4% | 91.7% | 11.3% | -15.6% | 4.5% |
| pink_5db | sarvam | translit | 45 | 0 | 84.4% | 91.7% | 20.5% | -15.6% | 5.7% |

### Five worst utterances per provider by semantic match

### faster-whisper-base

| Utterance | Mode | Reference | Hypothesis | Semantic probability |
| --- | --- | --- | --- | --- |
| hi01 | transcribe-no-hint | हाँ, मैं रोहन बोल रहा हूँ। | ข้าไม่รู้ขึ้นบัลร้อง | 0.010 |
| en08 | transcribe-no-hint | I can pay on Friday, not before that. | I can pay on Friday or before that. | 0.010 |
| en08 | transcribe | I can pay on Friday, not before that. | I can pay on Friday or before that. | 0.010 |
| en05 | transcribe | How do I pay through the app? | How do I fade through the app? | 0.010 |
| en05 | transcribe-no-hint | How do I pay through the app? | How do I fade through the app? | 0.010 |

### sarvam

| Utterance | Mode | Reference | Hypothesis | Semantic probability |
| --- | --- | --- | --- | --- |
| hg10 | codemix | Kya late fee teen sau rupaye hai? | क्या Lead fee ₹300 है? | 0.031 |
| hi14 | transcribe | मैं तीन नवंबर को यूपीआई से भुगतान कर दूँगा। | मैं 3 नवंबर को यूपीआई से भुगतान कर दूँगा। | 0.989 |
| hi10 | transcribe | क्या देरी का जुर्माना तीन सौ रुपये है? | क्या डेरी का जुर्माना ₹300 है? | 0.989 |
| hi10 | codemix | क्या देरी का जुर्माना तीन सौ रुपये है? | क्या डेरी का जुर्माना ₹300 है? | 0.989 |
| hg07 | codemix | Agar saat tareekh ke baad bharunga toh kya hoga? | अगर 7th के बाद भरूंगा तो क्या होगा? | 0.990 |


## Latency

Latest run: 2026-10-22T12:08:44Z; machine: Linux-7.2.11-zen1-1-zen-x86_64-with-glibc2.44; region: Asia/Kolkata local machine timezone; LLM: openai-compatible/deepseek-v4-flash.

### Timing definitions

- `t0`: perf_counter immediately after the last real-time audio chunk is sent
- `stt_final_ms`: t0 to final transcript
- `llm_first_token_ms`: final transcript to first LLM token
- `tts_first_audio_ms`: first complete sentence sent to TTS to first audio byte
- `end_to_end_ms`: t0 to first TTS audio byte

### Overall

| Provider combination | Field | Count | Failures | p50 ms | p95 ms | Max ms |
| --- | --- | --- | --- | --- | --- | --- |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | stt_first_partial_ms | 100 | 0 | 2602.6 | 4323.9 | 4914.6 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | stt_final_ms | 100 | 0 | 267.5 | 338.8 | 1400.2 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | llm_first_token_ms | 100 | 0 | 789.0 | 1027.0 | 13760.7 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | tts_first_audio_ms | 100 | 0 | 330.2 | 769.7 | 5382.5 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | end_to_end_ms | 100 | 0 | 1611.7 | 2699.0 | 19726.4 |

### By language

| Provider combination | Language | Field | Count | p50 ms | p95 ms | Max ms |
| --- | --- | --- | --- | --- | --- | --- |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | en | stt_first_partial_ms | 36 | 2678.6 | 4902.8 | 4914.6 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | en | stt_final_ms | 36 | 269.2 | 308.3 | 1400.2 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | en | llm_first_token_ms | 36 | 800.8 | 984.5 | 1095.4 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | en | tts_first_audio_ms | 36 | 352.1 | 1798.5 | 5382.5 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | en | end_to_end_ms | 36 | 1545.5 | 3535.9 | 6793.2 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | hi | stt_first_partial_ms | 32 | 2640.1 | 3900.9 | 3913.1 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | hi | stt_final_ms | 32 | 267.2 | 301.2 | 338.7 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | hi | llm_first_token_ms | 32 | 797.0 | 1057.5 | 13760.7 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | hi | tts_first_audio_ms | 32 | 364.4 | 3545.1 | 5319.2 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | hi | end_to_end_ms | 32 | 1779.7 | 5017.4 | 19726.4 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | hinglish | stt_first_partial_ms | 32 | 2593.8 | 3493.6 | 3511.2 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | hinglish | stt_final_ms | 32 | 266.9 | 559.3 | 1126.1 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | hinglish | llm_first_token_ms | 32 | 769.1 | 971.9 | 1047.7 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | hinglish | tts_first_audio_ms | 32 | 190.2 | 324.2 | 595.7 |
| llm: openai-compatible/deepseek-v4-flash, stt: sarvam/saaras:v3-realtime, tts: sarvam/bulbul:v3 | hinglish | end_to_end_ms | 32 | 1601.8 | 2321.9 | 2642.8 |

### Turns where stage sum differs by more than fifty milliseconds

Count: 96 of 100 turns.

| Utterance | Repeat | Difference ms |
| --- | --- | --- |
| en01 | 1 | 81.1 |
| hi01 | 1 | 310.6 |
| hg01 | 1 | 421.4 |
| en02 | 1 | 115.8 |
| hi02 | 1 | 464.7 |
| hg02 | 1 | 312.0 |
| en03 | 1 | 130.6 |
| hi03 | 1 | 387.8 |
| hg03 | 1 | 437.6 |
| en04 | 1 | 197.9 |
| hi04 | 1 | 184.2 |
| hg04 | 1 | 513.3 |
| en05 | 1 | 220.1 |
| hi05 | 1 | 288.8 |
| hg05 | 1 | 442.1 |
| en06 | 1 | 163.0 |
| hi06 | 1 | 372.4 |
| hg06 | 1 | 696.9 |
| en07 | 1 | 105.4 |
| hi07 | 1 | 339.8 |
| hg07 | 1 | 233.7 |
| en08 | 1 | 131.1 |
| hi08 | 1 | 379.4 |
| hg08 | 1 | 453.9 |
| en09 | 1 | 120.7 |
| en01 | 2 | 109.9 |
| hi01 | 2 | 418.6 |
| hg01 | 2 | 428.1 |
| hi02 | 2 | 626.5 |
| hg02 | 2 | 445.3 |
| en03 | 2 | 121.7 |
| hi03 | 2 | 417.9 |
| hg03 | 2 | 382.1 |
| en04 | 2 | 178.6 |
| hi04 | 2 | 191.8 |
| hg04 | 2 | 445.2 |
| en05 | 2 | 154.7 |
| hi05 | 2 | 402.1 |
| hg05 | 2 | 408.1 |
| en06 | 2 | 136.0 |
| hi06 | 2 | 339.2 |
| hg06 | 2 | 419.3 |
| hi07 | 2 | 285.1 |
| hg07 | 2 | 412.2 |
| en08 | 2 | 145.0 |
| hi08 | 2 | 356.5 |
| hg08 | 2 | 294.6 |
| en09 | 2 | 94.3 |
| hi01 | 3 | 420.7 |
| hg01 | 3 | 414.3 |
| hi02 | 3 | 432.3 |
| hg02 | 3 | 535.8 |
| en03 | 3 | 116.7 |
| hi03 | 3 | 391.2 |
| hg03 | 3 | 403.0 |
| en04 | 3 | 217.4 |
| hi04 | 3 | 382.9 |
| hg04 | 3 | 262.0 |
| en05 | 3 | 95.9 |
| hi05 | 3 | 301.4 |
| hg05 | 3 | 393.7 |
| en06 | 3 | 113.5 |
| hi06 | 3 | 382.9 |
| hg06 | 3 | 637.9 |
| en07 | 3 | 149.5 |
| hi07 | 3 | 279.7 |
| hg07 | 3 | 390.1 |
| en08 | 3 | 116.7 |
| hi08 | 3 | 420.1 |
| hg08 | 3 | 360.6 |
| en09 | 3 | 98.2 |
| en01 | 4 | 127.5 |
| hi01 | 4 | 322.8 |
| hg01 | 4 | 298.7 |
| en02 | 4 | 72.0 |
| hi02 | 4 | 327.7 |
| hg02 | 4 | 317.0 |
| en03 | 4 | 86.7 |
| hi03 | 4 | 228.5 |
| hg03 | 4 | 432.5 |
| en04 | 4 | 185.9 |
| hi04 | 4 | 476.9 |
| hg04 | 4 | 272.1 |
| en05 | 4 | 183.6 |
| hi05 | 4 | 364.3 |
| hg05 | 4 | 437.4 |
| en06 | 4 | 94.5 |
| hi06 | 4 | 413.6 |
| hg06 | 4 | 624.2 |
| en07 | 4 | 79.6 |
| hi07 | 4 | 253.9 |
| hg07 | 4 | 227.3 |
| en08 | 4 | 138.3 |
| hi08 | 4 | 504.2 |
| hg08 | 4 | 324.6 |
| en09 | 4 | 167.8 |

The stage sum is `stt_final + llm_first_token + tts_first_audio`. It omits the time from the first LLM token to the first complete sentence and any scheduling or network gaps between stages. Positive differences are expected because sentence assembly is part of end-to-end latency but not part of the first-token duration.

## Scenarios

Judging method: classifier; model: featherless-ai/gemma-4-26B-A4B-classifier; questions per conversation: 5.

These are **training-set** results; the 20 scenarios were used to write the prompts.

### Pass rate by prompt version

| Version | Runs | Passed | Pass rate | Judge errors |
| --- | --- | --- | --- | --- |
| v1 | 60 | 7 | 11.7% | 0 |
| v2 | 60 | 43 | 71.7% | 0 |
| v3 | 60 | 55 | 91.7% | 0 |
| v4 | 60 | 50 | 83.3% | 0 |

### Pass rate by category

| Version | Category | Runs | Pass rate |
| --- | --- | --- | --- |
| v1 | abusive | 3 | 0.0% |
| v1 | already_paid | 6 | 0.0% |
| v1 | amount_dispute | 3 | 0.0% |
| v1 | call_later | 3 | 0.0% |
| v1 | happy_path | 6 | 0.0% |
| v1 | hardship | 3 | 0.0% |
| v1 | identity_refusal | 3 | 0.0% |
| v1 | interruption | 3 | 0.0% |
| v1 | language_switch | 3 | 0.0% |
| v1 | late_fee | 3 | 0.0% |
| v1 | legal_threat | 3 | 0.0% |
| v1 | numbers_for_tts | 3 | 0.0% |
| v1 | out_of_scope | 3 | 0.0% |
| v1 | payment_method | 3 | 100.0% |
| v1 | prompt_injection | 3 | 33.3% |
| v1 | silence | 3 | 100.0% |
| v1 | wants_human | 3 | 0.0% |
| v1 | wrong_person | 3 | 0.0% |
| v2 | abusive | 3 | 100.0% |
| v2 | already_paid | 6 | 66.7% |
| v2 | amount_dispute | 3 | 0.0% |
| v2 | call_later | 3 | 33.3% |
| v2 | happy_path | 6 | 100.0% |
| v2 | hardship | 3 | 66.7% |
| v2 | identity_refusal | 3 | 100.0% |
| v2 | interruption | 3 | 100.0% |
| v2 | language_switch | 3 | 100.0% |
| v2 | late_fee | 3 | 0.0% |
| v2 | legal_threat | 3 | 100.0% |
| v2 | numbers_for_tts | 3 | 0.0% |
| v2 | out_of_scope | 3 | 100.0% |
| v2 | payment_method | 3 | 0.0% |
| v2 | prompt_injection | 3 | 100.0% |
| v2 | silence | 3 | 100.0% |
| v2 | wants_human | 3 | 100.0% |
| v2 | wrong_person | 3 | 100.0% |
| v3 | abusive | 3 | 100.0% |
| v3 | already_paid | 6 | 100.0% |
| v3 | amount_dispute | 3 | 33.3% |
| v3 | call_later | 3 | 33.3% |
| v3 | happy_path | 6 | 100.0% |
| v3 | hardship | 3 | 100.0% |
| v3 | identity_refusal | 3 | 100.0% |
| v3 | interruption | 3 | 66.7% |
| v3 | language_switch | 3 | 100.0% |
| v3 | late_fee | 3 | 100.0% |
| v3 | legal_threat | 3 | 100.0% |
| v3 | numbers_for_tts | 3 | 100.0% |
| v3 | out_of_scope | 3 | 100.0% |
| v3 | payment_method | 3 | 100.0% |
| v3 | prompt_injection | 3 | 100.0% |
| v3 | silence | 3 | 100.0% |
| v3 | wants_human | 3 | 100.0% |
| v3 | wrong_person | 3 | 100.0% |
| v4 | abusive | 3 | 100.0% |
| v4 | already_paid | 6 | 100.0% |
| v4 | amount_dispute | 3 | 0.0% |
| v4 | call_later | 3 | 100.0% |
| v4 | happy_path | 6 | 100.0% |
| v4 | hardship | 3 | 100.0% |
| v4 | identity_refusal | 3 | 0.0% |
| v4 | interruption | 3 | 100.0% |
| v4 | language_switch | 3 | 100.0% |
| v4 | late_fee | 3 | 100.0% |
| v4 | legal_threat | 3 | 66.7% |
| v4 | numbers_for_tts | 3 | 100.0% |
| v4 | out_of_scope | 3 | 100.0% |
| v4 | payment_method | 3 | 100.0% |
| v4 | prompt_injection | 3 | 100.0% |
| v4 | silence | 3 | 0.0% |
| v4 | wants_human | 3 | 100.0% |
| v4 | wrong_person | 3 | 100.0% |

### Inconsistent scenarios

| Version | Inconsistent | Scenario ids |
| --- | --- | --- |
| v1 | 1 | s16 |
| v2 | 3 | s04, s08, s17 |
| v3 | 3 | s05, s08, s13 |
| v4 | 1 | s18 |

### Deterministic check failures

| Check | Failed turns |
| --- | --- |
| no_digits | 81 |
| word_count | 62 |

### Top failure causes

### v1

| Failure cause | Count |
| --- | --- |
| Deterministic check failed | 42 |
| One or more expected behaviors were not met. At least one forbidden behavior occurred. | 9 |
| One or more expected behaviors were not met. | 2 |

### v2

| Failure cause | Count |
| --- | --- |
| One or more expected behaviors were not met. | 17 |

### v3

| Failure cause | Count |
| --- | --- |
| Deterministic check failed | 2 |
| At least one statement was unsupported or factually wrong. | 1 |
| One or more expected behaviors were not met. At least one statement was unsupported or factually wrong. | 1 |
| One or more expected behaviors were not met. | 1 |

### v4

| Failure cause | Count |
| --- | --- |
| Deterministic check failed | 4 |
| One or more expected behaviors were not met. At least one forbidden behavior occurred. | 3 |
| One or more expected behaviors were not met. | 3 |


## Held-out test

This is the held-out result, separate from the training score.

| Prompt | Runs | Passed | Pass rate | Rerun |
| --- | --- | --- | --- | --- |
| final | 30 | 14 | 46.7% | False |
| v1 | 30 | 0 | 0.0% | False |

### Frozen hashes

| Artifact | SHA-256 |
| --- | --- |
| Scenarios | 7c8c129edc1db666df9c8c24348a9d15c6b5aa44399fdcd1073a9ede16e9b069 |
| Classifier | d25cec8c308634b11c60f34329d7bbce4095f51e4401e2a18e6cb58d933f68d3 |
| v1 prompt | 463cc2c871f0e92147f17899dfbe2173217660dbea965bae1d5f66b2ebdd9258 |
| final prompt | dd2cb19a7875da8a803953ae0d8f7ba9aac285fe497464f652b3755ffada2900 |

## Classifier calibration

Current calibration sample. Source: `labels.json`.

| Group | n | Agreement | Agreement 95% CI | False-pass | False-pass 95% CI | Cohen kappa | Kappa 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Overall | 40 | 87.5% | 73.9–94.5% | not available | not available | 0.375 | -0.081–0.787 |
| Conversations | 25 | 88.0% | 70.0–95.8% | not available (0 human failures) | not available | 0.000 | 0.000–1.000 |
| STT | 15 | 86.7% | 62.1–96.3% | not available | not available | 0.595 | 0.000–1.000 |

## Check and scenario changelogs

### CHECKS_CHANGELOG.md

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

### scenarios_CHANGELOG.md

# Scenario changelog

## 2026-10-22

No scenario expectations were changed during the BENCHMARK2 work. Diagnostics
showed that the happy-path failures came from the old prompt-overlap check and
from agent language behavior, not from contradictory scenarios.

### CLASSIFIER_CHANGELOG.md

# Classifier calibration changelog

## Calibration round 1

- Sample: 25 conversation labels and 15 STT labels.
- Conversation agreement was 72.0%, Cohen's kappa 0.112, and false-pass rate
  50.0%, below the required thresholds.
- Question changed: `expected_behaviors_met` now requires a strict review
  standard and explicitly rejects invented customer agreement, including
  assuming agreement from silence.
- Question changed: `language_mirrored` now treats Hindi and Romanized Hinglish
  as mutually acceptable in this bilingual dataset while keeping English
  distinct. This reflects the manual labels.
- Both `yes=good` polarities are unchanged.
- Action: rerun every prompt version with the revised questions and calibrate a
  fresh sample. The previous labeled sample is not relabeled.

## Calibration round 2

- Sample: 25 conversation labels and 15 STT labels.
- The calibration tool was corrected to compare the human label with the
  classifier verdict. It previously used the combined deterministic and
  classifier pass flag.
- Conversation disagreement still concentrated on Hindi versus Romanized
  Hinglish replies and on the strict script wording.
- Question changed: `language_mirrored` now asks whether a speaker of the
  customer's current language can understand each reply without translation.
  Script differences are ignored within the Hindi/Hinglish family.
- Action: rerun every prompt version and collect another fresh sample. No
  previous item is relabeled.

## Calibration round 3 preparation

- Corrected calibration labels now compare the classifier-only verdict rather
  than the combined deterministic and classifier result.
- The language question was reduced to comprehension within the customer's
  language family, ignoring script between Hindi and Romanized Hinglish.
- All prompt versions were rerun with the revised question.
- A third fresh sample is required. Previous labels remain archived and are not
  reused.

## Final calibration

- Fresh conversation sample: 25 labels.
- Reused STT sample: 15 labels, because the STT question did not change.
- Overall agreement: 87.5%, approximate 95% interval 73.9% to 94.5%.
- Conversation agreement: 88.0%, approximate 95% interval 70.0% to 95.8%.
- False-pass rate: 0% because the manual sample contained no human failures.
- The thresholds passed. No further question changes were made before the
  held-out run.
