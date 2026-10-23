/**
 * Guide (simplified studio): the engineering pipeline, the reasons behind it, and the words used.
 * Every fact is taken from the code and committed reports (docs/REPAIR_PIPELINE_PROPOSAL.md,
 * reports/workflow/STAGE1_/STAGE2_ALOHA_VX300S.md, ASSETS_V1.md, reports/CONVERT_REVIEW_CAMPAIGN_2026-10-21.md).
 * Measured results are dated; nothing here is a prediction.
 */
export type Step = {
  id: string;
  n: number;
  title: string;
  page: "repair";
  doWhat: string;
  happens: string;
  get: string;
  why: string;
  code?: string;
};

export const FLOW: Step[] = [
  {
    id: "input",
    n: 1,
    title: "URDF input",
    page: "repair",
    doWhat: "Start from the robot maker's own description file (URDF) and its 3D mesh files. The first robot is the ALOHA 2 follower arm.",
    happens: "The file and every mesh it uses are fixed at a known version and fingerprinted (SHA-256), with their licence and source.",
    get: "One reference that every later step is compared against.",
    why: "If the input could change, no result could be reproduced or traced. Robots enter only as a URDF and its meshes, so the pipeline works for other robots too.",
    code: "kkh/workflow/stage1_convert.py",
  },
  {
    id: "convert",
    n: 2,
    title: "Convert (no AI)",
    page: "repair",
    doWhat: "Nothing: the conversion is automatic.",
    happens:
      "The DLR URDFModelica converter, pinned at a fixed version, writes the Modelica package. The studio converts twice to prove the output is identical, maps every URDF link and joint to its Modelica component, compares every copied value with the URDF, and lists what the converter ignores or does not use.",
    get: "A reproducible Modelica package, a URDF → Modelica map, and a table of 255 values (ALOHA arm: all copied unchanged).",
    why: "A deterministic converter gives the same answer every time, so it is a fair, auditable starting point. In our earlier tests, no model written from scratch by a local AI passed the completeness check.",
    code: "kkh/workflow/stage1_convert.py · kkh/convert/urdfmodelica.py",
  },
  {
    id: "check",
    n: 3,
    title: "OpenModelica check",
    page: "repair",
    doWhat: "Read the findings: what is wrong, where, and how serious.",
    happens:
      "The unmodified package goes through ordered checks: load → structure → equation balance and translation → a 2 s simulation → agreement with the URDF (geometry under motion within 1 mm, axes, masses, inertias, joint torques against an independent MuJoCo reference) → every parameter value against the URDF. Diagram graphics are checked separately.",
    get: "A machine-readable list of findings, each with its step, category, severity, location and evidence, and a verdict.",
    why: "A model that compiles is not necessarily a correct robot. The ALOHA package compiles and simulates, yet the right finger ends up 52.9 mm from where the URDF puts it, because the converter drops the finger coupling (mimic).",
    code: "kkh/workflow/stage2_check.py",
  },
  {
    id: "repair",
    n: 4,
    title: "AI repair comparison",
    page: "repair",
    doWhat: "Choose a case (the natural findings or one of ten seeded faults) and compare the two AI methods side by side.",
    happens:
      "Two AI methods receive exactly the same package, findings and rules, with the same local model, settings and three attempts. AI only works from that alone. AI + Modelica assets also receives passages from the Modelica Standard Library, the language reference and project patterns, chosen for each finding, each with its source, version and licence, and must cite what it used. Every proposed edit is applied to an isolated copy.",
    get: "For each method: the edits, their explanations and cited sources, and the result after each attempt.",
    why: "The question is whether engineering knowledge measurably helps an AI repair a model. Identical conditions make the answer meaningful, and the experiment stays valid whichever method does better. The ten faults were frozen before any AI run.",
    code: "kkh/workflow/stage3_repair.py · faults.py · assets.py",
  },
  {
    id: "validate",
    n: 5,
    title: "Independent validation",
    page: "repair",
    doWhat: "Read each method's verdict: validated, improved, regressed, unchanged or rejected.",
    happens:
      "Each final candidate is checked again from scratch with the same OpenModelica checks. Findings resolved, remaining and new are counted. An integrity guard rejects “repairs” that delete parts, connections or assertions, change values taken from the URDF, or only touch the drawing.",
    get: "A comparison of the two methods per case and in total.",
    why: "An AI can make errors disappear by changing the problem. Only changes that keep the robot intact, and pass the same checks as everything else, count.",
    code: "kkh/workflow/stage4_validate.py",
  },
  {
    id: "review",
    n: 6,
    title: "Engineer review",
    page: "repair",
    doWhat: "Keep or reject each proposed change, amend a file by hand if needed, re-check, and open the model in OMEdit.",
    happens: "Kept changes are applied to a fresh copy of the original, so nothing unreviewed slips in. Every hand edit becomes a new version. Every action records who did it and why.",
    get: "A reviewed candidate with its own independent check result.",
    why: "AI explains, finds and proposes; a person decides. No AI can overwrite an approved model.",
    code: "kkh/workflow/review.py",
  },
  {
    id: "approve",
    n: 7,
    title: "Approved model & simulation",
    page: "repair",
    doWhat: "Approve (or reject) the candidate, then simulate it here or open it in OMEdit.",
    happens:
      "Approval normally requires a validated model; approving with open findings needs a written justification, which is recorded with them. The approved copy then gets a separate drawing pass that adds the missing connection lines, without changing anything else.",
    get: "An approved, traceable Modelica package that is readable in OMEdit, from the URDF fingerprint to the approver.",
    why: "Approval is an engineering decision with a record, not a side effect of a green check. Drawing quality is improved only after approval, so it never influences the comparison.",
    code: "kkh/workflow/review.py · layout.py",
  },
];

export const RATIONALE: { title: string; text: string }[] = [
  { title: "Converter first, AI second", text: "A deterministic converter writes the model; AI only repairs what the checks find. That keeps the starting point reproducible and the AI's contribution measurable." },
  { title: "Compiling is not validating", text: "OpenModelica accepting a model proves it is well formed. The pipeline also checks it against the robot file: geometry under motion, parameters and joint torques." },
  { title: "Independent references", text: "Geometry is compared with forward kinematics from the studio's own URDF reader, torques with MuJoCo inverse dynamics. Neither depends on the model being tested." },
  { title: "One difference only", text: "Both AI methods share the model, settings, inputs, rules and attempts. The only difference is the Modelica knowledge the second one receives." },
  { title: "Faults frozen in advance", text: "Ten known errors were written and committed before any AI run, so they could not be tuned to favour either method. Three are held out." },
  { title: "Provenance everywhere", text: "Every retrieved passage carries its source, version and licence; every finding its evidence; every approval its author and reason." },
  { title: "Honest outcomes", text: "A repair that makes the model fail earlier is “regressed”; one that changes the robot is “rejected”. A null result is still a result." },
  { title: "Local and private", text: "The language models run on this computer through Ollama; OpenModelica and MuJoCo run locally. No robot data leaves the machine." },
  { title: "People decide", text: "Every change is reviewed and every promotion approved by a person, with a record. Nothing is accepted automatically." },
];

/** Measured so far: dated, sourced, quoted from committed reports. */
export const MEASURED: { date: string; text: string; source: string }[] = [
  { date: "21 Oct 2026", text: "Earlier comparison on the ALOHA leader arm: the DLR converter was best; no model written from scratch by a local AI passed the completeness check. This is why AI now repairs instead of writing.", source: "reports/CONVERT_REVIEW_CAMPAIGN_2026-10-21.md" },
  { date: "23 Oct 2026", text: "ALOHA follower, conversion: reproducible (63 files byte-identical), 255 URDF values copied unchanged, 15 items flagged (finger mimic recorded but not used, ros2_control ignored, mesh paths rewritten).", source: "reports/workflow/STAGE1_ALOHA_VX300S.md" },
  { date: "23 Oct 2026", text: "OpenModelica check: loads, balanced (6 814 equations = unknowns), simulates, but not validated: right finger up to 52.9 mm off; both fingers start outside their limits; 18 of 49 robot connections have no drawn line.", source: "reports/workflow/STAGE2_ALOHA_VX300S.md" },
  { date: "23 Oct 2026", text: "Modelica knowledge collection: 1 730 passages from the Modelica Standard Library 4.1.0, ModelicaReference 4.1.0 and 5 project patterns, each with source, version and licence; nothing downloaded.", source: "reports/workflow/ASSETS_V1.md" },
  { date: "23 Oct 2026", text: "Ten seeded faults frozen before any AI run; all ten are caught by the OpenModelica checks. The AI repair comparison is running; its results will be reported as measured.", source: "kkh/workflow/faults.py (commit 7c8d735)" },
];

export const GLOSSARY: { group: string; terms: [string, string][] }[] = [
  {
    group: "The robot description",
    terms: [
      ["URDF", "Unified Robot Description Format: an XML file listing a robot's links, joints, masses, inertias, limits and meshes. The input of everything here."],
      ["xacro", "A macro language that generates URDF files; it is expanded to plain URDF before use."],
      ["Link", "A rigid part of the robot (a bone)."],
      ["Joint", "A connection between two links that allows motion: revolute (turns), prismatic (slides), continuous, or fixed."],
      ["Degree of freedom", "One independent way of moving; each moving joint adds one."],
      ["Mimic joint", "A joint whose position is defined by another joint (e.g. the right gripper finger mirrors the left)."],
      ["Mass, centre of mass, inertia", "How heavy a link is, where its weight is centred, and how hard it is to rotate."],
      ["Effort limit", "The largest force or torque a joint's motor may apply, from the URDF."],
      ["Mesh", "A 3D shape file (STL) used to draw a link; it does not affect the physics."],
      ["Pinned source", "A file fetched at a fixed commit, recorded with its checksum and licence, so results can be reproduced."],
    ],
  },
  {
    group: "Modelica and OpenModelica",
    terms: [
      ["Modelica", "An open, equation-based language for physical system models: you connect components like real parts and the tool solves the equations."],
      ["Modelica Standard Library (MSL)", "The free standard library of components (mechanics, electrics, control). Version 4.1.0 here."],
      ["MultiBody", "The MSL package for 3D mechanical systems: bodies, joints, frames, gravity."],
      ["OpenModelica", "The open-source tool that loads, checks, compiles and simulates Modelica models on this computer."],
      ["OMEdit", "OpenModelica's graphical editor, where a package can be opened, drawn and simulated."],
      ["Package / class", "A Modelica package groups classes; a class is a model, a block, a connector or a record of parameters."],
      ["connect / connector", "connect(a, b) joins two connectors (e.g. two mechanical frames), which generates the equations between them."],
      ["Balanced model", "As many equations as unknowns: a necessary condition for a model to be simulated."],
      ["Translation", "OpenModelica turning the model's equations into a program that can be simulated."],
      ["Placement / Line annotation", "Drawing information: where a component appears in the diagram and how a connection line is routed. Without it, OMEdit cannot draw the model properly."],
      ["Assertion", "A condition checked during simulation, e.g. “joint position over its limit”."],
    ],
  },
  {
    group: "Conversion and checking",
    terms: [
      ["URDFModelica", "A deterministic URDF → Modelica converter published by the German Aerospace Center (DLR), pinned at a fixed commit."],
      ["Deterministic", "Same input, same output, every time; no randomness and no AI."],
      ["Reproducible", "Running the conversion again gives byte-identical files (checked at Stage 1)."],
      ["Standard excitation", "A test motion that drives every joint through 80 % of its URDF range for 4 s, so geometry errors show."],
      ["Forward kinematics", "Computing where every part is from the joint angles, using the URDF. The studio's reference for geometry."],
      ["Inverse dynamics (MuJoCo)", "Computing the torques needed for a motion; MuJoCo provides an independent reference for the torque check."],
      ["Coverage", "The share of URDF links and moving joints found in the simulated model."],
      ["Tolerance", "How far a value may differ and still pass: 1 mm and 0.1° for geometry, 1 % for masses, 5 % of the effort limit for torques."],
      ["Finding / diagnostic", "One recorded problem, with its step, category, severity, location and evidence."],
      ["Validated", "In the new workflow: loads, balances, simulates and matches the URDF. Compiling alone does not count."],
    ],
  },
  {
    group: "AI and knowledge",
    terms: [
      ["Language model (LLM)", "A model that writes text or code. Here it always runs locally through Ollama (e.g. nemotron-3-nano 4B, qwen3-coder 30B)."],
      ["Seed, temperature", "Settings that make a language model's output repeatable: fixed seed 42, temperature 0."],
      ["Token budget", "How much the model may read and write; sized per robot and recorded with every run."],
      ["Repair round / attempt", "A new try after OpenModelica's real error messages are given back to the AI; limited and all recorded."],
      ["RAG (retrieval)", "Retrieval-augmented generation: relevant documents are looked up and added to the AI's prompt."],
      ["BM25", "A classic, deterministic keyword-search ranking used to find library classes; no download or embedding model."],
      ["Ontology", "A shared vocabulary with rules (what a joint, a limit or a unit is) that a computer can check."],
      ["Knowledge graph (GraphDB)", "The robot's facts stored with that vocabulary, each with its unit and source."],
      ["Provenance", "Where a fact or a piece of retrieved text comes from: file, version, licence."],
    ],
  },
  {
    group: "Reviews and evaluation",
    terms: [
      ["Seeded error (mutation)", "One deliberate error put into a copy of a correct model, so that the right answer is known."],
      ["Held-out set", "Seeded errors written only after the checking rules were frozen, so the rules cannot have been tuned to them."],
      ["Ground truth", "The known defects a review is scored against."],
      ["Recall", "The share of real defects a review found."],
      ["Precision", "The share of a review's reported issues that are real defects."],
      ["Brier score", "How well stated confidence matches reality (0 is perfect, 1 is worst)."],
      ["Integrity guard", "A check that rejects “repairs” that make a model compile by deleting parts or changing robot values."],
      ["Sim-to-real gap", "The difference between what a simulation predicts and what the real robot does: the reason every assumption is labelled."],
    ],
  },
];
