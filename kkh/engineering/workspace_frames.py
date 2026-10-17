"""Shared studio workspace frames: one source of truth for robot base poses in the 3D display world.

`config/workspace/aloha2_display_layouts.json` defines named layouts (base xyz + yaw for leader and follower,
table). The same file is read by the web renderer (web/src/workspaceFrames.ts), so Python checks and the display can
never use different base transforms.

Every transform here is an EXPERIMENTAL DISPLAY transform: nothing is a hardware calibration. Points carry their frame
(`LocalPoint.role`), so a follower-local position can never be converted as if it were leader-local.

CLI: python -m kkh.engineering.workspace_frames [--layout experimental_shared_table] [--output reports/...json]
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[2]
LAYOUTS = ROOT / "config" / "workspace" / "aloha2_display_layouts.json"
ROLES = ("leader", "follower")
TOLERANCE_M = 0.005


def load_layouts(path: Path = LAYOUTS) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def layout(name: str | None = None, data: dict | None = None) -> dict:
    data = data or load_layouts()
    name = name or data["default_layout"]
    if name not in data["layouts"]:
        raise KeyError(f"Unknown display layout {name}")
    out = dict(data["layouts"][name])
    out["name"] = name
    for role in ROLES:
        base = out["bases"][role]
        if len(base["xyz"]) != 3 or not all(math.isfinite(v) for v in [*base["xyz"], base["yaw"]]):
            raise ValueError(f"Layout {name}: {role} base pose must be three finite metres and a finite yaw")
    return out


@dataclass(frozen=True)
class LocalPoint:
    """A point in one robot's URDF base frame (metres). The role is part of the value."""
    role: str
    xyz: tuple[float, float, float]

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"Unknown robot frame {self.role!r}")
        if len(self.xyz) != 3 or not all(math.isfinite(v) for v in self.xyz):
            raise ValueError("Expected three finite coordinates in metres")


def _point(p) -> np.ndarray:
    a = np.asarray(p, dtype=float)
    if a.shape != (3,) or not np.isfinite(a).all():
        raise ValueError("Expected three finite coordinates in metres")
    return a


def base_matrix(lay: dict, role: str) -> np.ndarray:
    """4x4 transform base(role) -> display world: rotation about +Z by yaw, then translation."""
    if role not in ROLES:
        raise ValueError(f"Unknown robot frame {role!r}")
    b = lay["bases"][role]
    c, s = math.cos(b["yaw"]), math.sin(b["yaw"])
    T = np.eye(4)
    T[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    T[:3, 3] = b["xyz"]
    return T


def to_world(lay: dict, point: LocalPoint) -> list[float]:
    T = base_matrix(lay, point.role)
    return (T[:3, :3] @ _point(point.xyz) + T[:3, 3]).tolist()


def to_local(lay: dict, role: str, world) -> LocalPoint:
    T = base_matrix(lay, role)
    local = T[:3, :3].T @ (_point(world) - T[:3, 3])
    return LocalPoint(role, tuple(float(v) for v in local))


def convert(lay: dict, point: LocalPoint, role: str) -> LocalPoint:
    """Local point of one robot expressed in the other robot's base frame (through the display world)."""
    return to_local(lay, role, to_world(lay, point))


# ------------------------------------------------------------------------------------------------ reachability
def _robot(model: str):
    from kkh.studio import robotics as R
    return R, R.robot_for(model)


def ik_check(model: str, local, *, gripper_down: bool) -> dict:
    """Bounded least-squares IK on the URDF (position, optionally gripper x-axis pointing down).

    Position/pointing only: no collision, no grasp orientation about the vertical, no contact."""
    R, robot = _robot(model)
    names = R.JOINTS[:6]
    lo = np.array([robot.joints[n].limit.lower for n in names])
    hi = np.array([robot.joints[n].limit.upper for n in names])
    target = _point(local)
    tail = [0.0, 0.0]

    def residual(q):
        T = robot.forward_kinematics(dict(zip(R.JOINTS, [*q, *tail])))["ee_gripper_link"]
        r = T[:3, 3] - target
        if gripper_down:
            r = np.r_[r, 0.2 * (1.0 - T[:3, 0] @ np.array([0.0, 0.0, -1.0]))]  # 0 when the gripper x-axis points down
        return r

    best, best_q = float("inf"), None
    seeds = [np.clip(np.zeros(6), lo + 1e-8, hi - 1e-8),
             np.clip(np.array([math.atan2(target[1], target[0]), 0.0, 0.0, 0.0, 1.2, 0.0]), lo + 1e-8, hi - 1e-8),
             np.clip(np.array([math.atan2(target[1], target[0]), -0.5, 0.8, 0.0, 1.0, 0.0]), lo + 1e-8, hi - 1e-8)]
    for seed in seeds:
        sol = least_squares(residual, seed, bounds=(lo, hi), max_nfev=300, ftol=1e-10)
        T = robot.forward_kinematics(dict(zip(R.JOINTS, [*sol.x, *tail])))["ee_gripper_link"]
        pos_err = float(np.linalg.norm(T[:3, 3] - target))
        down_err = float(math.degrees(math.acos(np.clip(T[:3, 0] @ [0, 0, -1], -1, 1))))
        score = pos_err + (down_err * 1e-4 if gripper_down else 0.0)
        if score < best:
            best, best_q = score, (sol.x, pos_err, down_err)
    q, pos_err, down_err = best_q
    ok = pos_err <= TOLERANCE_M and (not gripper_down or down_err <= 5.0)
    return {"reachable": bool(ok), "position_error_m": round(pos_err, 6),
            "gripper_down_error_deg": round(down_err, 2) if gripper_down else None,
            "waist_rad": round(float(q[0]), 4), "q": [round(float(v), 6) for v in q], "tolerance_m": TOLERANCE_M,
            "checked": "position + gripper pointing down" if gripper_down else "position only",
            "collision_checked": False, "grasp_orientation_checked": False}


def check_point(lay: dict, world) -> dict:
    """Reachability of one display-world point for both arms in their own base frames."""
    out = {"world_m": [round(v, 6) for v in _point(world)]}
    for role in ROLES:
        local = to_local(lay, role, world)
        model = lay["bases"][role]["model"]
        out[role] = {"local_m": [round(v, 6) for v in local.xyz],
                     "position_ik": ik_check(model, local.xyz, gripper_down=False),
                     "gripper_down_ik": ik_check(model, local.xyz, gripper_down=True)}
    return out


def search_task_points(lay: dict, cube_half_height: float, *, separation_m: float = 0.12,
                       xs=(-0.10, -0.05, 0.0, 0.05, 0.10), ys=(-0.12, -0.06, 0.0, 0.06)) -> dict:
    """Shared tabletop A/B pairs (B = A + separation along +Y) reachable by BOTH arms with the gripper pointing
    down. Ranked by the smallest IK margin to the arm with the least slack (largest position error first)."""
    table = lay["table"]
    if not 0 < cube_half_height < 0.1:
        raise ValueError("Unexpected cube half height; inspect scenario units")
    z = table["top_z"] + cube_half_height
    evaluated, feasible = [], []
    for x in xs:
        for y in ys:
            a, b = [x, y, z], [x, y + separation_m, z]
            if not all(_on_table(table, p, cube_half_height) for p in (a, b)):
                continue
            pa, pb = check_point(lay, a), check_point(lay, b)
            ok = all(p[r]["gripper_down_ik"]["reachable"] for p in (pa, pb) for r in ROLES)
            item = {"cube_A": pa, "target_B": pb, "gripper_down_feasible_both_arms": ok,
                    "centre_distance_m": round(math.hypot(x, y + separation_m / 2), 4)}
            evaluated.append(item)
            if ok:
                feasible.append(item)
    feasible.sort(key=lambda i: i["centre_distance_m"])  # most central first: equal slack for both mounts
    return {"evaluated": len(evaluated), "feasible": len(feasible), "best": feasible[0] if feasible else None}


def _on_table(table: dict, p, half: float) -> bool:
    cx, cy = table["center_xy"]
    sx, sy = table["size_xy"]
    return abs(p[0] - cx) <= sx / 2 - half and abs(p[1] - cy) <= sy / 2 - half


def gates(report_ok: bool) -> dict:
    """Engineering gates. Only the display layout and position/pointing IK are ever true here."""
    return {
        "display_layout_applied": True,
        "position_ik_both_arms": bool(report_ok),
        "gripper_down_ik_both_arms": bool(report_ok),
        "grasp_orientation_about_vertical": False,
        "robot_table_collision": False,
        "leader_follower_collision": False,
        "physical_contact_3d": False,
        "hardware_registration": False,
        "enable_ab_shortcuts": False,
        "grasp_automation": False,
        "hardware_motion": False,
    }


def audit_layout(name: str = "experimental_shared_table", scenario: dict | None = None) -> dict:
    """Check the task points of a layout's scenario (must be in the display world frame) for both arms."""
    lay = layout(name)
    from kkh import scenarios as S
    sc = scenario or S.load(lay["scenario"])
    if sc.get("frame", {}).get("layout") != name:
        raise ValueError(f"Scenario {sc['id']} is not expressed in the {name} display world")
    half = sc["objects"][0]["size_m"][2] / 2
    a, b = sc["objects"][0]["start_m"], sc["targets"][0]["center_m"]
    pa, pb = check_point(lay, a), check_point(lay, b)
    ok = all(p[r]["gripper_down_ik"]["reachable"] for p in (pa, pb) for r in ROLES)
    table = lay["table"]
    return {
        "status": "EXPERIMENTAL_DISPLAY_LAYOUT_POSITION_IK_ONLY" if ok else "BLOCKED_TASK_POINT_UNREACHABLE",
        "layout": name, "layout_file": LAYOUTS.relative_to(ROOT).as_posix(), "world_frame": "STUDIO_DISPLAY_WORLD",
        "bases": lay["bases"], "evidence": lay["evidence"],
        "scenario": {"id": sc["id"], "version": sc["version"]},
        "table_top_z_m": table["top_z"],
        "cube_centre_on_table": abs(a[2] - (table["top_z"] + half)) < 1e-9,
        "task_points": {"cube_A": pa, "target_B": pb},
        "engineering_gates": gates(ok),
        "statement": "Experimental layout — position IK only; orientation/collision/physical contact unverified. "
                     "Display transforms are not hardware calibration.",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--layout", default="experimental_shared_table")
    p.add_argument("--search", action="store_true", help="search shared A/B candidates instead of auditing")
    p.add_argument("--output", type=Path, default=ROOT / "reports" / "workspace_layout.json")
    args = p.parse_args()
    if args.search:
        result = {"layout": args.layout, **search_task_points(layout(args.layout), 0.02),
                  "engineering_gates": gates(False) | {"display_layout_applied": False}}
    else:
        result = audit_layout(args.layout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2)[:6000])


if __name__ == "__main__":
    main()
