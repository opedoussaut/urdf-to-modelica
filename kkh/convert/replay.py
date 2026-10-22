"""Replay of a scored simulation for the 3D view: where OpenModelica put each part of the converted model over time,
next to where the robot file says it must be (URDF forward kinematics at the same simulated joint angles).

Only stored OpenModelica results are read (the run made while scoring); nothing is simulated or estimated here.
Positions are relative to the root link, as in the geometry check (`score.kinematic_match`)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from kkh.engineering.omc import MatResult
from kkh.engineering.urdf_model import load_urdf

from . import runner, score, sources

FRAMES = 160  # samples sent to the browser (the scoring runs store 400 intervals over 4 s)


def result_file(run_id: str, mode: str) -> tuple[Path, str] | None:
    """The stored result of the method's scored run: the standard excitation if it ran, else the model's own run."""
    report = runner.load(run_id)
    r = report["modes"].get(mode)
    if not r or not r.get("score", {}).get("simulates"):
        return None
    if r.get("best_attempt"):
        omc = sources.ROOT / Path(r["main_file"]).parent / "omc"
    else:
        omc = sources.RUNS / run_id / runner.safe_dir(mode) / "omc"
    ex = omc / "KkhExcite_res.mat"
    if ex.exists() and (r["score"].get("excitation") or {}).get("used"):
        return ex, "standard excitation (every joint through 80 % of its range)"
    own = sorted(p for p in omc.glob("*_res.mat") if p.name != "KkhExcite_res.mat")
    return (own[0], "the model's own test motion") if own else None


def build(run_id: str, mode: str) -> dict:
    report = runner.load(run_id)
    found = result_file(run_id, mode)
    if found is None:
        raise ValueError("This method's model did not simulate, so there is nothing to replay")
    mat, motion = found
    urdf, _ = sources.resolve(report["source"]["id"])
    robot = load_urdf(urdf)
    res = MatResult(mat)
    names = res.names
    frames = score._instances(names, ".frame_a.r_0[1]")
    phis = {**score._instances(names, ".phi"), **score._instances(names, ".s")}
    links = {}
    for l in robot.links:
        hit = score._find(frames, l)
        if hit and not hit[1]:
            links[l] = hit[0]
    joints = {j.name: score._find(phis, j.name)[0] for j in robot.joints.values() if j.movable and score._find(phis, j.name)}
    idx = np.unique(np.linspace(0, len(res.time) - 1, FRAMES).round().astype(int))
    root = robot.root
    out_links = {l: {"model": [], "urdf": []} for l in robot.links if l != "world"}
    q_out = {j: [] for j in joints}
    for k in idx:
        q = {j: float(res.get(v)[k]) for j, v in joints.items()}
        for j in joints:
            q_out[j].append(round(q[j], 5))
        poses = robot.forward_kinematics(q, apply_mimic=True)
        base = np.array([res.get(links[root][:-3] + f"[{i}]")[k] for i in (1, 2, 3)]) if root in links else np.zeros(3)
        for l, o in out_links.items():
            T = poses.get(l)
            o["urdf"].append([round(float(x), 5) for x in (*T[:3, 3], *T[:3, :3].ravel())] if T is not None else None)
            var = links.get(l)
            if var is None:
                o["model"].append(None)
                continue
            p = np.array([res.get(var[:-3] + f"[{i}]")[k] for i in (1, 2, 3)]) - base
            Rt = score._rot(res, var.split(".r_0")[0], k)
            R = Rt.T if Rt is not None else None  # MSL stores world->frame; the browser needs frame->world
            o["model"].append([round(float(x), 5) for x in (*p, *(R.ravel() if R is not None else [np.nan] * 9))])
    for o in out_links.values():  # NaN is not JSON: orientation unknown -> None per frame
        o["model"] = [None if m is None else (m[:3] + [None] * 9 if any(x != x for x in m[3:]) else m) for m in o["model"]]
    missing = sorted(l for l, o in out_links.items() if all(m is None for m in o["model"]))
    kin = report["modes"][mode]["score"].get("kinematics") or {}
    return {"run": run_id, "mode": mode, "source": report["source"]["id"], "label": report["source"].get("label"),
            "motion": motion, "result_file": mat.name, "times": [round(float(res.time[k]), 4) for k in idx],
            "links": out_links, "joints": q_out, "missing_links": missing, "tolerance_mm": score.KIN_TOL_MM,
            "max_position_error_mm": kin.get("max_position_error_mm")}
