"""Error-detection experiment: mutations, scoring, ontology rules, API."""
from pathlib import Path

import pytest

from kkh.benchmark import detection as D
from kkh.domain.aloha import candidate as cand


def test_every_mutation_applies_exactly_and_changes_the_model():
    frozen = (D.FROZEN / D.CLASS_REL).read_text(encoding="utf-8")
    for m in D.MUTATIONS:
        out = m["apply"](frozen)
        assert (out == frozen) == (m["entity"] is None), m["id"]


def test_affirmation_filter_and_scoring():
    m = next(x for x in D.MUTATIONS if x["id"] == "M1-axis-sign")
    findings = [
        {"entity": "waist", "category": "joint_type", "explanation": "Axis (0,0,1) and n = {0,0,1}. Consistent."},
        {"entity": "elbow", "category": "joint_type", "explanation": "This is inconsistent because the axis is reversed."},
    ]
    assert D.is_affirmation(findings[0]) and not D.is_affirmation(findings[1])
    s = D.score(m, findings)
    assert s["detected"] is True and s["accepted_category"] is False  # localised, wrong category
    assert s["false_positives"] == 0 and s["strict_false_positives"] == 1 and s["affirmations_filtered"] == 1


def test_lift_recovers_declared_structure():
    g, _ = cand.lift(D.FROZEN / D.CLASS_REL, "unit-test")
    q = lambda p: len(list(g.triples((None, p, None))))
    assert q(cand.K.declaredAxis) == 9          # 9 movable joints
    assert q(cand.K.declaredParentComponent) == 13 and q(cand.K.declaredChildComponent) == 13
    assert q(cand.K.declaredMimicMultiplier) == 1


@pytest.mark.graphdb
@pytest.mark.parametrize("mid,category", [("M0-control", None), ("M3-unit-degrees", "unit"),
                                          ("M4-wrong-parent", "connectivity"), ("M6-mimic-sign", "mimic")])
def test_ontology_rules_against_graphdb(tmp_path, mid, category):
    from kkh.semantic.graphdb import GraphDB
    m = next(x for x in D.MUTATIONS if x["id"] == mid)
    f = tmp_path / "AlohaVX300s.mo"
    f.write_text(m["apply"]((D.FROZEN / D.CLASS_REL).read_text(encoding="utf-8")), encoding="utf-8")
    db = GraphDB()
    try:
        cand.publish_qudt_subset(db)
        r = cand.check(db, f, "pytest/" + mid)
        assert r["candidate_graph"] not in db.graphs()  # isolated graph removed afterwards
    finally:
        db.close()
    if category is None:
        assert r["findings"] == []
    else:
        assert [(x["category"], x["entity"]) for x in r["findings"]] == [(category, m["entity"])]


@pytest.mark.graphdb
def test_benchmark_api():
    from fastapi.testclient import TestClient
    from kkh.api.main import app
    c = TestClient(app)
    assert c.get("/api/benchmark").status_code == 200
    d = c.get("/api/benchmark/candidates/M8-origin-typo/diff").json()
    assert any(l.startswith("+") and "0.03}" in l for l in d["diff"])
    r = c.post("/api/benchmark/candidates/M8-origin-typo/check").json()
    assert r["C_RULE"]["accepted_category"] and r["DIFF"]["accepted_category"]
    assert c.get("/api/benchmark/candidates/nope/diff").status_code == 404
    ov = c.get("/api/overview").json()
    assert ov["totals"]["links"] == 29 and ov["graph"]["ok"]
