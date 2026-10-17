"""Pure offline validation of experiment contract; not physics verification."""
from pathlib import Path
from kkh.engineering.grasp_experiment import mos_script, validate_result
import csv
import pytest


def test_modelica_source_declares_real_forces():
    source = (Path(__file__).resolve().parents[1] /
              "engineering/modelica/GEN7Contact/TwoFingerGrasp.mo").read_text()
    assert "cubeMass*der(vz) = tableNormal + gripVerticalForce - cubeMass*gravity" in source
    assert "Modelica.Math.tanh" in source
    assert "leftNormal - rightNormal" in source
    assert "twoSidedContact" in source


def test_mos_targets_new_model(tmp_path):
    script = mos_script(tmp_path / "package.mo")
    assert "checkModel(GEN7Contact.TwoFingerGrasp)" in script
    assert 'outputFormat="csv"' in script


def test_invalid_csv_rejected(tmp_path):
    result = tmp_path / "bad.csv"
    with result.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "z"])
        writer.writeheader()
        writer.writerows([{"time": i*.001, "z": 0.02} for i in range(501)])
    with pytest.raises(ValueError, match="x"):
        validate_result(result)


def test_friction_limits_are_exported_and_validator_does_not_require_constant_parameter():
    model = (Path(__file__).resolve().parents[1] /
             "engineering/modelica/GEN7Contact/TwoFingerGrasp.mo").read_text()
    assert "leftFrictionLimit = frictionCoefficient*leftNormal;" in model
    assert "rightFrictionLimit = frictionCoefficient*rightNormal;" in model
    source = (Path(__file__).resolve().parents[1] /
              "kkh/engineering/grasp_experiment.py").read_text()
    assert 'col("leftFrictionLimit")' in source
    assert 'col("rightFrictionLimit")' in source
    assert 'col("frictionCoefficient")' not in source
