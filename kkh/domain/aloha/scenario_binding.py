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


def _to_scenario_frame(ee: np.ndarray, role: str, scenario: dict | None) -> np.ndarray:
    """Base-frame end-effector points -> the scenario's frame.

    Legacy scenarios are expressed in the follower base frame (only role "follower" is meaningful there). Scenarios
    with a `frame.layout` are expressed in the studio display world of that layout (experimental display transform)."""
    layout_name = (scenario or {}).get("frame", {}).get("layout")
    if not layout_name:
        if role != "follower":
            raise ValueError("Legacy scenario is in the follower base frame; a leader point cannot be used there")
        return ee
    from kkh.engineering import workspace_frames as W
    lay = W.layout(layout_name)
    T = W.base_matrix(lay, role)
    return ee @ T[:3, :3].T + T[:3, 3]


def signals(q_rows, scenario: dict | None = None, role: str | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(ee[n,3], opening[n]) for recorded leader joint rows, in the scenario frame.

    role "follower" (legacy default): follower executing the joint-mapped leader rows. role "leader": the leader's own
    end effector (demonstration on a shared-table layout)."""
    role = role or (scenario or {}).get("manipulator", {}).get("role", "follower")
    ee, op = [], []
    if role == "leader":
        robot = R.robot_for(LEADER)
        for row in q_rows:
            ee.append(robot.forward_kinematics(dict(zip(R.JOINTS, R.vector(row))))["ee_gripper_link"][:3, 3])
            op.append(opening(row))
    elif role == "follower":
        robot = R.robot_for(FOLLOWER)
        for row in q_rows:
            fq = R.mapping(row)["q"]
            ee.append(robot.forward_kinematics(dict(zip(R.JOINTS, fq)))["ee_gripper_link"][:3, 3])
            op.append(opening(row))
    else:
        raise ValueError(f"Unknown manipulator role {role!r}")
    return _to_scenario_frame(np.array(ee), role, scenario), np.array(op)


def follower_opening(q_follower) -> float:
    lim = R.robot_for(FOLLOWER).joints["left_finger"].limit
    return float((q_follower[7] - lim.lower) / (lim.upper - lim.lower))


def follower_signals(q_follower_rows, scenario: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(ee[n,3], opening[n]) for a FOLLOWER-joint recording (e.g. a retargeted attempt), in the scenario frame."""
    robot = R.robot_for(FOLLOWER)
    ee = np.array([robot.forward_kinematics(dict(zip(R.JOINTS, R.vector(row, FOLLOWER))))["ee_gripper_link"][:3, 3]
                   for row in q_follower_rows])
    return _to_scenario_frame(ee, "follower", scenario), np.array([follower_opening(r) for r in q_follower_rows])


def simulated_signals(q_follower_rows, time, recorded_time, recorded_q,
                      scenario: dict | None = None, reference_space: str = "leader_joints") -> tuple[np.ndarray, np.ndarray]:
    """(ee[n,3], opening[n]) for a SIMULATED follower response (follower joint rows from OpenModelica).

    The gripper is not torque-driven in the follower model, so its opening is the recorded leader command
    interpolated at the simulation time points."""
    robot = R.robot_for(FOLLOWER)
    ee = np.array([robot.forward_kinematics(dict(zip(R.JOINTS, row)))["ee_gripper_link"][:3, 3] for row in q_follower_rows])
    commanded = np.array([follower_opening(row) if reference_space == "follower_joints" else opening(row)
                          for row in recorded_q])
    return _to_scenario_frame(ee, "follower", scenario), np.interp(np.asarray(time, float), np.asarray(recorded_time, float), commanded)


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
