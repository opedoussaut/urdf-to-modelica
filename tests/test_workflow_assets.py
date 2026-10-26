"""Increment 3: governed Modelica knowledge collection (provenance, licences, exclusions, deterministic retrieval)."""
import json
from pathlib import Path

import pytest

from kkh.workflow import assets as A

FIELDS = {"id", "asset_id", "version", "licence", "class", "kind", "source_path", "line_start", "line_end",
          "file_sha256", "text"}

LIB = '''within Lib.Sub;
package P "A package"
  model M "Model with documentation"
    parameter Real k = 1 "Gain";
    Modelica.Blocks.Interfaces.RealInput u "Input" annotation (Placement(transformation(extent={{-10,-10},{10,10}})));
  equation
    if k > 0 then
      y = k*u;
    end if;
    annotation (Documentation(info="<html><p>Shows <b>model M</b>; code inside text: model Fake end Fake;</p></html>"));
  end M;
  type Angle = Real(unit="rad") "Short class";
  package Examples "Examples"
    model Demo "Demo"
      M m;
      M n;
    equation
      connect(m.y, n.u) annotation (Line(points={{0,0},{10,0}}, color={0,0,127}));
    end Demo;
  end Examples;
end P;
'''


def _asset(i="test-lib"):
    return {"id": i, "version": "1.0", "licence": "Modelica 3-Clause BSD (test)"}


def test_parser_handles_nesting_short_classes_and_code_inside_strings(tmp_path):
    found, _ = A.classes(LIB)
    names = [c["full"] for c in found]
    assert names == ["Lib.Sub.P", "Lib.Sub.P.M", "Lib.Sub.P.Angle", "Lib.Sub.P.Examples", "Lib.Sub.P.Examples.Demo"]
    assert "Fake" not in " ".join(names)  # a class name inside a documentation string is not a class


def test_chunks_carry_full_provenance_docs_and_example_patterns(tmp_path):
    f = tmp_path / "P.mo"
    f.write_text(LIB, encoding="utf-8")
    chunks = {c["class"]: c for c in A.chunks_of_file(f, tmp_path, _asset(), "abc")}
    for c in chunks.values():
        assert FIELDS <= set(c) and c["licence"] and c["version"] == "1.0" and c["file_sha256"] == "abc"
        assert c["id"] == f"test-lib:{c['class']}" and 1 <= c["line_start"] <= c["line_end"]
    m = chunks["Lib.Sub.P.M"]
    assert 'parameter Real k = 1 "Gain";' in m["text"] and "Placement" not in m["text"]  # annotations stripped
    assert "Shows model M" in m["text"]  # documentation HTML -> text
    assert chunks["Lib.Sub.P.M"]["line_start"] == 3 and chunks["Lib.Sub.P.M"]["line_end"] == 11
    demo = chunks["Lib.Sub.P.Examples.Demo"]["text"]
    assert "connect(m.y, n.u)" in demo and "annotation (Line( points={{0,0},{10,0}}" in demo.replace("(Line(", "(Line( ")


def test_patterns_have_front_matter_provenance(tmp_path):
    files = sorted(A.PATTERNS.glob("*.md"))
    assert len(files) >= 5
    a = _asset("project-patterns")
    for f in files:
        c = A.pattern_chunk(f, a, "x")
        assert c["kind"] == "pattern" and c["provenance"]["commit"] and c["provenance"]["evidence"]
    (tmp_path / "bare.md").write_text("# no front matter\n", encoding="utf-8")
    (tmp_path / "partial.md").write_text("---\nid: x\ntitle: y\n---\nbody\n", encoding="utf-8")
    for name in ("bare.md", "partial.md"):  # missing front matter, missing source/commit/evidence
        with pytest.raises(ValueError):
            A.pattern_chunk(tmp_path / name, a, "x")


def test_excluded_sources_are_refused(tmp_path):
    for p in ("third_party/urdfmodelica/URDFModelica/Joints/Revolute.mo", "generated/modelica/ALOHA2/package.mo",
              "third_party/ref/aloha/Model.mo"):
        assert A._excluded(Path(p))
    assert not A._excluded(Path("C:/libs/Modelica 4.1.0+maint.om/Mechanics/MultiBody/World.mo"))
    ref = tmp_path / "third_party" / "ref"
    ref.mkdir(parents=True)
    (ref / "X.mo").write_text("model X end X;", encoding="utf-8")
    assert A._files(tmp_path, ["third_party"]) == []


def test_unlicensed_library_is_refused(tmp_path):
    (tmp_path / "package.mo").write_text('package L "no licence text" end L;', encoding="utf-8")
    with pytest.raises(ValueError, match="no verified licence"):
        A._licence(tmp_path)


def _tiny_index(tmp_path):
    f = tmp_path / "P.mo"
    f.write_text(LIB, encoding="utf-8")
    chunks = sorted(A.chunks_of_file(f, tmp_path, _asset(), "abc"), key=lambda c: c["id"])
    toks = [A._doc_tokens(c) for c in chunks]
    from collections import Counter
    return {"chunks": chunks, "tokens": toks, "df": dict(Counter(t for ts in toks for t in set(ts))), "n": len(chunks),
            "avgdl": sum(map(len, toks)) / len(toks)}


def test_search_is_deterministic_filterable_and_query_for_uses_the_finding(tmp_path):
    idx = _tiny_index(tmp_path)
    a = [h["id"] for h in A.search("connect line example demo model", k=5, index=idx)]
    b = [h["id"] for h in A.search("connect line example demo model", k=5, index=idx)]
    assert a == b and a[0] == "test-lib:Lib.Sub.P.Examples.Demo"
    assert all(h["kind"] == "type" for h in A.search("angle unit rad", k=5, index=idx, kinds=["type"]))
    assert A.search("angle", k=5, index=idx, asset_ids=["other"]) == []
    q = A.query_for({"category": "graphical annotation", "check": "connection lines", "message": "no Line annotation",
                     "entity": "Aloha_vx300s"})
    assert "Line" in q and "Aloha" in q and "Diagram" in q


@pytest.mark.slow
def test_real_collection_builds_with_licences_and_answers_findings(tmp_path):
    try:
        idx = A.build()
    except Exception as exc:  # no OpenModelica / libraries on this machine
        pytest.skip(f"Modelica libraries not available: {exc}")
    assert {a["id"] for a in idx["manifest"]["assets"]} == {"msl-4.1.0", "modelicareference-4.1.0", "project-patterns",
                                                           "mls-3.7", "omc-errors-1.27.1", "msl-conversion-4.0.0", "omc-guide-1.27"}
    assert all(a["licence"] for a in idx["manifest"]["assets"]) and idx["n"] > 1000
    assert all(FIELDS <= set(c) and c["licence"] for c in idx["chunks"])
    assert not any(A._excluded(Path(c["source_path"])) for c in idx["chunks"])
    finding = {"id": "D021", "category": "mechanical or kinematic inconsistency", "check": "kinematics",
               "message": "link positions differ from URDF forward kinematics; mimic recorded but not used",
               "entity": "right_finger"}
    r1, r2 = A.retrieve(finding, index=idx), A.retrieve(finding, index=idx)
    assert [c["id"] for c in r1["chunks"]] == [c["id"] for c in r2["chunks"]] and r1["chunks"]
    assert json.dumps(r1)  # serialisable for the repair prompt record


@pytest.mark.slow
def test_v2_sources_answer_the_findings_they_were_added_for():
    """Knowledge collection v2 (26 Oct 2026): each added source is found for the kind of finding it covers."""
    try:
        idx = A.build()
    except Exception as exc:
        pytest.skip(f"Modelica libraries not available: {exc}")
    def top(message, category, k=5):
        return [c["id"] for c in A.retrieve({"category": category, "check": "", "message": message, "entity": ""}, k=k, index=idx)["chunks"]]
    assert any(i.startswith("msl-conversion-4.0.0:Modelica.SIunits") for i in
               top("Function Modelica.SIunits.Conversions.to_deg not found in scope Elbow.", "missing class or library"))
    assert "omc-errors-1.27.1:IMBALANCED_EQUATIONS" in top(
        "An independent subset of the model has imbalanced number of equations (5520) and variables (5519).", "other")
    assert any(i.startswith("omc-errors-1.27.1:STRUCTURAL_SINGULAR_INITIAL") for i in
               top("Initialization problem is structural singular. Please, check the initial conditions.", "initialization and numerical"))
    licences = {c["asset_id"]: c["licence"] for c in idx["chunks"]}
    assert "CC BY-SA 4.0" in licences["mls-3.7"] and "OSMC" in licences["omc-errors-1.27.1"]
