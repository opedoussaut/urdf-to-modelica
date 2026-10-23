---
id: urdf-rpy-rotation
title: URDF origin rpy maps to FixedRotation with a planar rotation sequence {3,2,1}
source: CLAUDE.md (Modelica generation conventions); kkh/engineering/modelica_gen.py lines 135-139, 177-181, 203-207
commit: 9e867d1
evidence: Validated in the generated ALOHA2 package: simulated link frames match URDF forward kinematics (kkh.engineering.validation)
applies_to: Every URDF joint origin with a non-zero rpy, translated into MSL MultiBody parts
---
A URDF origin `rpy = "r p y"` means: rotate about the fixed X axis by roll, then about fixed Y by pitch, then about
fixed Z by yaw. That is the same as rotating about the moving axes in the order Z (yaw), Y (pitch), X (roll).

In the Modelica Standard Library this is `Modelica.Mechanics.MultiBody.Parts.FixedRotation` with a planar rotation
sequence `{3, 2, 1}` and the angles in that order, converted to degrees:

```modelica
Modelica.Mechanics.MultiBody.Parts.FixedRotation origin(
  r = xyz,
  rotationType = Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence,
  sequence = {3, 2, 1},
  angles = Modelica.Units.Conversions.to_deg({rpy[3], rpy[2], rpy[1]}));
```

The common mistakes are passing `{roll, pitch, yaw}` with sequence `{1, 2, 3}`, or forgetting the conversion to
degrees (`angles` is in degrees). Both produce frames that look plausible but no longer match the URDF.
