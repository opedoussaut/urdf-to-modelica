within ALOHA.Components;
model RigidLink "URDF link: rigid body with optional source inertia and mesh visualisation"
  import SI = Modelica.Units.SI;
  Modelica.Mechanics.MultiBody.Interfaces.Frame_a frame_a "URDF link frame"
    annotation (Placement(transformation(extent={{-116,-16},{-84,16}})));
  parameter Boolean hasInertia = true "false = massless reference frame (URDF placeholder inertial)"
    annotation (Evaluate=true);
  parameter SI.Mass m = 0 "Mass (URDF inertial/mass)";
  parameter SI.Position r_CM[3] = {0, 0, 0} "Centre of mass in link frame (URDF inertial/origin/xyz)";
  parameter SI.Inertia I[3, 3] = zeros(3, 3)
    "Inertia about CM resolved in link frame (URDF tensor rotated by inertial/origin/rpy)";
  parameter Boolean hasShape = false "true if a source mesh is available" annotation (Evaluate=true);
  parameter String shapeFile = "" "Mesh URI (STL)";
  parameter SI.Position r_shape[3] = {0, 0, 0} "Mesh origin in link frame (URDF visual/origin/xyz)";
  parameter Real lengthDirection[3] = {1, 0, 0} "Mesh x-axis in link frame";
  parameter Real widthDirection[3] = {0, 1, 0} "Mesh y-axis in link frame";
  parameter Real meshScale = 1 "Mesh scale factor (URDF mesh/scale)";
  parameter Modelica.Mechanics.MultiBody.Types.Color color = {40, 40, 40};
  parameter Boolean animation = true "Enable mesh animation";
  Modelica.Mechanics.MultiBody.Parts.Body body(
    m = m, r_CM = r_CM,
    I_11 = I[1, 1], I_22 = I[2, 2], I_33 = I[3, 3], I_21 = I[2, 1], I_31 = I[3, 1], I_32 = I[3, 2],
    animation = false) if hasInertia
    annotation (Placement(transformation(extent={{-10,-10},{10,10}})));
  Modelica.Mechanics.MultiBody.Visualizers.FixedShape shape(
    shapeType = shapeFile, r_shape = r_shape, lengthDirection = lengthDirection,
    widthDirection = widthDirection, length = meshScale, width = meshScale, height = meshScale,
    color = color, animation = animation) if hasShape
    annotation (Placement(transformation(extent={{-10,30},{10,50}})));
equation
  if not hasInertia and not hasShape then
    // Massless, invisible reference frame: contributes no force/torque to the connection set.
    frame_a.f = zeros(3);
    frame_a.t = zeros(3);
  end if;
  connect(frame_a, body.frame_a);
  connect(frame_a, shape.frame_a);
  annotation (Icon(graphics={Rectangle(extent={{-100,30},{100,-30}}, fillColor={160,160,164},
    fillPattern=FillPattern.HorizontalCylinder, lineColor={0,0,0}),
    Text(extent={{-150,80},{150,40}}, textString="%name", textColor={0,0,255})}));
end RigidLink;
