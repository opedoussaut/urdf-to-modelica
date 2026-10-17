# Step 4B — Shared workspace candidate generator

This step searches for two positions on a shared tabletop that are **position-only reachable** by both arms with the existing URDF inverse kinematics. It does **not** edit or authorize the interactive scene, generate physical contact, or calibrate mounts.

Requires Step 4 `kkh/engineering/workspace_registration.py` already installed.

```powershell
cd E:\users\opt2.ai\NOVA\ai-kkh-physicalai
.\.venv\Scripts\python.exe -m pytest tests/test_workspace_candidate.py -q
.\.venv\Scripts\python.exe -m kkh.engineering.workspace_candidate --output reports/workspace_candidate.json
Get-Content reports\workspace_candidate.json -Raw
```

The default visual offsets place the leader and follower almost a metre apart; a shared task may have **no feasible location**. That is a legitimate engineering result and must not be overridden with arbitrary geometry. When no position-only candidate exists, the next phase must propose and test explicit base rotations/translations, not relax IK errors or fake a reachable target.

Position-only IK is **not** proof of feasible gripper orientation, collision clearance, contact, or real robot mounting. No A/B shortcuts are enabled by this code. The search locations are not hardware measurements.
