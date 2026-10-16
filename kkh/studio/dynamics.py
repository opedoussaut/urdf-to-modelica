"""Real torque-driven MultiBody follower experiments on immutable recorded references.

Controller/actuator settings are illustrative, not measured hardware parameters.
The six revolute axes use URDF inertials, gravity and multibody coupling. Finger
motion remains prescribed because motor-to-finger transmission is undocumented.
"""
from __future__ import annotations
import json
import re
import shutil
import uuid
import numpy as np
from kkh.domain.aloha import configuration as C
from kkh.engineering.omc import OMCService, MatResult
from .robotics import mapping, trajectory, JOINTS
from .models import BASELINE, manifest

JOINT_SOURCE = '''within ALOHA2.Components;
model DynamicRevolute
  import SI = Modelica.Units.SI;
  extends Modelica.Mechanics.MultiBody.Interfaces.PartialTwoFrames;
  parameter SI.Position r[3]={0,0,0};
  parameter SI.Angle rpy[3]={0,0,0};
  parameter Real n[3]={0,0,1};
  parameter Boolean limited=true;
  parameter SI.Angle q_min=-Modelica.Constants.inf, q_max=Modelica.Constants.inf, q_start=0;
  parameter SI.AngularVelocity qd_max=Modelica.Constants.inf;
  parameter SI.Torque tau_max=1;
  parameter Real kp=40 "Illustrative proportional gain, Nm/rad";
  parameter Real kd=4 "Illustrative derivative gain, Nm.s/rad";
  parameter SI.Time actuatorTime=0.03 "Assumed first-order torque lag, not identified";
  parameter Real damping=0, friction=0 "URDF joint dynamics; Coulomb friction regularized with tanh(w/0.01)";
  Modelica.Blocks.Interfaces.RealInput q, qd, qdd, feedforward;
  SI.Angle phi=joint.phi;
  SI.AngularVelocity w=der(joint.phi);
  SI.Torque tau=joint.axis.tau;
  SI.Torque applied(start=0, fixed=true);
  SI.Torque demand;
  Modelica.Mechanics.MultiBody.Parts.FixedRotation origin(r=r,
    rotationType=Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence,
    sequence={3,2,1}, angles=Modelica.Units.Conversions.to_deg({rpy[3],rpy[2],rpy[1]}), animation=false);
  Modelica.Mechanics.MultiBody.Joints.Revolute joint(n=n, useAxisFlange=true, animation=false,
    stateSelect=StateSelect.prefer, phi(start=q_start, fixed=true), w(start=0, fixed=true));
  Modelica.Mechanics.Rotational.Sources.Torque drive(useSupport=true);
equation
  demand=kp*(q-phi)+kd*(qd-w)+feedforward;
  actuatorTime*der(applied)=min(tau_max,max(-tau_max,demand))-applied;
  drive.tau=applied-damping*w-friction*tanh(w/0.01);
  connect(frame_a,origin.frame_a);
  connect(origin.frame_b,joint.frame_a);
  connect(joint.frame_b,frame_b);
  connect(drive.flange,joint.axis);
  connect(drive.support,joint.support);
end DynamicRevolute;
'''


def generate(directory, data, improved=False, axes=6, source_package=BASELINE, options=None):
    if axes not in (1, 6):
        raise ValueError("Use the single shoulder-axis milestone or six-axis follower")
    data = trajectory(data)
    q = np.array([mapping(row)["q"] for row in data["q"]])
    t = np.array(data["time"])
    # Smooth cubic table differentiates the same recorded positions for both controllers.
    table = np.column_stack([t, q])
    text = ";\n".join(",".join(f"{v:.16g}" for v in row) for row in table)
    options=options or {}
    kp=options.get("kp",80) if improved else 40
    kd=options.get("kd",8) if improved else 4
    lag=options.get("lag",.03)
    for key,value,lo,hi in [("kp",kp,1,500),("kd",kd,0,80),("lag",lag,.005,.3)]:
        if not isinstance(value,(float,int)) or not np.isfinite(value) or not lo<=value<=hi:
            raise ValueError(f"{key} must be finite and between {lo} and {hi}")
    shutil.copytree(source_package, directory)
    (directory / "Components/DynamicRevolute.mo").write_text(JOINT_SOURCE, encoding="utf-8")
    with (directory / "Components/package.order").open("a") as file:
        file.write("\nDynamicRevolute\n")
    source = (directory / "Arms/AlohaVX300s.mo").read_text(encoding="utf-8")
    source = source.replace("within ALOHA2.Arms;", "within ALOHA2;").replace("model AlohaVX300s", "model DynamicArm").replace("end AlohaVX300s;", "end DynamicArm;")
    source = source.replace("equation\n", "  Modelica.Blocks.Interfaces.RealInput feedforward[6];\nequation\n", 1)
    selected = JOINTS[:6] if axes == 6 else ["shoulder"]
    robot = C.arm_robot("aloha_vx300s")
    for index, name in enumerate(JOINTS[:6]):
        if name in selected:
            joint = robot.joints[name]
            source = source.replace(f"ALOHA2.Components.RevoluteJoint j_{name}(",
                                    f"ALOHA2.Components.DynamicRevolute j_{name}(q_start={q[0,index]}, kp={kp}, kd={kd}, actuatorTime={lag}, damping={joint.damping or 0}, friction={joint.friction or 0}, ")
            source = source.replace("equation\n", f"equation\n  j_{name}.feedforward=feedforward[{index+1}];\n", 1)
    (directory / "DynamicArm.mo").write_text(source, encoding="utf-8")
    actual = ",".join(f"arm.j_{name}.phi" for name in JOINTS[:7]) + ",arm.j_left_finger.s"
    tau = ",".join(f"arm.j_{name}.{'applied' if name in selected else 'tau'}" for name in JOINTS[:6])
    velocity = ",".join(f"arm.j_{name}.w" for name in JOINTS[:7]) + ",arm.j_left_finger.v"
    nominal = ",".join(f"nominal.j_{name}.tau" for name in JOINTS[:6])
    experiment = f'''within ALOHA2;
model RecordedFollower
  inner Modelica.Mechanics.MultiBody.World world(n={{0,0,-1}}, animateWorld=false, animateGravity=false);
  ALOHA2.Arms.AlohaVX300s nominal(animation=false);
  ALOHA2.DynamicArm arm(animation=false);
  Modelica.Blocks.Sources.CombiTimeTable reference(table=[{text}], columns=2:9,
    smoothness=Modelica.Blocks.Types.Smoothness.ContinuousDerivative,
    extrapolation=Modelica.Blocks.Types.Extrapolation.HoldLastPoint);
  Real q_reference[8], q_actual[8], qd_actual[8], tau_actual[6], ee_reference[3], ee_actual[3];
equation
  connect(world.frame_b,nominal.frame_a);
  connect(world.frame_b,arm.frame_a);
  q_reference=reference.y;
  nominal.q=q_reference;
  nominal.qd=der(q_reference);
  nominal.qdd=der(nominal.qd);
  arm.q=q_reference;
  arm.qd=nominal.qd;
  arm.qdd=nominal.qdd;
  arm.feedforward={1 if improved else 0}*{{{nominal}}};
  q_actual={{{actual}}};
  qd_actual={{{velocity}}};
  tau_actual={{{tau}}};
  ee_reference=nominal.ee_gripper_link.frame_a.r_0;
  ee_actual=arm.ee_gripper_link.frame_a.r_0;
end RecordedFollower;
'''
    (directory / "RecordedFollower.mo").write_text(experiment, encoding="utf-8")
    with (directory / "package.order").open("a") as file:
        file.write("\nDynamicArm\nRecordedFollower\n")
    return {"kp": kp, "kd": kd, "inverse_dynamics_feedforward": improved,
            "actuator_time_s": lag, "status":"illustrative user configuration, not hardware identified", "dynamic_axes": list(selected), "reference": data["sample_sha256"]}


def measure(mat, seconds):
    time, unique = np.unique(mat.time, return_index=True)
    get = lambda prefix, n: np.array([mat.get(f"{prefix}[{i+1}]")[unique] for i in range(n)]).T
    reference, actual = get("q_reference", 8), get("q_actual", 8)
    error = actual[:, :6] - reference[:, :6]
    ee_error = np.linalg.norm(get("ee_actual", 3)-get("ee_reference", 3), axis=1)
    torque = get("tau_actual", 6)
    velocity=get("qd_actual",8) if hasattr(mat,"has") and mat.has("qd_actual[1]") else np.gradient(actual,time,axis=0)
    robot = C.arm_robot("aloha_vx300s")
    limits = sum(int(np.count_nonzero((actual[:, i] < robot.joints[j].limit.lower-1e-6) | (actual[:, i] > robot.joints[j].limit.upper+1e-6))) for i, j in enumerate(JOINTS[:6]))
    speed_limits=sum(int(np.count_nonzero(abs(velocity[:,i])>robot.joints[j].limit.velocity+1e-6)) for i,j in enumerate(JOINTS[:6]))
    duration=float(time[-1]-time[0])
    rms=lambda value:np.sqrt(np.trapezoid(value**2,time,axis=0)/duration)
    delays = []
    grid = np.linspace(time[0], time[-1], len(time))
    for i in range(6):
        a, b = np.interp(grid,time,actual[:,i]), np.interp(grid,time,reference[:,i])
        if np.ptp(b) < .01:
            delays.append(None)
        else:
            a, b = np.gradient(a), np.gradient(b)
            bound=max(1,min(100,len(grid)//4,int(.5/(grid[1]-grid[0]))))
            shift = np.arange(-bound,bound+1)
            scores = [np.mean((a[max(0,s):min(len(a),len(a)+s)] - b[max(0,-s):min(len(b),len(b)-s)])**2) for s in shift]
            best=int(np.argmin(scores))
            delays.append(float(shift[best]*(grid[1]-grid[0])) if best not in {0,len(shift)-1} else None)
    stride = max(1,len(time)//1000)
    return {"metrics": {"joint_rms_rad": rms(error).tolist(), "joint_max_rad": np.max(abs(error),axis=0).tolist(),
                        "ee_rms_m": float(rms(ee_error)), "ee_max_m": float(max(ee_error)), "delay_s": delays,
                        "peak_effort_Nm": np.max(abs(torque),axis=0).tolist(), "limit_violation_samples": limits,"velocity_limit_violation_samples":speed_limits, "runtime_s": seconds},
            "time": time[::stride].tolist(), "q_reference": reference[::stride].tolist(), "q_actual": actual[::stride].tolist(),
            "ee_error_m": ee_error[::stride].tolist(), "effort_Nm": torque[::stride].tolist(),
            "metric_method":"Time-weighted trapezoidal RMS after deduplicating timestamps. Maxima and violations on exported OMC samples; violations count joint-samples against source URDF limits. Effort is actuator output before passive friction on dynamic axes; prescribed axes report required joint torque. Peaks between exported samples are not guaranteed to be captured.",
            "delay_method": "Velocity mean-square alignment within ±0.5 s, capped at 100 samples and quarter duration. Excursion below 0.01 rad or optimum at search boundary returns null (insufficient excitation / identifiable lag). This is a coarse trajectory alignment, not identified hardware latency."}


def compare(data, axes=6, source_package=BASELINE, options=None):
    identity = uuid.uuid4().hex
    directory = C.ROOT / "runs/studio/dynamics" / identity
    directory.mkdir(parents=True)
    result = {"id": identity, "mode": "OpenModelica torque-driven follower", "baseline_hashes": manifest(BASELINE), "model_hashes":manifest(source_package), "results": {},
              "limitations": ["Controller gains and 30 ms actuator lag are illustrative, not identified hardware parameters.",
                               "URDF mass, centre of mass, tensor inertia, axes, effort limits and joint dynamics; gravity 9.80665 m/s² and full MultiBody coupling.",
                               "Six rotary axes are torque driven (or shoulder only in stage 1); gripper and other axes remain prescribed. No identified transmission, backlash or payload.",
                               "URDF friction=0.1 and damping=0.1 are generic defaults, not calibrated measurements. Coulomb friction uses tanh(w/0.01).",
                               "Both controllers use the identical mapped, cubic-interpolated recorded reference. Numerical derivatives in saved recordings are separately documented."]}
    for improved, name in [(False,"baseline"),(True,"improved")]:
        package = directory / name / "ALOHA2"
        config = generate(package,data,improved,axes,source_package,options)
        omc = OMCService(package.parent / "simulation")
        try:
            loaded = omc.load_package(package / "package.mo")
            check = omc.check("ALOHA2.RecordedFollower")
            if not loaded.ok or not check.ok:
                raise RuntimeError(json.dumps({"load":loaded.to_dict(),"check":check.to_dict()}))
            simulated = omc.simulate("ALOHA2.RecordedFollower", data["time"][-1], intervals=400,
                                     variable_filter="time|q_reference.*|q_actual.*|qd_actual.*|tau_actual.*|ee_reference.*|ee_actual.*")
            if not simulated.ok:
                raise RuntimeError(json.dumps(simulated.to_dict()))
            result["results"][name] = {**measure(MatResult(simulated.data["resultFile"]),simulated.seconds), "config":config,
                                       "check":check.to_dict(), "simulation":simulated.to_dict()}
        finally:
            omc.close()
    before, after = [result["results"][n]["metrics"]["ee_rms_m"] for n in ("baseline","improved")]
    result["conclusion"] = "Measured end-effector RMS decreased on this reference." if after < before else "No end-effector RMS improvement measured on this reference."
    (directory / "report.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
