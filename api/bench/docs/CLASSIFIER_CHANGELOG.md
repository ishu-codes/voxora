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
