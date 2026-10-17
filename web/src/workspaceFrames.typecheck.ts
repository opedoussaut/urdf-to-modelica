// Compile-time guard (checked by `tsc -b` in `npm run build`): frame mix-ups must not type-check.
// If any line below ever compiles, its @ts-expect-error becomes unused and the build fails.
import { layout, local, toLocal, toWorld, world } from "./workspaceFrames";

const l = layout("experimental_shared_table");
const followerPoint = local("follower", [0.469, 0.06, 0.02]);
const leaderPoint = local("leader", [0.469, -0.06, 0.02]);

toWorld(l, "follower", followerPoint); // correct use
toWorld(l, "leader", leaderPoint); // correct use
// @ts-expect-error a follower-local position cannot be converted as leader-local
toWorld(l, "leader", followerPoint);
// @ts-expect-error a raw array is not a world point
toLocal(l, "leader", [0, 0, 0.02]);
// @ts-expect-error a leader-local point is not a world point
toLocal(l, "follower", leaderPoint);
toLocal(l, "follower", world([0, -0.06, 0.02])); // correct use
