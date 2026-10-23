"""Stage 2 of the URDF -> Modelica workflow: ordered OpenModelica checks and the machine-readable diagnostic record."""
import json

import pytest

from kkh.convert import urdfmodelica
from kkh.engineering import omc
from kkh.workflow import stage1_convert as s1
from kkh.workflow import stage2_check as s2

# Recorded OpenModelica simulation output (ALOHA follower test model, 2026-10-23), shortened paths.
SIM_LOG = (
    "LOG_ASSERT        | warning | [C:/x/URDFModelica/Examples/Aloha_vx300s/Joints/Left_finger.mo:36:3-36:85:writable]\n"
    "|                 | |       | The following assertion has been violated during initialization at time 0.000000\n"
    "|                 | |       | ((not aloha_vx300sRun.aloha_vx300s.left_finger.posLimitLow.y)) --> \"Joint position over low limit\"\n"
    "LOG_ASSERT        | warning | [C:/x/URDFModelica/Examples/Aloha_vx300s/Joints/Right_finger.mo:35:3-35:87:writable]\n"
    "|                 | |       | The following assertion has been violated at time 1.250000\n"
    "|                 | |       | ((not aloha_vx300sRun.aloha_vx300s.right_finger.speedLimitHigh.y)) --> \"Joint speed over high limit\"\n"
    "LOG_SUCCESS       | info    | The simulation finished successfully.\n")


def test_every_omc_class_maps_to_a_mission_category():
    assert {c for c, _ in omc.ERROR_CLASSES} | {"other"} == set(s2.OMC_CLASS_TO_CATEGORY)
    assert set(s2.OMC_CLASS_TO_CATEGORY.values()) <= set(s2.CATEGORIES)
    assert s2.category_of("Class Modelica.Mechanics.MultiBody.Parts.Foo not found in scope") == "missing class or library"
    assert s2.category_of("Parse error: Missing token") == "syntax and translation"
    assert s2.category_of("Inconsistent unit: rad vs deg") == "type and unit"
    assert s2.category_of("Too many equations, over-determined system") == "connector and equation"
    assert s2.category_of("The initial conditions are not fully specified.") == "initialization and numerical"


def test_assertions_are_parsed_per_instance_with_location_and_time():
    a = s2.parse_assertions(SIM_LOG)
    assert [x["instance"].split(".")[-1] for x in a] == ["left_finger", "right_finger"]
    assert a[0]["when"] == "during initialization" and a[1]["when"] == "1.250000"
    assert a[0]["text"] == "Joint position over low limit" and a[0]["line"] == 36 and a[0]["file"].endswith("Left_finger.mo")


def test_expected_warnings_are_kept_as_info_and_repeats_become_one_finding():
    d = s2.Diagnostics()
    world = {"level": "warning", "kind": "translation", "omc_id": "379",
             "msg": "The model can't be instantiated due to top-level outer element 'world'"}
    init = {"level": "warning", "kind": "translation", "omc_id": "496", "msg": "The initial conditions are not fully specified."}
    d.omc("structure", "structure", [], [world, init], None, blocking=True)
    d.omc("simulation", "simulation", [], [init], None, blocking=True)
    assert len(d.items) == 2
    w, i = d.items
    assert w["severity"] == "info" and "expected" in w["evidence"] and not w["blocking"]
    assert i["severity"] == "warning" and i["also_in"] == ["simulation"]


def test_parsed_errors_block_and_keep_their_location(tmp_path):
    d = s2.Diagnostics()
    parsed = omc.parse_messages(f"[{tmp_path / 'P' / 'M.mo'}:12:5-12:40:writable] Error: Class Foo not found in scope M.")
    d.omc("load", "load", parsed, [], tmp_path, blocking=True)
    (f,) = d.items
    assert f["severity"] == "error" and f["blocking"] and f["category"] == "missing class or library"
    assert (f["file"], f["line"], f["col"]) == ("P/M.mo", 12, 5)


def test_findings_on_the_same_entity_are_cross_referenced():
    d = s2.Diagnostics()
    d.add("conversion", "stage1", "unsupported URDF element", "warning", "mimic: recorded but unused", entity="right_finger")
    d.add("urdf_consistency", "kinematics", "mechanical or kinematic inconsistency", "error", "52 mm", entity="right_finger")
    d.add("graphics", "lines", "graphical annotation", "warning", "no Line", entity="Aloha_vx300s")
    s2._relate(d.items)
    assert d.items[0]["related"] == ["D002"] and d.items[1]["related"] == ["D001"] and "related" not in d.items[2]


def test_unknown_category_is_rejected():
    with pytest.raises(AssertionError):
        s2.Diagnostics().add("load", "load", "made-up category", "error", "x")


@pytest.mark.omc
@pytest.mark.slow
@pytest.mark.skipif(not (urdfmodelica.UMO / "Resources" / "urdf_to_package.py").exists(), reason="pinned URDFModelica not fetched")
def test_stage2_on_aloha_follower_measures_the_known_mimic_gap(tmp_path):
    s1.run("aloha_vx300s", tmp_path, check_reproducible=False, log=lambda *_: None)
    r = s2.run(tmp_path, log=lambda *_: None)
    st = r["steps"]
    assert [st[k]["state"] for k in ("load", "structure", "balance_translation", "simulation")] == ["pass"] * 4
    assert st["balance_translation"]["equations"] == st["balance_translation"]["variables"]
    # compiling and simulating is not validation: the unused URDF mimic moves the right finger off the URDF
    assert r["verdict"] == "simulates, engineering checks fail"
    kin = [f for f in r["findings"] if f["check"] == "kinematics"]
    assert kin and kin[0]["entity"] == "right_finger" and kin[0]["severity"] == "error"
    mimic = next(f for f in r["findings"] if f["step"] == "conversion" and f["entity"] == "right_finger")
    assert kin[0]["id"] in mimic["related"]
    assert st["graphics"]["totals"]["connections"] > 0
    assert json.loads((tmp_path / "stage2" / "diagnostics.json").read_text(encoding="utf-8"))["schema"] == s2.SCHEMA
