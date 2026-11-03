"""Deterministic URDF -> Modelica (MSL MultiBody) generator. Generic: no robot-specific logic.

Produces self-contained Modelica text that depends only on the Modelica Standard Library:
  * `component_library()`   reusable link/joint/trajectory classes (placed in <Pkg>.Components / .Blocks)
  * `robot_class()`         one model per URDF tree, one component instance per URDF link and joint
  * `mapping`               URDF entity -> Modelica component path

Formulation: prescribed motion. Every independently driven joint is driven by a
Rotational/Translational `Move` source fed with analytic q, qd, qdd, so no actuator dynamics and
no invented parameters are needed. Bodies carry the source URDF mass/inertia (placeholder
inertials are rendered as massless frames and reported) so reaction torques are available.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

from .urdf_model import Joint, Link, Robot, rpy_to_matrix

MSL_VERSION = "4.1.0"

_KEYWORDS = set("""algorithm and annotation block break class connect connector constant constrainedby der
discrete each else elseif elsewhen encapsulated end enumeration equation expandable extends external false
final flow for function if import impure in initial inner input loop model not operator or outer output
package parameter partial protected public pure record redeclare replaceable return stream then true type
when while within time""".split())


def ident(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not s or s[0].isdigit():
        s = "_" + s
    if s in _KEYWORDS:
        s = s + "_"
    return s


def fmt(x: float) -> str:
    if abs(x) < 1e-15:
        return "0"
    return repr(float(round(x, 12)))


def vec(v) -> str:
    return "{" + ", ".join(fmt(x) for x in v) + "}"


def mat_rows(M) -> str:
    return "[" + "; ".join(", ".join(fmt(x) for x in row) for row in M) + "]"


# --------------------------------------------------------------------------------------------
# Component library (generic, emitted into the generated package)
# --------------------------------------------------------------------------------------------
def component_library(pkg: str) -> dict[str, str]:
    """Return {relative_path: modelica_text} for the reusable classes."""
    files = {}
    files["Components/package.mo"] = f'''within {pkg};
package Components "Generic link and joint components generated from URDF semantics"
  extends Modelica.Icons.Package;
  annotation (Documentation(info="<html><p>Reusable building blocks emitted by the KKH URDF-to-Modelica generator.
Each URDF <code>link</code> becomes a <code>RigidLink</code>; each URDF <code>joint</code> becomes a
<code>RevoluteJoint</code>, <code>PrismaticJoint</code> or <code>FixedJoint</code>.
URDF origins are applied with <code>FixedRotation</code> using the URDF roll-pitch-yaw convention
(extrinsic X-Y-Z, i.e. planar rotation sequence {{3,2,1}} with angles {{yaw,pitch,roll}}).</p></html>"));
end Components;
'''
    files["Components/package.order"] = "RigidLink\nRevoluteJoint\nPrismaticJoint\nFixedJoint\n"
    files["Components/RigidLink.mo"] = f'''within {pkg}.Components;
model RigidLink "URDF link: rigid body with optional source inertia and mesh visualisation"
  import SI = Modelica.Units.SI;
  Modelica.Mechanics.MultiBody.Interfaces.Frame_a frame_a "URDF link frame"
    annotation (Placement(transformation(extent={{{{-116,-16}},{{-84,16}}}})));
  parameter Boolean hasInertia = true "false = massless reference frame (URDF placeholder inertial)"
    annotation (Evaluate=true);
  parameter SI.Mass m = 0 "Mass (URDF inertial/mass)";
  parameter SI.Position r_CM[3] = {{0, 0, 0}} "Centre of mass in link frame (URDF inertial/origin/xyz)";
  parameter SI.Inertia I[3, 3] = zeros(3, 3)
    "Inertia about CM resolved in link frame (URDF tensor rotated by inertial/origin/rpy)";
  parameter Boolean hasShape = false "true if a source mesh is available" annotation (Evaluate=true);
  parameter String shapeFile = "" "Mesh URI (STL)";
  parameter SI.Position r_shape[3] = {{0, 0, 0}} "Mesh origin in link frame (URDF visual/origin/xyz)";
  parameter Real lengthDirection[3] = {{1, 0, 0}} "Mesh x-axis in link frame";
  parameter Real widthDirection[3] = {{0, 1, 0}} "Mesh y-axis in link frame";
  parameter Real meshScale = 1 "Mesh scale factor (URDF mesh/scale)";
  parameter Modelica.Mechanics.MultiBody.Types.Color color = {{40, 40, 40}};
  parameter Boolean animation = true "Enable mesh animation";
  Modelica.Mechanics.MultiBody.Parts.Body body(
    m = m, r_CM = r_CM,
    I_11 = I[1, 1], I_22 = I[2, 2], I_33 = I[3, 3], I_21 = I[2, 1], I_31 = I[3, 1], I_32 = I[3, 2],
    animation = false) if hasInertia
    annotation (Placement(transformation(extent={{{{-10,-10}},{{10,10}}}})));
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape shape(
    shapeType = shapeFile, r_shape = r_shape, lengthDirection = lengthDirection,
    widthDirection = widthDirection, length = meshScale, width = meshScale, height = meshScale,
    color = color, animation = animation) if hasShape
    annotation (Placement(transformation(extent={{{{-10,30}},{{10,50}}}})));
equation
  if not hasInertia and not hasShape then
    // Massless, invisible reference frame: contributes no force/torque to the connection set.
    frame_a.f = zeros(3);
    frame_a.t = zeros(3);
  end if;
  connect(frame_a, body.frame_a);
  connect(frame_a, shape.frame_a);
  annotation (Icon(graphics={{Rectangle(extent={{{{-100,30}},{{100,-30}}}}, fillColor={{160,160,164}},
    fillPattern=FillPattern.HorizontalCylinder, lineColor={{0,0,0}}),
    Text(extent={{{{-150,80}},{{150,40}}}}, textString="%name", textColor={{0,0,255}})}}));
end RigidLink;
'''
    joint_common = '''  import SI = Modelica.Units.SI;
  extends Modelica.Mechanics.MultiBody.Interfaces.PartialTwoFrames;
  parameter SI.Position r[3] = {0, 0, 0} "URDF joint/origin/xyz (in parent link frame)";
  parameter SI.Angle rpy[3] = {0, 0, 0} "URDF joint/origin/rpy";
'''
    files["Components/RevoluteJoint.mo"] = f'''within {pkg}.Components;
model RevoluteJoint "URDF revolute/continuous joint with prescribed motion (q, qd, qdd)"
{joint_common}  parameter Real n[3] = {{0, 0, 1}} "URDF joint/axis (in joint frame)";
  parameter Boolean limited = true "false for URDF continuous joints" annotation (Evaluate=true);
  parameter SI.Angle q_min = -Modelica.Constants.inf "URDF limit/lower";
  parameter SI.Angle q_max = Modelica.Constants.inf "URDF limit/upper";
  parameter SI.AngularVelocity qd_max = Modelica.Constants.inf "URDF limit/velocity";
  parameter SI.Torque tau_max = Modelica.Constants.inf "URDF limit/effort";
  Modelica.Blocks.Interfaces.RealInput q "Prescribed angle [rad]"
    annotation (Placement(transformation(origin={{-60,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qd "Prescribed angular velocity [rad/s]"
    annotation (Placement(transformation(origin={{0,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qdd "Prescribed angular acceleration [rad/s2]"
    annotation (Placement(transformation(origin={{60,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
  SI.Angle phi = joint.phi "Joint angle";
  SI.AngularVelocity w = der(joint.phi) "Joint angular velocity";
  SI.Torque tau = joint.axis.tau "Torque required at the joint axis";
  Modelica.Mechanics.MultiBody.Parts.FixedRotation origin(r = r,
    rotationType = Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence,
    sequence = {{3, 2, 1}}, angles = Modelica.Units.Conversions.to_deg({{rpy[3], rpy[2], rpy[1]}}),
    animation = false) annotation (Placement(transformation(extent={{{{-70,-10}},{{-50,10}}}})));
  Modelica.Mechanics.MultiBody.Joints.Revolute joint(n = n, useAxisFlange = true, animation = false,
    stateSelect = StateSelect.never)
    annotation (Placement(transformation(extent={{{{-10,-10}},{{10,10}}}})));
  Modelica.Mechanics.Rotational.Sources.Move move(useSupport = true)
    annotation (Placement(transformation(extent={{{{-10,40}},{{10,60}}}})));
equation
  move.u = {{q, qd, qdd}};
  connect(frame_a, origin.frame_a);
  connect(origin.frame_b, joint.frame_a);
  connect(joint.frame_b, frame_b);
  connect(move.flange, joint.axis);
  connect(move.support, joint.support);
  if limited then
    assert(phi >= q_min - 1e-6 and phi <= q_max + 1e-6, "Joint angle outside URDF limits",
      AssertionLevel.warning);
  end if;
  annotation (Icon(graphics={{Rectangle(extent={{{{-100,-60}},{{-20,60}}}}, fillColor={{192,192,192}},
    fillPattern=FillPattern.HorizontalCylinder), Rectangle(extent={{{{20,-60}},{{100,60}}}},
    fillColor={{192,192,192}}, fillPattern=FillPattern.HorizontalCylinder),
    Text(extent={{{{-150,-70}},{{150,-110}}}}, textString="%name", textColor={{0,0,255}})}}));
end RevoluteJoint;
'''
    files["Components/PrismaticJoint.mo"] = f'''within {pkg}.Components;
model PrismaticJoint "URDF prismatic joint with prescribed motion (s, v, a)"
{joint_common}  parameter Real n[3] = {{1, 0, 0}} "URDF joint/axis (in joint frame)";
  parameter SI.Position s_min = -Modelica.Constants.inf "URDF limit/lower";
  parameter SI.Position s_max = Modelica.Constants.inf "URDF limit/upper";
  parameter SI.Velocity v_max = Modelica.Constants.inf "URDF limit/velocity";
  parameter SI.Force f_max = Modelica.Constants.inf "URDF limit/effort";
  Modelica.Blocks.Interfaces.RealInput q "Prescribed position [m]"
    annotation (Placement(transformation(origin={{-60,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qd "Prescribed velocity [m/s]"
    annotation (Placement(transformation(origin={{0,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qdd "Prescribed acceleration [m/s2]"
    annotation (Placement(transformation(origin={{60,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
  SI.Position s = joint.s "Joint position";
  SI.Velocity v = der(joint.s) "Joint velocity";
  SI.Force f = joint.axis.f "Force required along the joint axis";
  Modelica.Mechanics.MultiBody.Parts.FixedRotation origin(r = r,
    rotationType = Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence,
    sequence = {{3, 2, 1}}, angles = Modelica.Units.Conversions.to_deg({{rpy[3], rpy[2], rpy[1]}}),
    animation = false) annotation (Placement(transformation(extent={{{{-70,-10}},{{-50,10}}}})));
  Modelica.Mechanics.MultiBody.Joints.Prismatic joint(n = n, useAxisFlange = true, animation = false,
    stateSelect = StateSelect.never)
    annotation (Placement(transformation(extent={{{{-10,-10}},{{10,10}}}})));
  Modelica.Mechanics.Translational.Sources.Move move(useSupport = true)
    annotation (Placement(transformation(extent={{{{-10,40}},{{10,60}}}})));
equation
  move.u = {{q, qd, qdd}};
  connect(frame_a, origin.frame_a);
  connect(origin.frame_b, joint.frame_a);
  connect(joint.frame_b, frame_b);
  connect(move.flange, joint.axis);
  connect(move.support, joint.support);
  assert(s >= s_min - 1e-9 and s <= s_max + 1e-9, "Joint position outside URDF limits",
    AssertionLevel.warning);
  annotation (Icon(graphics={{Rectangle(extent={{{{-100,-50}},{{-30,50}}}}, fillColor={{192,192,192}},
    fillPattern=FillPattern.Solid), Rectangle(extent={{{{-30,-30}},{{100,30}}}}, fillColor={{230,230,230}},
    fillPattern=FillPattern.Solid), Text(extent={{{{-150,-70}},{{150,-110}}}}, textString="%name",
    textColor={{0,0,255}})}}));
end PrismaticJoint;
'''
    files["Components/FixedJoint.mo"] = f'''within {pkg}.Components;
model FixedJoint "URDF fixed joint: constant transform from parent to child link frame"
{joint_common}  Modelica.Mechanics.MultiBody.Parts.FixedRotation origin(r = r,
    rotationType = Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence,
    sequence = {{3, 2, 1}}, angles = Modelica.Units.Conversions.to_deg({{rpy[3], rpy[2], rpy[1]}}),
    animation = false) annotation (Placement(transformation(extent={{{{-10,-10}},{{10,10}}}})));
equation
  connect(frame_a, origin.frame_a);
  connect(origin.frame_b, frame_b);
  annotation (Icon(graphics={{Rectangle(extent={{{{-100,10}},{{100,-10}}}}, fillColor={{95,95,95}},
    fillPattern=FillPattern.Solid), Text(extent={{{{-150,-30}},{{150,-70}}}}, textString="%name",
    textColor={{0,0,255}})}}));
end FixedJoint;
'''
    files["Blocks/package.mo"] = f'''within {pkg};
package Blocks "Signal sources for prescribed-motion experiments"
  extends Modelica.Icons.Package;
end Blocks;
'''
    files["Blocks/package.order"] = "cosineBlend\nWaypointTrajectory\n"
    files["Blocks/cosineBlend.mo"] = f'''within {pkg}.Blocks;
function cosineBlend "Position (order 0), velocity (1) or acceleration (2) of a cosine-blended waypoint path"
  extends Modelica.Icons.Function;
  input Real t "Time";
  input Real t_wp[:] "Waypoint times (strictly increasing)";
  input Real q_wp[size(t_wp, 1)] "Waypoint values";
  input Integer order "0: position, 1: velocity, 2: acceleration";
  output Real y;
protected
  Integer nWp = size(t_wp, 1);
  Integer k = nWp - 1;
  Real T, s, dq;
algorithm
  if t <= t_wp[1] then
    y := if order == 0 then q_wp[1] else 0;
  elseif t >= t_wp[nWp] then
    y := if order == 0 then q_wp[nWp] else 0;
  else
    for i in 1:nWp - 1 loop
      if t < t_wp[i + 1] then
        k := i;
        break;
      end if;
    end for;
    T := t_wp[k + 1] - t_wp[k];
    s := (t - t_wp[k]) / T;
    dq := q_wp[k + 1] - q_wp[k];
    if order == 0 then
      y := q_wp[k] + dq * (1 - cos(Modelica.Constants.pi * s)) / 2;
    elseif order == 1 then
      y := dq * Modelica.Constants.pi / (2 * T) * sin(Modelica.Constants.pi * s);
    else
      y := dq * (Modelica.Constants.pi / T)^2 / 2 * cos(Modelica.Constants.pi * s);
    end if;
  end if;
end cosineBlend;
'''
    files["Blocks/WaypointTrajectory.mo"] = f'''within {pkg}.Blocks;
block WaypointTrajectory "Smooth multi-axis waypoint trajectory with analytic q, qd, qdd (cosine blend)"
  extends Modelica.Blocks.Icons.Block;
  parameter Integer n = 1 "Number of axes";
  parameter Integer nWp = 2 "Number of waypoints";
  parameter Modelica.Units.SI.Time t_wp[nWp] "Waypoint times (strictly increasing)";
  parameter Real Q[nWp, n] "Waypoint positions (rows = waypoints)";
  Modelica.Blocks.Interfaces.RealOutput q[n] annotation (Placement(transformation(extent={{{{100,50}},{{120,70}}}})));
  Modelica.Blocks.Interfaces.RealOutput qd[n] annotation (Placement(transformation(extent={{{{100,-10}},{{120,10}}}})));
  Modelica.Blocks.Interfaces.RealOutput qdd[n] annotation (Placement(transformation(extent={{{{100,-70}},{{120,-50}}}})));
equation
  for j in 1:n loop
    q[j] = cosineBlend(time, t_wp, Q[:, j], 0);
    qd[j] = cosineBlend(time, t_wp, Q[:, j], 1);
    qdd[j] = cosineBlend(time, t_wp, Q[:, j], 2);
  end for;
  annotation (Documentation(info="<html><p>Between consecutive waypoints each axis follows
q(s) = Q<sub>k</sub> + (Q<sub>k+1</sub>-Q<sub>k</sub>)(1-cos &pi;s)/2, s = (t-t<sub>k</sub>)/T<sub>k</sub>.
Velocity is zero at every waypoint (C1 continuous); acceleration is analytic within each segment.
q, qd and qdd are exactly consistent, as required by the <code>Move</code> sources.</p></html>"));
end WaypointTrajectory;
'''
    return files


# --------------------------------------------------------------------------------------------
# Robot class generation
# --------------------------------------------------------------------------------------------
@dataclass
class ClassMapping:
    class_name: str
    links: dict[str, str] = field(default_factory=dict)   # urdf link -> component name
    joints: dict[str, str] = field(default_factory=dict)  # urdf joint -> component name
    actuated: list[str] = field(default_factory=list)     # urdf joint names in input order
    mimic: dict[str, tuple] = field(default_factory=dict)
    placeholders: list[str] = field(default_factory=list)
    missing_mesh: list[str] = field(default_factory=list)


def _shape_args(link: Link, mesh_uri) -> tuple[str, bool]:
    v = next((v for v in link.visuals if v.mesh), None)
    if v is None:
        return "hasShape = false", False
    R = rpy_to_matrix(v.origin.rpy)
    scale = float(v.scale[0])
    color = [int(255 * c) for c in v.rgba[:3]] if v.rgba else [40, 40, 40]
    return (f'hasShape = true, shapeFile = "{mesh_uri(v.mesh)}", r_shape = {vec(v.origin.xyz)}, '
            f'lengthDirection = {vec(R[:, 0])}, widthDirection = {vec(R[:, 1])}, meshScale = {fmt(scale)}, '
            f'color = {{{", ".join(str(c) for c in color)}}}, animation = animation'), True


def robot_class(robot: Robot, pkg: str, class_name: str, within: str, description: str,
                mesh_uri, doc_html: str = "") -> tuple[str, ClassMapping]:
    """Generate one Modelica model for a URDF tree.

    Interface: frame_a (root link), RealInput q/qd/qdd[nq] for actuated joints in URDF order.
    Mimic joints are driven from their master joint (multiplier, offset).
    """
    cm = ClassMapping(class_name)
    act = robot.actuated_joints()
    cm.actuated = [j.name for j in act]
    idx = {j.name: i + 1 for i, j in enumerate(act)}
    nq = len(act)
    decl, eqs = [], []

    # Layout: depth-first along the tree, links in column 0, joints in column 1.
    order = []

    def walk(link, depth):
        order.append(("link", link))
        for j in robot.child_joints(link):
            order.append(("joint", j.name))
            walk(j.child, depth + 1)
    walk(robot.root, 0)
    pos = {name: i for i, (_, name) in enumerate(order)}

    def place(name, col):
        y = 180 - 40 * pos[name]
        return f"annotation (Placement(transformation(origin={{{col}, {y}}}, extent={{{{-10,-10}},{{10,10}}}})))"

    for lname, link in robot.links.items():
        c = ident(lname)
        cm.links[lname] = c
        shape, has_mesh = _shape_args(link, mesh_uri)
        if link.is_placeholder:
            cm.placeholders.append(lname)
            args = f"hasInertia = false, {shape}"
            note = "massless frame: URDF inertial is a placeholder"
        else:
            ine = link.inertial
            I = ine.inertia_in_link_frame()
            args = (f"hasInertia = true, m = {fmt(ine.mass)}, r_CM = {vec(ine.origin.xyz)}, "
                    f"I = {mat_rows(I)}, {shape}")
            note = "URDF inertial"
        if not has_mesh:
            cm.missing_mesh.append(lname)
        decl.append(f'  {pkg}.Components.RigidLink {c}({args}) "URDF link {lname} ({note})"\n    {place(lname, -40)};')

    for jname, j in robot.joints.items():
        c = ident("j_" + jname)
        cm.joints[jname] = c
        common = f"r = {vec(j.origin.xyz)}, rpy = {vec(j.origin.rpy)}"
        if j.rotational:
            lim = j.limit
            limited = j.type == "revolute"
            extra = f", n = {vec(j.axis)}, limited = {'true' if limited else 'false'}"
            if limited:
                extra += f", q_min = {fmt(lim.lower)}, q_max = {fmt(lim.upper)}"
            if lim and lim.velocity is not None:
                extra += f", qd_max = {fmt(lim.velocity)}"
            if lim and lim.effort is not None:
                extra += f", tau_max = {fmt(lim.effort)}"
            cls = "RevoluteJoint"
        elif j.type == "prismatic":
            lim = j.limit
            extra = f", n = {vec(j.axis)}, s_min = {fmt(lim.lower)}, s_max = {fmt(lim.upper)}"
            if lim.velocity is not None:
                extra += f", v_max = {fmt(lim.velocity)}"
            if lim.effort is not None:
                extra += f", f_max = {fmt(lim.effort)}"
            cls = "PrismaticJoint"
        elif j.type == "fixed":
            extra, cls = "", "FixedJoint"
        else:
            raise NotImplementedError(f"joint type {j.type} ({jname}) not supported")
        decl.append(f'  {pkg}.Components.{cls} {c}({common}{extra}) "URDF joint {jname} ({j.type}): '
                    f'{j.parent} -> {j.child}"\n    {place(jname, 20)};')
        eqs.append(f"  connect({cm.links[j.parent]}.frame_a, {c}.frame_a);")
        eqs.append(f"  connect({c}.frame_b, {ident(j.child)}.frame_a);")
        if j.movable:
            if j.mimic is None:
                i = idx[jname]
                eqs.append(f"  connect(q[{i}], {c}.q);\n  connect(qd[{i}], {c}.qd);\n  connect(qdd[{i}], {c}.qdd);")
            else:
                src, mult, off = j.mimic
                cm.mimic[jname] = (src, mult, off)
                i = idx[src]
                eqs.append(f"  // URDF mimic: {jname} = {fmt(mult)} * {src} + {fmt(off)}\n"
                           f"  {c}.q = {fmt(mult)} * q[{i}] + {fmt(off)};\n"
                           f"  {c}.qd = {fmt(mult)} * qd[{i}];\n  {c}.qdd = {fmt(mult)} * qdd[{i}];")

    act_doc = ", ".join(f"{i + 1}: {j.name}" for i, j in enumerate(act))
    text = f'''within {within};
model {class_name} "{description}"
  parameter Boolean animation = true "Animate link meshes";
  constant Integer nq = {nq} "Number of independently driven joints";
  Modelica.Mechanics.MultiBody.Interfaces.Frame_a frame_a "Mount frame = URDF root link {robot.root}"
    annotation (Placement(transformation(extent={{{{-116,-16}},{{-84,16}}}})));
  Modelica.Blocks.Interfaces.RealInput q[nq] "Joint positions [rad or m]: {act_doc}"
    annotation (Placement(transformation(origin={{-60,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qd[nq] "Joint velocities"
    annotation (Placement(transformation(origin={{0,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qdd[nq] "Joint accelerations"
    annotation (Placement(transformation(origin={{60,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
{chr(10).join(decl)}
equation
  connect(frame_a, {cm.links[robot.root]}.frame_a);
{chr(10).join(eqs)}
  annotation (
    Icon(graphics={{Rectangle(extent={{{{-100,100}},{{100,-100}}}}, lineColor={{0,0,0}}, fillColor={{255,255,255}},
      fillPattern=FillPattern.Solid), Line(points={{{{-80,-80}},{{-40,0}},{{20,30}},{{60,70}}}}, thickness=1),
      Text(extent={{{{-150,150}},{{150,110}}}}, textString="%name", textColor={{0,0,255}})}}),
    Diagram(coordinateSystem(extent={{{{-100,-{40 * len(order) - 160}}},{{100,200}}}})),
    Documentation(info="<html>{doc_html}<p>Generated deterministically from <code>{robot.name}</code>:
{len(robot.links)} links, {len(robot.joints)} joints, {nq} independently driven joints ({act_doc}).</p></html>"));
end {class_name};
'''
    return text, cm
