"""Run the conversion comparison: each mode in its own isolated directory, one shared scorer, one report.

    PYTHONPATH=. python -m kkh.convert.runner aloha_wx250s [--modes urdfmodelica,llm,llm_rag]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
import uuid
from pathlib import Path

from . import llm, score, sources, urdfmodelica

MODES = {
    "llm": {"label": "AI only", "plain": "The local AI reads the robot file and writes the model on its own."},
    "llm_rag": {"label": "AI + Modelica library search",
                "plain": "The same AI, but first given matching building blocks found in the Modelica libraries."},
    "urdfmodelica": {"label": "URDFModelica converter",
                     "plain": "A published, rule-based converter (DLR) translates the file. No AI involved."},
}
CRITERIA = {
    "produced": "A model file was produced",
    "loads": "OpenModelica can read it",
    "checks": "OpenModelica accepts it as a complete model",
    "simulates": "It runs (2 s simulation)",
    "coverage": "Every part and joint of the robot is in it",
    "kinematics": "Its geometry matches the robot file while the joints move (within 1 mm and 0.1°)",
    "parameters": "Joint axes, masses, centres of mass and inertias match the robot file",
    "dynamics": "Motor torques match the robot file's physics (within 5 % of each joint's limit)",
}


def _jsonable(o):
    if isinstance(o, Path):
        try:
            return o.resolve().relative_to(sources.ROOT).as_posix()
        except ValueError:
            return o.as_posix()
    raise TypeError(type(o))


def verdict(name: str, s: dict, result: dict | None = None) -> str:
    """Deterministic plain-language summary of one score (no LLM)."""
    label = MODES[base(name)]["label"] + (f" ({name.split(':', 1)[1]})" if ":" in name else "")
    attempts = (result or {}).get("attempts") or []
    if not s.get("produced"):
        why = ""
        if any("incomplete" in str(a.get("error", "")) for a in attempts):
            why = " The AI's reply was cut off before the file was complete."
        elif any(a.get("error") for a in attempts):
            why = " The AI call failed: " + str(next(a["error"] for a in attempts if a.get("error")))[:160]
        elif (result or {}).get("error"):
            why = " " + str(result["error"])[:160]
        return f"{label} produced no usable model.{why}"
    scored = next((a for a in attempts if a.get("attempt") == (result or {}).get("best_attempt")), None)
    if scored and scored.get("truncated") and not s.get("loads"):
        return f"{label} ran out of room: its file was cut off before the end, so OpenModelica cannot read it."
    if not s.get("loads"):
        return f"{label} wrote a file OpenModelica cannot read (syntax or unknown names)."
    if not s.get("checks"):
        return f"{label} wrote a readable file, but OpenModelica rejects it as incomplete or inconsistent."
    if not s.get("simulates"):
        return f"{label} produced a valid model that fails when simulated."
    kin = s.get("kinematics") or {}
    cov = s.get("coverage", 0)
    parts = f"{s.get('links_found')}/{s.get('links_total')} parts and {s.get('joints_found')}/{s.get('joints_total')} moving joints"
    if not kin:
        return f"{label} produced a model that runs, with {parts} recognisable; its geometry could not be compared."
    good = "matches" if kin.get("pass") else "differs from"
    return (f"{label} produced a model that runs, with {parts}; its geometry {good} the robot file "
            f"(largest gap {kin['max_position_error_mm']} mm, at {kin['worst_link'][0] if kin.get('worst_link') else '-'}).")


ACTIVE = sources.RUNS / "active.json"


class Progress:
    """Live status of the running comparison (polled by the page): per mode its state, current phase and the exact
    time it started. Phases are real events; the page's bar within a phase is an estimate from typical durations."""

    def __init__(self, identity: str, source_label: str, modes: list[str]):
        self.state = {"id": identity, "source": source_label, "started": time.time(), "running": True,
                      "modes": {m: {"status": "waiting"} for m in modes}}
        self.write()

    def write(self):
        ACTIVE.parent.mkdir(parents=True, exist_ok=True)
        tmp = ACTIVE.with_suffix(".tmp")
        tmp.write_text(json.dumps({**self.state, "now": time.time()}), encoding="utf-8")
        tmp.replace(ACTIVE)

    def phase(self, mode: str, phase: str, attempt: int | None = None, attempts: int | None = None):
        m = self.state["modes"][mode]
        if m["status"] == "waiting":
            m.update(status="running", started=time.time())
        m.update(phase=phase, phase_started=time.time(), attempt=attempt, attempts=attempts)
        self.write()

    def checks(self, mode: str, items: list[dict], activity: str):
        self.state["modes"][mode].update(checks=items, activity=activity)
        self.write()

    def done(self, mode: str, r: dict):
        m = self.state["modes"][mode]
        m.update(status="done" if r["score"].get("produced") else "failed", finished=time.time(),
                 passed=r["score"].get("passed"), phase=None, activity=None,
                 checks=score.live_checks(r["score"], {c["id"] for c in r["score"]["criteria"]}))
        self.write()

    def close(self):
        self.state["running"] = False
        self.state["finished"] = time.time()
        self.write()


def active() -> dict | None:
    if not ACTIVE.exists():
        return None
    state = json.loads(ACTIVE.read_text(encoding="utf-8"))
    state["now"] = time.time()
    return state


def base(key: str) -> str:
    """Mode of a result key: 'urdfmodelica', 'llm', 'llm_rag' or 'llm:<ollama model>' / 'llm_rag:<ollama model>'."""
    return key.split(":", 1)[0]


def safe_dir(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", key)


def run_comparison(source: str, modes: list[str] | None = None, log=print, models: list[str] | None = None) -> dict:
    """Run each selected method; AI methods run once per selected local model (key '<mode>:<model>')."""
    modes = modes or ["urdfmodelica", "llm", "llm_rag"]
    for m in modes:
        if m not in MODES:
            raise ValueError(f"Unknown mode {m}")
    models = models or [llm.DEFAULT_MODEL]
    keys = [m if m == "urdfmodelica" else f"{m}:{model}" for m in modes for model in (models if m != "urdfmodelica" else [None])]
    urdf, meta = sources.resolve(source)
    identity = uuid.uuid4().hex[:12]
    root = sources.RUNS / identity
    root.mkdir(parents=True)
    report = {"id": identity, "source": {**meta, "sha256": sources.sha256(urdf), **sources.summary(urdf)},
              "started": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "modes": {},
              "criteria": CRITERIA, "scoring": score.__doc__}
    progress = Progress(identity, meta.get("label", source), keys)
    try:
        for m in keys:
            log(f"[{m}] starting")
            d = root / safe_dir(m)
            d.mkdir()
            t = time.time()
            live = lambda items, activity, m=m: progress.checks(m, items, activity)  # noqa: E731
            try:
                if m == "urdfmodelica":
                    progress.phase(m, "converting")
                    r = urdfmodelica.convert(urdf, d)
                    progress.phase(m, "checking")
                    r["score"] = score.score(urdf, r.get("package_file"), r.get("model"), d, on_step=live)
                else:
                    r = llm.convert(urdf, d, rag=(base(m) == "llm_rag"), model=m.split(":", 1)[1],
                                    score_fn=lambda f, model, w, live=live: score.score(urdf, f, model, w, on_step=live), log=log,
                                    phase=lambda ph, a, n, m=m: progress.phase(m, ph, a, n))
                    r.setdefault("score", score.finish({"produced": False}))
            except Exception as exc:  # report the failure; never invent a result
                r = {"mode": base(m), "error": f"{type(exc).__name__}: {exc}"[:1500], "score": score.finish({"produced": False})}
            r["wall_seconds"] = round(time.time() - t, 1)
            r["label"], r["plain"] = MODES[base(m)]["label"], MODES[base(m)]["plain"]
            r["verdict"] = verdict(m, r["score"], r)
            report["modes"][m] = r
            progress.done(m, r)
            log(f"[{m}] {r['verdict']}")
            (root / "report.json").write_text(json.dumps(report, indent=1, default=_jsonable), encoding="utf-8")
    finally:
        progress.close()
    ranking = sorted(report["modes"], key=lambda m: report["modes"][m]["score"]["rank_key"], reverse=True)
    report["ranking"] = ranking
    keys = {m: report["modes"][m]["score"]["rank_key"] for m in ranking}
    report["ties"] = [[a, b] for i, a in enumerate(ranking) for b in ranking[i + 1:] if keys[a] == keys[b]]
    report["finished"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    (root / "report.json").write_text(json.dumps(report, indent=1, default=_jsonable), encoding="utf-8")
    return json.loads(json.dumps(report, default=_jsonable))


def list_runs() -> list[dict]:
    out = []
    for f in sorted(sources.RUNS.glob("*/report.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        r = json.loads(f.read_text(encoding="utf-8"))
        out.append({"id": r["id"], "source": r["source"].get("label"), "started": r.get("started"),
                    "finished": r.get("finished"), "ranking": r.get("ranking"),
                    "modes": {m: {"passed": v["score"].get("passed"), "verdict": v.get("verdict")} for m, v in r["modes"].items()}})
    return out


def load(identity: str) -> dict:
    if not identity.isalnum():
        raise ValueError("Bad run id")
    f = sources.RUNS / identity / "report.json"
    if not f.exists():
        raise KeyError(identity)
    report = json.loads(f.read_text(encoding="utf-8"))
    # verdicts, labels and ties are pure functions of the stored scores: recompute so older reports read the same way
    for m, r in report["modes"].items():
        r["label"], r["plain"] = MODES[base(m)]["label"], MODES[base(m)]["plain"]
        r["verdict"] = verdict(m, r["score"], r)
    if report.get("ranking"):
        keys = {m: report["modes"][m]["score"]["rank_key"] for m in report["ranking"]}
        report["ties"] = [[a, b] for i, a in enumerate(report["ranking"]) for b in report["ranking"][i + 1:] if keys[a] == keys[b]]
    return report


def _first_errors(messages: str, n: int = 3) -> str:
    lines = [l.strip() for l in (messages or "").splitlines() if "Error" in l or "error:" in l.lower()]
    return "\n".join(lines[:n]) or (messages or "").strip()[-400:]


def findings(report: dict, mode: str, version: int = 0) -> list[dict]:
    """Measured problems of one generated file, in plain words, derived only from its real OpenModelica score and the
    URDF (no AI). Each item: title (plain), detail (engineering), basis ('measured' / 'inferred from the URDF'),
    and for defects a machine-readable `entity` (URDF name, last segment) and `category` (the categories of
    kkh/benchmark/detection.CATEGORIES), `defect` True. These are the natural-defect ground truth for scoring reviews."""
    from kkh.engineering.urdf_model import load_urdf
    m = report["modes"][mode]
    s = m["edits"][version - 1]["score"] if version and m.get("edits") else m["score"]
    robot = load_urdf(sources.ROOT / report["source"]["path"])
    out = []
    short = lambda n: (n or "").split("/")[-1]

    def add(title, detail="", basis="measured", entity=None, category=None, defect=True):
        out.append({"title": title, "detail": detail, "basis": basis, "entity": short(entity) if entity else None,
                    "category": category, "defect": defect})
    if not s.get("produced"):
        add("No model file was produced", m.get("error") or "", entity="model", category="other")
        return out
    if not s.get("loads"):
        add("OpenModelica cannot read the file (syntax error or unknown building blocks)", _first_errors(s.get("load_messages")),
            entity="model", category="other")
        return out
    if not s.get("checks"):
        add("OpenModelica rejects the model as incomplete or inconsistent", _first_errors(s.get("check_messages")),
            entity="model", category="other")
        return out
    if not s.get("simulates"):
        add("The model fails when simulated", _first_errors(s.get("simulate_messages")), entity="model", category="other")
        return out
    for l in s.get("missing_links") or []:
        add(f"Part {short(l)} is missing from the model", "URDF link not found in the simulated model", entity=l, category="missing_component")
    for j in s.get("missing_joints") or []:
        add(f"Joint {short(j)} is missing from the model", "URDF moving joint not found in the simulated model", entity=j, category="missing_component")
    kin = s.get("kinematics") or {}
    suspects = (s.get("structure") or {}).get("suspect_joints")
    if suspects is None and kin.get("worst_link"):  # reports scored before localisation existed
        pj = robot.parent_joint(kin["worst_link"][0]) if kin["worst_link"][0] in robot.links else None
        suspects = [pj.name] if pj is not None else []
    suspects = suspects or []
    if kin and not kin.get("pass"):
        link = kin["worst_link"][0] if kin.get("worst_link") else "?"
        add(f"A part is in the wrong place: {short(link)} ends up {kin['max_position_error_mm']:.1f} mm from where the robot file puts it",
            f"max {kin['max_position_error_mm']} mm, mean {kin['mean_position_error_mm']} mm over {kin['links_compared']} links"
            + (f"; orientation up to {kin['max_orientation_error_deg']} deg" if kin.get("max_orientation_error_deg") else "")
            + " (URDF forward kinematics at the simulated joint angles)", defect=False)
        for jn in suspects:
            j = robot.joints.get(jn)
            if j is not None and j.mimic:
                src, mult, off = j.mimic
                add(f"Likely cause: the robot file says joint '{short(jn)}' must copy joint '{short(src)}' "
                    f"(times {mult:g}{f', plus {off:g}' if off else ''}), and the model does not enforce this coupling",
                    f'URDF <mimic joint="{src}" multiplier="{mult:g}" offset="{off:g}"/> on {jn}', "inferred from the URDF",
                    entity=jn, category="mimic")
            else:
                add(f"Joint {short(jn)} is the first place where the geometry goes wrong (its origin, axis or parent link)",
                    "first misplaced link on its chain from the root", entity=jn, category="geometry")
    par = s.get("parameters") or {}
    for a in [a for a in par.get("axes", []) if not a["match"]]:
        add(f"Joint {short(a['joint'])} turns around the wrong axis", f"model {a['model']} vs URDF {a['urdf']}", entity=a["joint"], category="axis")
    for x in [x for x in par.get("masses", []) if not x["match"]]:
        add(f"Part {short(x['link'])} has the wrong mass", f"model {x['model']:.6g} kg vs URDF {x['urdf']:.6g} kg",
            entity=x["link"], category="parameter_provenance")
    for x in [x for x in par.get("com", []) if not x["match"]]:
        add(f"Part {short(x['link'])} has its centre of mass in the wrong place", f"{x['error_mm']} mm from the URDF <inertial> origin",
            entity=x["link"], category="parameter_provenance")
    for x in [x for x in par.get("inertia", []) if not x["match"]]:
        add(f"Part {short(x['link'])} has the wrong inertia", f"largest relative difference {x['max_rel_error']:.1%}",
            entity=x["link"], category="parameter_provenance")
    for x in (s.get("dynamics") or {}).get("joints", []):
        if not x.get("match", True):
            add(f"Joint {short(x['joint'])} needs a different motor torque than the robot file implies",
                f"RMS error {x['rms_nm']} N·m ({x['rms_pct_effort']}% of the URDF effort limit) vs MuJoCo inverse dynamics",
                entity=x["joint"], category="parameter_provenance")
    if kin and kin.get("max_joint_motion_rad", 1) < 0.01:
        add("The joints barely moved during the check, so the geometry comparison is weak",
            f"largest joint motion {kin.get('max_joint_motion_rad')} rad in the 2 s run", defect=False)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--modes", default="urdfmodelica,llm,llm_rag")
    ap.add_argument("--models", default="", help="comma-separated local Ollama models for the AI methods (default: the studio default)")
    a = ap.parse_args()
    rep = run_comparison(a.source, a.modes.split(","), models=[m for m in a.models.split(",") if m] or None)
    print(json.dumps({"id": rep["id"], "ranking": rep["ranking"],
                      "verdicts": {m: v["verdict"] for m, v in rep["modes"].items()}}, indent=1))
