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
Modelica packages (`ALOHA2`), API paths (`/api/workbench/…`) and the Git repository name `ai-kkh-physicalai`.


## Run the existing workspace

```powershell

# After license activation, ingest and verify the evidence graph.
.venv\Scripts\python -m kkh.domain.aloha.knowledge

# Build the React UI and start the loopback FastAPI server.
scripts\start.ps1
```


### Workspaces

| Workspace | What is real |
|---|---|
| **Guided demo** | Seven-step engineering story with live facts and a system-readiness check (`docs/DEMO_2026-10-18.md`). |
| **Generate model** | Live URDF → Modelica conversion with the project converter into `runs/studio/pipeline/<id>`, mapping, completeness, OpenModelica check, integrity (sources and frozen package re-hashed). |
| **Joint simulation** | Single-joint servo model (MSL Rotational) with URDF-derived inertia and gravity, assumed servo parameters from the model revision, real OpenModelica runs, baseline vs candidate comparison, proposal as unaccepted revision. |
| Modelica Engineering Editor · Robot Workspace · AI assistant · Knowledge Explorer | Existing workspaces (revisions/OMEdit, leader–follower and cube task, paired copilot, graph and trace). |

Deep links: `?ws=journey|reasoning|pipeline|lab|editor|robot|copilot|knowledge` (+ `step`, `node`, `case`, `run`).


For a fresh Python environment, install `requirements.txt` into a virtual environment on the workspace drive. `tools/fetch_sources.py` and `tools/expand_xacro.py` reproduce pinned input assets when absent. Existing `third_party/` assets are read-only. Do not refetch or recreate the environment merely to run this preserved checkout.

## Reproduce engineering checks

```powershell
# Preserves the generated model and writes a new unique run directory.
.venv\Scripts\python -m kkh.domain.aloha.verify RightArmReach
.venv\Scripts\python -m kkh.domain.aloha.verify HoldStartPose
.venv\Scripts\python -m kkh.domain.aloha.verify LeaderArmCheck

.venv\Scripts\python -m pytest -q --basetemp=runs/pytest-check

# Paired local-model parameter generation/repair: identical sources and budgets.
.venv\Scripts\python -m kkh.benchmark.harness --repeats 2 --max-attempts 2

# Third-party DLR converter reference, evaluated separately.
.venv\Scripts\python -m kkh.benchmark.workflow_a
```

`kkh.domain.aloha.pipeline` remains the original regenerate/check/simulate pipeline. Its explicit `run_dir` now isolates generated files and avoids replacing project reports during tests. The UI uses the separate frozen-model verifier.

## Evidence and boundaries

- [Preserved engineering baseline](../reports/ENGINEERING_BASELINE.md): 29 links including world, 28 joints, 16 prescribed coordinates, two mimic joints; 9-second reach verified before feature work. FK agreement establishes consistency with URDF, not hardware, contact, controller, or actuator-load accuracy.
- `reports/benchmark.json`: latest paired B/C measurements, source and model hashes, prompts, proposals, every attempt, independent validation, actual OMC diagnostics, and model digest. `runs/benchmark/BC/` retains isolated candidates and result files. Success means the experiment completed, not that each candidate passed engineering checks.
- Copilot source IDs and single-joint axis names are validated. Other generated claims still need engineering review. Missing inline markers are rendered from the model's valid declared citation list; no citations are invented. Model changes remain proposals, and no copilot endpoint can accept or apply them.

See [PROJECT_STATUS.md](../PROJECT_STATUS.md) for the current measured milestone status and remaining limitations.
