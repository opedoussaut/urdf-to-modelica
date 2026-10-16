"""ALOHA domain: manifest, scenarios, generated package completeness, full pipeline (slow)."""
import json

import numpy as np
import pytest

from kkh.domain.aloha import configuration as C
from kkh.domain.aloha.build import build
from kkh.domain.aloha.scenarios import check_limits, scenarios
from kkh.engineering.modelica_inspect import completeness


def test_manifest_totals():
    m = C.build_manifest()
    assert m["totals"] == {"links": 29, "joints": 28, "driven": 16, "mimic": 2}
    assert {a["model"] for a in m["arms"]} == {"aloha_vx300s"}
    assert m["leader"]["model"] == "aloha_wx250s"
    assert any("shoulder limit" in d["item"] for d in m["discrepancies"])


def test_scenarios_respect_urdf_limits():
    for name, sc in scenarios().items():
        assert check_limits(sc) == [], name
        assert np.array(sc["Q"]).shape[1] == (16 if sc["target"] == "assembly" else 8)


def test_generated_package_complete(tmp_path):
    rec = build(tmp_path)
    for model, cls in C.ARM_CLASS.items():
        rep = completeness(C.arm_robot(model), tmp_path / "ALOHA2" / "Arms" / f"{cls}.mo")
        assert rep["complete"], rep["issues"]
    mapping = json.loads((tmp_path / "aloha2_mapping.json").read_text())
    assert sum(len(a["links"]) for a in mapping["arms"]) == 28
    assert len(list((tmp_path / "ALOHA2" / "Resources" / "Meshes").rglob("*.stl"))) == 20
    assert rec["totals"]["driven"] == 16


@pytest.mark.omc
@pytest.mark.slow
def test_full_pipeline(tmp_path):
    from kkh.domain.aloha.pipeline import Pipeline
    rep = Pipeline("RightArmReach", log=lambda *_: None, run_dir=tmp_path).run()
    assert rep["success"], rep["steps"]
    v = rep["validation"]
    assert v["forward_kinematics"]["max_position_error_m"] < 1e-6
    assert v["limit_violations"] == []
    assert rep["results"]["n_moving_joints"] == 8


def test_crosscheck_against_official_mjcf():
    pytest.importorskip("mujoco")
    from kkh.domain.aloha.crosscheck import run
    r = run(n_configs=10, write=False)
    assert r["pass"], r["arms"]
