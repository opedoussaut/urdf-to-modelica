within GEN7Contact;
model TwoFingerGrasp "Reduced-order 2D pinch, lift and release: experimental contact surrogate"
  import SI = Modelica.Units.SI;
  parameter SI.Mass cubeMass = 0.08 "ASSUMED cube mass";
  parameter SI.Length cubeSide = 0.04 "ASSUMED cube width/height";
  parameter SI.Acceleration gravity = 9.81;
  parameter SI.TranslationalSpringConstant fingerStiffness = 8000 "ASSUMED N/m";
  parameter SI.TranslationalDampingConstant fingerDamping = 5 "ASSUMED N.s/m";
  parameter SI.TranslationalSpringConstant tableStiffness = 20000 "ASSUMED N/m";
  parameter SI.TranslationalDampingConstant tableDamping = 8 "ASSUMED N.s/m";
  parameter Real frictionCoefficient(min=0) = 0.6 "ASSUMED Coulomb friction coefficient";
  parameter SI.Velocity regularizationSpeed = 0.002 "ASSUMED friction transition speed";
  parameter SI.Length openGap = 0.058;
  parameter SI.Length closedGap = 0.038 "Compresses cube by 1 mm per side at centre";
  parameter SI.Length liftHeight = 0.08;

  SI.Position x(start=0, fixed=true) "Cube horizontal centre relative to gripper centre";
  SI.Velocity vx(start=0, fixed=true);
  SI.Position z(start=cubeSide/2, fixed=true) "Cube centre above tabletop";
  SI.Velocity vz(start=0, fixed=true);
  SI.Length gripGap "Distance between finger inner surfaces";
  SI.Position fingerZ "Prescribed finger centre height (not an ALOHA mechanism)";
  SI.Velocity fingerVz;
  SI.Length leftPenetration;
  SI.Length rightPenetration;
  SI.Length tablePenetration;
  SI.Force leftNormal;
  SI.Force rightNormal;
  SI.Force tableNormal;
  SI.Force leftFriction "Positive = upward";
  SI.Force rightFriction "Positive = upward";
  SI.Force leftFrictionLimit "Computed mu*N, exported as a time-varying diagnostic";
  SI.Force rightFrictionLimit "Computed mu*N, exported as a time-varying diagnostic";
  SI.Force gripVerticalForce;
  Boolean twoSidedContact;

equation
  // Smooth prescribed closing, raising and opening. Motion is NOT VLA inference.
  gripGap = if time < 0.1 then openGap else
    if time < 0.4 then openGap + (closedGap - openGap)*
      (1 - cos(Modelica.Constants.pi*(time - 0.1)/0.3))/2 else
    if time < 1.45 then closedGap else
    if time < 1.7 then closedGap + (openGap - closedGap)*
      (1 - cos(Modelica.Constants.pi*(time - 1.45)/0.25))/2 else openGap;
  fingerZ = if time < 0.65 then cubeSide/2 else
    if time < 1.15 then cubeSide/2 + liftHeight*
      (1 - cos(Modelica.Constants.pi*(time - 0.65)/0.5))/2 else cubeSide/2 + liftHeight;
  fingerVz = der(fingerZ);

  leftPenetration = max(0, cubeSide/2 - gripGap/2 - x);
  rightPenetration = max(0, cubeSide/2 - gripGap/2 + x);
  leftNormal = noEvent(if leftPenetration > 0 then max(0,
    fingerStiffness*leftPenetration + fingerDamping*max(0, -der(gripGap)/2 - vx)) else 0);
  rightNormal = noEvent(if rightPenetration > 0 then max(0,
    fingerStiffness*rightPenetration + fingerDamping*max(0, -der(gripGap)/2 + vx)) else 0);
  leftFrictionLimit = frictionCoefficient*leftNormal;
  rightFrictionLimit = frictionCoefficient*rightNormal;
  leftFriction = leftFrictionLimit*Modelica.Math.tanh((fingerVz - vz)/regularizationSpeed);
  rightFriction = rightFrictionLimit*Modelica.Math.tanh((fingerVz - vz)/regularizationSpeed);
  gripVerticalForce = leftFriction + rightFriction;
  twoSidedContact = noEvent(leftNormal > 0 and rightNormal > 0);

  tablePenetration = max(0, cubeSide/2 - z);
  tableNormal = noEvent(if tablePenetration > 0 then max(0,
    tableStiffness*tablePenetration + tableDamping*max(0, -vz)) else 0);

  der(x) = vx;
  der(z) = vz;
  cubeMass*der(vx) = leftNormal - rightNormal;
  cubeMass*der(vz) = tableNormal + gripVerticalForce - cubeMass*gravity;

  annotation(experiment(StartTime=0, StopTime=2.4, Interval=0.001),
    Documentation(info="<html><p>Experimental reduced-order 2D pinch/lift/release surrogate. Two prescribed finger inner faces produce unilateral penalty normal forces. Vertical friction is regularized and limited by mu*N. The cube has 2 translational DOFs; rotation, edge contact, finger geometry, distributed pressure, actuator dynamics and real ALOHA link coupling are NOT represented. Finite penetration is intentional. All physical parameters are assumed, not measured. Use for hypothesis testing, never for claims of validated grasp stability.</p></html>"));
end TwoFingerGrasp;
