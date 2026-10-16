"""Benchmark workflow A - deterministic third-party conversion (DLR URDFModelica), no LLM.

Public assets -> documented mechanical pre-processing -> URDFModelica urdf_to_package.py -> OpenModelica.
Pre-processing is limited to two workarounds for converter defects found during evaluation:
  T1  '/'-namespaced URDF names -> '_' (Modelica class names cannot contain '/')
  T2  <texture> material -> <color rgba> (converter crashes on textures: TypeError in make_Material_Text)
and running the converter with a relative root path (defect: it rewrites '-' to '_' in absolute paths).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from kkh.engineering.omc import MatResult, OMCService
from kkh.engineering.urdf_model import load_urdf
from kkh.engineering.validation import compare_frames

ROOT = Path(__file__).resolve().parents[2]
UMO = ROOT / "third_party" / "urdfmodelica" / "URDFModelica"
URDF = ROOT / "data" / "urdf" / "aloha_stationary.urdf"
PREFIX = "aloha_stationaryRun.aloha_stationary"


def _cls(name: str) -> str:
    return name.replace("/", "_").replace("-", "_").capitalize()


def run(out_dir: Path | None = None, stop_time: float = 3.0, log=print) -> dict:
    t0 = time.time()
    out_dir = out_dir or ROOT / "runs" / "benchmark" / "A" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    ws = out_dir / "ws"
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(UMO, ws / "URDFModelica", ignore=shutil.ignore_patterns("Reference", "*.PNG", "*.png"))
    metrics = {"workflow": "A", "description": "DLR URDFModelica (deterministic, no LLM)",
               "converter_commit": "92541b6f6aa76fd510983a25afd3082377b4028f", "preprocessing": ["T1", "T2", "relative-root"],
               "human_interventions": 3, "repair_iterations": 0, "llm_calls": 0}

    text = URDF.read_text(encoding="utf-8")
    text = re.sub(r'(name|link|joint)="([^"/]*)/([^"]*)"', r'\1="\2_\3"', text)            # T1
    text = re.sub(r'<texture filename="[^"]*"\s*/>', '<color rgba="0.1 0.1 0.1 1" />', text)  # T2
    (ws / "aloha.urdf").write_text(text, encoding="utf-8")
    p = subprocess.run([sys.executable, "URDFModelica/Resources/urdf_to_package.py", "-i", "aloha.urdf",
                        "-o", "aloha_record.mo", "-r", ".", "-p", "URDFModelica/Examples", "-s"],
                       cwd=ws, capture_output=True, text=True, timeout=300)
    metrics["converter_ok"] = p.returncode == 0
    if p.returncode != 0:
        metrics["converter_error"] = p.stderr[-2000:]
        return _finish(metrics, out_dir, t0)
    gen = ws / "URDFModelica" / "Examples" / "Aloha_stationary"
    robot = load_urdf(URDF)
    link_cls = {f.stem for f in (gen / "Links").glob("*.mo") if not f.stem.endswith("Params") and f.stem != "package"}
    joint_cls = {f.stem for f in (gen / "Joints").glob("*.mo") if not f.stem.endswith("Params") and f.stem != "package"}
    metrics["link_coverage"] = round(sum(_cls(l) in link_cls or _cls(l) + "0" in link_cls for l in robot.links) / len(robot.links), 4)
    metrics["joint_coverage"] = round(sum(_cls(j) in joint_cls for j in robot.joints) / len(robot.joints), 4)
    asm = (gen / "Aloha_stationary.mo").read_text()
    metrics["connections"] = asm.count("connect(")
    metrics["mimic_enforced"] = "mimic" in asm.lower() and "multiplier" in asm.lower()
    placeholder = [l for l, v in robot.links.items() if v.is_placeholder]
    metrics["placeholder_links_given_mass"] = sum(1 for l in placeholder if l != "world")

    omc = OMCService(out_dir / "omc", msl_version="4.0.0")
    try:
        lr = omc.load_package(ws / "URDFModelica" / "package.mo")
        model = "URDFModelica.Examples.Aloha_stationary.Aloha_stationaryTest"
        chk = omc.check(model)
        metrics.update(load_ok=lr.ok, check_ok=chk.ok, equations=chk.data.get("equations"))
        flt = (r"time|aloha_stationaryRun\.aloha_stationary\.[A-Za-z0-9_]+\.(revolute\.phi|prismatic\.s|frame_a\.r_0\[.*|frame_a\.R\.T\[.*)")
        sim = omc.simulate(model, stop_time=stop_time, intervals=int(stop_time / 0.02), variable_filter=flt)
        metrics.update(simulate_ok=sim.ok, compile_seconds=sim.data.get("timeTotal"),
                       limit_assertions=sim.data.get("assert_warnings"))
        if sim.ok:
            res = MatResult(sim.data["resultFile"])
            links = [{"urdf": l, "r_vars": [f"{PREFIX}.{_cls(l)}.frame_a.r_0[{i}]".replace(_cls(l), _cls(l).lower()) for i in (1, 2, 3)],
                      "R_vars": [f"{PREFIX}.{_cls(l).lower()}.frame_a.R.T[{i},{j}]" for i in (1, 2, 3) for j in (1, 2, 3)]}
                     for l in robot.links if l != "world"]
            links = [l for l in links if res.has(l["r_vars"][0])]
            joints = []
            for jn, j in robot.joints.items():
                if j.movable:
                    v = f"{PREFIX}.{_cls(jn).lower()}.{'prismatic.s' if j.type == 'prismatic' else 'revolute.phi'}"
                    if res.has(v):
                        joints.append({"urdf": jn, "var": v})
            free = compare_frames(res, robot, links, joints, n_samples=15, apply_mimic=False)
            free.pop("per_link")
            metrics["kinematics"] = free
            urdf = compare_frames(res, robot, links, [x for x in joints if not robot.joints[x["urdf"]].mimic],
                                  n_samples=15, apply_mimic=True)
            metrics["kinematics_with_urdf_mimic_max_error_m"] = urdf["max_position_error_m"]
            # Out-of-limit motion and mimic behaviour of the converter's own test experiment
            viol = 0
            for jn, j in robot.joints.items():
                if j.type in ("revolute", "prismatic") and any(x["urdf"] == jn for x in joints):
                    q = res.get(next(x["var"] for x in joints if x["urdf"] == jn))
                    viol += int(q.min() < j.limit.lower - 1e-9 or q.max() > j.limit.upper + 1e-9)
            metrics["joints_outside_limits"] = viol
            lf = f"{PREFIX}.follower_right_left_finger.prismatic.s"
            rf = f"{PREFIX}.follower_right_right_finger.prismatic.s"
            if res.has(lf) and res.has(rf):
                metrics["mimic_max_error"] = float(np.max(np.abs(res.get(lf) + res.get(rf))))
    finally:
        omc.close()
    return _finish(metrics, out_dir, t0)


def _finish(metrics, out_dir, t0):
    metrics["time_to_first_executable_s"] = round(time.time() - t0, 1) if metrics.get("simulate_ok") else None
    metrics["success"] = bool(metrics.get("simulate_ok"))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=1))
    return metrics


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
