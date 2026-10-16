"""URDF-based leader control, bounded IK, explicit mapping and immutable trajectory processing."""
from __future__ import annotations
import hashlib
import json
from functools import lru_cache
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from scipy.signal import savgol_filter
from kkh.domain.aloha import configuration as C

JOINTS = C.ACTUATED
robot_for = lru_cache(maxsize=2)(C.arm_robot)
CONFIG_ID = "aloha2-urdf-" + hashlib.sha256((C.URDF_DIR / "aloha_wx250s.urdf").read_bytes() + (C.URDF_DIR / "aloha_vx300s.urdf").read_bytes()).hexdigest()[:16]


def description():
    models = C.build_manifest()["models"]
    return {"configuration_id": CONFIG_ID, "joint_ids": JOINTS,
            "units": ["rad"] * 7 + ["m"], "home": C.start_vector(),
            "leader": models["aloha_wx250s"], "follower": models["aloha_vx300s"],
            "mapping": {"rotational": "Match semantic joint names and local axis directions, then clamp to follower limits.",
                        "gripper": "Normalize left-finger travel between each URDF range; right finger follows its source mimic. Prop held at zero: motor/finger linkage unknown.",
                        "cartesian": "Different link geometry means joint correspondence does not imply Cartesian equivalence."},
            "display_layout": "Side-by-side offsets are presentation only; leader-to-follower hardware registration is unknown."}


def vector(values, model="aloha_wx250s", clamp=False):
    values = np.array(values, dtype=float, copy=True)
    if values.shape != (8,) or not np.all(np.isfinite(values)):
        raise ValueError("Expected eight finite joint values (seven radian coordinates and one metre coordinate)")
    robot = robot_for(model)
    for i, name in enumerate(JOINTS):
        limit = robot.joints[name].limit
        if limit and limit.lower is not None:
            if clamp:
                values[i] = np.clip(values[i], limit.lower, limit.upper)
            elif values[i] < limit.lower - 1e-10 or values[i] > limit.upper + 1e-10:
                raise ValueError(f"{name} exceeds source URDF limits")
    return values


def poses(values, model="aloha_wx250s"):
    values = vector(values, model)
    transforms = robot_for(model).forward_kinematics(dict(zip(JOINTS, values)))
    return {name: [*T[:3, 3].tolist(), *Rotation.from_matrix(T[:3, :3]).as_quat().tolist()] for name, T in transforms.items()}


def mapping(values):
    leader = vector(values)
    follower = leader.copy()
    left, right = robot_for("aloha_wx250s"), robot_for("aloha_vx300s")
    warnings = []
    for i, name in enumerate(JOINTS[:6]):
        sign = float(np.dot(left.joints[name].axis, right.joints[name].axis))
        if abs(abs(sign) - 1) > 1e-8:
            raise ValueError(f"Axis mapping for {name} requires a coordinate transform")
        follower[i] *= sign
        lim = right.joints[name].limit
        if lim.lower is not None:
            clipped = float(np.clip(follower[i], lim.lower, lim.upper))
            if abs(clipped - follower[i]) > 1e-9:
                warnings.append(f"{name}: clamped to follower URDF limit")
            follower[i] = clipped
    a, b = left.joints["left_finger"].limit, right.joints["left_finger"].limit
    follower[7] = b.lower + (leader[7] - a.lower) / (a.upper - a.lower) * (b.upper - b.lower)
    follower[6] = 0
    return {"q": follower.tolist(), "warnings": warnings, "mode": "kinematic replay"}


def inverse_kinematics(values, target):
    original = vector(values)
    target = np.asarray(target, dtype=float)
    if target.shape != (3,) or not np.all(np.isfinite(target)):
        raise ValueError("Target must be three finite metre coordinates")
    robot = robot_for("aloha_wx250s")
    lo = np.array([robot.joints[j].limit.lower for j in JOINTS[:6]])
    hi = np.array([robot.joints[j].limit.upper for j in JOINTS[:6]])
    def residual(q):
        transform = robot.forward_kinematics(dict(zip(JOINTS, [*q, *original[6:]])))["ee_gripper_link"]
        return np.r_[transform[:3, 3] - target, 0.002 * (q - original[:6])]
    solved = least_squares(residual, original[:6], bounds=(lo, hi), max_nfev=100, ftol=1e-8)
    error = float(np.linalg.norm(residual(solved.x)[:3]))
    if not solved.success or error > .005:
        return {"success": False, "q": original.tolist(), "error_m": error, "message": "Target unreachable within 5 mm tolerance; previous pose retained."}
    # Damped, bounded increments prevent a single drag event jumping across branches.
    step = np.clip(solved.x - original[:6], -.15, .15)
    output = original.copy(); output[:6] += step
    return {"success": True, "q": output.tolist(), "error_m": error, "message": "Bounded IK step; continue dragging to converge."}


def trajectory(data):
    if data.get("configuration_id") != CONFIG_ID or data.get("joint_ids") != JOINTS:
        raise ValueError("Trajectory robot identity or joint layout does not match this configuration")
    t, q = np.asarray(data["time"], dtype=float), np.asarray(data["q"], dtype=float)
    if (t.ndim != 1 or len(t) < 3 or len(t) > 30000 or q.shape != (len(t), 8)
            or not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0) or t[0] < 0 or t[-1] - t[0] > 600):
        raise ValueError("Use 3–30000 strictly ordered finite samples, at most 600 seconds")
    for row in q:
        vector(row)
    t = t - t[0]
    qd = np.gradient(q, t, axis=0, edge_order=2)
    qdd = np.gradient(qd, t, axis=0, edge_order=2)
    return {**data, "schema_version": 1, "time": t.tolist(), "q": q.tolist(), "qd": qd.tolist(), "qdd": qdd.tolist(),
            "units": ["rad"] * 7 + ["m"], "gripper": q[:, 7].tolist(),
            "derivatives": "numpy.gradient on nonuniform timestamps, second-order boundary differences; accelerations differentiate numerical velocities",
            "sample_sha256": hashlib.sha256(json.dumps([t.tolist(), q.tolist()]).encode()).hexdigest()}


def smooth(data, window=9):
    if window < 3 or window % 2 != 1 or window > len(data["time"]):
        raise ValueError("Smoothing window must be odd, at least 3 and no greater than the sample count")
    # First resample uniformly; Savitzky–Golay is not valid on nonuniform timestamps.
    t = np.linspace(data["time"][0], data["time"][-1], len(data["time"]))
    q = np.array([np.interp(t, data["time"], np.asarray(data["q"])[:, i]) for i in range(8)]).T
    q = savgol_filter(q, window, min(2, window-1), axis=0)
    q = np.array([vector(row, clamp=True) for row in q])
    return trajectory({**data, "time": t.tolist(), "q": q.tolist(), "processing": f"Uniform resampling + Savitzky–Golay window={window}, degree=2; source-limit clipping", "derived": True})
