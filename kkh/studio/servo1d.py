"""1D Simulation Lab: one follower joint as a single-degree-of-freedom servo experiment in OpenModelica.

Plant (Modelica Standard Library 4.x, Mechanics.Rotational):
  Inertia J  ── equivalent inertia of the rigid moving subtree about the joint axis
  Damper d   ── URDF <dynamics damping>      (generic URDF default, not identified)
  load       ── gravity torque A·sin(q+φ) + Coulomb friction τc·tanh(ω/0.01)  (A, φ derived; τc = URDF friction)
  actuator   ── PD servo u = kp·e + kd·(ω_cmd − ω) − ff·A·sin(q_cmd+φ), saturated at the URDF effort limit,
               first-order torque lag Ta.

Derived, not assumed: J, A and φ are computed from the follower URDF inertials (mass, centre of mass, inertia tensor)
with the outer joints held at the ALOHA start pose. Rotation about the joint axis keeps the subtree rigid, so J is exact
for that pose and the gravity torque is exactly A·sin(q+φ) (checked by the fit residual). Not included (unknown, stated):
motor rotor inertia reflected through the gearbox, backlash, compliance, payload, dual-servo load sharing.
Assumed (tunable, revision-bound): kp, kd, Ta, ff from ALOHA2.Control.FollowerServoSettings.

Every run is a real OpenModelica compile + simulation in an isolated directory under runs/studio/servo1d/<id>.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import uuid
from pathlib import Path

import numpy as np

from kkh.domain.aloha import configuration as C
from kkh.domain.aloha.build import SERVO_BOUNDS, SERVO_DEFAULTS, SERVO_JOINTS
from kkh.engineering.omc import MatResult, OMCService

from . import robotics as R

def _rel(path) -> str:
    """Repository-relative path for records; absolute when outside the repository (e.g. test directories)."""
    try:
        return Path(path).resolve().relative_to(C.ROOT).as_posix()
    except ValueError:
        return str(path)


FOLLOWER = "aloha_vx300s"
G = 9.80665
RUNS = C.ROOT / "runs" / "studio" / "servo1d"
TUNABLE = ("kp", "kd", "actuatorTime", "feedforward")
UNITS = {"kp": "N·m/rad", "kd": "N·m·s/rad", "actuatorTime": "s", "feedforward": "1"}
MODEL = "ServoJoint1D"
PLACEHOLDER_MASS = 1e-3
OUTPUTS = ["q_cmd", "qd_cmd", "q", "qd", "e", "tau", "u", "tau_gravity"]


# ------------------------------------------------------------------------------------------------ plant derivation
def _subtree(robot, link: str) -> list[str]:
    out, stack = [], [link]
    while stack:
        current = stack.pop()
        out.append(current)
        stack += [j.child for j in robot.child_joints(current)]
    return out


def derive_plant(joint: str = "shoulder") -> dict:
    """Equivalent inertia and gravity-torque law of one follower joint, derived from the URDF at the start pose."""
    if joint not in SERVO_JOINTS:
        raise ValueError(f"Joint must be one of {SERVO_JOINTS}")
    robot = R.robot_for(FOLLOWER)
    j = robot.joints[joint]
    pose = dict(zip(R.JOINTS, R.mapping(C.start_vector())["q"]))
    links = [l for l in _subtree(robot, j.child)
             if robot.links[l].inertial is not None and robot.links[l].inertial.mass > PLACEHOLDER_MASS]
    massless = [l for l in _subtree(robot, j.child) if l not in links]
    g_vec = np.array([0.0, 0.0, -G])

    def state(theta):
        q = dict(pose)
        q[joint] = theta
        poses = robot.forward_kinematics(q)
        T = poses[j.parent] @ j.origin.matrix()
        axis = T[:3, :3] @ (np.asarray(j.axis, float) / np.linalg.norm(j.axis))
        return poses, T[:3, 3], axis

    poses, p, axis = state(pose[joint])
    J, mass = 0.0, 0.0
    for name in links:
        inert = robot.links[name].inertial
        Tl = poses[name]
        c = Tl[:3, :3] @ inert.origin.xyz + Tl[:3, 3]
        Iw = Tl[:3, :3] @ inert.inertia_in_link_frame() @ Tl[:3, :3].T
        r = c - p
        r_perp = r - (r @ axis) * axis
        J += float(axis @ Iw @ axis + inert.mass * r_perp @ r_perp)
        mass += inert.mass

    def gravity_torque(theta):
        poses_t, p_t, axis_t = state(theta)
        tau = 0.0
        for name in links:
            inert = robot.links[name].inertial
            Tl = poses_t[name]
            c = Tl[:3, :3] @ inert.origin.xyz + Tl[:3, 3]
            tau += float(axis_t @ np.cross(c - p_t, inert.mass * g_vec))
        return tau

    grid = np.linspace(-math.pi, math.pi, 37)
    tau = np.array([gravity_torque(t) for t in grid])
    A = np.column_stack([np.sin(grid), np.cos(grid)])
    (a, b), *_ = np.linalg.lstsq(A, tau, rcond=None)
    residual = float(np.max(np.abs(A @ [a, b] - tau)))
    lim = j.limit
    return {
        "joint": joint, "model": FOLLOWER, "urdf": f"data/urdf/{FOLLOWER}.urdf", "urdf_joint": joint,
        "parent_link": j.parent, "child_link": j.child, "axis": [float(v) for v in j.axis],
        "pose": {k: round(float(v), 6) for k, v in pose.items()}, "q0": float(pose[joint]),
        "inertia_kgm2": round(J, 6), "moving_mass_kg": round(mass, 4),
        "gravity_amplitude_Nm": round(float(math.hypot(a, b)), 6), "gravity_phase_rad": round(float(math.atan2(b, a)), 6),
        "gravity_fit_residual_Nm": residual,
        "damping_Nms_per_rad": float(j.damping or 0.0), "coulomb_friction_Nm": float(j.friction or 0.0),
        "effort_limit_Nm": float(lim.effort), "q_min": float(lim.lower), "q_max": float(lim.upper),
        "velocity_limit_rad_s": float(lim.velocity),
        "links": links, "massless_placeholders": massless,
        "evidence": {
            "inertia_kgm2": "derived: sum of URDF link inertias + parallel-axis terms about the joint axis, outer joints at the start pose",
            "gravity": f"derived: URDF masses and centres of mass, g = {G} m/s², exact A·sin(q+φ) law (fit residual {residual:.2e} N·m)",
            "damping_Nms_per_rad": "URDF <dynamics damping> (generic default 0.1, not identified)",
            "coulomb_friction_Nm": "URDF <dynamics friction> (generic default 0.1, not identified)",
            "effort_limit_Nm": "URDF <limit effort> (verified source fact)",
            "limits": "URDF <limit lower/upper/velocity> (verified source facts)",
            "not_modelled": "reflected motor rotor inertia (gear ratio/rotor data not in the evidence graph), backlash, compliance, payload, dual-servo load sharing",
        },
    }


# ------------------------------------------------------------------------------------------------ inputs
def command(spec: dict, plant: dict) -> dict:
    """Commanded angle/velocity table. kinds: step (ideal or ramped) or a recorded leader trajectory."""
    kind = spec.get("kind", "step")
    q0 = plant["q0"]
    if kind == "step":
        amp = float(spec.get("amplitude", 0.3))
        t_step = float(spec.get("step_time", 0.5))
        ramp = float(spec.get("ramp_time", 0.0))
        stop = float(spec.get("stop_time", 3.0))
        if not (0.0 < abs(amp) <= 1.0 and 0 <= t_step < stop <= 30 and 0 <= ramp <= 2):
            raise ValueError("Step: |amplitude| in (0, 1] rad, 0 ≤ step time < stop time ≤ 30 s, ramp 0–2 s")
        target = q0 + amp
        if not plant["q_min"] <= target <= plant["q_max"]:
            raise ValueError(f"Step target {target:.3f} rad is outside the URDF joint limits [{plant['q_min']}, {plant['q_max']}]")
        if ramp > 0:
            t = np.linspace(t_step, t_step + ramp, 41)
            s = (1 - np.cos(np.pi * (t - t_step) / ramp)) / 2
            q = q0 + amp * s
            qd = amp * np.pi / (2 * ramp) * np.sin(np.pi * (t - t_step) / ramp)
            table = [[0.0, q0, 0.0], *zip(t.tolist(), q.tolist(), qd.tolist()), [stop, target, 0.0]]
        else:
            table = [[0.0, q0, 0.0], [t_step, q0, 0.0], [t_step, target, 0.0], [stop, target, 0.0]]
        label = f"{'ramped ' if ramp else ''}step {amp:+.3f} rad at {t_step:g} s" + (f" over {ramp:g} s" if ramp else "")
        return {"kind": kind, "table": table, "stop_time": stop, "label": label, "q_start": q0,
                "spec": {"amplitude": amp, "step_time": t_step, "ramp_time": ramp, "stop_time": stop}}
    if kind == "trajectory":
        data = spec["data"]
        index = R.JOINTS.index(plant["joint"])
        rows = data["q"] if data.get("reference_space") == "follower_joints" else [R.mapping(r)["q"] for r in data["q"]]
        t = np.asarray(data["time"], float)
        q = np.asarray([r[index] for r in rows], float)
        qd = np.gradient(q, t, edge_order=2)
        return {"kind": kind, "table": np.column_stack([t, q, qd]).tolist(), "stop_time": float(t[-1]),
                "label": f"recorded {spec.get('name', 'trajectory')} ({plant['joint']}, follower joint space)",
                "q_start": float(q[0]), "spec": {"trajectory": spec.get("id"), "samples": len(t)}}
    raise ValueError("Input kind must be 'step' or 'trajectory'")


# ------------------------------------------------------------------------------------------------ Modelica
def modelica_source(plant: dict, params: dict, cmd: dict) -> str:
    table = ";".join(",".join(f"{v:.12g}" for v in row) for row in cmd["table"])
    p = params
    return f'''model {MODEL} "1D servo experiment: follower {plant['joint']} joint (HT GEN7 PhysAI Studio 1D Simulation Lab)"
  import SI = Modelica.Units.SI;
  // Plant: derived from the follower URDF at the start pose (see the run provenance)
  parameter SI.Inertia J = {plant['inertia_kgm2']} "Equivalent inertia of the moving subtree about the joint axis (derived)";
  parameter SI.Torque tauG = {plant['gravity_amplitude_Nm']} "Gravity torque amplitude (derived)";
  parameter SI.Angle phiG = {plant['gravity_phase_rad']} "Gravity torque phase (derived)";
  parameter Real d(unit = "N.m.s/rad") = {plant['damping_Nms_per_rad']} "Viscous damping (URDF, generic default)";
  parameter SI.Torque tauC = {plant['coulomb_friction_Nm']} "Coulomb friction (URDF, generic default)";
  parameter SI.Torque tauMax = {plant['effort_limit_Nm']} "Actuator torque limit (URDF effort)";
  // Servo: tunable, assumed (ALOHA2.Control.ServoGains of the selected revision or the experiment edit)
  parameter Real kp(unit = "N.m/rad", min = {SERVO_BOUNDS['kp'][0]}, max = {SERVO_BOUNDS['kp'][1]}) = {p['kp']} "Proportional gain";
  parameter Real kd(unit = "N.m.s/rad", min = {SERVO_BOUNDS['kd'][0]}, max = {SERVO_BOUNDS['kd'][1]}) = {p['kd']} "Derivative gain";
  parameter SI.Time Ta(min = {SERVO_BOUNDS['actuatorTime'][0]}, max = {SERVO_BOUNDS['actuatorTime'][1]}) = {p['actuatorTime']} "Actuator torque lag";
  parameter Real ff(unit = "1", min = {SERVO_BOUNDS['feedforward'][0]}, max = {SERVO_BOUNDS['feedforward'][1]}) = {p['feedforward']} "Gravity feed-forward fraction";
  Modelica.Blocks.Sources.CombiTimeTable command(table = [{table}], columns = {{2, 3}},
    smoothness = Modelica.Blocks.Types.Smoothness.LinearSegments,
    extrapolation = Modelica.Blocks.Types.Extrapolation.HoldLastPoint) "Commanded angle and velocity";
  Modelica.Mechanics.Rotational.Components.Fixed fixed;
  Modelica.Mechanics.Rotational.Components.Inertia link(J = J, phi(start = {cmd['q_start']}, fixed = false), w(start = 0, fixed = true));
  Modelica.Mechanics.Rotational.Components.Damper damper(d = d);
  Modelica.Mechanics.Rotational.Sources.Torque actuator "Servo torque";
  Modelica.Mechanics.Rotational.Sources.Torque load "Gravity and Coulomb friction";
  Modelica.Blocks.Nonlinear.Limiter saturation(uMax = tauMax, uMin = -tauMax);
  Modelica.Blocks.Continuous.FirstOrder lag(k = 1, T = Ta, initType = Modelica.Blocks.Types.Init.SteadyState);
  constant SI.AngularVelocity perSecond = 1 "unit carrier: the table's velocity column is in rad/s";
  SI.Angle q_cmd "Commanded angle";
  SI.AngularVelocity qd_cmd "Commanded velocity";
  SI.Angle q "Joint angle";
  SI.AngularVelocity qd "Joint velocity";
  SI.Angle e "Tracking error";
  SI.Torque u "Controller output before saturation";
  SI.Torque tau "Applied actuator torque";
  SI.Torque tau_gravity "Gravity torque on the joint";
initial equation
  der(link.w) = 0 "start at the closed-loop equilibrium under gravity";
equation
  connect(actuator.flange, link.flange_a);
  connect(load.flange, link.flange_b);
  connect(damper.flange_a, link.flange_b);
  connect(damper.flange_b, fixed.flange);
  q_cmd = command.y[1];
  qd_cmd = command.y[2] * perSecond;
  q = link.phi;
  qd = link.w;
  e = q_cmd - q;
  tau_gravity = tauG * sin(q + phiG);
  load.tau = tau_gravity - tauC * tanh(qd / 0.01);
  u = kp * e + kd * (qd_cmd - qd) - ff * tauG * sin(q_cmd + phiG);
  saturation.u = u;
  lag.u = saturation.y;
  actuator.tau = lag.y;
  tau = lag.y;
  annotation(experiment(StopTime = {cmd['stop_time']}, Interval = {cmd['stop_time'] / 800:.6g}, Tolerance = 1e-6));
end {MODEL};
'''


# ------------------------------------------------------------------------------------------------ run
def check_params(params: dict) -> dict:
    out = {}
    for key in TUNABLE:
        if key not in params:
            raise ValueError(f"Missing servo parameter {key}")
        value = float(params[key])
        lo, hi = SERVO_BOUNDS[key]
        if not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{key} = {value} {UNITS[key]} is outside the bounds declared in ALOHA2.Control.ServoGains [{lo}, {hi}]")
        out[key] = value
    return out


def _metrics(series: dict, plant: dict, cmd: dict) -> dict:
    t, q, e, tau, u = (np.asarray(series[k]) for k in ("time", "q", "e", "tau", "u"))
    qd = np.asarray(series["qd"])
    out = {
        "rms_error_rad": float(np.sqrt(np.mean(e ** 2))),
        "max_abs_error_rad": float(np.max(np.abs(e))),
        "peak_torque_Nm": float(np.max(np.abs(tau))),
        "saturated_fraction": float(np.mean(np.abs(u) >= plant["effort_limit_Nm"] - 1e-9)),
        "joint_limit_violation_samples": int(np.sum((q < plant["q_min"]) | (q > plant["q_max"]))),
        "velocity_limit_violation_samples": int(np.sum(np.abs(qd) > plant["velocity_limit_rad_s"])),
        "initial_static_error_rad": float(e[0]),
    }
    if cmd["kind"] == "step":
        s = cmd["spec"]
        amp, t0 = s["amplitude"], s["step_time"] + s["ramp_time"]
        target = plant["q0"] + amp
        after = t >= s["step_time"]
        resp = (q[after] - q[after][0]) / amp  # normalised response, 1 = target
        out["steady_state_error_rad"] = float(np.mean(e[t >= t[-1] - 0.1 * (t[-1] - t0)]))
        out["overshoot_percent"] = float(max(0.0, (np.max(resp) - 1.0) * 100)) if abs(amp) > 0 else None
        try:
            rise = t[after][np.argmax(resp >= 0.9)] - t[after][np.argmax(resp >= 0.1)] if np.any(resp >= 0.9) else None
        except ValueError:
            rise = None
        out["rise_time_10_90_s"] = float(rise) if rise is not None else None
        band = 0.02 * abs(amp)
        outside = np.where(np.abs(q - target) > band)[0]
        settle = None
        if len(outside) == 0:
            settle = 0.0
        elif outside[-1] < len(t) - 1 and t[outside[-1] + 1] >= s["step_time"]:
            settle = float(t[outside[-1] + 1] - s["step_time"])
        out["settling_time_2pct_s"] = settle
        out["settles_within_horizon"] = settle is not None
    return out


def simulate(plant: dict, params: dict, cmd: dict, directory) -> dict:
    """One real OpenModelica check + simulation of the 1D model in `directory`."""
    params = check_params(params)
    directory.mkdir(parents=True, exist_ok=True)
    source = modelica_source(plant, params, cmd)
    path = directory / f"{MODEL}.mo"
    path.write_text(source, encoding="utf-8")
    omc = OMCService(directory)
    try:
        loaded = omc.load_package(path)
        check = omc.check(MODEL)
        if not loaded.ok or not check.ok:
            return {"ok": False, "stage": "check", "diagnostic": (check.messages or loaded.messages)[:4000],
                    "source_sha256": hashlib.sha256(source.encode()).hexdigest()}
        sim = omc.simulate(MODEL, cmd["stop_time"], intervals=800, tolerance=1e-6,
                           variable_filter="time|" + "|".join(OUTPUTS), timeout_s=120)
        if not sim.ok:
            return {"ok": False, "stage": "simulate", "diagnostic": sim.messages[:4000], "check": check.data,
                    "source_sha256": hashlib.sha256(source.encode()).hexdigest()}
        mat = MatResult(sim.data["resultFile"])
        series = {"time": mat.get("time").tolist(), **{k: mat.get(k).tolist() for k in OUTPUTS}}
        version = omc.version()
    finally:
        omc.close()
    return {"ok": True, "params": params, "series": series, "metrics": _metrics(series, plant, cmd),
            "check": check.data, "timing_s": {k: sim.data.get(k) for k in ("timeCompile", "timeSimulation", "timeTotal")},
            "omc_version": version, "source_sha256": hashlib.sha256(source.encode()).hexdigest(), "source": source,
            "result_file": str(sim.data["resultFile"]), "model_file": str(path)}


def run_experiment(joint: str, baseline: dict, candidate: dict | None, input_spec: dict, *, baseline_label: str,
                   revision: str | None = None) -> dict:
    """Baseline and (optionally) candidate servo parameters on the identical command and solver settings."""
    plant = derive_plant(joint)
    cmd = command(input_spec, plant)
    identity = uuid.uuid4().hex
    root = RUNS / identity
    runs = {"baseline": simulate(plant, baseline, cmd, root / "baseline")}
    if candidate is not None:
        runs["candidate"] = simulate(plant, candidate, cmd, root / "candidate")
    comparison = None
    if candidate is not None and runs["baseline"]["ok"] and runs["candidate"]["ok"]:
        comparison = compare_metrics(runs["baseline"]["metrics"], runs["candidate"]["metrics"])
    result = {
        "id": identity, "joint": joint, "created": dt.datetime.now(dt.timezone.utc).isoformat(),
        "plant": plant, "input": {k: v for k, v in cmd.items() if k != "table"},
        "input_sha256": hashlib.sha256(json.dumps(cmd["table"]).encode()).hexdigest(),
        "baseline_label": baseline_label, "revision": revision, "runs": runs, "comparison": comparison,
        "run_directory": _rel(root),
        "solver": {"method": "dassl", "tolerance": 1e-6, "intervals": 800},
        "limitations": [
            "Servo gains, actuator lag and feed-forward are assumed values (not identified on the Dynamixel hardware).",
            "Inertia and gravity are derived from URDF inertials with the outer joints fixed at the start pose; other poses change both.",
            "Reflected motor rotor inertia, backlash, compliance, payload and dual-servo load sharing are not modelled.",
            "URDF damping 0.1 and friction 0.1 are generic defaults, not measurements.",
        ],
    }
    (root / "report.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


KEY_METRICS = [("rms_error_rad", "lower"), ("max_abs_error_rad", "lower"), ("peak_torque_Nm", "info"),
               ("overshoot_percent", "lower"), ("settling_time_2pct_s", "lower"), ("steady_state_error_rad", "abs_lower"),
               ("saturated_fraction", "lower")]


def compare_metrics(base: dict, cand: dict, tolerance: float = 0.01) -> dict:
    """Per-metric change; 'improved' / 'worse' only beyond a 1 % relative difference; no blanket verdict."""
    rows = []
    for key, sense in KEY_METRICS:
        a, b = base.get(key), cand.get(key)
        if a is None or b is None:
            rows.append({"metric": key, "baseline": a, "candidate": b, "change": None, "verdict": "n/a"})
            continue
        if sense == "abs_lower":
            a_cmp, b_cmp = abs(a), abs(b)
        else:
            a_cmp, b_cmp = a, b
        rel = (b_cmp - a_cmp) / abs(a_cmp) if abs(a_cmp) > 1e-12 else (0.0 if abs(b_cmp) < 1e-12 else math.inf)
        if sense == "info":
            verdict = "higher" if rel > tolerance else "lower" if rel < -tolerance else "unchanged"
        else:
            verdict = "improved" if rel < -tolerance else "worse" if rel > tolerance else "unchanged"
        rows.append({"metric": key, "baseline": a, "candidate": b, "change": rel if math.isfinite(rel) else None,
                     "verdict": verdict})
    better = [r["metric"] for r in rows if r["verdict"] == "improved"]
    worse = [r["metric"] for r in rows if r["verdict"] == "worse"]
    return {"rows": rows, "improved": better, "worse": worse,
            "summary": ("Mixed result" if better and worse else "Improves" if better else "Worse" if worse else "No measurable change")
            + (f": better {', '.join(better)}" if better else "") + (f"; worse {', '.join(worse)}" if worse else "")
            + " (same command, solver and plant; 1 % threshold)."}
