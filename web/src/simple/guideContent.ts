/**
 * Guide (simplified studio): the flow, the reasons behind it, and the words used.
 * Every fact is taken from the code and committed reports (docs/SIMPLE_UI.md, docs/HANDOVER_2026-10-22.md,
 * reports/CONVERT_REVIEW_CAMPAIGN_2026-10-21.md, reports/workflow/STAGE1_/STAGE2_ALOHA_VX300S.md). Measured results
 * are dated; nothing here is a prediction.
 */
export type Step = {
  id: string;
  n: number;
  title: string;
  page: "convert" | "review";
  doWhat: string;
  happens: string;
  get: string;
  why: string;
  code?: string;
};

export const FLOW: Step[] = [
  {
    id: "robot",
    n: 1,
    title: "Choose a robot",
    page: "convert",
    doWhat: "Pick one of the pinned robots (SO-101 arm, Unitree G1, Berkeley Humanoid Lite, ALOHA 2 follower and leader) or upload your own URDF file.",
    happens: "The studio reads the robot description (URDF) and draws it in 3D from the maker's own mesh files. You can move the joints, see the centre of mass, and hover a part for its name, mass and joint.",
    get: "A robot whose every link, joint, mass and limit comes from a pinned, public source file, with its licence and commit.",
    why: "Everything that follows is compared against this one file. Pinning it (a fixed version, with a checksum) makes every later result reproducible and traceable.",
    code: "kkh/convert/sources.py · robot3d.py · RobotView.tsx",
  },
  {
    id: "convert",
    n: 2,
    title: "Convert it three ways",
    page: "convert",
    doWhat: "Choose the conversion methods and, for the AI methods, which local language models to use. Press Run.",
    happens:
      "The same URDF becomes a Modelica physics model in three ways, each in its own isolated folder: (1) AI only - a local model writes the model from the URDF; (2) AI + library search - the same, plus relevant Modelica Standard Library classes found by keyword search; (3) URDFModelica - the deterministic converter published by DLR, no AI.",
    get: "Up to three Modelica packages for the same robot, each with its attempts, tokens and timings recorded.",
    why: "A deterministic converter is the reference: it gives the same output every time. Running the AI methods under identical conditions (same model, seed 42, temperature 0, same budgets, same two repair rounds fed only by real OpenModelica messages) makes the comparison fair.",
    code: "kkh/convert/runner.py · llm.py · library_index.py · urdfmodelica.py",
  },
  {
    id: "checks",
    n: 3,
    title: "Eight measured checks",
    page: "convert",
    doWhat: "Watch each check turn green or red as OpenModelica and MuJoCo work, then read the result cards.",
    happens:
      "Each model goes through the same eight checks: produced → loads → checks (equations = unknowns) → simulates (2 s) → coverage (every URDF link and moving joint present) → geometry under motion (every joint driven through 80 % of its range; parts must stay within 1 mm and 0.1° of the URDF) → parameters (axes, masses, centres of mass, inertias) → dynamics (joint torques within 5 % of the effort limit against an independent MuJoCo reference).",
    get: "A completion score per method, with every check explained. Colours follow the score, not the rank: green only at 100 %.",
    why: "A model that compiles is not necessarily a correct robot. The four validity gates show that it runs; the four engineering checks show that it behaves like the URDF. Each number comes from a real run, never from an estimate.",
    code: "kkh/convert/score.py · excite.py · dynamics.py",
  },
  {
    id: "watch",
    n: 4,
    title: "Watch and download",
    page: "convert",
    doWhat: "Open “Watch the simulation” on a result, or download the package.",
    happens:
      "The stored OpenModelica run is replayed in 3D: solid parts where OpenModelica computed them, a grey ghost of the URDF at the same joint angles, and parts more than 1 mm off shown in red. The download includes the meshes and the exact test motion, ready for OMEdit.",
    get: "A visual explanation of what the numbers say, and a model you can open in OMEdit yourself.",
    why: "A score says that something is wrong; the replay shows where. Nothing is re-simulated for the replay: what you see is what was scored.",
    code: "kkh/convert/replay.py · export.py",
  },
  {
    id: "review",
    n: 5,
    title: "Review a model",
    page: "review",
    doWhat: "Choose a converted file, or a test file with one known error, and review it by hand, with AI, or with AI + ontologies.",
    happens:
      "Reviewers see the Modelica file, the cleaned URDF and OpenModelica's own messages, never the answer. The AI reviews return structured issues (entity, category, evidence, confidence, a proposed correction). The ontology mode adds facts from the knowledge graph (ALOHA arms only).",
    get: "A scored review: recall, precision, corrections that actually work when applied to a copy, claims checked against the URDF, and the Brier score of the stated confidence.",
    why: "To compare people and AI fairly, each review is scored against errors that are known in advance: either real conversion defects or a single seeded error. Corrections are tested by applying them to an isolated copy, never to the original.",
    code: "kkh/convert/review.py · review_score.py · Review.tsx",
  },
];

export const RATIONALE: { title: string; text: string }[] = [
  {
    title: "An engineering model, not an animation",
    text: "An animation replays positions. A Modelica model computes them from masses, axes, motors and gravity, so it can answer “what if?” and reveal errors that a picture hides.",
  },
  {
    title: "A deterministic baseline first",
    text: "The DLR URDFModelica converter gives the same output every time. It is the reference that any AI method has to beat, and the starting point for AI repair in the new workflow.",
  },
  {
    title: "Compiling is not validating",
    text: "OpenModelica accepting a model only proves it is well formed. The studio also checks it against the URDF: geometry under motion, physical parameters and joint torques. A model can compile and still put a finger 5 cm in the wrong place.",
  },
  {
    title: "Independent references",
    text: "Geometry is compared with forward kinematics computed by the studio's own URDF reader, and torques with MuJoCo inverse dynamics. Neither depends on the model being tested.",
  },
  {
    title: "Fair comparisons",
    text: "The AI methods share the same model, seed, temperature, budgets and repair rounds. The only difference between them is the extra knowledge the augmented method receives.",
  },
  {
    title: "Known answers for scoring",
    text: "Reviews are scored against defects known in advance (seeded errors, some held out until the rules were frozen), so recall and precision mean something.",
  },
  {
    title: "Honest signals",
    text: "Green only at 100 %. The best result of a run can still be red. Every result card says what the checks show and what they do not.",
  },
  {
    title: "Local and private",
    text: "Language models run on this computer through Ollama, and OpenModelica, MuJoCo and GraphDB run locally. No robot data leaves the machine.",
  },
  {
    title: "People decide",
    text: "AI explains, finds and proposes. Nothing it writes replaces an approved model without a person's review.",
  },
];

/** Measured so far: dated, sourced, quoted from committed reports. */
export const MEASURED: { date: string; text: string; source: string }[] = [
  { date: "21 Oct 2026", text: "ALOHA leader arm: URDFModelica is the best of the three methods. Its only defect is the unenforced finger mimic (right finger 34 mm off under motion). No AI-written file passed the completeness check.", source: "reports/CONVERT_REVIEW_CAMPAIGN_2026-10-21.md" },
  { date: "21 Oct 2026", text: "Reviews: qwen3-coder 30B located 9 of 16 seeded errors. Ontology grounding made the stated numbers more accurate but did not improve detection. The focused protocol (v2) halved the noise at the same recall and was 3.4× faster.", source: "reports/CONVERT_REVIEW_CAMPAIGN_2026-10-21.md" },
  { date: "22 Oct 2026", text: "SO-101 arm: URDFModelica passes 8/8 checks in 23 s.", source: "docs/HANDOVER_2026-10-22.md" },
  { date: "23 Oct 2026", text: "ALOHA follower, new workflow Stage 1: conversion reproducible (63 files byte-identical), 255 URDF values copied unchanged, 15 items flagged (mimic recorded but not used, ros2_control ignored, mesh paths rewritten).", source: "reports/workflow/STAGE1_ALOHA_VX300S.md" },
  { date: "23 Oct 2026", text: "Stage 2: the package loads, is balanced (6 814 equations = unknowns) and simulates, but is not validated: right finger up to 52.9 mm off; both fingers start outside their URDF limits; 18 of 49 robot connections have no drawn line.", source: "reports/workflow/STAGE2_ALOHA_VX300S.md" },
];

export type Stage = { title: string; text: string; status: "built" | "in progress" | "planned" };

/** The revised workflow (docs/REPAIR_PIPELINE_PROPOSAL.md): AI repairs the converter's output instead of writing it. */
export const NEXT: Stage[] = [
  { title: "URDF input", text: "The robot file and its meshes, pinned and hashed.", status: "built" },
  { title: "Convert", text: "DLR URDFModelica only, no AI, no corrections. Reproducibility, mapping and a field-by-field value table recorded.", status: "built" },
  { title: "OpenModelica check", text: "Ordered checks (load → structure → balance → simulation → URDF consistency, graphics apart) and a machine-readable list of findings.", status: "built" },
  { title: "AI repair comparison", text: "Two arms with identical inputs and settings: AI only, and AI + a governed collection of Modelica documentation and examples (with source, version and licence).", status: "in progress" },
  { title: "Independent validation", text: "The same checks on both candidates, plus a guard that rejects “fixes” that delete parts or change robot values.", status: "planned" },
  { title: "Engineer review", text: "Side-by-side diffs, the evidence behind each change, accept or reject edit by edit, open in OMEdit.", status: "planned" },
  { title: "Approved model & simulation", text: "Only a person promotes a model; then it is simulated from the studio or OMEdit.", status: "planned" },
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
