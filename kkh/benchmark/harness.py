"""Reproducible B/C ablation on frozen full-assembly parameter generation/repair.

Both arms use the same source URDF excerpt, model, seed, task and token budget.
C additionally receives graph facts retrieved from the live reasoning repository.
Numeric proposals are applied ONLY in isolated copies, never accepted into the project.
This measures constrained parameter repair, not unconstrained whole-robot synthesis.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import time
import uuid
from xml.etree import ElementTree as ET

import numpy as np

from kkh.domain.aloha.configuration import ROOT, URDF_DIR, arm_robot
from kkh.domain.aloha.build import variable_filter
from kkh.domain.aloha.pipeline import Pipeline
from kkh.domain.aloha.scenarios import scenarios
from kkh.engineering.omc import MatResult, OMCService
from kkh.llm.ollama import Ollama

TASKS = [
    {"id": "generate-elbow-axis", "joint": "elbow", "field": "axis",
     "instruction": "Generate the elbow joint axis vector in its URDF joint frame for Modelica n. Return {axis:[x,y,z]}.", "fault": [0, 0, 0]},
    {"id": "repair-finger-mimic", "joint": "right_finger", "field": "value",
     "instruction": "The candidate has right_finger = +1 * left_finger. Repair its multiplier from the source. Return {value:number}.", "fault": 1},
    {"id": "repair-shoulder-limit", "joint": "shoulder", "field": "value",
     "instruction": "The candidate shoulder q_min is -3 rad. Repair it from the URDF (radians), preserving the URDF when a vendor page disagrees. Return {value:number}.", "fault": -3},
]


def expected(task):
    j = arm_robot("aloha_vx300s").joints[task["joint"]]
    return j.axis.tolist() if task["field"] == "axis" else j.mimic[1] if j.mimic else j.limit.lower


def extract_value(task, content):
    data = json.loads(content)
    value = data[task["field"]]
    values = value if isinstance(value, list) else [value]
    if (task["field"] == "axis" and len(values) != 3) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 10 for v in values):
        raise ValueError("Proposal must contain finite bounded numbers")
    return value


def apply_proposal(source: str, task: dict, value) -> str:
    """Only validated numeric literals enter Modelica source."""
    if task["id"] == "repair-finger-mimic":
        for lhs, rhs in [("q", "q[8]"), ("qd", "qd[8]"), ("qdd", "qdd[8]")]:
            pattern = rf"(j_right_finger\.{lhs} = )[-+\d.eE]+( \* {re.escape(rhs)})"
            source, count = re.subn(pattern, lambda m: m[1] + str(float(value)) + m[2], source)
            if count != 1:
                raise ValueError("Frozen mimic template changed")
        return source
    pattern = rf"(j_{task['joint']}\([^;]+?)(\))"
    match = re.search(pattern, source)
    if not match:
        raise ValueError("Frozen joint template changed")
    block = match[1]
    if task["field"] == "axis":
        literal = "{" + ", ".join(str(float(v)) for v in value) + "}"
        block, count = re.subn(r"n = \{[^}]+\}", lambda _: "n = " + literal, block)
    else:
        block, count = re.subn(r"q_min = [-+\d.eE]+", lambda _: "q_min = " + str(float(value)), block)
    if count != 1:
        raise ValueError("Frozen parameter template changed")
    return source[:match.start()] + block + match[2] + source[match.end():]


def evaluate(task, value, directory: Path):
    candidate = directory / "candidate" / "ALOHA2"
    shutil.copytree(ROOT / "generated/modelica/ALOHA2", candidate)
    file = candidate / "Arms/AlohaVX300s.mo"
    file.write_text(apply_proposal(file.read_text(), task, value), encoding="utf-8")
    record = {"parameter_correct": bool(np.allclose(value, expected(task), atol=1e-10, rtol=0)),
              "check_ok": False, "simulate_ok": False, "engineering_valid": False}
    omc = OMCService(directory / "omc")
    try:
        record["load"] = omc.load_package(candidate / "package.mo").to_dict()
        record["check"] = omc.check("ALOHA2.Experiments.RightArmReach").to_dict()
        record["check_ok"] = record["load"]["ok"] and record["check"]["ok"]
        if not record["check_ok"]:
            return record
        sc = scenarios()["RightArmReach"]
        sim = omc.simulate("ALOHA2.Experiments.RightArmReach", 9, intervals=450, variable_filter=variable_filter(sc))
        record["simulation"] = sim.to_dict()
        record["simulate_ok"] = sim.ok
        if sim.ok:
            res = MatResult(sim.data["resultFile"])
            arms = json.loads((ROOT / "generated/modelica/aloha2_mapping.json").read_text())["arms"]
            validation = Pipeline("RightArmReach", run_dir=directory)._validate(res, arms, sc)
            record["validation"] = validation
            record["engineering_valid"] = validation["ok"] and record["parameter_correct"]
    finally:
        omc.close()
    return record


def run(model=None, repeats=1, seed=42, max_attempts=2) -> dict:
    from kkh.llm.ollama import DEFAULT_MODEL
    model = model or DEFAULT_MODEL  # recorded in the report; historical reports keep their own model ID
    if not 1 <= repeats <= 10:
        raise ValueError("repeats must be 1–10")
    if not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be 1–3")
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    out = ROOT / "runs/benchmark/BC" / run_id
    out.mkdir(parents=True)
    source_path = URDF_DIR / "aloha_vx300s.urdf"
    tree = ET.parse(source_path)
    frozen = ROOT / "generated/modelica/ALOHA2/Arms/AlohaVX300s.mo"
    report = {"run_id": run_id, "model": model, "seed": seed, "repeats": repeats, "max_attempts": max_attempts,
              "scope": "Constrained numeric parameter generation/repair in isolated copies of the full ALOHA2 assembly",
              "protocol": f"Same URDF excerpt, tasks, seed, temperature=0, 8192 context, 500 output tokens, up to {max_attempts} attempts. Failed attempts receive independent validation diagnostics, never a hidden target answer. Numeric proposals are evaluated only in isolated full-model copies.",
              "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
              "frozen_model_sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
              "started": dt.datetime.now(dt.timezone.utc).isoformat(), "trials": []}
    client = Ollama()
    try:
        report["model_digest"] = next(m["digest"] for m in client.models() if m["name"] == model)
        for repeat in range(repeats):
            for task in TASKS:
                for workflow in ["B"]:
                    trial = {"workflow": workflow, "task": task["id"], "repeat": repeat,
                             "seed": seed + repeat, "initial_fault": task["fault"], "parameter_correct": False,
                             "check_ok": False, "simulate_ok": False, "engineering_valid": False}
                    trial_dir = out / f"{repeat}-{task['id']}-{workflow}"
                    trial_dir.mkdir()
                    start = time.perf_counter()
                    try:
                        excerpt = ET.tostring(tree.find(f"joint[@name='{task['joint']}']"), encoding="unicode")
                        context = {"task": task["instruction"], "source_urdf": excerpt}
                        schema = {"type": "object", "properties": {
                            task["field"]: {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
                            if task["field"] == "axis" else {"type": "number"}},
                            "required": [task["field"]], "additionalProperties": False}
                        messages = [{"role": "system", "content": "Recover the requested Modelica parameter from supplied engineering evidence. Return only the requested JSON. Preserve URDF frame conventions and SI units."},
                                    {"role": "user", "content": json.dumps(context)}]
                        trial["prompt"] = messages
                        from kkh.rag.repair import repair
                        attempts = repair(messages,
                            lambda history: client.chat(history, model=model, schema=schema, seed=seed+repeat, max_tokens=500),
                            lambda content: extract_value(task, content),
                            lambda value, index: evaluate(task, value, trial_dir / f"attempt-{index+1}"),
                            max_attempts=max_attempts)
                        trial["attempts"] = attempts
                        trial["first_attempt_valid"] = bool(attempts[0].get("engineering_valid"))
                        trial["repair_iterations"] = len(attempts) - 1
                        trial.update({k: v for k, v in attempts[-1].items() if k not in {"attempt", "prompt"}})
                    except Exception as exc:
                        trial["error"] = str(exc)
                    trial["wall_seconds"] = round(time.perf_counter() - start, 3)
                    report["trials"].append(trial)
                    (trial_dir / "trial.json").write_text(json.dumps(trial, indent=2), encoding="utf-8")
                    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                    print(f"{workflow} {task['id']}: valid={trial['engineering_valid']} ({trial['wall_seconds']}s)", flush=True)
    finally:
        client.close()
    report["summary"] = {w: {"trials": len(rows := [t for t in report["trials"] if t["workflow"] == w]),
                                    "parameter_correct": sum(t["parameter_correct"] for t in rows),
                                    "executable": sum(t["simulate_ok"] for t in rows),
                                    "engineering_valid": sum(t["engineering_valid"] for t in rows),
                                    "first_attempt_valid": sum(t.get("first_attempt_valid", False) for t in rows),
                                    "repair_iterations": sum(t.get("repair_iterations", 0) for t in rows),
                                    "mean_wall_seconds": round(sum(t["wall_seconds"] for t in rows)/len(rows), 2)} for w in ["B"]}
    report["success"] = all("response" in t and "error" not in t for t in report["trials"])
    report["finished"] = dt.datetime.now(dt.timezone.utc).isoformat()
    b = report["summary"]["B"]
    report["interpretation"] = (f"B validated {b['engineering_valid']}/{b['trials']} candidates. "
        + "Compilation alone does not establish engineering correctness. These constrained tasks and local model do not establish whole-model synthesis or statistical generalization.")
    report["frozen_model_unchanged"] = hashlib.sha256(frozen.read_bytes()).hexdigest() == report["frozen_model_sha256"]
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "reports/benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-attempts", type=int, default=2)
    args = parser.parse_args()
    result = run(args.model, args.repeats, max_attempts=args.max_attempts)
    print(json.dumps(result["summary"], indent=2))
