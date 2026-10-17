# Known limitations (16 October 2026)

## Engineering fidelity
* **Servo parameters are assumptions.** `Control/FollowerServoSettings.mo` (kp 40 N·m/rad, kd 4 N·m·s/rad, 30 ms
  torque lag, feed-forward 0) are illustrative defaults; no Dynamixel XM540/XM430 motor constants, gear ratios,
  firmware PID or latency were identified. Improvements are model sensitivities, not hardware predictions.
* URDF friction 0.1 / damping 0.1 are generic defaults; no backlash, compliance, payload or dual-servo load sharing.
* Gripper prop/finger linkage is undocumented: fingers remain prescribed in the dynamic follower.
* Leader↔follower relation is joint-name mapping with limit clamping; the side-by-side placement is for display only
  (no measured registration). Joint correspondence does not imply Cartesian equivalence.
* Recordings made by mouse drags before the rate limiter (recordings saved before 16 Oct 2026 evening, e.g. "Demo
  shoulder reference") contain near-step reference changes; maximum tracking error is then dominated by those steps.
  All operator commands now pass through a rate limiter (1.2 rad/s joints, 0.03 m/s gripper) before being recorded.

## Cube transfer scenario (Level 1 visual task)
* **Not physics.** The cube attaches to the follower fingertip when the leader gripper closes (normalised opening
  ≤ 0.30) within 6 cm of the cube, follows it rigidly, and drops vertically to the table when the gripper opens
  (≥ 0.60). No collision, contact, friction, grasp stability, slip, payload or finger geometry; orientation is ignored.
  The cube never influences the follower model. Rule and thresholds are declared in
  `config/scenarios/aloha2_cube_transfer.json` (version and SHA-256 are stored with every recording).
* Cube, table and target live in the follower base frame; the frame is a display convention, not a measured cell layout.
* The live cube in the browser and the backend evaluation use the same rule; **the saved task result is the backend
  computation** (the live view can miss a gripper transition only if the pose service lags; the backend never does).
* "Task on the OpenModelica follower" re-applies the same rule to the simulated follower joints. The gripper is not
  torque-driven there, so its opening is the recorded command. It shows how model tracking errors would change the
  task outcome *under this rule* — not how a real robot would grasp.
* Cartesian buttons (X/Y/Up/Down, Above A/B) solve follower IK within the shared leader/follower joint limits with the
  gripper pointing down (5 mm tolerance); outside the shared workspace the pose is left unchanged. **Drag leader end
  effector** moves the teal leader's marker in the camera plane using position-only leader IK, bounded joint steps
  and the same motion rate limiter. It does not preserve gripper orientation or guarantee Cartesian agreement with
  the differently sized follower. Use the follower Cartesian buttons for the guided cube task.
* Level 2 (rigid-body contact via a physics backend such as MuJoCo) is only an interface
  (`kkh/scenarios/physics.py`, no implementation). No Real-to-Sim calibration has been performed; recordings are
  leader commands from the UI, not physical robot measurements.

## Workspace layout (Step 4C, `docs/STEP4C_WORKSPACE_FRAMES.md`)
* Base poses come from `config/workspace/aloha2_display_layouts.json` and are **display transforms, not hardware
  registration**. The experimental shared table follows the ALOHA reference mounting convention (Menagerie, values
  only); deviations are listed in the file.
* Task points A/B were checked with URDF IK only (position < 5 mm, gripper pointing down < 5°). No collision checking
  (the joint-mirrored follower can swing into the leader's work area), no grasp orientation about the vertical, no
  contact. Above A/B, grasp automation and hardware motion stay disabled.
* On the shared table the follower attempt is a joint-space replay of the leader demonstration (no retargeting), so it
  does not reach the cube; its task result is shown as such.

## AI assistance
* Local models make mistakes: qwen3:4b may repeat current values as "proposals" (rejected as no-op) or misread
  metrics; qwen3:8b gives better structured proposals but takes ~2–4 min per paired question on the RTX A1000.
* Proposal checks are structural and policy checks (instance exists, numeric, changed, Modelica-declared bounds,
  only tunable design parameters). They do not establish engineering correctness — the simulation comparison does,
  for the recorded reference only.
* No measured evidence that GraphDB grounding improves answers (see `reports/DETECTION_RESULTS.md` and
  `reports/BENCHMARK_RESULTS.md`); the "with ontology" side adds traceable evidence, not proven accuracy.

## Application
* The Modelica "Physical diagram" is a connection graph from source structure/placements, not icon-level Modelica graphics.
* OMEdit integration loads the editable root `package.mo`; select the requested qualified class in its Libraries
  browser (the studio displays its name). Nested `.mo` files cannot be passed as independent top-level CLI files.
  Native GUI parameter editing and saving, diff detection, explicit import, compiler validation and simulation
  were exercised on an isolated verification model on 16 October 2026. This does not exhaustively test every
  native connection/component/annotation editing operation.
* Only the head revision can be validated; comparing older revisions works but they cannot be re-validated in place.
* Revisions created before the Control package receive it as an extra recorded revision on first use (or, for
  simulation of an old revision, generator defaults are injected and recorded as such).
* Large Monaco chunk (~3 MB) slows the first load of the Modelica editor.
* Single local user; no authentication; loopback only.
