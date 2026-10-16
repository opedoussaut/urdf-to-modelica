"""Generate the ALOHA 2 Modelica package (deterministic) plus URDF<->Modelica mapping and provenance.

Output (default generated/modelica/):
  ALOHA2/ package.mo, Components/, Blocks/, Arms/{AlohaVX300s,AlohaWX250s}.mo, Aloha2.mo (assembly),
          Experiments/*.mo, Resources/Meshes/<model>/*.stl, Resources/Licenses/
  aloha2_mapping.json, build_record.json
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from kkh.engineering import modelica_gen as mg

from . import configuration as C
from .scenarios import arms_for, check_limits, scenarios

PKG = "ALOHA2"
ASSEMBLY = "Aloha2"
GENERATOR_VERSION = "1.1.0"
DESC_ROOT = C.ROOT / "third_party/interbotix_ros_manipulators/interbotix_ros_xsarms/interbotix_xsarm_descriptions"
OUT_ROOT = C.ROOT / "generated" / "modelica"


def _mesh_uri(mesh: str) -> str:
    parts = mesh.split("/")
    return f"modelica://{PKG}/Resources/Meshes/{parts[-2].replace('_meshes', '')}/{parts[-1]}"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git_head() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=C.ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _assembly() -> str:
    decl, eqs = [], []
    n = len(C.ACTUATED)
    for k, arm in enumerate(C.ARMS):
        cls, m = C.ARM_CLASS[arm["model"]], arm["modelica"]
        y = 40 - 60 * k
        rpy = arm["mount_rpy"]
        decl.append(
            f'  Modelica.Mechanics.MultiBody.Parts.FixedRotation mount_{m}(r = {mg.vec(arm["mount_xyz"])}, '
            f'rotationType = Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence, '
            f'sequence = {{3, 2, 1}}, angles = Modelica.Units.Conversions.to_deg({mg.vec([rpy[2], rpy[1], rpy[0]])}), '
            f'animation = false) "Base mount world -> {arm["id"]}/base_link ({C.MOUNT_SOURCE})"\n'
            f'    annotation (Placement(transformation(origin={{-40, {y}}}, extent={{{{-10,-10}},{{10,10}}}})));')
        decl.append(
            f'  {PKG}.Arms.{cls} {m}(animation = animation) "{C.ARM_PRODUCT[arm["model"]]}, {arm["side"]}"\n'
            f'    annotation (Placement(transformation(origin={{20, {y}}}, extent={{{{-10,-10}},{{10,10}}}})));')
        a, b = k * n + 1, (k + 1) * n
        eqs += [f"  connect(frame_a, mount_{m}.frame_a);", f"  connect(mount_{m}.frame_b, {m}.frame_a);",
                f"  connect(q[{a}:{b}], {m}.q);", f"  connect(qd[{a}:{b}], {m}.qd);", f"  connect(qdd[{a}:{b}], {m}.qdd);"]
    layout = "".join(f"<li>q[{k * n + 1}:{(k + 1) * n}] &rarr; {a['modelica']} ({', '.join(C.ACTUATED)})</li>"
                     for k, a in enumerate(C.ARMS))
    return f'''within {PKG};
model {ASSEMBLY} "ALOHA 2 robot: two follower ALOHA ViperX-300 6DOF arms at the official ALOHA 2 base poses"
  parameter Boolean animation = true "Animate link meshes";
  constant Integer nq = {n * len(C.ARMS)} "Number of independently driven joints ({len(C.ARMS)} arms x {n})";
  Modelica.Mechanics.MultiBody.Interfaces.Frame_a frame_a "Robot (world) frame"
    annotation (Placement(transformation(extent={{{{-116,-16}},{{-84,16}}}})));
  Modelica.Blocks.Interfaces.RealInput q[nq] "Joint positions, see documentation for layout"
    annotation (Placement(transformation(origin={{-60,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qd[nq] "Joint velocities"
    annotation (Placement(transformation(origin={{0,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qdd[nq] "Joint accelerations"
    annotation (Placement(transformation(origin={{60,120}}, extent={{{{-20,-20}},{{20,20}}}}, rotation=-90)));
{chr(10).join(decl)}
equation
{chr(10).join(eqs)}
  annotation (Icon(graphics={{Rectangle(extent={{{{-100,100}},{{100,-100}}}}, fillColor={{255,255,255}},
      fillPattern=FillPattern.Solid), Text(extent={{{{-90,40}},{{90,-40}}}}, textString="ALOHA 2"),
      Text(extent={{{{-150,150}},{{150,110}}}}, textString="%name", textColor={{0,0,255}})}}),
    Documentation(info="<html><p>Two follower arms mounted at the base poses of the official ALOHA 2 MuJoCo model
(<code>{C.SRC['mjcf']}</code>). Input layout:</p><ul>{layout}</ul>
<p>Right-finger joints follow the URDF mimic relation (right = -left).</p></html>"));
end {ASSEMBLY};
'''


def _experiment(name: str, sc: dict) -> str:
    rows = ";\n      ".join(", ".join(mg.fmt(x) for x in r) for r in np.array(sc["Q"]))
    if sc["target"] == "assembly":
        inst = f"  {PKG}.{ASSEMBLY} aloha annotation (Placement(transformation(extent={{{{-10,-10}},{{10,10}}}})));"
    else:
        inst = f"  {PKG}.Arms.{C.ARM_CLASS[C.LEADER['model']]} aloha annotation (Placement(transformation(extent={{{{-10,-10}},{{10,10}}}})));"
    return f'''within {PKG}.Experiments;
model {name} "{sc['title']}"
  extends Modelica.Icons.Example;
  inner Modelica.Mechanics.MultiBody.World world(n = {{0, 0, -1}}, axisLength = 0.2, animateGravity = false)
    annotation (Placement(transformation(extent={{{{-80,-10}},{{-60,10}}}})));
{inst}
  {PKG}.Blocks.WaypointTrajectory trajectory(n = aloha.nq, nWp = {len(sc['t'])},
    t_wp = {mg.vec(sc['t'])},
    Q = [{rows}]) annotation (Placement(transformation(extent={{{{-40,40}},{{-20,60}}}})));
equation
  connect(world.frame_b, aloha.frame_a);
  connect(trajectory.q, aloha.q);
  connect(trajectory.qd, aloha.qd);
  connect(trajectory.qdd, aloha.qdd);
  annotation (experiment(StartTime = 0, StopTime = {mg.fmt(sc['stop_time'])}, Interval = 0.02, Tolerance = 1e-06),
    Documentation(info="<html><p>{sc['description']}</p><p>Output interval 0.02 s = ALOHA control period
(aloha/constants.py DT). Prescribed motion, no actuator dynamics; joint efforts are the inverse-dynamics
reactions of the URDF inertials under gravity.</p></html>"));
end {name};
'''


def variable_filter(sc: dict) -> str:
    p = r"aloha\.[A-Za-z]+\." if sc["target"] == "assembly" else r"aloha\."
    return rf"time|{p}j_[A-Za-z_]+\.(phi|w|tau|s|v|f)|{p}[A-Za-z_]+_link\.frame_a\.(r_0|R\.T)\[.*"


def _arm_mapping(arm: dict, cm, prefix: str, base_index: int) -> dict:
    """prefix: Modelica instance path inside the experiment ('aloha.left' or 'aloha')."""
    ns = arm["id"]
    return {
        "arm": ns, "model": arm["model"], "modelica_instance": prefix, "class": f"{PKG}.Arms.{cm.class_name}",
        "links": [{"urdf": f"{ns}/{l}", "urdf_local": l, "modelica": f"{prefix}.{c}",
                   "placeholder": l in cm.placeholders, "mesh": l not in cm.missing_mesh,
                   "result_vars": {"r_0": [f"{prefix}.{c}.frame_a.r_0[{i}]" for i in (1, 2, 3)],
                                   "R": [f"{prefix}.{c}.frame_a.R.T[{i},{j}]" for i in (1, 2, 3) for j in (1, 2, 3)]}}
                  for l, c in cm.links.items()],
        "joints": [{"urdf": f"{ns}/{jn}", "urdf_local": jn, "modelica": f"{prefix}.{c}",
                    "driven_index": base_index + cm.actuated.index(jn) + 1 if jn in cm.actuated else None,
                    "mimic": cm.mimic.get(jn)} for jn, c in cm.joints.items()],
    }


# Follower servo parameters used by the dynamic (torque-driven) follower experiments of the studio.
# They are ASSUMED illustrative values (no identified hardware data exists); bounds are declared in Modelica so that
# editors and AI proposals can be checked against them.
SERVO_DEFAULTS = {"kp": 40.0, "kd": 4.0, "actuatorTime": 0.03, "feedforward": 0.0}
SERVO_BOUNDS = {"kp": (1, 500), "kd": (0, 80), "actuatorTime": (0.005, 0.3), "feedforward": (0, 1)}
SERVO_JOINTS = ["waist", "shoulder", "elbow", "forearm_roll", "wrist_angle", "wrist_rotate"]


def control_package() -> dict[str, str]:
    files = {}
    files["Control/package.mo"] = f'''within {PKG};
package Control "Follower servo settings for dynamic follower experiments (assumed values, not hardware-identified)"
  extends Modelica.Icons.Package;
end Control;
'''
    files["Control/package.order"] = "ServoGains\nFollowerServoSettings\n"
    b = SERVO_BOUNDS
    files["Control/ServoGains.mo"] = f'''within {PKG}.Control;
record ServoGains "Joint servo parameters of the follower (assumed, illustrative; not identified on hardware)"
  extends Modelica.Icons.Record;
  parameter Real kp(unit = "N.m/rad", min = {b["kp"][0]}, max = {b["kp"][1]}) = {SERVO_DEFAULTS["kp"]} "Proportional position gain";
  parameter Real kd(unit = "N.m.s/rad", min = {b["kd"][0]}, max = {b["kd"][1]}) = {SERVO_DEFAULTS["kd"]} "Derivative (velocity) gain";
  parameter Modelica.Units.SI.Time actuatorTime(min = {b["actuatorTime"][0]}, max = {b["actuatorTime"][1]}) = {SERVO_DEFAULTS["actuatorTime"]} "First-order torque lag of the actuator";
  parameter Real feedforward(unit = "1", min = {b["feedforward"][0]}, max = {b["feedforward"][1]}) = {SERVO_DEFAULTS["feedforward"]} "Inverse-dynamics feed-forward gain (0 off, 1 full)";
end ServoGains;
'''
    servo = {"aloha_vx300s": C.ACTUATORS["aloha_vx300s"]}
    decl = []
    for j in SERVO_JOINTS:
        models = "+".join(servo["aloha_vx300s"][j])
        ids = ",".join(str(i) for i in C.SERVO_IDS[j])
        args = ", ".join(f"{k} = {v}" for k, v in SERVO_DEFAULTS.items())
        decl.append(f'  parameter {PKG}.Control.ServoGains {j}({args}) "Follower servo for URDF joint {j} ({models}, ID {ids})";')
    files["Control/FollowerServoSettings.mo"] = f'''within {PKG}.Control;
model FollowerServoSettings "Servo settings of the follower arm, read by the dynamic follower experiment"
{chr(10).join(decl)}
  annotation (Documentation(info="<html><p>One <code>ServoGains</code> instance per torque-driven follower joint.
Values are assumptions for illustration (no identified motor, transmission, friction or latency data is public);
edit them here, in the Modelica editor or OMEdit. The studio reads them from the revision being simulated.</p></html>"));
end FollowerServoSettings;
'''
    return files


def build(out_root: Path | None = None) -> dict:
    out_root = out_root or OUT_ROOT
    pkg_dir = out_root / PKG
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    files = dict(mg.component_library(PKG))
    cms = {}
    for model, cls in C.ARM_CLASS.items():
        doc = (f"<p><b>{C.ARM_PRODUCT[model]}</b>. Source: <code>{model}.urdf.xacro</code> "
               f"({C.SRC['descriptions']}), BSD-3-Clause.</p>")
        text, cm = mg.robot_class(C.arm_robot(model), PKG, cls, f"{PKG}.Arms",
                                  f"{C.ARM_PRODUCT[model]} ({model} URDF)", _mesh_uri, doc)
        files[f"Arms/{cls}.mo"] = text
        cms[model] = cm
    files["Arms/package.mo"] = f'within {PKG};\npackage Arms "Arm models generated one-to-one from URDF"\n  extends Modelica.Icons.Package;\nend Arms;\n'
    files["Arms/package.order"] = "\n".join(C.ARM_CLASS.values()) + "\n"
    files[f"{ASSEMBLY}.mo"] = _assembly()

    scs = scenarios()
    for name, sc in scs.items():
        errs = check_limits(sc)
        if errs:
            raise ValueError(f"Scenario {name} violates URDF limits: {errs}")
        files[f"Experiments/{name}.mo"] = _experiment(name, sc)
    files["Experiments/package.mo"] = f'within {PKG};\npackage Experiments "Prescribed-motion simulation experiments"\n  extends Modelica.Icons.ExamplesPackage;\nend Experiments;\n'
    files["Experiments/package.order"] = "\n".join(scs) + "\n"

    totals = C.build_manifest()["totals"]
    files["package.mo"] = f'''within ;
package {PKG} "ALOHA 2 robot generated from public engineering sources (URDF, kinematic / prescribed-motion)"
  extends Modelica.Icons.Package;
  annotation (
    uses(Modelica(version = "{mg.MSL_VERSION}")),
    version = "{GENERATOR_VERSION}",
    Documentation(info="<html>
<h4>ALOHA 2 virtual twin</h4>
<p>Generated by the K&amp;KH Engineering Studio generator v{GENERATOR_VERSION} from pinned public sources:</p>
<ul><li>{C.SRC['descriptions']} (URDF/xacro, meshes)</li><li>{C.SRC['mjcf']} (base poses only)</li>
<li>{C.SRC['constants']} (start pose, gripper constants)</li></ul>
<p>Robot: {totals['links']} links (incl. world), {totals['joints']} joints, {totals['driven']} driven joints,
{totals['mimic']} mimic joints. One <code>Components.RigidLink</code> per URDF link and one joint component per URDF joint.
Masses and inertias are URDF values; URDF placeholder inertials are massless.</p>
<p>Run <code>{PKG}.Experiments.RightArmReach</code>. Meshes: Interbotix, BSD-3-Clause (Resources/Licenses).</p></html>"));
end {PKG};
'''
    files.update(control_package())
    files["package.order"] = f"Components\nBlocks\nArms\nControl\n{ASSEMBLY}\nExperiments\n"
    for rel, text in files.items():
        _write(pkg_dir / rel, text)
    for model in C.ARM_CLASS:
        dst = pkg_dir / "Resources" / "Meshes" / model
        dst.mkdir(parents=True, exist_ok=True)
        for f in sorted((DESC_ROOT / "meshes" / f"{model}_meshes").glob("*.stl")):
            shutil.copy2(f, dst / f.name)
    lic = C.ROOT / "third_party/interbotix_ros_manipulators/LICENSE"
    (pkg_dir / "Resources" / "Licenses").mkdir(parents=True, exist_ok=True)
    if lic.exists():
        shutil.copy2(lic, pkg_dir / "Resources" / "Licenses" / "Interbotix_LICENSE.txt")

    n = len(C.ACTUATED)
    mapping = {"package": PKG, "assembly": f"{PKG}.{ASSEMBLY}",
               "arms": [dict(_arm_mapping(a, cms[a["model"]], f"aloha.{a['modelica']}", k * n),
                             mount={"modelica": f"aloha.mount_{a['modelica']}", "urdf_joint": f"{a['id']}_mount",
                                    "xyz": a["mount_xyz"], "rpy": a["mount_rpy"]})
                        for k, a in enumerate(C.ARMS)],
               "leader": _arm_mapping(C.LEADER, cms[C.LEADER["model"]], "aloha", 0),
               "classes": {m: {"class": f"{PKG}.Arms.{cm.class_name}", "links": cm.links, "joints": cm.joints,
                               "actuated": cm.actuated, "placeholders": cm.placeholders} for m, cm in cms.items()}}
    _write(out_root / "aloha2_mapping.json", json.dumps(mapping, indent=1))
    record = {
        "generator": "kkh.domain.aloha.build", "generator_version": GENERATOR_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "repo_commit": _git_head(), "msl_version": mg.MSL_VERSION,
        "inputs": {str(p.relative_to(C.ROOT)).replace("\\", "/"): _sha(p) for p in
                   [C.URDF_DIR / f"{m}.urdf" for m in C.ARM_CLASS]},
        "files": {rel: hashlib.sha256(t.encode()).hexdigest() for rel, t in sorted(files.items())},
        "totals": totals,
        "scenarios": {k: {"target": v["target"], "t": v["t"], "stop_time": v["stop_time"]} for k, v in scs.items()},
        "placeholders": {m: cm.placeholders for m, cm in cms.items()},
        "links_without_mesh": {m: cm.missing_mesh for m, cm in cms.items()},
    }
    _write(out_root / "build_record.json", json.dumps(record, indent=1))
    return record


if __name__ == "__main__":
    r = build()
    print(json.dumps({k: r[k] for k in ("totals", "scenarios")}, indent=1))
