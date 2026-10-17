# Modelica-first contact experiments (GEN7)

**Status: model authored, not yet numerically validated on the user's OpenModelica installation.**

The `GEN7Contact.CubeTableDrop` model is an **isolated vertical cube/table penalty-contact experiment**. It represents a falling cube's gravity, mass, centre height, incoming speed, unilateral normal reaction, damping and penetration. It intentionally excludes robot fingers, grasping, mesh collisions, friction and payload coupling. Its parameter values are assumptions, not identified ALOHA properties.

This package is separate from the frozen `generated/modelica/ALOHA2` baseline and introduces **no MuJoCo dependency**. It tests the feasibility and numerical behavior of a small contact model before it becomes part of a larger gripper/robot assembly.

From the project root, with OpenModelica `omc` on PATH:

```powershell
.\.venv\Scripts\python.exe -m kkh.engineering.contact_experiment --out runs\contact-experiment
```

Inspect `runs/contact-experiment/run.json` and `GEN7Contact.CubeTableDrop_res.csv`. Check that the cube initially falls, contact force is zero before impact and never tensile, penetration is bounded, and the cube settles near `cubeSide/2`. If the solver fails or contact oscillates, report the result rather than changing parameters to achieve a cosmetically successful animation.

**Next engineering gate:** numerically validate vertical contact, then introduce two-finger contact geometry and tangential friction, verify force closure and stable grasp/release in isolation, and *only then* connect this physical state to the shared tabletop UI. The React cube animation must not be labeled a physics simulation until driven by verified simulation outputs. A realtime interactive backend is a separate performance/reliability decision.
