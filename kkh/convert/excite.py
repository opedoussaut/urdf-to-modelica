"""Standard excitation: drive every recognised moving joint through most of its URDF range, so the geometry and
dynamics checks see real motion (a model's own test motion can be almost static).

Signal per joint: q(t) = centre + A·sin(2π f t), A = 40 % of the URDF range (80 % peak to peak), centre = middle of the
range; joints without limits ±1 rad / ±0.05 m; frequencies 0.25 + 0.05·k Hz so joints do not move in lock-step.
Mimic joints are NOT driven by their own signal when the model drives them independently (held at 0): if the model
does not enforce the URDF mimic relation, the geometry check then shows it.

Two wrappers, written to a separate file and loaded after the package (the converted file is never modified):
- URDFModelica packages: instantiate `<Robot>Run` and feed its position inputs (index order read from the robot
  class's `connect(<joint>.flange_a, rotational_flange_a[i])` statements).
- Contract files (AI methods): `extends <Pkg>.<Pkg>Test(j_x(useAxisFlange=true), ...)` with an MSL Position source
  on each `j_x` that is a direct Revolute/Prismatic component of the test model.
"""
from __future__ import annotations

import re
from pathlib import Path

STOP_TIME = 4.0
NAME = "KkhExcite"


def _signal(joint) -> tuple[float, float]:
    """(centre, amplitude) for one URDF joint."""
    lim = joint.limit
    if lim is not None and lim.lower is not None and lim.upper is not None and lim.upper > lim.lower and joint.type != "continuous":
        return (lim.lower + lim.upper) / 2, 0.4 * (lim.upper - lim.lower)
    return 0.0, (0.05 if joint.type == "prismatic" else 1.0)


def _sine(name: str, centre: float, amp: float, k: int) -> str:
    return (f"  Modelica.Blocks.Sources.Sine {name}(amplitude={amp:.6g}, f={0.25 + 0.05 * k:.3g}, "
            f"offset={centre:.6g});\n")


def _short(n: str) -> str:
    return n.split("/")[-1]


def urdfmodelica_wrapper(robot, main_file: Path, model: str) -> tuple[str, dict]:
    """Wrapper around URDFModelica's <Robot>Run for the package whose robot class is `main_file`."""
    text = main_file.read_text(encoding="utf-8")
    rot = {int(i): j for j, i in re.findall(r"connect\((\w+)\.flange_a,\s*rotational_flange_a\[(\d+)\]\)", text)}
    tra = {int(i): j for j, i in re.findall(r"connect\((\w+)\.flange_a,\s*translational_flange_a\[(\d+)\]\)", text)}
    by_short = {_short(j.name).replace("-", "_").lower(): j for j in robot.joints.values()}
    run = model.removesuffix("Test") + "Run"
    decl, eqs, driven = "", "", {}
    for kind, table in (("rotational", rot), ("translational", tra)):
        for i in sorted(table):
            j = by_short.get(table[i].lower())
            if j is None or j.mimic:
                centre, amp = 0.0, 0.0
            else:
                centre, amp = _signal(j)
                driven[j.name] = {"centre": centre, "amplitude": amp}
            s = f"s_{kind[0]}{i}"
            decl += _sine(s, centre, amp, len(driven))
            eqs += f"  connect({s}.y, run.{kind}PositionInput[{i}]);\n"
    src = (f"model {NAME} \"Standard excitation (HT GEN7 PhysAI Studio scorer)\"\n  {run} run;\n{decl}equation\n{eqs}"
           f"  annotation(experiment(StopTime={STOP_TIME}));\nend {NAME};\n")
    return src, driven


def contract_wrapper(robot, code: str, model: str) -> tuple[str, dict] | None:
    """Wrapper for an AI-written file following the output contract (joints j_<name> directly in <Pkg>Test)."""
    test = model.split(".")[-1]
    body = re.search(r"\bmodel\s+" + re.escape(test) + r"\b(.*?)\bend\s+" + re.escape(test) + r"\s*;", code, re.S)
    if not body:
        return None
    comps = re.findall(r"Modelica\.Mechanics\.MultiBody\.Joints\.(Revolute|Prismatic)\s+(\w+)", body.group(1))
    by_short = {_short(j.name).replace("-", "_").lower(): j for j in robot.joints.values()}
    mods, decl, eqs, driven = [], "", "", {}
    for kind, inst in comps:
        j = by_short.get(re.sub(r"^j_", "", inst).lower())
        if j is None or j.mimic or not j.movable:
            continue
        centre, amp = _signal(j)
        driven[j.name] = {"centre": centre, "amplitude": amp, "instance": inst}
        k = len(driven)
        mods.append(f"{inst}(useAxisFlange=true)")
        if kind == "Revolute":
            decl += f"  Modelica.Mechanics.Rotational.Sources.Position p_{inst}(useSupport=true);\n"
            eqs += f"  connect(p_{inst}.flange, {inst}.axis);\n  connect(p_{inst}.support, {inst}.support);\n"
        else:
            decl += f"  Modelica.Mechanics.Translational.Sources.Position p_{inst}(useSupport=true);\n"
            eqs += f"  connect(p_{inst}.flange, {inst}.axis);\n  connect(p_{inst}.support, {inst}.support);\n"
        decl += _sine(f"s_{inst}", centre, amp, k)
        eqs += f"  connect(s_{inst}.y, p_{inst}.{'phi_ref' if kind == 'Revolute' else 's_ref'});\n"
    if not driven:
        return None
    src = (f"model {NAME} \"Standard excitation (HT GEN7 PhysAI Studio scorer)\"\n  extends {model}({', '.join(mods)});\n"
           f"{decl}equation\n{eqs}  annotation(experiment(StopTime={STOP_TIME}));\nend {NAME};\n")
    return src, driven


def build(robot, model: str, main_file: Path | None, work: Path) -> tuple[Path, dict] | None:
    """Write the wrapper next to the scoring work directory; None when no wrapper applies to this file."""
    if not main_file or not Path(main_file).exists():
        return None
    if model.startswith("URDFModelica.Examples."):
        src, driven = urdfmodelica_wrapper(robot, Path(main_file), model)
    else:
        out = contract_wrapper(robot, Path(main_file).read_text(encoding="utf-8", errors="replace"), model)
        if out is None:
            return None
        src, driven = out
    f = work / f"{NAME}.mo"
    f.write_text(src, encoding="utf-8")
    return f, driven


def peak_to_peak(driven: dict) -> float:
    return max((2 * d["amplitude"] for d in driven.values()), default=0.0)

