within ALOHA.Experiments;
model FollowerRightReach "Right follower reach and grasp"
  extends Modelica.Icons.Example;
  inner Modelica.Mechanics.MultiBody.World world(n = {0, 0, -1}, axisLength = 0.2, animateGravity = false)
    annotation (Placement(transformation(extent={{-80,-10},{-60,10}})));
  ALOHA.AlohaStationary aloha annotation (Placement(transformation(extent={{-10,-10},{10,10}})));
  ALOHA.Blocks.WaypointTrajectory trajectory(n = aloha.nq, nWp = 7,
    t_wp = {0, 1.0, 3.5, 4.5, 5.5, 8.0, 9.0},
    Q = [0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239;
      0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239;
      0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0.6, -0.3, 0.5, 0.5, 0.9, -0.6, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239;
      0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0.6, -0.3, 0.5, 0.5, 0.9, -0.6, 0, 0.057, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239;
      0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0.6, -0.3, 0.5, 0.5, 0.9, -0.6, 0, 0.044, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239;
      0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239;
      0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239, 0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239]) annotation (Placement(transformation(extent={{-40,40},{-20,60}})));
equation
  connect(world.frame_b, aloha.frame_a);
  connect(trajectory.q, aloha.q);
  connect(trajectory.qd, aloha.qd);
  connect(trajectory.qdd, aloha.qdd);
  annotation (experiment(StartTime = 0, StopTime = 9.0, Interval = 0.02, Tolerance = 1e-06),
    Documentation(info="<html><p>Right follower arm moves smoothly from START_ARM_POSE to a reach pose, opens the gripper (URDF upper finger limit), closes it to the documented ALOHA close position and returns. The other three arms hold the start pose.</p><p>Output interval 0.02 s = ALOHA control period DT
(aloha/constants.py). Prescribed motion: no actuator dynamics; joint torques are the inverse-dynamics
reaction torques of the URDF inertials under gravity.</p></html>"));
end FollowerRightReach;
