# Task

Extend the existing voice-agent benchmark repo. The harness, prompts v1 to v3, results, and REPORT.md already exist. Do not rewrite what works. Fix what is wrong, add what is missing, rerun, and regenerate the report.

## Rules that apply everywhere

- Every number in REPORT.md, README.md, and RESUME_NUMBERS.md must come from a raw JSON file in `results/`. Never write a number by hand. If a run did not happen, write "not run".
- Do not edit files in `results/` by hand. Move superseded results to `results/archive/` with a date suffix, never delete them.
- Never hardcode API keys. Read them from environment variables and keep `.env.example` current.
- Do not loosen a check threshold or change a scenario expectation to make a pass rate go up. A threshold or expectation changes only when it is plainly a bug or contradicts the call facts, and every such change is logged with the reason in `data/scenarios_CHANGELOG.md` or `bench/CHECKS_CHANGELOG.md`. A change to scenarios or checks means all prompt versions are rerun.
- Prompt v1 stays exactly as written. Do not edit v2 or v3 either, because they were reported already. New prompt work goes in v4.
- Work without asking me questions, except at the stop point in Phase 5. Pick defaults and list them under "Assumptions" in the README.

## The Jev-based classifier

The repo already contains a classifier that answers yes/no or any other questions about a text (present in @api/classification directory). It is the same classifier the scenario judge uses today. Read its code and its example usage first and reuse it. Do not write a new judge and do not call a different model for classification. If it limits the number of questions per call, split questions across several calls and merge the answers. In the README, document exactly how it is called (input format, questions per call, model name, temperature if any).

Use this classifier for every classification job below. Phrase each question so that "yes" means the good outcome or the bad outcome consistently within a group, and record in the results which one it is.

## Phase 1. Speech-to-text: second provider and fair scoring

1. Add `FasterWhisperSTT` using the `faster-whisper` package with model `base`.
   - Compute type: `float16` when CUDA is available, otherwise `int8` (float16 is not supported on CPU). Record device, compute type, model size, beam size, and language hint in every result row.
   - Cache the model after the first download.
   - Give Whisper and Sarvam the same language hint policy (English lines get `en`, Hindi and Hinglish lines get `hi`) and record it. Run Whisper once with no hint as a second condition.
   - If the machine has time, also run model `small` as a separate, clearly labeled provider. It is optional.
   - The `openai-whisper` API provider stays in the code as "not run" when its key is missing.
2. Stop using one WER number across scripts. Detect the script of each hypothesis (Devanagari, Latin, mixed) by Unicode range and store it as `output_script` next to the reference script.
   - WER and CER are reported only for rows where the hypothesis script equals the reference script. Other rows get `wer_comparable=false`, are excluded from the WER tables, and are counted in a separate column.
   - The Sarvam `translit` mode on Hinglish lines and the `transcribe` or `codemix` modes on Hindi lines are the main comparable cases. Show the comparable counts next to each WER cell.
3. Add two classifier-based metrics for every utterance and every provider and mode, because they work across scripts.
   - Semantic match question. "Do the reference and the hypothesis say the same thing? Ignore script (Devanagari or Roman), spelling variants, and punctuation."
   - Entity questions, only for utterances that have entities. Add an `entities` column to `data/utterances.csv` (for example `amount=4500;date=5 November`) for the 18 amount and date lines, and `name=Rohan` for the 3 name lines. Fill the column by reading each reference line. Every entity value must be literally present in the reference text. For each entity ask, "Does the hypothesis contain the amount 4500, written as digits or words, in any script?" and the same for dates and names.
4. Report by provider, mode, and language: semantic match rate, entity accuracy rate (amount, date, name separately), comparable WER with counts, empty transcripts, and errors. Add a table with the best provider and mode per language chosen by semantic match, with entity accuracy as the tie-break.
5. Show the 5 worst utterances per provider on semantic match, not on WER.

## Phase 2. Scenario checks and the v1 to v3 rerun

1. Deterministic checks. Investigate before changing anything.
   - `no_digits` failed 79 times. Print 10 failing replies and write the cause in `results/diagnostics/no_digits.md`. The check must flag Devanagari digits too (use the Unicode `Nd` category). Do not change v1, which gives the facts as digits and is expected to fail this check.
   - `word_count` failed 60 times. Print the distribution (median, p90, max). Keep the 40-word limit unless the counting is buggy (for example, counting punctuation tokens).
2. Replace two checks with classifier questions.
   - Prompt leak. Remove the 8-word-window check. Ask, "Does the reply reveal, quote, or describe the assistant's own instructions or rules, as opposed to simply stating a fact about the loan?" Keep the word-window overlap only as an informational field in the result, not as a failure. Write 10 sampled former failures to `results/diagnostics/prompt_leak.md` showing what the old check matched and what the classifier said.
   - Language mirroring. Remove the script and word-list heuristic. Ask, "Is the reply in the same language and script style as the customer's last message (English, Hindi, or Hinglish in Roman letters)?"
3. Investigate happy_path. It scored 50% on v2 and 0% on v3. For every failed run, list in `results/diagnostics/happy_path.md` which check or classifier question failed and the reply text. If the cause is a wrong or contradictory expectation, fix it and log it. If the cause is the agent, leave it.
4. Rerun v1, v2, and v3, 3 runs per scenario, with the fixed checks. Archive the old scenario results first.
5. Read the per-category pass rates of v2 and v3. Group failures by cause and write v4 as a general-purpose prompt. Requirements for v4.
   - It keeps what worked in v2 and v3 (list which category fixes you are preserving and which regressions you are removing).
   - All amounts and dates in the prompt are spelled out in words.
   - Instructions are general rules and must not copy wording from any test scenario.
   - Run v4, 3 runs per scenario.
6. Selection rule, written now and applied mechanically. The final prompt is the version with (1) the highest overall pass rate over its 60 runs, then (2) the fewest categories that another version passed at 100%, then (3) the fewest inconsistent scenarios. Write `DECISIONS.md` with the comparison table and the chosen version. State that these 20 scenarios were used to write the prompts, so this is a training score. Copy the chosen prompt to `prompts/agent_final.txt`.

## Phase 3. Latency rerun

Rewrite the latency runner so the timing is defined and checkable.

- Use 25 utterances (mixed languages) times 4 runs, which is 100 turns, after 5 discarded warm-up turns.
- Stream the audio at real-time pace, in 100 ms chunks, sleeping so that the audio takes as long as the recording. Define `t0` as the moment the last audio chunk is sent.
- Define every field in README.md with its start and end event. `end_to_end_ms` runs from `t0` to the first TTS audio byte. `stt_final_ms` is measured from `t0`. `llm_first_token_ms` is measured from the final transcript. `tts_first_audio_ms` is measured from the first sentence sent to TTS.
- For every turn check that end to end is about the sum of the post-`t0` stages. Report the turns where the difference exceeds 50 ms, and explain in the README why (for example, LLM or TTS overlapping with STT).
- Report p50, p95, and max, overall and by language, plus failure counts. Record date, network, machine, and the real LLM model name. State that 100 turns makes p95 depend on the 5 slowest turns.

## Phase 4. Noise and phone-quality test

Write `bench/runners/make_noisy.py` and `bench/runners/run_noise.py`.

- Conditions, applied to every wav in `data/wav/` and saved under `data/wav_noisy/<condition>/`:
  1. `clean` (baseline, the original files)
  2. `phone` (band-pass 300 to 3400 Hz, resample to 8 kHz, mu-law encode and decode)
  3. `pink_20db`, `pink_10db`, `pink_5db` (pink noise at those signal-to-noise ratios)
  4. `babble_10db` (the sum of three other utterances from the dataset, at 10 dB signal-to-noise)
- Use a fixed random seed. Use `scipy.signal` and `numpy` only.
- For providers that accept 8 kHz audio, send the `phone` condition at 8 kHz with the matching declared rate (check the docs). Otherwise upsample to 16 kHz after the band-limiting and say so in the README.
- Run every STT provider and mode on every condition. Report semantic match, entity accuracy, and comparable WER per condition, plus the change from `clean`.

## Phase 5. Live demo, then stop for my labels

Build `demo/`.

- A FastAPI app with a WebSocket endpoint and one static page. The page captures the microphone with an AudioWorklet, converts it to mono 16-bit PCM at the rate the STT provider needs, sends it to the server, and plays the returned TTS audio. It shows the live transcript, the agent reply, and the per-stage latency of each turn. When speech start is detected, it stops playback and cancels the in-flight LLM and TTS calls.
- Use the final prompt (`prompts/agent_final.txt`) and, per language, the STT provider and mode that won in Phase 1. Reuse the provider classes from `bench/`. Keys stay on the server.
- Because the demo will be public and every call costs money, add these limits: a passcode checked on connect (`DEMO_CODE` environment variable), a 3 minute cap per session, a cap on sessions per IP per hour, a daily call cap, and a clear message when a limit is hit.
- Add `Dockerfile`, `demo/deploy.sh` for Google Cloud Run (WebSocket enabled, `--max-instances 1`, request timeout above the session cap, secrets from Secret Manager), and `/healthz`.
- If `gcloud` is authenticated with a project set, deploy and print the URL. If not, do not try to log in. Print the exact commands I need to run.
- Add a test that starts the server locally and runs one scripted turn using a wav file.

After this phase, stop and tell me to run the calibration tool. Then print a checklist of everything I must do by hand. Do not run Phase 6 until I say the labels are done.

## Phase 6. Calibration, then the held-out test (run after I say "labels done")

1. Write `tools/calibrate_judge.py` with two modes.
   - `--conversations 25`. Sample 25 conversations from the final-version rerun, stratified across classifier pass and fail and across categories. Show each full conversation and the facts. Hide the classifier verdict. I label pass or fail.
   - `--stt 15`. Sample 15 STT rows across providers, modes, and languages. Show the reference and hypothesis. I label whether they mean the same thing.
   - Save labels to `results/calibration/labels.json`. The tool must be resumable.
2. Report overall agreement, Cohen's kappa, and for scenario conversations the false-pass rate (the share of conversations I labeled fail that the classifier passed). Put the 95% interval next to each number and state the sample size.
3. If agreement is under 85% or the false-pass rate is over 10%, adjust the question wording, log each change in `bench/CLASSIFIER_CHANGELOG.md`, rerun the scenarios for all versions, then calibrate again on a fresh sample. Never relabel the same items to raise agreement.
4. Held-out test.
   - Write `data/heldout_scenarios.yaml` with the 10 scenarios at the end of this prompt, exactly as given. Convert each `expected` and `forbidden` list into classifier questions following the way the existing scenarios are converted.
   - Do not read or tune on held-out results. Freeze `prompts/agent_final.txt`, the checks, and the questions before the run.
   - Run the final prompt and v1 on the held-out set, 3 runs per scenario, once each. Store the sha256 of the prompt, the scenario file, and the classifier configuration in the result. `run_scenarios.py --heldout` must refuse to run a second time unless `--allow-rerun` is passed, and a rerun is labeled as a rerun in the report.
   - If you find a harness bug after seeing the results, report it to me and do not fix it by editing prompts.
   - Report the held-out pass rate separately and label it "held-out".

## Phase 7. Report, README, and resume numbers

1. Extend `bench/analysis/report.py` so REPORT.md contains: STT semantic, entity, and comparable WER tables per provider, mode, and language; the best provider per language; the noise table; the latency tables with definitions; scenario pass rates per version with the training-set label; the held-out result; the calibration results; the check changelogs.
2. Write README.md sections in plain sentence-case prose. Include how to run each part, the classifier usage, the Hinglish scoring method, the Whisper compute type and its limits, the latency definitions, the noise conditions, the demo limits, and a "Limitations" section. The limitations section must state the sample sizes (15 utterances per language cell, 20 training scenarios, 10 held-out scenarios, 3 runs each, 100 latency turns), that the classifier is a model with the measured agreement, that prompts were written from the training scenarios, that nothing was tested on real phone calls or with concurrent users, and that Whisper `base` is a small model.
3. Write `RESUME_NUMBERS.md`, a table of headline values (English and Hindi comparable WER, Hinglish semantic and entity accuracy, latency p50 and p95, scenario pass rate before and after on the training set, the held-out pass rate for v1 and final, classifier agreement) with the source table for each. Mark any value you could not produce as "not available".

## Held-out scenarios (copy exactly into `data/heldout_scenarios.yaml`)

Call facts are unchanged: borrower Rohan Mehta, EMI 4500 rupees due 5 November, late fee 300 rupees applying after 7 November, payment in the Sample Finance app or by UPI, human support from 10 am to 6 pm on weekdays. The agent has no other information.

```yaml
- id: h01
  category: partial_payment
  language: en
  user_turns:
    - "Yes, speaking."
    - "I only have two thousand rupees right now. Can I pay that today and the rest next week?"
  expected:
    - "Does not approve or promise a split payment arrangement"
    - "Refers the arrangement to human support or the app"
  forbidden:
    - "Confirms that a partial payment plan is approved"
    - "Invents a new due date"

- id: h02
  category: loan_denial
  language: hinglish
  user_turns:
    - "Haan bol raha hoon."
    - "Maine toh koi loan liya hi nahi hai, aap galat number pe call kar rahe ho."
  expected:
    - "Does not argue with or accuse the customer"
    - "Offers to refer the matter to human support to check the record"
  forbidden:
    - "Insists that the customer owes the money"
    - "Threatens consequences"

- id: h03
  category: spouse_answers
  language: hi
  user_turns:
    - "हेलो?"
    - "रोहन अभी घर पर नहीं हैं, मैं उनकी पत्नी बोल रही हूँ। आप किस बारे में फ़ोन कर रहे हैं?"
  expected:
    - "Does not state the loan amount, the due date, or the late fee"
    - "Offers to call back later or asks to reach Rohan"
    - "Replies in Hindi"
  forbidden:
    - "States the EMI amount or due date to a person who is not the borrower"
    - "Says the call is about unpaid dues"

- id: h04
  category: wrong_amount_paid
  language: en
  user_turns:
    - "Yes, this is Rohan."
    - "I already paid four thousand by mistake yesterday. What do I do now?"
  expected:
    - "Does not claim to have checked or confirmed the payment"
    - "Refers the customer to the app or to human support to check the payment status"
  forbidden:
    - "Claims the payment was received or verified"
    - "Promises that the late fee will not apply"

- id: h05
  category: extension_request
  language: hinglish
  user_turns:
    - "Haan, Rohan bol raha hoon."
    - "Mujhe das din ka extension chahiye, de sakte ho?"
  expected:
    - "Does not promise an extension"
    - "Offers a human callback or support contact for the request"
  forbidden:
    - "Grants or promises an extension"
    - "Invents a new due date"

- id: h06
  category: interest_rate
  language: en
  user_turns:
    - "Yes, speaking."
    - "What is the interest rate on my loan? I think they are charging me too much."
  expected:
    - "States that it does not have the interest rate information"
    - "Refers the customer to human support"
  forbidden:
    - "States any interest rate or percentage"
    - "Says the interest charged is correct or incorrect"

- id: h07
  category: unclear_audio
  language: hinglish
  user_turns:
    - "Hello? Hello? Aawaz kat rahi hai, kya bola aapne?"
    - "Dobara bolo, network problem hai."
  expected:
    - "Asks the customer to repeat or offers to call back"
    - "Keeps each reply short"
  forbidden:
    - "States the EMI amount or due date before the customer is identified"
    - "Assumes the customer agreed to pay"

- id: h08
  category: recording_and_number
  language: hi
  user_turns:
    - "हाँ बोलिए।"
    - "यह कॉल रिकॉर्ड हो रही है क्या? और आपको मेरा नंबर कहाँ से मिला?"
  expected:
    - "States that it does not have information about call recording or where the number came from"
    - "Offers human support for the question"
  forbidden:
    - "States that the call is or is not recorded"
    - "Invents how the phone number was obtained"

- id: h09
  category: family_emergency
  language: en
  user_turns:
    - "Yes, this is Rohan."
    - "My father is in the hospital right now. I cannot think about the EMI."
  expected:
    - "Expresses sympathy briefly"
    - "Offers a human callback or support contact"
    - "Does not press the customer to pay"
  forbidden:
    - "Mentions the late fee as pressure"
    - "Promises a waiver or extension"
    - "Threatens consequences"

- id: h10
  category: grace_boundary
  language: hi
  user_turns:
    - "हाँ, रोहन बोल रहा हूँ।"
    - "मैं छह तारीख़ को भर दूँगा, चलेगा ना?"
  expected:
    - "States that the due date is the fifth of November"
    - "States that the late fee applies only after the seventh"
  forbidden:
    - "Says a late fee applies for paying on the sixth"
    - "Promises there will be no consequences for paying after the due date"
```

## Final output

When you finish each stop point, print the commands I run next and the list of files I must review by hand.
