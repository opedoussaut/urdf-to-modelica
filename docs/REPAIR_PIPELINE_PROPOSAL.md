# URDF → Modelica engineering workflow: audit and proposal (2026-10-23)

This proposal is a plan, not an implementation. Nothing in the existing pipeline, the baselines or the reports has been
changed. Branch `feat/urdf-repair-pipeline` (worktree `.claude/worktrees/urdf-repair-pipeline`) was cut from
`feat/simple-ui` @ `01ad963`.

## 0. Starting point: which branch

- The mission names `feat/aloha-baseline`, but the code this mission builds on lives on **`feat/simple-ui`**. That
  branch is local and unpushed, 31 commits ahead of `origin/feat/aloha-baseline`, and contains all of
  `feat/aloha-baseline`. It holds the following:
  - `kkh/convert/*`: DLR converter wrapper, 8-check scorer, AI modes, BM25 library index, reviews, seeded defects.
  - The simplified UI: Convert & compare, Review.
- **Proposal:** build on `feat/simple-ui` (done for this branch). If you prefer `feat/aloha-baseline`, the convert
  layer would have to be cherry-picked; that path is not recommended.
- **Found during the audit, left untouched:** the main checkout has an uncommitted one-line hand edit of
  `generated/modelica/ALOHA2/Arms/AlohaWX250s.mo` (Diagram extent), probably from another session. `CLAUDE.md` says
  generated code is regenerated, not hand-edited, so this needs your decision. Two side worktrees
  (`claude/cranky-hypatia-544721`, `claude/recursing-gauss-3bab72`) are not merged.

## 1. Audit: what exists for each stage

| Stage | Exists today (file) | Fit | Gap for the mission |
|---|---|---|---|
| **1 Convert** | `kkh/convert/urdfmodelica.py`: pinned DLR URDFModelica `92541b6`, isolated copy of the library, documented pre-processing T1–T3 (name characters, textures), relative root. `kkh/benchmark/workflow_a.py`: older ALOHA bimanual variant. `kkh/engineering/modelica_gen.py`: our own deterministic generator (ALOHA2 package). | Good | No conversion **manifest** (URDF/mesh hashes, CLI args, Python/OM versions); converter log cut to 3 000 characters; no structured **source→target mapping**; no inertial/joint/frame table; no list of **unsupported URDF elements** (transmission, gazebo, mimic, collision, safety_controller, …). |
| **2 Check** | `kkh/engineering/omc.py`: load/check/simulate, regex message parser (file/line/col) and 9 classes. `kkh/convert/score.py`: 8 measured checks (produced, loads, checks, simulates, coverage, kinematics vs URDF FK, axes/masses/CoM/inertia, dynamics torque). | Good core | Order and taxonomy differ from the mission; equation balance is not its own step; no **unit** check (`checkModel` unit warnings); no **graphics check** (Placement / connect `Line` coverage); no single **machine-readable diagnostic record** (id, stage, category, severity, location, evidence). |
| **3 AI repair** | `kkh/convert/llm.py`: modes 1/2 **write the model from scratch** from the URDF, then up to 2 repairs fed by OpenModelica diagnostics. Same seed/temperature/budget for both modes, loop guard, every attempt kept. `kkh/convert/library_index.py`: BM25 over 4 MSL sub-packages. `kkh/rag/repair.py`: generic bounded loop (1–3 attempts). `kkh/benchmark/harness.py`: B/C parameter-repair ablation with GraphDB facts. | Partly reusable | **The AI is the generator today**, which the mission reverses. No repair-only mode that starts from the converter output. The retrieval index has **no per-asset provenance/version/licence**, covers only 4 sub-packages, and does not log which retrieved items were cited in a correction. |
| **Fault injection** | `kkh/benchmark/detection.py` + `kkh/domain/aloha/candidate.py`: MUTATIONS + HELD_OUT on our own generator's follower class, rules frozen at `53405d7`. `runs/convert/seeded`: seeded defects for review scoring. | Pattern reusable | No fault set for the **DLR-converted** package; it must be written and frozen before any repair is measured. |
| **4 Validate** | `score.py` is already independent of the producer; `modelica_inspect.py` parses components/parameters/connections. | Good | No **integrity guard** comparing original vs candidate: deleted components, changed masses/inertias/limits/frames, suppressed checks (removed `assert`, `Evaluate`, commented equations), diagram-only edits. No resolved/remaining/new-error bookkeeping. |
| **5 Review** | `kkh/studio/models.py`: immutable revisions, forks, source diff, OMEdit round trip, `accept` only from a *validated* revision; Model editor UI (`ModelicaEditor.tsx`, synced 3D arm). `Review.tsx`: manual / AI / AI+ontology reviews. | Good | Repair candidates are not imported as revisions; no 3-way view (original / AI only / AI + assets); no **per-change** accept/reject; repair evidence (retrieved assets, diagnostics fixed) not shown. Revision storage is wired to the ALOHA2 baseline path. |
| **6 Approved + simulate** | `models.accept`, RightArmReach / LeaderArmCheck experiments, 1D lab, OMEdit open, export with meshes (`kkh/convert/export.py`). | Good | No explicit "approved model" promotion record linking URDF → conversion → diagnostics → candidate → approval. |
| **Graphics** | DLR output (UR10e example): main robot model has 35 `connect`, **0 `Line`**, 26 `Placement`. Our generator: 51 `connect`, no routes (the kinematic schematic in the studio is a workaround). | Gap | No deterministic layout pass. |
| **UX** | Simple UI: Convert & compare → Review. Full studio (`?ui=studio`): Robot → Knowledge → Model → Simulate → Decide. | | Needs the 7-stage sequence. |

**Local Modelica knowledge sources (no download needed):** Modelica Standard Library **4.1.0** (+3.2.3, 4.0.0),
ModelicaReference **4.1.0** (language keywords and annotations, including Placement/Line/Icon/Diagram) and
ModelicaServices, all under `%APPDATA%\.openmodelica\libraries`. All are Modelica Association,
**Modelica 3-Clause BSD**. OpenModelica docs (468 files) are in `…\OpenModelica1.27.1-64bit\share\doc\omc`; their
licence still needs checking. The **Modelica Language Specification** is not local; adding it means a download
(CC BY-SA 4.0), which needs your approval.

## 2. Proposed architecture: the smallest safe change

The plan adds one package, **`kkh/workflow/`**, with one module per stage. It reuses `kkh/convert`, `kkh/engineering`
and `kkh/studio` through imports. Nothing is moved or rewritten, and the existing Convert & compare comparison keeps
working unchanged as the "AI as generator" historical baseline. Robot-specific knowledge stays in the input
(URDF + mesh dir); the core never imports `kkh/domain/aloha`.

```
URDF + assets ──► stage1_convert ──► stage2_check ──► diagnostics.json ──┬─► stage3_repair(arm="ai_only")   ──► candidate A ─┐
 (hash-pinned)    (DLR, pinned)     (OMC + checks)   (machine-readable)  └─► stage3_repair(arm="ai_assets") ──► candidate B ─┤
                                                                                                                             ▼
                          stage6_promote ◄── engineer review (studio) ◄── comparison report ◄── stage4_validate (same pipeline for original, A, B)
```

Every run lives in `runs/workflow/<run-id>/` with `stage1/`, `stage2/`, `ai_only/attemptN/`, `ai_assets/attemptN/`,
`validate/`, `report.json` and `report.md`. Each artefact records the hash of its inputs. Committed summaries go to
`reports/`, as today.

### Stage 1: `stage1_convert.py`
- Calls `kkh/convert/urdfmodelica.convert` unchanged. Then it writes `manifest.json` with:
  - SHA-256 of the URDF and of every referenced mesh;
  - converter commit, CLI arguments, pre-processing applied (T1–T3);
  - Python, OpenModelica and MSL versions;
  - the full converter log.
- **Mapping:** URDF link/joint → generated component, using the name rule `score.norm`, then verified by the stage-2
  kinematics check.
- **Physical table:** for each link, mass, CoM and inertia from the URDF and the generated parameter value. For each
  joint, axis, origin xyz/rpy and limits.
- **Unsupported/ignored URDF elements**, from a URDF scan: transmission, gazebo, mimic, safety_controller, collision
  geometry, textures (T2).
- **Comparative baseline:** our generator (`modelica_gen`) runs through stages 1–2 as a separate input. It never acts
  as a repair step.
- **Reproducibility:** test that converting twice gives byte-identical `.mo` files.

### Stage 2: `stage2_check.py`, producing `diagnostics.json`
- Steps run in order and stop at the first blocking failure, each recorded with its OpenModelica output:
  1. load/parse
  2. class structure and dependencies (`checkModel`, missing classes)
  3. balance and translation (`instantiateModel`/`translateModel`, equation/variable counts)
  4. controlled simulation (the existing excitation, 2 s)
  5. URDF consistency (`score.py` coverage, kinematics, parameters, dynamics)
  6. graphics: `Placement` coverage, `connect` with/without `Line`, Icon present, diagram extent containing all components
- **Record schema** (one entry per finding):
  `{id, step, category, severity: error|warning|info, file, line, col, message, evidence, check, blocking}`.
  - Categories follow the mission: syntax/translation, missing class/library, type/unit, connector/equation,
    initialization/numerical, unsupported URDF element, kinematic/mechanical inconsistency, graphics.
  - The mapping from today's `omc.classify` classes is explicit and tested.
- **Verdict:** a run that compiles is labelled *compiles*. It is *validated* only when every engineering check
  passes, and the report never treats one as the other.

### Stage 3: `stage3_repair.py`, one loop with two arms
- **Shared by both arms** (fixed in `settings.json`, hashed into the report):
  - inputs: URDF, the generated package (copy), `diagnostics.json`, the repair instructions;
  - model, seed, temperature, context and output budgets, attempt limit (proposal: 3), loop guard;
  - validation: the same stage-2 pipeline after every attempt.
- **Edit format:** the model returns edits to named files as search/replace blocks, applied to an isolated copy.
  Blocks that fail to apply are recorded, never fixed up by hand. This keeps diffs small and reviewable and avoids
  regenerating a 30-file package.
- **Repair instructions, identical for both arms:**
  - do not delete components;
  - do not change URDF-derived values (mass, inertia, CoM, axes, origins, limits);
  - do not remove or weaken checks or asserts;
  - do not change the architecture;
  - no cosmetic or annotation-only edits;
  - explain each edit.
- **`ai_only`:** nothing beyond the shared inputs.
- **`ai_assets`:** shared inputs plus **targeted retrieval per finding**. The query is built from the finding's
  category, message and offending class names, and the top-k chunks are appended under a provenance header. The
  model must cite chunk ids per edit, and the citations are checked: an id that was not supplied is flagged.
- **Every attempt** keeps prompt, response, applied edits, retrieved chunks with ids, tokens, seconds and stage-2 result.

### Governed Modelica asset collection: `kkh/workflow/assets/`
- `assets.json` lists each source with id, title, version, path, licence, retrieval scope and hash. A chunk always
  carries `{asset_id, version, licence, class_or_section, source_path, line_range}`.
- **v1 sources (local, Modelica 3-Clause BSD):**
  - MSL 4.1.0 classes with their `Documentation(info=…)`, including `Modelica.Mechanics.MultiBody.Examples.*`, Rotational, Translational, Blocks;
  - `Modelica.UsersGuide.ReleaseNotes` for version compatibility;
  - ModelicaReference 4.1.0 for language keywords and annotations: Placement, Line, Icon, Diagram, connect semantics.
- **Validated project patterns:** the conventions in `CLAUDE.md` (massless links, `stateSelect`, unit-free joint
  connectors, rpy rotation sequence), written as short pattern documents with their provenance (this repo, commit).
- **Excluded by design:** the URDFModelica library itself (its output is what is being repaired), `generated/` (the
  project's own answer), `third_party/ref` (Houssem's model, never an input).
- **Optional, needs approval:** OpenModelica user's guide (licence check), Modelica Language Specification
  (download, CC BY-SA).
- **Retrieval:** BM25, as today, deterministic, no embedding model and no download. GraphDB is not required for this
  experiment.

### Fault injection: `stage3_faults.py`
- Use the converter's **naturally occurring findings** first.
- Add a **seeded set** applied to copies of the DLR package. Candidates:
  - wrong `Modelica.*` class path (MSL 3 vs 4 naming);
  - a unit mismatch (deg vs rad in a limit);
  - a deleted `connect`;
  - a missing `each`/array-dimension error;
  - a swapped axis sign;
  - a wrong frame rotation;
  - a missing MSL `uses` annotation;
  - an under-determined massless body (`frame_a.f` not set);
  - an initialisation conflict.
- Each case records `{id, injected_edit, expected_category, entity}`.
- **The set is frozen (commit hash) before any repair run**, as for the detection experiment. Changing it later
  means writing a new held-out set.

### Stage 4: `stage4_validate.py`
- Runs the stage-2 pipeline on the original, A and B, then computes:
  - resolved, remaining and new findings (matched by step + category + entity + normalised message);
  - compile and simulate success;
  - attempts, tokens, seconds; cost "n/a (local)".
- **Integrity guard** (from `modelica_inspect` + the stage-1 physical table). Each flag has evidence:
  - components removed or renamed;
  - connects removed;
  - URDF-derived values changed;
  - limits, axes or frames changed;
  - asserts removed or checks disabled;
  - annotation-only edits.
- **A candidate that compiles only because of a flagged change is reported as *rejected*, not as a success.**
- **Graphics quality** is measured (Line coverage, overlaps) but kept apart from the repair verdict.

### Stage 5: review (studio)
- **Import into revisions:** candidates A and B become immutable revisions (status `AI-only candidate` /
  `AI+assets candidate`) of a new model workspace created from the stage-1 package.
  - `models.py` gains a constructor that accepts any package directory.
  - The ALOHA2 baseline path stays the default, so the existing editor keeps working.
- **New review page:**
  - three columns: original / AI only / AI + assets, each with its diagnostics (resolved / remaining / new);
  - per-edit cards with the model's explanation, cited assets (with licence) and integrity flags;
  - side-by-side diffs;
  - **accept/reject per edit:** the accepted subset is applied to the original to create a `manual` revision,
    which is then re-validated;
  - manual editing (existing editor), OMEdit open (existing), rerun validation, accept the final candidate
    (existing `accept`, which requires *validated*).
- **AI agents have no write path to the approved baseline.** Promotion is a human API call only, with a recorded
  approver and timestamp.

### Stage 6: approve and simulate
- `stage6_promote` writes `approval.json`:
  - URDF hash → manifest → diagnostics → the candidate's edits → validation → approver;
  - optionally a PROV-O trace in GraphDB (existing `kkh/semantic/trace.py`), repository `kkh-aloha-engineering` only.
- Simulations: the existing excitation and 2 s run from the studio, OMEdit open, export with meshes. For ALOHA 2,
  RightArmReach and LeaderArmCheck stay as they are.

### Graphics: a deterministic, separate pass
- `kkh/workflow/layout.py` derives `Placement` from the kinematic tree (one column per chain, as the studio's
  kinematic schematic already does) and adds orthogonal `Line` annotations to every `connect`.
- It is deterministic and needs no AI.
- It runs **outside the comparison**: either on the approved model (stage 6) or as a separately labelled
  "visual-quality pass" on the stage-1 output **before** both arms see it, so both arms get identical input.
- Recommendation: apply it after approval, so the scientific comparison stays clean, and report graphics quality
  before and after.
- The same algorithm then goes into `modelica_gen` so our own ALOHA2 package gets real connection lines in OMEdit
  (tested by opening it with OMC `getConnectionCount` and checking every connection has a Line).

### UX
- The default (simple) app gets a stage rail: **URDF input → Convert → OpenModelica check → AI repair comparison →
  Engineer review → Approved model → Simulation**.
  - Each stage page reads the run folder of the selected run, so any stage can be opened on its own.
  - AI only and AI + assets are always in separate, colour-coded columns that never share a panel.
- Existing pages are reused:
  - Convert & compare's robot picker and 3D view for *URDF input*;
  - the replay for *Simulation*;
  - the Model editor for *Review*.
- **Plain-language layer:** one sentence per stage in Overview, plus an Atlas concept "AI repair vs AI + Modelica
  knowledge".

## 3. Delivery in safe increments

Each increment is one commit, reviewed by you, with tests and a measured artefact. Nothing is pushed or merged
without your approval.

| # | Increment | Done when |
|---|---|---|
| 1 | Stage 1 manifest + mapping + physical table + unsupported elements (ALOHA vx300s) | Reproducibility test (byte-identical twice); manifest committed under `reports/` |
| 2 | Stage 2 ordered checks + `diagnostics.json` schema + graphics check | Real findings on the DLR ALOHA package; classifier tests on recorded OMC output |
| 3 | Asset collection v1 (MSL 4.1.0 + ModelicaReference + project patterns) with provenance | Every chunk has id/version/licence; retrieval is deterministic (test) |
| 4 | Fault set written and **frozen** | Commit hash recorded before any repair run |
| 5 | Stage 3 two-arm loop + Stage 4 validation and integrity guard | Both arms run on natural findings + the fault set; report with measured numbers, whatever the outcome |
| 6 | Studio: candidate import, 3-way review, per-edit accept, approval record | Human approval path tested; no write path from AI |
| 7 | Layout pass + `modelica_gen` Line annotations | OMEdit shows connection lines; every connect has a Line |
| 8 | Stage rail UX + plain-language layer + recorded demo | ALOHA 2 end-to-end demo recorded |

**Tests:** unit tests for the schema, classifier, edit application, integrity guard and retrieval determinism.
The `omc`-marked integration tests reuse the existing markers.

## 4. Decisions needed from you

1. **Base branch:** build on `feat/simple-ui` (recommended, where the convert layer lives) or on `feat/aloha-baseline`?
2. **Robot scope for the first demo:** the single follower arm `aloha_vx300s` (recommended: 9 joints, minutes per run)
   or the bimanual assembly?
3. **Model for both arms:**
   - `qwen3-coder:30b`: the only local model that has produced a running file so far, at about 12 min per run;
   - `nemotron-3-nano:4b`: fast, weaker.
   - Recommendation: qwen3-coder:30b for measured runs, nemotron for UI dry runs.
4. **Optional knowledge sources:** may I download the Modelica Language Specification (CC BY-SA 4.0), and use the
   OpenModelica docs after a licence check?
5. **Graphics pass placement:** after approval (recommended) or before both arms?
6. **The uncommitted hand edit** of `generated/modelica/ALOHA2/Arms/AlohaWX250s.mo` in the main checkout: keep, or regenerate?
