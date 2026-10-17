// Run: node --test web/src/workspaceFrames.test.ts   (Node >= 22.18 strips TypeScript types natively)
import test from "node:test";
import assert from "node:assert/strict";
import { GATES, LAYOUT_NAMES, layout, local, poseToWorld, restingZ, toLocal, toWorld, world } from "./workspaceFrames.ts";

const near = (a: readonly number[], b: readonly number[], tol = 1e-9) =>
  a.forEach((v, i) => assert.ok(Math.abs(v - b[i]) <= tol, `${a} != ${b}`));

test("both layouts round-trip world <-> local for both arms", () => {
  for (const name of LAYOUT_NAMES) {
    const l = layout(name);
    for (const role of ["leader", "follower"] as const) {
      const p = world([0.123, -0.045, 0.02]);
      near(toWorld(l, role, toLocal(l, role, p)), p);
      const q = local(role, [0.3, 0.12, 0.02]);
      near(toLocal(l, role, toWorld(l, role, q)), q);
    }
  }
});

test("shared-table task points convert to the documented local coordinates", () => {
  const l = layout("experimental_shared_table");
  const A = world([0, -0.06, 0.02]),
    B = world([0, 0.06, 0.02]);
  near(toLocal(l, "leader", A), [0.469, -0.06, 0.02]);
  near(toLocal(l, "follower", A), [0.469, 0.06, 0.02]); // follower yawed by pi: Y flips
  near(toLocal(l, "leader", B), [0.469, 0.06, 0.02]);
  near(toLocal(l, "follower", B), [0.469, -0.06, 0.02]);
  // the same local coordinates are different world points for the two arms
  const leaderWorld = toWorld(l, "leader", local("leader", [0.469, 0.06, 0.02]));
  const followerWorld = toWorld(l, "follower", local("follower", [0.469, 0.06, 0.02]));
  near(leaderWorld, [0, 0.06, 0.02]);
  near(followerWorld, [0, -0.06, 0.02]);
});

test("legacy layout reproduces the historic display offsets", () => {
  const l = layout("legacy_side_by_side");
  near(toWorld(l, "follower", local("follower", [0.3, 0.12, 0.02])), [0.75, 0.12, 0.02]);
  near(toLocal(l, "leader", world([0.75, 0.12, 0.02])), [1.25, 0.12, 0.02]);
});

test("pose rotation follows the base yaw", () => {
  const l = layout("experimental_shared_table");
  // identity orientation at the follower base origin -> yawed by pi in the world
  near(poseToWorld(l, "follower", [0, 0, 0, 0, 0, 0, 1]), [0.469, 0, 0, 0, 0, 1, 0]);
  near(poseToWorld(l, "leader", [0.1, 0, 0.2, 0, 0, 0, 1]), [-0.369, 0, 0.2, 0, 0, 0, 1]);
});

test("cube rests on the table top and gates stay closed", () => {
  const l = layout("experimental_shared_table");
  assert.equal(restingZ(l, 0.04), 0.02);
  for (const key of ["hardware_registration", "enable_ab_shortcuts", "grasp_automation", "physical_contact_3d",
    "robot_table_collision", "leader_follower_collision", "grasp_orientation_about_vertical", "hardware_motion"] as const)
    assert.equal(GATES[key], false, key);
});

test("invalid points and unknown frames are rejected", () => {
  assert.throws(() => world([Number.NaN, 0, 0]));
  assert.throws(() => local("wrist" as "leader", [0, 0, 0]));
  assert.throws(() => layout("unknown"));
});
