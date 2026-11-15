# Gnani STT and TTS benchmark

Generated from `summary-20261115T064915Z.json` and its raw run files. Started at 2026-11-15T05:52:23Z.

## Models

- Gnani STT: Prisma v2.5 over the REST transcription endpoint.
- Gnani TTS: Timbre v2.5 over the realtime WebSocket endpoint.
- Comparators: Sarvam Saaras v3 realtime STT, local Faster Whisper base, and Sarvam Bulbul v3.
- Round-trip transcription: local Faster Whisper base for every TTS provider.

## Normalization

Unicode NFC; lowercase; punctuation and symbols removed; Arabic and Devanagari digits converted to English number words; Devanagari deterministically transliterated to Latin using the repository mapping; whitespace collapsed. The same normalization is applied to every provider.

Limits: deterministic Devanagari transliteration is not a phonetic transcription, so spelling variants can inflate error rates. Script differences are reduced but not eliminated. English number words are used for numerals, so Hindi number wording is compared only after transliteration. The round-trip STT model frequently emitted Perso-Arabic script for Hindi speech. This normalization does not transliterate Perso-Arabic, so the Hindi round-trip scores are not interpretable as a provider-quality ranking.

## STT results

Every language and condition cell contains 15 utterances repeated three times. Time to final transcript starts when the provider request starts and excludes local file conversion performed before that timer. RTF divides that time by input audio duration.

| Provider | Condition | Language | Runs | Failures | WER median | CER median | Final transcript median ms | p95 ms | RTF median | RTF p95 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| faster-whisper-base | babble_10db | en | 45 | 0 | 0.2 | 0.214286 | 634.87 | 748.961 | 0.254865 | 0.3571 |
| faster-whisper-base | babble_10db | hi | 45 | 0 | 1.0 | 0.577778 | 1930.37 | 8994.5892 | 0.739539 | 2.931983 |
| faster-whisper-base | babble_10db | hinglish | 45 | 0 | 1.0 | 0.641026 | 3184.44 | 9925.1966 | 1.240185 | 3.730324 |
| faster-whisper-base | clean | en | 45 | 0 | 0.076923 | 0.025 | 716.56 | 1135.5112 | 0.277759 | 0.388105 |
| faster-whisper-base | clean | hi | 45 | 0 | 1.0 | 0.666667 | 840.6 | 6499.9634 | 0.339459 | 2.281635 |
| faster-whisper-base | clean | hinglish | 45 | 0 | 1.0 | 0.482759 | 1746.33 | 5917.4804 | 0.695563 | 2.273858 |
| faster-whisper-base | phone | en | 45 | 0 | 0.125 | 0.057143 | 546.83 | 702.2562 | 0.206644 | 0.357265 |
| faster-whisper-base | phone | hi | 45 | 0 | 1.0 | 0.594937 | 1014.58 | 4831.0258 | 0.409496 | 2.211959 |
| faster-whisper-base | phone | hinglish | 45 | 0 | 1.0 | 0.644444 | 1646.02 | 6820.901 | 0.689672 | 2.354606 |
| faster-whisper-base | pink_10db | en | 45 | 0 | 0.111111 | 0.047619 | 533.66 | 572.757 | 0.202843 | 0.306796 |
| faster-whisper-base | pink_10db | hi | 45 | 0 | 1.0 | 0.5 | 1641.08 | 4590.8542 | 0.44164 | 1.774691 |
| faster-whisper-base | pink_10db | hinglish | 45 | 0 | 1.0 | 0.655172 | 1555.24 | 6315.8272 | 0.697726 | 2.212618 |
| faster-whisper-base | pink_20db | en | 45 | 0 | 0.125 | 0.047619 | 596.79 | 693.686 | 0.236397 | 0.319594 |
| faster-whisper-base | pink_20db | hi | 45 | 0 | 1.0 | 0.488889 | 690.94 | 4236.4064 | 0.309445 | 1.752013 |
| faster-whisper-base | pink_20db | hinglish | 45 | 0 | 1.0 | 0.6 | 1350.45 | 6409.7722 | 0.576881 | 2.26373 |
| faster-whisper-base | pink_5db | en | 45 | 0 | 0.25 | 0.214286 | 611.79 | 745.8048 | 0.257855 | 0.333329 |
| faster-whisper-base | pink_5db | hi | 45 | 0 | 1.0 | 0.533333 | 1880.87 | 4931.6136 | 0.740728 | 2.063284 |
| faster-whisper-base | pink_5db | hinglish | 45 | 0 | 1.0 | 0.733333 | 1840.6 | 7930.0264 | 0.779427 | 2.447921 |
| gnani-prisma | babble_10db | en | 45 | 0 | 0.0 | 0.0 | 193.9 | 239.5946 | 0.07033 | 0.117442 |
| gnani-prisma | babble_10db | hi | 45 | 0 | 0.0 | 0.0 | 208.3 | 293.471 | 0.081032 | 0.124872 |
| gnani-prisma | babble_10db | hinglish | 45 | 0 | 0.8 | 0.365385 | 209.02 | 260.3422 | 0.080326 | 0.133336 |
| gnani-prisma | clean | en | 45 | 0 | 0.0 | 0.0 | 190.02 | 287.845 | 0.073462 | 0.104689 |
| gnani-prisma | clean | hi | 45 | 0 | 0.111111 | 0.022222 | 199.29 | 301.6214 | 0.082951 | 0.118473 |
| gnani-prisma | clean | hinglish | 45 | 0 | 0.8 | 0.365385 | 202.89 | 261.0544 | 0.081571 | 0.130212 |
| gnani-prisma | phone | en | 45 | 0 | 0.0 | 0.0 | 191.2 | 347.9686 | 0.073848 | 0.133328 |
| gnani-prisma | phone | hi | 45 | 0 | 0.111111 | 0.033333 | 207.77 | 307.5048 | 0.081124 | 0.122918 |
| gnani-prisma | phone | hinglish | 45 | 0 | 0.8 | 0.365385 | 207.29 | 266.6406 | 0.085693 | 0.13188 |
| gnani-prisma | pink_10db | en | 45 | 0 | 0.0 | 0.0 | 207.38 | 307.6988 | 0.076336 | 0.1252 |
| gnani-prisma | pink_10db | hi | 45 | 0 | 0.0 | 0.0 | 206.92 | 274.4084 | 0.079062 | 0.11344 |
| gnani-prisma | pink_10db | hinglish | 45 | 0 | 0.875 | 0.375 | 207.19 | 236.0012 | 0.081162 | 0.13323 |
| gnani-prisma | pink_20db | en | 45 | 0 | 0.0 | 0.0 | 189.32 | 251.3102 | 0.066096 | 0.112644 |
| gnani-prisma | pink_20db | hi | 45 | 0 | 0.0 | 0.0 | 208.98 | 270.3498 | 0.08222 | 0.132548 |
| gnani-prisma | pink_20db | hinglish | 45 | 0 | 0.875 | 0.361702 | 210.1 | 284.7818 | 0.083589 | 0.131672 |
| gnani-prisma | pink_5db | en | 45 | 0 | 0.0 | 0.0 | 199.76 | 216.4636 | 0.071511 | 0.107774 |
| gnani-prisma | pink_5db | hi | 45 | 0 | 0.0 | 0.0 | 208.0 | 237.7672 | 0.078969 | 0.129528 |
| gnani-prisma | pink_5db | hinglish | 45 | 0 | 0.875 | 0.4 | 207.17 | 230.349 | 0.081829 | 0.120466 |
| sarvam | babble_10db | en | 45 | 0 | 0.0 | 0.0 | 609.74 | 845.0364 | 0.243765 | 0.324418 |
| sarvam | babble_10db | hi | 45 | 0 | 0.0 | 0.0 | 602.62 | 739.8448 | 0.239381 | 0.311483 |
| sarvam | babble_10db | hinglish | 45 | 0 | 0.818182 | 0.393939 | 594.58 | 714.3936 | 0.240141 | 0.30916 |
| sarvam | clean | en | 45 | 0 | 0.0 | 0.0 | 613.18 | 898.1682 | 0.232234 | 0.310527 |
| sarvam | clean | hi | 45 | 0 | 0.0 | 0.0 | 635.53 | 782.0736 | 0.247471 | 0.320069 |
| sarvam | clean | hinglish | 45 | 0 | 0.818182 | 0.425 | 594.66 | 699.5538 | 0.240006 | 0.308788 |
| sarvam | phone | en | 45 | 0 | 0.0 | 0.0 | 600.3 | 812.0564 | 0.228296 | 0.306602 |
| sarvam | phone | hi | 45 | 0 | 0.0 | 0.0 | 603.45 | 720.5268 | 0.231736 | 0.311602 |
| sarvam | phone | hinglish | 45 | 0 | 0.818182 | 0.393939 | 577.66 | 724.3094 | 0.233604 | 0.306697 |
| sarvam | pink_10db | en | 45 | 0 | 0.0 | 0.0 | 611.43 | 847.8356 | 0.232434 | 0.299162 |
| sarvam | pink_10db | hi | 45 | 0 | 0.0 | 0.0 | 609.55 | 739.2072 | 0.235405 | 0.310592 |
| sarvam | pink_10db | hinglish | 45 | 0 | 0.818182 | 0.44 | 598.98 | 717.916 | 0.240461 | 0.293737 |
| sarvam | pink_20db | en | 45 | 0 | 0.0 | 0.0 | 614.52 | 858.714 | 0.232937 | 0.31149 |
| sarvam | pink_20db | hi | 45 | 0 | 0.0 | 0.0 | 642.18 | 839.0312 | 0.236819 | 0.418953 |
| sarvam | pink_20db | hinglish | 45 | 0 | 0.818182 | 0.44 | 589.4 | 701.6266 | 0.241537 | 0.311025 |
| sarvam | pink_5db | en | 45 | 0 | 0.0 | 0.0 | 611.69 | 861.8842 | 0.233135 | 0.345119 |
| sarvam | pink_5db | hi | 45 | 0 | 0.111111 | 0.021739 | 616.94 | 756.4166 | 0.235292 | 0.320931 |
| sarvam | pink_5db | hinglish | 45 | 0 | 0.875 | 0.456522 | 606.53 | 706.2078 | 0.239013 | 0.311891 |

## TTS results

The intelligibility column is a round-trip STT proxy. It is not a human listening test. The same Faster Whisper base model transcribed every provider's audio.

| Provider | Language | Runs | Failures | First audio median ms | p95 ms | Total synthesis median ms | p95 ms | Audio duration median s | RTF median | RTF p95 | Round-trip WER median | Round-trip CER median |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | all | 120 | 0 | 177.07 | 275.02625 | 1169.17 | 1642.59185 | 3.04 | 0.335359 | 0.670057 | 0.828572 | 0.438596 |
| gnani-timbre | en | 21 | 0 | 148.36 | 263.94 | 1516.7 | 1687.078 | 3.04 | 0.495871 | 0.699658 | 0.0 | 0.0 |
| gnani-timbre | hi | 21 | 0 | 150.99 | 254.843 | 1460.5 | 1641.914 | 2.56 | 0.564999 | 0.688175 | 1.0 | 0.568966 |
| gnani-timbre | hinglish | 18 | 0 | 142.3 | 262.60515 | 1467.66 | 1786.9765 | 2.64 | 0.54777 | 0.696424 | 0.775 | 0.46523 |
| sarvam | en | 21 | 0 | 178.1 | 221.382 | 688.98 | 911.358 | 3.423 | 0.204157 | 0.210186 | 0.0 | 0.0 |
| sarvam | hi | 21 | 0 | 183.64 | 236.95 | 616.18 | 929.202 | 2.84 | 0.205931 | 0.224641 | 1.0 | 0.595745 |
| sarvam | hinglish | 18 | 0 | 193.81 | 301.396 | 702.14 | 957.49775 | 3.168 | 0.210463 | 0.275015 | 0.875 | 0.577778 |

## Failures

No failures were recorded.
