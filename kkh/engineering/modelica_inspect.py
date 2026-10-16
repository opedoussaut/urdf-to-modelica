"""Lightweight Modelica source inspection (components, parameters, connections) and
structural-completeness measurement of a generated model against its URDF.

Completeness is measured from the Modelica text itself (not from the generator's own bookkeeping),
so it also applies to models produced by other workflows (URDFModelica, LLM-assisted, hand-written).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from .urdf_model import Robot

_DECL = re.compile(
    r"^\s*(?P<prefix>(?:parameter|constant|inner|outer|final|input|output)\s+)*"
    r"(?P<type>[A-Z][\w.]*)\s+(?P<name>\w+)(?P<dims>\[[^\]]*\])?\s*(?:\((?P<mods>.*?)\))?\s*"
    r"(?:=\s*(?P<value>[^\"]+?))?\s*(?:\"(?P<comment>[^\"]*)\")?\s*(?:annotation|;)", re.M | re.S)
_CONNECT = re.compile(r"connect\(\s*([\w.\[\]:]+)\s*,\s*([\w.\[\]:]+)\s*\)")
_CLASS = re.compile(r"^\s*(?:partial\s+)?(model|block|function|package|record|connector|type)\s+(\w+)\s*(?:\"([^\"]*)\")?",
                    re.M)


def _balanced_mods(text: str, start: int) -> str:
    depth, i = 0, start
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
        i += 1
    return ""


def parse_class(path: str | Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    m = _CLASS.search(text)
    kind, name, desc = (m.group(1), m.group(2), m.group(3)) if m else (None, None, None)
    body = text.split("\nequation", 1)
    decl_text = body[0]
    eq_text = body[1] if len(body) > 1 else ""
    comps = []
    for line_m in re.finditer(r"^  (?!annotation)(?P<line>(?:parameter |constant |inner |final )*[A-Z][\w.]*(?:\[[^\]]*\])? \w+.*?)(?=\n  \S|\nequation|\nend |\Z)",
                              decl_text, re.M | re.S):
        line = line_m.group("line")
        dm = re.match(r"(?P<prefix>(?:(?:parameter|constant|inner|final) )*)(?P<type>[A-Z][\w.]*)(?P<tdims>\[[^\]]*\])? (?P<name>\w+)(?P<dims>\[[^\]]*\])?", line)
        if not dm:
            continue
        rest = line[dm.end():]
        mods = _balanced_mods(rest, rest.find("(")) if rest.lstrip().startswith("(") else ""
        after = rest[rest.find(mods) + len(mods) + 1:] if mods else rest
        cm = re.search(r"\"([^\"]*)\"", after)
        vm = re.match(r"\s*=\s*([^\"]+?)\s*(?:\"|annotation|;|$)", after)
        comps.append({"name": dm.group("name"), "type": dm.group("type"),
                      "prefix": dm.group("prefix").strip(), "dims": (dm.group("tdims") or "") + (dm.group("dims") or ""),
                      "modifiers": mods, "value": vm.group(1).strip() if vm else None,
                      "comment": cm.group(1) if cm else ""})
    connects = [list(c) for c in _CONNECT.findall(eq_text)]
    equations = [l.strip() for l in eq_text.split("annotation (")[0].splitlines()
                 if l.strip() and not l.strip().startswith(("connect(", "//", "end ", "annotation"))]
    return {"kind": kind, "name": name, "description": desc, "components": comps, "connections": connects,
            "equations": equations, "source": text}


def parse_modifiers(mods: str) -> dict[str, str]:
    out, depth, cur = {}, 0, ""
    parts = []
    for c in mods:
        if c in "({[":
            depth += 1
        elif c in ")}]":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    if cur.strip():
        parts.append(cur)
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _arr(s: str) -> np.ndarray:
    return np.array([float(x) for x in s.strip("{} ").split(",")])


def completeness(robot: Robot, class_file: str | Path, link_name=lambda l: l, joint_name=lambda j: "j_" + j) -> dict:
    """Coverage of URDF links/joints/connections/axes/limits in a generated arm class."""
    cls = parse_class(class_file)
    comps = {c["name"]: c for c in cls["components"]}
    conns = {tuple(c) for c in cls["connections"]}
    links_ok = [l for l in robot.links if link_name(l) in comps]
    joints_ok, conn_ok, axis_ok, limit_ok, axis_checked, limit_checked = [], [], [], [], 0, 0
    issues = []
    for jn, j in robot.joints.items():
        c = comps.get(joint_name(jn))
        if c is None:
            issues.append(f"joint {jn}: no component")
            continue
        joints_ok.append(jn)
        mods = parse_modifiers(c["modifiers"])
        pa, ch = link_name(j.parent), link_name(j.child)
        if (f"{pa}.frame_a", f"{joint_name(jn)}.frame_a") in conns and (f"{joint_name(jn)}.frame_b", f"{ch}.frame_a") in conns:
            conn_ok.append(jn)
        else:
            issues.append(f"joint {jn}: parent/child connection missing")
        if j.movable:
            axis_checked += 1
            if "n" in mods and np.allclose(_arr(mods["n"]), j.axis, atol=1e-12):
                axis_ok.append(jn)
            else:
                issues.append(f"joint {jn}: axis mismatch ({mods.get('n')} vs {j.axis.tolist()})")
        if "r" in mods and not np.allclose(_arr(mods["r"]), j.origin.xyz, atol=1e-12):
            issues.append(f"joint {jn}: origin xyz mismatch")
        if "rpy" in mods and not np.allclose(_arr(mods["rpy"]), j.origin.rpy, atol=1e-12):
            issues.append(f"joint {jn}: origin rpy mismatch")
        if j.type in ("revolute", "prismatic"):
            limit_checked += 1
            lo, hi = ("q_min", "q_max") if j.type == "revolute" else ("s_min", "s_max")
            if lo in mods and abs(float(mods[lo]) - j.limit.lower) < 1e-9 and abs(float(mods[hi]) - j.limit.upper) < 1e-9:
                limit_ok.append(jn)
            else:
                issues.append(f"joint {jn}: limits missing or different")
    disconnected = [c for c in comps if c in {link_name(l) for l in robot.links}
                    and not any(c + ".frame_a" in pair for pair in conns)]
    ratio = lambda a, b: round(len(a) / b, 4) if b else 1.0
    return {
        "class": cls["name"], "links": f"{len(links_ok)}/{len(robot.links)}", "link_coverage": ratio(links_ok, len(robot.links)),
        "joints": f"{len(joints_ok)}/{len(robot.joints)}", "joint_coverage": ratio(joints_ok, len(robot.joints)),
        "connection_coverage": ratio(conn_ok, len(robot.joints)),
        "axis_correctness": ratio(axis_ok, axis_checked), "limit_coverage": ratio(limit_ok, limit_checked),
        "disconnected_links": disconnected, "issues": issues,
        "complete": not issues and not disconnected and len(links_ok) == len(robot.links),
    }
