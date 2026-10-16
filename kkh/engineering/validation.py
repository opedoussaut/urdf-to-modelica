"""Independent kinematic validation of simulated Modelica link frames against reference URDF FK.

The reference (kkh.engineering.urdf_model.Robot.forward_kinematics) is a separate numpy
implementation of URDF conventions and reads the URDF directly; it shares no code with the
Modelica generator. Inputs: the simulated joint coordinates (from the result file); outputs:
per-link position / orientation errors at sampled time instants.
"""
from __future__ import annotations

import numpy as np

from .omc import MatResult
from .urdf_model import Robot

TOL_POS_M = 1e-6       # 1 micrometre
TOL_ROT = 1e-6         # Frobenius norm of R_model - R_ref


def compare_frames(res: MatResult, robot: Robot, links: list[dict], joints: list[dict],
                   n_samples: int = 25, apply_mimic: bool = True) -> dict:
    """links: [{urdf, r_vars[3], R_vars[9]}], joints: [{urdf, var}].

    apply_mimic=True: mimic joints are computed from their masters (checks the model honours URDF mimic);
    False: pass simulated mimic-joint coordinates in `joints` to check pure frame kinematics."""
    t = res.time
    idx = np.unique(np.linspace(0, len(t) - 1, n_samples).round().astype(int))
    worst_p, worst_r, worst = 0.0, 0.0, None
    per_link = {l["urdf"]: [0.0, 0.0] for l in links}
    for k in idx:
        q = {j["urdf"]: float(res.get(j["var"])[k]) for j in joints}
        poses = robot.forward_kinematics(q, apply_mimic=apply_mimic)
        for l in links:
            T = poses[l["urdf"]]
            p = np.array([res.get(v)[k] for v in l["r_vars"]])
            Rt = np.array([res.get(v)[k] for v in l["R_vars"]]).reshape(3, 3)  # MSL R.T: world -> frame
            ep = float(np.linalg.norm(p - T[:3, 3]))
            er = float(np.linalg.norm(Rt.T - T[:3, :3]))
            per_link[l["urdf"]][0] = max(per_link[l["urdf"]][0], ep)
            per_link[l["urdf"]][1] = max(per_link[l["urdf"]][1], er)
            if ep > worst_p:
                worst_p, worst = ep, (l["urdf"], float(t[k]))
            worst_r = max(worst_r, er)
    return {"samples": len(idx), "links_checked": len(links), "max_position_error_m": worst_p,
            "max_rotation_error": worst_r, "worst": worst, "tol_position_m": TOL_POS_M, "tol_rotation": TOL_ROT,
            "pass": worst_p <= TOL_POS_M and worst_r <= TOL_ROT,
            "per_link": {k: {"pos": v[0], "rot": v[1]} for k, v in per_link.items()}}


def compare_trajectory(res: MatResult, var: str, t_wp, q_wp, tol: float = 1e-9) -> float:
    """Max |simulated - reference cosine blend| for one joint coordinate (independent numpy evaluation)."""
    t_wp, q_wp = np.asarray(t_wp, float), np.asarray(q_wp, float)
    ref = np.empty_like(res.time)
    for i, t in enumerate(res.time):
        if t <= t_wp[0]:
            ref[i] = q_wp[0]
        elif t >= t_wp[-1]:
            ref[i] = q_wp[-1]
        else:
            k = np.searchsorted(t_wp, t, side="right") - 1
            s = (t - t_wp[k]) / (t_wp[k + 1] - t_wp[k])
            ref[i] = q_wp[k] + (q_wp[k + 1] - q_wp[k]) * (1 - np.cos(np.pi * s)) / 2
    return float(np.max(np.abs(res.get(var) - ref)))
