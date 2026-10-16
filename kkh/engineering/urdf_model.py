"""URDF parsing, structural validation and reference forward kinematics (generic, robot-agnostic).

The FK here is an independent implementation (numpy, URDF conventions) used to validate the
kinematics of generated Modelica models. It shares no code with the Modelica generator.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

# Links whose inertial is a URDF "placeholder" (tiny mass, isotropic dummy inertia, no geometry)
# are treated as massless reference frames. Threshold is a documented derivation rule.
PLACEHOLDER_MASS = 1e-3


def _vec(s: str | None, default=(0.0, 0.0, 0.0)) -> np.ndarray:
    return np.array([float(x) for x in s.split()]) if s else np.array(default, dtype=float)


@dataclass
class Origin:
    xyz: np.ndarray = field(default_factory=lambda: np.zeros(3))
    rpy: np.ndarray = field(default_factory=lambda: np.zeros(3))

    @staticmethod
    def parse(el) -> "Origin":
        if el is None:
            return Origin()
        return Origin(_vec(el.get("xyz")), _vec(el.get("rpy")))

    def matrix(self) -> np.ndarray:
        T = np.eye(4)
        T[:3, :3] = rpy_to_matrix(self.rpy)
        T[:3, 3] = self.xyz
        return T


@dataclass
class Inertial:
    origin: Origin
    mass: float
    inertia: np.ndarray  # 3x3, about COM, resolved in inertial origin frame

    def inertia_in_link_frame(self) -> np.ndarray:
        """Inertia about COM resolved in the link frame: R I R^T."""
        R = rpy_to_matrix(self.origin.rpy)
        return R @ self.inertia @ R.T


@dataclass
class Visual:
    origin: Origin
    mesh: str | None
    scale: np.ndarray
    rgba: tuple | None = None


@dataclass
class Link:
    name: str
    inertial: Inertial | None
    visuals: list[Visual]

    @property
    def is_placeholder(self) -> bool:
        return (self.inertial is None or self.inertial.mass <= PLACEHOLDER_MASS) and not self.visuals


@dataclass
class Limit:
    lower: float | None
    upper: float | None
    effort: float | None
    velocity: float | None


@dataclass
class Joint:
    name: str
    type: str
    parent: str
    child: str
    origin: Origin
    axis: np.ndarray
    limit: Limit | None
    mimic: tuple[str, float, float] | None  # (joint, multiplier, offset)
    friction: float | None = None
    damping: float | None = None

    @property
    def movable(self) -> bool:
        return self.type in ("revolute", "continuous", "prismatic")

    @property
    def rotational(self) -> bool:
        return self.type in ("revolute", "continuous")


@dataclass
class Robot:
    name: str
    links: dict[str, Link]
    joints: dict[str, Joint]  # insertion order == URDF order
    source: str | None = None

    # ---------------------------------------------------------------- structure
    @property
    def root(self) -> str:
        children = {j.child for j in self.joints.values()}
        roots = [l for l in self.links if l not in children]
        if len(roots) != 1:
            raise ValueError(f"URDF must have exactly one root link, found {roots}")
        return roots[0]

    def child_joints(self, link: str) -> list[Joint]:
        return [j for j in self.joints.values() if j.parent == link]

    def parent_joint(self, link: str) -> Joint | None:
        for j in self.joints.values():
            if j.child == link:
                return j
        return None

    def topological_joints(self) -> list[Joint]:
        out, stack = [], [self.root]
        while stack:
            l = stack.pop(0)
            for j in self.child_joints(l):
                out.append(j)
                stack.append(j.child)
        return out

    def actuated_joints(self) -> list[Joint]:
        """Movable joints that are independently driven (mimic joints excluded), URDF order."""
        return [j for j in self.joints.values() if j.movable and j.mimic is None]

    def leaves(self) -> list[str]:
        parents = {j.parent for j in self.joints.values()}
        return [l for l in self.links if l not in parents]

    def validate_structure(self) -> dict:
        """Connectivity and naming checks. Returns a report; `ok` is False on any error."""
        errors, warnings = [], []
        names = list(self.joints)
        if len(set(names)) != len(names):
            errors.append("duplicate joint names")
        for j in self.joints.values():
            if j.parent not in self.links:
                errors.append(f"joint {j.name}: unknown parent link {j.parent}")
            if j.child not in self.links:
                errors.append(f"joint {j.name}: unknown child link {j.child}")
            if j.movable and abs(np.linalg.norm(j.axis) - 1.0) > 1e-9:
                errors.append(f"joint {j.name}: axis not unit length {j.axis.tolist()}")
            if j.type == "revolute" and (j.limit is None or j.limit.lower is None or j.limit.upper is None):
                errors.append(f"joint {j.name}: revolute without limits")
            if j.mimic and j.mimic[0] not in self.joints:
                errors.append(f"joint {j.name}: mimics unknown joint {j.mimic[0]}")
        try:
            root = self.root
            reached = {root} | {j.child for j in self.topological_joints()}
            missing = set(self.links) - reached
            if missing:
                errors.append(f"links not reachable from root: {sorted(missing)}")
        except ValueError as e:
            errors.append(str(e))
            root = None
        counts = {}
        for j in self.joints.values():
            counts[j.type] = counts.get(j.type, 0) + 1
        return {"ok": not errors, "errors": errors, "warnings": warnings, "root": root,
                "n_links": len(self.links), "n_joints": len(self.joints), "joint_types": counts,
                "n_actuated": len(self.actuated_joints()), "leaves": self.leaves()}

    def validate_inertials(self) -> list[dict]:
        """Physical plausibility of each inertial: mass > 0, PD tensor, triangle inequality."""
        out = []
        for l in self.links.values():
            rec = {"link": l.name, "placeholder": l.is_placeholder}
            if l.inertial is None:
                rec.update(status="absent")
            else:
                I = l.inertial.inertia
                ev = np.linalg.eigvalsh(I)
                tri = ev[0] + ev[1] >= ev[2] * (1 - 1e-6)
                rec.update(mass=l.inertial.mass, eig=ev.tolist(), positive_definite=bool(ev.min() > 0),
                           triangle_inequality=bool(tri),
                           status="placeholder" if l.is_placeholder else
                           ("ok" if ev.min() > 0 and tri and l.inertial.mass > 0 else "implausible"))
            out.append(rec)
        return out

    # ---------------------------------------------------------------- kinematics
    def joint_transform(self, j: Joint, q: float) -> np.ndarray:
        T = j.origin.matrix()
        M = np.eye(4)
        if j.rotational:
            M[:3, :3] = axis_angle(j.axis, q)
        elif j.type == "prismatic":
            M[:3, 3] = j.axis * q
        return T @ M

    def forward_kinematics(self, q: dict[str, float], base: np.ndarray | None = None,
                           apply_mimic: bool = True) -> dict[str, np.ndarray]:
        """Pose (4x4, in root frame or `base`) of every link. Mimic joints are resolved from their
        master unless apply_mimic is False (then the given mimic-joint values are used as-is)."""
        qq = dict(q)
        for j in self.joints.values():
            if j.mimic and apply_mimic:
                src, mult, off = j.mimic
                qq[j.name] = mult * qq.get(src, 0.0) + off
        poses = {self.root: np.eye(4) if base is None else base}
        for j in self.topological_joints():
            poses[j.child] = poses[j.parent] @ self.joint_transform(j, qq.get(j.name, 0.0))
        return poses


def rpy_to_matrix(rpy) -> np.ndarray:
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def axis_angle(axis, q) -> np.ndarray:
    a = np.asarray(axis, dtype=float)
    a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * K @ K


def load_urdf(path: str | Path, strip_prefix: str | None = None) -> Robot:
    path = Path(path)
    root = ET.parse(path).getroot()
    materials = {m.get("name"): m for m in root.findall("material")}

    def nm(s):
        if strip_prefix and s.startswith(strip_prefix):
            return s[len(strip_prefix):]
        return s

    links = {}
    for le in root.findall("link"):
        inertial = None
        ie = le.find("inertial")
        if ie is not None:
            i = ie.find("inertia")
            I = np.array([[float(i.get("ixx")), float(i.get("ixy")), float(i.get("ixz"))],
                          [float(i.get("ixy")), float(i.get("iyy")), float(i.get("iyz"))],
                          [float(i.get("ixz")), float(i.get("iyz")), float(i.get("izz"))]])
            inertial = Inertial(Origin.parse(ie.find("origin")), float(ie.find("mass").get("value")), I)
        visuals = []
        for ve in le.findall("visual"):
            me = ve.find("geometry/mesh")
            rgba = None
            mat = ve.find("material")
            if mat is not None:
                c = mat.find("color")
                if c is None and mat.get("name") in materials:
                    c = materials[mat.get("name")].find("color")
                if c is not None:
                    rgba = tuple(_vec(c.get("rgba")))
            visuals.append(Visual(Origin.parse(ve.find("origin")),
                                  me.get("filename") if me is not None else None,
                                  _vec(me.get("scale") if me is not None else None, (1, 1, 1)), rgba))
        links[nm(le.get("name"))] = Link(nm(le.get("name")), inertial, visuals)

    joints = {}
    for je in root.findall("joint"):
        lim = je.find("limit")
        limit = None
        if lim is not None:
            g = lambda k: float(lim.get(k)) if lim.get(k) is not None else None
            limit = Limit(g("lower"), g("upper"), g("effort"), g("velocity"))
        mi = je.find("mimic")
        mimic = None
        if mi is not None:
            mimic = (nm(mi.get("joint")), float(mi.get("multiplier", 1.0)), float(mi.get("offset", 0.0)))
        dyn = je.find("dynamics")
        joints[nm(je.get("name"))] = Joint(
            nm(je.get("name")), je.get("type"), nm(je.find("parent").get("link")), nm(je.find("child").get("link")),
            Origin.parse(je.find("origin")), _vec(je.find("axis").get("xyz") if je.find("axis") is not None else None,
                                                   (1, 0, 0)),
            limit, mimic,
            float(dyn.get("friction")) if dyn is not None and dyn.get("friction") else None,
            float(dyn.get("damping")) if dyn is not None and dyn.get("damping") else None)
    return Robot(root.get("name"), links, joints, str(path))
