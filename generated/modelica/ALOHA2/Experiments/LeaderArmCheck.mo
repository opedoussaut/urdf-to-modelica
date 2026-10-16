within ALOHA2.Experiments;
model LeaderArmCheck "Leader arm check (standalone)"
  extends Modelica.Icons.Example;
  inner Modelica.Mechanics.MultiBody.World world(n = {0, 0, -1}, axisLength = 0.2, animateGravity = false)
    annotation (Placement(transformation(extent={{-80,-10},{-60,10}})));
  ALOHA2.Arms.AlohaWX250s aloha annotation (Placement(transformation(extent={{-10,-10},{10,10}})));
  ALOHA2.Blocks.WaypointTrajectory trajectory(n = aloha.nq, nWp = 5,
    t_wp = {0, 0.5, 2.5, 3.5, 5.5},
    Q = [0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239;
      0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239;
      -0.5, -0.4, 0.4, 0, 0.7, 0, 0, 0.02239;
      -0.5, -0.4, 0.4, 0, 0.7, 0, 0, 0.0323;
      0, -0.96, 1.16, 0, -0.3, 0, 0, 0.02239]) annotation (Placement(transformation(extent={{-40,40},{-20,60}})));
equation
  connect(world.frame_b, aloha.frame_a);
  connect(trajectory.q, aloha.q);
  connect(trajectory.qd, aloha.qd);
  connect(trajectory.qdd, aloha.qdd);
  annotation (experiment(StartTime = 0, StopTime = 6.0, Interval = 0.02, Tolerance = 1e-06),
    Documentation(info="<html><p>Standalone leader WidowX-250 arm: move from START_ARM_POSE, open the handle gripper, return.</p><p>Output interval 0.02 s = ALOHA control period
(aloha/constants.py DT). Prescribed motion, no actuator dynamics; joint efforts are the inverse-dynamics
reactions of the URDF inertials under gravity.</p></html>"));
end LeaderArmCheck;
