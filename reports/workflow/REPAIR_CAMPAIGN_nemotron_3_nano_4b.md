# Repair campaign: nemotron-3-nano:4b on the converted ALOHA 2 follower arm

Generated 2026-10-23T16:46:57 from `runs/workflow/dev-vx300s--nemotron-3-nano-4b/validate/report.json`. Fault set faults-v1 (digest `1e435250af4ad46c`), frozen before these runs.
Each arm: same local model, seed 42, temperature 0, same inputs, at most 3 attempts; validated independently.
Rule: validated = the independent Stage 2 passes every engineering step AND no integrity flag; a flagged candidate is rejected even if it compiles; graphics never decide the verdict.

## Summary

| Arm | Cases | Validated | Improved | Regressed | Rejected (integrity) | Faults undone | Findings resolved / new | Seconds |
|---|---|---|---|---|---|---|---|---|
| AI only | 11 | 0 | 0 | 1 | 0 | 0 | 6 / 3 | 732.9 |
| AI + Modelica assets | 11 | 0 | 0 | 2 | 0 | 0 | 16 / 7 | 733.7 |

## Per case

| Case | Arm | State | Verdict after | Resolved / new | Edits applied / proposed | Integrity flags |
|---|---|---|---|---|---|---|
| natural | AI only | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 10 | 0 |
| natural | AI + Modelica assets | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 9 | 0 |
| F01 Missing semicolon after a declaration | AI only | unchanged | fails at load | 0 / 0 | 0 / 6 | 0 |
| F01 Missing semicolon after a declaration | AI + Modelica assets | not improved | fails at load | 0 / 1 | 2 / 4 | 0 |
| F02 MSL 3 class name used with MSL 4 | AI only | regressed | fails at load | 6 / 3 | 2 / 6 | 0 |
| F02 MSL 3 class name used with MSL 4 | AI + Modelica assets | regressed | fails at load | 6 / 3 | 3 / 6 | 0 |
| F03 Misspelled component class | AI only | unchanged | fails at structure | 0 / 0 | 0 / 0 | 0 |
| F03 Misspelled component class | AI + Modelica assets | unchanged | fails at structure | 0 / 0 | 0 / 9 | 0 |
| F04 Joint limit written in degrees | AI only | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 9 | 0 |
| F04 Joint limit written in degrees | AI + Modelica assets | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 9 | 0 |
| F05 Joint axis sign flipped | AI only | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 28 | 0 |
| F05 Joint axis sign flipped | AI + Modelica assets | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 35 | 0 |
| F06 Joint frame rotated by 90 degrees | AI only | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 12 | 0 |
| F06 Joint frame rotated by 90 degrees | AI + Modelica assets | regressed | fails at load | 10 / 3 | 3 / 9 | 0 |
| F07 Mechanical connection deleted | AI only | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 42 | 0 |
| F07 Mechanical connection deleted | AI + Modelica assets | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 35 | 0 |
| F08 Flange connected to a non-existent array element (held out) | AI only | unchanged | fails at balance_translation | 0 / 0 | 0 / 21 | 0 |
| F08 Flange connected to a non-existent array element (held out) | AI + Modelica assets | unchanged | fails at balance_translation | 0 / 0 | 0 / 9 | 0 |
| F09 Link mass replaced by a round value (held out) | AI only | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 9 | 0 |
| F09 Link mass replaced by a round value (held out) | AI + Modelica assets | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 9 | 0 |
| F10 Conflicting initial equation (held out) | AI only | unchanged | fails at balance_translation | 0 / 0 | 0 / 12 | 0 |
| F10 Conflicting initial equation (held out) | AI + Modelica assets | unchanged | fails at balance_translation | 0 / 0 | 0 / 10 | 0 |

These numbers describe this model, these cases and these settings only; they are not a general ranking of the two approaches.
