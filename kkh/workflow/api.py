"""HTTP API of the engineering workflow (simple UI page "Repair workflow"): read every stage of a run, review, decide.

Long actions run as studio jobs (poll /api/workbench/job/{id}). Run ids and candidate keys are validated against fixed
patterns; files are read only inside a candidate package. No endpoint can write to generated/ or to an approved copy.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import faults as F
from . import review as R
from .stage1_convert import RUNS

router = APIRouter(prefix="/api/workflow")
_lock = threading.Lock()  # one OpenModelica / GPU workload at a time
RUN_ID = re.compile(r"^[\w.-]{1,120}$")


def _job(name, fn):
    from kkh.studio.api import job
    if _lock.locked():
        raise HTTPException(409, "Another workflow action is running; wait for it to finish")

    def work():
        with _lock:
            return fn()
    return job(name, work)


def _run(rid: str) -> Path:
    if not RUN_ID.match(rid) or not (RUNS / rid / "stage1" / "manifest.json").exists():
        raise HTTPException(404, "Unknown run")
    return RUNS / rid


def _j(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _guard(fn):
    try:
        return fn()
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/runs")
def runs():
    out = []
    for d in sorted(RUNS.glob("*/stage1/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        m, run = _j(d), d.parent.parent
        diag = _j(run / "stage2" / "diagnostics.json")
        out.append({"id": run.name, "robot": m["source"]["label"] if m.get("ok") else None, "created": m.get("created"),
                    "model": (_j(run / "campaign.json") or {}).get("model"), "verdict": diag["verdict"] if diag else None,
                    "validated_cases": len(list((run / "validate").glob("*/comparison.json")))})
    return out


@router.get("/runs/{rid}")
def run_detail(rid: str):
    d = _run(rid)
    m = _j(d / "stage1" / "manifest.json")
    diag = _j(d / "stage2" / "diagnostics.json")
    char = _j(d / "faults" / "characterisation.json")
    repairs = {}
    for rec in sorted(d.glob("repair/*/*/record.json")):
        r = _j(rec)
        repairs.setdefault(r["case"], {})[r["arm"]] = {"final_verdict": r.get("final_verdict"), "attempts": len(r["attempts"]),
                                                       "seconds": r.get("seconds"), "model": r["model"]}
    reviews = [_j(p) for p in sorted(d.glob("review/*/*/review.json"))]
    for rv in reviews:
        rv["validation"] = _j(R.ws_of(d, rv["key"]).parent / "validation.json")
    approvals = [_j(p) for p in sorted(d.glob("approved/*/approval.json"))]
    return {"id": rid, "campaign": _j(d / "campaign.json"), "stage0": _j(d / "stage0" / "compliance.json"),
            "stage1": {k: m.get(k) for k in ("source", "converter", "versions", "reproducibility", "summary", "assets")} if m else None,
            "unsupported": _j(d / "stage1" / "unsupported.json"),
            "stage2": {k: diag[k] for k in ("verdict", "graphics_verdict", "counts", "steps", "findings", "verdict_rule")} if diag else None,
            "faults": {"version": F.VERSION, "digest": F.set_digest(),
                       "list": [{k: f[k] for k in ("id", "title", "category", "entity", "file", "held_out", "represents")} for f in F.FAULTS],
                       "characterisation": char["rows"] if char else None},
            "repairs": repairs, "validation": _j(d / "validate" / "report.json"), "reviews": reviews, "approvals": approvals}


@router.get("/runs/{rid}/repair/{case}/{arm}")
def repair_record(rid: str, case: str, arm: str):
    d = _run(rid)
    if not re.fullmatch(r"natural|F\d\d", case) or arm not in ("ai_only", "ai_assets"):
        raise HTTPException(404)
    rec = _j(d / "repair" / case / arm / "record.json")
    if not rec:
        raise HTTPException(404, "This arm has not been run for this case")
    return {"record": rec, "edits": R.arm_edits(d, case, arm), "comparison": _j(d / "validate" / case / "comparison.json")}


@router.get("/runs/{rid}/candidate/files")
def candidate_files(rid: str, key: str):
    return _guard(lambda: R.files(_run(rid), key))


@router.get("/runs/{rid}/candidate/file")
def candidate_file(rid: str, key: str, path: str):
    return {"key": key, "path": path, "text": _guard(lambda: R.read(_run(rid), key, path))}


@router.get("/runs/{rid}/candidate/diff")
def candidate_diff(rid: str, key: str, against: str | None = None):
    return _guard(lambda: R.diff(_run(rid), key, against))


class Accept(BaseModel):
    case: str = Field(pattern=r"^(natural|F\d\d)$")
    arm: str = Field(pattern=r"^(ai_only|ai_assets)$")
    edits: list[str] = Field(max_length=200)
    reviewer: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=2000)


@router.post("/runs/{rid}/review/accept")
def review_accept(rid: str, body: Accept):
    return _guard(lambda: R.accept_edits(_run(rid), body.case, body.arm, body.edits, body.reviewer, body.note))


class Amend(BaseModel):
    key: str
    path: str = Field(max_length=200)
    text: str = Field(max_length=400_000)
    reviewer: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=2000)


@router.post("/runs/{rid}/review/amend")
def review_amend(rid: str, body: Amend):
    if body.key.startswith("approved/"):
        raise HTTPException(422, "Approved models are not edited here; amend a candidate and approve again")
    return _guard(lambda: R.amend(_run(rid), body.key, body.path, body.text, body.reviewer, body.note))


class Key(BaseModel):
    key: str


@router.post("/runs/{rid}/validate")
def validate(rid: str, body: Key):
    d = _run(rid)
    _guard(lambda: R.ws_of(d, body.key))
    return _job("Validate candidate", lambda: R.validate(d, body.key))


class Decide(BaseModel):
    key: str
    decision: str = Field(pattern=r"^(approve|reject)$")
    reviewer: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=2000)
    accept_open_findings: bool = False


@router.post("/runs/{rid}/decide")
def decide(rid: str, body: Decide):
    d = _run(rid)
    return _job("Engineering decision", lambda: R.decide(d, body.key, body.decision, body.reviewer, body.note, body.accept_open_findings))


@router.post("/runs/{rid}/omedit")
def omedit(rid: str, body: Key):
    return _guard(lambda: R.open_omedit(_run(rid), body.key))


@router.post("/runs/{rid}/simulate")
def simulate(rid: str, body: Key):
    d = _run(rid)
    return _job("Simulate approved model", lambda: R.simulate(d, body.key))


# ---------------------------------------------------------------- launch from the studio

class Launch(BaseModel):
    source: str = Field(min_length=1, max_length=80)


@router.get("/robots")
def robots():
    """The studio's pipeline robots (Unitree G1, Berkeley Humanoid Lite, ALOHA 2 follower) and uploaded URDFs."""
    from .launch import robots as _robots
    return _robots()


@router.post("/launch")
def launch(body: Launch):
    """Run URDF compliance -> convert -> OpenModelica check for one robot, in a new run (follow GET /active)."""
    from kkh.convert import sources
    from .launch import ROBOTS, launch as _launch
    if body.source not in ROBOTS and not re.fullmatch(r"upload-[0-9a-f]{16}", body.source):
        raise HTTPException(422, "Choose one of the studio's robots or an uploaded URDF")
    _guard(lambda: sources.resolve(body.source))
    return _job("Engineering pipeline", lambda: _launch(body.source))


@router.get("/active")
def active():
    from .launch import active as _active
    return _active()


# ---------------------------------------------------------------- downloads

@router.get("/runs/{rid}/versions")
def versions(rid: str):
    from . import downloads as D
    d = _run(rid)
    return [{"key": k, "label": D.describe(k)} for k in D.keys(d)]


@router.get("/runs/{rid}/download")
def download(rid: str, key: str | None = None):
    """One version ready for OMEdit (key), or every version before and after repair with diffs (no key)."""
    from fastapi.responses import Response
    from . import downloads as D
    d = _run(rid)
    data, name = _guard(lambda: D.version_zip(d, key) if key else D.compare_zip(d))
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}"'})


class RepairLaunch(BaseModel):
    model: str = Field(min_length=1, max_length=80)


@router.get("/models")
def models():
    """Local Ollama models available for the repair battle."""
    from kkh.convert.api import installed_models
    return installed_models()


@router.post("/runs/{rid}/repair")
def repair_launch(rid: str, body: RepairLaunch):
    """Both AI arms on this run's natural findings with one local model, then independent validation (follow /active)."""
    from kkh.convert.api import installed_models
    from .launch import launch_repair
    d = _run(rid)
    if body.model not in {m["name"] for m in installed_models()}:
        raise HTTPException(422, "Not an installed local model")
    return _job("AI repair battle", lambda: launch_repair(d.name, body.model))
