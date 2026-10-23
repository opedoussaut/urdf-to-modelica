# Repair campaign: qwen3-coder:30b on the converted ALOHA 2 follower arm

Generated 2026-10-23T16:46:58 from `runs/workflow/dev-vx300s--qwen3-coder-30b/validate/report.json`. Fault set faults-v1 (digest `1e435250af4ad46c`), frozen before these runs.
Each arm: same local model, seed 42, temperature 0, same inputs, at most 3 attempts; validated independently.
Rule: validated = the independent Stage 2 passes every engineering step AND no integrity flag; a flagged candidate is rejected even if it compiles; graphics never decide the verdict.

## Summary

| Arm | Cases | Validated | Improved | Regressed | Rejected (integrity) | Faults undone | Findings resolved / new | Seconds |
|---|---|---|---|---|---|---|---|---|
| AI only | 4 | 0 | 1 | 0 | 2 | 2 | 12 / 2 | 1190.9 |
| AI + Modelica assets | 4 | 0 | 2 | 0 | 0 | 2 | 10 / 1 | 1203.9 |

## Per case

| Case | Arm | State | Verdict after | Resolved / new | Edits applied / proposed | Integrity flags |
|---|---|---|---|---|---|---|
| natural | AI only | rejected (integrity) | compiles, does not simulate | 1 / 1 | 3 / 4 | 1 |
| natural | AI + Modelica assets | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 3 | 0 |
| F04 Joint limit written in degrees | AI only | improved | simulates, engineering checks fail | 1 / 0 | 6 / 6 | 0 |
| F04 Joint limit written in degrees | AI + Modelica assets | improved | simulates, engineering checks fail | 1 / 0 | 1 / 4 | 0 |
| F05 Joint axis sign flipped | AI only | rejected (integrity) | compiles, does not simulate | 10 / 1 | 3 / 4 | 2 |
| F05 Joint axis sign flipped | AI + Modelica assets | improved | simulates, engineering checks fail | 9 / 1 | 1 / 3 | 0 |
| F07 Mechanical connection deleted | AI only | unchanged | simulates, engineering checks fail | 0 / 0 | 0 / 3 | 0 |
| F07 Mechanical connection deleted | AI + Modelica assets | not improved | simulates, engineering checks fail | 0 / 0 | 3 / 4 | 0 |

These numbers describe this model, these cases and these settings only; they are not a general ranking of the two approaches.
