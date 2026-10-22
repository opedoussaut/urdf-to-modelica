"""HTTP API for the conversion comparison (simple UI, page "Convert & compare")."""
from __future__ import annotations

import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import runner, sources

router = APIRouter(prefix="/api/convert")
_run_lock = threading.Lock()  # one comparison at a time: one GPU, one OpenModelica workload


def _job(name, fn):
    from kkh.studio.api import job  # shared job store and worker pool of the studio (polled via /api/workbench/job/{id})
    return job(name, fn)


def installed_models() -> list[dict]:
    """Local Ollama models (never cloud ones). Empty list if Ollama is not running."""
    from kkh.llm.ollama import DEFAULT_MODEL, Ollama
    try:
        client = Ollama(timeout=5)
        try:
            rows = client.models()
        finally:
            client.close()
    except Exception:
        return []
    out = [{"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1), "default": m["name"] == DEFAULT_MODEL,
            "parameters": (m.get("details") or {}).get("parameter_size")}
           for m in rows if not Ollama._cloud(m["name"]) and "embed" not in m["name"]]
    return sorted(out, key=lambda m: (not m["default"], m["size_gb"]))


@router.get("/sources")
def get_sources():
    return {"sources": sources.list_sources(), "modes": runner.MODES, "criteria": runner.CRITERIA,
            "upload_limit_bytes": sources.MAX_UPLOAD, "models": installed_models()}


class Upload(BaseModel):
    filename: str = Field(max_length=200)
    content: str = Field(max_length=sources.MAX_UPLOAD)


@router.post("/upload")
def upload(body: Upload):
    try:
        return sources.store_upload(body.filename, body.content.encode("utf-8"))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


class Run(BaseModel):
    source: str = Field(max_length=80)
    modes: list[str] = Field(default_factory=lambda: ["urdfmodelica", "llm", "llm_rag"], max_length=3)
    models: list[str] = Field(default_factory=list, max_length=6)


@router.post("/run")
def run(body: Run):
    try:
        sources.resolve(body.source)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if any(m not in runner.MODES for m in body.modes) or not body.modes:
        raise HTTPException(422, "Unknown mode")
    if any(m != "urdfmodelica" for m in body.modes):
        available = {m["name"] for m in installed_models()}
        if not body.models:
            raise HTTPException(422, "Choose at least one local AI model for the AI methods")
        missing = [m for m in body.models if m not in available]
        if missing:
            raise HTTPException(422, f"Not installed in Ollama: {', '.join(missing)}")
    if _run_lock.locked():
        raise HTTPException(409, "A comparison is already running; wait for it to finish")

    def work():
        with _run_lock:
            return runner.run_comparison(body.source, body.modes, models=body.models or None)
    return _job("Conversion comparison", work)


@router.get("/active")
def active():
    """Live progress of the comparison being run (or the last one), per method."""
    return runner.active() or {"running": False}


@router.get("/active/text")
def active_text(mode: str):
    """The Modelica text an AI method is writing right now (streamed from the local model)."""
    state = runner.active() or {}
    if mode not in (state.get("modes") or {}):
        raise HTTPException(404, "No such method in the current comparison")
    return runner.live_text(mode)


def _batch_running() -> bool:
    """True while a kkh.convert.batch process is alive (it writes its PID to runs/convert/batch.pid)."""
    import os
    f = sources.RUNS / "batch.pid"
    if not f.exists():
        return False
    try:
        pid = int(f.read_text().strip())
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return code.value == 259  # STILL_ACTIVE
        os.kill(pid, 0)
        return True
    except (ValueError, OSError):
        return False


class Reset(BaseModel):
    confirm: str = Field(max_length=10)


@router.post("/reset")
def reset(body: Reset):
    """Delete everything the simplified app created: uploaded robots, all conversion runs (files, scores, edits),
    the live progress file and the "Understand" conversations about those files. Pinned robot files, the library
    search index (a rebuildable cache) and the full studio's data are not touched. Requires confirm == "RESET"."""
    import re
    import shutil
    if body.confirm != "RESET":
        raise HTTPException(422, 'Type RESET to confirm')
    state = runner.active() or {}
    if _batch_running():
        raise HTTPException(409, "A measurement campaign (kkh.convert.batch) is running; reset after it finishes")
    if _run_lock.locked() or state.get("running"):
        raise HTTPException(409, "A comparison is running; wait for it to finish before resetting")
    removed = {"runs": 0, "uploads": 0, "conversations": 0}
    root = sources.RUNS.resolve()
    for d in root.iterdir() if root.exists() else []:
        if d.is_dir() and re.fullmatch(r"[0-9a-f]{12}", d.name):
            shutil.rmtree(d)
            removed["runs"] += 1
    if sources.UPLOADS.exists():
        removed["uploads"] = sum(1 for d in sources.UPLOADS.iterdir() if d.is_dir())
        shutil.rmtree(sources.UPLOADS)
    for f in (runner.ACTIVE, runner.ACTIVE.with_suffix(".tmp")):
        f.unlink(missing_ok=True)
    from kkh.studio.api import store
    for c in store.list("conversation", limit=2000):
        if isinstance(c["data"].get("context"), dict) and c["data"]["context"].get("conversion"):
            store.update(c["id"], c["version"], delete=True)
            removed["conversations"] += 1
    return {"removed": removed}


@router.get("/runs")
def runs():
    return runner.list_runs()


@router.get("/runs/{identity}")
def get_run(identity: str):
    try:
        return runner.load(identity)
    except (KeyError, ValueError) as exc:
        raise HTTPException(404, "Unknown run") from exc


@router.get("/runs/{identity}/findings")
def get_findings(identity: str, mode: str, version: int = 0):
    """Measured problems of one file in plain words (deterministic, no AI)."""
    try:
        rep = runner.load(identity)
        if mode not in rep["modes"]:
            raise KeyError(mode)
        return runner.findings(rep, mode, version)
    except (KeyError, ValueError, IndexError) as exc:
        raise HTTPException(404, "Unknown run, mode or version") from exc


@router.get("/runs/{identity}/file")
def get_file(identity: str, mode: str, version: int = 0):
    """Main Modelica file produced by one mode (version 0 = original, n = the person's n-th edit). Read-only."""
    try:
        rep = runner.load(identity)
    except (KeyError, ValueError) as exc:
        raise HTTPException(404, "Unknown run") from exc
    m = rep["modes"].get(mode)
    if not m or not m.get("main_file"):
        raise HTTPException(404, "This mode produced no file")
    edits = m.get("edits", [])
    if version < 0 or version > len(edits):
        raise HTTPException(404, "Unknown version")
    rel = edits[version - 1]["file"] if version else m["main_file"]
    path = (sources.ROOT / rel).resolve()
    if sources.RUNS.resolve() not in path.parents:
        raise HTTPException(403, "Outside the conversion runs")
    return {"path": rel, "model": m.get("model"), "version": version, "versions": len(edits),
            "text": path.read_text(encoding="utf-8", errors="replace")}


# ------------------------------------------------------------------------------------------- reviews
def _target(kind: str, run: str = "", mode: str = "", mutation: str = "") -> dict:
    if kind == "seeded":
        from .review import _seeded_mutation
        try:
            _seeded_mutation(mutation)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"kind": "seeded", "mutation": mutation}
    if kind == "conversion":
        try:
            rep = runner.load(run)
        except (KeyError, ValueError) as exc:
            raise HTTPException(404, "Unknown run") from exc
        if mode not in rep["modes"]:
            raise HTTPException(404, "Unknown method")
        return {"kind": "conversion", "run": run, "mode": mode}
    raise HTTPException(422, "kind must be conversion or seeded")


@router.get("/review/targets")
def review_targets():
    from .review import REVIEW_MODES, seeded_list
    from kkh.benchmark.detection import CATEGORIES
    return {"seeded": seeded_list(), "runs": runner.list_runs(), "modes": REVIEW_MODES, "categories": CATEGORIES,
            "properties": __import__("kkh.convert.review", fromlist=["PROPERTIES"]).PROPERTIES, "models": installed_models()}


@router.get("/review/file")
def review_file(kind: str, run: str = "", mode: str = "", mutation: str = ""):
    """The file(s) a reviewer reads (annotations removed) and the entity names for the manual form. No ground truth."""
    from .review import entities, model_text, target_files
    t = _target(kind, run, mode, mutation)
    try:
        files, _, ctx = target_files(t)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"target": t, "label": ctx["label"], "text": model_text(files), "files": list(files),
            "omc_messages": ctx["omc_messages"], "entities": entities(t), "graph": ctx["robot"] in ("aloha_vx300s", "aloha_wx250s")}


class ReviewRun(BaseModel):
    kind: str = Field(max_length=20)
    run: str = Field(default="", max_length=40)
    mode: str = Field(default="", max_length=120)
    mutation: str = Field(default="", max_length=60)
    review_mode: str = Field(max_length=20)
    model: str = Field(default="", max_length=80)
    manual: dict | None = None
    manual_seconds: float | None = Field(default=None, ge=0, le=86400)
    reviewer: str = Field(default="", max_length=80)
    protocol: str = Field(default="v1", max_length=4)


@router.post("/review/run")
def review_run(body: ReviewRun):
    from .review import REVIEW_MODES, run_review
    t = _target(body.kind, body.run, body.mode, body.mutation)
    if body.review_mode not in REVIEW_MODES:
        raise HTTPException(422, "Unknown review mode")
    if body.review_mode != "manual":
        available = {m["name"] for m in installed_models()}
        if body.model and body.model not in available:
            raise HTTPException(422, f"Not installed in Ollama: {body.model}")
    elif body.manual is None:
        raise HTTPException(422, "A manual review needs the report")
    if body.protocol not in ("v1", "v2"):
        raise HTTPException(422, "Unknown review protocol")
    return _job("Review", lambda: run_review(t, body.review_mode, body.model or None, body.manual, body.manual_seconds, body.reviewer, body.protocol))


@router.get("/review/list")
def review_list(kind: str, run: str = "", mode: str = "", mutation: str = ""):
    """Reviews of one file with their scores, plus the ground truth (shown once reviews exist, for the comparison)."""
    from .review import list_reviews
    from .review_score import ground_truth
    t = _target(kind, run, mode, mutation)
    reviews = list_reviews(t)
    return {"target": t, "reviews": reviews, "ground_truth": ground_truth(t) if reviews else None}


@router.get("/scores")
def scores(table: str = "conversions", format: str = "json"):
    """All measured scores in one table, for research reporting: table=conversions (one row per run × method) or
    table=reviews (one row per review). format=json|csv."""
    import csv
    import io
    from fastapi.responses import Response
    from .review import list_reviews, seeded_list
    rows = []
    if table == "conversions":
        for r in runner.list_runs():
            rep = runner.load(r["id"])
            for key, m in rep["modes"].items():
                s = m.get("score", {})
                crit = {c["id"]: c["ok"] for c in s.get("criteria", [])}
                kin, dyn, par = s.get("kinematics") or {}, s.get("dynamics") or {}, s.get("parameters") or {}
                rows.append({"run": rep["id"], "started": rep.get("started"), "robot": rep["source"].get("id"),
                             "method": runner.base(key), "llm_model": m.get("llm_model") or "", "checks_passed": s.get("passed"),
                             **{f"ok_{k}": v for k, v in crit.items()},
                             "coverage": s.get("coverage"), "max_position_error_mm": kin.get("max_position_error_mm"),
                             "max_orientation_error_deg": kin.get("max_orientation_error_deg"),
                             "joint_motion_rad": kin.get("max_joint_motion_rad"), "motion": s.get("motion"),
                             "params_ok": sum(par.get(f + "_ok", 0) for f in ("axes", "masses", "com", "inertia")),
                             "params_checked": sum(par.get(f + "_checked", 0) for f in ("axes", "masses", "com", "inertia")),
                             "dynamics_worst_pct_effort": dyn.get("worst_pct_effort"),
                             "wall_seconds": m.get("wall_seconds"), "llm_calls": m.get("llm_calls"), "repair_attempts": m.get("repair_attempts")})
    elif table == "reviews":
        targets = [{"kind": "seeded", "mutation": x["id"]} for x in seeded_list()]
        for r in runner.list_runs():
            targets += [{"kind": "conversion", "run": r["id"], "mode": k} for k in r["modes"]]
        for t in targets:
            for rv in list_reviews(t):
                s = rv["score"]
                rows.append({"review": rv["id"], "created": rv["created"], "target": t.get("mutation") or f"{t['run']}:{t['mode']}",
                             "target_kind": t["kind"], "review_mode": rv["mode"], "protocol": rv.get("protocol", "v1"), "llm_model": rv.get("llm_model") or "",
                             "reviewer": rv.get("reviewer") or "", "defects": s["defects"], "found": s["found"], "found_type": s["found_type"],
                             "recall": s["recall"], "precision": s["precision"], "false_alarms": s["false_alarms"],
                             "corrections_proposed": s["corrections_proposed"], "corrections_fixed": s["corrections_fixed"],
                             "corrections_with_new_problems": s["corrections_with_new_problems"],
                             "claims_checked": s["faithfulness"]["checked"], "claims_correct": s["faithfulness"]["correct"],
                             "brier": s["brier"], "seconds": rv.get("seconds")})
    else:
        raise HTTPException(422, "table must be conversions or reviews")
    if format == "csv":
        buf = io.StringIO()
        cols = list(dict.fromkeys(k for r in rows for k in r))
        w = csv.DictWriter(buf, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="physai-{table}.csv"'})
    return rows


@router.get("/download")
def download(kind: str, what: str = "file", run: str = "", mode: str = "", mutation: str = ""):
    """Download the file under review, exactly as generated (what=file, .mo), or a package ready to open in OMEdit or
    Dymola (what=package, .zip with a README). Seeded test files get neutral names that do not reveal the error."""
    import io
    import zipfile
    from fastapi.responses import Response
    from .review import seeded_file
    t = _target(kind, run, mode, mutation)
    if t["kind"] == "seeded":
        f = seeded_file(t["mutation"])
        tag = "test-" + t["mutation"].split("-")[0]
        pkg_root, main_rel, model = f.parents[2], f"ALOHA2/Arms/{f.name}", "ALOHA2.Arms.AlohaVX300s"
        open_file, simulate = "ALOHA2/package.mo", "ALOHA2.Experiments.RightArmReach (prescribed reach motion)"
        extra = {}
        note = ("The studio's own ViperX follower model with (possibly) one deliberate error. Visual meshes are not "
                "included (animation shows no shapes); kinematics and dynamics are unaffected.")
    else:
        rep = runner.load(t["run"])
        m = rep["modes"][t["mode"]]
        if not m.get("main_file"):
            raise HTTPException(404, "This method produced no file")
        main = (sources.ROOT / m["main_file"]).resolve()
        if sources.RUNS.resolve() not in main.parents:
            raise HTTPException(403, "Outside the conversion runs")
        tag = f"{rep['source'].get('id', 'robot')}-{runner.safe_dir(t['mode'])}"
        model = m.get("model") or "(no model found in the file)"
        work = sources.RUNS / t["run"] / runner.safe_dir(t["mode"])
        extra = {p.name: p for p in [work / "KkhExcite.mo"] if p.exists()}
        if runner.base(t["mode"]) == "urdfmodelica":
            pkg_root = (sources.ROOT / m["package_file"]).resolve().parent.parent  # .../ws containing URDFModelica/
            main_rel, open_file, simulate = main.relative_to(pkg_root).as_posix(), "URDFModelica/package.mo", model
            note = ("Generated by the DLR URDFModelica converter inside an isolated copy of the URDFModelica library "
                    "(the generated robot lives in URDFModelica.Examples). Meshes are not included.")
        else:
            pkg_root, main_rel, open_file, simulate = main.parent, main.name, main.name, model
            note = ("Written by a local AI; scored by the studio as: " + str(m.get("verdict", "")))
    if what == "file":
        text = (pkg_root / main_rel).read_text(encoding="utf-8", errors="replace")
        return Response(text, media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{tag}-{Path(main_rel).name}"'})
    if what != "package":
        raise HTTPException(422, "what must be file or package")
    buf = io.BytesIO()
    skip = {".stl", ".dae", ".png", ".jpg", ".mat", ".exe", ".o", ".c", ".h", ".dll", ".log", ".json", ".makefile", ".libs"}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        files = [p for p in pkg_root.rglob("*") if p.is_file() and p.suffix.lower() not in skip
                 and "omc" not in p.relative_to(pkg_root).parts and "reviews" not in p.relative_to(pkg_root).parts
                 and "corrections" not in p.relative_to(pkg_root).parts]
        for p in files:
            z.write(p, p.relative_to(pkg_root).as_posix())
        for name, p in extra.items():
            z.write(p, name)
        z.writestr("README.txt", "\n".join([
            "HT GEN7 PhysAI Studio - model export",
            "",
            note,
            "",
            f"Open in OMEdit or Dymola:  {open_file}",
            f"Model to check / simulate: {simulate}",
            "Requires the Modelica Standard Library 4.x (the studio uses MSL 4.1.0 with OpenModelica 1.27.1).",
            "Dymola has not been tested by the studio.",
            *([f"KkhExcite.mo: the studio's standard excitation wrapper (every joint through 80 % of its range, 4 s);",
               "  open it after the package, then simulate model KkhExcite."] if extra else []),
        ]) + "\n")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{tag}.zip"'})


@router.get("/robot3d")
def robot3d(source: str):
    """Links, visuals and joints of a robot for the 3D view (meshes referenced by index)."""
    from .robot3d import describe
    try:
        return describe(source)[0]
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/mesh")
def mesh(source: str, i: int, lod: str = "full"):
    """One visual mesh of a robot, by index into its URDF's resolved meshes (never by path); lod=low: light preview copy."""
    from fastapi.responses import FileResponse
    from .robot3d import describe, simplified
    try:
        _, meshes = describe(source)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if not 0 <= i < len(meshes):
        raise HTTPException(404, "Unknown mesh")
    return FileResponse(simplified(meshes[i]) if lod == "low" else meshes[i], media_type="model/stl", headers={"Cache-Control": "max-age=86400"})


@router.get("/runs/{run_id}/replay")
def run_replay(run_id: str, mode: str):
    """Stored OpenModelica motion of one method's model, with the URDF pose at the same joint angles (3D replay)."""
    from .replay import build
    try:
        return build(run_id, mode)
    except KeyError as exc:
        raise HTTPException(404, "Unknown run") from exc
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
