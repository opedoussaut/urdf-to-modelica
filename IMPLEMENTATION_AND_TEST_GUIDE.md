# Implementation and test guide

Audit date: 16 October 2026. This guide covers the supplied master brief through section 22; the attachment ends at the unfinished word “Keep”. Existing work is preserved on `feat/aloha-baseline`.

## Audit before implementation

Inspected committed and uncommitted Python, React/TypeScript, Modelica, URDF/configuration, ontology, tests, startup scripts, and measured reports. Preserved 136 tracked/untracked source and artifact files, their hashes, the working-tree patch, and a Git bundle in `E:/users/opt2.ai/NOVA/ai-kkh-preserved/pre-master-brief-20261016-072121`. Earlier full-workspace and cold GraphDB backups remain intact. Ignored runtime assets and license files are retained in place.

| Capability at audit | Classification | Evidence / gap |
| --- | --- | --- |
| Pinned geometry, URDF FK, limit/mimic handling | Implemented and verified | Existing engineering modules, real meshes, independent FK tests |
| Prescribed-motion Modelica | Implemented and verified | Frozen source hashes, 9-second OMC reach, 7.29e-14 m FK error |
| GraphDB 11.3.3, ingestion, inference, SHACL | Implemented and verified | `reports/ontology.json`, positive and negative validation controls |
| Local Ollama and grounded read-only copilot | Implemented and verified | Existing client, citations, real API/browser calls; generated claims still need review |
| Persistent conversation history | Missing | Only last answer in React state; audit JSON files exist and can be recovered |
| Read-only robot viewer / recorded playback | Implemented and verified | Existing `Twin.tsx`; no mouse-driven joint or IK control |
| Leader/follower mapping and saved recordings | Missing | Only fixed scenarios and ignored simulation outputs exist |
| Actuator/controller follower dynamics and tracking comparison | Missing | Existing Move sources prescribe motion; not a dynamic tracking baseline |
| Source-backed graphical Modelica inspection | Partially implemented | Generic source parser and existing annotations; no engineering editor UI |
| Source/parameter revision editing and diffs | Missing | Generated baseline must remain protected |
| OMEdit launch and round trip | Missing; executable available | OpenModelica 1.27.1 `bin/OMEdit.exe` detected |
| Dual copilot with durable comparison history | Missing | One grounded assistant; internal paired numeric experiment exists |
| Professional UI | Partially implemented | Existing viewer/graph/citations verified; navigation does not match the new four workspaces |
| Internal validation experiments | Implemented and verified | 33 tests; retain tools and reports while removing benchmark navigation |

## Testing the preserved implementation

```powershell
scripts\start.ps1
.venv\Scripts\python -m kkh.domain.aloha.verify RightArmReach
.venv\Scripts\python -m pytest -q --basetemp=runs/pytest-master-check
```

The frozen verifier writes a unique run and does not regenerate baseline files. GraphDB is project-only on port 7201; do not modify containers on ports 7200 or 7300. Runtime AI is local Ollama only. License files must remain excluded from Git.

## Acceptance boundaries

All new models use editable copies and immutable revision snapshots. Original generated `.mo` sources and regression outputs remain protected. Layout offsets for displaying the standalone leader beside the follower are presentation choices, not measured hardware registration. Kinematic replay is not physical tracking. Dynamics must expose sourced versus illustrative parameters and report only real OpenModelica results. Actual hardware control, friction, backlash, motor constants and load sharing have not been measured.

Further implementation results and exact user testing instructions are appended as features are verified.

## Takeover verification (16 October 2026) — how to test

Start everything: `scripts\start.ps1` (add `-Restart` to force an API restart, `-NoBrowser` to stay in the shell).
Expected: `[graphdb] running`, `[ollama] running`, `[status] GraphDB: ready | Ollama: 7 local models`.

Automated: `.venv\Scripts\python -m pytest -q` → 52 passed (real OpenModelica, GraphDB, Ollama).

Manual (http://127.0.0.1:8000):

1. **Chat history** — Dual AI Copilot → New conversation → ask "Which links does the follower elbow joint connect,
   and what is its axis?" → wait for both answers → reload the page → the conversation and both answers are listed.
   Open "Read-only tool trace & context": the first entry `resolve_focus` shows robot/joint taken from the question.
2. **AI proposal** — Modelica Engineering Editor → create/open an editable model → Dual AI Copilot → ask "Propose
   setting j_shoulder q_max to 101 degrees in radians for review." → under the answer, "Structured parameter proposal"
   shows current vs proposed and the structural check → "Create proposal revision for review" → Modelica editor:
   a new revision with status "AI proposal"; review the diff, run Check, then accept or restore. It is never accepted
   automatically.
3. **Leader–Follower** — Joint drag or sliders → Record leader → Stop → Save recording → Play → choose the saved run
   or run the dynamic follower comparison (real OpenModelica, illustrative gains).
4. **Knowledge Explorer** — click a joint node → source values with units and provenance; the context bar updates.

## End-to-end demonstrator (16 October 2026)

Follow `DEMO_WALKTHROUGH.md` for the full scenario and expected observations. Quick checks:

* `/api/workbench/entity?robot=aloha_vx300s&joint=shoulder` → `j_shoulder` in `Arms/AlohaVX300s.mo`, servo instance
  `shoulder` in `Control/FollowerServoSettings.mo`, KG IRI `…/follower_right/joint/shoulder`.
* Modelica editor with the follower shoulder in focus opens the arm class with `j_shoulder` selected; "Servo settings
  shoulder" opens the Control file (adds it as a revision to older models).
* Dynamic follower: reference and candidate revisions are simulated with their own servo files; the run record lists
  `config.servo`, `servo_origin`, `revision` per run.
* Copilot proposals: try `kp = 900` (rejected, bounds [1, 500]), `j_shoulder.tau_max` (rejected, URDF fact),
  same-as-current values (rejected, no change).
* `pytest -q` → 56 passed.

## Resumed verification and repairs (16 October 2026)

Preserved the newer Claude commits and all existing uncommitted/untracked work before editing. Checkpoint:
`E:/users/opt2.ai/NOVA/ai-kkh-preserved/codex-resume-verification-20261016-215127` (534 files, 59.9 MB, Git bundle,
working-tree patch, untracked sources, consistent SQLite backup, model copies and project-repository RDF export).
Ignored dependencies, simulation binaries and the live GraphDB volume remain in place; older full backups are intact.

Verified the current code, not only the earlier milestone reports:

* `.venv\Scripts\python -m pytest -q --basetemp=runs/pytest-resume-complete` → **64 passed**, one existing
  Starlette/httpx deprecation warning. Includes the new native-launch regression.
* `npm --prefix web run build` → TypeScript and production build passed. Monaco's large lazy chunk remains a known
  first-load cost; it does not block the build.
* All frozen `.mo` hashes still match `reports/engineering_baseline.json`; branch remains `feat/aloha-baseline`.
  Project GraphDB **11.3.3** on 7201, installed local Ollama models and OpenModelica are healthy.
* Restored **Drag leader end effector** alongside Move leader arm, Look around and the existing follower Cartesian
  controls. Click the mode, then drag the glowing teal marker in the camera plane. The existing leader IK applies
  bounded joint goals through the shared motion rate limiter. Unreachable targets keep the previous goal. Browser
  drag returned “Bounded IK step; continue dragging to converge.” This controls leader position, not follower
  Cartesian position or orientation; the cube workflow continues to use the follower IK buttons.
* Native OMEdit testing found and fixed an actual launch error: loading `package.mo` and a nested arm `.mo` as two
  top-level files produced a `within` grammar error. The backend now passes only the root package and returns the
  qualified selected-class name for navigation in Libraries.
* Native round trip: isolated model **Codex native round-trip verification** (`34080d51`), opened
  `ALOHA2.Arms.AlohaVX300s` in the native diagram, changed its animation parameter `true → false` using the
  Parameters dialog, and saved in OMEdit. Diff detection found exactly that source-file change. Explicit import
  created revision `114987d3`; OMC checked **8,178 equations / 8,178 variables** and successfully compiled/simulated
  `ALOHA2.Experiments.RightArmReach` for 3 seconds. The verification model remains **unaccepted**. The user's accepted
  model was not edited. Details: `runs/studio/native-verification.json`; screenshot:
  `docs/img/omedit-native-roundtrip.png`.
* A failed lazy workspace load now displays a recovery panel inside that workspace. Other mounted workspaces stay
  available, so a local frontend rebuild cannot blank the entire studio and discard their unsaved state. Save ongoing
  work before choosing Reload studio.
* Moved the stage status beneath the permanent leader/follower labels and verified the result in the browser.
  Screenshot: `docs/img/resume-motion-verification.png`. Final hashes, service status and native-validation evidence
  are recorded in `reports/resume_verification.json`.

The guided cube-transfer implementation, semantic trace, revision-bound servo parameters, recorded simulations,
reviewed AI-proposal workflow and all previous experiment/regression tools have been retained. See
`DEMO_WALKTHROUGH.md` and `KNOWN_LIMITATIONS.md` for their measured results and engineering boundaries.
