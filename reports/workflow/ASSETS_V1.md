# Increment 3: governed Modelica knowledge collection v1 (2026-10-23)

This is the knowledge the **AI + Modelica assets** repair arm may consult. The **AI only** arm never receives it.
Module: `kkh/workflow/assets.py`; patterns: `kkh/workflow/patterns/*.md`; tests: `tests/test_workflow_assets.py`.
The measured numbers below are also in `assets_v1.json`. Nothing was downloaded.

## Sources
| Asset | Version (asked from OpenModelica) | Licence (read from the source) | Files | Scope |
|---|---|---|---|---|
| `msl-4.1.0` Modelica Standard Library | 4.1.0 | Modelica 3-Clause BSD | 582 | Mechanics/MultiBody (incl. Examples), Mechanics/Rotational, Mechanics/Translational, Blocks, Units, UsersGuide (Conventions, Connectors, Overview, ReleaseNotes) |
| `modelicareference-4.1.0` ModelicaReference | 4.1.0 | Modelica 3-Clause BSD | 1 | whole library |
| `project-patterns` | per pattern: commit `9e867d1` | project-internal (the repository has no licence file) | 5 | massless frame, joint-input units, URDF rpy rotation, prescribed motion, URDF mimic |

- **Library roots** come from OpenModelica (`getSourceFile`) and **versions** from `getVersion`. A library whose
  `package.mo` does not carry the Modelica 3-Clause BSD licence is refused. Every pattern must have front matter with
  source, commit and evidence.
- **Excluded by design**, asserted in code and tests: the URDFModelica library, `generated/` and `third_party/ref`.
- **Cache key:** `runs/workflow/assets/index-<hash>.json`, where the hash covers the source specs, the SHA-256 of every
  indexed file and the chunker code (`f61f…` for this build, recorded with the code hash in `assets_v1.json`).

## Chunks (measured)
**1 730 chunks**, one per class (short type definitions included). Each carries
`id, asset_id, version, licence, class, kind, source_path, line_start, line_end, file_sha256, text`.

| Asset / kind | Chunks |
|---|---|
| msl / type | 565 |
| msl / model | 399 |
| msl / block | 271 |
| msl / function | 221 |
| msl / package | 101 |
| msl / class | 72 |
| msl / connector | 27 |
| msl / record | 24 |
| modelicareference / class + package | 40 + 5 |
| project-patterns / pattern | 5 |

**Chunk text:**
- declaration lines with annotations removed;
- the description string;
- the `Documentation(info=…)` HTML as plain text, up to 1 500 characters;
- for `*.Examples.*` models, the equation section, plus up to 3 verbatim `connect(...) annotation(Line(...))`
  statements as graphical-annotation examples (123 chunks have them).

The structure scanner blanks string literals and comments first, so code quoted inside documentation (frequent in
ModelicaReference) is never mistaken for a class.

## Coverage gap found: graphical annotations
- **The gap:** ModelicaReference 4.1.0 has **no entry for `Placement`, `Line` or `Diagram`** (0 occurrences; its 166
  "Icon" hits are its own icon classes). The proposal assumed it documented them. These annotations are specified in
  the Modelica Language Specification (graphical annotations), which is not local.
- **v1 mitigation:** genuine MSL examples of drawn connections (the 123 chunks above).
- **Closing it fully:** add the specification (download, CC BY-SA 4.0), which needs your approval.

## Retrieval on the real Stage 2 findings (ALOHA follower; top hits as returned)
- **How retrieval works:**
  - query = finding category + check + message + entity name words + a fixed, documented term list per category;
  - BM25 via `kkh.convert.library_index`, ties broken by chunk id; identical queries give identical results (tested);
  - budget 6 000 characters, at most 5 chunks; MSL package headers (tables of contents) are skipped.

| Finding | Top chunks (score) | Assessment |
|---|---|---|
| D004, Stage 1: mimic recorded but not used (right finger) | `project-patterns:urdf-mimic` (42.7), `project-patterns:urdf-rpy-rotation` (17.9), `Translational.Examples.Utilities.SpringDamperNoRelativeStates` (17.3), `Rotational.…SpringDamperNoRelativeStates` (16.7), `Rotational.Components.Fixed` (14.6) | Relevant first hit; the rest is weak |
| D021, kinematics: right finger up to 52.9 mm from URDF FK | `project-patterns:urdf-mimic` (43.5), `MultiBody.Joints.Assemblies.JointRRR` (26.1), `MultiBody.Joints.Constraints.Spherical` (24.1) | Relevant first hit, without "mimic" appearing in the finding text; the other two are only loosely related |
| D019 / D020, finger position limit asserted at initialisation | `Blocks.Logical.AssertCondition` (21.7), `MultiBody.Examples.Elementary.InitSpringConstant` (21.5), `Blocks.Types.Init` (20.5), then `LimIntegrator` / `Hysteresis` / `Math.Mean` | **Weak**: generic initialisation and assert material; nothing addresses "test model starts a joint outside its URDF limits" |
| D023, 18 of 49 connections without `Line` | `Blocks.Examples.RealNetwork1` (21.7, contains verbatim `connect … annotation(Line(points=…))` examples), `ModelicaReference.Annotations.DynamicSelect` (20.4), `UsersGuide.ReleaseNotes.Version_3_0` (19.9), `Blocks.MathBoolean.Nand` (19.0) | One usable example; the rest is noise (see the gap above) |

## What this means for the experiment
- **No claim of benefit yet.** These are retrieval results, not repair results. Whether the retrieved material
  helps is measured in increment 5, with both arms on the same findings, and the outcome is reported whatever it is.
- **A fairness note to keep in mind when reading results:**
  - the `urdf-mimic` pattern describes how a URDF mimic is expressed in Modelica, so it is close to the fix for this
    robot's main natural defect;
  - it is a legitimate, validated project pattern (and the mission lists validated patterns as assets), but results on
    the mimic finding should be read with this in mind;
  - the seeded fault set (increment 4) should include defects that no pattern names directly.
- **Queries are deliberately simple** (no LLM rewriting), so retrieval stays deterministic and auditable. Improving
  them is a separate, measurable change.
