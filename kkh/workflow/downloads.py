"""Downloads of a pipeline run: any single version ready for OMEdit, or every version before and after repair.

  version   one version (original converter output, a fault, an AI repair, a reviewed or an approved version) as the
            full URDFModelica workspace, with the robot's meshes (kkh.convert.export) and a README naming the version
  compare   the robot package of the converter's original and of every repaired / reviewed / approved version side by
            side, each with a unified diff against the version it started from, and a README

Files are read from the run only; nothing in the run is changed (mesh paths are rewritten inside the zip only).
"""
from __future__ import annotations

import datetime as dt
import difflib
import io
import json
import re
import zipfile
from pathlib import Path

from kkh.convert import sources
from kkh.convert.export import urdfmodelica_visuals

from . import review as R

SKIP_DIRS = {"omc", "excite", "__pycache__"}
SKIP_EXT = {".mat", ".exe", ".o", ".c", ".h", ".dll", ".log", ".makefile", ".libs", ".json"}

LABEL = {"original": "the DLR converter's output, unmodified (Stage 1)", "fault": "a deliberately injected fault",
         "repair": "an AI repair proposal, as produced (Stage 3)", "review": "an engineer-reviewed version (Stage 5)",
         "approved": "an approved version (Stage 6)"}
ARM = {"ai_only": "AI only", "ai_assets": "AI + Modelica knowledge"}


def keys(run_dir: Path) -> list[str]:
    """Every version that exists in this run, original first."""
    d = Path(run_dir)
    out = ["original"]
    out += [f"fault/{p.parent.name}" for p in sorted((d / "faults").glob("F*/ws"))]
    out += [f"repair/{p.parent.parent.name}/{p.parent.name}" for p in sorted((d / "repair").glob("*/*/ws"))]
    out += [f"review/{p.parent.parent.name}/{p.parent.name}" for p in sorted((d / "review").glob("*/*/ws"))]
    out += [f"approved/{p.parent.name}" for p in sorted((d / "approved").glob("*/ws"))]
    return [k for k in out if R.KEY.match(k)]


def describe(key: str) -> str:
    kind = key.split("/")[0]
    parts = key.split("/")
    if kind == "repair":
        return f"AI repair proposal, case {parts[1]}, method {ARM.get(parts[2], parts[2])}"
    if kind == "review":
        return f"Engineer-reviewed version '{parts[2]}', case {parts[1]}"
    if kind == "fault":
        return f"Fault {parts[1]} injected into the converter's output"
    return LABEL.get(kind, key)


def _manifest(run_dir: Path) -> dict:
    return json.loads((Path(run_dir) / "stage1" / "manifest.json").read_text(encoding="utf-8"))


def _slug(key: str) -> str:
    return re.sub(r"[^\w.-]+", "_", key)


def version_zip(run_dir: Path, key: str) -> tuple[bytes, str]:
    """(zip bytes, file name) of one version, ready to open in OMEdit."""
    run_dir = Path(run_dir)
    ws = R.ws_of(run_dir, key)
    if not ws.exists():
        raise ValueError(f"version {key} does not exist in this run")
    m = _manifest(run_dir)
    model = m["generated"]["test_model"]
    urdf = sources.ROOT / m["source"]["urdf"]
    rewritten, added, n_mesh = urdfmodelica_visuals(urdf, ws, model) if urdf.exists() else ({}, {}, 0)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ws.rglob("*")):
            rel = p.relative_to(ws)
            if not p.is_file() or set(rel.parts) & SKIP_DIRS or p.suffix.lower() in SKIP_EXT:
                continue
            r = rel.as_posix()
            z.writestr(r, rewritten[r]) if r in rewritten else z.write(p, r)
        for r, data in added.items():
            z.writestr(r, data)
        z.writestr("README.txt", "\n".join([
            "HT GEN7 PhysAI Studio - engineering pipeline export",
            "",
            f"Robot:   {m['source'].get('label')} ({m['source'].get('urdf')})",
            f"Run:     {run_dir.name}",
            f"Version: {key} - {describe(key)}",
            f"Package: URDFModelica/Examples/{R.pkg_of(ws).name}",
            "",
            "Open in OMEdit: File > Open Model/Library File(s) > URDFModelica/package.mo, then simulate",
            f"  {model}",
            "Requires the Modelica Standard Library 4.x (the studio uses MSL 4.1.0 with OpenModelica 1.27.1).",
            (f"For the 3D animation, {n_mesh} mesh files are included under URDFModelica/Resources/Meshes and referenced "
             "with modelica:// URIs (inside this zip only; visualisation only)." if n_mesh else "Meshes are not included."),
            f"Exported {dt.datetime.now().isoformat(timespec='seconds')}.",
        ]) + "\n")
    return buf.getvalue(), f"{m['source'].get('id', 'robot')}-{_slug(key)}.zip"


def compare_zip(run_dir: Path) -> tuple[bytes, str]:
    """(zip bytes, file name): the robot package of every version side by side, with diffs against their starting point."""
    run_dir = Path(run_dir)
    m = _manifest(run_dir)
    ks = keys(run_dir)
    buf = io.BytesIO()
    lines = ["HT GEN7 PhysAI Studio - every version of the robot model, before and after repair", "",
             f"Robot: {m['source'].get('label')}   Run: {run_dir.name}", "",
             "Each folder holds the generated robot package (the .mo files) of one version.",
             "Each *.diff file shows what changed against the version it started from:",
             "the converter's original for natural findings, the faulty version for an injected fault.", ""]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, key in enumerate(ks):
            pkg = R.pkg_of(R.ws_of(run_dir, key))
            folder = f"{i:02d}_{_slug(key)}"
            for p in sorted(pkg.rglob("*.mo")):
                z.write(p, f"{folder}/{pkg.name}/{p.relative_to(pkg).as_posix()}")
            lines.append(f"{folder}/  {describe(key)}")
            if key != "original":
                base = "original" if R.case_of(key) == "natural" else f"fault/{R.case_of(key)}"
                if key.startswith("fault/"):
                    base = "original"
                bpkg = R.pkg_of(R.ws_of(run_dir, base))
                chunks = []
                for p in sorted(set(x.relative_to(pkg).as_posix() for x in pkg.rglob("*.mo"))
                                | set(x.relative_to(bpkg).as_posix() for x in bpkg.rglob("*.mo"))):
                    a = (bpkg / p).read_text(encoding="utf-8").splitlines(keepends=True) if (bpkg / p).exists() else []
                    b = (pkg / p).read_text(encoding="utf-8").splitlines(keepends=True) if (pkg / p).exists() else []
                    if a != b:
                        chunks += difflib.unified_diff(a, b, f"{_slug(base)}/{p}", f"{_slug(key)}/{p}")
                z.writestr(f"{folder}.diff", "".join(chunks) or "(no change)\n")
                lines.append(f"{'':4}{folder}.diff: {'changes against ' + base if chunks else 'no change'}")
        z.writestr("README.txt", "\n".join(lines) + "\n")
    return buf.getvalue(), f"{m['source'].get('id', 'robot')}-{run_dir.name}-all-versions.zip"
