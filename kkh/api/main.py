"""Loopback engineering API. Simulation jobs preserve the frozen generated package."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from kkh.domain.aloha import configuration as C
from kkh.domain.aloha.scenarios import scenarios
from kkh.engineering.urdf_model import rpy_to_matrix
from kkh.llm.ollama import DEFAULT_MODEL, Ollama

ROOT = C.ROOT
app = FastAPI(title="HT GEN7 PhysAI Studio", version="0.2.0")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])
pool = ThreadPoolExecutor(max_workers=1)
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


@app.middleware("http")
async def loopback_origin(request: Request, call_next):
    # Protect expensive local jobs against cross-origin browser requests.
    # The page's own origin is always allowed: the host is restricted to loopback names above, so a same-origin
    # request can only come from this studio, whatever port it is served on.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        same = origin == f"http://{request.headers.get('host', '')}"
        if not same and origin not in {None, "http://localhost:8000", "http://127.0.0.1:8000",
                                       "http://localhost:5173", "http://127.0.0.1:5173"}:
            return JSONResponse({"detail": "Cross-origin writes are prohibited"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


@app.get("/api/health")
def health():
    status = {}
    client = Ollama(timeout=3)
    try:
        installed = [m["name"] for m in client.models()]
        status["ollama"] = {"ok": True, "models": installed, "default_model": DEFAULT_MODEL,
                            "default_available": DEFAULT_MODEL in installed,
                            "note": "ready" if DEFAULT_MODEL in installed else f"default model missing: ollama pull {DEFAULT_MODEL}"}
    except Exception as exc:
        status["ollama"] = {"ok": False, "error": str(exc)}
    finally:
        client.close()
    status["openmodelica"] = {"installed": (Path(__import__('kkh.engineering.omc', fromlist=['DEFAULT_OMHOME']).DEFAULT_OMHOME) / "bin/omc.exe").exists(),
                               "last_verified": read_json(ROOT / "reports/engineering_baseline.json", {}).get("tools")}
    return status


@app.get("/api/studio")
def studio():
    return {"manifest": C.build_manifest(), "baseline": read_json(ROOT / "reports/engineering_baseline.json"),
            "reference_benchmark": read_json(ROOT / "reports/benchmark_A.json"), "scenarios": scenarios()}


@app.get("/api/runs")
def runs():
    paths = sorted((ROOT / "runs").glob("*/report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    records = [read_json(p) for p in paths]
    # Old four-arm runs are preserved on disk but do not match the ALOHA2 viewer.
    return [r for r in records if r.get("experiment") in scenarios() or r.get("source_commit") == "a909ce2"][:30]


def run_directory(run_id: str):
    if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
        raise HTTPException(400, "Invalid run ID")
    directory = ROOT / "runs" / run_id
    if not directory.is_dir():
        raise HTTPException(404, "Run not found")
    return directory


@app.get("/api/runs/{run_id}/results")
def results(run_id: str):
    path = run_directory(run_id) / "results.json"
    if not path.is_file():
        raise HTTPException(404, "No simulation results exist for this run")
    return FileResponse(path, media_type="application/json")


class RunRequest(BaseModel):
    experiment: str = "RightArmReach"


def submit(fn):
    with jobs_lock:
        if any(j["state"] in {"queued", "running"} for j in jobs.values()):
            raise HTTPException(409, "An engineering job is already running")
        job_id = uuid.uuid4().hex
        jobs[job_id] = {"id": job_id, "state": "queued"}

    def work():
        with jobs_lock:
            jobs[job_id]["state"] = "running"
        try:
            result = fn()
            with jobs_lock:
                jobs[job_id].update(state="complete" if result.get("success") else "failed", result=result)
        except Exception as exc:
            with jobs_lock:
                jobs[job_id].update(state="failed", error=str(exc))
    pool.submit(work)
    return {"id": job_id, "state": "queued"}


@app.post("/api/runs", status_code=202)
def start_run(body: RunRequest):
    if body.experiment not in scenarios():
        raise HTTPException(422, "Unknown experiment")
    from kkh.domain.aloha.verify import verify
    return submit(lambda: verify(body.experiment))


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(404, "Job not found")
        return dict(jobs[job_id])


@app.get("/api/sources/{model}/urdf")
def source_urdf(model: str):
    if model not in C.ARM_CLASS:
        raise HTTPException(404, "Unknown source model")
    return FileResponse(C.URDF_DIR / f"{model}.urdf", media_type="application/xml")


@app.get("/api/geometry")
def geometry():
    out = []
    for arm in [*C.ARMS, C.LEADER]:
        robot = C.arm_robot(arm["model"])
        for name, link in robot.links.items():
            for visual in link.visuals:
                if not visual.mesh:
                    continue
                out.append({"link": f"{arm['id']}/{name}",
                            "mesh": f"/meshes/{arm['model']}/{visual.mesh.split('/')[-1]}",
                            "scale": visual.scale.tolist(), "origin": visual.origin.xyz.tolist(),
                            "rotation": rpy_to_matrix(visual.origin.rpy).tolist()})
    return out


from kkh.studio.api import router as workbench_router
app.include_router(workbench_router)
from kkh.convert.api import router as convert_router  # noqa: E402
app.include_router(convert_router)
from kkh.workflow.api import router as workflow_router  # noqa: E402
app.include_router(workflow_router)
app.mount("/meshes", StaticFiles(directory=ROOT / "generated/modelica/ALOHA2/Resources/Meshes"), name="meshes")
dist = ROOT / "web/dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="studio")
