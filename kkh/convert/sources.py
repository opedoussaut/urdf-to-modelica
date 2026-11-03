"""Conversion inputs: allowlisted pinned URDFs and validated uploads (stored by content hash)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from kkh.engineering.urdf_model import load_urdf

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "convert"
UPLOADS = RUNS / "uploads"
MAX_UPLOAD = 300_000  # bytes

PINNED = {
    "themis": {
        "path": "third_party/themis_simulation_model/TH02-A7-FULL/urdf/TH02-A7-FULL.urdf",
        "label": "Westwood Robotics THEMIS (TH02-A7)", "short": "THEMIS", "default": True, "featured": True,
        "what": "Full-size humanoid with 7-DoF arms and three-finger EN02 hands; TH02-A7 is the model in production",
        "sources": ["Westwood Robotics THEMIS-Simulation-Model (official URDF TH02-A7-FULL, exported from SolidWorks)",
                    "Repository README: TH02-A7 is the only THEMIS model in mass production (other models discontinued 25 Sep 2025)",
                    "Note: the published file gives every joint lower = upper = 0, effort 0 and velocity 0 (exporter defaults), "
                    "and two thumb links an inertia rounded to zero; Stage 0 reports both"],
        "license": "Apache-2.0", "repo": "https://github.com/Westwood-Robotics/THEMIS-Simulation-Model",
        "provenance": "THEMIS-Simulation-Model @ c955a30 (pinned, config/public_sources.json)"},
    "so101": {
        "path": "third_party/so_arm100/Simulation/SO101/so101_new_calib.urdf",
        "label": "SO-101 arm (LeRobot)", "short": "SO-101", "demo": True,
        "what": "Low-cost 6-joint arm used with Hugging Face LeRobot for learning robot skills; small enough for a demo in minutes",
        "sources": ["TheRobotStudio SO-ARM100 repository (official SO-101 URDF exported from the CAD, so101_new_calib)",
                    "Hugging Face LeRobot documentation (SO-101 setup and calibration)",
                    "Note: the file gives every joint the same effort limit (10 N·m), a generic value rather than the servo rating"],
        "license": "Apache-2.0", "repo": "https://github.com/TheRobotStudio/SO-ARM100",
        "provenance": "SO-ARM100 @ a758567 (pinned, config/public_sources.json)"},
    "unitree_g1": {
        "path": "third_party/unitree_ros/robots/g1_description/g1_29dof_with_hand_rev_1_0.urdf",
        "label": "Unitree G1 EDU with Dex3-1 hands", "short": "Unitree G1",
        "what": "Bipedal humanoid with dexterous three-finger hands",
        "sources": ["Unitree unitree_ros g1_description (official URDF g1_29dof_with_hand_rev_1_0)",
                    "Unitree G1 product page and developer documentation"],
        "license": "BSD-3-Clause", "repo": "https://github.com/unitreerobotics/unitree_ros",
        "provenance": "unitree_ros @ 5994d4f (pinned, config/public_sources.json)"},
    "berkeley_humanoid_lite": {
        "path": "third_party/berkeley_humanoid_lite_assets/data/robots/berkeley_humanoid/berkeley_humanoid_lite/urdf/berkeley_humanoid_lite.urdf",
        "label": "Berkeley Humanoid Lite", "short": "Berkeley Humanoid Lite",
        "what": "Open-source humanoid, about 0.8 m and 16 kg, 3D-printed cycloidal actuators",
        "sources": ["Berkeley Humanoid Lite assets (URDF exported from the project's CAD)",
                    "Project README joint table and motor configuration", "RSS 2025 paper (arXiv 2504.17249)"],
        "license": "CC-BY-SA-4.0", "repo": "https://github.com/HybridRobotics/Berkeley-Humanoid-Lite-Assets",
        "provenance": "Berkeley-Humanoid-Lite-Assets @ fc90fed (pinned, config/public_sources.json)"},
    "aloha_vx300s": {"path": "data/urdf/aloha_vx300s.urdf", "label": "ALOHA 2 follower arm (ViperX 300 S)", "short": "ALOHA follower",
                     "what": "The arm that does the work in the ALOHA 2 bimanual workcell, with a two-finger gripper",
                     "sources": ["Interbotix ALOHA xacro (aloha_vx300s), expanded by tools/expand_xacro.py",
                                 "Trossen specification pages", "ALOHA 2 paper (arXiv 2405.02292)"],
                     "license": "BSD-3-Clause", "repo": "https://github.com/Interbotix/interbotix_ros_manipulators",
                     "provenance": "Interbotix xacro, pinned commit, expanded by tools/expand_xacro.py"},
    "aloha_wx250s": {"path": "data/urdf/aloha_wx250s.urdf", "label": "ALOHA 2 leader arm (WidowX 250 S)", "short": "ALOHA leader",
                     "what": "The arm a person moves by hand to teach ALOHA 2 (teleoperation)",
                     "sources": ["Interbotix ALOHA xacro (aloha_wx250s), expanded by tools/expand_xacro.py",
                                 "Trossen specification pages", "ALOHA 2 paper (arXiv 2405.02292)"],
                     "license": "BSD-3-Clause", "repo": "https://github.com/Interbotix/interbotix_ros_manipulators",
                     "provenance": "Interbotix xacro, pinned commit, expanded by tools/expand_xacro.py"},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(path: Path) -> dict:
    robot = load_urdf(path)
    return {"robot": robot.name, "links": len(robot.links), "joints": len(robot.joints),
            "movable": sum(1 for j in robot.joints.values() if j.movable),
            "joint_types": sorted({j.type for j in robot.joints.values()}),
            "mimic": sum(1 for j in robot.joints.values() if j.mimic),
            "mass_kg": round(sum(l.inertial.mass for l in robot.links.values() if l.inertial), 4),
            "bytes": path.stat().st_size}


def list_sources() -> list[dict]:
    out = [{"id": k, **v, "kind": "pinned", "sha256": sha256(ROOT / v["path"]), **summary(ROOT / v["path"])}
           for k, v in PINNED.items()]
    for meta in sorted(UPLOADS.glob("*/meta.json")):
        out.append(json.loads(meta.read_text(encoding="utf-8")))
    return out


def resolve(source: str) -> tuple[Path, dict]:
    """Source id → URDF path and its metadata. Only allowlisted ids or stored uploads are accepted."""
    if source in PINNED:
        meta = {"id": source, **PINNED[source], "kind": "pinned"}
        return ROOT / PINNED[source]["path"], meta
    if re.fullmatch(r"upload-[0-9a-f]{16}", source):
        d = UPLOADS / source.removeprefix("upload-")
        if (d / "robot.urdf").exists():
            return d / "robot.urdf", json.loads((d / "meta.json").read_text(encoding="utf-8"))
    raise ValueError("Unknown source: choose a pinned arm or an uploaded URDF")


def store_upload(filename: str, data: bytes) -> dict:
    """Validate and store an uploaded URDF. Rejects anything that is not a parseable URDF robot."""
    if not filename.lower().endswith(".urdf"):
        raise ValueError("Only .urdf files are accepted (expand xacro files first)")
    if len(data) > MAX_UPLOAD:
        raise ValueError(f"File too large ({len(data):,} bytes; limit {MAX_UPLOAD:,})")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Not valid XML: {exc}") from exc
    if root.tag != "robot" or not root.findall("link"):
        raise ValueError("Not a URDF: the root element must be <robot> with at least one <link>")
    if root.find(".//{http://www.ros.org/wiki/xacro}macro") is not None or b"xacro:" in data:
        raise ValueError("This looks like a xacro file; expand it to plain URDF first")
    digest = hashlib.sha256(data).hexdigest()
    d = UPLOADS / digest[:16]
    d.mkdir(parents=True, exist_ok=True)
    (d / "robot.urdf").write_bytes(data)
    try:
        info = summary(d / "robot.urdf")
        structure = load_urdf(d / "robot.urdf").validate_structure()
    except Exception as exc:
        raise ValueError(f"The URDF could not be parsed as a robot: {exc}") from exc
    path = d / "robot.urdf"
    meta = {"id": "upload-" + digest[:16], "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix(),
            "label": f"{info['robot']} (uploaded: {Path(filename).name})", "provenance": "uploaded by the user",
            "kind": "upload", "sha256": digest, "structure": structure, **info}
    (d / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def prompt_text(path: Path) -> str:
    """URDF text for an LLM prompt: visuals/collisions/materials removed (meshes are irrelevant to kinematics and
    dynamics, and they cost context), comments dropped. Inertials, joints, origins, axes, limits, mimic kept."""
    root = ET.parse(path).getroot()
    for parent in root.iter():
        for child in list(parent):
            if child.tag in ("visual", "collision", "material", "gazebo", "transmission", "ros2_control"):
                parent.remove(child)
    text = ET.tostring(root, encoding="unicode")
    return re.sub(r"\n\s*\n", "\n", text)
