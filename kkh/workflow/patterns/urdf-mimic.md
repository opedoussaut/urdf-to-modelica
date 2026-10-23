---
id: urdf-mimic
title: URDF mimic joint expressed as an equation on the mimicking joint
source: kkh/engineering/modelica_gen.py lines 389-397
commit: 9e867d1
evidence: Validated in the generated ALOHA2 package: the mimicking finger follows URDF forward kinematics in RightArmReach (kkh.engineering.validation, mimic error reported)
applies_to: Any URDF joint with a <mimic joint="src" multiplier="m" offset="o"/> element, in kinematically driven models
---
In URDF, `<mimic joint="src" multiplier="m" offset="o"/>` means the joint's position is always `m * q_src + o`.
Copying the mimic values into a parameter record is not enough: unless an equation uses them, the joint moves
independently and the model no longer matches the URDF.

When the joints are driven kinematically (prescribed motion), give the mimicking joint the source joint's motion
through the mimic relation instead of its own input, for position, velocity and acceleration:

```modelica
// URDF mimic: child = m * src + o
child.q   = m * q[i_src] + o;
child.qd  = m * qd[i_src];
child.qdd = m * qdd[i_src];
```

The multiplier and offset come from the URDF unchanged. The mimicking joint is then not an independent input.
When joints are driven by actuators instead, the same relation is a constraint between the two joint positions
(for example `child.q = m * src.q + o` on the joint angle or position variables), and only the source joint is actuated.
