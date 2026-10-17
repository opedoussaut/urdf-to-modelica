/**
 * Shared studio workspace frames (single source: config/workspace/aloha2_display_layouts.json, also read by
 * kkh/engineering/workspace_frames.py).
 *
 * STUDIO_DISPLAY_WORLD: right-handed, +Z up, table top at z = 0. Each robot's URDF base frame is placed in it by a
 * yaw + translation. These are EXPERIMENTAL DISPLAY transforms, never hardware calibration.
 *
 * Points are branded with their frame, so a follower-local point cannot be converted as if it were leader-local
 * (see workspaceFrames.typecheck.ts). Pure math, no Three.js: unit-tested with `node --test`.
 */
import layouts from "../../config/workspace/aloha2_display_layouts.json" with { type: "json" };

export type Role = "leader" | "follower";
export type Vec3 = readonly [number, number, number];
export type WorldPoint = Vec3 & { readonly __frame: "world" };
export type LocalPoint<R extends Role> = Vec3 & { readonly __frame: R };
export type Base = { model: string; xyz: number[]; yaw: number };
export type Layout = {
  name: string;
  label: string;
  status: string;
  bases: Record<Role, Base>;
  table: { center_xy: number[]; size_xy: number[]; top_z: number };
  evidence: string;
  scenario: string;
};

export const LAYOUT_FILE = layouts as unknown as {
  default_layout: string;
  calibration: { hardware_registration: boolean };
  layouts: Record<string, Omit<Layout, "name">>;
};
export const LAYOUT_NAMES = Object.keys(LAYOUT_FILE.layouts);
export const DEFAULT_LAYOUT = LAYOUT_FILE.default_layout;

function finite(p: readonly number[], what: string) {
  if (p.length !== 3 || !p.every(Number.isFinite)) throw new Error(`${what}: expected three finite metre values`);
}

export function layout(name: string = DEFAULT_LAYOUT): Layout {
  const l = LAYOUT_FILE.layouts[name];
  if (!l) throw new Error(`Unknown display layout ${name}`);
  for (const role of ["leader", "follower"] as const) {
    finite(l.bases[role].xyz, `${name} ${role} base`);
    if (!Number.isFinite(l.bases[role].yaw)) throw new Error(`${name} ${role} base yaw must be finite`);
  }
  return { ...l, name };
}

/** Tag a display-world point (metres). */
export function world(p: readonly number[]): WorldPoint {
  finite(p, "world point");
  return [p[0], p[1], p[2]] as unknown as WorldPoint;
}

/** Tag a point in one robot's URDF base frame (metres). */
export function local<R extends Role>(role: R, p: readonly number[]): LocalPoint<R> {
  if (role !== "leader" && role !== "follower") throw new Error(`Unknown robot frame ${role}`);
  finite(p, `${role}-local point`);
  return [p[0], p[1], p[2]] as unknown as LocalPoint<R>;
}

export function toWorld<R extends Role>(l: Layout, role: R, p: LocalPoint<NoInfer<R>>): WorldPoint {
  const b = l.bases[role],
    c = Math.cos(b.yaw),
    s = Math.sin(b.yaw);
  return world([c * p[0] - s * p[1] + b.xyz[0], s * p[0] + c * p[1] + b.xyz[1], p[2] + b.xyz[2]]);
}

export function toLocal<R extends Role>(l: Layout, role: R, p: WorldPoint): LocalPoint<R> {
  const b = l.bases[role],
    c = Math.cos(b.yaw),
    s = Math.sin(b.yaw),
    dx = p[0] - b.xyz[0],
    dy = p[1] - b.xyz[1];
  return local(role, [c * dx + s * dy, -s * dx + c * dy, p[2] - b.xyz[2]]);
}

/** Base-frame link pose [x, y, z, qx, qy, qz, qw] (as returned by /api/workbench/pose) -> display world. */
export function poseToWorld(l: Layout, role: Role, pose: readonly number[]): number[] {
  const p = toWorld(l, role, local(role, pose.slice(0, 3)));
  const h = l.bases[role].yaw / 2,
    [zx, zy, zz, zw] = [0, 0, Math.sin(h), Math.cos(h)],
    [x, y, z, w] = pose.slice(3, 7);
  // Hamilton product q_yaw * q_local (x, y, z, w order)
  return [
    p[0],
    p[1],
    p[2],
    zw * x + zx * w + zy * z - zz * y,
    zw * y - zx * z + zy * w + zz * x,
    zw * z + zx * y - zy * x + zz * w,
    zw * w - zx * x - zy * y - zz * z,
  ];
}

/** Centre height of a cube resting on the table top. */
export function restingZ(l: Layout, cubeHeight: number): number {
  return l.table.top_z + cubeHeight / 2;
}

/** Display gates: the layout may be drawn; nothing that needs calibration, collision or contact is enabled. */
export const GATES = {
  display_layout_applied: true,
  position_ik_checked_offline: true,
  grasp_orientation_about_vertical: false,
  robot_table_collision: false,
  leader_follower_collision: false,
  physical_contact_3d: false,
  hardware_registration: false,
  enable_ab_shortcuts: false,
  grasp_automation: false,
  hardware_motion: false,
} as const;

export const EXPERIMENTAL_NOTICE =
  "Experimental layout — position IK only; orientation/collision/physical contact unverified";
