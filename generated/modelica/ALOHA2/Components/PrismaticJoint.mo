within ALOHA2.Components;
model PrismaticJoint "URDF prismatic joint with prescribed motion (s, v, a)"
  import SI = Modelica.Units.SI;
  extends Modelica.Mechanics.MultiBody.Interfaces.PartialTwoFrames;
  parameter SI.Position r[3] = {0, 0, 0} "URDF joint/origin/xyz (in parent link frame)";
  parameter SI.Angle rpy[3] = {0, 0, 0} "URDF joint/origin/rpy";
  parameter Real n[3] = {1, 0, 0} "URDF joint/axis (in joint frame)";
  parameter SI.Position s_min = -Modelica.Constants.inf "URDF limit/lower";
  parameter SI.Position s_max = Modelica.Constants.inf "URDF limit/upper";
  parameter SI.Velocity v_max = Modelica.Constants.inf "URDF limit/velocity";
  parameter SI.Force f_max = Modelica.Constants.inf "URDF limit/effort";
  Modelica.Blocks.Interfaces.RealInput q "Prescribed position [m]"
    annotation (Placement(transformation(origin={-60,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qd "Prescribed velocity [m/s]"
    annotation (Placement(transformation(origin={0,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qdd "Prescribed acceleration [m/s2]"
    annotation (Placement(transformation(origin={60,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  SI.Position s = joint.s "Joint position";
  SI.Velocity v = der(joint.s) "Joint velocity";
  SI.Force f = joint.axis.f "Force required along the joint axis";
  Modelica.Mechanics.MultiBody.Parts.FixedRotation origin(r = r,
    rotationType = Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence,
    sequence = {3, 2, 1}, angles = Modelica.Units.Conversions.to_deg({rpy[3], rpy[2], rpy[1]}),
    animation = false) annotation (Placement(transformation(extent={{-70,-10},{-50,10}})));
  Modelica.Mechanics.MultiBody.Joints.Prismatic joint(n = n, useAxisFlange = true, animation = false,
    stateSelect = StateSelect.never)
    annotation (Placement(transformation(extent={{-10,-10},{10,10}})));
  Modelica.Mechanics.Translational.Sources.Move move(useSupport = true)
    annotation (Placement(transformation(extent={{-10,40},{10,60}})));
equation
  move.u = {q, qd, qdd};
  connect(frame_a, origin.frame_a);
  connect(origin.frame_b, joint.frame_a);
  connect(joint.frame_b, frame_b);
  connect(move.flange, joint.axis);
  connect(move.support, joint.support);
  assert(s >= s_min - 1e-9 and s <= s_max + 1e-9, "Joint position outside URDF limits",
    AssertionLevel.warning);
  annotation (Icon(graphics={Rectangle(extent={{-100,-50},{-30,50}}, fillColor={192,192,192},
    fillPattern=FillPattern.Solid), Rectangle(extent={{-30,-30},{100,30}}, fillColor={230,230,230},
    fillPattern=FillPattern.Solid), Text(extent={{-150,-70},{150,-110}}, textString="%name",
    textColor={0,0,255})}));
end PrismaticJoint;
