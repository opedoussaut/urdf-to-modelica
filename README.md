# HT GEN7 PhysAI Studio

**Engineering-Grounded Physical AI**

| Name | Use |
|---|---|
| **HT GEN7 PhysAI Studio** | Official project and application name |
| **PhysAI** | Short form of Physical AI |
| **Physical AI** | Full technical term |
| **GEN7** | Initiative identity |
| **Engineering-Grounded Physical AI** | Positioning tagline |

Technical identifiers keep their historic names so that code, data and history stay valid: the Python package `kkh`,
`KKH_*` environment variables, the GraphDB repository `kkh-aloha-engineering`, ontology URIs (`https://w3id.org/kkh/…`),
Modelica packages (`ALOHA2`), API paths (`/api/workbench/…`) and the Git repository name `ai-kkh-physicalai`.

Local engineering demonstrator built on the preserved `feat/aloha-baseline` branch: pinned public ALOHA 2 assets → evidence graph → executable Modelica twin → ontology-grounded Ollama copilot.

## Run the existing workspace

```powershell
# Activate the existing project GraphDB service only.
docker compose up -d --no-deps graphdb

# After license activation, ingest and verify the evidence graph.
.venv\Scripts\python -m kkh.domain.aloha.knowledge

# Build the React UI and start the loopback FastAPI server.
scripts\start.ps1
```

Open [HT GEN7 PhysAI Studio](http://127.0.0.1:8000) or [GraphDB Workbench](http://localhost:7201). The installed local Ollama server must be running on port 11434. Primary local engineering copilot: **NVIDIA Nemotron 3 Nano 4B** (`nemotron-3-nano:4b`, override with `KKH_OLLAMA_MODEL`); any other installed local model can be chosen in the UI, and a missing model is reported explicitly (never substituted). The application does not download models, call hosted inference, or use cloud fallback. Historical benchmark reports keep the model IDs they were produced with (qwen3). See `docs/MODEL_STRATEGY_NVIDIA_FIRST.md`.

### Workspaces

| Workspace | What is real |
|---|---|
| **Demo Journey** | Seven-step engineering story with live facts and a system-readiness check (`docs/DEMO_2026-10-18.md`). |
| **Engineering Reasoning** | Joint reasoning chain read from the URDF and GraphDB (asserted / inferred / verified / assumed / simulated), ontology rule check of seeded faulty models on isolated copies. |
| **Robot Model Pipeline** | Live URDF → Modelica conversion with the project converter into `runs/studio/pipeline/<id>`, mapping, completeness, OpenModelica check, integrity (sources and frozen package re-hashed). |
| **1D Simulation Lab** | Single-joint servo model (MSL Rotational) with URDF-derived inertia and gravity, assumed servo parameters from the model revision, real OpenModelica runs, baseline vs candidate comparison, proposal as unaccepted revision. |
| Modelica Engineering Editor · Robot Workspace · Dual AI Copilot · Knowledge Explorer | Existing workspaces (revisions/OMEdit, leader–follower and cube task, paired copilot, graph and trace). |

Deep links: `?ws=journey|reasoning|pipeline|lab|editor|robot|copilot|knowledge` (+ `step`, `node`, `case`, `run`).

The UI provides recorded 3D playback with pinned vendor meshes, joint telemetry and source inspection, a GraphDB-backed physical relationship graph, reasoning witnesses, measured B/C benchmark results, the source discrepancy register, and an evidence-cited copilot. All playback data comes from actual OpenModelica runs. **Run verification** compiles and simulates the existing generated package without regenerating it.

For a fresh Python environment, install `requirements.txt` into a virtual environment on the workspace drive. `tools/fetch_sources.py` and `tools/expand_xacro.py` reproduce pinned input assets when absent. Existing `third_party/` assets are read-only. Do not refetch or recreate the environment merely to run this preserved checkout.

## Reproduce engineering checks

```powershell
# Preserves the generated model and writes a new unique run directory.
.venv\Scripts\python -m kkh.domain.aloha.verify RightArmReach
.venv\Scripts\python -m kkh.domain.aloha.verify HoldStartPose
.venv\Scripts\python -m kkh.domain.aloha.verify LeaderArmCheck

# Includes synthetic and full-model OMC round trips, real GraphDB and Ollama checks.
.venv\Scripts\python -m pytest -q --basetemp=runs/pytest-check

# Paired local-model parameter generation/repair: identical sources and budgets.
.venv\Scripts\python -m kkh.benchmark.harness --repeats 2 --max-attempts 2

# Third-party DLR converter reference, evaluated separately.
.venv\Scripts\python -m kkh.benchmark.workflow_a
```

`kkh.domain.aloha.pipeline` remains the original regenerate/check/simulate pipeline. Its explicit `run_dir` now isolates generated files and avoids replacing project reports during tests. The UI uses the separate frozen-model verifier.

## Evidence and boundaries

- [Preserved engineering baseline](reports/ENGINEERING_BASELINE.md): 29 links including world, 28 joints, 16 prescribed coordinates, two mimic joints; 9-second reach verified before feature work. FK agreement establishes consistency with URDF, not hardware, contact, controller, or actuator-load accuracy.
- `reports/ontology.json`: GraphDB version and repository, full-precision data round trip, explicit/inferred witnesses, SPARQL facts, application pySHACL and GraphDB bulk SHACL reports with negative controls. Bulk validation does not install an incremental SHACL write gate.
- `reports/benchmark.json`: latest paired B/C measurements, source and model hashes, prompts, proposals, every attempt, independent validation, actual OMC diagnostics, and model digest. `runs/benchmark/BC/` retains isolated candidates and result files. Success means the experiment completed, not that each candidate passed engineering checks.
- B = Ollama with raw URDF; C = the same input plus ontology evidence. The current benchmark measures constrained numeric parameter generation/repair in a full-model context. It does not establish unrestricted whole-model synthesis or statistical generalization. Workflow A uses its own motion experiment and must not be ranked as a matched B/C trial.
- Copilot source IDs and single-joint axis names are validated. Other generated claims still need engineering review. Missing inline markers are rendered from the model's valid declared citation list; no citations are invented. Model changes remain proposals, and no copilot endpoint can accept or apply them.
- GraphDB writes are restricted to repository `kkh-aloha-engineering`. The primary endpoint is port 7201. Ports 7200 and 7300 belong to unrelated containers. Read-only retrieval uses fixed queries; bounded SPARQL rejects updates and federation.
- Runtime outputs, local license files, and backups are excluded from Git. [GraphDB upgrade record](docs/GRAPHDB_UPGRADE.md) documents the data-preserving 11.3.3 upgrade and the cold backup.

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for the current measured milestone status and remaining limitations.
