within ALOHA.Arms;
model AlohaVX300s "ALOHA ViperX-300 6DOF arm (aloha_vx300s URDF)"
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
  ALOHA.Components.RigidLink base_link(hasInertia = true, m = 0.969034, r_CM = {-0.0534774, -0.000562575, 0.0205961}, I = [0.0017, -4.713e-05, 8.415e-05; -4.713e-05, 0.006024, 3.851e-06; 8.415e-05, 3.851e-06, 0.007162], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/base.stl", r_shape = {0, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link base_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, 180}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink shoulder_link(hasInertia = true, m = 0.798614, r_CM = {0.000259233, -3.3552e-06, 0.0116129}, I = [0.001138, 1e-09, -5.9568e-06; 1e-09, 0.0009388, -1.91e-08; -5.9568e-06, -1.91e-08, 0.001201], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/shoulder.stl", r_shape = {0, 0, -0.003}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link shoulder_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, 100}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink upper_arm_link(hasInertia = true, m = 0.792592, r_CM = {0.0206949, 4e-10, 0.226459}, I = [0.008937, 0, -0.001201; 0, 0.008925, 0; -0.001201, 0, 0.0009357], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/upper_arm.stl", r_shape = {0, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link upper_arm_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, 20}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink upper_forearm_link(hasInertia = true, m = 0.322228, r_CM = {0.105723, 0, 0}, I = [0.0001524, -1.883e-05, -8.4064e-06; -1.883e-05, 0.001342, 1.2564e-06; -8.4064e-06, 1.2564e-06, 0.001441], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/upper_forearm.stl", r_shape = {0, 0, 0}, lengthDirection = {1.0, 0, 0}, widthDirection = {0, 1.0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link upper_forearm_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -60}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink lower_forearm_link(hasInertia = true, m = 0.414823, r_CM = {0.0513477, 0.00680462, 0}, I = [0.0001753, 8.528e-05, 0; 8.528e-05, 0.0005269, 0; 0, 0, 0.0005911], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/lower_forearm.stl", r_shape = {0, 0, 0}, lengthDirection = {1.0, 0, 0}, widthDirection = {0, -1.0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link lower_forearm_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -140}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink wrist_link(hasInertia = true, m = 0.115395, r_CM = {0.046743, -7.6652e-06, 0.010565}, I = [4.514e-05, -1.95e-08, -4.2002e-06; -1.95e-08, 4.631e-05, 2.3e-09; -4.2002e-06, 2.3e-09, 5.27e-05], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/wrist.stl", r_shape = {0, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link wrist_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -220}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink gripper_link(hasInertia = true, m = 0.097666, r_CM = {0.023001, 0, 0.011523}, I = [2.436e-05, 0, -2.785e-07; 0, 3.268e-05, 0; -2.785e-07, 0, 2.119e-05], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/gripper.stl", r_shape = {-0.02, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link gripper_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -300}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink ee_arm_link(hasInertia = false, hasShape = false) "URDF link ee_arm_link (massless frame: URDF inertial is a placeholder)"
    annotation (Placement(transformation(origin={-40, -380}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink gripper_prop_link(hasInertia = true, m = 0.008009, r_CM = {0.002378, 2.85e-08, 0}, I = [4.2979e-06, 0, 0; 0, 2.0386e-06, 6.559e-07; 0, 6.559e-07, 2.3796e-06], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/gripper_prop.stl", r_shape = {-0.0685, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link gripper_prop_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -460}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink gripper_bar_link(hasInertia = true, m = 0.150986, r_CM = {0.006794, -4.272e-07, -0.000776}, I = [0.0003283, 1.2e-09, -1.7465e-06; 1.2e-09, 7.895e-05, 1.341e-07; -1.7465e-06, 1.341e-07, 0.0003095], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/gripper_bar.stl", r_shape = {-0.063, 0, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {-1.0, 0, 0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link gripper_bar_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -540}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink fingers_link(hasInertia = false, hasShape = false) "URDF link fingers_link (massless frame: URDF inertial is a placeholder)"
    annotation (Placement(transformation(origin={-40, -620}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink left_finger_link(hasInertia = true, m = 0.034796, r_CM = {0.017344, -0.0060692, 0}, I = [1.255e-05, 2.4004e-06, 0; 2.4004e-06, 2.433e-05, 0; 0, 0, 1.417e-05], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/gripper_finger.stl", r_shape = {-0.0404, -0.0575, 0}, lengthDirection = {0, -1.0, 0}, widthDirection = {0, 0, -1.0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link left_finger_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -700}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink right_finger_link(hasInertia = true, m = 0.034796, r_CM = {0.017344, 0.0060692, 0}, I = [1.255e-05, 2.4001e-06, 0; 2.4001e-06, 2.433e-05, 0; 0, 0, 1.417e-05], hasShape = true, shapeFile = "modelica://ALOHA/Resources/Meshes/aloha_vx300s/gripper_finger.stl", r_shape = {-0.0404, 0.0575, 0}, lengthDirection = {0, 1.0, 0}, widthDirection = {0, 0, 1.0}, meshScale = 0.001, color = {40, 40, 40}, animation = animation) "URDF link right_finger_link (URDF inertial)"
    annotation (Placement(transformation(origin={-40, -780}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RigidLink ee_gripper_link(hasInertia = false, hasShape = false) "URDF link ee_gripper_link (massless frame: URDF inertial is a placeholder)"
    annotation (Placement(transformation(origin={-40, -860}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RevoluteJoint j_waist(r = {0, 0, 0.079}, rpy = {0, 0, 0}, n = {0, 0, 1.0}, limited = true, q_min = -3.14158265359, q_max = 3.14158265359, qd_max = 3.14159265359, tau_max = 10.0) "URDF joint waist (revolute): base_link -> shoulder_link"
    annotation (Placement(transformation(origin={20, 140}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RevoluteJoint j_shoulder(r = {0, 0, 0.04805}, rpy = {0, 0, 0}, n = {0, 1.0, 0}, limited = true, q_min = -1.850049007114, q_max = 1.256637061436, qd_max = 3.14159265359, tau_max = 20.0) "URDF joint shoulder (revolute): shoulder_link -> upper_arm_link"
    annotation (Placement(transformation(origin={20, 60}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RevoluteJoint j_elbow(r = {0.05955, 0, 0.3}, rpy = {0, 0, 0}, n = {0, 1.0, 0}, limited = true, q_min = -1.762782544514, q_max = 1.605702911835, qd_max = 3.14159265359, tau_max = 15.0) "URDF joint elbow (revolute): upper_arm_link -> upper_forearm_link"
    annotation (Placement(transformation(origin={20, -20}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RevoluteJoint j_forearm_roll(r = {0.2, 0, 0}, rpy = {0, 0, 0}, n = {1.0, 0, 0}, limited = true, q_min = -3.14158265359, q_max = 3.14158265359, qd_max = 3.14159265359, tau_max = 2.0) "URDF joint forearm_roll (revolute): upper_forearm_link -> lower_forearm_link"
    annotation (Placement(transformation(origin={20, -100}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RevoluteJoint j_wrist_angle(r = {0.1, 0, 0}, rpy = {0, 0, 0}, n = {0, 1.0, 0}, limited = true, q_min = -1.867502299634, q_max = 2.234021442553, qd_max = 3.14159265359, tau_max = 5.0) "URDF joint wrist_angle (revolute): lower_forearm_link -> wrist_link"
    annotation (Placement(transformation(origin={20, -180}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RevoluteJoint j_wrist_rotate(r = {0.069744, 0, 0}, rpy = {0, 0, 0}, n = {1.0, 0, 0}, limited = true, q_min = -3.14158265359, q_max = 3.14158265359, qd_max = 3.14159265359, tau_max = 1.0) "URDF joint wrist_rotate (revolute): wrist_link -> gripper_link"
    annotation (Placement(transformation(origin={20, -260}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.FixedJoint j_ee_arm(r = {0.042825, 0, 0}, rpy = {0, 0, 0}) "URDF joint ee_arm (fixed): gripper_link -> ee_arm_link"
    annotation (Placement(transformation(origin={20, -340}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.RevoluteJoint j_gripper(r = {0.005675, 0, 0}, rpy = {0, 0, 0}, n = {1.0, 0, 0}, limited = false, qd_max = 3.14159265359, tau_max = 1.0) "URDF joint gripper (continuous): ee_arm_link -> gripper_prop_link"
    annotation (Placement(transformation(origin={20, -420}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.FixedJoint j_gripper_bar(r = {0, 0, 0}, rpy = {0, 0, 0}) "URDF joint gripper_bar (fixed): ee_arm_link -> gripper_bar_link"
    annotation (Placement(transformation(origin={20, -500}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.FixedJoint j_ee_bar(r = {0.025875, 0, 0}, rpy = {0, 0, 0}) "URDF joint ee_bar (fixed): gripper_bar_link -> fingers_link"
    annotation (Placement(transformation(origin={20, -580}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.PrismaticJoint j_left_finger(r = {0, 0, 0}, rpy = {0, 0, 0}, n = {0, 1.0, 0}, s_min = 0.021, s_max = 0.057, v_max = 1.0, f_max = 5.0) "URDF joint left_finger (prismatic): fingers_link -> left_finger_link"
    annotation (Placement(transformation(origin={20, -660}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.PrismaticJoint j_right_finger(r = {0, 0, 0}, rpy = {0, 0, 0}, n = {0, 1.0, 0}, s_min = -0.057, s_max = -0.021, v_max = 1.0, f_max = 5.0) "URDF joint right_finger (prismatic): fingers_link -> right_finger_link"
    annotation (Placement(transformation(origin={20, -740}, extent={{-10,-10},{10,10}})));
  ALOHA.Components.FixedJoint j_ee_gripper(r = {0.0385, 0, 0}, rpy = {0, 0, 0}) "URDF joint ee_gripper (fixed): fingers_link -> ee_gripper_link"
    annotation (Placement(transformation(origin={20, -820}, extent={{-10,-10},{10,10}})));
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
    Diagram(coordinateSystem(extent={{-100,-920},{100,200}})),
    Documentation(info="<html><p><b>ALOHA ViperX-300 6DOF</b>. Source: <code>aloha_vx300s.urdf.xacro</code> (Interbotix/interbotix_ros_manipulators@b66d5b905725 (humble) interbotix_xsarm_descriptions), BSD-3-Clause.</p><p>Generated deterministically from <code>aloha_vx300s</code>:
14 links, 13 joints, 8 independently driven joints (1: waist, 2: shoulder, 3: elbow, 4: forearm_roll, 5: wrist_angle, 6: wrist_rotate, 7: gripper, 8: left_finger).</p></html>"));
end AlohaVX300s;
