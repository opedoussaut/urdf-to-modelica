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
    doWhat: "On the start screen, choose our main target, the Westwood Robotics THEMIS humanoid, or one of the reference robots (Unitree G1, Berkeley Humanoid Lite, ALOHA 2 follower arm), each from its maker's own URDF and 3D mesh files, or upload your own URDF, then press Launch.",
    happens: "The file and every mesh it uses are fixed at a known version and fingerprinted (SHA-256), with their licence and source.",
    get: "One reference that every later step is compared against.",
    why: "If the input could change, no result could be reproduced or traced. Robots enter only as a URDF and its meshes, so the pipeline works for other robots too.",
    code: "kkh/workflow/stage1_convert.py",
  },
  {
    id: "compliance",
    n: 2,
    title: "URDF compliance",
    page: "repair",
    doWhat: "Nothing: the check runs before every conversion. If the robot is designed in SolidWorks, export the URDF with the free SolidWorks to URDF Exporter rather than writing it by hand.",
    happens:
      "The file is checked against the official URDF specification on the ROS wiki (required elements and attributes, joint types, limits on revolute and prismatic joints, number formats, colours, mimic references), against its tree rule (one root, one parent per link, no cycle, nothing disconnected), and against basic physics that the specification does not cover (positive masses, an inertia a real body can have, ordered limits, mesh files that exist). Every finding gives the line in the file and the rule it breaks.",
    get: "A verdict (compliant, compliant with warnings, physically implausible, not compliant). A file with any error is refused before conversion.",
    why: "A malformed or physically impossible file would otherwise surface later, disguised as a Modelica error, and waste the converter, the checks and the AI on a problem that is in the input. THEMIS's published file is refused as physically implausible (two thumb inertias rounded to zero; all 44 joints with zero limits, effort and velocity); the reference robots pass; 14 deliberate violations in the tests are each caught by the rule that names them. An engineer can still convert a refused file: the override is recorded.",
    code: "kkh/workflow/stage0_urdf.py",
  },
  {
    id: "convert",
    n: 3,
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
    n: 4,
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
    n: 5,
    title: "AI Repair Comparison",
    page: "repair",
    doWhat: "Choose a case (the natural findings or one of ten seeded faults) and compare the two AI methods side by side.",
    happens:
      "Two AI methods receive exactly the same package, findings and rules, with the same local model, settings and three attempts. AI only works from that alone. AI + Modelica knowledge also receives passages from the Modelica Standard Library, the language reference and project patterns, chosen for each finding, each with its source, version and licence, and must cite what it used. Every proposed edit is applied to an isolated copy.",
    get: "For each method: the edits, their explanations and cited sources, and the result after each attempt.",
    why: "The question is whether engineering knowledge measurably helps an AI repair a model. Identical conditions make the answer meaningful, and the experiment stays valid whichever method does better. The ten faults were frozen before any AI run.",
    code: "kkh/workflow/stage3_repair.py · faults.py · assets.py",
  },
  {
    id: "validate",
    n: 6,
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
    n: 7,
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
    n: 8,
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
  { title: "Every failure explained", text: "Wherever something fails (a check, a repair, a launch), a note opens on demand and says in simple terms what happened, why it matters and what usually fixes it, next to the system's own message." },
  { title: "People decide", text: "Every change is reviewed and every promotion approved by a person, with a record. Nothing is accepted automatically." },
];

/** Measured so far: dated, sourced, quoted from committed reports. */
export const MEASURED: { date: string; text: string; source: string }[] = [
  { date: "21 Oct 2026", text: "Earlier comparison on the ALOHA leader arm: the DLR converter was best; no model written from scratch by a local AI passed the completeness check. This is why AI now repairs instead of writing.", source: "reports/CONVERT_REVIEW_CAMPAIGN_2026-10-21.md" },
  { date: "23 Oct 2026", text: "ALOHA follower, conversion: reproducible (63 files byte-identical), 255 URDF values copied unchanged, 15 items flagged (finger mimic recorded but not used, ros2_control ignored, mesh paths rewritten).", source: "reports/workflow/STAGE1_ALOHA_VX300S.md" },
  { date: "23 Oct 2026", text: "OpenModelica check: loads, balanced (6 814 equations = unknowns), simulates, but not validated: right finger up to 52.9 mm off; both fingers start outside their limits; 18 of 49 robot connections have no drawn line.", source: "reports/workflow/STAGE2_ALOHA_VX300S.md" },
  { date: "26 Oct 2026", text: "Modelica knowledge collection v2: 3 036 passages, adding the Modelica Language Specification 3.7, the OpenModelica 1.27.1 error messages, the MSL 3 → 4 conversion rules and the OpenModelica User's Guide. On the frozen faults, the right source now comes first for an old MSL 3 name (F02), unbalanced equations (F08) and a singular initialization (F10).", source: "reports/workflow/ASSETS_V2.md" },
  { date: "23 Oct 2026", text: "Modelica knowledge collection v1: 1 730 passages from the Modelica Standard Library 4.1.0, ModelicaReference 4.1.0 and 5 project patterns, each with source, version and licence; nothing downloaded.", source: "reports/workflow/ASSETS_V1.md" },
  { date: "23 Oct 2026", text: "Ten seeded faults frozen before any AI run; all ten are caught by the OpenModelica checks. The AI Repair Comparison is running; its results will be reported as measured.", source: "kkh/workflow/faults.py (commit 7c8d735)" },
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
      ["Prompt (request)", "Everything the AI receives for one answer: rules, robot file, findings, model files and, for one method, reference passages. It is kept with every run."],
      ["Passage (chunk)", "One piece of the reference material, usually one library class, with its id, source file, line, version and licence."],
      ["Citation", "The ids of the passages the AI says it used for an edit; an id that was not given is flagged as invented."],
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

/** What the AI receives in the repair stage, where that knowledge comes from, and how the model uses it.
 * Every number is read from kkh/workflow/stage3_repair.py (SETTINGS, RULES, ASSETS_RULE) and reports/workflow/ASSETS_V1.md. */
export const AI_INPUTS: { what: string; aiOnly: boolean; aiAssets: boolean; detail: string }[] = [
  { what: "Repair rules", aiOnly: true, aiAssets: true, detail: "Six fixed rules: fix the findings; never delete parts, connections or checks; never change values that come from the robot file; keep the robot's structure; no cosmetic edits; small, exact edits, each explained." },
  { what: "The robot file (URDF)", aiOnly: true, aiAssets: true, detail: "The same URDF the converter used, without its 3D shapes. It is the only allowed source of physical values (masses, inertias, positions, limits)." },
  { what: "The findings to fix", aiOnly: true, aiAssets: true, detail: "Up to 8 errors and warnings from the OpenModelica check (errors first), each with its evidence. Drawing-only findings are left out for both arms." },
  { what: "The model files concerned", aiOnly: true, aiAssets: true, detail: "The main robot model, its test model, and the files and parameter records of the parts the findings name, up to about 26 000 characters." },
  { what: "Modelica reference material", aiOnly: false, aiAssets: true, detail: "Up to 3 short passages per finding (about 9 000 characters in total), each labelled with an id, its library, version, licence, file and line." },
  { what: "Its previous attempt", aiOnly: true, aiAssets: true, detail: "From the second attempt on: which edits applied, which failed and why, and the new check result. At most 3 attempts." },
];

export const AI_SOURCES: { name: string; version: string; licence: string; what: string }[] = [
  { name: "Modelica Standard Library", version: "4.1.0 (the version the studio simulates with)", licence: "Modelica 3-Clause BSD", what: "The building blocks the model is made of: MultiBody (bodies, joints, frames, with their examples), rotational and translational mechanics, signal blocks, units, and the library's user guide. 582 files." },
  { name: "ModelicaReference", version: "4.1.0", licence: "Modelica 3-Clause BSD", what: "The language reference: keywords, operators and annotations, with their meaning." },
  { name: "Project patterns", version: "commit 9e867d1", licence: "project-internal", what: "5 short notes, each validated in this project: URDF mimic joints, URDF roll-pitch-yaw rotations, massless frames, joint-input units, prescribed motion." },
  { name: "Modelica Language Specification", version: "3.7 (May 2026, the latest), pinned from the Modelica Association's repository", licence: "CC BY-SA 4.0", what: "The official rules of the language, one passage per section: syntax, connectors and connections, arrays, equations and initialization, units, and the graphical annotations (Placement, Line, Diagram). 568 passages." },
  { name: "OpenModelica error messages", version: "1.27.1 (the compiler the studio runs), from its source code", licence: "OSMC-PL 1.8 or AGPL 3", what: "Every message the compiler can print, with its kind and severity: 608 messages. The search can match a finding's exact error text to its explanation." },
  { name: "MSL 3 → 4 conversion rules", version: "shipped with MSL 4.1.0", licence: "Modelica 3-Clause BSD", what: "The library's own renaming table from version 3 to 4 (e.g. Modelica.SIunits → Modelica.Units.SI), grouped by package: 64 passages." },
  { name: "OpenModelica User's Guide", version: "1.27", licence: "OSMC-PL 1.8 or AGPL 3", what: "The chapters about solving, initialization, debugging, compiler flags, porting and the FAQ: 66 passages." },
];

export const AI_HOW: { title: string; text: string }[] = [
  { title: "1 · Cut into passages, once", text: "Each library class becomes one passage: its declarations, its description and its documentation (and, for examples, its equations). 3 036 passages in all (version 2 of the collection, 26 Oct 2026), each keeping its source, version, licence and line numbers." },
  { title: "2 · Search per finding, without AI", text: "For each finding, a keyword search (BM25, the ranking method used by classic search engines) looks for the passages whose words best match the finding's words, plus a fixed list of terms for its category. The same finding always returns the same passages." },
  { title: "3 · Put in the prompt", text: "The best passages are pasted into the request, labelled with their ids. The model does not learn or remember anything: it reads them for this request only, like an engineer opening a manual at the right page." },
  { title: "4 · The model proposes edits", text: "It returns small search-and-replace edits on the model files, each with a one-sentence reason, the findings it addresses and the ids of the passages it used. Invented ids are flagged." },
  { title: "5 · Checked, never trusted", text: "Each edit is applied to a copy, the full OpenModelica check runs again, and an integrity guard rejects any edit that deletes parts or changes robot values. Then a person decides." },
];

export const AI_EXAMPLE = {
  finding: "The right finger is up to 52.9 mm away from where the robot file puts it (ALOHA follower).",
  retrieved: "Top passage, found without the word \u201cmimic\u201d in the finding: the project pattern \u201cURDF mimic joint expressed as an equation on the mimicking joint\u201d (score 43.5), then two MultiBody joint classes that are only loosely related.",
  use: "The pattern explains that the right finger must follow the left one (right = \u22121 \u00d7 left), so the model can propose that relation instead of guessing; the multiplier itself must come from the robot file, never from the passage.",
};

export const AI_LIMITS: string[] = [
  "The “AI only” method receives everything except the reference material, so any difference between the two arms comes from that material.",
  "Retrieval is simple keyword search, deliberately: it is predictable and auditable, but sometimes weak (for a finger starting outside its limits, it returned only generic initialisation material).",
  "Some faults remain hard for any documentation: a missing semicolon or a misspelled class name returns only generic material, because the right answer is in the model itself, not in a manual.",
  "The MSL conversion rules are close to an answer key for one frozen fault (F02, an old MSL 3 name); results on F02 are reported separately.",
  "Reference passages never supply physical values: robot values come only from the URDF (rule 7).",
  "The model runs locally (Ollama); nothing is sent outside this computer, and nothing is used to train it.",
];
