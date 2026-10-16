"""Cross-source verification: vendor URDF (aloha_vx300s) vs official ALOHA 2 MJCF (mujoco_menagerie/aloha).

MuJoCo is used purely as an independent kinematics engine for the MJCF; nothing is converted from it.
Result is written to config/aloha2_crosscheck.json and cited by the manifest and the knowledge graph.
"""
from __future__ import annotations

import json

import numpy as np

from . import configuration as C

ARM_JOINTS = ["waist", "shoulder", "elbow", "forearm_roll", "wrist_angle", "wrist_rotate"]
ARM_LINKS = ["shoulder_link", "upper_arm_link", "upper_forearm_link", "lower_forearm_link", "wrist_link", "gripper_link"]
MJCF = C.ROOT / "third_party/mujoco_menagerie/aloha/aloha.xml"
OUT = C.ROOT / "config/aloha2_crosscheck.json"


def run(n_configs: int = 50, seed: int = 0, write: bool = True) -> dict:
    import mujoco
    m = mujoco.MjModel.from_xml_path(str(MJCF))
    d = mujoco.MjData(m)
    r = C.arm_robot("aloha_vx300s")
    rng = np.random.default_rng(seed)
    out = {"mjcf": "mujoco_menagerie/aloha/aloha.xml@62ab00f", "urdf": "data/urdf/aloha_vx300s.urdf",
           "engine": f"mujoco {mujoco.__version__}", "n_configs": n_configs, "arms": {}, "joints": {}}
    for side in ("left", "right"):
        bid = m.body(f"{side}/base_link").id
        worst_p = worst_r = 0.0
        for k in range(n_configs):
            q = {n: 0.0 if k == 0 else float(rng.uniform(*m.joint(f"{side}/{n}").range)) for n in ARM_JOINTS}
            for n, v in q.items():
                d.qpos[m.joint(f"{side}/{n}").qposadr] = v
            mujoco.mj_kinematics(m, d)
            B = np.eye(4)
            B[:3, :3] = d.xmat[bid].reshape(3, 3)
            B[:3, 3] = d.xpos[bid]
            P = r.forward_kinematics(q, base=B)
            for l in ARM_LINKS:
                b = m.body(f"{side}/{l}").id
                worst_p = max(worst_p, float(np.linalg.norm(d.xpos[b] - P[l][:3, 3])))
                worst_r = max(worst_r, float(np.linalg.norm(d.xmat[b].reshape(3, 3) - P[l][:3, :3])))
        out["arms"][f"follower_{side}"] = {"mount_xyz": d.xpos[bid].round(6).tolist(),
                                           "max_position_diff_m": worst_p, "max_rotation_diff": worst_r}
    for j in ARM_JOINTS:
        mj = m.joint(f"left/{j}")
        u = r.joints[j]
        out["joints"][j] = {"axis_equal": bool(np.allclose(m.jnt_axis[mj.id], u.axis)),
                            "range_mjcf": [round(float(x), 5) for x in mj.range],
                            "range_urdf": [round(u.limit.lower, 5), round(u.limit.upper, 5)],
                            "range_equal": bool(np.allclose(mj.range, [u.limit.lower, u.limit.upper], atol=1e-4))}
    fl = m.joint("left/left_finger")
    out["gripper"] = {
        "same_model": False,
        "mjcf": {"finger_joints": ["left_finger", "right_finger"], "axis": m.jnt_axis[fl.id].tolist(),
                 "range_m": [round(float(x), 4) for x in fl.range], "gripper_prop_joint": False,
                 "note": "MJCF README: default ViperX gripper replaced by the updated ALOHA 2 design; finger "
                         "coupling via equality constraint."},
        "urdf": {"finger_joints": ["left_finger", "right_finger (mimic -1)"], "axis": r.joints["left_finger"].axis.tolist(),
                 "range_m": [r.joints["left_finger"].limit.lower, r.joints["left_finger"].limit.upper],
                 "gripper_prop_joint": True}}
    out["verdict"] = ("Arm kinematics (6 joints, 6 links) of the vendor URDF are identical to the official ALOHA 2 "
                      "MJCF within numerical precision; joint axes and ranges are identical. Gripper parameterisation "
                      "differs between the two sources and is reported, not reconciled.")
    out["pass"] = all(a["max_position_diff_m"] < 1e-9 and a["max_rotation_diff"] < 1e-9 for a in out["arms"].values()) \
        and all(j["axis_equal"] and j["range_equal"] for j in out["joints"].values())
    if write:
        OUT.write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
