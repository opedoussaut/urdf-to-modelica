"""Stage 1 - deterministic URDF conversion with the pinned DLR URDFModelica converter, no AI, no corrections.

Records everything needed to reproduce and audit the conversion:
  manifest.json        input hashes (URDF + every referenced mesh), converter commit/arguments/pre-processing,
                       tool versions, generated files with hashes, full converter log, reproducibility result
  mapping.json         URDF link/joint -> converted name -> Modelica class, instance and parameter record
                       (by the converter's documented naming rule; stage 2's kinematic check verifies the wiring)
  physical_table.json  every URDF mass, centre of mass, inertia, joint origin, axis, limit, dynamics and mimic value
                       next to the value written in the generated parameter record, with a match flag
  unsupported.json     URDF content the conversion ignores, transforms or records without using
Generic: works for any URDF the converter accepts; nothing here is robot-specific.

    PYTHONPATH=. python -m kkh.workflow.stage1_convert aloha_vx300s [--out runs/workflow/<id>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

from kkh.convert import sources, urdfmodelica
from kkh.convert.robot3d import _package_dir
from kkh.engineering.omc import DEFAULT_OMHOME
from kkh.engineering.urdf_model import load_urdf

ROOT = sources.ROOT
RUNS = ROOT / "runs" / "workflow"
REL_TOL = 1e-9  # values are copied as text; anything beyond float formatting is a real difference
# URDFModelica.Types.JointType literal -> URDF joint type (the enumeration calls fixed joints 'fixedJoint')
JOINT_TYPE_URDF = {"fixedJoint": "fixed"}
SCHEMA = "kkh.workflow.stage1/1"


# ---------------------------------------------------------------- helpers

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def converted_name(urdf_name: str) -> str:
    """Name after the documented pre-processing (T1 '/' -> '_', T3 '-' -> '_')."""
    return urdf_name.replace("/", "_").replace("-", "_")


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _safe_roots() -> list[Path]:
    # third_party may be a link to a shared checkout; it is still the pinned, read-only source tree
    return [ROOT.resolve(), (ROOT / "third_party").resolve()]


def resolve_asset(urdf: Path, filename: str) -> Path | None:
    """package://pkg/sub or a relative path -> file inside the repository's pinned sources (never file:// or outside)."""
    if filename.startswith("package://"):
        pkg, _, sub = filename[len("package://"):].partition("/")
        base = urdf.parent if pkg in ("..", ".") else _package_dir(urdf, pkg)
        p = (base / sub).resolve() if base else None
    elif "://" in filename:
        return None
    else:
        p = (urdf.parent / filename).resolve()
    if p is None or not p.is_file() or not any(r == p or r in p.parents for r in _safe_roots()):
        return None
    return p


def urdf_assets(urdf: Path) -> list[dict]:
    """Every file the URDF references (meshes, textures), resolved and hashed; unresolved ones are listed too."""
    out, seen = [], set()
    for el in ET.parse(urdf).getroot().iter():
        f = el.get("filename")
        if el.tag in ("mesh", "texture") and f and f not in seen:
            seen.add(f)
            p = resolve_asset(urdf, f)
            out.append({"uri": f, "kind": el.tag, "path": _rel(p) if p else None,
                        "sha256": sha256_file(p) if p else None, "bytes": p.stat().st_size if p else None,
                        "resolved": p is not None})
    return out


def urdf_features(urdf: Path) -> dict[str, int]:
    """Count of every element path (robot/link/inertial/mass, robot/joint/mimic, robot/ros2_control/...)."""
    counts: dict[str, int] = {}

    def walk(el, path):
        counts[path] = counts.get(path, 0) + 1
        for c in el:
            if isinstance(c.tag, str):
                walk(c, f"{path}/{c.tag}")

    walk(ET.parse(urdf).getroot(), "robot")
    return dict(sorted(counts.items()))


# ---------------------------------------------------------------- generated parameter records

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def _vec(s: str) -> list[float]:
    return [float(x) for x in re.findall(_NUM, s)]


def _field(text: str, name: str) -> str | None:
    m = re.search(rf"\b{name}\s*=\s*([^,\n)]+)", text)
    return m.group(1).strip() if m else None


def _num(text: str, name: str) -> float | None:
    v = _field(text, name)
    return float(v) if v is not None and re.fullmatch(_NUM, v) else None


def _origin_after(text: str, key: str) -> dict | None:
    m = re.search(rf"\b{key}\s*=\s*[\w.]*Origin\(xyz\s*=\s*\{{([^}}]*)\}},\s*rpy\s*=\s*\{{([^}}]*)\}}", text)
    return {"xyz": _vec(m.group(1)), "rpy": _vec(m.group(2))} if m else None


def _bool(text: str, name: str) -> bool | None:
    v = _field(text, name)
    return None if v is None else v == "true"


def parse_link_record(text: str) -> dict:
    head, _, rest = text.partition("inertial =")
    inertial = rest.split("visual =")[0] if rest else ""
    return {"name": (re.search(r'\bname\s*=\s*"([^"]*)"', head) or [None, None])[1],
            "com": _origin_after(inertial, "origin"), "mass": _num(inertial, "mass"),
            "inertia": {k: _num(inertial, k) for k in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")},
            "visual_mesh": (re.search(r'visual\s*=.*?filename\s*=\s*"([^"]*)"', text, re.S) or [None, None])[1],
            "has_visual": _bool(text, "hasVisual"), "has_collision": _bool(text, "hasCollision")}


def parse_joint_record(text: str) -> dict:
    lim = re.search(r"limit\s*=\s*[\w.]*Limit\(([^)]*)\)", text)
    dyn = re.search(r"dynamics\s*=\s*[\w.]*Dynamics\(([^)]*)\)", text)
    mim = re.search(r"mimic\s*=\s*[\w.]*Mimic\(([^)]*)\)", text)
    axis = re.search(r"axis\s*=\s*[\w.]*Axis\(xyz\s*=\s*\{([^}]*)\}", text)
    jt = re.search(r"jointType\s*=\s*[\w.]*JointType\.(\w+)", text)
    return {"name": (re.search(r'\bname\s*=\s*"([^"]*)"', text) or [None, None])[1],
            "type": jt.group(1) if jt else None,
            "origin": _origin_after(text, "origin"),
            "parent": (re.search(r'Parent\(link\s*=\s*"([^"]*)"', text) or [None, None])[1],
            "child": (re.search(r'Child\(link\s*=\s*"([^"]*)"', text) or [None, None])[1],
            "axis": _vec(axis.group(1)) if axis else None,
            "has_limit": _bool(text, "hasLimit"), "has_dynamics": _bool(text, "hasDynamics"),
            "has_mimic": _bool(text, "hasMimic"), "has_safety_controller": _bool(text, "hasSafety_controller"),
            "has_calibration": _bool(text, "hasCalibration"),
            "limit": {k: _num(lim.group(1), k) for k in ("lower", "upper", "effort", "velocity")} if lim else None,
            "dynamics": {k: _num(dyn.group(1), k) for k in ("damping", "friction")} if dyn else None,
            "mimic": {"joint": (re.search(r'joint\s*=\s*"([^"]*)"', mim.group(1)) or [None, None])[1],
                      "multiplier": _num(mim.group(1), "multiplier"), "offset": _num(mim.group(1), "offset")} if mim else None}


# ---------------------------------------------------------------- comparison

def _close(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    a, b = np.atleast_1d(np.asarray(a, float)), np.atleast_1d(np.asarray(b, float))
    return a.shape == b.shape and bool(np.all(np.abs(a - b) <= REL_TOL * np.maximum(1.0, np.abs(a))))


def _row(entity: str, kind: str, field: str, urdf_value, generated_value, unit: str) -> dict:
    as_list = lambda v: v.tolist() if isinstance(v, np.ndarray) else v
    u, g = as_list(urdf_value), as_list(generated_value)
    return {"entity": entity, "kind": kind, "field": field, "unit": unit, "urdf": u, "generated": g,
            "match": _close(u, g)}


def physical_table(robot, mapping: list[dict], pkg_dir: Path) -> list[dict]:
    rows = []
    for m in mapping:
        rec = pkg_dir / m["params_file"] if m["params_file"] else None
        text = rec.read_text(encoding="utf-8") if rec and rec.exists() else ""
        if m["kind"] == "link":
            link, g = robot.links[m["urdf_name"]], parse_link_record(text)
            if link.inertial is None:
                rows.append(_row(m["urdf_name"], "link", "inertial", None, g["mass"], "-"))
                continue
            I = link.inertial.inertia
            rows += [_row(m["urdf_name"], "link", "mass", link.inertial.mass, g["mass"], "kg"),
                     _row(m["urdf_name"], "link", "com.xyz", link.inertial.origin.xyz, (g["com"] or {}).get("xyz"), "m"),
                     _row(m["urdf_name"], "link", "com.rpy", link.inertial.origin.rpy, (g["com"] or {}).get("rpy"), "rad")]
            for k, (i, j) in {"ixx": (0, 0), "ixy": (0, 1), "ixz": (0, 2), "iyy": (1, 1), "iyz": (1, 2), "izz": (2, 2)}.items():
                rows.append(_row(m["urdf_name"], "link", f"inertia.{k}", I[i, j], g["inertia"].get(k), "kg.m2"))
        else:
            j, g = robot.joints[m["urdf_name"]], parse_joint_record(text)
            gtype = JOINT_TYPE_URDF.get(g["type"], g["type"])
            rows += [_row(m["urdf_name"], "joint", "type", None, None, "-") | {"urdf": j.type, "generated": g["type"], "match": j.type == gtype},
                     _row(m["urdf_name"], "joint", "parent", None, None, "-") | {"urdf": converted_name(j.parent), "generated": g["parent"], "match": converted_name(j.parent) == g["parent"]},
                     _row(m["urdf_name"], "joint", "child", None, None, "-") | {"urdf": converted_name(j.child), "generated": g["child"], "match": converted_name(j.child) == g["child"]},
                     _row(m["urdf_name"], "joint", "origin.xyz", j.origin.xyz, (g["origin"] or {}).get("xyz"), "m"),
                     _row(m["urdf_name"], "joint", "origin.rpy", j.origin.rpy, (g["origin"] or {}).get("rpy"), "rad")]
            if j.type != "fixed":
                rows.append(_row(m["urdf_name"], "joint", "axis", j.axis, g["axis"], "-"))
            if j.limit is not None:
                unit = "m" if j.type == "prismatic" else "rad"
                for k, u in (("lower", unit), ("upper", unit), ("effort", "N|N.m"), ("velocity", unit + "/s")):
                    uv = getattr(j.limit, k)
                    if uv is not None:
                        rows.append(_row(m["urdf_name"], "joint", f"limit.{k}", uv, (g["limit"] or {}).get(k), u))
            for k in ("damping", "friction"):
                uv = getattr(j, k)
                if uv is not None:
                    rows.append(_row(m["urdf_name"], "joint", f"dynamics.{k}", uv, (g["dynamics"] or {}).get(k), "-"))
            if j.mimic:
                gm = g["mimic"] or {}
                rows += [_row(m["urdf_name"], "joint", "mimic.joint", None, None, "-") | {"urdf": converted_name(j.mimic[0]), "generated": gm.get("joint"), "match": converted_name(j.mimic[0]) == gm.get("joint")},
                         _row(m["urdf_name"], "joint", "mimic.multiplier", j.mimic[1], gm.get("multiplier"), "-"),
                         _row(m["urdf_name"], "joint", "mimic.offset", j.mimic[2], gm.get("offset"), "-")]
    return rows


# ---------------------------------------------------------------- mapping and unsupported features

def build_mapping(robot, pkg_dir: Path, main_file: Path) -> list[dict]:
    """URDF name -> converted name -> class -> instance -> parameter record, by the converter's naming rule."""
    main = main_file.read_text(encoding="utf-8")
    instances = {(kind, cls): inst for kind, cls, inst in re.findall(r"^\s*(Links|Joints)\.(\w+)\s+(\w+)\s*\(", main, re.M)}
    out = []
    for kind, names in (("link", robot.links), ("joint", robot.joints)):
        folder = "Links" if kind == "link" else "Joints"
        for name in names:
            conv = converted_name(name)
            cls = urdfmodelica.title(conv)
            model_file, params_file = f"{folder}/{cls}.mo", f"{folder}/{cls}Params.mo"
            out.append({"kind": kind, "urdf_name": name, "converted_name": conv, "class": f"{folder}.{cls}",
                        "instance": instances.get((folder, cls)),
                        "model_file": model_file if (pkg_dir / model_file).exists() else None,
                        "params_file": params_file if (pkg_dir / params_file).exists() else None,
                        "rule": "converter naming: '/' and '-' -> '_', class = title case",
                        "verified_by": "stage 2 kinematic comparison (pending)"})
    return out


# record flag -> parameter path that a joint model must reference for the feature to have any effect
_RECORDED_FEATURES = {"has_mimic": "jointParams.mimic", "has_safety_controller": "jointParams.safety_controller",
                      "has_calibration": "jointParams.calibration"}


def unsupported(urdf: Path, robot, mapping: list[dict], pkg_dir: Path, preprocessing: list[str], log: str) -> list[dict]:
    """URDF content the conversion drops, rewrites or records without using. Each item has evidence."""
    items = []
    for line in log.splitlines():
        m = re.search(r'Unknown tag "([^"]+)"', line)
        if m:
            items.append({"feature": m.group(1), "effect": "ignored by the converter", "severity": "warning",
                          "category": "unsupported URDF element", "evidence": line.strip()})
    pre = {"T1": "'/' in link/joint names replaced by '_' before conversion",
           "T2": "<texture> materials replaced by a flat colour before conversion (the converter crashes on textures)",
           "T3": "'-' in names replaced by '_' before conversion"}
    for t in preprocessing:
        if t in pre:
            items.append({"feature": t, "effect": "transformed before conversion", "severity": "info",
                          "category": "unsupported URDF element", "evidence": pre[t]})
    for m in mapping:
        if m["kind"] != "joint" or not m["params_file"]:
            continue
        rec = parse_joint_record((pkg_dir / m["params_file"]).read_text(encoding="utf-8"))
        model = (pkg_dir / m["model_file"]).read_text(encoding="utf-8") if m["model_file"] else ""
        for flag, ref in _RECORDED_FEATURES.items():
            if rec.get(flag) and ref not in model:
                items.append({"feature": flag.removeprefix("has_"), "entity": m["urdf_name"],
                              "effect": "recorded in the parameter record but not used by the joint model",
                              "severity": "warning", "category": "unsupported URDF element",
                              "evidence": f"{m['params_file']}: {flag[4:]} present; {m['model_file']} never references {ref}"})
    for m in mapping:
        if m["kind"] != "link" or not m["params_file"]:
            continue
        link = robot.links[m["urdf_name"]]
        g = parse_link_record((pkg_dir / m["params_file"]).read_text(encoding="utf-8"))
        src = next((v.mesh for v in link.visuals if v.mesh), None)
        if src and g["visual_mesh"] and g["visual_mesh"] != src:
            items.append({"feature": "visual mesh URI", "entity": m["urdf_name"], "effect": "rewritten by the converter",
                          "severity": "warning", "category": "unsupported URDF element",
                          "evidence": f"URDF {src!r} -> record {g['visual_mesh']!r}"})
    return items


# ---------------------------------------------------------------- run

def _generated_hashes(pkg_dir: Path) -> dict[str, str]:
    return {f.relative_to(pkg_dir).as_posix(): sha256_file(f) for f in sorted(pkg_dir.rglob("*")) if f.is_file()}


def _versions() -> dict:
    def pkg(name):
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return None
    omc = Path(DEFAULT_OMHOME) / "bin" / "omc.exe"
    try:
        om = subprocess.run([str(omc), "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        om = None
    umo = ROOT / "third_party" / "urdfmodelica"
    try:
        head = subprocess.run(["git", "-C", str(umo), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        head = None
    uses = re.search(r"uses\(([^)]*\))\)", (urdfmodelica.UMO / "package.mo").read_text(encoding="utf-8"))
    return {"python": sys.version.split()[0], "urdf_parser_py": pkg("urdf_parser_py"), "openmodelica": om,
            "converter_checkout_head": head, "converter_pinned": urdfmodelica.CONVERTER_COMMIT,
            "converter_head_matches_pin": head == urdfmodelica.CONVERTER_COMMIT,
            "converter_uses": uses.group(1) if uses else None}


def run(source: str, out: Path | None = None, check_reproducible: bool = True, log=print) -> dict:
    urdf, meta = sources.resolve(source)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = out or RUNS / f"{source}-{stamp}"
    st = out / "stage1"
    if st.exists():
        shutil.rmtree(st)
    (st / "input").mkdir(parents=True)
    shutil.copy2(urdf, st / "input" / urdf.name)  # the exact URDF that was converted
    robot = load_urdf(urdf)

    log(f"[stage1] converting {source} with DLR URDFModelica {urdfmodelica.CONVERTER_COMMIT[:8]}")
    conv = urdfmodelica.convert(urdf, st / "convert")
    if not conv.get("main_file"):
        manifest = {"schema": SCHEMA, "source": source, "ok": False, "error": conv.get("error"), "converter": conv}
        (st / "manifest.json").write_text(json.dumps(manifest, indent=1, default=str), encoding="utf-8")
        return manifest
    pkg_dir = Path(conv["main_file"]).parent
    gen_hashes = _generated_hashes(pkg_dir)

    repro = None
    if check_reproducible:
        log("[stage1] converting a second time to check reproducibility")
        again = urdfmodelica.convert(urdf, st / "repro")
        h2 = _generated_hashes(Path(again["main_file"]).parent) if again.get("main_file") else {}
        diff = sorted(k for k in set(gen_hashes) | set(h2) if gen_hashes.get(k) != h2.get(k))
        repro = {"identical": not diff and bool(h2), "files_compared": len(gen_hashes), "differing_files": diff}
        shutil.rmtree(st / "repro", ignore_errors=True)  # only the comparison is kept

    mapping = build_mapping(robot, pkg_dir, Path(conv["main_file"]))
    table = physical_table(robot, mapping, pkg_dir)
    log_text = (st / "convert" / "converter.log").read_text(encoding="utf-8")
    unsup = unsupported(urdf, robot, mapping, pkg_dir, conv["preprocessing"], log_text)
    assets = urdf_assets(urdf)

    mismatches = [r for r in table if not r["match"]]
    manifest = {
        "schema": SCHEMA, "created": dt.datetime.now().isoformat(timespec="seconds"), "ok": True,
        "source": {"id": source, "label": meta.get("label"), "provenance": meta.get("provenance"),
                   "license": meta.get("license"), "urdf": _rel(urdf), "urdf_sha256": sha256_file(urdf),
                   "robot": robot.name, "links": len(robot.links), "joints": len(robot.joints),
                   "movable_joints": sum(1 for j in robot.joints.values() if j.movable)},
        "assets": {"count": len(assets), "resolved": sum(a["resolved"] for a in assets), "files": assets},
        "urdf_features": urdf_features(urdf),
        "converter": {"name": "DLR URDFModelica", "repo": "https://github.com/DLR-RM/urdfmodelica",
                      "commit": conv["converter_commit"], "args": conv.get("converter_args"),
                      "preprocessing": conv["preprocessing"], "returncode": conv.get("returncode"),
                      "seconds": conv["seconds"], "log_file": _rel(st / "convert" / "converter.log"),
                      "warnings": [l.strip() for l in log_text.splitlines() if re.search(r"warn|unknown|error", l, re.I)]},
        "versions": _versions(),
        "generated": {"package_dir": _rel(pkg_dir), "package_file": _rel(Path(conv["package_file"])),
                      "test_model": conv["model"], "files": gen_hashes},
        "reproducibility": repro,
        "summary": {"mapped_links": sum(1 for m in mapping if m["kind"] == "link" and m["params_file"]),
                    "mapped_joints": sum(1 for m in mapping if m["kind"] == "joint" and m["params_file"]),
                    "unmapped": [m["urdf_name"] for m in mapping if not m["params_file"]],
                    "physical_values_compared": len(table), "physical_mismatches": len(mismatches),
                    "unsupported_items": len(unsup)},
        "notes": ["No AI and no correction is applied at this stage; the package is exactly the converter's output.",
                  "A matching record value means the converter copied the URDF value; whether the model uses it "
                  "correctly is tested by stage 2 (OpenModelica check, simulation, kinematics)."],
    }
    for name, data in (("manifest", manifest), ("mapping", mapping), ("physical_table", table), ("unsupported", unsup)):
        (st / f"{name}.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    log(f"[stage1] {manifest['summary']}; reproducible: {repro and repro['identical']}")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="pinned source id (e.g. aloha_vx300s) or upload-<hash>")
    ap.add_argument("--out", type=Path, help="run directory (default runs/workflow/<source>-<time>)")
    ap.add_argument("--no-repro", action="store_true", help="skip the second conversion")
    a = ap.parse_args()
    m = run(a.source, a.out, check_reproducible=not a.no_repro)
    print(json.dumps(m.get("summary", m), indent=1))


if __name__ == "__main__":
    main()
