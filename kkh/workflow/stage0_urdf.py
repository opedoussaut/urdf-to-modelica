"""Stage 0 - URDF compliance: is the input a valid URDF before anything is converted?

Three layers, each finding citing where its rule comes from:

  spec       the URDF XML specification on the ROS wiki (robot, link, joint, model pages): required elements and
             attributes, allowed joint types, <limit> required for revolute/prismatic joints, number formats,
             colour range, mimic references
  structure  "only tree structures can be represented" (urdf/XML/model): every joint references existing links, one
             parent per link, exactly one root, no cycles, no disconnected link
  physical   BEYOND the specification, labelled as such: masses, physically possible inertia (positive definite,
             triangle inequality), ordered limits, positive effort/velocity, mesh files that resolve, project rule for
             placeholder inertials

Output: stage0/compliance.json with {id, layer, rule, severity, blocking, element, entity, line, message, evidence,
source}. Verdict: "not compliant" (a spec or structure error), "physically implausible" (a physical error),
"compliant with warnings", "compliant". Stage 1 refuses to convert a non-compliant URDF (blocking findings).

    PYTHONPATH=. python -m kkh.workflow.stage0_urdf <source id or path to .urdf>
"""
from __future__ import annotations

import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

SCHEMA = "kkh.workflow.urdf_compliance/1"
WIKI = "https://wiki.ros.org/urdf/XML"
SRC = {"robot": f"{WIKI}/robot", "link": f"{WIKI}/link", "joint": f"{WIKI}/joint", "model": f"{WIKI}/model",
       "project": "CLAUDE.md (placeholder inertials: mass <= 1e-3 kg are rendered massless and reported)",
       "physics": "rigid-body mechanics (beyond the URDF specification)"}
JOINT_TYPES = ("revolute", "continuous", "prismatic", "fixed", "floating", "planar")
ROBOT_CHILDREN = {"link", "joint", "material", "transmission", "gazebo"}  # robot page + top-level material (link page)
GEOMETRIES = ("box", "cylinder", "sphere", "mesh")
PLACEHOLDER_MASS = 1e-3
_NUM = re.compile(r"^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$")


class _El(ET.Element):
    """Element that can carry its source line."""


def parse(path: Path) -> ET.Element:
    """ElementTree built with expat so every element keeps its source line (`el.line`); ElementTree alone does not."""
    from xml.parsers import expat
    p = expat.ParserCreate()
    stack: list[ET.Element] = []
    root: list[ET.Element] = []

    def start(tag, attrs):
        el = _El(tag, attrs)
        el.line = p.CurrentLineNumber
        (stack[-1].append(el) if stack else root.append(el))
        stack.append(el)

    p.StartElementHandler = start
    p.EndElementHandler = lambda tag: stack.pop()
    try:
        p.Parse(path.read_bytes(), True)
    except expat.ExpatError as exc:
        raise ET.ParseError(str(exc)) from exc
    return root[0]


def _floats(s: str | None, n: int | None = None) -> list[float] | None:
    """Space-separated finite numbers (exactly n if given), else None."""
    if s is None:
        return None
    parts = s.split()
    if (n is not None and len(parts) != n) or not parts or not all(_NUM.match(p) for p in parts):
        return None
    v = [float(p) for p in parts]
    return v if all(math.isfinite(x) for x in v) else None


class _Report:
    def __init__(self):
        self.findings: list[dict] = []

    def add(self, layer, rule, severity, el, entity, message, evidence="", source="joint"):
        self.findings.append({
            "id": f"U{len(self.findings) + 1:03d}", "layer": layer, "rule": rule, "severity": severity,
            "blocking": severity == "error", "element": el.tag if el is not None else None, "entity": entity,
            "line": getattr(el, "line", None), "message": message, "evidence": evidence, "source": SRC[source]})


def _origin(rep, el, owner, src):
    o = el.find("origin")
    if o is None:
        return
    for a in ("xyz", "rpy"):
        if o.get(a) is not None and _floats(o.get(a), 3) is None:
            rep.add("spec", f"{a}-format", "error", o, owner, f"<origin {a}> must be three numbers", f'{a}="{o.get(a)}"', src)


def _geometry(rep, holder, link, kind, base: Path | None, resolve):
    g = holder.find("geometry")
    if g is None:
        rep.add("spec", "geometry-required", "error", holder, link, f"<{kind}> requires a <geometry>", source="link")
        return
    shapes = [c for c in g if c.tag in GEOMETRIES]
    if len(shapes) != 1:
        rep.add("spec", "geometry-one-shape", "error", g, link,
                f"<geometry> must hold exactly one of box, cylinder, sphere, mesh (found {len(shapes)})",
                ", ".join(c.tag for c in g), "link")
        return
    s = shapes[0]
    need = {"box": [("size", 3)], "cylinder": [("radius", 1), ("length", 1)], "sphere": [("radius", 1)]}.get(s.tag, [])
    for attr, n in need:
        v = _floats(s.get(attr), n)
        if v is None:
            rep.add("spec", f"{s.tag}-{attr}", "error", s, link, f"<{s.tag}> requires {attr} as {n} number(s)",
                    f'{attr}="{s.get(attr)}"', "link")
        elif any(x <= 0 for x in v):
            rep.add("physical", f"{s.tag}-{attr}-positive", "warning", s, link, f"<{s.tag}> {attr} should be positive",
                    f'{attr}="{s.get(attr)}"', "physics")
    if s.tag == "mesh":
        if not s.get("filename"):
            rep.add("spec", "mesh-filename", "error", s, link, "<mesh> requires a filename", source="link")
        else:
            if s.get("scale") is not None and _floats(s.get("scale"), 3) is None:
                rep.add("spec", "mesh-scale", "error", s, link, "<mesh scale> must be three numbers", f'scale="{s.get("scale")}"', "link")
            if resolve and base is not None and resolve(base, s.get("filename")) is None:
                rep.add("physical", "mesh-resolves", "warning", s, link,
                        f"{kind} mesh file not found next to the URDF or in the pinned sources (shape only, no effect on physics)",
                        s.get("filename"), "link")


def _material(rep, m, owner, defined: set[str]):
    c = m.find("color")
    if c is not None:
        v = _floats(c.get("rgba"), 4)
        if v is None or any(x < 0 or x > 1 for x in v):
            rep.add("spec", "color-rgba", "error", c, owner, "<color rgba> must be four numbers in [0, 1]", f'rgba="{c.get("rgba")}"', "link")
    if c is None and m.find("texture") is None and m.get("name") and m.get("name") not in defined:
        rep.add("spec", "material-reference", "warning", m, owner,
                f"material '{m.get('name')}' has no colour or texture here and is not defined at robot level", source="link")


def _inertial(rep, link_el, name):
    i = link_el.find("inertial")
    if i is None:
        rep.add("physical", "no-inertial", "info", link_el, name,
                "no <inertial>: the specification defaults to zero mass and zero inertia (massless link)", source="link")
        return
    _origin(rep, i, name, "link")
    m_el, in_el = i.find("mass"), i.find("inertia")
    mass = _floats(m_el.get("value"), 1) if m_el is not None else None
    if m_el is None or mass is None:
        rep.add("spec", "mass-value", "error", m_el if m_el is not None else i, name, "<inertial> requires <mass value> (a number)", source="link")
    keys = ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")
    vals = {k: _floats(in_el.get(k), 1) for k in keys} if in_el is not None else {}
    if in_el is None or any(v is None for v in vals.values()):
        missing = [k for k in keys if vals.get(k) is None] if in_el is not None else list(keys)
        rep.add("spec", "inertia-attributes", "error", in_el if in_el is not None else i, name,
                "<inertial> requires <inertia> with numeric ixx, ixy, ixz, iyy, iyz, izz", "missing or invalid: " + ", ".join(missing), "link")
        vals = None
    if mass is not None:
        m = mass[0]
        if m < 0:
            rep.add("physical", "mass-positive", "error", m_el, name, "negative mass", f"mass = {m}", "physics")
        elif m == 0:
            rep.add("physical", "mass-zero", "warning", m_el, name, "mass is zero although <inertial> is given", "", "physics")
        elif m <= PLACEHOLDER_MASS:
            rep.add("physical", "placeholder-mass", "info", m_el, name,
                    f"mass {m:g} kg looks like a placeholder (<= {PLACEHOLDER_MASS:g} kg); treated as massless", "", "project")
    if vals:
        v = {k: x[0] for k, x in vals.items()}
        I = np.array([[v["ixx"], v["ixy"], v["ixz"]], [v["ixy"], v["iyy"], v["iyz"]], [v["ixz"], v["iyz"], v["izz"]]])
        if np.allclose(I, 0):
            if mass and mass[0] > PLACEHOLDER_MASS:
                rep.add("physical", "inertia-zero", "warning", in_el, name, "inertia is zero for a link with mass", "", "physics")
            return
        ev = np.linalg.eigvalsh(I)
        tol = 1e-12 * max(1.0, float(np.abs(ev).max()))
        if ev.min() <= -tol:
            rep.add("physical", "inertia-positive-definite", "error", in_el, name,
                    "inertia tensor is not positive (semi-)definite: physically impossible",
                    "principal moments " + ", ".join(f"{x:.4g}" for x in ev), "physics")
        else:
            a, b, c = sorted(ev)
            if a + b < c - 1e-9 * max(c, 1e-30):
                rep.add("physical", "inertia-triangle", "error", in_el, name,
                        "principal moments violate the triangle inequality (I1 + I2 >= I3): no real body has this inertia",
                        f"{a:.4g} + {b:.4g} < {c:.4g}", "physics")


def _joint(rep, j, name, joint_names):
    t = j.get("type")
    if t not in JOINT_TYPES:
        rep.add("spec", "joint-type", "error", j, name, f"joint type must be one of {', '.join(JOINT_TYPES)}", f'type="{t}"')
    for tag in ("parent", "child"):
        e = j.find(tag)
        if e is None or not e.get("link"):
            rep.add("spec", f"joint-{tag}", "error", e if e is not None else j, name, f"<{tag} link=...> is required")
    _origin(rep, j, name, "joint")
    ax = j.find("axis")
    if ax is not None:
        v = _floats(ax.get("xyz"), 3)
        if v is None:
            rep.add("spec", "axis-xyz", "error", ax, name, "<axis xyz> is required and must be three numbers", f'xyz="{ax.get("xyz")}"')
        elif t in ("revolute", "continuous", "prismatic", "planar"):
            n = math.sqrt(sum(x * x for x in v))
            if n == 0:
                rep.add("spec", "axis-nonzero", "error", ax, name, "joint axis is the zero vector", f'xyz="{ax.get("xyz")}"')
            elif abs(n - 1) > 1e-6:
                rep.add("spec", "axis-normalized", "warning", ax, name, "the axis vector should be normalized", f"|axis| = {n:.6g}")
    lim = j.find("limit")
    if t in ("revolute", "prismatic") and lim is None:
        rep.add("spec", "limit-required", "error", j, name, f"<limit> is required for {t} joints")
    if lim is not None:
        for a in ("effort", "velocity"):
            if _floats(lim.get(a), 1) is None:
                rep.add("spec", f"limit-{a}", "error", lim, name, f"<limit {a}> is required (a number)", f'{a}="{lim.get(a)}"')
        for a in ("lower", "upper"):
            if lim.get(a) is not None and _floats(lim.get(a), 1) is None:
                rep.add("spec", f"limit-{a}-format", "error", lim, name, f"<limit {a}> must be a number", f'{a}="{lim.get(a)}"')
        if t == "continuous" and (lim.get("lower") is not None or lim.get("upper") is not None):
            rep.add("spec", "continuous-no-bounds", "info", lim, name,
                    "lower/upper should be omitted for a continuous joint (they are ignored)")
        lo, up = _floats(lim.get("lower") or "0", 1), _floats(lim.get("upper") or "0", 1)
        if t in ("revolute", "prismatic") and lo and up:
            if lo[0] > up[0]:
                rep.add("physical", "limits-ordered", "error", lim, name, "lower limit is above the upper limit", f"{lo[0]} > {up[0]}", "physics")
            elif lo[0] == up[0]:
                rep.add("physical", "limits-range", "warning", lim, name,
                        "lower = upper: the joint cannot move (both default to 0 when omitted)", f"{lo[0]} = {up[0]}", "joint")
        for a in ("effort", "velocity"):
            v = _floats(lim.get(a), 1)
            if v and v[0] <= 0 and t != "fixed":
                rep.add("physical", f"{a}-positive", "warning", lim, name, f"{a} limit is {v[0]:g}: the joint cannot be driven", "", "physics")
    dyn = j.find("dynamics")
    if dyn is not None:
        for a in ("damping", "friction"):
            if dyn.get(a) is not None:
                v = _floats(dyn.get(a), 1)
                if v is None:
                    rep.add("spec", f"dynamics-{a}", "error", dyn, name, f"<dynamics {a}> must be a number", f'{a}="{dyn.get(a)}"')
                elif v[0] < 0:
                    rep.add("physical", f"{a}-nonnegative", "warning", dyn, name, f"negative {a}", f"{a} = {v[0]}", "physics")
    mim = j.find("mimic")
    if mim is not None:
        if not mim.get("joint"):
            rep.add("spec", "mimic-joint", "error", mim, name, "<mimic joint=...> is required")
        elif mim.get("joint") not in joint_names:
            rep.add("spec", "mimic-exists", "error", mim, name, f"mimics a joint that does not exist: '{mim.get('joint')}'")
        elif mim.get("joint") == name:
            rep.add("spec", "mimic-self", "error", mim, name, "a joint cannot mimic itself")
        for a in ("multiplier", "offset"):
            if mim.get(a) is not None and _floats(mim.get(a), 1) is None:
                rep.add("spec", f"mimic-{a}", "error", mim, name, f"<mimic {a}> must be a number", f'{a}="{mim.get(a)}"')
    sc = j.find("safety_controller")
    if sc is not None:
        if _floats(sc.get("k_velocity"), 1) is None:
            rep.add("spec", "safety-k-velocity", "error", sc, name, "<safety_controller k_velocity> is required")
        if lim is not None:
            lo, up = _floats(lim.get("lower") or "0", 1), _floats(lim.get("upper") or "0", 1)
            slo, sup = _floats(sc.get("soft_lower_limit") or "0", 1), _floats(sc.get("soft_upper_limit") or "0", 1)
            if lo and slo and sc.get("soft_lower_limit") is not None and slo[0] < lo[0]:
                rep.add("spec", "soft-lower-inside", "warning", sc, name, "soft_lower_limit should be larger than the lower limit", f"{slo[0]} < {lo[0]}")
            if up and sup and sc.get("soft_upper_limit") is not None and sup[0] > up[0]:
                rep.add("spec", "soft-upper-inside", "warning", sc, name, "soft_upper_limit should be smaller than the upper limit", f"{sup[0]} > {up[0]}")


def check(urdf: Path, resolve=None) -> dict:
    """Compliance record for one URDF file. `resolve(urdf, filename)` locates mesh files (optional)."""
    rep = _Report()
    try:
        root = parse(urdf)
    except ET.ParseError as exc:
        rep.add("spec", "xml-well-formed", "error", None, None, f"not well-formed XML: {exc}", source="model")
        return _finish(urdf, rep, {})
    if root.tag != "robot":
        rep.add("spec", "root-robot", "error", root, None, f"the root element must be <robot>, found <{root.tag}>", source="robot")
        return _finish(urdf, rep, {})
    if not root.get("name"):
        rep.add("spec", "robot-name", "error", root, None, "<robot> requires a name attribute", source="robot")
    for c in root:
        if isinstance(c.tag, str) and c.tag not in ROBOT_CHILDREN:
            rep.add("spec", "custom-element", "info", c, None,
                    f"<{c.tag}> is not a URDF element; URDF parsers ignore custom elements", source="link")
    links, joints = root.findall("link"), root.findall("joint")
    defined_materials = {m.get("name") for m in root.findall("material") if m.get("name")}
    for m in root.findall("material"):
        _material(rep, m, m.get("name"), set())
    names: dict[str, int] = {}
    for l in links:
        n = l.get("name")
        if not n:
            rep.add("spec", "link-name", "error", l, None, "<link> requires a name", source="link")
            continue
        if n in names:
            rep.add("structure", "link-unique", "error", l, n, f"link name '{n}' is used twice (first on line {names[n]})", source="model")
        names.setdefault(n, l.line)
        _inertial(rep, l, n)
        for kind in ("visual", "collision"):
            for v in l.findall(kind):
                _origin(rep, v, n, "link")
                _geometry(rep, v, n, kind, urdf, resolve)
                for m in v.findall("material"):
                    _material(rep, m, n, defined_materials)
    joint_names: dict[str, int] = {}
    for j in joints:
        n = j.get("name")
        if not n:
            rep.add("spec", "joint-name", "error", j, None, "<joint> requires a name")
            continue
        if n in joint_names:
            rep.add("spec", "joint-unique", "error", j, n, f"joint name '{n}' is used twice (first on line {joint_names[n]})")
        joint_names.setdefault(n, j.line)
    for j in joints:
        if j.get("name"):
            _joint(rep, j, j.get("name"), joint_names)
    # tree structure (urdf/XML/model: only tree structures can be represented)
    parent_of: dict[str, str] = {}
    edges: dict[str, list[str]] = {}
    for j in joints:
        p, c = (j.find("parent"), j.find("child"))
        p, c = (p.get("link") if p is not None else None), (c.get("link") if c is not None else None)
        jn = j.get("name")
        for role, l in (("parent", p), ("child", c)):
            if l and l not in names:
                rep.add("structure", "link-exists", "error", j, jn, f"{role} link '{l}' is not defined", source="model")
        if p and c and p == c:
            rep.add("structure", "no-self-joint", "error", j, jn, "parent and child are the same link", source="model")
        if c:
            if c in parent_of:
                rep.add("structure", "one-parent", "error", j, jn,
                        f"link '{c}' already has parent joint '{parent_of[c]}': a link can have only one parent (tree)", source="model")
            parent_of.setdefault(c, jn)
        if p and c:
            edges.setdefault(p, []).append(c)
    roots = [n for n in names if n not in parent_of]
    struct = {"links": len(names), "joints": len(joint_names), "roots": roots,
              "movable_joints": sum(1 for j in joints if j.get("type") in ("revolute", "continuous", "prismatic", "planar", "floating"))}
    if len(names) and len(roots) != 1:
        rep.add("structure", "single-root", "error", root, None,
                f"a URDF tree has exactly one root link; found {len(roots)}: {', '.join(roots[:6]) or 'none (cycle)'}", source="model")
    if len(roots) == 1:
        seen, stack = set(), [roots[0]]
        while stack:
            n = stack.pop()
            if n in seen:
                rep.add("structure", "no-cycle", "error", root, n, "the joints form a cycle (closed chain): not a tree", source="model")
                break
            seen.add(n)
            stack.extend(edges.get(n, []))
        unreachable = sorted(set(names) - seen)
        in_cycle: set[str] = set()
        for start in unreachable:  # a disconnected group whose parent chain loops back is a closed chain
            chain, n = [], start
            while n in parent_of and n not in chain:
                chain.append(n)
                n = next((c.find("parent").get("link") for c in joints
                          if c.get("name") == parent_of[n] and c.find("parent") is not None), None)
            if n in chain and not (set(chain) & in_cycle):
                loop = chain[chain.index(n):]
                in_cycle |= set(loop)
                rep.add("structure", "no-cycle", "error", root, loop[0],
                        f"the joints form a closed chain (not a tree): {' -> '.join(loop + [loop[0]])}", source="model")
        unreachable = [n for n in unreachable if n not in in_cycle]
        if unreachable:
            rep.add("structure", "connected", "error", root, None,
                    f"{len(unreachable)} link(s) are not connected to the root: {', '.join(unreachable[:6])}", source="model")
    return _finish(urdf, rep, struct)


def _finish(urdf: Path, rep: _Report, struct: dict) -> dict:
    f = rep.findings
    errors = [x for x in f if x["severity"] == "error"]
    spec_err = [x for x in errors if x["layer"] in ("spec", "structure")]
    if spec_err:
        verdict = "not compliant"
    elif errors:
        verdict = "physically implausible"
    elif any(x["severity"] == "warning" for x in f):
        verdict = "compliant with warnings"
    else:
        verdict = "compliant"
    counts = {f"{layer}_{sev}": sum(1 for x in f if x["layer"] == layer and x["severity"] == sev)
              for layer in ("spec", "structure", "physical") for sev in ("error", "warning", "info")}
    return {"schema": SCHEMA, "file": urdf.name, "verdict": verdict, "blocking": bool(errors), "structure": struct,
            "counts": counts, "findings": f,
            "specification": {"robot": SRC["robot"], "link": SRC["link"], "joint": SRC["joint"], "model": SRC["model"],
                              "read": "2026-10-26"},
            "verdict_rule": "not compliant = an error against the URDF specification or its tree structure; physically "
                            "implausible = an error only in the physical layer (beyond the specification); conversion "
                            "is refused while any error remains"}


def run(source: str, out: Path | None = None) -> dict:
    from kkh.convert import sources
    from kkh.convert.robot3d import resolve_mesh
    p = Path(source)
    urdf = p if p.suffix == ".urdf" and p.exists() else sources.resolve(source)[0]
    rec = check(urdf, resolve_mesh)
    if out is not None:
        (out / "stage0").mkdir(parents=True, exist_ok=True)
        (out / "stage0" / "compliance.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="pinned source id (e.g. so101) or a path to a .urdf file")
    a = ap.parse_args()
    rec = run(a.source)
    print(json.dumps({k: rec[k] for k in ("file", "verdict", "structure", "counts")}, indent=1))
    for x in rec["findings"]:
        if x["severity"] != "info":
            print(f"  {x['id']} {x['severity']:7s} {x['layer']:9s} line {x['line']}: {x['entity']}: {x['message']} {x['evidence']}")


if __name__ == "__main__":
    main()
