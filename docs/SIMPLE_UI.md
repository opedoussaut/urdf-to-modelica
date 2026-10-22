# Simplified studio (branch `feat/simple-ui`)

The studio now opens on a two-feature app. The full studio (all ten pages) stays one click away ("Full studio",
or `?ui=studio`; any `?ws=` deep link also opens it). "Simple view" in the full studio switches back. The choice is
remembered per browser (`localStorage kkh.ui`).

| Page | What it does | Code |
| --- | --- | --- |
| **Convert & compare** | URDF → Modelica three ways, scored by the same seven real OpenModelica checks | `kkh/convert/`, `web/src/simple/Convert.tsx` |
| **Review** | Review a generated (or seeded test) file: manually, AI-assisted, or AI + ontologies; each review scored against known defects | `kkh/convert/review.py`, `review_score.py`, `web/src/simple/Review.tsx` |
| **Learn the ideas** | The Physical AI Atlas, incl. the concept "Three ways to build a model from a robot file" | `web/src/Atlas.tsx` |

Simulation of the converted models beyond the 2 s check comes later.

## Convert & compare

Inputs (`kkh/convert/sources.py`): five pinned robots — the **SO-101 arm** (TheRobotStudio / LeRobot, Apache-2.0; 6 joints, the quick demo robot: URDFModelica 8/8 checks in 23 s), **Unitree G1 EDU with Dex3-1 hands** (default; unitree_ros
`g1_29dof_with_hand_rev_1_0.urdf`, BSD-3), **Berkeley Humanoid Lite** (CC-BY-SA-4.0), the ALOHA 2 **follower**
(`aloha_vx300s`) and **leader** (`aloha_wx250s`) — or an uploaded `.urdf` (≤ 300 kB, parsed before acceptance, stored by
hash in `runs/convert/uploads/`). The humanoids are pinned sparse checkouts (URDF + the meshes it references, listed in
`config/public_sources.json` `sparse_files`). Only the ALOHA arms are in the knowledge graph so far.

**3D view** (`kkh/convert/robot3d.py`, `web/src/simple/RobotView.tsx`): drawn from the same URDF that is converted —
joint frames from URDF origins (rpy as Z·Y·X), motion about the URDF axis, mimic joints applied, the maker's STL meshes.
`GET /api/convert/robot3d?source=` describes links/joints; `GET /api/convert/mesh?source=&i=&lod=` serves a mesh by index
only (paths resolved server-side, never outside the repository). Card previews use `lod=low` (vertex clustering, cached
in `runs/convert/mesh_cache/`, ~10 % of the size). "Move the joints" plays the scorer's standard excitation. Uploads,
which come without meshes, are drawn as a skeleton.
**Clashes and motion modes:** the standard excitation moves each joint within its own URDF limits, so parts can pass
through each other (a URDF has no self-collision limits; the converted models and the MuJoCo reference have no
contacts either, so scores are unaffected). The 3D view shows it honestly: parts passing through each other turn red
and are listed (exact triangle test with `three-mesh-bvh` 0.9.16 on the light preview meshes; parts joined by fixed
joints count as one body; neighbours across a moving joint and pairs already touching at rest are ignored). "One joint
at a time" moves each joint in turn (2 s of test time each) from the rest pose and back, which avoids most clashes.

Modes (one isolated directory each, `runs/convert/<id>/<mode>/`):

**Token budget of the AI methods** (`llm.budget`, stored per run as `budget`): output cap = max(10 000, 1 500 + 250 ×
joints) — the ALOHA arms keep the campaign's 10 000, the G1 gets 14 500; context window = estimated prompt + 2 × cap
(a repair resends the previous file) + 1 500, rounded up to 1 024 and never below 24 576. Prompt size is estimated at
1.6 characters per token (nemotron measured ~1.8 on URDF text). The campaign of 21 Oct 2026 never exceeded its fixed
24 576-token window (largest attempt 18 951). A cut-off file is scored as written; the next attempt is asked to be
more compact. The live view shows tokens written against this cap.
**Loop guard** (`llm.repeating`): generation stops as soon as the end of the text is an exact repetition of one block
(period 8–600 characters, at least 4 copies, at least 800 characters). Measured on the 40 earlier AI attempts: it
fires on 9, all nemotron outputs that repeated one line hundreds of times up to the cap, and on none of the others or
the reference ALOHA model. The stopped text is scored as written; the next attempt is told it was repeating.

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
`GET /api/convert/runs/{id}/file?mode=`, `GET /api/convert/runs/{id}/findings?mode=`, `GET /api/convert/scores?table=conversions|reviews&format=json|csv`.

## Scoring a converted model (eight checks, all measured)

`kkh/convert/score.py`, ranking lexicographic, every check shown. **Completion** = checks passed / 8, shown in %;
colours follow the percentage (red < 50 %, amber 50–99 %, green only at 100 %), never the rank — the highest score
of a run can still be red. While a run is in progress each check is reported live (`on_step` → `active.json`):
running / passed / failed / not reached, with what OpenModelica or MuJoCo is doing.
1–4. **Validity gates**: produced → loads → checks (equations = variables) → simulates (2 s).
5. **Coverage**: URDF links / moving joints found (lenient names).
6. **Geometry under motion** (`kinematics`): a **standard excitation** (`kkh/convert/excite.py`) drives every
   recognised joint through 80 % of its URDF range for 4 s (sines, distinct frequencies; URDFModelica via its `Run`
   inputs, contract files via `extends …Test(j_x(useAxisFlange=true))` + Position sources; mimic joints are not driven
   on their own, so an unenforced mimic shows). Link positions and orientations vs URDF FK; pass ≤ 1 mm and ≤ 0.1°.
   **Localisation**: the first wrong joint on each chain is reported as the suspect. Fallback: the model's own motion,
   flagged (`max_joint_motion_rad`).
7. **Parameters**: joint axes, masses, centres of mass and inertia tensors; COM/inertia compared in the link's own
   frame when the result exposes it (geometry-independent), otherwise in world via URDF FK; limits are not checkable
   from results (stated).
8. **Dynamics** (`kkh/convert/dynamics.py`): model joint torque (MSL `tau` / `f`, the rigid-body axis torque) vs
   **MuJoCo** inverse dynamics from the cleaned URDF at the simulated q, q̇, q̈ — rigid body only on the reference
   (damping, friction, armature 0; constraints incl. MuJoCo's mimic equalities disabled); pass ≤ 5 % of the URDF effort
   limit per joint; mimic joints reported apart. Reference self-check (forward → inverse) ≈ 1e-14 N·m.

Validated on the URDFModelica leader arm (20 Oct 2026): 9/9 axes, 15/15 masses, 12/12 centres of mass, 12/12
inertias; arm torques within 0.01 % of effort vs MuJoCo; the unenforced finger mimic is the only defect (right finger
up to 34 mm off under excitation; suspect joint `right_finger`). Negative tests (orientation, COM, inertia errors
injected into the reference) are caught on exactly the injected link.

## Review: three modes, one scorecard

`kkh/convert/review.py` (run, store), `review_score.py` (score). Targets: a converted file (`conversion`) or a
**seeded test file** (`seeded`): the frozen follower class with exactly one known error from
`kkh/benchmark/detection.MUTATIONS` (M0 control … H7, held-out ones marked).
- **Manual**: a form (entity, category, note, confidence, optional correction); time measured.
- **AI-assisted** / **AI + ontologies**: local model (any installed), same prompt, seed 42, 24 k context, structured
  output (`issues` with entity/category/evidence/confidence/correction, `claims` with numeric URDF facts). The
  ontology mode adds GraphDB joint facts (`kkh/rag/retrieval.joint_facts`; pinned arms only).
- Reviewers never see the ground truth: file (annotations removed) + cleaned URDF + OpenModelica's own messages.

Ground truth: converted files → `runner.findings()` defects (entity + category); seeded → the mutation.
Metrics: **recall** (right entity + accepted category), **precision** (affirmations filtered as in detection.py),
**corrections that work** (applied to an isolated copy: seeded → `detection.det_diff` no longer flags the entity and
nothing new; conversion → full OpenModelica re-score; at most 3 per review), **faithfulness** (claims vs URDF),
**Brier score** of the confidence, time. "Compare the reviews" shows one column per review; exports via
`/api/convert/scores`.

First measurements (seeded M1, elbow axis sign): nemotron-3-nano:4b — AI and AI + ontologies both report nothing
(recall 0; the ontology review states 20/20 correct facts but does not use them); qwen2.5-coder:7b — AI reports
nothing, AI + ontologies reports 12 false alarms at full confidence (precision 0, Brier 1.0), none of its corrections
applicable. A correct manual review of M3 scores recall 1, precision 1, correction 1/1.

The earlier "edit and save versions" feature was removed at the user's request: the files are reviewed, not hand-fixed.

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
