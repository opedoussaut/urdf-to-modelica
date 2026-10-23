---
id: prescribed-motion
title: Prescribed joint motion with Move sources fed by analytic q, qd, qdd
source: CLAUDE.md (Modelica generation conventions); kkh/engineering/modelica_gen.py lines 9-12, 141-143, 183-185, 221-278
commit: 9e867d1
evidence: Validated in the generated ALOHA2 package (RightArmReach simulates and matches URDF forward kinematics); an algorithm section with Integer segment indices made OpenModelica 1.27 index reduction fail
applies_to: Kinematic test models where joints follow a given trajectory instead of being driven by actuators
---
To make a joint follow a reference motion exactly, drive its flange with a `Move` source
(`Modelica.Mechanics.Rotational.Sources.Move` for revolute joints, `...Translational.Sources.Move` for prismatic
ones). A `Move` source needs position, velocity and acceleration, and they must be mutually consistent.

- Compute q, qd and qdd from **analytic functions of time**, for example a cosine blend between waypoints:
  `q = cosineBlend(time, t_wp, Q, 0)`, `qd = cosineBlend(time, t_wp, Q, 1)`, `qdd = cosineBlend(time, t_wp, Q, 2)`.
- Give the driven joint `stateSelect = StateSelect.never`, so the tool does not choose the prescribed angle as a state.
- Do **not** put trajectory logic in an `algorithm` section that switches segments with Integer indices. OpenModelica
  1.27 index reduction fails on it.

```modelica
Modelica.Mechanics.MultiBody.Joints.Revolute joint(useAxisFlange = true, n = axis,
  stateSelect = StateSelect.never);
Modelica.Mechanics.Rotational.Sources.Move move(useSupport = true);
equation
  move.u = {q, qd, qdd};
  connect(move.flange, joint.axis);
  connect(move.support, joint.support);
```
