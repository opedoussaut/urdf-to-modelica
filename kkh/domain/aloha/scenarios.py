"""Prescribed-motion experiments (joint-space waypoints).

target "assembly": input layout = for arm in ARMS: ACTUATED (8) -> 16 values.
target "leader":   standalone leader arm, 8 values.
Every waypoint is checked against URDF position and velocity limits before generation.
"""
from __future__ import annotations

import numpy as np

from .configuration import ACTUATED, ARMS, GRIPPER_POSITION, LEADER, arm_robot, start_vector

N = len(ACTUATED)
REACH = {"waist": 0.6, "shoulder": -0.3, "elbow": 0.5, "forearm_roll": 0.5, "wrist_angle": 0.9, "wrist_rotate": -0.6}


def _set(v, k: int, values: dict):
    v = np.array(v, dtype=float)
    for name, val in values.items():
        v[k * N + ACTUATED.index(name)] = val
    return v


def _clamp_finger(model: str, x: float) -> float:
    lim = arm_robot(model).joints["left_finger"].limit
    return float(min(max(x, lim.lower), lim.upper))


def scenarios() -> dict[str, dict]:
    s0 = np.concatenate([start_vector() for _ in ARMS])
    f_open = _clamp_finger("aloha_vx300s", GRIPPER_POSITION["follower"]["open"])
    f_close = _clamp_finger("aloha_vx300s", GRIPPER_POSITION["follower"]["close"])
    right = [a["id"] for a in ARMS].index("follower_right")
    reach = _set(s0, right, REACH)
    out = {
        "HoldStartPose": {
            "target": "assembly", "title": "Hold start pose",
            "description": "Both ALOHA 2 follower arms hold the documented START_ARM_POSE (static assembly check).",
            "t": [0.0, 2.0], "Q": [s0, s0], "stop_time": 2.0},
        "RightArmReach": {
            "target": "assembly", "title": "Right arm reach and grasp",
            "description": ("The right follower arm moves smoothly from START_ARM_POSE to a reach pose, opens the "
                            "gripper to the URDF finger limit, closes it to the documented ALOHA close position and "
                            "returns. The left arm holds the start pose."),
            "t": [0.0, 1.0, 3.5, 4.5, 5.5, 8.0, 9.0],
            "Q": [s0, s0, reach, _set(reach, right, {"left_finger": f_open}),
                  _set(reach, right, {"left_finger": f_close}), s0, s0],
            "stop_time": 9.0},
    }
    l0 = np.array(start_vector())
    l_open = _clamp_finger("aloha_wx250s", GRIPPER_POSITION["leader"]["open"])
    lift = _set(l0, 0, {"waist": -0.5, "shoulder": -0.4, "elbow": 0.4, "wrist_angle": 0.7})
    out["LeaderArmCheck"] = {
        "target": "leader", "title": "Leader arm check (standalone)",
        "description": "Standalone leader WidowX-250 arm: move from START_ARM_POSE, open the handle gripper, return.",
        "t": [0.0, 0.5, 2.5, 3.5, 5.5], "Q": [l0, l0, lift, _set(lift, 0, {"left_finger": l_open}), l0],
        "stop_time": 6.0}
    for v in out.values():
        v["Q"] = np.array(v["Q"]).tolist()
    return out


def arms_for(sc: dict) -> list[dict]:
    return ARMS if sc["target"] == "assembly" else [LEADER]


def check_limits(sc: dict) -> list[str]:
    errs = []
    Q, t = np.array(sc["Q"]), np.array(sc["t"])
    for k, arm in enumerate(arms_for(sc)):
        r = arm_robot(arm["model"])
        for i, jn in enumerate(ACTUATED):
            col, lim = Q[:, k * N + i], r.joints[jn].limit
            if lim and lim.lower is not None and (col.min() < lim.lower - 1e-12 or col.max() > lim.upper + 1e-12):
                errs.append(f"{arm['id']}.{jn}: position outside [{lim.lower}, {lim.upper}]")
            if lim and lim.velocity:
                for s in range(len(t) - 1):
                    vmax = abs(col[s + 1] - col[s]) * np.pi / (2 * (t[s + 1] - t[s]))
                    if vmax > lim.velocity:
                        errs.append(f"{arm['id']}.{jn}: peak velocity {vmax:.3f} > {lim.velocity}")
    return errs
