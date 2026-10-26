"""Controlled fault injection for the repair experiment: single, realistic edits to COPIES of the Stage 1 package.

FAULT SET v1 is frozen by commit before any AI repair run. Each fault is pinned to the SHA-256 of the exact Stage 1 file
it edits (DLR URDFModelica @ 92541b6f on data/urdf/aloha_vx300s.urdf); applying it to anything else is refused.
If the set changes, write a NEW version (v2) and keep v1 untouched; never re-measure v1 with edited faults.

Held-out faults (held_out=True) are reported separately: the repair instructions were written without them in view.
The natural findings of the conversion (unused mimic, finger start positions outside the limits, missing connection
lines) are present in every copy; a fault adds exactly one extra defect.

    PYTHONPATH=. python -m kkh.workflow.faults runs/workflow/<run-id> [--characterise]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

VERSION = "faults-v1"
TARGET = {"source": "aloha_vx300s", "converter_commit": "92541b6f6aa76fd510983a25afd3082377b4028f",
          "package": "Aloha_vx300s"}

# (id, title, category, entity, file, regex, replacement, held_out, what it represents)
_F = [
    ("F01", "Missing semicolon after a declaration", "syntax and translation", "elbow", "Joints/Elbow.mo",
     r"(parameter Integer flangeIndex = 0);", r"\1", False, "typing slip that breaks parsing"),
    ("F02", "MSL 3 class name used with MSL 4", "missing class or library", "elbow", "Joints/Elbow.mo",
     r"Modelica\.Units\.Conversions\.to_deg", "Modelica.SIunits.Conversions.to_deg", False,
     "library version mismatch: Modelica.SIunits was removed in MSL 4"),
    ("F03", "Misspelled component class", "missing class or library", "elbow", "Aloha_vx300s.mo",
     r"Joints\.Elbow elbow\(", "Joints.Elbw elbow(", False, "a reference to a class that does not exist"),
    ("F04", "Joint limit written in degrees", "type and unit", "elbow", "Joints/ElbowParams.mo",
     r"upper = 1\.6057029118347832,", "upper = 92.0,", False, "92 deg typed into a field in radians"),
    ("F05", "Joint axis sign flipped", "mechanical or kinematic inconsistency", "shoulder", "Joints/ShoulderParams.mo",
     r"axis = URDFModelica\.Records\.Axis\(xyz = \{0\.0, 1\.0, 0\.0\}\)", "axis = URDFModelica.Records.Axis(xyz = {0.0, -1.0, 0.0})",
     False, "the shoulder turns the wrong way"),
    ("F06", "Joint frame rotated by 90 degrees", "mechanical or kinematic inconsistency", "wrist_angle", "Joints/Wrist_angleParams.mo",
     r"origin = URDFModelica\.Records\.Origin\(xyz = \{0\.1, 0\.0, 0\.0\},rpy = \{0\.0, 0\.0, 0\.0\}\)",
     "origin = URDFModelica.Records.Origin(xyz = {0.1, 0.0, 0.0},rpy = {0.0, 0.0, 1.5707963267948966})", False,
     "a wrong yaw in the joint origin"),
    ("F07", "Mechanical connection deleted", "connector and equation", "elbow", "Aloha_vx300s.mo",
     r"  connect\(elbow\.frame_b, aloha_vx300s_upper_forearm_link\.frame_a\)\n    annotation \(Line\([^\n]*\)\);\n", "",
     False, "the forearm is no longer attached to the elbow"),
    ("F08", "Flange connected to a non-existent array element", "connector and equation", "elbow", "Aloha_vx300s.mo",
     r"connect\(elbow\.flange_a, rotational_flange_a\[3\]\);", "connect(elbow.flange_a, rotational_flange_a[12]);", True,
     "index out of range: only 6 rotational joints"),
    ("F09", "Link mass replaced by a round value", "mechanical or kinematic inconsistency", "upper_arm_link",
     "Links/Aloha_vx300s_upper_arm_linkParams.mo", r"mass = 0\.792592,", "mass = 1.0,", True,
     "an arbitrary physical value instead of the URDF mass"),
    ("F10", "Conflicting initial equation", "initialization and numerical", "elbow", "Joints/Elbow.mo",
     r"\nequation\n", "\ninitial equation\n  revolute.phi = 2.5;\nequation\n", True,
     "an initial angle outside the joint range that also conflicts with the prescribed motion"),
]
# How to tell, in a candidate, that the fault itself was undone (the full verdict comes from the independent checks):
# ("present", regex) must match again, or ("absent", regex) must no longer match, in the faulted file.
_RESTORED = {
    "F01": ("present", r"parameter Integer flangeIndex = 0;"),
    "F02": ("absent", r"Modelica\.SIunits"),
    "F03": ("present", r"Joints\.Elbow elbow\("),
    "F04": ("present", r"upper = 1\.60570291183478"),
    "F05": ("present", r"Axis\(xyz = \{0\.0, 1\.0, 0\.0\}\)"),
    "F06": ("present", r"Origin\(xyz = \{0\.1, 0\.0, 0\.0\},rpy = \{0\.0, 0\.0, 0\.0\}\)"),
    "F07": ("present", r"connect\(\s*elbow\.frame_b\s*,\s*aloha_vx300s_upper_forearm_link\.frame_a\s*\)"),
    "F08": ("absent", r"rotational_flange_a\[12\]"),
    "F09": ("present", r"mass = 0\.792592"),
    "F10": ("absent", r"revolute\.phi\s*=\s*2\.5"),
}
FAULTS = [{"id": i, "title": t, "category": c, "entity": e, "file": f, "pattern": p, "replacement": r, "held_out": h,
           "represents": w, "restored": _RESTORED[i]} for i, t, c, e, f, p, r, h, w in _F]


def restored(fault: dict, ws: Path) -> bool:
    """True when the faulted text is undone in the candidate workspace (not, by itself, a validation)."""
    f = ws / "URDFModelica" / "Examples" / TARGET["package"] / fault["file"]
    if not f.exists():
        return False
    how, rx = fault["restored"]
    found = re.search(rx, f.read_text(encoding="utf-8")) is not None
    return found if how == "present" else not found


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_hashes(run_dir: Path) -> dict[str, str]:
    """SHA-256 of each Stage 1 file the faults edit (taken from the Stage 1 manifest)."""
    files = json.loads((Path(run_dir) / "stage1" / "manifest.json").read_text(encoding="utf-8"))["generated"]["files"]
    return {f["file"]: files[f["file"]] for f in FAULTS}


def set_digest() -> str:
    """Digest of the fault definitions themselves (recorded with every result)."""
    return hashlib.sha256(json.dumps(FAULTS, sort_keys=True).encode()).hexdigest()


def pkg_of(ws: Path) -> Path:
    """The generated robot package inside a URDFModelica workspace: the Examples folder that is not part of the pinned
    library (any robot; the fault set itself only targets the ALOHA follower)."""
    from kkh.convert.sources import ROOT
    ex = Path(ws) / "URDFModelica" / "Examples"
    lib = ROOT / "third_party" / "URDFModelica" / "URDFModelica" / "Examples"
    library = {p.name for p in lib.iterdir()} if lib.exists() else set()
    generated = [p for p in ex.iterdir() if p.is_dir() and p.name not in library] if ex.exists() else []
    return generated[0] if len(generated) == 1 else ex / TARGET["package"]


def stage1_ws(run_dir: Path) -> Path:
    return Path(run_dir) / "stage1" / "convert" / "ws"


def copy_ws(run_dir: Path, dest: Path) -> Path:
    """Isolated copy of the Stage 1 workspace (library + generated package); the original is never touched."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(stage1_ws(run_dir), dest)
    return dest


def apply(fault: dict, ws: Path, expected_sha: str | None = None) -> dict:
    """Apply one fault to a workspace copy. The pattern must match exactly once; the file must be the pinned one."""
    f = ws / "URDFModelica" / "Examples" / TARGET["package"] / fault["file"]
    text = f.read_text(encoding="utf-8")
    if expected_sha and _sha(f) != expected_sha:
        raise ValueError(f"{fault['id']}: {fault['file']} is not the pinned Stage 1 file")
    n = len(re.findall(fault["pattern"], text))
    if n != 1:
        raise ValueError(f"{fault['id']}: pattern matched {n} times in {fault['file']}")
    new = re.sub(fault["pattern"], fault["replacement"], text, count=1)
    f.write_text(new, encoding="utf-8")
    return {"id": fault["id"], "file": fault["file"], "sha_before": hashlib.sha256(text.encode()).hexdigest(),
            "sha_after": hashlib.sha256(new.encode()).hexdigest()}


def build(run_dir: Path, out: Path) -> list[dict]:
    """One workspace per fault under out/<id>/ws, plus out/faults.json (definitions, pins, digest)."""
    pins = pinned_hashes(run_dir)
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for fault in FAULTS:
        ws = copy_ws(run_dir, out / fault["id"] / "ws")
        made.append({**fault, **apply(fault, ws, pins[fault["file"]]), "ws": ws.as_posix()})
    (out / "faults.json").write_text(json.dumps({"version": VERSION, "digest": set_digest(), "target": TARGET,
                                                 "pins": pins, "faults": made}, indent=1), encoding="utf-8")
    return made


def characterise(run_dir: Path, out: Path, log=print) -> list[dict]:
    """Run the deterministic Stage 2 checks on every faulted copy (no AI): which step catches each fault, and how."""
    from kkh.workflow import stage2_check as s2
    base = json.loads((Path(run_dir) / "stage2" / "diagnostics.json").read_text(encoding="utf-8"))
    base_keys = {(f["step"], f["check"], f.get("entity"), f["message"]) for f in base["findings"]}
    rows = []
    for fault in build(run_dir, out):
        log(f"[faults] {fault['id']} {fault['title']}")
        r = s2.run(run_dir, log=lambda *_: None, ws_dir=Path(fault["ws"]), out_dir=out / fault["id"] / "stage2")
        new = [f for f in r["findings"] if (f["step"], f["check"], f.get("entity"), f["message"]) not in base_keys]
        rows.append({"id": fault["id"], "title": fault["title"], "category": fault["category"], "held_out": fault["held_out"],
                     "verdict": r["verdict"], "steps": {k: v.get("state") for k, v in r["steps"].items()},
                     "new_findings": len(new), "caught_by": sorted({f["step"] for f in new}),
                     "first_new": [{k: f[k] for k in ("step", "check", "category", "severity", "entity", "message")} for f in new[:3]]})
        log(f"[faults]   -> {r['verdict']}; new findings {len(new)} in {rows[-1]['caught_by']}")
    (out / "characterisation.json").write_text(json.dumps({"version": VERSION, "digest": set_digest(), "rows": rows}, indent=1),
                                               encoding="utf-8")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--characterise", action="store_true", help="also run Stage 2 on every faulted copy")
    a = ap.parse_args()
    out = a.run_dir / "faults"
    rows = characterise(a.run_dir, out) if a.characterise else build(a.run_dir, out)
    print(json.dumps([{k: r[k] for k in ("id", "title") + (("verdict", "caught_by") if a.characterise else ())} for r in rows], indent=1))


if __name__ == "__main__":
    main()
