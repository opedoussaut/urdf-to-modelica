# HT GEN7 PhysAI Studio — Step 5: retargeted follower attempt

*Engineering-Grounded Physical AI*

Status (17 Oct 2026): implemented and verified in the running studio with real OpenModelica runs. A follower attempt
is a **kinematic reference derived by computation**. It is not observed data, not collision-checked, has no contact
model and has no hardware registration behind it.

## Story

Leader demonstration on the shared table → **retarget** to the follower (world-frame IK) → derived recording (follower
joint space) → kinematic replay with the leader parked → **OpenModelica follower** tracks the same reference → the same
Level-1 task rule scores the demonstration, the kinematic attempt and the simulated attempt.

## What was implemented

* `kkh/domain/aloha/retarget.py`: every leader sample → leader URDF FK → display world (layout transform) → follower
  base → follower URDF IK. Constrained: gripper position in the world and the tilt of the approach axis from the vertical
  (pointing down for a grasp). Free: rotation about the vertical. On facing mounts, copying the full world orientation
  would make the follower point back at its own base. The first full-orientation attempt produced 180° errors and wrist
  flips; the grasp orientation about the vertical stays an open gate. Warm starts from the previous sample keep the
  joint path continuous. The finger transfers the normalised opening. The report covers per-sample position/tilt error,
  intervals outside tolerance, velocity-limit samples, and follower vs leader peak joint speeds.
* Recordings now declare `reference_space` (`leader_joints`, the default, or `follower_joints`):
  * validation uses the matching URDF limits;
  * OpenModelica receives follower joints without the leader→follower mapping;
  * task evaluation uses follower FK in the scenario frame (and refuses to score a follower recording as the leader).
* `POST /api/workbench/trajectory/{id}/retarget` (background job): only shared-layout leader demonstrations are
  accepted (legacy-frame recordings and attempts are rejected with 422). It creates a new derived recording; the source
  is never modified.
* Semantic trace: the attempt is recorded with evidence status **kkh:Derived** and `prov:wasDerivedFrom` the source
  observation. Its task metrics are also Derived. The Knowledge Explorer shows it as *Derived · derived from “…”*.
* UI: **Create follower attempt (retarget)** under the task cards of a saved shared-table demonstration. The attempt
  replays with the leader parked at home and the follower driven by the derived reference. Status chip: *FOLLOWER
  ATTEMPT · leader parked*. The motion library shows *follower attempt (retargeted)*. Task cards: *Leader
  demonstration*, *Follower attempt (joint-mapped replay, no retargeting)*, *Follower attempt (retargeted, kinematic)*
  with a **derived** badge, and *Task on the OpenModelica follower* (simulated).

## Verified (17 Oct 2026, this machine, browser UI + OpenModelica)

| Evaluation of recording *Shared-table demonstration (Step 5)* | Result |
|---|---|
| Leader demonstration (observed commands) | completed · grasp 13.38 s · release 22.56 s · cube 0 mm from the B centre |
| Joint-mapped follower replay (no retargeting) | **not completed** · 1 missed grasp · cube 120 mm from the B centre |
| Retargeted follower attempt (derived, kinematic) | completed · 100 % of samples within 5 mm / 5° · cube 0 mm from the B centre |
| Retargeted attempt on the OpenModelica follower (revision `b4cc8de1`, accepted; six torque-driven axes) | **not completed / cannot be validated**: grasp 13.39 s, release 22.58 s, cube 6 mm from the B centre, but the end-effector point entered the cube in 13 samples; end-effector tracking RMS 68.8 mm, max 171.8 mm |

The last row is the engineering result of this step. With the assumed servo parameters, the torque-driven follower lags
the retargeted reference by centimetres while reaching across the table, and dips into the cube. That is a
model-sensitivity finding on assumed parameters, not a hardware prediction. Next is a proposal/validate/compare loop
on this attempt (servo gains, actuator lag) and/or a slower reference.

Tests: `tests/test_retarget.py` (6) — gripper path reproduced within tolerance, normalised opening transferred,
follower-limit validation, attempt cannot be re-retargeted or scored as leader, OpenModelica table uses follower
joints unmapped, API job + derived trace + 422 rejections. Full suite 106 passed; `npm run build` passes.

## Still closed

Collision (robot/table, leader/follower), grasp orientation about the vertical, 3D contact, hardware registration,
Above A/B, grasp automation, hardware motion. The OpenModelica follower model has no cube or contact.
