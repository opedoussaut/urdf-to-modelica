"""Read-only comparison of GEN7 ALOHA follower URDF with pinned Menagerie MJCF.

No coordinate mapping or physically calibrated contact is inferred from differing source models.
Run: python -m kkh.engineering.aloha_reference_audit
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_URDF = ROOT / 'data/urdf/aloha_vx300s.urdf'
DEFAULT_MJCF = ROOT / 'third_party/mujoco_menagerie/aloha/aloha.xml'
DEFAULT_SCENE = ROOT / 'third_party/mujoco_menagerie/aloha/scene.xml'


def _finger_urdf(path: Path) -> dict:
    root = ET.parse(path).getroot()
    results = {}
    for name in ('left_finger', 'right_finger'):
        joint = root.find(f"./joint[@name='{name}']")
        if joint is None:
            raise ValueError(f'Missing URDF joint: {name}')
        lim = joint.find('limit')
        axis = joint.find('axis')
        mimic = joint.find('mimic')
        if lim is None or axis is None:
            raise ValueError(f'Incomplete URDF joint: {name}')
        results[name] = {
            'type': joint.attrib['type'],
            'range_m': [float(lim.attrib['lower']), float(lim.attrib['upper'])],
            'axis_local': [float(x) for x in axis.attrib['xyz'].split()],
            'mimic': mimic.attrib if mimic is not None else None,
        }
    return results


def _finger_mjcf(path: Path) -> dict:
    root = ET.parse(path).getroot()
    cls = root.find(".//default[@class='finger']")
    if cls is None:
        raise ValueError('Menagerie finger default class missing')
    actuator = cls.find('position')
    if actuator is None:
        raise ValueError('Menagerie finger actuator definition missing')
    output = {'actuator': {
        'command_range_m': [float(x) for x in actuator.attrib['ctrlrange'].split()],
        'kp': float(actuator.attrib['kp']),
        'kv': float(actuator.attrib['kv']),
    }, 'fingers': {}}
    for name in ('left_finger', 'right_finger'):
        sub = cls.find(f"./default[@class='{name}']/joint")
        if sub is None:
            raise ValueError(f'Menagerie {name} definition missing')
        output['fingers'][name] = {
            'physical_range_m': [float(x) for x in sub.attrib['range'].split()],
            'axis_local': [float(x) for x in sub.attrib['axis'].split()],
        }
    for arm in ('left', 'right'):
        for finger in ('left', 'right'):
            points = []
            for idx in range(3):
                geom = root.find(f".//geom[@name='{arm}/{finger}_g{idx}']")
                if geom is not None:
                    points.append({'name': geom.attrib['name'], 'pos_local_m': [float(x) for x in geom.attrib['pos'].split()]})
            output.setdefault('contact_markers', {})[f'{arm}/{finger}'] = points
    return output


def audit(urdf: Path = DEFAULT_URDF, mjcf: Path = DEFAULT_MJCF, scene: Path = DEFAULT_SCENE) -> dict:
    if not urdf.is_file():
        raise FileNotFoundError(f'GEN7 follower URDF not found: {urdf}')
    source = _finger_urdf(urdf)
    report = {
        'status': 'reference_not_available',
        'source_urdf': str(urdf),
        'menagerie_mjcf': str(mjcf),
        'urdf_finger_joints': source,
        'source_policy': 'URDF remains GEN7 kinematic source of truth; MJCF is comparative evidence only.',
        'engineering_gates': {
            'reference_frame_registration': 'NOT_VERIFIED',
            'finger_coordinate_conversion': 'NOT_VERIFIED',
            'gripper_contact_geometry': 'NOT_VERIFIED',
            'physically_validated_grasp': 'NOT_VERIFIED',
        },
        'known_reference_difference': 'GEN7 URDF left 0.021..0.057 m; Menagerie MJCF left 0..0.041 m; distinct origins and conventions. Do not directly substitute.',
    }
    if not mjcf.is_file():
        report['next_action'] = ('Run the existing tools/fetch_sources.py workflow for the pinned mujoco_menagerie_aloha asset, '
                                 'or specify --mjcf PATH. No download or simulator switch is performed automatically.')
        return report
    report['menagerie'] = _finger_mjcf(mjcf)
    report['status'] = 'sources_compared_registration_pending'
    if scene.is_file():
        env = ET.parse(scene).getroot()
        table = env.find(".//geom[@name='table']")
        report['scene_table_collision'] = dict(table.attrib) if table is not None else None
    report['findings'] = [
        'Finger joint axis conventions differ and must be transformed through complete kinematic chains.',
        'MJCF finger actuator gains use MJCF position-servo conventions; they are not validated Modelica controller gains.',
        'ALOHA Menagerie includes two side-by-side follower arms; a facing leader/follower scene needs independently verified base transforms.',
        'Collision sites/meshes are useful geometric references but do not establish a valid Modelica grasp.',
    ]
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--urdf', type=Path, default=DEFAULT_URDF)
    p.add_argument('--mjcf', type=Path, default=DEFAULT_MJCF)
    p.add_argument('--scene', type=Path, default=DEFAULT_SCENE)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    result = audit(a.urdf, a.mjcf, a.scene)
    report = json.dumps(result, indent=2)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(report + '\n', encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()
