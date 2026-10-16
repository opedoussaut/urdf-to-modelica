"""Generate the complete ALOHA Modelica package (deterministic) plus URDF<->Modelica mapping and provenance.

Output (default generated/modelica/ALOHA):
  package.mo, Components/, Blocks/, Arms/{AlohaVX300s,AlohaWX250s}.mo, AlohaStationary.mo,
  Experiments/*.mo, Resources/Meshes/<model>/*.stl, Resources/Licenses/
and generated/modelica/aloha_mapping.json, generated/modelica/build_record.json
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
from .scenarios import check_limits, scenarios

PKG = "ALOHA"
GENERATOR_VERSION = "1.0.0"
DESC_ROOT = C.ROOT / "third_party/interbotix_ros_manipulators/interbotix_ros_xsarms/interbotix_xsarm_descriptions"


def _mesh_uri(mesh: str) -> str:
    # package://interbotix_xsarm_descriptions/meshes/<model>_meshes/<file>.stl
    parts = mesh.split("/")
    model = parts[-2].replace("_meshes", "")
    return f"modelica://{PKG}/Resources/Meshes/{model}/{parts[-1]}"


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


def _assembly(arms_cm: dict) -> str:
    decl, eqs = [], []
    nq = len(C.ACTUATED)
    for k, arm in enumerate(C.ARMS):
        cls = C.ARM_CLASS[arm["model"]]
        m = arm["modelica"]
        y = 60 - 40 * k
        decl.append(
            f'  Modelica.Mechanics.MultiBody.Parts.FixedTranslation mount_{m}(r = {mg.vec(arm["mount_xyz"])}, '
            f'animation = false) "Mount world -> {arm["id"]}/base_link (aloha_bringup.launch.py)"\n'
            f'    annotation (Placement(transformation(origin={{-40, {y}}}, extent={{{{-10,-10}},{{10,10}}}})));')
        decl.append(
            f'  {PKG}.Arms.{cls} {m}(animation = animation) "{C.ARM_PRODUCT[arm["model"]]} - {arm["role"]} {arm["side"]}"\n'
            f'    annotation (Placement(transformation(origin={{20, {y}}}, extent={{{{-10,-10}},{{10,10}}}})));')
        a, b = k * nq + 1, (k + 1) * nq
        eqs += [f"  connect(frame_a, mount_{m}.frame_a);", f"  connect(mount_{m}.frame_b, {m}.frame_a);",
                f"  connect(q[{a}:{b}], {m}.q);", f"  connect(qd[{a}:{b}], {m}.qd);", f"  connect(qdd[{a}:{b}], {m}.qdd);"]
    layout = "".join(f"<li>q[{k * nq + 1}:{(k + 1) * nq}] &rarr; {a['modelica']} ({', '.join(C.ACTUATED)})</li>"
                     for k, a in enumerate(C.ARMS))
    return f'''within {PKG};
model AlohaStationary "Complete ALOHA Stationary mechanical assembly: 2 follower ViperX-300 + 2 leader WidowX-250 arms"
  parameter Boolean animation = true "Animate link meshes";
  constant Integer nq = {nq * len(C.ARMS)} "Number of independently driven joints (4 arms x {nq})";
  Modelica.Mechanics.MultiBody.Interfaces.Frame_a frame_a "Workcell (ROS 'world') frame"
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
      fillPattern=FillPattern.Solid), Text(extent={{{{-90,40}},{{90,-40}}}}, textString="ALOHA"),
      Text(extent={{{{-150,150}},{{150,110}}}}, textString="%name", textColor={{0,0,255}})}}),
    Documentation(info="<html><p>Four arms mounted on the workcell frame at the static transforms published by
<code>Interbotix/aloha launch/aloha_bringup.launch.py</code>. Input layout:</p><ul>{layout}</ul>
<p>Right finger joints follow the URDF mimic relation (right = -left).</p></html>"));
end AlohaStationary;
'''


def _experiment(name: str, sc: dict) -> str:
    Q = np.array(sc["Q"])
    rows = ";\n      ".join(", ".join(mg.fmt(x) for x in r) for r in Q)
    return f'''within {PKG}.Experiments;
model {name} "{sc['title']}"
  extends Modelica.Icons.Example;
  inner Modelica.Mechanics.MultiBody.World world(n = {{0, 0, -1}}, axisLength = 0.2, animateGravity = false)
    annotation (Placement(transformation(extent={{{{-80,-10}},{{-60,10}}}})));
  {PKG}.AlohaStationary aloha annotation (Placement(transformation(extent={{{{-10,-10}},{{10,10}}}})));
  {PKG}.Blocks.WaypointTrajectory trajectory(n = aloha.nq, nWp = {len(sc['t'])},
    t_wp = {mg.vec(sc['t'])},
    Q = [{rows}]) annotation (Placement(transformation(extent={{{{-40,40}},{{-20,60}}}})));
equation
  connect(world.frame_b, aloha.frame_a);
  connect(trajectory.q, aloha.q);
  connect(trajectory.qd, aloha.qd);
  connect(trajectory.qdd, aloha.qdd);
  annotation (experiment(StartTime = 0, StopTime = {mg.fmt(sc['stop_time'])}, Interval = 0.02, Tolerance = 1e-06),
    Documentation(info="<html><p>{sc['description']}</p><p>Output interval 0.02 s = ALOHA control period DT
(aloha/constants.py). Prescribed motion: no actuator dynamics; joint torques are the inverse-dynamics
reaction torques of the URDF inertials under gravity.</p></html>"));
end {name};
'''


def variable_filter() -> str:
    return (r"time|aloha\.[A-Za-z]+\.j_[A-Za-z_]+\.(phi|w|tau|s|v|f)"
            r"|aloha\.[A-Za-z]+\.[A-Za-z_]+_link\.frame_a\.(r_0|R\.T)\[.*")


def build(out_root: Path | None = None) -> dict:
    out_root = out_root or C.ROOT / "generated" / "modelica"
    pkg_dir = out_root / PKG
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    files = {}
    files.update(mg.component_library(PKG))
    arms_cm, class_files = {}, {}
    for model, cls in C.ARM_CLASS.items():
        robot = C.arm_robot(model)
        doc = (f"<p><b>{C.ARM_PRODUCT[model]}</b>. Source: <code>{model}.urdf.xacro</code> "
               f"({C.VARIANT['sources']['descriptions']}), BSD-3-Clause.</p>")
        text, cm = mg.robot_class(robot, PKG, cls, f"{PKG}.Arms", f"{C.ARM_PRODUCT[model]} arm ({model} URDF)",
                                  _mesh_uri, doc)
        files[f"Arms/{cls}.mo"] = text
        arms_cm[model] = cm
    files["Arms/package.mo"] = f'within {PKG};\npackage Arms "Arm models generated one-to-one from URDF"\n  extends Modelica.Icons.Package;\nend Arms;\n'
    files["Arms/package.order"] = "\n".join(C.ARM_CLASS.values()) + "\n"
    files["AlohaStationary.mo"] = _assembly(arms_cm)

    scs = scenarios()
    limit_report = {}
    for name, sc in scs.items():
        errs = check_limits(sc)
        limit_report[name] = errs
        if errs:
            raise ValueError(f"Scenario {name} violates URDF limits: {errs}")
        files[f"Experiments/{name}.mo"] = _experiment(name, sc)
    files["Experiments/package.mo"] = f'within {PKG};\npackage Experiments "Prescribed-motion simulation experiments"\n  extends Modelica.Icons.ExamplesPackage;\nend Experiments;\n'
    files["Experiments/package.order"] = "\n".join(scs) + "\n"

    totals = C.build_manifest()["totals"]
    files["package.mo"] = f'''within ;
package {PKG} "ALOHA Stationary robot: complete mechanical assembly generated from public engineering sources"
  extends Modelica.Icons.Package;
  annotation (
    uses(Modelica(version = "{mg.MSL_VERSION}")),
    version = "{GENERATOR_VERSION}",
    Documentation(info="<html>
<h4>ALOHA Stationary virtual twin (kinematic / prescribed-motion formulation)</h4>
<p>Generated by the K&amp;KH ALOHA Engineering Studio generator v{GENERATOR_VERSION} from pinned public sources:</p>
<ul><li>{C.VARIANT['sources']['descriptions']}</li><li>{C.VARIANT['sources']['bringup']}</li>
<li>{C.VARIANT['sources']['constants']}</li></ul>
<p>Assembly: {totals['links']} links (incl. world), {totals['joints']} joints, {totals['driven']} independently
driven joints, {totals['mimic']} mimic joints. Every URDF link maps to one <code>Components.RigidLink</code>, every
URDF joint to one joint component. Masses and inertias are the URDF values; URDF placeholder inertials are massless.</p>
<p>Run <code>{PKG}.Experiments.FollowerRightReach</code> (9 s). Meshes: Interbotix, BSD-3-Clause
(see Resources/Licenses).</p></html>"));
end {PKG};
'''
    files["package.order"] = "Components\nBlocks\nArms\nAlohaStationary\nExperiments\n"
    for rel, text in files.items():
        _write(pkg_dir / rel, text)

    # Meshes + license
    for model in C.ARM_CLASS:
        src = DESC_ROOT / "meshes" / f"{model}_meshes"
        dst = pkg_dir / "Resources" / "Meshes" / model
        dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(src.glob("*.stl")):
            shutil.copy2(f, dst / f.name)
    lic_dir = pkg_dir / "Resources" / "Licenses"
    lic_dir.mkdir(parents=True, exist_ok=True)
    lic = C.ROOT / "third_party/interbotix_ros_manipulators/LICENSE"
    if lic.exists():
        shutil.copy2(lic, lic_dir / "Interbotix_LICENSE.txt")

    # Mapping: physical arm instance -> URDF entity -> Modelica component path
    mapping = {"package": PKG, "assembly": f"{PKG}.AlohaStationary", "arms": []}
    for arm in C.ARMS:
        cm = arms_cm[arm["model"]]
        m = arm["modelica"]
        mapping["arms"].append({
            "arm": arm["id"], "modelica_instance": m, "class": f"{PKG}.Arms.{cm.class_name}",
            "mount": {"modelica": f"mount_{m}", "urdf_joint": f"{arm['id']}_mount", "xyz": arm["mount_xyz"]},
            "links": [{"urdf": f"{arm['id']}/{l}", "urdf_local": l, "modelica": f"{m}.{c}",
                       "placeholder": l in cm.placeholders, "mesh": l not in cm.missing_mesh,
                       "result_vars": {"r_0": [f"aloha.{m}.{c}.frame_a.r_0[{i}]" for i in (1, 2, 3)],
                                       "R": [f"aloha.{m}.{c}.frame_a.R.T[{i},{j}]" for i in (1, 2, 3) for j in (1, 2, 3)]}}
                      for l, c in cm.links.items()],
            "joints": [{"urdf": f"{arm['id']}/{jn}", "urdf_local": jn, "modelica": f"{m}.{c}",
                        "driven_index": (C.ARMS.index(arm) * len(C.ACTUATED) + cm.actuated.index(jn) + 1)
                        if jn in cm.actuated else None,
                        "mimic": cm.mimic.get(jn)}
                       for jn, c in cm.joints.items()],
        })
    _write(out_root / "aloha_mapping.json", json.dumps(mapping, indent=1))

    inputs = [C.URDF_DIR / f"{m}.urdf" for m in C.ARM_CLASS]
    record = {
        "generator": "kkh.domain.aloha.build", "generator_version": GENERATOR_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "repo_commit": _git_head(), "msl_version": mg.MSL_VERSION,
        "inputs": {str(p.relative_to(C.ROOT)).replace("\\", "/"): _sha(p) for p in inputs},
        "files": {rel: hashlib.sha256(t.encode()).hexdigest() for rel, t in sorted(files.items())},
        "totals": totals, "scenarios": {k: {"t": v["t"], "stop_time": v["stop_time"]} for k, v in scs.items()},
        "scenario_limit_check": limit_report,
        "placeholders": {m: cm.placeholders for m, cm in arms_cm.items()},
        "links_without_mesh": {m: cm.missing_mesh for m, cm in arms_cm.items()},
    }
    _write(out_root / "build_record.json", json.dumps(record, indent=1))
    return record


if __name__ == "__main__":
    r = build()
    print(json.dumps({k: r[k] for k in ("totals", "placeholders", "links_without_mesh")}, indent=1))
