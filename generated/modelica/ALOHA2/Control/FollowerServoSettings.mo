within ALOHA2.Control;
model FollowerServoSettings "Servo settings of the follower arm, read by the dynamic follower experiment"
  parameter ALOHA2.Control.ServoGains waist(kp = 40.0, kd = 4.0, actuatorTime = 0.03, feedforward = 0.0) "Follower servo for URDF joint waist (XM540-W270, ID 1)";
  parameter ALOHA2.Control.ServoGains shoulder(kp = 40.0, kd = 4.0, actuatorTime = 0.03, feedforward = 0.0) "Follower servo for URDF joint shoulder (XM540-W270+XM540-W270, ID 2,3)";
  parameter ALOHA2.Control.ServoGains elbow(kp = 40.0, kd = 4.0, actuatorTime = 0.03, feedforward = 0.0) "Follower servo for URDF joint elbow (XM540-W270+XM540-W270, ID 4,5)";
  parameter ALOHA2.Control.ServoGains forearm_roll(kp = 40.0, kd = 4.0, actuatorTime = 0.03, feedforward = 0.0) "Follower servo for URDF joint forearm_roll (XM540-W270, ID 6)";
  parameter ALOHA2.Control.ServoGains wrist_angle(kp = 40.0, kd = 4.0, actuatorTime = 0.03, feedforward = 0.0) "Follower servo for URDF joint wrist_angle (XM540-W270, ID 7)";
  parameter ALOHA2.Control.ServoGains wrist_rotate(kp = 40.0, kd = 4.0, actuatorTime = 0.03, feedforward = 0.0) "Follower servo for URDF joint wrist_rotate (XM430-W350, ID 8)";
  annotation (Documentation(info="<html><p>One <code>ServoGains</code> instance per torque-driven follower joint.
Values are assumptions for illustration (no identified motor, transmission, friction or latency data is public);
edit them here, in the Modelica editor or OMEdit. The studio reads them from the revision being simulated.</p></html>"));
end FollowerServoSettings;
