"""Controlled error-detection experiment: does ontology grounding detect engineering errors more reliably?

Candidates: the frozen generated follower arm class (control) plus seeded single-error variants.
Each candidate is checked by five detectors that all see the SAME engineering information
(the aloha_vx300s URDF and the candidate Modelica class):

  SIM    OpenModelica check + RightArmReach simulation + independent FK/limit/mimic validation (no ontology, no LLM)
  DIFF   deterministic URDF <-> Modelica text comparison (modelica_inspect.completeness; no ontology, no LLM)
  B      local Ollama reading the raw URDF and the candidate Modelica class
  C_LLM  the same Ollama model reading graph evidence (SPARQL over GraphDB) instead of the raw URDF
  C_RULE candidate lifted to RDF in GraphDB + fixed SPARQL rules using ontology relations and QUDT units

Scoring per candidate: detected (a finding on the mutated entity), classified (also the correct category),
false positives (findings on any other entity; on the control every finding is false).
Mutations are applied only to isolated copies; the frozen generated model is never modified.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import time
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET

from kkh.domain.aloha import candidate as cand
from kkh.domain.aloha.configuration import ROOT, URDF_DIR, arm_robot
from kkh.engineering.modelica_inspect import completeness

FROZEN = ROOT / "generated/modelica/ALOHA2"
CLASS_REL = "Arms/AlohaVX300s.mo"
CATEGORIES = ["axis", "unit", "limit", "connectivity", "mapping", "missing_component", "mimic", "joint_type",
              "parameter_provenance", "geometry", "other"]


def _sub(pattern, repl, count=1):
    def apply(text):
        out, n = re.subn(pattern, repl, text, flags=re.M)
        if n != count:
            raise ValueError(f"mutation pattern matched {n} times: {pattern}")
        return out
    return apply


def _rename_joint(old, new):
    def apply(text):
        text = text.replace(f'"URDF joint {old} (', '"Servo-driven axis (')
        n = len(re.findall(rf"\bj_{old}\b", text))
        if n < 2:
            raise ValueError("rename target missing")
        return re.sub(rf"\bj_{old}\b", new, text)
    return apply


MUTATIONS = [
    {"id": "M0-control", "entity": None, "category": None, "accept": [],
     "description": "Unmodified generated model (false-positive control).", "apply": lambda t: t},
    {"id": "M1-axis-sign", "entity": "elbow", "category": "axis", "accept": ["axis"],
     "description": "Elbow axis sign flipped: n = {0,-1,0} instead of {0,1,0}.",
     "apply": _sub(r"(j_elbow\(r = \{[^}]*\}, rpy = \{[^}]*\}, n = )\{0, 1\.0, 0\}", r"\1{0, -1.0, 0}")},
    {"id": "M2-axis-swap", "entity": "forearm_roll", "category": "axis", "accept": ["axis"],
     "description": "Forearm roll axis set to z instead of x.",
     "apply": _sub(r"(j_forearm_roll\(r = \{[^}]*\}, rpy = \{[^}]*\}, n = )\{1\.0, 0, 0\}", r"\1{0, 0, 1.0}")},
    {"id": "M3-unit-degrees", "entity": "shoulder", "category": "unit", "accept": ["unit", "limit"],
     "description": "Shoulder upper limit written in degrees (72) in a radian parameter.",
     "apply": _sub(r"(j_shoulder\([^;]*?q_max = )[-0-9.e]+", r"\g<1>72.0")},
    {"id": "M4-wrong-parent", "entity": "elbow", "category": "connectivity", "accept": ["connectivity"],
     "description": "Elbow joint attached to shoulder_link instead of upper_arm_link.",
     "apply": _sub(r"connect\(upper_arm_link\.frame_a, j_elbow\.frame_a\);", "connect(shoulder_link.frame_a, j_elbow.frame_a);")},
    {"id": "M5-lost-mapping", "entity": "wrist_rotate", "aliases": ["axis6"], "category": "mapping",
     "accept": ["mapping", "missing_component"],
     "description": "Wrist-rotate component renamed and its URDF reference removed (traceability lost).",
     "apply": _rename_joint("wrist_rotate", "axis6")},
    {"id": "M6-mimic-sign", "entity": "right_finger", "category": "mimic", "accept": ["mimic"],
     "description": "Right finger mimic multiplier +1 instead of -1.",
     "apply": lambda t: _sub(r"j_right_finger\.qdd = -1\.0 \*", "j_right_finger.qdd = 1.0 *")(
         _sub(r"j_right_finger\.qd = -1\.0 \*", "j_right_finger.qd = 1.0 *")(
             _sub(r"j_right_finger\.q = -1\.0 \*", "j_right_finger.q = 1.0 *")(t)))},
    {"id": "M7-unsourced-mass", "entity": "upper_arm_link", "category": "parameter_provenance",
     "accept": ["parameter_provenance", "other"],
     "description": "Upper-arm mass changed to 1.2 kg (no source supports it; URDF: 0.792592 kg).",
     "apply": _sub(r"(upper_arm_link\(hasInertia = true, m = )0\.792592", r"\g<1>1.2")},
    {"id": "M8-origin-typo", "entity": "elbow", "category": "geometry", "accept": ["geometry"],
     "description": "Elbow origin z = 0.03 m instead of 0.3 m (decimal typo).",
     "apply": _sub(r"(j_elbow\(r = \{0\.05955, 0, )0\.3\}", r"\g<1>0.03}")},
    {"id": "M9-joint-type", "entity": "gripper", "category": "joint_type", "accept": ["joint_type", "limit"],
     "description": "Continuous gripper joint modelled as limited revolute (limits invented: ±1.5 rad).",
     "apply": _sub(r"(j_gripper\(r = \{[^}]*\}, rpy = \{[^}]*\}, n = \{[^}]*\}, )limited = false",
                   r"\g<1>limited = true, q_min = -1.5, q_max = 1.5")},
]


def _norm(entity: str | None) -> str:
    e = (entity or "").lower().strip()
    e = e.split("/")[-1].split(".")[-1].removeprefix("j_")
    return e


def score(mut: dict, findings: list[dict]) -> dict:
    target = mut["entity"]
    names = {target, *mut.get("aliases", [])} if target else set()
    on_target = [f for f in findings if _norm(f.get("entity")) in names]
    other = [f for f in findings if _norm(f.get("entity")) not in names]
    return {"detected": bool(on_target) if target else None,
            "classified": any(f.get("category") == mut["category"] for f in on_target) if target else None,
            "accepted_category": any(f.get("category") in mut["accept"] for f in on_target) if target else None,
            "false_positives": len(other)}


# ------------------------------------------------------------------------------------- detectors
def det_diff(class_file: Path) -> list[dict]:
    rep = completeness(arm_robot("aloha_vx300s"), class_file)
    out = []
    for issue in rep["issues"]:
        m = re.match(r"joint (\S+): (.*)", issue)
        ent, text = (m.group(1), m.group(2)) if m else ("", issue)
        cat = ("axis" if "axis" in text else "limit" if "limit" in text else "connectivity" if "connection" in text
               else "missing_component" if "no component" in text else "geometry" if "origin" in text else "other")
        out.append({"entity": ent, "category": cat, "explanation": issue})
    for l in rep["disconnected_links"]:
        out.append({"entity": l, "category": "connectivity", "explanation": "disconnected link"})
    return out


def det_sim(package: Path, work: Path) -> dict:
    from kkh.domain.aloha.build import variable_filter
    from kkh.domain.aloha.pipeline import Pipeline as P
    from kkh.domain.aloha.scenarios import scenarios
    from kkh.engineering.omc import MatResult, OMCService
    rec = {"check_ok": False, "simulate_ok": False, "validation_ok": False}
    omc = OMCService(work)
    try:
        lr = omc.load_package(package / "package.mo")
        chk = omc.check("ALOHA2.Experiments.RightArmReach")
        rec.update(check_ok=lr.ok and chk.ok, check_messages=chk.messages[-1500:])
        if not rec["check_ok"]:
            return rec
        sc = scenarios()["RightArmReach"]
        sim = omc.simulate("ALOHA2.Experiments.RightArmReach", 9, intervals=450, variable_filter=variable_filter(sc))
        rec["simulate_ok"] = sim.ok
        if sim.ok:
            arms = json.loads((ROOT / "generated/modelica/aloha2_mapping.json").read_text())["arms"]
            v = P("RightArmReach", log=lambda *_: None, run_dir=work)._validate(MatResult(sim.data["resultFile"]), arms, sc)
            fk = v["forward_kinematics"]
            rec.update(validation_ok=v["ok"], fk_max_error_m=fk["max_position_error_m"], fk_worst=fk["worst"],
                       mimic_max_error=v["mimic_max_error"], limit_violations=v["limit_violations"])
    finally:
        omc.close()
    return rec


SCHEMA = {"type": "object", "properties": {"findings": {"type": "array", "maxItems": 12, "items": {
    "type": "object", "properties": {"entity": {"type": "string"}, "category": {"type": "string", "enum": CATEGORIES},
                                     "explanation": {"type": "string"}},
    "required": ["entity", "category", "explanation"]}}}, "required": ["findings"]}

SYSTEM = ("You are an engineering model reviewer. Compare the candidate Modelica arm model with the supplied "
          "engineering reference and report every inconsistency (joint axes, joint origins, limits and units, "
          "parent/child connectivity, missing or untraceable components, mimic relations, joint types, physical "
          "parameters without a source). 'entity' must be the URDF joint or link name (e.g. elbow, upper_arm_link). "
          "Report only inconsistencies you can point to in the supplied text. If there are none, return an empty list.")


def _urdf_kinematic_excerpt() -> str:
    """URDF with visual/collision geometry removed (identical information for kinematics and inertials)."""
    tree = ET.parse(URDF_DIR / "aloha_vx300s.urdf")
    root = tree.getroot()
    for parent in root.iter():
        for child in list(parent):
            if child.tag in ("visual", "collision", "ros2_control", "gazebo", "transmission"):
                parent.remove(child)
    text = ET.tostring(root, encoding="unicode")
    return re.sub(r"\n\s*\n", "\n", text).replace("aloha_vx300s/", "")


def _modelica_excerpt(class_file: Path) -> str:
    """Candidate class without diagram annotations/mesh paths (same content for B and C_LLM)."""
    text = class_file.read_text()
    text = re.sub(r"\n\s*annotation \(Placement\([^;]*\)\)\)", "", text)
    text = re.sub(r", hasShape = true, shapeFile = \"[^\"]*\", r_shape = \{[^}]*\}, lengthDirection = \{[^}]*\}, "
                  r"widthDirection = \{[^}]*\}, meshScale = [0-9.e-]+, color = \{[^}]*\}, animation = animation", "", text)
    return text.split("\n  annotation (\n")[0]


def _graph_evidence(db) -> str:
    """Engineering facts for the follower arm, retrieved from GraphDB by fixed SPARQL (no candidate data)."""
    from kkh.rag.retrieval import JOINTS, joint_facts
    facts = {}
    for j in sorted(JOINTS):
        rows = joint_facts("follower_right", j, db)
        facts[j] = {r["property"]: r["value"] + (f" [{r['unit'].split('/')[-1]}]" if r.get("unit") else "") for r in rows}
    q = cand.PREFIX + f"""SELECT ?label ?parent ?child ?ox ?oy ?oz ?type WHERE {{
      GRAPH <{cand.DATA_GRAPH}> {{ <{cand.entity('follower_right')}> kkh:hasJoint ?j . ?j rdfs:label ?label ; a ?type ;
      kkh:parentLink/rdfs:label ?parent ; kkh:childLink/rdfs:label ?child ; kkh:originXYZ [ kkh:x ?ox ; kkh:y ?oy ; kkh:z ?oz ] }} }}"""
    for r in db.select(q, infer=False):
        j = r["label"].split("/")[-1]
        facts.setdefault(j, {}).update({"type": r["type"].split("#")[-1], "parent": r["parent"].split("/")[-1],
                                       "child": r["child"].split("/")[-1],
                                       "origin_xyz": f"{float(r['ox']):g},{float(r['oy']):g},{float(r['oz']):g} [M]"})
    q = cand.PREFIX + f"""SELECT ?label ?m ?status WHERE {{ GRAPH <{cand.DATA_GRAPH}> {{
      <{cand.entity('follower_right')}> kkh:hasLink ?l . ?l rdfs:label ?label ; kkh:inertialStatus ?status .
      OPTIONAL {{ ?l kkh:mass/qudt:numericValue ?m }} }} }}"""
    links = {r["label"].split("/")[-1]: {"mass_kg": r.get("m"), "inertial_status": r["status"]} for r in db.select(q, infer=False)}
    return json.dumps({"joints": facts, "links": links,
                       "source": "GraphDB repository kkh-aloha-engineering, graph " + cand.DATA_GRAPH}, separators=(",", ":"))


def det_llm(client, model, seed, reference_name, reference, class_file) -> dict:
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"{reference_name}:\n{reference}\n\nCandidate Modelica model:\n{_modelica_excerpt(class_file)}"}]
    t = time.perf_counter()
    out = client.chat(messages, model=model, schema=SCHEMA, seed=seed, max_tokens=1500, num_ctx=16384)
    findings = json.loads(out["content"]).get("findings", [])
    return {"findings": findings, "seconds": round(time.perf_counter() - t, 2), "metrics": out["metrics"],
            "prompt_chars": sum(len(m["content"]) for m in messages)}


# ------------------------------------------------------------------------------------- experiment
def run(model="qwen3:4b", seeds=(42, 43), with_sim=True, llm=True, only: list[str] | None = None) -> dict:
    from kkh.llm.ollama import Ollama
    from kkh.semantic.graphdb import GraphDB
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    out = ROOT / "runs/benchmark/detection" / run_id
    out.mkdir(parents=True)
    frozen_hash = hashlib.sha256((FROZEN / CLASS_REL).read_bytes()).hexdigest()
    db = GraphDB()
    client = Ollama() if llm else None
    report = {"run_id": run_id, "model": model, "seeds": list(seeds), "frozen_class_sha256": frozen_hash,
              "started": dt.datetime.now(dt.timezone.utc).isoformat(), "categories": CATEGORIES,
              "protocol": ("Each candidate = frozen ALOHA2 package with one seeded error in Arms/AlohaVX300s.mo "
                           "(isolated copy). B and C_LLM use the same model, seed, temperature 0, 16k context, "
                           "JSON schema and system prompt; B receives the URDF (visual/collision geometry removed), "
                           "C_LLM receives GraphDB evidence retrieved by fixed SPARQL for the same arm. Both receive "
                           "the identical candidate Modelica excerpt. C_RULE uses no LLM."),
              "candidates": []}
    try:
        report["graphdb"] = db.version()
        report["qudt_subset_triples"] = cand.publish_qudt_subset(db)
        if llm:
            report["model_digest"] = next(m["digest"] for m in client.models() if m["name"] == model)
        urdf_ref = _urdf_kinematic_excerpt()
        graph_ref = _graph_evidence(db)
        report["reference_sizes_chars"] = {"urdf": len(urdf_ref), "graph_evidence": len(graph_ref)}
        (out / "reference_urdf.xml").write_text(urdf_ref, encoding="utf-8")
        (out / "reference_graph.json").write_text(graph_ref, encoding="utf-8")
        for mut in MUTATIONS:
            if only and mut["id"] not in only:
                continue
            d = out / mut["id"]
            pkg = d / "ALOHA2"
            shutil.copytree(FROZEN, pkg, ignore=shutil.ignore_patterns("*.stl"))
            f = pkg / CLASS_REL
            f.write_text(mut["apply"](f.read_text()), encoding="utf-8")
            rec = {k: mut[k] for k in ("id", "entity", "category", "description")}
            rec["detectors"] = {}
            # DIFF
            t = time.perf_counter()
            findings = det_diff(f)
            rec["detectors"]["DIFF"] = {"findings": findings, "seconds": round(time.perf_counter() - t, 3), **score(mut, findings)}
            # C_RULE
            t = time.perf_counter()
            cr = cand.check(db, f, f"{run_id}/{mut['id']}")
            for x in cr["findings"]:
                x.pop("c", None)
            rec["detectors"]["C_RULE"] = {"findings": cr["findings"], "candidate_triples": cr["triples"],
                                          "seconds": round(time.perf_counter() - t, 3), **score(mut, cr["findings"])}
            # SIM
            if with_sim:
                t = time.perf_counter()
                s = det_sim(pkg, d / "omc")
                flagged = not (s["check_ok"] and s["simulate_ok"] and s["validation_ok"])
                rec["detectors"]["SIM"] = {**s, "seconds": round(time.perf_counter() - t, 2),
                                           "detected": flagged if mut["entity"] else None,
                                           "false_positives": int(flagged and not mut["entity"]),
                                           "classified": None, "note": "flags the model; does not localise or classify"}
            # LLM detectors
            if llm:
                for name, ref_name, ref in (("B", "Engineering reference (URDF)", urdf_ref),
                                            ("C_LLM", "Engineering reference (knowledge-graph evidence, JSON)", graph_ref)):
                    runs = []
                    for seed in seeds:
                        try:
                            r = det_llm(client, model, seed, ref_name, ref, f)
                            r.update(score(mut, r["findings"]), seed=seed)
                        except Exception as e:
                            r = {"seed": seed, "error": repr(e), "detected": False, "classified": False,
                                 "accepted_category": False, "false_positives": 0}
                        runs.append(r)
                    rec["detectors"][name] = {"runs": runs}
            report["candidates"].append(rec)
            (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
            print(mut["id"], {k: (v.get("detected"), v.get("false_positives")) if "runs" not in v else
                              [(r.get("detected"), r.get("false_positives")) for r in v["runs"]]
                              for k, v in rec["detectors"].items()}, flush=True)
    finally:
        db.close()
        if client:
            client.close()
    report["summary"] = summarize(report)
    report["frozen_model_unchanged"] = hashlib.sha256((FROZEN / CLASS_REL).read_bytes()).hexdigest() == frozen_hash
    report["finished"] = dt.datetime.now(dt.timezone.utc).isoformat()
    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    if not only:
        (ROOT / "reports/detection.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def summarize(report: dict) -> dict:
    seeded = [c for c in report["candidates"] if c["entity"]]
    control = [c for c in report["candidates"] if not c["entity"]]
    out = {}
    names = sorted({n for c in report["candidates"] for n in c["detectors"]})
    for n in names:
        rows = []  # (candidate, run) pairs
        for c in report["candidates"]:
            det = c["detectors"].get(n)
            if det is None:
                continue
            for r in det.get("runs", [det]):
                rows.append((c, r))
        s = [(c, r) for c, r in rows if c["entity"]]
        ctrl = [(c, r) for c, r in rows if not c["entity"]]
        out[n] = {
            "trials": len(s),
            "detected": sum(bool(r.get("detected")) for _, r in s),
            "correctly_classified": sum(bool(r.get("classified")) for _, r in s),
            "accepted_category": sum(bool(r.get("accepted_category")) for _, r in s),
            "control_false_findings": sum(r.get("false_positives", 0) for _, r in ctrl),
            "off_target_findings_on_seeded": sum(r.get("false_positives", 0) for _, r in s),
            "errors": sum("error" in r for _, r in rows),
            "mean_seconds": round(sum(r.get("seconds", 0) for _, r in rows) / max(1, len(rows)), 2),
            "per_candidate": {c["id"]: [r.get("detected") for r in c["detectors"][n].get("runs", [c["detectors"][n]])]
                              for c in seeded + control if n in c["detectors"]},
        }
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3:4b")
    ap.add_argument("--seeds", default="42,43")
    ap.add_argument("--no-sim", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    r = run(a.model, tuple(int(s) for s in a.seeds.split(",")), not a.no_sim, not a.no_llm,
            [x for x in a.only.split(",") if x] or None)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "per_candidate"} for k, v in r["summary"].items()}, indent=1))
