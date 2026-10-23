"""Stage 1 of the URDF -> Modelica workflow: deterministic conversion record (no OpenModelica needed)."""
import json

import pytest

from kkh.convert import urdfmodelica
from kkh.workflow import stage1_convert as s1

CONVERTER = urdfmodelica.UMO / "Resources" / "urdf_to_package.py"
needs_converter = pytest.mark.skipif(not CONVERTER.exists(), reason="pinned URDFModelica not fetched (tools/fetch_sources.py)")

LINK_RECORD = """record L
  extends URDFModelica.Records.Link(
name = "r_upper_link",
hasVisual = true,
hasCollision = false,
inertial = URDFModelica.Records.Inertial(origin = URDFModelica.Records.Origin(xyz = {0.02, 4e-10, 0.22},rpy = {0.0, 0.0, 1.5}),
mass = 0.79,
inertia = URDFModelica.Records.Inertia(ixx = 0.008,
ixy = 0.0,
ixz = -1e-05,
iyy = 0.009,
iyz = 0.0012,
izz = 0.0009)),
visual = URDFModelica.Records.Visual(origin = URDFModelica.Records.Origin(xyz = {9.0, 9.0, 9.0},rpy = {0.0, 0.0, 0.0}),
geometry = URDFModelica.Records.Geometry(filename = "package:_/pkg/meshes/upper.stl"),
material = URDFModelica.Records.Material(name = "black")));
end L;"""

JOINT_RECORD = """record J
  extends URDFModelica.Records.Joint(
name = "right_finger",
hasCalibration = false,
hasDynamics = true,
hasLimit = true,
hasMimic = true,
hasSafety_controller = false,
jointType = URDFModelica.Types.JointType.prismatic,
origin = URDFModelica.Records.Origin(xyz = {0.0, -0.01, 0.0},rpy = {0.0, 0.0, 0.0}),
parent = URDFModelica.Records.Parent(link = "r_fingers_link"),
child = URDFModelica.Records.Child(link = "r_right_finger_link"),
axis = URDFModelica.Records.Axis(xyz = {0.0, 1.0, 0.0}),
dynamics = URDFModelica.Records.Dynamics(damping = 0.1,friction = 0.2),
limit = URDFModelica.Records.Limit(lower = -0.057,
upper = -0.021,
effort = 5.0,
velocity = 1.0),
mimic = URDFModelica.Records.Mimic(joint = "left_finger",
multiplier = -1.0,
offset = 0.0));
end J;"""


def test_link_record_parsing_reads_the_inertial_not_the_visual_origin():
    g = s1.parse_link_record(LINK_RECORD)
    assert g["name"] == "r_upper_link" and g["mass"] == 0.79
    assert g["com"] == {"xyz": [0.02, 4e-10, 0.22], "rpy": [0.0, 0.0, 1.5]}
    assert g["inertia"] == {"ixx": 0.008, "ixy": 0.0, "ixz": -1e-05, "iyy": 0.009, "iyz": 0.0012, "izz": 0.0009}
    assert g["visual_mesh"] == "package:_/pkg/meshes/upper.stl" and g["has_collision"] is False


def test_joint_record_parsing():
    g = s1.parse_joint_record(JOINT_RECORD)
    assert (g["name"], g["type"], g["parent"], g["child"]) == ("right_finger", "prismatic", "r_fingers_link", "r_right_finger_link")
    assert g["axis"] == [0.0, 1.0, 0.0] and g["origin"]["xyz"] == [0.0, -0.01, 0.0]
    assert g["limit"] == {"lower": -0.057, "upper": -0.021, "effort": 5.0, "velocity": 1.0}
    assert g["dynamics"] == {"damping": 0.1, "friction": 0.2}
    assert g["has_mimic"] is True and g["mimic"] == {"joint": "left_finger", "multiplier": -1.0, "offset": 0.0}


def test_value_comparison_is_exact_up_to_float_formatting():
    assert s1._close(0.1, 0.1 + 1e-12) and not s1._close(0.1, 0.1001)
    assert s1._close([0, 1.5707963267948966, 0], [0.0, 1.5707963267948966, 0.0])
    assert not s1._close([0, 0, 1], [0, 1, 0]) and not s1._close(1.0, None) and s1._close(None, None)
    assert s1.converted_name("arm/upper-link") == "arm_upper_link"


def test_recorded_but_unused_feature_is_reported(tmp_path):
    """A mimic written into the record but never referenced by the joint model is an explicit finding."""
    (tmp_path / "Joints").mkdir()
    (tmp_path / "Joints" / "Right_fingerParams.mo").write_text(JOINT_RECORD, encoding="utf-8")
    (tmp_path / "Joints" / "Right_finger.mo").write_text("model Right_finger\n  parameter Right_fingerParams jointParams;\nend Right_finger;", encoding="utf-8")
    mapping = [{"kind": "joint", "urdf_name": "right_finger", "params_file": "Joints/Right_fingerParams.mo",
                "model_file": "Joints/Right_finger.mo"}]
    items = s1.unsupported(tmp_path / "x.urdf", None, mapping, tmp_path, ["T1"], 'Unknown tag "ros2_control" in /robot')
    kinds = {(i["feature"], i["effect"]) for i in items}
    assert ("mimic", "recorded in the parameter record but not used by the joint model") in kinds
    assert ("ros2_control", "ignored by the converter") in kinds and ("T1", "transformed before conversion") in kinds


@needs_converter
def test_stage1_on_aloha_follower_is_reproducible_and_complete(tmp_path):
    m = s1.run("aloha_vx300s", tmp_path, log=lambda *_: None)
    assert m["ok"] and m["reproducibility"]["identical"] and m["reproducibility"]["files_compared"] > 50
    assert m["versions"]["converter_head_matches_pin"]
    s = m["summary"]
    assert s["mapped_links"] == m["source"]["links"] and s["mapped_joints"] == m["source"]["joints"] and not s["unmapped"]
    # the converter copies every URDF value into its records unchanged (measured: 255 values, 0 differences)
    assert s["physical_values_compared"] > 200 and s["physical_mismatches"] == 0
    assert m["assets"]["count"] == m["assets"]["resolved"] > 0 and all(a["sha256"] for a in m["assets"]["files"])
    unsup = json.loads((tmp_path / "stage1" / "unsupported.json").read_text(encoding="utf-8"))
    assert any(i["feature"] == "mimic" and i["entity"] == "right_finger" for i in unsup)
    assert any(i["feature"] == "ros2_control" for i in unsup)
    mapping = json.loads((tmp_path / "stage1" / "mapping.json").read_text(encoding="utf-8"))
    elbow = next(x for x in mapping if x["urdf_name"] == "elbow")
    assert elbow["instance"] == "elbow" and elbow["params_file"] == "Joints/ElbowParams.mo"
