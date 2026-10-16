within ALOHA2;
model Aloha2 "ALOHA 2 robot: two follower ALOHA ViperX-300 6DOF arms at the official ALOHA 2 base poses"
  parameter Boolean animation = true "Animate link meshes";
  constant Integer nq = 16 "Number of independently driven joints (2 arms x 8)";
  Modelica.Mechanics.MultiBody.Interfaces.Frame_a frame_a "Robot (world) frame"
    annotation (Placement(transformation(extent={{-116,-16},{-84,16}})));
  Modelica.Blocks.Interfaces.RealInput q[nq] "Joint positions, see documentation for layout"
    annotation (Placement(transformation(origin={-60,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qd[nq] "Joint velocities"
    annotation (Placement(transformation(origin={0,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qdd[nq] "Joint accelerations"
    annotation (Placement(transformation(origin={60,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Mechanics.MultiBody.Parts.FixedRotation mount_left(r = {-0.469, -0.019, 0.02}, rotationType = Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence, sequence = {3, 2, 1}, angles = Modelica.Units.Conversions.to_deg({0, 0, 0}), animation = false) "Base mount world -> follower_left/base_link (google-deepmind/mujoco_menagerie@62ab00f aloha/aloha.xml (left/base_link, right/base_link body poses))"
    annotation (Placement(transformation(origin={-40, 40}, extent={{-10,-10},{10,10}})));
  ALOHA2.Arms.AlohaVX300s left(animation = animation) "ALOHA ViperX-300 6DOF (follower), left"
    annotation (Placement(transformation(origin={20, 40}, extent={{-10,-10},{10,10}})));
  Modelica.Mechanics.MultiBody.Parts.FixedRotation mount_right(r = {0.469, -0.019, 0.02}, rotationType = Modelica.Mechanics.MultiBody.Types.RotationTypes.PlanarRotationSequence, sequence = {3, 2, 1}, angles = Modelica.Units.Conversions.to_deg({3.14159265359, 0, 0}), animation = false) "Base mount world -> follower_right/base_link (google-deepmind/mujoco_menagerie@62ab00f aloha/aloha.xml (left/base_link, right/base_link body poses))"
    annotation (Placement(transformation(origin={-40, -20}, extent={{-10,-10},{10,10}})));
  ALOHA2.Arms.AlohaVX300s right(animation = animation) "ALOHA ViperX-300 6DOF (follower), right"
    annotation (Placement(transformation(origin={20, -20}, extent={{-10,-10},{10,10}})));
equation
  connect(frame_a, mount_left.frame_a);
  connect(mount_left.frame_b, left.frame_a);
  connect(q[1:8], left.q);
  connect(qd[1:8], left.qd);
  connect(qdd[1:8], left.qdd);
  connect(frame_a, mount_right.frame_a);
  connect(mount_right.frame_b, right.frame_a);
  connect(q[9:16], right.q);
  connect(qd[9:16], right.qd);
  connect(qdd[9:16], right.qdd);
  annotation (Icon(graphics={Rectangle(extent={{-100,100},{100,-100}}, fillColor={255,255,255},
      fillPattern=FillPattern.Solid), Text(extent={{-90,40},{90,-40}}, textString="ALOHA 2"),
      Text(extent={{-150,150},{150,110}}, textString="%name", textColor={0,0,255})}),
    Documentation(info="<html><p>Two follower arms mounted at the base poses of the official ALOHA 2 MuJoCo model
(<code>google-deepmind/mujoco_menagerie@62ab00f aloha/aloha.xml</code>). Input layout:</p><ul><li>q[1:8] &rarr; left (waist, shoulder, elbow, forearm_roll, wrist_angle, wrist_rotate, gripper, left_finger)</li><li>q[9:16] &rarr; right (waist, shoulder, elbow, forearm_roll, wrist_angle, wrist_rotate, gripper, left_finger)</li></ul>
<p>Right-finger joints follow the URDF mimic relation (right = -left).</p></html>"));
end Aloha2;
