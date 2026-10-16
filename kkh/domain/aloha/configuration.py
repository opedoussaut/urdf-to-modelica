"""ALOHA 2 domain knowledge: selected public configuration, sourced constants, configuration manifest.

Every constant carries a source reference and an evidence status:
  verified   copied from a pinned public source
  derived    computed deterministically from verified values (rule documented)
  assumption chosen by this project, explicitly flagged
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from kkh.engineering.urdf_model import load_urdf

ROOT = Path(__file__).resolve().parents[3]
URDF_DIR = ROOT / "data" / "urdf"
ASSEMBLY_URDF = URDF_DIR / "aloha2_bimanual.urdf"

SRC = {
    "site": "https://aloha-2.github.io/",
    "descriptions": "Interbotix/interbotix_ros_manipulators@b66d5b9 (humble) interbotix_xsarm_descriptions",
    "mjcf": "google-deepmind/mujoco_menagerie@62ab00f aloha/aloha.xml",
    "constants": "Interbotix/aloha@4fa6b2c aloha/constants.py",
    "spec_follower": "https://docs.trossenrobotics.com/interbotix_xsarms_docs/specifications/avx300s.html",
    "spec_leader": "https://docs.trossenrobotics.com/interbotix_xsarms_docs/specifications/awx250s.html",
}

VARIANT = {
    "id": "aloha2",
    "name": "ALOHA 2 (bimanual follower robot)",
    "rationale": (
        "aloha-2.github.io links (a) the ALOHA 2 hardware repo (CAD/STL only, no URDF), (b) the official MuJoCo "
        "model (mujoco_menagerie/aloha, MJCF, two follower ViperX-300 arms) and (c) the Trossen Robotics ALOHA kits "
        "as the commercial ALOHA 2 hardware. The only public ALOHA 2 URDF is the Trossen/Interbotix "
        "aloha_vx300s / aloha_wx250s description; its arm kinematics were cross-verified against the official "
        "MJCF (config/aloha2_crosscheck.json). Original ALOHA (tonyzhaozh/aloha v1) specifications are not used. "
        "Kyoto University's exact hardware is unconfirmed."),
    "sources": SRC,
}

# The ALOHA 2 robot assembly (as defined by the official ALOHA 2 simulation): two follower arms.
ARMS = [
    {"id": "follower_left", "modelica": "left", "model": "aloha_vx300s", "role": "follower", "side": "left",
     "mount_xyz": [-0.469, -0.019, 0.02], "mount_rpy": [0.0, 0.0, 0.0]},
    {"id": "follower_right", "modelica": "right", "model": "aloha_vx300s", "role": "follower", "side": "right",
     "mount_xyz": [0.469, -0.019, 0.02], "mount_rpy": [0.0, 0.0, math.pi]},
]
MOUNT_SOURCE = SRC["mjcf"] + " (left/base_link, right/base_link body poses)"
# Leader (teleoperation) arm: modelled and validated standalone; no ALOHA 2 source gives its pose in the robot frame.
LEADER = {"id": "leader", "modelica": "leader", "model": "aloha_wx250s", "role": "leader"}

ARM_CLASS = {"aloha_vx300s": "AlohaVX300s", "aloha_wx250s": "AlohaWX250s"}
ARM_PRODUCT = {"aloha_vx300s": "ALOHA ViperX-300 6DOF (follower)", "aloha_wx250s": "ALOHA WidowX-250 6DOF (leader)"}

# Official servo configuration (Trossen spec pages, retrieved 2026-10-16; snapshots in data/sources/)
ACTUATORS = {
    "aloha_vx300s": {
        "waist": ["XM540-W270"], "shoulder": ["XM540-W270", "XM540-W270"], "elbow": ["XM540-W270", "XM540-W270"],
        "forearm_roll": ["XM540-W270"], "wrist_angle": ["XM540-W270"], "wrist_rotate": ["XM430-W350"],
        "gripper": ["XM430-W350"]},
    "aloha_wx250s": {
        "waist": ["XM430-W350"], "shoulder": ["XM430-W350", "XM430-W350"], "elbow": ["XM430-W350", "XM430-W350"],
        "forearm_roll": ["XM430-W350"], "wrist_angle": ["XM430-W350"], "wrist_rotate": ["XM430-W350"],
        "gripper": ["XC430-W150"]},
}
SERVO_IDS = {"waist": [1], "shoulder": [2, 3], "elbow": [4, 5], "forearm_roll": [6], "wrist_angle": [7],
             "wrist_rotate": [8], "gripper": [9]}
SPEC_LIMITS = {
    "aloha_vx300s": {"waist": (-180, 180), "shoulder": (-101, 101), "elbow": (-101, 92), "wrist_angle": (-107, 130),
                     "forearm_roll": (-180, 180), "wrist_rotate": (-180, 180), "gripper_mm": (42, 116)},
    "aloha_wx250s": {"waist": (-180, 180), "shoulder": (-108, 114), "elbow": (-123, 92), "forearm_roll": (-180, 180),
                     "wrist_angle": (-100, 123), "wrist_rotate": (-180, 180), "gripper_mm": (30, 74)},
}

# Interbotix/aloha aloha/constants.py
START_ARM_POSE = [0.0, -0.96, 1.16, 0.0, -0.3, 0.0]
START_FINGER = 0.02239
GRIPPER_POSITION = {"leader": {"open": 0.0323, "close": 0.0185}, "follower": {"open": 0.0579, "close": 0.0440}}
ACTUATED = ["waist", "shoulder", "elbow", "forearm_roll", "wrist_angle", "wrist_rotate", "gripper", "left_finger"]

JOINT_FUNCTION = {
    "waist": "Base yaw: rotates the whole arm about the vertical axis.",
    "shoulder": "Shoulder pitch: lifts the upper arm (dual servo).",
    "elbow": "Elbow pitch: folds the forearm relative to the upper arm (dual servo).",
    "forearm_roll": "Forearm roll: rotates the wrist assembly about the forearm axis.",
    "wrist_angle": "Wrist pitch: tilts the gripper.",
    "wrist_rotate": "Wrist roll: rotates the gripper about its approach axis.",
    "gripper": "Gripper servo shaft (prop). URDF does not couple it to finger motion.",
    "left_finger": "Left finger translation (independently driven).",
    "right_finger": "Right finger translation; URDF mimic of left_finger with multiplier -1.",
}


def arm_robot(model: str):
    return load_urdf(URDF_DIR / f"{model}.urdf", strip_prefix=f"{model}/")


def start_vector() -> list[float]:
    """Start pose of one arm in ACTUATED order. Gripper prop joint: 0 rad (assumption, see manifest)."""
    return START_ARM_POSE + [0.0, START_FINGER]


def _arm_record(model: str) -> dict:
    r = arm_robot(model)
    rep = r.validate_structure()
    joints = []
    for j in r.joints.values():
        lim = j.limit
        joints.append({
            "name": j.name, "type": j.type, "parent": j.parent, "child": j.child,
            "axis": j.axis.tolist() if j.movable else None,
            "origin_xyz": j.origin.xyz.tolist(), "origin_rpy": j.origin.rpy.tolist(),
            "limit": None if lim is None else {"lower": lim.lower, "upper": lim.upper,
                                                "effort": lim.effort, "velocity": lim.velocity},
            "mimic": list(j.mimic) if j.mimic else None,
            "actuators": ACTUATORS[model].get(j.name),
            "servo_ids": SERVO_IDS.get(j.name) if j.name in ACTUATORS[model] else None,
            "function": JOINT_FUNCTION.get(j.name),
        })
    return {"model": model, "product": ARM_PRODUCT[model], "urdf": f"data/urdf/{model}.urdf",
            "n_links": rep["n_links"], "n_joints": rep["n_joints"], "joint_types": rep["joint_types"],
            "driven_joints": [j.name for j in r.actuated_joints()],
            "mimic_joints": [j.name for j in r.joints.values() if j.mimic], "joints": joints,
            "links": [{"name": x["link"], "inertial_status": x["status"], "mass": x.get("mass"),
                       "mesh": next((v.mesh for v in r.links[x["link"]].visuals if v.mesh), None)}
                      for x in r.validate_inertials()]}


def discrepancies() -> list[dict]:
    out = []
    for model in ARM_CLASS:
        r = arm_robot(model)
        for jn, (lo, hi) in SPEC_LIMITS[model].items():
            if jn == "gripper_mm":
                f = r.joints["left_finger"].limit
                u = (round(2000 * f.lower, 1), round(2000 * f.upper, 1))
                if u != (lo, hi):
                    out.append({"model": model, "item": "gripper opening (2 x left_finger)", "urdf": u, "spec": (lo, hi),
                                "unit": "mm", "source": SRC["spec_follower" if model == "aloha_vx300s" else "spec_leader"]})
                continue
            l = r.joints[jn].limit
            u = (round(math.degrees(l.lower)), round(math.degrees(l.upper)))
            if u != (lo, hi):
                out.append({"model": model, "item": f"{jn} limit", "urdf": u, "spec": (lo, hi), "unit": "deg",
                            "source": SRC["spec_follower" if model == "aloha_vx300s" else "spec_leader"]})
    fl = arm_robot("aloha_vx300s").joints["left_finger"].limit
    if GRIPPER_POSITION["follower"]["open"] > fl.upper:
        out.append({"model": "aloha_vx300s", "item": "FOLLOWER_GRIPPER_POSITION_OPEN", "urdf": fl.upper,
                    "spec": GRIPPER_POSITION["follower"]["open"], "unit": "m", "source": SRC["constants"],
                    "resolution": "trajectories clamp to the URDF limit"})
    out.append({"model": "aloha_vx300s", "item": "spec page servo-ID tables", "source": SRC["spec_follower"],
                "detail": "Joint-limit table lists Wrist Angle ID 6 / Forearm Roll ID 7; servo table lists "
                          "6 forearm_roll / 7 wrist_angle. URDF order matches the servo table."})
    out.append({"model": "aloha_vx300s", "item": "gripper model URDF vs ALOHA 2 MJCF", "source": SRC["mjcf"],
                "detail": "MJCF uses the updated ALOHA 2 gripper (finger axis 0 0 -1, range 0-0.041 m, no prop joint); "
                          "URDF uses finger axis 0 1 0, range 0.021-0.057 m and a continuous prop joint."})
    return out


def build_manifest() -> dict:
    follower = _arm_record("aloha_vx300s")
    leader = _arm_record("aloha_wx250s")
    n = len(ARMS)
    totals = {"links": 1 + n * follower["n_links"], "joints": n * (follower["n_joints"] + 1),
              "driven": n * len(follower["driven_joints"]), "mimic": n * len(follower["mimic_joints"])}
    xc_path = ROOT / "config/aloha2_crosscheck.json"
    xc = json.loads(xc_path.read_text()) if xc_path.exists() else None
    return {
        "variant": VARIANT,
        "complete_robot_definition": (
            "ALOHA 2 robot = two follower ALOHA ViperX-300 6DOF arms with every URDF link and joint (incl. gripper "
            "prop, fingers and finger mimic) mounted at the official ALOHA 2 MJCF base poses. Leader WidowX-250 arms "
            "are generated and validated as standalone models. Not modelled (no public machine-readable geometry "
            "for the URDF format): aluminium frame, table, cameras, passive gravity compensation."),
        "mount_source": MOUNT_SOURCE, "arms": ARMS, "leader": LEADER, "totals": totals,
        "models": {"aloha_vx300s": follower, "aloha_wx250s": leader},
        "start_pose": {"arm_joints": START_ARM_POSE, "left_finger": START_FINGER, "source": SRC["constants"]},
        "gripper_constants": GRIPPER_POSITION,
        "crosscheck": xc and {"pass": xc["pass"], "verdict": xc["verdict"],
                              "arms": xc["arms"], "engine": xc["engine"], "n_configs": xc["n_configs"]},
        "missing_information": [
            "Gripper motor-to-finger linkage (URDF: independent prop and finger joints; MJCF: different gripper model).",
            "Servo gear ratios, motor constants, friction and efficiency (URDF dynamics friction=0.1 damping=0.1 are "
            "generic defaults; MJCF contains system-identified values for a different actuator formulation).",
            "Dual-servo (shoulder/elbow shadow) load sharing.",
            "Leader-arm pose relative to the follower robot.",
            "Placeholder inertials (0.001 kg) on ee_arm_link, fingers_link, ee_gripper_link: rendered massless.",
        ],
        "assumptions": [
            "Gripper prop (continuous) joint held at 0 rad in experiments (no documented coupling in URDF).",
            "Start pose for all arms = START_ARM_POSE of aloha/constants.py.",
        ],
        "discrepancies": discrepancies(),
    }


def write_manifest(path: Path | None = None) -> Path:
    path = path or ROOT / "config" / "aloha2_configuration.json"
    path.write_text(json.dumps(build_manifest(), indent=2))
    return path
