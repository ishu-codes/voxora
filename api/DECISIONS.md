# Prompt decision

These 20 scenarios were used to write the prompts. The selected score is a training score, not a held-out score.

| Version | Runs | Passed | Pass rate | Categories lost to a 100% version | Inconsistent scenarios |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1 | 60 | 7 | 11.7% | 15 | 1 |
| v2 | 60 | 43 | 71.7% | 6 | 3 |
| v3 | 60 | 55 | 91.7% | 2 | 3 |
| v4 | 60 | 50 | 83.3% | 3 | 1 |

Selected version: **v3**. The selection applies the specified order: highest overall pass rate, then fewest categories another version passed completely, then fewest inconsistent scenarios. An exact remaining tie is resolved by choosing the earlier version identifier, which is the documented deterministic tie-break.

`prompts/agent_final.txt` is copied from `prompts/agent_v3.txt`.
