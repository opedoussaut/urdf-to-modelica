# Known limitations (16 October 2026)

## Engineering fidelity
* **Servo parameters are assumptions.** `Control/FollowerServoSettings.mo` (kp 40 N·m/rad, kd 4 N·m·s/rad, 30 ms
  torque lag, feed-forward 0) are illustrative defaults; no Dynamixel XM540/XM430 motor constants, gear ratios,
  firmware PID or latency were identified. Improvements are model sensitivities, not hardware predictions.
* URDF friction 0.1 / damping 0.1 are generic defaults; no backlash, compliance, payload or dual-servo load sharing.
* Gripper prop/finger linkage is undocumented: fingers remain prescribed in the dynamic follower.
* Leader↔follower relation is joint-name mapping with limit clamping; the side-by-side placement is for display only
  (no measured registration). Joint correspondence does not imply Cartesian equivalence.
* Recordings made by mouse drags contain near-step reference changes; maximum tracking error is then dominated by those
  steps (in the verified demo the max barely changes while RMS improves).

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
* OMEdit integration launches OMEdit on the working copy; edits come back via Refresh Changes → import/reject
  (unit-tested; the OMEdit GUI itself was not driven in automated tests).
* Only the head revision can be validated; comparing older revisions works but they cannot be re-validated in place.
* Revisions created before the Control package receive it as an extra recorded revision on first use (or, for
  simulation of an old revision, generator defaults are injected and recorded as such).
* Large Monaco chunk (~3 MB) slows the first load of the Modelica editor.
* Single local user; no authentication; loopback only.
