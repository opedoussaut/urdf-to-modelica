from pathlib import Path
from kkh.engineering.aloha_reference_audit import _finger_urdf, _finger_mjcf, audit


def test_gen7_finger_joint_conventions():
    p = Path(__file__).resolve().parents[1] / 'data/urdf/aloha_vx300s.urdf'
    finger = _finger_urdf(p)
    assert finger['left_finger']['range_m'] == [0.021, 0.057]
    assert finger['right_finger']['range_m'] == [-0.057, -0.021]
    assert finger['right_finger']['mimic']['multiplier'] == '-1'


def test_no_false_geometry_claim_without_source(tmp_path):
    p = Path(__file__).resolve().parents[1] / 'data/urdf/aloha_vx300s.urdf'
    result = audit(p, tmp_path / 'missing.xml')
    assert result['status'] == 'reference_not_available'
    assert all(v == 'NOT_VERIFIED' for v in result['engineering_gates'].values())


def test_menagerie_xml_extract(tmp_path):
    p = tmp_path / 'aloha.xml'
    p.write_text('''<mujoco><default><default class="finger"><position ctrlrange="0.002 0.037" kp="2000" kv="124"/><default class="left_finger"><joint range="0 0.041" axis="0 0 -1"/></default><default class="right_finger"><joint range="0 0.041" axis="0 0 -1"/></default></default></default></mujoco>''')
    values = _finger_mjcf(p)
    assert values['actuator']['command_range_m'] == [0.002, 0.037]
    assert values['fingers']['left_finger']['physical_range_m'] == [0, 0.041]
