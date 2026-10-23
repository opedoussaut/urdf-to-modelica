# Stage 2: OpenModelica verification of the converted ALOHA 2 follower arm (2026-10-23)

This is the measured output of `PYTHONPATH=. python -m kkh.workflow.stage2_check runs/workflow/<run>`, applied to the
**unmodified** Stage 1 package (DLR URDFModelica @ `92541b6f`). The full machine-readable record is in
`stage2_aloha_vx300s.json`. Each finding has the fields
`{id, step, check, category, severity, blocking, entity, file, line, col, message, evidence, related, also_in}`.
OpenModelica v1.27.1, MSL 4.1.0; the stage takes about 50 s.

## Ordered checks
| # | Step | Result | Evidence |
|---|---|---|---|
| 1 | Load and parse | pass | — |
| 2 | Structure (`checkModel` of robot class and test model) | pass | robot 7 217 equations = 7 217 variables; test model 6 814 = 6 814 |
| 3 | Balance and translation | pass | balanced; `translateModel` succeeds, with the warning "initial conditions are not fully specified" |
| 4 | Baseline simulation (2 s) | pass | 2 runtime assertion warnings at initialisation (below) |
| 5 | URDF consistency | **fail** | coverage 14/14 links and 9/9 moving joints; axes 9/9, masses 14/14, CoM 11/11, inertia 11/11; torques 8/8 joints within 5 % of the effort limit vs MuJoCo; **kinematics: right finger up to 52.9 mm from URDF forward kinematics** |
| 6 | Graphics (separate) | fail | 30 model classes, 262 connections, **18 without a `Line`** (all in the robot model `Aloha_vx300s`: rotational flange connections, not drawn in OMEdit); 234 components all placed; 2 inputs outside the diagram extent of `Aloha_vx300sRun` |

**Verdict:** *simulates, engineering checks fail.* The package compiles and simulates, but it is **not validated**:
the right finger does not follow the URDF.

## Findings (24: 1 error, 17 warnings, 6 info; none blocking)
- **Right finger, kinematics (error).** Its position differs from URDF forward kinematics by up to 52.9 mm under the
  standard excitation. It is cross-referenced to the Stage 1 record "mimic: recorded in the parameter record but not
  used by the joint model": the right finger is free instead of mirroring the left finger.
- **Finger start positions (2 warnings).** At initialisation, `left_finger` is below its lower URDF position limit and
  `right_finger` above its upper one (its range is negative). The converter's test model starts both fingers at 0,
  outside the URDF range.
- **Initial conditions not fully specified (warning).** Reported once; it also occurs in the simulation and excitation
  steps (`also_in`).
- **`world` inner/outer (2 info).** These are expected when the robot class is checked on its own: the test model
  supplies `world`. The reason is recorded, nothing is dropped.
- **Graphics (warning + info).** 18 unrouted connections; 2 components outside the extent.
- **Carried over from Stage 1 (15).** `ros2_control` ignored; mimic unused; 11 mesh URIs rewritten to `package:_/…`;
  pre-processing T1, T2.

## What this establishes, and what it does not
- **Established:**
  - the converter output is structurally sound (balanced, simulates);
  - every URDF value is copied;
  - the joint torques agree with an independent MuJoCo reference;
  - the engineering defect is a feature the converter drops (mimic), plus a test-model initial state outside the URDF limits.
- **Not established:** behaviour beyond the 2 s baseline and the standard excitation, contact or grasping, real
  hardware. The kinematic and dynamic references are the URDF itself and MuJoCo inverse dynamics.
- **For the repair experiment:** these are **natural findings**. A repair arm must fix the right-finger kinematics
  without changing URDF-derived values. That is checked by the Stage 4 integrity guard, which is still to be built.
