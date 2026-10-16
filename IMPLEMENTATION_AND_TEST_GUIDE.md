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
