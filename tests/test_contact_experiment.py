"""Contract tests for the isolated Modelica-first experiment.

An actual numeric OpenModelica run is separately required before claiming physical validation.
"""
from pathlib import Path
import csv
import pytest

from kkh.engineering.contact_experiment import MODEL_DIR, mos_script, validate_result


def test_contact_model_has_unilateral_reaction_and_isolated_package():
    text = (MODEL_DIR / "CubeTableDrop.mo").read_text(encoding="utf-8")
    assert "normalForce = noEvent(if penetration > 0" in text
    assert "max(0, contactStiffness*penetration" in text
    assert "cubeMass*der(vz) = normalForce - cubeMass*gravity;" in text
    assert "no horizontal geometry" in text
    assert "ALOHA2" not in (MODEL_DIR / "package.mo").read_text(encoding="utf-8")


def test_omc_script_references_isolated_package():
    script = mos_script(MODEL_DIR / "package.mo")
    assert "loadFile(" in script
    assert "checkModel(GEN7Contact.CubeTableDrop)" in script
    assert 'outputFormat="csv"' in script


def test_contact_result_validation_rejects_tensile_force(tmp_path):
    p = tmp_path / "res.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["time", "z", "normalForce", "penetration"])
        for i in range(101):
            writer.writerow([i / 100, 0.12 if i < 50 else 0.019, -0.001 if i == 90 else (0 if i < 50 else 0.8), 0 if i < 50 else 0.001])
    with pytest.raises(ValueError, match="tensile"):
        validate_result(p)
