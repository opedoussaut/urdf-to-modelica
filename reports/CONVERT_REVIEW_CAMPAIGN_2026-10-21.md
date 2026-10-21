# Conversion and review campaign — 21 October 2026

Command: `python -m kkh.convert.batch --robot aloha_wx250s --models nemotron-3-nano:4b,qwen2.5-coder:7b,qwen3-coder:30b`
(log `runs/convert/batch_20261021-0728.log`, 319 min, 0 failures). All numbers below come from real OpenModelica runs,
the URDF, MuJoCo and known defects (`docs/SIMPLE_UI.md` describes the protocol). Local models only (Ollama).

## 1. Conversion (WidowX 250 S leader arm, run `8941c0696368`)

| Method · model | Result (8 checks) |
| --- | --- |
| **URDFModelica** (rule-based) | runs; 15/15 links, 9/9 joints; axes, masses, centres of mass, inertias all match; arm torques within 0.01 % of effort vs MuJoCo; **fails geometry**: URDF finger mimic not enforced (right finger up to 34.3 mm off under excitation) |
| AI only · qwen3-coder:30b | file **loads**; OpenModelica rejects it as incomplete |
| AI + MSL search · qwen2.5-coder:7b | file **loads**; rejected as incomplete (AI only with the same model: does not load) |
| AI + MSL search · qwen3-coder:30b | file loads; rejected as incomplete |
| AI only / AI + MSL search · nemotron-3-nano:4b; AI only · qwen2.5-coder:7b | file does not load |

No AI-written file passes the completeness check. Larger model and library retrieval each move the AI one gate further.

## 2. Reviews (AI-assisted vs AI + ontologies, three models)

Seeded test files: 17 (M0 control + 16 single known errors, 7 of them held out); converted files: the 7 above.
"found" = issue on the defective entity; "type" = also an accepted error category; precision pooled over all issues;
"fixed" = proposed corrections that removed the defect on an isolated copy without new problems; claims = numeric
statements checked against the URDF; control FA = false alarms on the unmodified M0 file.

### Seeded files

| Mode | Model | found | type | issues | false alarms | precision | fixed | claims correct | Brier | control FA | s/review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AI | nemotron 4B | 0/16 | 0 | 0 | 0 | – | 0/0 | – | – | 0 | 9 |
| AI + ontologies | nemotron 4B | 0/16 | 0 | 0 | 0 | – | 0/0 | 120/120 | – | 0 | 12 |
| AI | qwen2.5-coder 7B | 0/16 | 0 | 0 | 0 | – | 0/0 | 340/340 | – | 0 | 62 |
| AI + ontologies | qwen2.5-coder 7B | 3/16 | 0 | 144 | 144 | 0.00 | 1/144 | 165/315 | 1.00 | 12 | 158 |
| AI | qwen3-coder 30B | **9/16** | 1 | 93 | 89 | 0.04 | **8/92** | 147/157 | 0.87 | 0 | 167 |
| AI + ontologies | qwen3-coder 30B | **9/16** | 1 | 111 | 108 | 0.03 | 6/110 | **190/190** | 0.88 | 0 | 169 |

Entities found per seeded file (right place): M1 axis sign, M3 unit, M4 parent, M5 mapping, M7 mass, M8 origin,
M9 joint type (also right category), H1, H2, H3, H5 — almost all by qwen3-coder:30b.

### Converted files (natural defects measured by the scorer)

| Mode | Model | found | type | issues | false alarms | precision | fixed | claims correct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AI | nemotron 4B | 0/7 | 0 | 27 | 27 | 0.00 | 0/27 | 0/20 |
| AI + ontologies | nemotron 4B | 2/7 | 2 | 37 | 35 | 0.05 | 0/37 | 41/41 |
| AI | qwen2.5-coder 7B | 4/7 | 4 | 24 | 20 | **0.17** | 0/24 | 32/32 |
| AI + ontologies | qwen2.5-coder 7B | 3/7 | 2 | 33 | 31 | 0.06 | 0/33 | 37/80 |
| AI | qwen3-coder 30B | 4/7 | 4 | 65 | 61 | 0.06 | 0/54 | 72/72 |
| AI + ontologies | qwen3-coder 30B | 4/7 | 3 | 84 | 77 | 0.08 | 0/81 | 84/84 |

## 3. Reading (what the data supports, and what it does not)

- **Model size dominates.** Only qwen3-coder:30b localises seeded errors (9/16) and proposes corrections that work
  (8 on the seeded set). The 4B and 7B models mostly report nothing or report noise.
- **Ontology grounding did not improve detection or correction** in this campaign: same 9/16 for the 30B model, fewer
  working corrections (6 vs 8), more issues. For nemotron it turned 0/7 into 2/7 on converted files, at 35 false alarms.
- **Ontology grounding did improve factual accuracy**: numbers stated by grounded reviews are correct far more
  consistently (30B: 190/190 vs 147/157; nemotron 120/120 and 41/41 vs 0/20). Exception: qwen2.5-coder 7B grounded
  (165/315) — it misread the graph facts.
- **Reviews find the place, rarely the kind of error** (type 1/16 even for 30B) and **precision is very low**
  (≤ 0.17): every review reports up to 12 issues. A reviewer would need to sift ~10 alarms per real defect.
- **Calibration is poor** (Brier 0.6–1.0): the models state high confidence on wrong issues.
- Consistent with the earlier detection experiment (`reports/DETECTION_RESULTS.md`): the deterministic rules and the
  measured scorer remain the reliable error finders; local LLMs add value mainly by explaining and quoting facts.

Limits: one robot, one seed per review, ≤ 12 issues per review (schema cap), seeded errors from one generator's
syntax; precision counts issues on other entities as false alarms even when partly justified. No manual reviews yet:
the human baseline is still missing.
