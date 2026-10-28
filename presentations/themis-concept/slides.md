---
theme: default
title: THEMIS, from robot file to trustworthy physics model
info: |
  HT GEN7 PhysAI Studio, concept presentation around Westwood Robotics THEMIS (TH02-A7).
  Every screen is a capture of the running studio; every number comes from a real run (see the last slide).
transition: slide-left
mdc: true
---

<div class="eyebrow">HT GEN7 PhysAI Studio · Engineering-Grounded Physical AI</div>

# THEMIS, from robot file<br/>to trustworthy physics model

<p class="lead">How we turn a humanoid's description file into a simulation an engineer can trust: a proven converter, measured checks, AI that only proposes, and a person who decides.</p>

<div class="kpi">
  <div><b>44</b><span>joints</span></div>
  <div><b>45</b><span>parts</span></div>
  <div><b>37.9 kg</b><span>total mass in the file</span></div>
  <div><b>100 %</b><span>local: no cloud, no invented numbers</span></div>
</div>

<div class="abs-br m-6 text-xs muted">Westwood Robotics THEMIS TH02-A7 · official URDF, Apache-2.0</div>

---

# The problem

A robot ships with a **description file (URDF)**: its parts, joints, masses and inertias. Before the robot moves, engineers want a **physics model** (Modelica) to simulate it.

<v-clicks>

- Writing that model by hand takes weeks and invites mistakes.
- Converters exist, but they **silently drop or rewrite** things.
- AI can write code fast, but a model that **runs** can still describe **another robot**.
- So the real question is not "can AI do it?", but **"how do we know the result is right?"**

</v-clicks>

<div class="box-blue mt-6"><b>In plain words:</b> we turn a robot's parts list into a simulation, and we <b>measure</b> whether it is faithful instead of trusting whoever produced it.</div>

---

# Why THEMIS

<div class="grid grid-cols-3 gap-3 text-sm">
<div class="box"><b>In production.</b> TH02-A7 is the THEMIS model Westwood builds today: 7-DoF arms, three-finger EN02 hands.</div>
<div class="box"><b>Official file.</b> Published by Westwood Robotics, Apache-2.0, exported from SolidWorks.</div>
<div class="box"><b>Real and current.</b> Exactly the kind of robot file our customers bring.</div>
</div>

<div class="crop mt-3" style="--x:150;--y:445;--w:1140;--h:405"><img src="/shots/01_start.png" /></div>
<div class="cap">The studio's start screen: THEMIS as the main target, rendered from its own URDF and meshes.</div>

---

# The concept: one pipeline, every step measured

```mermaid {scale: 0.56}
flowchart LR
  A[THEMIS URDF<br/>+ 45 meshes<br/>hash-pinned] --> Z[0 · URDF compliance<br/>ROS specification,<br/>tree, physics]
  Z --> B[1 · Convert<br/>DLR URDFModelica<br/>no AI]
  B --> C[2 · OpenModelica check<br/>ordered, measured<br/>vs the robot file]
  C --> D1[3a · AI only]
  C --> D2[3b · AI + Modelica<br/>knowledge]
  D1 --> E[4 · Independent<br/>validation +<br/>integrity guard]
  D2 --> E
  E --> F[5 · Engineer<br/>review]
  F --> G[6 · Approval<br/>+ simulation]
```

<div class="grid grid-cols-3 gap-4 mt-4 text-sm">
<div class="box"><b>Converter writes.</b> DLR URDFModelica: reproducible, every value traceable to the file.</div>
<div class="box"><b>Measurement decides.</b> OpenModelica, URDF kinematics and MuJoCo torques: no opinion, only numbers.</div>
<div class="box"><b>AI proposes, people decide.</b> AI edits copies only; nothing is accepted without an engineer.</div>
</div>

---

# Step 0 · Is the file valid?

<div class="flex items-center gap-6 text-sm">
<div class="kpi" style="margin:0"><div><b class="text-red-600">2</b><span>errors</span></div><div><b class="text-orange-600">133</b><span>warnings</span></div></div>
<div class="box flex-1"><b>All 44 joints:</b> limits, effort and velocity left at 0 by the exporter. <b>Two thumbs:</b> inertia rounded to 0, impossible for a real body. Found in under a second, with the line and the rule.</div>
</div>

<div class="crop mt-3" style="--x:140;--y:580;--w:1160;--h:420"><img src="/shots/04_compliance.png" /></div>
<div class="cap">URDF compliance on THEMIS: verdict, plain-language note, counts per layer.</div>

---

# The engineer stays in charge

<div class="grid grid-cols-2 gap-3 text-sm">
<div class="box">A refused file can still be converted: <b>"Convert anyway (engineer override, recorded)"</b>, exactly as published, nothing corrected or invented.</div>
<div class="box">The refusal stays in the run. Live progress shows each real step: compliance (overridden), conversion in 3 s, OpenModelica check in about 3 min.</div>
</div>

<div class="crop mt-3" style="--x:150;--y:1265;--w:1140;--h:410"><img src="/shots/02_launch_progress.png" /></div>
<div class="cap">Launching THEMIS: live progress, with the override and its explanation.</div>

---

# Step 1 · Convert, without AI

<div class="flex items-center gap-6">
<div class="kpi" style="margin:0"><div><b>845/845</b><span>URDF values copied unchanged</span></div><div><b>45/44</b><span>parts / joints mapped</span></div><div><b>yes</b><span>reproducible</span></div></div>
<div class="box flex-1 text-sm"><b>DLR URDFModelica</b> (German Aerospace Center, Modelica Library Award 2025). Everything it drops or rewrites is listed.</div>
</div>

<div class="crop mt-3" style="--x:120;--y:430;--w:1200;--h:430"><img src="/shots/05_convert.png" /></div>
<div class="cap">The eight-step rail (red = a step that did not pass) and the conversion record.</div>

---

# Step 2 · OpenModelica check

<div class="grid grid-cols-3 gap-3 text-sm">
<div class="box"><b>Sound structure:</b> 25 600 equations = 25 600 unknowns; it simulates.</div>
<div class="box"><b>Not the robot yet:</b> motion and torques do not match the file; torque-limit warnings because every effort limit is 0.</div>
<div class="box-blue">Every failure: <b>"What went wrong, in simple terms"</b>: what, why it matters, what fixes it.</div>
</div>

<div class="crop mt-3" style="--x:140;--y:580;--w:1160;--h:390"><img src="/shots/06_check.png" /></div>
<div class="cap">THEMIS's verdict with its plain-language explanation.</div>

---

# Step 3 · AI Repair Comparison

<div class="grid grid-cols-2 gap-3 text-sm">
<div class="box"><b>Identical conditions:</b> same local model, seed, rules, findings and attempts. <b>AI only</b> against <b>AI + Modelica knowledge</b>.</div>
<div class="box"><b>Knowledge v2, 3 036 passages, all licensed:</b> Modelica Language Specification 3.7, OpenModelica error messages, MSL 4.1.0 and its 3→4 rules, OpenModelica guide, project patterns. Must be cited.</div>
</div>

<div class="crop mt-3" style="--x:140;--y:575;--w:1160;--h:410"><img src="/shots/07_repair_start.png" /></div>
<div class="cap">THEMIS's AI Repair Comparison running with qwen3-coder 30B, entirely on this laptop.</div>

---

# Step 4 · Checked, never trusted

<!-- REPAIR_RESULTS -->

<div class="grid grid-cols-2 gap-6 mt-4 text-sm">
<div class="box"><b>Independent validation:</b> the full OpenModelica check runs again on every candidate; findings are matched as resolved, remaining or new.</div>
<div class="box"><b>Integrity guard:</b> a "fix" that deletes a part, a connection or a check, or changes a value from the robot file, is rejected even if it compiles.</div>
</div>

---

# Steps 5–6 · The engineer decides

<div class="grid grid-cols-3 gap-4 mt-6">
<div class="box"><b>Review</b><br/>Keep or reject each proposed edit, amend by hand, re-check, open in OMEdit.</div>
<div class="box"><b>Approve</b><br/>Only a validated model, or one with a written justification and its open findings recorded.</div>
<div class="box"><b>Before &amp; after</b><br/>Download any version for OMEdit, or every version side by side with its changes (diff).</div>
</div>

<div class="box-blue mt-6">Nothing reaches the approved model without a person. Every decision is recorded with its author and reason.</div>

---

# Explore THEMIS in 3D

<div class="grid grid-cols-4 gap-3 text-xs">
<div class="box">Drawn from the <b>same file</b> that is converted.</div>
<div class="box">Every joint moves through the <b>test motion</b>, slow or real speed.</div>
<div class="box">Parts passing through each other turn <b>red</b>.</div>
<div class="box">Centre of mass; point at a part for its name, mass and joint.</div>
</div>

<div class="crop mt-3" style="--x:145;--y:1262;--w:1150;--h:438"><img src="/shots/11_explore_3d.png" /></div>
<div class="cap">THEMIS in the interactive 3D view.</div>

---

# Same pipeline, other robots

| Robot | Stage 0 | Converter → check | What the pipeline found |
|---|---|---|---|
| **THEMIS TH02-A7** | <span class="pill bad">implausible</span> | simulates, checks fail | zero joint limits and efforts, two impossible thumb inertias |
| Unitree G1 + Dex3-1 | <span class="pill ok">compliant</span> | simulates, checks fail | 43 joints, end to end in about 3 min |
| Berkeley Humanoid Lite | <span class="pill ok">compliant</span> | **fails at structure** | a **converter bug**: the `imu` sensor link written twice |
| ALOHA 2 follower arm | <span class="pill ok">compliant</span> | simulates, checks fail | finger "mimic" dropped by the converter: 52.9 mm off |

<div class="box-blue mt-6">The pipeline catches problems in the <b>vendor file</b> (THEMIS), in the <b>converter</b> (Berkeley, ALOHA) and in the <b>AI's repairs</b>: three different sources of error, one method.</div>

---

# Built for non-experts too

<div class="grid grid-cols-2 gap-6">
<div>

- A **Guide**: what you do, what happens, what you get, and why, for every step.
- **"What the AI receives"**: the exact request, its sources, and how the knowledge is used.
- Two levels of detail: **Overview** and **Engineering**.
- A **Physical AI Atlas** of the underlying ideas.

</div>
<div>

<div class="crop mt-3" style="--x:340;--y:135;--w:980;--h:660"><img src="/shots/10_guide.png" /></div>
<div class="cap">The Guide.</div>

</div>
</div>

---

# What THEMIS teaches us

<div class="grid grid-cols-2 gap-6 mt-4">
<div>

### For Westwood's file

- Enter real **joint limits, efforts and velocities** in the exporter: today all 44 are 0.
- Export inertias with **more precision**: two thumbs round to 0.
- Both are fixed **in the robot file**, not in the physics model.

</div>
<div>

### For our method

- A **compliance gate before conversion** catches vendor-file issues in under a second.
- The converter copied **845/845** values faithfully: the errors were already in the file.
- AI repair is measured, cited and guarded, **and a person decides**.

</div>
</div>

<div class="box-blue mt-6 text-lg"><b>Engineering-Grounded Physical AI:</b> AI can help build robot models, if every proposal is measured and an engineer has the last word.</div>

---

# What this shows, and what it does not

<div class="grid grid-cols-2 gap-6 mt-4">
<div class="box">

### Shows

- A traceable path from THEMIS's file to an approved model.
- Exactly where the file, the converter or an AI repair is wrong.
- That human approval is enforced, not optional.

</div>
<div class="box">

### Does not show

- That the model matches the **real robot**: motors, friction and controllers are not in the URDF; no hardware data.
- Balance, contact or walking: the test motion is a consistency check.
- A general ranking of AI models: one setting, these cases.

</div>
</div>

---

# Next steps

1. **Simulate** step with levels: drop under gravity → hold a pose (are THEMIS's motors strong enough?) → reach and place → fixed-base humanoid scenarios.
2. Share the Stage 0 findings with **Westwood Robotics** and re-run on their corrected file.
3. A **human review baseline** to compare with the two AI methods.
4. A frozen **fault set for THEMIS**, to measure AI repair on our main target.

---

# Sources

<div class="grid grid-cols-2 gap-6 text-xs">
<div>

**THEMIS**
- [Westwood Robotics THEMIS-Simulation-Model](https://github.com/Westwood-Robotics/THEMIS-Simulation-Model), commit `c955a30`, Apache-2.0 (README: TH02-A7 in mass production)
- [SolidWorks to URDF Exporter](https://wiki.ros.org/sw_urdf_exporter)

**Standards and tools**
- [URDF XML specification (ROS wiki)](https://wiki.ros.org/urdf/XML)
- [Modelica Language Specification 3.7](https://specification.modelica.org/maint/3.7/MLS.pdf) (CC BY-SA 4.0)
- [DLR URDFModelica](https://github.com/DLR-RM/urdfmodelica) (BSD-3, Library Award 2025)
- OpenModelica 1.27.1, MSL 4.1.0, MuJoCo 3.16, Ollama (local models)

</div>
<div>

**Our measurements** (this repository, branch `feat/urdf-repair-pipeline`)
- THEMIS run `themis-261028-011359` (forced, recorded): Stage 0, conversion, check
- THEMIS AI Repair Comparison with qwen3-coder 30B
- `reports/workflow/ASSETS_V2.md` (knowledge collection v2)
- Reference robots: runs `g1-261026-070842`, `bhl-261026-071445`, `aloha-261026-070516`

All screens are captures of the running studio (`capture.ps1`).

</div>
</div>
