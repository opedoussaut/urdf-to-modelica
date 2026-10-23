# Stage 1: deterministic conversion of the ALOHA 2 follower arm (2026-10-23)

This is the measured output of `PYTHONPATH=. python -m kkh.workflow.stage1_convert aloha_vx300s`. The full record is in
`stage1_aloha_vx300s.json`; the run folder (`runs/workflow/<id>/stage1/`) also keeps the converted package and the
full converter log. No AI and no correction is involved: the package is exactly what the converter produced.

## Input and tools
- **URDF:** `data/urdf/aloha_vx300s.urdf` (Interbotix xacro, expanded, BSD-3-Clause): 14 links, 13 joints (9 movable).
  The file and all 11 referenced mesh files are resolved and hashed (SHA-256) in the manifest.
- **Converter:** DLR URDFModelica @ `92541b6f`. The checkout HEAD equals the pin. Arguments, pre-processing T1
  (`/` → `_` in names), T2 (textures → flat colour) and relative root are recorded. It declares `Modelica 4.0.0`,
  which OpenModelica resolves to 4.1.0.
- **Versions:** Python 3.12.10, urdf_parser_py 0.0.4, OpenModelica v1.27.1.
- **Output:** 63 generated files, test model `URDFModelica.Examples.Aloha_vx300s.Aloha_vx300sTest`. Conversion takes
  about 1 s.

## Results
| Measure | Result |
|---|---|
| Reproducible (second conversion, all 63 files byte-identical) | **yes** |
| URDF links / joints mapped to a Modelica class, instance and parameter record | **14 / 14, 13 / 13** |
| URDF physical values compared with the generated parameter records (mass, CoM, inertia, origins, axes, limits, damping/friction, mimic) | **255** |
| Values that differ | **0**: the converter copies every URDF value unchanged |
| Unsupported / transformed / unused URDF content | **15 items** (below) |

### What the converter ignores, rewrites or records without using
- **`ros2_control` ignored** (warning). The converter logs `Unknown tag "ros2_control"`.
- **Mimic recorded but not used** (warning). `Joints/Right_fingerParams.mo` holds the URDF mimic (right finger =
  −1 × left finger), but `Joints/Right_finger.mo` never references `jointParams.mimic`, so the right finger moves on
  its own. The existing OpenModelica-scored test (`tests/test_convert.py`) already measures the resulting kinematic
  error on the right finger.
- **Visual mesh URIs rewritten** (warning, 11 links). `package://interbotix_xsarm_descriptions/meshes/…` becomes
  `package:_/…`, which no tool can resolve. `kkh/convert/export.py` repairs this for downloads.
- **Pre-processing T1, T2** (info). These are documented workarounds applied before conversion.

## What this stage does not establish
Matching record values show only that the converter **copied** the URDF correctly. Whether the model **uses** them
correctly (frames, wiring, mimic, dynamics) is for Stage 2: OpenModelica check, balance, simulation, and kinematic and
dynamic comparison with the URDF.
