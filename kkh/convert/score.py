"""One scorer for every conversion mode. Every number comes from a real OpenModelica run (load, check, simulate,
.mat result) compared with the source URDF read by the independent kkh.engineering.urdf_model implementation.

Criteria (in ranking order):
  1 produced   a Modelica file exists (converter ran / the LLM returned code)
  2 loads      OpenModelica loadFile succeeds
  3 checks     checkModel succeeds; equations == variables is reported separately
  4 simulates  a 2 s simulation finishes
  5 coverage   URDF links and movable joints found in the simulated model (by name)
  6 kinematics URDF forward kinematics at the simulated joint angles vs simulated link frame positions
  7 parameters joint axes and link masses read from the result file vs the URDF
Names are matched leniently (case, '_' '/' '-', prefixes j_/l_/link_, URDFModelica title case); a match is a name
correspondence, not proof of correct wiring - the kinematic comparison is what tests the wiring.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import numpy as np

from kkh.engineering.omc import MatResult, OMCService
from kkh.engineering.urdf_model import load_urdf

STOP_TIME = 2.0
KIN_TOL_MM = 1.0       # kinematic agreement threshold for a "good" verdict
MASS_TOL = 0.01        # 1 % relative


NESTED = ("body", "revolute", "prismatic", "joint", "fixed", "frameTranslation", "bodyShape")


def norm(name: str) -> str:
    s = name.lower()
    s = re.sub(r"^(j|l|link|joint|body)_", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return re.sub(r"0$", "", s) if len(s) > 1 else s


def keys(urdf_name: str) -> list[str]:
    """Accepted model names for a URDF element: with its namespace (URDFModelica keeps it) or without."""
    return list(dict.fromkeys([norm(urdf_name.replace("/", "_")), norm(urdf_name.split("/")[-1])]))


def _instances(names: list[str], suffix: str) -> dict[str, tuple[str, bool]]:
    """Normalised instance name -> (variable ending with `suffix`, nested). Direct matches (`link.frame_a`) win over
    nested ones (`link.body.frame_a`, which can sit at the centre of mass rather than the link frame); then shortest."""
    out: dict[str, tuple[str, bool]] = {}
    for v in names:
        if not v.endswith(suffix):
            continue
        parts = v[: -len(suffix)].split(".")
        for depth, inst in enumerate(reversed(parts[-2:])):
            key, cand = norm(inst), (v, depth == 1)
            if key and (key not in out or (cand[1], len(v)) < (out[key][1], len(out[key][0]))):
                out[key] = cand
            if inst not in NESTED:
                break
    return out


def _find(table: dict, urdf_name: str):
    return next((table[k] for k in keys(urdf_name) if k in table), None)


def kinematic_match(res: MatResult, robot) -> dict:
    names = res.names
    frames = _instances(names, ".frame_a.r_0[1]")
    phis = {**_instances(names, ".phi"), **_instances(names, ".s")}
    urdf_links = [l for l in robot.links if l != "world"]  # 'world' is the environment, not a robot link
    found = {l: _find(frames, l) for l in urdf_links if _find(frames, l)}
    # kinematics only on link frames (nested body frames may be offset to the centre of mass)
    links = {l: v for l, (v, nested) in found.items() if not nested}
    movable = [j for j in robot.joints.values() if j.movable]
    joints = {j.name: _find(phis, j.name)[0] for j in movable if _find(phis, j.name)}
    out = {"links_total": len(urdf_links), "links_found": len(found), "joints_total": len(movable),
           "joints_found": len(joints), "missing_links": sorted(set(urdf_links) - set(found))[:20],
           "missing_joints": sorted({j.name for j in movable} - set(joints))[:20],
           "links_without_frame": sorted(set(found) - set(links))[:20]}
    out["coverage"] = round((len(found) + len(joints)) / max(1, len(urdf_links) + len(movable)), 4)
    if not links or not joints:
        out["kinematics"] = None
        return out
    root = robot.root
    idx = np.unique(np.linspace(0, len(res.time) - 1, 15).round().astype(int))
    worst, worst_at, errs = 0.0, None, []
    for k in idx:
        q = {j: float(res.get(v)[k]) for j, v in joints.items()}
        poses = robot.forward_kinematics(q, apply_mimic=True)
        base = np.array([res.get(links[root][:-3] + f"[{i}]")[k] for i in (1, 2, 3)]) if root in links else np.zeros(3)
        for l, var in links.items():
            p = np.array([res.get(var[:-3] + f"[{i}]")[k] for i in (1, 2, 3)]) - base
            e = float(np.linalg.norm(p - poses[l][:3, 3]))
            errs.append(e)
            if e > worst:
                worst, worst_at = e, (l, round(float(res.time[k]), 3))
    out["kinematics"] = {"max_position_error_mm": round(worst * 1000, 4), "mean_position_error_mm": round(float(np.mean(errs)) * 1000, 4),
                         "worst_link": worst_at, "samples": len(idx), "links_compared": len(links),
                         "reference": "URDF forward kinematics (kkh.engineering.urdf_model) at the simulated joint angles; positions relative to the root link",
                         "pass": worst * 1000 <= KIN_TOL_MM}
    # joint motion actually exercised (a model that never moves would pass trivially)
    out["kinematics"]["max_joint_motion_rad"] = round(max(float(np.ptp(res.get(v))) for v in joints.values()), 4)
    # parameters: joint axis vectors and link masses
    axes, masses = [], []
    for jn, var in joints.items():
        stem = var.rsplit(".", 1)[0]
        nv = [f"{stem}.n[{i}]" for i in (1, 2, 3)]
        if all(res.has(v) for v in nv):
            n = np.array([res.get(v)[0] for v in nv])
            ref = robot.joints[jn].axis
            axes.append({"joint": jn, "model": n.round(6).tolist(), "urdf": ref.round(6).tolist(),
                         "match": bool(np.allclose(n / (np.linalg.norm(n) or 1), ref / (np.linalg.norm(ref) or 1), atol=1e-6))})
    for l, (var, _) in found.items():
        stem = var.split(".frame_a")[0]
        mv = next((v for v in (f"{stem}.m", f"{stem}.body.m") if res.has(v)), None)
        link = robot.links[l]
        if mv and link.inertial:
            m = float(res.get(mv)[0])
            masses.append({"link": l, "model": m, "urdf": link.inertial.mass,
                           "match": abs(m - link.inertial.mass) <= MASS_TOL * max(link.inertial.mass, 1e-9)})
    out["parameters"] = {"axes_checked": len(axes), "axes_ok": sum(a["match"] for a in axes),
                         "masses_checked": len(masses), "masses_ok": sum(m["match"] for m in masses),
                         "axes": axes, "masses": masses}
    return out


def score(urdf: Path, package_file: Path | None, model: str | None, work: Path) -> dict:
    """Load, check and simulate `model` from `package_file`, then compare with the URDF."""
    s: dict = {"produced": bool(package_file and Path(package_file).exists() and model)}
    if not s["produced"]:
        return finish(s)
    robot = load_urdf(urdf)
    omc = OMCService(work / "omc")
    t = time.time()
    try:
        lr = omc.load_package(package_file)
        s["loads"] = lr.ok
        s["load_messages"] = lr.messages[-1500:]
        if not lr.ok:
            return finish(s)
        chk = omc.check(model)
        s["checks"] = chk.ok
        s["equations"], s["variables"] = chk.data.get("equations"), chk.data.get("variables")
        s["balanced"] = bool(chk.data) and chk.data.get("equations") == chk.data.get("variables")
        s["check_messages"] = chk.messages[-1500:]
        if not chk.ok:
            return finish(s)
        sim = omc.simulate(model, stop_time=STOP_TIME, intervals=100, timeout_s=120)
        s["simulates"] = sim.ok
        s["simulate_messages"] = sim.messages[-1500:]
        s["assertions"] = sim.data.get("assert_warnings")
        if sim.ok:
            s.update(kinematic_match(MatResult(sim.data["resultFile"]), robot))
    finally:
        s["omc_seconds"] = round(time.time() - t, 2)
        try:
            s["omc_version"] = omc.version()
        except Exception:
            pass
        omc.close()
    return finish(s)


def finish(s: dict) -> dict:
    kin = s.get("kinematics") or {}
    par = s.get("parameters") or {}
    s["criteria"] = [
        {"id": "produced", "ok": s.get("produced", False)},
        {"id": "loads", "ok": s.get("loads", False)},
        {"id": "checks", "ok": s.get("checks", False), "detail": f"{s.get('equations')} equations / {s.get('variables')} variables" if s.get("equations") is not None else None},
        {"id": "simulates", "ok": s.get("simulates", False)},
        {"id": "coverage", "ok": s.get("coverage", 0) >= 0.999 if "coverage" in s else False, "value": s.get("coverage"),
         "detail": f"{s.get('links_found')}/{s.get('links_total')} links, {s.get('joints_found')}/{s.get('joints_total')} moving joints" if "coverage" in s else None},
        {"id": "kinematics", "ok": bool(kin.get("pass")), "value": kin.get("max_position_error_mm"),
         "detail": f"max {kin['max_position_error_mm']} mm, mean {kin['mean_position_error_mm']} mm over {kin['links_compared']} links" if kin else None},
        {"id": "parameters", "ok": bool(par) and par["axes_ok"] == par["axes_checked"] and par["masses_ok"] == par["masses_checked"] and (par["axes_checked"] + par["masses_checked"]) > 0,
         "detail": f"axes {par['axes_ok']}/{par['axes_checked']}, masses {par['masses_ok']}/{par['masses_checked']}" if par else None},
    ]
    s["passed"] = sum(c["ok"] for c in s["criteria"])
    # lexicographic rank key: higher is better
    s["rank_key"] = [s["passed"] if not s.get("simulates") else 4 + s.get("coverage", 0),
                     -(kin.get("max_position_error_mm") if kin else 1e9),
                     (par.get("axes_ok", 0) + par.get("masses_ok", 0)) if par else 0]
    return s
