"""Additive, executable engineering architecture; never edits the frozen package.

The mechanical model reuses every source link, joint and connection. The servo law
is the existing demonstrator law, split into inspectable controller and actuator
blocks. Unknown transmission/contact effects are deliberately not synthesized.
"""
from __future__ import annotations

import re
from pathlib import Path

from kkh.domain.aloha import configuration as C


def place(x, y, w=20, h=16):
    return f'annotation(Placement(transformation(origin={{{x},{y}}},extent={{{{-{w},-{h}}},{{{w},{h}}}}})))'


def icon(label, color="37,99,235"):
    return ('Icon(coordinateSystem(extent={{-100,-100},{100,100}}),graphics={'
            f'Rectangle(extent={{{{-100,70}},{{100,-70}}}},lineColor={{{color}}},'
            'fillColor={242,247,252},fillPattern=FillPattern.Solid,radius=10),'
            f'Text(extent={{{{-95,40}},{{95,-40}}}},textString="{label}",textColor={{{color}}}),'
            'Text(extent={{-120,110},{120,80}},textString="%name",textColor={0,0,160})})')


def wire(a, b, points, color="0,0,127"):
    return f'  connect({a},{b}) annotation(Line(points={points},color={{{color}}},thickness=0.5));'


def extensions(directory: Path) -> dict[str, str]:
    """Return new files only. Existing arm mechanics/parameters remain untouched."""
    from .dynamics import JOINT_SOURCE
    from .robotics import JOINTS
    files = {}
    files['package.mo'] = '''within ALOHA2;
package Engineering "GEN7 engineering architecture: executable mechanics, servo, observations"
  extends Modelica.Icons.Package;
  annotation(Documentation(info="<html><p>Source-derived URDF mechanics; assumed servo dynamics.
  Navigate System → FollowerMechanics → j_shoulder → controller / actuator.
  Cube/contact physics, transmission ratios, backlash, compliance and payload remain unknown or unimplemented.
  Task outcomes are evaluated outside Modelica using the declared Level-1 visual rule.</p></html>"));
end Engineering;
'''
    files['JointController.mo'] = f'''within ALOHA2.Engineering;
block JointController "Assumed PD law; gains supplied by revision's servo settings"
  parameter Real kp(unit="N.m/rad")=40;
  parameter Real kd(unit="N.m.s/rad")=4;
  Modelica.Blocks.Interfaces.RealInput reference {place(-120,60,20,20)};
  Modelica.Blocks.Interfaces.RealInput velocityReference {place(-120,20,20,20)};
  Modelica.Blocks.Interfaces.RealInput position {place(-120,-20,20,20)};
  Modelica.Blocks.Interfaces.RealInput velocity {place(-120,-60,20,20)};
  Modelica.Blocks.Interfaces.RealInput feedforward {place(0,-100,20,20)};
  Modelica.Blocks.Interfaces.RealOutput demand {place(110,0,10,10)};
equation
  demand=kp*(reference-position)+kd*(velocityReference-velocity)+feedforward;
  annotation({icon('PD')},Diagram(coordinateSystem(extent={{{{-140,-120}},{{140,120}}}}),graphics={{
    Text(extent={{{{-100,60}},{{100,20}}}},textString="kp (q_ref - q) + kd (w_ref - w)",textColor={{37,99,235}}),
    Text(extent={{{{-100,0}},{{100,-40}}}},textString="+ inverse-dynamics feed-forward",textColor={{37,99,235}})}}));
end JointController;
'''
    files['TorqueActuator.mo'] = f'''within ALOHA2.Engineering;
block TorqueActuator "Effort saturation and assumed first-order torque response"
  parameter Modelica.Units.SI.Torque tau_max=1 "Source URDF effort cap";
  parameter Modelica.Units.SI.Time actuatorTime(min=0.005)=0.03 "Assumed; not identified";
  Modelica.Blocks.Interfaces.RealInput demand {place(-120,0,20,20)};
  Modelica.Blocks.Interfaces.RealOutput applied(start=0,fixed=true) {place(110,0,10,10)};
equation
  actuatorTime*der(applied)=min(tau_max,max(-tau_max,demand))-applied;
  annotation({icon('LIMIT | LAG')},Diagram(coordinateSystem(extent={{{{-140,-100}},{{140,100}}}}),graphics={{
    Text(extent={{{{-110,50}},{{110,10}}}},textString="URDF torque limit",textColor={{37,99,235}}),
    Text(extent={{{{-110,-10}},{{110,-50}}}},textString="Assumed first-order lag",textColor={{37,99,235}})}}));
end TorqueActuator;
'''
    joint = JOINT_SOURCE.replace('within ALOHA2.Components;', 'within ALOHA2.Engineering;')
    joint = joint.replace('model DynamicRevolute', 'model ServoJoint').replace('end DynamicRevolute;', 'end ServoJoint;')
    joint = joint.replace('  SI.Torque applied(start=0, fixed=true);', '  SI.Torque applied=actuator.applied;')
    joint = joint.replace('  SI.Torque demand;', '  SI.Torque demand=controller.demand;')
    joint = joint.replace('  Modelica.Blocks.Interfaces.RealInput q, qd, qdd, feedforward;',
        '\n'.join(f'  Modelica.Blocks.Interfaces.RealInput {name} {place(x,110,12,12)};'
                  for name,x in [('q',-100),('qd',-35),('qdd',35),('feedforward',100)]))
    joint = joint.replace('  Modelica.Mechanics.Rotational.Sources.Torque drive(useSupport=true);',
        f'  Modelica.Mechanics.Rotational.Sources.Torque drive(useSupport=true) {place(65,0,12,12)};\n'
        f'  ALOHA2.Engineering.JointController controller(kp=kp,kd=kd) {place(-75,25,24,20)};\n'
        f'  ALOHA2.Engineering.TorqueActuator actuator(tau_max=tau_max,actuatorTime=actuatorTime) {place(0,25,24,20)};')
    joint = joint.replace('animation=false);', f'animation=false) {place(-65,-70,16,16)};',1)
    joint = joint.replace('w(start=0, fixed=true));', f'w(start=0, fixed=true)) {place(65,-70,16,16)};')
    joint = joint.replace('  demand=kp*(q-phi)+kd*(qd-w)+feedforward;\n  actuatorTime*der(applied)=min(tau_max,max(-tau_max,demand))-applied;',
        '  controller.position=phi;\n  controller.velocity=w;\n'
        + wire('q','controller.reference','{{-100,110},{-120,110},{-120,37},{-104,37}}')+'\n'
        + wire('qd','controller.velocityReference','{{-35,110},{-110,110},{-110,29},{-104,29}}')+'\n'
        + wire('feedforward','controller.feedforward','{{100,110},{100,70},{-75,70},{-75,5}}')+'\n'
        + wire('controller.demand','actuator.demand','{{-49,25},{-29,25}}'))
    # Native physical paths: frame connectors follow MSL conventions, scalar signal paths are blue.
    replacements = {
      'connect(frame_a,origin.frame_a);':wire('frame_a','origin.frame_a','{{-100,0},{-140,0},{-140,-70},{-81,-70}}','95,95,95').strip(),
      'connect(origin.frame_b,joint.frame_a);':wire('origin.frame_b','joint.frame_a','{{-49,-70},{49,-70}}','95,95,95').strip(),
      'connect(joint.frame_b,frame_b);':wire('joint.frame_b','frame_b','{{81,-70},{140,-70},{140,0},{100,0}}','95,95,95').strip(),
      'connect(drive.flange,joint.axis);':wire('drive.flange','joint.axis','{{77,0},{90,0},{90,-54},{65,-54}}','0,0,0').strip(),
      'connect(drive.support,joint.support);':wire('drive.support','joint.support','{{65,-12},{65,-30},{55,-30},{55,-54}}','0,0,0').strip(),
    }
    for a,b in replacements.items():joint=joint.replace(a,b)
    joint=joint.replace('end ServoJoint;', f'  annotation({icon("SERVO JOINT")},Diagram(coordinateSystem(extent={{{{-160,-110}},{{160,130}}}})));\nend ServoJoint;')
    files['ServoJoint.mo']=joint
    arm=(directory/'Arms/AlohaVX300s.mo').read_text(encoding='utf-8')
    arm=arm.replace('within ALOHA2.Arms;', 'within ALOHA2.Engineering;').replace('model AlohaVX300s','model FollowerMechanics').replace('end AlohaVX300s;','end FollowerMechanics;')
    arm=arm.replace('equation\n',f'  ALOHA2.Control.FollowerServoSettings settings {place(-300,-130)};\n'
        f'  Modelica.Blocks.Interfaces.RealOutput actual[8] {place(365,-100,10,10)};\nequation\n',1)
    robot=C.arm_robot('aloha_vx300s')
    for name in JOINTS[:6]:
        j=robot.joints[name]
        arm=arm.replace(f'ALOHA2.Components.RevoluteJoint j_{name}(',
            f'ALOHA2.Engineering.ServoJoint j_{name}(q_start={C.start_vector()[JOINTS.index(name)]},'
            f'kp=settings.{name}.kp,kd=settings.{name}.kd,actuatorTime=settings.{name}.actuatorTime,'
            f'damping={j.damping or 0},friction={j.friction or 0},')
        arm=arm.replace('equation\n',f'equation\n  j_{name}.feedforward=0;\n',1)
    arm=arm.replace('equation\n','equation\n  actual={'+','.join(f'j_{n}.phi' for n in JOINTS[:7])+',j_left_finger.s};\n',1)
    # Layout preserves every declaration/connection and places the serial chain across two rows.
    from kkh.engineering.modelica_inspect import parse_class
    components=parse_class(directory/'Arms/AlohaVX300s.mo')['components']
    physical=[c for c in components if c['type'].startswith('ALOHA2.Components.')]
    positions={c['name']:(-300+(i%7)*100,70-(i//7)*80) for i,c in enumerate(physical)}
    for name,(x,y) in positions.items():
        pattern=r'(\b'+re.escape(name)+r'\(.*?annotation\s*\(Placement\(transformation\()origin=\{[^}]+\}'
        arm=re.sub(pattern,lambda m:m[1]+f'origin={{{x},{y}}}',arm,count=1,flags=re.S)
    def route(match):
        a,b=match[1],match[2];pa=positions.get(a.split('.')[0]);pb=positions.get(b.split('.')[0])
        if not pa or not pb:return match[0]
        x,y=pa;u,v=pb;mid=(x+u)/2
        points='{'+','.join('{'+str(px)+','+str(py)+'}' for px,py in [(x,y),(mid,y),(mid,v),(u,v)])+'}'
        return wire(a,b,points,'95,95,95').strip()
    arm=re.sub(r'connect\(([^,]+),\s*([^\)]+)\);',route,arm)
    arm=arm.replace('Diagram(coordinateSystem(extent={{-100,-920},{100,200}}))',
        'Diagram(coordinateSystem(extent={{-380,-300},{400,180}}),graphics={'
        'Text(extent={{-340,175},{340,140}},textString="Follower mechanics | URDF links + six torque-driven joints",textColor={37,99,235}),'
        'Text(extent={{-340,-250},{340,-280}},textString="Source inertias and gravity | assumed servo/friction | prescribed fingers",textColor={80,80,80})})')
    files['FollowerMechanics.mo']=arm
    files['Verification.mo']=f'''within ALOHA2.Engineering;
block Verification "Error observations; not physical sensors"
  Modelica.Blocks.Interfaces.RealInput reference[8] {place(-120,50,20,20)};
  Modelica.Blocks.Interfaces.RealInput actual[8] {place(-120,-50,20,20)};
  Modelica.Blocks.Interfaces.RealOutput error[8] {place(110,0,10,10)};
  Real integralSquaredError[6](each start=0,each fixed=true);
  Real rms[6];
equation
  error=actual-reference;
  der(integralSquaredError)=error[1:6].^2;
  rms=sqrt(integralSquaredError/max(time,1e-9));
  annotation({icon('ERROR | RMS')});
end Verification;
'''
    home=C.start_vector(); finish=home.copy();finish[1]+=.2
    rows=';'.join(','.join(str(v) for v in row) for row in [home,home,finish,home])
    files['System.mo']=f'''within ALOHA2.Engineering;
model System "Engineering reference experiment: source mechanics and assumed six-axis servos"
  inner Modelica.Mechanics.MultiBody.World world(n={{0,0,-1}},animateWorld=false,animateGravity=false) {place(-170,-70)};
  ALOHA2.Blocks.WaypointTrajectory reference(n=8,nWp=4,t_wp={{0,0.5,2,3.5}},Q=[{rows}]) {place(-170,60,30,24)};
  ALOHA2.Arms.AlohaWX250s leader(animation=false) {place(-50,-70,30,24)};
  ALOHA2.Engineering.FollowerMechanics follower(animation=false) {place(-35,60,35,28)};
  ALOHA2.Engineering.Verification verification {place(130,60,32,24)};
equation
{wire('world.frame_b','leader.frame_a','{{-150,-70},{-80,-70}}','95,95,95')}
{wire('world.frame_b','follower.frame_a','{{-150,-70},{-110,-70},{-110,60},{-70,60}}','95,95,95')}
{wire('reference.q','follower.q','{{-137,74},{-100,74},{-100,105},{-56,105},{-56,94}}')}
{wire('reference.qd','follower.qd','{{-137,60},{-95,60},{-95,115},{-35,115},{-35,94}}')}
{wire('reference.qdd','follower.qdd','{{-137,46},{-90,46},{-90,125},{-14,125},{-14,94}}')}
{wire('reference.q','leader.q','{{-137,74},{-120,74},{-120,-20},{-68,-20},{-68,-41}}')}
{wire('reference.qd','leader.qd','{{-137,60},{-125,60},{-125,-15},{-50,-15},{-50,-41}}')}
{wire('reference.qdd','leader.qdd','{{-137,46},{-130,46},{-130,-10},{-32,-10},{-32,-41}}')}
{wire('reference.q','verification.reference','{{-137,74},{-115,74},{-115,140},{70,140},{70,72},{92,72}}')}
{wire('follower.actual','verification.actual','{{93,32},{110,32},{110,48},{92,48}}')}
  annotation({icon('ALOHA ENGINEERING')},experiment(StopTime=3.5,Interval=0.01,Tolerance=1e-6),
    Diagram(coordinateSystem(extent={{{{-230,-140}},{{220,190}}}}),graphics={{
      Text(extent={{{{-215,185}},{{210,155}}}},textString="GEN7 | ALOHA engineering reference",textColor={{37,99,235}}),
      Text(extent={{{{-100,-110}},{{200,-135}}}},textString="Leader: prescribed | Follower: six-axis dynamics",textColor={{80,80,80}})}}),
    Documentation(info="<html><p>This short analytic reference is a reproducible engineering check, not a human training recording.
    Saved human trajectories continue through RecordedFollower. Joint correspondence is illustrative; gripper remains prescribed.
    Gear ratio, backlash, compliance, payload and contact physics are unknown/unimplemented.</p></html>"));
end System;
'''
    files['package.order']='JointController\nTorqueActuator\nServoJoint\nFollowerMechanics\nVerification\nSystem\n'
    return {'Engineering/'+name:content for name,content in files.items()}


def install(directory):
    """Install once; caller enforces reviewed working-copy guards and snapshots."""
    if (directory/'Engineering/package.mo').exists():
        return False
    from .dynamics import ensure_control
    ensure_control(directory)
    for name,content in extensions(directory).items():
        file=directory/name;file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(content,encoding='utf-8')
    order=directory/'package.order'
    names=order.read_text().split()
    if 'Engineering' not in names:order.write_text('\n'.join([*names,'Engineering'])+'\n')
    return True
