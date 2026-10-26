# Modelica knowledge collection v2 (2026-10-26)

Knowledge the **AI + Modelica knowledge** repair arm may consult; the **AI only** arm never receives it. Generated from `kkh.workflow.assets.build()` (manifest `bb7b87751e8bea4e`). Downloads approved by the user on 26 Oct 2026 and pinned in `config/public_sources.json`.

## Sources

| Asset | Version | Licence (verified from the source) | Passages |
|---|---|---|---|
| `msl-4.1.0` | 4.1.0 | Modelica 3-Clause BSD (https://modelica.org/licenses/modelica-3-clause-bsd) | 1680 |
| `modelicareference-4.1.0` | 4.1.0 | Modelica 3-Clause BSD (https://modelica.org/licenses/modelica-3-clause-bsd) | 45 |
| `project-patterns` | per pattern | project-internal (authored in this repository; the repository has no licence file) | 5 |
| `mls-3.7` | 3.7 | CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/) | 568 |
| `omc-errors-1.27.1` | 1.27.1 | OSMC-PL 1.8 or AGPL 3 (Open Source Modelica Consortium) | 608 |
| `msl-conversion-4.0.0` | 4.1.0 | Modelica 3-Clause BSD (https://modelica.org/licenses/modelica-3-clause-bsd) | 64 |
| `omc-guide-1.27` | 1.27 | OSMC-PL 1.8 or AGPL 3 (Open Source Modelica Consortium) | 66 |
| **total** | | | **3036** |

- **Pinned downloads:** Modelica Language Specification 3.7 (`modelica/ModelicaSpecification` tag v3.7, commit `b7361fa`, LaTeX chapters, CC BY-SA 4.0 per its LICENSE.md); OpenModelica 1.27.1 `OMCompiler/Compiler/Util/Error.mo` (tag v1.27.1, commit `4a7248c`, OSMC-PL 1.8 or AGPL 3). Shallow fetch: only the pinned commit and the listed files (415 kB and 2.8 MB).
- **Local, no download:** the MSL 3.2.3 -> 4.0.0 conversion script (part of MSL 4.1.0) and 9 pages of the OpenModelica User's Guide 1.27 (solving, debugger, simulation flags, FAQ, porting, compiler, backwards compatibility, technical details, command-line help).
- **Error catalog coverage:** 608 of the 618 messages in Error.mo are parsed (the rest use another format).
- **Still excluded by design:** the URDFModelica library, `generated/`, `third_party/ref`.

## Retrieval on real findings (ALOHA follower, frozen fault set v1; top 3 as returned)

| Case | Finding | Top passages |
|---|---|---|
| natural | link positions differ from URDF forward kinematics by up to 52.8813 mm (tolerance 1.0 mm); | `project-patterns:urdf-mimic` (49.4)<br>`msl-4.1.0:Modelica.Mechanics.MultiBody.Joints.Assemblies.JointRRR` (33.0)<br>`msl-4.1.0:Modelica.Mechanics.MultiBody.Joints.Constraints.Spherical` (31.0) |
| F01 | Missing token: SEMICOLON | `modelicareference-4.1.0:ModelicaReference.Annotations.missingInnerMessage` (11.8)<br>`omc-errors-1.27.1:LOAD_MODEL_ERROR` (11.3)<br>`omc-errors-1.27.1:MISSING_INNER_MESSAGE` (11.2) |
| F02 | Function Modelica.SIunits.Conversions.to_deg not found in scope Elbow. | `mls-3.7:conversion-rules#1` (34.2)<br>`msl-conversion-4.0.0:Modelica.SIunits.Conversions` (30.5)<br>`omc-errors-1.27.1:USES_MISSING_VERSION` (27.9) |
| F03 | Class Joints.Elbw not found in scope Aloha_vx300s. | `omc-errors-1.27.1:USES_MISSING_VERSION` (27.9)<br>`modelicareference-4.1.0:ModelicaReference.Annotations.version` (26.2)<br>`mls-3.7:version-handling#1` (26.0) |
| F07 | link positions differ from URDF forward kinematics by up to 79012.2021 mm (tolerance 1.0 m | `project-patterns:urdf-mimic` (49.4)<br>`msl-4.1.0:Modelica.Mechanics.MultiBody.Joints.Constraints.Spherical` (31.0)<br>`msl-4.1.0:Modelica.Mechanics.MultiBody.Joints.Constraints.Prismatic` (30.6) |
| F08 | An independent subset of the model has imbalanced number of equations (5520) and variables | `omc-errors-1.27.1:IMBALANCED_EQUATIONS` (46.2)<br>`mls-3.7:equation-operators-for-overconstrained-connection-based-equation-systems1` (21.7)<br>`mls-3.7:recommended-selection-of-start-values` (19.3) |
| F10 | Initialization problem is structural singular. Please, check the initial conditions. | `omc-errors-1.27.1:STRUCTURAL_SINGULAR_INITIAL_SYSTEM` (40.1)<br>`omc-guide-1.27:porting/incomplete-specification-of-initial-conditions` (31.7)<br>`omc-errors-1.27.1:MIXED_DETERMINED` (24.7) |

## Reading

- The new sources come first exactly where they apply: the MSL renames for an old MSL 3 name (F02), OpenModelica's own explanation of unbalanced equations (F08) and of a singular initialization, with the User's Guide and the specification section on initialization (F10).
- They do not help where the answer is in the model itself: a missing semicolon (F01) or a misspelled class name (F03).
- **Fairness:** the conversion rules are close to an answer key for F02; report F02 separately. Collection v2 differs from v1 used in the 23 Oct campaigns: compare the two arms only within one collection version, and re-run both arms when measuring with v2.
- These are retrieval results, not repair results; whether the AI uses the passages well is measured by the campaign.
