"""Make a downloaded URDFModelica package animate in OMEdit: the converter writes each mesh as a bare, mangled file
name (first '/' -> '_', e.g. "assets_base.stl", "package:_/pkg/meshes/base.stl") that no tool can find, and the meshes
are not in the package. The export copies the meshes into URDFModelica/Resources/Meshes/<Robot>/ (scale from the URDF
baked in, so every file is in metres), points each visual at it with a modelica:// URI, and sets the shape size factors
to 1. Only visualisation changes; masses, inertias, frames and joints are untouched. The run's own files are never
modified: changed files are written into the zip only."""
from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

from .robot3d import resolve_mesh

STL = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])


def _scaled_stl(p: Path, scale: tuple[float, float, float]) -> bytes:
    data = p.read_bytes()
    if scale == (1.0, 1.0, 1.0):
        return data
    n = int.from_bytes(data[80:84], "little")
    if 84 + 50 * n != len(data):  # ASCII STL: scale each vertex line
        s = np.array(scale)
        return re.sub(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)",
                      lambda m: b"vertex %g %g %g" % tuple(float(x) * k for x, k in zip(m.groups(), s)), data)
    rec = np.frombuffer(data, dtype=STL, count=n, offset=84).copy()
    rec["v"] *= np.array(scale, dtype="<f4")
    return data[:84] + rec.tobytes()


def urdfmodelica_visuals(urdf: Path, pkg_root: Path, model: str) -> tuple[dict[str, str], dict[str, bytes], int]:
    """(rewritten text files by zip path, added mesh files by zip path, number of meshes) for one URDFModelica package."""
    robot_dir = model.split(".")[2] if model.startswith("URDFModelica.Examples.") else None
    if not robot_dir:
        return {}, {}, 0
    meshes: dict[tuple[str, tuple], str] = {}
    added: dict[str, bytes] = {}
    by_key: dict[str, str] = {}
    for me in ET.parse(urdf).getroot().iter("mesh"):
        f = me.get("filename")
        p = resolve_mesh(urdf, f)
        if p is None:
            continue
        scale = tuple(float(x) for x in (me.get("scale") or "1 1 1").split())
        key = f.replace("/", "_", 1)  # how the converter writes the file name into the model
        if (key, scale) not in meshes:
            name = p.name if scale == (1.0, 1.0, 1.0) else f"{p.stem}_x{scale[0]:g}{p.suffix}"
            rel = f"URDFModelica/Resources/Meshes/{robot_dir}/{name}"
            meshes[(key, scale)] = rel
            added[rel] = _scaled_stl(p, scale)
        by_key[key] = meshes[(key, scale)]
    if not by_key:
        return {}, {}, 0
    links_dir = pkg_root / "URDFModelica" / "Examples" / robot_dir / "Links"
    rewritten: dict[str, str] = {}
    for f in links_dir.glob("*.mo"):
        t = f.read_text(encoding="utf-8")
        new = re.sub(r'filename = "([^"]+)"', lambda m: f'filename = "modelica://{by_key[m.group(1)]}"' if m.group(1) in by_key else m.group(0), t)
        new = re.sub(r"(FixedShape (?:visualMesh|collisionMesh)\([^;]*?)height = 0,", r"\1height = 1,", new)
        new = re.sub(r"(FixedShape (?:visualMesh|collisionMesh)\([^;]*?)width = 0, length = 0\)", r"\1width = 1, length = 1)", new)
        if new != t:
            rewritten[f.relative_to(pkg_root).as_posix()] = new
    return rewritten, added, len(added)
