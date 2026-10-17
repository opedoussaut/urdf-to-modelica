"""Retarget a leader demonstration to a follower attempt through the shared display world (Step 5).

For every recorded leader sample: leader URDF FK -> gripper pose in the leader base -> display world (layout
transform) -> follower base -> follower URDF IK, warm-started from the previous sample so the joint path stays
continuous. Constrained: gripper position in the world and the tilt of the gripper approach axis from the vertical
(e.g. pointing down for a grasp). Not constrained: rotation about the vertical. The arms face each other, so copying
the leader's full world orientation would make the follower point back at its own base; the grasp orientation about
the vertical stays an open gate. The finger opening is transferred as the normalised opening.

Output is a follower-joint-space recording (`reference_space: "follower_joints"`) that the OpenModelica follower model
can track directly. Every sample carries its IK residual; samples outside the follower workspace are solved
best-effort and reported, never hidden. The layout is an experimental display transform (no hardware registration),
there is no collision checking and no grasp/contact model: a retargeted attempt is a kinematic reference, not a
validated robot program.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares

from kkh.engineering import workspace_frames as W
from kkh.studio import robotics as R

LEADER, FOLLOWER = "aloha_wx250s", "aloha_vx300s"
POSITION_TOLERANCE_M = 0.005
TILT_TOLERANCE_DEG = 5.0
TILT_WEIGHT = 0.1  # metres per unit of vertical-component error of the gripper approach axis


def _finger_limits(model: str):
    lim = R.robot_for(model).joints["left_finger"].limit
    return lim.lower, lim.upper


def leader_opening(q_leader) -> float:
    lo, hi = _finger_limits(LEADER)
    return float((q_leader[7] - lo) / (hi - lo))


def follower_finger(opening: float) -> float:
    lo, hi = _finger_limits(FOLLOWER)
    return float(lo + np.clip(opening, 0.0, 1.0) * (hi - lo))


def _target_in_follower(lay: dict, T_leader: np.ndarray) -> np.ndarray:
    """Leader-base gripper pose -> follower-base target pose via the display world."""
    return np.linalg.inv(W.base_matrix(lay, "follower")) @ W.base_matrix(lay, "leader") @ T_leader


def retarget(data: dict, layout_name: str) -> dict:
    """Follower-joint recording + per-sample report for a leader recording `data` (validated trajectory data)."""
    if data.get("reference_space", "leader_joints") != "leader_joints":
        raise ValueError("Only leader recordings can be retargeted")
    lay = W.layout(layout_name)
    lead, foll = R.robot_for(LEADER), R.robot_for(FOLLOWER)
    names = R.JOINTS[:6]
    lo = np.array([foll.joints[n].limit.lower for n in names])
    hi = np.array([foll.joints[n].limit.upper for n in names])
    vmax = np.array([foll.joints[n].limit.velocity or np.inf for n in names])
    time = np.asarray(data["time"], float)

    def fk(q6):
        return foll.forward_kinematics(dict(zip(R.JOINTS, [*q6, 0.0, 0.0])))["ee_gripper_link"]

    rows, pos_err, rot_err = [], [], []
    previous = None
    for row in data["q"]:
        T_target = _target_in_follower(lay, lead.forward_kinematics(dict(zip(R.JOINTS, R.vector(row))))["ee_gripper_link"])
        p_t, R_t = T_target[:3, 3], T_target[:3, :3]

        tilt_t = R_t[2, 0]  # vertical component of the target approach axis (-1 = pointing straight down)

        def residual(q6, ref=previous):
            T = fk(q6)
            r = np.r_[T[:3, 3] - p_t, TILT_WEIGHT * (T[2, 0] - tilt_t), 2e-3 * q6[[3, 5]]]  # wrist roll/rotate centred
            if ref is not None:
                r = np.r_[r, 2e-3 * (q6 - ref)]  # continuity: prefer the branch of the previous sample
            return r

        seeds = [previous] if previous is not None else [
            np.clip([math.atan2(p_t[1], p_t[0]), s, e, 0.0, w, 0.0], lo + 1e-6, hi - 1e-6)
            for s, e, w in ((0.0, 0.0, 1.2), (-0.5, 0.8, 1.0), (0.3, -0.3, 1.4))]
        best = None
        for seed in seeds:
            sol = least_squares(residual, seed, bounds=(lo, hi), max_nfev=60 if previous is not None else 400,
                                xtol=1e-10, ftol=1e-10)
            if best is None or sol.cost < best.cost:
                best = sol
        q6 = best.x
        T = fk(q6)
        pos_err.append(float(np.linalg.norm(T[:3, 3] - p_t)))
        rot_err.append(abs(math.degrees(math.asin(np.clip(T[2, 0], -1, 1)) - math.asin(np.clip(tilt_t, -1, 1)))))
        rows.append([*q6.tolist(), 0.0, follower_finger(leader_opening(row))])
        previous = q6

    q = np.array(rows)
    qd = np.gradient(q[:, :6], time, axis=0, edge_order=2) if len(time) > 2 else np.zeros((len(time), 6))
    pos_err, rot_err = np.array(pos_err), np.array(rot_err)
    within = (pos_err <= POSITION_TOLERANCE_M) & (rot_err <= TILT_TOLERANCE_DEG)
    leader_qd = np.gradient(np.asarray(data["q"], float)[:, :6], time, axis=0, edge_order=2) if len(time) > 2 else qd
    over_speed = {n: int(np.sum(np.abs(qd[:, i]) > vmax[i])) for i, n in enumerate(names) if np.isfinite(vmax[i])}
    report = {
        "method": "per-sample follower URDF IK on the leader gripper position mapped through the display world plus "
                  "the tilt of the gripper approach axis from the vertical; rotation about the vertical free; "
                  "warm-started from the previous sample; follower joint limits",
        "layout": layout_name, "layout_status": lay["status"],
        "samples": len(rows),
        "within_tolerance_fraction": round(float(within.mean()), 4),
        "tolerance": {"position_m": POSITION_TOLERANCE_M, "approach_tilt_deg": TILT_TOLERANCE_DEG},
        "position_error_m": {"max": round(float(pos_err.max()), 5), "rms": round(float(np.sqrt((pos_err ** 2).mean())), 5)},
        "approach_tilt_error_deg": {"max": round(float(rot_err.max()), 3), "rms": round(float(np.sqrt((rot_err ** 2).mean())), 3)},
        "outside_tolerance_intervals_s": _intervals(time, ~within),
        "velocity_limit_samples": over_speed,
        "max_joint_speed_rad_s": {n: round(float(np.abs(qd[:, i]).max()), 4) for i, n in enumerate(names)},
        "leader_max_joint_speed_rad_s": {n: round(float(np.abs(leader_qd[:, i]).max()), 4) for i, n in enumerate(names)},
        "checked": {"position_ik": True, "approach_tilt_ik": True, "grasp_orientation_about_vertical": False,
                    "joint_limits": True,
                    "velocity_limits": True, "collision": False, "contact": False, "hardware_registration": False},
    }
    out = {k: v for k, v in data.items() if k not in {"q", "qd", "qdd", "gripper", "sample_sha256", "units",
                                                    "derivatives", "schema_version"}}
    out.update({
        "q": q.tolist(),
        "reference_space": "follower_joints",
        "provenance": "Retargeted follower attempt (kinematic): derived from a leader demonstration by world-frame IK; "
                      "experimental display layout, no collision or contact model",
        "derived": {"kind": "retargeted_follower_attempt", "report": report},
    })
    return {"data": out, "report": report, "position_error_m": pos_err.tolist(), "approach_tilt_error_deg": rot_err.tolist()}


def _intervals(time: np.ndarray, mask: np.ndarray) -> list[list[float]]:
    out, start = [], None
    for t, m in zip(time, mask):
        if m and start is None:
            start = t
        if not m and start is not None:
            out.append([round(float(start), 3), round(float(t), 3)])
            start = None
    if start is not None:
        out.append([round(float(start), 3), round(float(time[-1]), 3)])
    return out[:50]
