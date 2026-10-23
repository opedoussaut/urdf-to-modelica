---
id: joint-input-units
title: Joint input vectors that mix revolute and prismatic joints carry no unit attribute
source: CLAUDE.md (Modelica generation conventions); kkh/engineering/modelica_gen.py lines 127-131, 169-173, 407-411
commit: 9e867d1
evidence: Validated in the generated ALOHA2 package; a unit on the mixed vector triggered unit-inconsistency findings in OpenModelica
applies_to: Robot models whose actuated joints include both revolute (rad) and prismatic (m) joints, fed by one input vector
---
A robot class usually receives the positions of all actuated joints as one vector, for example
`RealInput q[nq]`. When the arm has revolute joints (radians) and prismatic joints such as gripper fingers (metres),
no single `unit` is correct for the whole vector. Declaring `unit="rad"` makes every prismatic element inconsistent,
and OpenModelica's unit checking reports it.

Declare the shared connector without a `unit`, and state the meaning in the description string:

```modelica
Modelica.Blocks.Interfaces.RealInput q[nq] "Joint positions [rad or m]: 1: waist, ..., 8: left_finger";
```

The project applies the same rule to the joint components' own input connectors: they carry no `unit` attribute
either, and the unit is stated in the description string (`RealInput q "Prescribed angle [rad]"` for a revolute
joint, `"Prescribed position [m]"` for a prismatic one, modelica_gen.py lines 127-131 and 169-173). The physical
quantities inside the joints (joint angle, position) keep their MSL units.
