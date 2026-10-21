"""3D description of a robot for the browser: links, visual meshes and joints, read from the same URDF that is
converted (so the picture shows exactly what the physics model will represent). The browser computes the pose from
the joint values with the URDF conventions; meshes are served by index only (no client-supplied paths)."""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import numpy as np

from kkh.engineering.urdf_model import load_urdf

from . import sources

MESH_TYPES = {".stl"}  # what the browser viewer loads; other formats fall back to the skeleton


def _package_dir(urdf: Path, pkg: str) -> Path | None:
    """Directory of ROS package `pkg`: an ancestor of the URDF with that name, else a matching directory under the
    pinned third_party sources (searched once, cached)."""
    for parent in urdf.parents:
        if parent.name == pkg:
            return parent
        if parent == sources.ROOT:
            break
    return _third_party_dirs().get(pkg)


@lru_cache(maxsize=1)
def _third_party_dirs() -> dict[str, Path]:
    out: dict[str, Path] = {}
    tp = sources.ROOT / "third_party"
    for d in tp.rglob("*"):
        if d.is_dir() and ".git" not in d.parts and d.name not in out:
            out[d.name] = d
    return out


def resolve_mesh(urdf: Path, filename: str | None) -> Path | None:
    if not filename:
        return None
    if filename.startswith("package://"):
        rest = filename[len("package://"):]
        pkg, _, sub = rest.partition("/")
        if pkg in ("..", "."):
            p = (urdf.parent / rest).resolve()
        else:
            base = _package_dir(urdf, pkg)
            p = (base / sub).resolve() if base else None
    elif filename.startswith("file://"):
        return None  # absolute paths from someone else's machine are never followed
    else:
        p = (urdf.parent / filename).resolve()
    if p is None or not p.is_file() or p.suffix.lower() not in MESH_TYPES:
        return None
    if sources.ROOT.resolve() not in p.parents:
        return None
    return p


@lru_cache(maxsize=32)
def describe(source: str) -> tuple[dict, list[Path]]:
    urdf, meta = sources.resolve(source)
    robot = load_urdf(urdf)
    meshes: list[Path] = []
    links = {}
    for name, link in robot.links.items():
        vis = []
        for v in link.visuals:
            p = resolve_mesh(urdf, v.mesh)
            idx = None
            if p is not None:
                if p not in meshes:
                    meshes.append(p)
                idx = meshes.index(p)
            vis.append({"mesh": idx, "xyz": [float(x) for x in v.origin.xyz], "rpy": [float(x) for x in v.origin.rpy],
                        "scale": [float(x) for x in v.scale], "rgba": [float(x) for x in v.rgba] if v.rgba else None})
        links[name] = {"mass": float(link.inertial.mass) if link.inertial else None, "placeholder": bool(link.is_placeholder), "visuals": vis}
    joints = [{"name": j.name, "type": j.type, "parent": j.parent, "child": j.child,
               "xyz": [float(x) for x in j.origin.xyz], "rpy": [float(x) for x in j.origin.rpy],
               "axis": [float(x) for x in j.axis],
               "lower": float(j.limit.lower) if j.limit and j.limit.lower is not None else None,
               "upper": float(j.limit.upper) if j.limit and j.limit.upper is not None else None,
               "mimic": {"joint": j.mimic[0], "multiplier": float(j.mimic[1]), "offset": float(j.mimic[2])} if j.mimic else None}
              for j in robot.joints.values()]
    return {"source": source, "robot": robot.name, "label": meta.get("label"), "root": robot.root, "links": links,
            "joints": joints, "meshes": len(meshes),
            "mesh_bytes": sum(p.stat().st_size for p in meshes)}, meshes


LOW_CELLS = 36  # preview level of detail: vertices merged on a grid of ~36 cells across each mesh's diagonal


def simplified(p: Path, cells: int = LOW_CELLS) -> Path:
    """Light copy of a binary STL for previews (vertex clustering: vertices in the same grid cell are merged, collapsed
    triangles dropped). Same shape at a glance, a few % of the triangles. Cached under runs/convert/mesh_cache."""
    data = p.read_bytes()
    key = hashlib.sha256(data).hexdigest()[:20]
    out = sources.RUNS / "mesh_cache" / f"{key}-{cells}.stl"
    if out.exists():
        return out
    n = int.from_bytes(data[80:84], "little")
    if 84 + 50 * n != len(data):
        return p  # ASCII STL: served as is
    rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
    v = rec["v"].reshape(-1, 3).astype(np.float64)
    lo, hi = v.min(0), v.max(0)
    cell = max(float(np.linalg.norm(hi - lo)) / cells, 1e-12)
    _, idx = np.unique(np.floor((v - lo) / cell).astype(np.int64), axis=0, return_inverse=True)
    idx = idx.reshape(-1)
    centre = np.zeros((idx.max() + 1, 3))
    np.add.at(centre, idx, v)
    centre /= np.bincount(idx)[:, None]
    t = idx.reshape(-1, 3)
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    t = t[np.sort(np.unique(np.sort(t, axis=1), axis=0, return_index=True)[1])]
    tri = centre[t]
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-30)
    res = np.zeros(len(tri), dtype=rec.dtype)
    res["n"], res["v"] = nrm, tri
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"kkh preview (vertex clustering)".ljust(80, b" ") + len(tri).to_bytes(4, "little") + res.tobytes())
    return out
