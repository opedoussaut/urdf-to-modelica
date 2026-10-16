"""Task scenarios (robot-agnostic).

A scenario (config/scenarios/*.json) defines task objects, targets, the manipulating arm and the Level-1 visual grasp
rule. A robot *binding* module (named in the scenario) converts recorded joint data into end-effector positions and a
normalised gripper opening; evaluation below only sees those signals, so other robots/scenarios reuse it unchanged.

Level 1 = visual demonstration logic (kinematic attachment). It is NOT physics: no contact, friction, grasp stability
or payload. Level 2 is the PhysicsBackend interface in kkh.scenarios.physics (not implemented).
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = ROOT / "config" / "scenarios"


def available() -> list[dict]:
    out = []
    for f in sorted(SCENARIO_DIR.glob("*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        out.append({k: s[k] for k in ("id", "version", "title", "task", "robot_configuration")})
    return out


def load(scenario_id: str) -> dict:
    for f in SCENARIO_DIR.glob("*.json"):
        s = json.loads(f.read_text(encoding="utf-8"))
        if s["id"] == scenario_id:
            s["sha256"] = hashlib.sha256(f.read_bytes()).hexdigest()
            s["file"] = f.relative_to(ROOT).as_posix()
            return s
    raise KeyError(f"Unknown scenario {scenario_id}")


def binding(scenario: dict):
    return importlib.import_module(scenario["binding"])


def evaluate(scenario: dict, time, ee, opening) -> dict:
    """Apply the Level-1 visual grasp rule to (time[n], ee[n,3], opening[n]) and score the task.

    Returns the cube path, grasp/release events and task metrics. Deterministic; same rule as the UI."""
    rule = scenario["visual_grasp"]
    cube_spec, target = scenario["objects"][0], scenario["targets"][0]
    half = cube_spec["size_m"][2] / 2
    time, ee, opening = np.asarray(time, float), np.asarray(ee, float), np.asarray(opening, float)
    cube = np.array(cube_spec["start_m"], float)
    attached, offset, closed = False, np.zeros(3), opening[0] <= rule["gripper_closed_below"]
    events, path = [], []
    for k in range(len(time)):
        was_closed = closed
        if opening[k] <= rule["gripper_closed_below"]:
            closed = True
        elif opening[k] >= rule["gripper_open_above"]:
            closed = False
        if closed and not was_closed:
            distance = float(np.linalg.norm(ee[k] - cube))
            if distance <= rule["capture_radius_m"]:
                attached, offset = True, cube - ee[k]
                events.append({"t": float(time[k]), "event": "grasp", "distance_m": distance})
            else:
                events.append({"t": float(time[k]), "event": "close_missed", "distance_m": distance})
        if not closed and was_closed:
            if attached:
                attached = False
                cube = np.array([cube[0], cube[1], half])  # declared rule: vertical drop to the table
                events.append({"t": float(time[k]), "event": "release"})
            else:
                events.append({"t": float(time[k]), "event": "open"})
        if attached:
            cube = ee[k] + offset
        path.append([*cube.round(5).tolist(), int(attached)])
    centre, size = np.array(target["center_m"][:2]), np.array(target["size_m"]) / 2
    inside = bool(np.all(np.abs(cube[:2] - centre) <= size) and not attached and abs(cube[2] - half) < 1e-6)
    kinds = [e["event"] for e in events]
    grasp_t = next((e["t"] for e in events if e["event"] == "grasp"), None)
    release_t = next((e["t"] for e in events if e["event"] == "release"), None)
    return {
        "scenario": {"id": scenario["id"], "version": scenario["version"], "sha256": scenario.get("sha256")},
        "level": 1, "method": rule["model"],
        "metrics": {
            "grasped": "grasp" in kinds,
            "released": "release" in kinds,
            "grasp_before_release": grasp_t is not None and release_t is not None and grasp_t < release_t,
            "cube_in_target": inside,
            "cube_final_m": cube.round(4).tolist(),
            "distance_to_target_centre_m": round(float(np.linalg.norm(cube[:2] - centre)), 4),
            "missed_grasps": kinds.count("close_missed"),
            "task_completed": inside and "grasp" in kinds and "release" in kinds,
        },
        "events": events,
        "cube_path": path,
        "limitations": [
            "Level 1 visual demonstration logic: kinematic attachment, not physical grasping.",
            "No collision, contact, friction, grasp stability or payload; the cube does not affect the follower model.",
            "Attachment uses fingertip position only (orientation ignored); release drops the cube vertically.",
        ],
    }
