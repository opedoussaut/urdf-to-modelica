within ALOHA.Components;
model FixedJoint "URDF fixed joint: constant transform from parent to child link frame"
  import SI = Modelica.Units.SI;
  extends Modelica.Mechanics.MultiBody.Interfaces.PartialTwoFrames;
  parameter SI.Position r[3] = {0, 0, 0} "URDF joint/origin/xyz (in parent link frame)";
  parameter SI.Angle rpy[3] = {0, 0, 0} "URDF joint/origin/rpy";
  Modelica.Mechanics.MultiBody.Parts.FixedRotation origin(r = r,
    rotationType = Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence,
    sequence = {3, 2, 1}, angles = Modelica.Units.Conversions.to_deg({rpy[3], rpy[2], rpy[1]}),
    animation = false) annotation (Placement(transformation(extent={{-10,-10},{10,10}})));
equation
  connect(frame_a, origin.frame_a);
  connect(origin.frame_b, frame_b);
  annotation (Icon(graphics={Rectangle(extent={{-100,10},{100,-10}}, fillColor={95,95,95},
    fillPattern=FillPattern.Solid), Text(extent={{-150,-30},{150,-70}}, textString="%name",
    textColor={0,0,255})}));
end FixedJoint;
