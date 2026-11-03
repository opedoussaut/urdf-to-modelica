"""Scoring a review against known defects. Same metrics for manual and AI reviews.

Ground truth (never shown to the reviewer):
  conversion file → the scorer's measured defects (kkh.convert.runner.findings, entity + category)
  seeded file     → the one known error of kkh/benchmark/detection.MUTATIONS (M0 = control, no error)

Metrics:
  recall          defects found on the right entity / defects                (found_type: also an accepted category)
  precision       reported issues that match a defect / reported issues      (affirmations filtered, as in detection.py)
  corrections     each proposed correction applied to an ISOLATED copy, then re-checked:
                  seeded → deterministic URDF↔Modelica comparison (detection.det_diff) no longer flags the entity
                  conversion → full re-score (real OpenModelica run) no longer reports the defect, nothing new breaks
  faithfulness    numeric claims checked against the URDF (axis, origins, limits, mass, centre of mass, mimic)
  calibration     Brier score of the stated confidence vs "issue matches a defect" (0 = perfect, 0.25 = coin flip)
"""
from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

import numpy as np

from kkh.benchmark.detection import _norm, is_affirmation
from kkh.engineering.urdf_model import load_urdf

from . import runner, sources

MAX_CORRECTIONS = 3  # corrections re-checked per review (each conversion re-check is a real OpenModelica run)
ACCEPT = {"mimic": ["mimic"], "geometry": ["geometry", "axis", "connectivity"], "axis": ["axis"],
          "missing_component": ["missing_component", "mapping"], "parameter_provenance": ["parameter_provenance", "geometry"],
          "other": None}  # None: any category (whole-file problems)
MODEL_WORDS = {"model", "file", "package", "", "syntax", "modelica"}


# ------------------------------------------------------------------------------------------- ground truth
def ground_truth(target: dict) -> list[dict]:
    from .review import _seeded_mutation
    if target.get("kind") == "seeded":
        m = _seeded_mutation(target["mutation"])
        if not m["entity"]:
            return []
        return [{"entity": m["entity"], "aliases": m.get("aliases", []), "category": m["category"], "accept": m["accept"],
                 "title": m["description"]}]
    report = runner.load(str(target["run"]))
    out = []
    for f in runner.findings(report, str(target["mode"])):
        if f.get("defect"):
            out.append({"entity": f["entity"], "aliases": [], "category": f["category"],
                        "accept": ACCEPT.get(f["category"], [f["category"]]), "title": f["title"]})
    return out


def _matches(issue: dict, defect: dict) -> tuple[bool, bool]:
    """(right entity, right entity AND accepted category)."""
    e = _norm(issue.get("entity"))
    if defect["entity"] == "model":
        on = e in MODEL_WORDS or issue.get("category") == "other"
    else:
        names = {_norm(defect["entity"]), *(_norm(a) for a in defect.get("aliases", []))}
        on = e in names or e.removesuffix("_link") in names or (e + "_link") in names
    acc = defect.get("accept")
    return on, on and (acc is None or issue.get("category") in acc)


# ------------------------------------------------------------------------------------------- faithfulness
def check_claims(claims: list[dict], urdf: Path) -> dict:
    robot = load_urdf(urdf)
    joints = {n.split("/")[-1]: j for n, j in robot.joints.items()}
    links = {n.split("/")[-1]: l for n, l in robot.links.items()}
    rows = []
    for c in claims:
        ent, prop, val = c["entity"].split("/")[-1].removeprefix("j_"), c["property"], np.array(c["value"], float)
        j, l = joints.get(ent), links.get(ent) or links.get(ent + "_link")
        ref = None
        if j is not None:
            ref = {"axis": j.axis, "origin_xyz": j.origin.xyz, "origin_rpy": j.origin.rpy,
                   "lower_limit": [j.limit.lower] if j.limit and j.limit.lower is not None else None,
                   "upper_limit": [j.limit.upper] if j.limit and j.limit.upper is not None else None,
                   "effort_limit": [j.limit.effort] if j.limit and j.limit.effort is not None else None,
                   "velocity_limit": [j.limit.velocity] if j.limit and j.limit.velocity is not None else None,
                   "mimic_multiplier": [j.mimic[1]] if j.mimic else None}.get(prop)
        if ref is None and l is not None and l.inertial is not None:
            ref = {"mass": [l.inertial.mass], "com_xyz": l.inertial.origin.xyz}.get(prop)
        if ref is None:
            rows.append({**c, "verdict": "unverifiable"})
            continue
        ref = np.array(ref, float)
        ok = val.shape == ref.shape and bool(np.allclose(val, ref, rtol=1e-3, atol=1e-6))
        rows.append({**c, "urdf": ref.round(6).tolist(), "verdict": "correct" if ok else "wrong"})
    checkable = [r for r in rows if r["verdict"] != "unverifiable"]
    return {"claims": rows, "checked": len(checkable), "correct": sum(r["verdict"] == "correct" for r in checkable),
            "rate": round(sum(r["verdict"] == "correct" for r in checkable) / len(checkable), 4) if checkable else None}


# ------------------------------------------------------------------------------------------- corrections
def _block(text: str, start: int) -> tuple[int, int]:
    """Span of the balanced parenthesis block whose '(' is at or after `start`."""
    i = text.index("(", start)
    depth = 0
    for k in range(i, len(text)):
        depth += {"(": 1, ")": -1}.get(text[k], 0)
        if depth == 0:
            return i, k
    raise ValueError("unbalanced parentheses")


def apply_correction(texts: dict[str, str], corr: dict) -> tuple[str, str]:
    """Apply {component, parameter (dotted path), value} to the first file that contains the component.
    Returns (file key, new text). Raises ValueError when it cannot be applied (reported as 'not applicable')."""
    comp, path = corr["component"].strip(), [p for p in corr["parameter"].strip().split(".") if p]
    if not comp or not path or not corr.get("value"):
        raise ValueError("no parameter change proposed")
    lit = (f"{corr['value'][0]:.12g}" if len(corr["value"]) == 1 else "{" + ", ".join(f"{v:.12g}" for v in corr["value"]) + "}")
    for key, text in texts.items():
        m = re.search(r"\b" + re.escape(comp) + r"\s*\(", text)
        if m:
            lo, hi = _block(text, m.start())
        else:
            m = re.search(r"\b(record|model|block)\s+" + re.escape(comp) + r"\b", text)
            if not m:
                continue
            end = re.search(r"\bend\s+" + re.escape(comp) + r"\s*;", text[m.end():])
            lo, hi = m.end(), m.end() + (end.start() if end else len(text) - m.end())
        for seg in path[:-1]:
            sm = re.search(r"\b" + re.escape(seg) + r"\s*=\s*[\w.]*\s*\(", text[lo:hi])
            if not sm:
                raise ValueError(f"'{seg}' not found in {comp}")
            lo, hi = _block(text, lo + sm.start())
        pm = re.search(r"\b" + re.escape(path[-1]) + r"\s*=\s*(\{[^}]*\}|[-+0-9.eE]+)", text[lo:hi])
        if not pm:
            raise ValueError(f"'{corr['parameter']}' not found in {comp}")
        a, b = lo + pm.start(1), lo + pm.end(1)
        return key, text[:a] + lit + text[b:]
    raise ValueError(f"component '{comp}' not found in the file")


def _recheck_seeded(target: dict, key: str, new_text: str, defect: dict | None) -> dict:
    from kkh.benchmark.detection import det_diff
    from .review import seeded_file
    work = sources.RUNS / "seeded" / "_corrections" / uuid.uuid4().hex[:8]
    work.mkdir(parents=True)
    try:
        f = work / "class.mo"
        f.write_text(new_text, encoding="utf-8")
        after = det_diff(f)
        before = det_diff(seeded_file(target["mutation"]))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ents_after = {_norm(x["entity"]) for x in after}
    ents_before = {_norm(x["entity"]) for x in before}
    fixed = defect is not None and _norm(defect["entity"]) not in ents_after and _norm(defect["entity"]) in ents_before
    return {"fixed": bool(fixed), "new_problems": sorted(ents_after - ents_before), "method": "deterministic URDF↔Modelica comparison"}


def _recheck_conversion(target: dict, key: str, new_text: str, defect: dict | None) -> dict:
    from . import score
    report = runner.load(str(target["run"]))
    m = report["modes"][str(target["mode"])]
    work = sources.RUNS / str(target["run"]) / runner.safe_dir(str(target["mode"])) / "corrections" / uuid.uuid4().hex[:8]
    main = sources.ROOT / m["main_file"]
    if runner.base(target["mode"]) == "urdfmodelica":
        lib = (sources.ROOT / m["package_file"]).parent
        shutil.copytree(lib, work / "URDFModelica", ignore=shutil.ignore_patterns("*.stl", "*.STL", "*.dae", "*.png", "*.PNG"))
        rel = (main.parent / key) if "/" in key else main
        (work / "URDFModelica" / rel.relative_to(lib)).write_text(new_text, encoding="utf-8")
        package, model = work / "URDFModelica" / "package.mo", m["model"]
    else:
        work.mkdir(parents=True)
        package = work / main.name
        package.write_text(new_text, encoding="utf-8")
        from .llm import model_names
        model = model_names(new_text, "")
    s = score.score(sources.ROOT / report["source"]["path"], package, model, work)
    fake = {**report, "modes": {**report["modes"], "_c": {**m, "score": s}}}
    after = [f for f in runner.findings(fake, "_c") if f.get("defect")]
    before = [f for f in runner.findings(report, str(target["mode"])) if f.get("defect")]
    key_of = lambda f: (f["entity"], f["category"])
    fixed = defect is not None and key_of(defect) not in {key_of(f) for f in after}
    return {"fixed": bool(fixed), "new_problems": sorted({f"{f['entity']}:{f['category']}" for f in after} - {f"{f['entity']}:{f['category']}" for f in before}),
            "checks_passed_after": s.get("passed"), "method": "full re-score (OpenModelica)"}


# ------------------------------------------------------------------------------------------- score
def score_review(target: dict, report: dict, recheck: bool = True) -> dict:
    from .review import target_files
    defects = ground_truth(target)
    issues = [i for i in report["issues"] if not is_affirmation({"explanation": i.get("evidence", "")})]
    found = [{"defect": d["title"], "entity": d["entity"], "category": d["category"],
              "found": any(_matches(i, d)[0] for i in issues), "found_type": any(_matches(i, d)[1] for i in issues)} for d in defects]
    matched = [any(_matches(i, d)[1] for d in defects) for i in issues]
    files, urdf, _ = target_files(target)
    corrections = []
    for i in [i for i in issues if i["correction"]["component"]][:MAX_CORRECTIONS]:
        defect = next((d for d in defects if _matches(i, d)[0]), None)
        row = {"issue": i["entity"], "correction": i["correction"], "targets_defect": defect["title"] if defect else None}
        try:
            key, new = apply_correction(files, i["correction"])
            if recheck:
                full = _full_text(target, key)
                key2, new_full = apply_correction({key: full}, i["correction"])
                row.update((_recheck_seeded if target.get("kind") == "seeded" else _recheck_conversion)(target, key, new_full, defect))
            row["applied"] = True
        except Exception as exc:
            row.update(applied=False, reason=str(exc)[:200], fixed=False)
        corrections.append(row)
    brier = [((i["confidence"] - (1.0 if ok else 0.0)) ** 2) for i, ok in zip(issues, matched)]
    claims = check_claims(report.get("claims", []), urdf)
    n_def = len(defects)
    return {
        "defects": n_def, "found": sum(x["found"] for x in found), "found_type": sum(x["found_type"] for x in found),
        "recall": round(sum(x["found_type"] for x in found) / n_def, 4) if n_def else None,
        "issues_reported": len(issues), "affirmations_filtered": len(report["issues"]) - len(issues),
        "precision": round(sum(matched) / len(issues), 4) if issues else None,
        "false_alarms": len(issues) - sum(matched),
        "corrections_proposed": sum(1 for i in issues if i["correction"]["component"]),
        "corrections_fixed": sum(1 for c in corrections if c.get("fixed")),
        "corrections_with_new_problems": sum(1 for c in corrections if c.get("new_problems")),
        "corrections": corrections, "by_defect": found,
        "faithfulness": claims, "brier": round(float(np.mean(brier)), 4) if brier else None,
    }


def _full_text(target: dict, key: str) -> str:
    """Unstripped text of a reviewed file (corrections are applied to the real file, annotations included)."""
    from .review import seeded_file
    if target.get("kind") == "seeded":
        return seeded_file(target["mutation"]).read_text(encoding="utf-8")
    report = runner.load(str(target["run"]))
    main = sources.ROOT / report["modes"][str(target["mode"])]["main_file"]
    return ((main.parent / key) if "/" in key else main).read_text(encoding="utf-8", errors="replace")
