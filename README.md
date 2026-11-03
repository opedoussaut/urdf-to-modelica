# URDF → Modelica: conversion and repair pipeline

**Deterministic converter + AI repair, human approval.** A robot's URDF is converted to an executable Modelica model by
the pinned DLR [URDFModelica](https://github.com/DLR-RM/urdfmodelica) converter, without AI. OpenModelica checks the
result in a fixed order. Local AI then proposes repairs for what fails, those repairs are re-checked independently,
and an engineer accepts or rejects every edit before a model is approved.

Everything runs locally: OpenModelica for checks and simulation, Ollama for the AI, no hosted inference.

## The pipeline

| Stage | What it does | Code |
|---|---|---|
| **0 URDF compliance** | Is the input a valid URDF? Checks the ROS wiki specification, the tree rule and, labelled as beyond the spec, physical plausibility (positive-definite inertia, ordered limits, mesh files). Conversion is refused on errors unless an engineer overrides it. | `kkh/workflow/stage0_urdf.py` |
| **1 Convert** | DLR URDFModelica at a pinned commit, no corrections. Records a manifest (input hashes, converter arguments, tool versions), the URDF → Modelica mapping, a physical value table and the URDF content the converter ignores. | `kkh/workflow/stage1_convert.py` |
| **2 Check** | OpenModelica, in order: load, structure, balance and translation, simulation, URDF consistency (kinematics, masses, inertia, joint torques against MuJoCo), record values, and graphics separately. One machine-readable `diagnostics.json`. | `kkh/workflow/stage2_check.py` |
| **3 AI repair** | Two comparable arms on the same package and diagnostics: **AI only** and **AI + Modelica assets** (governed knowledge collection, cited by chunk id). Same model, seed, temperature and budgets for both. Edits are exact search/replace blocks; an edit that does not match is recorded as failed, never fixed up. | `kkh/workflow/stage3_repair.py`, `assets.py` |
| **4 Validate** | Fresh Stage 2 on each candidate, resolved / remaining / new findings, and an integrity guard (removed components, changed URDF values, removed assertions…). A candidate that compiles only thanks to a flagged change is rejected. | `kkh/workflow/stage4_validate.py` |
| **5 Review** | The engineer keeps or rejects each edit, can amend by hand, and re-validates. Every action records who, when and why. | `kkh/workflow/review.py` |
| **6 Approve** | Promotion of an approved copy, then a deterministic layout pass that draws missing connection lines (annotations only), OMEdit and simulation. | `kkh/workflow/review.py`, `layout.py` |

Repairs are measured on a **frozen fault set** (`kkh/workflow/faults.py`, v1 frozen before any repair run, with
held-out faults) as well as on the natural findings of the conversion. Robots supported from the studio: ALOHA 2
(vx300s arm), Unitree G1, Berkeley Humanoid Lite, THEMIS (Westwood Robotics TH02-A7), or any uploaded URDF.

Plan, design choices and open decisions: [docs/REPAIR_PIPELINE_PROPOSAL.md](docs/REPAIR_PIPELINE_PROPOSAL.md).
Measured results: [reports/workflow/](reports/workflow/).

## Setup (Windows)

Requires OpenModelica 1.27.1 with MSL 4.1.0, Python 3.11+, Node.js (for the web UI) and a local
[Ollama](https://ollama.com) server for the repair stage.

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
# Pinned public sources (DLR converter, robot descriptions, Modelica specification) -> third_party/, not in Git
.venv\Scripts\python tools\fetch_sources.py
.venv\Scripts\python tools\expand_xacro.py
```

## Run

**Studio** (the Engineering pipeline tab is the landing page):

```powershell
scripts\start.ps1
```

Then open http://127.0.0.1:8000. The start screen launches Stages 0–2 for a robot or an uploaded URDF; the repair,

**Command line** (from bash, set `PYTHONPATH=.`):

```bash
python -m kkh.workflow.stage0_urdf aloha_vx300s
python -m kkh.workflow.stage1_convert aloha_vx300s --out runs/workflow/<id>
python -m kkh.workflow.stage2_check runs/workflow/<id>
python -m kkh.workflow.faults runs/workflow/<id> --characterise
python -m kkh.workflow.stage3_repair runs/workflow/<id> --case natural --arms ai_only,ai_assets
python -m kkh.workflow.stage4_validate runs/workflow/<id>
python -m kkh.workflow.campaign runs/workflow/<id> --model qwen3-coder:30b --cases natural,F04,F05
```


## Layout

```
kkh/workflow/      the pipeline: stages 0-4, faults, assets, campaign, review/approval, layout, downloads, API
kkh/convert/       DLR converter wrapper, scorer, MuJoCo dynamics reference, export with meshes
kkh/engineering/   URDF parsing and forward kinematics, OpenModelica service, Modelica inspection
kkh/api/           FastAPI backend;  web/src/simple/  React UI (Workflow.tsx = the pipeline page, Guide.tsx)
config/            pinned public sources (public_sources.json)
reports/workflow/  committed stage and campaign reports;  runs/ (ignored) holds full outputs
presentations/     Slidev decks: repair-pipeline, themis-concept
```

## History

This repository was split on 2026-11-02 from the `feat/urdf-repair-pipeline` branch of `ai-kkh-physicalai`, history
see [docs/STUDIO_README.md](docs/STUDIO_README.md). Technical identifiers keep their historic names: the Python package
`kkh`, `KKH_*` environment variables and the API paths.
