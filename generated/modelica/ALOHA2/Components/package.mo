within ALOHA2;
package Components "Generic link and joint components generated from URDF semantics"
  extends Modelica.Icons.Package;
  annotation (Documentation(info="<html><p>Reusable building blocks emitted by the KKH URDF-to-Modelica generator.
Each URDF <code>link</code> becomes a <code>RigidLink</code>; each URDF <code>joint</code> becomes a
<code>RevoluteJoint</code>, <code>PrismaticJoint</code> or <code>FixedJoint</code>.
URDF origins are applied with <code>FixedRotation</code> using the URDF roll-pitch-yaw convention
(extrinsic X-Y-Z, i.e. planar rotation sequence {3,2,1} with angles {yaw,pitch,roll}).</p></html>"));
end Components;
