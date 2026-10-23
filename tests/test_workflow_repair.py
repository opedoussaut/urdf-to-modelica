"""Stages 3-6 of the URDF -> Modelica workflow: the parts that decide fairness and safety (no LLM, no OpenModelica)."""
import pytest

from kkh.workflow import layout, review as R, stage3_repair as s3, stage4_validate as s4


def _pkg(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def test_edits_apply_only_inside_the_package_and_only_on_an_exact_single_match(tmp_path):
    pkg = _pkg(tmp_path / "P", {"A.mo": "model A\n  Real x = 1;\n  Real y = 1;\nend A;", "B.mo": "x"})
    (tmp_path / "outside.mo").write_text("secret", encoding="utf-8")
    r = s3.apply_edits(pkg, [
        {"file": "A.mo", "search": "Real x = 1;", "replace": "Real x = 2;"},
        {"file": "A.mo", "search": "= 1;", "replace": "= 3;"},          # now matches once (y) -> applied
        {"file": "A.mo", "search": "Real z", "replace": "Real w"},      # not found
        {"file": "../outside.mo", "search": "secret", "replace": "x"},  # outside the package
        {"file": "B.mo", "search": "x", "replace": "x"},               # no change
    ])
    assert [x["applied"] for x in r] == [True, True, False, False, False]
    assert (pkg / "A.mo").read_text() == "model A\n  Real x = 2;\n  Real y = 3;\nend A;"
    assert (tmp_path / "outside.mo").read_text() == "secret"


def test_invented_citations_are_flagged():
    edits = [{"n": 1, "cites": ["msl:A", "made:up"]}, {"n": 2, "cites": []}]
    assert s3.check_citations(edits, {"msl:A"}) == [{"edit": 1, "invented": ["made:up"]}]
    assert s3.check_citations(edits, set()) == [{"edit": 1, "invented": ["msl:A", "made:up"]}]


def test_both_arms_get_the_same_findings_without_cosmetic_ones():
    fs = [{"id": "D1", "severity": "warning", "step": "conversion", "message": "visual mesh URI: rewritten"},
          {"id": "D2", "severity": "warning", "step": "graphics", "message": "no Line"},
          {"id": "D3", "severity": "info", "step": "structure", "message": "world"},
          {"id": "D4", "severity": "warning", "step": "simulation", "message": "assertion"},
          {"id": "D5", "severity": "error", "step": "urdf_consistency", "message": "52 mm"}]
    assert [f["id"] for f in s3.in_scope(fs)] == ["D5", "D4"]
    assert s3.settings_digest("m") == s3.settings_digest("m") != s3.settings_digest("other")


def test_findings_are_matched_without_their_numbers():
    a = {"step": "urdf_consistency", "check": "kinematics", "category": "c", "entity": "x.right_finger", "message": "off by 52.9 mm", "severity": "error"}
    b = dict(a, message="off by 12.1 mm", entity="right_finger")
    c = dict(a, entity="left_finger")
    r = s4.compare_findings([a], [b, c])
    assert (r["initial"], len(r["resolved"]), len(r["remaining"]), len(r["new"])) == (1, 0, 1, 1)


def test_findings_match_across_copies_that_live_in_different_folders():
    a = {"step": "load", "check": "load", "category": "c", "entity": None,
         "message": "Missing token in E:/x/runs/w/repair/F01/ai_only/ws/URDFModelica/Examples/A/Joints/Elbow.mo:5"}
    b = dict(a, message="Missing token in E:\\x\\faults\\F01\\ws\\Joints\\Elbow.mo:5")
    c = dict(a, message="Missing token in E:/y/Shoulder.mo:5")
    assert s4.key(a) == s4.key(b) != s4.key(c)
    assert "Elbow.mo" in s4.key(a)[-1]


def test_integrity_guard_flags_shortcuts(tmp_path):
    orig = _pkg(tmp_path / "o", {"M.mo": "model M\n  Joints.Elbow elbow(i = 1);\nequation\n  assert(x, \"a\");\n  connect(a, b) annotation(Line(points={{0,0},{1,1}}));\nend M;",
                                 "N.mo": "model N\n  Real q annotation(Placement(transformation(origin={0,0})));\nend N;", "Gone.mo": "x"})
    cand = _pkg(tmp_path / "c", {"M.mo": "model M\nequation\n  connect(a, b) annotation(Line(points={{0,0},{1,1}}));\nend M;",
                                 "N.mo": "model N\n  Real q annotation(Placement(transformation(origin={9,9})));\nend N;", "New.mo": "y"})
    rec = {"step": "records", "check": "record.mass", "category": "mechanical or kinematic inconsistency", "entity": "upper_arm_link",
           "message": "mass in the parameter record differs from the URDF", "severity": "error", "evidence": "{}"}
    flags = {f["flag"] for f in s4.integrity(orig, cand, {"findings": []}, {"findings": [rec]})}
    assert {"file deleted", "file added", "assertion removed", "component removed", "annotation-only edit", "URDF value changed"} <= flags


def test_annotation_only_check_ignores_whitespace():
    assert s4._strip_annotations("connect(a, b);") == s4._strip_annotations("connect(a, b)\n    annotation (Line(points = {{0, 0}}));")


def test_candidate_keys_are_strict(tmp_path):
    for ok in ("original", "fault/F03", "repair/natural/ai_only", "review/F04/accepted-ai-assets-2", "approved/3"):
        R.ws_of(tmp_path, ok)
    for bad in ("../x", "repair/natural/other", "review/natural/../../x", "approved/x", "fault/F3"):
        with pytest.raises(ValueError):
            R.ws_of(tmp_path, bad)


def test_layout_routes_are_orthogonal():
    pts = layout.route((-55.0, 70.0), (-40.0, 100.0))
    assert pts == [[-55.0, 70.0], [-47.5, 70.0], [-47.5, 100.0], [-40.0, 100.0]]
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(pts, pts[1:]))
    assert layout._component("rotational_flange_a[3]") == "rotational_flange_a" and layout._component("elbow.flange_a") == "elbow"
