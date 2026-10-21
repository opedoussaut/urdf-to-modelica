"""Write data/urdf/demo_two_link_arm.urdf: a small TEACHING robot for live demos (minutes instead of a quarter hour).

It is not a real product. Every value is defined here and derived openly: each part is a uniform solid box, inertia
about its centre of mass from the textbook formula I = m/12 (b^2 + c^2) per axis. Two revolute joints about y (pitch),
so gravity loads both joints and the torque check is meaningful.

    python tools/make_demo_robot.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "urdf" / "demo_two_link_arm.urdf"

# name: (size x, y, z in m, mass kg, centre of the box in the link frame, rgba)
PARTS = {
    "base_link": ((0.08, 0.08, 0.20), 2.0, (0.0, 0.0, 0.10), "0.35 0.38 0.42 1"),
    "upper_arm": ((0.30, 0.04, 0.04), 0.6, (0.15, 0.0, 0.0), "0.15 0.39 0.92 1"),
    "forearm": ((0.25, 0.03, 0.03), 0.35, (0.125, 0.0, 0.0), "0.92 0.35 0.05 1"),
}
# name: (parent, child, origin xyz in the parent frame, lower, upper, effort N·m, velocity rad/s)
JOINTS = {
    "shoulder": ("base_link", "upper_arm", (0.0, 0.0, 0.20), -2.5, 2.5, 6.0, 3.14),
    "elbow": ("upper_arm", "forearm", (0.30, 0.0, 0.0), -2.5, 2.5, 3.0, 3.14),
}


def box_inertia(size, m):
    x, y, z = size
    return m / 12 * (y * y + z * z), m / 12 * (x * x + z * z), m / 12 * (x * x + y * y)


def fmt(v):
    return " ".join(f"{a:.6g}" for a in v)


def main():
    lines = ['<?xml version="1.0"?>',
             "<!-- Teaching robot for live demos of the HT GEN7 PhysAI Studio. Not a real product: all values are defined",
             "     in tools/make_demo_robot.py (uniform boxes, I = m/12 (b^2 + c^2)). Regenerate, do not hand-edit. -->",
             '<robot name="demo_two_link_arm">']
    for name, (size, m, c, rgba) in PARTS.items():
        ixx, iyy, izz = box_inertia(size, m)
        lines += [f'  <link name="{name}">',
                  "    <inertial>",
                  f'      <origin xyz="{fmt(c)}" rpy="0 0 0"/>',
                  f'      <mass value="{m:g}"/>',
                  f'      <inertia ixx="{ixx:.6g}" ixy="0" ixz="0" iyy="{iyy:.6g}" iyz="0" izz="{izz:.6g}"/>',
                  "    </inertial>",
                  "    <visual>",
                  f'      <origin xyz="{fmt(c)}" rpy="0 0 0"/>',
                  f'      <geometry><box size="{fmt(size)}"/></geometry>',
                  f'      <material name="{name}_colour"><color rgba="{rgba}"/></material>',
                  "    </visual>",
                  "  </link>"]
    for name, (parent, child, xyz, lo, hi, effort, vel) in JOINTS.items():
        lines += [f'  <joint name="{name}" type="revolute">',
                  f'    <parent link="{parent}"/>',
                  f'    <child link="{child}"/>',
                  f'    <origin xyz="{fmt(xyz)}" rpy="0 0 0"/>',
                  '    <axis xyz="0 1 0"/>',
                  f'    <limit lower="{lo:g}" upper="{hi:g}" effort="{effort:g}" velocity="{vel:g}"/>',
                  "  </joint>"]
    lines.append("</robot>")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
