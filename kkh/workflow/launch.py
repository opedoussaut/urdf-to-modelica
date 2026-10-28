"""Launch the pipeline from the studio: URDF compliance (Stage 0) -> convert (Stage 1) -> OpenModelica check (Stage 2),
for one of the studio's robots or an uploaded URDF. Progress is written to runs/workflow/active.json after every step
so the page can follow it; nothing is estimated, every step reports when it really starts and ends.

The AI repair, review and approval stages are then run from their own pages (they need a model choice and a person).
"""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

from kkh.convert import sources

from . import stage1_convert as s1
from . import stage2_check as s2

ROBOTS = ("themis", "unitree_g1", "berkeley_humanoid_lite", "aloha_vx300s")  # the studio's pipeline robots, in display order
ACTIVE = s1.RUNS / "active.json"
# Short run names: Windows limits paths to 260 characters and the converter's own library already uses ~140 of them.
SHORT = {"themis": "themis", "unitree_g1": "g1", "berkeley_humanoid_lite": "bhl", "aloha_vx300s": "aloha"}
STEPS = [("compliance", "URDF compliance"), ("convert", "Convert (DLR URDFModelica)"), ("check", "OpenModelica check")]


def robots() -> list[dict]:
    """The three studio robots and every uploaded URDF, with what the start screen shows."""
    keep = ("id", "label", "short", "what", "license", "provenance", "links", "joints", "movable", "mass_kg", "kind", "filename",
            "featured", "sources", "repo")
    out = []
    for s in sources.list_sources():
        if s["id"] in ROBOTS or s.get("kind") != "pinned":
            out.append({k: s.get(k) for k in keep})
    out.sort(key=lambda s: ROBOTS.index(s["id"]) if s["id"] in ROBOTS else len(ROBOTS))
    return out


class Progress:
    def __init__(self, run_id: str, source: str, label: str):
        self.state = {"run": run_id, "source": source, "label": label, "running": True, "started": time.time(),
                      "steps": [{"id": i, "label": l, "status": "pending"} for i, l in STEPS]}
        self.write()

    def write(self):
        ACTIVE.parent.mkdir(parents=True, exist_ok=True)
        tmp = ACTIVE.with_suffix(".tmp")
        tmp.write_text(json.dumps({**self.state, "now": time.time()}), encoding="utf-8")
        for _ in range(20):  # Windows: the page may be reading the file
            try:
                tmp.replace(ACTIVE)
                return
            except PermissionError:
                time.sleep(0.05)

    def step(self, sid: str, status: str, note: str | None = None):
        s = next(x for x in self.state["steps"] if x["id"] == sid)
        s["status"] = status
        s["started" if status == "running" else "finished"] = time.time()
        if note:
            s["note"] = note
        self.write()

    def close(self, ok: bool, error: str | None = None):
        self.state.update(running=False, finished=time.time(), ok=ok, error=error)
        self.write()


def active() -> dict:
    if not ACTIVE.exists():
        return {"running": False}
    st = json.loads(ACTIVE.read_text(encoding="utf-8"))
    st["now"] = time.time()
    return st


def launch(source: str, log=print, force: bool = False) -> dict:
    """Run stages 0-2 for `source` in a new run directory; returns {run, ok, verdict, ...}. force: an engineer's
    override converts a URDF that Stage 0 refused; the refusal stays on record and the run is labelled as forced."""
    urdf, meta = sources.resolve(source)  # refuses unknown ids
    run_id = f"{SHORT.get(source, source.replace('upload-', 'up-')[:9])}-{dt.datetime.now().strftime('%y%m%d-%H%M%S')}"
    out = s1.RUNS / run_id
    p = Progress(run_id, source, meta.get("label") or urdf.name)
    try:
        p.step("compliance", "running")
        from kkh.convert.robot3d import resolve_mesh
        from .stage0_urdf import check
        comp = check(urdf, resolve_mesh)
        p.step("compliance", "failed" if comp["blocking"] else "done",
               comp["verdict"] + (" · converted anyway: engineer override, recorded" if comp["blocking"] and force else ""))
        if not comp["blocking"] or force:
            p.step("convert", "running")
        m = s1.run(source, out, log=log, force=force)  # repeats Stage 0 as its own gate and records it in the run
        if not m.get("ok"):
            p.step("convert", "skipped" if comp["blocking"] and not force else "failed", m.get("error", "")[:300])
            p.step("check", "skipped")
            p.close(False, m.get("error"))
            return {"run": run_id, "ok": False, "error": m.get("error"), "compliance": comp["verdict"]}
        p.step("convert", "done", f"{m['summary']['mapped_links']} links, {m['summary']['mapped_joints']} joints mapped")
        p.step("check", "running")
        diag = s2.run(out, log=log)
        p.step("check", "done", diag.get("verdict"))
        p.close(True)
        return {"run": run_id, "ok": True, "verdict": diag.get("verdict"), "compliance": comp["verdict"], "forced": comp["blocking"] and force}
    except Exception as exc:  # report, never hide
        for s in p.state["steps"]:
            if s["status"] == "running":
                p.step(s["id"], "failed", f"{type(exc).__name__}: {exc}"[:300])
        p.close(False, f"{type(exc).__name__}: {exc}"[:500])
        raise


REPAIR_STEPS = [("ai_only", "AI only"), ("ai_assets", "AI + Modelica knowledge"), ("validate", "Independent validation")]


def launch_repair(base_run: str, model: str, log=print) -> dict:
    """The AI Repair Comparison on a run's own (natural) findings: both arms with the same local model, then independent
    validation. Runs in a copy of the base run named <run>--<model>, like the measured campaigns."""
    from . import campaign
    from . import stage3_repair as s3
    from . import stage4_validate as s4
    base = s1.RUNS / base_run
    if not (base / "stage2" / "diagnostics.json").exists():
        raise ValueError("This run has no OpenModelica check yet; launch the pipeline first")
    d = campaign.model_run(base, model)
    p = Progress(d.name, base_run, f"AI Repair Comparison · {model}")
    p.state["steps"] = [{"id": i, "label": l, "status": "pending"} for i, l in REPAIR_STEPS]
    p.write()
    try:
        for arm in s3.ARMS:
            p.step(arm, "running")
            rec = s3.repair(d, "natural", arm, model, log=log)
            p.step(arm, "done", rec.get("final_verdict"))
        p.step("validate", "running")
        s4.validate_case(d, "natural", log=log)
        rep = s4.report(d, ["natural"])
        states = {a: (rep["cases"][0]["arms"].get(a) or {}).get("state") for a in s3.ARMS}
        p.step("validate", "done", " · ".join(f"{dict(REPAIR_STEPS)[a]}: {s}" for a, s in states.items()))
        p.close(True)
        return {"run": d.name, "ok": True, "states": states}
    except Exception as exc:
        for s in p.state["steps"]:
            if s["status"] == "running":
                p.step(s["id"], "failed", f"{type(exc).__name__}: {exc}"[:300])
        p.close(False, f"{type(exc).__name__}: {exc}"[:500])
        raise
