within ALOHA.Blocks;
block WaypointTrajectory "Smooth multi-axis waypoint trajectory with analytic q, qd, qdd (cosine blend)"
  extends Modelica.Blocks.Icons.Block;
  parameter Integer n = 1 "Number of axes";
  parameter Integer nWp = 2 "Number of waypoints";
  parameter Modelica.Units.SI.Time t_wp[nWp] "Waypoint times (strictly increasing)";
  parameter Real Q[nWp, n] "Waypoint positions (rows = waypoints)";
  Modelica.Blocks.Interfaces.RealOutput q[n] annotation (Placement(transformation(extent={{100,50},{120,70}})));
  Modelica.Blocks.Interfaces.RealOutput qd[n] annotation (Placement(transformation(extent={{100,-10},{120,10}})));
  Modelica.Blocks.Interfaces.RealOutput qdd[n] annotation (Placement(transformation(extent={{100,-70},{120,-50}})));
equation
  for j in 1:n loop
    q[j] = cosineBlend(time, t_wp, Q[:, j], 0);
    qd[j] = cosineBlend(time, t_wp, Q[:, j], 1);
    qdd[j] = cosineBlend(time, t_wp, Q[:, j], 2);
  end for;
  annotation (Documentation(info="<html><p>Between consecutive waypoints each axis follows
q(s) = Q<sub>k</sub> + (Q<sub>k+1</sub>-Q<sub>k</sub>)(1-cos &pi;s)/2, s = (t-t<sub>k</sub>)/T<sub>k</sub>.
Velocity is zero at every waypoint (C1 continuous); acceleration is analytic within each segment.
q, qd and qdd are exactly consistent, as required by the <code>Move</code> sources.</p></html>"));
end WaypointTrajectory;
