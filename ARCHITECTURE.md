# Architecture — HT GEN7 PhysAI Studio (ALOHA 2)

*Engineering-Grounded Physical AI*

Local-first: browser UI → FastAPI on 127.0.0.1:8000 → local services. No hosted inference, no cloud fallback.

```
web/ (React 19 + TS, Vite)             kkh/api/main.py (FastAPI, loopback, cross-origin writes refused)
  LeaderFollower.tsx  ── /api/workbench/pose|ik|trajectory|follower-pose ─┐
  ModelicaEditor.tsx  ── /api/workbench/model/* (source, action, propose) ├─ kkh/studio/api.py (router)
  DualCopilot.tsx     ── /api/workbench/conversation/* ───────────────────┤    storage.py   SQLite documents + history
                                                                             models.py    editable copies, revisions,
                                                                                          OMEdit round trip, AI proposals
                                                                             dynamics.py  torque-driven follower (OMC)
                                                                             copilot.py   paired local inference
kkh/engineering/  urdf_model (parse, validate, FK) · modelica_gen (URDF → MSL MultiBody) · modelica_inspect ·
                  omc (OpenModelica service, .mat reader) · validation (independent FK)
kkh/domain/aloha/ configuration (sourced constants, manifest) · build (ALOHA2 package) · pipeline/verify ·
kkh/llm/          ollama (loopback-only client)
kkh/benchmark/    internal experiments (not in the UI): workflow_a, harness (repair pilot), detection
```

## Services
| Service | Endpoint | Owner |
|---|---|---|
| Studio API + UI | http://127.0.0.1:8000 | `scripts/start.ps1` |
| Ollama | http://127.0.0.1:11434 | user's Ollama app |
| OpenModelica 1.27.1 / OMEdit | `C:\Program Files\OpenModelica1.27.1-64bit` | installed |

## Data
* `generated/modelica/ALOHA2` — frozen generated baseline (hash-protected; never edited by the studio).
* `runs/studio/studio.sqlite3` — conversations, messages, trajectories, models, revisions, simulations, jobs (WAL,
  compare-and-swap versions, history table). Editable models: `runs/studio/models/<id>/{working,versions/<rev>}`.
  transient (`…/graphs/candidate/…`, removed after each check).

## Safety model
* LLM output never changes a model directly. Structured `parameter_changes` are checked structurally; a human click
  creates an unaccepted "AI proposal" revision; acceptance requires OpenModelica validation and an explicit action.
* Both copilot sides use the same model, seed, temperature, context window, output budget and bounded JSON schema;
