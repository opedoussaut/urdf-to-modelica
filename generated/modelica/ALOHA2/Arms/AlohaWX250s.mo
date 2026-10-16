within ALOHA2.Arms;
model AlohaWX250s "ALOHA WidowX-250 6DOF (leader) (aloha_wx250s URDF)"
  parameter Boolean animation = true "Animate link meshes";
  constant Integer nq = 8 "Number of independently driven joints";
  Modelica.Mechanics.MultiBody.Interfaces.Frame_a frame_a "Mount frame = URDF root link base_link"
    annotation (Placement(transformation(extent={{-116,-16},{-84,16}})));
  Modelica.Blocks.Interfaces.RealInput q[nq] "Joint positions [rad or m]: 1: waist, 2: shoulder, 3: elbow, 4: forearm_roll, 5: wrist_angle, 6: wrist_rotate, 7: gripper, 8: left_finger"
    annotation (Placement(transformation(origin={-60,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qd[nq] "Joint velocities"
    annotation (Placement(transformation(origin={0,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  Modelica.Blocks.Interfaces.RealInput qdd[nq] "Joint accelerations"
    annotation (Placement(transformation(origin={60,120}, extent={{-20,-20},{20,20}}, rotation=-90)));
  ALOHA2.Components.RigidLink base_link(hasInertia = true, m = 0.538736, r_CM = {-0.0380446, 0.000613892, 0.0193354}, I = [0.0006921, 1.635e-05, -4.642e-05; 1.635e-05, 0.002115, 6.998e-07; -4.642e-05, 6.998e-07, 0.002524], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/base.stl", r_shape = {0, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link base_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, 180}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink shoulder_link(hasInertia = true, m = 0.480879, r_CM = {2.23482e-05, 4.14609e-05, 0.0066287}, I = [0.0005557, -2.2e-09, -1.2245e-06; -2.2e-09, 0.000379, -3.561e-07; -1.2245e-06, -3.561e-07, 0.0005889], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/shoulder.stl", r_shape = {0, 0, -0.003}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link shoulder_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, 100}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink upper_arm_link(hasInertia = true, m = 0.489715, r_CM = {0.015386, 0, 0.18511}, I = [0.0043745412, 2e-10, -0.0004799594; 2e-10, 0.0042527386, -1.5e-09; -0.0004799594, -1.5e-09, 0.0004827537], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/upper_arm.stl", r_shape = {0, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link upper_arm_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, 20}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink upper_forearm_link(hasInertia = true, m = 0.234589, r_CM = {0.107963, 0.000115876, 0}, I = [3.971e-05, 2.3528e-06, 0; 2.3528e-06, 0.0008878, 0; 0, 0, 0.000888], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/upper_forearm.stl", r_shape = {0, 0, 0}, lengthDirection = {1.0, 0, 0}, widthDirection = {0, 1.0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link upper_forearm_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -60}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink lower_forearm_link(hasInertia = true, m = 0.252924, r_CM = {0.033582, 0.004726, 0}, I = [7.41889e-05, 1.94025e-05, 0; 1.94025e-05, 0.0002100083, 4e-10; 0, 4e-10, 0.0002256883], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/lower_forearm.stl", r_shape = {0, 0, 0}, lengthDirection = {1.0, 0, 0}, widthDirection = {0, -1.0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link lower_forearm_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -140}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink wrist_link(hasInertia = true, m = 0.156052, r_CM = {0.0484, 2e-06, 0.008123}, I = [5.51559e-05, 2e-10, 3.7652e-06; 2e-10, 6.91991e-05, -4.2e-09; 3.7652e-06, -4.2e-09, 6.56414e-05], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/wrist.stl", r_shape = {0, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link wrist_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -220}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink gripper_link(hasInertia = true, m = 0.103095, r_CM = {0.019411, 0, 0.00501}, I = [3.24528e-05, -1e-10, -2.3449e-06; -1e-10, 3.57525e-05, 0; -2.3449e-06, 0, 2.708e-05], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/gripper.stl", r_shape = {-0.02, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link gripper_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -300}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink handle_link(hasInertia = true, m = 0.062224, r_CM = {0.00763, 0, -0.035739}, I = [0.0001321742, -3e-10, -1.99732e-05; -3e-10, 0.0001309199, -1e-10; -1.99732e-05, -1e-10, 1.39779e-05], hasShape = false) "URDF link handle_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -380}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink ee_arm_link(hasInertia = false, hasShape = false) "URDF link ee_arm_link (massless frame: URDF inertial is a placeholder)"
    annotation (Placement(transformation(origin={-40, -460}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink gripper_prop_link(hasInertia = true, m = 0.01034, r_CM = {0.000846, -1.6817e-06, 4.2e-05}, I = [1.1156e-06, 0, 4e-10; 0, 5.923e-07, 3.195e-07; 4e-10, 3.195e-07, 5.743e-07], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/gripper_prop.stl", r_shape = {-0.0685, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link gripper_prop_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -540}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink gripper_bar_link(hasInertia = true, m = 0.133504, r_CM = {0.011745, 0, 0.001831}, I = [0.0002705379, 1.5e-09, 2.643e-06; 1.5e-09, 3.71885e-05, 0; 2.643e-06, 0, 0.0002579847], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/gripper_bar.stl", r_shape = {-0.063, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link gripper_bar_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -620}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink fingers_link(hasInertia = false, hasShape = false) "URDF link fingers_link (massless frame: URDF inertial is a placeholder)"
    annotation (Placement(transformation(origin={-40, -700}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink left_finger_link(hasInertia = true, m = 0.040526, r_CM = {0.004206, 0, -0.00803}, I = [1.64667e-05, -6.813e-07, 1.193e-07; -6.813e-07, 1.69266e-05, -1.691e-07; 1.193e-07, -1.691e-07, 3.8108e-06], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/gripper_finger.stl", r_shape = {0, 0.005, 0}, lengthDirection = {-1.0, 0, 0}, widthDirection = {0, -1.0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link left_finger_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -780}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink right_finger_link(hasInertia = true, m = 0.040995, r_CM = {0.003969, 0, -0.006528}, I = [1.75327e-05, 6.84e-07, 5.777e-07; 6.84e-07, 1.81304e-05, -6.879e-07; 5.777e-07, -6.879e-07, 3.9562e-06], hasShape = true, shapeFile = "modelica://ALOHA2/Resources/Meshes/aloha_wx250s/gripper_finger.stl", r_shape = {0, -0.005, 0}, lengthDirection = {-1.0, 0, 0}, widthDirection = {0, 1.0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link right_finger_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -860}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RigidLink ee_gripper_link(hasInertia = false, hasShape = false) "URDF link ee_gripper_link (massless frame: URDF inertial is a placeholder)"
    annotation (Placement(transformation(origin={-40, -940}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RevoluteJoint j_waist(r = {0, 0, 0.072}, rpy = {0, 0, 0}, n = {0, 0, 1.0}, limited = true, q_min = -3.14158265359, q_max = 3.14158265359, qd_max = 3.14159265359, tau_max = 10.0) "URDF joint waist (revolute): base_link -> shoulder_link"
    annotation (Placement(transformation(origin={20, 140}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RevoluteJoint j_shoulder(r = {0, 0, 0.03865}, rpy = {0, 0, 0}, n = {0, 1.0, 0}, limited = true, q_min = -1.884955592154, q_max = 1.989675347274, qd_max = 3.14159265359, tau_max = 20.0) "URDF joint shoulder (revolute): shoulder_link -> upper_arm_link"
    annotation (Placement(transformation(origin={20, 60}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RevoluteJoint j_elbow(r = {0.04975, 0, 0.25}, rpy = {0, 0, 0}, n = {0, 1.0, 0}, limited = true, q_min = -2.146754979953, q_max = 1.605702911835, qd_max = 3.14159265359, tau_max = 15.0) "URDF joint elbow (revolute): upper_arm_link -> upper_forearm_link"
    annotation (Placement(transformation(origin={20, -20}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RevoluteJoint j_forearm_roll(r = {0.175, 0, 0}, rpy = {0, 0, 0}, n = {1.0, 0, 0}, limited = true, q_min = -3.14158265359, q_max = 3.14158265359, qd_max = 3.14159265359, tau_max = 2.0) "URDF joint forearm_roll (revolute): upper_forearm_link -> lower_forearm_link"
    annotation (Placement(transformation(origin={20, -100}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RevoluteJoint j_wrist_angle(r = {0.075, 0, 0}, rpy = {0, 0, 0}, n = {0, 1.0, 0}, limited = true, q_min = -1.745329251994, q_max = 2.146754979953, qd_max = 3.14159265359, tau_max = 5.0) "URDF joint wrist_angle (revolute): lower_forearm_link -> wrist_link"
    annotation (Placement(transformation(origin={20, -180}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RevoluteJoint j_wrist_rotate(r = {0.065, 0, 0}, rpy = {0, 0, 0}, n = {1.0, 0, 0}, limited = true, q_min = -3.14158265359, q_max = 3.14158265359, qd_max = 3.14159265359, tau_max = 1.0) "URDF joint wrist_rotate (revolute): wrist_link -> gripper_link"
    annotation (Placement(transformation(origin={20, -260}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.FixedJoint j_gripper_handle(r = {0, 0, 0}, rpy = {0, 0, 0}) "URDF joint gripper_handle (fixed): gripper_link -> handle_link"
    annotation (Placement(transformation(origin={20, -340}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.FixedJoint j_ee_arm(r = {0.043, 0, 0}, rpy = {0, 0, 0}) "URDF joint ee_arm (fixed): gripper_link -> ee_arm_link"
    annotation (Placement(transformation(origin={20, -420}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.RevoluteJoint j_gripper(r = {0.0055, 0, 0}, rpy = {0, 0, 0}, n = {1.0, 0, 0}, limited = false, qd_max = 3.14159265359, tau_max = 1.0) "URDF joint gripper (continuous): ee_arm_link -> gripper_prop_link"
    annotation (Placement(transformation(origin={20, -500}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.FixedJoint j_gripper_bar(r = {0, 0, 0}, rpy = {0, 0, 0}) "URDF joint gripper_bar (fixed): ee_arm_link -> gripper_bar_link"
    annotation (Placement(transformation(origin={20, -580}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.FixedJoint j_ee_bar(r = {0.023, 0, 0}, rpy = {0, 0, 0}) "URDF joint ee_bar (fixed): gripper_bar_link -> fingers_link"
    annotation (Placement(transformation(origin={20, -660}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.PrismaticJoint j_left_finger(r = {0, 0, 0}, rpy = {0, 0, 0}, n = {0, 1.0, 0}, s_min = 0.015, s_max = 0.037, v_max = 1.0, f_max = 5.0) "URDF joint left_finger (prismatic): fingers_link -> left_finger_link"
    annotation (Placement(transformation(origin={20, -740}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.PrismaticJoint j_right_finger(r = {0, 0, 0}, rpy = {0, 0, 0}, n = {0, 1.0, 0}, s_min = -0.037, s_max = -0.015, v_max = 1.0, f_max = 5.0) "URDF joint right_finger (prismatic): fingers_link -> right_finger_link"
    annotation (Placement(transformation(origin={20, -820}, extent={{-10,-10},{10,10}})));
  ALOHA2.Components.FixedJoint j_ee_gripper(r = {0.027575, 0, 0}, rpy = {0, 0, 0}) "URDF joint ee_gripper (fixed): fingers_link -> ee_gripper_link"
    annotation (Placement(transformation(origin={20, -900}, extent={{-10,-10},{10,10}})));
equation
  connect(frame_a, base_link.frame_a);
  connect(base_link.frame_a, j_waist.frame_a);
  connect(j_waist.frame_b, shoulder_link.frame_a);
  connect(q[1], j_waist.q);
  connect(qd[1], j_waist.qd);
  connect(qdd[1], j_waist.qdd);
  connect(shoulder_link.frame_a, j_shoulder.frame_a);
  connect(j_shoulder.frame_b, upper_arm_link.frame_a);
  connect(q[2], j_shoulder.q);
  connect(qd[2], j_shoulder.qd);
  connect(qdd[2], j_shoulder.qdd);
  connect(upper_arm_link.frame_a, j_elbow.frame_a);
  connect(j_elbow.frame_b, upper_forearm_link.frame_a);
  connect(q[3], j_elbow.q);
  connect(qd[3], j_elbow.qd);
  connect(qdd[3], j_elbow.qdd);
  connect(upper_forearm_link.frame_a, j_forearm_roll.frame_a);
  connect(j_forearm_roll.frame_b, lower_forearm_link.frame_a);
  connect(q[4], j_forearm_roll.q);
  connect(qd[4], j_forearm_roll.qd);
  connect(qdd[4], j_forearm_roll.qdd);
  connect(lower_forearm_link.frame_a, j_wrist_angle.frame_a);
  connect(j_wrist_angle.frame_b, wrist_link.frame_a);
  connect(q[5], j_wrist_angle.q);
  connect(qd[5], j_wrist_angle.qd);
  connect(qdd[5], j_wrist_angle.qdd);
  connect(wrist_link.frame_a, j_wrist_rotate.frame_a);
  connect(j_wrist_rotate.frame_b, gripper_link.frame_a);
  connect(q[6], j_wrist_rotate.q);
  connect(qd[6], j_wrist_rotate.qd);
  connect(qdd[6], j_wrist_rotate.qdd);
  connect(gripper_link.frame_a, j_gripper_handle.frame_a);
  connect(j_gripper_handle.frame_b, handle_link.frame_a);
  connect(gripper_link.frame_a, j_ee_arm.frame_a);
  connect(j_ee_arm.frame_b, ee_arm_link.frame_a);
  connect(ee_arm_link.frame_a, j_gripper.frame_a);
  connect(j_gripper.frame_b, gripper_prop_link.frame_a);
  connect(q[7], j_gripper.q);
  connect(qd[7], j_gripper.qd);
  connect(qdd[7], j_gripper.qdd);
  connect(ee_arm_link.frame_a, j_gripper_bar.frame_a);
  connect(j_gripper_bar.frame_b, gripper_bar_link.frame_a);
  connect(gripper_bar_link.frame_a, j_ee_bar.frame_a);
  connect(j_ee_bar.frame_b, fingers_link.frame_a);
  connect(fingers_link.frame_a, j_left_finger.frame_a);
  connect(j_left_finger.frame_b, left_finger_link.frame_a);
  connect(q[8], j_left_finger.q);
  connect(qd[8], j_left_finger.qd);
  connect(qdd[8], j_left_finger.qdd);
  connect(fingers_link.frame_a, j_right_finger.frame_a);
  connect(j_right_finger.frame_b, right_finger_link.frame_a);
  // URDF mimic: right_finger = -1.0 * left_finger + 0
  j_right_finger.q = -1.0 * q[8] + 0;
  j_right_finger.qd = -1.0 * qd[8];
  j_right_finger.qdd = -1.0 * qdd[8];
  connect(fingers_link.frame_a, j_ee_gripper.frame_a);
  connect(j_ee_gripper.frame_b, ee_gripper_link.frame_a);
  annotation (
    Icon(graphics={Rectangle(extent={{-100,100},{100,-100}}, lineColor={0,0,0}, fillColor={255,255,255},
      fillPattern=FillPattern.Solid), Line(points={{-80,-80},{-40,0},{20,30},{60,70}}, thickness=1),
      Text(extent={{-150,150},{150,110}}, textString="%name", textColor={0,0,255})}),
    Diagram(coordinateSystem(extent={{-100,-1000},{100,200}})),
    Documentation(info="<html><p><b>ALOHA WidowX-250 6DOF (leader)</b>. Source: <code>aloha_wx250s.urdf.xacro</code> (Interbotix/interbotix_ros_manipulators@b66d5b9 (humble) interbotix_xsarm_descriptions), BSD-3-Clause.</p><p>Generated deterministically from <code>aloha_wx250s</code>:
15 links, 14 joints, 8 independently driven joints (1: waist, 2: shoulder, 3: elbow, 4: forearm_roll, 5: wrist_angle, 6: wrist_rotate, 7: gripper, 8: left_finger).</p></html>"));
end AlohaWX250s;
