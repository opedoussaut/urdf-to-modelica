within GEN7Contact;
model CubeTableDrop "Minimal vertical cube/table contact experiment, not a grasp model"
  import SI = Modelica.Units.SI;

  parameter SI.Mass cubeMass = 0.08 "ASSUMED cube mass; not hardware-identified";
  parameter SI.Length cubeSide = 0.04 "ASSUMED edge length";
  parameter SI.Acceleration gravity = 9.81;
  parameter SI.TranslationalSpringConstant contactStiffness = 2000
    "ASSUMED penalty stiffness (N/m)";
  parameter SI.TranslationalDampingConstant contactDamping = 2
    "ASSUMED penetration damping (N.s/m)";
  parameter SI.Position initialCentreHeight = 0.12;
  parameter SI.Velocity initialVerticalSpeed = 0;

  SI.Position z(start=initialCentreHeight, fixed=true) "Cube centre above table plane";
  SI.Velocity vz(start=initialVerticalSpeed, fixed=true);
  SI.Length penetration "Positive only while cube intersects table plane";
  SI.Force normalForce "Unilateral contact reaction; never tensile";
  SI.Energy mechanicalEnergy "Diagnostic: gravity + kinetic energy";
  Boolean touching;

equation
  der(z) = vz;
  penetration = max(0, cubeSide/2 - z);
  touching = noEvent(penetration > 0);
  // Penalty contact: use damping only while moving into the table.
  // This model allows small penetration and is not a rigid constraint solver.
  normalForce = noEvent(if penetration > 0 then
    max(0, contactStiffness*penetration + contactDamping*max(0, -vz)) else 0);
  cubeMass*der(vz) = normalForce - cubeMass*gravity;
  mechanicalEnergy = 0.5*cubeMass*vz*vz + cubeMass*gravity*z;

  annotation (experiment(StartTime=0, StopTime=1.5, Interval=0.001),
    Documentation(info="<html><p>Isolated 1D vertical cube/table drop with unilateral penalty contact. It tests gravity and table reaction only; no horizontal geometry, gripper, friction, collision meshes, grasp stability, or ALOHA robot coupling. All cube/contact parameters are assumptions. It does not establish physical accuracy.</p></html>"));
end CubeTableDrop;
