"""Prescribed-motion experiments for the ALOHA assembly (joint-space waypoints, 32 driven inputs).

Input vector layout: for arm in configuration.ARMS: ACTUATED (8 values) -> 4 x 8 = 32.
All waypoints are checked against URDF limits before generation (see `check_limits`).
"""
from __future__ import annotations

import numpy as np

from .configuration import ACTUATED, ARMS, GRIPPER_POSITION, arm_robot, start_vector

N_PER_ARM = len(ACTUATED)


def _start() -> np.ndarray:
    return np.concatenate([start_vector(a) for a in ARMS])


def _set(v: np.ndarray, arm_id: str, values: dict) -> np.ndarray:
    v = v.copy()
    k = [a["id"] for a in ARMS].index(arm_id)
    for name, val in values.items():
        v[k * N_PER_ARM + ACTUATED.index(name)] = val
    return v


def _clamp_finger(model: str, x: float) -> float:
    lim = arm_robot(model).joints["left_finger"].limit
    return float(min(max(x, lim.lower), lim.upper))


REACH = {"waist": 0.6, "shoulder": -0.3, "elbow": 0.5, "forearm_roll": 0.5, "wrist_angle": 0.9, "wrist_rotate": -0.6}


def scenarios() -> dict[str, dict]:
    s0 = _start()
    f_open = _clamp_finger("aloha_vx300s", GRIPPER_POSITION["follower"]["open"])
    f_close = _clamp_finger("aloha_vx300s", GRIPPER_POSITION["follower"]["close"])
    l_open = _clamp_finger("aloha_wx250s", GRIPPER_POSITION["leader"]["open"])
    l_close = _clamp_finger("aloha_wx250s", GRIPPER_POSITION["leader"]["close"])

    reach = _set(s0, "follower_right", REACH)
    out = {}
    out["HoldStartPose"] = {
        "title": "Hold start pose",
        "description": "All four arms hold the documented ALOHA START_ARM_POSE. Static check of the assembly.",
        "t": [0.0, 2.0], "Q": [s0, s0], "stop_time": 2.0}

    out["FollowerRightReach"] = {
        "title": "Right follower reach and grasp",
        "description": ("Right follower arm moves smoothly from START_ARM_POSE to a reach pose, opens the gripper "
                        "(URDF upper finger limit), closes it to the documented ALOHA close position and returns. "
                        "The other three arms hold the start pose."),
        "t": [0.0, 1.0, 3.5, 4.5, 5.5, 8.0, 9.0],
        "Q": [s0, s0, reach,
              _set(reach, "follower_right", {"left_finger": f_open}),
              _set(reach, "follower_right", {"left_finger": f_close}),
              s0, s0],
        "stop_time": 9.0}

    # Teleoperation-style mirror: in ALOHA, followers track leader joint angles one-to-one; gripper fingers are
    # mapped with LEADER2FOLLOWER_POSITION_FN (normalise on leader range, unnormalise on follower range).
    def tele(values, lf):
        v = s0.copy()
        frac = (lf - GRIPPER_POSITION["leader"]["close"]) / (GRIPPER_POSITION["leader"]["open"] - GRIPPER_POSITION["leader"]["close"])
        ff = _clamp_finger("aloha_vx300s", GRIPPER_POSITION["follower"]["close"] + frac * (
            GRIPPER_POSITION["follower"]["open"] - GRIPPER_POSITION["follower"]["close"]))
        for side, sign in (("left", 1.0), ("right", -1.0)):
            vals = dict(values)
            vals["waist"] = sign * values["waist"]
            vals["forearm_roll"] = sign * values["forearm_roll"]
            vals["wrist_rotate"] = sign * values["wrist_rotate"]
            v = _set(v, f"leader_{side}", {**vals, "left_finger": lf})
            v = _set(v, f"follower_{side}", {**vals, "left_finger": ff})
        return v

    lift = {"waist": 0.4, "shoulder": -0.5, "elbow": 0.6, "forearm_roll": 0.3, "wrist_angle": 0.6, "wrist_rotate": 0.5}
    s_l = tele({k: s0[ACTUATED.index(k)] for k in REACH}, l_close)
    out["TeleopMirror"] = {
        "title": "Bimanual teleoperation mirror",
        "description": ("Both leaders move symmetrically; each follower reproduces its leader's joint angles "
                        "(ALOHA joint-space teleoperation) and its gripper follows the documented "
                        "leader-to-follower gripper mapping. All 32 driven joints move."),
        "t": [0.0, 1.0, 3.5, 4.5, 5.5, 8.0, 9.0],
        "Q": [s0, s_l, tele(lift, l_close), tele(lift, l_open), tele(lift, l_close), s_l, s0],
        "stop_time": 9.0}
    for v in out.values():
        v["Q"] = np.array(v["Q"]).tolist()
    return out


def check_limits(sc: dict) -> list[str]:
    """Return violations of URDF position limits and velocity limits for every waypoint segment."""
    errs = []
    Q = np.array(sc["Q"])
    t = np.array(sc["t"])
    for k, arm in enumerate(ARMS):
        r = arm_robot(arm["model"])
        for i, jn in enumerate(ACTUATED):
            j = r.joints[jn]
            col = Q[:, k * N_PER_ARM + i]
            lim = j.limit
            if lim and lim.lower is not None and (col.min() < lim.lower - 1e-12 or col.max() > lim.upper + 1e-12):
                errs.append(f"{arm['id']}.{jn}: position outside [{lim.lower}, {lim.upper}]")
            if lim and lim.velocity:
                for s in range(len(t) - 1):
                    vmax = abs(col[s + 1] - col[s]) * np.pi / (2 * (t[s + 1] - t[s]))
                    if vmax > lim.velocity:
                        errs.append(f"{arm['id']}.{jn}: peak velocity {vmax:.3f} > {lim.velocity}")
    return errs
