"""Review scoring (kkh/convert/review_score.py): ground truth, matching, corrections, faithfulness, calibration.
Fast: seeded files use the deterministic URDF<->Modelica comparison, no OpenModelica and no LLM."""
from pathlib import Path

import pytest

from kkh.convert import review, review_score as RS, sources

M1 = {"kind": "seeded", "mutation": "M1-axis-sign"}


def _issue(entity, category, confidence=0.9, component="", parameter="", value=()):
    return {"entity": entity, "category": category, "evidence": "differs from the URDF", "confidence": confidence,
            "correction": {"component": component, "parameter": parameter, "value": list(value)}}


@pytest.fixture(autouse=True)
def isolated_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "RUNS", tmp_path)
    monkeypatch.setattr(review, "SEEDED", tmp_path / "seeded")


def test_seeded_ground_truth_and_hidden_from_reviewer():
    truth = RS.ground_truth(M1)
    assert [(d["entity"], d["category"]) for d in truth] == [("elbow", "axis")]
    assert RS.ground_truth({"kind": "seeded", "mutation": "M0-control"}) == []
    files, urdf, ctx = review.target_files(M1)
    text = review.model_text(files)
    assert "{0, -1.0, 0}" in text  # the seeded error is in the file the reviewer reads ...
    assert "axis-sign" not in text and "M1" not in text and "flipped" not in text.lower()  # ... but nothing reveals it


def test_correct_review_with_working_correction():
    rep = {"issues": [_issue("elbow", "axis", 0.9, "j_elbow", "n", (0, 1, 0))],
           "claims": [{"entity": "elbow", "property": "axis", "value": [0, 1, 0]},
                      {"entity": "shoulder", "property": "upper_limit", "value": [72]}]}
    s = RS.score_review(M1, rep)
    assert s["recall"] == 1.0 and s["precision"] == 1.0 and s["false_alarms"] == 0
    assert s["corrections_fixed"] == 1 and s["corrections"][0]["new_problems"] == []
    assert s["faithfulness"]["checked"] == 2 and s["faithfulness"]["correct"] == 1  # 72 rad is not the URDF limit
    assert s["brier"] == pytest.approx(0.01)


def test_wrong_review_and_harmful_correction():
    s = RS.score_review(M1, {"issues": [_issue("wrist_angle", "unit", 0.8, "j_wrist_angle", "q_max", (1,))], "claims": []})
    assert s["recall"] == 0.0 and s["precision"] == 0.0 and s["false_alarms"] == 1
    assert s["corrections_fixed"] == 0 and s["corrections"][0]["new_problems"] == ["wrist_angle"]
    assert s["brier"] == pytest.approx(0.64)


def test_right_place_wrong_kind_and_affirmations():
    rep = {"issues": [_issue("elbow", "limit"), {**_issue("shoulder", "axis"), "evidence": "axis is consistent with the URDF"}], "claims": []}
    s = RS.score_review(M1, rep)
    assert s["found"] == 1 and s["found_type"] == 0 and s["affirmations_filtered"] == 1


def test_apply_correction_paths():
    texts = {"a.mo": 'model R\n  J j_elbow(r = {0, 0, 0.3}, n = {0, -1.0, 0}, q_max = 1.6);\nend R;\n',
             "ElbowParams.mo": 'record ElbowParams\n extends X(axis = URDFModelica.Records.Axis(xyz = {0.0, -1.0, 0.0}),\n limit = L(lower = -2.0, upper = 1.6));\nend ElbowParams;\n'}
    k, t = RS.apply_correction(texts, {"component": "j_elbow", "parameter": "n", "value": [0, 1, 0]})
    assert k == "a.mo" and "n = {0, 1, 0}" in t and "q_max = 1.6" in t
    k, t = RS.apply_correction(texts, {"component": "ElbowParams", "parameter": "axis.xyz", "value": [0, 1, 0]})
    assert k == "ElbowParams.mo" and "xyz = {0, 1, 0}" in t
    k, t = RS.apply_correction(texts, {"component": "ElbowParams", "parameter": "limit.upper", "value": [1.7]})
    assert "upper = 1.7" in t and "lower = -2.0" in t
    for bad in ({"component": "j_wrist", "parameter": "n", "value": [1]}, {"component": "j_elbow", "parameter": "m", "value": [1]},
                {"component": "", "parameter": "n", "value": [1]}):
        with pytest.raises(ValueError):
            RS.apply_correction(texts, bad)


def test_validate_report_normalises_input():
    rep = review.validate_report({"issues": [{"entity": "elbow", "category": "nonsense", "confidence": 7, "correction": None}],
                                  "claims": [{"entity": "elbow", "property": "colour", "value": [1]}]})
    assert rep["issues"][0]["category"] == "other" and rep["issues"][0]["confidence"] == 1.0 and rep["claims"] == []
