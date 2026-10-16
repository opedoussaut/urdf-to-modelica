within ALOHA2.Control;
record ServoGains "Joint servo parameters of the follower (assumed, illustrative; not identified on hardware)"
  extends Modelica.Icons.Record;
  parameter Real kp(unit = "N.m/rad", min = 1, max = 500) = 40.0 "Proportional position gain";
  parameter Real kd(unit = "N.m.s/rad", min = 0, max = 80) = 4.0 "Derivative (velocity) gain";
  parameter Modelica.Units.SI.Time actuatorTime(min = 0.005, max = 0.3) = 0.03 "First-order torque lag of the actuator";
  parameter Real feedforward(unit = "1", min = 0, max = 1) = 0.0 "Inverse-dynamics feed-forward gain (0 off, 1 full)";
end ServoGains;
