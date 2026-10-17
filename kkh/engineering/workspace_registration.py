"""Read-only ALOHA task-frame audit; display offsets are NOT hardware registration.

The live renderer currently adds simple X offsets to independent URDF base frames.
This tool converts scene points to each displayed base, then checks real URDF IK
reachability before enabling any task-oriented motion shortcuts.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from kkh.studio import robotics as R
from kkh.domain.aloha import configuration as C

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / 'web' / 'src' / 'RobotStage.tsx'
SCENARIO = ROOT / 'config' / 'scenarios' / 'aloha2_cube_transfer.json'


def offsets(stage_text: str) -> dict[str, float]:
    m = re.search(r'const\s+FOLLOWER_OFFSET\s*=\s*(-?[\d.]+)\s*,\s*LEADER_OFFSET\s*=\s*(-?[\d.]+)', stage_text)
    if not m:
        raise ValueError('Cannot verify RobotStage.tsx display offsets; halt registration')
    return {'follower': float(m.group(1)), 'leader': float(m.group(2))}


def legacy_offsets() -> dict[str, float]:
    """X offsets of the legacy side-by-side display layout (single source: config/workspace/aloha2_display_layouts.json).

    RobotStage.tsx no longer hard-codes these values; it reads the same layout file through web/src/workspaceFrames.ts."""
    from kkh.engineering.workspace_frames import layout
    lay = layout('legacy_side_by_side')
    for role in ('leader', 'follower'):
        b = lay['bases'][role]
        if b['yaw'] != 0.0 or b['xyz'][1:] != [0.0, 0.0]:
            raise ValueError('Legacy layout is no longer X-translation-only; use kkh.engineering.workspace_frames')
    return {role: float(lay['bases'][role]['xyz'][0]) for role in ('follower', 'leader')}


def transform_point(point, source_offset: float, destination_offset: float) -> list[float]:
    """Translation-only mapping between the currently drawn URDF base origins.

    Important: no calibrated base rotation is known, so this is diagnostic ONLY.
    """
    point = np.asarray(point, dtype=float)
    if point.shape != (3,) or not np.isfinite(point).all():
        raise ValueError('Expected three finite coordinates in metres')
    return (point + [source_offset-destination_offset, 0., 0.]).tolist()


def reachable(model: str, point, *, max_error_m: float = 0.005) -> dict:
    robot = R.robot_for(model)
    q = np.asarray(C.start_vector(), float)
    if model == 'aloha_vx300s':
        q = np.asarray(R.mapping(q)['q'], float)
    names = R.JOINTS[:6]
    lo = np.array([robot.joints[n].limit.lower for n in names])
    hi = np.array([robot.joints[n].limit.upper for n in names])
    initial = np.clip(q[:6], lo+1e-8, hi-1e-8)
    point = np.asarray(point, float)
    def error(joints):
        pose = robot.forward_kinematics(dict(zip(R.JOINTS, [*joints, *q[6:]])))['ee_gripper_link']
        return pose[:3, 3] - point
    # Several bounded seeds reduce false negatives due to local IK minima.
    seeds = [initial, np.clip(np.zeros(6), lo+1e-8, hi-1e-8)]
    best = float('inf')
    for seed in seeds:
        result = least_squares(error, seed, bounds=(lo, hi), max_nfev=250, ftol=1e-10)
        best = min(best, float(np.linalg.norm(error(result.x))))
    return {'reachable_position_only': best <= max_error_m, 'best_position_error_m': round(best, 6),
            'tolerance_m': max_error_m, 'orientation_and_collision_checked': False}


def audit(stage_text: str | None = None, scenario: dict | None = None) -> dict:
    off = offsets(stage_text) if stage_text is not None else legacy_offsets()
    sc = scenario if scenario is not None else json.loads(SCENARIO.read_text(encoding='utf-8'))
    results = {}
    for label, point in [('cube_A', sc['objects'][0]['start_m']), ('target_B', sc['targets'][0]['center_m'])]:
        follower = list(map(float, point))
        leader = transform_point(follower, off['follower'], off['leader'])
        world = transform_point(follower, off['follower'], 0.)
        results[label] = {'follower_local_m': follower, 'leader_local_display_only_m': leader,
                          'display_world_m': world, 'leader_ik': reachable('aloha_wx250s', leader),
                          'follower_ik': reachable('aloha_vx300s', follower)}
    passed = all(p['leader_ik']['reachable_position_only'] and p['follower_ik']['reachable_position_only'] for p in results.values())
    return {
        'status': 'position_reachable_display_only_UNCALIBRATED' if passed else 'BLOCKED_UNREACHABLE_TASK_POINT',
        'frame_policy': 'Display X translations only; unknown leader/follower base rotations, no physical calibration',
        'display_base_offsets_x_m': off,
        'task_points': results,
        'engineering_gates': {'display_position_reachability': passed,
                              'hardware_base_registration': False,
                              'gripper_pose_orientation': False,
                              'cube_contact_3d': False,
                              'enable_ab_shortcuts': False},
        'safe_next_action': 'Define and verify actual scene base transforms before task motion. Never command above-A/B using follower coordinates directly.'
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=ROOT/'reports'/'workspace_registration.json')
    args = p.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
