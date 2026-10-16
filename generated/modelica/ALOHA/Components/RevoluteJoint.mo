within ALOHA.Components;
model RevoluteJoint "URDF revolute/continuous joint with prescribed motion (q, qd, qdd)"
  import SI = Modelica.Units.SI;
  extends Modelica.Mechanics.MultiBody.Interfaces.PartialTwoFrames;
  parameter SI.Position r[3] = {0, 0, 0} "URDF joint/origin/xyz (in parent link frame)";
  parameter SI.Angle rpy[3] = {0, 0, 0} "URDF joint/origin/rpy";
  parameter Real n[3] = {0, 0, 1} "URDF joint/axis (in joint frame)";
  parameter Boolean limited = true "false for URDF continuous joints" annotation (Evaluate=true);
  parameter SI.Angle q_min = -Modelica.Constants.inf "URDF limit/lower";
  parameter SI.Angle q_max = Modelica.Constants.inf "URDF limit/upper";
  parameter SI.AngularVelocity qd_max = Modelica.Constants.inf "URDF limit/velocity";
  parameter SI.Torque tau_max = Modelica.Constants.inf "URDF limit/effort";
  Modelica.Blocks.Interfaces.RealInput q "Prescribed angle [rad]"
    annotation (Placement(transformation(origin={-60,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qd "Prescribed angular velocity [rad/s]"
    annotation (Placement(transformation(origin={0,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qdd "Prescribed angular acceleration [rad/s2]"
    annotation (Placement(transformation(origin={60,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  SI.Angle phi = joint.phi "Joint angle";
  SI.AngularVelocity w = der(joint.phi) "Joint angular velocity";
  SI.Torque tau = joint.axis.tau "Torque required at the joint axis";
  Modelica.Mechanics.MultiBody.Parts.FixedRotation origin(r = r,
    rotationType = Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence,
    sequence = {3, 2, 1}, angles = Modelica.Units.Conversions.to_deg({rpy[3], rpy[2], rpy[1]}),
    animation = false) annotation (Placement(transformation(extent={{-70,-10},{-50,10}})));
  Modelica.Mechanics.MultiBody.Joints.Revolute joint(n = n, useAxisFlange = true, animation = false,
    stateSelect = StateSelect.never)
    annotation (Placement(transformation(extent={{-10,-10},{10,10}})));
  Modelica.Mechanics.Rotational.Sources.Move move(useSupport = true)
    annotation (Placement(transformation(extent={{-10,40},{10,60}})));
equation
  move.u = {q, qd, qdd};
  connect(frame_a, origin.frame_a);
  connect(origin.frame_b, joint.frame_a);
  connect(joint.frame_b, frame_b);
  connect(move.flange, joint.axis);
  connect(move.support, joint.support);
  if limited then
    assert(phi >= q_min - 1e-6 and phi <= q_max + 1e-6, "Joint angle outside URDF limits",
      AssertionLevel.warning);
  end if;
  annotation (Icon(graphics={Rectangle(extent={{-100,-60},{-20,60}}, fillColor={192,192,192},
    fillPattern=FillPattern.HorizontalCylinder), Rectangle(extent={{20,-60},{100,60}},
    fillColor={192,192,192}, fillPattern=FillPattern.HorizontalCylinder),
    Text(extent={{-150,-70},{150,-110}}, textString="%name", textColor={0,0,255})}));
end RevoluteJoint;
