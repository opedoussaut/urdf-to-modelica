"""ALOHA 2 binding for task scenarios: leader joint recordings -> follower end-effector + gripper opening.

The follower executes the leader's joint angles through the explicit joint-name mapping (kkh.studio.robotics.mapping);
its end-effector position comes from the follower URDF forward kinematics in the follower base frame.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

from kkh.studio import robotics as R

FOLLOWER = "aloha_vx300s"
LEADER = "aloha_wx250s"


def opening(q_leader) -> float:
    """Normalised leader finger opening: 0 = fully closed, 1 = fully open (URDF left_finger range)."""
    lim = R.robot_for(LEADER).joints["left_finger"].limit
    return float((q_leader[7] - lim.lower) / (lim.upper - lim.lower))


def signals(q_rows) -> tuple[np.ndarray, np.ndarray]:
    """(ee[n,3] in follower base frame, opening[n]) for recorded leader joint rows."""
    robot = R.robot_for(FOLLOWER)
    ee, op = [], []
    for row in q_rows:
        fq = R.mapping(row)["q"]
        ee.append(robot.forward_kinematics(dict(zip(R.JOINTS, fq)))["ee_gripper_link"][:3, 3])
        op.append(opening(row))
    return np.array(ee), np.array(op)


def follower_ik(q_leader, target, gripper_down: bool = True) -> dict:
    """Leader joint command that places the follower end effector at `target` (follower base frame, metres).

    Solved on the follower URDF within the intersection of leader and follower joint limits; since every mapped
    axis has sign +1, the same joint values are a valid leader command. Bounded step for smooth motion."""
    q0 = R.vector(q_leader)
    target = np.asarray(target, float)
    if target.shape != (3,) or not np.all(np.isfinite(target)):
        raise ValueError("Target must be three finite metre coordinates")
    lead, foll = R.robot_for(LEADER), R.robot_for(FOLLOWER)
    names = R.JOINTS[:6]
    lo = np.array([max(lead.joints[j].limit.lower, foll.joints[j].limit.lower) for j in names])
    hi = np.array([min(lead.joints[j].limit.upper, foll.joints[j].limit.upper) for j in names])
    start = np.clip(R.mapping(q0)["q"][:6], lo, hi)
    tail = R.mapping(q0)["q"][6:]

    def residual(q):
        T = foll.forward_kinematics(dict(zip(R.JOINTS, [*q, *tail])))["ee_gripper_link"]
        down = (1 - T[:3, 0] @ np.array([0.0, 0.0, -1.0])) * 0.05 if gripper_down else 0.0
        return np.r_[T[:3, 3] - target, down, 0.002 * (q - start)]

    solved = least_squares(residual, start, bounds=(lo, hi), max_nfev=200, ftol=1e-9)
    T = foll.forward_kinematics(dict(zip(R.JOINTS, [*solved.x, *tail])))["ee_gripper_link"]
    error = float(np.linalg.norm(T[:3, 3] - target))
    if error > 0.005:
        return {"success": False, "q": q0.tolist(), "error_m": error,
                "message": "Target outside the shared reachable workspace (5 mm tolerance); pose unchanged."}
    out = q0.copy()
    out[:6] = solved.x
    return {"success": True, "q": out.tolist(), "error_m": error, "ee_m": T[:3, 3].round(5).tolist(),
            "message": "Follower end effector placed by IK (shared leader/follower limits, gripper pointing down)."}
