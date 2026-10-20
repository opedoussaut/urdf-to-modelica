"""Dynamic fidelity: the joint torques a model needs for its motion vs an independent reference.

Reference: MuJoCo (already installed) loaded from the cleaned URDF (visuals/collisions removed), rigid body only:
joint damping, friction and armature are set to zero and constraints (limits, mimic equalities) disabled on the reference, and the model torque is read where it is the
rigid-body joint torque (MSL Revolute/Prismatic `tau` / `f`, i.e. the axis torque; URDFModelica measures it after its
friction element). Gravity: URDF/ROS convention, 9.81 m/s² along -z.

At sampled instants of the simulation we read q, q̇, q̈ of every matched joint and compute
tau_ref = MuJoCo inverse dynamics(q, q̇, q̈). Joints whose torque the model does not expose count as applying 0
(a free joint), so a model that accelerates wrongly also shows up as a torque error. Mimic joints are reported apart
(MuJoCo's URDF import does not enforce mimic constraints).
"""
from __future__ import annotations

import re

import numpy as np

from .sources import prompt_text

TOL_PCT_EFFORT = 5.0  # pass threshold: RMS torque error ≤ 5 % of the URDF effort limit


def reference_model(urdf_path):
    """MuJoCo model of the URDF (names sanitised: '/' and '-' → '_') and a URDF-name → MuJoCo-joint-index map."""
    import mujoco
    xml = prompt_text(urdf_path)
    xml = re.sub(r'((?:name|link|joint)=")([^"]*)"', lambda m: m.group(1) + re.sub(r"[/\-]", "_", m.group(2)) + '"', xml)
    m = mujoco.MjModel.from_xml_string(xml)
    m.dof_damping[:] = 0
    m.dof_frictionloss[:] = 0
    m.dof_armature[:] = 0
    m.opt.gravity[:] = (0, 0, -9.81)
    # pure rigid-body reference: no joint-limit, equality (MuJoCo turns URDF <mimic> into one) or contact forces
    m.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_CONSTRAINT)
    index = {}
    for i in range(m.njnt):
        index[m.joint(i).name] = int(m.jnt_dofadr[i])
    return m, index


def compare(res, robot, urdf_path, joint_vars: dict, n_samples: int = 40) -> dict:
    """joint_vars: URDF joint name → result variable of its coordinate (…phi / …s)."""
    import mujoco
    m, index = reference_model(urdf_path)
    d = mujoco.MjData(m)
    # result variables per joint: q, qd, qdd, tau
    cols = {}
    for jn, qv in joint_vars.items():
        stem, coord = qv.rsplit(".", 1)
        names = ({"phi": ("w", "a", "tau"), "s": ("v", "a", "f")}).get(coord)
        if not names:
            continue
        vd, va, vt = (f"{stem}.{n}" for n in names)
        if not (res.has(vd) and res.has(va)):
            continue
        mj = re.sub(r"[/\-]", "_", jn)
        if mj not in index:
            continue
        cols[jn] = (qv, vd, va, vt if res.has(vt) else None, index[mj])
    if not cols:
        return {"checked": False, "reason": "joint velocities/accelerations not found in the result file"}
    t = res.time
    idx = np.unique(np.linspace(int(0.05 * len(t)), len(t) - 1, n_samples).round().astype(int))  # skip start transient
    err = {jn: [] for jn in cols}
    tau_model_all = {jn: [] for jn in cols}
    for k in idx:
        d.qpos[:] = 0
        d.qvel[:] = 0
        d.qacc[:] = 0
        for jn, (qv, vd, va, vt, dof) in cols.items():
            d.qpos[m.jnt_qposadr[m.dof_jntid[dof]]] = res.get(qv)[k]
            d.qvel[dof] = res.get(vd)[k]
            d.qacc[dof] = res.get(va)[k]
        mujoco.mj_inverse(m, d)
        for jn, (qv, vd, va, vt, dof) in cols.items():
            tau_m = float(res.get(vt)[k]) if vt else 0.0
            tau_model_all[jn].append(tau_m)
            err[jn].append(tau_m - float(d.qfrc_inverse[dof]))
    rows = []
    for jn, e in err.items():
        j = robot.joints[jn]
        e = np.array(e)
        effort = j.limit.effort if j.limit is not None and j.limit.effort else None
        rms, mx = float(np.sqrt(np.mean(e ** 2))), float(np.max(np.abs(e)))
        pct = round(100 * rms / effort, 2) if effort else None
        rows.append({"joint": jn, "rms_nm": round(rms, 5), "max_nm": round(mx, 5), "effort_limit": effort,
                     "rms_pct_effort": pct, "torque_exposed": cols[jn][3] is not None, "mimic": bool(j.mimic),
                     "match": (pct is not None and pct <= TOL_PCT_EFFORT) if not j.mimic else True})
    main = [r for r in rows if not r["mimic"]]
    return {"checked": True, "samples": len(idx), "joints": rows,
            "joints_checked": len(main), "joints_ok": sum(r["match"] for r in main),
            "worst_pct_effort": max((r["rms_pct_effort"] or 0) for r in main) if main else None,
            "reference": "MuJoCo inverse dynamics from the URDF, rigid body (no damping, friction, armature), gravity -z",
            "tolerance": f"RMS error ≤ {TOL_PCT_EFFORT}% of the URDF effort limit per joint; mimic joints reported apart"}


def self_check(urdf_path, seed: int = 0) -> float:
    """Reference sanity check: forward dynamics then inverse dynamics on the MuJoCo model returns the applied torque.
    Returns the max absolute difference (N·m); should be ~1e-9."""
    import mujoco
    m, _ = reference_model(urdf_path)
    d = mujoco.MjData(m)
    rng = np.random.default_rng(seed)
    d.qpos[:] = rng.uniform(-0.5, 0.5, m.nq) * 0.1
    d.qvel[:] = rng.uniform(-0.5, 0.5, m.nv)
    tau = rng.uniform(-1, 1, m.nv)
    d.qfrc_applied[:] = tau
    mujoco.mj_forward(m, d)
    qacc = d.qacc.copy()
    d.qfrc_applied[:] = 0
    d.qacc[:] = qacc
    mujoco.mj_inverse(m, d)
    return float(np.max(np.abs(d.qfrc_inverse - tau)))
