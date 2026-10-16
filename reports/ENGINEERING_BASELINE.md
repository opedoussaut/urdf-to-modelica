# Preserved engineering baseline — 16 October 2026

Verified the existing files at `a909ce2` on `feat/aloha-baseline` **before feature implementation**, without regeneration. Full pre-change workspace backup (including ignored and untracked files): `E:/users/opt2.ai/NOVA/ai-kkh-preserved/20261016-082452`; 21,399 files, 1,850,126,941 bytes, manifest and Git bundle. The initial working tree was clean.

Machine-readable evidence: `reports/engineering_baseline.json`. Raw run: `runs/20261016-082555-preserved-baseline/` (ignored, retained locally). The report includes hashes of every existing Modelica source.

| Check | Measured result |
| --- | --- |
| Tools | OpenModelica 1.27.1, MSL 4.1.0 |
| Configuration | ALOHA 2: two follower arms; standalone leader checked separately |
| Assembly coverage | 29 links including world, 28 joints, 16 prescribed coordinates, 2 mimic joints |
| Equation balance | Assembly 8,194/8,194; RightArmReach 8,178/8,178 |
| Simulation | RightArmReach, 0–9 s, 450 intervals, 226 playback samples |
| OMC total / verification wall time | 11.773 s / 13.813 s |
| Independent URDF FK | 28 links × 25 samples; position error 7.2872e-14 m, rotation error 2.9290e-13 |
| Trajectory / mimic error | 0 / 0 |
| Position-limit violations / assertion warnings | 0 / 0 |
| Right end-effector path | 0.57466 m |

The runtime reports Euler with zero continuous dynamic states after symbolic elimination, despite the requested DASSL method. This is expected for prescribed motion, and must not be described as a validated dynamic controller.

This baseline establishes kinematic consistency of the generated model with its URDF. It does **not** establish hardware accuracy, contact/grasp physics, servo-control performance, load sharing, or motor/gear/friction fidelity. Reported efforts are ideal inverse-dynamics reactions under prescribed motion. Six source discrepancies remain, including URDF versus MJCF gripper geometry and a documented open position exceeding the URDF limit (trajectories clamp to URDF). Placeholder inertials are rendered massless. Leader placement is unknown, so it remains standalone.

The earlier PROJECT_STATUS described the superseded four-arm configuration. The previous latest reach report also pointed to a pytest temporary directory; this verification uses a durable run directory instead.
