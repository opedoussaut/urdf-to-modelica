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
from kkh.engineering.urdf_model import load_urdf, rpy_to_matrix

from .dynamics import TOL_PCT_EFFORT

STOP_TIME = 2.0
KIN_TOL_MM = 1.0       # kinematic agreement threshold for a "good" verdict
ROT_TOL_DEG = 0.1      # orientation agreement threshold
PARAM_FAMILIES = ("axes", "masses", "com", "inertia")
PARAM_LABEL = {"axes": "axes", "masses": "masses", "com": "centres of mass", "inertia": "inertias"}
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
    out["joint_vars"] = joints
    if not links or not joints:
        out["kinematics"] = None
        return out
    root = robot.root
    idx = np.unique(np.linspace(0, len(res.time) - 1, 15).round().astype(int))
    worst, worst_at, errs = 0.0, None, []
    per_link: dict[str, float] = {}
    rot_worst, rot_checked, per_link_rot = 0.0, set(), {}
    for k in idx:
        q = {j: float(res.get(v)[k]) for j, v in joints.items()}
        poses = robot.forward_kinematics(q, apply_mimic=True)
        base = np.array([res.get(links[root][:-3] + f"[{i}]")[k] for i in (1, 2, 3)]) if root in links else np.zeros(3)
        for l, var in links.items():
            p = np.array([res.get(var[:-3] + f"[{i}]")[k] for i in (1, 2, 3)]) - base
            e = float(np.linalg.norm(p - poses[l][:3, 3]))
            errs.append(e)
            per_link[l] = max(per_link.get(l, 0.0), e)
            if e > worst:
                worst, worst_at = e, (l, round(float(res.time[k]), 3))
            Rt = _rot(res, var.split(".r_0")[0], k)  # orientation of the link frame (world→frame)
            if Rt is not None:
                rot_checked.add(l)
                c = (np.trace(Rt @ poses[l][:3, :3]) - 1) / 2  # angle between model frame (Rt.T) and URDF frame
                ang = float(np.degrees(np.arccos(np.clip(c, -1, 1))))
                rot_worst = max(rot_worst, ang)
                per_link_rot[l] = max(per_link_rot.get(l, 0.0), ang)
    out["kinematics"] = {"max_position_error_mm": round(worst * 1000, 4), "mean_position_error_mm": round(float(np.mean(errs)) * 1000, 4),
                         "worst_link": worst_at, "samples": len(idx), "links_compared": len(links),
                         "reference": "URDF forward kinematics (kkh.engineering.urdf_model) at the simulated joint angles; positions relative to the root link",
                         "pass": worst * 1000 <= KIN_TOL_MM and rot_worst <= ROT_TOL_DEG,
                         "max_orientation_error_deg": round(rot_worst, 4) if rot_checked else None,
                         "orientation_links_compared": len(rot_checked)}
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
    out["parameters"].update(inertial_checks(res, robot, found, joints))
    out["structure"] = localise(robot, out["kinematics"], per_link, per_link_rot)
    return out


def _vec(res: MatResult, stem: str, k: int) -> np.ndarray | None:
    names = [f"{stem}[{i}]" for i in (1, 2, 3)]
    return np.array([res.get(v)[k] for v in names]) if all(res.has(v) for v in names) else None


def _rot(res: MatResult, frame: str, k: int) -> np.ndarray | None:
    """World→frame rotation R.T of an MSL frame (`<frame>.R.T[i,j]`) at sample k, or None."""
    names = [f"{frame}.R.T[{i},{j}]" for i in (1, 2, 3) for j in (1, 2, 3)]
    return np.array([res.get(v)[k] for v in names]).reshape(3, 3) if all(res.has(v) for v in names) else None


def inertial_checks(res: MatResult, robot, found: dict, joints: dict) -> dict:
    """Centre of mass and inertia tensor of each matched body, compared in WORLD coordinates at the first sample, so
    the result does not depend on how the file nests its frames. Reference: URDF FK at the simulated joint angles plus
    the URDF <inertial> origin. Bodies whose orientation is not in the result file are 'not checkable'."""
    k = 0
    q = {j: float(res.get(v)[k]) for j, v in joints.items()}
    poses = robot.forward_kinematics(q, apply_mimic=True)
    root = robot.root
    com, inertia, unchecked = [], [], []
    for l, (var, _) in found.items():
        link = robot.links[l]
        if not link.inertial or link.is_placeholder:
            continue
        stem = var.split(".frame_a")[0]
        body = next((b for b in (f"{stem}.body", stem) if res.has(f"{b}.m")), None)
        if not body:
            unchecked.append(l)
            continue
        r0, R = _vec(res, f"{body}.frame_a.r_0", k), _rot(res, f"{body}.frame_a", k)
        rcm = _vec(res, f"{body}.r_CM", k)
        if r0 is None or R is None or rcm is None:
            unchecked.append(l)
            continue
        p_world = r0 + R.T @ rcm  # R.T maps world→frame, so frame→world is its transpose
        I_world = None
        Iv = [f"{body}.I_{a}" for a in ("11", "22", "33", "21", "31", "32")]
        if all(res.has(v) for v in Iv):
            i11, i22, i33, i21, i31, i32 = (float(res.get(v)[k]) for v in Iv)
            I_world = R.T @ np.array([[i11, i21, i31], [i21, i22, i32], [i31, i32, i33]]) @ R
        R_in = rpy_to_matrix(link.inertial.origin.rpy)
        I_ref_link = R_in @ link.inertial.inertia @ R_in.T
        frame_r0, frame_R = None, None
        if not found[l][1]:  # the link's own frame is in the result: compare in the link frame (geometry-independent)
            lf = var.split(".r_0")[0]
            frame_r0, frame_R = _vec(res, f"{lf}.r_0", k), _rot(res, lf, k)
        if frame_r0 is not None and frame_R is not None:
            com_local = frame_R @ (p_world - frame_r0)
            e = float(np.linalg.norm(com_local - link.inertial.origin.xyz))
            I_cmp, I_ref, basis = (frame_R @ I_world @ frame_R.T if I_world is not None else None), I_ref_link, "link frame"
        else:  # only the body is exposed: compare in world coordinates via URDF FK (depends on correct geometry)
            T_link = poses[l]
            p_ref = T_link[:3, :3] @ link.inertial.origin.xyz + T_link[:3, 3]
            root_var = found.get(root)
            offset = _vec(res, root_var[0].split(".frame_a")[0] + ".frame_a.r_0", k) if root_var else None
            e = float(np.linalg.norm(p_world - (offset if offset is not None else 0) + poses[root][:3, 3] - p_ref))
            I_cmp, I_ref, basis = I_world, T_link[:3, :3] @ I_ref_link @ T_link[:3, :3].T, "world (via URDF FK)"
        com.append({"link": l, "error_mm": round(e * 1000, 4), "match": e <= 1e-3, "basis": basis})
        if I_cmp is not None:
            scale = max(float(np.abs(I_ref).max()), 1e-12)
            rel = float(np.abs(I_cmp - I_ref).max()) / scale
            inertia.append({"link": l, "max_rel_error": round(rel, 6), "match": rel <= 0.01, "basis": basis})
    return {"com_checked": len(com), "com_ok": sum(c["match"] for c in com), "com": com,
            "inertia_checked": len(inertia), "inertia_ok": sum(c["match"] for c in inertia), "inertia": inertia,
            "inertial_not_checkable": sorted(unchecked)[:20],
            "limits": "not checkable from the result file (MSL joints carry no limits); compared in the source only"}


def localise(robot, kin: dict | None, per_link: dict, per_link_rot: dict | None = None) -> dict:
    """Which joint is most likely wrong: for each misplaced link, the joint above the FIRST misplaced link on its
    chain from the root (errors propagate down the chain, so only the first one points at a cause)."""
    if not kin:
        return {"misplaced_links": [], "suspect_joints": []}
    tol = KIN_TOL_MM / 1000
    bad = {l for l, e in per_link.items() if e > tol} | {l for l, a in (per_link_rot or {}).items() if a > ROT_TOL_DEG}
    suspects = []
    for l in sorted(bad):
        chain, cur = [], l
        while (j := robot.parent_joint(cur)) is not None:
            chain.append(j)
            cur = j.parent
        first = next((j for j in reversed(chain) if j.child in bad), None)
        if first and first.name not in suspects:
            suspects.append(first.name)
    return {"misplaced_links": sorted(bad), "suspect_joints": suspects}


def _excite(omc, robot, urdf: Path, model: str, package_file: Path, work: Path) -> tuple[dict, MatResult | None]:
    """Standard excitation run (kkh.convert.excite); returns (info, result) - result None when not applicable/failed."""
    from . import excite
    main = Path(package_file)
    if model.startswith("URDFModelica.Examples."):
        pkg = model.split(".")[2]
        main = Path(package_file).parent / "Examples" / pkg / f"{pkg}.mo"
    built = excite.build(robot, model, main, work)
    if built is None:
        return {"used": False, "reason": "no excitation wrapper applies to this file (joints not found as direct components)"}, None
    wrapper, driven = built
    info = {"used": False, "driven_joints": len(driven), "stop_time_s": excite.STOP_TIME, "signals": driven}
    lr = omc.load_package(wrapper)
    chk = omc.check(excite.NAME) if lr.ok else None
    if not lr.ok or not chk.ok:
        info["reason"] = "excitation wrapper rejected by OpenModelica: " + ((chk.messages if chk else lr.messages) or "")[-600:]
        return info, None
    sim = omc.simulate(excite.NAME, stop_time=excite.STOP_TIME, intervals=400, timeout_s=180)
    if not sim.ok:
        info["reason"] = "excitation run failed: " + (sim.messages or "")[-600:]
        return info, None
    info["used"] = True
    return info, MatResult(sim.data["resultFile"])


GATES = ("produced", "loads", "checks", "simulates")


def live_checks(s: dict, decided: set[str], running: str | None = None) -> list[dict]:
    """The 8 checks as the page shows them while scoring: pass / fail for decided ones, running, waiting, or
    not reached (an earlier gate failed)."""
    out, blocked = [], False
    for c in finish(dict(s))["criteria"]:
        if c["id"] in decided:
            state = "pass" if c["ok"] else "fail"
        elif blocked:
            state = "skipped"
        else:
            state = "running" if c["id"] == running else "pending"
        out.append({"id": c["id"], "state": state, "detail": c.get("detail") if c["id"] in decided else None})
        blocked = blocked or (c["id"] in GATES and state == "fail")
    return out


def score(urdf: Path, package_file: Path | None, model: str | None, work: Path, on_step=None) -> dict:
    """Load, check and simulate `model` from `package_file`, then compare with the URDF. When possible, a standard
    excitation (every joint through most of its range) replaces the model's own motion for the geometry and
    dynamics checks; otherwise the model's own motion is used and flagged. on_step(checks, activity) reports progress live."""
    s: dict = {"produced": bool(package_file and Path(package_file).exists() and model)}
    decided: set[str] = {"produced"}

    def step(running: str | None, activity: str, *ids: str):
        decided.update(ids)
        if on_step:
            on_step(live_checks(s, decided, running), activity)

    if not s["produced"]:
        step(None, "No model file to test")
        return finish(s)
    step("loads", "OpenModelica is reading the file")
    robot = load_urdf(urdf)
    omc = OMCService(work / "omc")
    t = time.time()
    try:
        lr = omc.load_package(package_file)
        s["loads"] = lr.ok
        s["load_messages"] = lr.messages[-1500:]
        if not lr.ok:
            step(None, "OpenModelica could not read the file", "loads")
            return finish(s)
        step("checks", "OpenModelica is counting equations and unknowns", "loads")
        chk = omc.check(model)
        s["checks"] = chk.ok
        s["equations"], s["variables"] = chk.data.get("equations"), chk.data.get("variables")
        s["balanced"] = bool(chk.data) and chk.data.get("equations") == chk.data.get("variables")
        s["check_messages"] = chk.messages[-1500:]
        if not chk.ok:
            step(None, "OpenModelica rejected the model as incomplete", "checks")
            return finish(s)
        step("simulates", f"OpenModelica is simulating {STOP_TIME:g} s", "checks")
        sim = omc.simulate(model, stop_time=STOP_TIME, intervals=100, timeout_s=120)
        s["simulates"] = sim.ok
        s["simulate_messages"] = sim.messages[-1500:]
        s["assertions"] = sim.data.get("assert_warnings")
        if sim.ok:
            from . import dynamics
            res = MatResult(sim.data["resultFile"])
            s.update(kinematic_match(res, robot))
            s["motion"] = "the model's own test motion"
            step("kinematics", "Moving every joint through 80 % of its range (OpenModelica), then comparing each part with the robot file",
                 "simulates", "coverage")
            info, res_ex = _excite(omc, robot, urdf, model, package_file, work)
            s["excitation"] = info
            if res_ex is not None:
                s.update(kinematic_match(res_ex, robot))
                s["motion"] = "standard excitation (every joint through 80 % of its range)"
                res = res_ex
            step("dynamics", "Computing the reference torques with MuJoCo and comparing joint by joint",
                 "kinematics", "parameters")
            try:
                s["dynamics"] = dynamics.compare(res, robot, urdf, s.get("joint_vars") or {})
            except Exception as exc:  # the reference could not be built for this URDF: say so, never guess
                s["dynamics"] = {"checked": False, "reason": f"{type(exc).__name__}: {exc}"[:300]}
            step(None, "All checks done", "dynamics")
        else:
            step(None, "The simulation failed", "simulates")
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
    dyn = s.get("dynamics") or {}
    s["criteria"] = [
        {"id": "produced", "ok": s.get("produced", False)},
        {"id": "loads", "ok": s.get("loads", False)},
        {"id": "checks", "ok": s.get("checks", False), "detail": f"{s.get('equations')} equations / {s.get('variables')} variables" if s.get("equations") is not None else None},
        {"id": "simulates", "ok": s.get("simulates", False)},
        {"id": "coverage", "ok": s.get("coverage", 0) >= 0.999 if "coverage" in s else False, "value": s.get("coverage"),
         "detail": f"{s.get('links_found')}/{s.get('links_total')} links, {s.get('joints_found')}/{s.get('joints_total')} moving joints" if "coverage" in s else None},
        {"id": "kinematics", "ok": bool(kin.get("pass")), "value": kin.get("max_position_error_mm"),
         "detail": (f"max {kin['max_position_error_mm']} mm, mean {kin['mean_position_error_mm']} mm over {kin['links_compared']} links"
                    + (f"; orientation max {kin['max_orientation_error_deg']}°" if kin.get("max_orientation_error_deg") is not None else "")
                    + (f"; suspect joint(s): {', '.join(x.split('/')[-1] for x in (s.get('structure') or {}).get('suspect_joints', []))}"
                       if (s.get("structure") or {}).get("suspect_joints") else "")) if kin else None},
        {"id": "parameters", "ok": bool(par) and all(par.get(f + "_ok", 0) == par.get(f + "_checked", 0) for f in PARAM_FAMILIES)
                                and sum(par.get(f + "_checked", 0) for f in PARAM_FAMILIES) > 0,
         "detail": ", ".join(f"{PARAM_LABEL[f]} {par.get(f + '_ok', 0)}/{par.get(f + '_checked', 0)}" for f in PARAM_FAMILIES if f + "_checked" in par) if par else None},
        {"id": "dynamics", "ok": bool(dyn.get("checked")) and dyn.get("joints_checked", 0) > 0 and dyn["joints_ok"] == dyn["joints_checked"],
         "value": dyn.get("worst_pct_effort"),
         "detail": (f"{dyn['joints_ok']}/{dyn['joints_checked']} joints within {TOL_PCT_EFFORT:g}% of their effort limit (worst {dyn['worst_pct_effort']}%)"
                    if dyn.get("checked") else dyn.get("reason"))},
    ]
    s["passed"] = sum(c["ok"] for c in s["criteria"])
    # lexicographic rank key: higher is better
    s["rank_key"] = [s["passed"] if not s.get("simulates") else 4 + s.get("coverage", 0),
                     -(kin.get("max_position_error_mm") if kin else 1e9),
                     sum(par.get(f + "_ok", 0) for f in PARAM_FAMILIES) if par else 0,
                     -(dyn.get("worst_pct_effort") or 1e9) if dyn.get("checked") else -1e9]
    return s
