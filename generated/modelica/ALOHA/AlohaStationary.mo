within ALOHA;
model AlohaStationary "Complete ALOHA Stationary mechanical assembly: 2 follower ViperX-300 + 2 leader WidowX-250 arms"
  parameter Boolean animation = true "Animate link meshes";
  constant Integer nq = 32 "Number of independently driven joints (4 arms x 8)";
  Modelica.Mechanics.MultiBody.Interfaces.Frame_a frame_a "Workcell (ROS 'world') frame"
    annotation (Placement(transformation(extent={{-116,-16},{-84,16}})));
  Modelica.Blocks.Interfaces.RealInput q[nq] "Joint positions, see documentation for layout"
    annotation (Placement(transformation(origin={-60,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qd[nq] "Joint velocities"
    annotation (Placement(transformation(origin={0,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qdd[nq] "Joint accelerations"
    annotation (Placement(transformation(origin={60,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation mount_followerLeft(r = {0.5, 0.25, 0}, animation = false) "Mount world -> follower_left/base_link (aloha_bringup.launch.py)"
    annotation (Placement(transformation(origin={-40, 60}, extent={{-10,-10},{10,10}})));
  ALOHA.Arms.AlohaVX300s followerLeft(animation = animation) "ALOHA ViperX-300 6DOF - follower left"
    annotation (Placement(transformation(origin={20, 60}, extent={{-10,-10},{10,10}})));
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation mount_followerRight(r = {0.5, -0.25, 0}, animation = false) "Mount world -> follower_right/base_link (aloha_bringup.launch.py)"
    annotation (Placement(transformation(origin={-40, 20}, extent={{-10,-10},{10,10}})));
  ALOHA.Arms.AlohaVX300s followerRight(animation = animation) "ALOHA ViperX-300 6DOF - follower right"
    annotation (Placement(transformation(origin={20, 20}, extent={{-10,-10},{10,10}})));
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation mount_leaderLeft(r = {-0.5, 0.25, 0}, animation = false) "Mount world -> leader_left/base_link (aloha_bringup.launch.py)"
    annotation (Placement(transformation(origin={-40, -20}, extent={{-10,-10},{10,10}})));
  ALOHA.Arms.AlohaWX250s leaderLeft(animation = animation) "ALOHA WidowX-250 6DOF - leader left"
    annotation (Placement(transformation(origin={20, -20}, extent={{-10,-10},{10,10}})));
  Modelica.Mechanics.MultiBody.Parts.FixedTranslation mount_leaderRight(r = {-0.5, -0.25, 0}, animation = false) "Mount world -> leader_right/base_link (aloha_bringup.launch.py)"
    annotation (Placement(transformation(origin={-40, -60}, extent={{-10,-10},{10,10}})));
  ALOHA.Arms.AlohaWX250s leaderRight(animation = animation) "ALOHA WidowX-250 6DOF - leader right"
    annotation (Placement(transformation(origin={20, -60}, extent={{-10,-10},{10,10}})));
equation
  connect(frame_a, mount_followerLeft.frame_a);
  connect(mount_followerLeft.frame_b, followerLeft.frame_a);
  connect(q[1:8], followerLeft.q);
  connect(qd[1:8], followerLeft.qd);
  connect(qdd[1:8], followerLeft.qdd);
  connect(frame_a, mount_followerRight.frame_a);
  connect(mount_followerRight.frame_b, followerRight.frame_a);
  connect(q[9:16], followerRight.q);
  connect(qd[9:16], followerRight.qd);
  connect(qdd[9:16], followerRight.qdd);
  connect(frame_a, mount_leaderLeft.frame_a);
  connect(mount_leaderLeft.frame_b, leaderLeft.frame_a);
  connect(q[17:24], leaderLeft.q);
  connect(qd[17:24], leaderLeft.qd);
  connect(qdd[17:24], leaderLeft.qdd);
  connect(frame_a, mount_leaderRight.frame_a);
  connect(mount_leaderRight.frame_b, leaderRight.frame_a);
  connect(q[25:32], leaderRight.q);
  connect(qd[25:32], leaderRight.qd);
  connect(qdd[25:32], leaderRight.qdd);
  annotation (Icon(graphics={Rectangle(extent={{-100,100},{100,-100}}, fillColor={255,255,255},
      fillPattern=FillPattern.Solid), Text(extent={{-90,40},{90,-40}}, textString="ALOHA"),
      Text(extent={{-150,150},{150,110}}, textString="%name", textColor={0,0,255})}),
    Documentation(info="<html><p>Four arms mounted on the workcell frame at the static transforms published by
<code>Interbotix/aloha launch/aloha_bringup.launch.py</code>. Input layout:</p><ul><li>q[1:8] &rarr; followerLeft (waist, shoulder, elbow, forearm_roll, wrist_angle, wrist_rotate, gripper, left_finger)</li><li>q[9:16] &rarr; followerRight (waist, shoulder, elbow, forearm_roll, wrist_angle, wrist_rotate, gripper, left_finger)</li><li>q[17:24] &rarr; leaderLeft (waist, shoulder, elbow, forearm_roll, wrist_angle, wrist_rotate, gripper, left_finger)</li><li>q[25:32] &rarr; leaderRight (waist, shoulder, elbow, forearm_roll, wrist_angle, wrist_rotate, gripper, left_finger)</li></ul>
<p>Right finger joints follow the URDF mimic relation (right = -left).</p></html>"));
end AlohaStationary;
