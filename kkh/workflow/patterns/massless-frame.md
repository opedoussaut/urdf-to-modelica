---
id: massless-frame
title: Massless link without geometry must close its frame equations
source: CLAUDE.md (Modelica generation conventions); kkh/engineering/modelica_gen.py lines 102-106
commit: 9e867d1
evidence: Validated in the generated ALOHA2 package (RightArmReach and LeaderArmCheck check, simulate and match URDF forward kinematics); without these equations OpenModelica reports 6 missing equations per massless link
applies_to: MultiBody link components with no inertia and no visual shape; URDF links with placeholder or absent inertials
---
A link component that has neither a body (no mass/inertia) nor a visual shape connects only its `frame_a` to the
connection set. Its connector then has 6 flow variables (force `f[3]`, torque `t[3]`) that no equation defines, so
the model is under-determined: 6 missing equations for each such link.

Close the frame explicitly inside the link class when it has neither inertia nor shape:

```modelica
equation
  if not hasInertia and not hasShape then
    // Massless, invisible reference frame: contributes no force/torque to the connection set.
    frame_a.f = zeros(3);
    frame_a.t = zeros(3);
  end if;
```

Do not give such a link an arbitrary small mass to balance the equations: that changes the physics. The URDF's own
values (including "no inertial") are kept, and the frame is closed instead.
