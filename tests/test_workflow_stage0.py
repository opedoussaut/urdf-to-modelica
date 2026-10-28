"""Stage 0, URDF compliance: valid files pass; each single, deliberate violation is caught by the rule that names it."""
import pytest

from kkh.convert import sources
from kkh.workflow import stage0_urdf as S0

GOOD = """<?xml version="1.0"?>
<robot name="arm">
  <material name="grey"><color rgba="0.5 0.5 0.5 1"/></material>
  <link name="base">
    <inertial><origin xyz="0 0 0.05"/><mass value="1.0"/><inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/></inertial>
    <visual><geometry><box size="0.1 0.1 0.1"/></geometry><material name="grey"/></visual>
  </link>
  <link name="upper">
    <inertial><mass value="0.5"/><inertia ixx="0.004" ixy="0" ixz="0" iyy="0.004" iyz="0" izz="0.0005"/></inertial>
    <collision><geometry><cylinder radius="0.02" length="0.3"/></geometry></collision>
  </link>
  <link name="lower">
    <inertial><mass value="0.3"/><inertia ixx="0.002" ixy="0" ixz="0" iyy="0.002" iyz="0" izz="0.0003"/></inertial>
  </link>
  <joint name="shoulder" type="revolute">
    <origin xyz="0 0 0.1" rpy="0 0 0"/><parent link="base"/><child link="upper"/>
    <axis xyz="0 1 0"/><limit lower="-1.5" upper="1.5" effort="5" velocity="2"/>
  </joint>
  <joint name="elbow" type="revolute">
    <origin xyz="0 0 0.3"/><parent link="upper"/><child link="lower"/>
    <axis xyz="0 1 0"/><limit lower="-2" upper="2" effort="3" velocity="2"/>
  </joint>
</robot>
"""


def _check(tmp_path, text):
    f = tmp_path / "r.urdf"
    f.write_text(text, encoding="utf-8")
    return S0.check(f)


def _rules(rec, severity=None):
    return {x["rule"] for x in rec["findings"] if severity is None or x["severity"] == severity}


def test_good_file_is_compliant(tmp_path):
    rec = _check(tmp_path, GOOD)
    assert rec["verdict"] == "compliant" and not rec["blocking"], rec["findings"]
    assert rec["structure"] == {"links": 3, "joints": 2, "roots": ["base"], "movable_joints": 2}


@pytest.mark.parametrize("old,new,rule,verdict", [
    ('<robot name="arm">', "<robot>", "robot-name", "not compliant"),
    ('type="revolute">\n    <origin xyz="0 0 0.1"', 'type="hinge">\n    <origin xyz="0 0 0.1"', "joint-type", "not compliant"),
    ('<axis xyz="0 1 0"/><limit lower="-1.5" upper="1.5" effort="5" velocity="2"/>', '<axis xyz="0 1 0"/>', "limit-required", "not compliant"),
    ('effort="5" velocity="2"', 'velocity="2"', "limit-effort", "not compliant"),
    ('<child link="lower"/>', '<child link="forearm"/>', "link-exists", "not compliant"),
    ('<parent link="upper"/><child link="lower"/>', '<parent link="upper"/><child link="upper"/>', "no-self-joint", "not compliant"),
    ('<origin xyz="0 0 0.3"/>', '<origin xyz="0 0.3"/>', "xyz-format", "not compliant"),
    ('rgba="0.5 0.5 0.5 1"', 'rgba="128 128 128 255"', "color-rgba", "not compliant"),
    ('<box size="0.1 0.1 0.1"/>', '<box size="0.1"/>', "box-size", "not compliant"),
    ('<mass value="0.3"/>', '<mass value="0.3"/><!-- -->', None, "compliant"),
    ('lower="-2" upper="2"', 'lower="2" upper="-2"', "limits-ordered", "physically implausible"),
    ('ixx="0.002" ixy="0" ixz="0" iyy="0.002" iyz="0" izz="0.0003"', 'ixx="0.001" ixy="0" ixz="0" iyy="0.001" iyz="0" izz="0.01"',
     "inertia-triangle", "physically implausible"),
    ('ixx="0.002" ixy="0" ixz="0"', 'ixx="0.002" ixy="0.01" ixz="0"', "inertia-positive-definite", "physically implausible"),
    ('<mass value="0.5"/>', '<mass value="-0.5"/>', "mass-positive", "physically implausible"),
])
def test_each_violation_is_caught(tmp_path, old, new, rule, verdict):
    assert old in GOOD
    rec = _check(tmp_path, GOOD.replace(old, new, 1))
    assert rec["verdict"] == verdict, rec["findings"]
    if rule:
        assert rule in _rules(rec, "error"), rec["findings"]
        hit = next(x for x in rec["findings"] if x["rule"] == rule)
        assert hit["line"] and hit["source"].startswith(("https://wiki.ros.org/urdf/XML", "rigid-body"))


def test_tree_rules(tmp_path):
    two_parents = GOOD.replace("</robot>", '<joint name="extra" type="fixed"><parent link="base"/><child link="lower"/></joint></robot>')
    assert "one-parent" in _rules(_check(tmp_path, two_parents), "error")
    orphan = GOOD.replace("</robot>", '<link name="loose"/></robot>')
    rec = _check(tmp_path, orphan)
    assert "single-root" in _rules(rec, "error") and rec["structure"]["roots"] == ["base", "loose"]
    cycle = GOOD.replace('<parent link="base"/><child link="upper"/>', '<parent link="lower"/><child link="upper"/>')
    assert "no-cycle" in _rules(_check(tmp_path, cycle), "error")


def test_warnings_and_info_do_not_block(tmp_path):
    rec = _check(tmp_path, GOOD.replace('<axis xyz="0 1 0"/><limit lower="-2"', '<axis xyz="0 2 0"/><limit lower="-2"'))
    assert rec["verdict"] == "compliant with warnings" and not rec["blocking"]
    assert "axis-normalized" in _rules(rec, "warning")
    rec = _check(tmp_path, GOOD.replace("</robot>", "<gazebo/><sensor_proposal/></robot>"))
    assert rec["verdict"] == "compliant" and "custom-element" in _rules(rec, "info")


def test_mimic_and_malformed_xml(tmp_path):
    mim = GOOD.replace('<axis xyz="0 1 0"/><limit lower="-2"', '<mimic joint="wrist"/><axis xyz="0 1 0"/><limit lower="-2"')
    assert "mimic-exists" in _rules(_check(tmp_path, mim), "error")
    rec = _check(tmp_path, GOOD.replace("</robot>", ""))
    assert rec["verdict"] == "not compliant" and "xml-well-formed" in _rules(rec)


@pytest.mark.parametrize("source", list(sources.PINNED))
def test_pinned_robots_are_compliant(source):
    urdf = sources.resolve(source)[0]
    if not urdf.exists():
        pytest.skip("pinned source not fetched")
    from kkh.convert.robot3d import resolve_mesh
    rec = S0.check(urdf, resolve_mesh)
    if source == "themis":
        # Known fact about Westwood's published TH02-A7 file (26-28 Oct 2026): two thumb inertias rounded to zero by the
        # exporter, and every joint limit / effort / velocity left at 0. If the vendor file changes, this test says so.
        assert rec["verdict"] == "physically implausible"
        assert sorted(x["entity"] for x in rec["findings"] if x["blocking"]) == ["THUMB_MIDDLE_L", "THUMB_MIDDLE_R"]
        assert sum(x["rule"] == "effort-positive" for x in rec["findings"]) == 44
        return
    assert not rec["blocking"], [x for x in rec["findings"] if x["blocking"]]


def test_stage1_refuses_a_non_compliant_urdf(tmp_path, monkeypatch):
    from kkh.convert import urdfmodelica
    from kkh.workflow import stage1_convert as S1
    bad = tmp_path / "bad.urdf"
    bad.write_text(GOOD.replace('type="revolute">\n    <origin xyz="0 0 0.1"', 'type="hinge">\n    <origin xyz="0 0 0.1"', 1), encoding="utf-8")
    monkeypatch.setattr(S1.sources, "resolve", lambda s: (bad, {"label": "bad"}))
    called = []
    monkeypatch.setattr(urdfmodelica, "convert", lambda *a, **k: called.append(1) or {})
    m = S1.run("bad", out=tmp_path / "run", check_reproducible=False, log=lambda *_: None)
    assert m["ok"] is False and m["compliance"] == "not compliant" and "joint type" in m["error"] and not called
    assert (tmp_path / "run" / "stage0" / "compliance.json").exists()
