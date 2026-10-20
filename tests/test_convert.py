"""Conversion comparison (kkh/convert): name matching, upload validation, prompt hygiene, retrieval, scorer."""
from pathlib import Path

import numpy as np
import pytest

from kkh.convert import llm, score, sources, urdfmodelica
from kkh.engineering.urdf_model import load_urdf

ROOT = Path(__file__).resolve().parents[1]
LEADER = ROOT / "data/urdf/aloha_wx250s.urdf"


def test_name_matching_is_lenient_but_specific():
    assert "baselink" in score.keys("aloha_wx250s/base_link")
    assert "alohawx250sbaselink" in score.keys("aloha_wx250s/base_link")
    assert score.norm("j_shoulder") == score.norm("shoulder") == "shoulder"
    assert score.norm("Aloha_wx250s_base_link") == "alohawx250sbaselink"
    assert score.norm("gripper") != score.norm("gripper_link")


def test_instances_prefer_link_frame_over_nested_body():
    names = ["m.arm.link1.body.frame_a.r_0[1]", "m.arm.link1.frame_a.r_0[1]", "m.arm.link2.body.frame_a.r_0[1]",
             "m.arm.j_elbow.revolute.phi", "m.arm.j_elbow.phi"]
    frames = score._instances(names, ".frame_a.r_0[1]")
    assert frames["link1"] == ("m.arm.link1.frame_a.r_0[1]", False)
    assert frames["link2"][1] is True  # only the nested body frame exists: flagged, excluded from kinematics
    assert score._instances(names, ".phi")["elbow"][0] == "m.arm.j_elbow.phi"


def test_upload_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "UPLOADS", tmp_path)
    with pytest.raises(ValueError, match=".urdf"):
        sources.store_upload("robot.xacro", b"<robot/>")
    with pytest.raises(ValueError, match="XML"):
        sources.store_upload("r.urdf", b"<robot><link")
    with pytest.raises(ValueError, match="URDF"):
        sources.store_upload("r.urdf", b"<html><link/></html>")
    with pytest.raises(ValueError, match="too large"):
        sources.store_upload("r.urdf", b"<robot>" + b" " * (sources.MAX_UPLOAD + 1) + b"</robot>")
    meta = sources.store_upload("leader.urdf", LEADER.read_bytes())
    assert meta["kind"] == "upload" and meta["graph"] is False and meta["joints"] == len(load_urdf(LEADER).joints)
    path, again = sources.resolve(meta["id"])
    assert path.read_bytes() == LEADER.read_bytes() and again["id"] == meta["id"]
    with pytest.raises(ValueError):
        sources.resolve("../../etc")


def test_prompt_text_keeps_physics_drops_geometry():
    text = sources.prompt_text(LEADER)
    assert "<inertial" in text and "<axis" in text and "<limit" in text and "<mimic" in text
    assert "<visual" not in text and "<collision" not in text and ".stl" not in text.lower()


def test_llm_output_parsing():
    reply = "<think>x</think>Here:\n```modelica\npackage R\n model RTest\n end RTest;\nend R;\n```\nDone."
    code = llm.extract_code(reply)
    assert code.startswith("package R") and "Done" not in code
    assert llm.model_names(code, "R") == "R.RTest"
    assert llm.package_name("aloha-wx250s") == "aloha_wx250s" and llm.package_name("2arm") == "R_2arm"


def test_urdfmodelica_preprocessing():
    text, applied = urdfmodelica.preprocess('<robot name="a-b"><link name="x/y"/><joint name="j-1"/></robot>')
    assert 'name="a_b"' in text and 'name="x_y"' in text and 'name="j_1"' in text
    assert applied == ["T1", "T3"]


def test_finish_ranks_simulating_models_first():
    failing = score.finish({"produced": True, "loads": True, "checks": True})
    running = score.finish({"produced": True, "loads": True, "checks": True, "simulates": True, "coverage": 0.5})
    assert running["rank_key"] > failing["rank_key"]
    assert [c["id"] for c in running["criteria"]] == ["produced", "loads", "checks", "simulates", "coverage", "kinematics", "parameters"]


@pytest.mark.omc
def test_retrieval_is_deterministic_and_excludes_answers():
    from kkh.convert import library_index as L
    robot = load_urdf(LEADER)
    a, b = L.retrieve_for(robot), L.retrieve_for(robot)
    assert [x["class"] for x in a] == [x["class"] for x in b]
    classes = {x["class"] for x in a}
    assert "Modelica.Mechanics.MultiBody.Joints.Revolute" in classes and "Modelica.Mechanics.MultiBody.Parts.Body" in classes
    assert all("generated/modelica" not in x["file"] and "third_party" not in x["file"] for x in a)


@pytest.mark.omc
@pytest.mark.slow
def test_urdfmodelica_mode_scores_from_real_run(tmp_path):
    r = urdfmodelica.convert(LEADER, tmp_path)
    assert r["converter_ok"], r.get("converter_log")
    s = score.score(LEADER, r["package_file"], r["model"], tmp_path)
    assert s["loads"] and s["checks"] and s["balanced"] and s["simulates"]
    assert s["coverage"] == 1.0 and s["parameters"]["axes_ok"] == s["parameters"]["axes_checked"] > 0
    # the converter does not enforce the URDF finger mimic: a real, measured kinematic gap on the right finger
    assert s["kinematics"]["max_position_error_mm"] > 1.0 and "right_finger" in s["kinematics"]["worst_link"][0]
