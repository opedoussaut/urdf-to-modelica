# HT GEN7 PhysAI Studio — Step 3: ALOHA geometry alignment

**Scope:** source audit, not a change to live simulation. Modelica remains the primary engineering simulation tool; MuJoCo Menagerie is read-only reference evidence.

## Run the source comparison

From the project root in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_aloha_reference_audit.py -q
.\.venv\Scripts\python.exe -m kkh.engineering.aloha_reference_audit --output reports/aloha_reference_alignment.json
```

If `status` is `reference_not_available`, the pinned Menagerie files have not been downloaded at the expected `third_party/mujoco_menagerie/aloha` path. The existing `config/public_sources.json` pins Menagerie revision `62ab00f2bc44f6f20c1c9b7a13f3fb1dd41a4e35`, under BSD-3-Clause. Use the existing project source-fetch workflow or supply `--mjcf` and `--scene` paths. Do not pull an unpinned revision silently.

## Grounded engineering discrepancies

| Property | GEN7 follower URDF (`data/urdf/aloha_vx300s.urdf`) | Menagerie ALOHA MJCF | Decision |
|---|---|---|---|
| Left finger coordinate | 0.021–0.057 m, local axis (0,1,0) | physical displacement 0–0.041 m, local axis (0,0,-1) | Not directly comparable: coordinate origins/frames differ |
| Right finger | −0.057 to −0.021 m; mimic left × −1 | 0–0.041 m physical; coupling handled by MJCF constraints | Require verified mapping |
| Finger commanded travel | URDF gives physical joint limits | 0.002–0.037 m in MJCF | Never conflate physical and software bounds |
| Finger actuator | URDF has damping/friction, no calibrated servo gains | `kp=2000`, `kv=124`; MJCF semantics | Do not copy gains into Modelica |
| Contact | URDF triangle meshes and joint poses | Contact mesh and small fingertip markers | Need full local-to-world transforms and contact calibration |
| Workcell | GEN7 visual side-by-side offsets are not calibrated | Menagerie has two side-by-side follower mounts and a collision table | Our leader-facing-follower scene requires new base registration |

## Next gate before changing the scene

Identify the exact leader and follower world transforms, finger pad poses over joint travel, table top plane and cube task poses, **in one documented coordinate system**. Check physical reachability on both robots and use measured or properly sourced bounds. Only then connect collision/contact models to interactive control. Do not claim validated physical grasp based on this audit alone.
