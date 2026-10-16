"""ALOHA domain knowledge: selected public configuration, sourced constants, configuration manifest.

Every constant here carries a source reference. Values are classified as
  verified  - copied from a pinned public source
  derived   - computed deterministically from verified values (rule documented)
  assumption- chosen by this project, explicitly flagged
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from kkh.engineering.urdf_model import load_urdf

ROOT = Path(__file__).resolve().parents[3]
URDF_DIR = ROOT / "data" / "urdf"

VARIANT = {
    "id": "aloha_stationary_trossen",
    "name": "ALOHA Stationary (Trossen Robotics / Interbotix ROS 2 'aloha' package)",
    "rationale": (
        "Best-documented public ALOHA configuration with machine-readable kinematics and inertials: "
        "official URDF/xacro + meshes for the ALOHA-specific arm variants (aloha_vx300s, aloha_wx250s), "
        "official bringup with workcell transforms, and official per-arm spec pages. The Kyoto University "
        "configuration could not be confirmed from public evidence. Original Stanford ALOHA "
        "(tonyzhaozh/aloha) and ALOHA 2 MJCF (mujoco_menagerie) are different variants and are NOT mixed in."),
    "sources": {
        "descriptions": "Interbotix/interbotix_ros_manipulators@b66d5b905725 (humble) interbotix_xsarm_descriptions",
        "bringup": "Interbotix/aloha@4fa6b2c4428f launch/aloha_bringup.launch.py",
        "constants": "Interbotix/aloha@4fa6b2c4428f aloha/constants.py",
        "spec_follower": "https://docs.trossenrobotics.com/interbotix_xsarms_docs/specifications/avx300s.html",
        "spec_leader": "https://docs.trossenrobotics.com/interbotix_xsarms_docs/specifications/awx250s.html",
    },
}

# Arm order defines the order of the assembly input vector (8 driven joints per arm).
ARMS = [
    {"id": "follower_left", "modelica": "followerLeft", "model": "aloha_vx300s", "role": "follower", "side": "left",
     "mount_xyz": [0.5, 0.25, 0.0]},
    {"id": "follower_right", "modelica": "followerRight", "model": "aloha_vx300s", "role": "follower", "side": "right",
     "mount_xyz": [0.5, -0.25, 0.0]},
    {"id": "leader_left", "modelica": "leaderLeft", "model": "aloha_wx250s", "role": "leader", "side": "left",
     "mount_xyz": [-0.5, 0.25, 0.0]},
    {"id": "leader_right", "modelica": "leaderRight", "model": "aloha_wx250s", "role": "leader", "side": "right",
     "mount_xyz": [-0.5, -0.25, 0.0]},
]
MOUNT_SOURCE = ("Interbotix/aloha launch/aloha_bringup.launch.py static_transform_publisher world->*/base_link "
                "(identity rotation). Classified 'verified' as published; it is the ROS visualisation frame "
                "layout, not a surveyed physical workcell measurement.")

ARM_CLASS = {"aloha_vx300s": "AlohaVX300s", "aloha_wx250s": "AlohaWX250s"}
ARM_PRODUCT = {"aloha_vx300s": "ALOHA ViperX-300 6DOF", "aloha_wx250s": "ALOHA WidowX-250 6DOF"}

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

# Documented spec-page joint limits (degrees; gripper in mm finger separation)
SPEC_LIMITS = {
    "aloha_vx300s": {"waist": (-180, 180), "shoulder": (-101, 101), "elbow": (-101, 92), "wrist_angle": (-107, 130),
                     "forearm_roll": (-180, 180), "wrist_rotate": (-180, 180), "gripper_mm": (42, 116)},
    "aloha_wx250s": {"waist": (-180, 180), "shoulder": (-108, 114), "elbow": (-123, 92), "forearm_roll": (-180, 180),
                     "wrist_angle": (-100, 123), "wrist_rotate": (-180, 180), "gripper_mm": (30, 74)},
}

# Interbotix/aloha aloha/constants.py
START_ARM_POSE = [0.0, -0.96, 1.16, 0.0, -0.3, 0.0]          # waist..wrist_rotate [rad]
START_FINGER = 0.02239                                       # left_finger [m]; right_finger = -left
GRIPPER_POSITION = {"leader": {"open": 0.0323, "close": 0.0185},
                    "follower": {"open": 0.0579, "close": 0.0440}}
ACTUATED = ["waist", "shoulder", "elbow", "forearm_roll", "wrist_angle", "wrist_rotate", "gripper", "left_finger"]


def arm_robot(model: str):
    return load_urdf(URDF_DIR / f"{model}.urdf", strip_prefix=f"{model}/")


def start_vector(arm: dict) -> list[float]:
    """Start pose of one arm in ACTUATED order. Gripper (prop) joint: 0 (assumption, see manifest)."""
    return START_ARM_POSE + [0.0, START_FINGER]


def build_manifest() -> dict:
    arms_out, totals = [], {"links": 1, "joints": 0, "driven": 0, "mimic": 0}
    discrepancies = []
    for arm in ARMS:
        r = arm_robot(arm["model"])
        rep = r.validate_structure()
        inert = r.validate_inertials()
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
                "actuators": ACTUATORS[arm["model"]].get(j.name),
                "servo_ids": SERVO_IDS.get(j.name) if j.name in ACTUATORS[arm["model"]] else None,
            })
        arms_out.append({
            **arm, "product": ARM_PRODUCT[arm["model"]], "urdf": f"data/urdf/{arm['model']}.urdf",
            "n_links": rep["n_links"], "n_joints": rep["n_joints"], "joint_types": rep["joint_types"],
            "driven_joints": [j.name for j in r.actuated_joints()],
            "mimic_joints": [j.name for j in r.joints.values() if j.mimic],
            "joints": joints,
            "links": [{"name": x["link"], "inertial_status": x["status"], "mass": x.get("mass"),
                       "mesh": next((v.mesh for v in r.links[x["link"]].visuals if v.mesh), None)} for x in inert],
        })
        totals["links"] += rep["n_links"]
        totals["joints"] += rep["n_joints"] + 1  # + mount joint
        totals["driven"] += rep["n_actuated"]
        totals["mimic"] += len([j for j in r.joints.values() if j.mimic])
        # Compare URDF limits against spec page
        for jn, (lo, hi) in SPEC_LIMITS[arm["model"]].items():
            if jn == "gripper_mm":
                f = r.joints["left_finger"].limit
                urdf_mm = (round(2000 * f.lower, 1), round(2000 * f.upper, 1))
                if urdf_mm != (lo, hi):
                    discrepancies.append({"arm": arm["id"], "item": "gripper opening (2 x left_finger)",
                                          "urdf_mm": urdf_mm, "spec_mm": (lo, hi)})
                continue
            l = r.joints[jn].limit
            u = (round(math.degrees(l.lower)), round(math.degrees(l.upper)))
            if u != (lo, hi):
                discrepancies.append({"arm": arm["id"], "item": f"{jn} limit", "urdf_deg": u, "spec_deg": (lo, hi)})
    fl = arm_robot("aloha_vx300s").joints["left_finger"].limit
    if GRIPPER_POSITION["follower"]["open"] > fl.upper:
        discrepancies.append({"arm": "followers", "item": "FOLLOWER_GRIPPER_POSITION_OPEN (aloha/constants.py)",
                              "value": GRIPPER_POSITION["follower"]["open"], "urdf_upper": fl.upper,
                              "resolution": "trajectories clamp to the URDF limit"})
    lw = arm_robot("aloha_wx250s").joints["left_finger"].limit
    if GRIPPER_POSITION["leader"]["close"] < lw.lower:
        discrepancies.append({"arm": "leaders", "item": "LEADER_GRIPPER_POSITION_CLOSE (aloha/constants.py)",
                              "value": GRIPPER_POSITION["leader"]["close"], "urdf_lower": lw.lower,
                              "resolution": "trajectories clamp to the URDF limit"})
    discrepancies.append({"arm": "followers", "item": "spec page servo-ID table vs servo configuration table",
                          "detail": "Joint-limit table lists Wrist Angle as ID 6 / Forearm Roll ID 7; servo table lists "
                                    "6 forearm_roll / 7 wrist_angle. URDF joint order (forearm_roll before wrist_angle) "
                                    "matches the servo table."})
    return {
        "variant": VARIANT,
        "complete_robot_definition": (
            "The complete documented mechanical assembly = 4 arms (2 follower ALOHA ViperX-300 6DOF, 2 leader "
            "ALOHA WidowX-250 6DOF) with every URDF link and joint (including grippers, finger mimic, leader "
            "handle), mounted in the world frame with the bringup transforms. Excluded because no public "
            "machine-readable geometry exists for this variant: table/frame, cameras, gravity compensators."),
        "mount_source": MOUNT_SOURCE,
        "totals": totals,
        "arms": arms_out,
        "start_pose": {"arm_joints": START_ARM_POSE, "left_finger": START_FINGER,
                       "source": VARIANT["sources"]["constants"] + " START_ARM_POSE"},
        "gripper_constants": GRIPPER_POSITION,
        "missing_information": [
            "Gripper motor-to-finger linkage: URDF models the gripper prop rotation (continuous) and finger "
            "translation (prismatic) as independent joints; the mechanical coupling is not in the URDF. "
            "aloha/constants.py gives a calibrated linear map only between the ALOHA close/open points.",
            "Gearbox ratios, motor constants, friction and efficiency of the Dynamixel servos (datasheet values not "
            "ingested yet; URDF <dynamics friction=0.1 damping=0.1> are generic defaults, not identified values).",
            "Dual-servo (shoulder/elbow shadow) load sharing.",
            "Workcell frame, table and camera mounts for this variant.",
            "Placeholder inertials (mass 0.001 kg, I = 1e-4 kg m^2) on ee_arm_link, fingers_link, ee_gripper_link: "
            "rendered as massless frames.",
        ],
        "assumptions": [
            "Gripper prop (continuous) joint held at 0 rad in baseline experiments (no documented coupling).",
            "Followers and leaders use the same START_ARM_POSE (as in aloha/constants.py).",
        ],
        "discrepancies": discrepancies,
    }


def write_manifest(path: Path | None = None) -> Path:
    path = path or ROOT / "config" / "aloha_configuration.json"
    path.write_text(json.dumps(build_manifest(), indent=2))
    return path
