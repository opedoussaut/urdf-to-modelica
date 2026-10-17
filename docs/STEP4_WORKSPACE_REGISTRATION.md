# Step 4 — Coordinate registration audit (diagnostic, not calibration)

This step detects the currently inconsistent task coordinate conventions. It makes **no changes** to the frozen Modelica models, robot scene, IK API, or GraphDB.

The current renderer applies `FOLLOWER_OFFSET = +0.45 m` and `LEADER_OFFSET = -0.50 m` only for presentation. The cube's initial follower-local position `[0.30, 0.12, 0.02] m` therefore displays at world X `0.75 m`; the same visible point is at leader-display-local X `1.25 m`. This is likely unreachable, and cannot be fixed by swapping IK endpoints alone.

## Install and verify

Extract this ZIP to your GEN7 project directory, then from that directory run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workspace_registration.py -q
.\.venv\Scripts\python.exe -m kkh.engineering.workspace_registration --output reports/workspace_registration.json
```

Review the report's `task_points`, `display_position_reachability`, and `engineering_gates`. A failing reachability gate is **good diagnostic information**: it must block automatic A/B moves, not be ignored.

## Next implementation step

Specify a reachable common tabletop layout using **explicit scene base transforms** (rotation and translation), verify both arms' IK and gripper orientations against the real URDF, and only then change the rendered mount poses and UI task coordinates. Physical mounting of a leader opposite a follower is a demonstrator assumption, **not measured ALOHA 2 hardware registration**. Following this, adapt task evaluation and Modelica contact inputs to this verified frame.
