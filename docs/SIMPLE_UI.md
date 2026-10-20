# Simplified studio (branch `feat/simple-ui`)

The studio now opens on a two-feature app. The full studio (all ten pages) stays one click away ("Full studio",
or `?ui=studio`; any `?ws=` deep link also opens it). "Simple view" in the full studio switches back. The choice is
remembered per browser (`localStorage kkh.ui`).

| Page | What it does | Code |
| --- | --- | --- |
| **Convert & compare** | URDF → Modelica three ways, scored by the same seven real OpenModelica checks | `kkh/convert/`, `web/src/simple/Convert.tsx` |
| **Understand & fix** | Read a generated model, ask the local AI (alone vs grounded in the robot knowledge graph), edit it and re-check | `kkh/studio/copilot.py` (`conversion_context`), `web/src/simple/Understand.tsx` |
| **Learn the ideas** | The Physical AI Atlas, incl. the concept "Three ways to build a model from a robot file" | `web/src/Atlas.tsx` |

Simulation of the converted models beyond the 2 s check comes later.

## Convert & compare

Inputs: the pinned ALOHA arms (`aloha_vx300s` follower, `aloha_wx250s` leader) or an uploaded `.urdf` (≤ 300 kB,
parsed before acceptance, stored by hash in `runs/convert/uploads/`). Uploads have no knowledge graph.

Modes (one isolated directory each, `runs/convert/<id>/<mode>/`):

1. **AI only** (`llm`): local Ollama (`nemotron-3-nano:4b`), URDF text with visuals/collisions removed, a fixed
   output contract (package `<Robot>`, model `<Robot>Test`, one body per link, `j_<joint>` per joint, unactuated).
2. **AI + Modelica library search** (`llm_rag`): the same prompt plus Modelica Standard Library classes: the core
   MultiBody classes looked up by exact name (World, Body, FixedTranslation, FixedRotation, Revolute/Prismatic as
   present in the URDF) and worked examples found by BM25 keyword search (`kkh/convert/library_index.py`, index cached in
   `runs/convert/index/`). Never indexed: `generated/modelica` (the project's own answer), `third_party/ref`, and the
   URDFModelica library (that is mode 3).
3. **URDFModelica** (`urdfmodelica`): the DLR converter in an isolated copy, with the documented pre-processing
   (T1 '/'-names, T2 textures, T3 '-' in names, relative root).

Models: the AI methods run once per local Ollama model ticked on the page (installed models are listed by
`GET /api/convert/sources`; cloud models are excluded). Result keys are `llm:<model>` / `llm_rag:<model>` (older
reports use plain `llm` / `llm_rag`). CLI: `--models nemotron-3-nano:4b,qwen2.5-coder:7b`. Ollama's model store is
`E:\ollama\models` (set in the Ollama app's settings, 20 Oct 2026).

Fairness: modes 1 and 2 share model, seed 42, temperature 0, `num_ctx` 24 576, 10 000 output tokens and two repair
rounds that receive only OpenModelica's real diagnostics. A reply cut off at the token limit is scored as written and
the next round restarts from the original prompt with a request to be more compact.

Scorer (`kkh/convert/score.py`), in ranking order: produced → loads → checks (equations = variables reported) →
simulates (2 s) → coverage (URDF links/moving joints found by lenient name matching) → kinematics (URDF forward
kinematics at the simulated joint angles vs simulated link frames, relative to the root, pass ≤ 1 mm; nested
`body.frame_a` frames, which can sit at the centre of mass, are counted for coverage but not compared) → parameters
(joint axes `n`, link masses ±1 % from the result file). Ranking is lexicographic; the page shows every criterion.

First measured result (leader arm, 20 Oct 2026): URDFModelica loads, checks (7 049 equations = variables), runs,
contains 15/15 links and 9/9 moving joints, all axes and masses match, but fails the kinematic check: it does not
enforce the URDF finger mimic, so the right finger is up to 9.9 mm off. Reports: `runs/convert/<id>/report.json`.

CLI: `PYTHONPATH=. python -m kkh.convert.runner aloha_wx250s --modes llm,llm_rag,urdfmodelica`

API: `GET /api/convert/sources`, `POST /api/convert/upload` (JSON `{filename, content}`), `POST /api/convert/run`
(job, poll `/api/workbench/job/{id}`), `GET /api/convert/runs`, `GET /api/convert/runs/{id}`,
`GET /api/convert/runs/{id}/file?mode=&version=`, `POST /api/convert/runs/{id}/edit` (job).

## Understand & fix

- The copilot's paired answers (`kkh/studio/copilot.pair`, identical settings both sides) receive the generated file,
  its source URDF and the file's score card. The grounded side adds GraphDB evidence for the pinned arms; for an
  upload it declines explicitly ("no robot knowledge graph") instead of answering without grounding.
- Preset questions: Explain this model, Find possible errors, Suggest a fix; or a free question.
- **What the checks found** (`GET /api/convert/runs/{id}/findings`, `kkh/convert/runner.findings`): the file's measured
  problems in plain words, derived only from its OpenModelica score and the URDF, with a likely cause when the URDF
  explains it (e.g. a mimic joint not enforced). Shown above the code and given to both AI sides first.
- Measured AI result (20 Oct 2026, `nemotron-3-nano:4b`, URDFModelica file of the leader arm): asked to find errors,
  both sides answered "no modelling errors" and missed the measured 9.9 mm finger gap, even with the findings supplied;
  the grounded side also wrongly stated the mimic coupling is enforced. This is why the deterministic findings box is
  shown first and labelled "No AI involved".
- Edits: a person edits the file; "Save as a new version and check" stores `edits/v<n>/` beside the original and runs
  the same scorer. Nothing is applied automatically; AI suggestions are review-only.

## Non-expert layer

Every page has an "In plain words" banner, criteria have one-line explanations, results include "What these checks
show / do not show", the Overview/Engineering switch hides paths and tool messages in Overview, and the Atlas explains
the three methods with sourced definitions (URDFModelica, RAG, BM25).

## Limits

- One local 4B model; results are specific to it and to the URDF given.
- Kinematic agreement on the joint motion that the 2 s run happens to exercise (gravity drop or the converter's test
  motion); `max_joint_motion_rad` is reported so a model that barely moves is visible.
- Name-based matching: a match is a name correspondence; the kinematic comparison is what tests the wiring.
- Not a hardware validation: motors, friction and controllers are outside the URDF.
