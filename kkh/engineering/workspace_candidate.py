"""Produce a reviewable shared-workspace candidate using URDF position IK.

This is a DESIGN proposal, not calibrated scene registration, grasp feasibility,
collision checking, or permission to move the robot automatically.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import numpy as np

from kkh.engineering.workspace_registration import (
    ROOT, SCENARIO, legacy_offsets, reachable, transform_point,
)


def evaluate_candidate(
    cube_world: list[float], target_world: list[float],
    base_offsets: dict[str, float],
    reach: Callable[[str, list[float]], dict] = reachable,
) -> dict:
    """Compare two task points in both displayed robot-base frames.

    All points use metres. X-only offsets are a *rendering convention*, not a
    measured physical transform. Only position IK is evaluated.
    """
    if set(base_offsets) != {'leader', 'follower'}:
        raise ValueError('Explicit leader and follower display offsets are required')
    answers: dict = {}
    for name, xyz in [('cube_A', cube_world), ('target_B', target_world)]:
        p = np.asarray(xyz, dtype=float)
        if p.shape != (3,) or not np.isfinite(p).all():
            raise ValueError('Task points must be three finite metre values')
        checks = {}
        for role, model in [('leader', 'aloha_wx250s'), ('follower', 'aloha_vx300s')]:
            local = transform_point(p.tolist(), 0., base_offsets[role])
            ik = reach(model, local)
            checks[role] = {'local_m': local, 'position_ik': ik}
        answers[name] = {'world_m': p.tolist(), 'arms': checks}
    feasible = all(
        entry['position_ik']['reachable_position_only']
        for task in answers.values() for entry in task['arms'].values()
    )
    worst = max(
        entry['position_ik']['best_position_error_m']
        for task in answers.values() for entry in task['arms'].values()
    )
    return {'position_ik_feasible': bool(feasible), 'worst_position_error_m': float(worst), 'task_points': answers}


def candidates(scenario: dict, base_offsets: dict[str, float], *,
               reach: Callable[[str, list[float]], dict] = reachable) -> dict:
    """Search a conservative set of *shared* tabletop locations.

    Candidates are displayed world points. They must not be applied until
    orientation, robot/table collision and scene mount transforms are checked.
    """
    half_height = float(scenario['objects'][0]['size_m'][2]) / 2
    if not 0 < half_height < 0.1:
        raise ValueError('Unexpected cube half height; inspect scenario units')
    # Two task points on a shared table, separated by 12 cm along the Y axis.
    # These ranges are search proposals, NOT a verified physical tabletop.
    options = []
    for x in (-0.08, 0.0, 0.08, 0.16):
        for y in (-0.08, 0.0, 0.08):
            a = [x, y, half_height]
            b = [x, y + 0.12, half_height]
            result = evaluate_candidate(a, b, base_offsets, reach)
            options.append(result)
    valid = [v for v in options if v['position_ik_feasible']]
    valid.sort(key=lambda item: item['worst_position_error_m'])
    return {
        'status': 'POSITION_IK_CANDIDATE_FOUND_REVIEW_REQUIRED' if valid else 'NO_COMMON_POSITION_IK_CANDIDATE',
        'reference_frame': 'THREE_JS_DISPLAY_WORLD; X-only base offsets; uncalibrated',
        'source_provenance': 'GEN7 URDF FK/IK, NOT hardware or MJCF registration',
        'display_base_offsets_x_m': base_offsets,
        'candidates_evaluated': len(options),
        'candidates_feasible_position_only': len(valid),
        'best_candidate': valid[0] if valid else None,
        'engineering_gates': {
            'position_only_ik': bool(valid),
            'orientation_ik': False,
            'robot_table_collision': False,
            'leader_follower_collision': False,
            'gripper_contact_model': False,
            'hardware_registration': False,
            'safe_to_apply_to_live_scene': False,
        },
        'next_action': 'Review results and define a confirmed scene frame before updating renderer, scenario JSON or robot commands.',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports' / 'workspace_candidate.json')
    args = parser.parse_args()
    sc = json.loads(SCENARIO.read_text(encoding='utf-8'))
    off = legacy_offsets()
    proposal = candidates(sc, off)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proposal, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(proposal, indent=2))


if __name__ == '__main__':
    main()
