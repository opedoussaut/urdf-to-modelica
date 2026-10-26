"""Stages 5-6 - engineer review, approval and promotion. Every action is a person's, recorded with who, when and why.

Candidates are workspaces addressed by key; none of them is ever the project's baseline (generated/ is not touched):
  original             the Stage 1 package (natural case)        fault/F03            a frozen faulted copy
  repair/<case>/<arm>  the final AI candidate of one arm         review/<case>/<name> a reviewer-built candidate
  approved/<n>         a promoted copy (after approval; with the separate layout pass)

Review: accept a subset of an arm's applied edits -> they are re-applied, in order, to a fresh copy of the case's
starting package (nothing unreviewed leaks in); amend a file by hand -> a new version; validate -> the independent
Stage 2 + integrity guard. Approval normally requires 'validated' and no integrity flag; approving anyway needs a
written justification (accept_open_findings) and the open findings are recorded with the approval.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from kkh.engineering.omc import DEFAULT_OMHOME

from . import faults as F
from . import layout, stage2_check as s2, stage4_validate as s4
from .stage3_repair import apply_edits, case_paths

KEY = re.compile(r"^(original|fault/F\d\d|repair/(natural|F\d\d)/(ai_only|ai_assets)|review/(natural|F\d\d)/[\w-]{1,40}|approved/\d{1,4})$")


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def ws_of(run_dir: Path, key: str) -> Path:
    if not KEY.match(key):
        raise ValueError(f"invalid candidate key {key!r}")
    run_dir = Path(run_dir).resolve()
    if key == "original":
        return F.stage1_ws(run_dir)
    kind, *rest = key.split("/")
    base = {"fault": run_dir / "faults", "repair": run_dir / "repair", "review": run_dir / "review", "approved": run_dir / "approved"}[kind]
    return base.joinpath(*rest, "ws")


def case_of(key: str) -> str:
    if key == "original":
        return "natural"
    parts = key.split("/")
    return parts[1] if parts[0] in ("fault", "repair", "review") else "natural"


def pkg_of(ws: Path) -> Path:
    return F.pkg_of(ws)


def files(run_dir: Path, key: str) -> list[str]:
    return sorted(p.relative_to(pkg_of(ws_of(run_dir, key))).as_posix() for p in pkg_of(ws_of(run_dir, key)).rglob("*.mo"))


def read(run_dir: Path, key: str, rel: str) -> str:
    pkg = pkg_of(ws_of(run_dir, key)).resolve()
    f = (pkg / rel).resolve()
    if pkg not in f.parents or f.suffix != ".mo":
        raise ValueError("not a Modelica file of this candidate")
    return f.read_text(encoding="utf-8")


def diff(run_dir: Path, key: str, against: str | None = None) -> list[dict]:
    against = against or ("original" if case_of(key) == "natural" else f"fault/{case_of(key)}")
    return s4.diff(pkg_of(ws_of(run_dir, against)), pkg_of(ws_of(run_dir, key)))


def arm_edits(run_dir: Path, case: str, arm: str) -> list[dict]:
    """Every applied edit of an arm, in order, with a stable id (attempt.n), its explanation, citations and the
    provenance of the cited chunks."""
    rec = json.loads((Path(run_dir) / "repair" / case / arm / "record.json").read_text(encoding="utf-8"))
    out = []
    for a in rec["attempts"]:
        prov = {c["id"]: c for c in a.get("retrieved") or []}
        for e in a["edits"]:
            if e.get("applied"):
                out.append({"id": f"{a['attempt']}.{e['n']}", "attempt": a["attempt"], **{k: e.get(k) for k in ("file", "search", "replace", "explanation", "addresses", "cites")},
                            "cited_sources": [prov.get(c, {"id": c, "unknown": True}) for c in (e.get("cites") or [])]})
    return out


def _new_review_ws(run_dir: Path, case: str, name: str) -> Path:
    src, _ = case_paths(run_dir, case)
    dest = ws_of(run_dir, f"review/{case}/{name}")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def _next_name(run_dir: Path, case: str, stem: str) -> str:
    d = Path(run_dir) / "review" / case
    n = 1 + max([int(m.group(1)) for p in (d.glob(f"{stem}-*") if d.exists() else []) if (m := re.match(rf"{stem}-(\d+)$", p.name))] or [0])
    return f"{stem}-{n}"


def accept_edits(run_dir: Path, case: str, arm: str, edit_ids: list[str], reviewer: str, note: str = "") -> dict:
    """Build a reviewer candidate from the accepted subset of an arm's edits (applied to a fresh starting copy)."""
    all_edits = {e["id"]: e for e in arm_edits(run_dir, case, arm)}
    unknown = [i for i in edit_ids if i not in all_edits]
    if unknown:
        raise ValueError(f"unknown edit ids: {unknown}")
    name = _next_name(run_dir, case, f"accepted-{arm.replace('_', '-')}")
    ws = _new_review_ws(run_dir, case, name)
    chosen = [all_edits[i] for i in sorted(edit_ids, key=lambda x: tuple(map(int, x.split("."))))]
    applied = apply_edits(pkg_of(ws), chosen)
    meta = {"key": f"review/{case}/{name}", "case": case, "created": _now(), "reviewer": reviewer, "note": note,
            "from": {"arm": arm, "accepted": edit_ids, "rejected": [i for i in all_edits if i not in edit_ids]},
            "applied": [{"id": c["id"], "applied": a["applied"], "error": a.get("error")} for c, a in zip(chosen, applied)],
            "history": []}
    (ws.parent / "review.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def amend(run_dir: Path, key: str, rel: str, text: str, reviewer: str, note: str = "") -> dict:
    """Manual edit by the engineer: written into a NEW reviewer candidate (the edited one is kept unchanged)."""
    case = case_of(key)
    read(run_dir, key, rel)  # validates the path
    name = _next_name(run_dir, case, "manual")
    dest = ws_of(run_dir, f"review/{case}/{name}")
    shutil.copytree(ws_of(run_dir, key), dest)
    before = (pkg_of(dest) / rel).read_text(encoding="utf-8")
    (pkg_of(dest) / rel).write_text(text, encoding="utf-8")
    meta = {"key": f"review/{case}/{name}", "case": case, "created": _now(), "reviewer": reviewer, "note": note,
            "from": {"key": key, "file": rel, "sha_before": hashlib.sha256(before.encode()).hexdigest(),
                     "sha_after": hashlib.sha256(text.encode()).hexdigest()}}
    (dest.parent / "review.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def validate(run_dir: Path, key: str) -> dict:
    """Independent Stage 2 + integrity guard against the case's starting package; stored next to the candidate."""
    run_dir = Path(run_dir).resolve()
    ws = ws_of(run_dir, key)
    case = case_of(key)
    start_ws, diag_path = case_paths(run_dir, case)
    orig = json.loads(diag_path.read_text(encoding="utf-8"))
    v = s2.run(run_dir, log=lambda *_: None, ws_dir=ws, out_dir=ws.parent / "validation")
    cmp = s4.compare_findings(orig["findings"], v["findings"])
    flags = s4.integrity(pkg_of(start_ws), pkg_of(ws), orig, v)
    res = {"key": key, "validated_at": _now(), "verdict": v["verdict"], "integrity_flags": flags,
           "findings": {"initial": cmp["initial"], "resolved": len(cmp["resolved"]), "remaining": len(cmp["remaining"]), "new": len(cmp["new"])},
           "open_findings": [{k: f.get(k) for k in ("id", "step", "check", "category", "severity", "entity", "message")}
                             for f in s4.in_scope_all(v["findings"])],
           "graphics": v["steps"].get("graphics", {}).get("totals"), "files": v["subject"]["files"]}
    (ws.parent / "validation.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return res


def decide(run_dir: Path, key: str, decision: str, reviewer: str, note: str, accept_open_findings: bool = False) -> dict:
    """approve -> promoted copy + separate layout pass; reject -> recorded. Requires a fresh validation."""
    run_dir = Path(run_dir).resolve()
    if not reviewer.strip():
        raise ValueError("a reviewer name is required")
    ws = ws_of(run_dir, key)
    vfile = ws.parent / "validation.json"
    if not vfile.exists():
        raise ValueError("validate the candidate first")
    val = json.loads(vfile.read_text(encoding="utf-8"))
    current = {p.relative_to(pkg_of(ws)).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(pkg_of(ws).rglob("*")) if p.is_file()}
    if current != val["files"]:
        raise ValueError("the candidate changed after its validation; validate again")
    rec = {"key": key, "decision": decision, "reviewer": reviewer, "note": note, "at": _now(), "validation": val}
    log = run_dir / "decisions.jsonl"
    if decision == "reject":
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        return rec
    if decision != "approve":
        raise ValueError("decision must be approve or reject")
    clean = val["verdict"] == "validated" and not val["integrity_flags"]
    if not clean and not (accept_open_findings and len(note.strip()) >= 15):
        raise ValueError("not validated or integrity flags present: approving needs accept_open_findings and a written justification")
    n = 1 + max([int(p.name) for p in (run_dir / "approved").glob("*") if p.name.isdigit()] or [0])
    dest = run_dir / "approved" / str(n)
    shutil.copytree(ws, dest / "ws")
    st1 = json.loads((run_dir / "stage1" / "manifest.json").read_text(encoding="utf-8"))
    chain = {"urdf_sha256": st1["source"]["urdf_sha256"], "converter_commit": st1["converter"]["commit"],
             "candidate": key, "candidate_meta": _meta(ws), "validation_files": val["files"]}
    lay = layout.run(dest / "ws", F.pkg_of(dest / "ws").name, work=dest / "layout_omc")
    approval = {**rec, "approved": f"approved/{n}", "status": "approved" if clean else "approved with open findings",
                "open_findings": val["open_findings"] if not clean else [], "integrity_flags": val["integrity_flags"],
                "chain": chain, "layout_pass": {k: lay[k] for k in ("before", "after", "files_changed", "annotations_only")} | {"skipped": len(lay["skipped"])},
                "note_layout": "visual-quality pass applied after approval only; annotations only; not part of the repair comparison"}
    (dest / "approval.json").write_text(json.dumps(approval, indent=1, default=str), encoding="utf-8")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: approval[k] for k in ("key", "decision", "reviewer", "note", "at", "approved", "status")}) + "\n")
    return approval


def _meta(ws: Path) -> dict | None:
    for p in (ws.parent / "review.json", ws.parent / "record.json"):
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            return {k: d.get(k) for k in ("key", "case", "arm", "model", "reviewer", "from", "settings_digest") if d.get(k) is not None}
    return None


def open_omedit(run_dir: Path, key: str) -> dict:
    exe = Path(DEFAULT_OMHOME) / "bin" / "OMEdit.exe"
    if not exe.exists():
        raise ValueError("OMEdit is not available in the configured OpenModelica installation")
    package = ws_of(run_dir, key) / "URDFModelica" / "package.mo"
    subprocess.Popen([str(exe), str(package)], cwd=package.parent)
    return {"opened": package.as_posix(), "hint": f"Open URDFModelica.Examples.{F.TARGET['package']} in OMEdit's Libraries browser"}


def simulate(run_dir: Path, key: str) -> dict:
    """Simulation of an approved model from the studio: the full checks incl. the standard excitation run."""
    if not key.startswith("approved/"):
        raise ValueError("only approved models are simulated here")
    ws = ws_of(run_dir, key)
    v = s2.run(Path(run_dir), log=lambda *_: None, ws_dir=ws, out_dir=ws.parent / "simulation")
    return {"key": key, "verdict": v["verdict"], "steps": {k: x.get("state") for k, x in v["steps"].items()},
            "simulation": v["steps"].get("simulation"), "consistency": v["steps"].get("urdf_consistency", {}).get("criteria")}
