"""HTTP API for the conversion comparison (simple UI, page "Convert & compare")."""
from __future__ import annotations

import threading

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


class Edit(BaseModel):
    mode: str = Field(max_length=20)
    text: str = Field(min_length=10, max_length=400_000)
    note: str = Field(default="", max_length=300)


@router.post("/runs/{identity}/edit")
def edit(identity: str, body: Edit):
    """Save a person's edited file as a new version and check it with OpenModelica (job)."""
    try:
        runner.load(identity)
    except (KeyError, ValueError) as exc:
        raise HTTPException(404, "Unknown run") from exc
    return _job("Check edited Modelica file", lambda: runner.save_edit(identity, body.mode, body.text, body.note))


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
