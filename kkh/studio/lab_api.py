"""1D Simulation Lab and Robot Model Pipeline endpoints (registered on the workbench router).

Both run real local tools only: OpenModelica for simulation/checks and the existing deterministic URDF→Modelica
generator. Outputs go to isolated directories under runs/studio/; the frozen generated package, the pinned URDF
sources and accepted revisions are never written.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field

from kkh.domain.aloha import configuration as C

from .api import guard, job, models, router, store
from . import servo1d as S1

def _rel(path) -> str:
    """Repository-relative path for records; absolute when outside the repository (e.g. test directories)."""
    try:
        return Path(path).resolve().relative_to(C.ROOT).as_posix()
    except ValueError:
        return str(path)


PIPELINE_RUNS = C.ROOT / "runs" / "studio" / "pipeline"
FROZEN = C.ROOT / "generated" / "modelica" / "ALOHA2"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): _sha(p) for p in sorted(root.rglob("*")) if p.is_file()} if root.exists() else {}


# ================================================================================================ 1D Simulation Lab
class ServoParams(BaseModel):
    kp: float
    kd: float
    actuatorTime: float
    feedforward: float


class ServoInput(BaseModel):
    kind: str = "step"
    amplitude: float = 0.3
    step_time: float = 0.5
    ramp_time: float = 0.0
    stop_time: float = 3.0
    trajectory: str | None = None


class ServoRun(BaseModel):
    joint: str = "shoulder"
    model: str | None = None
    revision: str | None = None
    candidate: ServoParams | None = None
    input: ServoInput = Field(default_factory=ServoInput)


def _revision_servo(model: str | None, revision: str | None, joint: str) -> tuple[dict, str, str | None]:
    """Baseline servo parameters: the selected (or accepted, else head) revision of a model, else generator defaults."""
    if not model:
        return dict(S1.SERVO_DEFAULTS), "generator defaults (ALOHA2.Control.ServoGains)", None
    workspace = store.get(model, "model")
    rid = revision or workspace["data"].get("accepted") or workspace["data"].get("head")
    rev = store.get(rid, "revision")
    if rev["data"]["workspace"] != model:
        raise ValueError("Revision belongs to another model")
    from .dynamics import SETTINGS_FILE, read_servo
    directory = models.revision_dir(rev)
    if not (directory / SETTINGS_FILE).exists():
        return dict(S1.SERVO_DEFAULTS), f"generator defaults (revision {rid[:8]} predates the Control package)", rid
    values = read_servo(directory).get(joint)
    if not values:
        raise ValueError(f"Revision {rid[:8]} has no servo settings for {joint}")
    status = rev["data"]["status"] + (" · accepted" if workspace["data"].get("accepted") == rid else "")
    return {k: float(values[k]) for k in S1.TUNABLE}, f"revision {rid[:8]} ({status}) · Control/FollowerServoSettings.mo", rid


def _semantics(joint: str) -> dict:
    """Knowledge-graph semantics of each tunable servo parameter (best effort: GraphDB may be offline)."""
    try:
        from kkh.semantic.graphdb import GraphDB
        from kkh.semantic.parameters import applicability
        db = GraphDB(timeout=6)
        try:
            return {k: applicability(db, f"ALOHA2.Control.FollowerServoSettings.{joint}", k) for k in S1.TUNABLE}
        finally:
            db.close()
    except Exception as exc:
        return {"_error": f"GraphDB unavailable: {str(exc)[:160]}"}


@router.get("/lab/servo1d/setup")
def servo_setup(joint: str = "shoulder", model: str | None = None, revision: str | None = None):
    plant = guard(lambda: S1.derive_plant(joint))
    baseline, label, rid = guard(lambda: _revision_servo(model, revision, joint))
    cmd = S1.command({"kind": "step"}, plant)
    trajectories = [{"id": t["id"], "name": t["name"], "duration_s": t["data"]["time"][-1],
                     "space": t["data"].get("reference_space", "leader_joints")} for t in store.list("trajectory", limit=50)]
    return {"joint": joint, "joints": S1.SERVO_JOINTS, "plant": plant, "baseline": baseline, "baseline_label": label,
            "revision": rid, "bounds": S1.SERVO_BOUNDS, "units": S1.UNITS, "semantics": _semantics(joint),
            "model_preview": S1.modelica_source(plant, baseline, cmd), "trajectories": trajectories}


@router.post("/lab/servo1d/run")
def servo_run(body: ServoRun):
    baseline, label, rid = guard(lambda: _revision_servo(body.model, body.revision, body.joint))
    candidate = body.candidate.model_dump() if body.candidate else None
    if candidate is not None:
        guard(lambda: S1.check_params(candidate))
    spec = body.input.model_dump()
    if spec["kind"] == "trajectory":
        record = guard(lambda: store.get(spec["trajectory"] or "", "trajectory"))
        spec.update({"data": record["data"], "name": record["name"], "id": record["id"]})
    guard(lambda: S1.command({k: v for k, v in spec.items()}, S1.derive_plant(body.joint)))  # validate before queueing

    def run():
        result = S1.run_experiment(body.joint, baseline, candidate, spec, baseline_label=label, revision=rid)
        result["model"] = body.model
        result["governance"] = {k: v for k, v in _semantics(body.joint).items() if not k.startswith("_")} if candidate else {}
        name = f"1D {body.joint} · {result['input']['label']}" + (" · baseline vs candidate" if candidate else "")
        return store.create("servo1d", name, result, result["id"])
    return job("1D servo experiment (OpenModelica)", run)


@router.get("/lab/servo1d/runs")
def servo_runs(limit: int = 20):
    out = []
    for r in store.list("servo1d", limit=limit):
        d = r["data"]
        out.append({"id": r["id"], "name": r["name"], "created": r["created"], "joint": d["joint"],
                    "ok": all(x["ok"] for x in d["runs"].values()), "summary": (d.get("comparison") or {}).get("summary"),
                    "baseline": d["runs"]["baseline"].get("params"), "candidate": d["runs"].get("candidate", {}).get("params")})
    return out


class ServoProposal(BaseModel):
    model: str
    reason: str = ""


@router.post("/lab/servo1d/{identity}/propose")
def servo_propose(identity: str, body: ServoProposal):
    """Write the candidate's changed servo values into the model's working copy as a new UNACCEPTED revision.

    Reuses the guarded proposal path (bounds from Modelica, all-or-nothing). Acceptance still requires
    OpenModelica validation and an explicit human click in the editor/compare panel."""
    record = guard(lambda: store.get(identity, "servo1d"))
    data = record["data"]
    cand, base = data["runs"].get("candidate"), data["runs"]["baseline"]
    if not cand or not cand.get("ok"):
        raise HTTPException(422, "Only a successfully simulated candidate can be proposed")
    from .copilot import ontology_applicability
    changes = []
    for key in S1.TUNABLE:
        if abs(cand["params"][key] - base["params"][key]) <= 1e-12:
            continue
        gate = ontology_applicability(f"ALOHA2.Control.FollowerServoSettings.{data['joint']}", key, "Control/FollowerServoSettings.mo")
        if not gate["applicable"]:
            raise HTTPException(422, f"{key}: {gate['reason']}")
        changes.append({"file": "Control/FollowerServoSettings.mo", "component": data["joint"], "parameter": key,
                        "value": cand["params"][key]})
    if not changes:
        raise HTTPException(422, "The candidate does not change any servo parameter")
    reason = (f"1D Lab experiment {identity[:8]} ({data['input']['label']}): "
              + ", ".join(f"{data['joint']}.{c['parameter']}={c['value']:g}" for c in changes)
              + (f" - {body.reason}" if body.reason else ""))
    result = guard(lambda: models.propose_parameters(body.model, "Control/FollowerServoSettings.mo", changes, reason))
    store.update(identity, record["version"], {**data, "proposal_revision": result["revision"], "proposal_model": body.model})
    return result


# ================================================================================================ Robot Model Pipeline
SOURCES = {
    "aloha2": {"label": "ALOHA 2 assembly - two ViperX-300 followers + WidowX-250 leader (project assembly of pinned arm URDFs)",
               "files": ["data/urdf/aloha_vx300s.urdf", "data/urdf/aloha_wx250s.urdf"],
               "interface": "kkh.domain.aloha.build.build(out_root=…)"},
    "aloha_vx300s": {"label": "ViperX-300 follower arm (pinned Interbotix URDF)", "files": ["data/urdf/aloha_vx300s.urdf"],
                     "interface": "kkh.engineering.modelica_gen.component_library + robot_class"},
    "aloha_wx250s": {"label": "WidowX-250 leader arm (pinned Interbotix URDF)", "files": ["data/urdf/aloha_wx250s.urdf"],
                     "interface": "kkh.engineering.modelica_gen.component_library + robot_class"},
}
HIGHLIGHT = {"aloha_vx300s": ["shoulder", "left_finger", "right_finger"], "aloha_wx250s": ["shoulder", "left_finger", "right_finger"]}


def _robot_summary(model: str) -> dict:
    robot = C.arm_robot(model)
    joints = list(robot.joints.values())
    structure = robot.validate_structure()
    inertials = robot.validate_inertials()
    placeholders = [l for l, link in robot.links.items() if link.is_placeholder]
    return {
        "model": model, "product": C.ARM_PRODUCT[model], "root": robot.root,
        "links": len(robot.links), "joints": len(joints),
        "fixed": sum(j.type == "fixed" for j in joints), "moving": sum(j.movable for j in joints),
        "mimic": sum(j.mimic is not None for j in joints), "actuated": len(robot.actuated_joints()),
        "total_mass_kg": round(sum(l.inertial.mass for l in robot.links.values() if l.inertial), 4),
        "placeholder_links": placeholders, "structure": structure, "inertial_issues": inertials,
        "joint_table": [{"name": j.name, "type": j.type, "parent": j.parent, "child": j.child,
                         "axis": [float(v) for v in j.axis], "lower": j.limit.lower if j.limit else None,
                         "upper": j.limit.upper if j.limit else None, "effort": j.limit.effort if j.limit else None,
                         "velocity": j.limit.velocity if j.limit else None,
                         "mimic": {"joint": j.mimic[0], "multiplier": j.mimic[1], "offset": j.mimic[2]} if j.mimic else None,
                         "unit": "m" if j.type == "prismatic" else "rad"} for j in joints],
    }


@router.get("/lab/pipeline/sources")
def pipeline_sources():
    out = []
    for key, s in SOURCES.items():
        files = [{"path": f, "sha256": _sha(C.ROOT / f), "bytes": (C.ROOT / f).stat().st_size} for f in s["files"]]
        arms = [m for m in ("aloha_vx300s", "aloha_wx250s") if f"data/urdf/{m}.urdf" in s["files"]]
        out.append({"id": key, **s, "files_detail": files, "arms": [_robot_summary(m) for m in arms]})
    return {"sources": out, "provenance": C.SRC, "frozen_package": _rel(FROZEN),
            "note": "ALOHA 2 is assembled by this project from two follower URDF arms (and the leader); "
                    "it is not a separately published official ALOHA 2 URDF."}


def _mapping_rows(model: str, class_file: Path) -> list[dict]:
    """URDF joint → generated Modelica component with the modifiers that carry axis, limits and mimic."""
    from kkh.engineering.modelica_inspect import parse_class, parse_modifiers
    robot = C.arm_robot(model)
    comps = {c["name"]: c for c in parse_class(class_file)["components"]}
    rows = []
    for name in HIGHLIGHT.get(model, []):
        j = robot.joints[name]
        comp = comps.get("j_" + name)
        rows.append({"urdf_joint": name, "type": j.type, "axis": [float(v) for v in j.axis],
                     "limits": [j.limit.lower, j.limit.upper] if j.limit else None,
                     "mimic": {"joint": j.mimic[0], "multiplier": j.mimic[1], "offset": j.mimic[2]} if j.mimic else None,
                     "modelica_component": comp["name"] if comp else None, "modelica_type": comp["type"] if comp else None,
                     "modifiers": parse_modifiers(comp["modifiers"]) if comp else {}})
    return rows


def _mimic_equations(class_file: Path) -> list[str]:
    import re
    text = class_file.read_text(encoding="utf-8")
    return [l.strip() for l in text.splitlines() if re.search(r"finger", l) and ("=" in l) and ("*" in l or "-" in l)
            and not l.strip().startswith(("parameter", "ALOHA2", "//", "annotation"))][:6]


def run_pipeline(source: str) -> dict:
    if source not in SOURCES:
        raise ValueError("Unknown source")
    spec = SOURCES[source]
    identity = uuid.uuid4().hex
    root = PIPELINE_RUNS / identity
    root.mkdir(parents=True)
    stages = []
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def stage(name, fn):
        t = dt.datetime.now()
        try:
            out = fn()
            stages.append({"stage": name, "ok": True, "seconds": round((dt.datetime.now() - t).total_seconds(), 2), "result": out})
            return out
        except Exception as exc:
            stages.append({"stage": name, "ok": False, "seconds": round((dt.datetime.now() - t).total_seconds(), 2),
                           "error": str(exc)[:2000]})
            raise

    sources_before = {f: _sha(C.ROOT / f) for f in spec["files"]}
    frozen_before = _tree_hashes(FROZEN)
    arms = [m for m in ("aloha_vx300s", "aloha_wx250s") if f"data/urdf/{m}.urdf" in spec["files"]]
    result = {"id": identity, "source": source, "label": spec["label"], "interface": spec["interface"],
              "started": started, "output_root": _rel(root), "stages": stages}
    try:
        stage("1 · Source", lambda: {"files": [{"path": f, "sha256": h} for f, h in sources_before.items()],
                                     "provenance": C.SRC})
        stage("2 · Parse & validate URDF", lambda: {m: {k: v for k, v in _robot_summary(m).items() if k != "joint_table"} for m in arms})

        def generate():
            from kkh.domain.aloha.build import GENERATOR_VERSION, _mesh_uri, build
            from kkh.engineering import modelica_gen as mg
            if source == "aloha2":
                record = build(out_root=root)
                return {"package": _rel((root / "ALOHA2")), "generator_version": GENERATOR_VERSION,
                        "files": len(record["files"]), "file_hashes": record["files"], "totals": record["totals"],
                        "placeholders": record["placeholders"], "class_files": {m: f"ALOHA2/Arms/{C.ARM_CLASS[m]}.mo" for m in arms}}
            model = arms[0]
            pkg = root / "ALOHA2"
            files = dict(mg.component_library("ALOHA2"))
            text, cm = mg.robot_class(C.arm_robot(model), "ALOHA2", C.ARM_CLASS[model], "ALOHA2.Arms",
                                      f"{C.ARM_PRODUCT[model]} ({model} URDF)", _mesh_uri, "")
            files[f"Arms/{C.ARM_CLASS[model]}.mo"] = text
            files["Arms/package.mo"] = 'within ALOHA2;\npackage Arms "Arm models generated one-to-one from URDF"\n  extends Modelica.Icons.Package;\nend Arms;\n'
            files["Arms/package.order"] = C.ARM_CLASS[model] + "\n"
            files["package.mo"] = (f'within ;\npackage ALOHA2 "Single-arm candidate generated from {model}.urdf"\n'
                                   f'  extends Modelica.Icons.Package;\n  annotation(uses(Modelica(version = "{mg.MSL_VERSION}")), version = "{GENERATOR_VERSION}");\nend ALOHA2;\n')
            files["package.order"] = "Components\nBlocks\nArms\n" if "Blocks/package.mo" in files else "Components\nArms\n"
            for rel, t in files.items():
                (pkg / rel).parent.mkdir(parents=True, exist_ok=True)
                (pkg / rel).write_text(t, encoding="utf-8")
            hashes = {rel: hashlib.sha256(t.encode()).hexdigest() for rel, t in sorted(files.items())}
            (root / "build_record.json").write_text(json.dumps({"generator": spec["interface"], "generator_version": GENERATOR_VERSION,
                                                                "inputs": sources_before, "files": hashes}, indent=1), encoding="utf-8")
            return {"package": _rel(pkg), "generator_version": GENERATOR_VERSION, "files": len(files),
                    "file_hashes": hashes, "class_files": {model: f"ALOHA2/Arms/{C.ARM_CLASS[model]}.mo"},
                    "mapped": {"links": len(cm.links), "joints": len(cm.joints), "actuated": len(cm.actuated)},
                    "placeholders": cm.placeholders, "meshes": "not copied for single-arm candidates (visualisation only)"}
        generated = stage("3 · Generate Modelica (real converter)", generate)

        def mapping():
            out = {}
            for m in arms:
                cf = root / generated["class_files"][m]
                out[m] = {"class_file": generated["class_files"][m], "rows": _mapping_rows(m, cf), "mimic_equations": _mimic_equations(cf)}
            return out
        stage("4 · URDF ↔ Modelica mapping", mapping)

        def completeness():
            from kkh.engineering.modelica_inspect import completeness as comp
            return {m: comp(C.arm_robot(m), root / generated["class_files"][m]) for m in arms}
        stage("5 · Completeness (independent inspection)", completeness)

        def omc_check():
            from kkh.engineering.omc import OMCService
            omc = OMCService(root / "omc")
            try:
                loaded = omc.load_package(root / "ALOHA2" / "package.mo")
                checks = {}
                for m in arms:
                    cls = f"ALOHA2.Arms.{C.ARM_CLASS[m]}"
                    c = omc.check(cls)
                    checks[cls] = {"ok": c.ok, "equations": c.data.get("equations"), "variables": c.data.get("variables"),
                                   "message": c.messages[-600:]}
                if source == "aloha2":
                    c = omc.check("ALOHA2.Experiments.RightArmReach")
                    checks["ALOHA2.Experiments.RightArmReach"] = {"ok": c.ok, "equations": c.data.get("equations"),
                                                                 "variables": c.data.get("variables"), "message": c.messages[-600:]}
                version = omc.version()
            finally:
                omc.close()
            if not loaded.ok or not all(v["ok"] for v in checks.values()):
                raise RuntimeError(json.dumps({"load": loaded.ok, "load_message": loaded.messages[-800:], "checks": checks}))
            return {"omc": version, "command": "loadFile(package.mo); checkModel(<class>)", "checks": checks}
        stage("6 · OpenModelica load & check", omc_check)

        def integrity():
            after = {f: _sha(C.ROOT / f) for f in spec["files"]}
            frozen_after = _tree_hashes(FROZEN)
            new = generated["file_hashes"]
            frozen_rel = {k: v for k, v in frozen_before.items()}
            same = sum(1 for k, v in new.items() if frozen_rel.get(k) == v)
            return {"sources_unchanged": after == sources_before, "frozen_package_unchanged": frozen_after == frozen_before,
                    "generated_files_identical_to_frozen": f"{same}/{len(new)}",
                    "note": "Deterministic generator: identical bytes mean the preserved package is reproducible from the pinned URDF."}
        stage("7 · Integrity & reproducibility", integrity)
        result["ok"] = True
    except Exception:
        result["ok"] = False
    result["finished"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    (root / "pipeline_report.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result


class PipelineRun(BaseModel):
    source: str = "aloha2"


@router.post("/lab/pipeline/run")
def pipeline_run(body: PipelineRun):
    if body.source not in SOURCES:
        raise HTTPException(422, "Choose one of the allowlisted pinned sources")

    def run():
        result = run_pipeline(body.source)
        return store.create("pipeline", f"URDF→Modelica · {body.source} · {result['id'][:8]}", result, result["id"])
    return job("URDF → Modelica conversion", run)


@router.get("/lab/pipeline/runs")
def pipeline_runs(limit: int = 10):
    return [{"id": r["id"], "name": r["name"], "created": r["created"], "ok": r["data"].get("ok"),
             "source": r["data"]["source"]} for r in store.list("pipeline", limit=limit)]


@router.get("/lab/pipeline/{identity}/file")
def pipeline_file(identity: str, path: str):
    """Read one generated Modelica file of a pipeline run (read-only, confined to that run's package)."""
    guard(lambda: store.get(identity, "pipeline"))
    base = (PIPELINE_RUNS / identity / "ALOHA2").resolve()
    target = (base / path).resolve()
    if base not in target.parents or target.suffix != ".mo" or not target.exists():
        raise HTTPException(404, "File not found in this generated package")
    return {"path": path, "text": target.read_text(encoding="utf-8")}


class PipelineImport(BaseModel):
    name: str = "Generated candidate (URDF→Modelica)"
    confirm: bool = False


@router.post("/lab/pipeline/{identity}/import")
def pipeline_import(identity: str, body: PipelineImport):
    """Explicitly import a freshly generated full ALOHA2 package as a NEW editable model workspace."""
    record = guard(lambda: store.get(identity, "pipeline"))
    if not body.confirm:
        raise HTTPException(422, "Confirm the import explicitly")
    if record["data"]["source"] != "aloha2" or not record["data"].get("ok"):
        raise HTTPException(422, "Only a successful full ALOHA 2 package can become an editable model")
    package = PIPELINE_RUNS / identity / "ALOHA2"
    return guard(lambda: models.create(body.name, source=package,
                                       reason=f"Imported URDF→Modelica candidate {identity[:8]} (generated from pinned URDF)"))


# ================================================================================================ Ontology reasoning
@router.get("/lab/reasoning/joint")
def reasoning_joint(joint: str = "shoulder", robot: str = "aloha_vx300s"):
    from . import reasoning
    from .robotics import JOINTS
    if joint not in JOINTS:
        raise HTTPException(422, "Unknown joint")
    arm = "leader" if robot == "aloha_wx250s" else "follower_right"
    return guard(lambda: reasoning.joint_reasoning(joint, arm, store))


@router.get("/lab/ontology/cases")
def ontology_cases():
    from kkh.benchmark.detection import MUTATIONS
    from .reasoning import DIAGNOSTIC_CASES
    by_id = {m["id"]: m for m in MUTATIONS}
    return [{"id": c, "description": by_id[c]["description"], "category": by_id[c].get("category"),
             "held_out": bool(by_id[c].get("held_out"))} for c in DIAGNOSTIC_CASES]


class Diagnostic(BaseModel):
    case: str = "M3-unit-degrees"


@router.post("/lab/ontology/diagnostic")
def ontology_diagnostic(body: Diagnostic):
    from . import reasoning
    if body.case not in reasoning.DIAGNOSTIC_CASES:
        raise HTTPException(422, "Unknown diagnostic case")
    return guard(lambda: reasoning.rule_diagnostic(body.case))


# ================================================================================================ Readiness
@router.get("/lab/readiness")
def readiness():
    """What is available right now and what each missing dependency disables. No green without a real check."""
    import shutil as _sh
    from kkh.engineering.omc import DEFAULT_OMHOME
    from kkh.llm.ollama import DEFAULT_MODEL, Ollama
    items = []
    try:
        from kkh.semantic.graphdb import GraphDB
        db = GraphDB(timeout=4)
        try:
            graphs = {r["g"]: int(r["n"]) for r in db.select("SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g", infer=False)}
            items.append({"id": "graphdb", "label": "GraphDB knowledge graph", "ok": bool(graphs), "detail":
                          f"{db.repo} · {sum(graphs.values())} triples in {len(graphs)} named graphs", "graphs": graphs,
                          "disables": "ontology reasoning, rule diagnostics, applicability gates, trace"})
        finally:
            db.close()
    except Exception as exc:
        items.append({"id": "graphdb", "label": "GraphDB knowledge graph", "ok": False, "detail": str(exc)[:160],
                      "disables": "ontology reasoning, rule diagnostics, applicability gates, trace"})
    omc = Path(DEFAULT_OMHOME) / "bin" / "omc.exe"
    last = store.list("servo1d", limit=1)
    items.append({"id": "openmodelica", "label": "OpenModelica", "ok": omc.exists(), "detail": str(omc) + (
        f" · last 1D run {last[0]['created'][:19]} ({last[0]['data']['runs']['baseline'].get('omc_version', '')})" if last else " · no 1D run yet"),
        "disables": "all simulations and Modelica checks"})
    try:
        client = Ollama(timeout=3)
        try:
            installed = [m["name"] for m in client.models()]
        finally:
            client.close()
        items.append({"id": "ollama", "label": "Local copilot (Ollama)", "ok": DEFAULT_MODEL in installed,
                      "detail": f"default {DEFAULT_MODEL} · installed: {', '.join(installed) or 'none'}", "model": DEFAULT_MODEL,
                      "disables": "AI explanations only (engineering functions do not depend on it)"})
    except Exception as exc:
        items.append({"id": "ollama", "label": "Local copilot (Ollama)", "ok": False, "detail": str(exc)[:160], "model": DEFAULT_MODEL,
                      "disables": "AI explanations only (engineering functions do not depend on it)"})
    urdf = [{"path": f, "sha256": _sha(C.ROOT / f)[:16]} for f in ("data/urdf/aloha_vx300s.urdf", "data/urdf/aloha_wx250s.urdf")]
    items.append({"id": "sources", "label": "Pinned URDF sources", "ok": all((C.ROOT / u["path"]).exists() for u in urdf),
                  "detail": " · ".join(f"{u['path'].split('/')[-1]} {u['sha256']}…" for u in urdf), "disables": "conversion and derivation"})
    pkg = sum(1 for _ in FROZEN.rglob("*.mo"))
    items.append({"id": "package", "label": "Preserved generated Modelica package", "ok": pkg > 0,
                  "detail": f"generated/modelica/ALOHA2 · {pkg} .mo files (frozen baseline)", "disables": "editor baseline"})
    last_pipe = store.list("pipeline", limit=1)
    return {"items": items, "default_model": DEFAULT_MODEL,
            "latest": {"servo1d": last[0]["id"] if last else None, "pipeline": last_pipe[0]["id"] if last_pipe else None},
            "checked": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
